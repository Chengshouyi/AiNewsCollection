import pytest
from datetime import datetime
from src.model.article_links_schema import ArticleLinksCreateSchema, ArticleLinksUpdateSchema
from src.model.base_model import ValidationError

class TestArticleLinksCreateSchema:
    def test_valid_article_links_create(self):
        """測試有效的 ArticleLinksCreateSchema 資料"""
        valid_data = {
            "article_link": "https://example.com/article/1",
            "source_name": "範例新聞",
            "source_url": "https://example.com",
            "is_scraped": False
        }
        
        schema = ArticleLinksCreateSchema.model_validate(valid_data)
        assert schema.article_link == valid_data["article_link"]
        assert schema.source_name == valid_data["source_name"]
        assert schema.source_url == valid_data["source_url"]
        assert schema.is_scraped == valid_data["is_scraped"]
    
    def test_empty_article_link(self):
        """測試空的文章連結"""
        invalid_data = {
            "article_link": "",
            "source_name": "範例新聞",
            "source_url": "https://example.com",
            "is_scraped": False
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ArticleLinksCreateSchema.model_validate(invalid_data)
        assert "article_link: do not be empty." in str(exc_info.value)
    
    def test_too_long_article_link(self):
        """測試過長的文章連結"""
        invalid_data = {
            "article_link": "a" * 1001,
            "source_name": "範例新聞",
            "source_url": "https://example.com",
            "is_scraped": False
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ArticleLinksCreateSchema.model_validate(invalid_data)
        assert "article_link: length must be between 1 and 1000." in str(exc_info.value)
    
    def test_empty_source_name(self):
        """測試空的來源名稱"""
        invalid_data = {
            "article_link": "https://example.com/article/1",
            "source_name": "",
            "source_url": "https://example.com",
            "is_scraped": False
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ArticleLinksCreateSchema.model_validate(invalid_data)
        assert "source_name: do not be empty." in str(exc_info.value)
    
    def test_too_long_source_name(self):
        """測試過長的來源名稱"""
        invalid_data = {
            "article_link": "https://example.com/article/1",
            "source_name": "a" * 51,
            "source_url": "https://example.com",
            "is_scraped": False
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ArticleLinksCreateSchema.model_validate(invalid_data)
        assert "source_name: length must be between 1 and 50." in str(exc_info.value)
    
    def test_empty_source_url(self):
        """測試空的來源URL"""
        invalid_data = {
            "article_link": "https://example.com/article/1",
            "source_name": "範例新聞",
            "source_url": "",
            "is_scraped": False
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ArticleLinksCreateSchema.model_validate(invalid_data)
        assert "source_url: do not be empty." in str(exc_info.value)
    
    def test_too_long_source_url(self):
        """測試過長的來源URL"""
        invalid_data = {
            "article_link": "https://example.com/article/1",
            "source_name": "範例新聞",
            "source_url": "a" * 1001,
            "is_scraped": False
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ArticleLinksCreateSchema.model_validate(invalid_data)
        assert "source_url: length must be between 1 and 1000." in str(exc_info.value)
    
    def test_missing_required_fields(self):
        """測試缺少必要欄位"""
        test_cases = [
            # 缺少 article_link
            {
                "source_name": "範例新聞",
                "source_url": "https://example.com",
                "is_scraped": False
            },
            # 缺少 source_name
            {
                "article_link": "https://example.com/article/1",
                "source_url": "https://example.com",
                "is_scraped": False
            },
            # 缺少 source_url
            {
                "article_link": "https://example.com/article/1",
                "source_name": "範例新聞",
                "is_scraped": False
            },
            # 缺少 is_scraped
            {
                "article_link": "https://example.com/article/1",
                "source_name": "範例新聞",
                "source_url": "https://example.com"
            }
        ]
        
        for invalid_data in test_cases:
            with pytest.raises(ValidationError) as exc_info:
                ArticleLinksCreateSchema.model_validate(invalid_data)
            missing_field = set(["article_link", "source_name", "source_url", "is_scraped"]) - set(invalid_data.keys())
            assert f"{list(missing_field)[0]}: do not be empty." in str(exc_info.value)


class TestArticleLinksUpdateSchema:
    def test_valid_article_links_update(self):
        """測試有效的 ArticleLinksUpdateSchema 資料"""
        valid_data = {
            "source_name": "更新後的範例新聞",
            "source_url": "https://updated-example.com",
            "is_scraped": True
        }
        
        schema = ArticleLinksUpdateSchema.model_validate(valid_data)
        assert schema.source_name == valid_data["source_name"]
        assert schema.source_url == valid_data["source_url"]
        assert schema.is_scraped == valid_data["is_scraped"]
    
    def test_update_article_link(self):
        """測試更新文章連結（不允許）"""
        invalid_data = {
            "article_link": "https://example.com/updated-article",
            "source_name": "範例新聞"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ArticleLinksUpdateSchema.model_validate(invalid_data)
        assert "do not allow to update article_link field." in str(exc_info.value)
    
    def test_update_created_at(self):
        """測試更新 created_at（不允許）"""
        invalid_data = {
            "source_name": "範例新聞",
            "created_at": datetime.now()
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ArticleLinksUpdateSchema.model_validate(invalid_data)
        assert "do not allow to update created_at field." in str(exc_info.value)
    
    def test_no_update_fields(self):
        """測試沒有提供更新欄位"""
        invalid_data = {}
        
        with pytest.raises(ValidationError) as exc_info:
            ArticleLinksUpdateSchema.model_validate(invalid_data)
        assert "must provide at least one field to update." in str(exc_info.value)
    
    def test_empty_source_name(self):
        """測試空的來源名稱"""
        invalid_data = {
            "source_name": "",
            "is_scraped": True
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ArticleLinksUpdateSchema.model_validate(invalid_data)
        assert "source_name: do not be empty" in str(exc_info.value)
    
    def test_too_long_source_name(self):
        """測試過長的來源名稱"""
        invalid_data = {
            "source_name": "a" * 51,
            "is_scraped": True
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ArticleLinksUpdateSchema.model_validate(invalid_data)
        assert "source_name: length must be between 1 and 50." in str(exc_info.value)
    
    def test_empty_source_url(self):
        """測試空的來源URL"""
        invalid_data = {
            "source_url": "",
            "is_scraped": True
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ArticleLinksUpdateSchema.model_validate(invalid_data)
        assert "source_url: do not be empty" in str(exc_info.value)
    
    def test_too_long_source_url(self):
        """測試過長的來源URL"""
        invalid_data = {
            "source_url": "a" * 1001,
            "is_scraped": True
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ArticleLinksUpdateSchema.model_validate(invalid_data)
        assert "source_url: length must be between 1 and 1000." in str(exc_info.value)
    
    def test_partial_update(self):
        """測試部分更新"""
        valid_data = {
            "is_scraped": True
        }
        
        schema = ArticleLinksUpdateSchema.model_validate(valid_data)
        assert schema.is_scraped == valid_data["is_scraped"]
        assert schema.source_name is None
        assert schema.source_url is None
        assert schema.article_link is None

    def test_whitespace_in_fields(self):
        """測試欄位中的空白"""
        invalid_data = {
            "source_name": "   ",
            "is_scraped": True
        }
        
        with pytest.raises( ValidationError) as exc_info:
            ArticleLinksUpdateSchema.model_validate(invalid_data)
        assert "source_name: do not be empty" in str(exc_info.value)