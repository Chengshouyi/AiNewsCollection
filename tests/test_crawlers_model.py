import pytest
from datetime import datetime, timezone
from src.models.crawlers_model import Crawlers
from src.error.errors import ValidationError

class TestCrawlersModel:
    """Crawlers 模型的測試類"""
    
    def test_crawlers_creation_with_required_fields(self):
        """測試使用必填欄位創建 Crawlers"""
        crawler = Crawlers(
            crawler_name="test_crawler",
            scrape_target="https://example.com",
            crawl_interval=60,
            is_active=True,
            crawler_type="web"  # 新增 crawler_type
        )
        
        assert crawler.crawler_name == "test_crawler"
        assert crawler.scrape_target == "https://example.com"
        assert crawler.crawl_interval == 60
        assert crawler.is_active is True
        assert crawler.crawler_type == "web"
        assert crawler.created_at is not None
        assert crawler.updated_at is None
        assert crawler.last_crawl_time is None
    
    def test_default_values(self):
        """測試默認值設置"""
        crawler = Crawlers(
            crawler_name="test_crawler",
            scrape_target="https://example.com",
            crawl_interval=60,
            crawler_type="web"
        )
        
        assert crawler.is_active is True
        assert crawler.created_at is not None
        assert isinstance(crawler.created_at, datetime)
    
    def test_created_at_cannot_update(self):
        """測試 created_at 屬性無法更新"""
        crawler = Crawlers(
            crawler_name="test_crawler",
            scrape_target="https://example.com",
            crawl_interval=60,
            crawler_type="web"
        )
        
        original_time = crawler.created_at
        
        with pytest.raises(ValidationError) as exc_info:
            crawler.created_at = datetime.now(timezone.utc)
        
        assert "created_at cannot be updated" in str(exc_info.value)
        assert crawler.created_at == original_time
    
    def test_id_cannot_update(self):
        """測試 id 屬性無法更新"""
        crawler = Crawlers(
            id=1,
            crawler_name="test_crawler",
            scrape_target="https://example.com",
            crawl_interval=60,
            crawler_type="web"
        )
        
        with pytest.raises(ValidationError) as exc_info:
            crawler.id = 2
        
        assert "id cannot be updated" in str(exc_info.value)
        assert crawler.id == 1
    
    def test_crawler_type_cannot_update(self):
        """測試 crawler_type 屬性無法更新"""
        crawler = Crawlers(
            crawler_name="test_crawler",
            scrape_target="https://example.com",
            crawl_interval=60,
            crawler_type="web"
        )
        
        with pytest.raises(ValidationError) as exc_info:
            crawler.crawler_type = "mobile"
        
        assert "crawler_type cannot be updated" in str(exc_info.value)
        assert crawler.crawler_type == "web"
    
    def test_crawlers_repr(self):
        """測試 Crawlers 的 __repr__ 方法"""
        crawler = Crawlers(
            id=1,
            crawler_name="test_crawler",
            scrape_target="https://example.com",
            crawl_interval=60,
            is_active=True,
            crawler_type="web"
        )
        
        expected_repr = "<Crawlers(id=1, crawler_name='test_crawler', scrape_target='https://example.com', crawler_type='web', is_active=True)>"
        assert repr(crawler) == expected_repr
    
    def test_crawler_name_length_validation(self):
        """測試 crawler_name 長度驗證"""
        # 測試太短的名稱
        with pytest.raises(Exception):
            Crawlers(
                crawler_name="",
                scrape_target="https://example.com",
                crawl_interval=60,
                crawler_type="web"
            )
        
        # 測試太長的名稱
        with pytest.raises(Exception):
            Crawlers(
                crawler_name="a" * 101,
                scrape_target="https://example.com",
                crawl_interval=60,
                crawler_type="web"
            )
    
    def test_scrape_target_length_validation(self):
        """測試 scrape_target 長度驗證"""
        # 測試太短的目標
        with pytest.raises(Exception):
            Crawlers(
                crawler_name="test_crawler",
                scrape_target="",
                crawl_interval=60,
                crawler_type="web"
            )
        
        # 測試太長的目標
        with pytest.raises(Exception):
            Crawlers(
                crawler_name="test_crawler",
                scrape_target="a" * 1001,
                crawl_interval=60,
                crawler_type="web"
            )
    
    def test_crawler_type_length_validation(self):
        """測試 crawler_type 長度驗證"""
        # 測試太短的類型
        with pytest.raises(Exception):
            Crawlers(
                crawler_name="test_crawler",
                scrape_target="https://example.com",
                crawl_interval=60,
                crawler_type=""
            )
        
        # 測試太長的類型
        with pytest.raises(Exception):
            Crawlers(
                crawler_name="test_crawler",
                scrape_target="https://example.com",
                crawl_interval=60,
                crawler_type="a" * 101
            )