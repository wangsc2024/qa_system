import os
from sqlalchemy.orm import Session
from app.database import SessionLocal, Base, engine
from app.models.role import Role
from app.models.department import Department
from app.models.user import User
from app.models.question import Question, QuestionStatus
from app.models.report import Report
from passlib.context import CryptContext
from datetime import datetime, timedelta
from sqlalchemy import insert
from app.models.question import question_report_department, question_answer_department

# 刪除現有資料庫
if os.path.exists("qa_system.db"):
    os.remove("qa_system.db")
    print("已刪除現有資料庫")

# 創建新的資料表
Base.metadata.create_all(bind=engine)
print("已創建新的資料表")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def reset_db():
    db: Session = SessionLocal()
    
    try:
        # 建立部門
        root_department = Department(code="0000", name="總管理處")
        it_department = Department(code="1000", name="資訊部門")
        hr_department = Department(code="2000", name="人力資源部")
        finance_department = Department(code="3000", name="財務部")
        admin_department = Department(code="4000", name="行政處")
        water_department = Department(code="5000", name="水利處")
        
        db.add_all([root_department, it_department, hr_department, finance_department, admin_department, water_department])
        db.flush()
        
        # 建立角色
        admin_role = Role(
            name="系統管理員",
            description="擁有所有權限",
            permissions=[
                "read_question", "create_question", "edit_question", "close_question",
                "read_report", "create_report", "edit_report",
                "export_questions", "export_reports",
                "manage_users", "manage_roles", "manage_departments", "manage_all"
            ]
        )
        
        manager_role = Role(
            name="部門主管",
            description="可以管理問題和回覆",
            permissions=[
                "read_question", "create_question", "edit_question", "close_question",
                "read_report", "create_report", "edit_report"
            ]
        )
        
        staff_role = Role(
            name="一般員工",
            description="只能查看和回覆問題",
            permissions=[
                "read_question", "create_question",
                "read_report", "create_report", "edit_report"
            ],
            departments=[it_department, hr_department]  # 只能訪問資訊部門和人力資源部
        )
        
        db.add_all([admin_role, manager_role, staff_role])
        db.flush()
        
        # 建立用戶
        admin_user = User(
            username="admin",
            password_hash=pwd_context.hash("admin123"),
            email="admin@example.com",
            is_active=True
        )
        # 設定角色和部門
        admin_user.roles = [admin_role]
        admin_user.departments = [root_department]
        
        manager_user = User(
            username="manager",
            password_hash=pwd_context.hash("manager123"),
            email="manager@example.com",
            is_active=True
        )
        # 設定角色和部門
        manager_user.roles = [manager_role]
        manager_user.departments = [root_department]
        
        it_user = User(
            username="it_staff",
            password_hash=pwd_context.hash("staff123"),
            email="it@example.com",
            is_active=True
        )
        # 設定角色和部門
        it_user.roles = [staff_role]
        it_user.departments = [it_department]
        
        hr_user = User(
            username="hr_staff",
            password_hash=pwd_context.hash("staff123"),
            email="hr@example.com",
            is_active=True
        )
        # 設定角色和部門
        hr_user.roles = [staff_role]
        hr_user.departments = [hr_department]
        
        db.add_all([admin_user, manager_user, it_user, hr_user])
        db.flush()
        
        # 建立問題
        question1 = Question(
            title="系統登入問題",
            content="無法登入系統，顯示密碼錯誤",
            year=2023,
            question_date=datetime.utcnow() - timedelta(days=5),
            created_date=datetime.utcnow() - timedelta(days=5),
            creator_id=manager_user.id
        )
        
        question2 = Question(
            title="薪資計算錯誤",
            content="本月薪資計算有誤，加班費未計入",
            year=2023,
            question_date=datetime.utcnow() - timedelta(days=3),
            created_date=datetime.utcnow() - timedelta(days=3),
            creator_id=it_user.id
        )
        
        question3 = Question(
            title="網路連線不穩定",
            content="辦公室網路經常斷線，影響工作效率",
            year=2023,
            question_date=datetime.utcnow() - timedelta(days=1),
            created_date=datetime.utcnow() - timedelta(days=1),
            status=QuestionStatus.CLOSED,
            summary="已更換新的網路設備，問題已解決",
            closed_date=datetime.utcnow(),
            creator_id=hr_user.id
        )
        
        db.add_all([question1, question2, question3])
        db.flush()
        
        # 添加問題和部門關聯
        # 添加填報部門關聯
        db.execute(insert(question_report_department).values(question_id=question1.id, department_id=root_department.id))
        db.execute(insert(question_report_department).values(question_id=question2.id, department_id=it_department.id))
        db.execute(insert(question_report_department).values(question_id=question3.id, department_id=hr_department.id))
        
        # 添加回答部門關聯
        db.execute(insert(question_answer_department).values(question_id=question1.id, department_id=it_department.id))
        db.execute(insert(question_answer_department).values(question_id=question2.id, department_id=hr_department.id))
        db.execute(insert(question_answer_department).values(question_id=question3.id, department_id=it_department.id))
        
        # 建立報告
        report1 = Report(
            question_id=question1.id,
            reply_content="請嘗試重設密碼，如果問題持續存在請聯繫IT部門",
            reply_date=datetime.utcnow() - timedelta(days=4),
            user_id=it_user.id,
            department_id=it_department.id
        )
        
        report2 = Report(
            question_id=question2.id,
            reply_content="已收到您的問題，我們將檢查薪資計算系統",
            reply_date=datetime.utcnow() - timedelta(days=2),
            user_id=hr_user.id,
            department_id=hr_department.id
        )
        
        report3 = Report(
            question_id=question3.id,
            reply_content="我們將派技術人員檢查網路設備",
            reply_date=datetime.utcnow() - timedelta(days=1),
            user_id=it_user.id,
            department_id=it_department.id
        )
        
        db.add_all([report1, report2, report3])
        
        db.commit()
        print("資料庫重置完成，已添加測試數據")
    except Exception as e:
        db.rollback()
        print(f"重置過程中發生錯誤: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_db() 