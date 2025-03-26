import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from src.models.article_links_model import ArticleLinks
from src.models.articles_model import Articles
from src.models.base_model import Base
from src.database.article_links_repository import ArticleLinksRepository
from src.database.articles_repository import ArticlesRepository
from sqlalchemy import create_engine
from src.database.base_repository import SchemaType
from src.models.article_links_schema import ArticleLinksCreateSchema, ArticleLinksUpdateSchema
from src.error.errors import ValidationError, DatabaseOperationError, InvalidOperationError, DatabaseConnectionError

# 設置測試資料庫
@pytest.fixture
def engine():
    return create_engine('sqlite:///:memory:')

@pytest.fixture
def tables(engine):
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture
def session(engine, tables):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    
    try:
        yield session
    finally:
        session.close()
        # 只有在事務仍然有效時才回滾
        if transaction.is_active:
            transaction.rollback()
        connection.close()

@pytest.fixture
def article_links_repo(session):
    return ArticleLinksRepository(session, ArticleLinks)

@pytest.fixture
def article_repo(session):
    return ArticlesRepository(session, Articles)

@pytest.fixture
def sample_articles(session):
    """創建測試文章數據"""
    articles = [
        Articles(
            title="測試文章1",
            link="https://example.com/article1",
            content="測試內容1",
            is_ai_related=True,
            source="測試來源1",
            published_at=datetime.now(timezone.utc)
        ),
        Articles(
            title="測試文章2",
            link="https://example.com/article2",
            content="測試內容2",
            is_ai_related=False,
            source="測試來源1",
            published_at=datetime.now(timezone.utc)
        ),
        Articles(
            title="測試文章3",
            link="https://example.com/article3",
            content="測試內容3",
            is_ai_related=True,
            source="測試來源2",
            published_at=datetime.now(timezone.utc)
        )
    ]
    session.add_all(articles)
    session.commit()
    return articles

@pytest.fixture
def sample_article_links(session):
    """創建測試文章連結數據"""
    links = [
        ArticleLinks(
            article_link="https://example.com/article1",
            is_scraped=False,
            source_name="測試來源1",
            source_url="https://example.com/source1"
        ),
        ArticleLinks(
            article_link="https://example.com/article2",
            is_scraped=False,
            source_name="測試來源1",
            source_url="https://example.com/source2"
        ),
        ArticleLinks(
            article_link="https://example.com/article3",
            is_scraped=True,
            source_name="測試來源2",
            source_url="https://example.com/source3"
        )
    ]
    session.add_all(links)
    session.commit()
    return links

# ArticleLinksRepository 測試
class TestArticleLinksRepository:
    """測試 ArticleLinks Repository 的所有功能"""
    
    def test_get_schema_class(self, article_links_repo):
        """測試獲取schema類的方法"""
        # 測試默認返回
        schema = article_links_repo.get_schema_class()
        assert schema == ArticleLinksCreateSchema
        
        # 測試各種類型的schema
        create_schema = article_links_repo.get_schema_class(SchemaType.CREATE)
        assert create_schema == ArticleLinksCreateSchema
        
        update_schema = article_links_repo.get_schema_class(SchemaType.UPDATE)
        assert update_schema == ArticleLinksUpdateSchema
        
        with pytest.raises(ValueError) as exc_info:
            article_links_repo.get_schema_class(SchemaType.LIST)
        assert "未支援的 schema 類型" in str(exc_info.value)
    
    def test_find_by_article_link(self, article_links_repo, sample_article_links):
        """測試根據文章連結查詢"""
        # 測試存在的連結
        result = article_links_repo.find_by_article_link("https://example.com/article1")
        assert result is not None
        assert result.article_link == "https://example.com/article1"
        assert result.source_name == "測試來源1"
        
        # 測試不存在的連結
        result = article_links_repo.find_by_article_link("https://nonexistent.com")
        assert result is None

    def test_find_unscraped_links(self, article_links_repo, sample_article_links):
        """測試查詢未爬取的連結"""
        # 測試無過濾條件
        results = article_links_repo.find_unscraped_links()
        assert len(results) == 2
        assert all(not link.is_scraped for link in results)
        
        # 測試限制數量
        results = article_links_repo.find_unscraped_links(limit=1)
        assert len(results) == 1
        
        # 測試來源過濾
        results = article_links_repo.find_unscraped_links(source_name="測試來源1")
        assert len(results) == 2
        assert all(link.source_name == "測試來源1" and not link.is_scraped for link in results)

    def test_count_unscraped_links(self, article_links_repo, sample_article_links):
        """測試計算未爬取的連結數量"""
        # 測試總數
        count = article_links_repo.count_unscraped_links()
        assert count == 2
        
        # 測試特定來源的數量
        count = article_links_repo.count_unscraped_links(source_name="測試來源1")
        assert count == 2
        
        count = article_links_repo.count_unscraped_links(source_name="測試來源2")
        assert count == 0

    def test_mark_as_scraped(self, article_links_repo, sample_article_links):
        """測試標記文章為已爬取"""
        # 測試標記存在的連結
        success = article_links_repo.mark_as_scraped("https://example.com/article1")
        assert success is True
        
        # 驗證狀態已更新
        link = article_links_repo.find_by_article_link("https://example.com/article1")
        assert link.is_scraped is True
        
        # 測試標記不存在的連結
        success = article_links_repo.mark_as_scraped("https://nonexistent.com")
        assert success is False

    def test_get_source_statistics(self, article_links_repo, sample_article_links):
        """測試獲取來源統計"""
        stats = article_links_repo.get_source_statistics()
        
        # 驗證測試來源1的統計
        source1_stats = stats["測試來源1"]
        assert source1_stats["total"] == 2
        assert source1_stats["unscraped"] == 2
        assert source1_stats["scraped"] == 0
        
        # 驗證測試來源2的統計
        source2_stats = stats["測試來源2"]
        assert source2_stats["total"] == 1
        assert source2_stats["unscraped"] == 0
        assert source2_stats["scraped"] == 1

    def test_create(self, article_links_repo):
        """測試創建文章連結"""
        # 測試成功創建
        new_link_data = {
            "article_link": "https://example.com/new-article",
            "source_name": "新測試來源",
            "source_url": "https://example.com/new-source",
            "is_scraped": False
        }
        
        new_link = article_links_repo.create(new_link_data)
        assert new_link is not None
        assert new_link.article_link == new_link_data["article_link"]
        assert new_link.source_name == new_link_data["source_name"]
        
        # 測試創建重複連結
        with pytest.raises(ValidationError) as exc_info:
            article_links_repo.create(new_link_data)
        assert "已存在具有相同連結的文章" in str(exc_info.value)
        
        # 測試缺少必填欄位
        invalid_data = {
            "article_link": "https://example.com/another-article"
        }
        with pytest.raises(ValidationError):
            article_links_repo.create(invalid_data)

    def test_update(self, article_links_repo, sample_article_links):
        """測試更新文章連結"""
        # 獲取第一個連結的ID
        link = article_links_repo.find_by_article_link("https://example.com/article1")
        link_id = link.id
        
        # 更新數據
        update_data = {
            "is_scraped": True,
            "source_name": "更新後的來源"
        }
        
        updated_link = article_links_repo.update(link_id, update_data)
        assert updated_link is not None
        assert updated_link.is_scraped is True
        assert updated_link.source_name == "更新後的來源"
        assert updated_link.article_link == "https://example.com/article1"  # 未更新的欄位應保持不變
        
        # 測試更新不存在的ID
        non_existent_id = 9999
        result = article_links_repo.update(non_existent_id, update_data)
        assert result is None

    def test_batch_mark_as_scraped(self, article_links_repo, sample_article_links):
        """測試批量標記為已爬取"""
        links_to_mark = [
            "https://example.com/article1",
            "https://example.com/article2",
            "https://nonexistent.com"
        ]
        
        result = article_links_repo.batch_mark_as_scraped(links_to_mark)
        
        assert result["success_count"] == 2
        assert result["fail_count"] == 1
        assert "https://nonexistent.com" in result["failed_links"]
        
        # 驗證更新後的狀態
        for link in ["https://example.com/article1", "https://example.com/article2"]:
            article_link = article_links_repo.find_by_article_link(link)
            assert article_link.is_scraped is True

    def test_execute_query_error_handling(self, article_links_repo):
        """測試執行查詢時的錯誤處理"""
        def failing_query():
            raise Exception("測試錯誤")
            
        with pytest.raises(DatabaseOperationError) as exc_info:
            article_links_repo.execute_query(
                failing_query,
                err_msg="測試錯誤處理"
            )
        assert "測試錯誤處理" in str(exc_info.value)

class TestErrorHandling:
    """測試錯誤處理情況"""
    
    def test_database_error_handling(self, article_links_repo):
        """測試資料庫錯誤處理"""
        with pytest.raises(DatabaseOperationError) as excinfo:
            article_links_repo.execute_query(
                lambda: article_links_repo.session.execute("SELECT * FROM nonexistent_table")
            )
        assert "資料庫操作錯誤" in str(excinfo.value)

    def test_invalid_operation_handling(self, article_links_repo):
        """測試無效操作處理"""
        with pytest.raises(DatabaseOperationError) as excinfo:
            article_links_repo.get_all(sort_by="nonexistent_column")
        assert "無效的排序欄位" in str(excinfo.value)

    def test_database_connection_error(self, article_links_repo, session):
        """測試資料庫連接錯誤"""
        # 先關閉 session
        session.close()
        # 移除 session 的綁定
        session.bind = None
        
        with pytest.raises(DatabaseConnectionError) as excinfo:
            article_links_repo.find_unscraped_links()
        assert "資料庫連接已關閉" in str(excinfo.value)

class TestArticleLinksRelationship:
    """測試Article和ArticleLinks的關係"""
    
    def test_article_links_relationship(self, session, article_repo, article_links_repo):
        """測試ArticleLinks和Article之間的關係"""
        # 先創建一篇文章
        article_data = {
            "title": "關係測試文章",
            "link": "https://example.com/relation-test",
            "content": "測試文章和連結關係",
            "is_ai_related": True,
            "source": "測試來源",
            "published_at": datetime.now(timezone.utc)
        }
        article = article_repo.create(article_data)
        session.flush()
        
        # 創建對應的連結
        link_data = {
            "article_link": "https://example.com/relation-test",
            "is_scraped": True,
            "source_name": "測試來源",
            "source_url": f"https://example.com/source-{uuid.uuid4()}"
        }
        article_link = article_links_repo.create(link_data)
        
        # 根據連結查找文章
        found_article = article_repo.find_by_link(article_link.article_link)
        assert found_article is not None
        assert found_article.id == article.id
        
        # 反向測試 - 根據文章連結查找相關連結
        found_links = article_links_repo.find_by_article_link(article.link)
        assert found_links is not None