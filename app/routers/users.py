from fastapi import APIRouter, Depends, HTTPException, Request, Form, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from passlib.context import CryptContext
import logging

from app.database import get_db
from app.models.user import User
from app.models.role import Role
from app.models.department import Department
from app.schemas.user import UserCreate, UserUpdate
from app.dependencies import get_current_user, has_permission, page_permission_required

router = APIRouter()
templates = Jinja2Templates(directory="templates")
templates.env.globals["has_permission"] = has_permission
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 獲取用戶列表頁面
@router.get("/", response_class=HTMLResponse)
async def list_users(
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(page_permission_required("manage_users")),
    search: Optional[str] = None
):
    # 如果 current_user 是 RedirectResponse，直接返回它
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    query = db.query(User)
    
    if search:
        query = query.filter(User.username.contains(search))
    
    users = query.all()
    
    # 確保每個用戶的角色和部門數據已加載
    for user in users:
        _ = user.roles
        _ = user.departments
    
    return templates.TemplateResponse(
        "users/list.html",
        {"request": request, "users": users, "current_user": current_user, "search": search}
    )

# 獲取創建用戶頁面
@router.get("/create", response_class=HTMLResponse)
async def create_user_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(page_permission_required("manage_users"))
):
    # 如果 current_user 是 RedirectResponse，直接返回它
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    roles = db.query(Role).all()
    departments = db.query(Department).all()
    
    return templates.TemplateResponse(
        "users/create.html",
        {
            "request": request, 
            "roles": roles, 
            "departments": departments, 
            "current_user": current_user
        }
    )

# 創建新用戶
@router.post("/", response_class=HTMLResponse)
async def create_user(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(None),
    password: str = Form(...),
    email: Optional[str] = Form(None),
    role_ids: List[int] = Form(...),
    department_ids: List[int] = Form(...),
    is_active: Optional[bool] = Form(None),
    db: Session = Depends(get_db),
    current_user = Depends(page_permission_required("manage_users"))
):
    # 如果 current_user 是 RedirectResponse，直接返回它
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    # 檢查用戶名是否已存在
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        roles = db.query(Role).all()
        departments = db.query(Department).all()
        return templates.TemplateResponse(
            "users/create.html",
            {
                "request": request, 
                "roles": roles, 
                "departments": departments, 
                "current_user": current_user,
                "error": "用戶名已存在",
                "username": username,
                "full_name": full_name,
                "email": email,
                "role_ids": role_ids,
                "department_ids": department_ids,
                "is_active": is_active
            },
            status_code=400
        )
    
    try:
        # 創建新用戶
        hashed_password = pwd_context.hash(password)
        
        # 處理啟用狀態，如果表單中沒有提交 is_active，則設為 False
        active_status = True if is_active else False
        
        new_user = User(
            username=username,
            full_name=full_name,
            password_hash=hashed_password,
            email=email if email and email.strip() else None,
            is_active=active_status
        )
        
        db.add(new_user)
        db.flush()
        
        # 添加角色
        for role_id in role_ids:
            role = db.query(Role).filter(Role.id == role_id).first()
            if role:
                new_user.roles.append(role)
        
        db.flush()
        
        # 添加部門
        for dept_id in department_ids:
            department = db.query(Department).filter(Department.id == dept_id).first()
            if department:
                new_user.departments.append(department)
        
        db.flush()
        db.commit()
        
    except Exception as e:
        db.rollback()
        logging.error(f"創建用戶時發生錯誤: {str(e)}")
        roles = db.query(Role).all()
        departments = db.query(Department).all()
        return templates.TemplateResponse(
            "users/create.html",
            {
                "request": request, 
                "roles": roles, 
                "departments": departments, 
                "current_user": current_user,
                "error": f"創建用戶時發生錯誤: {str(e)}",
                "username": username,
                "full_name": full_name,
                "email": email,
                "role_ids": role_ids,
                "department_ids": department_ids,
                "is_active": is_active
            },
            status_code=500
        )
    
    return RedirectResponse(url="/users", status_code=303)

# 獲取編輯用戶頁面
@router.get("/{user_id}/edit", response_class=HTMLResponse)
async def edit_user_page(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(page_permission_required("manage_users"))
):
    # 如果 current_user 是 RedirectResponse，直接返回它
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return RedirectResponse(url="/users", status_code=303)
    
    # 載入用戶的角色和部門
    _ = user.roles
    _ = user.departments
    
    roles = db.query(Role).all()
    departments = db.query(Department).all()
    
    # 獲取用戶當前的角色和部門ID列表
    user_role_ids = [role.id for role in user.roles]
    user_department_ids = [dept.id for dept in user.departments]
    
    return templates.TemplateResponse(
        "users/edit.html",
        {
            "request": request, 
            "user": user, 
            "roles": roles, 
            "departments": departments, 
            "current_user": current_user,
            "user_role_ids": user_role_ids,
            "user_department_ids": user_department_ids
        }
    )

# 更新用戶
@router.post("/{user_id}/edit", response_class=HTMLResponse)
async def update_user(
    user_id: int,
    request: Request,
    username: str = Form(...),
    full_name: str = Form(None),
    password: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    role_ids: List[int] = Form(...),
    department_ids: List[int] = Form(...),
    is_active: Optional[bool] = Form(None),
    db: Session = Depends(get_db),
    current_user = Depends(page_permission_required("manage_users"))
):
    # 如果 current_user 是 RedirectResponse，直接返回它
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return RedirectResponse(url="/users", status_code=303)
    
    # 檢查用戶名是否已被其他用戶使用
    existing_user = db.query(User).filter(User.username == username, User.id != user_id).first()
    if existing_user:
        roles = db.query(Role).all()
        departments = db.query(Department).all()
        user_role_ids = [role.id for role in user.roles]
        user_department_ids = [dept.id for dept in user.departments]
        return templates.TemplateResponse(
            "users/edit.html",
            {
                "request": request, 
                "user": user,
                "roles": roles, 
                "departments": departments, 
                "current_user": current_user,
                "error": "用戶名已被使用",
                "user_role_ids": user_role_ids,
                "user_department_ids": user_department_ids
            },
            status_code=400
        )
    
    try:
        # 更新基本信息
        user.username = username
        user.full_name = full_name
        user.email = email if email and email.strip() else None
        user.is_active = True if is_active else False
        
        # 如果提供了新密碼，則更新密碼
        if password and password.strip():
            user.password_hash = pwd_context.hash(password)
        
        # 更新角色
        user.roles.clear()
        for role_id in role_ids:
            role = db.query(Role).filter(Role.id == role_id).first()
            if role:
                user.roles.append(role)
        
        # 更新部門
        user.departments.clear()
        for dept_id in department_ids:
            department = db.query(Department).filter(Department.id == dept_id).first()
            if department:
                user.departments.append(department)
        
        db.commit()
        
    except Exception as e:
        db.rollback()
        logging.error(f"更新用戶時發生錯誤: {str(e)}")
        roles = db.query(Role).all()
        departments = db.query(Department).all()
        user_role_ids = [role.id for role in user.roles]
        user_department_ids = [dept.id for dept in user.departments]
        return templates.TemplateResponse(
            "users/edit.html",
            {
                "request": request, 
                "user": user,
                "roles": roles, 
                "departments": departments, 
                "current_user": current_user,
                "error": f"更新用戶時發生錯誤: {str(e)}",
                "user_role_ids": user_role_ids,
                "user_department_ids": user_department_ids
            },
            status_code=500
        )
    
    return RedirectResponse(url="/users", status_code=303)

# 刪除用戶
@router.post("/{user_id}/delete", response_class=HTMLResponse)
async def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(page_permission_required("manage_users"))
):
    # 如果 current_user 是 RedirectResponse，直接返回它
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return RedirectResponse(url="/users", status_code=303)
    
    try:
        # 刪除用戶
        db.delete(user)
        db.commit()
    except Exception as e:
        db.rollback()
        logging.error(f"刪除用戶時發生錯誤: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request, 
                "current_user": current_user,
                "error": f"刪除用戶時發生錯誤: {str(e)}"
            },
            status_code=500
        )
    
    return RedirectResponse(url="/users", status_code=303)
