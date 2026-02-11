from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import StreamingResponse, HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from io import BytesIO
import openpyxl
from datetime import datetime
from typing import Optional, List
from sqlalchemy import exists, and_, or_, desc

from app.database import get_db
from app.models.question import Question, QuestionStatus
from app.models.department import Department
from app.models.report import Report
from app.models.user import User
from app.dependencies import permission_required, can_access_department
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def export_index(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_required("export_questions"))
):
    # 獲取所有部門（用於部門過濾選擇）
    all_departments = db.query(Department).all()
    
    # 獲取當前年度
    current_year = datetime.now().year
    
    # 獲取所有可能的狀態
    statuses = [status.value for status in QuestionStatus]
    
    return templates.TemplateResponse(
        "export/index.html",
        {
            "request": request, 
            "current_user": current_user,
            "departments": all_departments,
            "current_year": current_year,
            "statuses": statuses
        }
    )

@router.get("/search", response_class=HTMLResponse)
async def search_questions(
    request: Request,
    department_id: Optional[str] = None,
    year: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_required("export_questions"))
):
    # 初始化查詢
    query = db.query(Question)
    
    # 部門過濾邏輯
    if department_id and department_id.strip():
        try:
            dept_id = int(department_id)
            department = db.query(Department).filter(Department.id == dept_id).first()
            
            if department:
                print(f"過濾部門: ID={dept_id}, 名稱={department.name}")
                
                # 檢查權限
                if not can_access_department(current_user, dept_id, db):
                    print(f"用戶無權訪問部門 ID: {dept_id}")
                else:
                    # 過濾與此部門關聯的問題
                    query = query.filter(
                        or_(
                            Question.report_departments.any(Department.id == dept_id),
                            Question.answer_departments.any(Department.id == dept_id)
                        )
                    )
        except ValueError:
            print(f"無效的部門 ID: {department_id}")
    else:
        # 如果沒有指定部門，則只顯示用戶有權限的部門的問題
        accessible_departments = []
        for dept in db.query(Department).all():
            if can_access_department(current_user, dept.id, db):
                accessible_departments.append(dept.id)
        
        if accessible_departments:
            # 過濾出用戶有權限的部門的問題
            query = query.filter(
                or_( 
                    Question.report_departments.any(Department.id.in_(accessible_departments)),
                    Question.answer_departments.any(Department.id.in_(accessible_departments))
                )
            )
    
    # 年份過濾邏輯
    if year and year.strip():
        try:
            year_int = int(year)
            query = query.filter(Question.year == year_int)
            selected_year = year_int
        except ValueError:
            selected_year = None
    else:
        selected_year = None
    
    # 狀態過濾邏輯
    if status and status.strip() and status != "all":
        try:
            # 將字符串轉換為 QuestionStatus 枚舉
            status_enum = QuestionStatus(status)
            query = query.filter(Question.status == status_enum)
        except (ValueError, KeyError):
            print(f"無效的狀態值: {status}")
    
    # 關鍵字搜尋
    if keyword and keyword.strip():
        search_term = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                Question.title.like(search_term),
                Question.content.like(search_term),
                Question.summary.like(search_term)
            )
        )
    
    # 按創建日期降序排序
    query = query.order_by(desc(Question.created_date))
    
    # 執行查詢
    questions = query.all()
    
    # 獲取所有部門（用於部門過濾選擇）
    all_departments = db.query(Department).all()
    
    # 獲取當前年度
    current_year = datetime.now().year
    
    # 獲取所有可能的狀態
    statuses = [status.value for status in QuestionStatus]
    
    return templates.TemplateResponse(
        "export/search_results.html",
        {
            "request": request, 
            "questions": questions, 
            "current_user": current_user, 
            "departments": all_departments, 
            "current_year": current_year, 
            "selected_year": selected_year,
            "selected_department_id": department_id,
            "selected_status": status,
            "keyword": keyword,
            "statuses": statuses
        }
    )

@router.get("/questions")
def export_all_questions(
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_required("export_questions"))
):
    questions = db.query(Question).all()
    return export_questions_to_excel(questions, db)

@router.get("/questions/filtered")
def export_filtered_questions(
    department_id: Optional[str] = None,
    year: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_required("export_questions"))
):
    # 初始化查詢
    query = db.query(Question)
    
    # 部門過濾邏輯
    if department_id and department_id.strip():
        try:
            dept_id = int(department_id)
            department = db.query(Department).filter(Department.id == dept_id).first()
            
            if department:
                # 檢查權限
                if not can_access_department(current_user, dept_id, db):
                    pass
                else:
                    # 過濾與此部門關聯的問題
                    query = query.filter(
                        or_(
                            Question.report_departments.any(Department.id == dept_id),
                            Question.answer_departments.any(Department.id == dept_id)
                        )
                    )
        except ValueError:
            pass
    else:
        # 如果沒有指定部門，則只顯示用戶有權限的部門的問題
        accessible_departments = []
        for dept in db.query(Department).all():
            if can_access_department(current_user, dept.id, db):
                accessible_departments.append(dept.id)
        
        if accessible_departments:
            # 過濾出用戶有權限的部門的問題
            query = query.filter(
                or_( 
                    Question.report_departments.any(Department.id.in_(accessible_departments)),
                    Question.answer_departments.any(Department.id.in_(accessible_departments))
                )
            )
    
    # 年份過濾邏輯
    if year and year.strip():
        try:
            year_int = int(year)
            query = query.filter(Question.year == year_int)
        except ValueError:
            pass
    
    # 狀態過濾邏輯
    if status and status.strip() and status != "all":
        try:
            # 將字符串轉換為 QuestionStatus 枚舉
            status_enum = QuestionStatus(status)
            query = query.filter(Question.status == status_enum)
        except (ValueError, KeyError):
            print(f"無效的狀態值: {status}")
    
    # 關鍵字搜尋
    if keyword and keyword.strip():
        search_term = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                Question.title.like(search_term),
                Question.content.like(search_term),
                Question.summary.like(search_term)
            )
        )
    
    # 按創建日期降序排序
    query = query.order_by(desc(Question.created_date))
    
    # 執行查詢
    questions = query.all()
    
    return export_questions_to_excel(questions, db)

def export_questions_to_excel(questions, db):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["ID", "年度", "問題日期", "建立日期", "標題", "內容", "填報單位", "回答單位", "摘要", "狀態", "結案日期"])

    for q in questions:
        # 獲取填報部門和回答部門的名稱
        report_depts = ", ".join([d.name for d in q.report_departments]) if hasattr(q, 'report_departments') else ""
        answer_depts = ", ".join([d.name for d in q.answer_departments]) if hasattr(q, 'answer_departments') else ""
        
        ws.append([
            q.id, 
            q.year,
            q.question_date.strftime('%Y-%m-%d') if q.question_date else "",
            q.created_date.strftime('%Y-%m-%d') if q.created_date else "",
            q.title,
            q.content,
            report_depts,
            answer_depts,
            q.summary if q.summary else "",
            q.status.value if q.status else "",
            q.closed_date.strftime('%Y-%m-%d') if q.closed_date else ""
        ])

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    filename = f"questions_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        stream, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/reports/{question_id}")
def export_reports(
    question_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_required("export_reports"))
):
    reports = db.query(Report).filter(Report.question_id == question_id).all()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["ID", "填報日期", "填報人員", "回覆內容"])

    for r in reports:
        ws.append([
            r.id, 
            r.reply_date.strftime('%Y-%m-%d') if r.reply_date else "", 
            r.user.username if r.user else "", 
            r.reply_content if r.reply_content else ""
        ])

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    filename = f"reports_{question_id}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        stream, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
