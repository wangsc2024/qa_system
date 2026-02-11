import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def remove_role_department_table():
    try:
        # 連接到 SQLite 資料庫
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # 檢查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='role_department'")
        if cursor.fetchone():
            # 刪除 role_department 表
            cursor.execute("DROP TABLE role_department")
            conn.commit()
            logger.info("已刪除 role_department 表")
        else:
            logger.info("role_department 表不存在，無需刪除")
        
    except Exception as e:
        logger.error(f"刪除 role_department 表失敗: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    remove_role_department_table() 