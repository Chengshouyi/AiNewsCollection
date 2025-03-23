from src.database.database_manager import DatabaseManager
from src.models.base_model import Base
from typing import Optional
import os

# 專案根目錄
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 配置檔案路徑
CONFIG_DIR = os.path.join(BASE_DIR, 'src', 'config')
BNEXT_CONFIG_PATH = os.path.join(CONFIG_DIR, 'bnext_crawler_config.json')

# 確保配置目錄存在
os.makedirs(CONFIG_DIR, exist_ok=True)

def create_database_manager(db_path: Optional[str] = None) -> DatabaseManager:
    """
    創建並初始化資料庫管理器
    
    Args:
        db_path: 資料庫路徑，預設為 'data/news.db'
    
    Returns:
        初始化的 DatabaseManager 實例
    """
    db_manager = DatabaseManager(db_path)
    db_manager.create_tables(Base)
    return db_manager

# 提供單例模式
_db_manager = None

def get_db_manager(db_path: Optional[str] = None) -> DatabaseManager:
    """
    獲取資料庫管理器的單例
    
    Args:
        db_path: 資料庫路徑，預設為 'data/news.db'
    
    Returns:
        DatabaseManager 單例實例
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = create_database_manager(db_path)
    return _db_manager
