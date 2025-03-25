from src.models.crawlers_schema import CrawlersCreateSchema, CrawlersUpdateSchema
from src.error.errors import ValidationError
import pytest
from datetime import datetime

class TestCrawlersCreateSchema:
    """CrawlersCreateSchema 的測試類"""
    
    def test_crawlers_schema_with_valid_data(self):
        """測試有效的系統設定資料"""
        data = {
            "crawler_name": "test_crawler",
            "scrape_target": "https://example.com",
            "crawl_interval": 60,
            "is_active": True,
            "crawler_type": "web"
        }
        schema = CrawlersCreateSchema.model_validate(data)
        assert schema.crawler_name == "test_crawler"
        assert schema.scrape_target == "https://example.com"
        assert schema.crawl_interval == 60
        assert schema.is_active is True
        assert schema.crawler_type == "web"
        assert schema.created_at is not None
    
    def test_crawlers_required_fields(self):
        """測試必填欄位的驗證"""
        # 缺少 crawler_name
        data1 = {
            "scrape_target": "https://example.com",
            "crawl_interval": 60,
            "crawler_type": "web"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data1)
        assert "crawler_name: 不能為空" in str(exc_info.value)
        
        # 缺少 scrape_target
        data2 = {
            "crawler_name": "test_crawler",
            "crawl_interval": 60,
            "crawler_type": "web"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data2)
        assert "scrape_target: 不能為空" in str(exc_info.value)
        
        # 缺少 crawl_interval
        data3 = {
            "crawler_name": "test_crawler",
            "scrape_target": "https://example.com",
            "crawler_type": "web"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data3)
        assert "crawl_interval: 不能為空" in str(exc_info.value)
    
    def test_crawlers_crawler_name_validation(self):
        """測試爬蟲名稱的驗證"""
        # 空值
        data_empty = {
            "crawler_name": "",
            "scrape_target": "https://example.com",
            "crawl_interval": 60,
            "crawler_type": "web"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data_empty)
        assert "crawler_name: 不能為空" in str(exc_info.value)
        
        # 過長
        data_too_long = {
            "crawler_name": "a" * 101,
            "scrape_target": "https://example.com",
            "crawl_interval": 60,
            "crawler_type": "web"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data_too_long)
        assert "crawler_name: 長度不能超過 100 字元" in str(exc_info.value)
        
        # 邊界值
        data_min = {
            "crawler_name": "a",
            "scrape_target": "https://example.com",
            "crawl_interval": 60,
            "crawler_type": "web"
        }
        schema_min = CrawlersCreateSchema.model_validate(data_min)
        assert schema_min.crawler_name == "a"
        
        data_max = {
            "crawler_name": "a" * 100,
            "scrape_target": "https://example.com",
            "crawl_interval": 60,
            "crawler_type": "web"
        }
        schema_max = CrawlersCreateSchema.model_validate(data_max)
        assert len(schema_max.crawler_name) == 100
    
    def test_crawlers_scrape_target_validation(self):
        """測試爬取目標的驗證"""
        # 空值
        data_empty = {
            "crawler_name": "test_crawler",
            "scrape_target": "",
            "crawl_interval": 60,
            "crawler_type": "web"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data_empty)
        assert "scrape_target: URL不能為空" in str(exc_info.value)

        # 過長
        data_too_long = {
            "crawler_name": "test_crawler",
            "scrape_target": "http://example.com/" + "a" * 1000,
            "crawl_interval": 60,
            "crawler_type": "web"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data_too_long)
        assert "scrape_target: 長度不能超過 1000 字元" in str(exc_info.value)

        # 邊界值
        data_max = {
            "crawler_name": "test_crawler",
            "scrape_target": "http://example.com/" + "a" * 980,  # 確保總長度不超過1000
            "crawl_interval": 60,
            "crawler_type": "web"
        }
        schema_max = CrawlersCreateSchema.model_validate(data_max)
        assert schema_max.scrape_target == data_max["scrape_target"]

        # 無效的 URL 格式
        data_invalid_url = {
            "crawler_name": "test_crawler",
            "scrape_target": "invalid_url",
            "crawl_interval": 60,
            "crawler_type": "web"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data_invalid_url)
        assert "scrape_target: 無效的URL格式" in str(exc_info.value)
    
    def test_crawlers_crawler_type_validation(self):
        """測試爬蟲類型的驗證"""
        # 空值
        data_empty = {
            "crawler_name": "test_crawler",
            "scrape_target": "https://example.com",
            "crawl_interval": 60,
            "crawler_type": ""
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data_empty)
        assert "crawler_type: 不能為空" in str(exc_info.value)
        
        # 過長
        data_too_long = {
            "crawler_name": "test_crawler",
            "scrape_target": "https://example.com",
            "crawl_interval": 60,
            "crawler_type": "a" * 101
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data_too_long)
        assert "crawler_type: 長度不能超過 100 字元" in str(exc_info.value)
    
    def test_crawlers_crawl_interval_validation(self):
        """測試爬取間隔的驗證"""
        # 負值
        data_negative = {
            "crawler_name": "test_crawler",
            "scrape_target": "https://example.com",
            "crawl_interval": -1,
            "crawler_type": "web"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data_negative)
        assert "crawl_interval: 必須大於 0" in str(exc_info.value)
        
        # 零值
        data_zero = {
            "crawler_name": "test_crawler",
            "scrape_target": "https://example.com",
            "crawl_interval": 0,
            "crawler_type": "web"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data_zero)
        assert "crawl_interval: 必須大於 0" in str(exc_info.value)
    
    def test_crawlers_is_active_validation(self):
        """測試是否啟用的驗證"""
        # 非布林值
        data_not_bool = {
            "crawler_name": "test_crawler",
            "scrape_target": "https://example.com",
            "crawl_interval": 60,
            "crawler_type": "web",
            "is_active": "not_a_boolean"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data_not_bool)
        assert "is_active: 必須是布爾值" in str(exc_info.value)

class TestCrawlersUpdateSchema:
    """CrawlersUpdateSchema 的測試類"""
    
    def test_crawlers_update_schema_with_valid_data(self):
        """測試有效的系統設定更新資料"""
        data = {
            "crawler_name": "test_crawler",
            "crawl_interval": 60,
            "is_active": True
        }
        schema = CrawlersUpdateSchema.model_validate(data)
        assert schema.crawler_name == "test_crawler"
        assert schema.crawl_interval == 60
        assert schema.is_active is True
    
    def test_crawlers_update_schema_with_partial_data(self):
        """測試部分欄位更新"""
        # 只更新 crawler_name
        data1 = {
            "crawler_name": "updated_crawler"
        }
        schema1 = CrawlersUpdateSchema.model_validate(data1)
        assert schema1.crawler_name == "updated_crawler"
        assert schema1.crawl_interval is None
        assert schema1.is_active is None
        
        # 只更新 crawl_interval
        data2 = {
            "crawl_interval": 120
        }
        schema2 = CrawlersUpdateSchema.model_validate(data2)
        assert schema2.crawler_name is None
        assert schema2.crawl_interval == 120
        assert schema2.is_active is None
        
        # 只更新 is_active
        data3 = {
            "is_active": False
        }
        schema3 = CrawlersUpdateSchema.model_validate(data3)
        assert schema3.crawler_name is None
        assert schema3.crawl_interval is None
        assert schema3.is_active is False
    
    def test_crawlers_update_no_fields_validation(self):
        """測試沒有提供更新欄位的驗證"""
        data = {}
        with pytest.raises(ValidationError) as exc_info:
            CrawlersUpdateSchema.model_validate(data)
        assert "必須提供至少一個要更新的欄位" in str(exc_info.value)
    
    def test_crawlers_update_immutable_fields_validation(self):
        """測試不允許更新不可變欄位的驗證"""
        # 不允許更新 created_at
        data1 = {
            "crawler_name": "test_crawler",
            "created_at": datetime.now()
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersUpdateSchema.model_validate(data1)
        assert "不允許更新 created_at 欄位" in str(exc_info.value)
        
        # 不允許更新 id
        data2 = {
            "crawler_name": "test_crawler",
            "id": 1
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersUpdateSchema.model_validate(data2)
        assert "不允許更新 id 欄位" in str(exc_info.value)
        
        # 不允許更新 crawler_type
        data3 = {
            "crawler_name": "test_crawler",
            "crawler_type": "mobile"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersUpdateSchema.model_validate(data3)
        assert "不允許更新 crawler_type 欄位" in str(exc_info.value)
    
    def test_crawlers_update_crawler_name_validation(self):
        """測試更新爬蟲名稱的驗證"""
        # 空字串
        data_empty = {
            "crawler_name": ""
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersUpdateSchema.model_validate(data_empty)
        assert "crawler_name: 不能為空" in str(exc_info.value)
        
        # 過長
        data_too_long = {
            "crawler_name": "a" * 101
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersUpdateSchema.model_validate(data_too_long)
        assert "crawler_name: 長度不能超過 100 字元" in str(exc_info.value)
        
        # None值是允許的
        data_none = {
            "crawl_interval": 60,
            "crawler_name": None
        }
        schema = CrawlersUpdateSchema.model_validate(data_none)
        assert schema.crawler_name is None
    
    def test_crawlers_update_crawl_interval_validation(self):
        """測試更新爬取間隔的驗證"""
        # 負值
        data_negative = {
            "crawl_interval": -1
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersUpdateSchema.model_validate(data_negative)
        assert "crawl_interval: 必須大於 0" in str(exc_info.value)
        
        # 零值
        data_zero = {
            "crawl_interval": 0
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersUpdateSchema.model_validate(data_zero)
        assert "crawl_interval: 必須大於 0" in str(exc_info.value)
        
        # None值是允許的
        data_none = {
            "crawler_name": "test_crawler",
            "crawl_interval": None
        }
        schema = CrawlersUpdateSchema.model_validate(data_none)
        assert schema.crawl_interval is None
    
    def test_crawlers_update_is_active_validation(self):
        """測試更新是否啟用的驗證"""
        # 非布林值
        data_not_bool = {
            "is_active": "not_a_boolean"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersUpdateSchema.model_validate(data_not_bool)
        assert "is_active: 必須是布爾值" in str(exc_info.value)