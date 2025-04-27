"""測試排程服務 (SchedulerService) 的單元測試"""

# 標準函式庫
from datetime import datetime, timedelta, timezone
from unittest.mock import ANY, MagicMock, patch

# 第三方函式庫
import pytest
import pytz
from apscheduler.schedulers import SchedulerNotRunningError
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

# 本地應用程式 imports
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.database.database_manager import DatabaseManager
from src.models.base_model import Base
from src.models.crawler_tasks_model import CrawlerTasks, ScrapeMode, ScrapePhase
from src.models.crawlers_model import Crawlers
from src.services.scheduler_service import SchedulerService
from src.services.task_executor_service import TaskExecutorService
from src.utils.enum_utils import TaskStatus
from src.utils.log_utils import LoggerSetup

# flake8: noqa: F811
# pylint: disable=redefined-outer-name

# 設定統一 logger
logger = LoggerSetup.setup_logger(__name__)


# --- Fixtures ---


@pytest.fixture(scope="function")
def initialized_db_manager(db_manager_for_test: DatabaseManager):
    """
    提供一個配置好的 DatabaseManager 實例，確保資料表存在並在每次測試前清理。
    依賴來自 conftest.py 的 db_manager_for_test。
    """
    logger.debug("為排程服務測試函數創建資料表...")
    engine = db_manager_for_test.engine
    Base.metadata.create_all(engine)
    logger.debug("資料表已創建。")

    logger.debug("測試前清理資料表...")
    with db_manager_for_test.session_scope() as session:
        try:
            session.execute(text("DELETE FROM apscheduler_jobs"))
            session.commit()
            logger.debug("apscheduler_jobs 資料表已清理。")
        except OperationalError as e:
            if "no such table" in str(e).lower():
                logger.warning("刪除時未找到 'apscheduler_jobs' 資料表，已跳過。")
                session.rollback()
            else:
                logger.error(
                    f"清理 apscheduler_jobs 時發生 OperationalError: {e}",
                    exc_info=True,
                )
                session.rollback()
                raise
        except Exception as e:
            logger.error(f"清理 apscheduler_jobs 時發生未預期錯誤: {e}", exc_info=True)
            session.rollback()
            raise

        session.query(CrawlerTasks).delete()
        session.query(Crawlers).delete()
        session.commit()
        logger.debug("CrawlerTasks 和 Crawlers 資料表已清理。")

    yield db_manager_for_test


@pytest.fixture(scope="function")
def task_executor_service(initialized_db_manager: DatabaseManager):
    """創建任務執行服務實例"""
    service = TaskExecutorService(db_manager=initialized_db_manager)
    return service


@pytest.fixture(scope="function")
def scheduler_service_with_mocks(
    initialized_db_manager: DatabaseManager, task_executor_service: TaskExecutorService
):
    """創建排程服務實例並返回服務和 mock 排程器"""
    with patch(
        "apscheduler.schedulers.background.BackgroundScheduler"
    ) as mock_scheduler_class:
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler
        mock_scheduler.get_jobs.return_value = []

        service = SchedulerService(task_executor_service, initialized_db_manager)

        try:
            yield service, mock_scheduler
        finally:
            if service.scheduler_status["running"]:
                try:
                    service.stop_scheduler()
                except SchedulerNotRunningError:
                    logger.warning(
                        "排程器狀態標記為運行中，但在停止時 APScheduler 引發 SchedulerNotRunningError。已忽略。"
                    )
                except Exception as e:
                    logger.error(
                        f"Fixture 清理期間停止排程器時發生錯誤: {e}",
                        exc_info=True,
                    )


@pytest.fixture(scope="function")
def sample_crawler_data(initialized_db_manager: DatabaseManager) -> dict:
    """創建一個測試用的爬蟲資料，返回包含 ID 的字典"""
    crawler_id = None
    crawler_data = {
        "crawler_name": "TestCrawler",
        "module_name": "test_module",
        "base_url": "https://test.com",
        "is_active": True,
        "crawler_type": "RSS",
        "config_file_name": "test_config.json",
    }
    with initialized_db_manager.session_scope() as session:
        crawler = Crawlers(**crawler_data)
        session.add(crawler)
        session.flush()
        crawler_id = crawler.id
        session.commit()
        logger.debug(f"已創建範例爬蟲資料，ID: {crawler_id}")
    crawler_data["id"] = crawler_id
    return crawler_data


@pytest.fixture(scope="function")
def sample_tasks_data(
    initialized_db_manager: DatabaseManager, sample_crawler_data: dict
) -> dict:
    """創建多個測試用的爬蟲任務資料，返回包含任務名稱到 {id, data} 映射的字典"""
    crawler_id = sample_crawler_data["id"]
    tasks_details = {}

    tasks_to_create = [
        {
            "task_name": "Auto Task",
            "crawler_id": crawler_id,
            "cron_expression": "0 */6 * * *",
            "is_auto": True,
            "is_active": True,
            "is_scheduled": False,
            "task_args": {"scrape_mode": ScrapeMode.FULL_SCRAPE.value},
            "scrape_phase": ScrapePhase.INIT,
            "task_status": TaskStatus.INIT,
            "retry_count": 0,
        },
        {
            "task_name": "Manual Task",
            "crawler_id": crawler_id,
            "cron_expression": "0 0 * * *",
            "is_auto": False,
            "is_active": True,
            "is_scheduled": False,
            "task_args": {"scrape_mode": ScrapeMode.LINKS_ONLY.value},
            "scrape_phase": ScrapePhase.INIT,
            "task_status": TaskStatus.INIT,
            "retry_count": 0,
        },
        {
            "task_name": "Scheduled Task",
            "crawler_id": crawler_id,
            "cron_expression": "*/30 * * * *",
            "is_auto": True,
            "is_active": True,
            "is_scheduled": True,
            "task_args": {"scrape_mode": ScrapeMode.CONTENT_ONLY.value},
            "scrape_phase": ScrapePhase.INIT,
            "task_status": TaskStatus.INIT,
            "retry_count": 0,
        },
    ]

    with initialized_db_manager.session_scope() as session:
        created_tasks = []
        for task_data in tasks_to_create:
            task = CrawlerTasks(**task_data)
            session.add(task)
            created_tasks.append(task)
        session.flush()

        for i, task in enumerate(created_tasks):
            task_name = tasks_to_create[i]["task_name"]
            task_dict = {
                column.name: getattr(task, column.name)
                for column in task.__table__.columns
            }
            if isinstance(task_dict.get("scrape_phase"), ScrapePhase):
                task_dict["scrape_phase"] = task_dict["scrape_phase"].value
            if isinstance(task_dict.get("task_status"), TaskStatus):
                task_dict["task_status"] = task_dict["task_status"].value
            tasks_details[task_name] = task_dict
        session.commit()
        logger.debug(f"已創建範例任務資料 (字典格式): {tasks_details}")

    return tasks_details


# --- Tests ---


class TestSchedulerService:
    """測試排程服務"""

    @pytest.fixture(scope="function")
    def scheduler_service_for_init(
        self,
        initialized_db_manager: DatabaseManager,
        task_executor_service: TaskExecutorService,
    ):
        """創建排程服務實例 (僅用於 test_init)"""
        with patch(
            "apscheduler.schedulers.background.BackgroundScheduler"
        ) as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler
            mock_scheduler.get_jobs.return_value = []
            service = SchedulerService(task_executor_service, initialized_db_manager)
            yield service
            if service.scheduler_status["running"]:
                service.stop_scheduler()

    def test_init(
        self,
        scheduler_service_for_init: SchedulerService,
        initialized_db_manager: DatabaseManager,
        task_executor_service: TaskExecutorService,
    ):
        """測試排程服務初始化"""
        scheduler_service = scheduler_service_for_init
        assert scheduler_service.db_manager is initialized_db_manager
        assert scheduler_service.task_executor_service is task_executor_service
        assert scheduler_service.cron_scheduler is not None
        assert scheduler_service.scheduler_status["running"] is False
        assert scheduler_service.scheduler_status["job_count"] == 0

    def test_start_scheduler(
        self,
        scheduler_service_with_mocks,
        sample_tasks_data: dict,
        initialized_db_manager: DatabaseManager,
    ):
        """測試啟動排程器"""
        scheduler_service, _ = scheduler_service_with_mocks
        auto_task_id = sample_tasks_data["Auto Task"]["id"]
        manual_task_id = sample_tasks_data["Manual Task"]["id"]
        scheduled_task_id = sample_tasks_data["Scheduled Task"]["id"]

        with patch.object(
            scheduler_service, "_schedule_task", return_value=True
        ) as mock_schedule, patch.object(
            scheduler_service.cron_scheduler, "start"
        ) as mock_start_on_instance:

            result = scheduler_service.start_scheduler()

        assert result["success"] is True
        assert "調度器已啟動" in result["message"]
        assert scheduler_service.scheduler_status["running"] is True

        with initialized_db_manager.session_scope() as session:
            auto_task_db = session.get(CrawlerTasks, auto_task_id)
            manual_task_db = session.get(CrawlerTasks, manual_task_id)
            scheduled_task_db = session.get(CrawlerTasks, scheduled_task_id)

            assert auto_task_db is not None
            assert auto_task_db.is_scheduled is True
            assert manual_task_db is not None
            assert manual_task_db.is_scheduled is False
            assert scheduled_task_db is not None
            assert scheduled_task_db.is_scheduled is True

        mock_start_on_instance.assert_called_once()

        expected_auto_tasks_count = sum(
            1 for task_data in sample_tasks_data.values() if task_data.get("is_auto")
        )
        assert mock_schedule.call_count == expected_auto_tasks_count

    def test_stop_scheduler(self, scheduler_service_with_mocks):
        """測試停止排程器"""
        scheduler_service, _ = scheduler_service_with_mocks
        scheduler_service.scheduler_status["running"] = True
        scheduler_service.scheduler_status["job_count"] = 5

        with patch.object(
            scheduler_service.cron_scheduler, "pause"
        ) as mock_pause_on_instance:
            result = scheduler_service.stop_scheduler()

        assert result["success"] is True
        assert "調度器已暫停" in result["message"]
        assert scheduler_service.scheduler_status["running"] is False
        mock_pause_on_instance.assert_called_once()

    def test_schedule_task(
        self,
        scheduler_service_with_mocks,
        sample_tasks_data: dict,
        initialized_db_manager: DatabaseManager,
    ):
        """測試設定任務排程 (_schedule_task 內部方法)"""
        scheduler_service, _ = scheduler_service_with_mocks
        auto_task_id = sample_tasks_data["Auto Task"]["id"]
        expected_task_args = sample_tasks_data["Auto Task"]["task_args"]
        expected_task_name = sample_tasks_data["Auto Task"]["task_name"]
        job_id = f"task_{auto_task_id}"

        with initialized_db_manager.session_scope() as session:
            auto_task_obj = session.get(CrawlerTasks, auto_task_id)
            assert auto_task_obj is not None

            with patch.object(
                scheduler_service.cron_scheduler, "add_job"
            ) as mock_add_job_on_instance:
                result = scheduler_service._schedule_task(auto_task_obj)

            assert result is True

            mock_add_job_on_instance.assert_called_once_with(
                func=scheduler_service._trigger_task,
                trigger=ANY,
                args=[auto_task_id],
                id=job_id,
                name=expected_task_name,
                replace_existing=True,
                misfire_grace_time=1800,
                kwargs={"task_args": expected_task_args},
                jobstore="default",
            )

            mock_add_job_on_instance.reset_mock()
            auto_task_obj.cron_expression = None
            session.flush()
            result_no_cron = scheduler_service._schedule_task(auto_task_obj)

            assert result_no_cron is False
            mock_add_job_on_instance.assert_not_called()

    @patch("src.database.crawler_tasks_repository.CrawlerTasksRepository.get_by_id")
    @patch("src.services.scheduler_service.get_task_executor_service")
    def test_trigger_task(
        self,
        mock_get_executor,
        mock_get_by_id,
        scheduler_service_with_mocks,
        sample_tasks_data: dict,
        initialized_db_manager: DatabaseManager,
    ):
        """測試觸發任務執行 (_trigger_task 內部方法)"""
        scheduler_service, _ = scheduler_service_with_mocks
        auto_task_id = sample_tasks_data["Auto Task"]["id"]
        manual_task_id = sample_tasks_data["Manual Task"]["id"]
        auto_task_args = sample_tasks_data["Auto Task"]["task_args"]
        manual_task_args = sample_tasks_data["Manual Task"]["task_args"]

        mock_auto_task_data = sample_tasks_data["Auto Task"]
        mock_manual_task_data = sample_tasks_data["Manual Task"]

        mock_auto_task_obj = MagicMock(spec=CrawlerTasks, **mock_auto_task_data)
        mock_manual_task_obj = MagicMock(spec=CrawlerTasks, **mock_manual_task_data)

        mock_get_by_id.return_value = mock_auto_task_obj
        mock_executor_instance = MagicMock()
        mock_get_executor.return_value = mock_executor_instance

        scheduler_service._trigger_task(auto_task_id, auto_task_args)
        mock_get_executor.assert_called_once()
        mock_executor_instance.execute_task.assert_called_once_with(
            auto_task_id, auto_task_args
        )

        mock_get_by_id.return_value = None
        mock_get_executor.reset_mock()
        mock_executor_instance.reset_mock()
        scheduler_service._trigger_task(999, {"some": "args"})
        mock_get_executor.assert_not_called()
        mock_executor_instance.execute_task.assert_not_called()

        mock_get_by_id.return_value = mock_manual_task_obj
        mock_get_executor.reset_mock()
        mock_executor_instance.reset_mock()
        scheduler_service._trigger_task(manual_task_id, manual_task_args)
        mock_get_executor.assert_not_called()
        mock_executor_instance.execute_task.assert_not_called()

    def test_add_or_update_task_to_scheduler(
        self,
        scheduler_service_with_mocks,
        sample_tasks_data: dict,
        initialized_db_manager: DatabaseManager,
    ):
        """測試新增或更新任務到排程器"""
        scheduler_service, _ = scheduler_service_with_mocks
        auto_task_id = sample_tasks_data["Auto Task"]["id"]
        job_id = f"task_{auto_task_id}"

        with initialized_db_manager.session_scope() as session:
            auto_task_obj = session.get(CrawlerTasks, auto_task_id)
            assert auto_task_obj is not None

            with patch.object(
                scheduler_service, "_schedule_task", return_value=True
            ) as mock_schedule_add, patch.object(
                scheduler_service.cron_scheduler, "get_job", return_value=None
            ) as mock_get_job_add:
                result_add = scheduler_service.add_or_update_task_to_scheduler(
                    auto_task_obj, session
                )

            assert result_add["success"] is True
            assert result_add["added_count"] == 1
            assert result_add["updated_count"] == 0
            mock_get_job_add.assert_called_once_with(job_id)
            mock_schedule_add.assert_called_once_with(auto_task_obj)

            session.refresh(auto_task_obj)
            assert auto_task_obj.is_scheduled is True

        with initialized_db_manager.session_scope() as session:
            auto_task_obj_for_update = session.get(CrawlerTasks, auto_task_id)
            assert auto_task_obj_for_update is not None

            original_cron = auto_task_obj_for_update.cron_expression
            auto_task_obj_for_update.cron_expression = "0 1 * * *"
            assert original_cron != auto_task_obj_for_update.cron_expression

            mock_job_exists = MagicMock(id=job_id)
            mock_job_exists.trigger = MagicMock()
            mock_job_exists.trigger.expression = original_cron

            with patch.object(
                scheduler_service, "_schedule_task", return_value=True
            ) as mock_schedule_update, patch.object(
                scheduler_service.cron_scheduler,
                "get_job",
                return_value=mock_job_exists,
            ) as mock_get_job_update, patch.object(
                scheduler_service.cron_scheduler, "remove_job"
            ) as mock_remove_job_update:
                result_update = scheduler_service.add_or_update_task_to_scheduler(
                    auto_task_obj_for_update, session
                )

            assert result_update["success"] is True
            assert result_update["added_count"] == 0
            assert result_update["updated_count"] == 1
            mock_get_job_update.assert_called_once_with(job_id)
            mock_remove_job_update.assert_called_once_with(job_id)
            mock_schedule_update.assert_called_once_with(auto_task_obj_for_update)

            session.refresh(auto_task_obj_for_update)
            assert auto_task_obj_for_update.is_scheduled is True
            assert auto_task_obj_for_update.cron_expression == "0 1 * * *"

        with initialized_db_manager.session_scope() as session:
            auto_task_obj_for_fail = session.get(CrawlerTasks, auto_task_id)
            assert auto_task_obj_for_fail is not None
            original_scheduled_state = auto_task_obj_for_fail.is_scheduled

            with patch.object(
                scheduler_service, "_schedule_task", return_value=False
            ) as mock_schedule_fail, patch.object(
                scheduler_service.cron_scheduler, "get_job", return_value=None
            ) as mock_get_job_fail:
                result_fail = scheduler_service.add_or_update_task_to_scheduler(
                    auto_task_obj_for_fail, session
                )

            assert result_fail["success"] is False
            assert result_fail["added_count"] == 0
            assert result_fail["updated_count"] == 0
            mock_get_job_fail.assert_called_once_with(job_id)
            mock_schedule_fail.assert_called_once_with(auto_task_obj_for_fail)

            session.refresh(auto_task_obj_for_fail)
            assert auto_task_obj_for_fail.is_scheduled == original_scheduled_state

    def test_remove_task_from_scheduler(
        self,
        scheduler_service_with_mocks,
        sample_tasks_data: dict,
        initialized_db_manager: DatabaseManager,
    ):
        """測試從排程器移除任務"""
        scheduler_service, _ = scheduler_service_with_mocks
        scheduled_task_id = sample_tasks_data["Scheduled Task"]["id"]
        job_id = f"task_{scheduled_task_id}"

        with initialized_db_manager.session_scope() as session:
            task = session.get(CrawlerTasks, scheduled_task_id)
            assert task is not None
            task.is_scheduled = True
            session.commit()

        with patch.object(
            scheduler_service.cron_scheduler, "remove_job"
        ) as mock_remove_job_on_instance:
            result = scheduler_service.remove_task_from_scheduler(scheduled_task_id)

        assert result["success"] is True
        assert f"從排程移除任務 {scheduled_task_id}" in result["message"]

        with initialized_db_manager.session_scope() as session:
            updated_task = session.get(CrawlerTasks, scheduled_task_id)
            assert updated_task is not None
            assert updated_task.is_scheduled is False

        mock_remove_job_on_instance.assert_called_once_with(job_id)

    def test_reload_scheduler(
        self,
        scheduler_service_with_mocks,
        sample_tasks_data: dict,
        initialized_db_manager: DatabaseManager,
    ):
        """測試重新載入排程器"""
        scheduler_service, _ = scheduler_service_with_mocks
        scheduler_service.scheduler_status["running"] = True

        auto_task_id = sample_tasks_data["Auto Task"]["id"]
        scheduled_task_id = sample_tasks_data["Scheduled Task"]["id"]

        mock_job_auto = MagicMock(id=f"task_{auto_task_id}")
        mock_job_stale = MagicMock(id="task_999")

        recorded_task_ids_for_add_update = []

        def add_update_side_effect(task_obj, session_arg):
            recorded_task_ids_for_add_update.append(task_obj.id)
            return {"success": True, "added_count": 1, "updated_count": 0}

        with patch.object(
            scheduler_service.cron_scheduler,
            "get_jobs",
        ) as mock_get_jobs, patch.object(
            scheduler_service.cron_scheduler, "remove_job"
        ) as mock_remove_job, patch.object(
            scheduler_service,
            "add_or_update_task_to_scheduler",
            side_effect=add_update_side_effect,
        ) as mock_add_update:

            mock_get_jobs.side_effect = [
                [mock_job_auto, mock_job_stale],
                [mock_job_auto],
            ]
            result = scheduler_service.reload_scheduler()

        assert result["success"] is True
        assert "調度器已重載" in result["message"]
        assert "移除 1 個任務" in result["message"]
        assert "更新 0 個任務" in result["message"]
        assert "新增 2 個任務" in result["message"]

        assert mock_get_jobs.call_count == 2

        mock_remove_job.assert_called_once_with(mock_job_stale.id)
        assert mock_add_update.call_count == 2
        expected_task_ids_called = {auto_task_id, scheduled_task_id}
        assert set(recorded_task_ids_for_add_update) == expected_task_ids_called

        actual_calls_args = mock_add_update.call_args_list
        assert all(isinstance(call[0][1], Session) for call in actual_calls_args)

        scheduler_service.scheduler_status["running"] = False
        mock_get_jobs.reset_mock()
        mock_remove_job.reset_mock()
        mock_add_update.reset_mock()

        result_not_running = scheduler_service.reload_scheduler()
        assert result_not_running["success"] is False
        assert "調度器未運行" in result_not_running["message"]
        mock_get_jobs.assert_not_called()
        mock_remove_job.assert_not_called()
        mock_add_update.assert_not_called()

    def test_get_scheduler_status(self, scheduler_service_with_mocks):
        """測試獲取排程器狀態"""
        scheduler_service, _ = scheduler_service_with_mocks
        now = datetime.now(timezone.utc)
        scheduler_service.scheduler_status = {
            "running": True,
            "job_count": 0,
            "last_start_time": now,
            "last_shutdown_time": None,
        }

        mock_job1 = MagicMock(id="task_1")
        mock_job2 = MagicMock(id="task_2")
        with patch.object(
            scheduler_service.cron_scheduler,
            "get_jobs",
            return_value=[mock_job1, mock_job2],
        ) as mock_get_jobs:
            result = scheduler_service.get_scheduler_status()

        assert result["success"] is True
        assert result["message"] == "獲取調度器狀態成功"
        status = result["status"]
        assert status["running"] is True
        assert status["job_count"] == 2
        assert status["last_start_time"] == now
        assert status["last_shutdown_time"] is None
        mock_get_jobs.assert_called_once()

    def test_get_persisted_jobs_info(
        self,
        scheduler_service_with_mocks,
        sample_tasks_data: dict,
        initialized_db_manager: DatabaseManager,
    ):
        """測試獲取持久化任務的詳細信息"""
        scheduler_service, _ = scheduler_service_with_mocks
        auto_task_data = sample_tasks_data["Auto Task"]
        manual_task_data = sample_tasks_data["Manual Task"]
        auto_task_id = auto_task_data["id"]
        manual_task_id = manual_task_data["id"]

        mock_job_auto = MagicMock()
        mock_job_auto.id = f"task_{auto_task_id}"
        mock_job_auto.name = auto_task_data["task_name"]
        mock_job_auto.next_run_time = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_trigger_auto = MagicMock()
        mock_trigger_auto.__str__.return_value = (
            f"CronTrigger: {auto_task_data['cron_expression']}"
        )
        mock_trigger_auto.expression = auto_task_data["cron_expression"]
        mock_job_auto.trigger = mock_trigger_auto
        mock_job_auto.misfire_grace_time = 3600

        mock_job_manual = MagicMock()
        mock_job_manual.id = f"task_{manual_task_id}"
        mock_job_manual.name = manual_task_data["task_name"]
        mock_job_manual.next_run_time = None
        mock_trigger_manual = MagicMock()
        mock_trigger_manual.__str__.return_value = (
            f"CronTrigger: {manual_task_data['cron_expression']}"
        )
        mock_trigger_manual.expression = manual_task_data["cron_expression"]
        mock_job_manual.trigger = mock_trigger_manual
        mock_job_manual.misfire_grace_time = 3600

        mock_job_stale = MagicMock(id="task_999", name="Stale Job")
        mock_job_stale.next_run_time = datetime.now(timezone.utc) + timedelta(
            minutes=10
        )
        mock_trigger_stale = MagicMock(
            __str__=lambda _: "CronTrigger: 0 0 * * *", expression="0 0 * * *"
        )
        mock_job_stale.trigger = mock_trigger_stale
        mock_job_stale.misfire_grace_time = 3600

        with patch.object(
            scheduler_service.cron_scheduler,
            "get_jobs",
            return_value=[mock_job_auto, mock_job_manual, mock_job_stale],
        ) as mock_get_jobs:
            result = scheduler_service.get_persisted_jobs_info()

        assert result["success"] is True
        assert len(result["jobs"]) == 3

        job_info_auto = next(
            (j for j in result["jobs"] if j["id"] == mock_job_auto.id), None
        )
        job_info_manual = next(
            (j for j in result["jobs"] if j["id"] == mock_job_manual.id), None
        )
        job_info_stale = next(
            (j for j in result["jobs"] if j["id"] == mock_job_stale.id), None
        )

        assert job_info_auto is not None
        assert job_info_auto["task_id"] == auto_task_id
        assert job_info_auto["exists_in_db"] is True
        assert job_info_auto["task_name"] == auto_task_data["task_name"]
        assert job_info_auto["is_auto_in_db"] == auto_task_data["is_auto"]
        assert job_info_auto["is_scheduled_in_db"] == auto_task_data["is_scheduled"]
        assert job_info_auto["cron_expression"] == mock_trigger_auto.expression
        assert (
            job_info_auto["cron_expression_in_db"] == auto_task_data["cron_expression"]
        )
        assert job_info_auto["next_run_time"] == mock_job_auto.next_run_time.isoformat()
        assert job_info_auto["misfire_grace_time"] == mock_job_auto.misfire_grace_time
        assert job_info_auto["trigger"] == str(mock_trigger_auto)
        assert job_info_auto["active"] is True

        assert job_info_manual is not None
        assert job_info_manual["task_id"] == manual_task_id
        assert job_info_manual["exists_in_db"] is True
        assert job_info_manual["task_name"] == manual_task_data["task_name"]
        assert job_info_manual["is_auto_in_db"] == manual_task_data["is_auto"]
        assert job_info_manual["is_scheduled_in_db"] == manual_task_data["is_scheduled"]
        assert job_info_manual["cron_expression"] == mock_trigger_manual.expression
        assert (
            job_info_manual["cron_expression_in_db"]
            == manual_task_data["cron_expression"]
        )
        assert job_info_manual["next_run_time"] is None
        assert (
            job_info_manual["misfire_grace_time"] == mock_job_manual.misfire_grace_time
        )
        assert job_info_manual["trigger"] == str(mock_trigger_manual)
        assert job_info_manual["active"] is False

        assert job_info_stale is not None
        assert job_info_stale["task_id"] == 999
        assert job_info_stale["exists_in_db"] is False
        assert job_info_stale["name"] == mock_job_stale.name
        assert job_info_stale["cron_expression"] == mock_trigger_stale.expression
        assert (
            job_info_stale["next_run_time"] == mock_job_stale.next_run_time.isoformat()
        )
        assert job_info_stale["trigger"] == str(mock_trigger_stale)
        assert job_info_stale["misfire_grace_time"] == mock_job_stale.misfire_grace_time
        assert job_info_stale["active"] is True

        assert "task_name" not in job_info_stale
        assert "is_auto_in_db" not in job_info_stale
        assert "is_scheduled_in_db" not in job_info_stale
        assert "cron_expression_in_db" not in job_info_stale

        mock_get_jobs.assert_called_once()
