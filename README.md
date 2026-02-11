# 問題填報回覆系統

## 簡介
本系統使用 **FastAPI + SQLite + SQLAlchemy + JWT** 製作，提供：
- 問題填報、回覆、結案管理
- Excel 匯出
- 帳號、角色、權限管理
- 單位二層結構
- 簡易 Bootstrap 5 前端模板

---

## 預設管理員
- 帳號：admin
- 密碼：admin123

---

## 安裝與執行

```bash
git clone https://github.com/your-repo/issue_reporting_system.git
cd issue_reporting_system
python -m venv venv
source venv/bin/activate  # Windows 用 venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
python init_db.py
uvicorn main:app --reload --host 172.20.11.22 --port 8080
