import pytest
from datetime import datetime, timezone
from src.models.articles_schema import ArticleCreateSchema, ArticleUpdateSchema
from src.models.articles_model import ArticleScrapeStatus
from src.error.errors import ValidationError

class TestArticleCreateSchema:
    """ArticleCreateSchema 的測試類"""
    
    def test_article_schema_with_valid_data(self):
        """測試有效的文章資料"""
        data = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "source": "test_source",
            "source_url": "https://test.com/article",
            "summary": "這是文章摘要",
            "content": "這是文章內容",
            "category": "測試",
            "author": "測試作者",
            "article_type": "news",
            "tags": "tag1,tag2,tag3",
            "is_ai_related": True,
            "is_scraped": True,
            "scrape_status": ArticleScrapeStatus.PENDING,
            "scrape_error": None,
            "last_scrape_attempt": None,
            "task_id": None
        }
        schema = ArticleCreateSchema.model_validate(data)
        assert schema.title == "測試文章"
        assert schema.link == "https://test.com/article"
        assert schema.source == "test_source"
        assert schema.source_url == "https://test.com/article"
        assert schema.summary == "這是文章摘要"
        assert schema.content == "這是文章內容"
        assert schema.category == "測試"
        assert schema.author == "測試作者"
        assert schema.article_type == "news"
        assert schema.tags == "tag1,tag2,tag3"
        assert schema.is_ai_related is True
        assert schema.is_scraped is True
        assert schema.scrape_status == ArticleScrapeStatus.PENDING
        assert schema.scrape_error is None
        assert schema.last_scrape_attempt is None
        assert schema.task_id is None

    def test_missing_required_fields(self):
        """測試缺少必要欄位"""
        base_data = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "source": "test_source",
            "source_url": "https://test.com/article",
            "summary": "這是文章摘要",
            "content": "這是文章內容",
            "category": "測試",
            "author": "測試作者",
            "article_type": "news",
            "tags": "tag1,tag2,tag3",
            "is_ai_related": True,
            "is_scraped": True,
            "scrape_status": ArticleScrapeStatus.PENDING,
            "scrape_error": None,
            "last_scrape_attempt": None,
            "task_id": None
        }
        required_fields = ArticleCreateSchema.get_required_fields()
        
        test_cases = []
        for field in required_fields:
            case = base_data.copy()
            del case[field]
            test_cases.append(case)

        for i, test_case in enumerate(test_cases):
            with pytest.raises(ValidationError) as exc_info:
                ArticleCreateSchema.model_validate(test_case)
            
            # 驗證錯誤訊息包含任何「不能為空」的提示
            error_message = str(exc_info.value)
            # 檢查錯誤訊息是否包含遺失的欄位名稱和錯誤訊息
            missing_field = required_fields[i]
            assert f"以下必填欄位缺失或值為空/空白:" in error_message, f"測試案例 {i+1}: 錯誤訊息應提示欄位缺失或為空"
            assert missing_field in error_message, f"測試案例 {i+1}: 錯誤訊息應包含遺失的欄位 {missing_field}"

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
            "source_url": "https://test.com/article",
            "article_type": "news",
            "tags": "tag1,tag2,tag3",
            "is_ai_related": True,
            "is_scraped": True,
            "scrape_status": ArticleScrapeStatus.PENDING,
            "scrape_error": None,
            "last_scrape_attempt": None,
            "task_id": None
        }
        schema = ArticleCreateSchema.model_validate(data)
        assert schema.title == "測試文章"
        assert schema.summary == "這是文章摘要"
        assert schema.content == "這是文章內容"
        assert schema.link == "https://test.com/article"
        assert schema.category == "測試"
        assert schema.author == "測試作者"
        assert schema.source == "test_source"
        assert schema.source_url == "https://test.com/article"
        assert schema.article_type == "news"
        assert schema.tags == "tag1,tag2,tag3"
        assert schema.is_ai_related is True
        assert schema.is_scraped is True
        assert schema.scrape_status == ArticleScrapeStatus.PENDING
        assert schema.scrape_error is None
        assert schema.last_scrape_attempt is None
        assert schema.task_id is None
        # 標題欄位測試
        def test_article_title_empty_validation(self):
            """測試標題為空的驗證"""
            data = {
                "title": "",
                "link": "https://test.com/article",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "source": "test_source",
                "source_url": "https://test.com/article",
                "summary": "這是文章摘要",
                "content": "這是文章內容",
                "category": "測試",
                "author": "測試作者",
                "article_type": "news",
                "tags": "tag1,tag2,tag3",
                "is_ai_related": True,
                "is_scraped": True,
                "scrape_status": ArticleScrapeStatus.PENDING,
                "scrape_error": None,
                "last_scrape_attempt": None,
                "task_id": None
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
                "source": "test_source",
                "source_url": "https://test.com/article",
                "summary": "這是文章摘要",
                "content": "這是文章內容",
                "category": "測試",
                "author": "測試作者",
                "article_type": "news",
                "tags": "tag1,tag2,tag3",
                "is_ai_related": True,
                "is_scraped": True,
                "scrape_status": ArticleScrapeStatus.PENDING,
                "scrape_error": None,
                "last_scrape_attempt": None,
                "task_id": None
            }
            with pytest.raises(ValidationError) as exc_info:
                ArticleCreateSchema.model_validate(data)
            assert "link: URL不能為空" in str(exc_info.value)
        
        def test_article_title_boundary_values(self):
            """測試標題長度的邊界值"""
            # 測試最短有效長度
            data_min = {
                "title": "a",
                "link": "https://test.com/article",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "source": "test_source",
                "source_url": "https://test.com/article",
                "summary": "這是文章摘要",
                "content": "這是文章內容",
                "category": "測試",
                "author": "測試作者",
                "article_type": "news",
                "tags": "tag1,tag2,tag3",
                "is_ai_related": True,
                "is_scraped": True,
                "scrape_status": ArticleScrapeStatus.PENDING,
                "scrape_error": None,
                "last_scrape_attempt": None,
                "task_id": None
            }
            schema_min = ArticleCreateSchema.model_validate(data_min)
            assert schema_min.title == "a"
            
            # 測試最長有效長度
            data_max = {
                "title": "a" * 500,
                "link": "https://test.com/article",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "source": "test_source",
                "source_url": "https://test.com/article",
                "summary": "這是文章摘要",
                "content": "這是文章內容",
                "category": "測試",
                "author": "測試作者",
                "article_type": "news",
                "tags": "tag1,tag2,tag3",
                "is_ai_related": True,
                "is_scraped": True,
                "scrape_status": ArticleScrapeStatus.PENDING,
                "scrape_error": None,
                "last_scrape_attempt": None,
                "task_id": None
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
                "source": "test_source",
                "source_url": "https://test.com/article",
                "summary": "這是文章摘要",
                "content": "這是文章內容",
                "category": "測試",
                "author": "測試作者",
                "article_type": "news",
                "tags": "tag1,tag2,tag3",
                "is_ai_related": True,
                "is_scraped": True,
                "scrape_status": ArticleScrapeStatus.PENDING, 
                "scrape_error": None,
                "last_scrape_attempt": None,
                "task_id": None
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
                "source": "test_source",
                "source_url": "https://test.com/article",
                "summary": "這是文章摘要",
                "content": "這是文章內容",
                "category": "測試",
                "author": "測試作者",
                "article_type": "news",
                "tags": "tag1,tag2,tag3",
                "is_ai_related": True,
                "is_scraped": True,
                "scrape_status": ArticleScrapeStatus.PENDING,
                "scrape_error": None,
                "last_scrape_attempt": None,
                "task_id": None
            }
            with pytest.raises(ValidationError) as exc_info:
                ArticleCreateSchema.model_validate(data)
            assert "source: 不能為空" in str(exc_info.value)
        
        def test_article_link_boundary_values(self):
            """測試連結長度的邊界值"""
            # 測試最短有效長度
            data_min = {
                "title": "測試文章",
                "link": "a",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "source": "test_source",
                "source_url": "https://test.com/article",
                "summary": "這是文章摘要",
                "content": "這是文章內容",
                "category": "測試",
                "author": "測試作者",
                "article_type": "news",
                "tags": "tag1,tag2,tag3",
                "is_ai_related": True,
                "is_scraped": True,
                "scrape_status": ArticleScrapeStatus.PENDING,
                "scrape_error": None,
                "last_scrape_attempt": None,
                "task_id": None
            }
            with pytest.raises(ValidationError) as exc_info:
                ArticleCreateSchema.model_validate(data_min)
            assert "link: 無效的URL格式" in str(exc_info.value)
            
            # 測試最長有效長度
            data_max = {
                "title": "測試文章",
                "link": "https://"+"a" * 1000,
                "published_at": datetime.now(timezone.utc).isoformat(),
                "source": "test_source",
                "source_url": "https://test.com/article",
                "summary": "這是文章摘要",
                "content": "這是文章內容",
                "category": "測試",
                "author": "測試作者",
                "article_type": "news",
                "tags": "tag1,tag2,tag3",
                "is_ai_related": True,
                "is_scraped": True,
                "scrape_status": ArticleScrapeStatus.PENDING,
                "scrape_error": None,
                "last_scrape_attempt": None,
                "task_id": None
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
                "source_url": "https://test.com/article",
                "summary": "a" * 10001,
                "content": "這是文章內容",
                "category": "測試",
                "author": "測試作者",
                "article_type": "news",
                "tags": "tag1,tag2,tag3",
                "is_ai_related": True,
                "is_scraped": True,
                "scrape_status": ArticleScrapeStatus.PENDING,
                "scrape_error": None,
                "last_scrape_attempt": None,
                "task_id": None
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
                "source_url": "https://test.com/article",
                "summary": "a" * 10000,
                "content": "這是文章內容",
                "category": "測試",
                "author": "測試作者",
                "article_type": "news",
                "tags": "tag1,tag2,tag3",
                "is_ai_related": True,
                "is_scraped": True,
                "scrape_status": ArticleScrapeStatus.PENDING,
                "scrape_error": None,
                "last_scrape_attempt": None,
                "task_id": None
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
                "source_url": "https://test.com/article",
                "summary": "這是文章摘要",
                "content": "a" * 65537,
                "category": "測試",
                "author": "測試作者",
                "article_type": "news",
                "tags": "tag1,tag2,tag3",
                "is_ai_related": True,
                "is_scraped": True,
                "scrape_status": ArticleScrapeStatus.PENDING,
                "scrape_error": None,
                "last_scrape_attempt": None,
                "task_id": None
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
                "source_url": "https://test.com/article",
                "summary": "這是文章摘要",
                "content": "a" * 65536,
                "category": "測試",
                "author": "測試作者",
                "article_type": "news",
                "tags": "tag1,tag2,tag3",
                "is_ai_related": True,
                "is_scraped": True,
                "scrape_status": ArticleScrapeStatus.PENDING,
                "scrape_error": None,
                "last_scrape_attempt": None,
                "task_id": None
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
                "source": "",
                "source_url": "https://test.com/article",
                "summary": "這是文章摘要",
                "content": "這是文章內容",
                "category": "測試",
                "author": "測試作者",
                "article_type": "news",
                "tags": "tag1,tag2,tag3",
                "is_ai_related": True,
                "is_scraped": True,
                "scrape_status": ArticleScrapeStatus.PENDING,
                "scrape_error": None,
                "last_scrape_attempt": None,
                "task_id": None
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
                "source": "a" * 51,
                "source_url": "https://test.com/article",
                "summary": "這是文章摘要",
                "content": "這是文章內容",
                "category": "測試",
                "author": "測試作者",
                "article_type": "news",
                "tags": "tag1,tag2,tag3",
                "is_ai_related": True,
                "is_scraped": True,
                "scrape_status": ArticleScrapeStatus.PENDING,
                "scrape_error": None,
                "last_scrape_attempt": None,
                "task_id": None
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
                "source": "a",
                "source_url": "https://test.com/article",
                "summary": "這是文章摘要",
                "content": "這是文章內容",
                "category": "測試",
                "author": "測試作者",
                "article_type": "news",
                "tags": "tag1,tag2,tag3",
                "is_ai_related": True,
                "is_scraped": True,
                "scrape_status": ArticleScrapeStatus.PENDING,
                "scrape_error": None,
                "last_scrape_attempt": None,
                "task_id": None
            }
            schema_min = ArticleCreateSchema.model_validate(data_min)
            assert schema_min.source == "a"
            
            # 測試最長有效長度
            data_max = {
                "title": "測試文章",
                "link": "https://test.com/article",
                "published_at": datetime.now(timezone.utc),
                "source": "a" * 50,
                "source_url": "https://test.com/article",
                "summary": "這是文章摘要",
                "content": "這是文章內容",
                "category": "測試",
                "author": "測試作者",
                "article_type": "news",
                "tags": "tag1,tag2,tag3",
                "is_ai_related": True,
                "is_scraped": True,
                "scrape_status": ArticleScrapeStatus.PENDING,
                "scrape_error": None,
                "last_scrape_attempt": None,
                "task_id": None
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
                "source": "test_source",
                "source_url": "https://test.com/article",
                "summary": "這是文章摘要",
                "content": "這是文章內容",
                "category": "測試",
                "author": "測試作者",
                "article_type": "news",
                "tags": "tag1,tag2,tag3",
                "is_ai_related": True,
                "is_scraped": True,
                "scrape_status": ArticleScrapeStatus.PENDING,
                "scrape_error": None,
                "last_scrape_attempt": None,
                "task_id": None
            }
            with pytest.raises(ValidationError) as exc_info:
                ArticleCreateSchema.model_validate(data)
            assert "published_at: 不能為空" in str(exc_info.value)
        
        # 作者欄位測試
        def test_article_author_too_long_validation(self):
            """測試作者過長的驗證"""
            data = {
                "title": "測試文章",
                "link": "https://test.com/article",
                "published_at": datetime.now(timezone.utc),
                "source": "test_source",
                "source_url": "https://test.com/article",
                "summary": "這是文章摘要",
                "content": "這是文章內容",
                "category": "測試",
                "author": "a" * 101,
                "article_type": "news",
                "tags": "tag1,tag2,tag3",
                "is_ai_related": True,
                "is_scraped": True,
                "scrape_status": ArticleScrapeStatus.PENDING,
                "scrape_error": None,
                "last_scrape_attempt": None,
                "task_id": None
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
                "source_url": "https://test.com/article",
                "summary": "這是文章摘要",
                "content": "這是文章內容",
                "category": "測試",
                "author": "測試作者",
                "article_type": "a" * 21,
                "tags": "tag1,tag2,tag3",
                "is_ai_related": True,
                "is_scraped": True,
                "scrape_status": ArticleScrapeStatus.PENDING,
                "scrape_error": None,
                "last_scrape_attempt": None,
                "task_id": None
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
                "source_url": "https://test.com/article",
                "summary": "這是文章摘要",
                "content": "這是文章內容",
                "category": "測試",
                "author": "測試作者",
                "article_type": "news",
                "tags": "a" * 501,
                "is_ai_related": True,
                "is_scraped": True,
                "scrape_status": ArticleScrapeStatus.PENDING,
                "scrape_error": None,
                "last_scrape_attempt": None,
                "task_id": None
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
                "source_url": "https://test.com/article",
                "summary": "這是文章摘要",
                "content": "這是文章內容",
                "category": "測試",
                "author": "測試作者",
                "article_type": "news",
                "tags": "tag1,tag2,tag3",
                "is_ai_related": True,
                "is_scraped": True,
                "scrape_status": ArticleScrapeStatus.PENDING,
                "scrape_error": None,
                "last_scrape_attempt": None,
                "task_id": None
            }
            schema = ArticleCreateSchema.model_validate(data)
            assert schema.is_ai_related is True


        def test_article_with_invalid_is_ai_related(self):
            """測試 is_ai_related 欄位的無效值"""
            data = {
                "title": "測試文章",
                "link": "https://test.com/article",
                "published_at": datetime.now(timezone.utc),
                "source": "test_source",
                "source_url": "https://test.com/article",
                "summary": "這是文章摘要",
                "content": "這是文章內容",
                "category": "測試",
                "author": "測試作者",
                "article_type": "news",
                "tags": "tag1,tag2,tag3",
                "is_ai_related": "not_a_boolean", # 無效的布林值
                "is_scraped": True,
                "scrape_status": ArticleScrapeStatus.PENDING,
                "scrape_error": None,
                "last_scrape_attempt": None,
                "task_id": None
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
        assert "published_at: 不能為空" in str(exc_info.value)

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

    def test_update_new_fields(self):
        """測試更新新增的欄位 (scrape_error, last_scrape_attempt, task_id)"""
        now = datetime.now(timezone.utc)
        data = {
            "scrape_error": "測試錯誤訊息",
            "last_scrape_attempt": now,
            "task_id": 123
        }
        schema = ArticleUpdateSchema.model_validate(data)
        assert schema.scrape_error == "測試錯誤訊息"
        assert schema.last_scrape_attempt == now
        assert schema.task_id == 123

    def test_update_scrape_error_too_long_validation(self):
        """測試更新 scrape_error 過長的驗證"""
        data = {
            "scrape_error": "a" * 1001
        }
        with pytest.raises(ValidationError) as exc_info:
            ArticleUpdateSchema.model_validate(data)
        assert "scrape_error: 長度不能超過 1000 字元" in str(exc_info.value)

    def test_update_task_id_with_invalid_value(self):
        """測試更新 task_id 欄位的無效值"""
        data = {
            "task_id": "not_an_integer"  # 無效的整數值
        }
        with pytest.raises(Exception):  # Pydantic 會自動驗證型別
            ArticleUpdateSchema.model_validate(data)

    def test_get_updated_fields(self):
        """測試 get_updated_fields 方法包含所有需要的欄位"""
        updated_fields = ArticleUpdateSchema.get_updated_fields()
        
        # 檢查所有必須包含的欄位
        required_fields = [
            'title', 'summary', 'content', 'source', 'source_url', 
            'published_at', 'category', 'author', 'article_type', 
            'tags', 'is_ai_related', 'is_scraped', 'scrape_status', 
            'scrape_error', 'last_scrape_attempt', 'task_id', 'updated_at'
        ]
        
        for field in required_fields:
            assert field in updated_fields, f"欄位 {field} 應該存在於 updated_fields 列表中"

    def test_update_immutable_fields_not_allowed(self):
        """測試不允許更新不可變欄位 (created_at, link)"""
        immutable_fields_test_cases = [
            {"created_at": datetime.now(timezone.utc)},
            {"link": "https://new-link.com"}
        ]
        
        for field_data in immutable_fields_test_cases:
            field_name = list(field_data.keys())[0]
            data = {
                "title": "更新的文章標題",
                **field_data
            }
            with pytest.raises(ValidationError) as exc_info:
                ArticleUpdateSchema.model_validate(data)
            assert f"不允許更新 {field_name} 欄位" in str(exc_info.value), f"更新 {field_name} 應該引發錯誤"