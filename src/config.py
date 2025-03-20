from src.model.database_manager import DatabaseManager
from src.model.base_models import Base
from typing import Optional

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
