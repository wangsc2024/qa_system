import pytest
from app.models.user import User
from app.models.role import Role
from app.models.department import Department
from app.models.question import Question, QuestionStatus
from app.dependencies import create_access_token

@pytest.fixture
def admin_user(db_session):
    # 建立具有完整權限的角色
    role = Role(
        name="管理員", 
        permissions=[
            "create_question", "read_question", "edit_question", 
            "delete_question", "close_question", "manage_all"
        ]
    )
    db_session.add(role)
    db_session.commit()
    
    dept = Department(code="0100", name="管理部")
    db_session.add(dept)
    db_session.commit()
    
    user = User(username="admin_test", full_name="Admin", is_active=True, role_id=role.id, department_id=dept.id)
    user.set_password("admin123")
    user.roles.append(role)
    user.departments.append(dept)
    db_session.add(user)
    db_session.commit()
    return user

@pytest.fixture
def auth_headers(admin_user):
    token = create_access_token(data={"sub": admin_user.username})
    return {"Cookie": f"access_token=Bearer {token}"}

def test_create_question_api(client, db_session, auth_headers):
    # 準備部門
    dept1 = Department(code="1001", name="部門1")
    dept2 = Department(code="1002", name="部門2")
    db_session.add_all([dept1, dept2])
    db_session.commit()
    
    # 呼叫 API
    data = {
        "title": "API 測試問題",
        "content": "這是內容",
        "report_department_ids": [dept1.id],
        "answer_department_ids": [dept2.id],
        "year": 113
    }
    
    response = client.post("/questions/", json=data, headers=auth_headers)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["title"] == "API 測試問題"
    assert res_data["id"] is not None

def test_list_questions_api(client, db_session, auth_headers, admin_user):
    # 先建立一個問題
    q = Question(title="List Test", content="Content", creator_id=admin_user.id)
    db_session.add(q)
    db_session.commit()
    
    response = client.get("/questions/", headers=auth_headers)
    assert response.status_code == 200
    # 注意：根據路由實現，如果是 Web 請求可能會回傳 HTML，測試時需確保 Accept header 或檢查回傳內容
    # 我們的 questions 列表路由目前似乎主要回傳 TemplateResponse (HTML)
    assert "List Test" in response.text

def test_get_question_detail_api(client, db_session, auth_headers, admin_user):
    q = Question(title="Detail Test", content="UniqueContent", creator_id=admin_user.id)
    db_session.add(q)
    db_session.commit()
    
    response = client.get(f"/questions/{q.id}", headers=auth_headers)
    assert response.status_code == 200
    assert "Detail Test" in response.text
    assert "UniqueContent" in response.text

def test_close_question_api(client, db_session, auth_headers, admin_user):
    q = Question(title="Close Test", content="Content", creator_id=admin_user.id, status=QuestionStatus.PENDING)
    db_session.add(q)
    db_session.commit()
    
    # 測試結案
    response = client.post(f"/questions/{q.id}/close", headers=auth_headers, follow_redirects=False)
    assert response.status_code == 302 # 通常重定向回列表或詳情
    
    db_session.refresh(q)
    assert q.status == QuestionStatus.CLOSED
