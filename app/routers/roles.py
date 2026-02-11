from fastapi import APIRouter, Depends, Request, Form, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional, List
from app.database import get_db
from app.models.role import Role
from app.models.user import User
from app.dependencies import page_permission_required, has_permission
import logging
from fastapi import HTTPException

templates = Jinja2Templates(directory="templates")
templates.env.globals["has_permission"] = has_permission
router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def list_roles(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(page_permission_required("manage_roles"))
):
    roles = db.query(Role).all()
    
    return templates.TemplateResponse(
        "roles/list.html", 
        {"request": request, "roles": roles, "current_user": current_user}
    )

@router.get("/create", response_class=HTMLResponse)
async def create_role_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(page_permission_required("manage_roles"))
):
    # 預設權限列表，分類顯示
    permission_groups = {
        "問題管理": [
            "read_question", "create_question", "edit_question", "close_question"
        ],
        "回覆管理": [
            "read_report", "create_report", "edit_report"
        ],
        "匯出功能": [
            "export_questions", "export_reports"
        ],
        "系統管理": [
            "manage_users", "manage_roles", "manage_departments", "manage_all"
        ]
    }
    
    return templates.TemplateResponse(
        "roles/create.html", 
        {
            "request": request, 
            "current_user": current_user,
            "permission_groups": permission_groups
        }
    )

@router.post("/", response_class=HTMLResponse)
async def create_role(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    permissions: List[str] = Form([]),
    db: Session = Depends(get_db),
    current_user: User = Depends(page_permission_required("manage_roles"))
):
    try:
        # 檢查角色名稱是否已存在
        existing_role = db.query(Role).filter(Role.name == name).first()
        if existing_role:
            permission_groups = {
                "問題管理": [
                    "read_question", "create_question", "edit_question", "close_question"
                ],
                "回覆管理": [
                    "read_report", "create_report", "edit_report"
                ],
                "匯出功能": [
                    "export_questions", "export_reports"
                ],
                "系統管理": [
                    "manage_users", "manage_roles", "manage_departments", "manage_all"
                ]
            }
            return templates.TemplateResponse(
                "roles/create.html", 
                {
                    "request": request, 
                    "current_user": current_user,
                    "permission_groups": permission_groups,
                    "error": "角色名稱已存在",
                    "name": name,
                    "description": description,
                    "selected_permissions": permissions
                },
                status_code=400
            )
        
        # 創建新角色
        new_role = Role(name=name, description=description, permissions=permissions)
        db.add(new_role)
        db.commit()
        return RedirectResponse(url="/roles", status_code=status.HTTP_303_SEE_OTHER)
        
    except Exception as e:
        db.rollback()
        logging.error(f"創建角色時發生錯誤: {str(e)}")
        permission_groups = {
            "問題管理": [
                "read_question", "create_question", "edit_question", "close_question"
            ],
            "回覆管理": [
                "read_report", "create_report", "edit_report"
            ],
            "匯出功能": [
                "export_questions", "export_reports"
            ],
            "系統管理": [
                "manage_users", "manage_roles", "manage_departments", "manage_all"
            ]
        }
        return templates.TemplateResponse(
            "roles/create.html",
            {
                "request": request,
                "current_user": current_user,
                "permission_groups": permission_groups,
                "error": f"創建角色時發生錯誤: {str(e)}",
                "name": name,
                "description": description,
                "selected_permissions": permissions
            },
            status_code=500
        )

@router.get("/{role_id}/edit", response_class=HTMLResponse)
async def edit_role_page(
    role_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(page_permission_required("manage_roles"))
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        return RedirectResponse(url="/roles", status_code=status.HTTP_303_SEE_OTHER)
    
    # 預設權限列表，分類顯示
    permission_groups = {
        "問題管理": [
            "read_question", "create_question", "edit_question", "close_question"
        ],
        "回覆管理": [
            "read_report", "create_report", "edit_report"
        ],
        "匯出功能": [
            "export_questions", "export_reports"
        ],
        "系統管理": [
            "manage_users", "manage_roles", "manage_departments", "manage_all"
        ]
    }
    
    return templates.TemplateResponse(
        "roles/edit.html", 
        {
            "request": request, 
            "role": role, 
            "current_user": current_user,
            "permission_groups": permission_groups
        }
    )

@router.post("/{role_id}/edit", response_class=HTMLResponse)
async def update_role(
    role_id: int,
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    permissions: Optional[List[str]] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(page_permission_required("manage_roles"))
):
    try:
        # 記錄請求資料
        logging.info(f"角色編輯請求資料: role_id={role_id}, name={name}, description={description}, permissions={permissions}")
        
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            logging.error(f"角色不存在: role_id={role_id}")
            return RedirectResponse(url="/roles", status_code=status.HTTP_303_SEE_OTHER)
        
        # 記錄角色原始資料
        logging.info(f"角色原始資料: id={role.id}, name={role.name}, description={role.description}, permissions={role.permissions}")
        
        # 檢查角色名稱是否已被其他角色使用
        existing_role = db.query(Role).filter(Role.name == name, Role.id != role_id).first()
        if existing_role:
            logging.warning(f"角色名稱已存在: name={name}, existing_role_id={existing_role.id}")
            permission_groups = {
                "問題管理": [
                    "read_question", "create_question", "edit_question", "close_question"
                ],
                "回覆管理": [
                    "read_report", "create_report", "edit_report"
                ],
                "匯出功能": [
                    "export_questions", "export_reports"
                ],
                "系統管理": [
                    "manage_users", "manage_roles", "manage_departments", "manage_all"
                ]
            }
            return templates.TemplateResponse(
                "roles/edit.html", 
                {
                    "request": request, 
                    "role": role,
                    "current_user": current_user,
                    "permission_groups": permission_groups,
                    "error": "角色名稱已存在"
                },
                status_code=400
            )
        
        # 更新角色基本信息
        role.name = name
        role.description = description
        
        # 只有當表單中明確提交了權限時才更新權限
        if permissions is not None:
            role.permissions = permissions
        
        db.commit()
        logging.info(f"角色更新成功: role_id={role.id}, name={role.name}")
        return RedirectResponse(url="/roles", status_code=status.HTTP_303_SEE_OTHER)
        
    except Exception as e:
        db.rollback()
        logging.error(f"更新角色時發生錯誤: role_id={role_id}, error={str(e)}")
        permission_groups = {
            "問題管理": [
                "read_question", "create_question", "edit_question", "close_question"
            ],
            "回覆管理": [
                "read_report", "create_report", "edit_report"
            ],
            "匯出功能": [
                "export_questions", "export_reports"
            ],
            "系統管理": [
                "manage_users", "manage_roles", "manage_departments", "manage_all"
            ]
        }
        return templates.TemplateResponse(
            "roles/edit.html",
            {
                "request": request,
                "role": role,
                "current_user": current_user,
                "permission_groups": permission_groups,
                "error": f"更新角色時發生錯誤: {str(e)}"
            },
            status_code=500
        )

@router.post("/{role_id}/delete", response_class=HTMLResponse)
async def delete_role(
    role_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(page_permission_required("manage_roles"))
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if role:
        # 檢查是否有用戶使用此角色
        users_with_role = db.query(User).filter(User.role_id == role_id).count()
        if users_with_role > 0:
            roles = db.query(Role).all()
            return templates.TemplateResponse(
                "roles/list.html", 
                {
                    "request": request, 
                    "roles": roles, 
                    "current_user": current_user,
                    "error": f"無法刪除角色：有 {users_with_role} 個用戶正在使用此角色"
                },
                status_code=400
            )
        
        db.delete(role)
        db.commit()
    
    return RedirectResponse(url="/roles", status_code=status.HTTP_303_SEE_OTHER)
