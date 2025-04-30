"""測試 src.database.database_manager 模組的功能。"""

import os
import logging
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
from pytest import fixture
from sqlalchemy import text, create_engine

# 導入可能在 dispose 後引發的異常
from sqlalchemy.exc import OperationalError, InvalidRequestError, StatementError

from src.database.database_manager import (
    DatabaseManager,
    DatabaseConfigError,
    DatabaseConnectionError,
    DatabaseOperationError,
)
from src.models.articles_model import Articles
from src.models.base_model import Base
from src.models.crawlers_model import Crawlers


# flake8: noqa: F811
# pylint: disable=redefined-outer-name

# 設定 logger
logger = logging.getLogger(__name__)  # 使用統一的 logger


@fixture
def set_memory_db_url(monkeypatch):
    """設定記憶體資料庫的環境變數"""
    db_url = "sqlite:///:memory:"
    monkeypatch.setenv("DATABASE_URL", db_url)
    logger.debug("Set DATABASE_URL for memory DB: %s", db_url)
    return db_url


@fixture
def set_temp_file_db_url(monkeypatch, tmp_path):
    """設定臨時文件資料庫的環境變數"""
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path.resolve()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    logger.debug("Set DATABASE_URL for file DB: %s", db_url)
    return db_url, str(db_path)


@fixture
def db_manager_memory(set_memory_db_url):
    """創建使用記憶體資料庫的 DatabaseManager 實例"""
    logger.debug("Creating DatabaseManager instance (memory)...")
    manager = DatabaseManager()
    manager.create_tables(Base)
    yield manager
    logger.debug("Cleaning up DatabaseManager instance (memory)...")
    manager.cleanup()


@fixture
def db_manager_file(set_temp_file_db_url):
    """創建使用文件資料庫的 DatabaseManager 實例"""
    db_url, db_path = set_temp_file_db_url
    logger.debug("Creating DatabaseManager instance (file: %s)...", db_path)
    manager = DatabaseManager()
    manager.create_tables(Base)
    yield manager, db_path
    logger.debug("Cleaning up DatabaseManager instance (file: %s)...", db_path)
    manager.cleanup()


@fixture
def sample_article():
    """創建一個測試用的文章樣本"""
    return {
        "title": "測試文章",
        "link": "https://example.com/test",
        "published_at": datetime.now(timezone.utc),
        "content": "測試內容",
        "created_at": datetime.now(timezone.utc),
        "source": "test_source",
        "source_url": "https://example.com/source",
    }


class TestDatabaseManager:
    """資料庫管理器測試類"""

    def test_initialization_missing_env_var(self, monkeypatch):
        """測試缺少 DATABASE_URL 環境變數時的初始化"""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(
            DatabaseConfigError, match="DATABASE_URL environment variable is not set"
        ):
            DatabaseManager()

    def test_initialization_success(self, db_manager_memory):
        """測試成功初始化"""
        assert db_manager_memory.engine is not None
        assert hasattr(db_manager_memory, "_session_factory")
        assert hasattr(db_manager_memory, "_scoped_session")
        assert db_manager_memory.database_url == "sqlite:///:memory:"

    def test_initialization_with_file_db(self, db_manager_file):
        """測試使用文件資料庫成功初始化"""
        manager, db_path = db_manager_file
        assert os.path.exists(db_path)
        assert manager.engine is not None
        assert manager.database_url.endswith(f"/{os.path.basename(db_path)}")

    def test_check_database_health_success(self, db_manager_memory):
        """測試資料庫健康檢查成功"""
        assert db_manager_memory.check_database_health() is True

    @patch("src.database.database_manager.DatabaseManager._verify_connection")
    def test_check_database_health_failure(self, mock_verify, set_memory_db_url):
        """測試資料庫健康檢查失敗"""
        mock_verify.return_value = None
        manager = DatabaseManager()
        mock_verify.side_effect = DatabaseConnectionError("模擬連接失敗")
        assert manager.check_database_health() is False
        assert mock_verify.call_count == 2
        manager.cleanup()

    def test_session_scope_commit(self, db_manager_memory, sample_article):
        """測試 session_scope 正常提交事務"""
        with db_manager_memory.session_scope() as session:
            article = Articles(**sample_article)
            session.add(article)

        with db_manager_memory.session_scope() as session:
            result = (
                session.query(Articles)
                .filter(Articles.link == sample_article["link"])
                .first()
            )
            assert result is not None
            assert result.title == sample_article["title"]
            assert result.source == sample_article["source"]

    def test_session_scope_rollback(self, db_manager_memory, sample_article):
        """測試 session_scope 異常回滾"""
        with db_manager_memory.session_scope() as session:
            initial_article = Articles(**sample_article)
            session.add(initial_article)

        second_article_data = sample_article.copy()
        second_article_data["link"] = "https://example.com/test2"

        with pytest.raises(ValueError, match="模擬異常，應觸發回滾"):
            with db_manager_memory.session_scope() as session:
                article = Articles(**second_article_data)
                session.add(article)
                raise ValueError("模擬異常，應觸發回滾")

        with db_manager_memory.session_scope() as session:
            result = (
                session.query(Articles)
                .filter(Articles.link == second_article_data["link"])
                .first()
            )
            assert result is None
            result = (
                session.query(Articles)
                .filter(Articles.link == sample_article["link"])
                .first()
            )
            assert result is not None

    def test_session_scope_cleanup(self, db_manager_memory, sample_article):
        """測試 session_scope 的清理功能（能開啟新事務）"""
        with db_manager_memory.session_scope() as session:
            article = Articles(**sample_article)
            session.add(article)

        second_article = sample_article.copy()
        second_article["link"] = "https://example.com/test2"
        with db_manager_memory.session_scope() as another_session:
            article2 = Articles(**second_article)
            another_session.add(article2)

        with db_manager_memory.session_scope() as final_session:
            count = final_session.query(Articles).count()
            assert count == 2

    def test_create_tables(self, db_manager_memory):
        """測試創建資料表（在 fixture 中已創建）"""
        with db_manager_memory.session_scope() as session:
            tables = session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table';")
            ).fetchall()
            table_names = [table[0] for table in tables]
            assert Articles.__tablename__ in table_names
            assert Crawlers.__tablename__ in table_names

    def test_env_path_handling(self, monkeypatch, tmp_path):
        """測試環境變數設置的文件資料庫路徑"""
        db_path = tmp_path / "env_test.db"
        db_url = f"sqlite:///{db_path.resolve()}"
        monkeypatch.setenv("DATABASE_URL", db_url)

        db_manager = DatabaseManager()
        assert os.path.exists(str(db_path))

        db_manager.create_tables(Base)
        with db_manager.session_scope() as session:
            tables = session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table';")
            ).fetchall()
            table_names = [table[0] for table in tables]
            assert Articles.__tablename__ in table_names
        db_manager.cleanup()

    def test_invalid_path_init(self, monkeypatch):
        """測試使用無效路徑進行初始化時的錯誤"""
        invalid_path = os.path.join(
            "/", "nonexistent", "path", "that", "cannot", "be", "created", "test.db"
        )
        invalid_url = f"sqlite:///{invalid_path}"
        monkeypatch.setenv("DATABASE_URL", invalid_url)

        with pytest.raises(
            (DatabaseConfigError, DatabaseConnectionError, OperationalError)
        ):
            DatabaseManager()

    # 修正：使用 patch.object 來驗證實例方法的呼叫
    def test_cleanup(self, set_memory_db_url):
        """測試 cleanup 方法是否呼叫了 dispose 和 remove"""
        manager = DatabaseManager()
        # 確保實例有 engine 和 _scoped_session 屬性
        assert hasattr(manager, "engine")
        assert hasattr(manager, "_scoped_session")

        # 使用 patch.object 作為 context manager
        with patch.object(
            manager.engine, "dispose", return_value=None
        ) as mock_dispose, patch.object(
            manager._scoped_session, "remove", return_value=None
        ) as mock_remove:

            # 在 patch 的上下文中執行清理
            manager.cleanup()

            # 驗證 mock 方法是否被呼叫
            mock_dispose.assert_called_once()
            mock_remove.assert_called_once()
