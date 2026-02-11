from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.department import Department
from app.dependencies import permission_required
from app.models.user import User
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def list_departments(
    request: Request,
    error: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_required("manage_departments"))
):
    # 獲取所有部門
    departments = db.query(Department).all()
    
    # 將部門組織成層級結構
    bureau_departments = []  # 局/處級部門
    section_departments = {}  # 科級部門，按局/處分組
    
    for dept in departments:
        if dept.is_bureau:
            bureau_departments.append(dept)
        else:
            bureau_code = dept.bureau_code
            if bureau_code not in section_departments:
                section_departments[bureau_code] = []
            section_departments[bureau_code].append(dept)
    
    return templates.TemplateResponse(
        "departments/list.html",
        {
            "request": request,
            "current_user": current_user,
            "bureau_departments": bureau_departments,
            "section_departments": section_departments,
            "error": error
        }
    )

@router.get("/create", response_class=HTMLResponse)
async def create_department_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_required("manage_departments"))
):
    # 獲取所有局/處級部門作為可選的父部門
    parent_departments = db.query(Department).filter(Department.code.endswith('00')).all()
    
    return templates.TemplateResponse(
        "departments/create.html",
        {
            "request": request,
            "current_user": current_user,
            "parent_departments": parent_departments
        }
    )

@router.post("/create")
async def create_department(
    request: Request,
    code: str = Form(...),
    name: str = Form(...),
    parent_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_required("manage_departments"))
):
    # 驗證部門代碼格式
    if not code.isdigit() or len(code) != 4:
        return templates.TemplateResponse(
            "departments/create.html",
            {
                "request": request,
                "current_user": current_user,
                "error": "部門代碼必須為4位數字"
            },
            status_code=400
        )
    
    # 檢查部門代碼是否已存在
    existing_dept = db.query(Department).filter(Department.code == code).first()
    if existing_dept:
        return templates.TemplateResponse(
            "departments/create.html",
            {
                "request": request,
                "current_user": current_user,
                "error": "部門代碼已存在"
            },
            status_code=400
        )
    
    # 如果是科級部門，檢查其父部門是否存在且為局/處級
    if not code.endswith('00'):
        bureau_code = code[:2] + '00'
        parent_dept = db.query(Department).filter(Department.code == bureau_code).first()
        if not parent_dept:
            return templates.TemplateResponse(
                "departments/create.html",
                {
                    "request": request,
                    "current_user": current_user,
                    "error": "必須先創建對應的局/處級部門"
                },
                status_code=400
            )
        parent_id = parent_dept.id
    
    # 創建新部門
    new_department = Department(
        code=code,
        name=name,
        parent_id=parent_id
    )
    db.add(new_department)
    db.commit()
    
    return RedirectResponse(url="/departments", status_code=303)

@router.get("/{department_id}/edit", response_class=HTMLResponse)
async def edit_department_page(
    department_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_required("manage_departments"))
):
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="部門不存在")
    
    # 獲取所有可選的父部門（局/處級）
    parent_departments = db.query(Department).filter(Department.code.endswith('00')).all()
    
    return templates.TemplateResponse(
        "departments/edit.html",
        {
            "request": request,
            "current_user": current_user,
            "department": department,
            "parent_departments": parent_departments
        }
    )

@router.post("/{department_id}/edit")
async def edit_department(
    department_id: int,
    request: Request,
    name: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_required("manage_departments"))
):
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="部門不存在")
    
    # 更新部門名稱
    department.name = name
    db.commit()
    
    return RedirectResponse(url="/departments", status_code=303)

@router.post("/{department_id}/delete")
async def delete_department(
    department_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_required("manage_departments"))
):
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="部門不存在")
    
    # 檢查是否有子部門
    if db.query(Department).filter(Department.parent_id == department_id).count() > 0:
        return templates.TemplateResponse(
            "departments/list.html",
            {
                "request": request,
                "current_user": current_user,
                "error": "無法刪除含有子部門的部門"
            },
            status_code=400
        )
    
    # 檢查是否有關聯的問題
    if hasattr(department, 'report_questions') and len(department.report_questions) > 0:
        return templates.TemplateResponse(
            "departments/list.html",
            {
                "request": request,
                "current_user": current_user,
                "error": "無法刪除已關聯問題的部門（作為填報部門）"
            },
            status_code=400
        )
    
    if hasattr(department, 'answer_questions') and len(department.answer_questions) > 0:
        return templates.TemplateResponse(
            "departments/list.html",
            {
                "request": request,
                "current_user": current_user,
                "error": "無法刪除已關聯問題的部門（作為回答部門）"
            },
            status_code=400
        )
    
    # 檢查是否有關聯的用戶
    if hasattr(department, 'users') and len(department.users) > 0:
        return templates.TemplateResponse(
            "departments/list.html",
            {
                "request": request,
                "current_user": current_user,
                "error": "無法刪除已關聯用戶的部門"
            },
            status_code=400
        )
    
    if hasattr(department, 'all_users') and len(department.all_users) > 0:
        return templates.TemplateResponse(
            "departments/list.html",
            {
                "request": request,
                "current_user": current_user,
                "error": "無法刪除已關聯用戶的部門"
            },
            status_code=400
        )
    
    # 檢查是否有關聯的角色
    if hasattr(department, 'roles') and len(department.roles) > 0:
        return templates.TemplateResponse(
            "departments/list.html",
            {
                "request": request,
                "current_user": current_user,
                "error": "無法刪除已關聯角色的部門"
            },
            status_code=400
        )
    
    try:
        # 刪除部門
        db.delete(department)
        db.commit()
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse(
            "departments/list.html",
            {
                "request": request,
                "current_user": current_user,
                "error": f"刪除部門時發生錯誤: {str(e)}"
            },
            status_code=400
        )
    
    return RedirectResponse(url="/departments", status_code=303) 