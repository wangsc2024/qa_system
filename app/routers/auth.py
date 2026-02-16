from fastapi import APIRouter, Depends, HTTPException, Request, Form, Response
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
from zeep import Client
import logging
import xml.etree.ElementTree as ET
from jose import jwt

from app.database import get_db
from app.models.user import User
from app.models.role import Role
from app.models.department import Department
from passlib.context import CryptContext
from app.dependencies import create_access_token, get_current_user
from app.config import settings
from app.templates import templates

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter()

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})

@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not user.verify_password(form_data.password):
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
    
    if not user.is_active:
        raise HTTPException(status_code=401, detail="帳號已停用")
    
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        secure=True,       # 僅 HTTPS 傳送（安全修復）
        samesite="lax",    # 防 CSRF（安全修復）
        max_age=1800,
        expires=1800,
    )
    return response

@router.get("/sso_login")
async def sso_login(
    request: Request,
    ssoToken1: Optional[str] = None,
    SAMLart: Optional[str] = None,
    db: Session = Depends(get_db)
):
    try:
        # 獲取SSO Token
        artifact = ssoToken1 or SAMLart
        if not artifact:
            return templates.TemplateResponse(
                "error.html", 
                {"request": request, "message": "錯誤：未收到 SSO Token，請重新登入"}
            )

        logger.info(f"收到 SSO Token: {artifact}")

        # 使用 SOAP 呼叫 getUserProfile
        try:
            client = Client(settings.SSO_SOAP_WS_URL)
            result = client.service.getUserProfile(artifact)
            logger.info(f"SOAP 呼叫結果: {result}")
            
            if result:
                # 解析 XML 格式的 result
                root = ET.fromstring(result)
                if root.tag == 'Error':
                    return templates.TemplateResponse(
                        "error.html",
                        {"request": request, "message": "無法取得使用者資訊"}
                    )
                
                # 讀取帳號及姓名
                account = root.find('帳號').text
                name = root.find('姓名').text
                unit_code = root.find('單位代碼').text if root.find('單位代碼') is not None else None
                logger.info(f"解析用戶信息: 帳號={account}, 姓名={name}, 單位代碼={unit_code}")
                
                # 檢查用戶是否存在，不存在則創建
                user = db.query(User).filter(User.username == account).first()
                if not user:
                    logger.info(f"創建新用戶: {account}")
                    # 創建新用戶
                    user = User(
                        username=account,
                        full_name=name,
                        email=f"{account}@oa.pthg.gov.tw",  # 預設郵箱
                        is_active=True
                    )
                    db.add(user)
                    
                    try:
                        # 先提交用戶創建
                        db.commit()
                        db.refresh(user)
                        logger.info(f"用戶 {account} 基本信息創建成功")
                        
                        # 設置用戶角色為一般員工
                        staff_role = db.query(Role).filter(Role.name == "一般員工").first()
                        if staff_role:
                            logger.info(f"設置用戶角色: {staff_role.name}")
                            # 使用原生 SQL 插入角色關聯
                            from sqlalchemy import text
                            db.execute(
                                text("INSERT INTO user_role (user_id, role_id) VALUES (:user_id, :role_id)"),
                                {"user_id": user.id, "role_id": staff_role.id}
                            )
                            db.commit()
                            logger.info(f"用戶 {account} 角色設置成功")
                        else:
                            logger.warning("找不到一般員工角色")
                        
                        # 根據單位代碼設置用戶部門
                        if unit_code:
                            department = db.query(Department).filter(Department.code == unit_code).first()
                            if department:
                                logger.info(f"設置用戶部門: {department.name} (代碼: {department.code})")
                                # 使用原生 SQL 插入部門關聯
                                db.execute(
                                    text("INSERT INTO user_department (user_id, department_id) VALUES (:user_id, :department_id)"),
                                    {"user_id": user.id, "department_id": department.id}
                                )
                                db.commit()
                                logger.info(f"用戶 {account} 部門設置成功")
                            else:
                                logger.warning(f"找不到單位代碼為 {unit_code} 的部門")
                    except Exception as db_error:
                        logger.error(f"數據庫操作失敗: {str(db_error)}")
                        db.rollback()
                        return templates.TemplateResponse(
                            "error.html",
                            {"request": request, "message": "用戶建立過程發生錯誤，請聯繫系統管理員"}
                        )
                elif unit_code:
                    logger.info(f"用戶 {account} 已存在，檢查部門設置")
                    # 如果用戶已存在但單位代碼有變更，更新用戶部門
                    department = db.query(Department).filter(Department.code == unit_code).first()
                    if department:
                        # 檢查用戶是否已經屬於該部門
                        user_dept = db.execute(
                            text("SELECT * FROM user_department WHERE user_id = :user_id AND department_id = :department_id"),
                            {"user_id": user.id, "department_id": department.id}
                        ).fetchone()
                        if not user_dept:
                            logger.info(f"更新用戶部門: {department.name} (代碼: {department.code})")
                            # 使用原生 SQL 插入部門關聯
                            db.execute(
                                text("INSERT INTO user_department (user_id, department_id) VALUES (:user_id, :department_id)"),
                                {"user_id": user.id, "department_id": department.id}
                            )
                            try:
                                db.commit()
                                logger.info(f"用戶 {account} 部門更新成功")
                            except Exception as db_error:
                                logger.error(f"數據庫操作失敗: {str(db_error)}")
                                db.rollback()
                                return templates.TemplateResponse(
                                    "error.html",
                                    {"request": request, "message": "部門資料更新失敗，請聯繫系統管理員"}
                                )
                        else:
                            logger.info(f"用戶已經屬於部門 {department.name}")
                    else:
                        logger.warning(f"找不到單位代碼為 {unit_code} 的部門")
                
                # 創建訪問令牌
                access_token = create_access_token(data={"sub": account})
                response = RedirectResponse(url="/", status_code=303)
                response.set_cookie(
                    key="access_token",
                    value=f"Bearer {access_token}",
                    httponly=True,
                    secure=True,       # 僅 HTTPS 傳送（安全修復）
                    samesite="lax",    # 防 CSRF（安全修復）
                    max_age=1800,
                    expires=1800,
                )
                return response
                
            else:
                return templates.TemplateResponse(
                    "error.html",
                    {"request": request, "message": "無法取得使用者資訊"}
                )
                
        except Exception as soap_error:
            logger.error(f"SOAP 呼叫失敗: {str(soap_error)}")
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "message": "SSO 驗證服務暫時無法使用，請稍後再試"}
            )

    except Exception as e:
        logger.error(f"登入過程發生錯誤: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "message": "系統暫時無法處理您的請求，請稍後再試"}
        )

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response
