import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.models.crawlers_model import Crawlers
from src.database.crawlers_repository import CrawlersRepository, SchemaType
from src.models.base_model import Base
from src.error.errors import ValidationError, DatabaseOperationError

# 設置測試資料庫
@pytest.fixture
def engine():
    return create_engine('sqlite:///:memory:')

@pytest.fixture
def tables(engine):
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture
def session(engine, tables):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    
    try:
        yield session
    finally:
        session.close()
        # 只有在事務仍然有效時才回滾
        if transaction.is_active:
            transaction.rollback()
        connection.close()

@pytest.fixture
def crawlers_repo(session):
    return CrawlersRepository(session, Crawlers)

@pytest.fixture
def sample_crawlers(session):
    """建立測試用的爬蟲資料"""
    now = datetime.now(timezone.utc)
    
    crawlers = [
        Crawlers(
            crawler_name="新聞爬蟲1",
            base_url="https://example.com/news1",
            is_active=True,
            created_at=(now - timedelta(days=1)),
            crawler_type="web"
        ),
        Crawlers(
            crawler_name="新聞爬蟲2",
            base_url="https://example.com/news2",
            is_active=False,
            crawler_type="web"
        ),
        Crawlers(
            crawler_name="RSS爬蟲",
            base_url="https://example.com/rss",
            is_active=True,
            crawler_type="rss"
        )
    ]
    session.add_all(crawlers)
    session.commit()
    return crawlers

# CrawlersRepository 測試
class TestCrawlersRepository:
    """
    測試 Crawlers 相關資料庫操作
    """
    def test_get_schema_class(self, crawlers_repo):
        """測試獲取正確的 schema 類別"""
        from src.models.crawlers_schema import CrawlersCreateSchema, CrawlersUpdateSchema
        
        # 測試 CREATE schema
        schema_create = crawlers_repo.get_schema_class(SchemaType.CREATE)
        assert schema_create == CrawlersCreateSchema
        
        # 測試 UPDATE schema
        schema_update = crawlers_repo.get_schema_class(SchemaType.UPDATE)
        assert schema_update == CrawlersUpdateSchema
        
        # 測試 LIST 和 DETAIL schema
        with pytest.raises(ValueError) as exc_info:
            crawlers_repo.get_schema_class(SchemaType.LIST)
        assert "未支援的 schema 類型" in str(exc_info.value)
        
        # 測試默認值
        schema_default = crawlers_repo.get_schema_class()
        assert schema_default == CrawlersCreateSchema
    
    def test_get_all(self, crawlers_repo, sample_crawlers):
        """測試獲取所有爬蟲設定"""
        settings = crawlers_repo.get_all()
        assert len(settings) == 3
        assert isinstance(settings[0], Crawlers)
        
    def test_get_by_id(self, crawlers_repo, sample_crawlers):
        """測試通過ID獲取爬蟲設定"""
        # 測試存在的ID
        setting = crawlers_repo.get_by_id(1)
        assert setting is not None
        assert setting.id == 1
        
        # 測試不存在的ID
        setting = crawlers_repo.get_by_id(999)
        assert setting is None
    
    def test_find_by_crawler_name(self, crawlers_repo, sample_crawlers):
        """測試根據爬蟲名稱查詢"""
        # 完全匹配
        crawlers = crawlers_repo.find_by_crawler_name("新聞爬蟲1")
        assert len(crawlers) == 1
        assert crawlers[0].crawler_name == "新聞爬蟲1"
        
        # 部分匹配
        crawlers = crawlers_repo.find_by_crawler_name("爬蟲")
        assert len(crawlers) == 3
    
    def test_find_by_crawler_name_exact(self, crawlers_repo, sample_crawlers):
        """測試根據爬蟲名稱精確查詢"""
        # 完全匹配
        crawler = crawlers_repo.find_by_crawler_name_exact("新聞爬蟲1")
        assert crawler is not None
        assert crawler.crawler_name == "新聞爬蟲1"
        
        # 不存在的名稱
        crawler = crawlers_repo.find_by_crawler_name_exact("不存在的爬蟲")
        assert crawler is None
    
    def test_find_active_crawlers(self, crawlers_repo, sample_crawlers):
        """測試查詢活動中的爬蟲"""
        active_crawlers = crawlers_repo.find_active_crawlers()
        assert len(active_crawlers) == 2
        assert all(crawler.is_active for crawler in active_crawlers)


    def test_create(self, crawlers_repo):
        """測試使用模式驗證創建爬蟲"""
        new_crawler_data = {
            "crawler_name": "測試爬蟲",
            "base_url": "https://example.com/test",
            "is_active": True,
            "crawler_type": "web"
        }
        
        # 使用 create 方法創建新爬蟲設定
        new_crawler = crawlers_repo.create(new_crawler_data)
        assert new_crawler is not None
        assert new_crawler.id is not None
        assert new_crawler.crawler_name == "測試爬蟲"
        assert new_crawler.created_at is not None
        
        # 從資料庫中檢索並驗證
        retrieved = crawlers_repo.get_by_id(new_crawler.id)
        assert retrieved is not None
        assert retrieved.crawler_name == "測試爬蟲"
        assert retrieved.base_url == "https://example.com/test"
        assert retrieved.crawler_type == "web"
    
        # 測試驗證錯誤 - 缺少必填欄位
        invalid_data = {
            "crawler_name": "缺失欄位爬蟲",
            # 缺少 base_url
            "is_active": True
        }
        
        with pytest.raises(ValidationError):
            crawlers_repo.create(invalid_data)
            
    def test_crawler_name_uniqueness(self, crawlers_repo, sample_crawlers):
        """測試爬蟲名稱唯一性驗證"""
        # 嘗試創建重複名稱的爬蟲
        duplicate_data = {
            "crawler_name": "新聞爬蟲1",  # 已存在的名稱
            "base_url": "https://example.com/duplicate",
            "is_active": True,
            "crawler_type": "web"
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
    
    def test_update(self, crawlers_repo, sample_crawlers):
        """測試使用模式驗證更新爬蟲"""
        # 獲取第一個爬蟲設定的ID
        setting_id = sample_crawlers[0].id
        
        # 準備更新數據
        update_data = {
            "crawler_name": "已更新爬蟲名稱",
            "is_active": False
        }
        
        # 執行更新
        updated = crawlers_repo.update(setting_id, update_data)
        assert updated is not None
        assert updated.crawler_name == "已更新爬蟲名稱"
        assert updated.is_active is False
        assert updated.updated_at is not None
        
        # 確認只更新了指定欄位
        assert updated.base_url == sample_crawlers[0].base_url
        assert updated.crawler_type == sample_crawlers[0].crawler_type
        
        # 測試更新不存在的ID
        result = crawlers_repo.update(999, update_data)
        assert result is None
        
        # 測試嘗試更新不允許的欄位
        invalid_update = {
            "crawler_name": "測試非法更新",
            "crawler_type": "changed_type"  # 不允許更新類型
        }
        
        with pytest.raises(ValidationError):
            crawlers_repo.update(setting_id, invalid_update)
    
    def test_delete(self, crawlers_repo, sample_crawlers):
        """測試刪除爬蟲設定"""
        # 獲取最後一個爬蟲設定的ID
        setting_id = sample_crawlers[-1].id
        
        # 執行刪除
        result = crawlers_repo.delete(setting_id)
        assert result is True
        
        # 確認已從資料庫中刪除
        deleted = crawlers_repo.get_by_id(setting_id)
        assert deleted is None
        
        # 測試刪除不存在的ID
        result = crawlers_repo.delete(999)
        assert result is False

    def test_toggle_active_status(self, crawlers_repo, sample_crawlers):
        """測試切換爬蟲活躍狀態"""
        crawler_id = sample_crawlers[0].id
        original_status = sample_crawlers[0].is_active
        
        result = crawlers_repo.toggle_active_status(crawler_id)
        assert result is True
        
        updated_crawler = crawlers_repo.get_by_id(crawler_id)
        assert updated_crawler.is_active != original_status
        assert updated_crawler.updated_at is not None
        
        # 再次切換
        crawlers_repo.toggle_active_status(crawler_id)
        updated_again = crawlers_repo.get_by_id(crawler_id)
        assert updated_again.is_active == original_status
        
        # 測試切換不存在的ID
        result = crawlers_repo.toggle_active_status(999)
        assert result is False


    def test_find_by_type(self, crawlers_repo, sample_crawlers):
        """測試根據爬蟲類型查找"""
        web_crawlers = crawlers_repo.find_by_type("web")
        assert len(web_crawlers) == 2
        assert all(c.crawler_type == "web" for c in web_crawlers)
        
        rss_crawlers = crawlers_repo.find_by_type("rss")
        assert len(rss_crawlers) == 1
        assert rss_crawlers[0].crawler_type == "rss"

    def test_find_by_target(self, crawlers_repo, sample_crawlers):
        """測試根據爬取目標查詢"""
        news_crawlers = crawlers_repo.find_by_target("news")
        assert len(news_crawlers) == 2
        
        rss_crawlers = crawlers_repo.find_by_target("rss")
        assert len(rss_crawlers) == 1

    def test_get_crawler_statistics(self, crawlers_repo, sample_crawlers):
        """測試獲取爬蟲統計資訊"""
        stats = crawlers_repo.get_crawler_statistics()
        
        assert stats["total"] == 3
        assert stats["active"] == 2
        assert stats["inactive"] == 1
        assert stats["by_type"]["web"] == 2
        assert stats["by_type"]["rss"] == 1

    def test_create_or_update(self, crawlers_repo, sample_crawlers):
        """測試創建或更新功能"""
        # 測試更新現有記錄
        existing_id = sample_crawlers[0].id
        update_data = {
            "id": existing_id,
            "crawler_name": "更新通過create_or_update",
        }
        
        result = crawlers_repo.create_or_update(update_data)
        assert result is not None
        assert result.id == existing_id
        assert result.crawler_name == "更新通過create_or_update"

        # 測試創建新記錄
        new_data = {
            "crawler_name": "新記錄通過create_or_update",
            "base_url": "https://example.com/new",
            "crawler_type": "api"
        }
        
        result = crawlers_repo.create_or_update(new_data)
        assert result is not None
        assert result.id is not None
        assert result.crawler_name == "新記錄通過create_or_update"
        assert result.crawler_type == "api"
        
        # 測試ID不存在的情況
        nonexistent_id_data = {
            "id": 999,
            "crawler_name": "不存在的ID",
            "base_url": "https://example.com/nonexistent",
            "crawler_type": "web"
        }
        
        result = crawlers_repo.create_or_update(nonexistent_id_data)
        assert result is not None
        assert result.crawler_name == "不存在的ID"
        assert result.id != 999  # 應該創建新記錄

    def test_batch_toggle_active(self, crawlers_repo, sample_crawlers):
        """測試批量切換爬蟲活躍狀態"""
        # 獲取樣本爬蟲的ID
        crawler_ids = [c.id for c in sample_crawlers[:2]]
        
        # 測試批量啟用
        result = crawlers_repo.batch_toggle_active(crawler_ids, True)
        assert result["success_count"] == 2
        assert result["fail_count"] == 0
        
        # 驗證狀態已更新
        for crawler_id in crawler_ids:
            crawler = crawlers_repo.get_by_id(crawler_id)
            assert crawler.is_active is True
        
        # 測試批量停用
        result = crawlers_repo.batch_toggle_active(crawler_ids, False)
        assert result["success_count"] == 2
        
        # 驗證狀態已更新
        for crawler_id in crawler_ids:
            crawler = crawlers_repo.get_by_id(crawler_id)
            assert crawler.is_active is False
        
        # 測試包含不存在的ID
        mixed_ids = crawler_ids + [999]
        result = crawlers_repo.batch_toggle_active(mixed_ids, True)
        assert result["success_count"] == 2
        assert result["fail_count"] == 1
        assert 999 in result["failed_ids"]

    def test_error_handling(self, crawlers_repo, session):
        """測試錯誤處理"""
        # 測試資料庫操作錯誤
        with pytest.raises(DatabaseOperationError) as exc_info:
            crawlers_repo.execute_query(
                lambda: session.execute("SELECT * FROM nonexistent_table")
            )
        assert "資料庫操作錯誤" in str(exc_info.value)

class TestPagination:
    """測試分頁功能"""
    
    def test_pagination(self, crawlers_repo, sample_crawlers):
        """測試分頁功能"""
        # 添加更多測試數據以使分頁測試更有意義
        for i in range(6):
            new_setting = Crawlers(
                crawler_name=f"額外爬蟲{i+1}",
                base_url=f"https://example.com/extra{i+1}",
                is_active=True,
                crawler_type="web"
            )
            crawlers_repo.session.add(new_setting)
        crawlers_repo.session.commit()
        
        # 測試第一頁
        page1 = crawlers_repo.get_paginated(page=1, per_page=3)
        assert page1["page"] == 1
        assert page1["per_page"] == 3
        assert len(page1["items"]) == 3
        assert page1["total"] == 9  # 3個原始樣本+6個新增
        assert page1["total_pages"] == 3
        assert page1["has_next"] is True
        assert page1["has_prev"] is False
        
        # 測試第二頁
        page2 = crawlers_repo.get_paginated(page=2, per_page=3)
        assert page2["page"] == 2
        assert len(page2["items"]) == 3
        assert page2["has_next"] is True
        assert page2["has_prev"] is True
        
        # 測試第三頁
        page3 = crawlers_repo.get_paginated(page=3, per_page=3)
        assert page3["page"] == 3
        assert len(page3["items"]) == 3
        assert page3["has_next"] is False
        assert page3["has_prev"] is True
        
        # 測試超出範圍的頁碼
        page_out = crawlers_repo.get_paginated(page=10, per_page=3)
        assert page_out["page"] == 3
        
        # 測試排序功能
        sorted_page = crawlers_repo.get_paginated(page=1, per_page=10, sort_by="crawler_name", sort_desc=True)
        intervals = [item.crawler_name for item in sorted_page["items"]]
        assert intervals == sorted(intervals, reverse=True)

    def test_pagination_edge_cases(self, crawlers_repo, sample_crawlers):
        """測試分頁邊界情況"""
        # 測試每頁大小為0
        with pytest.raises(ValueError):
            crawlers_repo.get_paginated(page=1, per_page=0)
        
        # 測試負數頁碼
        page_neg = crawlers_repo.get_paginated(page=-1, per_page=3)
        assert page_neg["page"] == 1  # 應自動調整為第1頁
        
        # 測試空數據集的分頁
        crawlers_repo.session.query(Crawlers).delete()
        crawlers_repo.session.commit()
        
        empty_page = crawlers_repo.get_paginated(page=1, per_page=3)
        assert empty_page["total"] == 0
        assert empty_page["total_pages"] == 0
        assert len(empty_page["items"]) == 0
        assert empty_page["has_next"] is False
        assert empty_page["has_prev"] is False

    def test_pagination_sorting(self, crawlers_repo, sample_crawlers):
        """測試分頁排序功能"""
        # 測試升序排序
        asc_page = crawlers_repo.get_paginated(
            page=1, 
            per_page=10, 
            sort_by="crawler_name", 
            sort_desc=False
        )
        asc_intervals = [item.crawler_name for item in asc_page["items"]]
        assert asc_intervals == sorted(asc_intervals)
        
        # 測試降序排序
        desc_page = crawlers_repo.get_paginated(
            page=1, 
            per_page=10, 
            sort_by="crawler_name", 
            sort_desc=True
        )
        desc_intervals = [item.crawler_name for item in desc_page["items"]]
        assert desc_intervals == sorted(desc_intervals, reverse=True)
        
        # 測試無效的排序欄位
        with pytest.raises(DatabaseOperationError):
            crawlers_repo.get_paginated(
                page=1, 
                per_page=10, 
                sort_by="non_existent_field"
            )

    def test_pagination_data_integrity(self, crawlers_repo, sample_crawlers):
        """測試分頁數據的完整性"""
        all_records = crawlers_repo.get_all()
        total_count = len(all_records)
        
        # 收集所有分頁的數據
        collected_records = []
        page = 1
        while True:
            page_data = crawlers_repo.get_paginated(page=page, per_page=3)
            collected_records.extend(page_data["items"])
            if not page_data["has_next"]:
                break
            page += 1
        
        # 驗證收集到的記錄數量
        assert len(collected_records) == total_count
        
        # 驗證沒有重複記錄
        record_ids = [r.id for r in collected_records]
        assert len(record_ids) == len(set(record_ids))
