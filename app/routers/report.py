from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.models.report import Report
from app.models.question import Question
from app.schemas.report import ReportCreate
from app.dependencies import get_current_user, has_permission

router = APIRouter()

@router.post("/{question_id}", dependencies=[Depends(has_permission("create_report"))])
def create_report(question_id: int, report: ReportCreate, db: Session = Depends(get_db), user = Depends(get_current_user)):
    db_question = db.query(Question).filter(Question.id == question_id).first()
    if not db_question:
        raise HTTPException(status_code=404, detail="Question not found")
    new_report = Report(
        question_id=question_id,
        reply_content=report.reply_content,
        user_id=user.id
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)
    return new_report


@router.get("/{question_id}")
def get_reports(question_id: int, db: Session = Depends(get_db)):
    return db.query(Report).filter(Report.question_id == question_id).all()
