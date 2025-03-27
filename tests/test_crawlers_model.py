import pytest
from datetime import datetime, timezone
from src.models.crawlers_model import Crawlers


class TestCrawlersModel:
    """Crawlers 模型的測試類"""
    
    def test_crawlers_creation_with_required_fields(self):
        """測試使用必填欄位創建 Crawlers"""
        crawler = Crawlers(
            crawler_name="test_crawler",
            base_url="https://example.com",
            crawler_type="web"
        )
        
        assert crawler.crawler_name == "test_crawler"
        assert crawler.base_url == "https://example.com"
        assert crawler.is_active is True  # 測試默認值
        assert crawler.crawler_type == "web"
        assert isinstance(crawler.created_at, datetime)
        assert crawler.updated_at is None
        assert crawler.crawler_tasks == []  # 測試關聯關係
    
    def test_timestamps_behavior(self):
        """測試時間戳行為"""
        crawler = Crawlers(
            crawler_name="test_crawler",
            base_url="https://example.com",
            crawler_type="web"
        )
        
        # 只測試創建時間是 UTC
        assert crawler.created_at.tzinfo == timezone.utc
        
        # 確認 updated_at 初始為 None
        assert crawler.updated_at is None
    
    def test_to_dict_method(self):
        """測試 to_dict 方法"""
        crawler = Crawlers(
            id=1,
            crawler_name="test_crawler",
            base_url="https://example.com",
            crawler_type="web"
        )
        
        dict_data = crawler.to_dict()
        
        assert dict_data['id'] == 1
        assert dict_data['crawler_name'] == "test_crawler"
        assert dict_data['base_url'] == "https://example.com"
        assert dict_data['crawler_type'] == "web"
        assert dict_data['is_active'] is True
    
    def test_repr_method(self):
        """測試 __repr__ 方法"""
        crawler = Crawlers(
            id=1,
            crawler_name="test_crawler",
            base_url="https://example.com",
            crawler_type="web"
        )
        
        expected_repr = "<Crawlers(id=1, crawler_name='test_crawler', base_url='https://example.com', crawler_type='web', is_active=True)>"
        assert repr(crawler) == expected_repr
    
    def test_relationship_behavior(self):
        """測試關聯關係行為"""
        crawler = Crawlers(
            crawler_name="test_crawler",
            base_url="https://example.com",
            crawler_type="web"
        )
        
        assert hasattr(crawler, 'crawler_tasks')
        assert isinstance(crawler.crawler_tasks, list)
        assert len(crawler.crawler_tasks) == 0