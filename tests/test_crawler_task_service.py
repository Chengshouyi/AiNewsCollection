import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.crawler_tasks_model import CrawlerTasks, Base
from src.models.crawlers_model import Crawlers
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.services.crawler_task_service import CrawlerTaskService
from src.database.database_manager import DatabaseManager
from src.models.crawler_tasks_schema import TASK_ARGS_DEFAULT, CrawlerTaskReadSchema
from src.models.crawler_task_history_schema import CrawlerTaskHistoryReadSchema
from src.utils.enum_utils import TaskStatus, ScrapePhase, ScrapeMode
from src.error.errors import ValidationError
from src.utils.datetime_utils import enforce_utc_datetime_transform
from unittest.mock import call
from croniter import croniter

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
def crawler_task_service(session):
    """創建爬蟲任務服務實例"""
    db_manager = DatabaseManager(f'sqlite:///{session.get_bind().url.database}')
    db_manager.Session = sessionmaker(bind=session.get_bind())
    return CrawlerTaskService(db_manager)

@pytest.fixture(scope="function")
def sample_tasks(session):
    """創建測試用的爬蟲任務資料"""
    with session.begin_nested():
        session.query(CrawlerTaskHistory).delete()
        session.query(CrawlerTasks).delete()
        session.query(Crawlers).delete()
    session.commit()

    with session.begin_nested():
        crawler = Crawlers(
            crawler_name="測試爬蟲",
            module_name="test_module",
            base_url="https://test.com",
            is_active=True,
            crawler_type="RSS",
            config_file_name="test_config.json"
        )
        session.add(crawler)
        session.flush()

        tasks_data = [
            {
                "task_name": "每日新聞爬取",
                "crawler_id": crawler.id,
                "cron_expression": "0 0 * * *",
                "is_auto": True,
                "is_active": True,
                "task_args": {"max_items": 100, "scrape_mode": ScrapeMode.FULL_SCRAPE.value, "max_retries": 3, "ai_only": False, **TASK_ARGS_DEFAULT},
                "created_at": datetime(2023, 1, 1, tzinfo=timezone.utc),
                "updated_at": datetime(2023, 1, 1, tzinfo=timezone.utc),
                "scrape_phase": ScrapePhase.INIT,
                "retry_count": 0,
            },
            {
                "task_name": "週間財經新聞",
                "crawler_id": crawler.id,
                "cron_expression": "0 0 * * 1-5",
                "is_auto": True,
                "is_active": True,
                "task_args": {"max_items": 50, "scrape_mode": ScrapeMode.LINKS_ONLY.value, "max_retries": 3, "ai_only": True, **TASK_ARGS_DEFAULT},
                "created_at": datetime(2023, 1, 2, tzinfo=timezone.utc),
                "updated_at": datetime(2023, 1, 2, tzinfo=timezone.utc),
                "scrape_phase": ScrapePhase.INIT,
                "retry_count": 0,
            }
        ]
        tasks = [CrawlerTasks(**data) for data in tasks_data]
        session.add_all(tasks)

    session.commit()
    return tasks

class TestCrawlerTaskService:
    """測試爬蟲任務服務的核心功能"""

    def test_create_task(self, crawler_task_service, session):
        """測試創建爬蟲任務"""
        with session.begin_nested():
             crawler = Crawlers(
                 crawler_name="Create Test Crawler",
                 module_name="test_module",
                 base_url="http://create.test",
                 config_file_name="some_config.json"
             )
             session.add(crawler)
             session.flush()
             crawler_id_for_test = crawler.id
        session.commit()

        task_data = {
            "task_name": "測試任務",
            "crawler_id": crawler_id_for_test,
            "is_auto": True,
            "cron_expression": "0 0 * * *",
            "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False, "max_retries": 3, "scrape_mode": ScrapeMode.FULL_SCRAPE.value},
            "scrape_phase": ScrapePhase.INIT.value
        }

        result = crawler_task_service.create_task(task_data)
        print(f"Create task result: {result}")
        assert result["success"] is True
        assert "task" in result and result["task"] is not None
        assert isinstance(result["task"], CrawlerTaskReadSchema)
        task_id = result["task"].id
        assert task_id is not None
        assert result["message"] == "任務新增及排程器新增成功"

        get_result = crawler_task_service.get_task_by_id(task_id)
        assert get_result["success"] is True
        assert get_result["task"].id == task_id
        assert get_result["task"].task_name == "測試任務"
        assert get_result["task"].task_args['max_retries'] == 3

    def test_delete_task(self, crawler_task_service, sample_tasks):
        """測試刪除爬蟲任務"""
        task_id = sample_tasks[0].id
        result = crawler_task_service.delete_task(task_id)
        assert result["success"] is True
        assert "成功" in result["message"]

        result_get = crawler_task_service.get_task_by_id(task_id)
        assert result_get["success"] is False
        assert "任務不存在或不符合條件" in result_get["message"]
        assert result_get["task"] is None

    def test_get_task_by_id(self, crawler_task_service, sample_tasks):
        """測試根據ID獲取爬蟲任務"""
        task_id = sample_tasks[0].id
        result = crawler_task_service.get_task_by_id(task_id)

        assert result["success"] is True
        assert "task" in result
        assert result["task"] is not None
        assert isinstance(result["task"], CrawlerTaskReadSchema)
        assert result["task"].id == task_id
        assert result["task"].task_name == sample_tasks[0].task_name

    def test_find_all_tasks(self, crawler_task_service, sample_tasks):
        """測試獲取所有任務"""
        result = crawler_task_service.find_all_tasks()
        assert result["success"] is True
        assert "tasks" in result
        assert isinstance(result["tasks"], list)
        assert len(result["tasks"]) >= len(sample_tasks)
        if result["tasks"]:
             assert isinstance(result["tasks"][0], CrawlerTaskReadSchema)

    def test_find_task_history(self, crawler_task_service, sample_tasks, session):
        """測試獲取任務歷史記錄"""
        task_id = sample_tasks[0].id

        with session.begin_nested():
            histories_data = [
                {
                    "task_id": task_id,
                    "start_time": datetime(2023, 1, 1, tzinfo=timezone.utc),
                    "end_time": datetime(2023, 1, 1, 1, tzinfo=timezone.utc),
                    "success": True,
                    "message": "執行成功",
                    "articles_count": 10,
                    "task_status": TaskStatus.COMPLETED
                },
                {
                    "task_id": task_id,
                    "start_time": datetime(2023, 1, 2, tzinfo=timezone.utc),
                    "end_time": datetime(2023, 1, 2, 1, tzinfo=timezone.utc),
                    "success": False,
                    "message": "執行失敗",
                    "articles_count": 0,
                    "task_status": TaskStatus.FAILED
                }
            ]
            histories = [CrawlerTaskHistory(**data) for data in histories_data]
            session.add_all(histories)
        session.commit()

        result = crawler_task_service.find_task_history(task_id)

        assert result["success"] is True
        assert "history" in result
        assert isinstance(result["history"], list)
        assert len(result["history"]) == 2
        if result["history"]:
            assert isinstance(result["history"][0], CrawlerTaskHistoryReadSchema)
            assert result["history"][0].task_id == task_id
            assert result["history"][1].task_id == task_id

    def test_get_task_status(self, crawler_task_service, sample_tasks, session):
        """測試獲取任務狀態"""
        task_id = sample_tasks[0].id

        update_result = crawler_task_service.update_task_status(
            task_id,
            task_status=TaskStatus.RUNNING,
            scrape_phase=ScrapePhase.LINK_COLLECTION
        )
        assert update_result["success"] is True

        result = crawler_task_service.get_task_status(task_id)
        print(f"Get task status result: {result}")
        assert result["success"] is True
        assert "status" in result
        status_info = result["status"]
        assert status_info is not None
        assert status_info["task_id"] == task_id
        assert status_info["task_status"] == TaskStatus.RUNNING.value
        assert status_info["scrape_phase"] == ScrapePhase.LINK_COLLECTION.value

    def test_error_handling(self, crawler_task_service):
        """測試錯誤處理"""
        result_get = crawler_task_service.get_task_by_id(999999)
        assert result_get["success"] is False
        assert "任務不存在" in result_get["message"]
        assert result_get["task"] is None

        result_update = crawler_task_service.update_task(999999, {"task_name": "新名稱"})
        assert result_update["success"] is False
        assert "任務不存在" in result_update["message"]
        assert result_update["task"] is None

    def test_create_task_with_scrape_mode(self, crawler_task_service, session):
        """測試創建帶有抓取模式的任務"""
        with session.begin_nested():
             crawler = Crawlers(
                 crawler_name="Scrape Mode Test Crawler",
                 module_name="test_module",
                 base_url="http://scrape.test",
                 config_file_name="some_config.json"
             )
             session.add(crawler)
             session.flush()
             crawler_id_for_test = crawler.id
        session.commit()

        task_data = {
            "task_name": "測試抓取模式任務",
            "crawler_id": crawler_id_for_test,
            "is_auto": True,
            "cron_expression": "0 0 * * *",
            "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False, "max_retries": 3, "scrape_mode": ScrapeMode.LINKS_ONLY.value},
            "scrape_phase": ScrapePhase.INIT.value
        }

        result = crawler_task_service.create_task(task_data)
        assert result["success"] is True
        assert "task" in result and result["task"] is not None
        assert isinstance(result["task"], CrawlerTaskReadSchema)

        task_id = result["task"].id
        task_result = crawler_task_service.get_task_by_id(task_id)

        assert task_result["success"] is True
        assert isinstance(task_result["task"], CrawlerTaskReadSchema)
        assert task_result["task"].task_args.get("scrape_mode") == ScrapeMode.LINKS_ONLY.value

    def test_validate_task_data(self, crawler_task_service, session):
        """測試任務資料驗證功能"""
        with session.begin_nested():
            crawler = Crawlers(
                crawler_name="Validate Test Crawler",
                module_name="test_module",
                base_url="http://validate.test",
                config_file_name="some_config.json"
            )
            session.add(crawler)
            session.flush()
            crawler_id_for_test = crawler.id
        session.commit()

        valid_data = {
            "task_name": "測試驗證",
            "crawler_id": crawler_id_for_test,
            "is_auto": True,
            "cron_expression": "0 0 * * *",
            "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False, "max_retries": 3, "scrape_mode": ScrapeMode.FULL_SCRAPE.value},
            "scrape_phase": ScrapePhase.INIT.value
        }

        try:
            validated_result = crawler_task_service.validate_task_data(valid_data.copy())
            assert validated_result['success'] is True
            assert isinstance(validated_result, dict)
            validated_data = validated_result['data']
            assert "task_name" in validated_data
            assert validated_data["task_args"]["scrape_mode"] == ScrapeMode.FULL_SCRAPE.value
        except ValidationError as e:
            pytest.fail(f"驗證應該通過，但卻失敗了: {e}")

        invalid_data_no_cron = {
            "task_name": "測試驗證",
            "crawler_id": crawler_id_for_test,
            "is_auto": True,
            "cron_expression": None,
            "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False, "max_retries": 3, "scrape_mode": ScrapeMode.FULL_SCRAPE.value},
            "scrape_phase": ScrapePhase.INIT.value
        }

        invalid_result = crawler_task_service.validate_task_data(invalid_data_no_cron.copy())
        assert invalid_result['success'] is False
        assert "資料驗證失敗：cron_expression: 當設定為自動執行時,此欄位不能為空" in invalid_result['message']

    def test_find_due_tasks(self, crawler_task_service, sample_tasks, session):
        """測試查詢待執行任務 (需要模擬時間和上次執行狀態)"""
        cron_expression = "0 0 * * *"
        task_id = sample_tasks[0].id

        crawler_task_service.update_task(task_id, {"cron_expression": cron_expression, "is_auto": True, "is_active": True})

        now = datetime.now(timezone.utc)

        iter_for_test = croniter(cron_expression, now)
        prev_run_time_expected_utc = iter_for_test.get_prev(datetime)
        if prev_run_time_expected_utc.tzinfo is None:
             prev_run_time_expected_utc = prev_run_time_expected_utc.replace(tzinfo=timezone.utc)

        print(f"\n--- Testing find_due_tasks: Case 1 (Old last run) ---")
        old_last_run = prev_run_time_expected_utc - timedelta(days=1)
        update_res_1 = crawler_task_service.update_task(task_id, {"last_run_at": old_last_run})
        assert update_res_1["success"] is True
        result1 = crawler_task_service.find_due_tasks(cron_expression)
        print(f"Result 1 (Old last run): {result1}")
        assert result1["success"] is True
        assert "tasks" in result1
        assert any(task.id == task_id for task in result1["tasks"]), "Task should be due (old last run)"

        print(f"\n--- Testing find_due_tasks: Case 2 (Correct last run) ---")
        update_res_2 = crawler_task_service.update_task(task_id, {"last_run_at": prev_run_time_expected_utc})
        assert update_res_2["success"] is True
        result2 = crawler_task_service.find_due_tasks(cron_expression)
        print(f"Result 2 (Correct last run): {result2}")
        assert result2["success"] is True
        assert "tasks" in result2
        assert not any(task.id == task_id for task in result2["tasks"]), f"Task should NOT be due (correct last run). last_run_at={prev_run_time_expected_utc.isoformat()}"

        print(f"\n--- Testing find_due_tasks: Case 3 (Never run) ---")
        update_res_3 = crawler_task_service.update_task(task_id, {"last_run_at": None})
        assert update_res_3["success"] is True
        result3 = crawler_task_service.find_due_tasks(cron_expression)
        print(f"Result 3 (Never run): {result3}")
        assert result3["success"] is True
        assert "tasks" in result3
        assert any(task.id == task_id for task in result3["tasks"]), "Task should be due (never run)"

        print(f"\n--- Testing find_due_tasks: Case 4 (Inactive) ---")
        update_res_4 = crawler_task_service.update_task(task_id, {"last_run_at": None, "is_active": False})
        assert update_res_4["success"] is True
        result4 = crawler_task_service.find_due_tasks(cron_expression)
        print(f"Result 4 (Inactive): {result4}")
        assert result4["success"] is True
        assert "tasks" in result4
        assert not any(task.id == task_id for task in result4["tasks"]), "Task should NOT be due (inactive)"
        crawler_task_service.update_task(task_id, {"is_active": True})

    def test_update_task_status_and_history(self, crawler_task_service, sample_tasks, session):
        """測試更新任務狀態和歷史記錄"""
        task_id = sample_tasks[0].id
        now = datetime.now(timezone.utc)

        initial_status_result = crawler_task_service.get_task_status(task_id)
        assert initial_status_result["success"] is True
        initial_status = initial_status_result["status"]
        assert initial_status['task_status'] == TaskStatus.INIT.value
        assert initial_status['scrape_phase'] == ScrapePhase.INIT.value

        start_time = now - timedelta(minutes=1)
        history_data_start = {
            "task_id": task_id,
            "start_time": start_time,
            "task_status": TaskStatus.RUNNING,
            "message": "開始連結收集"
        }
        with session.begin_nested():
             history_to_update = CrawlerTaskHistory(**history_data_start)
             session.add(history_to_update)
             session.flush()
             history_id_start = history_to_update.id
        session.commit()

        result_start = crawler_task_service.update_task_status(
            task_id,
            task_status=TaskStatus.RUNNING,
            scrape_phase=ScrapePhase.LINK_COLLECTION,
        )
        assert result_start['success'] is True
        assert result_start['task'] is not None
        assert result_start['task']['task_status'].value == TaskStatus.RUNNING.value
        assert result_start['task']['scrape_phase'].value == ScrapePhase.LINK_COLLECTION.value

        status_running_result = crawler_task_service.get_task_status(task_id)
        assert status_running_result["success"] is True
        status_running = status_running_result["status"]
        assert status_running['task_status'] == TaskStatus.RUNNING.value
        assert status_running['scrape_phase'] == ScrapePhase.LINK_COLLECTION.value

        end_time = now
        history_data_end = {
            "success": True,
            "articles_count": 10,
            "task_status": TaskStatus.COMPLETED,
            "message": "任務執行成功"
        }
        result_end = crawler_task_service.update_task_status(
            task_id,
            task_status=TaskStatus.COMPLETED,
            scrape_phase=ScrapePhase.COMPLETED,
            history_id=history_id_start,
            history_data=history_data_end
        )
        assert result_end['success'] is True
        assert result_end['task'] is not None
        assert result_end['task']['task_status'].value == TaskStatus.COMPLETED.value
        assert result_end['task']['scrape_phase'].value == ScrapePhase.COMPLETED.value
        assert result_end['history'] is not None
        updated_history = result_end['history']
        assert updated_history['id'] == history_id_start
        assert updated_history['task_status'].value == TaskStatus.COMPLETED.value
        assert updated_history['success'] is True
        assert updated_history['articles_count'] == 10
        end_time_diff = abs(enforce_utc_datetime_transform(updated_history['end_time']) - end_time)
        assert end_time_diff < timedelta(seconds=5)

        status_completed_result = crawler_task_service.get_task_status(task_id)
        assert status_completed_result["success"] is True
        status_completed = status_completed_result["status"]
        assert status_completed['task_status'] == TaskStatus.COMPLETED.value
        assert status_completed['scrape_phase'] == ScrapePhase.COMPLETED.value

    def test_increment_retry_count(self, crawler_task_service, sample_tasks):
        """測試增加任務重試次數 (包括邊界條件)"""
        task_id = sample_tasks[0].id
        initial_task_res = crawler_task_service.get_task_by_id(task_id)
        assert initial_task_res["success"]
        max_retries = initial_task_res["task"].task_args.get('max_retries', 3)

        crawler_task_service.reset_retry_count(task_id)

        initial_task_result = crawler_task_service.get_task_by_id(task_id)
        assert initial_task_result["success"]
        initial_retry_count = initial_task_result["task"].retry_count
        assert initial_retry_count == 0

        for i in range(1, max_retries + 1):
            result = crawler_task_service.increment_retry_count(task_id)
            print(f"Increment {i}: {result}")
            assert result["success"] is True, f"Increment {i} should succeed"
            assert result["retry_count"] == i, f"Retry count should be {i} after increment {i}"
            task_check = crawler_task_service.get_task_by_id(task_id)["task"]
            assert task_check.retry_count == i

        result_exceed = crawler_task_service.increment_retry_count(task_id)
        print(f"Increment exceed: {result_exceed}")
        assert result_exceed["success"] is False
        assert "最大重試次數" in result_exceed.get("message", "") or "Repository 未返回" in result_exceed.get("message", "")
        assert result_exceed["retry_count"] == max_retries

        task_id_zero_retry = sample_tasks[1].id
        crawler_task_service.update_max_retries(task_id_zero_retry, 0)
        crawler_task_service.reset_retry_count(task_id_zero_retry)
        result_zero = crawler_task_service.increment_retry_count(task_id_zero_retry)
        print(f"Increment zero retries: {result_zero}")
        assert result_zero["success"] is False
        assert "最大重試次數" in result_zero.get("message", "") or "Repository 未返回" in result_zero.get("message", "")
        assert result_zero["retry_count"] == 0

    def test_reset_retry_count(self, crawler_task_service, sample_tasks):
        """測試重置任務重試次數"""
        task_id = sample_tasks[0].id

        crawler_task_service.update_max_retries(task_id, 3)
        crawler_task_service.increment_retry_count(task_id)
        crawler_task_service.increment_retry_count(task_id)

        task_before_reset = crawler_task_service.get_task_by_id(task_id)["task"]
        assert task_before_reset.retry_count == 2

        result = crawler_task_service.reset_retry_count(task_id)
        print(f"Reset result: {result}")
        assert result["success"] is True
        assert "task" not in result
        assert result["retry_count"] == 0

        task_result = crawler_task_service.get_task_by_id(task_id)
        assert task_result["success"] is True
        assert task_result["task"].retry_count == 0

        result_already_zero = crawler_task_service.reset_retry_count(task_id)
        print(f"Reset already zero result: {result_already_zero}")
        assert result_already_zero["success"] is True
        assert "無需重置" in result_already_zero["message"]
        assert result_already_zero["retry_count"] == 0

    def test_update_max_retries(self, crawler_task_service, sample_tasks):
        """測試更新任務最大重試次數"""
        task_id = sample_tasks[0].id

        initial_task = crawler_task_service.get_task_by_id(task_id)["task"]
        initial_args = initial_task.task_args.copy() if initial_task.task_args else {}

        new_max_retries = 5

        result = crawler_task_service.update_max_retries(task_id, new_max_retries)
        print(f"Update max_retries result: {result}")
        assert result["success"] is True
        assert result["task"] is not None
        assert isinstance(result["task"], CrawlerTaskReadSchema)
        assert result["task"].task_args.get('max_retries') == new_max_retries

        task_result = crawler_task_service.get_task_by_id(task_id)
        assert task_result["success"] is True
        updated_args = task_result["task"].task_args
        assert updated_args.get('max_retries') == new_max_retries

        for key, value in initial_args.items():
            if key != 'max_retries':
                 assert updated_args.get(key) == value, f"Task arg '{key}' changed unexpectedly"

        result_neg = crawler_task_service.update_max_retries(task_id, -1)
        assert result_neg["success"] is False
        assert "max_retries 不能為負數" in result_neg["message"]
        assert result_neg["task"] is None

    def test_find_failed_tasks(self, crawler_task_service, sample_tasks, session):
        """測試獲取最近失敗的任務"""
        days_to_check = 7
        crawler_id_for_test = sample_tasks[0].crawler_id

        with session.begin_nested():
            session.query(CrawlerTaskHistory).delete()
            session.query(CrawlerTasks).delete()
        session.commit()

        def create_test_task(name, last_run_success, last_run_at, is_active, scrape_phase_val):
            task_data = {
                "task_name": name, "crawler_id": crawler_id_for_test, "is_auto": False,
                "task_args": {**TASK_ARGS_DEFAULT, "max_retries": 1},
                "last_run_success": last_run_success,
                "last_run_message": name,
                "last_run_at": last_run_at,
                "is_active": is_active,
                "scrape_phase": scrape_phase_val
            }
            create_result = crawler_task_service.create_task(task_data)
            assert create_result["success"], f"Failed to create task '{name}'"
            return create_result["task"].id

        task_id_fail_recent = create_test_task(
            "最近失敗", False, datetime.now(timezone.utc) - timedelta(days=1), True, ScrapePhase.FAILED.value
        )

        task_id_fail_old = create_test_task(
            "很久以前失敗", False, datetime.now(timezone.utc) - timedelta(days=days_to_check + 1), True, ScrapePhase.FAILED.value
        )

        task_id_success_recent = create_test_task(
            "最近成功任務", True, datetime.now(timezone.utc) - timedelta(days=1), True, ScrapePhase.COMPLETED.value
        )

        task_id_fail_inactive = create_test_task(
             "最近失敗但不活躍", False, datetime.now(timezone.utc) - timedelta(days=1), False, ScrapePhase.FAILED.value
        )

        result = crawler_task_service.find_failed_tasks(days=days_to_check)
        assert result["success"] is True
        assert "tasks" in result
        failed_task_ids = [task.id for task in result["tasks"]]

        assert task_id_fail_recent in failed_task_ids
        assert task_id_fail_old not in failed_task_ids
        assert task_id_success_recent not in failed_task_ids
        assert task_id_fail_inactive not in failed_task_ids

    def test_update_task_persists_all_fields(self, crawler_task_service, sample_tasks):
        """測試 update_task 是否能正確持久化普通欄位和 task_args 的變更"""
        task_id = sample_tasks[0].id
        print(f"\n--- Testing update_task persistence for task {task_id} ---")

        initial_result = crawler_task_service.get_task_by_id(task_id, is_active=None)
        assert initial_result["success"]
        initial_task = initial_result["task"]
        initial_name = initial_task.task_name
        initial_is_active = initial_task.is_active
        initial_cron = initial_task.cron_expression
        initial_task_args = initial_task.task_args.copy() if initial_task.task_args else {}
        initial_scrape_phase = initial_task.scrape_phase
        print(f"Initial name: {initial_name}, is_active: {initial_is_active}, cron: {initial_cron}, phase: {initial_scrape_phase}, task_args: {initial_task_args}")

        new_name = "更新後的每日新聞"
        new_is_active = not initial_is_active
        new_cron = "5 0 * * *"
        new_scrape_phase = ScrapePhase.CONTENT_SCRAPING
        new_task_args = initial_task_args.copy()
        new_task_args["max_items"] = 200
        new_task_args["new_param"] = "test_value"
        new_task_args["scrape_mode"] = ScrapeMode.LINKS_ONLY.value

        update_data = {
            "task_name": new_name,
            "is_active": new_is_active,
            "cron_expression": new_cron,
            "scrape_phase": new_scrape_phase,
            "task_args": new_task_args
        }
        print(f"Update data being sent: {update_data}")

        update_result = crawler_task_service.update_task(task_id, update_data)
        print(f"Update result: {update_result}")
        assert update_result["success"] is True
        assert "任務更新成功" in update_result["message"]
        assert update_result["task"] is not None

        print(f"Fetching task {task_id} from DB again after update...")
        refetched_result = crawler_task_service.get_task_by_id(task_id, is_active=None)
        assert refetched_result["success"]
        refetched_task = refetched_result["task"]

        print(f"Refetched name: {refetched_task.task_name}, is_active: {refetched_task.is_active}, cron: {refetched_task.cron_expression}, phase: {refetched_task.scrape_phase}, task_args: {refetched_task.task_args}")
        assert refetched_task.task_name == new_name, "DB value for task_name mismatch"
        assert refetched_task.is_active == new_is_active, "DB value for is_active mismatch"
        assert refetched_task.cron_expression == new_cron, "DB value for cron_expression mismatch"
        assert refetched_task.scrape_phase == new_scrape_phase, "DB value for scrape_phase mismatch"
        assert refetched_task.task_args.get("max_items") == 200, "task_args['max_items'] mismatch"
        assert refetched_task.task_args.get("new_param") == "test_value", "task_args['new_param'] mismatch"
        assert refetched_task.task_args.get("scrape_mode") == ScrapeMode.LINKS_ONLY.value, "task_args['scrape_mode'] mismatch"
        if "max_pages" in initial_task_args:
             assert refetched_task.task_args.get("max_pages") == initial_task_args["max_pages"], "Default task arg lost"

        print(f"--- Test update_task persistence finished successfully ---")

    def test_find_tasks_advanced(self, crawler_task_service, sample_tasks, session):
        """測試進階搜尋任務 (find_tasks_advanced)"""
        # 添加更多樣化的數據以進行過濾和排序測試
        crawler_id_for_test = sample_tasks[0].crawler_id
        with session.begin_nested():
            session.add(CrawlerTasks(
                task_name="不活躍的舊任務", crawler_id=crawler_id_for_test, is_active=False,
                cron_expression="* * * * *", task_args=TASK_ARGS_DEFAULT,
                created_at=datetime(2022, 1, 1, tzinfo=timezone.utc)
            ))
            session.add(CrawlerTasks(
                task_name="活躍的特殊任務", crawler_id=crawler_id_for_test, is_active=True,
                cron_expression="1 1 * * *", task_args=TASK_ARGS_DEFAULT,
                created_at=datetime(2023, 5, 1, tzinfo=timezone.utc)
            ))
        session.commit()

        # 1. 基本分頁測試 (獲取所有活躍和不活躍的)
        result_page1 = crawler_task_service.find_tasks_advanced(page=1, per_page=2, sort_by='created_at', sort_desc=False) # 按創建時間升序
        assert result_page1["success"] is True
        assert "data" in result_page1
        data_page1 = result_page1["data"]
        assert data_page1["page"] == 1
        assert data_page1["per_page"] == 2
        assert data_page1["total"] == 4 # sample_tasks(2) + new tasks(2)
        assert data_page1["total_pages"] == 2
        assert data_page1["has_next"] is True
        assert data_page1["has_prev"] is False
        assert len(data_page1["items"]) == 2
        assert data_page1["items"][0]["task_name"] == "不活躍的舊任務" # 最舊的

        # 2. 帶過濾條件 (只獲取活躍的)
        result_active = crawler_task_service.find_tasks_advanced(is_active=True)
        assert result_active["success"] is True
        data_active = result_active["data"]
        assert data_active["total"] == 3 # sample_tasks(2) + new active(1)
        assert all(item["is_active"] for item in data_active["items"])

        # 3. 帶排序條件 (按名稱升序)
        result_sorted = crawler_task_service.find_tasks_advanced(sort_by='task_name', sort_desc=False)
        assert result_sorted["success"] is True
        data_sorted = result_sorted["data"]
        assert len(data_sorted["items"]) > 1 # Ensure there's something to compare
        assert data_sorted["items"][0]["task_name"] <= data_sorted["items"][1]["task_name"]

        # 4. 預覽模式
        preview_fields = ["id", "task_name"]
        result_preview = crawler_task_service.find_tasks_advanced(
            page=1, per_page=2, is_preview=True, preview_fields=preview_fields
        )
        assert result_preview["success"] is True
        data_preview = result_preview["data"]
        assert len(data_preview["items"]) == 2
        assert isinstance(data_preview["items"][0], dict)
        assert set(data_preview["items"][0].keys()) == set(preview_fields)

        # 5. 組合過濾和分頁
        result_combo = crawler_task_service.find_tasks_advanced(is_active=True, page=2, per_page=1, sort_by='created_at', sort_desc=False)
        assert result_combo["success"] is True
        data_combo = result_combo["data"]
        assert data_combo["page"] == 2
        assert data_combo["per_page"] == 1
        assert data_combo["total"] == 3 # 總共有3個活躍的
        assert len(data_combo["items"]) == 1
        # 驗證是否為活躍任務中第二個創建的 (sample_tasks[1])
        assert data_combo["items"][0]["task_name"] == "週間財經新聞"

        # 6. 測試無結果的過濾
        result_no_match = crawler_task_service.find_tasks_advanced(task_name="不存在的任務名稱")
        assert result_no_match["success"] is True
        data_no_match = result_no_match["data"]
        assert data_no_match["total"] == 0
        assert len(data_no_match["items"]) == 0
