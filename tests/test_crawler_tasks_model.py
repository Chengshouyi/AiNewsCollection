"""本模組測試 CrawlerTasks 模型的功能，包括任務創建、欄位驗證、狀態轉換和資料序列化等功能。"""

# flake8: noqa: F811
# pylint: disable=redefined-outer-name

from datetime import datetime, timedelta, timezone

import pytest

from src.models.base_model import Base
from src.models.crawler_tasks_model import CrawlerTasks, TASK_ARGS_DEFAULT
from src.utils.enum_utils import ScrapePhase, ScrapeMode, TaskStatus
from src.utils.log_utils import LoggerSetup

logger = LoggerSetup.setup_logger(__name__)


@pytest.fixture(scope="function")
def initialized_db_manager(db_manager_for_test):
    """初始化測試資料庫管理器並創建表"""
    try:
        db_manager_for_test.create_tables(Base)
        yield db_manager_for_test
    finally:
        pass


class TestCrawlerTasksModel:
    """CrawlerTasks 模型的測試類"""

    def test_crawler_tasks_creation_with_required_fields(self, initialized_db_manager):
        """測試使用必填欄位創建 CrawlerTasks"""
        with initialized_db_manager.session_scope() as session:
            task = CrawlerTasks(
                task_name="測試任務",
                crawler_id=1,
                is_auto=True,
                task_args=TASK_ARGS_DEFAULT,
                notes="測試任務",
            )
            session.add(task)
            session.flush()

            assert task.task_name == "測試任務"
            assert task.crawler_id == 1
            assert task.is_auto is True
            assert task.task_args == TASK_ARGS_DEFAULT
            assert task.notes == "測試任務"

            assert task.created_at is not None
            assert task.updated_at is not None
            assert task.updated_at.tzinfo == timezone.utc

            assert task.last_run_at is None
            assert task.last_run_success is None
            assert task.last_run_message is None
            assert task.cron_expression is None

            assert task.scrape_phase == ScrapePhase.INIT
            assert task.task_status == TaskStatus.INIT
            assert task.retry_count == 0

    def test_default_values(self, initialized_db_manager):
        """測試默認值設置"""
        with initialized_db_manager.session_scope() as session:
            task = CrawlerTasks(crawler_id=1, task_name="測試預設值任務")
            session.add(task)
            session.flush()

            assert task.is_auto is True
            assert task.is_active is True
            assert task.is_scheduled is False

            assert task.task_args["max_pages"] == 10
            assert task.task_args["ai_only"] is False
            assert task.task_args["num_articles"] == 10
            assert task.task_args["min_keywords"] == 3
            assert task.task_args["max_retries"] == 3
            assert task.task_args["retry_delay"] == 2.0
            assert task.task_args["timeout"] == 10
            assert task.task_args["is_test"] is False
            assert task.task_args["save_to_csv"] is False
            assert task.task_args["csv_file_prefix"] == ""
            assert task.task_args["save_to_database"] is True
            assert task.task_args["scrape_mode"] == ScrapeMode.FULL_SCRAPE.value
            assert task.task_args["get_links_by_task_id"] is False
            assert isinstance(task.task_args["article_links"], list)
            assert len(task.task_args["article_links"]) == 0

            assert task.notes is None
            assert task.cron_expression is None
            assert task.last_run_at is None
            assert task.last_run_success is None
            assert task.last_run_message is None

            assert task.scrape_phase == ScrapePhase.INIT
            assert task.task_status == TaskStatus.INIT
            assert task.retry_count == 0

    def test_crawler_tasks_repr(self):
        """測試 CrawlerTasks 的 __repr__ 方法"""
        task = CrawlerTasks(id=1, task_name="測試任務", crawler_id=1)

        expected_repr = "<CrawlerTask(id=1, task_name=測試任務, crawler_id=1)>"
        assert repr(task) == expected_repr

    def test_field_updates(self):
        """測試欄位更新"""
        task = CrawlerTasks(crawler_id=1, task_name="測試欄位更新")

        task.is_auto = False
        assert task.is_auto is False

        task.is_active = False
        assert task.is_active is False

        task.is_scheduled = True
        assert task.is_scheduled is True

        task.task_args = {"max_pages": 5, "num_articles": 20}
        assert task.task_args["max_pages"] == 5
        assert task.task_args["num_articles"] == 20

        task.task_name = "更新後的任務名稱"
        task.notes = "更新的備註"
        task.cron_expression = "*/5 * * * *"
        task.last_run_message = "執行成功"
        assert task.task_name == "更新後的任務名稱"
        assert task.notes == "更新的備註"
        assert task.last_run_message == "執行成功"
        assert task.cron_expression == "*/5 * * * *"

        task.scrape_phase = ScrapePhase.CONTENT_SCRAPING
        assert task.scrape_phase == ScrapePhase.CONTENT_SCRAPING

        task.task_args["max_retries"] = 5
        assert task.task_args["max_retries"] == 5

        task.retry_count = 2
        assert task.retry_count == 2

    def test_to_dict(self):
        """測試 to_dict 方法"""
        task = CrawlerTasks(
            id=1,
            task_name="測試任務",
            crawler_id=1,
            notes="測試任務",
            task_args={
                "max_pages": 5,
                "num_articles": 20,
                "scrape_mode": ScrapeMode.LINKS_ONLY.value,
            },
        )

        task_dict = task.to_dict()

        expected_keys = {
            "id",
            "task_name",
            "crawler_id",
            "is_auto",
            "is_active",
            "task_args",
            "notes",
            "created_at",
            "updated_at",
            "last_run_at",
            "last_run_success",
            "last_run_message",
            "cron_expression",
            "scrape_phase",
            "task_status",
            "retry_count",
            "is_scheduled",
        }

        assert set(task_dict.keys()) == expected_keys
        assert task_dict["is_active"] is True
        assert task_dict["scrape_phase"] == ScrapePhase.INIT.value
        assert task_dict["task_status"] == TaskStatus.INIT.value
        assert task_dict["task_args"]["scrape_mode"] == ScrapeMode.LINKS_ONLY.value

    def test_scrape_phase_transitions(self):
        """測試任務階段轉換"""
        task = CrawlerTasks(crawler_id=1)

        assert task.scrape_phase == ScrapePhase.INIT

        task.scrape_phase = ScrapePhase.LINK_COLLECTION
        assert task.scrape_phase == ScrapePhase.LINK_COLLECTION

        task.scrape_phase = ScrapePhase.CONTENT_SCRAPING
        assert task.scrape_phase == ScrapePhase.CONTENT_SCRAPING

        task.scrape_phase = ScrapePhase.COMPLETED
        assert task.scrape_phase == ScrapePhase.COMPLETED

    def test_retry_mechanism(self):
        """測試重試機制相關欄位"""
        task = CrawlerTasks(crawler_id=1, task_args={"max_retries": 5})

        assert task.task_args["max_retries"] == 5
        assert task.retry_count == 0

        task.retry_count += 1
        assert task.retry_count == 1

        task.retry_count = 0
        assert task.retry_count == 0

    def test_crawler_tasks_utc_datetime_conversion(self):
        """測試 CrawlerTasks 的 last_run_at 欄位 UTC 時間轉換"""
        naive_time = datetime(2025, 3, 28, 12, 0, 0)
        task = CrawlerTasks(crawler_id=1, last_run_at=naive_time)
        if task.last_run_at is not None:
            assert task.last_run_at.tzinfo == timezone.utc
        assert task.last_run_at == naive_time.replace(tzinfo=timezone.utc)

        utc_plus_8_time = datetime(
            2025, 3, 28, 14, 0, 0, tzinfo=timezone(timedelta(hours=8))
        )
        task.last_run_at = utc_plus_8_time
        expected_utc_time = datetime(2025, 3, 28, 6, 0, 0, tzinfo=timezone.utc)
        assert task.last_run_at.tzinfo == timezone.utc
        assert task.last_run_at == expected_utc_time

        utc_time = datetime(2025, 3, 28, 12, 0, 0, tzinfo=timezone.utc)
        task.last_run_at = utc_time
        assert task.last_run_at == utc_time

        task.notes = "新備註"
        assert task.last_run_at == utc_time

    def test_scrape_mode_enum(self):
        """測試 ScrapeMode 枚舉值及相關功能"""
        assert ScrapeMode.LINKS_ONLY.value == "links_only"
        assert ScrapeMode.CONTENT_ONLY.value == "content_only"
        assert ScrapeMode.FULL_SCRAPE.value == "full_scrape"

        task = CrawlerTasks(crawler_id=1)
        assert task.task_args["scrape_mode"] == ScrapeMode.FULL_SCRAPE.value

        task.task_args["scrape_mode"] = ScrapeMode.LINKS_ONLY.value
        assert task.task_args["scrape_mode"] == ScrapeMode.LINKS_ONLY.value

        task.task_args["scrape_mode"] = ScrapeMode.CONTENT_ONLY.value
        assert task.task_args["scrape_mode"] == ScrapeMode.CONTENT_ONLY.value

        task2 = CrawlerTasks(
            crawler_id=1, task_args={"scrape_mode": ScrapeMode.LINKS_ONLY.value}
        )
        assert task2.task_args["scrape_mode"] == ScrapeMode.LINKS_ONLY.value

    def test_relationship_fields(self, initialized_db_manager):
        """測試關聯關係欄位是否存在"""
        with initialized_db_manager.session_scope() as session:
            task = CrawlerTasks(task_name="測試關係", crawler_id=1)

            assert hasattr(task, "articles")
            assert hasattr(task, "crawler")
            assert hasattr(task, "history")

            assert task.articles == []
            assert task.crawler is None
            assert task.history == []

    def test_task_args_default(self):
        """測試 task_args 的預設值"""
        task = CrawlerTasks(crawler_id=1)

        for key, value in TASK_ARGS_DEFAULT.items():
            assert task.task_args[key] == value

        assert task.task_args["max_pages"] == TASK_ARGS_DEFAULT["max_pages"]
        assert task.task_args["ai_only"] == TASK_ARGS_DEFAULT["ai_only"]
        assert task.task_args["num_articles"] == TASK_ARGS_DEFAULT["num_articles"]
        assert task.task_args["min_keywords"] == TASK_ARGS_DEFAULT["min_keywords"]
        assert task.task_args["max_retries"] == TASK_ARGS_DEFAULT["max_retries"]
        assert task.task_args["retry_delay"] == TASK_ARGS_DEFAULT["retry_delay"]
        assert task.task_args["timeout"] == TASK_ARGS_DEFAULT["timeout"]
        assert task.task_args["is_test"] == TASK_ARGS_DEFAULT["is_test"]
        assert task.task_args["save_to_csv"] == TASK_ARGS_DEFAULT["save_to_csv"]
        assert task.task_args["csv_file_prefix"] == TASK_ARGS_DEFAULT["csv_file_prefix"]
        assert (
            task.task_args["save_to_database"] == TASK_ARGS_DEFAULT["save_to_database"]
        )
        assert task.task_args["scrape_mode"] == TASK_ARGS_DEFAULT["scrape_mode"]
        assert (
            task.task_args["get_links_by_task_id"]
            == TASK_ARGS_DEFAULT["get_links_by_task_id"]
        )
        assert isinstance(task.task_args["article_links"], list)
        assert len(task.task_args["article_links"]) == 0

        assert (
            task.task_args["save_partial_results_on_cancel"]
            == TASK_ARGS_DEFAULT["save_partial_results_on_cancel"]
        )
        assert (
            task.task_args["save_partial_to_database"]
            == TASK_ARGS_DEFAULT["save_partial_to_database"]
        )
        assert task.task_args["max_cancel_wait"] == TASK_ARGS_DEFAULT["max_cancel_wait"]
        assert (
            task.task_args["cancel_interrupt_interval"]
            == TASK_ARGS_DEFAULT["cancel_interrupt_interval"]
        )
        assert task.task_args["cancel_timeout"] == TASK_ARGS_DEFAULT["cancel_timeout"]

    def test_task_status_transitions(self):
        """測試任務狀態轉換"""
        task = CrawlerTasks(crawler_id=1)

        assert task.task_status == TaskStatus.INIT

        task.task_status = TaskStatus.RUNNING
        assert task.task_status == TaskStatus.RUNNING

        task.task_status = TaskStatus.COMPLETED
        assert task.task_status == TaskStatus.COMPLETED

        task.task_status = TaskStatus.FAILED
        assert task.task_status == TaskStatus.FAILED

        task.task_status = TaskStatus.CANCELLED
        assert task.task_status == TaskStatus.CANCELLED

    def test_cancel_related_settings(self):
        """測試取消相關設置"""
        task = CrawlerTasks(
            crawler_id=1,
            task_args={
                "save_partial_results_on_cancel": True,
                "save_partial_to_database": True,
                "max_cancel_wait": 60,
                "cancel_interrupt_interval": 10,
                "cancel_timeout": 120,
            },
        )

        assert task.task_args["save_partial_results_on_cancel"] is True
        assert task.task_args["save_partial_to_database"] is True
        assert task.task_args["max_cancel_wait"] == 60
        assert task.task_args["cancel_interrupt_interval"] == 10
        assert task.task_args["cancel_timeout"] == 120

        task.task_args["save_partial_results_on_cancel"] = False
        assert task.task_args["save_partial_results_on_cancel"] is False

        task.task_args["max_cancel_wait"] = 45
        assert task.task_args["max_cancel_wait"] == 45
