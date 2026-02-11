from fastapi.templating import Jinja2Templates
from app.dependencies import has_permission

# 創建模板引擎實例
templates = Jinja2Templates(directory="templates")

# 添加全局函數
templates.env.globals["has_permission"] = has_permission 