"""測試 ArticleService 的功能。

此模組包含對 ArticleService 類的所有測試案例，包括：
- CRUD 操作 (建立、讀取、更新、刪除)
- 批量操作
- 搜尋和過濾功能
- 統計功能
- 狀態更新
- 進階搜尋功能
- 錯誤處理
"""

# Standard library imports
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import logging

# Third party imports
import pytest
from sqlalchemy.orm import sessionmaker  # Keep for typing if needed, check usage later

# Local application imports
from src.models.articles_model import Articles, Base, ArticleScrapeStatus
from src.services.article_service import ArticleService
from src.models.articles_schema import ArticleReadSchema, PaginatedArticleResponse
from src.database.database_manager import (
    DatabaseManager,
)  # Keep for typing if needed, check usage later
from src.models.crawler_tasks_model import CrawlerTasks, ScrapeMode


# flake8: noqa: F811
# pylint: disable=redefined-outer-name

logger = logging.getLogger(__name__)  # 使用統一的 logger


@pytest.fixture(scope="function")
def initialized_db_manager(db_manager_for_test):
    """Fixture that depends on db_manager_for_test, creates tables, and yields the manager."""
    logger.debug("Creating tables for test function...")
    try:
        db_manager_for_test.create_tables(Base)  # Use Base from articles_model
        yield db_manager_for_test
    finally:
        logger.debug(
            "Test function finished, tables might be dropped by manager cleanup or next test setup."
        )
        # Ensure cleanup happens if needed, though db_manager_for_test likely handles it
        # db_manager_for_test.drop_tables(Base) # Uncomment if explicit drop needed


@pytest.fixture(scope="function")
def article_service(initialized_db_manager):
    """創建文章服務實例，使用 initialized_db_manager"""
    # ArticleService now takes the db_manager directly
    service = ArticleService(initialized_db_manager)
    return service


@pytest.fixture(scope="function")
def sample_task_data(initialized_db_manager) -> Dict[str, Any]:
    """創建測試用的爬蟲任務資料，返回包含 ID 的字典"""
    task_id = None
    with initialized_db_manager.session_scope() as session:
        task = CrawlerTasks(
            task_name="Test Task",
            crawler_id=1,  # Assuming a crawler with ID 1 exists or is not strictly checked
            source_name="Test Source",
            scrape_mode=ScrapeMode.FULL_SCRAPE,
            target_url="https://example.com/task",
            is_active=True,
            last_run_time=datetime.now(timezone.utc) - timedelta(days=1),
        )
        session.add(task)
        session.flush()  # Assign ID
        task_id = task.id
        session.commit()
        logger.debug(f"Created sample task with ID: {task_id}")
    # Return data outside the session scope
    return {"id": task_id}


@pytest.fixture(scope="function")
def sample_articles_data(
    initialized_db_manager, sample_task_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """創建測試用的文章資料，返回包含關鍵數據的字典列表"""
    task_id = sample_task_data["id"]
    articles_input_data = [
        {
            "title": "AI發展新突破",
            "link": "https://example.com/ai1",
            "summary": "AI領域的重大突破",
            "content": "詳細的AI研究內容",
            "source": "科技日報",
            "source_url": "https://example.com/source1",
            "category": "AI研究",
            "published_at": datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "is_ai_related": True,
            "is_scraped": True,
            "scrape_status": ArticleScrapeStatus.CONTENT_SCRAPED,
            "tags": "AI,研究",
            "task_id": task_id,  # 關聯任務
        },
        {
            "title": "市場分析報告",
            "link": "https://example.com/market1",
            "summary": "市場趨勢分析",
            "content": "詳細的市場分析內容",
            "source": "財經週刊",
            "source_url": "https://example.com/source2",
            "category": "財經",
            "published_at": datetime(2023, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
            "is_ai_related": False,
            "is_scraped": True,
            "scrape_status": ArticleScrapeStatus.CONTENT_SCRAPED,
            "tags": "財經,市場",
            "task_id": None,  # 不關聯任務
        },
        {
            "title": "機器學習應用",
            "link": "https://example.com/ml1",
            "summary": "機器學習在產業的應用",
            "content": "機器學習應用案例",
            "source": "科技日報",
            "source_url": "https://example.com/source3",
            "category": "AI研究",
            "published_at": datetime(2023, 1, 3, 12, 0, 0, tzinfo=timezone.utc),
            "is_ai_related": True,
            "is_scraped": True,
            "scrape_status": ArticleScrapeStatus.CONTENT_SCRAPED,
            "tags": "AI,機器學習",
            "task_id": task_id,  # 關聯任務
        },
        {
            "title": "待抓取新聞",
            "link": "https://example.com/news1",
            "summary": "等待抓取的新聞",
            "content": None,
            "source": "新聞網",
            "source_url": "https://example.com/source4",
            "category": "新聞",
            "published_at": datetime(2023, 1, 4, 12, 0, 0, tzinfo=timezone.utc),
            "is_ai_related": False,
            "is_scraped": False,
            "scrape_status": ArticleScrapeStatus.LINK_SAVED,
            "tags": "新聞,科技",
            "task_id": task_id,  # 關聯任務
        },
        {
            "title": "待抓取AI新聞",
            "link": "https://example.com/news_ai",
            "summary": "等待抓取的AI相關新聞",
            "content": None,
            "source": "科技前線",
            "source_url": "https://example.com/source5",
            "category": "新聞",
            "published_at": datetime(2023, 1, 5, 12, 0, 0, tzinfo=timezone.utc),
            "is_ai_related": True,  # AI相關
            "is_scraped": False,  # 未抓取
            "scrape_status": ArticleScrapeStatus.PENDING,
            "tags": "新聞,AI",
            "task_id": task_id,  # 關聯任務
        },
    ]
    created_article_data = []
    with initialized_db_manager.session_scope() as session:
        # Clear existing data first if necessary (though initialized_db_manager might handle this)
        session.query(Articles).delete()
        session.commit()  # Commit the delete before adding new

        articles_objs = [Articles(**data) for data in articles_input_data]
        session.add_all(articles_objs)
        session.flush()  # Assign IDs

        # Retrieve necessary data after flush/commit
        # Fetch based on the task_id or other unique identifiers if needed
        articles_db = session.query(Articles).order_by(Articles.published_at).all()
        for article in articles_db:
            created_article_data.append(
                {
                    "id": article.id,
                    "title": article.title,
                    "link": article.link,
                    "summary": article.summary,
                    "content": article.content,
                    "source": article.source,
                    "source_url": article.source_url,
                    "category": article.category,
                    "published_at": article.published_at,
                    "is_ai_related": article.is_ai_related,
                    "is_scraped": article.is_scraped,
                    "scrape_status": article.scrape_status,
                    "tags": article.tags,
                    "task_id": article.task_id,
                    "created_at": article.created_at,
                    "updated_at": article.updated_at,
                }
            )
        session.commit()
        logger.debug(f"Created {len(created_article_data)} sample articles.")

    return created_article_data


class TestArticleService:
    """測試文章服務的核心功能"""

    def test_create_article(self, article_service: ArticleService):
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
            "scrape_status": ArticleScrapeStatus.CONTENT_SCRAPED,
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
            "link": "https://test.com/article1",  # 使用相同連結
            "summary": "更新摘要",
        }
        result_update = article_service.create_article(update_data)
        assert result_update["success"] is True
        assert "article" in result_update
        assert isinstance(result_update["article"], ArticleReadSchema)
        assert result_update["article"].title == update_data["title"]
        assert result_update["article"].summary == update_data["summary"]
        assert result_update["article"].link == article_data["link"]

    def test_batch_create_articles(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試批量新增文章，包含新增、更新（重複連結）和失敗情況"""
        # 準備測試數據
        existing_article_link_1 = sample_articles_data[0]["link"]
        existing_article_link_2 = sample_articles_data[1]["link"]
        original_title_1 = sample_articles_data[0]["title"]
        original_category_2 = sample_articles_data[1]["category"]
        existing_article_id_1 = sample_articles_data[0]["id"]
        existing_article_id_2 = sample_articles_data[1]["id"]

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
                "scrape_status": ArticleScrapeStatus.LINK_SAVED,
            },
            {
                # 情況 2: 連結已存在，應更新現有文章 1
                "title": "更新後的AI發展",
                "link": existing_article_link_1,
                "summary": "這是更新後的摘要",
                "is_scraped": True,
            },
            {
                # 情況 3: 連結已存在，應更新現有文章 2
                "title": "更新後的市場分析",
                "link": existing_article_link_2,
                "category": "更新後的財經分類",
                "tags": "更新,財經",
            },
            {
                # 情況 4: 缺少 link，應失敗
                "title": "無效文章 - 缺少連結",
                "summary": "此項應失敗",
                "source": "無效來源",
                "source_url": "https://invalid.com/source",
            },
        ]

        result = article_service.batch_create_articles(articles_data)

        # 驗證總體結果
        assert result["success"] is False  # 因為有一筆失敗
        assert "resultMsg" in result
        result_msg = result["resultMsg"]

        # 驗證計數
        assert (
            result_msg["success_count"] == 1
        ), f"預期創建 1 筆，實際 {result_msg['success_count']}"
        assert (
            result_msg["update_count"] == 2
        ), f"預期更新 2 筆，實際 {result_msg['update_count']}"
        assert (
            result_msg["fail_count"] == 1
        ), f"預期失敗 1 筆，實際 {result_msg['fail_count']}"

        # 驗證創建的文章
        assert "inserted_articles" in result_msg
        assert len(result_msg["inserted_articles"]) == 1
        inserted_article_schema = result_msg["inserted_articles"][0]
        assert isinstance(inserted_article_schema, ArticleReadSchema)
        assert inserted_article_schema.title == "全新批量文章"
        assert inserted_article_schema.link == "https://test.com/batch_new_unique"
        assert inserted_article_schema.id is not None

        # 驗證更新的文章
        assert "updated_articles" in result_msg
        assert len(result_msg["updated_articles"]) == 2
        updated_schema_1 = next(
            (
                a
                for a in result_msg["updated_articles"]
                if a.link == existing_article_link_1
            ),
            None,
        )
        updated_schema_2 = next(
            (
                a
                for a in result_msg["updated_articles"]
                if a.link == existing_article_link_2
            ),
            None,
        )

        assert updated_schema_1 is not None
        assert isinstance(updated_schema_1, ArticleReadSchema)
        assert updated_schema_1.title == "更新後的AI發展"
        assert updated_schema_1.summary == "這是更新後的摘要"
        assert updated_schema_1.is_scraped is True
        assert updated_schema_1.id == existing_article_id_1  # ID 應保持不變

        assert updated_schema_2 is not None
        assert isinstance(updated_schema_2, ArticleReadSchema)
        assert updated_schema_2.title == "更新後的市場分析"
        assert updated_schema_2.category == "更新後的財經分類"
        assert updated_schema_2.tags == "更新,財經"
        assert updated_schema_2.id == existing_article_id_2  # ID 應保持不變

        # 驗證失敗的項目
        assert "failed_details" in result_msg
        assert len(result_msg["failed_details"]) == 1
        failed_detail = result_msg["failed_details"][0]
        assert failed_detail["data"]["title"] == "無效文章 - 缺少連結"
        assert "缺少 'link' 欄位" in failed_detail["error"]

        # (可選) 直接檢查資料庫確認更新已生效
        with article_service._transaction() as session:
            db_article_1 = session.get(Articles, existing_article_id_1)
            db_article_2 = session.get(Articles, existing_article_id_2)
            assert db_article_1 is not None
            assert db_article_1.title == "更新後的AI發展"
            assert db_article_1.is_scraped is True
            assert db_article_2 is not None
            assert db_article_2.category == "更新後的財經分類"
            assert db_article_2.tags == "更新,財經"

            # 確認新文章已存在
            new_db_article = (
                session.query(Articles)
                .filter_by(link="https://test.com/batch_new_unique")
                .first()
            )
            assert new_db_article is not None
            assert new_db_article.title == "全新批量文章"

    def test_get_article_by_id(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試根據ID獲取文章"""
        article_to_get = sample_articles_data[0]
        article_id = article_to_get["id"]
        result = article_service.get_article_by_id(article_id)

        assert result["success"] is True
        assert "article" in result
        assert isinstance(result["article"], ArticleReadSchema)
        assert result["article"].id == article_id
        assert result["article"].title == article_to_get["title"]

        # 測試獲取不存在的文章
        result_not_found = article_service.get_article_by_id(99999)
        assert result_not_found["success"] is False
        assert result_not_found["article"] is None

    def test_get_article_by_link(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試根據連結獲取文章"""
        article_to_get = sample_articles_data[0]
        link = article_to_get["link"]
        result = article_service.get_article_by_link(link)

        assert result["success"] is True
        assert "article" in result
        assert isinstance(result["article"], ArticleReadSchema)
        assert result["article"].link == link
        assert result["article"].title == article_to_get["title"]

        # 測試獲取不存在的連結
        result_not_found = article_service.get_article_by_link(
            "https://nonexistent.com"
        )
        assert result_not_found["success"] is False
        assert result_not_found["article"] is None

    def test_find_articles_paginated(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試分頁獲取文章"""
        total_articles = len(sample_articles_data)  # Should be 5
        # 測試第一頁，完整 Schema
        result = article_service.find_articles_paginated(
            page=1, per_page=2, is_preview=False
        )

        assert result["success"] is True
        assert "resultMsg" in result
        assert isinstance(result["resultMsg"], PaginatedArticleResponse)

        paginated_response = result["resultMsg"]
        assert len(paginated_response.items) == 2
        assert all(
            isinstance(item, ArticleReadSchema) for item in paginated_response.items
        )
        assert paginated_response.total == total_articles
        assert paginated_response.page == 1
        assert paginated_response.per_page == 2
        assert (
            paginated_response.total_pages == (total_articles + 1) // 2
        )  # Ceiling division
        assert paginated_response.has_next is True
        assert paginated_response.has_prev is False

        # 測試第二頁，完整 Schema
        result_page2 = article_service.find_articles_paginated(
            page=2, per_page=2, is_preview=False
        )
        assert result_page2["success"] is True
        assert isinstance(result_page2["resultMsg"], PaginatedArticleResponse)
        paginated_response2 = result_page2["resultMsg"]
        assert len(paginated_response2.items) == 2
        assert all(
            isinstance(item, ArticleReadSchema) for item in paginated_response2.items
        )
        assert paginated_response2.page == 2
        assert (
            paginated_response2.has_next is True
        )  # 5 total, 2 per page, page 3 exists
        assert paginated_response2.has_prev is True

        # 測試預覽模式
        preview_fields = ["title", "link", "source"]
        result_preview = article_service.find_articles_paginated(
            page=1, per_page=3, is_preview=True, preview_fields=preview_fields
        )
        assert result_preview["success"] is True
        assert isinstance(result_preview["resultMsg"], PaginatedArticleResponse)
        paginated_preview_response = result_preview["resultMsg"]
        assert len(paginated_preview_response.items) == 3
        assert all(isinstance(item, dict) for item in paginated_preview_response.items)
        # Check if all expected keys are present in each dict item
        assert all(
            all(key in item for key in preview_fields)
            for item in paginated_preview_response.items
        )
        # Check if no extra keys are present
        assert all(
            len(item.keys()) == len(preview_fields)
            for item in paginated_preview_response.items
        )
        assert paginated_preview_response.total == total_articles

    def test_find_ai_related_articles(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試獲取AI相關文章，支援預覽"""
        expected_ai_count = sum(
            1 for article in sample_articles_data if article["is_ai_related"]
        )  # Should be 3

        # 測試完整 Schema
        result = article_service.find_ai_related_articles(is_preview=False)
        assert result["success"] is True
        assert "articles" in result
        assert len(result["articles"]) == expected_ai_count
        assert all(
            isinstance(article, ArticleReadSchema) for article in result["articles"]
        )
        assert all(article.is_ai_related for article in result["articles"])

        # 測試預覽模式
        preview_fields = ["title", "is_ai_related"]
        result_preview = article_service.find_ai_related_articles(
            is_preview=True, preview_fields=preview_fields, limit=2  # 測試限制數量
        )
        assert result_preview["success"] is True
        assert "articles" in result_preview
        assert len(result_preview["articles"]) == 2  # 限制為 2
        assert all(isinstance(article, dict) for article in result_preview["articles"])
        assert all(
            all(key in item for key in preview_fields)
            for item in result_preview["articles"]
        )
        assert all(
            len(item.keys()) == len(preview_fields)
            for item in result_preview["articles"]
        )
        assert all(
            article["is_ai_related"] is True for article in result_preview["articles"]
        )

    def test_find_articles_by_category(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試根據分類獲取文章，支援預覽"""
        category_to_find = "AI研究"
        expected_category_count = sum(
            1
            for article in sample_articles_data
            if article["category"] == category_to_find
        )  # Should be 2

        # 測試完整 Schema
        result = article_service.find_articles_by_category(
            category_to_find, is_preview=False
        )
        assert result["success"] is True
        assert "articles" in result
        assert len(result["articles"]) == expected_category_count
        assert all(
            isinstance(article, ArticleReadSchema) for article in result["articles"]
        )
        assert all(
            article.category == category_to_find for article in result["articles"]
        )

        # 測試預覽模式
        preview_fields = ["link", "category"]
        result_preview = article_service.find_articles_by_category(
            category_to_find, is_preview=True, preview_fields=preview_fields, limit=1
        )
        assert result_preview["success"] is True
        assert "articles" in result_preview
        assert len(result_preview["articles"]) == 1
        assert all(isinstance(article, dict) for article in result_preview["articles"])
        assert all(
            all(key in item for key in preview_fields)
            for item in result_preview["articles"]
        )
        assert all(
            len(item.keys()) == len(preview_fields)
            for item in result_preview["articles"]
        )
        assert all(
            article["category"] == category_to_find
            for article in result_preview["articles"]
        )

        # 測試無結果的分類
        result_no_match = article_service.find_articles_by_category("不存在的分類")
        assert result_no_match["success"] is True
        assert len(result_no_match["articles"]) == 0

    def test_update_article(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試更新文章"""
        article_to_update = sample_articles_data[0]
        article_id = article_to_update["id"]
        original_title = article_to_update["title"]
        update_data = {"title": "更新後的標題", "content": "更新後的內容"}

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
        assert result_no_change["article"].title == "更新後的標題"
        assert result_no_change["message"] == "文章更新操作完成 (可能無實際變更)"

        # 測試更新不存在的文章
        result_not_exist = article_service.update_article(999999, {"title": "新標題"})
        assert result_not_exist["success"] is False
        assert result_not_exist["message"] == "文章不存在，無法更新"
        assert result_not_exist["article"] is None

    def test_batch_update_articles_by_ids(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試批量更新文章"""
        article_ids = [article["id"] for article in sample_articles_data[:2]]
        update_data = {"category": "更新分類", "summary": "更新的摘要"}

        result = article_service.batch_update_articles_by_ids(article_ids, update_data)
        assert result["success"] is True
        assert "resultMsg" in result
        assert result["resultMsg"]["success_count"] == 2
        assert result["resultMsg"]["fail_count"] == 0
        assert "updated_articles" in result["resultMsg"]
        assert len(result["resultMsg"]["updated_articles"]) == 2
        assert all(
            isinstance(a, ArticleReadSchema)
            for a in result["resultMsg"]["updated_articles"]
        )
        assert all(
            a.category == "更新分類" for a in result["resultMsg"]["updated_articles"]
        )
        assert all(
            a.summary == "更新的摘要" for a in result["resultMsg"]["updated_articles"]
        )

        # 測試包含不存在的 ID
        result_with_invalid = article_service.batch_update_articles_by_ids(
            article_ids + [99999], {"is_scraped": False}
        )
        assert result_with_invalid["success"] is True  # API 本身回報 True
        assert result_with_invalid["resultMsg"]["success_count"] == 2  # 只有兩個成功
        assert result_with_invalid["resultMsg"]["fail_count"] == 1  # 一個失敗
        assert len(result_with_invalid["resultMsg"]["updated_articles"]) == 2
        assert all(
            isinstance(a, ArticleReadSchema)
            for a in result_with_invalid["resultMsg"]["updated_articles"]
        )
        assert all(
            a.is_scraped is False
            for a in result_with_invalid["resultMsg"]["updated_articles"]
        )  # 驗證成功更新的部分
        assert (
            99999 in result_with_invalid["resultMsg"]["missing_ids"]
        )  # 檢查 missing_ids

    def test_batch_update_articles_by_link(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試根據連結批量更新文章"""
        article_data = [
            {
                "link": sample_articles_data[0]["link"],
                "category": "更新分類1",
                "summary": "更新的摘要1",
            },
            {
                "link": sample_articles_data[1]["link"],
                "category": "更新分類2",
                "summary": "更新的摘要2",
            },
            {
                "link": "https://nonexistent.com/update",  # 不存在的連結
                "category": "更新分類3",
                "summary": "更新的摘要3",
            },
        ]

        result = article_service.batch_update_articles_by_link(article_data)

        assert result["success"] is True  # API 本身成功
        assert "resultMsg" in result
        result_msg = result["resultMsg"]
        assert result_msg["success_count"] == 2  # 只有兩個成功
        assert result_msg["fail_count"] == 1  # 一個失敗
        assert "updated_articles" in result_msg
        assert len(result_msg["updated_articles"]) == 2
        assert all(
            isinstance(a, ArticleReadSchema) for a in result_msg["updated_articles"]
        )
        assert result_msg["updated_articles"][0].category == "更新分類1"
        assert result_msg["updated_articles"][1].category == "更新分類2"

        # 驗證失敗的連結被記錄在 missing_links 中
        assert "missing_links" in result_msg
        assert len(result_msg["missing_links"]) == 1
        assert result_msg["missing_links"][0] == "https://nonexistent.com/update"

        # 驗證 error_details
        assert "error_details" in result_msg
        assert len(result_msg["error_details"]) == 0

    def test_delete_article(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試刪除文章"""
        article_id_to_delete = sample_articles_data[0]["id"]
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

    def test_batch_delete_articles(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試批量刪除文章"""
        article_ids_to_delete = [article["id"] for article in sample_articles_data[:2]]
        non_existent_id = 99999
        all_ids = article_ids_to_delete + [non_existent_id]

        result = article_service.batch_delete_articles(all_ids)
        assert result["success"] is False  # 因為有一個失敗了
        assert "resultMsg" in result
        assert result["resultMsg"]["success_count"] == 2
        assert result["resultMsg"]["fail_count"] == 1
        assert non_existent_id in result["resultMsg"]["missing_ids"]  # 檢查失敗的ID

        # 確認文章已被刪除
        for article_id in article_ids_to_delete:
            get_result = article_service.get_article_by_id(article_id)
            assert get_result["success"] is False

        # 測試空列表
        result_empty = article_service.batch_delete_articles([])
        assert result_empty["success"] is True
        assert result_empty["resultMsg"]["success_count"] == 0

    def test_get_articles_statistics(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試獲取文章統計資訊"""
        # Recalculate expected counts based on the fixture data
        total_count = len(sample_articles_data)
        ai_related_count = sum(1 for a in sample_articles_data if a["is_ai_related"])
        categories = {}
        sources = {}
        statuses = {}
        for a in sample_articles_data:
            categories[a["category"]] = categories.get(a["category"], 0) + 1
            sources[a["source"]] = sources.get(a["source"], 0) + 1
            status_val = (
                a["scrape_status"].value
                if isinstance(a["scrape_status"], ArticleScrapeStatus)
                else a["scrape_status"]
            )
            statuses[status_val] = statuses.get(status_val, 0) + 1

        result = article_service.get_articles_statistics()

        assert result["success"] is True
        assert "statistics" in result
        stats = result["statistics"]

        assert "total_count" in stats
        assert "ai_related_count" in stats
        assert "category_distribution" in stats
        assert "source_distribution" in stats
        assert "scrape_status_distribution" in stats

        assert stats["total_count"] == total_count
        assert stats["ai_related_count"] == ai_related_count
        assert stats["category_distribution"] == categories
        assert stats["source_distribution"] == sources
        assert stats["scrape_status_distribution"] == statuses

    def test_error_handling(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試錯誤處理"""
        # 測試創建重複連結的文章 (現在應執行更新)
        existing_link = sample_articles_data[0]["link"]
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
            "scrape_status": ArticleScrapeStatus.CONTENT_SCRAPED,
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

    def test_find_articles_advanced(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試進階搜尋文章 (分頁, 支援預覽)"""
        # 測試多條件組合搜尋 (AI研究, is_ai_related=True) - 完整 Schema
        expected_combined_count = sum(
            1
            for a in sample_articles_data
            if a["category"] == "AI研究" and a["is_ai_related"]
        )

        result_combined = article_service.find_articles_advanced(
            category="AI研究",
            is_ai_related=True,
            is_preview=False,
            page=1,  # Ensure pagination args are present
            per_page=10,  # Ensure pagination args are present
        )
        assert result_combined["success"] is True
        assert "resultMsg" in result_combined
        assert isinstance(result_combined["resultMsg"], PaginatedArticleResponse)
        paginated_response = result_combined["resultMsg"]

        assert paginated_response.total == expected_combined_count
        assert (
            len(paginated_response.items) == expected_combined_count
        )  # Assuming per_page is large enough
        assert all(isinstance(a, ArticleReadSchema) for a in paginated_response.items)
        assert all(article.category == "AI研究" for article in paginated_response.items)
        assert all(article.is_ai_related for article in paginated_response.items)

        # 測試 is_scraped 條件 - 預覽模式
        preview_fields = ["link", "is_scraped"]
        expected_unscraped_count = sum(
            1 for a in sample_articles_data if not a["is_scraped"]
        )

        result_unscraped_preview = article_service.find_articles_advanced(
            is_scraped=False,
            is_preview=True,
            preview_fields=preview_fields,
            page=1,
            per_page=10,
        )
        assert result_unscraped_preview["success"] is True
        assert isinstance(
            result_unscraped_preview["resultMsg"], PaginatedArticleResponse
        )
        paginated_preview = result_unscraped_preview["resultMsg"]
        assert paginated_preview.total == expected_unscraped_count
        assert len(paginated_preview.items) == expected_unscraped_count
        assert all(isinstance(item, dict) for item in paginated_preview.items)
        assert all(
            all(key in item for key in preview_fields)
            for item in paginated_preview.items
        )
        assert all(
            len(item.keys()) == len(preview_fields) for item in paginated_preview.items
        )
        assert all(item["is_scraped"] is False for item in paginated_preview.items)

        # 測試 source 條件 + 分頁
        source_to_find = "科技日報"
        expected_source_count = sum(
            1 for a in sample_articles_data if a["source"] == source_to_find
        )

        result_source_page = article_service.find_articles_advanced(
            source=source_to_find, page=1, per_page=1, is_preview=False
        )
        assert result_source_page["success"] is True
        assert isinstance(result_source_page["resultMsg"], PaginatedArticleResponse)
        paginated_source = result_source_page["resultMsg"]
        assert paginated_source.total == expected_source_count
        assert len(paginated_source.items) == 1  # per_page=1
        assert isinstance(paginated_source.items[0], ArticleReadSchema)
        assert paginated_source.items[0].source == source_to_find

    def test_update_article_tags(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試更新文章標籤"""
        article_to_update = sample_articles_data[0]
        article_id = article_to_update["id"]
        new_tags = ["新標籤1", "新標籤2"]

        result = article_service.update_article_tags(article_id, new_tags)
        assert result["success"] is True
        assert "article" in result
        assert isinstance(result["article"], ArticleReadSchema)
        assert result["article"].tags == ",".join(new_tags)
        assert result["article"].id == article_id

        # Verify in DB
        check_result = article_service.get_article_by_id(article_id)
        assert check_result["success"] is True
        assert check_result["article"].tags == ",".join(new_tags)

    def test_find_articles_by_title(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試根據標題搜索文章，支援預覽"""
        # 模糊搜索 - 完整 Schema
        keyword_fuzzy = "AI"
        expected_fuzzy_count = sum(
            1 for a in sample_articles_data if keyword_fuzzy in a["title"]
        )
        result_fuzzy = article_service.find_articles_by_title(
            keyword=keyword_fuzzy, is_preview=False
        )
        assert result_fuzzy["success"] is True
        assert "articles" in result_fuzzy
        assert len(result_fuzzy["articles"]) == expected_fuzzy_count
        assert all(isinstance(a, ArticleReadSchema) for a in result_fuzzy["articles"])
        assert all(
            keyword_fuzzy in article.title for article in result_fuzzy["articles"]
        )

        # 精確搜索 - 預覽模式
        preview_fields = ["title"]
        keyword_exact = "機器學習應用"
        expected_exact_count = sum(
            1 for a in sample_articles_data if keyword_exact == a["title"]
        )
        result_exact_preview = article_service.find_articles_by_title(
            keyword=keyword_exact,
            exact_match=True,
            is_preview=True,
            preview_fields=preview_fields,
        )
        assert result_exact_preview["success"] is True
        assert "articles" in result_exact_preview
        assert len(result_exact_preview["articles"]) == expected_exact_count
        assert isinstance(result_exact_preview["articles"][0], dict)
        assert all(key in result_exact_preview["articles"][0] for key in preview_fields)
        assert len(result_exact_preview["articles"][0].keys()) == len(preview_fields)
        assert result_exact_preview["articles"][0]["title"] == keyword_exact

    def test_find_articles_by_keywords(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試根據關鍵字搜索文章 (標題/內容/摘要)，支援預覽"""
        # 關鍵字搜索 - 完整 Schema
        keyword_app = "應用"
        expected_app_count = sum(
            1
            for a in sample_articles_data
            if (keyword_app in a["title"])
            or (a["summary"] and keyword_app in a["summary"])
            or (a["content"] and keyword_app in a["content"])
        )
        result = article_service.find_articles_by_keywords(
            keywords=keyword_app, is_preview=False
        )
        assert result["success"] is True
        assert "articles" in result
        assert len(result["articles"]) == expected_app_count  # Should be 1
        assert all(isinstance(a, ArticleReadSchema) for a in result["articles"])
        assert any(
            keyword_app in a.title
            or (a.summary and keyword_app in a.summary)
            or (a.content and keyword_app in a.content)
            for a in result["articles"]
        )

        # 關鍵字搜索 - 預覽模式
        preview_fields = ["summary", "link"]
        keyword_break = "突破"
        expected_break_count = sum(
            1
            for a in sample_articles_data
            if (keyword_break in a["title"])
            or (a["summary"] and keyword_break in a["summary"])
            or (a["content"] and keyword_break in a["content"])
        )
        result_preview = article_service.find_articles_by_keywords(
            keywords=keyword_break,
            is_preview=True,
            preview_fields=preview_fields,
            limit=1,
        )
        assert result_preview["success"] is True
        assert "articles" in result_preview
        assert len(result_preview["articles"]) == 1  # Limited to 1
        assert isinstance(result_preview["articles"][0], dict)
        assert all(key in result_preview["articles"][0] for key in preview_fields)
        assert len(result_preview["articles"][0].keys()) == len(preview_fields)
        assert keyword_break in result_preview["articles"][0]["summary"]

    def test_get_source_statistics(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試獲取各來源的爬取統計"""
        expected_stats = {}
        for a in sample_articles_data:
            source = a["source"]
            if source not in expected_stats:
                expected_stats[source] = {"total": 0, "scraped": 0, "unscraped": 0}
            expected_stats[source]["total"] += 1
            if a["is_scraped"]:
                expected_stats[source]["scraped"] += 1
            else:
                expected_stats[source]["unscraped"] += 1

        result = article_service.get_source_statistics()
        assert result["success"] is True
        assert "statistics" in result
        stats = result["statistics"]
        assert stats == expected_stats

    def test_update_article_scrape_status(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試更新文章爬取狀態"""
        unscraped_article_data = next(
            (
                a
                for a in sample_articles_data
                if not a["is_scraped"] and a["link"] == "https://example.com/news1"
            ),
            None,
        )
        assert (
            unscraped_article_data is not None
        ), "Could not find target unscraped article in fixture data"
        link = unscraped_article_data["link"]
        article_id = unscraped_article_data["id"]  # Need ID for verification

        # 標記為已爬取
        result = article_service.update_article_scrape_status(
            link,
            is_scraped=True,
            # 不指定 status，repo 會根據 is_scraped 設為 CONTENT_SCRAPED
        )
        assert result["success"] is True

        # 確認狀態已更新
        article_result = article_service.get_article_by_id(
            article_id
        )  # Use ID for reliable fetching
        assert article_result["success"] is True
        assert isinstance(article_result["article"], ArticleReadSchema)
        assert article_result["article"].is_scraped is True
        assert (
            article_result["article"].scrape_status
            == ArticleScrapeStatus.CONTENT_SCRAPED
        )

        # 標記回未爬取，並指定狀態
        result_false = article_service.update_article_scrape_status(
            link,
            is_scraped=False,
            scrape_status=ArticleScrapeStatus.FAILED,  # 模擬一個失敗狀態
        )
        assert result_false["success"] is True
        article_result_false = article_service.get_article_by_id(article_id)
        assert article_result_false["success"] is True
        assert isinstance(article_result_false["article"], ArticleReadSchema)
        assert article_result_false["article"].is_scraped is False
        assert (
            article_result_false["article"].scrape_status == ArticleScrapeStatus.FAILED
        )

    def test_find_unscraped_articles(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試獲取未爬取的文章，支援預覽"""
        expected_unscraped_count = sum(
            1 for a in sample_articles_data if not a["is_scraped"]
        )  # Should be 2

        # 定義狀態優先級 (數值越小越優先)
        status_priority = {
            ArticleScrapeStatus.PENDING.value: 0,
            ArticleScrapeStatus.LINK_SAVED.value: 1,
            ArticleScrapeStatus.FAILED.value: 2,  # 假設失敗比 LINK_SAVED 優先級低
            # ... 其他狀態 ...
            ArticleScrapeStatus.CONTENT_SCRAPED.value: 99,  # 已完成的優先級最低 (雖然這裡只關心未抓取的)
        }

        # Find the expected article based on custom priority sort
        expected_preview_article = next(
            (
                a
                for a in sorted(
                    sample_articles_data,
                    key=lambda x: (
                        status_priority.get(x["scrape_status"].value, 999),
                        x["id"],
                    ),  # 使用優先級排序
                )
                if not a["is_scraped"]
            ),
            None,
        )

        # --- 預覽模式 ---
        preview_fields = ["link", "scrape_status"]  # <--- 在這裡定義變數

        result_preview = article_service.find_unscraped_articles(
            is_preview=True,
            preview_fields=preview_fields,  # <--- 使用定義好的變數
            limit=1,
        )
        assert result_preview["success"] is True
        assert "articles" in result_preview
        assert len(result_preview["articles"]) == 1
        assert isinstance(result_preview["articles"][0], dict)
        # 現在 preview_fields 在作用域中，斷言可以正常工作
        assert all(key in result_preview["articles"][0] for key in preview_fields)
        assert len(result_preview["articles"][0].keys()) == len(preview_fields)
        # ... (其他斷言) ...

    def test_find_scraped_articles(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試獲取已爬取的文章，支援預覽"""
        expected_scraped_count = sum(
            1 for a in sample_articles_data if a["is_scraped"]
        )  # Should be 3

        # 完整 Schema
        result = article_service.find_scraped_articles(is_preview=False)
        assert result["success"] is True
        assert "articles" in result
        assert len(result["articles"]) == expected_scraped_count
        assert all(isinstance(a, ArticleReadSchema) for a in result["articles"])
        assert all(article.is_scraped for article in result["articles"])

        # 預覽模式
        preview_fields = ["source", "published_at"]
        result_preview = article_service.find_scraped_articles(
            is_preview=True, preview_fields=preview_fields, limit=2
        )
        assert result_preview["success"] is True
        assert "articles" in result_preview
        assert len(result_preview["articles"]) == 2
        assert all(isinstance(a, dict) for a in result_preview["articles"])
        assert all(
            all(key in item for key in preview_fields)
            for item in result_preview["articles"]
        )
        assert all(
            len(item.keys()) == len(preview_fields)
            for item in result_preview["articles"]
        )

    def test_count_unscraped_articles(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試計算未爬取的文章數量"""
        expected_count = sum(1 for a in sample_articles_data if not a["is_scraped"])
        result = article_service.count_unscraped_articles()
        assert result["success"] is True
        assert "count" in result
        assert result["count"] == expected_count  # Should be 2

    def test_count_scraped_articles(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
    ):
        """測試計算已爬取的文章數量"""
        expected_count = sum(1 for a in sample_articles_data if a["is_scraped"])
        result = article_service.count_scraped_articles()
        assert result["success"] is True
        assert "count" in result
        assert result["count"] == expected_count  # Should be 3

    def test_find_articles_by_task_id(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
        sample_task_data: Dict[str, Any],
    ):
        """測試根據 task_id 查詢文章，支援預覽"""
        task_id = sample_task_data["id"]
        expected_count_all = sum(
            1 for a in sample_articles_data if a["task_id"] == task_id
        )
        expected_count_unscraped = sum(
            1
            for a in sample_articles_data
            if a["task_id"] == task_id and not a["is_scraped"]
        )
        expected_count_scraped = sum(
            1
            for a in sample_articles_data
            if a["task_id"] == task_id and a["is_scraped"]
        )

        # 獲取所有關聯此任務的文章 - 完整 Schema
        result_all = article_service.find_articles_by_task_id(
            task_id=task_id, is_preview=False
        )
        assert result_all["success"] is True
        assert "articles" in result_all
        assert len(result_all["articles"]) == expected_count_all  # Should be 4
        assert all(isinstance(a, ArticleReadSchema) for a in result_all["articles"])
        assert all(a.task_id == task_id for a in result_all["articles"])

        # 獲取此任務未爬取的文章 - 預覽模式
        preview_fields = ["link", "is_scraped"]
        result_unscraped_preview = article_service.find_articles_by_task_id(
            task_id=task_id,
            is_scraped=False,
            is_preview=True,
            preview_fields=preview_fields,
        )
        assert result_unscraped_preview["success"] is True
        assert "articles" in result_unscraped_preview
        assert (
            len(result_unscraped_preview["articles"]) == expected_count_unscraped
        )  # Should be 2
        assert all(isinstance(a, dict) for a in result_unscraped_preview["articles"])
        assert all(
            all(key in item for key in preview_fields)
            for item in result_unscraped_preview["articles"]
        )
        assert all(
            len(item.keys()) == len(preview_fields)
            for item in result_unscraped_preview["articles"]
        )
        assert all(
            a["is_scraped"] is False for a in result_unscraped_preview["articles"]
        )

        # 獲取此任務已爬取的文章 - 完整 Schema + limit
        result_scraped_limit = article_service.find_articles_by_task_id(
            task_id=task_id, is_scraped=True, limit=1, is_preview=False
        )
        assert result_scraped_limit["success"] is True
        assert "articles" in result_scraped_limit
        assert len(result_scraped_limit["articles"]) == 1  # 限制為 1
        assert isinstance(result_scraped_limit["articles"][0], ArticleReadSchema)
        assert result_scraped_limit["articles"][0].is_scraped is True
        assert result_scraped_limit["articles"][0].task_id == task_id

    def test_count_articles_by_task_id(
        self,
        article_service: ArticleService,
        sample_articles_data: List[Dict[str, Any]],
        sample_task_data: Dict[str, Any],
    ):
        """測試計算特定 task_id 的文章數量"""
        task_id = sample_task_data["id"]
        expected_count_all = sum(
            1 for a in sample_articles_data if a["task_id"] == task_id
        )
        expected_count_unscraped = sum(
            1
            for a in sample_articles_data
            if a["task_id"] == task_id and not a["is_scraped"]
        )
        expected_count_scraped = sum(
            1
            for a in sample_articles_data
            if a["task_id"] == task_id and a["is_scraped"]
        )

        # 計算總數
        result_total = article_service.count_articles_by_task_id(task_id=task_id)
        assert result_total["success"] is True
        assert result_total["count"] == expected_count_all

        # 計算未爬取數量
        result_unscraped = article_service.count_articles_by_task_id(
            task_id=task_id, is_scraped=False
        )
        assert result_unscraped["success"] is True
        assert result_unscraped["count"] == expected_count_unscraped

        # 計算已爬取數量
        result_scraped = article_service.count_articles_by_task_id(
            task_id=task_id, is_scraped=True
        )
        assert result_scraped["success"] is True
        assert result_scraped["count"] == expected_count_scraped

        # 測試無效 task_id
        result_invalid = article_service.count_articles_by_task_id(task_id=99999)
        assert result_invalid["success"] is True
        assert result_invalid["count"] == 0
