import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine
from src.database.database_manager import DatabaseManager
from src.models.articles_model import Articles
from src.models.article_links_model import ArticleLinks
from src.services.links_with_articles_service import LinksWithArticlesService
from datetime import datetime, timezone
from typing import List, Dict, Any
from src.models.base_model import Base


# 設定測試資料庫
@pytest.fixture(scope="session")
def engine():
    """建立全局測試引擎，使用記憶體 SQLite 資料庫"""
    return create_engine('sqlite:///:memory:')

@pytest.fixture(scope="session")
def tables(engine):
    """建立測試資料表，使用 session scope 減少重複建立和銷毀資料庫結構"""
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="session")
def session_factory(engine):
    """建立會話工廠，使用 session scope 共享會話工廠"""
    return sessionmaker(bind=engine)

@pytest.fixture(scope="function")
def session(session_factory, tables):
    """建立測試會話，每個測試函數獲取全新的獨立會話"""
    session = session_factory()
    
    try:
        yield session
    finally:
        session.close()

@pytest.fixture(scope="function")
def db_manager(engine, session_factory, monkeypatch):
    """創建真實的 DatabaseManager 實例用於測試，每個測試獲取獨立的數據庫管理器"""
    # 設定環境變數指向記憶體資料庫
    monkeypatch.setenv('DATABASE_PATH', 'sqlite:///:memory:')
    
    # 創建 DatabaseManager 實例
    manager = DatabaseManager()
    
    # 替換引擎和會話工廠，使用測試用的記憶體資料庫
    manager.engine = engine
    manager.Session = session_factory
    
    # 確保表格已經創建完成
    Base.metadata.create_all(engine)
    
    return manager

@pytest.fixture(scope="function")
def links_articles_service(db_manager: DatabaseManager) -> LinksWithArticlesService:
    """建立 LinksWithArticlesService 實例，scope為 function"""
    return LinksWithArticlesService(db_manager)

@pytest.fixture(scope="function")
def clear_tables(session: Session):
    """清除測試表格資料，確保每個測試的資料是獨立的，scope為 function"""
    session.query(Articles).delete()
    session.query(ArticleLinks).delete()
    session.commit()

@pytest.fixture(scope="function")
def sample_articles_data() -> List[Dict[str, Any]]:
    """提供範例文章資料"""
    now_utc = datetime.now(timezone.utc)
    return [
        {
            "link": "https://example.com/article1", 
            "title": "Title 1", 
            "published_at": now_utc, 
            "content": "Content 1", 
            "source": "source1"
            },
        {
            "link": "https://example.com/article2", 
            "title": "Title 2", 
            "published_at": now_utc, 
            "content": "Content 2", 
            "source": "source2"},
    ]

@pytest.fixture(scope="function")
def sample_article_links_data() -> List[Dict[str, Any]]:
    """提供範例文章連結資料"""
    return [
        {
            "source_name": "範例新聞",
            "source_url": "https://example.com",
            "article_link": "https://example.com/article1",
            "title": "測試文章",
            "summary": "測試摘要",
            "category": "測試分類",
            "published_age": "測試發佈年齡",
            "is_scraped": False
         },
        {
            "source_name": "範例新聞1",
            "source_url": "https://example.com",
            "article_link": "https://example.com/article2",
            "title": "測試文章1",
            "summary": "測試摘要1",
            "category": "測試分類1",
            "published_age": "測試發佈年齡1",
            "is_scraped": False
        },
    ]

class TestLinksWithArticlesService:
    def test_batch_insert_links_with_articles_success(self, links_articles_service: LinksWithArticlesService, session: Session, clear_tables, sample_article_links_data, sample_articles_data):
        """測試批量插入文章和連結成功"""
        links_articles_service.batch_insert_links_with_articles(sample_article_links_data, sample_articles_data)
        assert session.query(Articles).count() == len(sample_articles_data)
        assert session.query(ArticleLinks).count() == len(sample_article_links_data)

    def test_batch_insert_links_with_articles_only_links(self, links_articles_service: LinksWithArticlesService, session: Session, clear_tables, sample_article_links_data):
        """測試僅批量插入連結成功"""
        links_articles_service.batch_insert_links_with_articles(sample_article_links_data)
        assert session.query(ArticleLinks).count() == len(sample_article_links_data)
        assert session.query(Articles).count() == 0

    def test_batch_insert_links_with_articles_duplicate_links(self, links_articles_service: LinksWithArticlesService, session: Session, clear_tables, sample_article_links_data):
        """測試批量插入重複連結時應忽略"""
        initial_count = session.query(ArticleLinks).count()
        links_articles_service.batch_insert_links_with_articles(sample_article_links_data)
        links_articles_service.batch_insert_links_with_articles(sample_article_links_data)
        assert session.query(ArticleLinks).count() == len(sample_article_links_data) + initial_count # Assuming initial count is 0

    def test_get_articles_by_source_with_links(self, links_articles_service: LinksWithArticlesService, session: Session, clear_tables, sample_article_links_data, sample_articles_data):
        """測試根據來源獲取文章及其連結"""
        links_articles_service.batch_insert_links_with_articles(sample_article_links_data, sample_articles_data)
        source = "source1"
        results = links_articles_service.get_articles_by_source(source, with_links=True)
        assert len(results) == 1
        assert results[0]["article"].title == "Title 1"
        assert results[0]["links"].article_link == "https://example.com/article1"

    def test_get_articles_by_source_without_links(self, links_articles_service: LinksWithArticlesService, session: Session, clear_tables, sample_article_links_data, sample_articles_data):
        """測試根據來源獲取文章但不包含連結"""
        links_articles_service.batch_insert_links_with_articles(sample_article_links_data, sample_articles_data)
        source = "source2"
        results = links_articles_service.get_articles_by_source(source, with_links=False)
        assert len(results) == 1
        assert results[0]["article"].title == "Title 2"
        assert results[0]["links"] is None

    def test_get_articles_by_source_not_found(self, links_articles_service: LinksWithArticlesService, session: Session, clear_tables, sample_article_links_data, sample_articles_data):
        """測試根據不存在的來源獲取文章"""
        links_articles_service.batch_insert_links_with_articles(sample_article_links_data, sample_articles_data)
        source = "nonexistent_source"
        results = links_articles_service.get_articles_by_source(source)
        assert len(results) == 0

    def test_delete_article_with_links_success(self, links_articles_service: LinksWithArticlesService, session: Session, clear_tables, sample_article_links_data, sample_articles_data):
        """測試成功刪除文章及其相關連結"""
        links_articles_service.batch_insert_links_with_articles(sample_article_links_data, sample_articles_data)
        article_link_to_delete = "https://example.com/article1"
        initial_articles_count = session.query(Articles).count()
        initial_links_count = session.query(ArticleLinks).count()
        deletion_result = links_articles_service.delete_article_with_links(article_link_to_delete)
        assert deletion_result is True
        assert session.query(Articles).count() == initial_articles_count - 1
        assert session.query(ArticleLinks).count() == initial_links_count - 1
        assert session.query(Articles).filter(Articles.link == article_link_to_delete).first() is None
        assert session.query(ArticleLinks).filter(ArticleLinks.article_link == article_link_to_delete).first() is None

    def test_delete_article_with_links_not_found(self, links_articles_service: LinksWithArticlesService, session: Session, clear_tables):
        """測試刪除不存在的文章連結"""
        article_link_to_delete = "nonexistent_link"
        initial_articles_count = session.query(Articles).count()
        initial_links_count = session.query(ArticleLinks).count()
        deletion_result = links_articles_service.delete_article_with_links(article_link_to_delete)
        assert deletion_result is False
        assert session.query(Articles).count() == initial_articles_count
        assert session.query(ArticleLinks).count() == initial_links_count

    def test_delete_article_with_links_only_link_exists(self, links_articles_service: LinksWithArticlesService, session: Session, clear_tables, sample_article_links_data):
        """測試刪除只有連結存在的文章（文章不存在）"""
        links_articles_service.batch_insert_links_with_articles(sample_article_links_data)
        article_link_to_delete = "https://example.com/article1"
        initial_links_count = session.query(ArticleLinks).count()
        deletion_result = links_articles_service.delete_article_with_links(article_link_to_delete)
        assert deletion_result is True
        assert session.query(ArticleLinks).count() == initial_links_count - 1
        assert session.query(ArticleLinks).filter(ArticleLinks.article_link == article_link_to_delete).first() is None
        assert session.query(Articles).filter(Articles.link == article_link_to_delete).first() is None

    def test_get_articles_by_source_empty_database(self, links_articles_service: LinksWithArticlesService, session: Session, clear_tables):
        """測試在空資料庫中根據來源獲取文章"""
        source = "any_source"
        results = links_articles_service.get_articles_by_source(source)
        assert len(results) == 0

    def test_delete_article_with_links_empty_database(self, links_articles_service: LinksWithArticlesService, session: Session, clear_tables):
        """測試在空資料庫中刪除文章及其連結"""
        article_link_to_delete = "any_link"
        deletion_result = links_articles_service.delete_article_with_links(article_link_to_delete)
        assert deletion_result is False
        assert session.query(Articles).count() == 0
        assert session.query(ArticleLinks).count() == 0