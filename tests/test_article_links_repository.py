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
def sample_article_links(session, sample_articles):
    """創建測試文章連結數據"""
    links = [
        ArticleLinks(
            article_link="https://example.com/article1",  # 對應第一篇文章
            is_scraped=False,
            source_name="測試來源1",
            source_url=f"https://example.com/source-{uuid.uuid4()}"
        ),
        ArticleLinks(
            article_link="https://example.com/article2",  # 對應第二篇文章
            is_scraped=False,
            source_name="測試來源1",
            source_url=f"https://example.com/source-{uuid.uuid4()}"
        ),
        ArticleLinks(
            article_link="https://example.com/article3",  # 對應第三篇文章
            is_scraped=True,
            source_name="測試來源2",
            source_url=f"https://example.com/source-{uuid.uuid4()}"
        )
    ]
    session.add_all(links)
    session.commit()
    return links

# ArticleLinksRepository 測試
class TestArticleLinksRepository:
    """測試 ArticleLinks Repository 的所有功能"""
    
    def test_find_by_article_link(self, article_links_repo, sample_article_links):
        """測試根據文章連結查詢"""
        # 測試存在的連結
        result = article_links_repo.find_by_article_link("https://example.com/article1")
        assert result is not None
        assert result.article_link == "https://example.com/article1"
        
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
        assert all(link.source_name == "測試來源1" for link in results)

    def test_count_unscraped_links(self, article_links_repo, sample_article_links):
        """測試計算未爬取的連結數量"""
        # 測試總數
        count = article_links_repo.count_unscraped_links()
        assert count == 2
        
        # 測試特定來源的數量
        count = article_links_repo.count_unscraped_links(source_name="測試來源1")
        assert count > 0

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
        
        # 驗證統計結果格式
        assert isinstance(stats, dict)
        
        # 驗證測試來源1的統計
        source1_stats = stats.get("測試來源1", {})
        assert source1_stats["total"] == 2  # 應該有2篇文章
        assert source1_stats["unscraped"] == 2  # 都未爬取
        assert source1_stats["scraped"] == 0  # 沒有已爬取的
        
        # 驗證測試來源2的統計
        source2_stats = stats.get("測試來源2", {})
        assert source2_stats["total"] == 1  # 應該有1篇文章
        assert source2_stats["unscraped"] == 0  # 沒有未爬取的
        assert source2_stats["scraped"] == 1  # 1篇已爬取

    def test_create_article_link_success(self, article_links_repo, sample_articles):
        """測試成功創建文章連結"""
        # 為創建新連結先準備一篇新文章
        new_article_data = {
            "title": "新測試文章",
            "link": "https://example.com/new-article",
            "content": "新測試內容",
            "is_ai_related": True,
            "source": "新測試來源",
            "published_at": datetime.now(timezone.utc)
        }
        
        article_repo = ArticlesRepository(article_links_repo.session, Articles)
        article = article_repo.create(new_article_data)
        article_links_repo.session.flush()
        
        # 準備有效的連結數據
        valid_data = {
            "article_link": "https://example.com/new-article",
            "source_name": "新測試來源", 
            "source_url": "https://example.com/new-source",
            "is_scraped": False
        }
        
        # 首次創建應該成功
        new_link = article_links_repo.create_article_link(valid_data)
        assert new_link is not None
        assert new_link.article_link == valid_data["article_link"]

    def test_create_article_link_missing_fields(self, article_links_repo, sample_articles):
        """測試缺少必填欄位"""
        # 準備一篇新文章
        new_article = Articles(
            title="無關文章",
            link="https://example.com/another-article",
            content="測試內容",
            is_ai_related=True,
            source="測試來源",
            published_at=datetime.now(timezone.utc)
        )
        article_links_repo.session.add(new_article)
        article_links_repo.session.flush()
        
        # 缺少必填欄位
        invalid_data = {
            "article_link": "https://example.com/another-article"
            # 故意缺少source_name和source_url
        }
        
        with pytest.raises(ValidationError) as excinfo:
            article_links_repo.create_article_link(invalid_data)
        assert "不能為空" in str(excinfo.value)

    def test_create_article_link_duplicate(self, article_links_repo, sample_article_links):
        """測試創建重複連結"""
        # 首先確認連結確實存在
        article_link = "https://example.com/article1"
        existing = article_links_repo.find_by_article_link(article_link)
        assert existing is not None, "測試前提條件失敗：連結應該已存在"
        
        # 列印連結以調試
        print(f"測試中已存在的連結: {existing.article_link}")
        
        # 嘗試重複創建
        duplicate_data = {
            "article_link": article_link,
            "source_name": "測試來源X", 
            "source_url": "https://example.com/source-x"
        }
        
        with pytest.raises(ValidationError) as excinfo:
            article_links_repo.create_article_link(duplicate_data)
        assert "文章連結已存在" in str(excinfo.value)

    def test_update_article_link(self, article_links_repo, sample_article_links):
        """測試使用模式驗證更新文章連結"""
        # 獲取第一個文章連結
        link_id = sample_article_links[0].id
        
        # 準備更新數據
        update_data = {
            "source_name": "已更新的來源",
            "is_scraped": True
        }
        
        # 執行更新
        updated_link = article_links_repo.update_article_link(link_id, update_data)
        assert updated_link is not None
        assert updated_link.source_name == "已更新的來源"
        assert updated_link.is_scraped is True
        
        # 測試更新不允許的欄位
        invalid_update = {
            "article_link": "https://example.com/changed-link"  # 不允許更新
        }
        
        with pytest.raises(ValidationError) as excinfo:
            article_links_repo.update_article_link(link_id, invalid_update)
        assert "不允許更新" in str(excinfo.value)
        
        # 測試更新不存在的 ID
        result = article_links_repo.update_article_link(999, update_data)
        assert result is None

    def test_batch_mark_as_scraped(self, article_links_repo, sample_article_links):
        """測試批量標記為已爬取"""
        links_to_mark = [
            "https://example.com/article1",
            "https://example.com/article2",
            "https://nonexistent.com"  # 不存在的連結
        ]
        
        result = article_links_repo.batch_mark_as_scraped(links_to_mark)
        
        # 驗證結果格式
        assert "success_count" in result
        assert "fail_count" in result
        assert "failed_links" in result
        
        # 驗證處理結果
        assert result["success_count"] == 2  # 兩個有效連結
        assert result["fail_count"] == 1     # 一個無效連結
        assert "https://nonexistent.com" in result["failed_links"]
        
        # 驗證更新後的狀態
        for link in links_to_mark[:-1]:  # 排除不存在的連結
            article_link = article_links_repo.find_by_article_link(link)
            assert article_link.is_scraped is True

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
        with pytest.raises(InvalidOperationError) as excinfo:
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
        article_link = article_links_repo.create_article_link(link_data)
        
        # 根據連結查找文章
        found_article = article_repo.find_by_link(article_link.article_link)
        assert found_article is not None
        assert found_article.id == article.id
        
        # 反向測試 - 根據文章連結查找相關連結
        found_links = article_links_repo.find_by_article_link(article.link)
        assert found_links is not None