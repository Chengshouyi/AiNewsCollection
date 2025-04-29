"""測試 CrawlersService 的功能。

此模組包含對 CrawlersService 類的所有測試案例，包括：
- CRUD 操作 (建立、讀取、更新、刪除)
- 批量操作
- 搜尋和過濾功能
- 狀態切換
- 統計功能
- 配置檔案處理
- 錯誤處理
"""

# Standard library imports
from datetime import datetime, timezone, timedelta
import json
import os
from typing import List, Dict, Any

# Third party imports
import pytest
from sqlalchemy.orm import (
    sessionmaker,
)  # Keep for potential direct session use if needed outside service
from unittest.mock import MagicMock, patch # 確保 MagicMock 被導入

# Local application imports
from src.models.crawlers_model import Crawlers
from src.models.base_model import Base
from src.services.crawlers_service import CrawlersService
from src.error.errors import ValidationError, DatabaseOperationError
from src.database.database_manager import DatabaseManager
from src.models.crawlers_schema import CrawlerReadSchema, PaginatedCrawlerResponse
from src.utils.log_utils import LoggerSetup


# flake8: noqa: F811
# pylint: disable=redefined-outer-name

logger = LoggerSetup.setup_logger(__name__)  # 使用統一的 logger

# 固定測試時間
MOCK_TIME = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="function")
def initialized_db_manager(db_manager_for_test):
    """Fixture that depends on db_manager_for_test, creates tables, and yields the manager."""
    logger.debug("Creating tables for crawlers test function...")
    try:
        db_manager_for_test.create_tables(Base)  # Use Base from your models
        yield db_manager_for_test
    finally:
        logger.debug(
            "Crawlers test function finished, tables might be dropped by manager cleanup or next test setup."
        )
        # Ensure cleanup happens if needed, though db_manager_for_test likely handles it


@pytest.fixture(scope="function")
def crawlers_service(initialized_db_manager: DatabaseManager):
    """創建爬蟲服務實例，使用 initialized_db_manager"""
    service = CrawlersService(initialized_db_manager)
    yield service  # 使用 yield 確保模擬在測試期間有效


@pytest.fixture(scope="function")
def sample_crawlers(initialized_db_manager: DatabaseManager) -> List[Dict[str, Any]]:
    """創建樣本爬蟲資料並返回字典列表，包含 ID 和屬性值"""
    created_crawlers_data = []
    crawlers_input_data = [
        {
            "crawler_name": "數位時代爬蟲",
            "module_name": "test_module",
            "base_url": "https://www.bnext.com.tw/articles",
            "is_active": True,
            "crawler_type": "bnext",
            "config_file_name": "bnext_crawler_config.json",
            "created_at": MOCK_TIME - timedelta(seconds=30),
            "updated_at": MOCK_TIME,
        },
        {
            "crawler_name": "科技報導爬蟲",
            "module_name": "test_module",
            "base_url": "https://technews.tw",
            "is_active": False,
            "crawler_type": "technews",
            "config_file_name": "technews_crawler_config.json",
            "created_at": MOCK_TIME - timedelta(seconds=10),
            "updated_at": MOCK_TIME,
        },
        {
            "crawler_name": "商業週刊爬蟲",
            "module_name": "test_module",
            "base_url": "https://www.businessweekly.com.tw",
            "is_active": True,
            "crawler_type": "business",
            "config_file_name": "business_crawler_config.json",
            "created_at": MOCK_TIME - timedelta(seconds=20),
            "updated_at": MOCK_TIME,
        },
        {
            "crawler_name": "範例爬蟲",
            "module_name": "test_module",
            "base_url": "https://example.com",
            "is_active": True,
            "crawler_type": "example",
            "config_file_name": "example_config.json",
            "created_at": MOCK_TIME,
            "updated_at": MOCK_TIME,
        },
    ]

    with initialized_db_manager.session_scope() as session:
        # 清除可能存在的資料，確保測試隔離
        session.query(Crawlers).delete()
        session.commit()

        for crawler_data in crawlers_input_data:
            crawler = Crawlers(**crawler_data)
            session.add(crawler)
            session.flush()  # 在 commit 前取得 ID
            crawler_id = crawler.id
            session.commit()  # 提交以保存更改

            # 手動建立字典，包含 ID 和其他需要的欄位
            crawler_dict = {
                "id": crawler_id,
                "crawler_name": crawler.crawler_name,
                "module_name": crawler.module_name,
                "base_url": crawler.base_url,
                "is_active": crawler.is_active,
                "crawler_type": crawler.crawler_type,
                "config_file_name": crawler.config_file_name,
                "created_at": crawler.created_at,
                "updated_at": crawler.updated_at,
            }
            created_crawlers_data.append(crawler_dict)
        session.commit()  # Commit all changes at once
        logger.debug(
            f"Created {len(created_crawlers_data)} sample crawlers with data: {created_crawlers_data}"
        )  # Log created data

    return created_crawlers_data


@pytest.fixture(scope="function")
def valid_crawler_data():
    """提供有效的爬蟲資料用於測試"""
    return {
        "crawler_name": "測試爬蟲",
        "module_name": "test_module",
        "base_url": "https://example.com/test",
        "is_active": True,
        "crawler_type": "bnext",
        "config_file_name": "bnext_crawler_config.json",
    }


@pytest.fixture
def valid_config_file():
    """提供有效的配置檔案內容"""
    return {
        "name": "test_crawler",
        "base_url": "https://example.com",
        "list_url_template": "{base_url}/categories/{category}",
        "categories": {"test_category_key": "Test Category Display Name"},
        "full_categories": ["test"],
        "selectors": {
            "get_article_links": {
                "articles_container": "div.articles",
                "category": "span.category",
                "link": "a.link",
                "title": "h2.title",
                "summary": "div.summary",
            },
            "get_article_contents": {
                "content_container": "div.content",
                "published_date": "span.date",
                "category": "span.category",
                "title": "h1.title",
                "summary": "div.summary",
                "content": "div.article-content",
            },
        },
    }


class TestCrawlersService:
    """爬蟲服務的測試類"""

    def test_init(self, initialized_db_manager: DatabaseManager):
        """測試服務初始化"""
        service = CrawlersService(initialized_db_manager)
        assert service.db_manager == initialized_db_manager

    def test_create_crawler(
        self,
        crawlers_service: CrawlersService,
        valid_crawler_data: Dict[str, Any],
        initialized_db_manager: DatabaseManager,
    ):
        """測試創建爬蟲設定"""
        # 清除可能存在的同名爬蟲設定
        with initialized_db_manager.session_scope() as session:
            session.query(Crawlers).filter_by(
                crawler_name=valid_crawler_data["crawler_name"]
            ).delete()
            session.commit()

        result = crawlers_service.create_crawler(valid_crawler_data)
        assert result["success"] is True
        assert result["message"] == "爬蟲設定創建成功"
        assert result["crawler"] is not None

        # 驗證創建的爬蟲資料 (使用 Schema)
        created_crawler = result["crawler"]
        assert isinstance(created_crawler, CrawlerReadSchema)
        assert created_crawler.crawler_name == valid_crawler_data["crawler_name"]
        assert created_crawler.base_url == valid_crawler_data["base_url"]
        assert created_crawler.is_active == valid_crawler_data["is_active"]
        assert created_crawler.crawler_type == valid_crawler_data["crawler_type"]
        assert (
            created_crawler.config_file_name == valid_crawler_data["config_file_name"]
        )
        assert isinstance(created_crawler.updated_at, datetime)

    def test_find_all_crawlers(
        self, crawlers_service: CrawlersService, sample_crawlers: List[Dict[str, Any]]
    ):
        """測試獲取所有爬蟲設定，包括分頁、排序和預覽"""
        # 基本測試
        result = crawlers_service.find_all_crawlers()
        assert result["success"] is True
        assert len(result["crawlers"]) == len(sample_crawlers)
        assert all(isinstance(c, CrawlerReadSchema) for c in result["crawlers"])

        # 測試分頁
        result_limit = crawlers_service.find_all_crawlers(limit=2)
        assert result_limit["success"] is True
        assert len(result_limit["crawlers"]) == 2

        result_offset = crawlers_service.find_all_crawlers(offset=1, limit=1)
        assert result_offset["success"] is True
        assert len(result_offset["crawlers"]) == 1

        # 測試排序
        result_sort = crawlers_service.find_all_crawlers(
            sort_by="crawler_name", sort_desc=True
        )
        assert result_sort["success"] is True
        names = [crawler.crawler_name for crawler in result_sort["crawlers"]]
        expected_names = sorted(
            [c["crawler_name"] for c in sample_crawlers], reverse=True
        )
        assert names == expected_names

        # --- 測試預覽模式 ---
        preview_fields = ["id", "crawler_name", "is_active"]
        result_preview = crawlers_service.find_all_crawlers(
            is_preview=True, preview_fields=preview_fields
        )
        assert result_preview["success"] is True
        assert len(result_preview["crawlers"]) == len(sample_crawlers)
        # 驗證返回的是字典列表，且只包含指定欄位
        for item in result_preview["crawlers"]:
            assert isinstance(item, dict)
            assert set(item.keys()) == set(preview_fields)
            # 驗證字典中的值是否正確 (與 sample_crawlers 對比)
            original = next((c for c in sample_crawlers if c["id"] == item["id"]), None)
            assert original is not None
            assert item["crawler_name"] == original["crawler_name"]
            assert item["is_active"] == original["is_active"]

        # 測試預覽模式 + 分頁 + 排序
        result_preview_paged = crawlers_service.find_all_crawlers(
            is_preview=True,
            preview_fields=preview_fields,
            limit=1,
            offset=1,
            sort_by="crawler_name",
            sort_desc=False,
        )
        assert result_preview_paged["success"] is True
        assert len(result_preview_paged["crawlers"]) == 1
        assert isinstance(result_preview_paged["crawlers"][0], dict)
        assert set(result_preview_paged["crawlers"][0].keys()) == set(preview_fields)
        # 驗證是排序後的第二個元素
        expected_sorted_names = sorted([c["crawler_name"] for c in sample_crawlers])
        assert (
            result_preview_paged["crawlers"][0]["crawler_name"]
            == expected_sorted_names[1]
        )

    def test_get_crawler_by_id(
        self, crawlers_service: CrawlersService, sample_crawlers: List[Dict[str, Any]]
    ):
        """測試根據ID獲取爬蟲設定"""
        crawler_id = sample_crawlers[0]["id"]
        result = crawlers_service.get_crawler_by_id(crawler_id)

        assert result["success"] is True
        assert result["crawler"] is not None
        assert isinstance(result["crawler"], CrawlerReadSchema)  # 檢查類型
        assert result["crawler"].id == crawler_id
        assert (
            result["crawler"].crawler_name == sample_crawlers[0]["crawler_name"]
        )  # 驗證其他欄位

        # 測試無效ID
        result_invalid = crawlers_service.get_crawler_by_id(999999)
        assert result_invalid["success"] is False
        assert "不存在" in result_invalid["message"]
        assert result_invalid["crawler"] is None  # 確保無效時返回 None

    def test_get_active_crawlers(
        self, crawlers_service: CrawlersService, sample_crawlers: List[Dict[str, Any]]
    ):
        """測試獲取活動中的爬蟲設定，包括分頁和預覽"""
        expected_active_count = sum(1 for c in sample_crawlers if c["is_active"])
        # 基本測試
        result = crawlers_service.find_active_crawlers()
        assert result["success"] is True
        assert len(result["crawlers"]) == expected_active_count  # 預期有 2 個活動的
        assert all(isinstance(c, CrawlerReadSchema) for c in result["crawlers"])
        assert all(crawler.is_active for crawler in result["crawlers"])

        # --- 測試分頁 ---
        result_limit = crawlers_service.find_active_crawlers(limit=1)
        assert result_limit["success"] is True
        assert len(result_limit["crawlers"]) == 1

        result_offset = crawlers_service.find_active_crawlers(offset=1, limit=1)
        assert result_offset["success"] is True
        assert len(result_offset["crawlers"]) == 1  # 應該是第二個活躍的
        assert result_offset["crawlers"][0].is_active is True

        # --- 測試預覽模式 ---
        preview_fields = ["id", "base_url"]
        result_preview = crawlers_service.find_active_crawlers(
            is_preview=True, preview_fields=preview_fields
        )
        assert result_preview["success"] is True
        assert len(result_preview["crawlers"]) == expected_active_count
        for item in result_preview["crawlers"]:
            assert isinstance(item, dict)
            assert set(item.keys()) == set(preview_fields)
            # 驗證 base_url 存在且與 sample_crawlers 一致
            original = next((c for c in sample_crawlers if c["id"] == item["id"]), None)
            assert original is not None
            assert item["base_url"] == original["base_url"]

    def test_find_crawlers_by_name(
        self,
        crawlers_service: CrawlersService,
        sample_crawlers: List[Dict[str, Any]],
        initialized_db_manager: DatabaseManager,
    ):
        """測試根據名稱模糊查詢爬蟲設定，包括分頁、狀態過濾和預覽"""
        expected_all_count = len(sample_crawlers)
        expected_active_count = sum(1 for c in sample_crawlers if c["is_active"])
        expected_inactive_count = expected_all_count - expected_active_count

        # --- 測試 is_active=None (預設，查找所有) ---
        result_all = crawlers_service.find_crawlers_by_name("爬蟲")
        assert result_all["success"] is True
        assert len(result_all["crawlers"]) == expected_all_count
        assert all(isinstance(c, CrawlerReadSchema) for c in result_all["crawlers"])

        # --- 測試 is_active=True (僅查找活動的) ---
        result_active = crawlers_service.find_crawlers_by_name("爬蟲", is_active=True)
        assert result_active["success"] is True
        assert len(result_active["crawlers"]) == expected_active_count
        assert all(crawler.is_active for crawler in result_active["crawlers"])

        # --- 測試 is_active=False (僅查找非活動的) ---
        result_inactive = crawlers_service.find_crawlers_by_name(
            "爬蟲", is_active=False
        )
        assert result_inactive["success"] is True
        assert len(result_inactive["crawlers"]) == expected_inactive_count
        assert not result_inactive["crawlers"][0].is_active

        # --- 測試分頁 ---
        result_limit = crawlers_service.find_crawlers_by_name("爬蟲", limit=2)
        assert result_limit["success"] is True
        assert len(result_limit["crawlers"]) == 2

        result_offset = crawlers_service.find_crawlers_by_name(
            "爬蟲", offset=2, limit=1
        )
        assert result_offset["success"] is True
        assert len(result_offset["crawlers"]) == 1

        # --- 測試預覽模式 ---
        preview_fields = ["crawler_name", "crawler_type"]
        result_preview = crawlers_service.find_crawlers_by_name(
            "爬蟲", is_preview=True, preview_fields=preview_fields
        )
        assert result_preview["success"] is True
        assert len(result_preview["crawlers"]) == expected_all_count
        for item in result_preview["crawlers"]:
            assert isinstance(item, dict)
            assert set(item.keys()) == set(preview_fields)
            assert "爬蟲" in item["crawler_name"]  # 驗證內容

        # --- 測試不存在的名稱 ---
        no_crawlers_result = crawlers_service.find_crawlers_by_name("不存在")
        assert no_crawlers_result["success"] is True
        assert "找不到任何符合條件的爬蟲設定" in no_crawlers_result["message"]
        assert len(no_crawlers_result["crawlers"]) == 0

    def test_update_crawler(
        self, crawlers_service: CrawlersService, sample_crawlers: List[Dict[str, Any]]
    ):
        """測試更新爬蟲設定"""
        crawler_id = sample_crawlers[0]["id"]
        original_created_at = sample_crawlers[0]["created_at"]  # 從字典獲取

        update_data = {
            "crawler_name": "更新後的爬蟲名稱",
            "base_url": "https://example.com/updated",
            "is_active": False,
            "config_file_name": "bnext_crawler_config_updated.json",
            "crawler_type": "bnext",  # 確保傳遞了必要的欄位
        }

        result = crawlers_service.update_crawler(crawler_id, update_data)
        assert result["success"] is True
        assert result["crawler"] is not None
        assert isinstance(result["crawler"], CrawlerReadSchema)  # 檢查類型
        assert result["crawler"].id == crawler_id
        assert result["crawler"].crawler_name == "更新後的爬蟲名稱"
        assert result["crawler"].base_url == "https://example.com/updated"
        assert result["crawler"].is_active is False
        assert result["crawler"].config_file_name == "bnext_crawler_config_updated.json"
        assert isinstance(result["crawler"].updated_at, datetime)  # 驗證是時間類型
        assert (
            result["crawler"].updated_at > original_created_at
        )  # 驗證更新時間晚於創建時間
        assert result["crawler"].created_at == original_created_at  # 創建時間應保持不變

        # 測試不存在的ID
        result_invalid = crawlers_service.update_crawler(999999, update_data)
        assert result_invalid["success"] is False
        assert "不存在" in result_invalid["message"]
        assert result_invalid["crawler"] is None

    def test_delete_crawler(
        self, crawlers_service: CrawlersService, sample_crawlers: List[Dict[str, Any]]
    ):
        """測試刪除爬蟲設定"""
        crawler_id = sample_crawlers[0]["id"]

        result = crawlers_service.delete_crawler(crawler_id)
        assert result["success"] is True
        assert "刪除成功" in result["message"]

        # 確認爬蟲已被刪除
        get_result = crawlers_service.get_crawler_by_id(crawler_id)
        assert get_result["success"] is False
        assert "不存在" in get_result["message"]

        # 測試刪除不存在的爬蟲
        result_invalid = crawlers_service.delete_crawler(999999)
        assert result_invalid["success"] is False
        assert "不存在" in result_invalid["message"]  # 驗證錯誤消息

    def test_toggle_crawler_status(
        self, crawlers_service: CrawlersService, sample_crawlers: List[Dict[str, Any]]
    ):
        """測試切換爬蟲活躍狀態"""
        # 找到一個初始為 inactive 的爬蟲字典
        inactive_crawler = next(
            (c for c in sample_crawlers if not c["is_active"]), None
        )
        assert inactive_crawler is not None, "找不到 inactive 的樣本爬蟲"
        crawler_id = inactive_crawler["id"]
        original_is_active = inactive_crawler["is_active"]
        assert original_is_active is False  # 確保選取的樣本是 inactive

        # 第一次切換 (Inactive -> Active)
        result = crawlers_service.toggle_crawler_status(crawler_id)
        assert result["success"] is True
        assert result["crawler"] is not None
        assert isinstance(result["crawler"], CrawlerReadSchema)  # 檢查類型
        assert result["crawler"].id == crawler_id
        assert result["crawler"].is_active is True  # 狀態應變為 Active

        # 第二次切換 (Active -> Inactive)
        result_toggle_back = crawlers_service.toggle_crawler_status(crawler_id)
        assert result_toggle_back["success"] is True
        assert result_toggle_back["crawler"] is not None
        assert isinstance(result_toggle_back["crawler"], CrawlerReadSchema)  # 檢查類型
        assert result_toggle_back["crawler"].id == crawler_id
        assert result_toggle_back["crawler"].is_active is False  # 狀態應恢復為 Inactive

        # 測試不存在的爬蟲
        result_invalid = crawlers_service.toggle_crawler_status(999999)
        assert result_invalid["success"] is False
        assert "不存在" in result_invalid["message"]
        assert result_invalid["crawler"] is None

    def test_find_crawlers_by_type(
        self, crawlers_service: CrawlersService, sample_crawlers: List[Dict[str, Any]]
    ):
        """測試根據爬蟲類型查找爬蟲，包括分頁和預覽"""
        target_type = "bnext"
        expected_count = sum(
            1 for c in sample_crawlers if c["crawler_type"] == target_type
        )

        # --- 基本測試 ---
        result = crawlers_service.find_crawlers_by_type(target_type)
        assert result["success"] is True
        assert len(result["crawlers"]) == expected_count
        assert isinstance(result["crawlers"][0], CrawlerReadSchema)
        assert all(
            crawler.crawler_type == target_type for crawler in result["crawlers"]
        )

        # --- 測試分頁 (即使只有一個結果，也測試參數傳遞) ---
        result_limit = crawlers_service.find_crawlers_by_type(target_type, limit=1)
        assert result_limit["success"] is True
        assert len(result_limit["crawlers"]) == 1

        result_offset = crawlers_service.find_crawlers_by_type(
            target_type, offset=1, limit=1
        )
        assert result_offset["success"] is True
        assert len(result_offset["crawlers"]) == 0  # 因為偏移量為 1

        # --- 測試預覽模式 ---
        preview_fields = ["id", "config_file_name"]
        result_preview = crawlers_service.find_crawlers_by_type(
            target_type, is_preview=True, preview_fields=preview_fields
        )
        assert result_preview["success"] is True
        assert len(result_preview["crawlers"]) == expected_count
        assert isinstance(result_preview["crawlers"][0], dict)
        assert set(result_preview["crawlers"][0].keys()) == set(preview_fields)
        assert target_type in result_preview["crawlers"][0]["config_file_name"]

        # --- 測試不存在的類型 ---
        no_result = crawlers_service.find_crawlers_by_type("不存在類型")
        assert no_result["success"] is True
        assert f"找不到類型為 不存在類型 的爬蟲設定" in no_result["message"]
        assert len(no_result["crawlers"]) == 0

    def test_find_crawlers_by_target(
        self, crawlers_service: CrawlersService, sample_crawlers: List[Dict[str, Any]]
    ):
        """測試根據爬取目標(base_url)模糊查詢爬蟲，包括分頁和預覽"""
        target_keyword = "bnext"
        expected_count_bnext = sum(
            1 for c in sample_crawlers if target_keyword in c["base_url"]
        )
        target_keyword_com = ".com"
        expected_count_com = sum(
            1 for c in sample_crawlers if target_keyword_com in c["base_url"]
        )

        # --- 基本測試 ---
        result = crawlers_service.find_crawlers_by_target(target_keyword)
        assert result["success"] is True
        assert len(result["crawlers"]) == expected_count_bnext
        assert isinstance(result["crawlers"][0], CrawlerReadSchema)
        assert target_keyword in result["crawlers"][0].base_url

        # --- 測試分頁 ---
        result_limit = crawlers_service.find_crawlers_by_target(
            target_keyword_com, limit=2
        )  # 查找包含 .com 的
        assert result_limit["success"] is True
        assert len(result_limit["crawlers"]) == 2

        result_offset = crawlers_service.find_crawlers_by_target(
            target_keyword_com, offset=2, limit=1
        )
        assert result_offset["success"] is True
        assert len(result_offset["crawlers"]) == 1  # 總共3個.com, offset 2 應該取第3個

        # --- 測試預覽模式 ---
        preview_fields = ["id", "base_url"]
        result_preview = crawlers_service.find_crawlers_by_target(
            target_keyword, is_preview=True, preview_fields=preview_fields
        )
        assert result_preview["success"] is True
        assert len(result_preview["crawlers"]) == expected_count_bnext
        assert isinstance(result_preview["crawlers"][0], dict)
        assert set(result_preview["crawlers"][0].keys()) == set(preview_fields)
        assert target_keyword in result_preview["crawlers"][0]["base_url"]

        # --- 測試不存在的目標 ---
        no_result = crawlers_service.find_crawlers_by_target("不存在網址")
        assert no_result["success"] is True
        assert f"找不到目標包含 不存在網址 的爬蟲設定" in no_result["message"]
        assert len(no_result["crawlers"]) == 0

    def test_get_crawler_statistics(
        self, crawlers_service: CrawlersService, sample_crawlers: List[Dict[str, Any]]
    ):
        """測試獲取爬蟲統計信息"""
        expected_total = len(sample_crawlers)
        expected_active = sum(1 for c in sample_crawlers if c["is_active"])
        expected_inactive = expected_total - expected_active
        expected_types = {}
        for c in sample_crawlers:
            expected_types[c["crawler_type"]] = (
                expected_types.get(c["crawler_type"], 0) + 1
            )

        result = crawlers_service.get_crawler_statistics()
        assert result["success"] is True
        assert "statistics" in result

        stats = result["statistics"]
        assert stats["total"] == expected_total
        assert stats["active"] == expected_active
        assert stats["inactive"] == expected_inactive
        assert "by_type" in stats
        assert isinstance(stats["by_type"], dict)
        assert stats["by_type"] == expected_types

    def test_get_crawler_by_exact_name(
        self, crawlers_service: CrawlersService, sample_crawlers: List[Dict[str, Any]]
    ):
        """測試根據爬蟲名稱精確查詢"""
        exact_name = sample_crawlers[0]["crawler_name"]
        result = crawlers_service.get_crawler_by_exact_name(exact_name)
        assert result["success"] is True
        assert result["crawler"] is not None
        assert isinstance(result["crawler"], CrawlerReadSchema)  # 檢查類型
        assert result["crawler"].crawler_name == exact_name
        assert result["crawler"].id == sample_crawlers[0]["id"]

        # 測試不存在的名稱
        no_result = crawlers_service.get_crawler_by_exact_name("不存在的名稱")
        assert no_result["success"] is False  # 服務層精確查找失敗時返回 False
        assert "找不到名稱為" in no_result["message"]
        assert no_result["crawler"] is None

    def test_create_or_update_crawler(
        self, crawlers_service: CrawlersService, sample_crawlers: List[Dict[str, Any]]
    ):
        """測試創建或更新爬蟲設定"""
        # 測試更新現有爬蟲
        existing_id = sample_crawlers[0]["id"]
        original_created_at = sample_crawlers[0]["created_at"]  # 從字典獲取
        unique_name = f"更新測試爬蟲_{datetime.now().timestamp()}"

        update_data = {
            "id": existing_id,
            "crawler_name": unique_name,
            "module_name": "test_module",
            "base_url": "https://example.com/updated",
            "is_active": False,
            "config_file_name": "test_config_updated.json",
            "crawler_type": sample_crawlers[0]["crawler_type"],  # 保持原有 type
        }

        result_update = crawlers_service.create_or_update_crawler(update_data)
        assert result_update["success"] is True
        assert result_update["crawler"] is not None
        assert isinstance(result_update["crawler"], CrawlerReadSchema)  # 檢查類型
        assert result_update["crawler"].id == existing_id
        assert result_update["crawler"].crawler_name == unique_name
        assert result_update["crawler"].is_active is False
        assert isinstance(
            result_update["crawler"].updated_at, datetime
        )  # 檢查更新時間是 datetime
        assert (
            result_update["crawler"].updated_at > original_created_at
        )  # 檢查更新時間晚於創建時間
        assert (
            result_update["crawler"].created_at == original_created_at
        )  # 創建時間應不變
        assert "更新成功" in result_update["message"]

        # 測試創建新爬蟲
        new_unique_name = f"新建測試爬蟲_{datetime.now().timestamp()}"
        new_data = {
            "crawler_name": new_unique_name,
            "module_name": "test_module",
            "base_url": "https://example.com/new",
            "is_active": True,
            "crawler_type": "test_new",
            "config_file_name": "test_config_new.json",
        }

        result_create = crawlers_service.create_or_update_crawler(new_data)
        assert result_create["success"] is True
        assert result_create["crawler"] is not None
        assert isinstance(result_create["crawler"], CrawlerReadSchema)  # 檢查類型
        assert result_create["crawler"].crawler_name == new_unique_name
        assert result_create["crawler"].crawler_type == "test_new"
        assert isinstance(result_create["crawler"].created_at, datetime)
        assert isinstance(result_create["crawler"].updated_at, datetime)
        assert "創建成功" in result_create["message"]

    def test_batch_toggle_crawler_status(
        self, crawlers_service: CrawlersService, sample_crawlers: List[Dict[str, Any]]
    ):
        """測試批量設置爬蟲的活躍狀態"""
        crawler_ids = [crawler["id"] for crawler in sample_crawlers]

        # 批量停用所有爬蟲
        result_deactivate = crawlers_service.batch_toggle_crawler_status(
            crawler_ids, False
        )
        assert result_deactivate["success"] is True
        assert result_deactivate["result"]["success_count"] == len(sample_crawlers)
        assert result_deactivate["result"]["fail_count"] == 0
        assert "批量停用爬蟲設定完成" in result_deactivate["message"]

        # 檢查是否全部已停用
        all_crawlers_result_after_deactivate = crawlers_service.find_all_crawlers()
        assert all(
            not crawler.is_active
            for crawler in all_crawlers_result_after_deactivate["crawlers"]
        )

        # 批量啟用所有爬蟲
        result_activate = crawlers_service.batch_toggle_crawler_status(
            crawler_ids, True
        )
        assert result_activate["success"] is True
        assert result_activate["result"]["success_count"] == len(sample_crawlers)
        assert result_activate["result"]["fail_count"] == 0
        assert "批量啟用爬蟲設定完成" in result_activate["message"]

        # 檢查是否全部已啟用
        all_crawlers_result_after_activate = crawlers_service.find_all_crawlers()
        assert all(
            crawler.is_active
            for crawler in all_crawlers_result_after_activate["crawlers"]
        )

        # 測試部分不存在的 ID (預期部分失敗)
        invalid_ids = [999999, 888888]
        mixed_ids = [crawler_ids[0]] + invalid_ids  # 混合一個有效的 ID
        result_mixed = crawlers_service.batch_toggle_crawler_status(mixed_ids, False)
        assert result_mixed["success"] is True  # 因為至少有一個成功
        assert result_mixed["result"]["success_count"] == 1
        assert result_mixed["result"]["fail_count"] == 2
        assert 999999 in result_mixed["result"]["failed_ids"]  # 檢查失敗 ID
        assert 888888 in result_mixed["result"]["failed_ids"]

        # 檢查有效的 ID 狀態是否已變更
        check_toggled_crawler = crawlers_service.get_crawler_by_id(crawler_ids[0])
        assert check_toggled_crawler["success"] is True
        assert check_toggled_crawler["crawler"].is_active is False  # 狀態應為 False

    def test_find_filtered_crawlers(
        self, crawlers_service: CrawlersService, sample_crawlers: List[Dict[str, Any]]
    ):
        """測試根據過濾條件獲取分頁爬蟲列表，包括預覽"""
        expected_total = len(sample_crawlers)
        expected_active_count = sum(1 for c in sample_crawlers if c["is_active"])
        expected_bnext_count = sum(
            1 for c in sample_crawlers if c["crawler_type"] == "bnext"
        )
        expected_technews_count = sum(
            1 for c in sample_crawlers if c["crawler_type"] == "technews"
        )
        expected_active_bnext_count = sum(
            1
            for c in sample_crawlers
            if c["is_active"] and c["crawler_type"] == "bnext"
        )

        # --- 測試按類型過濾 ---
        filter_data_type = {"crawler_type": "bnext"}
        result_type = crawlers_service.find_filtered_crawlers(filter_data_type)
        assert result_type["success"] is True
        assert result_type["data"] is not None
        paginated_data_type = result_type["data"]
        assert isinstance(paginated_data_type, PaginatedCrawlerResponse)
        assert paginated_data_type.total == expected_bnext_count
        assert paginated_data_type.page == 1
        assert len(paginated_data_type.items) == expected_bnext_count
        assert isinstance(paginated_data_type.items[0], CrawlerReadSchema)
        assert paginated_data_type.items[0].crawler_type == "bnext"

        # --- 測試按啟用狀態過濾 ---
        filter_data_active = {"is_active": True}
        result_active = crawlers_service.find_filtered_crawlers(filter_data_active)
        assert result_active["success"] is True
        paginated_data_active = result_active["data"]
        assert isinstance(paginated_data_active, PaginatedCrawlerResponse)
        assert paginated_data_active.total == expected_active_count
        assert len(paginated_data_active.items) == expected_active_count
        assert all(
            isinstance(item, CrawlerReadSchema) for item in paginated_data_active.items
        )
        assert all(item.is_active for item in paginated_data_active.items)

        # --- 測試複合條件過濾 ---
        filter_data_compound = {"is_active": True, "crawler_type": "bnext"}
        result_compound = crawlers_service.find_filtered_crawlers(filter_data_compound)
        assert result_compound["success"] is True
        paginated_data_compound = result_compound["data"]
        assert isinstance(paginated_data_compound, PaginatedCrawlerResponse)
        assert paginated_data_compound.total == expected_active_bnext_count
        assert len(paginated_data_compound.items) == expected_active_bnext_count
        assert paginated_data_compound.items[0].crawler_type == "bnext"
        assert paginated_data_compound.items[0].is_active is True

        # --- 測試排序和分頁 ---
        filter_data_none = {}
        result_sort = crawlers_service.find_filtered_crawlers(
            filter_data_none, page=1, per_page=2, sort_by="crawler_name", sort_desc=True
        )
        assert result_sort["success"] is True
        paginated_data_sort = result_sort["data"]
        assert isinstance(paginated_data_sort, PaginatedCrawlerResponse)
        assert paginated_data_sort.total == expected_total
        assert paginated_data_sort.page == 1
        assert len(paginated_data_sort.items) == 2
        assert paginated_data_sort.has_next is True
        assert paginated_data_sort.has_prev is False
        expected_first_page_names = sorted(
            [c["crawler_name"] for c in sample_crawlers], reverse=True
        )[:2]
        actual_names = [item.crawler_name for item in paginated_data_sort.items]
        assert actual_names == expected_first_page_names

        # --- 測試預覽模式 ---
        preview_fields = ["id", "is_active"]
        filter_technews = {"crawler_type": "technews"}
        result_preview = crawlers_service.find_filtered_crawlers(
            filter_criteria=filter_technews,
            is_preview=True,
            preview_fields=preview_fields,
        )
        assert result_preview["success"] is True
        assert result_preview["data"] is not None
        paginated_preview = result_preview["data"]
        assert isinstance(paginated_preview, PaginatedCrawlerResponse)
        assert paginated_preview.total == expected_technews_count
        assert len(paginated_preview.items) == expected_technews_count
        item = paginated_preview.items[0]
        assert isinstance(item, dict)
        assert set(item.keys()) == set(preview_fields)
        # Find the original technews crawler data
        original_technews = next(
            (c for c in sample_crawlers if c["crawler_type"] == "technews"), None
        )
        assert original_technews is not None
        assert item["is_active"] == original_technews["is_active"]  # Should be False

        # --- 測試不匹配的條件 ---
        filter_data_nomatch = {"crawler_type": "不存在類型"}
        result_nomatch = crawlers_service.find_filtered_crawlers(filter_data_nomatch)
        assert result_nomatch["success"] is True  # 找不到結果也算成功
        assert result_nomatch["data"] is not None
        paginated_nomatch = result_nomatch["data"]
        assert isinstance(paginated_nomatch, PaginatedCrawlerResponse)
        assert paginated_nomatch.total == 0
        assert len(paginated_nomatch.items) == 0


class TestCrawlersServiceErrorHandling:
    """測試爬蟲服務的錯誤處理"""

    def test_invalid_crawler_data(self, crawlers_service: CrawlersService):
        """測試無效爬蟲設定資料處理 (缺少必要欄位)"""
        invalid_data = {
            "crawler_name": "測試爬蟲",
            "base_url": "https://example.com/test",
            # missing crawler_type
            "config_file_name": "test_config.json",
            "is_active": True,
        }

        result = crawlers_service.create_crawler(invalid_data)
        assert result["success"] is False
        assert "資料驗證失敗" in result["message"]
        assert "crawler_type" in result["message"]

    def test_validation_with_schema(self, crawlers_service: CrawlersService):
        """測試使用 Pydantic Schema 進行驗證 (例如空 URL)"""
        invalid_data = {
            "crawler_name": "測試爬蟲",
            "base_url": "",  # 無效的URL (假設 Schema 驗證不允許空)
            "is_active": True,
            "crawler_type": "test",
            "config_file_name": "test_config.json",
        }

        result = crawlers_service.create_crawler(invalid_data)
        assert result["success"] is False
        assert "資料驗證失敗" in result["message"]
        assert "base_url" in result["message"]  # 檢查特定欄位錯誤信息

    def test_empty_update_data(
        self, crawlers_service: CrawlersService, sample_crawlers: List[Dict[str, Any]]
    ):
        """測試空更新資料處理 (預期僅更新 updated_at)"""
        crawler_id = sample_crawlers[0]["id"]
        empty_update = {}

        # 獲取原始數據以供比較
        original_result = crawlers_service.get_crawler_by_id(crawler_id)
        assert original_result["success"] is True
        original_crawler_schema = original_result["crawler"]
        original_updated_at = original_crawler_schema.updated_at

        # 調用 update_crawler 並檢查返回的字典
        result = crawlers_service.update_crawler(crawler_id, empty_update)

        # 空字典應該只更新 updated_at (如果模型有 onupdate)，並返回成功
        assert (
            result["success"] is True
        ), f"空更新應該成功，但失敗了: {result.get('message')}"
        assert result["crawler"] is not None
        updated_crawler_schema = result["crawler"]
        assert updated_crawler_schema.id == crawler_id
        # 驗證其他字段未被更改
        assert (
            updated_crawler_schema.crawler_name == original_crawler_schema.crawler_name
        )
        assert updated_crawler_schema.base_url == original_crawler_schema.base_url
        assert updated_crawler_schema.is_active == original_crawler_schema.is_active
        # 驗證 updated_at 已更新 (可能被 onupdate 觸發，所以檢查它是否晚於原始更新時間)
        assert isinstance(updated_crawler_schema.updated_at, datetime)
        assert updated_crawler_schema.updated_at >= original_updated_at

    def test_create_or_update_validation(self, crawlers_service: CrawlersService):
        """測試創建或更新時的驗證錯誤處理"""
        # 測試創建時驗證失敗
        invalid_create_data = {
            "crawler_name": "測試爬蟲",
            "base_url": "",  # 無效的URL
            "is_active": True,
            "crawler_type": "test",
            "config_file_name": "test_config.json",
        }
        result_create = crawlers_service.create_or_update_crawler(invalid_create_data)
        assert result_create["success"] is False
        assert "爬蟲設定創建資料驗證失敗" in result_create["message"]
        assert "base_url" in result_create["message"]

        # 測試更新時驗證失敗 (假設 id 存在但其他數據無效)
        # 需先創建一個有效的爬蟲
        valid_data = {
            "crawler_name": "驗證測試爬蟲",
            "module_name": "test_module",
            "base_url": "https://valid.com",
            "is_active": True,
            "crawler_type": "validation",
            "config_file_name": "validation.json",
        }
        create_res = crawlers_service.create_crawler(valid_data)
        assert create_res["success"] is True
        crawler_id = create_res["crawler"].id

        invalid_update_data = {
            "id": crawler_id,
            "crawler_name": "測試爬蟲",
            "base_url": "",  # 無效的URL
            "is_active": True,
            "crawler_type": "test",
            "config_file_name": "test_config.json",
        }
        result_update = crawlers_service.create_or_update_crawler(invalid_update_data)
        assert result_update["success"] is False
        assert "爬蟲設定更新資料驗證失敗" in result_update["message"]
        assert "base_url" in result_update["message"]


class TestCrawlersServiceTransactions:
    """測試爬蟲服務的事務處理"""

    def test_update_transaction(
        self,
        crawlers_service: CrawlersService,
        sample_crawlers: List[Dict[str, Any]],
        initialized_db_manager: DatabaseManager,
    ):
        """測試更新操作的原子性 (因驗證失敗而回滾)"""
        crawler_id = sample_crawlers[0]["id"]
        original_name = sample_crawlers[0]["crawler_name"]  # 從字典獲取

        # 獲取原始數據狀態用於比較
        original_result = crawlers_service.get_crawler_by_id(crawler_id)
        assert original_result["success"] is True
        assert original_result["crawler"].crawler_name == original_name

        invalid_update = {
            "crawler_name": "有效名稱",
            "base_url": "",  # 無效值，會導致 Pydantic 驗證失敗
        }

        # 嘗試更新，預期因驗證失敗而服務層返回 False
        result = crawlers_service.update_crawler(crawler_id, invalid_update)
        assert result["success"] is False
        assert "資料驗證失敗" in result["message"]
        assert "base_url" in result["message"]

        # 驗證資料庫中的資料未被更改 (事务应已回滚)
        current_result = crawlers_service.get_crawler_by_id(crawler_id)
        assert current_result["success"] is True
        assert current_result["crawler"].crawler_name == original_name  # 應保持原樣

    def test_batch_toggle_transaction(
        self, crawlers_service: CrawlersService, sample_crawlers: List[Dict[str, Any]]
    ):
        """測試批量操作的事務性 (部分成功，部分失敗)"""
        valid_id = sample_crawlers[0]["id"]
        invalid_ids = [999999, 888888]
        mixed_ids = [valid_id] + invalid_ids

        # 獲取原始狀態
        original_crawler_result = crawlers_service.get_crawler_by_id(valid_id)
        assert original_crawler_result["success"] is True
        original_status = original_crawler_result["crawler"].is_active

        # 執行批量操作，切換狀態，預期部分失敗
        target_status = not original_status
        result = crawlers_service.batch_toggle_crawler_status(mixed_ids, target_status)

        # 驗證結果 - 即使有失敗，操作本身可能回報 success: True，但 result 內有失敗計數
        assert result["success"] is True  # 因為至少有一個成功
        assert result["result"]["success_count"] == 1
        assert result["result"]["fail_count"] == 2
        assert invalid_ids[0] in result["result"]["failed_ids"]
        assert invalid_ids[1] in result["result"]["failed_ids"]

        # 檢查有效 ID 的狀態是否已變更
        updated_result = crawlers_service.get_crawler_by_id(valid_id)
        assert updated_result["success"] is True
        assert updated_result["crawler"].is_active == target_status  # 狀態應已改變


class TestCrawlersServiceConfigFile:
    """測試爬蟲配置檔案相關功能"""

    def test_validate_config_file(
        self, crawlers_service: CrawlersService, valid_config_file: Dict[str, Any]
    ):
        """測試配置檔案格式驗證"""
        # Test valid config
        assert crawlers_service.validate_config_file(valid_config_file) is True
        invalid_config_missing_name = valid_config_file.copy()
        del invalid_config_missing_name["name"]
        assert (
            crawlers_service.validate_config_file(invalid_config_missing_name)
            is False
        )
        invalid_config_missing_selectors = valid_config_file.copy()
        del invalid_config_missing_selectors["selectors"]
        assert (
            crawlers_service.validate_config_file(invalid_config_missing_selectors)
            is False
        )
        invalid_config_missing_selector_key = valid_config_file.copy()
        invalid_config_missing_selector_key["selectors"] = valid_config_file[
            "selectors"
        ].copy()
        del invalid_config_missing_selector_key["selectors"]["get_article_links"]
        assert (
            crawlers_service.validate_config_file(
                invalid_config_missing_selector_key
            )
            is False
        )

    def test_update_crawler_config(
        self,
        crawlers_service: CrawlersService,
        sample_crawlers: List[Dict[str, Any]],
        valid_config_file: Dict[str, Any],
        tmp_path,
        monkeypatch,
    ):
        """測試更新爬蟲配置檔案"""
        # 1. 準備測試資料
        crawler_id = sample_crawlers[0]["id"]
        crawler_name = sample_crawlers[0]["crawler_name"] # <<< 獲取 crawler_name
        # *移除*測試內部自己生成 config_filename 的邏輯
        # config_filename = crawlers_service._clean_filename(f"test_config_{crawler_id}.json")

        # <<< 計算服務方法預期會生成的檔名 >>>
        expected_service_filename = crawlers_service._clean_filename(f"{crawler_name}.json")
        logger.info(f"服務預期生成的檔名: {expected_service_filename}")

        # 2. 設置環境變數指向 tmp_path
        config_dir = tmp_path / "test_configs"
        monkeypatch.setenv("WEB_SITE_CONFIG_DIR", str(config_dir))
        logger.info(f"測試配置目錄設定為: {config_dir}")

        # 3. 創建模擬的檔案對象 (檔名是使用者上傳的，不重要)
        mock_file = MagicMock()
        mock_file.filename = "user_uploaded_file.json" # 模擬使用者上傳的檔名
        config_bytes = json.dumps(valid_config_file).encode("utf-8")
        mock_file.read.return_value = config_bytes
        mock_file.seek = MagicMock()

        # 4. 準備爬蟲資料 (用於更新數據庫 - config_file_name 會被服務覆蓋)
        crawler_data = {
            "crawler_name": crawler_name,
            "base_url": sample_crawlers[0]["base_url"],
            "is_active": sample_crawlers[0]["is_active"],
            "crawler_type": sample_crawlers[0]["crawler_type"],
            # "config_file_name": config_filename, # <<< 這個欄位實際會被服務忽略並重新生成
        }

        # 5. 測試更新配置
        result = crawlers_service.update_crawler_config(
            crawler_id, mock_file, crawler_data
        )

        # 6. 驗證服務層返回結果
        assert result["success"] is True, f"更新失敗: {result.get('message')}"
        assert result["crawler"] is not None
        assert isinstance(result["crawler"], CrawlerReadSchema)

        # <<< 修改斷言：比較資料庫返回的檔名和服務預期生成的檔名 >>>
        assert result["crawler"].config_file_name == expected_service_filename
        assert result["crawler"].id == crawler_id

        # 7. 驗證配置檔案是否已保存到 tmp_path (使用預期生成的檔名)
        expected_config_path = config_dir / expected_service_filename # <<< 使用預期檔名
        assert expected_config_path.exists(), f"配置文件未在預期路徑找到: {expected_config_path}"

        # 8. 驗證配置檔案內容
        with open(expected_config_path, "r", encoding="utf-8") as f:
            saved_config = json.load(f)
        assert saved_config == valid_config_file
        logger.info(f"成功驗證已保存的配置文件內容於: {expected_config_path}")

    def test_update_crawler_config_invalid_json(
        self,
        crawlers_service: CrawlersService,
        sample_crawlers: List[Dict[str, Any]],
        tmp_path,
        monkeypatch,
    ):
        """測試更新無效的 JSON 配置檔案"""
        crawler_id = sample_crawlers[0]["id"]
        config_filename = crawlers_service._clean_filename(f"invalid_json_{crawler_id}.json")

        # 設置環境變數
        config_dir = tmp_path / "test_configs_invalid"
        monkeypatch.setenv("WEB_SITE_CONFIG_DIR", str(config_dir))

        # 創建模擬的檔案對象
        mock_file = MagicMock()
        mock_file.filename = config_filename
        mock_file.read.return_value = b"invalid json content{" # Malformed JSON
        mock_file.seek = MagicMock()

        # 準備爬蟲資料
        crawler_data = {
            "crawler_name": sample_crawlers[0]["crawler_name"],
            "base_url": sample_crawlers[0]["base_url"],
            "is_active": sample_crawlers[0]["is_active"],
            "crawler_type": sample_crawlers[0]["crawler_type"],
            "config_file_name": config_filename,
        }

        # 測試更新無效配置
        result = crawlers_service.update_crawler_config(
            crawler_id, mock_file, crawler_data
        )
        assert result["success"] is False
        assert "配置檔案不是有效的 JSON 格式" in result["message"]
        # 驗證檔案未被創建
        expected_config_path = config_dir / config_filename
        assert not expected_config_path.exists()

    def test_update_crawler_config_invalid_format(
        self,
        crawlers_service: CrawlersService,
        sample_crawlers: List[Dict[str, Any]],
        tmp_path,
        monkeypatch,
    ):
        """測試更新格式不正確的配置檔案 (缺少必要欄位)"""
        crawler_id = sample_crawlers[0]["id"]
        config_filename = crawlers_service._clean_filename(f"invalid_format_{crawler_id}.json")

        # 設置環境變數
        config_dir = tmp_path / "test_configs_invalid_format"
        monkeypatch.setenv("WEB_SITE_CONFIG_DIR", str(config_dir))

        # 創建格式不正確的配置檔案內容
        invalid_config = {
            "name": "test_crawler",
            "base_url": "https://example.com",
            # 缺少 selectors 等必要欄位
        }

        # 創建模擬的檔案對象
        mock_file = MagicMock()
        mock_file.filename = config_filename
        mock_file.read.return_value = json.dumps(invalid_config).encode("utf-8")
        mock_file.seek = MagicMock()

        # 準備爬蟲資料
        crawler_data = {
            "crawler_name": sample_crawlers[0]["crawler_name"],
            "base_url": sample_crawlers[0]["base_url"],
            "is_active": sample_crawlers[0]["is_active"],
            "crawler_type": sample_crawlers[0]["crawler_type"],
            "config_file_name": config_filename,
        }

        # 測試更新格式不正確的配置
        result = crawlers_service.update_crawler_config(
            crawler_id, mock_file, crawler_data
        )
        assert result["success"] is False
        assert "配置檔案格式或內容不正確" in result["message"] # 根據服務返回的錯誤訊息調整
        # 驗證檔案未被創建
        expected_config_path = config_dir / config_filename
        assert not expected_config_path.exists()

    def test_update_crawler_config_generates_safe_filename(
        self,
        crawlers_service: CrawlersService,
        sample_crawlers: List[Dict[str, Any]],
        valid_config_file: Dict[str, Any],
        tmp_path,
        monkeypatch,
    ):
        """測試 update_crawler_config 是否根據 crawler_name 生成安全檔名"""
        # 1. 準備測試資料
        crawler_id = sample_crawlers[0]["id"]
        crawler_name = sample_crawlers[0]["crawler_name"] # 例如 "數位時代爬蟲"
        # 提供一個包含特殊字符和路徑的原始檔名
        original_uploaded_filename = "../path/to/user upload with spaces & symbols!.json"

        # 2. 設置環境變數
        config_dir = tmp_path / "safe_name_test_configs"
        monkeypatch.setenv("WEB_SITE_CONFIG_DIR", str(config_dir))
        logger.info(f"安全檔名測試配置目錄設定為: {config_dir}")

        # 3. 創建模擬檔案對象
        mock_file = MagicMock()
        mock_file.filename = original_uploaded_filename # 使用包含特殊字符的原始檔名
        config_bytes = json.dumps(valid_config_file).encode("utf-8")
        mock_file.read.return_value = config_bytes
        mock_file.seek = MagicMock()

        # 4. 準備用於更新資料庫的爬蟲資料 (這裡的 config_file_name 會被服務覆蓋)
        crawler_data_for_update = {
            "crawler_name": crawler_name,
            "base_url": sample_crawlers[0]["base_url"],
            "is_active": sample_crawlers[0]["is_active"],
            "crawler_type": sample_crawlers[0]["crawler_type"],
            "config_file_name": "this_should_be_overwritten.json", # 提供一個會被覆蓋的值
        }

        # 5. 計算預期的安全檔名 (基於 crawler_name)
        expected_base_filename = f"{crawler_name}.json"
        expected_safe_filename = crawlers_service._clean_filename(expected_base_filename)
        logger.info(f"預期生成的安全檔名: {expected_safe_filename}")

        # 6. 執行更新操作
        result = crawlers_service.update_crawler_config(
            crawler_id, mock_file, crawler_data_for_update
        )

        # 7. 驗證服務層返回結果
        assert result["success"] is True, f"更新失敗: {result.get('message')}"
        assert result["crawler"] is not None

        # 8. 核心驗證：資料庫中儲存的檔名是否為預期的安全檔名
        assert result["crawler"].config_file_name == expected_safe_filename, \
            f"資料庫中的檔名 ({result['crawler'].config_file_name}) 與預期的安全檔名 ({expected_safe_filename}) 不符"

        # 9. 驗證實際儲存的檔案名稱是否為預期的安全檔名
        expected_config_path = config_dir / expected_safe_filename
        assert expected_config_path.exists(), f"配置文件未在預期路徑找到: {expected_config_path}"
        logger.info(f"成功驗證配置文件已使用安全檔名保存於: {expected_config_path}")

        # 10. (可選) 驗證檔案內容
        with open(expected_config_path, "r", encoding="utf-8") as f:
            saved_config = json.load(f)
        assert saved_config == valid_config_file

    def test_get_crawler_config(
        self,
        crawlers_service: CrawlersService,
        sample_crawlers: List[Dict[str, Any]],
        valid_config_file: Dict[str, Any],
        tmp_path,
        monkeypatch,
    ):
        """測試獲取爬蟲的配置檔案內容"""
        # 1. 準備：先保存一個有效的配置檔案
        crawler_id = sample_crawlers[0]["id"]
        # **重要**: 確保這裡使用的檔名與服務內部生成/查找的邏輯一致
        # 如果服務現在基於 crawler_name 生成，我們需要用生成的檔名創建測試檔案
        crawler_name = sample_crawlers[0]["crawler_name"]
        expected_base_filename = f"{crawler_name}.json"
        config_filename = crawlers_service._clean_filename(expected_base_filename) # <<< 使用清理後的檔名

        config_dir = tmp_path / "get_test_configs"
        config_path = config_dir / config_filename

        # --- 更新資料庫記錄 --- <<< 新增步驟 >>>
        update_result = crawlers_service.update_crawler(crawler_id, {"config_file_name": config_filename})
        assert update_result["success"] is True, f"未能更新測試爬蟲的 config_file_name: {update_result.get('message')}"
        logger.info(f"已更新資料庫中爬蟲 ID={crawler_id} 的 config_file_name 為: {config_filename}")
        # --- 更新結束 ---

        # 更新 sample_crawlers 中的檔名記錄... (這行現在變得不那麼重要，因為服務會讀資料庫，但保留也無妨)
        sample_crawlers[0]['config_file_name'] = config_filename

        monkeypatch.setenv("WEB_SITE_CONFIG_DIR", str(config_dir))

        config_dir.mkdir()
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(valid_config_file, f, indent=4)
        logger.info(f"測試用的配置文件已創建於: {config_path}")

        # 2. 執行獲取配置的服務方法 (現在它應該會查找正確的檔名)
        result = crawlers_service.get_crawler_config(crawler_id)

        # 3. 驗證結果
        assert result["success"] is True, f"獲取配置失敗: {result.get('message')}"
        assert result["config"] is not None
        assert result["config"] == valid_config_file

        # 4. 測試獲取不存在爬蟲的配置
        result_invalid_id = crawlers_service.get_crawler_config(999999)
        assert result_invalid_id["success"] is False
        assert "爬蟲設定不存在" in result_invalid_id["message"]

        # 5. 測試配置文件不存在的情況
        non_existent_filename = "non_existent_safe_name.json"
        crawlers_service.update_crawler(crawler_id, {"config_file_name": non_existent_filename})
        result_file_missing = crawlers_service.get_crawler_config(crawler_id)
        assert result_file_missing["success"] is False
        assert "配置檔案不存在" in result_file_missing["message"]
        # 恢復檔名
        crawlers_service.update_crawler(crawler_id, {"config_file_name": config_filename})
