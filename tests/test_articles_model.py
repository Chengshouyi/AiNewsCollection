import pytest
from datetime import datetime, timezone
from src.models.articles_model import Articles

class TestArticleModel:
    """Article 模型的基本測試類"""
    
    def test_article_creation_with_required_fields_only(self):
        """測試只使用必填欄位創建 Article"""
        article = Articles(
            title="測試文章",
            link="https://test.com/article"
        )
        
        assert article.title == "測試文章"
        assert article.link == "https://test.com/article"
        assert article.is_ai_related is False
        assert article.created_at is not None

    def test_article_creation_with_all_fields(self):
        """測試使用所有欄位創建 Article"""
        article = Articles(
            title="完整測試文章",
            link="https://test.com/full-article",
            summary="這是一篇測試文章的摘要",
            content="這是一篇測試文章的完整內容，包含了多個段落...",
            category="科技",
            published_at="2023-04-01",
            author="測試作者",
            source="測試來源",
            article_type="新聞",
            tags="AI,科技,測試",
            is_ai_related=True
        )
        
        assert article.title == "完整測試文章"
        assert article.link == "https://test.com/full-article"
        assert article.is_ai_related is True

    def test_article_is_ai_related_update(self):
        """測試 Article 的 is_ai_related 欄位更新"""
        article = Articles(
            title="測試文章",
            link="https://test.com/article"
        )
        
        article.is_ai_related = True
        assert article.is_ai_related is True
        
        article.is_ai_related = False
        assert article.is_ai_related is False

    def test_article_mutable_fields_update(self):
        """測試 Article 的可變欄位更新"""
        article = Articles(
            title="原始標題",
            link="https://test.com/article"
        )
        
        # 更新可變欄位
        article.title = "更新後的標題"
        article.summary = "更新後的摘要"
        article.content = "新增的內容"
        
        assert article.title == "更新後的標題"
        assert article.summary == "更新後的摘要"
        assert article.content == "新增的內容"

    def test_article_repr(self):
        """測試 Article 的 __repr__ 方法"""
        article = Articles(
            id=1,
            title="測試文章",
            link="https://test.com/article"
        )
        
        assert repr(article) == "<Article(id=1, title='測試文章', link='https://test.com/article')>"


