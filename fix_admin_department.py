from app.database import get_db
from sqlalchemy import text
import logging

def update_admin_department():
    """更新 admin 用戶的部門為地政處"""
    try:
        # 獲取數據庫連接
        db = next(get_db())
        
        # 首先查詢地政處的 ID
        result = db.execute(text("SELECT id FROM departments WHERE name = '地政處'"))
        land_dept = result.fetchone()
        
        if not land_dept:
            print("錯誤: 找不到地政處")
            return
        
        land_dept_id = land_dept[0]
        print(f"地政處 ID: {land_dept_id}")
        
        # 查詢 admin 用戶
        result = db.execute(text("SELECT id, username, department_id FROM users WHERE username = 'admin'"))
        admin = result.fetchone()
        
        if not admin:
            print("錯誤: 找不到 admin 用戶")
            return
        
        admin_id = admin[0]
        current_dept_id = admin[2]
        print(f"Admin 用戶 ID: {admin_id}, 當前部門 ID: {current_dept_id}")
        
        # 更新 admin 用戶的部門為地政處
        if current_dept_id != land_dept_id:
            db.execute(
                text("UPDATE users SET department_id = :dept_id WHERE id = :user_id"),
                {"dept_id": land_dept_id, "user_id": admin_id}
            )
            db.commit()
            print(f"已更新 admin 用戶的部門為地政處 (ID: {land_dept_id})")
        else:
            print("Admin 用戶已經屬於地政處，無需更新")
        
        # 檢查 user_department 表中是否已有關聯
        result = db.execute(
            text("SELECT * FROM user_department WHERE user_id = :user_id AND department_id = :dept_id"),
            {"user_id": admin_id, "dept_id": land_dept_id}
        )
        user_dept = result.fetchone()
        
        if not user_dept:
            # 添加到 user_department 表中
            db.execute(
                text("INSERT INTO user_department (user_id, department_id) VALUES (:user_id, :dept_id)"),
                {"user_id": admin_id, "dept_id": land_dept_id}
            )
            db.commit()
            print(f"已添加 admin 用戶與地政處的多對多關聯")
        else:
            print("user_department 表中已存在 admin 與地政處的關聯")
        
        print("操作完成")
        
    except Exception as e:
        print(f"錯誤: {str(e)}")
        logging.error(f"更新 admin 用戶部門時發生錯誤: {str(e)}")
        db.rollback()

if __name__ == "__main__":
    update_admin_department() 