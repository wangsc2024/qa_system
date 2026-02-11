from sqlalchemy import Column, Integer, String, JSON, Table, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    permissions = Column(JSON)  # 存儲為 JSON 字符串，適用於 SQLite
    
    # 單一角色關係 (向後兼容)
    users = relationship("User", back_populates="role", foreign_keys="User.role_id") 