from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, Table
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum

# 問題-填報部門多對多關聯表
question_report_department = Table(
    "question_report_department",
    Base.metadata,
    Column("question_id", Integer, ForeignKey("questions.id"), primary_key=True),
    Column("department_id", Integer, ForeignKey("departments.id"), primary_key=True)
)

# 問題-回答部門多對多關聯表
question_answer_department = Table(
    "question_answer_department",
    Base.metadata,
    Column("question_id", Integer, ForeignKey("questions.id"), primary_key=True),
    Column("department_id", Integer, ForeignKey("departments.id"), primary_key=True)
)

class QuestionStatus(enum.Enum):
    PENDING = "pending"  # 未回覆
    ANSWERED = "answered"  # 已回覆
    CLOSED = "closed"  # 已結案

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    year = Column(Integer, nullable=True)  # 年度
    question_date = Column(DateTime, nullable=True)  # 問題日期
    created_date = Column(DateTime, default=datetime.utcnow)
    status = Column(Enum(QuestionStatus), default=QuestionStatus.PENDING)
    summary = Column(Text, nullable=True)
    closed_date = Column(DateTime, nullable=True)
    creator_id = Column(Integer, ForeignKey("users.id"))
    
    # 問題創建者
    creator = relationship("User", foreign_keys=[creator_id])
    
    # 問題的填報部門，多對多關聯
    report_departments = relationship(
        "Department", 
        secondary=question_report_department, 
        back_populates="reported_questions"
    )
    
    # 問題指派的回答部門，多對多關聯
    answer_departments = relationship(
        "Department", 
        secondary=question_answer_department, 
        back_populates="assigned_questions"
    )
    
    # 問題的回覆
    reports = relationship("Report", back_populates="question", cascade="all, delete-orphan")
