import pytest
from datetime import datetime
from src.model.models import Article, SystemSettings

def test_article_model_validation():
    # 測試標題驗證
    with pytest.raises(ValueError):
        Article(
            title="",
            link="https://test.com/article",
            published_at=datetime.now()
        )
    
    with pytest.raises(ValueError):
        Article(
            title="a" * 256,
            link="https://test.com/article",
            published_at=datetime.now()
        )

def test_article_model_link_validation():
    # 測試連結驗證
    with pytest.raises(ValueError):
        Article(
            title="測試文章",
            link="",
            published_at=datetime.now()
        )

def test_article_model_published_at_validation():
    # 測試發布時間驗證
    with pytest.raises(ValueError):
        Article(
            title="測試文章",
            link="https://test.com/article",
            published_at=None
        )


def test_article_model_optional_fields():
    # 測試文章模型的可選欄位
    article = Article(
        title="測試文章",
        link="https://test.com/article",
        published_at=datetime.now()
    )
    
    assert article.summary is None
    assert article.content is None
    assert article.source is None
