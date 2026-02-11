import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, engine
from app.models.department import Department
from app.models.user import User
from app.models.role import Role  # 確保載入 Role 模型
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_database():
    # 確保所有模型都已載入
    Base.metadata.create_all(bind=engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # 1. 更新所有部門代碼，確保處級單位的代碼以00結尾
        departments = session.query(Department).all()
        processed_codes = set()
        
        for dept in departments:
            # 處理不同長度的代碼
            if len(dept.code) == 2:
                # 2位數代碼，加上00
                bureau_code = dept.code + "00"
            elif len(dept.code) == 4:
                # 4位數代碼，保持原樣如果已經以00結尾，否則只保留前2位並加上00
                if dept.code.endswith("00"):
                    bureau_code = dept.code
                else:
                    bureau_code = dept.code[:2] + "00"
            else:
                # 其他長度的代碼，嘗試提取前2位並加上00
                bureau_code = dept.code[:2] + "00" if len(dept.code) >= 2 else dept.code + "00"
            
            # 檢查是否已處理過此處代碼
            if bureau_code in processed_codes:
                logger.info(f"刪除重複部門: {dept.code} - {dept.name}")
                session.delete(dept)
                continue
                
            # 更新部門代碼
            dept.code = bureau_code
            processed_codes.add(bureau_code)
            logger.info(f"更新部門代碼: {dept.code} - {dept.name}")
        
        # 2. 更新使用者的部門關聯
        users = session.query(User).all()
        for user in users:
            if user.department:
                # 處理部門代碼
                if len(user.department.code) == 2:
                    bureau_code = user.department.code + "00"
                elif len(user.department.code) == 4:
                    if user.department.code.endswith("00"):
                        bureau_code = user.department.code
                    else:
                        bureau_code = user.department.code[:2] + "00"
                else:
                    bureau_code = user.department.code[:2] + "00" if len(user.department.code) >= 2 else user.department.code + "00"
                
                # 獲取處級單位
                new_dept = session.query(Department).filter(
                    Department.code == bureau_code
                ).first()
                
                if new_dept:
                    user.department_id = new_dept.id
                    # 更新多對多關係
                    if new_dept not in user.departments:
                        user.departments = [new_dept]
                    logger.info(f"更新使用者 {user.username} 的部門關聯到 {new_dept.code}")
        
        session.commit()
        logger.info("資料庫更新完成")
        
    except Exception as e:
        logger.error(f"更新失敗: {str(e)}")
        session.rollback()
        raise  # 重新拋出異常以查看完整的錯誤訊息
    finally:
        session.close()

if __name__ == "__main__":
    update_database() 