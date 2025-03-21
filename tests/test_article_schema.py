from datetime import datetime
import pytest
from src.model.article_schema import ArticleCreateSchema
from src.model.base_models import ValidationError

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
        with pytest.raises(ValidationError) as exc_info:
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
        assert "標題長度不能超過 500 個字元" in str(exc_info.value)
    
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
        with pytest.raises(ValidationError) as exc_info:
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
        assert "連結長度不能超過 1000 個字元" in str(exc_info.value)
    
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
            "summary": "a" * 10001
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleCreateSchema.model_validate(data)
        assert "摘要長度不能超過 10000 個字元" in str(exc_info.value)
    
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
            "summary": "a" * 10000
        }
        schema_max = ArticleCreateSchema.model_validate(data_max)
        assert len(schema_max.summary or "") == 10000
    
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
        assert "內容長度不能超過 65536 個字元" in str(exc_info.value)
    
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
        assert "來源長度不能超過 50 個字元" in str(exc_info.value)