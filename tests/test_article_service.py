import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.articles_model import Articles
from src.models.base_model import Base
from src.database.database_manager import DatabaseManager
from src.database.articles_repository import ArticlesRepository
from src.services.article_service import ArticleService
from src.error.errors import ValidationError

# 設置測試資料庫
@pytest.fixture(scope="session")
def engine():
    """創建測試資料庫引擎"""
    return create_engine('sqlite:///:memory:')

@pytest.fixture(scope="session")
def tables(engine):
    """創建資料表"""
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="session")
def session_factory(engine):
    """創建會話工廠"""
    return sessionmaker(bind=engine)

@pytest.fixture(scope="function")
def session(session_factory, tables):
    """為每個測試函數創建新的會話"""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture(scope="function")
def db_manager():
    """創建真實的資料庫管理器"""
    return DatabaseManager('sqlite:///:memory:')

@pytest.fixture(scope="function")
def articles_repository(session):
    """創建真實的文章儲存庫"""
    return ArticlesRepository(session, Articles)

@pytest.fixture(scope="function")
def article_service(db_manager):
    """創建真實的文章服務"""
    return ArticleService(db_manager)

@pytest.fixture(scope="function")
def sample_article_data():
    """返回一個範例文章資料字典"""
    return {
        "title": "測試文章",
        "summary": "這是測試摘要",
        "content": "這是測試內容",
        "published_at": datetime.now(timezone.utc),
        "source": "test_source",
        "source_url": "https://example.com/test",
        "link": "https://example.com/test",
        "category": "test_category",
        "tags": "test,pytest",
        "is_ai_related": True,
        "is_scraped": True
    }

@pytest.fixture(scope="function")
def sample_article(session, sample_article_data):
    """創建並返回一個範例文章物件"""
    article = Articles(**sample_article_data)
    session.add(article)
    session.commit()
    session.refresh(article)
    return article

class TestArticleServiceBasic:
    """測試 ArticleService 的基礎功能"""
    
    def test_init(self, db_manager):
        """測試初始化"""
        service = ArticleService(db_manager)
        assert service.db_manager == db_manager

class TestArticleServiceCreate:
    """測試文章創建相關功能"""
    
    def test_insert_article_success(self, article_service, session, sample_article_data):
        """測試成功創建文章"""
        result = article_service.insert_article(sample_article_data)
        
        assert result is not None
        assert result.title == sample_article_data["title"]
        assert result.summary == sample_article_data["summary"]
        assert result.content == sample_article_data["content"]
        assert result.link == sample_article_data["link"]
        
        # 驗證資料庫中確實存在這篇文章
        db_article = session.query(Articles).filter_by(link=sample_article_data["link"]).first()
        assert db_article is not None
        assert db_article.title == sample_article_data["title"]

    def test_insert_article_duplicate_link(self, article_service, session, sample_article):
        """測試創建重複連結的文章"""
        duplicate_data = {
            "title": "重複文章",
            "summary": "這是重複摘要",
            "content": "這是重複內容",
            "published_at": datetime.now(timezone.utc),
            "source": "test_source",
            "source_url": "https://example.com/test",
            "link": sample_article.link,  # 使用相同的連結
            "category": "test_category",
            "tags": "test,pytest",
            "is_ai_related": True,
            "is_scraped": True
        }
        
        with pytest.raises(ValidationError) as exc_info:
            article_service.insert_article(duplicate_data)
        
        assert "已存在具有相同連結的文章" in str(exc_info.value)

    def test_batch_insert_articles_success(self, article_service, session):
        """測試成功批量創建文章"""
        articles_data = [
            {
                "title": f"測試文章 {i}",
                "summary": f"這是測試摘要 {i}",
                "content": f"這是測試內容 {i}",
                "published_at": datetime.now(timezone.utc),
                "source": "test_source",
                "source_url": f"https://example.com/test{i}",
                "link": f"https://example.com/test{i}",
                "category": "test_category",
                "tags": "test,pytest",
                "is_ai_related": True,
                "is_scraped": True
            }
            for i in range(3)
        ]
        
        result = article_service.batch_insert_articles(articles_data)
        
        assert result["success_count"] == 3
        assert result["fail_count"] == 0
        assert len(result["inserted_articles"]) == 3
        
        # 驗證資料庫中確實存在這些文章
        for i in range(3):
            db_article = session.query(Articles).filter_by(link=f"https://example.com/test{i}").first()
            assert db_article is not None
            assert db_article.title == f"測試文章 {i}"

class TestArticleServiceQuery:
    """測試文章查詢相關功能"""
    
    def test_get_all_articles(self, article_service, session, sample_article):
        """測試獲取所有文章"""
        result = article_service.get_all_articles(limit=10, offset=0)
        
        assert len(result) > 0
        assert any(article.id == sample_article.id for article in result)

    def test_get_articles_paginated(self, article_service, session, sample_article):
        """測試分頁獲取文章"""
        result = article_service.get_articles_paginated(1, 10, sort_by="id", sort_desc=True)
        
        assert result["total"] > 0
        assert result["page"] == 1
        assert result["per_page"] == 10
        assert len(result["items"]) > 0
        assert any(article.id == sample_article.id for article in result["items"])

    def test_search_articles(self, article_service, session, sample_article):
        """測試搜尋文章"""
        search_terms = {"title": "測試"}
        result = article_service.search_articles(search_terms, limit=10, offset=0)
        
        assert len(result) > 0
        assert any(article.id == sample_article.id for article in result)

class TestArticleServiceUpdate:
    """測試文章更新相關功能"""
    
    def test_update_article_success(self, article_service, session, sample_article):
        """測試成功更新文章"""
        update_data = {
            "title": "更新後的標題",
            "content": "更新後的內容"
        }
        
        result = article_service.update_article(sample_article.id, update_data)
        
        assert result is not None
        assert result.title == update_data["title"]
        assert result.content == update_data["content"]
        
        # 驗證資料庫中的文章已被更新
        db_article = session.query(Articles).get(sample_article.id)
        assert db_article.title == update_data["title"]
        assert db_article.content == update_data["content"]

    def test_batch_update_articles_success(self, article_service, session, sample_article):
        """測試成功批量更新文章"""
        update_data = {
            "category": "更新後的分類"
        }
        
        result = article_service.batch_update_articles([sample_article.id], update_data)
        
        assert result["success_count"] == 1
        assert result["fail_count"] == 0
        assert len(result["updated_entities"]) == 1
        assert result["updated_entities"][0].category == update_data["category"]
        
        # 驗證資料庫中的文章已被更新
        db_article = session.query(Articles).get(sample_article.id)
        assert db_article.category == update_data["category"]

class TestArticleServiceDelete:
    """測試文章刪除相關功能"""
    
    def test_delete_article_success(self, article_service, session, sample_article):
        """測試成功刪除文章"""
        result = article_service.delete_article(sample_article.id)
        
        assert result is True
        
        # 驗證資料庫中的文章已被刪除
        db_article = session.query(Articles).get(sample_article.id)
        assert db_article is None

    def test_delete_article_by_link_success(self, article_service, session, sample_article):
        """測試成功根據連結刪除文章"""
        result = article_service.delete_article_by_link(sample_article.link)
        
        assert result is True
        
        # 驗證資料庫中的文章已被刪除
        db_article = session.query(Articles).filter_by(link=sample_article.link).first()
        assert db_article is None

class TestArticleServiceAdvanced:
    """測試文章服務的進階功能"""
    
    def test_get_articles_statistics(self, article_service, session, sample_article):
        """測試獲取文章統計資訊"""
        result = article_service.get_articles_statistics()
        
        assert "total_articles" in result
        assert "ai_related_articles" in result
        assert "category_distribution" in result
        assert "recent_articles" in result
        assert result["total_articles"] > 0
        assert "test_category" in result["category_distribution"]