import pytest
from datetime import datetime, timezone
from src.model.crawler_settings_models import CrawlerSettings


class TestCrawlerSettingsModel:
    """CrawlerSettings 模型的測試類"""
    
    def test_crawler_settings_creation_with_required_fields(self):
        """測試使用必填欄位創建 CrawlerSettings"""
        settings = CrawlerSettings(
            crawler_name="test_crawler",
            scrape_target="https://example.com",  # 添加必要的 scrape_target 字段
            crawl_interval=60,
            is_active=True
        )
        
        assert settings.crawler_name == "test_crawler"
        assert settings.scrape_target == "https://example.com"
        assert settings.crawl_interval == 60
        assert settings.is_active is True
        assert settings.created_at is not None
        assert settings.updated_at is None
        assert settings.last_crawl_time is None
    
    def test_default_values(self):
        """測試默認值設置"""
        settings = CrawlerSettings(
            crawler_name="test_crawler",
            scrape_target="https://example.com",
            crawl_interval=60
        )
        
        assert settings.is_active is True  # 测试默认值为 True
        assert settings.created_at is not None
        assert isinstance(settings.created_at, datetime)
    
    def test_created_at_cannot_update(self):
        """測試 created_at 屬性無法更新"""
        settings = CrawlerSettings(
            crawler_name="test_crawler",
            scrape_target="https://example.com",
            crawl_interval=60
        )
        
        original_time = settings.created_at
        
        with pytest.raises(AttributeError) as exc_info:
            settings.created_at = datetime.now(timezone.utc)
        
        assert "created_at cannot be updated" in str(exc_info.value)
        assert settings.created_at == original_time
    
    def test_id_cannot_update(self):
        """測試 id 屬性無法更新"""
        settings = CrawlerSettings(
            id=1,
            crawler_name="test_crawler",
            scrape_target="https://example.com",
            crawl_interval=60
        )
        
        with pytest.raises(AttributeError) as exc_info:
            settings.id = 2
        
        assert "id cannot be updated" in str(exc_info.value)
        assert settings.id == 1
    
    def test_crawler_settings_repr(self):
        """測試 CrawlerSettings 的 __repr__ 方法"""
        settings = CrawlerSettings(
            id=1,
            crawler_name="test_crawler",
            scrape_target="https://example.com",
            crawl_interval=60,
            is_active=True
        )
        
        expected_repr = "<CrawlerSettings(id=1, crawler_name='test_crawler', scrape_target='https://example.com', is_active=True)>"
        assert repr(settings) == expected_repr