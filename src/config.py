from src.database.database_manager import DatabaseManager
from src.models.base_model import Base
from typing import Optional
import os
from datetime import timezone
import pytz
import time
from src.utils.log_utils import LoggerSetup # 使用統一的 logger
logger = LoggerSetup.setup_logger(__name__) # 使用統一的 logger

# 專案根目錄
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


SYS_TIMEZONE = 'UTC'
# 自動偵測系統時區，如果無法偵測則預設為台北時區
try:
    # 嘗試從系統設定獲取時區
    system_timezone_name = time.tzname[0]
    USER_TIMEZONE = pytz.timezone(system_timezone_name)
except Exception:
    # 如果偵測失敗，預設為台北時區
    USER_TIMEZONE = pytz.timezone(SYS_TIMEZONE)


# 配置檔案路徑
CONFIG_DIR = os.path.join(BASE_DIR, 'src', 'config')
BNEXT_CONFIG_PATH = os.path.join(CONFIG_DIR, 'bnext_crawler_config.json')

# 確保配置目錄存在
os.makedirs(CONFIG_DIR, exist_ok=True)


def get_system_process_timezone():
    return timezone.utc

def create_database_manager() -> DatabaseManager:
    """
    創建並初始化資料庫管理器(從環境變數讀取 URL)
    
    Returns:
        初始化的 DatabaseManager 實例
    """
    db_manager = DatabaseManager()
    # 這裡不應該執行 create_tables，讓 Alembic 或應用初始化處理
    # db_manager.create_tables(Base)
    return db_manager

# 提供單例模式
_db_manager = None

def get_db_manager() -> DatabaseManager:
    """
    獲取資料庫管理器的單例
    
    Args:
        db_path: 資料庫路徑，預設為 'data/news.db'
    
    Returns:
        DatabaseManager 單例實例
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = create_database_manager()
    return _db_manager
