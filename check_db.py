import sqlite3
import os

def check_database():
    # 獲取數據庫路徑
    db_path = os.path.join(os.getcwd(), "database.db")
    print(f"連接到數據庫: {db_path}")
    
    # 連接到 SQLite 數據庫
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 列出所有表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("\n資料表列表:")
    for table in tables:
        print(f"- {table['name']}")
    
    # 檢查 users 表結構
    cursor.execute("PRAGMA table_info(users);")
    columns = cursor.fetchall()
    print("\nusers 表結構:")
    for col in columns:
        print(f"- {col['name']} ({col['type']})")
    
    # 檢查 admin 用戶
    cursor.execute("SELECT * FROM users WHERE username = 'admin';")
    admin = cursor.fetchone()
    if admin:
        print("\nAdmin 用戶信息:")
        for key in admin.keys():
            print(f"- {key}: {admin[key]}")
    else:
        print("\n找不到 admin 用戶")
    
    # 檢查地政處
    cursor.execute("SELECT * FROM departments WHERE name = '地政處';")
    land_dept = cursor.fetchone()
    if land_dept:
        print(f"\n地政處信息 (ID: {land_dept['id']}):")
        for key in land_dept.keys():
            print(f"- {key}: {land_dept[key]}")
        
        # 檢查地政處相關用戶
        cursor.execute("SELECT * FROM users WHERE department_id = ?;", (land_dept['id'],))
        users = cursor.fetchall()
        print("\n地政處直接關聯用戶:")
        if users:
            for user in users:
                print(f"- {user['username']} (ID: {user['id']})")
        else:
            print("- 無直接關聯用戶")
        
        # 檢查 user_department 表中的關聯
        cursor.execute("""
            SELECT u.username, u.id 
            FROM users u 
            JOIN user_department ud ON u.id = ud.user_id 
            WHERE ud.department_id = ?
        """, (land_dept['id'],))
        user_depts = cursor.fetchall()
        print("\n地政處在 user_department 表中的關聯:")
        if user_depts:
            for user in user_depts:
                print(f"- {user['username']} (ID: {user['id']})")
        else:
            print("- 無關聯用戶")
    else:
        print("\n找不到地政處")
    
    # 分析可能重疊的表格功能
    print("\n分析表格功能重疊情況:")
    print("1. 用戶部門關係:")
    print("   - 主表關係: users 表的 department_id 字段 -> 單一部門關係")
    print("   - 多對多關係: user_department 表 -> 多部門關係")
    
    # 查詢既有直接部門關係又有多對多部門關係的用戶
    cursor.execute("""
        SELECT u.id, u.username, u.department_id, COUNT(ud.department_id) as dept_count
        FROM users u
        LEFT JOIN user_department ud ON u.id = ud.user_id
        WHERE u.department_id IS NOT NULL
        GROUP BY u.id
        HAVING dept_count > 0
    """)
    overlap_users = cursor.fetchall()
    print("\n   同時使用兩種部門關係的用戶:")
    if overlap_users:
        for user in overlap_users:
            print(f"   - {user['username']} (ID: {user['id']}, 主部門: {user['department_id']}, 關聯部門數: {user['dept_count']})")
    else:
        print("   - 無")
    
    # 關閉連接
    conn.close()

if __name__ == "__main__":
    check_database() 