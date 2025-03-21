from src.model.crawler_settings_schema import CrawlerSettingsCreateSchema, CrawlerSettingsUpdateSchema
from src.model.base_models import ValidationError
import pytest
from datetime import datetime

class TestCrawlerSettingsCreateSchema:
    """CrawlerSettingsCreateSchema 的測試類"""
    
    def test_crawler_settings_schema_with_valid_data(self):
        """測試有效的系統設定資料"""
        data = {
            "crawler_name": "test_crawler",
            "scrape_target": "https://example.com",
            "crawl_interval": 60,
            "is_active": True
        }
        schema = CrawlerSettingsCreateSchema.model_validate(data)
        assert schema.crawler_name == "test_crawler"
        assert schema.scrape_target == "https://example.com"
        assert schema.crawl_interval == 60
        assert schema.is_active is True
        assert schema.created_at is not None
    
    def test_crawler_settings_required_fields(self):
        """測試必填欄位的驗證"""
        # 缺少 crawler_name
        data1 = {
            "scrape_target": "https://example.com",
            "crawl_interval": 60
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsCreateSchema.model_validate(data1)
        assert "crawler_name: do not be empty." in str(exc_info.value)
        
        # 缺少 scrape_target
        data2 = {
            "crawler_name": "test_crawler",
            "crawl_interval": 60
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsCreateSchema.model_validate(data2)
        assert "scrape_target: do not be empty." in str(exc_info.value)
        
        # 缺少 crawl_interval
        data3 = {
            "crawler_name": "test_crawler",
            "scrape_target": "https://example.com"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsCreateSchema.model_validate(data3)
        assert "crawl_interval: do not be empty." in str(exc_info.value)
    
    def test_crawler_settings_crawler_name_empty_validation(self):
        """測試爬蟲名稱為空的驗證"""
        data = {
            "crawler_name": "",
            "scrape_target": "https://example.com",
            "crawl_interval": 60,
            "is_active": True
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsCreateSchema.model_validate(data)
        assert "crawler_name: do not be empty." in str(exc_info.value)
    
    def test_crawler_settings_crawler_name_too_long_validation(self):
        """測試爬蟲名稱過長的驗證"""
        data = {
            "crawler_name": "a" * 256,
            "scrape_target": "https://example.com",
            "crawl_interval": 60,
            "is_active": True
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsCreateSchema.model_validate(data)
        assert "crawler_name: length must be between 1 and 255." in str(exc_info.value)
    
    def test_crawler_settings_crawler_name_boundary_values(self):
        """測試爬蟲名稱長度的邊界值"""
        # 測試最短有效長度
        data_min = {
            "crawler_name": "a",
            "scrape_target": "https://example.com",
            "crawl_interval": 60,
            "is_active": True
        }
        schema_min = CrawlerSettingsCreateSchema.model_validate(data_min)
        assert schema_min.crawler_name == "a"
        
        # 測試最長有效長度
        data_max = {
            "crawler_name": "a" * 255,
            "scrape_target": "https://example.com",
            "crawl_interval": 60,
            "is_active": True
        }
        schema_max = CrawlerSettingsCreateSchema.model_validate(data_max)
        assert len(schema_max.crawler_name) == 255
    
    def test_crawler_settings_scrape_target_validation(self):
        """測試爬取目標的驗證"""
        # 測試空值
        data_empty = {
            "crawler_name": "test_crawler",
            "scrape_target": "",
            "crawl_interval": 60,
            "is_active": True
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsCreateSchema.model_validate(data_empty)
        assert "scrape_target: do not be empty." in str(exc_info.value)
        
        # 測試長度邊界值
        data_max = {
            "crawler_name": "test_crawler",
            "scrape_target": "a" * 1000,
            "crawl_interval": 60,
            "is_active": True
        }
        schema_max = CrawlerSettingsCreateSchema.model_validate(data_max)
        assert len(schema_max.scrape_target) == 1000
        
        # 測試超出最大長度
        data_too_long = {
            "crawler_name": "test_crawler",
            "scrape_target": "a" * 1001,
            "crawl_interval": 60,
            "is_active": True
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsCreateSchema.model_validate(data_too_long)
        assert "scrape_target: length must be between 1 and 1000." in str(exc_info.value)
    
    def test_crawler_settings_crawl_interval_negative_validation(self):
        """測試爬取間隔為負值的驗證"""
        data = {
            "crawler_name": "test_crawler",
            "scrape_target": "https://example.com",
            "crawl_interval": -1,
            "is_active": True
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsCreateSchema.model_validate(data)
        assert "crawl_interval: must be greater than 0." in str(exc_info.value)
    
    def test_crawler_settings_crawl_interval_zero_validation(self):
        """測試爬取間隔為零的驗證"""
        data = {
            "crawler_name": "test_crawler",
            "scrape_target": "https://example.com",
            "crawl_interval": 0,
            "is_active": True
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsCreateSchema.model_validate(data)
        assert "crawl_interval: must be greater than 0." in str(exc_info.value)
    
    def test_crawler_settings_is_active_type_validation(self):
        """測試是否啟用的類型驗證"""
        data = {
            "crawler_name": "test_crawler",
            "scrape_target": "https://example.com",
            "crawl_interval": 60,
            "is_active": "not_a_boolean"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsCreateSchema.model_validate(data)
        assert "is_active: must be a boolean value." in str(exc_info.value)

    def test_crawler_settings_created_at_empty_validation(self):
        """測試建立時間為空的驗證"""
        data = {
            "crawler_name": "test_crawler",
            "scrape_target": "https://example.com",
            "crawl_interval": 60,
            "is_active": True,
            "created_at": None
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsCreateSchema.model_validate(data)
        assert "created_at: do not be empty." in str(exc_info.value)

class TestCrawlerSettingsUpdateSchema:
    """CrawlerSettingsUpdateSchema 的測試類"""
    
    def test_crawler_settings_update_schema_with_valid_data(self):
        """測試有效的系統設定更新資料"""
        data = {
            "crawler_name": "test_crawler",
            "crawl_interval": 60,
            "is_active": True
        }
        schema = CrawlerSettingsUpdateSchema.model_validate(data)
        assert schema.crawler_name == "test_crawler"
        assert schema.crawl_interval == 60
        assert schema.is_active is True
    
    def test_crawler_settings_update_schema_with_partial_data(self):
        """測試部分欄位更新"""
        # 只更新 crawler_name
        data1 = {
            "crawler_name": "updated_crawler"
        }
        schema1 = CrawlerSettingsUpdateSchema.model_validate(data1)
        assert schema1.crawler_name == "updated_crawler"
        assert schema1.crawl_interval is None
        assert schema1.is_active is None
        
        # 只更新 crawl_interval
        data2 = {
            "crawl_interval": 120
        }
        schema2 = CrawlerSettingsUpdateSchema.model_validate(data2)
        assert schema2.crawler_name is None
        assert schema2.crawl_interval == 120
        assert schema2.is_active is None
        
        # 只更新 is_active
        data3 = {
            "is_active": False
        }
        schema3 = CrawlerSettingsUpdateSchema.model_validate(data3)
        assert schema3.crawler_name is None
        assert schema3.crawl_interval is None
        assert schema3.is_active is False
    
    def test_crawler_settings_update_no_fields_validation(self):
        """測試沒有提供更新欄位的驗證"""
        data = {}
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsUpdateSchema.model_validate(data)
        assert "must provide at least one field to update." in str(exc_info.value)
    
    def test_crawler_settings_update_created_at_validation(self):
        """測試不允許更新 created_at 的驗證"""
        data = {
            "crawler_name": "test_crawler",
            "created_at": datetime.now()
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsUpdateSchema.model_validate(data)
        assert "do not allow to update created_at field." in str(exc_info.value)
    
    def test_crawler_settings_update_crawler_name_validation(self):
        """測試更新爬蟲名稱的驗證"""
        # 空字串
        data_empty = {
            "crawler_name": ""
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsUpdateSchema.model_validate(data_empty)
        assert "crawler_name: do not be empty." in str(exc_info.value)
        
        # 過長
        data_too_long = {
            "crawler_name": "a" * 256
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsUpdateSchema.model_validate(data_too_long)
        assert "crawler_name: length must be between 1 and 255." in str(exc_info.value)
        
        # None值是允許的
        data_none = {
            "crawl_interval": 60,
            "crawler_name": None
        }
        schema = CrawlerSettingsUpdateSchema.model_validate(data_none)
        assert schema.crawler_name is None
    
    def test_crawler_settings_update_crawl_interval_validation(self):
        """測試更新爬取間隔的驗證"""
        # 負值
        data_negative = {
            "crawl_interval": -1
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsUpdateSchema.model_validate(data_negative)
        assert "crawl_interval: must be greater than 0." in str(exc_info.value)
        
        # 零值
        data_zero = {
            "crawl_interval": 0
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsUpdateSchema.model_validate(data_zero)
        assert "crawl_interval: must be greater than 0." in str(exc_info.value)
        
        # None值是允許的
        data_none = {
            "crawler_name": "test_crawler",
            "crawl_interval": None
        }
        schema = CrawlerSettingsUpdateSchema.model_validate(data_none)
        assert schema.crawl_interval is None
    
    def test_crawler_settings_update_is_active_validation(self):
        """測試更新是否啟用的驗證"""
        # 非布林值
        data_not_bool = {
            "is_active": "not_a_boolean"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsUpdateSchema.model_validate(data_not_bool)
        assert "is_active: must be a boolean value." in str(exc_info.value)