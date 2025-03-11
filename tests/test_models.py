import pytest
from datetime import datetime
from src.model.models import Article, SystemSettings

class TestArticleModel:
    """Article 模型的測試類"""
    
    def test_article_creation_with_required_fields_only(self):
        """測試只使用必填欄位創建 Article"""
        article = Article(
            title="測試文章",
            link="https://test.com/article",
            published_at=datetime.now(),
            created_at=datetime.now()
        )
        
        assert article.title == "測試文章"
        assert article.link == "https://test.com/article"
        assert article.published_at is not None
        assert article.summary is None
        assert article.content is None
        assert article.source is None
        assert article.updated_at is None
        assert article.created_at is not None
    def test_article_title_empty_validation(self):
        """測試標題為空的驗證"""
        with pytest.raises(ValueError, match="標題長度需在 1 到 255 個字元之間"):
            Article(
                title="",
                link="https://test.com/article",
                published_at=datetime.now()
            )
    
    def test_article_title_too_long_validation(self):
        """測試標題過長的驗證"""
        with pytest.raises(ValueError, match="標題長度需在 1 到 255 個字元之間"):
            Article(
                title="a" * 256,
                link="https://test.com/article",
                published_at=datetime.now()
            )
    
    def test_article_title_boundary_values(self):
        """測試標題長度的邊界值"""
        # 測試最短有效長度
        article_min = Article(
            title="a",
            link="https://test.com/article",
            published_at=datetime.now()
        )
        assert article_min.title == "a"
        
        # 測試最長有效長度
        article_max = Article(
            title="a" * 255,
            link="https://test.com/article",
            published_at=datetime.now()
        )
        assert len(article_max.title) == 255

    def test_article_link_empty_validation(self):
        """測試連結為空的驗證"""
        with pytest.raises(ValueError, match="連結長度需在 1 到 512 個字元之間"):
            Article(
                title="測試文章",
                link="",
                published_at=datetime.now()
            )
    
    def test_article_link_too_long_validation(self):
        """測試連結過長的驗證"""
        with pytest.raises(ValueError, match="連結長度需在 1 到 512 個字元之間"):
            Article(
                title="測試文章",
                link="a" * 513,
                published_at=datetime.now()
            )
    
    def test_article_link_boundary_values(self):
        """測試連結長度的邊界值"""
        # 測試最短有效長度
        article_min = Article(
            title="測試文章",
            link="a",
            published_at=datetime.now()
        )
        assert article_min.link == "a"
        
        # 測試最長有效長度
        article_max = Article(
            title="測試文章",
            link="a" * 512,
            published_at=datetime.now()
        )
        assert len(article_max.link) == 512

    def test_article_published_at_null_validation(self):
        """測試發布時間為空的驗證"""
        with pytest.raises(ValueError, match="發布時間不能為空"):
            Article(
                title="測試文章",
                link="https://test.com/article",
                published_at=None
            )
    
    def test_article_summary_too_long_validation(self):
        """測試摘要過長的驗證"""
        with pytest.raises(ValueError, match="摘要長度需在 0 到 1024 個字元之間"):
            Article(
                title="測試文章",
                link="https://test.com/article",
                published_at=datetime.now(),
                summary="a" * 1025
            )
    
    def test_article_summary_boundary_values(self):
        """測試摘要長度的邊界值"""
        # 測試最短有效長度
        article_empty = Article(
            title="測試文章",
            link="https://test.com/article",
            published_at=datetime.now(),
            summary=""
        )
        assert article_empty.summary == ""
        
        # 測試最長有效長度
        article_max = Article(
            title="測試文章",
            link="https://test.com/article",
            published_at=datetime.now(),
            summary="a" * 1024
        )
        assert len(article_max.summary or "") == 1024
    
    def test_article_content_too_long_validation(self):
        """測試內容過長的驗證"""
        with pytest.raises(ValueError, match="內容長度需在 0 到 65536 個字元之間"):
            Article(
                title="測試文章",
                link="https://test.com/article",
                published_at=datetime.now(),
                content="a" * 65537
            )
    
    def test_article_content_boundary_values(self):
        """測試內容長度的邊界值"""
        # 測試最短有效長度
        article_empty = Article(
            title="測試文章",
            link="https://test.com/article",
            published_at=datetime.now(),
            content=""
        )
        assert article_empty.content == ""
        
        # 測試最長有效長度
        article_max = Article(
            title="測試文章",
            link="https://test.com/article",
            published_at=datetime.now(),
            content="a" * 65536
        )
        assert len(article_max.content or "") == 65536
    
    def test_article_source_too_long_validation(self):
        """測試來源過長的驗證"""
        with pytest.raises(ValueError, match="來源長度需在 1 到 255 個字元之間"):
            Article(
                title="測試文章",
                link="https://test.com/article",
                published_at=datetime.now(),
                source="a" * 256
            )
    
    def test_article_source_too_short_validation(self):
        """測試來源過短的驗證"""
        with pytest.raises(ValueError, match="來源長度需在 1 到 255 個字元之間"):
            Article(
                title="測試文章",
                link="https://test.com/article",
                published_at=datetime.now(),
                source=""
            )
    
    def test_article_source_boundary_values(self):
        """測試來源長度的邊界值"""
        # 測試最短有效長度
        article_min = Article(
            title="測試文章",
            link="https://test.com/article",
            published_at=datetime.now(),
            source="a"
        )
        assert article_min.source == "a"
        
        # 測試最長有效長度
        article_max = Article(
            title="測試文章",
            link="https://test.com/article",
            published_at=datetime.now(),
            source="a" * 255
        )
        assert len(article_max.source or "") == 255
    
    def test_article_repr(self):
        """測試 Article 的 __repr__ 方法"""
        article = Article(
            id=1,
            title="測試文章",
            link="https://test.com/article",
            published_at=datetime.now()
        )
        
        assert repr(article) == "<Article(id=1, title='測試文章', link='https://test.com/article')>"


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
    
    def test_system_settings_crawler_name_empty_validation(self):
        """測試爬蟲名稱為空的驗證"""
        with pytest.raises(ValueError, match="爬蟲名稱長度需在 1 到 255 個字元之間"):
            SystemSettings(
                crawler_name="",
                crawl_interval=60
            )
    
    def test_system_settings_crawler_name_too_long_validation(self):
        """測試爬蟲名稱過長的驗證"""
        with pytest.raises(ValueError, match="爬蟲名稱長度需在 1 到 255 個字元之間"):
            SystemSettings(
                crawler_name="a" * 256,
                crawl_interval=60
            )
    
    def test_system_settings_crawler_name_boundary_values(self):
        """測試爬蟲名稱長度的邊界值"""
        # 測試最短有效長度
        settings_min = SystemSettings(
            crawler_name="a",
            crawl_interval=60
        )
        assert settings_min.crawler_name == "a"
        
        # 測試最長有效長度
        settings_max = SystemSettings(
            crawler_name="a" * 255,
            crawl_interval=60
        )
        assert len(settings_max.crawler_name) == 255
    
    def test_system_settings_crawl_interval_negative_validation(self):
        """測試爬取間隔為負值的驗證"""
        with pytest.raises(ValueError, match="爬取間隔需大於 0"):
            SystemSettings(
                crawler_name="test_crawler",
                crawl_interval=-1
            )
    
    def test_system_settings_is_active_null_validation(self):
        """測試是否啟用為空的驗證"""
        with pytest.raises(ValueError, match="是否啟用不能為空"):
            SystemSettings(
                crawler_name="test_crawler",
                crawl_interval=60,
                is_active=None
            )
    
    def test_system_settings_created_at_null_validation(self):
        """測試建立時間為空的驗證"""
        with pytest.raises(ValueError, match="建立時間不能為空"):
            SystemSettings(
                crawler_name="test_crawler",
                crawl_interval=60,
                created_at=None
            )
    
    def test_system_settings_repr(self):
        """測試 SystemSettings 的 __repr__ 方法"""
        settings = SystemSettings(
            id=1,
            crawler_name="test_crawler",
            crawl_interval=60,
            is_active=True
        )
        
        assert repr(settings) == "<SystemSettings(id=1, crawler_name='test_crawler', is_active=True)>"