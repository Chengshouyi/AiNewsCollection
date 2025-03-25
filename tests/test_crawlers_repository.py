import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.models.crawlers_model import Crawlers
from src.database.crawlers_repository import CrawlersRepository
from src.models.base_model import Base
import uuid
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
    """確保所有時間都是 UTC aware"""
    now = datetime.now(timezone.utc)
    
    settings = [
        Crawlers(
            crawler_name="新聞爬蟲1",
            scrape_target="https://example.com/news1",
            crawl_interval=60,
            is_active=True,
            last_crawl_time=(now - timedelta(hours=2)).replace(tzinfo=timezone.utc),
            created_at=(now - timedelta(days=1)).replace(tzinfo=timezone.utc),
            crawler_type="web"
        ),
        Crawlers(
            crawler_name="新聞爬蟲2",
            scrape_target="https://example.com/news2",
            crawl_interval=120,
            is_active=False,
            last_crawl_time=now - timedelta(days=1),
            crawler_type="web"
        ),
        Crawlers(
            crawler_name="RSS爬蟲",
            scrape_target="https://example.com/rss",
            crawl_interval=30,
            is_active=True,
            last_crawl_time=None,
            crawler_type="rss"
        ),
        Crawlers(
            crawler_name="API爬蟲",
            scrape_target="https://example.com/api",
            crawl_interval=45,
            is_active=True,
            last_crawl_time=now - timedelta(minutes=20),
            crawler_type="api"
        )
    ]
    session.add_all(settings)
    session.commit()
    return settings

# CrawlersRepository 測試
class TestCrawlersRepository:
    """
    測試 Crawlers 相關資料庫操作
    """
    def test_get_all(self, crawlers_repo, sample_crawlers):
        """測試獲取所有爬蟲設定"""
        settings = crawlers_repo.get_all()
        assert len(settings) == 4
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
        """測試通過爬蟲名稱查找設定"""
        # 測試存在的名稱
        settings = crawlers_repo.find_by_crawler_name("新聞爬蟲1")
        assert len(settings) == 1
        assert settings[0].crawler_name == "新聞爬蟲1"
        
        # 測試部分匹配的名稱
        settings = crawlers_repo.find_by_crawler_name("爬蟲")
        assert len(settings) == 4
        
        # 測試不存在的名稱
        settings = crawlers_repo.find_by_crawler_name("不存在的爬蟲")
        assert len(settings) == 0
    
    def test_find_active_crawlers(self, crawlers_repo, sample_crawlers):
        """測試查找活躍的爬蟲"""
        settings = crawlers_repo.find_active_crawlers()
        assert len(settings) == 3
        assert all(setting.is_active for setting in settings)
    
    def test_find_pending_crawlers(self, crawlers_repo, sample_crawlers):
        """測試查找需要執行的爬蟲"""
        # 使用固定的時間點
        base_time = datetime(2025, 3, 25, 15, 0, 0, tzinfo=timezone.utc)
        
        # 重新設置所有爬蟲的時間
        for crawler in sample_crawlers:
            if crawler.last_crawl_time is not None:
                # 設置為3小時前
                crawler.last_crawl_time = base_time - timedelta(hours=3)
            # 設置創建時間
            crawler.created_at = base_time - timedelta(days=1)
        
        # 提交更改
        crawlers_repo.session.commit()
        
        # 強制重新從資料庫加載所有爬蟲
        crawlers_repo.session.expire_all()
        
        # 設置當前時間為基準時間加2小時
        current_time = base_time + timedelta(hours=2)
        settings = crawlers_repo.find_pending_crawlers(current_time)
        
        # 驗證結果
        assert len(settings) >= 2  # 至少應該有2個需要執行的爬蟲
        assert all(setting.is_active for setting in settings)
        
        # 驗證時間間隔
        for setting in settings:
            if setting.last_crawl_time:
                # 確保時間是 UTC aware
                last_crawl = setting.last_crawl_time
                if last_crawl.tzinfo is None:
                    last_crawl = last_crawl.replace(tzinfo=timezone.utc)
                
                time_diff = (current_time - last_crawl).total_seconds()
                assert time_diff >= setting.crawl_interval * 60

    def test_update_last_crawl_time(self, crawlers_repo, sample_crawlers):
        """測試更新最後爬蟲時間"""
        from time import sleep
        
        # 獲取第一個爬蟲設定
        setting_id = sample_crawlers[0].id
        old_time = sample_crawlers[0].last_crawl_time
        
        # 更新最後爬蟲時間，使用較早的時間
        first_time = datetime.now(timezone.utc)
        sleep(0.1)  # 確保時間差
        
        result = crawlers_repo.update_last_crawl_time(setting_id, first_time)
        assert result is True
        
        # 驗證更新成功
        updated_setting = crawlers_repo.get_by_id(setting_id)
        assert updated_setting.last_crawl_time != old_time
        assert updated_setting.last_crawl_time == first_time
        
        sleep(0.1)  # 確保時間差
        
        # 測試默認時間參數（應該使用更新的時間）
        result = crawlers_repo.update_last_crawl_time(setting_id)
        assert result is True
        
        # 獲取最終設置並驗證時間
        final_setting = crawlers_repo.get_by_id(setting_id)
        assert final_setting.last_crawl_time > first_time  # 比較與第一次更新的時間

    def test_create_crawler(self, crawlers_repo):
        """測試使用模式驗證創建爬蟲"""
        new_crawler_data = {
            "crawler_name": "測試爬蟲",
            "scrape_target": "https://example.com/test",
            "crawl_interval": 45,
            "is_active": True,
            "crawler_type": "web"
        }
        
        # 使用 create_crawler 方法創建新爬蟲設定
        new_crawler = crawlers_repo.create_crawler(new_crawler_data)
        assert new_crawler is not None
        assert new_crawler.id is not None
        assert new_crawler.crawler_name == "測試爬蟲"
        assert new_crawler.created_at is not None
        
        # 從資料庫中檢索並驗證
        retrieved = crawlers_repo.get_by_id(new_crawler.id)
        assert retrieved is not None
        assert retrieved.crawler_name == "測試爬蟲"
        assert retrieved.scrape_target == "https://example.com/test"
        assert retrieved.crawler_type == "web"
    
        # 測試驗證錯誤 - 缺少必填欄位
        invalid_data = {
            "crawler_name": "缺失欄位爬蟲",
            # 缺少 scrape_target
            "crawl_interval": 60,
            "is_active": True
        }
        
        with pytest.raises(ValidationError):
            crawlers_repo.create_crawler(invalid_data)
    
    def test_update_crawler(self, crawlers_repo, sample_crawlers):
        """測試使用模式驗證更新爬蟲"""
        # 獲取第一個爬蟲設定的ID
        setting_id = sample_crawlers[0].id
        
        # 準備更新數據
        update_data = {
            "crawler_name": "已更新爬蟲名稱",
            "crawl_interval": 90,
            "is_active": False
        }
        
        # 執行更新
        updated = crawlers_repo.update_crawler(setting_id, update_data)
        assert updated is not None
        assert updated.crawler_name == "已更新爬蟲名稱"
        assert updated.crawl_interval == 90
        assert updated.is_active is False
        assert updated.updated_at is not None
        
        # 確認只更新了指定欄位
        assert updated.scrape_target == sample_crawlers[0].scrape_target
        assert updated.crawler_type == sample_crawlers[0].crawler_type
        
        # 測試更新不存在的ID
        result = crawlers_repo.update_crawler(999, update_data)
        assert result is None
        
        # 測試嘗試更新不允許的欄位
        invalid_update = {
            "crawler_name": "測試非法更新",
            "crawler_type": "changed_type"  # 不允許更新類型
        }
        
        with pytest.raises(ValidationError):
            crawlers_repo.update_crawler(setting_id, invalid_update)
    
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
        # 獲取第一個爬蟲設定
        setting_id = sample_crawlers[0].id
        original_status = sample_crawlers[0].is_active
        
        # 執行切換
        result = crawlers_repo.toggle_active_status(setting_id)
        assert result is True
        
        # 確認狀態已切換
        updated = crawlers_repo.get_by_id(setting_id)
        assert updated.is_active != original_status
        
        # 再次切換
        crawlers_repo.toggle_active_status(setting_id)
        updated_again = crawlers_repo.get_by_id(setting_id)
        assert updated_again.is_active == original_status
        
        # 測試切換不存在的ID
        result = crawlers_repo.toggle_active_status(999)
        assert result is False

    def test_get_sorted_by_interval(self, crawlers_repo, sample_crawlers):
        """測試按爬取間隔排序的爬蟲設定"""
        # 測試默認升序排序
        crawlers = crawlers_repo.get_sorted_by_interval()
        intervals = [c.crawl_interval for c in crawlers]
        assert intervals == sorted(intervals)
        
        # 測試降序排序
        crawlers = crawlers_repo.get_sorted_by_interval(descending=True)
        intervals = [c.crawl_interval for c in crawlers]
        assert intervals == sorted(intervals, reverse=True)

    def test_find_by_type(self, crawlers_repo, sample_crawlers):
        """測試根據爬蟲類型查找爬蟲"""
        # 查找 web 類型爬蟲
        web_crawlers = crawlers_repo.find_by_type("web")
        assert len(web_crawlers) == 2
        assert all(c.crawler_type == "web" for c in web_crawlers)
        
        # 查找 rss 類型爬蟲
        rss_crawlers = crawlers_repo.find_by_type("rss")
        assert len(rss_crawlers) == 1
        assert rss_crawlers[0].crawler_type == "rss"
        
        # 查找不存在的類型
        nonexistent_crawlers = crawlers_repo.find_by_type("nonexistent")
        assert len(nonexistent_crawlers) == 0

    def test_find_by_target(self, crawlers_repo, sample_crawlers):
        """測試根據爬取目標模糊查詢爬蟲"""
        # 查找包含 "news" 的目標
        news_crawlers = crawlers_repo.find_by_target("news")
        assert len(news_crawlers) == 2
        
        # 查找包含 "api" 的目標
        api_crawlers = crawlers_repo.find_by_target("api")
        assert len(api_crawlers) == 1
        
        # 查找包含 "example.com" 的目標 (應該返回所有爬蟲)
        all_crawlers = crawlers_repo.find_by_target("example.com")
        assert len(all_crawlers) == 4
        
        # 查找不存在的目標
        nonexistent_crawlers = crawlers_repo.find_by_target("nonexistent")
        assert len(nonexistent_crawlers) == 0

    def test_get_crawler_statistics(self, crawlers_repo, sample_crawlers):
        """測試獲取爬蟲統計信息"""
        stats = crawlers_repo.get_crawler_statistics()
        
        # 檢查統計資料格式
        assert "total" in stats
        assert "active" in stats
        assert "inactive" in stats
        assert "by_type" in stats
        
        # 檢查數據是否正確
        assert stats["total"] == 4
        assert stats["active"] == 3
        assert stats["inactive"] == 1
        
        # 檢查類型統計
        assert "web" in stats["by_type"]
        assert stats["by_type"]["web"] == 2
        assert stats["by_type"]["rss"] == 1
        assert stats["by_type"]["api"] == 1

class TestPagination:
    """測試分頁功能"""
    
    def test_pagination(self, crawlers_repo, sample_crawlers):
        """測試分頁功能"""
        # 添加更多測試數據以使分頁測試更有意義
        for i in range(6):
            new_setting = Crawlers(
                crawler_name=f"額外爬蟲{i+1}",
                scrape_target=f"https://example.com/extra{i+1}",
                crawl_interval=60,
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
        assert page1["total"] == 10  # 4個原始樣本+6個新增
        assert page1["total_pages"] == 4
        assert page1["has_next"] is True
        assert page1["has_prev"] is False
        
        # 測試第二頁
        page2 = crawlers_repo.get_paginated(page=2, per_page=3)
        assert page2["page"] == 2
        assert len(page2["items"]) == 3
        assert page2["has_next"] is True
        assert page2["has_prev"] is True
        
        # 測試最後一頁
        page4 = crawlers_repo.get_paginated(page=4, per_page=3)
        assert page4["page"] == 4
        assert len(page4["items"]) == 1
        assert page4["has_next"] is False
        assert page4["has_prev"] is True
        
        # 測試超出範圍的頁碼
        page_out = crawlers_repo.get_paginated(page=10, per_page=3)
        assert page_out["page"] == 4  # 自動調整為最後一頁
        
        # 測試排序功能
        sorted_page = crawlers_repo.get_paginated(page=1, per_page=10, sort_by="crawl_interval", sort_desc=True)
        intervals = [item.crawl_interval for item in sorted_page["items"]]
        assert intervals == sorted(intervals, reverse=True)

class TestErrorHandling:
    """測試錯誤處理"""
    
    def test_database_operation_error(self, crawlers_repo, session):
        """測試資料庫操作錯誤處理"""
        # 測試無效SQL操作
        with pytest.raises(DatabaseOperationError) as excinfo:
            crawlers_repo.execute_query(
                lambda: session.execute("SELECT * FROM nonexistent_table")
            )
        assert "資料庫操作錯誤" in str(excinfo.value)
    
    def test_validation_error(self, crawlers_repo):
        """測試驗證錯誤處理"""
        # 測試缺少必要欄位
        invalid_data = {
            # 缺少 crawler_name
            "scrape_target": "https://example.com/test",
            "crawl_interval": 60,
            "is_active": True,
            "crawler_type": "web"
        }
        
        with pytest.raises(ValidationError):
            crawlers_repo.create_crawler(invalid_data)
        
        # 測試無效的爬取間隔
        invalid_interval = {
            "crawler_name": "無效間隔爬蟲",
            "scrape_target": "https://example.com/test",
            "crawl_interval": -10,  # 負值間隔
            "is_active": True,
            "crawler_type": "web"
        }
        
        with pytest.raises(ValidationError):
            crawlers_repo.create_crawler(invalid_interval)
