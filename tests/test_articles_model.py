import pytest
from datetime import datetime, timezone
from src.models.articles_model import Articles
from src.error.errors import ValidationError

class TestArticleModel:
    """Article 模型的測試類"""
    
    def test_article_creation_with_required_fields_only(self):
        """測試只使用必填欄位創建 Article"""
        article = Articles(
            title="測試文章",
            link="https://test.com/article"
        )
        
        assert article.title == "測試文章"
        assert article.link == "https://test.com/article"
        assert article.published_at is None
        assert article.summary is None
        assert article.content is None
        assert article.source is None
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
        assert article.summary == "這是一篇測試文章的摘要"
        assert article.content == "這是一篇測試文章的完整內容，包含了多個段落..."
        assert article.category == "科技"
        assert article.published_at == "2023-04-01"
        assert article.author == "測試作者"
        assert article.source == "測試來源"
        assert article.article_type == "新聞"
        assert article.tags == "AI,科技,測試"
        assert article.is_ai_related is True
        assert article.created_at is not None
        assert article.updated_at is None

    def test_article_is_ai_related_default(self):
        """測試 Article 的 is_ai_related 預設值"""
        article = Articles(
            title="測試文章",
            link="https://test.com/article"
        )
        
        assert article.is_ai_related is False  # 測試預設值為 False

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

    def test_article_immutable_fields(self):
        """測試 Article 的不可變欄位"""
        article = Articles(
            title="測試文章",
            link="https://test.com/article"
        )
        
        # 測試不可修改 id
        with pytest.raises(ValidationError, match="id cannot be updated"):
            article.id = 100
            
        # 測試不可修改 link
        with pytest.raises(ValidationError, match="link cannot be updated"):
            article.link = "https://test.com/new-link"
            
        # 測試不可修改 created_at
        with pytest.raises(ValidationError, match="created_at cannot be updated"):
            article.created_at = datetime.now(timezone.utc)

    def test_article_update_mutable_fields(self):
        """測試 Article 的可變欄位更新"""
        article = Articles(
            title="原始標題",
            link="https://test.com/article",
            summary="原始摘要"
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


