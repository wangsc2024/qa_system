import pytest
from app.models.user import User
from app.models.department import Department
from app.models.question import Question, QuestionStatus
from app.models.report import Report
from datetime import datetime

def test_create_user(db_session):
    user = User(username="testuser", full_name="Test User", email="test@example.com")
    user.set_password("password123")
    db_session.add(user)
    db_session.commit()
    
    db_user = db_session.query(User).filter(User.username == "testuser").first()
    assert db_user is not None
    assert db_user.username == "testuser"
    assert db_user.verify_password("password123")
    assert not db_user.verify_password("wrongpassword")

def test_department_hierarchy(db_session):
    parent = Department(code="0200", name="測試處")
    child = Department(code="0201", name="測試科", parent=parent)
    db_session.add(parent)
    db_session.add(child)
    db_session.commit()
    
    assert child.parent_id == parent.id
    assert child in parent.children
    assert parent.is_bureau is True
    assert child.is_bureau is False

def test_create_question_with_departments(db_session):
    # Setup users and depts
    dept_report = Department(code="0100", name="通報處")
    dept_answer = Department(code="0200", name="回答處")
    user = User(username="creator_q")
    db_session.add_all([dept_report, dept_answer, user])
    db_session.flush() # 確保 ID 生成
    
    # Create question
    question = Question(
        title="測試問題",
        content="內容",
        creator=user,
        status=QuestionStatus.PENDING
    )
    question.report_departments.append(dept_report)
    question.answer_departments.append(dept_answer)
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    
    assert question.id is not None
    assert dept_report in question.report_departments
    assert dept_answer in question.answer_departments
    assert question.status == QuestionStatus.PENDING

def test_question_reports(db_session):
    user = User(username="replier_r")
    dept = Department(code="0300", name="回覆處")
    question = Question(title="Q", content="C")
    db_session.add_all([user, dept, question])
    db_session.flush()
    
    report = Report(
        question=question,
        user=user,
        department_id=dept.id,
        reply_content="這是一個回覆",
        reply_date=datetime.utcnow()
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(question)
    
    assert len(question.reports) == 1
    assert question.reports[0].reply_content == "這是一個回覆"
    assert question.reports[0].user.username == "replier_r"
