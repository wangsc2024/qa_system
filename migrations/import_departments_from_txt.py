import sqlite3
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def import_departments():
    try:
        # 連接到 SQLite 資料庫
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # 首先清除現有部門資料
        cursor.execute("DELETE FROM departments")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='departments'")
        conn.commit()
        logger.info("已清除現有部門資料")
        
        # 定義部門資料 (從 department.txt 擷取)
        departments_data = [
            ("200", "民政處"),
            ("400", "城鄉發展處"),
            ("500", "教育處"),
            ("600", "農業處"),
            ("700", "社會處"),
            ("800", "地政處"),
            ("1000", "行政暨研考處"),
            ("1400", "工務處"),
            ("1500", "原住民處"),
            ("2200", "傳播暨國際事務處"),
            ("1600", "客家事務處"),
            ("1100", "人事處"),
            ("1200", "主計處"),
            ("1300", "政風處"),
            ("1700", "文化處"),
            ("1800", "勞動暨青年發展處"),
            ("1900", "水利處"),
            ("2100", "交通旅遊處"),
            ("2300", "長期照護處")
        ]
        
        # 確保部門代碼都是4位數
        formatted_departments = []
        for code, name in departments_data:
            # 格式化代碼為4位數，末尾為00
            if len(code) == 2:
                formatted_code = code + "00"
            elif len(code) == 3:
                formatted_code = "0" + code[0] + "00"
            elif len(code) == 4:
                formatted_code = code if code.endswith("00") else code[:2] + "00"
            else:
                formatted_code = code[:2] + "00"
            
            formatted_departments.append((formatted_code, name))
        
        # 插入部門資料
        for code, name in formatted_departments:
            try:
                cursor.execute(
                    "INSERT INTO departments (code, name) VALUES (?, ?)",
                    (code, name)
                )
                logger.info(f"匯入部門: {code} - {name}")
            except sqlite3.IntegrityError as e:
                logger.warning(f"部門代碼 {code} 錯誤: {str(e)}")
        
        # 提交更改
        conn.commit()
        logger.info(f"共匯入 {len(formatted_departments)} 筆部門資料")
        
    except Exception as e:
        logger.error(f"匯入失敗: {str(e)}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    import_departments() 