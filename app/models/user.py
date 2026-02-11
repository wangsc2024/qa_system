from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Table
from sqlalchemy.orm import relationship
from app.database import Base
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 用戶-角色多對多關聯表
user_role = Table(
    "user_role",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True)
)

# 用戶-部門多對多關聯表
user_department = Table(
    "user_department",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("department_id", Integer, ForeignKey("departments.id"), primary_key=True)
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    full_name = Column(String, nullable=True)
    password_hash = Column(String)
    email = Column(String, unique=True, nullable=True)
    is_active = Column(Boolean, default=True)

    # 單一角色關係 (向後兼容)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    role = relationship("Role", foreign_keys=[role_id], back_populates="users")
    
    # 單一部門關係 (向後兼容)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    department = relationship("Department", foreign_keys=[department_id], back_populates="users")
    
    # 多對多關係
    roles = relationship("Role", secondary=user_role, backref="all_users")
    departments = relationship("Department", secondary=user_department, back_populates="all_users")
    
    # 其他關係
    reports = relationship("Report", back_populates="user")

    def set_password(self, password):
        self.password_hash = pwd_context.hash(password)

    def verify_password(self, password):
        if not self.password_hash:
            return False
        return pwd_context.verify(password, self.password_hash) 