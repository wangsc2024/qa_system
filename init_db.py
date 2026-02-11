import os
import sys
from sqlalchemy.orm import Session
from app.database import SessionLocal, Base, engine
from app.models.role import Role
from app.models.department import Department
from app.models.user import User
from app.models.question import Question, QuestionStatus
from app.models.report import Report
from passlib.context import CryptContext
from datetime import datetime, timedelta

# 刪除現有資料庫
if os.path.exists("qa_system.db"):
    try:
        os.remove("qa_system.db")
        print("已刪除現有資料庫")
    except PermissionError:
        print("無法刪除資料庫文件，請確保沒有其他程序正在使用它")
        sys.exit(1)

# 創建新的資料表
Base.metadata.create_all(bind=engine)
print("已創建新的資料表")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def init_db():
    db: Session = SessionLocal()
    
    try:
        # 建立部門
        root_department = Department(name="總管理處")
        it_department = Department(name="資訊部門")
        hr_department = Department(name="人力資源部")
        finance_department = Department(name="財務部")
        admin_department = Department(name="行政處")
        water_department = Department(name="水利處")
        
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
                "manage_users", "manage_roles"
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
        # 設定部門主管可訪問的部門
        manager_role.departments.append(root_department)
        
        staff_role = Role(
            name="一般員工",
            description="只能查看和回覆問題",
            permissions=[
                "read_question", "create_question",
                "read_report", "create_report", "edit_report"
            ]
        )
        # 設定一般員工可訪問的部門
        staff_role.departments.extend([it_department, hr_department])
        
        viewer_role = Role(
            name="查閱者",
            description="只能查看問題和回覆",
            permissions=[
                "read_question", "read_report"
            ]
        )
        # 設定查閱者可訪問的部門
        viewer_role.departments.append(finance_department)
        
        db.add_all([admin_role, manager_role, staff_role, viewer_role])
        db.flush()
        
        # 建立用戶
        admin_user = User(
            username="admin",
            password_hash=pwd_context.hash("admin123"),
            email="admin@example.com",
            is_active=True
        )
        # 設定管理員角色和部門
        admin_user.roles.append(admin_role)
        admin_user.departments.append(root_department)
        
        manager_user = User(
            username="manager",
            password_hash=pwd_context.hash("manager123"),
            email="manager@example.com",
            is_active=True
        )
        # 設定主管角色和部門
        manager_user.roles.append(manager_role)
        manager_user.departments.append(root_department)
        
        it_user = User(
            username="it_staff",
            password_hash=pwd_context.hash("staff123"),
            email="it@example.com",
            is_active=True
        )
        # 設定IT員工角色和部門
        it_user.roles.append(staff_role)
        it_user.departments.append(it_department)
        
        hr_user = User(
            username="hr_staff",
            password_hash=pwd_context.hash("staff123"),
            email="hr@example.com",
            is_active=True
        )
        # 設定HR員工角色和部門
        hr_user.roles.append(staff_role)
        hr_user.departments.append(hr_department)
        
        # 多角色用戶示例
        multi_role_user = User(
            username="multi_role",
            password_hash=pwd_context.hash("multi123"),
            email="multi@example.com",
            is_active=True
        )
        # 設定多個角色和部門
        multi_role_user.roles.extend([manager_role, staff_role])
        multi_role_user.departments.extend([root_department, it_department])
        
        db.add_all([admin_user, manager_user, it_user, hr_user, multi_role_user])
        db.flush()
        
        # 建立問題
        question1 = Question(
            title="系統登入問題",
            content="無法登入系統，顯示密碼錯誤",
            created_date=datetime.utcnow() - timedelta(days=5),
            creator_id=manager_user.id
        )
        # 設定填報部門和回答部門
        question1.report_departments.append(root_department)
        question1.answer_departments.append(it_department)
        
        question2 = Question(
            title="薪資計算錯誤",
            content="本月薪資計算有誤，加班費未計入",
            created_date=datetime.utcnow() - timedelta(days=3),
            creator_id=it_user.id
        )
        # 設定填報部門和回答部門
        question2.report_departments.append(it_department)
        question2.answer_departments.append(hr_department)
        
        question3 = Question(
            title="網路連線不穩定",
            content="辦公室網路經常斷線，影響工作效率",
            created_date=datetime.utcnow() - timedelta(days=1),
            status=QuestionStatus.CLOSED,
            summary="已更換新的網路設備，問題已解決",
            closed_date=datetime.utcnow(),
            creator_id=hr_user.id
        )
        # 設定填報部門和回答部門
        question3.report_departments.append(hr_department)
        question3.answer_departments.append(it_department)
        
        # 多單位填報示例
        question4 = Question(
            title="多單位填報測試",
            content="這是一個測試多單位填報的問題",
            created_date=datetime.utcnow(),
            creator_id=multi_role_user.id
        )
        # 設定多個填報部門和回答部門
        question4.report_departments.extend([root_department, it_department, hr_department])
        question4.answer_departments.extend([it_department, finance_department])
        
        db.add_all([question1, question2, question3, question4])
        db.flush()
        
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
        
        # 多部門回覆示例
        report4 = Report(
            question_id=question1.id,
            reply_content="總管理處已確認此問題，請IT部門優先處理",
            reply_date=datetime.utcnow() - timedelta(days=3),
            user_id=manager_user.id,
            department_id=root_department.id
        )
        
        db.add_all([report1, report2, report3, report4])
        
        db.commit()
        print("資料庫初始化完成，已添加測試數據")
    except Exception as e:
        db.rollback()
        print(f"初始化過程中發生錯誤: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
