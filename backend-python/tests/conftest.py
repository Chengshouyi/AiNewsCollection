import shutil
import os
import pytest
import logging
from src.database.database_manager import DatabaseManager  # 導入 DatabaseManager
from src.models.base_model import Base


logger = logging.getLogger(__name__)  # 使用統一的 logger


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
    # 使用 URI filename 和 cache=shared 確保多線程共享同一個記憶體資料庫
    monkeypatch.setenv("DATABASE_URL", "sqlite:///file::memory:?cache=shared&uri=true")

    # 初始化 DatabaseManager
    db_manager = DatabaseManager()

    # 提供 db_manager 給測試函數
    yield db_manager

    # 測試結束後清理資源
    try:
        # 在 dispose 之前刪除所有表，確保下次 function scope 測試是乾淨的
        logger.debug("Dropping all tables after test function...")
        base = Base  # 確保 Base 已導入
        db_manager.drop_tables(base)
        logger.debug("All tables dropped.")
    except Exception as e:
        logger.error(f"Error dropping tables during cleanup: {e}", exc_info=True)
    finally:
        # 最終執行原始的 cleanup (dispose engine)
        db_manager.cleanup()
