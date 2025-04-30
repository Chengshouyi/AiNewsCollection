"""測試 CrawlersRepository 的功能。

此模組包含了對 CrawlersRepository 類的所有測試案例，包括：
- 基本的 CRUD 操作
- 搜尋和過濾功能
- 分頁功能
- 批次操作
- 統計功能
"""

import math
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any  # 引入 List, Dict, Any

import pytest

from src.database.crawlers_repository import CrawlersRepository, SchemaType
from src.error.errors import (
    DatabaseOperationError,
    InvalidOperationError,
    ValidationError,
)
from src.models.base_model import Base  # Base is needed for initialized_db_manager
from src.models.crawlers_model import Crawlers
from src.models.crawlers_schema import CrawlersCreateSchema, CrawlersUpdateSchema


# flake8: noqa: F811
# pylint: disable=redefined-outer-name

logger = logging.getLogger(__name__)  # 使用統一的 logger


# 使用 db_manager_for_test 的 fixture ---
@pytest.fixture(scope="function")
def initialized_db_manager(db_manager_for_test):
    """Fixture that depends on db_manager_for_test, creates tables, and yields the manager."""
    logger.debug("Creating tables for test function...")
    try:
        db_manager_for_test.create_tables(Base)
        yield db_manager_for_test
    finally:
        logger.debug(
            "Test function finished, tables might be dropped by manager cleanup or next test setup."
        )


# --- 更新依賴的 fixtures ---
@pytest.fixture(scope="function")
def crawlers_repo(initialized_db_manager):
    """為每個測試函數創建新的 CrawlersRepository 實例"""
    with initialized_db_manager.session_scope() as session:
        yield CrawlersRepository(session, Crawlers)


@pytest.fixture(scope="function")
def clean_db(initialized_db_manager):
    """清空資料庫的 fixture"""
    with initialized_db_manager.session_scope() as session:
        session.query(Crawlers).delete()
        session.commit()
        session.expire_all()


@pytest.fixture(scope="function")
def sample_crawlers_data(
    initialized_db_manager, clean_db
) -> List[Dict[str, Any]]:  # 修改名稱並返回 Dict
    """建立測試用的爬蟲資料，返回包含關鍵數據的字典列表"""
    crawlers_output_data = []
    with initialized_db_manager.session_scope() as session:
        now = datetime.now(timezone.utc)

        crawlers = [
            Crawlers(
                crawler_name="新聞爬蟲1",
                module_name="test_module",
                base_url="https://example.com/news1",
                is_active=True,
                created_at=(now - timedelta(days=1)),
                crawler_type="web",
                config_file_name="test_crawler.json",
            ),
            Crawlers(
                crawler_name="新聞爬蟲2",
                module_name="test_module",
                base_url="https://example.com/news2",
                is_active=False,
                crawler_type="web",
                config_file_name="test_crawler.json",
            ),
            Crawlers(
                crawler_name="RSS爬蟲",
                module_name="test_module",
                base_url="https://example.com/rss",
                is_active=True,
                crawler_type="rss",
                config_file_name="test_crawler.json",
            ),
        ]
        session.add_all(crawlers)
        session.flush()  # 分配 ID
        # 提取需要的數據到字典中
        for c in crawlers:
            crawlers_output_data.append(
                {
                    "id": c.id,
                    "crawler_name": c.crawler_name,
                    "base_url": c.base_url,
                    "is_active": c.is_active,
                    "crawler_type": c.crawler_type,
                    "created_at": c.created_at,
                }
            )
        session.commit()  # 提交事務

    return crawlers_output_data  # 返回字典列表


# CrawlersRepository 測試
class TestCrawlersRepository:
    """測試 Crawlers 相關資料庫操作"""

    def test_get_schema_class(self, crawlers_repo, clean_db):
        """測試獲取正確的 schema 類別"""
        schema = crawlers_repo.get_schema_class()
        assert schema == CrawlersCreateSchema
        create_schema = crawlers_repo.get_schema_class(SchemaType.CREATE)
        assert create_schema == CrawlersCreateSchema
        update_schema = crawlers_repo.get_schema_class(SchemaType.UPDATE)
        assert update_schema == CrawlersUpdateSchema
        with pytest.raises(ValueError) as exc_info:
            crawlers_repo.get_schema_class(SchemaType.LIST)
        assert "未支援的 schema 類型" in str(exc_info.value)

    def test_validate_data(self, crawlers_repo, clean_db):
        """測試 validate_data 方法"""
        crawler_data = {
            "crawler_name": "測試驗證爬蟲",
            "module_name": "test_module",
            "base_url": "https://example.com/validate",
            "is_active": True,
            "crawler_type": "web",
            "config_file_name": "test_crawler.json",
        }
        validated_create = crawlers_repo.validate_data(crawler_data, SchemaType.CREATE)
        assert validated_create is not None
        assert validated_create["crawler_name"] == "測試驗證爬蟲"
        assert validated_create["base_url"] == "https://example.com/validate"
        update_data = {"crawler_name": "更新的爬蟲名稱", "is_active": False}
        validated_update = crawlers_repo.validate_data(update_data, SchemaType.UPDATE)
        assert validated_update is not None
        assert validated_update["crawler_name"] == "更新的爬蟲名稱"
        assert validated_update["is_active"] is False
        assert "base_url" not in validated_update
        invalid_data = {"crawler_name": "缺失欄位爬蟲"}
        with pytest.raises(ValidationError) as excinfo:
            crawlers_repo.validate_data(invalid_data, SchemaType.CREATE)
        assert "以下必填欄位缺失或值為空/空白" in str(excinfo.value)

    def test_find_all(
        self, crawlers_repo, sample_crawlers_data, clean_db
    ):  # 使用 data fixture
        """測試獲取所有爬蟲設定 (使用 find_all)"""
        settings = crawlers_repo.find_all()
        assert len(settings) == len(sample_crawlers_data)  # 與 fixture data 數量比較
        assert isinstance(settings[0], Crawlers)
        settings_limit = crawlers_repo.find_all(limit=1)
        assert len(settings_limit) == 1
        settings_offset = crawlers_repo.find_all(limit=1, offset=1)
        assert len(settings_offset) == 1
        assert settings_limit[0].id != settings_offset[0].id
        preview_settings = crawlers_repo.find_all(
            is_preview=True, preview_fields=["id", "crawler_name"]
        )
        assert len(preview_settings) == len(sample_crawlers_data)
        assert isinstance(preview_settings[0], dict)
        assert "id" in preview_settings[0]
        assert "crawler_name" in preview_settings[0]
        assert "base_url" not in preview_settings[0]

    def test_get_by_id(
        self, crawlers_repo, sample_crawlers_data, clean_db
    ):  # 使用 data fixture
        """測試通過ID獲取爬蟲設定"""
        target_id = sample_crawlers_data[0]["id"]  # 從字典獲取 ID
        setting = crawlers_repo.get_by_id(target_id)
        assert setting is not None
        assert isinstance(setting, Crawlers)
        assert setting.id == target_id
        setting_nonexistent = crawlers_repo.get_by_id(999)
        assert setting_nonexistent is None

    def test_find_by_crawler_name(
        self, crawlers_repo, sample_crawlers_data, clean_db
    ):  # 使用 data fixture
        """測試根據爬蟲名稱模糊查詢"""
        # 驗證初始數據符合預期數量
        assert len(sample_crawlers_data) == 3

        crawlers_all = crawlers_repo.find_by_crawler_name("爬蟲")
        assert len(crawlers_all) == 3
        assert isinstance(crawlers_all[0], Crawlers)

        crawlers_active = crawlers_repo.find_by_crawler_name("爬蟲", is_active=True)
        assert len(crawlers_active) == 2

        crawlers_inactive = crawlers_repo.find_by_crawler_name("爬蟲", is_active=False)
        assert len(crawlers_inactive) == 1
        # 找到不活躍的爬蟲數據
        inactive_crawler_name = next(
            c["crawler_name"] for c in sample_crawlers_data if not c["is_active"]
        )
        assert (
            crawlers_inactive[0].crawler_name == inactive_crawler_name
        )  # 應為 "新聞爬蟲2"

        crawlers_limit = crawlers_repo.find_by_crawler_name("爬蟲", limit=1)
        assert len(crawlers_limit) == 1

        crawlers_offset = crawlers_repo.find_by_crawler_name("爬蟲", limit=1, offset=1)
        assert len(crawlers_offset) == 1
        assert crawlers_limit[0].id != crawlers_offset[0].id

        crawlers_preview = crawlers_repo.find_by_crawler_name(
            "爬蟲", is_preview=True, preview_fields=["id", "crawler_name"]
        )
        assert len(crawlers_preview) == 3
        assert isinstance(crawlers_preview[0], dict)
        assert "id" in crawlers_preview[0]
        assert "crawler_name" in crawlers_preview[0]
        assert "base_url" not in crawlers_preview[0]

        crawlers_preview_invalid = crawlers_repo.find_by_crawler_name(
            "爬蟲", is_preview=True, preview_fields=["invalid_field"]
        )
        assert len(crawlers_preview_invalid) == 3
        assert isinstance(crawlers_preview_invalid[0], Crawlers)

    def test_find_by_crawler_name_exact(
        self, crawlers_repo, sample_crawlers_data, clean_db
    ):  # 使用 data fixture
        """測試根據爬蟲名稱精確查詢"""
        target_data = sample_crawlers_data[0]  # 獲取第一個爬蟲的數據字典
        target_name = target_data["crawler_name"]
        target_id = target_data["id"]

        crawler_instance = crawlers_repo.find_by_crawler_name_exact(target_name)
        assert crawler_instance is not None
        assert isinstance(crawler_instance, Crawlers)
        assert crawler_instance.crawler_name == target_name
        assert crawler_instance.id == target_id

        crawler_preview = crawlers_repo.find_by_crawler_name_exact(
            target_name, is_preview=True, preview_fields=["id"]
        )
        assert crawler_preview is not None
        assert isinstance(crawler_preview, dict)
        assert crawler_preview["id"] == target_id
        assert "crawler_name" not in crawler_preview

        crawler_nonexistent = crawlers_repo.find_by_crawler_name_exact("不存在的爬蟲")
        assert crawler_nonexistent is None

    def test_find_active_crawlers(
        self, crawlers_repo, sample_crawlers_data, clean_db
    ):  # 使用 data fixture
        """測試查詢活動中的爬蟲"""
        active_crawlers = crawlers_repo.find_active_crawlers()
        expected_active_count = sum(1 for c in sample_crawlers_data if c["is_active"])
        assert len(active_crawlers) == expected_active_count  # 應為 2
        assert all(isinstance(c, Crawlers) and c.is_active for c in active_crawlers)

        active_limit = crawlers_repo.find_active_crawlers(limit=1)
        assert len(active_limit) == 1

        active_offset = crawlers_repo.find_active_crawlers(limit=1, offset=1)
        assert len(active_offset) == 1
        assert active_limit[0].id != active_offset[0].id

        active_preview = crawlers_repo.find_active_crawlers(
            is_preview=True, preview_fields=["crawler_name"]
        )
        assert len(active_preview) == expected_active_count
        assert isinstance(active_preview[0], dict)
        assert "crawler_name" in active_preview[0]
        assert "id" not in active_preview[0]

    def test_create(self, crawlers_repo, clean_db):
        """測試使用模式驗證創建爬蟲"""
        new_crawler_data_defaults = {
            "crawler_name": "測試預設值爬蟲",
            "module_name": "test_module",
            "base_url": "https://example.com/defaults",
            "crawler_type": "web",
            "config_file_name": "test_crawler.json",
        }
        new_crawler_defaults = crawlers_repo.create(new_crawler_data_defaults)
        # Commit before verifying with get_by_id
        crawlers_repo.session.commit()
        crawlers_repo.session.expire_all()

        created_default = crawlers_repo.get_by_id(new_crawler_defaults.id)
        assert created_default is not None
        assert created_default.is_active is True

        new_crawler_data_explicit = {
            "crawler_name": "測試明確狀態爬蟲",
            "module_name": "test_module",
            "base_url": "https://example.com/explicit",
            "is_active": False,
            "crawler_type": "web",
            "config_file_name": "test_crawler.json",
        }
        new_crawler_explicit = crawlers_repo.create(new_crawler_data_explicit)
        # Commit before verifying with get_by_id
        crawlers_repo.session.commit()
        crawlers_repo.session.expire_all()

        created_explicit = crawlers_repo.get_by_id(new_crawler_explicit.id)
        assert created_explicit is not None
        assert created_explicit.is_active is False

        invalid_data = {
            "crawler_name": "缺失欄位爬蟲",
            "module_name": "test_module",
            "is_active": True,
        }
        with pytest.raises(ValidationError):
            crawlers_repo.create(invalid_data)
        # No commit needed for failed creation

    def test_crawler_name_uniqueness(
        self, crawlers_repo, sample_crawlers_data, clean_db
    ):  # 使用 data fixture
        """測試爬蟲名稱唯一性驗證"""
        existing_name = sample_crawlers_data[0]["crawler_name"]  # "新聞爬蟲1"
        existing_id_to_update = sample_crawlers_data[1]["id"]  # "新聞爬蟲2" 的 ID

        duplicate_data = {
            "crawler_name": existing_name,  # 使用已存在的名稱
            "module_name": "test_module",
            "base_url": "https://example.com/duplicate",
            "is_active": True,
            "crawler_type": "web",
            "config_file_name": "test_crawler.json",
        }

        with pytest.raises(ValidationError) as exc_info:
            crawlers_repo.create(duplicate_data)
        assert "爬蟲名稱" in str(exc_info.value)
        assert "已存在" in str(exc_info.value)
        # No commit needed for failed creation

        with pytest.raises(ValidationError) as exc_info:
            crawlers_repo.update(existing_id_to_update, {"crawler_name": existing_name})
        assert "爬蟲名稱" in str(exc_info.value)
        assert "已存在" in str(exc_info.value)
        # No commit needed for failed update

    def test_update(
        self, crawlers_repo, sample_crawlers_data, clean_db
    ):  # 使用 data fixture
        """測試使用模式驗證更新爬蟲"""
        target_data = sample_crawlers_data[0]  # 獲取第一個爬蟲的數據字典
        setting_id = target_data["id"]
        original_base_url = target_data["base_url"]
        original_crawler_type = target_data["crawler_type"]

        update_data = {"crawler_name": "已更新爬蟲名稱", "is_active": False}

        updated_in_session = crawlers_repo.update(setting_id, update_data)
        # Commit before verifying with get_by_id
        crawlers_repo.session.commit()
        crawlers_repo.session.expire_all()

        updated_from_db = crawlers_repo.get_by_id(setting_id)

        assert updated_from_db is not None
        assert updated_from_db.crawler_name == "已更新爬蟲名稱"
        assert updated_from_db.is_active is False
        assert updated_from_db.updated_at is not None
        assert updated_from_db.base_url == original_base_url  # 驗證未變更
        assert updated_from_db.crawler_type == original_crawler_type  # 驗證未變更

        result_nonexistent = crawlers_repo.update(999, update_data)
        assert result_nonexistent is None
        # No commit needed for failed update attempt

        # Rollback to ensure clean state (though last successful commit persists)
        crawlers_repo.session.rollback()
        reverted_crawler = crawlers_repo.get_by_id(setting_id)
        # After rollback, it should still reflect the committed state
        assert reverted_crawler.crawler_name == "已更新爬蟲名稱"
        assert reverted_crawler.crawler_type == original_crawler_type

    def test_delete(
        self, crawlers_repo, sample_crawlers_data, clean_db
    ):  # 使用 data fixture
        """測試刪除爬蟲設定"""
        target_data = sample_crawlers_data[-1]  # 獲取最後一個爬蟲的數據字典
        setting_id = target_data["id"]

        result = crawlers_repo.delete(setting_id)
        # Commit before verifying with get_by_id
        crawlers_repo.session.commit()
        assert result is True

        deleted = crawlers_repo.get_by_id(setting_id)
        assert deleted is None

        result_nonexistent = crawlers_repo.delete(999)
        assert result_nonexistent is False
        # No commit needed for failed delete attempt

    def test_toggle_active_status(
        self, crawlers_repo, sample_crawlers_data, clean_db
    ):  # 使用 data fixture
        """測試切換爬蟲活躍狀態"""
        target_data = sample_crawlers_data[0]  # 獲取第一個爬蟲的數據字典
        crawler_id = target_data["id"]
        original_status = target_data["is_active"]  # 從字典獲取原始狀態

        result_toggle1 = crawlers_repo.toggle_active_status(crawler_id)
        # Commit before verifying state change
        crawlers_repo.session.commit()
        assert result_toggle1 is True

        crawlers_repo.session.expire_all()  # Reload from DB
        updated_crawler = crawlers_repo.get_by_id(crawler_id)
        assert updated_crawler is not None
        assert updated_crawler.is_active != original_status
        assert updated_crawler.updated_at is not None

        # Toggle back
        result_toggle2 = crawlers_repo.toggle_active_status(crawler_id)
        # Commit before verifying state change
        crawlers_repo.session.commit()
        assert result_toggle2 is True

        crawlers_repo.session.expire_all()  # Reload from DB
        updated_again = crawlers_repo.get_by_id(crawler_id)
        assert updated_again is not None
        assert updated_again.is_active == original_status  # 應恢復原始狀態

        result_toggle_nonexistent = crawlers_repo.toggle_active_status(999)
        assert result_toggle_nonexistent is False
        # No commit needed for failed toggle attempt

    def test_find_by_type(
        self, crawlers_repo, sample_crawlers_data, clean_db
    ):  # 使用 data fixture
        """測試根據爬蟲類型查找"""
        web_crawlers_active = crawlers_repo.find_by_type("web", is_active=True)
        expected_active_web_count = sum(
            1
            for c in sample_crawlers_data
            if c["crawler_type"] == "web" and c["is_active"]
        )
        assert len(web_crawlers_active) == expected_active_web_count  # 應為 1
        assert isinstance(web_crawlers_active[0], Crawlers)

        web_crawlers_inactive = crawlers_repo.find_by_type("web", is_active=False)
        expected_inactive_web_count = sum(
            1
            for c in sample_crawlers_data
            if c["crawler_type"] == "web" and not c["is_active"]
        )
        assert len(web_crawlers_inactive) == expected_inactive_web_count  # 應為 1

        web_limit = crawlers_repo.find_by_type("web", is_active=None, limit=1)
        assert len(web_limit) == 1

        web_offset = crawlers_repo.find_by_type(
            "web", is_active=None, limit=1, offset=1
        )
        assert len(web_offset) == 1
        assert web_limit[0].id != web_offset[0].id

        web_preview = crawlers_repo.find_by_type(
            "web", is_active=None, is_preview=True, preview_fields=["is_active"]
        )
        expected_web_count = sum(
            1 for c in sample_crawlers_data if c["crawler_type"] == "web"
        )
        assert len(web_preview) == expected_web_count  # 應為 2
        assert isinstance(web_preview[0], dict)
        assert "is_active" in web_preview[0]

        non_existent_type = crawlers_repo.find_by_type("api")
        assert isinstance(non_existent_type, list)
        assert len(non_existent_type) == 0

    def test_find_by_target(
        self, crawlers_repo, sample_crawlers_data, clean_db
    ):  # 使用 data fixture
        """測試根據爬取目標查詢"""
        # Fixture data doesn't have a 'target' field directly, the method uses base_url LIKE
        # Expected 'news' target matches base_url like '%news%'
        expected_news_count = sum(
            1 for c in sample_crawlers_data if "news" in c["base_url"]
        )  # 2
        expected_active_news = sum(
            1
            for c in sample_crawlers_data
            if "news" in c["base_url"] and c["is_active"]
        )  # 1
        expected_inactive_news = sum(
            1
            for c in sample_crawlers_data
            if "news" in c["base_url"] and not c["is_active"]
        )  # 1

        news_crawlers_active = crawlers_repo.find_by_target("news", is_active=True)
        assert len(news_crawlers_active) == expected_active_news  # 1
        assert isinstance(news_crawlers_active[0], Crawlers)

        news_crawlers_inactive = crawlers_repo.find_by_target("news", is_active=False)
        assert len(news_crawlers_inactive) == expected_inactive_news  # 1

        news_limit = crawlers_repo.find_by_target("news", is_active=None, limit=1)
        assert len(news_limit) == 1

        news_offset = crawlers_repo.find_by_target(
            "news", is_active=None, limit=1, offset=1
        )
        assert len(news_offset) == 1
        assert news_limit[0].id != news_offset[0].id

        news_preview = crawlers_repo.find_by_target(
            "news", is_active=None, is_preview=True, preview_fields=["base_url"]
        )
        assert len(news_preview) == expected_news_count  # 2
        assert isinstance(news_preview[0], dict)
        assert "base_url" in news_preview[0]

    def test_get_crawler_statistics(
        self, crawlers_repo, sample_crawlers_data, clean_db
    ):  # 使用 data fixture
        """測試獲取爬蟲統計資訊"""
        stats = crawlers_repo.get_crawler_statistics()

        expected_total = len(sample_crawlers_data)
        expected_active = sum(1 for c in sample_crawlers_data if c["is_active"])
        expected_inactive = expected_total - expected_active
        expected_web = sum(
            1 for c in sample_crawlers_data if c["crawler_type"] == "web"
        )
        expected_rss = sum(
            1 for c in sample_crawlers_data if c["crawler_type"] == "rss"
        )

        assert stats["total"] == expected_total  # 3
        assert stats["active"] == expected_active  # 2
        assert stats["inactive"] == expected_inactive  # 1
        assert stats["by_type"]["web"] == expected_web  # 2
        assert stats["by_type"]["rss"] == expected_rss  # 1

    def test_create_or_update(
        self, crawlers_repo, sample_crawlers_data, clean_db
    ):  # 使用 data fixture
        """測試創建或更新功能"""
        # --- 測試更新現有記錄 ---
        existing_data = sample_crawlers_data[0]  # 獲取第一個爬蟲的數據字典
        existing_id = existing_data["id"]
        update_data = {
            "id": existing_id,
            "crawler_name": "更新通過create_or_update",
        }

        result_update = crawlers_repo.create_or_update(update_data)
        # Commit before verifying
        crawlers_repo.session.commit()
        crawlers_repo.session.expire_all()

        updated_crawler = crawlers_repo.get_by_id(existing_id)
        assert updated_crawler is not None
        assert updated_crawler.id == existing_id
        assert updated_crawler.crawler_name == "更新通過create_or_update"

        # --- 測試創建新記錄 ---
        new_data = {
            "crawler_name": "新記錄通過create_or_update",
            "module_name": "test_module",
            "base_url": "https://example.com/new",
            "crawler_type": "api",
            "config_file_name": "test_crawler.json",
        }

        result_create = crawlers_repo.create_or_update(new_data)
        # Commit before verifying
        crawlers_repo.session.commit()
        new_id = (
            result_create.id
        )  # ID is assigned after create and before commit (due to flush likely)
        assert new_id is not None

        crawlers_repo.session.expire_all()
        created_crawler = crawlers_repo.get_by_id(new_id)
        assert created_crawler is not None
        assert created_crawler.id == new_id
        assert created_crawler.crawler_name == "新記錄通過create_or_update"
        assert created_crawler.crawler_type == "api"

        # --- 測試ID不存在的情況 (應觸發創建) ---
        nonexistent_id_data = {
            "id": 999,
            "crawler_name": "不存在的ID",
            "module_name": "test_module",
            "base_url": "https://example.com/nonexistent",
            "crawler_type": "web",
            "config_file_name": "test_crawler.json",
        }

        result_nonexistent = crawlers_repo.create_or_update(nonexistent_id_data)
        # Commit before verifying
        crawlers_repo.session.commit()
        created_via_nonexistent_id = result_nonexistent.id  # ID assigned before commit
        assert created_via_nonexistent_id is not None

        crawlers_repo.session.expire_all()
        created_nonexistent_crawler = crawlers_repo.get_by_id(
            created_via_nonexistent_id
        )
        assert created_nonexistent_crawler is not None
        assert created_nonexistent_crawler.crawler_name == "不存在的ID"
        assert created_nonexistent_crawler.id == created_via_nonexistent_id
        assert created_nonexistent_crawler.id != 999

    def test_batch_toggle_active(
        self, crawlers_repo, sample_crawlers_data, clean_db
    ):  # 使用 data fixture
        """測試批量切換爬蟲活躍狀態"""
        # 獲取前兩個爬蟲的 ID
        crawler_ids = [c["id"] for c in sample_crawlers_data[:2]]

        # --- 測試批量啟用 ---
        result_enable = crawlers_repo.batch_toggle_active(crawler_ids, True)
        # Commit before verifying state
        crawlers_repo.session.commit()
        crawlers_repo.session.expire_all()

        assert result_enable["success_count"] == 2
        assert result_enable["fail_count"] == 0

        for crawler_id in crawler_ids:
            crawler = crawlers_repo.get_by_id(crawler_id)
            assert (
                crawler.is_active is True
            ), f"Crawler ID {crawler_id} should be active after batch enable"

        # --- 測試批量停用 ---
        result_disable = crawlers_repo.batch_toggle_active(crawler_ids, False)
        # Commit before verifying state
        crawlers_repo.session.commit()
        crawlers_repo.session.expire_all()

        assert result_disable["success_count"] == 2
        assert result_disable["fail_count"] == 0

        for crawler_id in crawler_ids:
            crawler = crawlers_repo.get_by_id(crawler_id)
            assert (
                crawler.is_active is False
            ), f"Crawler ID {crawler_id} should be inactive after batch disable"

        # --- 測試包含不存在的ID ---
        mixed_ids = crawler_ids + [999]
        result_mixed = crawlers_repo.batch_toggle_active(mixed_ids, True)
        # Commit before verifying state (only affects existing IDs)
        crawlers_repo.session.commit()
        crawlers_repo.session.expire_all()

        assert result_mixed["success_count"] == 2
        assert result_mixed["fail_count"] == 1
        assert 999 in result_mixed["failed_ids"]

        for crawler_id in crawler_ids:
            crawler = crawlers_repo.get_by_id(crawler_id)
            assert (
                crawler.is_active is True
            ), f"Crawler ID {crawler_id} should be active after mixed batch enable"

    def test_error_handling(self, crawlers_repo, clean_db):
        """測試錯誤處理"""
        with pytest.raises(DatabaseOperationError) as exc_info:
            crawlers_repo.execute_query(
                lambda: crawlers_repo.session.execute("SELECT * FROM nonexistent_table")
            )
        assert "資料庫操作錯誤" in str(exc_info.value)

    def test_find_by_crawler_id(
        self, crawlers_repo, sample_crawlers_data, clean_db
    ):  # 使用 data fixture
        """測試根據 ID 查找爬蟲"""
        active_crawler_data = next(c for c in sample_crawlers_data if c["is_active"])
        inactive_crawler_data = next(
            c for c in sample_crawlers_data if not c["is_active"]
        )
        active_crawler_id = active_crawler_data["id"]
        inactive_crawler_id = inactive_crawler_data["id"]

        result_active = crawlers_repo.find_by_crawler_id(active_crawler_id)
        assert result_active is not None
        assert isinstance(result_active, Crawlers)
        assert result_active.id == active_crawler_id

        result_active_preview = crawlers_repo.find_by_crawler_id(
            active_crawler_id, is_preview=True, preview_fields=["id"]
        )
        assert result_active_preview is not None
        assert isinstance(result_active_preview, dict)
        assert "id" in result_active_preview

        result_inactive = crawlers_repo.find_by_crawler_id(
            inactive_crawler_id, is_active=False
        )
        assert result_inactive is not None
        assert isinstance(result_inactive, Crawlers)
        assert result_inactive.id == inactive_crawler_id

        result_inactive_as_active = crawlers_repo.find_by_crawler_id(
            inactive_crawler_id, is_active=True
        )
        assert result_inactive_as_active is None

        result_nonexistent = crawlers_repo.find_by_crawler_id(999)
        assert result_nonexistent is None


class TestCrawlersPaginationViaBase:
    """測試爬蟲的分頁功能 (通過 BaseRepository.find_paginated)"""

    def test_pagination(
        self, crawlers_repo, sample_crawlers_data, clean_db
    ):  # 使用 data fixture
        """測試分頁功能"""
        # 添加更多測試數據
        initial_count = len(sample_crawlers_data)
        added_count = 6
        total_expected = initial_count + added_count  # 3 + 6 = 9

        for i in range(added_count):
            new_setting = Crawlers(
                crawler_name=f"額外爬蟲{i+1}",
                module_name="test_module",
                base_url=f"https://example.com/extra{i+1}",
                is_active=True,
                crawler_type="web",
                config_file_name="test_crawler.json",
            )
            crawlers_repo.session.add(new_setting)
        # Commit added data before pagination tests
        crawlers_repo.session.commit()
        crawlers_repo.session.expire_all()

        current_page = 1
        per_page = 3
        total, items_p1 = crawlers_repo.find_paginated(
            page=current_page, per_page=per_page
        )
        total_pages = math.ceil(total / per_page) if per_page > 0 else 1
        has_next = current_page < total_pages
        has_prev = current_page > 1

        assert len(items_p1) == 3
        assert total == total_expected  # 9
        assert total_pages == 3
        assert has_next is True
        assert has_prev is False
        assert isinstance(items_p1[0], Crawlers)

        current_page = 2
        total, items_p2 = crawlers_repo.find_paginated(
            page=current_page, per_page=per_page
        )
        assert len(items_p2) == 3

        current_page = 3
        total, items_p3 = crawlers_repo.find_paginated(
            page=current_page, per_page=per_page
        )
        total_pages = math.ceil(total / per_page) if per_page > 0 else 1
        has_next = current_page < total_pages
        assert len(items_p3) == 3
        assert has_next is False

        total_preview, items_p1_preview = crawlers_repo.find_paginated(
            page=1, per_page=3, is_preview=True, preview_fields=["id"]
        )
        assert len(items_p1_preview) == 3
        assert isinstance(items_p1_preview[0], dict)
        assert "id" in items_p1_preview[0]
        assert "crawler_name" not in items_p1_preview[0]

    def test_pagination_edge_cases(
        self, crawlers_repo, sample_crawlers_data, clean_db
    ):  # 使用 data fixture
        """測試分頁邊界情況"""
        initial_count = len(sample_crawlers_data)

        with pytest.raises(InvalidOperationError):
            crawlers_repo.find_paginated(page=1, per_page=0)

        current_page = 1
        per_page = 3
        total_neg, items_neg = crawlers_repo.find_paginated(page=-1, per_page=per_page)
        total_pages_neg = math.ceil(total_neg / per_page) if per_page > 0 else 1
        has_prev_neg = current_page > 1
        assert len(items_neg) == min(initial_count, per_page)  # 3
        assert total_neg == initial_count  # 3
        assert has_prev_neg is False

        # 清空數據庫以測試空數據集
        crawlers_repo.session.query(Crawlers).delete()
        crawlers_repo.session.commit()
        crawlers_repo.session.expire_all()

        current_page = 1
        per_page = 3
        empty_total, empty_items = crawlers_repo.find_paginated(
            page=current_page, per_page=per_page
        )
        empty_total_pages = math.ceil(empty_total / per_page) if per_page > 0 else 1
        empty_has_next = current_page < empty_total_pages
        empty_has_prev = current_page > 1

        assert empty_total == 0
        assert empty_total_pages == 0
        assert len(empty_items) == 0
        assert empty_has_next is False
        assert empty_has_prev is False

    def test_pagination_sorting(
        self, crawlers_repo, sample_crawlers_data, clean_db
    ):  # 使用 data fixture
        """測試分頁排序功能"""
        initial_count = len(sample_crawlers_data)
        # 預期排序的名字
        expected_names_asc = sorted([c["crawler_name"] for c in sample_crawlers_data])
        expected_names_desc = sorted(
            [c["crawler_name"] for c in sample_crawlers_data], reverse=True
        )

        total_asc, items_asc = crawlers_repo.find_paginated(
            page=1, per_page=10, sort_by="crawler_name", sort_desc=False
        )
        assert total_asc == initial_count
        assert all(isinstance(item, Crawlers) for item in items_asc)
        asc_names = [item.crawler_name for item in items_asc]
        assert asc_names == expected_names_asc  # ["RSS爬蟲", "新聞爬蟲1", "新聞爬蟲2"]

        total_desc, items_desc = crawlers_repo.find_paginated(
            page=1, per_page=10, sort_by="crawler_name", sort_desc=True
        )
        assert total_desc == initial_count
        desc_names = [item.crawler_name for item in items_desc]
        assert (
            desc_names == expected_names_desc
        )  # ["新聞爬蟲2", "新聞爬蟲1", "RSS爬蟲"]

        with pytest.raises(InvalidOperationError) as exc_info:
            crawlers_repo.find_paginated(
                page=1, per_page=10, sort_by="non_existent_field"
            )
        assert "無效的排序欄位" in str(exc_info.value)

    def test_pagination_data_integrity(
        self, crawlers_repo, sample_crawlers_data, clean_db
    ):  # 使用 data fixture
        """測試分頁數據的完整性"""
        all_records_count = crawlers_repo.session.query(Crawlers).count()
        assert all_records_count == len(sample_crawlers_data)  # 確保初始數量正確

        collected_records = []
        page = 1
        per_page = 1  # 使用 per_page = 1 確保能收集所有記錄
        while True:
            total, items = crawlers_repo.find_paginated(page=page, per_page=per_page)
            if not items:  # 如果當前頁沒有項目，則停止
                break
            collected_records.extend(items)
            total_pages = math.ceil(total / per_page) if per_page > 0 else 1
            has_next = page < total_pages
            if not has_next:
                break
            page += 1

        assert len(collected_records) == all_records_count
        record_ids = {r.id for r in collected_records}  # 使用 set 檢查唯一性
        expected_ids = {c["id"] for c in sample_crawlers_data}
        assert record_ids == expected_ids  # 確保收集到的 ID 與 fixture 中的 ID 匹配


class TestCrawlersFilteringAndPaginationViaBase:
    """測試爬蟲的篩選和分頁組合功能 (通過 BaseRepository.find_paginated)"""

    @pytest.fixture(scope="function")
    def filter_test_crawlers_data(
        self, initialized_db_manager, clean_db
    ) -> List[Dict[str, Any]]:  # 返回 Dict
        """創建用於過濾和分頁測試的爬蟲數據，返回字典列表"""
        crawlers_output_data = []
        with initialized_db_manager.session_scope() as session:
            now = datetime.now(timezone.utc)
            crawlers = [
                Crawlers(
                    crawler_name="新聞爬蟲Web1",
                    module_name="test_module",
                    base_url="https://example.com/news1",
                    is_active=True,
                    created_at=(now - timedelta(days=5)),
                    crawler_type="web",
                    config_file_name="news_web1.json",
                ),
                Crawlers(
                    crawler_name="新聞爬蟲Web2",
                    module_name="test_module",
                    base_url="https://example.com/news2",
                    is_active=False,
                    created_at=(now - timedelta(days=3)),
                    crawler_type="web",
                    config_file_name="news_web2.json",
                ),
                Crawlers(
                    crawler_name="RSS爬蟲1",
                    module_name="test_module",
                    base_url="https://example.com/rss1",
                    is_active=True,
                    created_at=(now - timedelta(days=2)),
                    crawler_type="rss",
                    config_file_name="rss1.json",
                ),
                Crawlers(
                    crawler_name="RSS爬蟲2",
                    module_name="test_module",
                    base_url="https://example.com/rss2",
                    is_active=False,
                    created_at=(now - timedelta(days=1)),
                    crawler_type="rss",
                    config_file_name="rss2.json",
                ),
                Crawlers(
                    crawler_name="API爬蟲",
                    module_name="test_module",
                    base_url="https://example.com/api",
                    is_active=True,
                    created_at=now,
                    crawler_type="api",
                    config_file_name="api.json",
                ),
            ]
            session.add_all(crawlers)
            session.flush()  # 分配 ID
            for c in crawlers:
                crawlers_output_data.append(
                    {
                        "id": c.id,
                        "crawler_name": c.crawler_name,
                        "base_url": c.base_url,
                        "is_active": c.is_active,
                        "crawler_type": c.crawler_type,
                        "created_at": c.created_at,
                    }
                )
            session.commit()

        return crawlers_output_data

    # 使用 filter_test_crawlers_data fixture
    def test_combined_filters_with_pagination(
        self, crawlers_repo, filter_test_crawlers_data, clean_db
    ):
        """測試組合多種過濾條件並進行分頁"""
        initial_count = len(filter_test_crawlers_data)  # 5

        filter_dict_1 = {"is_active": True, "crawler_type": "web"}
        total_1, items_1 = crawlers_repo.find_paginated(
            filter_criteria=filter_dict_1, page=1, per_page=10
        )
        # 計算預期數量
        expected_count_1 = sum(
            1
            for c in filter_test_crawlers_data
            if c["is_active"] and c["crawler_type"] == "web"
        )
        assert total_1 == expected_count_1  # 1
        assert len(items_1) == expected_count_1
        assert items_1[0].crawler_name == "新聞爬蟲Web1"

        filter_dict_2 = {"crawler_type": {"$in": ["web", "rss"]}}
        total_2, items_2 = crawlers_repo.find_paginated(
            filter_criteria=filter_dict_2, page=1, per_page=10
        )
        expected_count_2 = sum(
            1 for c in filter_test_crawlers_data if c["crawler_type"] in ["web", "rss"]
        )
        assert total_2 == expected_count_2  # 4
        assert len(items_2) == expected_count_2

        two_days_ago = datetime.now(timezone.utc) - timedelta(days=2, hours=1)
        filter_dict_3 = {"created_at": {"$gte": two_days_ago}}
        total_3, items_3 = crawlers_repo.find_paginated(
            filter_criteria=filter_dict_3,
            page=1,
            per_page=10,
            sort_by="created_at",
            sort_desc=False,
        )
        expected_count_3 = sum(
            1 for c in filter_test_crawlers_data if c["created_at"] >= two_days_ago
        )
        assert total_3 == expected_count_3  # 3
        assert len(items_3) == expected_count_3
        assert items_3[0].crawler_name == "RSS爬蟲1"  # 最早創建的，但 >= two_days_ago

        filter_dict_4 = {"is_active": False, "crawler_type": "rss"}
        total_4, items_4 = crawlers_repo.find_paginated(
            filter_criteria=filter_dict_4, page=1, per_page=10
        )
        expected_count_4 = sum(
            1
            for c in filter_test_crawlers_data
            if not c["is_active"] and c["crawler_type"] == "rss"
        )
        assert total_4 == expected_count_4  # 1
        assert len(items_4) == expected_count_4
        assert items_4[0].crawler_name == "RSS爬蟲2"

        filter_dict_5 = {"crawler_type": {"$ne": "api"}}
        total_5, items_5 = crawlers_repo.find_paginated(
            filter_criteria=filter_dict_5, page=1, per_page=10
        )
        expected_count_5 = sum(
            1 for c in filter_test_crawlers_data if c["crawler_type"] != "api"
        )
        assert total_5 == expected_count_5  # 4

        current_page_empty = 1
        per_page_empty = 3
        total_empty, items_empty = crawlers_repo.find_paginated(
            filter_criteria={}, page=current_page_empty, per_page=per_page_empty
        )
        total_pages_empty = (
            math.ceil(total_empty / per_page_empty) if per_page_empty > 0 else 1
        )
        has_next_empty = current_page_empty < total_pages_empty
        assert total_empty == initial_count  # 5
        assert len(items_empty) == 3
        assert has_next_empty is True

        filter_dict_invalid = {"is_active": True, "invalid_key": "some_value"}
        total_invalid, items_invalid = crawlers_repo.find_paginated(
            filter_criteria=filter_dict_invalid, page=1, per_page=10
        )
        expected_count_invalid = sum(
            1 for c in filter_test_crawlers_data if c["is_active"]
        )  # 只看 is_active
        assert total_invalid == expected_count_invalid  # 3
        assert len(items_invalid) == expected_count_invalid

    # 使用 filter_test_crawlers_data fixture
    def test_pagination_with_sorting(
        self, crawlers_repo, filter_test_crawlers_data, clean_db
    ):
        """測試分頁排序與過濾結合"""
        filter_dict = {"is_active": True}
        total_asc, items_asc = crawlers_repo.find_paginated(
            filter_criteria=filter_dict,
            page=1,
            per_page=10,
            sort_by="created_at",
            sort_desc=False,
        )
        expected_count_active = sum(
            1 for c in filter_test_crawlers_data if c["is_active"]
        )
        assert total_asc == expected_count_active  # 3
        created_times_asc = [item.created_at for item in items_asc]
        assert created_times_asc == sorted(created_times_asc)
        # 找到活躍爬蟲中最早創建的 name
        expected_first_active = min(
            (c for c in filter_test_crawlers_data if c["is_active"]),
            key=lambda x: x["created_at"],
        )
        assert (
            items_asc[0].crawler_name == expected_first_active["crawler_name"]
        )  # "新聞爬蟲Web1"

        total_desc, items_desc = crawlers_repo.find_paginated(
            filter_criteria=filter_dict,
            page=1,
            per_page=10,
            sort_by="created_at",
            sort_desc=True,
        )
        assert total_desc == expected_count_active  # 3
        created_times_desc = [item.created_at for item in items_desc]
        assert created_times_desc == sorted(created_times_desc, reverse=True)
        # 找到活躍爬蟲中最晚創建的 name
        expected_last_active = max(
            (c for c in filter_test_crawlers_data if c["is_active"]),
            key=lambda x: x["created_at"],
        )
        assert (
            items_desc[0].crawler_name == expected_last_active["crawler_name"]
        )  # "API爬蟲"

        filter_dict_names = {"crawler_type": {"$in": ["web", "rss"]}}
        total_name_asc, items_name_asc = crawlers_repo.find_paginated(
            filter_criteria=filter_dict_names,
            page=1,
            per_page=10,
            sort_by="crawler_name",
            sort_desc=False,
        )
        expected_count_web_rss = sum(
            1 for c in filter_test_crawlers_data if c["crawler_type"] in ["web", "rss"]
        )
        assert total_name_asc == expected_count_web_rss  # 4
        names_asc = [item.crawler_name for item in items_name_asc]
        # 預期排序後的名稱
        expected_sorted_names = sorted(
            [
                c["crawler_name"]
                for c in filter_test_crawlers_data
                if c["crawler_type"] in ["web", "rss"]
            ]
        )
        assert (
            names_asc == expected_sorted_names
        )  # ["RSS爬蟲1", "RSS爬蟲2", "新聞爬蟲Web1", "新聞爬蟲Web2"]
