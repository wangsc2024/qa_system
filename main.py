from fastapi import FastAPI, Request, Depends, HTTPException, status, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse
from app.routers import auth, questions, reports, export, users, roles, departments
from app.database import Base, engine, SessionLocal, get_db
from app.dependencies import get_current_user_optional, has_permission
from app.models.user import User
from app.models.department import Department
from app.models.role import Role
from sqlalchemy.orm import Session
from jose import JWTError, jwt
import os
from datetime import datetime, timedelta
import logging
from zeep import Client
from zeep.transports import Transport
from app.config import settings
import urllib.parse

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 確保目錄存在
os.makedirs('static', exist_ok=True)

# 創建資料表
Base.metadata.create_all(bind=engine)

# 創建初始管理員用戶
def create_admin_user():
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                email="admin@example.com",
                is_active=True
            )
            # 使用環境變數設定管理員密碼，禁止硬編碼（安全修復）
            admin_password = os.environ.get('QA_ADMIN_PASSWORD')
            if not admin_password:
                logger.warning('環境變數 QA_ADMIN_PASSWORD 未設定，請設定後重新啟動')
                logger.warning('使用方式: set QA_ADMIN_PASSWORD=您的安全密碼')
                # 產生隨機密碼作為臨時方案
                import secrets
                admin_password = secrets.token_urlsafe(16)
                logger.warning(f'已產生臨時隨機密碼（僅顯示一次）: {admin_password}')
            admin.set_password(admin_password)
            db.add(admin)
            db.commit()
            logger.info("已創建管理員用戶")
            
        # 確保管理員角色存在並有部門管理權限
        admin_role = db.query(Role).filter(Role.name == "管理員").first()
        if not admin_role:
            admin_role = Role(
                name="管理員",
                description="系統管理員",
                permissions=["manage_users", "manage_roles", "manage_departments", "view_questions", "create_question", "edit_question", "delete_question", "create_report", "view_reports", "export_questions", "export_reports"]
            )
            db.add(admin_role)
            db.commit()
            logger.info("已創建管理員角色")
            
        # 確保管理員用戶有管理員角色
        if admin_role not in admin.roles:
            admin.roles.append(admin_role)
            db.commit()
            logger.info("已為管理員分配角色")
    except Exception as e:
        logger.error(f"創建管理員用戶時出錯: {str(e)}")
    finally:
        db.close()

create_admin_user()
logger.info(f"啟動時間: {datetime.now()}")

app = FastAPI()

# FastAPI 不使用 config.from_object 方法，需要直接導入配置
from app.config import Config
# FastAPI 不使用 secret_key 屬性，而是在依賴項中使用 Config.SECRET_KEY

_allowed_origins = os.environ.get("QA_CORS_ORIGINS", "http://172.20.11.22:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 添加全局模板函數
templates.env.globals["has_permission"] = has_permission

# 可選的OAuth2方案
def optional_oauth2_scheme(request: Request):
    token = request.cookies.get("access_token")
    if token and token.startswith("Bearer "):
        return token.replace("Bearer ", "")
    return None

# 可選的當前使用者
def get_current_user_optional(db: Session = Depends(get_db), token: str = Depends(optional_oauth2_scheme)):
    if not token:
        return None
    try:
        from app.config import settings
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None
    user = db.query(User).filter(User.username == username).first()
    return user

# 包含路由器
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(questions.router, prefix="/questions", tags=["Questions"])
app.include_router(reports.router, prefix="/reports", tags=["Reports"])
app.include_router(export.router, prefix="/export", tags=["Export"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(roles.router, prefix="/roles", tags=["Roles"])
app.include_router(departments.router, prefix="/departments", tags=["departments"])

# 首頁
@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional)
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "current_user": current_user}
    )

# 登入頁面
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request}
    )

# 處理登入
@app.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    from app.routers.auth import login as auth_login
    try:
        return await auth_login(form_data, db)
    except HTTPException:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "帳號或密碼不正確"}
        )

# 登出
@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="access_token")
    return response

@app.get("/sso_login")
async def sso_login(request: Request, ssoToken1: str = None, db: Session = Depends(get_db)):
    try:
        artifact = ssoToken1
        if not artifact:
            return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

        logging.info(f"收到 SSO Token: {artifact}")

        # 使用 SOAP 呼叫 getUserProfile
        try:
            transport = Transport()
            client = Client(settings.SSO_SOAP_WS_URL, transport=transport)
            result = client.service.getUserProfile(artifact)
            logging.info(f"SOAP 呼叫結果: {result}")
            
            if result:  # 如果成功獲取用戶信息
                # 解析 XML 格式的 result
                from xml.etree import ElementTree as ET
                root = ET.fromstring(result)
                if root.tag == 'Error':
                    return RedirectResponse(url="/login?error=無法取得使用者資訊", status_code=status.HTTP_302_FOUND)
                
                # 讀取帳號及部門
                account = root.find('帳號').text
                original_dept_code = root.find('單位代碼').text
                bureau_code = original_dept_code[:2] + "00"  # 轉換為處層級代碼 (如 "02" -> "0200")
                full_name = root.find('姓名').text  # 讀取用戶姓名
                
                # 檢查部門是否存在，不存在則創建
                department = db.query(Department).filter(Department.code == bureau_code).first()
                if not department:
                    # 如果部門不存在，創建新部門
                    department_name = root.find('機關名稱').text if root.find('機關名稱') is not None else f"處{bureau_code}"
                    department = Department(
                        code=bureau_code,
                        name=department_name
                    )
                    db.add(department)
                    db.commit()
                    db.refresh(department)
                
                # 檢查用戶是否存在，不存在則創建
                user = db.query(User).filter(User.username == account).first()
                if not user:
                    # 獲取一般員工角色
                    employee_role = db.query(Role).filter(Role.name == "一般員工").first()
                    if not employee_role:
                        # 如果一般員工角色不存在，則創建
                        employee_role = Role(
                            name="一般員工",
                            description="一般員工角色",
                            permissions=["view_questions", "create_reports"]  # 設置基本權限
                        )
                        db.add(employee_role)
                        db.commit()
                        db.refresh(employee_role)
                    
                    # 創建新用戶並設置角色
                    user = User(
                        username=account,
                        full_name=full_name,  # 設置用戶全名
                        email=f"{account}@oa.pthg.gov.tw",  # 預設郵箱
                        department_id=department.id,  # 使用找到或創建的部門ID
                        role_id=employee_role.id,  # 設置一般員工角色
                        is_active=True
                    )
                    db.add(user)
                    db.commit()
                    db.refresh(user)
                    
                    # 添加到多對多關係
                    user.departments.append(department)
                    user.roles.append(employee_role)
                    db.commit()
                else:
                    # 更新現有用戶資訊
                    user.full_name = full_name
                    user.department_id = department.id
                    
                    # 確保用戶在多對多關係中有此部門
                    if department not in user.departments:
                        user.departments.append(department)
                    
                    # 確保用戶有一般員工角色
                    employee_role = db.query(Role).filter(Role.name == "一般員工").first()
                    if employee_role and employee_role not in user.roles:
                        user.roles.append(employee_role)
                    
                    db.commit()
                    db.refresh(user)
                
                # 創建 JWT token
                access_token = create_access_token(
                    data={"sub": account},
                    expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
                )
                
                response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
                response.set_cookie(
                    key="access_token",
                    value=f"Bearer {access_token}",
                    httponly=True,
                    secure=True,       # 僅 HTTPS 傳送（安全修復）
                    samesite="lax",    # 防 CSRF（安全修復）
                    max_age=1800
                )
                return response
                
            else:
                return RedirectResponse(url="/login?error=無法取得使用者資訊", status_code=status.HTTP_302_FOUND)
                
        except Exception as soap_error:
            logging.error(f"SOAP 呼叫失敗: {str(soap_error)}")
            return RedirectResponse(url="/login?error=SSO驗證服務暫時無法使用，請稍後再試", status_code=status.HTTP_302_FOUND)

    except Exception as e:
        logging.error(f"登入過程發生錯誤: {str(e)}")
        return RedirectResponse(url="/login?error=系統暫時無法處理您的請求，請稍後再試", status_code=status.HTTP_302_FOUND)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

@app.get("/ss/ss0/redirect.aspx")
async def sso_redirect(request: Request, nTarget: str = None):
    try:
        logging.info(f"收到 SSO 重定向請求: nTarget={nTarget}")
        
        # 構建重定向 URL
        redirect_url = f"http://172.20.11.22:8000/sso_login"
        
        # 重定向到 SSO 登入頁面
        return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
    except Exception as e:
        logging.error(f"SSO 重定向錯誤: {str(e)}")
        return RedirectResponse(url="/login?error=SSO重定向失敗", status_code=status.HTTP_302_FOUND)
