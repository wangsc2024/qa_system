from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime, date
from app.models.question import QuestionStatus

class QuestionBase(BaseModel):
    title: str
    content: str
    year: Optional[int] = None
    question_date: Optional[datetime] = None

class QuestionCreate(QuestionBase):
    report_department_ids: List[int]  # 填報部門IDs
    answer_department_ids: List[int]  # 回答部門IDs
    year: Optional[int] = None
    question_date: Optional[date] = None

class QuestionUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    report_department_ids: Optional[List[int]] = None
    answer_department_ids: Optional[List[int]] = None

class QuestionInDB(QuestionBase):
    id: int
    created_date: datetime
    status: QuestionStatus
    creator_id: int
    
    model_config = ConfigDict(from_attributes=True)


class Question(QuestionInDB):
    pass
