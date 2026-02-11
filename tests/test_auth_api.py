import pytest
from app.models.user import User
from app.models.role import Role
from app.models.department import Department
from app.dependencies import create_access_token
from datetime import timedelta

@pytest.fixture
def test_password():
    return "testpass123"

@pytest.fixture
def test_user(db_session, test_password):
    # 建立角色
    role = Role(name="測試角色", permissions=["create_question", "read_question", "view_reports"])
    db_session.add(role)
    db_session.commit()
    
    # 建立部門
    dept = Department(code="9900", name="測試部門")
    db_session.add(dept)
    db_session.commit()
    
    # 建立用戶
    user = User(
        username="testapiuser",
        full_name="API Test User",
        email="api@test.com",
        is_active=True,
        role_id=role.id,
        department_id=dept.id
    )
    user.set_password(test_password)
    db_session.add(user)
    
    # 多對多關聯
    user.roles.append(role)
    user.departments.append(dept)
    
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def auth_token(test_user):
    return create_access_token(data={"sub": test_user.username})

@pytest.fixture
def auth_headers(auth_token):
    return {"Cookie": f"access_token=Bearer {auth_token}"}

def test_login_success(client, test_user, test_password):
    # 使用 Form Data 模擬登入
    response = client.post(
        "/auth/login",
        data={"username": test_user.username, "password": test_password},
        follow_redirects=False
    )
    assert response.status_code == 303
    assert "access_token" in response.cookies
    assert response.headers["location"] == "/"

def test_login_failure(client, test_user):
    response = client.post(
        "/auth/login",
        data={"username": test_user.username, "password": "wrongpassword"},
        follow_redirects=False
    )
    assert response.status_code == 401
    assert "access_token" not in response.cookies

def test_logout(client, auth_headers):
    # 帶着 Cookie 請求登出
    response = client.get("/auth/logout", headers=auth_headers, follow_redirects=False)
    assert response.status_code == 303
    # 驗證 Cookie 是否被清除 (在某些 TestClient 中可能表現為 expires 為過期時間)
    # 檢查是否有 set-cookie 指令
    cookie_header = response.headers.get("set-cookie", "")
    assert "access_token=;" in cookie_header or 'access_token=""' in cookie_header or "Max-Age=0" in cookie_header
