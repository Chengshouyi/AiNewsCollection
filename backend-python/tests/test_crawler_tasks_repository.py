"""測試 CrawlerTasksRepository 的功能。"""

# Standard Library Imports
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List
from unittest.mock import patch

# Third-Party Imports
import pytest
from sqlalchemy.orm.attributes import flag_modified

# Local Application Imports
from src.database.base_repository import SchemaType
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.error.errors import DatabaseOperationError, ValidationError
from src.models.base_model import Base
from src.models.crawler_tasks_model import (
    TASK_ARGS_DEFAULT,
    CrawlerTasks,
    ScrapeMode,
    ScrapePhase,
    TaskStatus,
)
from src.models.crawlers_model import Crawlers
  # 使用統一的 logger
from src.utils.transform_utils import convert_to_dict

# flake8: noqa: F811
# pylint: disable=redefined-outer-name

logger = logging.getLogger(__name__)  # 使用統一的 logger  # 使用統一的 logger


# 使用 db_manager_for_test 創建 initialized_db_manager fixture
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


# 修改 crawler_tasks_repo fixture 以使用 initialized_db_manager
@pytest.fixture(scope="function")
def crawler_tasks_repo(initialized_db_manager) -> Iterator[CrawlerTasksRepository]:
    """為每個測試函數創建新的 CrawlerTasksRepository 實例"""
    with initialized_db_manager.session_scope() as session:
        yield CrawlerTasksRepository(session, CrawlerTasks)


# 修改 clean_db fixture 以使用 initialized_db_manager
@pytest.fixture(scope="function")
def clean_db(initialized_db_manager):
    """清空資料庫的 fixture"""
    with initialized_db_manager.session_scope() as session:
        session.query(CrawlerTasks).delete()
        session.query(Crawlers).delete()
        session.commit()


@pytest.fixture(scope="function")
def sample_crawler_data(initialized_db_manager, clean_db) -> Dict[str, Any]:
    """創建測試用的爬蟲資料，返回包含 ID 的字典"""
    crawler_data = {
        "crawler_name": "測試爬蟲",
        "module_name": "test_module",
        "base_url": "https://example.com",
        "is_active": True,
        "crawler_type": "news",
        "config_file_name": "test_crawler_config.json",
    }
    crawler_id = None
    with initialized_db_manager.session_scope() as session:
        crawler = Crawlers(**crawler_data)
        session.add(crawler)
        session.commit()
        crawler_id = crawler.id
    if crawler_id is None:
        pytest.fail("Failed to get crawler_id within session scope.")
    return {"id": crawler_id, **crawler_data}


@pytest.fixture(scope="function")
def sample_tasks_data(
    initialized_db_manager, sample_crawler_data: Dict[str, Any], clean_db
) -> List[Dict[str, Any]]:
    """創建測試用的任務資料，返回包含 ID 和關鍵數據的字典列表"""
    crawler_id = sample_crawler_data["id"]
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    two_days_ago = now - timedelta(days=2)

    tasks_input_data = [
        {  # ID: 1
            "task_name": "自動AI任務(活動)",
            "crawler_id": crawler_id,
            "is_auto": True,
            "is_scheduled": True,
            "is_active": True,
            "cron_expression": "0 * * * *",
            "task_args": {
                **TASK_ARGS_DEFAULT,
                "ai_only": True,
                "max_pages": 10,
                "save_to_csv": False,
                "scrape_mode": ScrapeMode.FULL_SCRAPE.value,
            },
            "notes": "自動AI任務",
            "scrape_phase": ScrapePhase.COMPLETED,
            "task_status": TaskStatus.COMPLETED,
            "last_run_at": yesterday,
            "last_run_success": True,
            "retry_count": 0,
            "max_retries": 3,
        },
        {  # ID: 2
            "task_name": "自動一般任務(活動)",
            "crawler_id": crawler_id,
            "is_auto": True,
            "is_scheduled": True,
            "is_active": True,
            "cron_expression": "30 * * * *",
            "task_args": {
                **TASK_ARGS_DEFAULT,
                "ai_only": False,
                "max_pages": 5,
                "save_to_csv": True,
                "scrape_mode": ScrapeMode.LINKS_ONLY.value,
            },
            "notes": "有Notes的失敗任務",
            "scrape_phase": ScrapePhase.FAILED,
            "task_status": TaskStatus.FAILED,
            "last_run_at": now - timedelta(hours=1),
            "last_run_success": False,
            "retry_count": 1,
            "max_retries": 3,
        },
        {  # ID: 3
            "task_name": "手動AI任務(活動)",
            "crawler_id": crawler_id,
            "is_auto": False,
            "is_scheduled": False,
            "is_active": True,
            "cron_expression": None,
            "task_args": {
                **TASK_ARGS_DEFAULT,
                "ai_only": True,
                "max_pages": 100,
                "save_to_csv": False,
                "scrape_mode": ScrapeMode.CONTENT_ONLY.value,
            },
            "notes": "手動AI任務",
            "scrape_phase": ScrapePhase.INIT,
            "task_status": TaskStatus.INIT,
            "last_run_at": None,
            "last_run_success": None,
            "retry_count": 0,
            "max_retries": 0,
        },
        {  # ID: 4
            "task_name": "自動一般任務(非活動)",
            "crawler_id": crawler_id,
            "is_auto": True,
            "is_scheduled": True,
            "is_active": False,
            "cron_expression": "0 0 * * *",
            "task_args": {
                **TASK_ARGS_DEFAULT,
                "ai_only": False,
                "max_pages": 20,
                "save_to_csv": False,
                "scrape_mode": ScrapeMode.FULL_SCRAPE.value,
            },
            "notes": "非活動任務",
            "scrape_phase": ScrapePhase.COMPLETED,
            "task_status": TaskStatus.COMPLETED,
            "last_run_at": two_days_ago,
            "last_run_success": True,
            "retry_count": 3,
            "max_retries": 5,
        },
        {  # ID: 5
            "task_name": "手動AI任務(非活動)",
            "crawler_id": crawler_id,
            "is_auto": False,
            "is_scheduled": False,
            "is_active": False,
            "cron_expression": None,
            "task_args": {
                **TASK_ARGS_DEFAULT,
                "ai_only": True,
                "max_pages": 50,
                "save_to_csv": True,
                "scrape_mode": ScrapeMode.LINKS_ONLY.value,
            },
            "notes": None,
            "scrape_phase": ScrapePhase.INIT,
            "task_status": TaskStatus.INIT,
            "last_run_at": None,
            "last_run_success": None,
            "retry_count": 0,
            "max_retries": 3,
        },
        {  # ID: 6
            "task_name": "運行中任務(活動)",
            "crawler_id": crawler_id,
            "is_auto": True,
            "is_scheduled": True,
            "is_active": True,
            "cron_expression": "*/5 * * * *",
            "task_args": {
                **TASK_ARGS_DEFAULT,
                "ai_only": False,
                "max_pages": 15,
                "save_to_csv": False,
                "scrape_mode": ScrapeMode.FULL_SCRAPE.value,
            },
            "notes": "運行中",
            "scrape_phase": ScrapePhase.CONTENT_SCRAPING,
            "task_status": TaskStatus.RUNNING,
            "last_run_at": now - timedelta(minutes=2),
            "last_run_success": None,
            "retry_count": 0,
            "max_retries": 3,
        },
    ]

    created_tasks_data = []
    with initialized_db_manager.session_scope() as session:
        tasks_orm = [CrawlerTasks(**data) for data in tasks_input_data]
        session.add_all(tasks_orm)
        session.commit()
        for task in tasks_orm:
            session.refresh(task)
            task_dict = task.to_dict()
            created_tasks_data.append(task_dict)

    logger.debug(f"Created {len(created_tasks_data)} tasks.")
    return created_tasks_data


class TestCrawlerTasksRepository:
    """CrawlerTasksRepository 測試類"""

    def test_find_by_crawler_id(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        sample_tasks_data: List[Dict[str, Any]],
        sample_crawler_data: Dict[str, Any],
    ):
        crawler_id = sample_crawler_data["id"]
        active_count = sum(
            1
            for t in sample_tasks_data
            if t["crawler_id"] == crawler_id and t["is_active"]
        )
        inactive_count = sum(
            1
            for t in sample_tasks_data
            if t["crawler_id"] == crawler_id and not t["is_active"]
        )

        tasks_active = crawler_tasks_repo.find_tasks_by_crawler_id(crawler_id)
        assert len(tasks_active) == active_count
        assert all(
            isinstance(task, CrawlerTasks)
            and task.crawler_id == crawler_id
            and task.is_active
            for task in tasks_active
        )

        tasks_inactive = crawler_tasks_repo.find_tasks_by_crawler_id(
            crawler_id, is_active=False
        )
        assert len(tasks_inactive) == inactive_count
        assert all(
            isinstance(task, CrawlerTasks)
            and task.crawler_id == crawler_id
            and not task.is_active
            for task in tasks_inactive
        )

        tasks_limit = crawler_tasks_repo.find_tasks_by_crawler_id(crawler_id, limit=2)
        assert len(tasks_limit) <= 2
        assert len(tasks_limit) == min(active_count, 2)

        preview_fields = ["id", "task_name"]
        tasks_preview = crawler_tasks_repo.find_tasks_by_crawler_id(
            crawler_id, is_preview=True, preview_fields=preview_fields, limit=1
        )
        assert len(tasks_preview) <= 1
        if tasks_preview:
            assert isinstance(tasks_preview[0], dict)
            assert all(field in tasks_preview[0] for field in preview_fields)
            assert tasks_preview[0]["id"] is not None
            assert tasks_preview[0]["task_name"] is not None

        tasks_preview_invalid = crawler_tasks_repo.find_tasks_by_crawler_id(
            crawler_id, is_preview=True, preview_fields=["invalid_field"], limit=1
        )
        assert len(tasks_preview_invalid) <= 1
        if tasks_preview_invalid:
            assert isinstance(tasks_preview_invalid[0], CrawlerTasks)

    def test_find_auto_tasks(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        sample_tasks_data: List[Dict[str, Any]],
    ):
        active_auto_count = sum(
            1 for t in sample_tasks_data if t["is_auto"] and t["is_active"]
        )
        inactive_auto_count = sum(
            1 for t in sample_tasks_data if t["is_auto"] and not t["is_active"]
        )

        auto_tasks_active = crawler_tasks_repo.find_auto_tasks()
        assert len(auto_tasks_active) == active_auto_count
        assert all(
            isinstance(task, CrawlerTasks) and task.is_auto and task.is_active
            for task in auto_tasks_active
        )

        auto_tasks_inactive = crawler_tasks_repo.find_auto_tasks(is_active=False)
        assert len(auto_tasks_inactive) == inactive_auto_count
        assert all(
            isinstance(task, CrawlerTasks) and task.is_auto and not task.is_active
            for task in auto_tasks_inactive
        )

        auto_tasks_limit = crawler_tasks_repo.find_auto_tasks(limit=1)
        assert len(auto_tasks_limit) <= 1
        assert len(auto_tasks_limit) == min(active_auto_count, 1)

        preview_fields = ["id", "is_auto", "is_active"]
        auto_tasks_preview = crawler_tasks_repo.find_auto_tasks(
            is_preview=True, preview_fields=preview_fields, limit=1
        )
        assert len(auto_tasks_preview) <= 1
        if auto_tasks_preview:
            assert isinstance(auto_tasks_preview[0], dict)
            assert all(field in auto_tasks_preview[0] for field in preview_fields)
            assert auto_tasks_preview[0]["is_auto"] is True
            assert auto_tasks_preview[0]["is_active"] is True

    def test_find_scheduled_tasks(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        sample_tasks_data: List[Dict[str, Any]],
    ):
        active_scheduled_count = sum(
            1 for t in sample_tasks_data if t["is_scheduled"] and t["is_active"]
        )
        inactive_scheduled_count = sum(
            1 for t in sample_tasks_data if t["is_scheduled"] and not t["is_active"]
        )

        scheduled_tasks_active = crawler_tasks_repo.find_scheduled_tasks()
        assert len(scheduled_tasks_active) == active_scheduled_count
        assert all(
            isinstance(task, CrawlerTasks) and task.is_scheduled and task.is_active
            for task in scheduled_tasks_active
        )

        scheduled_tasks_inactive = crawler_tasks_repo.find_scheduled_tasks(
            is_active=False
        )
        assert len(scheduled_tasks_inactive) == inactive_scheduled_count
        assert all(
            isinstance(task, CrawlerTasks) and task.is_scheduled and not task.is_active
            for task in scheduled_tasks_inactive
        )

        scheduled_tasks_limit = crawler_tasks_repo.find_scheduled_tasks(limit=2)
        assert len(scheduled_tasks_limit) <= 2
        assert len(scheduled_tasks_limit) == min(active_scheduled_count, 2)

        preview_fields = ["id", "task_name", "is_scheduled"]
        scheduled_tasks_preview = crawler_tasks_repo.find_scheduled_tasks(
            is_preview=True, preview_fields=preview_fields, limit=1
        )
        assert len(scheduled_tasks_preview) <= 1
        if scheduled_tasks_preview:
            assert isinstance(scheduled_tasks_preview[0], dict)
            assert all(field in scheduled_tasks_preview[0] for field in preview_fields)
            assert scheduled_tasks_preview[0]["is_scheduled"] is True

    def test_find_ai_only_tasks(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        sample_tasks_data: List[Dict[str, Any]],
    ):
        active_ai_count = sum(
            1
            for t in sample_tasks_data
            if isinstance(t.get("task_args"), dict)
            and t["task_args"].get("ai_only") is True
            and t["is_active"]
        )
        inactive_ai_count = sum(
            1
            for t in sample_tasks_data
            if isinstance(t.get("task_args"), dict)
            and t["task_args"].get("ai_only") is True
            and not t["is_active"]
        )

        ai_tasks_active = crawler_tasks_repo.find_ai_only_tasks()
        assert len(ai_tasks_active) == active_ai_count
        assert all(
            isinstance(task, CrawlerTasks)
            and isinstance(task.task_args, dict)
            and task.task_args.get("ai_only") is True
            and task.is_active
            for task in ai_tasks_active
        )

        ai_tasks_inactive = crawler_tasks_repo.find_ai_only_tasks(is_active=False)
        assert len(ai_tasks_inactive) == inactive_ai_count
        assert all(
            isinstance(task, CrawlerTasks)
            and isinstance(task.task_args, dict)
            and task.task_args.get("ai_only") is True
            and not task.is_active
            for task in ai_tasks_inactive
        )

        ai_tasks_limit = crawler_tasks_repo.find_ai_only_tasks(limit=1)
        assert len(ai_tasks_limit) <= 1
        assert len(ai_tasks_limit) == min(active_ai_count, 1)

        preview_fields = ["id", "task_args"]
        ai_tasks_preview = crawler_tasks_repo.find_ai_only_tasks(
            is_preview=True, preview_fields=preview_fields, limit=1
        )
        assert len(ai_tasks_preview) <= 1
        if ai_tasks_preview:
            assert isinstance(ai_tasks_preview[0], dict)
            assert all(field in ai_tasks_preview[0] for field in preview_fields)
            assert isinstance(ai_tasks_preview[0]["task_args"], (dict, str))
            task_args_dict = ai_tasks_preview[0]["task_args"]
            if isinstance(task_args_dict, str):
                try:
                    task_args_dict = json.loads(task_args_dict)
                except json.JSONDecodeError:
                    pytest.fail("task_args in preview is not valid JSON")

            assert isinstance(task_args_dict, dict)
            assert task_args_dict.get("ai_only") is True

    def test_find_tasks_by_crawler_and_auto(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        sample_tasks_data: List[Dict[str, Any]],
        sample_crawler_data: Dict[str, Any],
    ):
        crawler_id = sample_crawler_data["id"]
        result_dict = crawler_tasks_repo.advanced_search(
            crawler_id=crawler_id, is_auto=True, is_active=True
        )
        auto_tasks_active = result_dict.get("tasks", [])

        expected_count = sum(
            1
            for t in sample_tasks_data
            if t["crawler_id"] == crawler_id and t["is_auto"] and t["is_active"]
        )
        assert len(auto_tasks_active) == expected_count
        assert all(
            isinstance(task, CrawlerTasks)
            and task.crawler_id == crawler_id
            and task.is_auto
            and task.is_active
            for task in auto_tasks_active
        )

    def test_toggle_auto_status(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        sample_tasks_data: List[Dict[str, Any]],
        initialized_db_manager,
    ):
        task_data = sample_tasks_data[0]
        task_id = task_data["id"]
        original_status = task_data["is_auto"]

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            result = repo_in_session.toggle_auto_status(task_id)
            assert result is not None
            assert result.id == task_id
            assert result.is_auto != original_status
            session.commit()

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            updated_task = repo_in_session.get_by_id(task_id)
            assert updated_task is not None
            assert updated_task.is_auto != original_status
            assert updated_task.updated_at is not None
            original_updated_at = task_data.get("updated_at")
            if original_updated_at:
                if isinstance(original_updated_at, str):
                    original_updated_at = datetime.fromisoformat(
                        original_updated_at.replace("Z", "+00:00")
                    )
                assert updated_task.updated_at > original_updated_at

    def test_toggle_scheduled_status(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        sample_tasks_data: List[Dict[str, Any]],
        initialized_db_manager,
    ):
        task_data = sample_tasks_data[0]
        task_id = task_data["id"]
        original_status = task_data["is_scheduled"]

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            result = repo_in_session.toggle_scheduled_status(task_id)
            assert result is not None
            assert result.id == task_id
            assert result.is_scheduled != original_status
            session.commit()

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            updated_task = repo_in_session.get_by_id(task_id)
            assert updated_task is not None
            assert updated_task.is_scheduled != original_status
            assert updated_task.updated_at is not None

    def test_update_ai_only_status(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        sample_tasks_data: List[Dict[str, Any]],
        initialized_db_manager,
    ):
        task_to_update_data = next(
            (
                t
                for t in sample_tasks_data
                if isinstance(t.get("task_args"), dict)
                and not t["task_args"].get("ai_only")
                and t["is_active"]
            ),
            None,
        )
        assert (
            task_to_update_data is not None
        ), "找不到適合測試的任務 (ai_only=False, is_active=True)"

        task_id = task_to_update_data["id"]
        original_args = task_to_update_data.get("task_args", {}).copy()
        logger.info(f"\n--- test_update_ai_only_status ---")
        logger.info(f"Task ID: {task_id}, Original task_args: {original_args}")

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            task_in_session = repo_in_session.get_by_id(task_id)
            assert task_in_session is not None

            new_task_args = (task_in_session.task_args or {}).copy()
            new_task_args["ai_only"] = True
            task_in_session.task_args = new_task_args
            logger.info(
                f"New task_args payload for session object: {task_in_session.task_args}"
            )
            flag_modified(task_in_session, "task_args")
            session.commit()
            logger.info(f"Committed changes for task ID: {task_id}")

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            reloaded_task = repo_in_session.get_by_id(task_id)
            assert reloaded_task is not None
            logger.info(f"Reloaded task_args from DB: {reloaded_task.task_args}")
            assert isinstance(reloaded_task.task_args, dict)
            assert reloaded_task.task_args.get("ai_only") is True
            for key, value in original_args.items():
                if key != "ai_only":
                    assert reloaded_task.task_args.get(key) == value
        logger.info(f"--- Test finished successfully ---")

    def test_update_notes(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        sample_tasks_data: List[Dict[str, Any]],
        initialized_db_manager,
    ):
        task_data = sample_tasks_data[0]
        task_id = task_data["id"]
        new_notes = "更新的備註"

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            result = repo_in_session.update_notes(task_id, new_notes)
            assert result is not None
            assert result.id == task_id
            assert result.notes == new_notes
            session.commit()

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            updated_task = repo_in_session.get_by_id(task_id)
            assert updated_task is not None
            assert updated_task.notes == new_notes
            assert updated_task.updated_at is not None

    def test_find_tasks_with_notes(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        sample_tasks_data: List[Dict[str, Any]],
    ):
        expected_count = sum(
            1
            for t in sample_tasks_data
            if t.get("notes") is not None and t["notes"] != ""
        )
        tasks = crawler_tasks_repo.find_tasks_with_notes()
        assert len(tasks) == expected_count
        assert all(
            isinstance(task, CrawlerTasks)
            and task.notes is not None
            and task.notes != ""
            for task in tasks
        )

        tasks_limit = crawler_tasks_repo.find_tasks_with_notes(limit=1)
        assert len(tasks_limit) <= 1
        assert len(tasks_limit) == min(expected_count, 1)

        preview_fields = ["id", "notes"]
        tasks_preview = crawler_tasks_repo.find_tasks_with_notes(
            is_preview=True, preview_fields=preview_fields, limit=1
        )
        assert len(tasks_preview) <= 1
        if tasks_preview:
            assert isinstance(tasks_preview[0], dict)
            assert all(field in tasks_preview[0] for field in preview_fields)

    def test_find_tasks_by_multiple_crawlers(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        sample_tasks_data: List[Dict[str, Any]],
        sample_crawler_data: Dict[str, Any],
    ):
        """測試根據多個爬蟲ID查詢任務"""
        crawler_id = sample_crawler_data["id"]
        expected_count = sum(
            1 for t in sample_tasks_data if t["crawler_id"] == crawler_id
        )

        tasks = crawler_tasks_repo.find_tasks_by_multiple_crawlers([crawler_id])
        assert len(tasks) == expected_count
        assert all(
            isinstance(task, CrawlerTasks) and task.crawler_id == crawler_id
            for task in tasks
        )

        tasks_nonexistent = crawler_tasks_repo.find_tasks_by_multiple_crawlers([99999])
        assert len(tasks_nonexistent) == 0

        tasks_mix = crawler_tasks_repo.find_tasks_by_multiple_crawlers(
            [crawler_id, 99999]
        )
        assert len(tasks_mix) == expected_count

    def test_get_tasks_count_by_crawler(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        sample_tasks_data: List[Dict[str, Any]],
        sample_crawler_data: Dict[str, Any],
    ):
        """測試獲取特定爬蟲的任務數量"""
        crawler_id = sample_crawler_data["id"]
        expected_count = sum(
            1 for t in sample_tasks_data if t["crawler_id"] == crawler_id
        )

        count = crawler_tasks_repo.count_tasks_by_crawler(crawler_id)
        assert count == expected_count

        count_nonexistent = crawler_tasks_repo.count_tasks_by_crawler(99999)
        assert count_nonexistent == 0

    def test_find_tasks_by_cron_expression(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        initialized_db_manager,
        sample_crawler_data: Dict[str, Any],
    ):
        """測試根據 cron 表達式查詢任務"""
        crawler_id = sample_crawler_data["id"]
        tasks_data = [
            {
                "task_name": "每小時執行任務",
                "crawler_id": crawler_id,
                "is_auto": True,
                "cron_expression": "0 * * * *",
                "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False},
                "scrape_phase": ScrapePhase.INIT,
                "max_retries": 3,
                "retry_count": 0,
            },
            {
                "task_name": "每天執行任務",
                "crawler_id": crawler_id,
                "is_auto": True,
                "cron_expression": "0 0 * * *",
                "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False},
                "scrape_phase": ScrapePhase.INIT,
                "max_retries": 3,
                "retry_count": 0,
            },
            {
                "task_name": "每週執行任務",
                "crawler_id": crawler_id,
                "is_auto": True,
                "cron_expression": "0 0 * * 1",
                "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False},
                "scrape_phase": ScrapePhase.INIT,
                "max_retries": 3,
                "retry_count": 0,
            },
        ]

        with initialized_db_manager.session_scope() as session:
            tasks_orm = [CrawlerTasks(**data) for data in tasks_data]
            session.add_all(tasks_orm)
            session.commit()

        hourly_tasks = crawler_tasks_repo.find_tasks_by_cron_expression("0 * * * *")
        assert len(hourly_tasks) == 1
        assert all(
            isinstance(t, CrawlerTasks)
            and t.cron_expression == "0 * * * *"
            and t.is_auto
            for t in hourly_tasks
        )
        assert hourly_tasks[0].task_name == "每小時執行任務"  # type: ignore[attr-defined]

        with pytest.raises(ValidationError) as excinfo:
            crawler_tasks_repo.find_tasks_by_cron_expression("invalid cron")
        assert "無效的 cron 表達式" in str(excinfo.value)

    def test_find_pending_tasks(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        initialized_db_manager,
        sample_crawler_data: Dict[str, Any],
    ):
        """測試查詢待執行的任務"""
        crawler_id = sample_crawler_data["id"]
        now = datetime.now(timezone.utc)
        tasks_data = [
            {  # 1. 上次執行超過1小時（應該被找到）
                "task_name": "超過1小時任務",
                "crawler_id": crawler_id,
                "is_auto": True,
                "is_active": True,
                "cron_expression": "0 * * * *",
                "last_run_at": now - timedelta(hours=2),
                "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False},
                "scrape_phase": ScrapePhase.INIT,
                "max_retries": 3,
                "retry_count": 0,
            },
            {  # 2. 上次執行於本小時初，cron 為每小時執行一次，因此本次不應執行 (不應該被找到)
                "task_name": "本小時初已執行任務", # Renamed for clarity
                "crawler_id": crawler_id,
                "is_auto": True,
                "is_active": True,
                "cron_expression": "0 * * * *",
                "last_run_at": now.replace(minute=0, second=0, microsecond=0),
                "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False},
                "scrape_phase": ScrapePhase.INIT,
                "max_retries": 3,
                "retry_count": 0,
            },
            {  # 3. 從未執行過（應該被找到）
                "task_name": "從未執行任務",
                "crawler_id": crawler_id,
                "is_auto": True,
                "is_active": True,
                "cron_expression": "0 * * * *",
                "last_run_at": None,
                "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False},
                "scrape_phase": ScrapePhase.INIT,
                "max_retries": 3,
                "retry_count": 0,
            },
            {  # 4. is_auto = False (不應該被找到)
                "task_name": "手動任務",
                "crawler_id": crawler_id,
                "is_auto": False,
                "is_active": True,
                "cron_expression": "0 * * * *",
                "last_run_at": None,
                "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False},
                "scrape_phase": ScrapePhase.INIT,
                "max_retries": 3,
                "retry_count": 0,
            },
            {  # 5. is_active = False (不應該被找到)
                "task_name": "非活動任務",
                "crawler_id": crawler_id,
                "is_auto": True,
                "is_active": False,
                "cron_expression": "0 * * * *",
                "last_run_at": None,
                "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False},
                "scrape_phase": ScrapePhase.INIT,
                "max_retries": 3,
                "retry_count": 0,
            },
        ]

        created_task_ids = {}
        with initialized_db_manager.session_scope() as session:
            session.query(CrawlerTasks).filter(
                CrawlerTasks.crawler_id == crawler_id
            ).delete()
            session.commit()
            tasks_orm = [CrawlerTasks(**data) for data in tasks_data]
            session.add_all(tasks_orm)
            session.commit()
            for task in tasks_orm:
                session.refresh(task)
                created_task_ids[task.task_name] = task.id

            due_tasks = crawler_tasks_repo.find_due_tasks("0 * * * *")
            found_ids = {task.id for task in due_tasks}  # type: ignore[attr-defined]
            logger.info(f"Found due task IDs for cron '0 * * * *': {found_ids}")
            logger.info(f"Created task IDs: {created_task_ids}")

            assert created_task_ids["超過1小時任務"] in found_ids
            assert created_task_ids["從未執行任務"] in found_ids
            assert created_task_ids["本小時初已執行任務"] not in found_ids
            assert created_task_ids["手動任務"] not in found_ids
            assert created_task_ids["非活動任務"] not in found_ids
            assert len(due_tasks) == 2
            

    def test_get_failed_tasks(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        initialized_db_manager,
        sample_crawler_data: Dict[str, Any],
    ):
        """測試獲取失敗的任務"""
        crawler_id = sample_crawler_data["id"]
        base_time = datetime.now(timezone.utc)
        tasks_data = [
            {
                "task_name": "失敗任務1",
                "crawler_id": crawler_id,
                "last_run_success": False,
                "last_run_at": base_time - timedelta(days=2),
                "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False},
                "scrape_phase": ScrapePhase.INIT,
                "max_retries": 3,
                "retry_count": 0,
            },
            {
                "task_name": "失敗任務2",
                "crawler_id": crawler_id,
                "last_run_success": False,
                "last_run_at": base_time - timedelta(hours=12),
                "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False},
                "scrape_phase": ScrapePhase.INIT,
                "max_retries": 3,
                "retry_count": 0,
            },
            {
                "task_name": "成功任務",
                "crawler_id": crawler_id,
                "last_run_success": True,
                "last_run_at": base_time - timedelta(hours=1),
                "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False},
                "scrape_phase": ScrapePhase.INIT,
                "max_retries": 3,
                "retry_count": 0,
            },
            {
                "task_name": "失敗任務3",
                "crawler_id": crawler_id,
                "last_run_success": False,
                "last_run_at": None,
                "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False},
                "scrape_phase": ScrapePhase.INIT,
                "max_retries": 3,
                "retry_count": 0,
            },
        ]

        with initialized_db_manager.session_scope() as session:
            session.query(CrawlerTasks).filter(
                CrawlerTasks.crawler_id == crawler_id
            ).delete()
            session.commit()
            tasks_orm = [CrawlerTasks(**data) for data in tasks_data]
            session.add_all(tasks_orm)
            session.commit()

        failed_tasks = crawler_tasks_repo.find_failed_tasks(days=1)
        assert len(failed_tasks) == 1
        assert all(
            isinstance(t, CrawlerTasks) and not t.last_run_success for t in failed_tasks
        )
        assert failed_tasks[0].task_name == "失敗任務2"  # type: ignore[attr-defined]
        one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        assert all(
            task.last_run_at >= one_day_ago  # type: ignore[attr-defined]
            for task in failed_tasks
            if task.last_run_at  # type: ignore[attr-defined]
        )

    def test_create_task_with_validation(
        self,
        # crawler_tasks_repo: CrawlerTasksRepository, # 不再直接使用 fixture
        sample_crawler_data: Dict[str, Any],
        initialized_db_manager,
    ):
        """測試創建任務時的驗證規則"""
        crawler_id = sample_crawler_data["id"]
        with initialized_db_manager.session_scope() as session:
            # 在 session 內創建 repo 實例
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)

            with pytest.raises(ValidationError) as excinfo:
                # 使用 session 內的 repo 進行驗證性創建
                repo_in_session.create(
                    {
                        "task_name": "測試任務",
                        "is_auto": True,
                        "cron_expression": "0 * * * *",
                        "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False},
                        "scrape_phase": ScrapePhase.INIT,
                        "max_retries": 3,
                        "retry_count": 0,
                        # 缺少 crawler_id
                    }
                )
            assert "crawler_id" in str(excinfo.value) or "必填欄位缺失" in str(
                excinfo.value
            )

            task_data = {
                "task_name": "測試任務成功",
                "crawler_id": crawler_id,
                "task_args": {
                    **TASK_ARGS_DEFAULT,
                    "ai_only": False,
                    "scrape_mode": ScrapeMode.FULL_SCRAPE.value,
                },
                "is_auto": True,
                "cron_expression": "0 * * * *",
                "scrape_phase": ScrapePhase.INIT,
            }
            # 使用 session 內的 repo 創建任務
            task = repo_in_session.create(task_data)
            assert task is not None  # 先確認 create 有返回物件
            session.flush()  # 寫入數據庫並獲取 ID，但不結束事務

            # 現在可以進行斷言
            assert task.id is not None
            assert task.crawler_id == crawler_id
            assert task.is_auto is True
            assert task.cron_expression == "0 * * * *"
            assert isinstance(task.task_args, dict)
            assert task.task_args.get("ai_only") is False
            assert task.task_args.get("scrape_mode") == ScrapeMode.FULL_SCRAPE.value

            task_id = task.id  # 在確認 id 非 None 後再賦值
            # 此 with 區塊結束時，session_scope 會自動 commit

        # 使用新的 session 驗證持久化
        with initialized_db_manager.session_scope() as session:
            repo_in_session_verify = CrawlerTasksRepository(session, CrawlerTasks)
            persisted_task = repo_in_session_verify.get_by_id(task_id)
            assert persisted_task is not None
            assert persisted_task.task_name == "測試任務成功"

    def test_update_task_with_validation(
        self,
        # crawler_tasks_repo: CrawlerTasksRepository, # 不再直接使用 fixture
        initialized_db_manager,
        sample_crawler_data: Dict[str, Any],
    ):
        """測試更新任務時的驗證規則"""
        crawler_id = sample_crawler_data["id"]
        task_id = None
        # 創建初始任務
        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            task = repo_in_session.create(
                {
                    "task_name": "待更新任務",
                    "crawler_id": crawler_id,
                    "is_auto": False,
                    "scrape_phase": ScrapePhase.INIT,
                    "task_args": {
                        **TASK_ARGS_DEFAULT,
                        "ai_only": False,
                        "scrape_mode": ScrapeMode.FULL_SCRAPE.value,
                    },
                }
            )
            assert task is not None
            session.flush()  # 獲取 ID
            task_id = task.id
            # 此 scope 結束時 commit 創建操作

        assert task_id is not None

        # 嘗試更新 crawler_id (預期失敗)
        with initialized_db_manager.session_scope() as session:
            repo_for_invalid_update = CrawlerTasksRepository(session, CrawlerTasks)
            with pytest.raises(ValidationError) as excinfo:
                repo_for_invalid_update.update(
                    task_id,
                    {
                        "crawler_id": 999,
                        "cron_expression": "0 * * * *",
                    },
                )
            assert "不允許更新 crawler_id 欄位" in str(excinfo.value)
            # 此 scope 結束時 rollback (因為拋出異常)

        # 執行有效更新
        update_data = {
            "is_auto": True,
            "cron_expression": "0 * * * *",
            "task_args": {
                **TASK_ARGS_DEFAULT,
                "ai_only": True,
                "scrape_mode": ScrapeMode.LINKS_ONLY.value,
            },
            "notes": "已更新",
        }
        with initialized_db_manager.session_scope() as update_session:
            repo_for_update = CrawlerTasksRepository(update_session, CrawlerTasks)
            updated_task = repo_for_update.update(task_id, update_data)

            # 在同一個 session 中驗證 update 返回值
            assert updated_task is not None
            assert updated_task.id == task_id
            assert updated_task.is_auto is True
            assert updated_task.cron_expression == "0 * * * *"
            assert isinstance(updated_task.task_args, dict)
            assert updated_task.task_args.get("ai_only") is True
            assert (
                updated_task.task_args.get("scrape_mode") == ScrapeMode.LINKS_ONLY.value
            )
            assert updated_task.notes == "已更新"
            # 此 scope 結束時 commit 更新操作

        # 使用新的 session 驗證持久化
        with initialized_db_manager.session_scope() as verify_session:
            repo_for_verify = CrawlerTasksRepository(verify_session, CrawlerTasks)
            persisted_task = repo_for_verify.get_by_id(task_id)
            assert persisted_task is not None
            assert persisted_task.is_auto is True  # 現在這個應該通過了
            assert persisted_task.cron_expression == "0 * * * *"
            assert persisted_task.task_args.get("ai_only") is True
            assert persisted_task.notes == "已更新"

    def test_default_values(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        sample_crawler_data: Dict[str, Any],
        initialized_db_manager,
    ):
        """測試新建任務時的預設值"""
        crawler_id = sample_crawler_data["id"]
        task_data = {
            "task_name": "預設值測試",
            "scrape_phase": ScrapePhase.INIT.value,
            "crawler_id": crawler_id,
            "is_auto": False,
            "task_args": {
                **TASK_ARGS_DEFAULT,
                "scrape_mode": ScrapeMode.FULL_SCRAPE.value,
            },
        }
        task_id = None
        created_task_data = None
        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            task = repo_in_session.create(task_data)
            assert task is not None
            session.flush()
            session.commit()
            task_id = task.id
            created_task_data = task

            assert task_id is not None
            assert created_task_data is not None

            assert created_task_data.is_auto is False
            assert created_task_data.is_scheduled is False
            assert created_task_data.is_active is True
            task_args = created_task_data.task_args
            assert isinstance(task_args, dict)
            assert task_args.get("ai_only") is False
            assert task_args.get("max_pages") == 10
            assert task_args.get("save_to_csv") is False
            assert task_args.get("scrape_mode") == ScrapeMode.FULL_SCRAPE.value
            assert created_task_data.scrape_phase == ScrapePhase.INIT
            assert created_task_data.task_status == TaskStatus.INIT
            assert created_task_data.retry_count == 0

    def test_find_tasks_by_id(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        sample_tasks_data: List[Dict[str, Any]],
    ):
        """測試根據任務ID查詢任務 (get_task_by_id)"""
        active_task_data = next((t for t in sample_tasks_data if t["is_active"]), None)
        inactive_task_data = next(
            (t for t in sample_tasks_data if not t["is_active"]), None
        )

        assert active_task_data is not None
        assert inactive_task_data is not None
        active_task_id = active_task_data["id"]
        inactive_task_id = inactive_task_data["id"]

        found_task = crawler_tasks_repo.get_task_by_id(active_task_id)
        assert found_task is not None
        assert isinstance(found_task, CrawlerTasks)
        assert found_task.id == active_task_id
        assert found_task.is_active is True

        found_task = crawler_tasks_repo.get_task_by_id(active_task_id, is_active=True)
        assert found_task is not None
        assert found_task.id == active_task_id
        assert found_task.is_active is True

        found_task = crawler_tasks_repo.get_task_by_id(
            inactive_task_id, is_active=False
        )
        assert found_task is not None
        assert found_task.id == inactive_task_id
        assert found_task.is_active is False

        found_task = crawler_tasks_repo.get_task_by_id(inactive_task_id, is_active=True)
        assert found_task is None

        found_task = crawler_tasks_repo.get_task_by_id(active_task_id, is_active=None)
        assert found_task is not None
        assert found_task.id == active_task_id

        found_task = crawler_tasks_repo.get_task_by_id(inactive_task_id, is_active=None)
        assert found_task is not None
        assert found_task.id == inactive_task_id
        assert found_task.is_active is False

        found_task = crawler_tasks_repo.get_task_by_id(99999)
        assert found_task is None

    def test_toggle_ai_only_status(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        sample_tasks_data: List[Dict[str, Any]],
        initialized_db_manager,
        sample_crawler_data: Dict[str, Any],
    ):
        """測試直接切換 AI 專用狀態"""
        task_false_to_true_data = next(
            (
                t
                for t in sample_tasks_data
                if isinstance(t.get("task_args"), dict)
                and t["task_args"].get("ai_only") is False
                and t["is_active"]
            ),
            None,
        )
        task_true_to_false_data = next(
            (
                t
                for t in sample_tasks_data
                if isinstance(t.get("task_args"), dict)
                and t["task_args"].get("ai_only") is True
                and t["is_active"]
            ),
            None,
        )

        assert task_false_to_true_data is not None
        assert task_true_to_false_data is not None
        task_id_1 = task_false_to_true_data["id"]
        task_id_2 = task_true_to_false_data["id"]

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            result1 = repo_in_session.toggle_ai_only_status(task_id_1)
            assert result1 is not None
            assert result1.id == task_id_1
            assert result1.task_args.get("ai_only") is True
            session.commit()

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            updated_task_1 = repo_in_session.get_by_id(task_id_1)
            assert updated_task_1 is not None
            assert updated_task_1.task_args.get("ai_only") is True
            assert updated_task_1.updated_at is not None

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            result2 = repo_in_session.toggle_ai_only_status(task_id_2)
            assert result2 is not None
            assert result2.id == task_id_2
            assert result2.task_args.get("ai_only") is False
            session.commit()

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            updated_task_2 = repo_in_session.get_by_id(task_id_2)
            assert updated_task_2 is not None
            assert updated_task_2.task_args.get("ai_only") is False
            assert updated_task_2.updated_at is not None

        task_id_3 = None
        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            new_task = repo_in_session.create(
                {
                    "task_name": "無task_args測試",
                    "crawler_id": sample_crawler_data["id"],
                    "scrape_phase": ScrapePhase.INIT.value,
                    "task_args": TASK_ARGS_DEFAULT,
                    "is_active": True,
                }
            )
            session.flush()
            session.commit()
            assert new_task is not None
            task_id_3 = new_task.id

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            result3 = repo_in_session.toggle_ai_only_status(task_id_3)
            session.flush()
            assert result3 is not None
            assert result3.id == task_id_3
            assert isinstance(result3.task_args, dict)
            assert result3.task_args.get("ai_only") is True
            session.commit()

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            updated_task_3 = repo_in_session.get_by_id(task_id_3)
            session.flush()
            assert updated_task_3 is not None
            assert updated_task_3.task_args.get("ai_only") is True

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            task_to_modify = repo_in_session.get_by_id(task_id_1)
            assert task_to_modify is not None
            task_to_modify.task_args = {"other_key": "value"}
            flag_modified(task_to_modify, "task_args")
            session.commit()

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            result4 = repo_in_session.toggle_ai_only_status(task_id_1)
            session.flush()
            assert result4 is not None
            assert result4.id == task_id_1
            assert result4.task_args.get("ai_only") is True
            assert result4.task_args.get("other_key") == "value"
            session.commit()

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            updated_task_4 = repo_in_session.get_by_id(task_id_1)
            assert updated_task_4 is not None
            assert updated_task_4.task_args.get("ai_only") is True
            assert updated_task_4.task_args.get("other_key") == "value"

        result_nonexistent = crawler_tasks_repo.toggle_ai_only_status(99999)
        assert result_nonexistent is None

    def test_toggle_active_status(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        sample_tasks_data: List[Dict[str, Any]],
        initialized_db_manager,
    ):
        """測試切換啟用狀態"""
        active_task_data = next((t for t in sample_tasks_data if t["is_active"]), None)
        inactive_task_data = next(
            (t for t in sample_tasks_data if not t["is_active"]), None
        )
        assert active_task_data is not None
        assert inactive_task_data is not None
        active_task_id = active_task_data["id"]
        inactive_task_id = inactive_task_data["id"]

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            result1 = repo_in_session.toggle_active_status(active_task_id)
            assert result1 is not None
            assert result1.id == active_task_id
            assert result1.is_active is False
            session.commit()

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            updated_task_1 = repo_in_session.get_by_id(active_task_id)
            assert updated_task_1 is not None
            assert updated_task_1.is_active is False
            assert updated_task_1.updated_at is not None

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            result2 = repo_in_session.toggle_active_status(inactive_task_id)
            assert result2 is not None
            assert result2.id == inactive_task_id
            assert result2.is_active is True
            session.commit()

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            updated_task_2 = repo_in_session.get_by_id(inactive_task_id)
            assert updated_task_2 is not None
            assert updated_task_2.is_active is True
            assert updated_task_2.updated_at is not None

        result3 = crawler_tasks_repo.toggle_active_status(99999)
        assert result3 is None

    def test_update_last_run(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        sample_tasks_data: List[Dict[str, Any]],
        initialized_db_manager,
    ):
        """測試更新最後執行狀態"""
        task_data = sample_tasks_data[0]
        task_id = task_data["id"]
        original_last_run_at_str = task_data.get("last_run_at")
        original_last_run_at = None
        if original_last_run_at_str and isinstance(original_last_run_at_str, str):
            original_last_run_at = datetime.fromisoformat(
                original_last_run_at_str.replace("Z", "+00:00")
            )
        elif isinstance(original_last_run_at_str, datetime):
            original_last_run_at = original_last_run_at_str

        success_message = "執行成功"
        updated_at_1 = None
        last_run_time_1 = None
        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            result1 = repo_in_session.update_last_run(
                task_id, success=True, message=success_message
            )
            session.flush()
            assert result1 is not None
            assert result1.id == task_id
            assert result1.last_run_success is True
            assert result1.last_run_message == success_message
            assert result1.last_run_at is not None
            assert result1.updated_at is not None
            last_run_time_1 = result1.last_run_at
            updated_at_1 = result1.updated_at
            session.commit()

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            updated_task_1 = repo_in_session.get_by_id(task_id)
            assert updated_task_1 is not None
            assert updated_task_1.last_run_success is True
            assert updated_task_1.last_run_message == success_message
            assert updated_task_1.last_run_at == last_run_time_1
            if original_last_run_at:
                assert isinstance(original_last_run_at, datetime)  # 添加類型斷言
                assert updated_task_1.last_run_at > original_last_run_at  # type: ignore[operator]

        time.sleep(0.01)

        updated_at_2 = None
        last_run_time_2 = None
        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            result2 = repo_in_session.update_last_run(task_id, success=False)
            assert result2 is not None
            assert result2.id == task_id
            assert result2.last_run_success is False
            assert result2.last_run_message == success_message
            assert result2.last_run_at is not None
            assert result2.updated_at is not None
            last_run_time_2 = result2.last_run_at
            updated_at_2 = result2.updated_at
            session.commit()

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            updated_task_2 = repo_in_session.get_by_id(task_id)
            assert updated_task_2 is not None
            assert updated_task_2.last_run_success is False
            assert updated_task_2.last_run_message == success_message
            assert updated_task_2.last_run_at == last_run_time_2
            assert updated_task_2.updated_at == updated_at_2
            assert last_run_time_2 > last_run_time_1
            assert updated_at_2 > updated_at_1

        time.sleep(0.01)

        fail_message = "執行失敗"
        updated_at_3 = None
        last_run_time_3 = None
        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            result3 = repo_in_session.update_last_run(
                task_id, success=False, message=fail_message
            )
            session.flush()
            assert result3 is not None
            assert result3.last_run_success is False
            assert result3.last_run_message == fail_message
            assert result3.last_run_at is not None
            assert result3.updated_at is not None
            last_run_time_3 = result3.last_run_at
            updated_at_3 = result3.updated_at
            session.commit()

        with initialized_db_manager.session_scope() as session:
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)
            updated_task_3 = repo_in_session.get_by_id(task_id)
            assert updated_task_3 is not None
            assert updated_task_3.last_run_success is False
            assert updated_task_3.last_run_message == fail_message
            assert updated_task_3.last_run_at == last_run_time_3
            assert updated_task_3.updated_at == updated_at_3
            assert last_run_time_3 >= last_run_time_2
            assert updated_at_3 >= updated_at_2

        result4 = crawler_tasks_repo.update_last_run(99999, success=True)
        assert result4 is None

    def test_advanced_search(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        sample_tasks_data: List[Dict[str, Any]],
        sample_crawler_data: Dict[str, Any]
    ):
        """測試 advanced_search 方法"""
        total_tasks = len(sample_tasks_data)
        crawler_id = sample_crawler_data["id"]

        def get_ids(results):
            return {t.id for t in results}

        def get_fixture_ids(data_list):
            return {t["id"] for t in data_list}

        all_fixture_task_ids = get_fixture_ids(sample_tasks_data)

        # 1. 無過濾器
        result_dict = crawler_tasks_repo.advanced_search()
        assert result_dict is not None
        assert "total_count" in result_dict and "tasks" in result_dict
        assert result_dict["total_count"] == total_tasks
        assert len(result_dict["tasks"]) == total_tasks
        assert get_ids(result_dict["tasks"]) == all_fixture_task_ids
        expected_ids_desc = sorted([t["id"] for t in sample_tasks_data], reverse=True)
        actual_ids_desc = [t.id for t in result_dict["tasks"]]
        assert actual_ids_desc == expected_ids_desc

        # 2. 簡單欄位過濾
        result_dict = crawler_tasks_repo.advanced_search(task_name="自動AI")
        expected_ids = {
            t["id"] for t in sample_tasks_data if "自動AI" in t["task_name"]
        }
        assert result_dict["total_count"] == len(expected_ids)
        assert get_ids(result_dict["tasks"]) == expected_ids

        result_dict = crawler_tasks_repo.advanced_search(crawler_id=crawler_id)
        assert result_dict["total_count"] == total_tasks
        assert get_ids(result_dict["tasks"]) == all_fixture_task_ids

        result_dict = crawler_tasks_repo.advanced_search(crawler_id=999)
        assert result_dict["total_count"] == 0
        assert len(result_dict["tasks"]) == 0

        result_dict = crawler_tasks_repo.advanced_search(is_auto=True)
        expected_ids = {t["id"] for t in sample_tasks_data if t["is_auto"]}
        assert result_dict["total_count"] == len(expected_ids)
        assert get_ids(result_dict["tasks"]) == expected_ids

        result_dict = crawler_tasks_repo.advanced_search(is_active=False)
        expected_ids = {t["id"] for t in sample_tasks_data if not t["is_active"]}
        assert result_dict["total_count"] == len(expected_ids)
        assert get_ids(result_dict["tasks"]) == expected_ids

        result_dict = crawler_tasks_repo.advanced_search(last_run_success=False)
        expected_ids = {
            t["id"] for t in sample_tasks_data if t["last_run_success"] is False
        }
        assert result_dict["total_count"] == len(expected_ids)
        assert get_ids(result_dict["tasks"]) == expected_ids

        result_dict = crawler_tasks_repo.advanced_search(cron_expression="0 * * * *")
        expected_ids = {
            t["id"] for t in sample_tasks_data if t["cron_expression"] == "0 * * * *"
        }
        assert result_dict["total_count"] == len(expected_ids)
        assert get_ids(result_dict["tasks"]) == expected_ids

        # 3. 範圍/比較過濾
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        result_dict = crawler_tasks_repo.advanced_search(date_range=(today_start, now))
        expected_ids = set()
        for t in sample_tasks_data:
            last_run_at_str = t.get("last_run_at")
            if last_run_at_str:
                last_run_at = (
                    datetime.fromisoformat(last_run_at_str.replace("Z", "+00:00"))
                    if isinstance(last_run_at_str, str)
                    else last_run_at_str
                )
                if last_run_at and today_start <= last_run_at <= now:
                    expected_ids.add(t["id"])
        assert result_dict["total_count"] == len(expected_ids)
        assert get_ids(result_dict["tasks"]) == expected_ids

        result_dict = crawler_tasks_repo.advanced_search(retry_count=1)
        expected_ids = {t["id"] for t in sample_tasks_data if t.get("retry_count") == 1}
        assert result_dict["total_count"] == len(expected_ids)
        assert get_ids(result_dict["tasks"]) == expected_ids

        result_dict = crawler_tasks_repo.advanced_search(
            retry_count={"min": 1, "max": 3}
        )
        expected_ids = {
            t["id"] for t in sample_tasks_data if 1 <= t.get("retry_count", 0) <= 3
        }
        assert result_dict["total_count"] == len(expected_ids)
        assert get_ids(result_dict["tasks"]) == expected_ids

        # 4. Presence 過濾
        result_dict = crawler_tasks_repo.advanced_search(has_notes=True)
        expected_ids = {t["id"] for t in sample_tasks_data if t.get("notes")}
        assert result_dict["total_count"] == len(expected_ids)
        assert get_ids(result_dict["tasks"]) == expected_ids

        result_dict = crawler_tasks_repo.advanced_search(has_notes=False)
        expected_ids = {t["id"] for t in sample_tasks_data if not t.get("notes")}
        assert result_dict["total_count"] == len(expected_ids)
        assert get_ids(result_dict["tasks"]) == expected_ids

        # 5. Enum 過濾
        result_dict = crawler_tasks_repo.advanced_search(
            task_status=TaskStatus.COMPLETED
        )
        expected_ids = {
            t["id"]
            for t in sample_tasks_data
            if t.get("task_status") == TaskStatus.COMPLETED.value
        }
        assert result_dict["total_count"] == len(expected_ids)
        assert get_ids(result_dict["tasks"]) == expected_ids

        result_dict = crawler_tasks_repo.advanced_search(scrape_phase=ScrapePhase.INIT)
        expected_ids = {
            t["id"]
            for t in sample_tasks_data
            if t.get("scrape_phase") == ScrapePhase.INIT.value
        }
        assert result_dict["total_count"] == len(expected_ids)
        assert get_ids(result_dict["tasks"]) == expected_ids

        # 6. JSON (task_args) 過濾
        result_dict = crawler_tasks_repo.advanced_search(ai_only=True)
        expected_ids = {
            t["id"]
            for t in sample_tasks_data
            if isinstance(t.get("task_args"), dict)
            and t["task_args"].get("ai_only") is True
        }
        assert result_dict["total_count"] == len(expected_ids)
        assert get_ids(result_dict["tasks"]) == expected_ids

        result_dict = crawler_tasks_repo.advanced_search(max_pages=10)
        expected_ids = {
            t["id"]
            for t in sample_tasks_data
            if isinstance(t.get("task_args"), dict)
            and t["task_args"].get("max_pages") == 10
        }
        assert result_dict["total_count"] == len(expected_ids)
        assert get_ids(result_dict["tasks"]) == expected_ids

        result_dict = crawler_tasks_repo.advanced_search(save_to_csv=True)
        expected_ids = {
            t["id"]
            for t in sample_tasks_data
            if isinstance(t.get("task_args"), dict)
            and t["task_args"].get("save_to_csv") is True
        }
        assert result_dict["total_count"] == len(expected_ids)
        assert get_ids(result_dict["tasks"]) == expected_ids

        result_dict = crawler_tasks_repo.advanced_search(
            scrape_mode=ScrapeMode.LINKS_ONLY
        )
        expected_ids = {
            t["id"]
            for t in sample_tasks_data
            if isinstance(t.get("task_args"), dict)
            and t["task_args"].get("scrape_mode") == ScrapeMode.LINKS_ONLY.value
        }
        assert result_dict["total_count"] == len(expected_ids)
        assert get_ids(result_dict["tasks"]) == expected_ids

        # 7. 排序
        result_dict = crawler_tasks_repo.advanced_search(
            sort_by="task_name", sort_desc=False
        )
        expected_sorted_names = sorted([t["task_name"] for t in sample_tasks_data])
        actual_sorted_names = [t.task_name for t in result_dict["tasks"]]
        assert actual_sorted_names == expected_sorted_names

        result_dict = crawler_tasks_repo.advanced_search(
            sort_by="last_run_at", sort_desc=True
        )
        assert result_dict["tasks"][0].last_run_at is not None
        tasks_with_date = [t for t in sample_tasks_data if t.get("last_run_at")]
        if tasks_with_date:
            expected_first_task_name = max(
                tasks_with_date,
                key=lambda x: (
                    datetime.fromisoformat(x["last_run_at"].replace("Z", "+00:00"))
                    if isinstance(x["last_run_at"], str)
                    else x["last_run_at"]
                ),
            )["task_name"]
            assert result_dict["tasks"][0].task_name == expected_first_task_name
        if any(t["last_run_at"] is None for t in sample_tasks_data):
            assert result_dict["tasks"][-1].last_run_at is None

        # 8. 分頁
        result_dict = crawler_tasks_repo.advanced_search(
            limit=2, offset=0, sort_by="id", sort_desc=False
        )
        assert len(result_dict["tasks"]) == 2
        assert result_dict["total_count"] == total_tasks
        expected_ids_page1 = sorted([t["id"] for t in sample_tasks_data])[0:2]
        actual_ids_page1 = [t.id for t in result_dict["tasks"]]
        assert actual_ids_page1 == expected_ids_page1

        result_dict = crawler_tasks_repo.advanced_search(
            limit=2, offset=2, sort_by="id", sort_desc=False
        )
        assert len(result_dict["tasks"]) == 2
        assert result_dict["total_count"] == total_tasks
        expected_ids_page2 = sorted([t["id"] for t in sample_tasks_data])[2:4]
        actual_ids_page2 = [t.id for t in result_dict["tasks"]]
        assert actual_ids_page2 == expected_ids_page2

        # 9. 組合測試
        result_dict = crawler_tasks_repo.advanced_search(
            is_active=True,
            ai_only=True,
            sort_by="task_name",
            sort_desc=False,
            limit=1,
        )
        expected_matching_tasks = [
            t
            for t in sample_tasks_data
            if t["is_active"]
            and isinstance(t.get("task_args"), dict)
            and t["task_args"].get("ai_only") is True
        ]
        expected_total_count = len(expected_matching_tasks)
        assert result_dict["total_count"] == expected_total_count
        assert len(result_dict["tasks"]) == min(expected_total_count, 1)
        if expected_matching_tasks:
            expected_first_name = sorted(
                [t["task_name"] for t in expected_matching_tasks]
            )[0]
            assert result_dict["tasks"][0].task_name == expected_first_name

        # 10. 空結果測試
        result_dict = crawler_tasks_repo.advanced_search(task_name="不存在的任務名稱")
        assert result_dict["total_count"] == 0
        assert len(result_dict["tasks"]) == 0


class TestCrawlerTasksConstraints:
    """測試CrawlerTasks的模型約束"""

    def test_boolean_defaults(
        self, initialized_db_manager, sample_crawler_data: Dict[str, Any]
    ):
        """測試布林欄位的默認值"""
        crawler_id = sample_crawler_data["id"]
        task_id = None
        created_task_data = None
        with initialized_db_manager.session_scope() as session:
            task = CrawlerTasks(
                task_name="布林預設測試",
                crawler_id=crawler_id,
                task_args={
                    **TASK_ARGS_DEFAULT,
                    "scrape_mode": ScrapeMode.FULL_SCRAPE.value,
                },
            )
            session.add(task)
            session.flush()
            task_id = task.id
            created_task_data = task.to_dict()
            session.commit()

            assert task_id is not None
            assert created_task_data is not None

            assert created_task_data.get("is_auto") is True
            assert created_task_data.get("is_scheduled") is False
            assert created_task_data.get("is_active") is True
            task_args = created_task_data.get("task_args", {})
            assert task_args.get("ai_only") is False
            assert created_task_data.get("scrape_phase") == ScrapePhase.INIT.value
            assert created_task_data.get("task_status") == TaskStatus.INIT.value


class TestSpecialCases:
    """測試特殊情況"""

    def test_empty_database(
        self, crawler_tasks_repo: CrawlerTasksRepository, initialized_db_manager
    ):
        """測試空數據庫的情況"""
        with initialized_db_manager.session_scope() as session:
            session.query(CrawlerTasks).delete()
            session.query(Crawlers).delete()
            session.commit()

        assert crawler_tasks_repo.find_all() == []
        assert crawler_tasks_repo.find_auto_tasks() == []
        assert crawler_tasks_repo.find_ai_only_tasks() == []
        result = crawler_tasks_repo.advanced_search()
        assert result["total_count"] == 0
        assert len(result["tasks"]) == 0

    def test_invalid_operations(self, crawler_tasks_repo: CrawlerTasksRepository):
        """測試對不存在的任務ID執行操作"""
        non_existent_id = 99999
        assert crawler_tasks_repo.get_by_id(non_existent_id) is None
        assert crawler_tasks_repo.get_task_by_id(non_existent_id) is None
        assert crawler_tasks_repo.toggle_auto_status(non_existent_id) is None
        assert crawler_tasks_repo.toggle_ai_only_status(non_existent_id) is None
        assert crawler_tasks_repo.update_notes(non_existent_id, "test") is None
        assert crawler_tasks_repo.toggle_active_status(non_existent_id) is None
        assert crawler_tasks_repo.toggle_scheduled_status(non_existent_id) is None
        assert crawler_tasks_repo.update_last_run(non_existent_id, True) is None
        assert crawler_tasks_repo.update(non_existent_id, {"task_name": "test"}) is None
        assert crawler_tasks_repo.delete(non_existent_id) == 0

    def test_invalid_cron_operations(self, crawler_tasks_repo: CrawlerTasksRepository):
        """測試無效的 cron 表達式操作"""
        with pytest.raises(ValidationError):
            crawler_tasks_repo.find_tasks_by_cron_expression("invalid cron string")

        with pytest.raises(ValidationError):
            crawler_tasks_repo.find_due_tasks("invalid cron string")

    def test_empty_cron_results(
        self, crawler_tasks_repo: CrawlerTasksRepository, initialized_db_manager
    ):
        """測試在沒有匹配任務時的 cron 相關查詢"""
        with initialized_db_manager.session_scope() as session:
            session.query(CrawlerTasks).delete()
            session.commit()

        assert crawler_tasks_repo.find_tasks_by_cron_expression("0 * * * *") == []
        assert crawler_tasks_repo.find_due_tasks("0 * * * *") == []

    def test_cron_with_no_auto_tasks(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        initialized_db_manager,
        sample_crawler_data: Dict[str, Any],
    ):
        """測試當存在匹配cron但 is_auto=False 的任務時的 cron 查詢"""
        crawler_id = sample_crawler_data["id"]
        cron_expr = "15 * * * *"
        with initialized_db_manager.session_scope() as session:
            session.query(CrawlerTasks).delete()
            task = CrawlerTasks(
                task_name="手動Cron任務",
                crawler_id=crawler_id,
                is_auto=False,
                is_active=True,
                cron_expression=cron_expr,
                task_args=TASK_ARGS_DEFAULT,
            )
            session.add(task)
            session.commit()

            found_tasks = crawler_tasks_repo.find_tasks_by_cron_expression(cron_expr)
            assert len(found_tasks) == 0

            due_tasks = crawler_tasks_repo.find_due_tasks(cron_expr)
            assert len(due_tasks) == 0


class TestCrawlerTasksRepositoryValidation:
    """CrawlerTasksRepository 驗證相關的測試類"""

    def test_validate_data_create(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        sample_crawler_data: Dict[str, Any],
    ):
        """測試 validate_data 方法用於創建操作時的行為"""
        crawler_id = sample_crawler_data["id"]
        valid_data = {
            "task_name": "測試驗證任務",
            "crawler_id": crawler_id,
            "is_auto": True,
            "cron_expression": "0 * * * *",
            "task_args": {
                **TASK_ARGS_DEFAULT,
                "scrape_mode": ScrapeMode.FULL_SCRAPE.value,
            },
            "scrape_phase": ScrapePhase.INIT.value,
            "task_status": TaskStatus.INIT.value,
        }

        validated_result = crawler_tasks_repo.validate_data(
            valid_data, SchemaType.CREATE
        )
        assert validated_result is not None
        assert validated_result.get("task_name") == "測試驗證任務"
        assert validated_result.get("crawler_id") == crawler_id
        assert validated_result.get("cron_expression") == "0 * * * *"
        assert validated_result.get("scrape_phase") == ScrapePhase.INIT.value
        assert validated_result.get("task_status") == TaskStatus.INIT.value

        invalid_data = valid_data.copy()
        del invalid_data["task_name"]
        with pytest.raises(ValidationError) as excinfo:
            crawler_tasks_repo.validate_data(invalid_data, SchemaType.CREATE)
        assert "task_name" in str(excinfo.value) or "必填欄位缺失" in str(excinfo.value)

        invalid_data_enum = valid_data.copy()
        invalid_data_enum["scrape_phase"] = "invalid_phase_value"
        with pytest.raises(ValidationError) as excinfo:
            crawler_tasks_repo.validate_data(invalid_data_enum, SchemaType.CREATE)
        assert "scrape_phase" in str(excinfo.value) and "無效的枚舉值" in str(
            excinfo.value
        )

    def test_validate_data_update(self, crawler_tasks_repo: CrawlerTasksRepository):
        """測試 validate_data 方法用於更新操作時的行為"""
        valid_update = {"notes": "新備註", "is_auto": False}

        validated_result = crawler_tasks_repo.validate_data(
            valid_update, SchemaType.UPDATE
        )
        assert validated_result is not None
        assert validated_result.get("notes") == "新備註"
        assert validated_result.get("is_auto") is False
        assert "crawler_id" not in validated_result

        invalid_update = {"crawler_id": 999}
        with pytest.raises(ValidationError) as excinfo:
            crawler_tasks_repo.validate_data(invalid_update, SchemaType.UPDATE)
        assert "不允許更新 crawler_id 欄位" in str(excinfo.value)

        invalid_enum_update = {"task_status": "invalid_status"}
        with pytest.raises(ValidationError) as excinfo:
            crawler_tasks_repo.validate_data(invalid_enum_update, SchemaType.UPDATE)
        assert "task_status" in str(excinfo.value) and "無效的枚舉值" in str(
            excinfo.value
        )

    def test_exception_handling_create(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        sample_crawler_data: Dict[str, Any],
    ):
        """測試創建時的異常處理"""
        crawler_id = sample_crawler_data["id"]
        test_data = {
            "task_name": "測試異常處理",
            "crawler_id": crawler_id,
            "is_auto": True,
            "cron_expression": "0 * * * *",
            "task_args": TASK_ARGS_DEFAULT,
            "scrape_phase": ScrapePhase.INIT,
            "max_retries": 3,
            "retry_count": 0,
            "scrape_mode": ScrapeMode.FULL_SCRAPE,
        }
        if isinstance(test_data["scrape_phase"], ScrapePhase):
            test_data["scrape_phase"] = test_data["scrape_phase"].value
        if isinstance(test_data.get("scrape_mode"), ScrapeMode):
            test_data["scrape_mode"] = test_data["scrape_mode"].value

        with patch.object(
            crawler_tasks_repo,
            "_create_internal",
            side_effect=DatabaseOperationError("模擬創建DB錯誤"),
        ):
            with pytest.raises(DatabaseOperationError) as excinfo:
                crawler_tasks_repo.create(test_data)
            assert "模擬創建DB錯誤" in str(excinfo.value)
            assert "創建 CrawlerTask 時發生未預期錯誤: 模擬創建DB錯誤" in str(
                excinfo.value
            )

        with patch.object(
            crawler_tasks_repo,
            "validate_data",
            side_effect=ValidationError("模擬驗證錯誤"),
        ):
            with pytest.raises(ValidationError) as excinfo:
                crawler_tasks_repo.create(test_data)
            assert "模擬驗證錯誤" in str(excinfo.value)

        with patch.object(
            crawler_tasks_repo, "validate_data", side_effect=Exception("意外的驗證錯誤")
        ):
            # 將預期的異常類型從 ValidationError 改為 DatabaseOperationError
            with pytest.raises(DatabaseOperationError) as excinfo:
                crawler_tasks_repo.create(test_data)
            assert "創建 CrawlerTask 時發生未預期錯誤" in str(excinfo.value)
            assert isinstance(excinfo.value.__cause__, Exception)
            assert "意外的驗證錯誤" in str(excinfo.value.__cause__)

    def test_exception_handling_update(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        sample_tasks_data: List[Dict[str, Any]],
    ):
        """測試更新時的異常處理"""
        if not sample_tasks_data:
            pytest.skip("需要樣本數據進行更新測試")
        task_id = sample_tasks_data[0]["id"]
        test_data = {"task_name": "更新的任務名稱", "is_auto": False}

        with patch.object(
            crawler_tasks_repo,
            "_update_internal",
            side_effect=DatabaseOperationError("模擬更新DB錯誤"),
        ):
            with pytest.raises(DatabaseOperationError) as excinfo:
                crawler_tasks_repo.update(task_id, test_data)
            assert "模擬更新DB錯誤" in str(excinfo.value)
            assert "更新 CrawlerTask (ID=1) 時發生未預期錯誤: 模擬更新DB錯誤" in str(
                excinfo.value
            )

        with patch.object(
            crawler_tasks_repo,
            "validate_data",
            side_effect=ValidationError("模擬驗證錯誤"),
        ):
            with pytest.raises(ValidationError) as excinfo:
                crawler_tasks_repo.update(task_id, test_data)
            assert "模擬驗證錯誤" in str(excinfo.value)

        with patch.object(
            crawler_tasks_repo, "get_by_id", side_effect=Exception("意外的獲取錯誤")
        ):
            with pytest.raises(DatabaseOperationError) as excinfo:
                crawler_tasks_repo.update(task_id, test_data)
            assert f"更新 CrawlerTask (ID={task_id}) 時發生未預期錯誤" in str(
                excinfo.value
            )
            assert "意外的獲取錯誤" in str(excinfo.value)
            # 可選：檢查原始異常
            assert isinstance(excinfo.value.__cause__, Exception)
            assert "意外的獲取錯誤" in str(excinfo.value.__cause__)

    def test_update_nonexistent_task(self, crawler_tasks_repo: CrawlerTasksRepository):
        """測試更新不存在的任務"""
        result = crawler_tasks_repo.update(99999, {"task_name": "新名稱"})
        assert result is None

    def test_update_empty_data(
        self,
        crawler_tasks_repo: CrawlerTasksRepository,
        sample_tasks_data: List[Dict[str, Any]],
    ):
        """測試使用空數據更新任務"""
        if not sample_tasks_data:
            pytest.skip("需要樣本數據進行更新測試")
        task_id = sample_tasks_data[0]["id"]
        original_name = sample_tasks_data[0]["task_name"]
        original_updated_at_str = sample_tasks_data[0].get("updated_at")
        original_updated_at = None
        if original_updated_at_str:
            original_updated_at = (
                datetime.fromisoformat(original_updated_at_str.replace("Z", "+00:00"))
                if isinstance(original_updated_at_str, str)
                else original_updated_at_str
            )

        result = crawler_tasks_repo.update(task_id, {})

        assert result is not None
        assert isinstance(result, CrawlerTasks)
        assert result.id == task_id
        assert result.task_name == original_name
        assert result.updated_at == original_updated_at


class TestComplexValidationScenarios:
    """測試複雜驗證場景"""

    def test_create_with_string_enum(
        self,
        # crawler_tasks_repo: CrawlerTasksRepository, # 不再直接使用 fixture
        sample_crawler_data: Dict[str, Any],
        initialized_db_manager,
    ):
        """測試使用字符串表示的枚舉創建任務"""
        crawler_id = sample_crawler_data["id"]
        create_data = {
            "task_name": "字符串枚舉測試",
            "crawler_id": crawler_id,
            "is_auto": False,
            "task_args": TASK_ARGS_DEFAULT,
            "scrape_phase": "init",
            "task_status": "running",
        }

        task_id = None
        with initialized_db_manager.session_scope() as session:
            # 在 session scope 內創建 repo
            repo_in_session = CrawlerTasksRepository(session, CrawlerTasks)

            # 使用 session 內的 repo 進行驗證
            validated_data = repo_in_session.validate_data(
                create_data, SchemaType.CREATE
            )
            assert validated_data["scrape_phase"] == ScrapePhase.INIT.value
            assert validated_data["task_status"] == TaskStatus.RUNNING.value

            # 使用 session 內的 repo 進行創建
            task = repo_in_session.create(validated_data)
            assert task is not None
            session.flush()  # 寫入 DB 並獲取 ID

            # 斷言
            assert task.id is not None
            assert task.scrape_phase == ScrapePhase.INIT.value
            assert task.task_status == TaskStatus.RUNNING.value

            task_id = task.id
            # 此 scope 結束時 commit

        # 驗證數據庫持久化
        with initialized_db_manager.session_scope() as session:
            repo_in_session_verify = CrawlerTasksRepository(session, CrawlerTasks)
            persisted_task = repo_in_session_verify.get_by_id(task_id)
            assert persisted_task is not None
            assert persisted_task.scrape_phase == ScrapePhase.INIT
            assert persisted_task.task_status == TaskStatus.RUNNING

        # 測試無效枚舉值
        with initialized_db_manager.session_scope() as session:
            repo_in_session_invalid = CrawlerTasksRepository(session, CrawlerTasks)
            invalid_data = create_data.copy()
            invalid_data["scrape_phase"] = "invalid_phase"
            with pytest.raises(ValidationError) as excinfo:
                repo_in_session_invalid.validate_data(invalid_data, SchemaType.CREATE)
            assert "scrape_phase: 無效的枚舉值" in str(excinfo.value)
