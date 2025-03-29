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

    def test_article_to_dict(self):
        """測試 Article 的 to_dict 方法"""
        test_time = datetime.now(timezone.utc)
        article = Articles(
            id=1,
            title="測試文章",
            link="https://test.com/article",
            summary="測試摘要",
            content="測試內容",
            category="測試分類",
            published_at=test_time,
            author="測試作者",
            source="測試來源",
            article_type="測試類型",
            tags="測試標籤",
            is_ai_related=True,
            created_at=test_time,
            updated_at=test_time
        )
        
        article_dict = article.to_dict()
        assert article_dict == {
            'id': 1,
            'title': "測試文章",
            'summary': "測試摘要",
            'content': "測試內容",
            'link': "https://test.com/article",
            'category': "測試分類",
            'published_at': test_time,
            'author': "測試作者",
            'source': "測試來源",
            'article_type': "測試類型",
            'tags': "測試標籤",
            'is_ai_related': True,
            'created_at': test_time,
            'updated_at': test_time
        }

    def test_article_default_timestamps(self):
        """測試 Article 的時間戳記預設值"""
        article = Articles(
            title="測試文章",
            link="https://test.com/article"
        )
        
        assert isinstance(article.created_at, datetime)
        assert article.created_at.tzinfo == timezone.utc
        assert article.updated_at is None
        
        # 模擬更新操作
        article.title = "新標題"
        # 注意：實際更新時間需要透過 SQLAlchemy session 的操作才會觸發

    def test_article_utc_datetime_conversion(self):
        """測試 Article 的 published_at 欄位 UTC 時間轉換"""
        from datetime import timedelta
        
        # 測試 1: 傳入無時區資訊的 datetime (naive datetime)
        naive_time = datetime(2025, 3, 28, 12, 0, 0)  # 無時區資訊
        article = Articles(
            title="測試 UTC 轉換",
            link="https://test.com/utc-test",
            published_at=naive_time
        )
        if article.published_at is not None:
            assert article.published_at.tzinfo == timezone.utc  # 確認有 UTC 時區
        assert article.published_at == naive_time.replace(tzinfo=timezone.utc)  # 確認值正確


        # 測試 2: 傳入帶非 UTC 時區的 datetime (aware datetime, UTC+8)
        utc_plus_8_time = datetime(2025, 3, 28, 14, 0, 0, tzinfo=timezone(timedelta(hours=8)))
        article.published_at = utc_plus_8_time
        expected_utc_time = datetime(2025, 3, 28, 6, 0, 0, tzinfo=timezone.utc)  # UTC+8 轉 UTC
        assert article.published_at.tzinfo == timezone.utc  # 確認轉換為 UTC 時區
        assert article.published_at == expected_utc_time  # 確認時間正確轉換

        # 測試 3: 傳入已是 UTC 的 datetime，確保不變
        utc_time = datetime(2025, 3, 28, 12, 0, 0, tzinfo=timezone.utc)
        article.published_at = utc_time
        assert article.published_at == utc_time  # 確認值未被改變

        # 測試 4: 確認非監聽欄位（如 title）不觸發轉換邏輯
        article.title = "新標題"
        assert article.published_at == utc_time  # published_at 不受影響


