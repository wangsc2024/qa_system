from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from sqlalchemy.orm import Session, joinedload
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta
from app.database import get_db
from app.models.user import User
from app.models.role import Role
from app.models.department import Department
from app.config import settings
import functools

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


def get_token_from_cookie(request: Request):
    token = request.cookies.get("access_token")
    if token and token.startswith("Bearer "):
        return token.replace("Bearer ", "")
    return None


# 自定義依賴來獲取當前請求，並檢查是否需要重定向
async def get_current_user_with_request(
    request: Request,
    db: Session = Depends(get_db)
):
    token = get_token_from_cookie(request)
    is_web_request = request.headers.get("accept", "").startswith("text/html")
    
    if not token:
        if is_web_request:
            return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="無效的認證憑證",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            if is_web_request:
                return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="無效的認證憑證",
                    headers={"WWW-Authenticate": "Bearer"},
                )
    except JWTError:
        if is_web_request:
            return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="無效的認證憑證",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    user = db.query(User).options(
        joinedload(User.roles),
        joinedload(User.departments)
    ).filter(User.username == username).first()
    
    if user is None:
        if is_web_request:
            return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="無效的認證憑證",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    return user


# 用於向後兼容的 get_current_user 函數
def get_current_user(db: Session = Depends(get_db), token: str = Depends(get_token_from_cookie)):
    """原始的獲取當前用戶函數，僅用於兼容現有代碼"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="無效的認證憑證",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        raise credentials_exception
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # 使用 joinedload 預加載關聯關係
    user = db.query(User).options(
        joinedload(User.roles),
        joinedload(User.departments)
    ).filter(User.username == username).first()
    
    if user is None:
        raise credentials_exception
    
    return user


def get_current_user_optional(request: Request, db: Session = Depends(get_db)):
    """獲取當前用戶，如果未登入則返回None"""
    token = get_token_from_cookie(request)
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None
    
    # 使用 joinedload 預加載關聯關係
    user = db.query(User).options(
        joinedload(User.roles),
        joinedload(User.departments)
    ).filter(User.username == username).first()
    
    return user


def has_permission(user, permission):
    """
    檢查用戶是否有特定權限
    
    Args:
        user: 用戶對象
        permission: 需要的權限
    
    Returns:
        bool: 是否有權限
    """
    if not user:
        return False
    
    # 檢查用戶的所有角色是否有所需權限
    for role in user.roles:
        if permission in role.permissions:
            return True
    
    return False


def permission_required(required_permission: str, department_id: int = None):
    """
    檢查用戶是否有特定權限，並且可以訪問特定部門
    
    Args:
        required_permission: 需要的權限
        department_id: 需要訪問的部門ID，如果為None則不檢查部門權限
    """
    def permission_checker(
        request: Request,
        db: Session = Depends(get_db),
        user = Depends(get_current_user_with_request)
    ):
        # 如果 user 是 RedirectResponse，直接返回它
        if isinstance(user, RedirectResponse):
            return user
            
        # 檢查用戶是否有所需權限
        if not has_permission(user, required_permission):
            if request.headers.get("accept") == "application/json":
                # API 請求返回 JSON 錯誤
                raise HTTPException(status_code=403, detail="權限不足")
            else:
                # 網頁請求重定向到首頁
                return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        # 如果指定了部門ID，檢查用戶是否有權限訪問該部門
        if department_id is not None and not can_access_department(user, department_id, db):
            if request.headers.get("accept") == "application/json":
                raise HTTPException(status_code=403, detail="無權訪問此部門")
            else:
                return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        return user
    return permission_checker


def check_page_permission(required_permission: str, request: Request, db: Session, department_id: int = None):
    """檢查頁面權限的輔助函數"""
    token = get_token_from_cookie(request)
    if not token:
        print(f"未找到 token，重定向到登錄頁面")
        return None, RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            print(f"Token 中未找到用戶名，重定向到登錄頁面")
            return None, RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    except JWTError:
        print(f"Token 解碼失敗，重定向到登錄頁面")
        return None, RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
            
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        print(f"未找到用戶 {username}，重定向到登錄頁面")
        return None, RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    # 載入相關資料
    _ = user.roles
    _ = user.departments
    
    print(f"用戶 {username} 請求權限 {required_permission}")
            
    # 檢查用戶角色是否有所需權限
    has_permission = False
    for role in user.roles:
        if required_permission in role.permissions:
            has_permission = True
            break
    
    if not has_permission:
        print(f"用戶 {username} 沒有權限 {required_permission}，重定向到首頁")
        return None, RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    # 如果指定了部門ID，檢查用戶是否有權限訪問該部門
    if department_id is not None and not can_access_department(user, department_id, db):
        print(f"用戶 {username} 無權訪問部門 {department_id}，重定向到首頁")
        return None, RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
            
    return user, None


def page_permission_required(required_permission: str, department_id: int = None):
    """網頁專用的權限檢查裝飾器，用於需要權限的頁面路由"""
    def dependency(request: Request, db: Session = Depends(get_db)):
        user, redirect = check_page_permission(required_permission, request, db, department_id)
        if redirect:
            return redirect
        return user
    return dependency


def can_access_department(user, department_id, db):
    """檢查用戶是否有權限訪問指定部門"""
    # 添加調試信息
    print(f"檢查用戶 {user.username} (ID={user.id}) 是否有權限訪問部門 ID={department_id}")
    
    # 如果用戶有 manage_all 權限，允許訪問所有部門
    if has_permission(user, "manage_all"):
        print(f"用戶 {user.username} 有 manage_all 權限，允許訪問所有部門")
        return True
    
    # 獲取目標部門
    target_dept = db.query(Department).filter(Department.id == department_id).first()
    if not target_dept:
        print(f"部門 ID={department_id} 不存在")
        return False
    
    # 檢查用戶是否直接屬於該部門
    for dept in user.departments:
        # 如果用戶屬於目標部門
        if dept.id == department_id:
            print(f"用戶 {user.username} 直接屬於部門 ID={department_id}，允許訪問")
            return True
        # 如果用戶屬於目標部門的父部門（局/處級）
        if dept.is_bureau and target_dept.bureau_code == dept.bureau_code:
            print(f"用戶 {user.username} 屬於父部門 {dept.name}，允許訪問子部門 {target_dept.name}")
            return True
    
    # 管理部門的權限
    if has_permission(user, "manage_departments"):
        print(f"用戶 {user.username} 有 manage_departments 權限，允許訪問所有部門")
        return True
    
    print(f"用戶 {user.username} 無權訪問部門 ID={department_id}")
    return False


def create_access_token(data: dict, expires_delta: timedelta = None):
    """
    創建訪問令牌
    
    Args:
        data: 要編碼到令牌中的數據
        expires_delta: 令牌的過期時間增量，如果未提供則使用默認值
        
    Returns:
        str: JWT令牌
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=60 * 24)  # 24小時
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt
