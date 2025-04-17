import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.articles_model import Articles, Base, ArticleScrapeStatus
from src.services.article_service import ArticleService
from src.models.articles_schema import ArticleReadSchema, PaginatedArticleResponse
from src.database.database_manager import DatabaseManager
from src.models.crawler_tasks_model import CrawlerTasks, ScrapeMode

# 設置測試資料庫
@pytest.fixture(scope="session")
def engine():
    """創建測試用的資料庫引擎"""
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
def article_service(session):
    """創建文章服務實例"""
    # 使用記憶體資料庫
    db_manager = DatabaseManager('sqlite:///:memory:')
    # 設置測試用的 session
    db_manager.Session = sessionmaker(bind=session.get_bind())
    return ArticleService(db_manager)

@pytest.fixture(scope="function")
def sample_articles(session):
    """創建測試用的文章資料"""
    # 清除現有資料
    session.query(Articles).delete()
    session.commit()

    articles = [
        Articles(
            title="AI發展新突破",
            link="https://example.com/ai1",
            summary="AI領域的重大突破",
            content="詳細的AI研究內容",
            source="科技日報",
            source_url="https://example.com/source1",
            category="AI研究",
            published_at=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            is_ai_related=True,
            is_scraped=True,
            scrape_status=ArticleScrapeStatus.CONTENT_SCRAPED,
            tags="AI,研究"
        ),
        Articles(
            title="市場分析報告",
            link="https://example.com/market1",
            summary="市場趨勢分析",
            content="詳細的市場分析內容",
            source="財經週刊",
            source_url="https://example.com/source2",
            category="財經",
            published_at=datetime(2023, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
            is_ai_related=False,
            is_scraped=True,
            scrape_status=ArticleScrapeStatus.CONTENT_SCRAPED,
            tags="財經,市場"
        ),
        Articles(
            title="機器學習應用",
            link="https://example.com/ml1",
            summary="機器學習在產業的應用",
            content="機器學習應用案例",
            source="科技日報",
            source_url="https://example.com/source3",
            category="AI研究",
            published_at=datetime(2023, 1, 3, 12, 0, 0, tzinfo=timezone.utc),
            is_ai_related=True,
            is_scraped=True,
            scrape_status=ArticleScrapeStatus.CONTENT_SCRAPED,
            tags="AI,機器學習"
        ),
        Articles(
            title="待抓取新聞",
            link="https://example.com/news1",
            summary="等待抓取的新聞",
            content=None,
            source="新聞網",
            source_url="https://example.com/source4",
            category="新聞",
            published_at=datetime(2023, 1, 4, 12, 0, 0, tzinfo=timezone.utc),
            is_ai_related=False,
            is_scraped=False,
            scrape_status=ArticleScrapeStatus.LINK_SAVED,
            tags="新聞,科技"
        )
    ]

    session.add_all(articles)
    session.commit()
    # 重新查詢以獲取分配的 ID
    articles = session.query(Articles).order_by(Articles.published_at).all()
    return articles

class TestArticleService:
    """測試文章服務的核心功能"""

    def test_create_article(self, article_service):
        """測試新增單一文章 (或更新若連結已存在)"""
        article_data = {
            "title": "測試文章",
            "link": "https://test.com/article1",
            "summary": "測試摘要",
            "content": "測試內容",
            "source": "測試來源",
            "source_url": "https://test.com/source",
            "category": "測試",
            "published_at": datetime.now(timezone.utc),
            "is_ai_related": True,
            "is_scraped": True,
            "tags": "測試,文章",
            "scrape_status": ArticleScrapeStatus.CONTENT_SCRAPED
        }

        result = article_service.create_article(article_data)
        assert result["success"] is True
        assert result["message"] == "文章創建成功"
        assert "article" in result
        assert isinstance(result["article"], ArticleReadSchema)
        assert result["article"].title == article_data["title"]
        assert result["article"].link == article_data["link"]
        assert result["article"].id is not None
        assert result["article"].created_at is not None
        assert result["article"].updated_at is not None

        # 測試更新現有文章
        update_data = {
            "title": "更新標題",
            "link": "https://test.com/article1", # 使用相同連結
            "summary": "更新摘要"
        }
        result_update = article_service.create_article(update_data)
        assert result_update["success"] is True
        assert "article" in result_update
        assert isinstance(result_update["article"], ArticleReadSchema)
        assert result_update["article"].title == update_data["title"]
        assert result_update["article"].summary == update_data["summary"]
        assert result_update["article"].link == article_data["link"] # 連結應保持不變

    def test_batch_create_articles(self, article_service):
        """測試批量新增文章"""
        articles_data = [
            {
                "title": f"batch_測試文章{i}",
                "link": f"https://test.com/batch_article{i}",
                "summary": f"batch_測試摘要{i}",
                "content": f"batch_測試內容{i}",
                "source": "測試來源",
                "source_url": f"https://test.com/batch_source{i}",
                "category": "測試",
                "published_at": datetime.now(timezone.utc),
                "is_ai_related": True,
                "is_scraped": True,
                "tags": "測試,文章",
                "scrape_status": ArticleScrapeStatus.CONTENT_SCRAPED
            }
            for i in range(3)
        ]

        result = article_service.batch_create_articles(articles_data)
        assert result["success"] is True
        assert "resultMsg" in result
        assert result["resultMsg"]["success_count"] == 3
        assert result["resultMsg"]["update_count"] == 0
        assert result["resultMsg"]["fail_count"] == 0
        assert "inserted_articles" in result["resultMsg"]
        assert len(result["resultMsg"]["inserted_articles"]) == 3
        assert all(isinstance(a, ArticleReadSchema) for a in result["resultMsg"]["inserted_articles"])
        assert "updated_articles" in result["resultMsg"]
        assert len(result["resultMsg"]["updated_articles"]) == 0

    def test_get_article_by_id(self, article_service, sample_articles):
        """測試根據ID獲取文章"""
        article_to_get = sample_articles[0]
        article_id = article_to_get.id
        result = article_service.get_article_by_id(article_id)

        assert result["success"] is True
        assert "article" in result
        assert isinstance(result["article"], ArticleReadSchema)
        assert result["article"].id == article_id
        assert result["article"].title == article_to_get.title

        # 測試獲取不存在的文章
        result_not_found = article_service.get_article_by_id(99999)
        assert result_not_found["success"] is False
        assert result_not_found["article"] is None

    def test_get_article_by_link(self, article_service, sample_articles):
        """測試根據連結獲取文章"""
        article_to_get = sample_articles[0]
        link = article_to_get.link
        result = article_service.get_article_by_link(link)

        assert result["success"] is True
        assert "article" in result
        assert isinstance(result["article"], ArticleReadSchema)
        assert result["article"].link == link
        assert result["article"].title == article_to_get.title

        # 測試獲取不存在的連結
        result_not_found = article_service.get_article_by_link("https://nonexistent.com")
        assert result_not_found["success"] is False
        assert result_not_found["article"] is None

    def test_get_articles_paginated(self, article_service, sample_articles):
        """測試分頁獲取文章"""
        result = article_service.get_articles_paginated(page=1, per_page=2)

        assert result["success"] is True
        assert "resultMsg" in result
        assert isinstance(result["resultMsg"], PaginatedArticleResponse)
        
        paginated_response = result["resultMsg"]
        assert len(paginated_response.items) == 2
        assert all(isinstance(item, ArticleReadSchema) for item in paginated_response.items)
        assert paginated_response.total == 4
        assert paginated_response.page == 1
        assert paginated_response.per_page == 2
        assert paginated_response.total_pages == 2
        assert paginated_response.has_next is True
        assert paginated_response.has_prev is False

        # 測試獲取第二頁
        result_page2 = article_service.get_articles_paginated(page=2, per_page=2)
        assert result_page2["success"] is True
        assert isinstance(result_page2["resultMsg"], PaginatedArticleResponse)
        paginated_response2 = result_page2["resultMsg"]
        assert len(paginated_response2.items) == 2
        assert all(isinstance(item, ArticleReadSchema) for item in paginated_response2.items)
        assert paginated_response2.page == 2
        assert paginated_response2.has_next is False
        assert paginated_response2.has_prev is True

    def test_get_ai_related_articles(self, article_service, sample_articles):
        """測試獲取AI相關文章"""
        result = article_service.get_ai_related_articles()
        assert result["success"] is True
        assert "articles" in result
        assert len(result["articles"]) == 2
        assert all(isinstance(article, ArticleReadSchema) for article in result["articles"])
        assert all(article.is_ai_related for article in result["articles"])

    def test_get_articles_by_category(self, article_service, sample_articles):
        """測試根據分類獲取文章"""
        result = article_service.get_articles_by_category("AI研究")
        assert result["success"] is True
        assert "articles" in result
        assert len(result["articles"]) == 2
        assert all(isinstance(article, ArticleReadSchema) for article in result["articles"])
        assert all(article.category == "AI研究" for article in result["articles"])

        # 測試無結果的分類
        result_no_match = article_service.get_articles_by_category("不存在的分類")
        assert result_no_match["success"] is True
        assert len(result_no_match["articles"]) == 0

    def test_update_article(self, article_service, sample_articles):
        """測試更新文章"""
        article_to_update = sample_articles[0]
        article_id = article_to_update.id
        original_title = article_to_update.title
        update_data = {
            "title": "更新後的標題",
            "content": "更新後的內容"
        }

        result = article_service.update_article(article_id, update_data)
        assert result["success"] is True
        assert "article" in result
        assert isinstance(result["article"], ArticleReadSchema)
        assert result["article"].title == "更新後的標題"
        assert result["article"].content == "更新後的內容"
        assert result["article"].id == article_id

        # 測試更新無變更 (傳遞相同數據)
        result_no_change = article_service.update_article(article_id, update_data)
        assert result_no_change["success"] is True
        assert isinstance(result_no_change["article"], ArticleReadSchema)
        assert result_no_change["article"].title == "更新後的標題" # 驗證資料未變

        # 測試更新不存在的文章
        result_not_exist = article_service.update_article(999999, {"title": "新標題"})
        assert result_not_exist["success"] is False
        assert result_not_exist["message"] == "文章不存在，無法更新"
        assert result_not_exist["article"] is None

    def test_batch_update_articles_by_ids(self, article_service, sample_articles):
        """測試批量更新文章"""
        article_ids = [article.id for article in sample_articles[:2]]
        update_data = {
            "category": "更新分類",
            "summary": "更新的摘要"
        }

        result = article_service.batch_update_articles_by_ids(article_ids, update_data)
        assert result["success"] is True
        assert "resultMsg" in result
        assert result["resultMsg"]["success_count"] == 2
        assert result["resultMsg"]["fail_count"] == 0
        assert "updated_articles" in result["resultMsg"]
        assert len(result["resultMsg"]["updated_articles"]) == 2
        assert all(isinstance(a, ArticleReadSchema) for a in result["resultMsg"]["updated_articles"])
        assert all(a.category == "更新分類" for a in result["resultMsg"]["updated_articles"])
        assert all(a.summary == "更新的摘要" for a in result["resultMsg"]["updated_articles"])
        
        # 測試包含不存在的 ID
        result_with_invalid = article_service.batch_update_articles_by_ids(article_ids + [99999], {"is_scraped": False})
        assert result_with_invalid["success"] is True # 即使有失敗，API 本身可能回報 True
        assert result_with_invalid["resultMsg"]["success_count"] == 2 # 只有兩個成功
        assert result_with_invalid["resultMsg"]["fail_count"] == 1 # 一個失敗
        assert len(result_with_invalid["resultMsg"]["updated_articles"]) == 2
        assert all(isinstance(a, ArticleReadSchema) for a in result_with_invalid["resultMsg"]["updated_articles"])
        assert all(a.is_scraped is False for a in result_with_invalid["resultMsg"]["updated_articles"]) # 驗證成功更新的部分

    def test_batch_update_articles_by_link(self, article_service, sample_articles):
        """測試根據連結批量更新文章"""
        article_data = [
            {
                "link": sample_articles[0].link,
                "category": "更新分類1",
                "summary": "更新的摘要1"
            },
            {
                "link": sample_articles[1].link,
                "category": "更新分類2",
                "summary": "更新的摘要2"
            },
             {
                "link": "https://nonexistent.com/update", # 不存在的連結
                "category": "更新分類3",
                "summary": "更新的摘要3"
            }
        ]
    
        result = article_service.batch_update_articles_by_link(article_data)
    
        assert result["success"] is True # API 本身成功
        assert "resultMsg" in result
        result_msg = result["resultMsg"] # 方便後續使用
        assert result_msg["success_count"] == 2 # 只有兩個成功
        assert result_msg["fail_count"] == 1 # 一個失敗
        assert "updated_articles" in result_msg
        assert len(result_msg["updated_articles"]) == 2
        assert all(isinstance(a, ArticleReadSchema) for a in result_msg["updated_articles"])
        assert result_msg["updated_articles"][0].category == "更新分類1"
        assert result_msg["updated_articles"][1].category == "更新分類2"
        
        # --- 修改斷言以匹配實際返回的鍵 ---
        # 驗證失敗的連結被記錄在 missing_links 中
        assert "missing_links" in result_msg 
        assert len(result_msg["missing_links"]) == 1
        assert result_msg["missing_links"][0] == "https://nonexistent.com/update"
        
        # 驗證 error_details (在此例中應為空)
        assert "error_details" in result_msg
        assert len(result_msg["error_details"]) == 0
        # --- 結束修改 ---

    def test_delete_article(self, article_service, sample_articles):
        """測試刪除文章"""
        article_id_to_delete = sample_articles[0].id
        result = article_service.delete_article(article_id_to_delete)
        assert result["success"] is True
        assert result["message"] == "文章刪除成功"

        # 確認文章已被刪除
        result_check = article_service.get_article_by_id(article_id_to_delete)
        assert result_check["success"] is False
        assert result_check["message"] == "文章不存在"

        # 測試刪除不存在的文章
        result_not_exist = article_service.delete_article(99999)
        assert result_not_exist["success"] is False
        assert result_not_exist["message"] == "文章不存在或刪除失敗"

    def test_batch_delete_articles(self, article_service, sample_articles):
        """測試批量刪除文章"""
        article_ids_to_delete = [article.id for article in sample_articles[:2]]
        non_existent_id = 99999
        all_ids = article_ids_to_delete + [non_existent_id]

        result = article_service.batch_delete_articles(all_ids)
        assert result["success"] is False # 因為有一個失敗了
        assert "resultMsg" in result
        assert result["resultMsg"]["success_count"] == 2
        assert result["resultMsg"]["fail_count"] == 1
        assert non_existent_id in result["resultMsg"]["missing_ids"] # 檢查失敗的ID

        # 確認文章已被刪除
        for article_id in article_ids_to_delete:
            get_result = article_service.get_article_by_id(article_id)
            assert get_result["success"] is False

        # 測試空列表
        result_empty = article_service.batch_delete_articles([])
        assert result_empty["success"] is True
        assert result_empty["resultMsg"]["success_count"] == 0

    def test_get_articles_statistics(self, article_service, sample_articles):
        """測試獲取文章統計資訊"""
        result = article_service.get_articles_statistics()

        assert result["success"] is True
        assert "statistics" in result
        stats = result["statistics"]

        assert "total_count" in stats
        assert "ai_related_count" in stats
        assert "category_distribution" in stats
        assert "source_distribution" in stats
        assert "scrape_status_distribution" in stats

        assert stats["total_count"] == 4
        assert stats["ai_related_count"] == 2
        assert stats["category_distribution"].get("AI研究", 0) == 2
        assert stats["category_distribution"].get("財經", 0) == 1
        assert stats["source_distribution"].get("科技日報", 0) == 2
        assert stats["source_distribution"].get("新聞網", 0) == 1
        assert stats["scrape_status_distribution"].get(ArticleScrapeStatus.CONTENT_SCRAPED.value, 0) == 3
        assert stats["scrape_status_distribution"].get(ArticleScrapeStatus.LINK_SAVED.value, 0) == 1

    def test_error_handling(self, article_service, sample_articles):
        """測試錯誤處理"""
        # 測試創建重複連結的文章 (現在應執行更新)
        existing_link = sample_articles[0].link
        article_data = {
            "title": "重複連結更新測試",
            "link": existing_link, 
            "summary": "新的摘要", 
            "content": "測試內容",
            "source": "測試來源",
            "source_url": "https://test.com/source",
            "category": "測試",
            "published_at": datetime.now(timezone.utc),
            "is_ai_related": True,
            "is_scraped": True,
            "scrape_status": ArticleScrapeStatus.CONTENT_SCRAPED
        }

        result = article_service.create_article(article_data)
        assert result["success"] is True
        assert result["message"] == "文章已存在，更新成功" 
        assert isinstance(result["article"], ArticleReadSchema)
        assert result["article"].summary == "新的摘要" 

        # 測試更新不存在的文章
        result_update_fail = article_service.update_article(999999, {"title": "新標題"})
        assert result_update_fail["success"] is False
        assert result_update_fail["message"] == "文章不存在，無法更新" 
        assert result_update_fail["article"] is None

class TestArticleServiceAdvancedFeatures:
    """測試文章服務的進階功能"""

    def test_advanced_search_articles(self, article_service, sample_articles):
        """測試進階搜尋文章"""
        # 測試多條件組合搜尋 (AI研究, is_ai_related=True)
        result_combined = article_service.advanced_search_articles(
            category="AI研究",
            is_ai_related=True
        )
        assert result_combined["success"] is True
        assert "articles" in result_combined
        assert "total_count" in result_combined
        assert result_combined["total_count"] == 2 # 應找到 AI發展新突破 和 機器學習應用
        assert len(result_combined["articles"]) == 2
        assert all(isinstance(a, ArticleReadSchema) for a in result_combined["articles"])
        assert all(article.category == "AI研究" for article in result_combined["articles"])
        assert all(article.is_ai_related for article in result_combined["articles"])

        # 測試 is_scraped 條件
        result_unscraped = article_service.advanced_search_articles(is_scraped=False)
        assert result_unscraped["success"] is True
        assert result_unscraped["total_count"] == 1
        assert len(result_unscraped["articles"]) == 1
        assert isinstance(result_unscraped["articles"][0], ArticleReadSchema)
        assert result_unscraped["articles"][0].is_scraped is False

        # 測試 source 條件 + 分頁
        result_source_page = article_service.advanced_search_articles(source="科技日報", limit=1, offset=0)
        assert result_source_page["success"] is True
        assert result_source_page["total_count"] == 2 # 總數應為 2
        assert len(result_source_page["articles"]) == 1 # 但只返回 1 篇
        assert isinstance(result_source_page["articles"][0], ArticleReadSchema)
        assert result_source_page["articles"][0].source == "科技日報"

    def test_update_article_tags(self, article_service, sample_articles):
        """測試更新文章標籤"""
        article_to_update = sample_articles[0]
        article_id = article_to_update.id
        new_tags = ["新標籤1", "新標籤2"]

        result = article_service.update_article_tags(article_id, new_tags)
        assert result["success"] is True
        assert "article" in result
        assert isinstance(result["article"], ArticleReadSchema)
        assert result["article"].tags == ",".join(new_tags)
        assert result["article"].id == article_id

    def test_search_by_title(self, article_service, sample_articles):
        """測試根據標題搜索文章"""
        result_fuzzy = article_service.search_articles_by_title("AI")
        assert result_fuzzy["success"] is True
        assert "articles" in result_fuzzy
        assert len(result_fuzzy["articles"]) == 1
        assert isinstance(result_fuzzy["articles"][0], ArticleReadSchema)
        assert "AI" in result_fuzzy["articles"][0].title

        result_exact = article_service.search_articles_by_title("機器學習應用", exact_match=True)
        assert result_exact["success"] is True
        assert len(result_exact["articles"]) == 1
        assert isinstance(result_exact["articles"][0], ArticleReadSchema)
        assert result_exact["articles"][0].title == "機器學習應用"

    def test_search_by_keywords(self, article_service, sample_articles):
        """測試根據關鍵字搜索文章 (標題或內容)"""
        result = article_service.search_articles_by_keywords("應用") # 應匹配 "機器學習應用"
        assert result["success"] is True
        assert "articles" in result
        assert len(result["articles"]) >= 1 # 至少應找到一篇
        assert all(isinstance(a, ArticleReadSchema) for a in result["articles"])
        assert any("機器學習應用" in a.title for a in result["articles"]) 

    def test_get_source_statistics(self, article_service, sample_articles):
        """測試獲取各來源的爬取統計"""
        result = article_service.get_source_statistics()
        assert result["success"] is True
        assert "statistics" in result 
        stats = result["statistics"]
        assert "科技日報" in stats
        assert "新聞網" in stats
        assert stats["科技日報"]["total"] == 2
        assert stats["新聞網"]["total"] == 1
        assert stats["新聞網"]["unscraped"] == 1 # 確保包含未爬取統計

    def test_update_article_scrape_status(self, article_service, sample_articles):
        """測試更新文章爬取狀態"""
        unscraped_article = sample_articles[3]
        link = unscraped_article.link
        assert unscraped_article.is_scraped is False

        # 標記為已爬取 (這裡只測試 service 方法，不檢查返回內容)
        result = article_service.update_article_scrape_status(
            link, 
            True, 
            ArticleScrapeStatus.CONTENT_SCRAPED # 明確指定狀態
        )
        assert result["success"] is True

        # 確認狀態已更新 (使用 get_article_by_link)
        article_result = article_service.get_article_by_link(link)
        assert article_result["success"] is True
        assert isinstance(article_result["article"], ArticleReadSchema)
        assert article_result["article"].is_scraped is True
        assert article_result["article"].scrape_status == ArticleScrapeStatus.CONTENT_SCRAPED

        # 標記回未爬取
        result_false = article_service.update_article_scrape_status(
            link, 
            False, 
            ArticleScrapeStatus.FAILED # 模擬一個失敗狀態
        )
        assert result_false["success"] is True
        article_result_false = article_service.get_article_by_link(link)
        assert article_result_false["success"] is True
        assert isinstance(article_result_false["article"], ArticleReadSchema)
        assert article_result_false["article"].is_scraped is False
        assert article_result_false["article"].scrape_status == ArticleScrapeStatus.FAILED

    def test_get_unscraped_articles(self, article_service, sample_articles):
        """測試獲取未爬取的文章"""
        result = article_service.get_unscraped_articles()
        assert result["success"] is True
        assert "articles" in result
        assert len(result["articles"]) == 1
        assert all(isinstance(a, ArticleReadSchema) for a in result["articles"])
        assert all(not article.is_scraped for article in result["articles"])

    def test_get_scraped_articles(self, article_service, sample_articles):
        """測試獲取已爬取的文章"""
        result = article_service.get_scraped_articles()
        assert result["success"] is True
        assert "articles" in result
        assert len(result["articles"]) == 3
        assert all(isinstance(a, ArticleReadSchema) for a in result["articles"])
        assert all(article.is_scraped for article in result["articles"])

    def test_count_unscraped_articles(self, article_service, sample_articles):
        """測試計算未爬取的文章數量"""
        result = article_service.count_unscraped_articles()
        assert result["success"] is True
        assert "count" in result
        assert result["count"] == 1

    def test_count_scraped_articles(self, article_service, sample_articles):
        """測試計算已爬取的文章數量"""
        result = article_service.count_scraped_articles()
        assert result["success"] is True
        assert "count" in result
        assert result["count"] == 3
