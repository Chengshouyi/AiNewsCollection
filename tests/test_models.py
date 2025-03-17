import pytest
from datetime import datetime
from src.model.models import Article, SystemSettings
from src.model.article_schema import ArticleCreateSchema
from src.model.system_settings_schema import SystemSettingsCreateSchema
from pydantic import ValidationError

class TestArticleModel:
    """Article 模型的測試類"""
    
    def test_article_creation_with_required_fields_only(self):
        """測試只使用必填欄位創建 Article"""
        article = Article(
            title="測試文章",
            link="https://test.com/article",
            published_at=datetime.now().isoformat(),
            created_at=datetime.now()
        )
        
        assert article.title == "測試文章"
        assert article.link == "https://test.com/article"
        assert article.published_at is not None
        assert article.summary is None
        assert article.content is None
        assert article.source is None
        assert article.created_at is not None

    def test_article_repr(self):
        """測試 Article 的 __repr__ 方法"""
        article = Article(
            id=1,
            title="測試文章",
            link="https://test.com/article",
            published_at=datetime.now().isoformat()
        )
        
        assert repr(article) == "<Article(id=1, title='測試文章', link='https://test.com/article')>"


class TestArticleSchema:
    """ArticleCreateSchema 的測試類"""
    
    def test_article_schema_with_valid_data(self):
        """測試有效的文章資料"""
        data = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now().isoformat(),
            "source": "test_source"
        }
        schema = ArticleCreateSchema.model_validate(data)
        assert schema.title == "測試文章"
        assert schema.link == "https://test.com/article"
        assert schema.source == "test_source"
    
    def test_article_title_empty_validation(self):
        """測試標題為空的驗證"""
        data = {
            "title": "",
            "link": "https://test.com/article",
            "published_at": datetime.now().isoformat(),
            "source": "test_source"
        }
        with pytest.raises(ValueError) as exc_info:
            ArticleCreateSchema.model_validate(data)
        assert "標題不能為空" in str(exc_info.value)
    
    def test_article_title_too_long_validation(self):
        """測試標題過長的驗證"""
        data = {
            "title": "a" * 501,
            "link": "https://test.com/article",
            "published_at": datetime.now().isoformat(),
            "source": "test_source"
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleCreateSchema.model_validate(data)
        assert "String should have at most 500 characters" in str(exc_info.value)
    
    def test_article_title_boundary_values(self):
        """測試標題長度的邊界值"""
        # 測試最短有效長度
        data_min = {
            "title": "a",
            "link": "https://test.com/article",
            "published_at": datetime.now().isoformat(),
            "source": "test_source"
        }
        schema_min = ArticleCreateSchema.model_validate(data_min)
        assert schema_min.title == "a"
        
        # 測試最長有效長度
        data_max = {
            "title": "a" * 500,
            "link": "https://test.com/article",
            "published_at": datetime.now().isoformat(),
            "source": "test_source"
        }
        schema_max = ArticleCreateSchema.model_validate(data_max)
        assert len(schema_max.title) == 500

    def test_article_link_empty_validation(self):
        """測試連結為空的驗證"""
        data = {
            "title": "測試文章",
            "link": "",
            "published_at": datetime.now().isoformat(),
            "source": "test_source"
        }
        with pytest.raises(ValueError) as exc_info:
            ArticleCreateSchema.model_validate(data)
        assert "連結不能為空" in str(exc_info.value)
    
    def test_article_link_too_long_validation(self):
        """測試連結過長的驗證"""
        data = {
            "title": "測試文章",
            "link": "a" * 1001,
            "published_at": datetime.now().isoformat(),
            "source": "test_source"
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleCreateSchema.model_validate(data)
        assert "String should have at most 1000 characters" in str(exc_info.value)
    
    def test_article_link_boundary_values(self):
        """測試連結長度的邊界值"""
        # 測試最短有效長度
        data_min = {
            "title": "測試文章",
            "link": "a",
            "published_at": datetime.now().isoformat(),
            "source": "test_source"
        }
        schema_min = ArticleCreateSchema.model_validate(data_min)
        assert schema_min.link == "a"
        
        # 測試最長有效長度
        data_max = {
            "title": "測試文章",
            "link": "a" * 1000,
            "published_at": datetime.now().isoformat(),
            "source": "test_source"
        }
        schema_max = ArticleCreateSchema.model_validate(data_max)
        assert len(schema_max.link) == 1000

    def test_article_summary_too_long_validation(self):
        """測試摘要過長的驗證"""
        data = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now().isoformat(),
            "source": "test_source",
            "summary": "a" * 1025
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleCreateSchema.model_validate(data)
        assert "String should have at most 1024 characters" in str(exc_info.value)
    
    def test_article_summary_boundary_values(self):
        """測試摘要長度的邊界值"""
        # 測試最短有效長度
        data_empty = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now().isoformat(),
            "source": "test_source",
            "summary": ""
        }
        schema_empty = ArticleCreateSchema.model_validate(data_empty)
        assert schema_empty.summary == ""
        
        # 測試最長有效長度
        data_max = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now().isoformat(),
            "source": "test_source",
            "summary": "a" * 1024
        }
        schema_max = ArticleCreateSchema.model_validate(data_max)
        assert len(schema_max.summary or "") == 1024
    
    def test_article_content_too_long_validation(self):
        """測試內容過長的驗證"""
        data = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now().isoformat(),
            "source": "test_source",
            "content": "a" * 65537
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleCreateSchema.model_validate(data)
        assert "String should have at most 65536 characters" in str(exc_info.value)
    
    def test_article_content_boundary_values(self):
        """測試內容長度的邊界值"""
        # 測試最短有效長度
        data_empty = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now().isoformat(),
            "source": "test_source",
            "content": ""
        }
        schema_empty = ArticleCreateSchema.model_validate(data_empty)
        assert schema_empty.content == ""
        
        # 測試最長有效長度
        data_max = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now().isoformat(),
            "source": "test_source",
            "content": "a" * 65536
        }
        schema_max = ArticleCreateSchema.model_validate(data_max)
        assert len(schema_max.content or "") == 65536
    
    def test_article_source_too_long_validation(self):
        """測試來源過長的驗證"""
        data = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now().isoformat(),
            "source": "a" * 51
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleCreateSchema.model_validate(data)
        assert "String should have at most 50 characters" in str(exc_info.value)


class TestSystemSettingsModel:
    """SystemSettings 模型的測試類"""
    
    def test_system_settings_creation_with_required_fields(self):
        """測試使用必填欄位創建 SystemSettings"""
        settings = SystemSettings(
            crawler_name="test_crawler",
            crawl_interval=60,
            created_at=datetime.now(),
            is_active=True
        )
        
        assert settings.crawler_name == "test_crawler"
        assert settings.crawl_interval == 60
        assert settings.is_active is True
        assert settings.created_at is not None
        assert settings.updated_at is None
        assert settings.last_crawl_time is None
    
    def test_system_settings_repr(self):
        """測試 SystemSettings 的 __repr__ 方法"""
        settings = SystemSettings(
            id=1,
            crawler_name="test_crawler",
            crawl_interval=60,
            is_active=True
        )
        
        assert repr(settings) == "<SystemSettings(id=1, crawler_name='test_crawler', is_active=True)>"


class TestSystemSettingsSchema:
    """SystemSettingsCreateSchema 的測試類"""
    
    def test_system_settings_schema_with_valid_data(self):
        """測試有效的系統設定資料"""
        data = {
            "crawler_name": "test_crawler",
            "crawl_interval": 60,
            "is_active": True
        }
        schema = SystemSettingsCreateSchema.model_validate(data)
        assert schema.crawler_name == "test_crawler"
        assert schema.crawl_interval == 60
        assert schema.is_active is True
    
    def test_system_settings_crawler_name_empty_validation(self):
        """測試爬蟲名稱為空的驗證"""
        data = {
            "crawler_name": "",
            "crawl_interval": 60,
            "is_active": True
        }
        with pytest.raises(ValueError) as exc_info:
            SystemSettingsCreateSchema.model_validate(data)
        assert "爬蟲名稱不能為空" in str(exc_info.value)
    
    def test_system_settings_crawler_name_too_long_validation(self):
        """測試爬蟲名稱過長的驗證"""
        data = {
            "crawler_name": "a" * 256,
            "crawl_interval": 60,
            "is_active": True
        }
        with pytest.raises(ValueError) as exc_info:
            SystemSettingsCreateSchema.model_validate(data)
        assert "爬蟲名稱長度必須在1到255個字符之間" in str(exc_info.value)
    
    def test_system_settings_crawler_name_boundary_values(self):
        """測試爬蟲名稱長度的邊界值"""
        # 測試最短有效長度
        data_min = {
            "crawler_name": "a",
            "crawl_interval": 60,
            "is_active": True
        }
        schema_min = SystemSettingsCreateSchema.model_validate(data_min)
        assert schema_min.crawler_name == "a"
        
        # 測試最長有效長度
        data_max = {
            "crawler_name": "a" * 255,
            "crawl_interval": 60,
            "is_active": True
        }
        schema_max = SystemSettingsCreateSchema.model_validate(data_max)
        assert len(schema_max.crawler_name) == 255
    
    def test_system_settings_crawl_interval_negative_validation(self):
        """測試爬取間隔為負值的驗證"""
        data = {
            "crawler_name": "test_crawler",
            "crawl_interval": -1,
            "is_active": True
        }
        with pytest.raises(ValueError) as exc_info:
            SystemSettingsCreateSchema.model_validate(data)
        assert "爬取間隔必須大於0" in str(exc_info.value)
    
    def test_system_settings_crawl_interval_zero_validation(self):
        """測試爬取間隔為零的驗證"""
        data = {
            "crawler_name": "test_crawler",
            "crawl_interval": 0,
            "is_active": True
        }
        with pytest.raises(ValueError) as exc_info:
            SystemSettingsCreateSchema.model_validate(data)
        assert "爬取間隔必須大於0" in str(exc_info.value)
    
    def test_system_settings_is_active_type_validation(self):
        """測試是否啟用的類型驗證"""
        data = {
            "crawler_name": "test_crawler",
            "crawl_interval": 60,
            "is_active": "not_a_boolean"
        }
        with pytest.raises(ValueError) as exc_info:
            SystemSettingsCreateSchema.model_validate(data)
        assert "is_active必須是布林值" in str(exc_info.value)