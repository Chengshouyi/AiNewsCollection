from src.model.crawler_settings_schema import CrawlerSettingsCreateSchema,CrawlerSettingsUpdateSchema
from src.model.base_models import ValidationError
import pytest

class TestCrawlerSettingsSchema:
    """CrawlerSettingsCreateSchema 的測試類"""
    
    def test_crawler_settings_schema_with_valid_data(self):
        """測試有效的系統設定資料"""
        data = {
            "crawler_name": "test_crawler",
            "crawl_interval": 60,
            "is_active": True
        }
        schema = CrawlerSettingsCreateSchema.model_validate(data)
        assert schema.crawler_name == "test_crawler"
        assert schema.crawl_interval == 60
        assert schema.is_active is True
    
    def test_crawler_settings_crawler_name_empty_validation(self):
        """測試爬蟲名稱為空的驗證"""
        data = {
            "crawler_name": "",
            "crawl_interval": 60,
            "is_active": True
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsCreateSchema.model_validate(data)
        assert "爬蟲名稱不能為空" in str(exc_info.value)
    
    def test_crawler_settings_crawler_name_too_long_validation(self):
        """測試爬蟲名稱過長的驗證"""
        data = {
            "crawler_name": "a" * 256,
            "crawl_interval": 60,
            "is_active": True
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsCreateSchema.model_validate(data)
        assert "爬蟲名稱長度必須在1到255個字符之間" in str(exc_info.value)
    
    def test_crawler_settings_crawler_name_boundary_values(self):
        """測試爬蟲名稱長度的邊界值"""
        # 測試最短有效長度
        data_min = {
            "crawler_name": "a",
            "crawl_interval": 60,
            "is_active": True
        }
        schema_min = CrawlerSettingsCreateSchema.model_validate(data_min)
        assert schema_min.crawler_name == "a"
        
        # 測試最長有效長度
        data_max = {
            "crawler_name": "a" * 255,
            "crawl_interval": 60,
            "is_active": True
        }
        schema_max = CrawlerSettingsCreateSchema.model_validate(data_max)
        assert len(schema_max.crawler_name) == 255
    
    def test_crawler_settings_crawl_interval_negative_validation(self):
        """測試爬取間隔為負值的驗證"""
        data = {
            "crawler_name": "test_crawler",
            "crawl_interval": -1,
            "is_active": True
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsCreateSchema.model_validate(data)
        assert "爬取間隔必須大於0" in str(exc_info.value)
    
    def test_crawler_settings_crawl_interval_zero_validation(self):
        """測試爬取間隔為零的驗證"""
        data = {
            "crawler_name": "test_crawler",
            "crawl_interval": 0,
            "is_active": True
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsCreateSchema.model_validate(data)
        assert "爬取間隔必須大於0" in str(exc_info.value)
    
    def test_crawler_settings_is_active_type_validation(self):
        """測試是否啟用的類型驗證"""
        data = {
            "crawler_name": "test_crawler",
            "crawl_interval": 60,
            "is_active": "not_a_boolean"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsCreateSchema.model_validate(data)
        assert "is_active必須是布林值" in str(exc_info.value)

    def test_crawler_settings_created_at_empty_validation(self):
        """測試建立時間為空的驗證"""
        data = {
            "crawler_name": "test_crawler",
            "crawl_interval": 60,
            "is_active": True,
            "created_at": None
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerSettingsCreateSchema.model_validate(data)
        assert "建立時間不能為空" in str(exc_info.value)
    
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