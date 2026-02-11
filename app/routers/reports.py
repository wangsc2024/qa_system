from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.question import Question
from app.models.report import Report
from app.schemas.report import ReportCreate, ReportUpdate
from app.dependencies import get_current_user, permission_required, page_permission_required, can_access_department, has_permission
from app.models.user import User
from app.models.role import Role
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="templates")
templates.env.globals["has_permission"] = has_permission

@router.post("/{question_id}", response_model=dict)
def create_report(
    question_id: int,
    report: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_required("create_report"))
):
    # 檢查問題是否存在
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="問題不存在")
    
    # 檢查用戶是否有權限訪問該問題的填報部門或回答部門
    has_access = False
    
    # 如果用戶有 manage_all 權限，允許訪問所有問題
    if has_permission(current_user, "manage_all"):
        has_access = True
    else:
        # 檢查填報部門
        for dept in question.report_departments:
            if can_access_department(current_user, dept.id, db):
                has_access = True
                break
                
        # 如果沒有權限訪問填報部門，檢查回答部門
        if not has_access:
            for dept in question.answer_departments:
                if can_access_department(current_user, dept.id, db):
                    has_access = True
                    break
    
    if not has_access:
        raise HTTPException(status_code=403, detail="無權訪問此問題")
    
    # 檢查問題是否已結案
    if question.status.value == "closed":
        raise HTTPException(status_code=400, detail="問題已結案，無法新增回覆")
    
    # 建立新報告
    db_report = Report(
        question_id=question_id,
        reply_content=report.reply_content,
        reply_date=datetime.utcnow(),
        user_id=current_user.id
    )
    
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    
    return {"success": True, "report_id": db_report.id}

@router.get("/{question_id}", response_model=list)
def get_reports(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_required("read_report"))
):
    # 檢查問題是否存在
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="問題不存在")
    
    # 檢查用戶是否有權限訪問該問題所屬的部門
    if not can_access_department(current_user, question.department_id, db):
        raise HTTPException(status_code=403, detail="無權訪問此部門")
    
    # 獲取該問題的所有報告
    reports = db.query(Report).filter(Report.question_id == question_id).all()
    
    return reports

@router.put("/{report_id}", response_model=dict)
def update_report(
    report_id: int,
    report_update: ReportUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_required("edit_report"))
):
    # 檢查報告是否存在
    db_report = db.query(Report).filter(Report.id == report_id).first()
    if not db_report:
        raise HTTPException(status_code=404, detail="回覆不存在")
    
    # 檢查問題是否存在
    question = db.query(Question).filter(Question.id == db_report.question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="問題不存在")
    
    # 檢查用戶是否有權限訪問該問題的填報部門或回答部門
    has_access = False
    
    # 如果用戶有 manage_all 權限，允許訪問所有問題
    if has_permission(current_user, "manage_all"):
        has_access = True
    else:
        # 檢查填報部門
        for dept in question.report_departments:
            if can_access_department(current_user, dept.id, db):
                has_access = True
                break
                
        # 如果沒有權限訪問填報部門，檢查回答部門
        if not has_access:
            for dept in question.answer_departments:
                if can_access_department(current_user, dept.id, db):
                    has_access = True
                    break
    
    if not has_access:
        raise HTTPException(status_code=403, detail="無權訪問此問題")
    
    # 檢查問題是否已結案
    if question.status.value == "closed":
        raise HTTPException(status_code=400, detail="問題已結案，無法編輯回覆")
    
    # 檢查是否為回覆的創建者或管理員
    if db_report.user_id != current_user.id and not has_permission(current_user, "manage_roles"):
        raise HTTPException(status_code=403, detail="只有回覆的創建者或管理員可以編輯回覆")
    
    # 更新報告
    db_report.reply_content = report_update.reply_content
    
    db.commit()
    db.refresh(db_report)
    
    return {"success": True} 