from app.database import get_db
from sqlalchemy import MetaData, inspect
import contextlib

def check_tables():
    with contextlib.closing(next(get_db())) as db:
        inspector = inspect(db.bind)
        
        # 獲取所有表名
        tables = inspector.get_table_names()
        print('資料表列表:')
        for table in tables:
            print(f'- {table}')
        
        # 檢查每個表的結構
        print("\n詳細資料表結構:")
        for table in tables:
            print(f"\n表名: {table}")
            columns = inspector.get_columns(table)
            print("列:")
            for column in columns:
                print(f"  - {column['name']}: {column['type']}")
            
            # 獲取外鍵
            foreign_keys = inspector.get_foreign_keys(table)
            if foreign_keys:
                print("外鍵:")
                for fk in foreign_keys:
                    print(f"  - {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}")

if __name__ == "__main__":
    check_tables() 