import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.crawlers_model import Crawlers
from src.database.crawlers_repository import CrawlersRepository, SchemaType
from src.models.base_model import Base
from src.error.errors import ValidationError, DatabaseOperationError, InvalidOperationError
from typing import Union, Dict, Any, List # 引入 Union, Dict, Any, List

# 設置測試資料庫，使用 session scope
@pytest.fixture(scope="session")
def engine():
    return create_engine('sqlite:///:memory:')

@pytest.fixture(scope="session")
def tables(engine):
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="session")
def session_factory(engine):
    """創建會話工廠"""
    return sessionmaker(bind=engine)

@pytest.fixture(scope="function")
def session(session_factory, tables):
    """為每個測試函數創建新的會話"""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture(scope="function")
def crawlers_repo(session):
    return CrawlersRepository(session, Crawlers)

@pytest.fixture(scope="function")
def clean_db(session):
    """清空資料庫的 fixture"""
    session.query(Crawlers).delete()
    session.commit()
    session.expire_all()

@pytest.fixture(scope="function")
def sample_crawlers(session, clean_db):
    """建立測試用的爬蟲資料"""
    now = datetime.now(timezone.utc)
    
    crawlers = [
        Crawlers(
            crawler_name="新聞爬蟲1",
            base_url="https://example.com/news1",
            is_active=True,
            created_at=(now - timedelta(days=1)),
            crawler_type="web",
            config_file_name="test_crawler.json"
        ),
        Crawlers(
            crawler_name="新聞爬蟲2",
            base_url="https://example.com/news2",
            is_active=False,
            crawler_type="web",
            config_file_name="test_crawler.json"
        ),
        Crawlers(
            crawler_name="RSS爬蟲",
            base_url="https://example.com/rss",
            is_active=True,
            crawler_type="rss",
            config_file_name="test_crawler.json"
        )
    ]
    session.add_all(crawlers)
    session.commit()
    
    # 確保所有物件都有正確的 ID
    session.expire_all()
    return crawlers

# CrawlersRepository 測試
class TestCrawlersRepository:
    """測試 Crawlers 相關資料庫操作"""
    
    def test_get_schema_class(self, crawlers_repo, clean_db):
        """測試獲取正確的 schema 類別"""
        from src.models.crawlers_schema import CrawlersCreateSchema, CrawlersUpdateSchema
        
        # 測試默認返回
        schema = crawlers_repo.get_schema_class()
        assert schema == CrawlersCreateSchema
        
        # 測試指定類型返回
        create_schema = crawlers_repo.get_schema_class(SchemaType.CREATE)
        assert create_schema == CrawlersCreateSchema
        
        update_schema = crawlers_repo.get_schema_class(SchemaType.UPDATE)
        assert update_schema == CrawlersUpdateSchema
        
        # 測試 LIST 和 DETAIL schema
        with pytest.raises(ValueError) as exc_info:
            crawlers_repo.get_schema_class(SchemaType.LIST)
        assert "未支援的 schema 類型" in str(exc_info.value)
    
    # 新增測試 validate_data 方法
    def test_validate_data(self, crawlers_repo, clean_db):
        """測試 validate_data 方法"""
        # 準備測試資料
        crawler_data = {
            "crawler_name": "測試驗證爬蟲",
            "base_url": "https://example.com/validate",
            "is_active": True,
            "crawler_type": "web",
            "config_file_name": "test_crawler.json"
        }
        
        # 測試 CREATE 驗證
        validated_create = crawlers_repo.validate_data(crawler_data, SchemaType.CREATE)
        assert validated_create is not None
        assert validated_create["crawler_name"] == "測試驗證爬蟲"
        assert validated_create["base_url"] == "https://example.com/validate"
        
        # 測試 UPDATE 驗證 (僅包含更新的欄位)
        update_data = {"crawler_name": "更新的爬蟲名稱", "is_active": False}
        validated_update = crawlers_repo.validate_data(update_data, SchemaType.UPDATE)
        assert validated_update is not None
        assert validated_update["crawler_name"] == "更新的爬蟲名稱"
        assert validated_update["is_active"] is False
        assert "base_url" not in validated_update  # UPDATE 應該只包含傳入的欄位
        
        # 測試驗證錯誤 (缺少必填欄位)
        invalid_data = {
            "crawler_name": "缺失欄位爬蟲"
            # 缺少 base_url
        }
        
        with pytest.raises(ValidationError) as excinfo:
            crawlers_repo.validate_data(invalid_data, SchemaType.CREATE)
        
        assert "以下必填欄位缺失或值為空/空白" in str(excinfo.value)
    
    def test_find_all(self, crawlers_repo, sample_crawlers, session, clean_db):
        """測試獲取所有爬蟲設定 (使用 find_all)"""
        # 使用基類的 find_all
        settings = crawlers_repo.find_all()
        assert len(settings) == 3
        assert isinstance(settings[0], Crawlers)

        # 測試 find_all 的 limit 和 offset
        settings_limit = crawlers_repo.find_all(limit=1)
        assert len(settings_limit) == 1

        settings_offset = crawlers_repo.find_all(limit=1, offset=1)
        assert len(settings_offset) == 1
        # 假設預設排序，檢查 ID 是否不同
        assert settings_limit[0].id != settings_offset[0].id

        # 測試 find_all 的預覽模式
        preview_settings = crawlers_repo.find_all(is_preview=True, preview_fields=["id", "crawler_name"])
        assert len(preview_settings) == 3
        assert isinstance(preview_settings[0], dict)
        assert "id" in preview_settings[0]
        assert "crawler_name" in preview_settings[0]
        assert "base_url" not in preview_settings[0]

    def test_get_by_id(self, crawlers_repo, sample_crawlers, session, clean_db):
        """測試通過ID獲取爬蟲設定"""
        # 測試存在的ID (返回實例)
        setting = crawlers_repo.get_by_id(sample_crawlers[0].id)
        assert setting is not None
        assert isinstance(setting, Crawlers)
        assert setting.id == sample_crawlers[0].id

        # 測試不存在的ID
        setting_nonexistent = crawlers_repo.get_by_id(999)
        assert setting_nonexistent is None

    def test_find_by_crawler_name(self, crawlers_repo, sample_crawlers, session, clean_db):
        """測試根據爬蟲名稱模糊查詢 (包含活躍狀態過濾、分頁、預覽)"""
        # 活躍查詢 (預設 is_active=None)
        crawlers_all = crawlers_repo.find_by_crawler_name("爬蟲")
        assert len(crawlers_all) == 3
        assert isinstance(crawlers_all[0], Crawlers)

        # 指定 is_active=True
        crawlers_active = crawlers_repo.find_by_crawler_name("爬蟲", is_active=True)
        assert len(crawlers_active) == 2

        # 指定 is_active=False
        crawlers_inactive = crawlers_repo.find_by_crawler_name("爬蟲", is_active=False)
        assert len(crawlers_inactive) == 1
        assert crawlers_inactive[0].crawler_name == "新聞爬蟲2"

        # 測試 limit
        crawlers_limit = crawlers_repo.find_by_crawler_name("爬蟲", limit=1)
        assert len(crawlers_limit) == 1

        # 測試 offset
        crawlers_offset = crawlers_repo.find_by_crawler_name("爬蟲", limit=1, offset=1)
        assert len(crawlers_offset) == 1
        assert crawlers_limit[0].id != crawlers_offset[0].id # 假設 ID 不同

        # 測試 is_preview
        crawlers_preview = crawlers_repo.find_by_crawler_name("爬蟲", is_preview=True, preview_fields=["id", "crawler_name"])
        assert len(crawlers_preview) == 3
        assert isinstance(crawlers_preview[0], dict)
        assert "id" in crawlers_preview[0]
        assert "crawler_name" in crawlers_preview[0]
        assert "base_url" not in crawlers_preview[0]

        # 測試無效預覽欄位
        crawlers_preview_invalid = crawlers_repo.find_by_crawler_name("爬蟲", is_preview=True, preview_fields=["invalid_field"])
        assert len(crawlers_preview_invalid) == 3
        assert isinstance(crawlers_preview_invalid[0], Crawlers) # 應回退到返回完整物件

    def test_find_by_crawler_name_exact(self, crawlers_repo, sample_crawlers, session, clean_db):
        """測試根據爬蟲名稱精確查詢 (包含預覽)"""
        target_name = "新聞爬蟲1"
        target_id = sample_crawlers[0].id

        # 完全匹配 (返回實例)
        crawler_instance = crawlers_repo.find_by_crawler_name_exact(target_name)
        assert crawler_instance is not None
        assert isinstance(crawler_instance, Crawlers)
        assert crawler_instance.crawler_name == target_name
        assert crawler_instance.id == target_id

        # 測試預覽模式
        crawler_preview = crawlers_repo.find_by_crawler_name_exact(target_name, is_preview=True, preview_fields=["id"])
        assert crawler_preview is not None
        assert isinstance(crawler_preview, dict)
        assert crawler_preview["id"] == target_id
        assert "crawler_name" not in crawler_preview

        # 不存在的名稱
        crawler_nonexistent = crawlers_repo.find_by_crawler_name_exact("不存在的爬蟲")
        assert crawler_nonexistent is None

    def test_find_active_crawlers(self, crawlers_repo, sample_crawlers, session, clean_db):
        """測試查詢活動中的爬蟲 (包含分頁、預覽)"""
        # 基礎查詢
        active_crawlers = crawlers_repo.find_active_crawlers()
        assert len(active_crawlers) == 2
        assert all(isinstance(c, Crawlers) and c.is_active for c in active_crawlers)

        # 測試 limit
        active_limit = crawlers_repo.find_active_crawlers(limit=1)
        assert len(active_limit) == 1

        # 測試 offset
        active_offset = crawlers_repo.find_active_crawlers(limit=1, offset=1)
        assert len(active_offset) == 1
        assert active_limit[0].id != active_offset[0].id

        # 測試預覽
        active_preview = crawlers_repo.find_active_crawlers(is_preview=True, preview_fields=["crawler_name"])
        assert len(active_preview) == 2
        assert isinstance(active_preview[0], dict)
        assert "crawler_name" in active_preview[0]
        assert "id" not in active_preview[0]

    def test_create(self, crawlers_repo, session, clean_db):
        """測試使用模式驗證創建爬蟲"""
        new_crawler_data_defaults = {
            "crawler_name": "測試預設值爬蟲",
            "base_url": "https://example.com/defaults",
            "crawler_type": "web",
            "config_file_name": "test_crawler.json"
            # is_active 未提供，應為 True
        }
        new_crawler_defaults = crawlers_repo.create(new_crawler_data_defaults)
        session.commit()
        session.expire_all()

        # 重新獲取以驗證
        created_default = crawlers_repo.get_by_id(new_crawler_defaults.id)
        assert created_default is not None
        assert created_default.is_active is True # 檢查預設值

        new_crawler_data_explicit = {
            "crawler_name": "測試明確狀態爬蟲",
            "base_url": "https://example.com/explicit",
            "is_active": False, # 明確設置為 False
            "crawler_type": "web",
            "config_file_name": "test_crawler.json"
        }
        new_crawler_explicit = crawlers_repo.create(new_crawler_data_explicit)
        session.commit()
        session.expire_all()

        # 重新獲取以驗證
        created_explicit = crawlers_repo.get_by_id(new_crawler_explicit.id)
        assert created_explicit is not None
        assert created_explicit.is_active is False # 檢查設置值

        # ... 原有的驗證錯誤測試 ...
        invalid_data = {
            "crawler_name": "缺失欄位爬蟲",
            "is_active": True
        }
        with pytest.raises(ValidationError):
            crawlers_repo.create(invalid_data)
        # 驗證錯誤不需要 commit，隱含 rollback

    def test_crawler_name_uniqueness(self, crawlers_repo, sample_crawlers, session, clean_db):
        """測試爬蟲名稱唯一性驗證"""
        # 嘗試創建重複名稱的爬蟲
        duplicate_data = {
            "crawler_name": "新聞爬蟲1",  # 已存在的名稱
            "base_url": "https://example.com/duplicate",
            "is_active": True,
            "crawler_type": "web",
            "config_file_name": "test_crawler.json"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            crawlers_repo.create(duplicate_data)
        assert "爬蟲名稱" in str(exc_info.value)
        assert "已存在" in str(exc_info.value)
    
        # 嘗試更新為重複名稱
        with pytest.raises(ValidationError) as exc_info:
            crawlers_repo.update(sample_crawlers[1].id, {"crawler_name": "新聞爬蟲1"})
        assert "爬蟲名稱" in str(exc_info.value)
        assert "已存在" in str(exc_info.value)
    
    def test_update(self, crawlers_repo, sample_crawlers, session, clean_db):
        """測試使用模式驗證更新爬蟲"""
        # 獲取第一個爬蟲設定的ID
        setting_id = sample_crawlers[0].id
        original_base_url = sample_crawlers[0].base_url # 保存原始值以便後續驗證
        original_crawler_type = sample_crawlers[0].crawler_type

        # 準備更新數據
        update_data = {
            "crawler_name": "已更新爬蟲名稱",
            "is_active": False
        }

        # 執行更新 (假設 repo.update 只修改 session 中的物件)
        updated_in_session = crawlers_repo.update(setting_id, update_data)

        # 模擬 Service 層的行為: 提交交易
        session.commit()

        # 清除 session 快取，強制從資料庫重新載入以驗證持久化
        session.expire_all()

        # 重新獲取或直接使用 updated_in_session (因為 expire 會觸發重新載入)
        updated_from_db = crawlers_repo.get_by_id(setting_id)

        assert updated_from_db is not None
        # 現在斷言應該會成功，因為變更已提交
        assert updated_from_db.crawler_name == "已更新爬蟲名稱"
        assert updated_from_db.is_active is False
        assert updated_from_db.updated_at is not None # 確保 updated_at 被設置

        # 確認只更新了指定欄位
        assert updated_from_db.base_url == original_base_url
        assert updated_from_db.crawler_type == original_crawler_type

        # --- 測試更新不存在的ID ---
        result_nonexistent = crawlers_repo.update(999, update_data)
        # 這裡也需要 commit 嗎？取決於 update 找不到 ID 時的行為。
        # 如果 update 在找不到時直接返回 None 且不做任何操作，則不需要 commit。
        # 如果 update 內部有其他可能影響 session 的操作（即使找不到 ID），則可能需要 commit 或 rollback。
        # 假設找不到時直接返回 None，所以不需要額外 commit/rollback。
        assert result_nonexistent is None

        # --- 測試嘗試更新不允許的欄位 ---
        invalid_update = {
            "crawler_name": "測試非法更新",
            "crawler_type": "changed_type"  # 不允許更新類型
        }

        # 驗證 ValidationError 的測試不需要 commit，因為預期會引發異常，
        # SQLAlchemy 的 session 在異常時通常會自動 rollback (或應在 repo 的錯誤處理中 rollback)。
        with pytest.raises(ValidationError):
            crawlers_repo.update(setting_id, invalid_update)

        # 可以選擇性地驗證 rollback 後的狀態
        session.rollback() # 確保 session 狀態乾淨
        reverted_crawler = crawlers_repo.get_by_id(setting_id)
        assert reverted_crawler.crawler_name == "已更新爬蟲名稱" # 名稱應保持上次成功提交的狀態
        assert reverted_crawler.crawler_type == original_crawler_type # 類型不應改變
    
    def test_delete(self, crawlers_repo, sample_crawlers, session, clean_db):
        """測試刪除爬蟲設定"""
        # 獲取最後一個爬蟲設定的ID
        setting_id = sample_crawlers[-1].id
        
        # 執行刪除
        result = crawlers_repo.delete(setting_id)
        session.commit()
        assert result is True
        
        # 確認已從資料庫中刪除
        deleted = crawlers_repo.get_by_id(setting_id)
        assert deleted is None
        
        # 測試刪除不存在的ID
        result = crawlers_repo.delete(999)
        assert result is False

    def test_toggle_active_status(self, crawlers_repo, sample_crawlers, session, clean_db):
        """測試切換爬蟲活躍狀態"""
        crawler_id = sample_crawlers[0].id
        original_status = sample_crawlers[0].is_active
        
        result_toggle1 = crawlers_repo.toggle_active_status(crawler_id)
        session.commit()
        assert result_toggle1 is True
        
        # 清除快取並重新獲取
        session.expire_all()
        updated_crawler = crawlers_repo.get_by_id(crawler_id)
        assert updated_crawler is not None
        assert updated_crawler.is_active != original_status
        assert updated_crawler.updated_at is not None
        
        # 再次切換
        result_toggle2 = crawlers_repo.toggle_active_status(crawler_id)
        session.commit()
        assert result_toggle2 is True

        # 清除快取並重新獲取
        session.expire_all()
        updated_again = crawlers_repo.get_by_id(crawler_id)
        assert updated_again is not None
        assert updated_again.is_active == original_status
        
        # 測試切換不存在的ID
        result_toggle_nonexistent = crawlers_repo.toggle_active_status(999)
        assert result_toggle_nonexistent is False

    def test_find_by_type(self, crawlers_repo, sample_crawlers, session, clean_db):
        """測試根據爬蟲類型查找 (包含活躍狀態過濾、分頁、預覽)"""
        # 活躍查詢 (預設 is_active=True)
        web_crawlers_active = crawlers_repo.find_by_type("web", is_active=True)
        assert len(web_crawlers_active) == 1
        assert isinstance(web_crawlers_active[0], Crawlers)

        # 指定 is_active=False
        web_crawlers_inactive = crawlers_repo.find_by_type("web", is_active=False)
        assert len(web_crawlers_inactive) == 1

        # 測試 limit
        web_limit = crawlers_repo.find_by_type("web", is_active=None, limit=1) # 查找所有 web 類型，限制1個
        assert len(web_limit) == 1

        # 測試 offset
        web_offset = crawlers_repo.find_by_type("web", is_active=None, limit=1, offset=1)
        assert len(web_offset) == 1
        assert web_limit[0].id != web_offset[0].id

        # 測試預覽
        web_preview = crawlers_repo.find_by_type("web", is_active=None, is_preview=True, preview_fields=["is_active"])
        assert len(web_preview) == 2
        assert isinstance(web_preview[0], dict)
        assert "is_active" in web_preview[0]

        # 測試不存在的類型
        non_existent_type = crawlers_repo.find_by_type("api")
        # find_by_filter 返回空列表
        assert isinstance(non_existent_type, list)
        assert len(non_existent_type) == 0

    def test_find_by_target(self, crawlers_repo, sample_crawlers, session, clean_db):
        """測試根據爬取目標查詢 (包含活躍狀態過濾、分頁、預覽)"""
        # 活躍查詢 (預設 is_active=True)
        news_crawlers_active = crawlers_repo.find_by_target("news", is_active=True)
        assert len(news_crawlers_active) == 1
        assert isinstance(news_crawlers_active[0], Crawlers)

        # 指定 is_active=False
        news_crawlers_inactive = crawlers_repo.find_by_target("news", is_active=False)
        assert len(news_crawlers_inactive) == 1

        # 測試 limit
        news_limit = crawlers_repo.find_by_target("news", is_active=None, limit=1)
        assert len(news_limit) == 1

        # 測試 offset
        news_offset = crawlers_repo.find_by_target("news", is_active=None, limit=1, offset=1)
        assert len(news_offset) == 1
        assert news_limit[0].id != news_offset[0].id

        # 測試預覽
        news_preview = crawlers_repo.find_by_target("news", is_active=None, is_preview=True, preview_fields=["base_url"])
        assert len(news_preview) == 2
        assert isinstance(news_preview[0], dict)
        assert "base_url" in news_preview[0]

    def test_get_crawler_statistics(self, crawlers_repo, sample_crawlers, session, clean_db):
        """測試獲取爬蟲統計資訊"""
        stats = crawlers_repo.get_crawler_statistics()
        
        assert stats["total"] == 3
        assert stats["active"] == 2
        assert stats["inactive"] == 1
        assert stats["by_type"]["web"] == 2
        assert stats["by_type"]["rss"] == 1

    def test_create_or_update(self, crawlers_repo, sample_crawlers, session, clean_db):
        """測試創建或更新功能"""
        # --- 測試更新現有記錄 ---
        existing_id = sample_crawlers[0].id
        update_data = {
            "id": existing_id,
            "crawler_name": "更新通過create_or_update",
        }

        result_update = crawlers_repo.create_or_update(update_data)
        session.commit()
        session.expire_all()

        # 重新獲取以確保是從 DB 讀取
        updated_crawler = crawlers_repo.get_by_id(existing_id)

        assert updated_crawler is not None
        assert updated_crawler.id == existing_id
        assert updated_crawler.crawler_name == "更新通過create_or_update"

        # --- 測試創建新記錄 ---
        new_data = {
            "crawler_name": "新記錄通過create_or_update",
            "base_url": "https://example.com/new",
            "crawler_type": "api",
            "config_file_name": "test_crawler.json"
        }

        result_create = crawlers_repo.create_or_update(new_data)
        # 先 commit 以分配 ID
        session.commit()
        # 現在 ID 應該可用了
        new_id = result_create.id
        assert new_id is not None # 可以加個斷言確保 ID 不是 None

        session.expire_all()

        # 重新獲取
        created_crawler = crawlers_repo.get_by_id(new_id)

        assert created_crawler is not None # 現在應該成功了
        assert created_crawler.id == new_id
        assert created_crawler.crawler_name == "新記錄通過create_or_update"
        assert created_crawler.crawler_type == "api"

        # --- 測試ID不存在的情況 (應觸發創建) ---
        nonexistent_id_data = {
            "id": 999, # 提供一個不存在的 ID
            "crawler_name": "不存在的ID",
            "base_url": "https://example.com/nonexistent",
            "crawler_type": "web",
            "config_file_name": "test_crawler.json"
        }

        # create_or_update 內部 update 會失敗返回 None，接著調用 create
        result_nonexistent = crawlers_repo.create_or_update(nonexistent_id_data)
        # 先 commit 以分配 ID
        session.commit()
        # 現在 ID 應該可用了
        created_via_nonexistent_id = result_nonexistent.id
        assert created_via_nonexistent_id is not None # 確保 ID 不是 None

        session.expire_all()

        # 重新獲取
        created_nonexistent_crawler = crawlers_repo.get_by_id(created_via_nonexistent_id)

        assert created_nonexistent_crawler is not None # 現在應該成功了
        assert created_nonexistent_crawler.crawler_name == "不存在的ID"
        assert created_nonexistent_crawler.id == created_via_nonexistent_id
        assert created_nonexistent_crawler.id != 999 # 確保創建了新記錄，ID 不是 999

    def test_batch_toggle_active(self, crawlers_repo, sample_crawlers, session, clean_db):
        """測試批量切換爬蟲活躍狀態"""
        # 獲取樣本爬蟲的ID (新聞爬蟲1 - True, 新聞爬蟲2 - False)
        crawler_ids = [c.id for c in sample_crawlers[:2]]
        
        # --- 測試批量啟用 ---
        # 預期: 兩個都變成 True
        result_enable = crawlers_repo.batch_toggle_active(crawler_ids, True)
        session.commit()
        session.expire_all()
        
        assert result_enable["success_count"] == 2
        assert result_enable["fail_count"] == 0
        
        # 驗證狀態已更新
        for crawler_id in crawler_ids:
            crawler = crawlers_repo.get_by_id(crawler_id)
            assert crawler.is_active is True, f"Crawler ID {crawler_id} should be active after batch enable"
        
        # --- 測試批量停用 ---
        # 預期: 兩個都變成 False
        result_disable = crawlers_repo.batch_toggle_active(crawler_ids, False)
        session.commit()
        session.expire_all()
        
        assert result_disable["success_count"] == 2
        assert result_disable["fail_count"] == 0

        # 驗證狀態已更新
        for crawler_id in crawler_ids:
            crawler = crawlers_repo.get_by_id(crawler_id)
            assert crawler.is_active is False, f"Crawler ID {crawler_id} should be inactive after batch disable"
        
        # --- 測試包含不存在的ID ---
        # 預期: 前兩個變 True，ID 999 失敗
        mixed_ids = crawler_ids + [999]
        result_mixed = crawlers_repo.batch_toggle_active(mixed_ids, True)
        session.commit()
        session.expire_all()

        assert result_mixed["success_count"] == 2
        assert result_mixed["fail_count"] == 1
        assert 999 in result_mixed["failed_ids"]

        # 驗證狀態 (前兩個應該是 True)
        for crawler_id in crawler_ids:
             crawler = crawlers_repo.get_by_id(crawler_id)
             assert crawler.is_active is True, f"Crawler ID {crawler_id} should be active after mixed batch enable"

    def test_error_handling(self, crawlers_repo, session, clean_db):
        """測試錯誤處理"""
        # 測試資料庫操作錯誤
        with pytest.raises(DatabaseOperationError) as exc_info:
            crawlers_repo.execute_query(
                lambda: session.execute("SELECT * FROM nonexistent_table")
            )
        assert "資料庫操作錯誤" in str(exc_info.value)

    def test_find_by_crawler_id(self, crawlers_repo, sample_crawlers, session, clean_db):
        """測試根據 ID 查找爬蟲 (包含活躍狀態過濾、預覽)"""
        active_crawler = sample_crawlers[0] # is_active=True
        inactive_crawler = sample_crawlers[1] # is_active=False

        # 測試查找活躍的 (返回實例)
        result_active = crawlers_repo.find_by_crawler_id(active_crawler.id)
        assert result_active is not None
        assert isinstance(result_active, Crawlers)
        assert result_active.id == active_crawler.id

        # 測試預覽模式
        result_active_preview = crawlers_repo.find_by_crawler_id(active_crawler.id, is_preview=True, preview_fields=["id"])
        assert result_active_preview is not None
        assert isinstance(result_active_preview, dict)
        assert "id" in result_active_preview

        # 測試查找不活躍的，使用 is_active=False (返回實例)
        result_inactive = crawlers_repo.find_by_crawler_id(inactive_crawler.id, is_active=False)
        assert result_inactive is not None
        assert isinstance(result_inactive, Crawlers)
        assert result_inactive.id == inactive_crawler.id

        # 測試查找不活躍的，使用 is_active=True (預期找不到)
        result_inactive_as_active = crawlers_repo.find_by_crawler_id(inactive_crawler.id, is_active=True)
        assert result_inactive_as_active is None

        # 測試不存在的 ID
        result_nonexistent = crawlers_repo.find_by_crawler_id(999)
        assert result_nonexistent is None

# --- 修改分頁測試類，使用 find_paginated ---
class TestCrawlersPaginationViaBase:
    """測試爬蟲的分頁功能 (通過 BaseRepository.find_paginated)"""

    def test_pagination(self, crawlers_repo, sample_crawlers, session, clean_db):
        """測試分頁功能"""
        # 添加更多測試數據
        for i in range(6):
            new_setting = Crawlers(
                crawler_name=f"額外爬蟲{i+1}",
                base_url=f"https://example.com/extra{i+1}",
                is_active=True,
                crawler_type="web",
                config_file_name="test_crawler.json"
            )
            crawlers_repo.session.add(new_setting)
        crawlers_repo.session.commit()
        session.expire_all()

        # 使用 find_paginated
        page1 = crawlers_repo.find_paginated(page=1, per_page=3)
        assert page1["page"] == 1
        assert page1["per_page"] == 3
        assert len(page1["items"]) == 3
        assert page1["total"] == 9
        assert page1["total_pages"] == 3
        assert page1["has_next"] is True
        assert page1["has_prev"] is False
        assert isinstance(page1["items"][0], Crawlers) # 預設返回實例

        page2 = crawlers_repo.find_paginated(page=2, per_page=3)
        assert page2["page"] == 2
        assert len(page2["items"]) == 3

        page3 = crawlers_repo.find_paginated(page=3, per_page=3)
        assert page3["page"] == 3
        assert len(page3["items"]) == 3
        assert page3["has_next"] is False

        # 測試預覽模式
        page1_preview = crawlers_repo.find_paginated(page=1, per_page=3, is_preview=True, preview_fields=["id"])
        assert len(page1_preview["items"]) == 3
        assert isinstance(page1_preview["items"][0], dict)
        assert "id" in page1_preview["items"][0]
        assert "crawler_name" not in page1_preview["items"][0]


    def test_pagination_edge_cases(self, crawlers_repo, sample_crawlers, session, clean_db):
        """測試分頁邊界情況"""
        # 測試每頁大小為0 (由基類處理)
        with pytest.raises(InvalidOperationError):
            crawlers_repo.find_paginated(page=1, per_page=0)

        # 測試負數頁碼 (由基類處理)
        page_neg = crawlers_repo.find_paginated(page=-1, per_page=3)
        assert page_neg["page"] == 1

        # 測試空數據集的分頁
        crawlers_repo.session.query(Crawlers).delete()
        crawlers_repo.session.commit()
        session.expire_all()

        empty_page = crawlers_repo.find_paginated(page=1, per_page=3)
        assert empty_page["total"] == 0
        assert empty_page["total_pages"] == 1 # 基類實現中，total=0時 total_pages 為 1
        assert len(empty_page["items"]) == 0
        assert empty_page["has_next"] is False
        assert empty_page["has_prev"] is False

    def test_pagination_sorting(self, crawlers_repo, sample_crawlers, session, clean_db):
        """測試分頁排序功能"""
        # 測試升序排序
        asc_page = crawlers_repo.find_paginated(
            page=1,
            per_page=10,
            sort_by="crawler_name",
            sort_desc=False
        )
        # 確保返回的是實例列表
        assert all(isinstance(item, Crawlers) for item in asc_page["items"])
        asc_names = [item.crawler_name for item in asc_page["items"]]
        assert asc_names == sorted(asc_names)

        # 測試降序排序
        desc_page = crawlers_repo.find_paginated(
            page=1,
            per_page=10,
            sort_by="crawler_name",
            sort_desc=True
        )
        desc_names = [item.crawler_name for item in desc_page["items"]]
        assert desc_names == sorted(desc_names, reverse=True)

        # 測試無效的排序欄位 (由基類處理)
        with pytest.raises(DatabaseOperationError) as exc_info: # 基類拋出 DatabaseOperationError
            crawlers_repo.find_paginated(
                page=1,
                per_page=10,
                sort_by="non_existent_field"
            )
        assert "無效的排序欄位" in str(exc_info.value)

    def test_pagination_data_integrity(self, crawlers_repo, sample_crawlers, session, clean_db):
        """測試分頁數據的完整性"""
        # find_all 現在也支援分頁，但為了明確測試 find_paginated，我們手動收集
        all_records_count = crawlers_repo.session.query(Crawlers).count()

        collected_records = []
        page = 1
        while True:
            page_data = crawlers_repo.find_paginated(page=page, per_page=3)
            collected_records.extend(page_data["items"])
            if not page_data["has_next"]:
                break
            page += 1

        assert len(collected_records) == all_records_count
        record_ids = [r.id for r in collected_records]
        assert len(record_ids) == len(set(record_ids))


# --- 修改篩選與分頁組合測試類，使用 find_paginated ---
class TestCrawlersFilteringAndPaginationViaBase:
    """測試爬蟲的篩選和分頁組合功能 (通過 BaseRepository.find_paginated)"""

    @pytest.fixture(scope="function")
    def filter_test_crawlers(self, session, clean_db):
        # ... (fixture 保持不變) ...
        now = datetime.now(timezone.utc)

        crawlers = [
            Crawlers(
                crawler_name="新聞爬蟲Web1",
                base_url="https://example.com/news1",
                is_active=True,
                created_at=(now - timedelta(days=5)),
                crawler_type="web",
                config_file_name="news_web1.json"
            ),
            Crawlers(
                crawler_name="新聞爬蟲Web2",
                base_url="https://example.com/news2",
                is_active=False,
                created_at=(now - timedelta(days=3)),
                crawler_type="web",
                config_file_name="news_web2.json"
            ),
            Crawlers(
                crawler_name="RSS爬蟲1",
                base_url="https://example.com/rss1",
                is_active=True,
                created_at=(now - timedelta(days=2)),
                crawler_type="rss",
                config_file_name="rss1.json"
            ),
            Crawlers(
                crawler_name="RSS爬蟲2",
                base_url="https://example.com/rss2",
                is_active=False,
                created_at=(now - timedelta(days=1)),
                crawler_type="rss",
                config_file_name="rss2.json"
            ),
            Crawlers(
                crawler_name="API爬蟲",
                base_url="https://example.com/api",
                is_active=True,
                created_at=now,
                crawler_type="api",
                config_file_name="api.json"
            )
        ]
        session.add_all(crawlers)
        session.commit()
        session.expire_all()
        return crawlers

    def test_combined_filters_with_pagination(self, crawlers_repo, filter_test_crawlers, session, clean_db):
        """測試組合多種過濾條件並進行分頁"""
        # 使用 find_paginated 進行測試
        filter_dict_1 = {"is_active": True, "crawler_type": "web"}
        page_data_1 = crawlers_repo.find_paginated(
            filter_criteria=filter_dict_1, page=1, per_page=10
        )
        assert page_data_1["total"] == 1
        assert len(page_data_1["items"]) == 1
        assert page_data_1["items"][0].crawler_name == "新聞爬蟲Web1"

        filter_dict_2 = {"crawler_type": {"$in": ["web", "rss"]}} # 使用 $in
        page_data_2 = crawlers_repo.find_paginated(
            filter_criteria=filter_dict_2, page=1, per_page=10
        )
        assert page_data_2["total"] == 4
        assert len(page_data_2["items"]) == 4

        two_days_ago = datetime.now(timezone.utc) - timedelta(days=2, hours=1)
        filter_dict_3 = {"created_at": {"$gte": two_days_ago}}
        page_data_3 = crawlers_repo.find_paginated(
            filter_criteria=filter_dict_3, page=1, per_page=10, sort_by="created_at", sort_desc=False
        )
        assert page_data_3["total"] == 3
        assert len(page_data_3["items"]) == 3
        assert page_data_3["items"][0].crawler_name == "RSS爬蟲1"

        filter_dict_4 = {"is_active": False, "crawler_type": "rss"}
        page_data_4 = crawlers_repo.find_paginated(
            filter_criteria=filter_dict_4, page=1, per_page=10
        )
        assert page_data_4["total"] == 1
        assert len(page_data_4["items"]) == 1
        assert page_data_4["items"][0].crawler_name == "RSS爬蟲2"

        filter_dict_5 = {"crawler_type": {"$ne": "api"}} # 使用 $ne
        page_data_5 = crawlers_repo.find_paginated(
            filter_criteria=filter_dict_5, page=1, per_page=10
        )
        assert page_data_5["total"] == 4

        # 測試空 filter_criteria
        page_data_empty = crawlers_repo.find_paginated(
            filter_criteria={}, page=1, per_page=3
        )
        assert page_data_empty["total"] == 5
        assert len(page_data_empty["items"]) == 3
        assert page_data_empty["has_next"] is True

        # 測試包含無效 key 的 filter_criteria (基類應忽略)
        filter_dict_invalid = {"is_active": True, "invalid_key": "some_value"}
        page_data_invalid = crawlers_repo.find_paginated(
            filter_criteria=filter_dict_invalid, page=1, per_page=10
        )
        assert page_data_invalid["total"] == 3 # Web1, RSS1, API
        assert len(page_data_invalid["items"]) == 3

    def test_pagination_with_sorting(self, crawlers_repo, filter_test_crawlers, session, clean_db):
        """測試分頁排序與過濾結合"""
        filter_dict = {"is_active": True}
        page_data_asc = crawlers_repo.find_paginated(
            filter_criteria=filter_dict,
            page=1,
            per_page=10,
            sort_by="created_at",
            sort_desc=False
        )
        assert page_data_asc["total"] == 3
        created_times_asc = [item.created_at for item in page_data_asc["items"]]
        assert created_times_asc == sorted(created_times_asc)
        assert page_data_asc["items"][0].crawler_name == "新聞爬蟲Web1"

        page_data_desc = crawlers_repo.find_paginated(
            filter_criteria=filter_dict,
            page=1,
            per_page=10,
            sort_by="created_at",
            sort_desc=True
        )
        assert page_data_desc["total"] == 3
        created_times_desc = [item.created_at for item in page_data_desc["items"]]
        assert created_times_desc == sorted(created_times_desc, reverse=True)
        assert page_data_desc["items"][0].crawler_name == "API爬蟲"

        filter_dict_names = {"crawler_type": {"$in": ["web", "rss"]}} # 使用 $in
        page_data_name_asc = crawlers_repo.find_paginated(
            filter_criteria=filter_dict_names,
            page=1,
            per_page=10,
            sort_by="crawler_name",
            sort_desc=False
        )
        assert page_data_name_asc["total"] == 4
        names_asc = [item.crawler_name for item in page_data_name_asc["items"]]
        assert names_asc == ["RSS爬蟲1", "RSS爬蟲2", "新聞爬蟲Web1", "新聞爬蟲Web2"]
