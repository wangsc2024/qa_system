# TDD 測試實作計畫 - 佛教問答系統 (QA System)

本計畫旨在透過測試驅動開發 (TDD) 模式，確保系統核心 API 功能的正確性與穩定性。

## 1. 測試環境設定
- **測試框架**: `pytest`
- **測試資料庫**: SQLite 記憶體資料庫或獨立的 `test_qa.db`。
- **工具**: `httpx` (用於 FastAPI 非同步測試), `pytest-asyncio`。

## 2. 測試範圍
### A. 認證模組 (`app/routers/auth.py`)
- [ ] `POST /auth/login`: 驗證帳號密碼登入。
- [ ] `GET /auth/logout`: 驗證登出並清除 Cookie。
- [ ] SSO 登入邏輯擬真測試 (模擬 SOAP 回傳結果)。

### B. 問題管理模組 (`app/routers/questions.py`)
- [ ] `POST /questions/`: 建立新問題 (檢查權限、部門關聯)。
- [ ] `GET /questions/`: 列表查詢 (檢查權限過濾、分頁)。
- [ ] `GET /questions/{id}`: 讀取問題詳情。
- [ ] `POST /questions/{id}/edit`: 編輯問題。
- [ ] `POST /questions/{id}/close`: 結案問題。

### C. 回覆管理模組 (`app/routers/reports.py`)
- [ ] `POST /reports/{question_id}`: 新增回覆 (檢查部門訪問權限)。
- [ ] `PUT /reports/{report_id}`: 編輯回覆 (檢查創作者權限)。

## 3. 待實作測試檔案
1. `tests/test_auth_api.py`: 認證 API 測試。
2. `tests/test_questions_api.py`: 問題管理 API 測試。
3. `tests/test_reports_api.py`: 回覆管理 API 測試。

## 4. 執行計畫
| 階段 | 描述 | 預計產出 |
| :--- | :--- | :--- |
| **第一階段** | 建立基礎測試設施與認證測試 | `tests/test_auth_api.py` |
| **第二階段** | 實作問題管理 API 測試 | `tests/test_questions_api.py` |
| **第三階段** | 實作回覆管理 API 測試 | `tests/test_reports_api.py` |
| **第四階段** | 執行整合測試並修正問題 | 測試報告 (All Green) |
