from app.database import engine
from sqlalchemy import text

def update_database():
    try:
        with engine.connect() as conn:
            # 檢查 full_name 欄位是否存在
            result = conn.execute(text("PRAGMA table_info(users)"))
            columns = [row[1] for row in result.fetchall()]
            
            # 如果 full_name 欄位不存在，則添加
            if 'full_name' not in columns:
                print("添加 full_name 欄位...")
                conn.execute(text("ALTER TABLE users ADD COLUMN full_name VARCHAR"))
                conn.commit()
                print("資料庫更新成功！")
            else:
                print("full_name 欄位已存在，無需更新。")
    except Exception as e:
        print(f"更新資料庫時發生錯誤: {str(e)}")

if __name__ == "__main__":
    update_database() 