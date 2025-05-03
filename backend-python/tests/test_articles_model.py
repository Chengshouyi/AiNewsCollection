"""本模組針對 Articles 相關模型進行單元測試，驗證其資料結構與資料庫互動行為。"""

import logging
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.articles_model import Articles, ArticleScrapeStatus
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.base_model import Base
  # 使用統一的 logger

# flake8: noqa: F811
# pylint: disable=redefined-outer-name

logger = logging.getLogger(__name__)  # 使用統一的 logger  # 使用統一的 logger


@pytest.fixture(scope="function")
def initialized_db_manager(db_manager_for_test):
    """
    依賴 db_manager_for_test，建立資料表並回傳資料庫管理器。
    """
    logger.debug("建立測試用資料表...")
    try:
        db_manager_for_test.create_tables(Base)
        yield db_manager_for_test
    finally:
        logger.debug("測試結束，資料表將由管理器清理。")


class TestArticleModel:
    """Article 模型的基本測試類"""

    def test_article_creation_with_required_fields_only(self, initialized_db_manager):
        """測試只使用必填欄位創建 Article"""
        article = Articles(
            title="測試文章",
            link="https://test.com/article",
            source="Bnext",
            source_url="https://test.com/article",
            summary="這是一篇測試文章的摘要",
            category="科技",
            is_ai_related=False,
            is_scraped=True,
            scrape_status=ArticleScrapeStatus.PENDING,
        )
        with initialized_db_manager.session_scope() as session:
            session.add(article)
            session.commit()

            assert article.title == "測試文章"
            assert article.link == "https://test.com/article"
            assert article.source == "Bnext"
            assert article.source_url == "https://test.com/article"
            assert article.summary == "這是一篇測試文章的摘要"
            assert article.category == "科技"
            assert article.is_ai_related is False
            assert article.is_scraped is True
            assert article.created_at is not None
            assert article.task_id is None
            assert article.scrape_status == ArticleScrapeStatus.PENDING

    def test_article_creation_with_all_fields(self, initialized_db_manager):
        """測試使用所有欄位創建 Article"""
        # 創建一個測試任務
        task = CrawlerTasks(
            task_name="測試任務", crawler_id=1, is_auto=True, ai_only=False
        )

        with initialized_db_manager.session_scope() as session:
            session.add(task)
            session.commit()
            article = Articles(
                title="完整測試文章",
                link="https://test.com/full-article",
                summary="這是一篇測試文章的摘要",
                content="這是一篇測試文章的完整內容，包含了多個段落...",
                category="科技",
                published_at=datetime(2023, 4, 1, tzinfo=timezone.utc),
                author="測試作者",
                source="測試來源",
                source_url="https://test.com/full-article",
                article_type="新聞",
                tags="AI,科技,測試",
                is_ai_related=True,
                is_scraped=True,
                task_id=task.id,
                scrape_status=ArticleScrapeStatus.PENDING,
            )
            session.add(article)
            session.commit()

            assert article.title == "完整測試文章"
            assert article.link == "https://test.com/full-article"
            assert article.source == "測試來源"
            assert article.source_url == "https://test.com/full-article"
            assert article.summary == "這是一篇測試文章的摘要"
            assert article.content == "這是一篇測試文章的完整內容，包含了多個段落..."
            assert article.category == "科技"
            assert article.published_at == datetime(2023, 4, 1, tzinfo=timezone.utc)
            assert article.author == "測試作者"
            assert article.article_type == "新聞"
            assert article.tags == "AI,科技,測試"
            assert article.is_ai_related is True
            assert article.is_scraped is True
            assert article.task_id == task.id
            assert article.scrape_status == ArticleScrapeStatus.PENDING

    def test_article_is_ai_related_update(self, initialized_db_manager):
        """測試 Article 的 is_ai_related 欄位更新"""
        article = Articles(
            title="測試文章",
            link="https://test.com/article",
            source="Bnext",
            source_url="https://test.com/article",
            summary="這是一篇測試文章的摘要",
            category="科技",
            is_ai_related=False,
            is_scraped=True,
        )

        article.is_ai_related = True
        assert article.is_ai_related is True

        article.is_ai_related = False
        assert article.is_ai_related is False

    def test_article_is_scraped_update(self, initialized_db_manager):
        """測試 Article 的 is_scraped 欄位更新"""
        article = Articles(
            title="測試文章",
            link="https://test.com/article",
            source="Bnext",
            source_url="https://test.com/article",
            summary="這是一篇測試文章的摘要",
            category="科技",
            is_ai_related=False,
            is_scraped=True,
        )
        article.is_scraped = True
        assert article.is_scraped is True
        article.is_scraped = False
        assert article.is_scraped is False

    def test_article_mutable_fields_update(self, initialized_db_manager):
        """測試 Article 的可變欄位更新"""
        article = Articles(
            title="原始標題",
            link="https://test.com/article",
            source="Bnext",
            source_url="https://test.com/article",
            summary="這是一篇測試文章的摘要",
            category="科技",
            is_ai_related=False,
            is_scraped=True,
        )

        # 更新可變欄位
        article.title = "更新後的標題"
        article.summary = "更新後的摘要"
        article.content = "新增的內容"
        article.category = "娛樂"
        article.published_at = datetime(2023, 4, 2, tzinfo=timezone.utc)
        article.author = "更新後的作者"
        article.source = "更新後的來源"
        article.source_url = "https://test.com/updated-article"
        article.article_type = "新聞"
        article.tags = "AI,科技,測試"

        assert article.title == "更新後的標題"
        assert article.summary == "更新後的摘要"
        assert article.content == "新增的內容"
        assert article.category == "娛樂"
        assert article.published_at == datetime(2023, 4, 2, tzinfo=timezone.utc)
        assert article.author == "更新後的作者"
        assert article.source == "更新後的來源"
        assert article.source_url == "https://test.com/updated-article"
        assert article.article_type == "新聞"
        assert article.tags == "AI,科技,測試"

    def test_article_repr(self, initialized_db_manager):
        """測試 Article 的 __repr__ 方法"""
        article = Articles(id=1, title="測試文章", link="https://test.com/article")

        assert (
            repr(article)
            == "<Article(id=1, title='測試文章', link='https://test.com/article')>"
        )

    def test_article_to_dict(self, initialized_db_manager):
        """測試 Article 的 to_dict 方法"""
        test_time = datetime.now(timezone.utc)
        article = Articles(
            id=1,
            title="測試文章",
            link="https://test.com/article",
            summary="測試摘要",
            content="測試內容",
            category="測試分類",
            published_at=test_time,
            author="測試作者",
            source="測試來源",
            source_url="https://test.com/article",
            article_type="測試類型",
            tags="測試標籤",
            is_ai_related=True,
            is_scraped=True,
            created_at=test_time,
            updated_at=test_time,
            scrape_status=ArticleScrapeStatus.PENDING,
        )

        article_dict = article.to_dict()
        assert article_dict == {
            "id": 1,
            "title": "測試文章",
            "summary": "測試摘要",
            "content": "測試內容",
            "link": "https://test.com/article",
            "category": "測試分類",
            "published_at": test_time.isoformat(),
            "author": "測試作者",
            "source": "測試來源",
            "source_url": "https://test.com/article",
            "article_type": "測試類型",
            "tags": "測試標籤",
            "is_ai_related": True,
            "is_scraped": True,
            "created_at": test_time.isoformat(),
            "updated_at": test_time.isoformat(),
            "scrape_status": ArticleScrapeStatus.PENDING.value,
            "scrape_error": None,
            "last_scrape_attempt": None,
            "task_id": None,
        }

    def test_article_default_timestamps(self, initialized_db_manager):
        """測試 Article 的時間戳記預設值"""
        article = Articles(
            title="測試文章",
            link="https://test.com/article",
            source="Bnext",
            source_url="https://test.com/article",
            summary="這是一篇測試文章的摘要",
            category="科技",
            is_ai_related=False,
            is_scraped=True,
        )

        assert isinstance(article.created_at, datetime)
        assert article.created_at.tzinfo == timezone.utc
        assert article.updated_at is not None
        assert article.updated_at.tzinfo == timezone.utc

        # 模擬更新操作
        article.title = "新標題"
        # 注意：實際更新時間需要透過 SQLAlchemy session 的操作才會觸發

    def test_article_utc_datetime_conversion(self, initialized_db_manager):
        """測試 Article 的 published_at 欄位 UTC 時間轉換"""

        # 測試 1: 傳入無時區資訊的 datetime (naive datetime)
        naive_time = datetime(2025, 3, 28, 12, 0, 0)  # 無時區資訊
        article = Articles(
            title="測試 UTC 轉換",
            link="https://test.com/utc-test",
            source="Bnext",
            source_url="https://test.com/utc-test",
            summary="這是一篇測試文章的摘要",
            category="科技",
            is_ai_related=False,
            is_scraped=True,
            published_at=naive_time,
        )
        if article.published_at is not None:
            assert article.published_at.tzinfo == timezone.utc  # 確認有 UTC 時區
        assert article.published_at == naive_time.replace(
            tzinfo=timezone.utc
        )  # 確認值正確

        # 測試 2: 傳入帶非 UTC 時區的 datetime (aware datetime, UTC+8)
        utc_plus_8_time = datetime(
            2025, 3, 28, 14, 0, 0, tzinfo=timezone(timedelta(hours=8))
        )
        article.published_at = utc_plus_8_time
        expected_utc_time = datetime(
            2025, 3, 28, 6, 0, 0, tzinfo=timezone.utc
        )  # UTC+8 轉 UTC
        assert article.published_at.tzinfo == timezone.utc  # 確認轉換為 UTC 時區
        assert article.published_at == expected_utc_time  # 確認時間正確轉換

        # 測試 3: 傳入已是 UTC 的 datetime，確保不變
        utc_time = datetime(2025, 3, 28, 12, 0, 0, tzinfo=timezone.utc)
        article.published_at = utc_time
        assert article.published_at == utc_time  # 確認值未被改變

        # 測試 4: 確認非監聽欄位（如 title）不觸發轉換邏輯
        article.title = "新標題"
        assert article.published_at == utc_time  # published_at 不受影響

    def test_article_task_relationship(self, initialized_db_manager):
        """測試 Article 與 CrawlerTasks 的關聯"""
        # 創建一個測試任務並保存到資料庫
        task = CrawlerTasks(
            task_name="測試任務", crawler_id=1, is_auto=True, ai_only=False
        )
        with initialized_db_manager.session_scope() as session:
            session.add(task)
            session.commit()

            # 使用唯一的 link
            unique_link = f"https://test.com/article/{datetime.now().timestamp()}"

            # 創建一個關聯到任務的文章
            article = Articles(
                title="測試文章",
                link=unique_link,  # 使用唯一的 link
                source="Bnext",
                source_url=unique_link,  # 保持一致
                task_id=task.id,
                scrape_status=ArticleScrapeStatus.PENDING,
            )
            session.add(article)
            session.commit()

            # 重新載入文章以確保關聯被正確設置
            article = session.get(Articles, article.id)

            # 測試關聯
            assert article.task_id == task.id
            assert article.task == task  # 測試 relationship 是否正確設置

            # 測試反向關聯
            assert article in task.articles  # 測試 task.articles 是否包含該文章

    def test_article_to_dict_with_task(self, initialized_db_manager):
        """測試 Article 的 to_dict 方法包含 task_id"""
        test_time = datetime.now(timezone.utc)
        task = CrawlerTasks(
            task_name="測試任務", crawler_id=1, is_auto=True, ai_only=False
        )
        with initialized_db_manager.session_scope() as session:
            session.add(task)
            session.commit()

            # 使用唯一的 link
            unique_link = f"https://test.com/article/{datetime.now().timestamp()}"

            article = Articles(
                title="測試文章",
                link=unique_link,  # 使用唯一的 link
                source="Bnext",
                source_url=unique_link,  # 保持一致
                task_id=task.id,
                created_at=test_time,
                updated_at=test_time,
                scrape_status=ArticleScrapeStatus.PENDING,
            )
            session.add(article)
            session.commit()

            article_dict = article.to_dict()
            assert article_dict["task_id"] == task.id
            assert article_dict["scrape_status"] == ArticleScrapeStatus.PENDING.value
