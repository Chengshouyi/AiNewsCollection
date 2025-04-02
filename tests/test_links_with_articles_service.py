import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine
from src.database.database_manager import DatabaseManager
from src.models.articles_model import Articles
from src.models.article_links_model import ArticleLinks
from src.services.links_with_articles_service import LinksWithArticlesService
from datetime import datetime, timezone
from typing import List, Dict, Any, Hashable
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
def sample_articles_data() -> List[Dict[Hashable, Any]]:
    """提供範例文章資料"""
    now_utc = datetime.now(timezone.utc)
    return [
        {
            "link": "https://example.com/article1", 
            "title": "Title 1", 
            "published_at": now_utc, 
            "content": "Content 1", 
            "source": "source1",
            "summary": "Summary 1",
            "category": "測試分類",
            "author": "Author 1",
            "article_type": "news",
            "tags": "AI,Tech",
            "is_ai_related": True
        },
        {
            "link": "https://example.com/article2", 
            "title": "Title 2", 
            "published_at": now_utc, 
            "content": "Content 2", 
            "source": "source2",
            "summary": "Summary 2",
            "category": "測試分類1",
            "author": "Author 2",
            "article_type": "news",
            "tags": "Business",
            "is_ai_related": False
        }
    ]

@pytest.fixture(scope="function")
def sample_article_links_data() -> List[Dict[Hashable, Any]]:
    """提供範例文章連結資料"""
    return [
        {
            "source_name": "範例新聞",
            "source_url": "https://example.com",
            "article_link": "https://example.com/article1",
            "title": "Title 1",
            "summary": "測試摘要",
            "category": "測試分類",
            "published_age": "1 小時前",
            "is_scraped": False
        },
        {
            "source_name": "範例新聞1",
            "source_url": "https://example.com/news",
            "article_link": "https://example.com/article2",
            "title": "Title 2",
            "summary": "測試摘要1",
            "category": "測試分類1",
            "published_age": "2 小時前",
            "is_scraped": True
        }
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
        # 先插入測試資料
        links_articles_service.batch_insert_links_with_articles(sample_article_links_data, sample_articles_data)
        
        # 確認初始數量
        initial_articles_count = session.query(Articles).count()
        initial_links_count = session.query(ArticleLinks).count()
        assert initial_articles_count > 0
        assert initial_links_count > 0
        
        # 執行刪除
        article_link_to_delete = "https://example.com/article1"
        deletion_result = links_articles_service.delete_article_with_links(article_link_to_delete)
        
        # 驗證刪除結果
        assert deletion_result is True
        assert session.query(Articles).count() == initial_articles_count - 1
        assert session.query(ArticleLinks).count() == initial_links_count - 1  # 連結應該被刪除，因為 article_link 是 NOT NULL
        
        # 驗證特定記錄已被刪除
        deleted_article = session.query(Articles).filter(Articles.link == article_link_to_delete).first()
        deleted_link = session.query(ArticleLinks).filter(ArticleLinks.article_link == article_link_to_delete).first()
        assert deleted_article is None
        assert deleted_link is None

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


    def test_batch_insert_links_with_existing_article(self, links_articles_service: LinksWithArticlesService, session: Session, clear_tables, sample_articles_data):
        """測試當文章已存在時的連結插入"""
        # 先插入一篇文章
        article_data = sample_articles_data[0]
        article = Articles(**article_data)
        session.add(article)
        session.commit()

        # 準備對應的連結資料
        link_data: List[Dict[Hashable, Any]] = [{
            "source_name": "範例新聞",
            "source_url": "https://example.com",
            "article_link": article_data["link"],  # 使用相同的連結
            "title": article_data["title"],
            "summary": "測試摘要",
            "category": article_data["category"],
            "published_age": "1 小時前",
            "is_scraped": False
        }]

        # 插入連結
        result = links_articles_service.batch_insert_links_with_articles(link_data, [article_data])
        
        # 驗證結果
        assert result["success_count"] == 1
        assert len(result["inserted_links"]) == 1
        assert len(result["inserted_articles"]) == 1
        assert session.query(Articles).count() == 1  # 文章數量應該還是1
        assert session.query(ArticleLinks).count() == 1

    def test_batch_insert_links_without_article_reference(self, links_articles_service: LinksWithArticlesService, session: Session, clear_tables):
        """測試插入沒有對應文章的連結"""
        link_data: List[Dict[Hashable, Any]] = [{
            "source_name": "範例新聞",
            "source_url": "https://example.com",
            "article_link": "https://example.com/no-article",
            "title": "無對應文章的連結",
            "summary": "測試摘要",
            "category": "測試分類",
            "published_age": "1 小時前",
            "is_scraped": False
        }]

        result = links_articles_service.batch_insert_links_with_articles(link_data)
        
        # 驗證結果
        assert result["success_count"] == 1
        assert len(result["inserted_links"]) == 1
        assert len(result["inserted_articles"]) == 0
        assert session.query(Articles).count() == 0
        assert session.query(ArticleLinks).count() == 1

    def test_get_articles_by_source_with_missing_links(self, links_articles_service: LinksWithArticlesService, session: Session, clear_tables, sample_articles_data):
        """測試獲取沒有對應連結的文章"""
        # 只插入文章，不插入連結
        article = Articles(**sample_articles_data[0])
        session.add(article)
        session.commit()

        results = links_articles_service.get_articles_by_source(sample_articles_data[0]["source"], with_links=True)
        
        assert len(results) == 1
        assert results[0]["article"].title == sample_articles_data[0]["title"]
        assert results[0]["links"] is None

    def test_delete_article_with_links_cascade(self, links_articles_service: LinksWithArticlesService, session: Session, clear_tables, sample_article_links_data, sample_articles_data):
        """測試刪除文章時連結的處理"""
        # 先插入資料
        links_articles_service.batch_insert_links_with_articles(sample_article_links_data, sample_articles_data)
        
        # 直接從資料庫刪除文章
        article = session.query(Articles).filter(Articles.link == sample_articles_data[0]["link"]).first()
        session.delete(article)
        session.commit()

        # 驗證連結是否已被刪除（因為 article_link 是 NOT NULL 且 ondelete="CASCADE"）
        link = session.query(ArticleLinks).filter(
            ArticleLinks.article_link == sample_article_links_data[0]["article_link"]
        ).first()
        assert link is None  # 連結應該被刪除，因為 article_link 是 NOT NULL

    def test_update_article_link_status_without_article(self, links_articles_service: LinksWithArticlesService, session: Session, clear_tables, sample_article_links_data):
        """測試更新沒有對應文章的連結狀態"""
        # 只插入連結
        links_articles_service.batch_insert_links_with_articles(sample_article_links_data)
        
        # 更新狀態
        result = links_articles_service.update_article_link_status(
            sample_article_links_data[0]["article_link"],
            True
        )
        
        assert result is True
        link = session.query(ArticleLinks).filter(
            ArticleLinks.article_link == sample_article_links_data[0]["article_link"]
        ).first()
        assert link is not None
        assert link.is_scraped is True