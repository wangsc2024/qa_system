from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(4), unique=True, index=True, nullable=False)  # 4位數代碼
    name = Column(String(50), nullable=False)
    parent_id = Column(Integer, ForeignKey('departments.id'), nullable=True)  # 父部門ID

    parent = relationship("Department", remote_side=[id], backref="children")
    
    # 問題關聯
    reported_questions = relationship(
        "Question",
        secondary="question_report_department",
        back_populates="report_departments"
    )
    
    assigned_questions = relationship(
        "Question",
        secondary="question_answer_department",
        back_populates="answer_departments"
    )

    
    # 用戶關聯
    users = relationship(
        "User",
        foreign_keys="User.department_id",
        back_populates="department"
    )
    
    # 添加 all_users 關係
    all_users = relationship(
        "User",
        secondary="user_department",
        back_populates="departments"
    )

    @property
    def is_bureau(self):
        """判斷是否為局/處級單位"""
        return self.code.endswith('00')
    
    @property
    def bureau_code(self):
        """獲取局/處代碼（前兩位）"""
        return self.code[:2]
    
    @property
    def section_code(self):
        """獲取科室代碼（後兩位）"""
        return self.code[2:]
