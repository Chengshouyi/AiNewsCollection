import logging
import os
import importlib
import inspect

from src.web.routes.article_api import article_bp
from src.web.routes.tasks_api import tasks_bp
from src.web.routes.crawler_api import crawler_bp
from src.web.routes.views import view_bp

from flask import Blueprint

__all__ = ['article_bp', 'tasks_bp', 'crawler_bp', 'view_bp']

logger = logging.getLogger(__name__)

# 存放所有藍圖的列表
all_blueprints = []

def load_blueprints():
    """動態載入所有藍圖"""
    # 取得 routes 目錄的絕對路徑
    routes_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 獲取所有 Python 檔案 (排除 __init__.py 和 __pycache__)
    for filename in os.listdir(routes_dir):
        if filename.endswith('.py') and filename != '__init__.py':
            module_name = filename[:-3]  # 移除 .py 副檔名
            
            # 載入模組
            try:
                module_path = f"src.web.routes.{module_name}"
                module = importlib.import_module(module_path)
                
                # 查找模組中的所有 Blueprint 實例
                for name, obj in inspect.getmembers(module):
                    if isinstance(obj, Blueprint):
                        logger.info("找到藍圖: %s 在 %s", name, module_path)
                        all_blueprints.append(obj)
            except Exception as e:
                logger.error("載入模組 %s 時發生錯誤: %s", module_name, e)

# 在模組載入時執行
load_blueprints()