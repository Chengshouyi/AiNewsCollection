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
            "module_name": "test_module",
            "base_url": "https://example.com",
            "is_active": True,
            "config_file_name": "test_config.json",
            "crawler_type": "web"
        }
        schema = CrawlersCreateSchema.model_validate(data)
        assert schema.crawler_name == "test_crawler"
        assert schema.module_name == "test_module"
        assert schema.base_url == "https://example.com"
        assert schema.is_active is True
        assert schema.crawler_type == "web"
        assert schema.config_file_name == "test_config.json"
        assert schema.created_at is not None
    
    def test_crawlers_required_fields(self):
        """測試必填欄位的驗證"""
        # 缺少 crawler_name
        data1 = {
            "base_url": "https://example.com",
            "crawler_type": "web",
            "config_file_name": "test_config.json"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data1)
        assert "以下必填欄位缺失或值為空/空白" in str(exc_info.value)
        
        # 缺少 base_url
        data2 = {
            "crawler_name": "test_crawler",
            "crawler_type": "web",
            "config_file_name": "test_config.json"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data2)
        assert "base_url" in str(exc_info.value)

    
    def test_crawlers_crawler_name_validation(self):
        """測試爬蟲名稱的驗證"""
        # 空值
        data_empty = {
            "crawler_name": "",
            "base_url": "https://example.com",
            "config_file_name": "test_config.json",
            "crawler_type": "web"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data_empty)
        assert "以下必填欄位缺失或值為空/空白" in str(exc_info.value)
        
        # 過長
        data_too_long = {
            "crawler_name": "a" * 101,
            "module_name": "test_module",
            "base_url": "https://example.com",
            "crawler_type": "web",
            "config_file_name": "test_config.json"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data_too_long)
        assert "crawler_name: 長度不能超過 100 字元" in str(exc_info.value)
        
        # 邊界值
        data_min = {
            "crawler_name": "a",
            "module_name": "test_module",
            "base_url": "https://example.com",
            "crawler_type": "web",
            "config_file_name": "test_config.json"
        }
        schema_min = CrawlersCreateSchema.model_validate(data_min)
        assert schema_min.crawler_name == "a"
        
        data_max = {
            "crawler_name": "a" * 100,
            "module_name": "test_module",
            "base_url": "https://example.com",
            "crawler_type": "web",
            "config_file_name": "test_config.json"
        }
        schema_max = CrawlersCreateSchema.model_validate(data_max)
        assert len(schema_max.crawler_name) == 100
    
    def test_crawlers_base_url_validation(self):
        """測試爬取目標的驗證"""
        # 空值
        data_empty = {
            "crawler_name": "test_crawler",
            "base_url": "",
            "config_file_name": "test_config.json",
            "crawler_type": "web"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data_empty)
        assert "以下必填欄位缺失或值為空/空白" in str(exc_info.value)

        # 過長
        data_too_long = {
            "crawler_name": "test_crawler",
            "module_name": "test_module",
            "base_url": "http://example.com/" + "a" * 1000,
            "crawler_type": "web",
            "config_file_name": "test_config.json"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data_too_long)
        assert "base_url: 長度不能超過 1000 字元" in str(exc_info.value)

        # 邊界值
        data_max = {
            "crawler_name": "test_crawler",
            "module_name": "test_module",
            "base_url": "http://example.com/" + "a" * 980,  # 確保總長度不超過1000
            "crawler_type": "web",
            "config_file_name": "test_config.json"
        }
        schema_max = CrawlersCreateSchema.model_validate(data_max)
        assert schema_max.base_url == data_max["base_url"]

        # 無效的 URL 格式
        data_invalid_url = {
            "crawler_name": "test_crawler",
            "module_name": "test_module",
            "base_url": "invalid_url",
            "crawler_type": "web",
            "config_file_name": "test_config.json"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data_invalid_url)
        assert "base_url: 無效的URL格式" in str(exc_info.value)
    
    def test_crawlers_crawler_type_validation(self):
        """測試爬蟲類型的驗證"""
        # 空值
        data_empty = {
            "crawler_name": "test_crawler",
            "module_name": "test_module",
            "base_url": "https://example.com",
            "config_file_name": "test_config.json",
            "crawler_type": ""
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data_empty)
        assert "以下必填欄位缺失或值為空/空白" in str(exc_info.value)
        
        # 過長
        data_too_long = {
            "crawler_name": "test_crawler",
            "module_name": "test_module",
            "base_url": "https://example.com",
            "config_file_name": "test_config.json",
            "crawler_type": "a" * 101
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data_too_long)
        assert "crawler_type: 長度不能超過 100 字元" in str(exc_info.value)
    
    def test_crawlers_config_file_name_validation(self):
        """測試設定檔案名的驗證"""
        # 空值
        data_empty = {
            "crawler_name": "test_crawler",
            "base_url": "https://example.com",
            "crawler_type": "web"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data_empty)
        assert "以下必填欄位缺失或值為空/空白" in str(exc_info.value)

    def test_crawlers_is_active_validation(self):
        """測試是否啟用的驗證"""
        # 非布林值
        data_not_bool = {
            "crawler_name": "test_crawler",
            "module_name": "test_module",
            "base_url": "https://example.com",
            "crawler_type": "web",
            "config_file_name": "test_config.json",
            "is_active": "not_a_boolean"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data_not_bool)
        assert "is_active: 必須是布爾值" in str(exc_info.value)

    def test_missing_required_fields(self):
        """測試缺少必填欄位"""
        data = {
            "base_url": "https://example.com",
            "crawler_type": "rss",
            "config_file_name": "example_config.json"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data)
        assert "以下必填欄位缺失或值為空/空白" in str(exc_info.value)

    def test_crawler_name_empty_validation(self):
        """測試crawler_name為空的驗證"""
        data = {
            "crawler_name": "",
            "module_name": "test_module",
            "base_url": "https://example.com",
            "crawler_type": "rss",
            "config_file_name": "example_config.json"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data)
        assert "以下必填欄位缺失或值為空/空白" in str(exc_info.value)

    def test_base_url_empty_validation(self):
        """測試base_url為空的驗證"""
        data = {
            "crawler_name": "Example Crawler",
            "module_name": "test_module",
            "base_url": "",
            "crawler_type": "rss",
            "config_file_name": "example_config.json"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data)
        assert "以下必填欄位缺失或值為空/空白" in str(exc_info.value)

    def test_minimum_required_fields(self):
        """測試最少需要提供哪些字段"""
        data = {
            "crawler_name": "",  # 空字串
            "module_name": "test_module",
            "base_url": "https://example.com",
            "crawler_type": "rss",
            "config_file_name": "example_config.json"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data)
        assert "以下必填欄位缺失或值為空/空白" in str(exc_info.value)

    def test_crawler_type_empty_validation(self):
        """測試crawler_type為空的驗證"""
        data = {
            "crawler_name": "Example Crawler",
            "module_name": "test_module",
            "base_url": "https://example.com",
            "crawler_type": "",
            "config_file_name": "example_config.json"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data)
        assert "以下必填欄位缺失或值為空/空白" in str(exc_info.value)

    def test_config_file_name_empty_validation(self):
        """測試config_file_name為空的驗證"""
        data = {
            "crawler_name": "Example Crawler",
            "module_name": "test_module",
            "base_url": "https://example.com",
            "crawler_type": "rss",
            "config_file_name": ""
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersCreateSchema.model_validate(data)
        assert "以下必填欄位缺失或值為空/空白" in str(exc_info.value)

class TestCrawlersUpdateSchema:
    """CrawlersUpdateSchema 的測試類"""
    
    def test_crawlers_update_schema_with_valid_data(self):
        """測試有效的系統設定更新資料"""
        data = {
            "crawler_name": "test_crawler",
            "module_name": "test_module",
            "is_active": True
        }
        schema = CrawlersUpdateSchema.model_validate(data)
        assert schema.crawler_name == "test_crawler"
        assert schema.module_name == "test_module"
        assert schema.is_active is True
    
    def test_crawlers_update_schema_with_partial_data(self):
        """測試部分欄位更新"""
        # 只更新 crawler_name
        data1 = {
            "crawler_name": "updated_crawler",
            "module_name": "test_module"
        }
        schema1 = CrawlersUpdateSchema.model_validate(data1)
        assert schema1.crawler_name == "updated_crawler"
        assert schema1.module_name == "test_module"
        assert schema1.is_active is None
        
        
        # 只更新 is_active
        data3 = {
            "is_active": False,
            "module_name": "test_module"
        }
        schema3 = CrawlersUpdateSchema.model_validate(data3)
        assert schema3.crawler_name is None
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
            "crawler_name": None
        }
        schema = CrawlersUpdateSchema.model_validate(data_none)
        assert schema.crawler_name is None
    
    def test_crawlers_update_is_active_validation(self):
        """測試更新是否啟用的驗證"""
        # 非布林值
        data_not_bool = {
            "is_active": "not_a_boolean"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersUpdateSchema.model_validate(data_not_bool)
        assert "is_active: 必須是布爾值" in str(exc_info.value)

    def test_update_with_empty_values(self):
        """測試使用空值更新"""
        data = {
            "crawler_name": ""
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlersUpdateSchema.model_validate(data)
        assert "crawler_name: 不能為空" in str(exc_info.value)