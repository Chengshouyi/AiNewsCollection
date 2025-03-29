import pytest
from datetime import datetime, timezone
from src.models.articles_schema import ArticleCreateSchema, ArticleUpdateSchema
from src.error.errors import ValidationError

class TestArticleCreateSchema:
    """ArticleCreateSchema 的測試類"""
    
    def test_article_schema_with_valid_data(self):
        """測試有效的文章資料"""
        data = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "source": "test_source"
        }
        schema = ArticleCreateSchema.model_validate(data)
        assert schema.title == "測試文章"
        assert schema.link == "https://test.com/article"
        assert schema.source == "test_source"
    def test_missing_required_fields(self):
        """測試缺少必要欄位"""
        test_cases = [
            # 缺少 title
            {
                "link": "https://test.com/article",
                "published_at": datetime.now(timezone.utc).isoformat(), 
                "source": "test_source"
            },
            # 缺少 link
            {
                "title": "測試文章",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "source": "test_source"
            },
            # 缺少 published_at
            {
                "title": "測試文章",
                "link": "https://test.com/article", 
                "source": "test_source"
            },
            # 缺少 source
            {
                "title": "測試文章",
                "link": "https://test.com/article", 
                "published_at": datetime.now(timezone.utc).isoformat()
            }
        ]
        
        for test_case in test_cases:
            with pytest.raises(ValidationError) as exc_info:
                ArticleCreateSchema.model_validate(test_case)   
            missing_field = set(["title", "link", "published_at", "source"]) - set(test_case.keys())
            assert f"{list(missing_field)[0]}: 不能為空" in str(exc_info.value)


    def test_article_with_all_optional_fields(self):
        """測試包含所有選填欄位的文章資料"""
        data = {
            "title": "測試文章",
            "summary": "這是文章摘要",
            "content": "這是文章內容",
            "link": "https://test.com/article",
            "category": "測試",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "author": "測試作者",
            "source": "test_source",
            "article_type": "news",
            "tags": "tag1,tag2,tag3"
        }
        schema = ArticleCreateSchema.model_validate(data)
        assert schema.title == "測試文章"
        assert schema.summary == "這是文章摘要"
        assert schema.content == "這是文章內容"
        assert schema.link == "https://test.com/article"
        assert schema.category == "測試"
        assert schema.author == "測試作者"
        assert schema.source == "test_source"
        assert schema.article_type == "news"
        assert schema.tags == "tag1,tag2,tag3"
    
    # 標題欄位測試
    def test_article_title_empty_validation(self):
        """測試標題為空的驗證"""
        data = {
            "title": "",
            "link": "https://test.com/article",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "source": "test_source"
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleCreateSchema.model_validate(data)
        assert "title: 不能為空" in str(exc_info.value)
    
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
        assert "title: 長度不能超過 500 字元" in str(exc_info.value)
    
    def test_article_title_boundary_values(self):
        """測試標題長度的邊界值"""
        # 測試最短有效長度
        data_min = {
            "title": "a",
            "link": "https://test.com/article",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "source": "test_source"
        }
        schema_min = ArticleCreateSchema.model_validate(data_min)
        assert schema_min.title == "a"
        
        # 測試最長有效長度
        data_max = {
            "title": "a" * 500,
            "link": "https://test.com/article",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "source": "test_source"
        }
        schema_max = ArticleCreateSchema.model_validate(data_max)
        assert len(schema_max.title) == 500

    # 連結欄位測試
    def test_article_link_empty_validation(self):
        """測試連結為空的驗證"""
        data = {
            "title": "測試文章",
            "link": "",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "source": "test_source"
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleCreateSchema.model_validate(data)
        assert "link: URL不能為空" in str(exc_info.value)
    
    def test_article_link_too_long_validation(self):
        """測試連結過長的驗證"""
        data = {
            "title": "測試文章",
            "link": "a" * 1001,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "source": "test_source"
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleCreateSchema.model_validate(data)
        assert "link: 長度不能超過 1000 字元" in str(exc_info.value)
    
    def test_article_link_boundary_values(self):
        """測試連結長度的邊界值"""
        # 測試最短有效長度
        data_min = {
            "title": "測試文章",
            "link": "a",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "source": "test_source"
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleCreateSchema.model_validate(data_min)
        assert "link: 無效的URL格式" in str(exc_info.value)
        
        # 測試最長有效長度
        data_max = {
            "title": "測試文章",
            "link": "https://"+"a" * 1000,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "source": "test_source"
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleCreateSchema.model_validate(data_max)
        assert "link: 長度不能超過 1000 字元" in str(exc_info.value)

    # 摘要欄位測試
    def test_article_summary_too_long_validation(self):
        """測試摘要過長的驗證"""
        data = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "source": "test_source",
            "summary": "a" * 10001
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleCreateSchema.model_validate(data)
        assert "summary: 長度不能超過 10000 字元" in str(exc_info.value)
    
    def test_article_summary_boundary_values(self):
        """測試摘要長度的邊界值"""
        
        # 測試最長有效長度
        data_max = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "source": "test_source",
            "summary": "a" * 10000
        }
        schema_max = ArticleCreateSchema.model_validate(data_max)
        assert schema_max.summary is not None
        assert len(schema_max.summary) == 10000
    
    # 內容欄位測試
    def test_article_content_too_long_validation(self):
        """測試內容過長的驗證"""
        data = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "source": "test_source",
            "content": "a" * 65537
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleCreateSchema.model_validate(data)
        assert "content: 長度不能超過 65536 字元" in str(exc_info.value)
    
    def test_article_content_boundary_values(self):
        """測試內容長度的邊界值"""  
        # 測試最長有效長度
        data_max = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "source": "test_source",
            "content": "a" * 65536
        }
        schema_max = ArticleCreateSchema.model_validate(data_max)
        assert schema_max.content is not None
        assert len(schema_max.content) == 65536
    
    # 來源欄位測試
    def test_article_source_empty_validation(self):
        """測試來源為空的驗證"""
        data = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now(timezone.utc),
            "source": ""
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleCreateSchema.model_validate(data)
        assert "source: 不能為空" in str(exc_info.value)
    
    def test_article_source_too_long_validation(self):
        """測試來源過長的驗證"""
        data = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now(timezone.utc),
            "source": "a" * 51
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleCreateSchema.model_validate(data)
        assert "source: 長度不能超過 50 字元" in str(exc_info.value)
    
    def test_article_source_boundary_values(self):
        """測試來源長度的邊界值"""
        # 測試最短有效長度
        data_min = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now(timezone.utc),
            "source": "a"
        }
        schema_min = ArticleCreateSchema.model_validate(data_min)
        assert schema_min.source == "a"
        
        # 測試最長有效長度
        data_max = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now(timezone.utc),
            "source": "a" * 50
        }
        schema_max = ArticleCreateSchema.model_validate(data_max)
        assert len(schema_max.source) == 50
    
    # 發布時間欄位測試
    def test_article_published_at_empty_validation(self):
        """測試發布時間為空的驗證"""
        data = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": "",
            "source": "test_source"
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleCreateSchema.model_validate(data)
        assert "published_at: 無效的日期時間格式。請使用 ISO 格式" in str(exc_info.value)
    
    # 作者欄位測試
    def test_article_author_too_long_validation(self):
        """測試作者過長的驗證"""
        data = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now(timezone.utc),
            "source": "test_source",
            "author": "a" * 101
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleCreateSchema.model_validate(data)
        assert "author: 長度不能超過 100 字元" in str(exc_info.value)
    
    # 文章類型欄位測試
    def test_article_type_too_long_validation(self):
        """測試文章類型過長的驗證"""
        data = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now(timezone.utc),
            "source": "test_source",
            "article_type": "a" * 21
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleCreateSchema.model_validate(data)
        assert "article_type: 長度不能超過 20 字元" in str(exc_info.value)
    
    # 標籤欄位測試
    def test_article_tags_too_long_validation(self):
        """測試標籤過長的驗證"""
        data = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now(timezone.utc),
            "source": "test_source",
            "tags": "a" * 501
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleCreateSchema.model_validate(data)
        assert "tags: 長度不能超過 500 字元" in str(exc_info.value)

    def test_article_with_is_ai_related(self):
        """測試包含 is_ai_related 欄位的文章資料"""
        data = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now(timezone.utc),
            "source": "test_source",
            "is_ai_related": True
        }
        schema = ArticleCreateSchema.model_validate(data)
        assert schema.is_ai_related is True

    def test_article_with_is_ai_related_default(self):
        """測試 is_ai_related 欄位的預設值"""
        data = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "source": "test_source"
        }
        schema = ArticleCreateSchema.model_validate(data)
        assert schema.is_ai_related is False

    def test_article_with_invalid_is_ai_related(self):
        """測試 is_ai_related 欄位的無效值"""
        data = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now(timezone.utc),
            "source": "test_source",
            "is_ai_related": "not_a_boolean"  # 無效的布林值
        }
        with pytest.raises(Exception):  # Pydantic 會自動驗證型別
            ArticleCreateSchema.model_validate(data)


class TestArticleUpdateSchema:
    """ArticleUpdateSchema 的測試類"""
    
    def test_article_update_schema_with_valid_data(self):
        """測試有效的文章更新資料"""
        data = {
            "title": "更新的文章標題"
        }
        schema = ArticleUpdateSchema.model_validate(data)
        assert schema.title == "更新的文章標題"
    
    def test_article_update_with_multiple_fields(self):
        """測試更新多個欄位"""
        data = {
            "title": "更新的文章標題",
            "summary": "更新的文章摘要",
            "content": "更新的文章內容"
        }
        schema = ArticleUpdateSchema.model_validate(data)
        assert schema.title == "更新的文章標題"
        assert schema.summary == "更新的文章摘要"
        assert schema.content == "更新的文章內容"
    
    def test_update_with_no_fields(self):
        """測試沒有提供任何欄位的情況"""
        data = {}
        with pytest.raises(ValidationError) as exc_info:
            ArticleUpdateSchema.model_validate(data)
        assert "必須提供至少一個要更新的欄位" in str(exc_info.value)
    
    def test_update_created_at_not_allowed(self):
        """測試不允許更新 created_at 欄位"""
        data = {
            "title": "更新的文章標題",
            "created_at": datetime.now(timezone.utc)
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleUpdateSchema.model_validate(data)
        assert "不允許更新 created_at 欄位" in str(exc_info.value)
    
    # 更新標題欄位測試
    def test_update_title_empty_validation(self):
        """測試更新標題為空的驗證"""
        data = {
            "title": ""
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleUpdateSchema.model_validate(data)
        assert "title: 不能為空" in str(exc_info.value)
    
    def test_update_title_too_long_validation(self):
        """測試更新標題過長的驗證"""
        data = {
            "title": "a" * 501
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleUpdateSchema.model_validate(data)
        assert "title: 長度不能超過 500 字元" in str(exc_info.value)
    
    # 更新連結欄位測試
    def test_update_link_empty_validation(self):
        """測試更新連結為空的驗證"""
        data = {
            "link": ""
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleUpdateSchema.model_validate(data)
        assert "link: URL不能為空" in str(exc_info.value)
    
    def test_update_link_too_long_validation(self):
        """測試更新連結過長的驗證"""
        data = {
            "link": "a" * 1001
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleUpdateSchema.model_validate(data)
        assert "link: 長度不能超過 1000 字元" in str(exc_info.value)
    
    # 更新其他欄位的測試
    def test_update_summary_too_long_validation(self):
        """測試更新摘要過長的驗證"""
        data = {
            "summary": "a" * 10001
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleUpdateSchema.model_validate(data)
        assert "summary: 長度不能超過 10000 字元" in str(exc_info.value)
    
    def test_update_content_too_long_validation(self):
        """測試更新內容過長的驗證"""
        data = {
            "content": "a" * 65537
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleUpdateSchema.model_validate(data)
        assert "content: 長度不能超過 65536 字元" in str(exc_info.value)
    
    def test_update_source_empty_validation(self):
        """測試更新來源為空的驗證"""
        data = {
            "source": ""
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleUpdateSchema.model_validate(data)
        assert "source: 不能為空" in str(exc_info.value)
    
    def test_update_published_at_empty_validation(self):
        """測試更新發布時間為空的驗證"""
        data = {
            "published_at": ""
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleUpdateSchema.model_validate(data)
        assert "published_at: 無效的日期時間格式。請使用 ISO 格式" in str(exc_info.value)

    def test_update_is_ai_related(self):
        """測試更新 is_ai_related 欄位"""
        data = {
            "is_ai_related": True
        }
        schema = ArticleUpdateSchema.model_validate(data)
        assert schema.is_ai_related is True

    def test_update_is_ai_related_with_invalid_value(self):
        """測試使用無效值更新 is_ai_related 欄位"""
        data = {
            "is_ai_related": "not_a_boolean"  # 無效的布林值
        }
        with pytest.raises(Exception):  # Pydantic 會自動驗證型別
            ArticleUpdateSchema.model_validate(data)

    def test_update_multiple_fields_with_is_ai_related(self):
        """測試同時更新多個欄位包含 is_ai_related"""
        data = {
            "title": "更新的文章標題",
            "summary": "更新的文章摘要",
            "is_ai_related": True
        }
        schema = ArticleUpdateSchema.model_validate(data)
        assert schema.title == "更新的文章標題"
        assert schema.summary == "更新的文章摘要"
        assert schema.is_ai_related is True