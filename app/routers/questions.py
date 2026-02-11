from fastapi import APIRouter, Depends, HTTPException, Request, Form, status, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from sqlalchemy import exists, and_, or_, desc, text
from sqlalchemy.exc import IntegrityError
import logging

from app.database import get_db
from app.models.question import Question, QuestionStatus
from app.models.department import Department
from app.models.role import Role
from app.schemas.question import QuestionCreate, QuestionUpdate
from app.dependencies import get_current_user, page_permission_required, permission_required, can_access_department, has_permission
from app.models.user import User
from app.models.report import Report

router = APIRouter()
templates = Jinja2Templates(directory="templates")
templates.env.globals["has_permission"] = has_permission

@router.post("/", response_model=dict)
def create_question(
    question: QuestionCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_required("create_question"))
):
    # 檢查用戶是否有權限訪問所有指定的部門
    for dept_id in question.report_department_ids + question.answer_department_ids:
        # 檢查部門是否為處層級
        department = db.query(Department).filter(Department.id == dept_id).first()
        if not department or not department.code.endswith('00'):
            raise HTTPException(
                status_code=400,
                detail=f"部門 ID={dept_id} 不是處層級部門"
            )
        
        # 檢查權限
        if not can_access_department(current_user, dept_id, db):
            raise HTTPException(
                status_code=403,
                detail=f"用戶無權訪問部門 ID={dept_id}"
            )
    
    # 檢查是否有重複的部門 ID
    report_dept_set = set(question.report_department_ids)
    answer_dept_set = set(question.answer_department_ids)
    
    # 檢查報告部門和回答部門是否有重複
    if report_dept_set.intersection(answer_dept_set):
        raise HTTPException(
            status_code=400,
            detail="同一個部門不能同時是報告部門和回答部門"
        )
    
    # 設置默認值
    current_year = datetime.now().year
    year = question.year or current_year
    question_date = question.question_date or datetime.now().date()
    
    try:
        # 使用 text() 函數來聲明 SQL 語句
        from sqlalchemy import text
        
        # 創建問題
        sql = text("""
            INSERT INTO questions (title, content, year, question_date, created_date, status, creator_id)
            VALUES (:title, :content, :year, :question_date, :created_date, :status, :creator_id)
            RETURNING id
        """)
        
        result = db.execute(
            sql,
            {
                "title": question.title,
                "content": question.content,
                "year": year,
                "question_date": question_date,
                "created_date": datetime.utcnow(),
                "status": "pending",  # 使用小寫的枚舉值
                "creator_id": current_user.id
            }
        )
        
        # 獲取新創建的問題 ID
        question_id = result.scalar_one()
        
        # 添加報告部門關聯
        for dept_id in question.report_department_ids:
            try:
                insert_sql = text("""
                    INSERT INTO question_report_department (question_id, department_id)
                    VALUES (:question_id, :department_id)
                """)
                
                db.execute(
                    insert_sql,
                    {"question_id": question_id, "department_id": dept_id}
                )
                db.flush()
            except Exception as e:
                logging.error(f"添加報告部門關聯時發生錯誤: {str(e)}")
                # 繼續處理其他部門，不中斷流程
        
        # 添加回答部門關聯
        for dept_id in question.answer_department_ids:
            try:
                insert_sql = text("""
                    INSERT INTO question_answer_department (question_id, department_id)
                    VALUES (:question_id, :department_id)
                """)
                
                db.execute(
                    insert_sql,
                    {"question_id": question_id, "department_id": dept_id}
                )
                db.flush()
            except Exception as e:
                logging.error(f"添加回答部門關聯時發生錯誤: {str(e)}")
                # 繼續處理其他部門，不中斷流程
        
        # 提交事務
        db.commit()
        
        # 返回創建的問題 ID
        return {"success": True, "question_id": question_id}
        
    except Exception as e:
        db.rollback()
        logging.error(f"創建問題時發生錯誤: {str(e)}")
        
        # 嘗試清理可能部分創建的問題
        try:
            # 檢查錯誤消息中是否包含問題 ID
            import re
            match = re.search(r'question_id, department_id\)\s+VALUES\s+\((\d+),', str(e))
            if match:
                problem_question_id = int(match.group(1))
                
                # 刪除問題及其關聯 - 分別執行每個 SQL 語句
                db.execute(text("DELETE FROM question_report_department WHERE question_id = :question_id"), 
                          {"question_id": problem_question_id})
                db.execute(text("DELETE FROM question_answer_department WHERE question_id = :question_id"), 
                          {"question_id": problem_question_id})
                db.execute(text("DELETE FROM questions WHERE id = :question_id"), 
                          {"question_id": problem_question_id})
                db.commit()
                logging.info(f"已刪除不完整的問題記錄 ID={problem_question_id}")
        except Exception as cleanup_error:
            logging.error(f"清理不完整問題記錄時發生錯誤: {str(cleanup_error)}")
        
        raise HTTPException(
            status_code=500,
            detail=f"創建問題時發生錯誤: {str(e)}"
        )

@router.get("/", response_class=HTMLResponse)
async def list_questions(
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(page_permission_required("read_question")),
    status: Optional[str] = None,
    department_id: Optional[str] = None,
    year: Optional[str] = None
):
    # 如果 current_user 是 RedirectResponse，直接返回它
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    logging.info(f"請求參數: status={status}, department_id={department_id}, year={year}")
    
    try:
        # 獲取用戶可訪問的部門 ID 列表
        accessible_departments = []
        for dept in db.query(Department).all():
            if can_access_department(current_user, dept.id, db):
                accessible_departments.append(dept.id)
        
        logging.info(f"用戶可訪問的部門 IDs: {accessible_departments}")
        
        if not accessible_departments:
            # 沒有權限訪問任何部門
            logging.warning("用戶無權訪問任何部門")
            questions = []
            return templates.TemplateResponse(
                "questions/list.html",
                {"request": request, "questions": questions, "current_user": current_user, "departments": [], "current_year": datetime.now().year, "selected_year": None}
            )
        
        # 使用原始 SQL 查詢獲取所有問題
        from sqlalchemy import text
        
        # 構建基本查詢
        sql_query = """
            SELECT * FROM questions
            ORDER BY created_date DESC
        """
        
        # 執行查詢
        result = db.execute(text(sql_query))
        rows = result.fetchall()
        
        # 將結果轉換為字典列表
        all_questions = []
        for row in rows:
            question_dict = dict(row._mapping)
            question_dict['report_departments'] = []
            question_dict['answer_departments'] = []
            
            # 確保日期欄位是可用的格式
            # 將字串日期轉換為日期對象，或者設為 None
            for date_field in ['question_date', 'created_date', 'closed_date']:
                if date_field in question_dict and question_dict[date_field] is not None:
                    if isinstance(question_dict[date_field], str):
                        try:
                            # 嘗試解析日期字串
                            question_dict[date_field] = datetime.fromisoformat(question_dict[date_field].replace('Z', '+00:00'))
                        except (ValueError, AttributeError):
                            # 如果解析失敗，設為 None
                            question_dict[date_field] = None
            
            all_questions.append(question_dict)
        
        # 獲取問題的報告部門和回答部門
        for question in all_questions:
            # 獲取報告部門
            report_dept_query = """
                SELECT d.* FROM departments d
                JOIN question_report_department qrd ON d.id = qrd.department_id
                WHERE qrd.question_id = :question_id
            """
            report_depts = db.execute(text(report_dept_query), {"question_id": question['id']}).fetchall()
            question['report_departments'] = [dict(dept._mapping) for dept in report_depts]
            
            # 獲取回答部門
            answer_dept_query = """
                SELECT d.* FROM departments d
                JOIN question_answer_department qad ON d.id = qad.department_id
                WHERE qad.question_id = :question_id
            """
            answer_depts = db.execute(text(answer_dept_query), {"question_id": question['id']}).fetchall()
            question['answer_departments'] = [dict(dept._mapping) for dept in answer_depts]
        
        # 手動過濾用戶有權限的部門的問題
        filtered_questions = []
        for question in all_questions:
            # 檢查用戶是否有權限訪問該問題的任一填報部門或回答部門
            has_access = False
            
            # 如果用戶有 manage_all 權限，允許訪問所有問題
            if has_permission(current_user, "manage_all"):
                has_access = True
            else:
                # 檢查填報部門
                for dept in question['report_departments']:
                    if dept['id'] in accessible_departments:
                        has_access = True
                        break
                
                # 如果沒有權限訪問填報部門，檢查回答部門
                if not has_access:
                    for dept in question['answer_departments']:
                        if dept['id'] in accessible_departments:
                            has_access = True
                            break
            
            # 狀態過濾
            if status and has_access:
                if status == "open" and question['status'] == 'closed':
                    has_access = False
                elif status == "closed" and question['status'] != 'closed':
                    has_access = False
            
            # 部門過濾
            if department_id and department_id.strip() and has_access:
                try:
                    dept_id = int(department_id)
                    # 檢查是否有指定的部門
                    department = db.query(Department).filter(Department.id == dept_id).first()
                    if not department:
                        logging.warning(f"找不到部門 ID: {dept_id}")
                        has_access = False
                    else:
                        logging.info(f"過濾部門: ID={dept_id}, 名稱={department.name}")
                        
                        # 檢查權限
                        if not can_access_department(current_user, dept_id, db):
                            logging.warning(f"用戶無權訪問部門 ID: {dept_id}")
                            has_access = False
                        else:
                            # 檢查問題是否與此部門關聯
                            dept_related = False
                            for dept in question['report_departments']:
                                if dept['id'] == dept_id:
                                    dept_related = True
                                    break
                            
                            if not dept_related:
                                for dept in question['answer_departments']:
                                    if dept['id'] == dept_id:
                                        dept_related = True
                                        break
                            
                            has_access = has_access and dept_related
                except ValueError:
                    logging.warning(f"無效的部門 ID: {department_id}")
            
            # 年份過濾
            if year and year.strip() and has_access:
                try:
                    year_int = int(year)
                    logging.info(f"過濾年份: {year_int}")
                    if question['year'] != year_int:
                        has_access = False
                except ValueError:
                    logging.warning(f"無效的年份: {year}")
            
            if has_access:
                # 為每個問題添加一個 display_status 屬性
                if question['status'] == 'closed' and not question.get('closed_date'):
                    # 如果狀態是 closed 但沒有關閉日期，根據是否有回覆調整顯示狀態
                    has_reports = db.query(exists().where(Report.question_id == question['id'])).scalar()
                    question['display_status'] = 'ANSWERED' if has_reports else 'PENDING'
                else:
                    # 將小寫狀態轉換為大寫
                    status_map = {'pending': 'PENDING', 'answered': 'ANSWERED', 'closed': 'CLOSED'}
                    question['display_status'] = status_map.get(question['status'], question['status'].upper() if question['status'] else '')
                
                # 添加一些模板可能需要的方法
                question['get_report_departments'] = lambda q=question: q['report_departments']
                question['get_answer_departments'] = lambda q=question: q['answer_departments']
                
                filtered_questions.append(question)
        
        # 獲取所有部門（用於部門過濾選擇）
        all_departments = db.query(Department).all()
        
        # 獲取當前年度
        current_year = datetime.now().year
        
        # 獲取選定的年份
        selected_year = None
        if year and year.strip():
            try:
                selected_year = int(year)
            except ValueError:
                pass
        
        return templates.TemplateResponse(
            "questions/list.html",
            {"request": request, "questions": filtered_questions, "current_user": current_user, "departments": all_departments, "current_year": current_year, "selected_year": selected_year}
        )
    
    except Exception as e:
        logging.error(f"列出問題時發生錯誤: {str(e)}")
        # 獲取所有部門（用於部門過濾選擇）
        all_departments = db.query(Department).all()
        
        # 獲取當前年度
        current_year = datetime.now().year
        
        return templates.TemplateResponse(
            "questions/list.html",
            {"request": request, "questions": [], "current_user": current_user, "departments": all_departments, "current_year": current_year, "selected_year": None, "error": f"載入問題時發生錯誤: {str(e)}"}
        )

@router.get("/create", response_class=HTMLResponse)
async def create_question_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_required("create_question"))
):
    # 如果 current_user 是 RedirectResponse，直接返回它
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    # 確保用戶部門信息已加載
    if hasattr(current_user, 'department_id') and current_user.department_id:
        # 加載用戶主要部門信息
        department = db.query(Department).filter(Department.id == current_user.department_id).first()
        current_user.department = department
        logging.info(f"用戶 {current_user.username} 的部門ID={current_user.department_id}, 部門名稱={department.name if department else 'None'}")
    else:
        logging.warning(f"用戶 {current_user.username} 沒有設定department_id")
    
    # 獲取所有處層級的部門（代碼以00結尾的4位數代碼）
    departments = db.query(Department).filter(
        Department.code.like('%00')  # 只選擇以00結尾的部門
    ).all()
    
    # 過濾用戶有權限的部門
    accessible_departments = [
        dept for dept in departments
        if can_access_department(current_user, dept.id, db)
    ]
    
    return templates.TemplateResponse(
        "questions/create.html",
        {
            "request": request, 
            "departments": accessible_departments,
            "current_user": current_user
        }
    )

@router.get("/{question_id}", response_class=HTMLResponse)
async def get_question(
    question_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(page_permission_required("read_question"))
):
    # 如果 current_user 是 RedirectResponse，直接返回它
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    # 使用原始 SQL 查詢獲取問題
    from sqlalchemy import text
    
    # 獲取問題
    question_query = """
        SELECT * FROM questions
        WHERE id = :question_id
    """
    result = db.execute(text(question_query), {"question_id": question_id}).fetchone()
    
    if not result:
        return RedirectResponse(url="/questions", status_code=302)
    
    # 將結果轉換為字典
    question = dict(result._mapping)
    
    # 確保日期欄位是可用的格式
    for date_field in ['question_date', 'created_date', 'closed_date']:
        if date_field in question and question[date_field] is not None:
            if isinstance(question[date_field], str):
                try:
                    # 嘗試解析日期字串
                    question[date_field] = datetime.fromisoformat(question[date_field].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    # 如果解析失敗，設為 None
                    question[date_field] = None
    
    # 獲取報告部門
    report_dept_query = """
        SELECT d.* FROM departments d
        JOIN question_report_department qrd ON d.id = qrd.department_id
        WHERE qrd.question_id = :question_id
    """
    report_depts = db.execute(text(report_dept_query), {"question_id": question_id}).fetchall()
    question['report_departments'] = [dict(dept._mapping) for dept in report_depts]
    
    # 獲取回答部門
    answer_dept_query = """
        SELECT d.* FROM departments d
        JOIN question_answer_department qad ON d.id = qad.department_id
        WHERE qad.question_id = :question_id
    """
    answer_depts = db.execute(text(answer_dept_query), {"question_id": question_id}).fetchall()
    question['answer_departments'] = [dict(dept._mapping) for dept in answer_depts]
    
    # 檢查用戶是否有權限訪問該問題的任一填報部門或回答部門
    has_access = False
    
    # 如果用戶有 manage_all 權限，允許訪問所有問題
    if has_permission(current_user, "manage_all"):
        has_access = True
    else:
        # 檢查填報部門
        for dept in question['report_departments']:
            if can_access_department(current_user, dept['id'], db):
                has_access = True
                break
                
        # 如果沒有權限訪問填報部門，檢查回答部門
        if not has_access:
            for dept in question['answer_departments']:
                if can_access_department(current_user, dept['id'], db):
                    has_access = True
                    break
    
    if not has_access:
        return RedirectResponse(url="/questions", status_code=302)
    
    # 過濾問題的填報部門和回答部門，只顯示用戶有權限的部門
    filtered_report_departments = []
    filtered_answer_departments = []
    
    for dept in question['report_departments']:
        if can_access_department(current_user, dept['id'], db):
            filtered_report_departments.append(dept)
    
    for dept in question['answer_departments']:
        if can_access_department(current_user, dept['id'], db):
            filtered_answer_departments.append(dept)
    
    # 添加過濾後的部門到問題字典
    question['filtered_report_departments'] = filtered_report_departments
    question['filtered_answer_departments'] = filtered_answer_departments
    
    # 添加一些模板可能需要的方法
    question['get_report_departments'] = lambda q=question: q['report_departments']
    question['get_answer_departments'] = lambda q=question: q['answer_departments']
    
    # 設置顯示狀態
    if question['status'] == 'closed' and not question.get('closed_date'):
        # 如果狀態是 closed 但沒有關閉日期，根據是否有回覆調整顯示狀態
        has_reports = db.query(exists().where(Report.question_id == question['id'])).scalar()
        question['display_status'] = 'ANSWERED' if has_reports else 'PENDING'
    else:
        # 將小寫狀態轉換為大寫
        status_map = {'pending': 'PENDING', 'answered': 'ANSWERED', 'closed': 'CLOSED'}
        question['display_status'] = status_map.get(question['status'], question['status'].upper() if question['status'] else '')
    
    # 獲取問題的回覆記錄
    reports_query = """
        SELECT r.*, u.username, u.id as user_id, d.name as department_name, d.id as department_id
        FROM reports r
        JOIN users u ON r.user_id = u.id
        JOIN departments d ON u.department_id = d.id
        WHERE r.question_id = :question_id
        ORDER BY r.reply_date DESC
    """
    reports = db.execute(text(reports_query), {"question_id": question_id}).fetchall()
    
    # 將結果轉換為字典列表
    question['reports'] = []
    
    # 獲取當前用戶的部門 ID 列表
    user_department_ids = [dept.id for dept in current_user.departments]
    
    for report in reports:
        report_dict = dict(report._mapping)
        
        # 只添加用戶有權限的部門的回答
        # 如果用戶有 manage_all 權限，或者回答來自用戶所屬的部門，則可以看到
        if has_permission(current_user, "manage_all") or report_dict['department_id'] in user_department_ids:
            # 確保日期欄位是可用的格式
            if 'reply_date' in report_dict and report_dict['reply_date'] is not None:
                if isinstance(report_dict['reply_date'], str):
                    try:
                        # 嘗試解析日期字串
                        report_dict['reply_date'] = datetime.fromisoformat(report_dict['reply_date'].replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        pass
            
            # 添加用戶信息
            report_dict['user'] = {
                'username': report_dict.get('username'),
                'id': report_dict.get('user_id'),
                'department': {'name': report_dict.get('department_name')}
            }
            
            question['reports'].append(report_dict)
    
    # 檢查當前用戶是否可以回答此問題
    can_reply = False
    if has_permission(current_user, "create_report"):
        # 檢查用戶是否屬於問題的回答部門
        for dept in question['answer_departments']:
            if dept['id'] in user_department_ids:
                can_reply = True
                break
    
    # 檢查當前用戶的部門是否已經回答過
    has_replied = False
    for report in question['reports']:
        if report['department_id'] in user_department_ids:
            has_replied = True
            break
    
    # 如果已經回答過，就不能再回答
    if has_replied:
        can_reply = False
    
    question['can_reply'] = can_reply
    
    return templates.TemplateResponse(
        "questions/detail.html",
        {
            "request": request, 
            "question": question,
            "current_user": current_user
        }
    )

@router.put("/{question_id}", response_model=dict)
def update_question(
    question_id: int,
    question_update: QuestionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_required("edit_question"))
):
    db_question = db.query(Question).filter(Question.id == question_id).first()
    if not db_question:
        raise HTTPException(status_code=404, detail="問題不存在")
    
    # 檢查用戶是否有權限訪問該問題所屬的部門
    if not can_access_department(current_user, db_question.department_id, db):
        raise HTTPException(status_code=403, detail="無權訪問此部門")
    
    if question_update.title is not None:
        db_question.title = question_update.title
    
    if question_update.content is not None:
        db_question.content = question_update.content
    
    db.commit()
    db.refresh(db_question)
    return {"success": True}

@router.put("/{question_id}/close", response_class=JSONResponse)
async def close_question(
    question_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_required("close_question"))
):
    # 如果 current_user 是 RedirectResponse，直接返回它
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    # 獲取請求體
    data = await request.json()
    summary = data.get("summary", "")
    
    # 使用原始 SQL 查詢獲取問題
    from sqlalchemy import text
    
    # 獲取問題
    question_query = """
        SELECT * FROM questions
        WHERE id = :question_id
    """
    result = db.execute(text(question_query), {"question_id": question_id}).fetchone()
    
    if not result:
        return JSONResponse(content={"success": False, "message": "問題不存在"}, status_code=404)
    
    # 將結果轉換為字典
    question = dict(result._mapping)
    
    # 獲取報告部門
    report_dept_query = """
        SELECT d.* FROM departments d
        JOIN question_report_department qrd ON d.id = qrd.department_id
        WHERE qrd.question_id = :question_id
    """
    report_depts = db.execute(text(report_dept_query), {"question_id": question_id}).fetchall()
    question['report_departments'] = [dict(dept._mapping) for dept in report_depts]
    
    # 獲取回答部門
    answer_dept_query = """
        SELECT d.* FROM departments d
        JOIN question_answer_department qad ON d.id = qad.department_id
        WHERE qad.question_id = :question_id
    """
    answer_depts = db.execute(text(answer_dept_query), {"question_id": question_id}).fetchall()
    question['answer_departments'] = [dict(dept._mapping) for dept in answer_depts]
    
    # 檢查用戶是否有權限訪問該問題的填報部門或回答部門
    has_access = False
    
    # 如果用戶有 manage_all 權限，允許訪問所有問題
    if has_permission(current_user, "manage_all"):
        has_access = True
    else:
        # 檢查填報部門
        for dept in question['report_departments']:
            if can_access_department(current_user, dept['id'], db):
                has_access = True
                break
                
        # 如果沒有權限訪問填報部門，檢查回答部門
        if not has_access:
            for dept in question['answer_departments']:
                if can_access_department(current_user, dept['id'], db):
                    has_access = True
                    break
    
    if not has_access:
        return JSONResponse(content={"success": False, "message": "無權訪問此問題"}, status_code=403)
    
    try:
        # 更新問題狀態為已結案
        update_query = """
            UPDATE questions
            SET status = 'closed',
                summary = :summary,
                closed_date = :closed_date
            WHERE id = :question_id
        """
        
        db.execute(
            text(update_query),
            {
                "summary": summary,
                "closed_date": datetime.now(),
                "question_id": question_id
            }
        )
        
        db.commit()
        return JSONResponse(content={"success": True})
        
    except Exception as e:
        db.rollback()
        logging.error(f"結案時發生錯誤: {str(e)}")
        return JSONResponse(
            content={"success": False, "message": f"結案時發生錯誤: {str(e)}"},
            status_code=500
        )

@router.post("/{question_id}/edit", response_class=HTMLResponse)
async def edit_question(
    question_id: int,
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    year: Optional[int] = Form(None),
    question_date: Optional[str] = Form(None),
    report_department_ids: List[int] = Form(...),
    answer_department_ids: List[int] = Form(...),
    closed_date: Optional[str] = Form(None),
    summary: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_required("edit_question"))
):
    # 如果 current_user 是 RedirectResponse，直接返回它
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    # 使用原始 SQL 查詢獲取問題
    from sqlalchemy import text
    
    # 獲取問題
    question_query = """
        SELECT * FROM questions
        WHERE id = :question_id
    """
    result = db.execute(text(question_query), {"question_id": question_id}).fetchone()
    
    if not result:
        return RedirectResponse(url="/questions", status_code=302)
    
    # 將結果轉換為字典
    question = dict(result._mapping)
    
    # 獲取報告部門
    report_dept_query = """
        SELECT d.* FROM departments d
        JOIN question_report_department qrd ON d.id = qrd.department_id
        WHERE qrd.question_id = :question_id
    """
    report_depts = db.execute(text(report_dept_query), {"question_id": question_id}).fetchall()
    question['report_departments'] = [dict(dept._mapping) for dept in report_depts]
    
    # 獲取回答部門
    answer_dept_query = """
        SELECT d.* FROM departments d
        JOIN question_answer_department qad ON d.id = qad.department_id
        WHERE qad.question_id = :question_id
    """
    answer_depts = db.execute(text(answer_dept_query), {"question_id": question_id}).fetchall()
    question['answer_departments'] = [dict(dept._mapping) for dept in answer_depts]
    
    # 檢查用戶是否有權限訪問該問題的填報部門或回答部門
    has_access = False
    
    # 如果用戶有 manage_all 權限，允許訪問所有問題
    if has_permission(current_user, "manage_all"):
        has_access = True
    else:
        # 檢查填報部門
        for dept in question['report_departments']:
            if can_access_department(current_user, dept['id'], db):
                has_access = True
                break
                
        # 如果沒有權限訪問填報部門，檢查回答部門
        if not has_access:
            for dept in question['answer_departments']:
                if can_access_department(current_user, dept['id'], db):
                    has_access = True
                    break
    
    if not has_access:
        return RedirectResponse(url="/questions", status_code=302)
    
    # 檢查用戶是否有權限訪問所有指定的部門
    for dept_id in report_department_ids + answer_department_ids:
        if not can_access_department(current_user, dept_id, db):
            # 獲取用戶有權限的部門
            accessible_departments = []
            all_departments = db.query(Department).all()
            for dept in all_departments:
                if can_access_department(current_user, dept.id, db):
                    accessible_departments.append(dept)
            
            return templates.TemplateResponse(
                "questions/edit.html",
                {
                    "request": request, 
                    "question": question,
                    "departments": accessible_departments,
                    "report_department_ids": report_department_ids,
                    "answer_department_ids": answer_department_ids,
                    "current_user": current_user,
                    "error": f"無權指派給部門 ID: {dept_id}"
                },
                status_code=403
            )
    
    try:
        # 更新問題基本信息
        update_query = """
            UPDATE questions
            SET title = :title,
                content = :content,
                year = :year,
                question_date = :question_date,
                closed_date = :closed_date,
                summary = :summary,
                status = :status
            WHERE id = :question_id
        """
        
        # 處理問題日期
        parsed_question_date = None
        if question_date:
            parsed_question_date = datetime.strptime(question_date, "%Y-%m-%d")
        
        # 處理結案日期和狀態
        parsed_closed_date = None
        status = question['status']  # 保持原狀態
        
        if closed_date:
            # 設置了結案日期，將狀態設為已結案
            parsed_closed_date = datetime.strptime(closed_date, "%Y-%m-%d")
            status = "closed"  # 使用小寫
        else:
            # 清除了結案日期，根據是否有回覆更新狀態
            # 檢查是否有回覆
            has_reports = db.query(exists().where(Report.question_id == question_id)).scalar()
            status = "answered" if has_reports else "pending"  # 使用小寫
        
        # 執行更新
        db.execute(
            text(update_query),
            {
                "title": title,
                "content": content,
                "year": year,
                "question_date": parsed_question_date,
                "closed_date": parsed_closed_date,
                "summary": summary,
                "status": status,
                "question_id": question_id
            }
        )
        
        # 更新填報部門關聯
        # 先刪除現有關聯
        db.execute(
            text("DELETE FROM question_report_department WHERE question_id = :question_id"),
            {"question_id": question_id}
        )
        
        # 添加新的關聯
        for dept_id in report_department_ids:
            db.execute(
                text("INSERT INTO question_report_department (question_id, department_id) VALUES (:question_id, :department_id)"),
                {"question_id": question_id, "department_id": dept_id}
            )
        
        # 更新回答部門關聯
        # 先刪除現有關聯
        db.execute(
            text("DELETE FROM question_answer_department WHERE question_id = :question_id"),
            {"question_id": question_id}
        )
        
        # 添加新的關聯
        for dept_id in answer_department_ids:
            db.execute(
                text("INSERT INTO question_answer_department (question_id, department_id) VALUES (:question_id, :department_id)"),
                {"question_id": question_id, "department_id": dept_id}
            )
        
        db.commit()
        
    except Exception as e:
        db.rollback()
        logging.error(f"更新問題時發生錯誤: {str(e)}")
        # 獲取用戶有權限的部門
        accessible_departments = []
        all_departments = db.query(Department).all()
        for dept in all_departments:
            if can_access_department(current_user, dept.id, db):
                accessible_departments.append(dept)
        
        return templates.TemplateResponse(
            "questions/edit.html",
            {
                "request": request, 
                "question": question,
                "departments": accessible_departments,
                "report_department_ids": report_department_ids,
                "answer_department_ids": answer_department_ids,
                "current_user": current_user,
                "error": f"更新問題時發生錯誤: {str(e)}"
            },
            status_code=500
        )
    
    return RedirectResponse(url=f"/questions/{question_id}", status_code=303)

@router.get("/{question_id}/edit", response_class=HTMLResponse)
async def edit_question_page(
    question_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_required("edit_question"))
):
    # 如果 current_user 是 RedirectResponse，直接返回它
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    # 使用原始 SQL 查詢獲取問題
    from sqlalchemy import text
    
    # 獲取問題
    question_query = """
        SELECT * FROM questions
        WHERE id = :question_id
    """
    result = db.execute(text(question_query), {"question_id": question_id}).fetchone()
    
    if not result:
        return RedirectResponse(url="/questions", status_code=302)
    
    # 將結果轉換為字典
    question = dict(result._mapping)
    
    # 確保日期欄位是可用的格式
    for date_field in ['question_date', 'created_date', 'closed_date']:
        if date_field in question and question[date_field] is not None:
            if isinstance(question[date_field], str):
                try:
                    # 嘗試解析日期字串
                    question[date_field] = datetime.fromisoformat(question[date_field].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    # 如果解析失敗，設為 None
                    question[date_field] = None
    
    # 獲取報告部門
    report_dept_query = """
        SELECT d.* FROM departments d
        JOIN question_report_department qrd ON d.id = qrd.department_id
        WHERE qrd.question_id = :question_id
    """
    report_depts = db.execute(text(report_dept_query), {"question_id": question_id}).fetchall()
    question['report_departments'] = [dict(dept._mapping) for dept in report_depts]
    
    # 獲取回答部門
    answer_dept_query = """
        SELECT d.* FROM departments d
        JOIN question_answer_department qad ON d.id = qad.department_id
        WHERE qad.question_id = :question_id
    """
    answer_depts = db.execute(text(answer_dept_query), {"question_id": question_id}).fetchall()
    question['answer_departments'] = [dict(dept._mapping) for dept in answer_depts]
    
    # 檢查用戶是否有權限訪問任何填報部門
    can_access = False
    for dept in question['report_departments']:
        if can_access_department(current_user, dept['id'], db):
            can_access = True
            break
    
    if not can_access:
        return RedirectResponse(url="/questions", status_code=302)
    
    # 獲取用戶有權限的部門（用於回答單位選擇）
    accessible_departments = []
    all_departments = db.query(Department).all()
    
    # 檢查用戶是否有權限訪問每個部門
    for dept in all_departments:
        if can_access_department(current_user, dept.id, db):
            accessible_departments.append(dept)
    
    # 獲取當前問題的填報部門和回答部門ID列表
    report_department_ids = [dept['id'] for dept in question['report_departments']]
    answer_department_ids = [dept['id'] for dept in question['answer_departments']]
    
    # 添加一些模板可能需要的方法
    question['get_report_departments'] = lambda q=question: q['report_departments']
    question['get_answer_departments'] = lambda q=question: q['answer_departments']
    
    return templates.TemplateResponse(
        "questions/edit.html",
        {
            "request": request, 
            "question": question,
            "departments": accessible_departments,
            "report_department_ids": report_department_ids,
            "answer_department_ids": answer_department_ids,
            "current_user": current_user
        }
    )

@router.put("/{question_id}/summary", response_class=JSONResponse)
async def update_summary(
    question_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="問題不存在")
    
    # 檢查是否為問題創建者
    if question.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有問題創建者可以編輯摘要")
    
    # 檢查問題是否已結案
    if question.status.value == "closed":
        raise HTTPException(status_code=400, detail="問題已結案，無法編輯摘要")
    
    # 從請求體中獲取摘要
    data = await request.json()
    summary = data.get("summary", "")
    
    # 更新摘要
    question.summary = summary
    
    db.commit()
    return {"success": True}

@router.post("/create", response_class=HTMLResponse)
async def create_question(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    form_data = await request.form()
    
    # 確保部門ID是整數
    try:
        report_department_id = int(form_data.get("report_department_id", current_user.department_id))
    except (TypeError, ValueError):
        report_department_id = current_user.department_id
    
    # 驗證部門是否存在
    department = db.query(Department).filter(Department.id == report_department_id).first()
    if not department:
        return templates.TemplateResponse(
            "questions/create.html",
            {
                "request": request,
                "current_user": current_user,
                "error": "無效的填報單位"
            }
        )
    
    # ... existing code ... 