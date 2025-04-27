"""測試 ArticlesRepository 的功能。

此模組包含了對 ArticlesRepository 類的所有測試案例，包括：
- 基本的 CRUD 操作
- 搜尋和過濾功能
- 分頁功能
- 批次操作
- 統計功能
"""

# flake8: noqa: F811
# pylint: disable=redefined-outer-name

# Standard library imports
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

# Third party imports
import pytest

# Local application imports
from src.database.articles_repository import ArticlesRepository
from src.models.articles_model import Articles, ArticleScrapeStatus
from src.models.base_model import Base
from src.database.base_repository import SchemaType
from src.models.articles_schema import ArticleCreateSchema, ArticleUpdateSchema
from src.error.errors import ValidationError, DatabaseOperationError
from src.utils.log_utils import LoggerSetup

logger = LoggerSetup.setup_logger(__name__)


@pytest.fixture(scope="function")
def article_repo(initialized_db_manager):
    """為每個測試函數創建新的 ArticlesRepository 實例"""
    with initialized_db_manager.session_scope() as session:
        return ArticlesRepository(session, Articles)


@pytest.fixture(scope="function")
def clean_db(initialized_db_manager):
    """清空資料庫的 fixture"""
    with initialized_db_manager.session_scope() as session:
        session.query(Articles).delete()
        session.commit()
        session.expire_all()


@pytest.fixture(scope="function")
def sample_article_data(initialized_db_manager, clean_db) -> List[Dict[str, Any]]:
    """創建測試用的文章數據，返回包含 ID 和 Link 的字典列表"""
    with initialized_db_manager.session_scope() as session:
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
                scrape_status=ArticleScrapeStatus.PENDING,
                tags="AI,研究",
                task_id=1,
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
                scrape_status=ArticleScrapeStatus.PENDING,
                tags="財經,市場",
                task_id=1,
            ),
            Articles(
                title="Python編程技巧分享",
                link="https://example.com/article3",
                summary="這是Python相關教學",
                content="這是Python相關教學內容",
                source="測試來源1",
                source_url="https://example.com/source3",
                category="科技",
                published_at=datetime(2023, 1, 5, tzinfo=timezone.utc),
                is_ai_related=False,
                is_scraped=False,
                scrape_status=ArticleScrapeStatus.LINK_SAVED,
                tags="Python,編程",
                task_id=2,
            ),
        ]
        session.add_all(articles)
        session.commit()
        # --- 修改點：查詢 ID 和 Link，而不是整個物件 ---
        # 需要確保查詢返回的順序與我們期望的一致，以便後續測試取用
        # 最好是根據一個確定性的欄位排序，例如 link 或 published_at
        query_result = (
            session.query(Articles.id, Articles.link)
            .order_by(Articles.published_at.asc())
            .all()
        )
        # 將查詢結果轉換為字典列表
        article_data = [{"id": row.id, "link": row.link} for row in query_result]
        return article_data
        # --- 修改結束 ---


@pytest.fixture(scope="function")
def filter_test_articles(initialized_db_manager, clean_db) -> List[Articles]:
    """創建專門用於過濾和分頁測試的文章"""
    with initialized_db_manager.session_scope() as session:
        articles = [
            Articles(
                title="AI研究報告1",
                link="https://example.com/ai1",
                category="AI研究",
                published_at=datetime(2023, 1, 1, 10, tzinfo=timezone.utc),
                is_ai_related=True,
                is_scraped=True,
                tags="AI,研究,深度學習",
                task_id=10,
                scrape_status=ArticleScrapeStatus.CONTENT_SCRAPED,
                summary="AI研究摘要",
                content="AI研究內容",
                source="來源A",
                source_url="https://source.a/ai1",
            ),
            Articles(
                title="一般科技新聞1",
                link="https://example.com/tech1",
                category="科技",
                published_at=datetime(2023, 1, 10, 10, tzinfo=timezone.utc),
                is_ai_related=False,
                is_scraped=True,
                tags="科技,創新",
                task_id=10,
                scrape_status=ArticleScrapeStatus.CONTENT_SCRAPED,
                summary="科技新聞摘要",
                content="科技新聞內容",
                source="來源B",
                source_url="https://source.b/tech1",
            ),
            Articles(
                title="財經報導",
                link="https://example.com/finance",
                category="財經",
                published_at=datetime(2023, 1, 5, 10, tzinfo=timezone.utc),
                is_ai_related=False,
                is_scraped=False,
                tags="財經,市場",
                task_id=11,
                scrape_status=ArticleScrapeStatus.LINK_SAVED,
                summary="財經報導摘要",
                content="財經報導內容",
                source="來源C",
                source_url="https://source.c/finance",
            ),
            Articles(
                title="AI研究報告2",
                link="https://example.com/ai2",
                category="AI研究",
                published_at=datetime(2023, 1, 15, 10, tzinfo=timezone.utc),
                is_ai_related=True,
                is_scraped=False,
                tags="AI,研究,大語言模型",
                task_id=11,
                scrape_status=ArticleScrapeStatus.PENDING,
                summary="更多AI研究摘要",
                content="更多AI研究內容",
                source="來源A",
                source_url="https://source.a/ai2",
            ),
            Articles(
                title="一般科技新聞2",
                link="https://example.com/tech2",
                category="科技",
                published_at=datetime(2023, 1, 20, 10, tzinfo=timezone.utc),
                is_ai_related=False,
                is_scraped=True,
                tags="科技,產業",
                task_id=10,
                scrape_status=ArticleScrapeStatus.CONTENT_SCRAPED,
                summary="更多科技新聞摘要",
                content="更多科技新聞內容",
                source="來源B",
                source_url="https://source.b/tech2",
            ),
        ]
        session.add_all(articles)
        session.commit()
        session.expire_all()
        return session.query(Articles).order_by(Articles.published_at.asc()).all()


@pytest.fixture(scope="function")
def initialized_db_manager(db_manager_for_test):
    """Fixture that depends on db_manager_for_test, creates tables, and yields the manager."""
    logger.debug("Creating tables for test function...")
    try:
        db_manager_for_test.create_tables(Base)
        yield db_manager_for_test
    finally:
        logger.debug(
            "Test function finished, tables might be dropped by manager cleanup or next test setup."
        )


# ArticleRepository 測試
class TestArticleRepository:
    """測試 ArticlesRepository 的核心功能"""

    def test_get_schema_class(self, article_repo, clean_db):
        """測試獲取schema類的方法"""
        schema = article_repo.get_schema_class()
        assert schema == ArticleCreateSchema
        create_schema = article_repo.get_schema_class(SchemaType.CREATE)
        assert create_schema == ArticleCreateSchema
        update_schema = article_repo.get_schema_class(SchemaType.UPDATE)
        assert update_schema == ArticleUpdateSchema
        with pytest.raises(ValueError) as exc_info:
            article_repo.get_schema_class(SchemaType.LIST)
        assert "未支援的 schema 類型" in str(exc_info.value)

    def test_find_by_link(self, article_repo, sample_article_data, clean_db):
        """測試根據連結查詢文章"""
        article = article_repo.find_by_link("https://example.com/article1")
        assert article is not None
        assert article.title == "科技新聞：AI研究突破"
        article = article_repo.find_by_link("https://nonexistent.com")
        assert article is None

    def test_find_by_category(self, article_repo, sample_article_data, clean_db):
        """測試根據分類查詢文章"""
        articles = article_repo.find_by_category("科技")
        assert len(articles) == 2
        assert all(isinstance(article, Articles) for article in articles)  # Check type
        assert all(article.category == "科技" for article in articles)

    def test_find_by_category_preview(
        self, article_repo, sample_article_data, clean_db
    ):
        """測試根據分類查詢文章（預覽模式）"""
        preview_fields = ["title", "link"]
        articles_preview = article_repo.find_by_category(
            "科技", is_preview=True, preview_fields=preview_fields
        )
        assert len(articles_preview) == 2
        assert all(isinstance(article, dict) for article in articles_preview)
        for article_dict in articles_preview:
            assert set(article_dict.keys()) == set(preview_fields)
            assert article_dict["title"] in [
                "科技新聞：AI研究突破",
                "Python編程技巧分享",
            ]

    def test_search_by_title(self, article_repo, sample_article_data, clean_db):
        """測試根據標題搜索文章"""
        # 測試模糊匹配 (非預覽)
        articles_fuzzy = article_repo.search_by_title("Python")
        assert len(articles_fuzzy) == 1
        assert isinstance(articles_fuzzy[0], Articles)
        assert "Python" in articles_fuzzy[0].title

        # 測試精確匹配 (非預覽)
        articles_exact = article_repo.search_by_title(
            "Python編程技巧分享", exact_match=True
        )
        assert len(articles_exact) == 1
        assert isinstance(articles_exact[0], Articles)
        assert articles_exact[0].title == "Python編程技巧分享"

    def test_search_by_title_preview(self, article_repo, sample_article_data, clean_db):
        """測試根據標題搜索文章（預覽模式）"""
        preview_fields = ["link", "category"]

        # 測試模糊匹配 (預覽)
        articles_fuzzy_preview = article_repo.search_by_title(
            "Python", is_preview=True, preview_fields=preview_fields
        )
        assert len(articles_fuzzy_preview) == 1
        assert isinstance(articles_fuzzy_preview[0], dict)
        assert set(articles_fuzzy_preview[0].keys()) == set(preview_fields)
        assert articles_fuzzy_preview[0]["link"] == "https://example.com/article3"
        assert articles_fuzzy_preview[0]["category"] == "科技"

        # 測試精確匹配 (預覽)
        articles_exact_preview = article_repo.search_by_title(
            "科技新聞：AI研究突破",
            exact_match=True,
            is_preview=True,
            preview_fields=preview_fields,
        )
        assert len(articles_exact_preview) == 1
        assert isinstance(articles_exact_preview[0], dict)
        assert set(articles_exact_preview[0].keys()) == set(preview_fields)
        assert articles_exact_preview[0]["link"] == "https://example.com/article1"
        assert articles_exact_preview[0]["category"] == "科技"

    def test_search_by_keywords(self, article_repo, sample_article_data, clean_db):
        """測試根據關鍵字搜索（標題、內容、摘要）"""
        # 關鍵字 "研究" 應該匹配 article1 的 title, summary, content
        results_research = article_repo.search_by_keywords("研究")
        assert len(results_research) == 1
        assert isinstance(results_research[0], Articles)
        assert results_research[0].title == "科技新聞：AI研究突破"

        # 關鍵字 "分析" 應該匹配 article2 的 title, summary, content
        results_analysis = article_repo.search_by_keywords("分析")
        assert len(results_analysis) == 1
        assert isinstance(results_analysis[0], Articles)
        assert results_analysis[0].title == "財經報導：股市走勢分析"

        # 關鍵字 "教學" 應該匹配 article3 的 summary, content
        results_teach = article_repo.search_by_keywords("教學")
        assert len(results_teach) == 1
        assert isinstance(results_teach[0], Articles)
        assert results_teach[0].title == "Python編程技巧分享"

        # 關鍵字 "摘要" 應該匹配 article1 和 article2
        results_summary = article_repo.search_by_keywords("摘要")
        assert len(results_summary) == 2
        assert all(isinstance(a, Articles) for a in results_summary)

        # 測試不存在的關鍵字
        results_none = article_repo.search_by_keywords("不存在")
        assert len(results_none) == 0

    def test_search_by_keywords_preview(
        self, article_repo, sample_article_data, clean_db
    ):
        """測試根據關鍵字搜索（預覽模式）"""
        preview_fields = ["source", "tags"]
        # 關鍵字 "內容" 應該匹配 article1 和 article2
        results_content_preview = article_repo.search_by_keywords(
            "內容", is_preview=True, preview_fields=preview_fields
        )
        assert len(results_content_preview) == 3  # article 1, 2, 3 have "內容"
        assert all(isinstance(a, dict) for a in results_content_preview)
        sources = {a["source"] for a in results_content_preview}
        assert "測試來源1" in sources
        assert "測試來源2" in sources
        assert set(results_content_preview[0].keys()) == set(preview_fields)

    # Renamed from test_get_by_filter to test_find_by_filter_logic
    def test_find_by_filter_logic(self, article_repo, sample_article_data, clean_db):
        """測試 find_by_filter 的過濾邏輯（包括覆寫的 _apply_filters）"""
        # --- 測試標準過濾（由基類處理） ---
        articles = article_repo.find_by_filter({"category": "科技"})
        assert len(articles) == 2
        assert all(isinstance(a, Articles) for a in articles)
        assert all(a.category == "科技" for a in articles)

        articles = article_repo.find_by_filter(
            {"category": "科技", "is_ai_related": True}
        )
        assert len(articles) == 1
        assert articles[0].is_ai_related is True

        articles = article_repo.find_by_filter(
            {"published_at": {"$gte": datetime(2023, 1, 3, tzinfo=timezone.utc)}}
        )
        assert len(articles) == 2  # article2 and article3

        # --- 測試自訂過濾（由 ArticlesRepository._apply_filters 處理） ---
        # 測試 search_text
        articles_search = article_repo.find_by_filter({"search_text": "研究"})
        assert len(articles_search) == 1
        assert articles_search[0].title == "科技新聞：AI研究突破"

        # 測試 tags (LIKE)
        articles_tags = article_repo.find_by_filter({"tags": "AI"})
        assert len(articles_tags) == 1
        assert articles_tags[0].title == "科技新聞：AI研究突破"

        # 測試混合過濾
        articles_mixed = article_repo.find_by_filter(
            {
                "search_text": "科技",  # 匹配 article1 和 article3
                "is_scraped": True,  # 進一步過濾，只剩 article1
            }
        )
        assert len(articles_mixed) == 1
        assert articles_mixed[0].link == "https://example.com/article1"

    def test_get_source_statistics(self, article_repo, sample_article_data, clean_db):
        """測試獲取來源統計數據"""
        stats = article_repo.get_source_statistics()
        assert isinstance(stats, dict)
        assert len(stats) == 2
        assert "測試來源1" in stats
        assert stats["測試來源1"]["total"] == 2
        assert stats["測試來源1"]["scraped"] == 1
        assert stats["測試來源1"]["unscraped"] == 1
        assert "測試來源2" in stats
        assert stats["測試來源2"]["total"] == 1
        assert stats["測試來源2"]["scraped"] == 1
        assert stats["測試來源2"]["unscraped"] == 0

    def test_count(self, article_repo, sample_article_data, clean_db):
        """測試計算文章總數（包括使用自訂過濾）"""
        assert article_repo.count() == 3

        # 測試標準過濾
        assert article_repo.count({"category": "科技"}) == 2
        assert article_repo.count({"is_ai_related": True}) == 1

        # 測試自訂過濾 (由 overridden _apply_filters 處理)
        assert article_repo.count({"search_text": "研究"}) == 1
        assert article_repo.count({"tags": "Python"}) == 1
        assert article_repo.count({"search_text": "摘要"}) == 2

        # 測試混合過濾
        assert article_repo.count({"category": "科技", "search_text": "教學"}) == 1

    def test_get_category_distribution(
        self, article_repo, sample_article_data, clean_db
    ):
        """測試獲取分類分佈"""
        distribution = article_repo.get_category_distribution()
        assert isinstance(distribution, dict)
        assert len(distribution) == 2
        assert "科技" in distribution
        assert distribution["科技"] == 2
        assert "財經" in distribution
        assert distribution["財經"] == 1

    def test_find_by_tags(self, article_repo, sample_article_data, clean_db):
        """測試根據標籤查找文章"""
        # 測試單一標籤 (非預覽)
        articles_single = article_repo.find_by_tags(["AI"])
        assert len(articles_single) == 1
        assert isinstance(articles_single[0], Articles)
        assert articles_single[0].title == "科技新聞：AI研究突破"

        # 測試多個標籤（OR 邏輯, 非預覽）
        articles_multi = article_repo.find_by_tags(["Python", "市場"])
        assert len(articles_multi) == 2
        assert all(isinstance(a, Articles) for a in articles_multi)
        titles = {a.title for a in articles_multi}
        assert "Python編程技巧分享" in titles
        assert "財經報導：股市走勢分析" in titles

    def test_find_by_tags_preview(self, article_repo, sample_article_data, clean_db):
        """測試根據標籤查找文章（預覽模式）"""
        preview_fields = ["title", "source"]
        # 測試多個標籤（OR 邏輯, 預覽）
        articles_multi_preview = article_repo.find_by_tags(
            ["Python", "研究"], is_preview=True, preview_fields=preview_fields
        )
        assert len(articles_multi_preview) == 2
        assert all(isinstance(a, dict) for a in articles_multi_preview)
        titles_found = {a["title"] for a in articles_multi_preview}
        assert "Python編程技巧分享" in titles_found
        assert "科技新聞：AI研究突破" in titles_found
        assert set(articles_multi_preview[0].keys()) == set(preview_fields)

    def test_validate_unique_link(self, article_repo, sample_article_data, clean_db):
        """測試連結唯一性驗證"""
        with pytest.raises(ValidationError) as exc_info:
            article_repo.validate_unique_link("https://example.com/article1")
        assert "已存在具有相同連結的文章" in str(exc_info.value)
        try:
            article_repo.validate_unique_link("https://new-unique-link.com")
        except ValidationError:
            pytest.fail("新的唯一連結不應引發 ValidationError")
        with pytest.raises(ValidationError) as exc_info:
            article_repo.validate_unique_link("")
        assert "連結不可為空" in str(exc_info.value)
        with pytest.raises(ValidationError) as exc_info:
            article_repo.validate_unique_link(None)
        assert "連結不可為空" in str(exc_info.value)

    def test_create_article(self, article_repo, clean_db):
        """測試創建新文章，並驗證返回的 Article 物件"""
        article_data = {
            "title": "測試創建文章",
            "link": "https://test.com/create",
            "summary": "創建摘要",
            "content": "創建內容",
            "category": "創建類別",
            "is_ai_related": False,
            "is_scraped": False,
            "source": "創建來源",
            "source_url": "https://test.com/source_create",
            "published_at": datetime(2023, 1, 10, tzinfo=timezone.utc),
            "scrape_status": ArticleScrapeStatus.LINK_SAVED,
            "tags": "創建,測試",
            "task_id": 10,
        }
        created_article = article_repo.create(article_data)
        article_repo.session.commit()

        assert created_article is not None
        assert isinstance(created_article, Articles)
        assert created_article.id is not None
        assert created_article.title == "測試創建文章"
        assert created_article.link == "https://test.com/create"
        assert created_article.category == "創建類別"
        assert created_article.is_ai_related is False
        assert created_article.is_scraped is False
        assert created_article.scrape_status == ArticleScrapeStatus.LINK_SAVED
        assert created_article.source == "創建來源"
        assert created_article.published_at == datetime(
            2023, 1, 10, tzinfo=timezone.utc
        )
        assert created_article.tags == "創建,測試"
        assert created_article.task_id == 10
        assert created_article.created_at is not None
        assert created_article.updated_at is not None

    def test_create_article_with_missing_fields(self, article_repo, clean_db):
        """測試創建缺少必要欄位的文章，預期引發 ValidationError"""
        minimal_data = {"title": "缺少欄位測試", "link": "https://test.com/missing"}
        with pytest.raises(ValidationError) as exc_info:
            article_repo.create(minimal_data)
        error_message = str(exc_info.value)
        assert "source" in error_message or "source_url" in error_message

    def test_update_article(self, article_repo, sample_article_data, clean_db):
        """測試更新現有文章，並驗證返回的 Article 物件或 None"""
        # 1. 從 fixture 獲取包含 ID 的字典
        article_info = sample_article_data[0]
        article_id = article_info["id"]

        # 2. 在當前 session 中使用 ID 查詢文章實例
        article_in_session = article_repo.get_by_id(article_id)
        if article_in_session is None:
            pytest.fail(f"使用 ID {article_id} 未能在資料庫中找到文章")
            return

        # 記錄原始 updated_at 以便比較
        original_updated_at = article_in_session.updated_at
        assert original_updated_at is not None

        # 確保時間戳有足夠差異
        time.sleep(0.001)

        # 4. 準備更新數據
        update_data = {
            "title": "更新後的 AI 文章標題",
            "content": "這是更新後的文章內容。",
            # "is_published": True, # 根據模型確認或移除
            "published_at": datetime.now(timezone.utc),
        }
        publish_time = update_data["published_at"]

        # 5. 執行更新操作 (使用 article_id)
        updated_article_result = article_repo.update(article_id, update_data)

        # --- 新增：在 refresh 之前顯式提交交易 ---
        try:
            article_repo.session.commit()
            logger.debug("Transaction committed successfully after update.")
        except Exception as e:
            # 如果提交失敗，也要知道原因
            article_repo.session.rollback()  # 提交失敗時回滾
            pytest.fail(f"提交更新交易時出錯: {e}")
            return
        # --------------------------------------

        # 6. 驗證基本更新結果 (現在這些值應該來自已提交的狀態)
        assert updated_article_result is not None
        # refresh 前先確認物件狀態
        assert updated_article_result.id == article_id
        assert updated_article_result.title == update_data["title"]
        assert updated_article_result.content == update_data["content"]
        assert updated_article_result.published_at == publish_time

        # 7. 驗證 updated_at
        if hasattr(updated_article_result, "updated_at"):
            # 現在 refresh 應該會從已提交的資料庫狀態加載
            article_repo.session.refresh(updated_article_result)
            final_updated_at = updated_article_result.updated_at
            logger.debug(
                "Final updated_at after commit and refresh: %s", final_updated_at
            )
            logger.debug("Original updated_at: %s", original_updated_at)

            assert (
                final_updated_at is not None
            ), "updated_at should not be None after update"
            # 關鍵斷言：確認時間戳已被更新 (大於原始值)
            assert (
                final_updated_at > original_updated_at
            ), f"updated_at was not updated. Final: {final_updated_at}, Original: {original_updated_at}"
            # 可選：檢查更新時間戳不早於發布時間
            assert final_updated_at >= publish_time

        else:
            pytest.fail(
                "updated_article_result object does not have attribute 'updated_at'"
            )

        # 8. (可選) 從資料庫再次獲取以確認持久化 (這步現在意義不大，因為 refresh 已做類似工作)
        # refetched_article = article_repo.get_by_id(article_id)
        # assert refetched_article is not None
        # assert refetched_article.title == update_data["title"]
        # assert refetched_article.updated_at == final_updated_at

    def test_update_article_with_link_field(
        self, article_repo, sample_article_data, clean_db
    ):
        """測試更新文章時包含不可變欄位（如 link），預期引發 ValidationError"""
        article_info = sample_article_data[0]  # 獲取數據字典
        article_id = article_info["id"]  # 獲取 ID
        # 需要原始 title 和 link 來驗證未修改
        original_article = article_repo.get_by_id(article_id)
        if original_article is None:
            pytest.fail(f"無法獲取 ID {article_id} 的原始文章")
            return
        original_title = original_article.title
        original_link = original_article.link

        update_data_with_link = {
            "title": "嘗試更新連結",
            "link": "https://new-link.com",  # 嘗試更新 link
        }
        with pytest.raises(ValidationError) as exc_info:
            article_repo.update(article_id, update_data_with_link)
        assert "link" in str(exc_info.value).lower()
        assert (
            "不能更新不可變欄位" in str(exc_info.value)
            or "extra fields not permitted" in str(exc_info.value).lower()
        )

        # 確保文章未被修改
        db_article = article_repo.session.get(Articles, article_id)
        assert db_article.title == original_title  # 與原始標題比較
        assert db_article.link == original_link  # 與原始連結比較

    def test_batch_mark_as_scraped(self, article_repo, sample_article_data, clean_db):
        """測試批量標記文章為已爬取"""
        link1 = sample_article_data[0]["link"]  # 從字典獲取 link
        link3 = sample_article_data[2]["link"]  # 從字典獲取 link
        non_existent_link = "https://nonexistent.com"
        links_to_mark = [link1, link3, non_existent_link]
        result = article_repo.batch_mark_as_scraped(links_to_mark)
        article_repo.session.commit()
        assert isinstance(result, dict)
        assert result["success_count"] == 2
        assert result["fail_count"] == 1
        assert non_existent_link in result["failed_links"]

    def test_get_paginated_by_filter_default_sort(
        self, article_repo, filter_test_articles, clean_db
    ):
        """測試分頁查詢，使用預設排序 (published_at desc)"""
        page = 1
        per_page = 2
        total_count, items = article_repo.get_paginated_by_filter(
            filter_dict={}, page=page, per_page=per_page
        )
        total_pages = (total_count + per_page - 1) // per_page

        assert total_pages == 3
        assert total_count == 5
        assert len(items) == 2
        assert all(isinstance(a, Articles) for a in items)  # Default is not preview
        # 預設排序現在是 published_at desc
        assert items[0].title == "一般科技新聞2"  # 2023-01-20
        assert items[1].title == "AI研究報告2"  # 2023-01-15

    def test_get_paginated_by_filter_custom_sort(
        self, article_repo, filter_test_articles, clean_db
    ):
        """測試分頁查詢，使用自定義排序"""
        page = 1
        per_page = 3
        total_count, items = article_repo.get_paginated_by_filter(
            filter_dict={},
            page=page,
            per_page=per_page,
            sort_by="title",
            sort_desc=False,
        )
        has_next = page * per_page < total_count

        assert len(items) == 3
        assert all(isinstance(a, Articles) for a in items)
        titles = [item.title for item in items]
        assert titles == ["AI研究報告1", "AI研究報告2", "一般科技新聞1"]  # 依標題升序
        assert has_next is True
        assert total_count == 5

    def test_get_paginated_by_filter_preview(
        self, article_repo, filter_test_articles, clean_db
    ):
        """測試分頁查詢（預覽模式）"""
        preview_fields = ["link", "category", "published_at"]
        page = 1
        per_page = 2
        total_count, items = (
            article_repo.find_paginated(  # Use find_paginated directly for preview testing
                filter_criteria={},
                page=page,
                per_page=per_page,
                is_preview=True,
                preview_fields=preview_fields,
                sort_by="id",
                sort_desc=True,
            )
        )
        total_pages = (total_count + per_page - 1) // per_page

        assert total_pages == 3
        assert total_count == 5
        assert len(items) == 2
        assert all(isinstance(a, dict) for a in items)
        assert set(items[0].keys()) == set(preview_fields)
        assert items[0]["link"] == "https://example.com/tech2"  # ID 5
        assert items[1]["link"] == "https://example.com/ai2"  # ID 4

        # Test with filter and preview
        page = 1
        per_page = 1
        total_count_filtered, items_filtered = article_repo.find_paginated(
            filter_criteria={"is_ai_related": True},  # Should match ai1, ai2
            page=page,
            per_page=per_page,
            sort_by="published_at",
            sort_desc=True,  # Newest AI first (ai2)
            is_preview=True,
            preview_fields=preview_fields,
        )
        total_pages_filtered = (total_count_filtered + per_page - 1) // per_page

        assert total_count_filtered == 2
        assert total_pages_filtered == 2
        assert len(items_filtered) == 1
        assert isinstance(items_filtered[0], dict)
        assert items_filtered[0]["link"] == "https://example.com/ai2"

    def test_pagination_navigation(self, article_repo, filter_test_articles, clean_db):
        """測試分頁導航屬性 (has_next, has_prev)"""
        page = 1
        per_page = 2
        total_expected = 5
        total_pages_expected = 3

        total_count, items = article_repo.get_paginated_by_filter(
            filter_dict={}, page=page, per_page=per_page
        )

        has_prev = page > 1
        has_next = page * per_page < total_count
        calculated_total_pages = (total_count + per_page - 1) // per_page

        assert has_prev is False
        assert has_next is True
        assert calculated_total_pages == total_pages_expected
        assert total_count == total_expected

    def test_delete_by_link(self, article_repo, sample_article_data, clean_db):
        """測試根據連結刪除文章，並在找不到連結時引發 ValidationError"""
        articles = sample_article_data
        link_to_delete = articles[0]["link"]
        id_to_delete = articles[0]["id"]
        deleted = article_repo.delete_by_link(link_to_delete)
        assert deleted is True
        article_repo.session.commit()
        assert article_repo.session.get(Articles, id_to_delete) is None
        with pytest.raises(ValidationError) as exc_info:
            article_repo.delete_by_link(link_to_delete)
        assert f"連結 '{link_to_delete}' 不存在，無法刪除" in str(exc_info.value)

    def test_count_unscraped_links(self, article_repo, sample_article_data, clean_db):
        """測試計算未爬取連結的數量"""
        assert article_repo.count_unscraped_links() == 1

        # --- 修改：獲取並修改 ORM 物件 ---
        article_id_to_modify = sample_article_data[2]["id"]  # 獲取第三篇文章的 ID
        article_to_modify = article_repo.get_by_id(article_id_to_modify)
        if article_to_modify is None:
            pytest.fail(f"無法獲取 ID 為 {article_id_to_modify} 的文章進行修改")
            return

        article_to_modify.is_scraped = True  # 修改 ORM 物件的屬性
        # --- 修改結束 ---

        article_repo.session.commit()  # 提交更改
        assert article_repo.count_unscraped_links() == 0  # 現在斷言應該通過

    def test_count_scraped_links(self, article_repo, sample_article_data, clean_db):
        """測試計算已爬取連結的數量"""
        assert article_repo.count_scraped_links() == 2

        # --- 修改：獲取並修改 ORM 物件 ---
        article_id_to_modify = sample_article_data[0]["id"]  # 獲取第一篇文章的 ID
        article_to_modify = article_repo.get_by_id(article_id_to_modify)
        if article_to_modify is None:
            pytest.fail(f"無法獲取 ID 為 {article_id_to_modify} 的文章進行修改")
            return

        article_to_modify.is_scraped = False  # 修改 ORM 物件的屬性
        # --- 修改結束 ---

        article_repo.session.commit()  # 提交更改
        assert article_repo.count_scraped_links() == 1  # 現在斷言應該通過

    def test_count_scraped_articles(self, article_repo, sample_article_data, clean_db):
        """測試計算已成功爬取內容的文章數量 (實際測試的是 is_scraped=True 的數量)"""
        assert article_repo.count_scraped_articles() == 2

        # --- 修改：獲取並修改 ORM 物件 ---
        article_id_to_modify = sample_article_data[2]["id"]  # 獲取第三篇文章的 ID
        article_to_modify = article_repo.get_by_id(article_id_to_modify)
        if article_to_modify is None:
            pytest.fail(f"無法獲取 ID 為 {article_id_to_modify} 的文章進行修改")
            return

        article_to_modify.is_scraped = True  # 修改 ORM 物件的屬性
        # --- 修改結束 ---

        article_repo.session.commit()  # 提交更改
        assert article_repo.count_scraped_articles() == 3  # 現在斷言應該通過

    def test_find_unscraped_links(self, article_repo, sample_article_data, clean_db):
        """測試查找未爬取的連結"""
        # sample_article_data[2] is initially unscraped
        unscraped_articles = article_repo.find_unscraped_links()
        assert len(unscraped_articles) == 1
        assert isinstance(unscraped_articles[0], Articles)
        assert unscraped_articles[0].link == sample_article_data[2]["link"]

    def test_find_unscraped_links_preview(
        self, article_repo, sample_article_data, clean_db
    ):
        """測試查找未爬取的連結（預覽模式）"""
        preview_fields = ["link", "scrape_status"]
        unscraped_preview = article_repo.find_unscraped_links(
            is_preview=True, preview_fields=preview_fields, limit=1
        )
        assert len(unscraped_preview) == 1
        assert isinstance(unscraped_preview[0], dict)
        assert set(unscraped_preview[0].keys()) == set(preview_fields)
        assert unscraped_preview[0]["link"] == sample_article_data[2]["link"]
        assert unscraped_preview[0]["scrape_status"] == ArticleScrapeStatus.LINK_SAVED

    def test_find_scraped_links(self, article_repo, sample_article_data, clean_db):
        """測試查找已爬取的連結"""
        scraped_articles = article_repo.find_scraped_links()
        assert len(scraped_articles) == 2
        assert all(isinstance(a, Articles) for a in scraped_articles)
        links_found = {a.link for a in scraped_articles}
        assert sample_article_data[0]["link"] in links_found
        assert sample_article_data[1]["link"] in links_found

    def test_find_scraped_links_preview(
        self, article_repo, sample_article_data, clean_db
    ):
        """測試查找已爬取的連結（預覽模式）"""
        preview_fields = ["title", "is_ai_related"]
        scraped_preview = article_repo.find_scraped_links(
            is_preview=True, preview_fields=preview_fields, limit=1
        )
        assert len(scraped_preview) == 1
        assert isinstance(scraped_preview[0], dict)
        assert set(scraped_preview[0].keys()) == set(preview_fields)

        # --- 修改斷言：直接使用已知的標題 ---
        expected_scraped_titles = [
            "科技新聞：AI研究突破",  # Article 1
            "財經報導：股市走勢分析",  # Article 2
        ]
        # 由於 limit=1 且預設排序不確定，只需確保返回的標題是預期中的一個即可
        assert scraped_preview[0]["title"] in expected_scraped_titles
        # --- 修改結束 ---

    def test_find_articles_by_task_id(
        self, article_repo, filter_test_articles, clean_db
    ):
        """測試根據 task_id 查找文章，並驗證返回列表"""
        # Test non-preview
        result_task10 = article_repo.find_articles_by_task_id(task_id=10)
        assert len(result_task10) == 3
        assert all(isinstance(a, Articles) for a in result_task10)
        titles_task10 = {a.title for a in result_task10}
        assert "AI研究報告1" in titles_task10
        assert "一般科技新聞1" in titles_task10
        assert "一般科技新聞2" in titles_task10

        result_task11 = article_repo.find_articles_by_task_id(task_id=11, limit=1)
        assert len(result_task11) == 1
        assert isinstance(result_task11[0], Articles)
        # find_articles_by_task_id sorts by scrape_status asc, then updated_at desc
        # Assuming ai2 (PENDING) comes before finance (LINK_SAVED)
        assert result_task11[0].title == "AI研究報告2"

    def test_find_articles_by_task_id_preview(
        self, article_repo, filter_test_articles, clean_db
    ):
        """測試根據 task_id 查找文章（預覽模式）"""
        preview_fields = ["link", "tags"]
        result_task11_preview = article_repo.find_articles_by_task_id(
            task_id=11, limit=1, is_preview=True, preview_fields=preview_fields
        )
        assert len(result_task11_preview) == 1
        assert isinstance(result_task11_preview[0], dict)
        assert set(result_task11_preview[0].keys()) == set(preview_fields)
        assert (
            result_task11_preview[0]["link"] == "https://example.com/ai2"
        )  # Based on sort

    def test_count_articles_by_task_id(
        self, article_repo, filter_test_articles, clean_db
    ):
        """測試根據 task_id 計算文章數量"""
        assert article_repo.count_articles_by_task_id(task_id=10) == 3
        assert article_repo.count_articles_by_task_id(task_id=11) == 2
        assert (
            article_repo.count_articles_by_task_id(task_id=10, is_scraped=True) == 3
        )  # tech1, tech2, ai1 are scraped
        assert (
            article_repo.count_articles_by_task_id(task_id=11, is_scraped=False) == 2
        )  # ai2, finance are unscraped
