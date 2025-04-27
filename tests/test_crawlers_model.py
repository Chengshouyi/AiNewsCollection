"""Tests for the Crawlers model functionality.

This module contains test cases for validating the Crawlers model behavior,
including creation, timestamps, relationships, and data serialization.
"""

# flake8: noqa: F811
# pylint: disable=redefined-outer-name

# Standard library imports
from datetime import datetime, timezone

# Third party imports
import pytest

# Local application imports
from src.models.crawlers_model import Crawlers
from src.utils.log_utils import LoggerSetup

logger = LoggerSetup.setup_logger(__name__)


@pytest.fixture(scope="function")
def initialized_db_manager(db_manager_for_test):
    """初始化測試資料庫管理器並創建表"""
    try:
        db_manager_for_test.create_tables(Crawlers)
        yield db_manager_for_test
    finally:
        pass


class TestCrawlersModel:
    """Crawlers 模型的測試類"""

    def test_crawlers_creation_with_required_fields(self, initialized_db_manager):
        """測試使用必填欄位創建 Crawlers"""
        with initialized_db_manager.session_scope() as session:
            crawler = Crawlers(
                crawler_name="test_crawler",
                module_name="test_module",
                base_url="https://example.com",
                crawler_type="web",
                config_file_name="test_config.json",
            )
            session.add(crawler)
            session.flush()

            assert crawler.crawler_name == "test_crawler"
            assert crawler.module_name == "test_module"
            assert crawler.base_url == "https://example.com"
            assert crawler.is_active is True
            assert crawler.crawler_type == "web"
            assert crawler.config_file_name == "test_config.json"
            assert isinstance(crawler.created_at, datetime)
            assert crawler.updated_at is not None
            assert crawler.updated_at.tzinfo == timezone.utc
            assert crawler.crawler_tasks == []

    def test_timestamps_behavior(self, initialized_db_manager):
        """測試時間戳行為"""
        with initialized_db_manager.session_scope() as session:
            crawler = Crawlers(
                crawler_name="test_crawler",
                module_name="test_module",
                base_url="https://example.com",
                crawler_type="web",
                config_file_name="test_config.json",
            )
            session.add(crawler)
            session.flush()

            assert crawler.created_at.tzinfo == timezone.utc
            assert crawler.updated_at is not None
            assert crawler.updated_at.tzinfo == timezone.utc

    def test_to_dict_method(self, initialized_db_manager):
        """測試 to_dict 方法"""
        with initialized_db_manager.session_scope() as session:
            crawler = Crawlers(
                id=1,
                crawler_name="test_crawler",
                module_name="test_module",
                base_url="https://example.com",
                crawler_type="web",
                config_file_name="test_config.json",
            )
            session.add(crawler)
            session.flush()

            dict_data = crawler.to_dict()

            assert dict_data["id"] == 1
            assert dict_data["crawler_name"] == "test_crawler"
            assert dict_data["module_name"] == "test_module"
            assert dict_data["base_url"] == "https://example.com"
            assert dict_data["crawler_type"] == "web"
            assert dict_data["is_active"] is True
            assert dict_data["config_file_name"] == "test_config.json"

    def test_repr_method(self, initialized_db_manager):
        """測試 __repr__ 方法"""
        with initialized_db_manager.session_scope() as session:
            crawler = Crawlers(
                id=1,
                crawler_name="test_crawler",
                module_name="test_module",
                base_url="https://example.com",
                crawler_type="web",
                config_file_name="test_config.json",
            )
            session.add(crawler)
            session.flush()

            expected_repr = "<Crawlers(id=1, crawler_name='test_crawler', module_name='test_module', base_url='https://example.com', crawler_type='web', config_file_name='test_config.json', is_active=True)>"

            assert repr(crawler) == expected_repr

    def test_relationship_behavior(self, initialized_db_manager):
        """測試關聯關係行為"""
        with initialized_db_manager.session_scope() as session:
            crawler = Crawlers(
                crawler_name="test_crawler",
                module_name="test_module",
                base_url="https://example.com",
                crawler_type="web",
                config_file_name="test_config.json",
            )
            session.add(crawler)
            session.flush()

            assert hasattr(crawler, "crawler_tasks")
            assert isinstance(crawler.crawler_tasks, list)
            assert len(crawler.crawler_tasks) == 0
