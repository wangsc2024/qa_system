import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_departments():
    try:
        # 連接到 SQLite 資料庫
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # 1. 獲取所有部門
        cursor.execute("SELECT id, code, name FROM departments")
        departments = cursor.fetchall()
        
        # 2. 更新處級部門代碼
        processed_codes = set()
        for dept_id, code, name in departments:
            # 如果代碼長度為2，加上00
            if len(code) == 2:
                bureau_code = code + "00"
            # 如果代碼長度為4，檢查是否以00結尾
            elif len(code) == 4:
                if code.endswith("00"):
                    bureau_code = code  # 保持原樣
                else:
                    bureau_code = code[:2] + "00"  # 取前2位加00
            # 其他長度的代碼
            else:
                bureau_code = code[:2] + "00" if len(code) >= 2 else code + "00"
                
            # 檢查是否有重複的處級部門代碼
            if bureau_code in processed_codes:
                logger.info(f"刪除重複部門: {code} - {name}")
                # 刪除重複部門
                cursor.execute("DELETE FROM departments WHERE id = ?", (dept_id,))
                # 刪除相關的多對多關係
                cursor.execute("DELETE FROM user_department WHERE department_id = ?", (dept_id,))
                cursor.execute("DELETE FROM role_department WHERE department_id = ?", (dept_id,))
            else:
                # 更新部門代碼
                cursor.execute("UPDATE departments SET code = ? WHERE id = ?", (bureau_code, dept_id))
                processed_codes.add(bureau_code)
                logger.info(f"更新部門: {code} -> {bureau_code} ({name})")
        
        # 3. 提交更改
        conn.commit()
        logger.info("部門資料更新完成")
        
        # 4. 更新使用者部門關聯
        cursor.execute("""
            SELECT u.id, u.username, d.id, d.code 
            FROM users u 
            JOIN departments d ON u.department_id = d.id
        """)
        user_depts = cursor.fetchall()
        
        for user_id, username, dept_id, dept_code in user_depts:
            if not dept_code.endswith("00"):
                # 找到對應的處級部門
                bureau_code = dept_code[:2] + "00"
                cursor.execute("SELECT id FROM departments WHERE code = ?", (bureau_code,))
                bureau_dept = cursor.fetchone()
                
                if bureau_dept:
                    bureau_dept_id = bureau_dept[0]
                    # 更新使用者部門
                    cursor.execute("UPDATE users SET department_id = ? WHERE id = ?", (bureau_dept_id, user_id))
                    # 更新多對多關係
                    cursor.execute("DELETE FROM user_department WHERE user_id = ?", (user_id,))
                    cursor.execute("INSERT INTO user_department (user_id, department_id) VALUES (?, ?)", (user_id, bureau_dept_id))
                    logger.info(f"更新使用者 {username} 的部門關聯到 {bureau_code}")
        
        # 最終提交
        conn.commit()
        logger.info("使用者部門關聯更新完成")
        
    except Exception as e:
        logger.error(f"更新失敗: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    update_departments() 