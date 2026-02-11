from app.database import get_db
import contextlib
from sqlalchemy import text

def check_users_departments():
    with contextlib.closing(next(get_db())) as db:
        # 查詢 admin 用戶信息
        result = db.execute(text("SELECT * FROM users WHERE username = 'admin'"))
        admin_user = result.fetchone()
        if admin_user:
            print(f"Admin用戶信息:")
            # 獲取列名
            columns = result.keys()
            for column in columns:
                print(f"  - {column}: {admin_user[column]}")
        else:
            print("找不到 admin 用戶")
        
        # 查詢地政處信息
        result = db.execute(text("SELECT * FROM departments WHERE name = '地政處'"))
        land_dept = result.fetchone()
        if land_dept:
            print(f"\n地政處信息:")
            # 獲取列名
            columns = result.keys()
            for column in columns:
                print(f"  - {column}: {land_dept[column]}")
            
            print("\n地政處相關用戶:")
            result = db.execute(
                text("SELECT u.* FROM users u WHERE u.department_id = :dept_id"), 
                {"dept_id": land_dept['id']}
            )
            for user in result.fetchall():
                print(f"  - {user['username']} (ID: {user['id']})")
            
            # 檢查 user_department 表
            print("\n地政處在 user_department 表中的關聯:")
            result = db.execute(
                text("SELECT u.username, u.id FROM users u JOIN user_department ud ON u.id = ud.user_id WHERE ud.department_id = :dept_id"),
                {"dept_id": land_dept['id']}
            )
            for user in result.fetchall():
                print(f"  - {user['username']} (ID: {user['id']})")
        else:
            print("找不到地政處")

if __name__ == "__main__":
    check_users_departments() 