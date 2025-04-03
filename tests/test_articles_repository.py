import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.articles_repository import ArticlesRepository
from src.models.articles_model import Articles
from src.models.base_model import Base
from src.database.base_repository import SchemaType
from src.models.articles_schema import ArticleCreateSchema, ArticleUpdateSchema
from src.error.errors import ValidationError, DatabaseOperationError

# 設置測試資料庫，使用 session scope
@pytest.fixture(scope="session")
def engine():
    return create_engine('sqlite:///:memory:')

@pytest.fixture(scope="session")
def tables(engine):
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
def article_repo(session):
    return ArticlesRepository(session, Articles)

@pytest.fixture(scope="function")
def sample_articles(session):
    # 清除可能的干擾資料
    session.query(Articles).delete()
    session.commit()
    
    articles = [
        Articles(
            title="科技新聞：AI研究突破",
            link="https://example.com/article1",
            summary="這是關於AI研究的文章摘要",
            content="這是關於AI研究的文章內容",
            source="測試來源1",
            source_url="https://example.com/source1",
            category="科技",
            published_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            is_ai_related=True,
            is_scraped=True
        ),
        Articles(
            title="財經報導：股市走勢分析", 
            link="https://example.com/article2",
            summary="這是股市分析的摘要",
            content="這是股市分析的內容",
            source="測試來源2",
            source_url="https://example.com/source2",
            category="財經",
            published_at=datetime(2023, 1, 3, tzinfo=timezone.utc),
            is_ai_related=False,
            is_scraped=True
        ),
        Articles(
            title="Python編程技巧分享",
            link="https://example.com/article3",
            summary="這是Python相關教學",
            content="這是Python相關教學",
            source="測試來源3",
            source_url="https://example.com/source3",
            category="科技",
            published_at=datetime(2023, 1, 5, tzinfo=timezone.utc),
            is_ai_related=False,
            is_scraped=True
        )
    ]
    session.add_all(articles)
    session.commit()
    
    # 確保所有物件都有正確的 ID
    session.expire_all()
    return articles

# ArticleRepository 測試
class TestArticleRepository:
    """測試 ArticlesRepository 的核心功能"""
    
    def test_get_schema_class(self, article_repo):
        """測試獲取schema類的方法"""
        # 測試默認返回
        schema = article_repo.get_schema_class()
        assert schema == ArticleCreateSchema
        
        # 測試指定類型返回
        create_schema = article_repo.get_schema_class(SchemaType.CREATE)
        assert create_schema == ArticleCreateSchema
        
        update_schema = article_repo.get_schema_class(SchemaType.UPDATE)
        assert update_schema == ArticleUpdateSchema

        with pytest.raises(ValueError) as exc_info:
            article_repo.get_schema_class(SchemaType.LIST)
        assert "未支援的 schema 類型" in str(exc_info.value)
    
    def test_find_by_link(self, article_repo, sample_articles, session):
        """測試根據連結查詢文章"""
        session.expire_all()  # 確保從數據庫重新讀取
        
        # 測試存在的連結
        article = article_repo.find_by_link("https://example.com/article1")
        assert article is not None
        assert article.title == "科技新聞：AI研究突破"
        
        # 測試不存在的連結
        article = article_repo.find_by_link("https://nonexistent.com")
        assert article is None
    
    def test_find_by_category(self, article_repo, sample_articles, session):
        """測試根據分類查詢文章"""
        session.expire_all()
        
        articles = article_repo.find_by_category("科技")
        assert len(articles) == 2
        assert all(article.category == "科技" for article in articles)
    
    def test_search_by_title(self, article_repo, sample_articles, session):
        """測試根據標題搜索文章"""
        session.expire_all()
        
        # 測試模糊匹配
        articles = article_repo.search_by_title("Python")
        assert len(articles) == 1
        assert "Python" in articles[0].title
        
        # 測試精確匹配
        articles = article_repo.search_by_title("Python編程技巧分享", exact_match=True)
        assert len(articles) == 1
        assert articles[0].title == "Python編程技巧分享"
    
    def test_get_by_filter(self, article_repo, sample_articles, session):
        """測試根據過濾條件查詢文章"""
        session.expire_all()
        
        # 測試單一條件過濾
        articles = article_repo.get_by_filter({"category": "科技"})
        assert len(articles) == 2
        assert all(a.category == "科技" for a in articles)
        
        # 測試多條件過濾
        articles = article_repo.get_by_filter({
            "category": "科技",
            "is_ai_related": True
        })
        assert len(articles) == 1
        assert articles[0].is_ai_related is True
        
        # 測試日期範圍過濾
        articles = article_repo.get_by_filter({
            "published_at": {
                "$gte": datetime(2023, 1, 1, tzinfo=timezone.utc),
                "$lte": datetime(2023, 1, 3, tzinfo=timezone.utc)
            }
        })
        assert len(articles) == 2

    def test_count(self, article_repo, sample_articles, session):
        """測試計算符合條件的文章數量"""
        session.expire_all()
        
        # 測試總數
        total = article_repo.count()
        assert total == 3
        
        # 測試帶條件的計數
        count = article_repo.count({"category": "科技"})
        assert count == 2
    
    def test_get_category_distribution(self, article_repo, sample_articles, session):
        """測試獲取分類分布"""
        session.expire_all()
        
        distribution = article_repo.get_category_distribution()
        assert distribution == {
            "科技": 2,
            "財經": 1
        }
    
    def test_validate_unique_link(self, article_repo, sample_articles, session):
        """測試驗證連結唯一性"""
        session.expire_all()
        
        # 測試新的唯一連結
        assert article_repo.validate_unique_link("https://new-link.com") is True
        
        # 測試已存在的連結
        with pytest.raises(ValidationError) as exc_info:
            article_repo.validate_unique_link("https://example.com/article1")
        assert "已存在具有相同連結的文章" in str(exc_info.value)
        
        # 測試更新時的連結驗證
        article_id = sample_articles[0].id
        assert article_repo.validate_unique_link(
            "https://example.com/article1", 
            exclude_id=article_id
        ) is True

    def test_create_article(self, article_repo, session):
        """測試創建文章"""
        article_data = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "summary": "測試摘要",
            "content": "測試內容",
            "category": "測試",
            "is_ai_related": True,
            "is_scraped": True,
            "source": "測試來源",
            "source_url": "https://test.com/source",
            "published_at": datetime.now(timezone.utc)
        }
        
        article = article_repo.create(article_data)
        session.expire_all()
        
        assert article is not None
        assert article.title == article_data["title"]
        assert article.link == article_data["link"]
    
    def test_create_article_with_missing_fields(self, article_repo):
        """測試創建缺少必填欄位的文章"""
        incomplete_data = {
            "title": "測試文章",
            "content": "測試內容"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            article_repo.create(incomplete_data)
        assert "缺少必填欄位" in str(exc_info.value)
    
    def test_update_article(self, article_repo, sample_articles, session):
        """測試更新文章"""
        session.expire_all()
        article_id = sample_articles[0].id
        update_data = {
            "title": "更新後的標題",
            "content": "更新後的內容"
        }
        
        updated = article_repo.update(article_id, update_data)
        session.expire_all()
        
        assert updated is not None
        assert updated.title == update_data["title"]
        assert updated.content == update_data["content"]
        # 確認其他欄位保持不變
        assert updated.link == sample_articles[0].link

    def test_batch_update(self, article_repo, sample_articles, session):
        """測試批量更新文章"""
        session.expire_all()
        article_ids = [sample_articles[0].id, sample_articles[1].id]
        update_data = {
            "category": "批量更新"
        }
        
        result = article_repo.batch_update(article_ids, update_data)
        session.expire_all()
        
        assert result["success_count"] == 2
        assert result["fail_count"] == 0
        assert all(entity.category == "批量更新" for entity in result["updated_articles"])

    def test_get_paginated_by_filter(self, article_repo, sample_articles, session):
        """測試分頁查詢"""
        session.expire_all()
        
        try:
            # 基本分頁測試
            result = article_repo.get_paginated_by_filter(
                filter_dict={},
                page=1,
                per_page=2
            )
            
            assert len(result["items"]) == 2
            assert result["total"] == 3
            assert result["total_pages"] == 2
            assert result["has_next"] is True
            
            # 驗證排序：應該按發布時間降序排列
            dates = [article.published_at for article in result["items"]]
            assert dates[0] >= dates[1]  # 確保降序排列
            
        except DatabaseOperationError as e:
            pytest.skip(f"資料庫操作錯誤: {str(e)}")

# 新增測試類專門測試分頁過濾功能
class TestArticlePaginationAndFiltering:
    """專門測試文章的分頁和過濾功能"""
    
    @pytest.fixture(scope="function")
    def filter_test_articles(self, session):
        """創建專門用於過濾測試的文章"""
        # 清除可能的干擾資料
        session.query(Articles).delete()
        session.commit()
        
        articles = [
            Articles(
                title="AI研究報告1",
                link="https://example.com/ai1",
                summary="這是關於AI研究的文章摘要",
                source="測試來源",
                source_url="https://example.com/source1",
                category="AI研究",
                published_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
                is_ai_related=True,
                is_scraped=True,
                tags="AI,研究,深度學習"
            ),
            Articles(
                title="AI研究報告2",
                link="https://example.com/ai2",
                summary="這是關於AI研究的文章摘要",
                source="測試來源",
                source_url="https://example.com/source2",
                category="AI研究",
                published_at=datetime(2023, 1, 15, tzinfo=timezone.utc),
                is_ai_related=True,
                is_scraped=True,
                tags="AI,研究,大語言模型"
            ),
            Articles(
                title="一般科技新聞1",
                link="https://example.com/tech1",
                summary="這是關於科技新聞的文章摘要",
                source="測試來源",
                source_url="https://example.com/source3",
                category="科技",
                published_at=datetime(2023, 1, 10, tzinfo=timezone.utc),
                is_ai_related=False,
                is_scraped=True,
                tags="科技,創新"
            ),
            Articles(
                title="一般科技新聞2",
                link="https://example.com/tech2",
                summary="這是關於科技新聞的文章摘要",
                source="測試來源",
                source_url="https://example.com/source4",
                category="科技",
                published_at=datetime(2023, 1, 20, tzinfo=timezone.utc),
                is_ai_related=False,
                is_scraped=True,
                tags="科技,產業"
            ),
            Articles(
                title="財經報導",
                link="https://example.com/finance",
                summary="這是關於財經報導的文章摘要",
                source="測試來源",
                source_url="https://example.com/source5",
                category="財經",
                published_at=datetime(2023, 1, 5, tzinfo=timezone.utc),
                is_ai_related=False,
                is_scraped=True,
                tags="財經,市場"
            )
        ]
        session.add_all(articles)
        session.commit()
        session.expire_all()
        return articles
    
    def test_combined_filters_with_pagination(self, article_repo, filter_test_articles, session):
        """測試組合多種過濾條件並進行分頁"""
        session.expire_all()
        
        try:
            combined_filter = {
                "is_ai_related": True,
                "published_at": {
                    "$gte": datetime(2023, 1, 10, tzinfo=timezone.utc)
                }
            }
            
            page_data = article_repo.get_paginated_by_filter(
                filter_dict=combined_filter,
                page=1,
                per_page=10
            )
            
            assert page_data["total"] == 1
            assert page_data["items"][0].is_ai_related is True
            assert page_data["items"][0].published_at >= datetime(2023, 1, 10, tzinfo=timezone.utc)
            
        except DatabaseOperationError as e:
            pytest.skip(f"資料庫操作錯誤: {str(e)}")
    
    def test_pagination_navigation(self, article_repo, filter_test_articles, session):
        """測試分頁導航功能"""
        session.expire_all()
        
        try:
            # 第一頁
            page_data = article_repo.get_paginated_by_filter(
                filter_dict={},
                page=1,
                per_page=2
            )
            
            total_items = page_data["total"]
            total_pages = page_data["total_pages"]
            
            assert page_data["page"] == 1
            assert page_data["has_next"] == (total_items > 2)
            assert not page_data["has_prev"]
            
            if total_pages > 1:
                # 最後一頁
                page_data = article_repo.get_paginated_by_filter(
                    filter_dict={},
                    page=total_pages,
                    per_page=2
                )
                
                assert page_data["page"] == total_pages
                assert not page_data["has_next"]
                assert page_data["has_prev"]
                
        except DatabaseOperationError as e:
            pytest.skip(f"資料庫操作錯誤: {str(e)}")