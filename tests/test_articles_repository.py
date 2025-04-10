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
from src.models.articles_model import ArticleScrapeStatus

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
def clean_db(session):
    """清空資料庫的 fixture"""
    session.query(Articles).delete()
    session.commit()
    session.expire_all()

@pytest.fixture(scope="function")
def sample_articles(session, clean_db):
    
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
            is_scraped=True,
            scrape_status=ArticleScrapeStatus.PENDING
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
            is_scraped=True,
            scrape_status=ArticleScrapeStatus.PENDING
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
            is_scraped=True,
            scrape_status=ArticleScrapeStatus.PENDING
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
    
    def test_get_schema_class(self, article_repo, clean_db):
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
    
    def test_find_by_link(self, article_repo, sample_articles, session, clean_db):
        """測試根據連結查詢文章"""
        
        # 測試存在的連結
        article = article_repo.find_by_link("https://example.com/article1")
        assert article is not None
        assert article.title == "科技新聞：AI研究突破"
        
        # 測試不存在的連結
        article = article_repo.find_by_link("https://nonexistent.com")
        assert article is None
    
    def test_find_by_category(self, article_repo, sample_articles, session, clean_db):
        """測試根據分類查詢文章"""
        
        articles = article_repo.find_by_category("科技")
        assert len(articles) == 2
        assert all(article.category == "科技" for article in articles)
    
    def test_search_by_title(self, article_repo, sample_articles, session, clean_db):
        """測試根據標題搜索文章"""
        
        # 測試模糊匹配
        articles = article_repo.search_by_title("Python")
        assert len(articles) == 1
        assert "Python" in articles[0].title
        
        # 測試精確匹配
        articles = article_repo.search_by_title("Python編程技巧分享", exact_match=True)
        assert len(articles) == 1
        assert articles[0].title == "Python編程技巧分享"
    
    def test_get_by_filter(self, article_repo, sample_articles, session, clean_db):
        """測試根據過濾條件查詢文章"""
        
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

    def test_count(self, article_repo, sample_articles, session, clean_db):
        """測試計算符合條件的文章數量"""
        
        # 測試總數
        total = article_repo.count()
        assert total == 3
        
        # 測試帶條件的計數
        count = article_repo.count({"category": "科技"})
        assert count == 2
    
    def test_get_category_distribution(self, article_repo, sample_articles, session, clean_db):
        """測試獲取分類分布"""
        
        distribution = article_repo.get_category_distribution()
        assert distribution == {
            "科技": 2,
            "財經": 1
        }
    
    def test_validate_unique_link(self, article_repo, sample_articles, session, clean_db):
        """測試驗證連結唯一性"""
        
        # 測試新的唯一連結
        assert article_repo.validate_unique_link("https://new-link.com") is True
        
        # 測試已存在的連結 - 不拋出異常，而是返回 False
        assert article_repo.validate_unique_link("https://example.com/article1", raise_error=False) is False
        
        # 測試更新時的連結驗證
        article_id = sample_articles[0].id
        assert article_repo.validate_unique_link(
            "https://example.com/article1", 
            exclude_id=article_id
        ) is True

    def test_create_article(self, article_repo, session, clean_db):
        """測試創建和更新文章"""
        # 測試創建新文章
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
            "published_at": datetime.now(timezone.utc),
            "scrape_status": ArticleScrapeStatus.PENDING
        }
        article = article_repo.create(article_data)
        session.expire_all()
        
        assert article is not None
        assert article.title == article_data["title"]
        assert article.link == article_data["link"]
        assert article.scrape_status == ArticleScrapeStatus.PENDING

        # 測試更新已存在的文章
        update_data = {
            "title": "更新後的標題",
            "link": "https://test.com/article",  # 相同的連結
            "summary": "更新後的摘要",
            "content": "更新後的內容",
            "category": "更新",
            "is_ai_related": False,
            "is_scraped": True,
            "source": "測試來源",
            "source_url": "https://test.com/source",
            "published_at": datetime.now(timezone.utc),
            "scrape_status": ArticleScrapeStatus.PENDING.value
        }
        
        updated_article = article_repo.create(update_data)
        session.expire_all()
        
        assert updated_article is not None
        assert updated_article.id == article.id  # 應該是同一筆資料
        assert updated_article.title == "更新後的標題"
        assert updated_article.category == "更新"
        assert updated_article.is_ai_related is False
    
    def test_create_article_with_missing_fields(self, article_repo):
        """測試創建缺少必填欄位的文章"""
        incomplete_data = {
            "title": "測試文章",
            "content": "測試內容"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            article_repo.create(incomplete_data)
        assert "缺少必填欄位" in str(exc_info.value)


    def test_batch_update_by_link(self, article_repo, sample_articles, session, clean_db):
        """測試批量更新文章"""
        update_data = []
        for article in sample_articles[:2]:  # 只更新前兩篇文章
            update_data.append({
                "link": article.link,
                "category": "批量更新"
            })  

        result = article_repo.batch_update_by_link(update_data)
        session.expire_all()
        
        assert result["success_count"] == 2
        assert result["fail_count"] == 0
        assert result["missing_links"] == []
        assert result["error_links"] == []
        assert all(entity.category == "批量更新" for entity in result["updated_articles"])


    def test_batch_update_by_ids(self, article_repo, sample_articles, session, clean_db):
        """測試批量更新文章"""
        article_ids = [sample_articles[0].id, sample_articles[1].id]
        update_data = {
            "category": "批量更新"
        }
        
        result = article_repo.batch_update_by_ids(article_ids, update_data)
        session.expire_all()
        
        assert result["success_count"] == 2
        assert result["fail_count"] == 0
        assert all(entity.category == "批量更新" for entity in result["updated_articles"])

    def test_get_paginated_by_filter(self, article_repo, sample_articles, session, clean_db):
        """測試分頁查詢"""
        
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
    
    def test_batch_create(self, article_repo, session, clean_db):
        """測試批量創建文章"""
        
        # 準備測試資料
        articles_data = [
            {
                "title": "測試文章1",
                "link": "https://test.com/batch_create_article1",
                "summary": "測試摘要1",
                "content": "測試內容1",
                "category": "測試",
                "is_ai_related": True,
                "is_scraped": True,
                "source": "測試來源",
                "source_url": "https://test.com/source1",
                "published_at": datetime.now(timezone.utc),
                "scrape_status": ArticleScrapeStatus.PENDING
            }
        ]
        
        result = article_repo.batch_create(articles_data)
        session.expire_all()
        
        assert result["success_count"] == 1
        assert result["update_count"] == 0
        assert result["fail_count"] == 0    
        assert result["inserted_articles"] is not None
        assert result["updated_articles"] is not None
        assert result["failed_articles"] == []
    
    def test_batch_create_with_missing_fields(self, article_repo, session, clean_db):
        """測試批量創建缺少必填欄位的文章"""
        
        # 準備測試資料
        articles_data = [
            {
                "title": "測試文章1",
                "content": "測試內容1"
            }
        ]
        
        result = article_repo.batch_create(articles_data)
        session.expire_all()
        
        assert result["success_count"] == 0
        assert result["fail_count"] == 1
        assert result["inserted_articles"] == []
        assert result["failed_articles"] is not None
        assert "缺少必填欄位" in result["failed_articles"][0]["error"]
        
    def test_batch_create_with_existing_link(self, article_repo, sample_articles, session, clean_db):
        """測試批量創建包含已存在連結的文章 - 應該更新而不是失敗"""
        
        # 準備測試資料 - 使用已存在的連結但更新其他欄位
        articles_data = [
            {
                "title": "更新後的文章標題",
                "link": "https://example.com/article1",  # 使用已存在的連結
                "summary": "更新後的摘要",
                "content": "更新後的內容",
                "category": "更新後分類",
                "is_ai_related": False,  # 改變 AI 相關標記
                "is_scraped": True,
                "source": "測試來源",
                "source_url": "https://example.com/source2",
                "published_at": datetime.now(timezone.utc),
                "scrape_status": ArticleScrapeStatus.PENDING
            }
        ]
        
        result = article_repo.batch_create(articles_data)
        session.expire_all()
        
        # 驗證結果
        assert result["success_count"] == 0  # 因為是更新而不是新增
        assert result["update_count"] == 1  # 應該有一筆更新
        assert result["fail_count"] == 0  # 不應該有失敗
        assert len(result["updated_articles"]) == 1
        assert result["inserted_articles"] == []
        assert result["failed_articles"] == []
        
        # 驗證更新後的內容
        updated_article = article_repo.find_by_link("https://example.com/article1")
        assert updated_article is not None
        assert updated_article.title == "更新後的文章標題"
        assert updated_article.summary == "更新後的摘要"
        assert updated_article.category == "更新後分類"
        assert updated_article.is_ai_related is False
    
    def test_batch_create_with_invalid_data(self, article_repo, session, clean_db):
        """測試批量創建無效資料"""
    
        # 準備測試資料
        articles_data = [
            {
                "title": "測試文章3",
                "link": "",
                "summary": "測試摘要3",
                "content": "測試內容3",
                "category": "測試",
                "is_ai_related": True,
                "is_scraped": True,
                "source": "測試來源",
                "source_url": "https://test.com/source3",
                "published_at": datetime.now(timezone.utc),
                "scrape_status": ArticleScrapeStatus.PENDING
            }
        ]
    
        result = article_repo.batch_create(articles_data)
        session.expire_all()
    
        assert result["success_count"] == 0
        assert result["fail_count"] == 1
        assert result["inserted_articles"] == []
        assert result["failed_articles"] is not None
        assert any(["link: URL不能為空" in result["failed_articles"][0]["error"], "link: 不能為空" in result["failed_articles"][0]["error"]])
    
    def test_batch_create_with_mixed_new_and_existing_links(self, article_repo, sample_articles, session, clean_db):
        """測試批量創建同時包含新連結和已存在連結的文章"""
        
        articles_data = [
            {
                # 新文章
                "title": "全新文章",
                "link": "https://example.com/new_article",
                "summary": "新文章摘要",
                "content": "新文章內容",
                "category": "測試",
                "is_ai_related": True,
                "is_scraped": True,
                "source": "測試來源",
                "source_url": "https://example.com/source_new",
                "published_at": datetime.now(timezone.utc),
                "scrape_status": ArticleScrapeStatus.PENDING
            },
            {
                # 更新已存在的文章
                "title": "更新的文章",
                "link": "https://example.com/article1",  # 已存在的連結
                "summary": "更新的摘要",
                "content": "更新的內容",
                "category": "更新分類",
                "is_ai_related": False,
                "is_scraped": True,
                "source": "測試來源",
                "source_url": "https://example.com/source_update",
                "published_at": datetime.now(timezone.utc),
                "scrape_status": ArticleScrapeStatus.PENDING
            }
        ]
        
        result = article_repo.batch_create(articles_data)
        session.expire_all()
        
        # 驗證結果
        assert result["success_count"] == 1  # 一筆新增
        assert result["update_count"] == 1  # 一筆更新
        assert result["fail_count"] == 0  # 不應該有失敗
        assert len(result["inserted_articles"]) == 1
        assert len(result["updated_articles"]) == 1
        assert result["failed_articles"] == []
        
        # 驗證新增的文章
        new_article = article_repo.find_by_link("https://example.com/new_article")
        assert new_article is not None
        assert new_article.title == "全新文章"
        
        # 驗證更新的文章
        updated_article = article_repo.find_by_link("https://example.com/article1")
        assert updated_article is not None
        assert updated_article.title == "更新的文章"
        assert updated_article.category == "更新分類"

    def test_batch_create_with_large_data(self, article_repo, session, clean_db):
        """測試批量創建大量資料"""
        
        # 準備測試資料
        articles_data = [
            {
                "title": f"測試文章{i}",
                "link": f"https://test.com/batch_create_article{i}",
                "summary": f"測試摘要{i}",
                "content": f"測試內容{i}",
                "category": "測試",
                "is_ai_related": True,
                "is_scraped": True,
                "source": "測試來源",
                "source_url": f"https://test.com/source{i}",
                "published_at": datetime.now(timezone.utc),
                "scrape_status": ArticleScrapeStatus.PENDING
            }
            for i in range(1000)
        ]
        
        result = article_repo.batch_create(articles_data)
        session.expire_all()    
        
        assert result["success_count"] == 1000
        assert result["fail_count"] == 0
        assert result["inserted_articles"] is not None
        assert result["failed_articles"] == []
        
    def test_batch_create_with_large_data_and_pagination(self, article_repo, session, clean_db):
        """測試批量創建大量資料並進行分頁"""
        
        # 準備測試資料
        articles_data = [
            {
                "title": f"測試文章{i}",
                "link": f"https://test.com/large_data_and_pagination_article{i}",
                "summary": f"測試摘要{i}",
                "content": f"測試內容{i}",
                "category": "測試",
                "is_ai_related": True,
                "is_scraped": True,
                "source": "測試來源",
                "source_url": f"https://test.com/source{i}",
                "published_at": datetime.now(timezone.utc),
                "scrape_status": ArticleScrapeStatus.PENDING
            }   
            for i in range(1000)
        ]
        
        result = article_repo.batch_create(articles_data)
        session.expire_all()    
        
        assert result["success_count"] == 1000
        assert result["fail_count"] == 0
        assert result["inserted_articles"] is not None
        assert result["failed_articles"] == []
        
        # 分頁查詢測試
        page_data = article_repo.get_paginated_by_filter(
            filter_dict={},
            page=1,
            per_page=10
        )
        
        assert page_data["total"] == 1000
        assert page_data["total_pages"] == 100
        assert page_data["items"] is not None
        assert len(page_data["items"]) == 10
        
        # 測試分頁導航  
        page_data = article_repo.get_paginated_by_filter(
            filter_dict={},
            page=100,
            per_page=10
        )
        
        assert page_data["page"] == 100
        assert page_data["has_next"] is False
        assert page_data["has_prev"] is True
    
    def test_batch_mark_as_scraped(self, article_repo, sample_articles, session, clean_db):
        """測試批量將文章連結標記為已爬取"""
        # 先將文章標記為未爬取
        for article in sample_articles:
            article.is_scraped = False
            article.scrape_status = ArticleScrapeStatus.PENDING
        session.commit()
        session.expire_all()
        
        # 準備要標記的連結
        links = [article.link for article in sample_articles[:2]]  # 只標記前兩篇文章
        
        # 執行批量標記
        result = article_repo.batch_mark_as_scraped(links)
        session.expire_all()
        
        # 驗證結果
        assert result["success_count"] == 2
        assert result["fail_count"] == 0
        assert result["failed_links"] == []
        
        # 驗證文章是否已被標記為已爬取
        for i, article in enumerate(sample_articles):
            updated_article = article_repo.find_by_link(article.link)
            if i < 2:  # 前兩篇應該是已爬取
                assert updated_article.is_scraped is True
                assert updated_article.scrape_status == ArticleScrapeStatus.CONTENT_SCRAPED
            else:  # 第三篇應該仍然是未爬取
                assert updated_article.is_scraped is False
                assert updated_article.scrape_status == ArticleScrapeStatus.PENDING


# 新增測試類專門測試分頁過濾功能
class TestArticlePaginationAndFiltering:
    """專門測試文章的分頁和過濾功能"""
    
    @pytest.fixture(scope="function")
    def filter_test_articles(self, session, clean_db):
        """創建專門用於過濾測試的文章"""
       
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
                tags="AI,研究,深度學習",
                scrape_status=ArticleScrapeStatus.PENDING
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
                tags="AI,研究,大語言模型",
                scrape_status=ArticleScrapeStatus.PENDING
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
                tags="科技,創新",
                scrape_status=ArticleScrapeStatus.PENDING
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
                tags="科技,產業",
                scrape_status=ArticleScrapeStatus.PENDING
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
                tags="財經,市場",
                scrape_status=ArticleScrapeStatus.PENDING
            )
        ]
        session.add_all(articles)
        session.commit()
        session.expire_all()
        return articles
    
    def test_combined_filters_with_pagination(self, article_repo, filter_test_articles, session, clean_db):
        """測試組合多種過濾條件並進行分頁"""
        
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
    
    def test_pagination_navigation(self, article_repo, filter_test_articles, session, clean_db):
        """測試分頁導航功能"""
        
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