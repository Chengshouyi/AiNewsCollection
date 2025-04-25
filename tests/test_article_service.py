import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.articles_model import Articles, Base, ArticleScrapeStatus
from src.services.article_service import ArticleService
from src.models.articles_schema import ArticleReadSchema, PaginatedArticleResponse
from src.database.database_manager import DatabaseManager
from src.models.crawler_tasks_model import CrawlerTasks, ScrapeMode
from typing import List, Dict, Any, Optional

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
        # 清理測試任務和文章數據，避免測試間互相影響
        session.query(Articles).delete()
        session.query(CrawlerTasks).delete() # 如果測試中有創建任務
        session.commit()
    finally:
        session.close()

@pytest.fixture(scope="function")
def article_service(session):
    """創建文章服務實例"""
    db_manager = DatabaseManager('sqlite:///:memory:')
    db_manager.Session = sessionmaker(bind=session.get_bind())
    # 直接將 session 傳遞給 ArticleService 的 db_manager
    service = ArticleService(db_manager)
    # 確保 service 使用的是當前測試的 session
    service.db_manager.Session = sessionmaker(bind=session.get_bind())
    return service

@pytest.fixture(scope="function")
def sample_task(session) -> CrawlerTasks:
    """創建測試用的爬蟲任務"""
    task = CrawlerTasks(
        task_name="Test Task",
        crawler_id=1,
        source_name="Test Source",
        scrape_mode=ScrapeMode.FULL_SCRAPE,
        target_url="https://example.com/task",
        is_active=True,
        last_run_time=datetime.now(timezone.utc) - timedelta(days=1)
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task

@pytest.fixture(scope="function")
def sample_articles(session, sample_task) -> List[Articles]:
    """創建測試用的文章資料"""
    # 清除現有資料 (雖然 session fixture 會做，這裡再做一次確保)
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
            tags="AI,研究",
            task_id=sample_task.id # 關聯任務
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
            tags="財經,市場",
            task_id=None # 不關聯任務
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
            tags="AI,機器學習",
            task_id=sample_task.id # 關聯任務
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
            tags="新聞,科技",
            task_id=sample_task.id # 關聯任務
        ),
         Articles(
            title="待抓取AI新聞",
            link="https://example.com/news_ai",
            summary="等待抓取的AI相關新聞",
            content=None,
            source="科技前線",
            source_url="https://example.com/source5",
            category="新聞",
            published_at=datetime(2023, 1, 5, 12, 0, 0, tzinfo=timezone.utc),
            is_ai_related=True, # AI相關
            is_scraped=False, # 未抓取
            scrape_status=ArticleScrapeStatus.PENDING,
            tags="新聞,AI",
            task_id=sample_task.id # 關聯任務
        )
    ]

    session.add_all(articles)
    session.commit()
    # 重新查詢以獲取分配的 ID 和關係
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

    def test_batch_create_articles(self, article_service, sample_articles):
        """測試批量新增文章，包含新增、更新（重複連結）和失敗情況"""
        # 準備測試數據
        existing_article_link_1 = sample_articles[0].link
        existing_article_link_2 = sample_articles[1].link
        original_title_1 = sample_articles[0].title
        original_category_2 = sample_articles[1].category

        articles_data = [
            {
                # 情況 1: 全新文章，應創建成功
                "title": "全新批量文章",
                "link": "https://test.com/batch_new_unique",
                "summary": "新摘要",
                "content": "新內容",
                "source": "批量測試來源",
                "source_url": "https://test.com/batch_new_source",
                "category": "批量測試",
                "published_at": datetime.now(timezone.utc),
                "is_ai_related": False,
                "is_scraped": False,
                "tags": "新,批量",
                "scrape_status": ArticleScrapeStatus.LINK_SAVED
            },
            {
                # 情況 2: 連結已存在，應更新現有文章 1
                "title": "更新後的AI發展",
                "link": existing_article_link_1,
                "summary": "這是更新後的摘要",
                "is_scraped": True # 假設更新了爬取狀態
            },
            {
                # 情況 3: 連結已存在，應更新現有文章 2
                "title": "更新後的市場分析", # 假設標題也更新了
                "link": existing_article_link_2,
                "category": "更新後的財經分類", # 更新分類
                "tags": "更新,財經" # 更新標籤
            },
            {
                # 情況 4: 缺少 link，應失敗
                "title": "無效文章 - 缺少連結",
                "summary": "此項應失敗",
                "source": "無效來源",
                "source_url": "https://invalid.com/source"
            }
        ]

        result = article_service.batch_create_articles(articles_data)

        # 驗證總體結果
        assert result["success"] is False # 因為有一筆失敗
        assert "resultMsg" in result
        result_msg = result["resultMsg"]

        # 驗證計數
        assert result_msg["success_count"] == 1, f"預期創建 1 筆，實際 {result_msg['success_count']}"
        assert result_msg["update_count"] == 2, f"預期更新 2 筆，實際 {result_msg['update_count']}"
        assert result_msg["fail_count"] == 1, f"預期失敗 1 筆，實際 {result_msg['fail_count']}"

        # 驗證創建的文章
        assert "inserted_articles" in result_msg
        assert len(result_msg["inserted_articles"]) == 1
        inserted_article_schema = result_msg["inserted_articles"][0]
        assert isinstance(inserted_article_schema, ArticleReadSchema)
        assert inserted_article_schema.title == "全新批量文章"
        assert inserted_article_schema.link == "https://test.com/batch_new_unique"
        assert inserted_article_schema.id is not None # 確保有 ID

        # 驗證更新的文章
        assert "updated_articles" in result_msg
        assert len(result_msg["updated_articles"]) == 2
        updated_schema_1 = next((a for a in result_msg["updated_articles"] if a.link == existing_article_link_1), None)
        updated_schema_2 = next((a for a in result_msg["updated_articles"] if a.link == existing_article_link_2), None)

        assert updated_schema_1 is not None
        assert isinstance(updated_schema_1, ArticleReadSchema)
        assert updated_schema_1.title == "更新後的AI發展" # 驗證更新的標題
        assert updated_schema_1.summary == "這是更新後的摘要" # 驗證更新的摘要
        assert updated_schema_1.is_scraped is True # 驗證更新的欄位
        assert updated_schema_1.id == sample_articles[0].id # ID 應保持不變

        assert updated_schema_2 is not None
        assert isinstance(updated_schema_2, ArticleReadSchema)
        assert updated_schema_2.title == "更新後的市場分析" # 驗證更新的標題
        assert updated_schema_2.category == "更新後的財經分類" # 驗證更新的分類
        assert updated_schema_2.tags == "更新,財經" # 驗證更新的標籤
        assert updated_schema_2.id == sample_articles[1].id # ID 應保持不變

        # 驗證失敗的項目
        assert "failed_details" in result_msg
        assert len(result_msg["failed_details"]) == 1
        failed_detail = result_msg["failed_details"][0]
        assert failed_detail["data"]["title"] == "無效文章 - 缺少連結"
        assert "缺少 'link' 欄位" in failed_detail["error"]

        # (可選) 直接檢查資料庫確認更新已生效
        with article_service._transaction() as session:
            db_article_1 = session.get(Articles, sample_articles[0].id)
            db_article_2 = session.get(Articles, sample_articles[1].id)
            assert db_article_1.title == "更新後的AI發展"
            assert db_article_1.is_scraped is True
            assert db_article_2.category == "更新後的財經分類"
            assert db_article_2.tags == "更新,財經"

            # 確認新文章已存在
            new_db_article = session.query(Articles).filter_by(link="https://test.com/batch_new_unique").first()
            assert new_db_article is not None
            assert new_db_article.title == "全新批量文章"

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

    def test_find_articles_paginated(self, article_service, sample_articles):
        """測試分頁獲取文章"""
        # 測試第一頁，完整 Schema
        result = article_service.find_articles_paginated(page=1, per_page=2, is_preview=False)

        assert result["success"] is True
        assert "resultMsg" in result
        assert isinstance(result["resultMsg"], PaginatedArticleResponse)

        paginated_response = result["resultMsg"]
        assert len(paginated_response.items) == 2
        assert all(isinstance(item, ArticleReadSchema) for item in paginated_response.items)
        assert paginated_response.total == 5 # 現在有 5 筆測試資料
        assert paginated_response.page == 1
        assert paginated_response.per_page == 2
        assert paginated_response.total_pages == 3 # 總頁數變為 3
        assert paginated_response.has_next is True
        assert paginated_response.has_prev is False

        # 測試第二頁，完整 Schema
        result_page2 = article_service.find_articles_paginated(page=2, per_page=2, is_preview=False)
        assert result_page2["success"] is True
        assert isinstance(result_page2["resultMsg"], PaginatedArticleResponse)
        paginated_response2 = result_page2["resultMsg"]
        assert len(paginated_response2.items) == 2
        assert all(isinstance(item, ArticleReadSchema) for item in paginated_response2.items)
        assert paginated_response2.page == 2
        assert paginated_response2.has_next is True # 因為還有第三頁
        assert paginated_response2.has_prev is True

        # 測試預覽模式
        preview_fields = ["title", "link", "source"]
        result_preview = article_service.find_articles_paginated(
            page=1,
            per_page=3,
            is_preview=True,
            preview_fields=preview_fields
        )
        assert result_preview["success"] is True
        assert isinstance(result_preview["resultMsg"], PaginatedArticleResponse)
        paginated_preview_response = result_preview["resultMsg"]
        assert len(paginated_preview_response.items) == 3
        assert all(isinstance(item, dict) for item in paginated_preview_response.items)
        assert all(set(item.keys()) == set(preview_fields) for item in paginated_preview_response.items)
        assert paginated_preview_response.total == 5

    def test_find_ai_related_articles(self, article_service, sample_articles):
        """測試獲取AI相關文章，支援預覽"""
        # 測試完整 Schema
        result = article_service.find_ai_related_articles(is_preview=False)
        assert result["success"] is True
        assert "articles" in result
        assert len(result["articles"]) == 3 # 現在有 3 篇 AI 相關
        assert all(isinstance(article, ArticleReadSchema) for article in result["articles"])
        assert all(article.is_ai_related for article in result["articles"])

        # 測試預覽模式
        preview_fields = ["title", "is_ai_related"]
        result_preview = article_service.find_ai_related_articles(
            is_preview=True,
            preview_fields=preview_fields,
            limit=2 # 測試限制數量
        )
        assert result_preview["success"] is True
        assert "articles" in result_preview
        assert len(result_preview["articles"]) == 2 # 限制為 2
        assert all(isinstance(article, dict) for article in result_preview["articles"])
        assert all(set(article.keys()) == set(preview_fields) for article in result_preview["articles"])
        assert all(article["is_ai_related"] is True for article in result_preview["articles"])


    def test_find_articles_by_category(self, article_service, sample_articles):
        """測試根據分類獲取文章，支援預覽"""
        # 測試完整 Schema
        result = article_service.find_articles_by_category("AI研究", is_preview=False)
        assert result["success"] is True
        assert "articles" in result
        assert len(result["articles"]) == 2
        assert all(isinstance(article, ArticleReadSchema) for article in result["articles"])
        assert all(article.category == "AI研究" for article in result["articles"])

        # 測試預覽模式
        preview_fields = ["link", "category"]
        result_preview = article_service.find_articles_by_category(
            "AI研究",
            is_preview=True,
            preview_fields=preview_fields,
            limit=1
        )
        assert result_preview["success"] is True
        assert "articles" in result_preview
        assert len(result_preview["articles"]) == 1
        assert all(isinstance(article, dict) for article in result_preview["articles"])
        assert all(set(article.keys()) == set(preview_fields) for article in result_preview["articles"])
        assert all(article["category"] == "AI研究" for article in result_preview["articles"])

        # 測試無結果的分類
        result_no_match = article_service.find_articles_by_category("不存在的分類")
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
        assert result_no_change["success"] is True # Service 層認為操作成功
        assert isinstance(result_no_change["article"], ArticleReadSchema)
        assert result_no_change["article"].title == "更新後的標題" # 驗證資料未變
        assert result_no_change["message"] == '文章更新操作完成 (可能無實際變更)'

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
        assert 99999 in result_with_invalid["resultMsg"]["missing_ids"] # 檢查 missing_ids

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

        # 驗證失敗的連結被記錄在 missing_links 中
        assert "missing_links" in result_msg
        assert len(result_msg["missing_links"]) == 1
        assert result_msg["missing_links"][0] == "https://nonexistent.com/update"

        # 驗證 error_details (在此例中應為空)
        assert "error_details" in result_msg
        assert len(result_msg["error_details"]) == 0


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

        assert stats["total_count"] == 5 # 現在有 5 筆
        assert stats["ai_related_count"] == 3 # 現在有 3 筆 AI 相關
        assert stats["category_distribution"].get("AI研究", 0) == 2
        assert stats["category_distribution"].get("財經", 0) == 1
        assert stats["category_distribution"].get("新聞", 0) == 2 # 新增的新聞分類
        assert stats["source_distribution"].get("科技日報", 0) == 2
        assert stats["source_distribution"].get("新聞網", 0) == 1
        assert stats["source_distribution"].get("科技前線", 0) == 1 # 新增的來源
        assert stats["scrape_status_distribution"].get(ArticleScrapeStatus.CONTENT_SCRAPED.value, 0) == 3
        assert stats["scrape_status_distribution"].get(ArticleScrapeStatus.LINK_SAVED.value, 0) == 1
        assert stats["scrape_status_distribution"].get(ArticleScrapeStatus.PENDING.value, 0) == 1 # 新增的 PENDING 狀態


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

    def test_find_articles_advanced(self, article_service, sample_articles):
        """測試進階搜尋文章 (分頁, 支援預覽)"""
        # 測試多條件組合搜尋 (AI研究, is_ai_related=True) - 完整 Schema
        result_combined = article_service.find_articles_advanced(
            category="AI研究",
            is_ai_related=True,
            is_preview=False
        )
        assert result_combined["success"] is True
        assert "resultMsg" in result_combined # 結果現在是 resultMsg
        assert isinstance(result_combined["resultMsg"], PaginatedArticleResponse)
        paginated_response = result_combined["resultMsg"]

        assert paginated_response.total == 2 # 應找到 AI發展新突破 和 機器學習應用
        assert len(paginated_response.items) == 2
        assert all(isinstance(a, ArticleReadSchema) for a in paginated_response.items)
        assert all(article.category == "AI研究" for article in paginated_response.items)
        assert all(article.is_ai_related for article in paginated_response.items)

        # 測試 is_scraped 條件 - 預覽模式
        preview_fields = ["link", "is_scraped"]
        result_unscraped_preview = article_service.find_articles_advanced(
            is_scraped=False,
            is_preview=True,
            preview_fields=preview_fields
        )
        assert result_unscraped_preview["success"] is True
        assert isinstance(result_unscraped_preview["resultMsg"], PaginatedArticleResponse)
        paginated_preview = result_unscraped_preview["resultMsg"]
        assert paginated_preview.total == 2 # 現在有 2 筆未抓取
        assert len(paginated_preview.items) == 2
        assert all(isinstance(item, dict) for item in paginated_preview.items)
        assert all(set(item.keys()) == set(preview_fields) for item in paginated_preview.items)
        assert all(item["is_scraped"] is False for item in paginated_preview.items)

        # 測試 source 條件 + 分頁
        result_source_page = article_service.find_articles_advanced(
            source="科技日報",
            page=1,
            per_page=1,
            is_preview=False
        )
        assert result_source_page["success"] is True
        assert isinstance(result_source_page["resultMsg"], PaginatedArticleResponse)
        paginated_source = result_source_page["resultMsg"]
        assert paginated_source.total == 2 # 總數應為 2
        assert len(paginated_source.items) == 1 # 但只返回 1 篇
        assert isinstance(paginated_source.items[0], ArticleReadSchema)
        assert paginated_source.items[0].source == "科技日報"

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

    def test_find_articles_by_title(self, article_service, sample_articles):
        """測試根據標題搜索文章，支援預覽"""
        # 模糊搜索 - 完整 Schema
        result_fuzzy = article_service.find_articles_by_title(
            keyword="AI",
            is_preview=False
        )
        assert result_fuzzy["success"] is True
        assert "articles" in result_fuzzy
        assert len(result_fuzzy["articles"]) == 2 # 匹配 "AI發展新突破" 和 "待抓取AI新聞"
        assert all(isinstance(a, ArticleReadSchema) for a in result_fuzzy["articles"])
        assert all("AI" in article.title for article in result_fuzzy["articles"])

        # 精確搜索 - 預覽模式
        preview_fields = ["title"]
        result_exact_preview = article_service.find_articles_by_title(
            keyword="機器學習應用",
            exact_match=True,
            is_preview=True,
            preview_fields=preview_fields
        )
        assert result_exact_preview["success"] is True
        assert "articles" in result_exact_preview
        assert len(result_exact_preview["articles"]) == 1
        assert isinstance(result_exact_preview["articles"][0], dict)
        assert set(result_exact_preview["articles"][0].keys()) == set(preview_fields)
        assert result_exact_preview["articles"][0]["title"] == "機器學習應用"

    def test_find_articles_by_keywords(self, article_service, sample_articles):
        """測試根據關鍵字搜索文章 (標題/內容/摘要)，支援預覽"""
        # 關鍵字搜索 - 完整 Schema
        result = article_service.find_articles_by_keywords(
            keywords="應用",
            is_preview=False
        )
        assert result["success"] is True
        assert "articles" in result
        assert len(result["articles"]) == 1 # 只匹配 "機器學習應用"
        assert all(isinstance(a, ArticleReadSchema) for a in result["articles"])
        assert any("機器學習應用" in a.title for a in result["articles"])

        # 關鍵字搜索 - 預覽模式
        preview_fields = ["summary", "link"]
        result_preview = article_service.find_articles_by_keywords(
            keywords="突破", # 匹配 "AI發展新突破" 的摘要
            is_preview=True,
            preview_fields=preview_fields,
            limit=1
        )
        assert result_preview["success"] is True
        assert "articles" in result_preview
        assert len(result_preview["articles"]) == 1
        assert isinstance(result_preview["articles"][0], dict)
        assert set(result_preview["articles"][0].keys()) == set(preview_fields)
        assert "突破" in result_preview["articles"][0]["summary"]

    def test_get_source_statistics(self, article_service, sample_articles):
        """測試獲取各來源的爬取統計"""
        result = article_service.get_source_statistics()
        assert result["success"] is True
        assert "statistics" in result
        stats = result["statistics"]
        assert "科技日報" in stats
        assert "新聞網" in stats
        assert "科技前線" in stats # 新增來源
        assert stats["科技日報"]["total"] == 2
        assert stats["科技日報"]["scraped"] == 2
        assert stats["科技日報"]["unscraped"] == 0
        assert stats["新聞網"]["total"] == 1
        assert stats["新聞網"]["unscraped"] == 1
        assert stats["科技前線"]["total"] == 1
        assert stats["科技前線"]["unscraped"] == 1

    def test_update_article_scrape_status(self, article_service, sample_articles):
        """測試更新文章爬取狀態"""
        unscraped_article = next(a for a in sample_articles if not a.is_scraped and a.link == "https://example.com/news1")
        link = unscraped_article.link
        assert unscraped_article.is_scraped is False

        # 標記為已爬取
        result = article_service.update_article_scrape_status(
            link,
            is_scraped=True
            # 不指定 status，repo 會根據 is_scraped 設為 CONTENT_SCRAPED
        )
        assert result["success"] is True

        # 確認狀態已更新
        article_result = article_service.get_article_by_link(link)
        assert article_result["success"] is True
        assert isinstance(article_result["article"], ArticleReadSchema)
        assert article_result["article"].is_scraped is True
        assert article_result["article"].scrape_status == ArticleScrapeStatus.CONTENT_SCRAPED

        # 標記回未爬取，並指定狀態
        result_false = article_service.update_article_scrape_status(
            link,
            is_scraped=False,
            scrape_status=ArticleScrapeStatus.FAILED # 模擬一個失敗狀態
        )
        assert result_false["success"] is True
        article_result_false = article_service.get_article_by_link(link)
        assert article_result_false["success"] is True
        assert isinstance(article_result_false["article"], ArticleReadSchema)
        assert article_result_false["article"].is_scraped is False
        assert article_result_false["article"].scrape_status == ArticleScrapeStatus.FAILED

    def test_find_unscraped_articles(self, article_service, sample_articles):
        """測試獲取未爬取的文章，支援預覽"""
        # 完整 Schema
        result = article_service.find_unscraped_articles(is_preview=False)
        assert result["success"] is True
        assert "articles" in result
        assert len(result["articles"]) == 2 # 現在有 2 篇未抓取
        assert all(isinstance(a, ArticleReadSchema) for a in result["articles"])
        assert all(not article.is_scraped for article in result["articles"])

        # 預覽模式
        preview_fields = ["link", "scrape_status"]
        result_preview = article_service.find_unscraped_articles(
            is_preview=True,
            preview_fields=preview_fields,
            limit=1 # repo 默認按狀態排序，應該先返回 PENDING
        )
        assert result_preview["success"] is True
        assert "articles" in result_preview
        assert len(result_preview["articles"]) == 1
        assert isinstance(result_preview["articles"][0], dict)
        assert set(result_preview["articles"][0].keys()) == set(preview_fields)
        # 驗證返回的是 PENDING 狀態的文章
        assert result_preview["articles"][0]["scrape_status"] == ArticleScrapeStatus.PENDING


    def test_find_scraped_articles(self, article_service, sample_articles):
        """測試獲取已爬取的文章，支援預覽"""
        # 完整 Schema
        result = article_service.find_scraped_articles(is_preview=False)
        assert result["success"] is True
        assert "articles" in result
        assert len(result["articles"]) == 3
        assert all(isinstance(a, ArticleReadSchema) for a in result["articles"])
        assert all(article.is_scraped for article in result["articles"])

        # 預覽模式
        preview_fields = ["source", "published_at"]
        result_preview = article_service.find_scraped_articles(
            is_preview=True,
            preview_fields=preview_fields,
            limit=2
        )
        assert result_preview["success"] is True
        assert "articles" in result_preview
        assert len(result_preview["articles"]) == 2
        assert all(isinstance(a, dict) for a in result_preview["articles"])
        assert all(set(a.keys()) == set(preview_fields) for a in result_preview["articles"])


    def test_count_unscraped_articles(self, article_service, sample_articles):
        """測試計算未爬取的文章數量"""
        result = article_service.count_unscraped_articles()
        assert result["success"] is True
        assert "count" in result
        assert result["count"] == 2 # 現在有 2 篇

    def test_count_scraped_articles(self, article_service, sample_articles):
        """測試計算已爬取的文章數量"""
        result = article_service.count_scraped_articles()
        assert result["success"] is True
        assert "count" in result
        assert result["count"] == 3

    def test_find_articles_by_task_id(self, article_service, sample_articles, sample_task):
        """測試根據 task_id 查詢文章，支援預覽"""
        task_id = sample_task.id

        # 獲取所有關聯此任務的文章 - 完整 Schema
        result_all = article_service.find_articles_by_task_id(task_id=task_id, is_preview=False)
        assert result_all["success"] is True
        assert "articles" in result_all
        assert len(result_all["articles"]) == 4 # 有 4 篇關聯了 task
        assert all(isinstance(a, ArticleReadSchema) for a in result_all["articles"])
        assert all(a.task_id == task_id for a in result_all["articles"])

        # 獲取此任務未爬取的文章 - 預覽模式
        preview_fields = ["link", "is_scraped"]
        result_unscraped_preview = article_service.find_articles_by_task_id(
            task_id=task_id,
            is_scraped=False,
            is_preview=True,
            preview_fields=preview_fields
        )
        assert result_unscraped_preview["success"] is True
        assert "articles" in result_unscraped_preview
        assert len(result_unscraped_preview["articles"]) == 2 # 2 篇未爬取
        assert all(isinstance(a, dict) for a in result_unscraped_preview["articles"])
        assert all(set(a.keys()) == set(preview_fields) for a in result_unscraped_preview["articles"])
        assert all(a["is_scraped"] is False for a in result_unscraped_preview["articles"])

        # 獲取此任務已爬取的文章 - 完整 Schema + limit
        result_scraped_limit = article_service.find_articles_by_task_id(
            task_id=task_id,
            is_scraped=True,
            limit=1,
            is_preview=False
        )
        assert result_scraped_limit["success"] is True
        assert "articles" in result_scraped_limit
        assert len(result_scraped_limit["articles"]) == 1 # 限制為 1
        assert isinstance(result_scraped_limit["articles"][0], ArticleReadSchema)
        assert result_scraped_limit["articles"][0].is_scraped is True
        assert result_scraped_limit["articles"][0].task_id == task_id

    def test_count_articles_by_task_id(self, article_service, sample_articles, sample_task):
        """測試計算特定 task_id 的文章數量"""
        task_id = sample_task.id

        # 計算總數
        result_total = article_service.count_articles_by_task_id(task_id=task_id)
        assert result_total["success"] is True
        assert result_total["count"] == 4

        # 計算未爬取數量
        result_unscraped = article_service.count_articles_by_task_id(task_id=task_id, is_scraped=False)
        assert result_unscraped["success"] is True
        assert result_unscraped["count"] == 2

        # 計算已爬取數量
        result_scraped = article_service.count_articles_by_task_id(task_id=task_id, is_scraped=True)
        assert result_scraped["success"] is True
        assert result_scraped["count"] == 2

        # 測試無效 task_id (假設服務層會處理或 repo 層拋錯)
        result_invalid = article_service.count_articles_by_task_id(task_id=99999)
        # 預期 count 為 0，success 仍為 True，因為查詢本身成功執行了
        assert result_invalid["success"] is True
        assert result_invalid["count"] == 0
