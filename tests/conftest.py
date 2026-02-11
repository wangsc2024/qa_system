import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
import os

from app.database import Base, get_db
from app.models import user, department, question, role, report # 預加載所有模型
from main import app

# 使用獨立的測試資料庫
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_qa.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    # 測試開始前創建所有表
    Base.metadata.create_all(bind=engine)
    yield
    # 測試結束後刪除測試資料庫文件
    Base.metadata.drop_all(bind=engine)
    engine.dispose()  # 重要：關閉所有連接以釋放文件
    if os.path.exists("./test_qa.db"):
        try:
            os.remove("./test_qa.db")
        except PermissionError:
            pass

@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()

@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    del app.dependency_overrides[get_db]
