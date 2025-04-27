import shutil
import os
import pytest
from src.database.database_manager import DatabaseManager  # 導入 DatabaseManager
from src.models.base_model import Base
from src.utils.log_utils import LoggerSetup

logger = LoggerSetup.setup_logger(__name__)


def pytest_configure(config):
    """Clear pytest cache at the start of every test session."""
    # Get the cache directory
    cache_dir = config.cache.makedir(".pytest_cache")

    # Clear the cache directory
    for item in os.listdir(cache_dir):
        path = os.path.join(cache_dir, item)
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

    print("Pytest cache cleared!")


@pytest.fixture(
    scope="function"
)  # 使用 function scope 確保每個測試函數都有獨立的資料庫
def db_manager_for_test(monkeypatch):
    """
    提供一個連接到記憶體 SQLite 資料庫的 DatabaseManager 實例供測試使用。
    """
    # 使用 monkeypatch 臨時設置環境變數
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    # 初始化 DatabaseManager
    db_manager = DatabaseManager()

    # 提供 db_manager 給測試函數
    yield db_manager

    # 測試結束後清理資源
    db_manager.cleanup()
