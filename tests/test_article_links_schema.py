import pytest
from datetime import datetime
from src.models.article_links_schema import ArticleLinksCreateSchema, ArticleLinksUpdateSchema
from src.error.errors import ValidationError

class TestArticleLinksCreateSchema:
    """ArticleLinksCreateSchema 的測試類"""
    
    def test_valid_article_links_create(self):
        """測試有效的 ArticleLinksCreateSchema 資料"""
        valid_data = {
            "source_name": "範例新聞",
            "source_url": "https://example.com",
            "article_link": "https://example.com/article/1",
            "title": "測試文章",
            "summary": "測試摘要",
            "category": "測試分類",
            "published_age": "測試發佈年齡",
            "is_scraped": False
        }
        
        schema = ArticleLinksCreateSchema.model_validate(valid_data)
        assert schema.source_name == valid_data["source_name"]
        assert schema.source_url == valid_data["source_url"]
        assert schema.article_link == valid_data["article_link"]
        assert schema.title == valid_data["title"]
        assert schema.summary == valid_data["summary"]
        assert schema.category == valid_data["category"]
        assert schema.published_age == valid_data["published_age"]
        assert schema.is_scraped == valid_data["is_scraped"]

    def test_default_values(self):
        """測試預設值"""
        valid_data = {
            "source_name": "範例新聞",
            "source_url": "https://example.com",
            "article_link": "https://example.com/article/1",
            "title": "測試文章",
            "summary": "測試摘要",
            "category": "測試分類",
            "published_age": "測試發佈年齡",
        }
        
        schema = ArticleLinksCreateSchema.model_validate(valid_data)
        assert schema.is_scraped is False

    def test_article_link_validation(self):
        """測試文章連結驗證"""
        test_cases = [
            ("", "article_link: URL不能為空"),
            ("   ", "article_link: 無效的URL格式"),
            ("a" * 1001, "article_link: 長度不能超過 1000 字元")
        ]
        
        for value, expected_error in test_cases:
            with pytest.raises(ValidationError) as exc_info:
                ArticleLinksCreateSchema.model_validate({
                    "article_link": value,
                    "source_name": "範例新聞",
                    "source_url": "https://example.com",
                    "title": "測試文章",
                    "summary": "測試摘要",
                    "category": "測試分類",
                    "published_age": "測試發佈年齡",
                    "is_scraped": False
                })
            assert expected_error in str(exc_info.value)

    def test_source_name_validation(self):
        """測試來源名稱驗證"""
        test_cases = [
            ("", "source_name: 不能為空"),
            ("   ", "source_name: 不能為空"),
            ("a" * 51, "source_name: 長度不能超過 50 字元")
        ]
        
        for value, expected_error in test_cases:
            with pytest.raises(ValidationError) as exc_info:
                ArticleLinksCreateSchema.model_validate({
                    "article_link": "https://example.com/article/1",
                    "source_name": value,
                    "source_url": "https://example.com",
                    "title": "測試文章",
                    "summary": "測試摘要",
                    "category": "測試分類",
                    "published_age": "測試發佈年齡",
                    "is_scraped": False
                })
            assert expected_error in str(exc_info.value)

    def test_source_url_validation(self):
        """測試來源URL驗證"""
        test_cases = [
            ("", "source_url: URL不能為空"),
            ("   ", "source_url: 無效的URL格式"),
            ("a" * 1001, "source_url: 長度不能超過 1000 字元")
        ]
        
        for value, expected_error in test_cases:
            with pytest.raises(ValidationError) as exc_info:
                ArticleLinksCreateSchema.model_validate({
                    "article_link": "https://example.com/article/1",
                    "source_name": "範例新聞",
                    "source_url": value,
                    "title": "測試文章",
                    "summary": "測試摘要",
                    "category": "測試分類",
                    "published_age": "測試發佈年齡",
                    "is_scraped": False
                })
            assert expected_error in str(exc_info.value)

    def test_required_fields(self):
        """測試必填欄位"""
        required_fields = ['source_name', 'source_url', 'article_link']
        
        for field in required_fields:
            data = {
                "article_link": "https://example.com/article/1",
                "source_name": "範例新聞",
                "source_url": "https://example.com"
            }
            data.pop(field)
            
            with pytest.raises(ValidationError) as exc_info:
                ArticleLinksCreateSchema.model_validate(data)
            assert f"{field}: 不能為空" in str(exc_info.value)


class TestArticleLinksUpdateSchema:
    """ArticleLinksUpdateSchema 的測試類"""
    
    def test_valid_update(self):
        """測試有效的更新資料"""
        valid_data = {
            "source_name": "更新後的範例新聞",
            "source_url": "https://updated-example.com",
            "is_scraped": True
        }
        
        schema = ArticleLinksUpdateSchema.model_validate(valid_data)
        assert schema.source_name == valid_data["source_name"]
        assert schema.source_url == valid_data["source_url"]
        assert schema.is_scraped == valid_data["is_scraped"]

    def test_immutable_fields(self):
        """測試不可變欄位"""
        immutable_fields = {
            'created_at': datetime.now(),
            'id': 1,
            'article_link': "https://example.com/article/1"
        }
        
        for field, value in immutable_fields.items():
            with pytest.raises(ValidationError) as exc_info:
                ArticleLinksUpdateSchema.model_validate({
                    "source_name": "範例新聞",
                    field: value
                })
            assert f"不允許更新 {field} 欄位" in str(exc_info.value)

    def test_empty_update(self):
        """測試空更新"""
        with pytest.raises(ValidationError) as exc_info:
            ArticleLinksUpdateSchema.model_validate({})
        assert "必須提供至少一個要更新的欄位" in str(exc_info.value)

    def test_partial_update(self):
        """測試部分更新"""
        test_cases = [
            {"source_name": "新名稱"},
            {"source_url": "https://new-example.com"},
            {"is_scraped": True}
        ]
        
        for data in test_cases:
            schema = ArticleLinksUpdateSchema.model_validate(data)
            for key, value in data.items():
                assert getattr(schema, key) == value