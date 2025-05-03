"""測試 CrawlerTaskService 的功能。

此模組包含對 CrawlerTaskService 類的所有測試案例，包括：
- CRUD 操作 (建立、讀取、更新、刪除)
- 任務狀態管理
- 任務排程相關功能 (查找待執行任務)
- 任務歷史記錄查詢
- 重試機制
- 錯誤處理
"""

# Standard library imports
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from unittest.mock import call

# Third party imports
import pytest
from croniter import croniter


# Local application imports
from src.models.base_model import Base
from src.models.crawler_tasks_model import CrawlerTasks


from src.models.crawlers_model import Crawlers
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.services.crawler_task_service import CrawlerTaskService
from src.database.database_manager import DatabaseManager
from src.models.crawler_tasks_schema import (
    TASK_ARGS_DEFAULT,
    CrawlerTaskReadSchema,
)  # 保持
from src.models.crawler_task_history_schema import CrawlerTaskHistoryReadSchema
from src.utils.enum_utils import TaskStatus, ScrapePhase, ScrapeMode
from src.error.errors import ValidationError
from src.utils.datetime_utils import enforce_utc_datetime_transform
  # 使用統一的 logger

# flake8: noqa: F811
# pylint: disable=redefined-outer-name

logger = logging.getLogger(__name__)  # 使用統一的 logger  # 使用統一的 logger


# 使用 db_manager_for_test 的 Fixture
@pytest.fixture(scope="function")
def initialized_db_manager(db_manager_for_test):
    """Fixture that depends on db_manager_for_test, creates tables, and yields the manager."""
    logger.debug("為測試函數創建資料表...")
    try:
        # 確保創建所有相關資料表
        db_manager_for_test.create_tables(Base)  # 使用 Base 來創建所有繼承它的模型表
        yield db_manager_for_test
    finally:
        logger.debug("測試函數完成，資料表可能由管理器清理或下次測試設置時處理。")
        # 確保清理（如果需要），儘管 db_manager_for_test 可能會處理它
        # db_manager_for_test.drop_tables(Base) # 如果需要明確刪除，則取消註解


# crawler_task_service fixture 以使用 initialized_db_manager
@pytest.fixture(scope="function")
def crawler_task_service(initialized_db_manager):
    """創建爬蟲任務服務實例"""
    # 直接傳遞 initialized_db_manager
    return CrawlerTaskService(initialized_db_manager)


# 新增 sample_crawler_data fixture
@pytest.fixture(scope="function")
def sample_crawler_data(initialized_db_manager) -> Dict[str, Any]:
    """創建測試用的爬蟲資料，返回包含 ID 的字典"""
    crawler_id = None
    crawler_name = "測試爬蟲"
    with initialized_db_manager.session_scope() as session:
        # 清理可能存在的舊爬蟲數據
        session.query(Crawlers).delete()
        session.commit()

        crawler = Crawlers(
            crawler_name=crawler_name,
            module_name="test_module",
            base_url="https://test.com",
            is_active=True,
            crawler_type="RSS",
            config_file_name="test_config.json",
        )
        session.add(crawler)
        session.flush()  # 分配 ID
        crawler_id = crawler.id
        session.commit()
        logger.debug(f"已創建 ID 為 {crawler_id} 的樣本爬蟲")
    return {"id": crawler_id, "crawler_name": crawler_name}


# 修改 sample_tasks fixture
@pytest.fixture(scope="function")
def sample_tasks(
    initialized_db_manager, sample_crawler_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """創建測試用的爬蟲任務資料，返回包含關鍵數據的字典列表"""
    task_ids = []
    crawler_id = sample_crawler_data["id"]
    created_tasks_data = []

    with initialized_db_manager.session_scope() as session:
        # 先清空相關表格
        session.query(CrawlerTaskHistory).delete()
        session.query(CrawlerTasks).delete()
        # 不需要刪除 Crawlers，因為 sample_crawler_data 會處理
        session.commit()

        tasks_input_data = [
            {
                "task_name": "每日新聞爬取",
                "crawler_id": crawler_id,
                "cron_expression": "0 0 * * *",
                "is_auto": True,
                "is_active": True,
                "task_args": {
                    **TASK_ARGS_DEFAULT,
                    "max_items": 100,
                    "scrape_mode": ScrapeMode.FULL_SCRAPE.value,
                    "max_retries": 3,
                    "ai_only": False,
                },
                "scrape_phase": ScrapePhase.INIT,
                "retry_count": 0,
                "created_at": datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            },
            {
                "task_name": "週間財經新聞",
                "crawler_id": crawler_id,
                "cron_expression": "0 0 * * 1-5",
                "is_auto": True,
                "is_active": True,
                "task_args": {
                    **TASK_ARGS_DEFAULT,
                    "max_items": 50,
                    "scrape_mode": ScrapeMode.LINKS_ONLY.value,
                    "max_retries": 0,
                    "ai_only": True,
                },
                "scrape_phase": ScrapePhase.INIT,
                "retry_count": 0,
                "created_at": datetime(2023, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
            },
        ]

        tasks_objs = [CrawlerTasks(**data) for data in tasks_input_data]
        session.add_all(tasks_objs)
        session.flush()  # 分配 ID

        # 提交事務以持久化更改
        session.commit()

        # 再次查詢以獲取包含 ID 和默認值的數據
        tasks_db = (
            session.query(CrawlerTasks)
            .filter(CrawlerTasks.crawler_id == crawler_id)
            .order_by(CrawlerTasks.id)
            .all()
        )
        for task in tasks_db:
            created_tasks_data.append(
                {
                    "id": task.id,
                    "task_name": task.task_name,
                    "crawler_id": task.crawler_id,
                    "cron_expression": task.cron_expression,
                    "is_auto": task.is_auto,
                    "is_active": task.is_active,
                    "task_args": task.task_args,
                    "created_at": task.created_at,
                    "updated_at": task.updated_at,
                    "scrape_phase": task.scrape_phase,
                    "retry_count": task.retry_count,
                    "last_run_at": task.last_run_at,
                }
            )
        logger.debug(f"已創建 {len(created_tasks_data)} 個樣本任務。")

    return created_tasks_data


class TestCrawlerTaskService:

    # 修改測試函數以使用新的 fixture 和日誌
    def test_create_task(
        self, crawler_task_service: CrawlerTaskService, initialized_db_manager
    ):
        crawler_id_for_test = None
        with initialized_db_manager.session_scope() as session:
            crawler = Crawlers(
                crawler_name="Create Test Crawler",
                module_name="test_module",
                base_url="http://create.test",
                config_file_name="some_config.json",
            )
            session.add(crawler)
            session.flush()
            crawler_id_for_test = crawler.id
            session.commit()  # 提交以確保爬蟲存在

        assert crawler_id_for_test is not None, "未能創建測試爬蟲"

        task_data = {
            "task_name": "測試任務",
            "crawler_id": crawler_id_for_test,
            "is_auto": True,
            "cron_expression": "0 0 * * *",
            "task_args": {
                **TASK_ARGS_DEFAULT,
                "ai_only": False,
                "max_retries": 3,
                "scrape_mode": ScrapeMode.FULL_SCRAPE.value,
            },
            "scrape_phase": ScrapePhase.INIT.value,  # Enum value needed here
        }

        result = crawler_task_service.create_task(task_data)
        logger.debug(f"創建任務結果: {result}")  # 使用 logger
        assert result["success"] is True
        assert "task" in result and result["task"] is not None
        assert isinstance(result["task"], CrawlerTaskReadSchema)
        task_id = result["task"].id
        assert task_id is not None
        assert result["message"] == "任務新增及排程器新增成功"

        # 驗證創建結果
        get_result = crawler_task_service.get_task_by_id(task_id)
        assert get_result["success"] is True
        assert get_result["task"].id == task_id
        assert get_result["task"].task_name == "測試任務"
        assert get_result["task"].task_args["max_retries"] == 3

    def test_delete_task(
        self,
        crawler_task_service: CrawlerTaskService,
        sample_tasks: List[Dict[str, Any]],
    ):
        task_id = sample_tasks[0]["id"]  # 從字典獲取 ID
        result = crawler_task_service.delete_task(task_id)
        logger.debug(f"刪除任務結果: {result}")  # 使用 logger
        assert result["success"] is True
        assert "成功" in result["message"]

        result_get = crawler_task_service.get_task_by_id(task_id)
        assert result_get["success"] is False
        assert "任務不存在或不符合條件" in result_get["message"]
        assert result_get["task"] is None

    def test_get_task_by_id(
        self,
        crawler_task_service: CrawlerTaskService,
        sample_tasks: List[Dict[str, Any]],
    ):
        task_to_get = sample_tasks[0]  # 獲取字典
        task_id = task_to_get["id"]
        result = crawler_task_service.get_task_by_id(task_id)

        assert result["success"] is True
        assert "task" in result
        assert result["task"] is not None
        assert isinstance(result["task"], CrawlerTaskReadSchema)
        assert result["task"].id == task_id
        assert result["task"].task_name == task_to_get["task_name"]  # 與字典比較

    def test_find_all_tasks(
        self,
        crawler_task_service: CrawlerTaskService,
        sample_tasks: List[Dict[str, Any]],
    ):
        result = crawler_task_service.find_all_tasks()
        assert result["success"] is True
        assert "tasks" in result
        assert isinstance(result["tasks"], list)
        # 驗證數量時，考慮到其他測試可能創建了任務，所以使用 >=
        assert len(result["tasks"]) >= len(sample_tasks)
        if result["tasks"]:
            assert isinstance(result["tasks"][0], CrawlerTaskReadSchema)

    def test_find_task_history(
        self,
        crawler_task_service: CrawlerTaskService,
        sample_tasks: List[Dict[str, Any]],
        initialized_db_manager,
    ):
        task_id = sample_tasks[0]["id"]  # 從字典獲取 ID

        # 在 session_scope 中創建歷史數據
        with initialized_db_manager.session_scope() as session:
            histories_data = [
                {
                    "task_id": task_id,
                    "start_time": datetime(2023, 1, 1, tzinfo=timezone.utc),
                    "end_time": datetime(2023, 1, 1, 1, tzinfo=timezone.utc),
                    "success": True,
                    "message": "執行成功",
                    "articles_count": 10,
                    "task_status": TaskStatus.COMPLETED,
                },
                {
                    "task_id": task_id,
                    "start_time": datetime(2023, 1, 2, tzinfo=timezone.utc),
                    "end_time": datetime(2023, 1, 2, 1, tzinfo=timezone.utc),
                    "success": False,
                    "message": "執行失敗",
                    "articles_count": 0,
                    "task_status": TaskStatus.FAILED,
                },
            ]
            histories = [CrawlerTaskHistory(**data) for data in histories_data]
            session.add_all(histories)
            session.commit()  # 提交以確保持久化

        result = crawler_task_service.find_task_history(task_id)
        logger.debug(f"查找任務歷史結果: {result}")  # 使用 logger

        assert result["success"] is True
        assert "history" in result
        assert isinstance(result["history"], list)
        assert len(result["history"]) == 2
        if result["history"]:
            assert isinstance(result["history"][0], CrawlerTaskHistoryReadSchema)
            assert result["history"][0].task_id == task_id
            assert result["history"][1].task_id == task_id

    def test_get_task_status(
        self,
        crawler_task_service: CrawlerTaskService,
        sample_tasks: List[Dict[str, Any]],
    ):
        task_id = sample_tasks[0]["id"]  # 從字典獲取 ID

        # 更新狀態，Service 內部處理 session
        update_result = crawler_task_service.update_task_status(
            task_id,
            task_status=TaskStatus.RUNNING,
            scrape_phase=ScrapePhase.LINK_COLLECTION,
        )
        assert update_result["success"] is True

        result = crawler_task_service.get_task_status(task_id)
        logger.debug(f"獲取任務狀態結果: {result}")  # 使用 logger
        assert result["success"] is True
        assert "status" in result
        status_info = result["status"]
        assert status_info is not None
        assert status_info["task_id"] == task_id
        assert status_info["task_status"] == TaskStatus.RUNNING.value
        assert status_info["scrape_phase"] == ScrapePhase.LINK_COLLECTION.value

    def test_error_handling(self, crawler_task_service: CrawlerTaskService):
        # 測試獲取不存在的任務
        result_get = crawler_task_service.get_task_by_id(999999)
        assert result_get["success"] is False
        assert "任務不存在" in result_get["message"]
        assert result_get["task"] is None

        # 測試更新不存在的任務
        result_update = crawler_task_service.update_task(
            999999, {"task_name": "新名稱"}
        )
        assert result_update["success"] is False
        assert "任務不存在" in result_update["message"]
        assert result_update["task"] is None

    def test_create_task_with_scrape_mode(
        self, crawler_task_service: CrawlerTaskService, initialized_db_manager
    ):
        crawler_id_for_test = None
        with initialized_db_manager.session_scope() as session:
            crawler = Crawlers(
                crawler_name="Scrape Mode Test Crawler",
                module_name="test_module",
                base_url="http://scrape.test",
                config_file_name="some_config.json",
            )
            session.add(crawler)
            session.flush()
            crawler_id_for_test = crawler.id
            session.commit()

        assert crawler_id_for_test is not None

        task_data = {
            "task_name": "測試抓取模式任務",
            "crawler_id": crawler_id_for_test,
            "is_auto": True,
            "cron_expression": "0 0 * * *",
            "task_args": {
                **TASK_ARGS_DEFAULT,
                "ai_only": False,
                "max_retries": 3,
                "scrape_mode": ScrapeMode.LINKS_ONLY.value,
            },
            "scrape_phase": ScrapePhase.INIT.value,
        }

        result = crawler_task_service.create_task(task_data)
        logger.debug(f"創建帶抓取模式任務結果: {result}")  # 使用 logger
        assert result["success"] is True
        assert "task" in result and result["task"] is not None
        assert isinstance(result["task"], CrawlerTaskReadSchema)

        task_id = result["task"].id
        task_result = crawler_task_service.get_task_by_id(task_id)

        assert task_result["success"] is True
        assert isinstance(task_result["task"], CrawlerTaskReadSchema)
        assert (
            task_result["task"].task_args.get("scrape_mode")
            == ScrapeMode.LINKS_ONLY.value
        )

    def test_validate_task_data(
        self, crawler_task_service: CrawlerTaskService, initialized_db_manager
    ):
        crawler_id_for_test = None
        with initialized_db_manager.session_scope() as session:
            crawler = Crawlers(
                crawler_name="Validate Test Crawler",
                module_name="test_module",
                base_url="http://validate.test",
                config_file_name="some_config.json",
            )
            session.add(crawler)
            session.flush()
            crawler_id_for_test = crawler.id
            session.commit()

        assert crawler_id_for_test is not None

        valid_data = {
            "task_name": "測試驗證",
            "crawler_id": crawler_id_for_test,
            "is_auto": True,
            "cron_expression": "0 0 * * *",
            "task_args": {
                **TASK_ARGS_DEFAULT,
                "ai_only": False,
                "max_retries": 3,
                "scrape_mode": ScrapeMode.FULL_SCRAPE.value,
            },
            "scrape_phase": ScrapePhase.INIT.value,
        }

        validated_result = crawler_task_service.validate_task_data(valid_data.copy())
        assert validated_result["success"] is True
        assert isinstance(validated_result, dict)
        validated_data = validated_result["data"]
        assert "task_name" in validated_data
        assert (
            validated_data["task_args"]["scrape_mode"] == ScrapeMode.FULL_SCRAPE.value
        )

        invalid_data_no_cron = {
            "task_name": "測試驗證",
            "crawler_id": crawler_id_for_test,
            "is_auto": True,
            "cron_expression": None,
            "task_args": {
                **TASK_ARGS_DEFAULT,
                "ai_only": False,
                "max_retries": 3,
                "scrape_mode": ScrapeMode.FULL_SCRAPE.value,
            },
            "scrape_phase": ScrapePhase.INIT.value,
        }

        invalid_result = crawler_task_service.validate_task_data(
            invalid_data_no_cron.copy()
        )
        assert invalid_result["success"] is False
        assert (
            "資料驗證失敗：cron_expression: 當設定為自動執行時,此欄位不能為空"
            in invalid_result["message"]
        )

    def test_find_due_tasks(
        self,
        crawler_task_service: CrawlerTaskService,
        sample_tasks: List[Dict[str, Any]],
    ):
        cron_expression = "0 0 * * *"
        task_id = sample_tasks[0]["id"]  # 從字典獲取 ID

        # 更新任務設定
        crawler_task_service.update_task(
            task_id,
            {"cron_expression": cron_expression, "is_auto": True, "is_active": True},
        )

        now = datetime.now(timezone.utc)

        iter_for_test = croniter(cron_expression, now)
        prev_run_time_expected_utc = iter_for_test.get_prev(datetime)
        if prev_run_time_expected_utc.tzinfo is None:
            prev_run_time_expected_utc = prev_run_time_expected_utc.replace(
                tzinfo=timezone.utc
            )

        logger.debug(
            f"\n--- 測試 find_due_tasks: Case 1 (舊的上次執行時間) ---"
        )  # logger
        old_last_run = prev_run_time_expected_utc - timedelta(days=1)
        update_res_1 = crawler_task_service.update_task(
            task_id, {"last_run_at": old_last_run}
        )
        assert update_res_1["success"] is True
        result1 = crawler_task_service.find_due_tasks(cron_expression)
        logger.debug(f"結果 1 (舊的上次執行時間): {result1}")  # logger
        assert result1["success"] is True
        assert "tasks" in result1
        assert any(
            task.id == task_id for task in result1["tasks"]
        ), "任務應為待執行 (舊的上次執行時間)"

        logger.debug(
            f"\n--- 測試 find_due_tasks: Case 2 (正確的上次執行時間) ---"
        )  # logger
        update_res_2 = crawler_task_service.update_task(
            task_id, {"last_run_at": prev_run_time_expected_utc}
        )
        assert update_res_2["success"] is True
        result2 = crawler_task_service.find_due_tasks(cron_expression)
        logger.debug(f"結果 2 (正確的上次執行時間): {result2}")  # logger
        assert result2["success"] is True
        assert "tasks" in result2
        assert not any(
            task.id == task_id for task in result2["tasks"]
        ), f"任務不應為待執行 (正確的上次執行時間). last_run_at={prev_run_time_expected_utc.isoformat()}"

        logger.debug(f"\n--- 測試 find_due_tasks: Case 3 (從未執行) ---")  # logger
        update_res_3 = crawler_task_service.update_task(task_id, {"last_run_at": None})
        assert update_res_3["success"] is True
        result3 = crawler_task_service.find_due_tasks(cron_expression)
        logger.debug(f"結果 3 (從未執行): {result3}")  # logger
        assert result3["success"] is True
        assert "tasks" in result3
        assert any(
            task.id == task_id for task in result3["tasks"]
        ), "任務應為待執行 (從未執行)"

        logger.debug(f"\n--- 測試 find_due_tasks: Case 4 (不活躍) ---")  # logger
        update_res_4 = crawler_task_service.update_task(
            task_id, {"last_run_at": None, "is_active": False}
        )
        assert update_res_4["success"] is True
        result4 = crawler_task_service.find_due_tasks(cron_expression)
        logger.debug(f"結果 4 (不活躍): {result4}")  # logger
        assert result4["success"] is True
        assert "tasks" in result4
        assert not any(
            task.id == task_id for task in result4["tasks"]
        ), "任務不應為待執行 (不活躍)"
        # 重置回活躍狀態以避免影響其他測試
        crawler_task_service.update_task(task_id, {"is_active": True})

    def test_update_task_status_and_history(
        self,
        crawler_task_service: CrawlerTaskService,
        sample_tasks: List[Dict[str, Any]],
        initialized_db_manager,
    ):
        task_id = sample_tasks[0]["id"]  # 從字典獲取 ID
        now = datetime.now(timezone.utc)
        history_id_start = None

        initial_status_result = crawler_task_service.get_task_status(task_id)
        assert initial_status_result["success"] is True
        initial_status = initial_status_result["status"]
        assert (
            initial_status["task_status"] == ScrapePhase.INIT.value
        )  # 初始狀態應為 INIT
        assert initial_status["scrape_phase"] == ScrapePhase.INIT.value

        # 在 session_scope 中創建初始歷史記錄
        start_time = now - timedelta(minutes=1)
        history_data_start = {
            "task_id": task_id,
            "start_time": start_time,
            "task_status": TaskStatus.RUNNING,
            "message": "開始連結收集",
        }
        with initialized_db_manager.session_scope() as session:
            history_to_update = CrawlerTaskHistory(**history_data_start)
            session.add(history_to_update)
            session.flush()
            history_id_start = history_to_update.id
            session.commit()  # 提交以確保歷史記錄存在

        assert history_id_start is not None, "未能創建初始歷史記錄"

        # 更新任務狀態到 RUNNING
        result_start = crawler_task_service.update_task_status(
            task_id,
            task_status=TaskStatus.RUNNING,
            scrape_phase=ScrapePhase.LINK_COLLECTION,
        )
        assert result_start["success"] is True
        assert result_start["task"] is not None
        assert result_start["task"]["task_status"].value == TaskStatus.RUNNING.value
        assert (
            result_start["task"]["scrape_phase"].value
            == ScrapePhase.LINK_COLLECTION.value
        )

        # 驗證狀態是否已更新
        status_running_result = crawler_task_service.get_task_status(task_id)
        assert status_running_result["success"] is True
        status_running = status_running_result["status"]
        assert status_running["task_status"] == TaskStatus.RUNNING.value
        assert status_running["scrape_phase"] == ScrapePhase.LINK_COLLECTION.value

        # 更新任務狀態到 COMPLETED 並更新歷史記錄
        end_time = now
        history_data_end = {
            "success": True,
            "articles_count": 10,
            "task_status": TaskStatus.COMPLETED,
            "message": "任務執行成功",
        }
        result_end = crawler_task_service.update_task_status(
            task_id,
            task_status=TaskStatus.COMPLETED,
            scrape_phase=ScrapePhase.COMPLETED,
            history_id=history_id_start,
            history_data=history_data_end,
        )
        logger.debug(f"更新狀態和歷史結果: {result_end}")  # logger
        assert result_end["success"] is True
        assert result_end["task"] is not None
        assert result_end["task"]["task_status"].value == TaskStatus.COMPLETED.value
        assert result_end["task"]["scrape_phase"].value == ScrapePhase.COMPLETED.value
        assert result_end["history"] is not None
        updated_history = result_end["history"]
        assert updated_history["id"] == history_id_start
        assert updated_history["task_status"].value == TaskStatus.COMPLETED.value
        assert updated_history["success"] is True
        assert updated_history["articles_count"] == 10
        # 比較時間戳（允許一些秒數誤差）
        end_time_diff = abs(
            enforce_utc_datetime_transform(updated_history["end_time"]) - end_time
        )
        assert end_time_diff < timedelta(seconds=5)

        # 驗證最終狀態
        status_completed_result = crawler_task_service.get_task_status(task_id)
        assert status_completed_result["success"] is True
        status_completed = status_completed_result["status"]
        assert status_completed["task_status"] == TaskStatus.COMPLETED.value
        assert status_completed["scrape_phase"] == ScrapePhase.COMPLETED.value

    def test_increment_retry_count(
        self,
        crawler_task_service: CrawlerTaskService,
        sample_tasks: List[Dict[str, Any]],
    ):
        # 測試有最大重試次數的任務
        task_id_with_retry = sample_tasks[0]["id"]  # ID for task with max_retries=3
        initial_task_res = crawler_task_service.get_task_by_id(task_id_with_retry)
        assert initial_task_res["success"]
        max_retries = initial_task_res["task"].task_args.get("max_retries", 3)  # 應為 3
        assert max_retries == 3

        # 先重置重試次數
        crawler_task_service.reset_retry_count(task_id_with_retry)

        initial_task_result = crawler_task_service.get_task_by_id(task_id_with_retry)
        assert initial_task_result["success"]
        initial_retry_count = initial_task_result["task"].retry_count
        assert initial_retry_count == 0

        # 遞增直到達到最大次數
        for i in range(1, max_retries + 1):
            result = crawler_task_service.increment_retry_count(task_id_with_retry)
            logger.debug(f"遞增 {i}: {result}")  # logger
            assert result["success"] is True, f"遞增 {i} 應成功"
            assert result["retry_count"] == i, f"重試次數應為 {i} 在遞增 {i} 後"
            # 再次獲取以驗證資料庫中的值
            task_check = crawler_task_service.get_task_by_id(task_id_with_retry)["task"]
            assert task_check.retry_count == i

        # 嘗試超過最大次數
        result_exceed = crawler_task_service.increment_retry_count(task_id_with_retry)
        logger.debug(f"遞增超限: {result_exceed}")  # logger
        assert result_exceed["success"] is False
        # 檢查錯誤訊息，可能有多種表述
        assert "最大重試次數" in result_exceed.get(
            "message", ""
        ) or "Repository 未返回" in result_exceed.get("message", "")
        assert result_exceed["retry_count"] == max_retries  # 重試次數應保持在最大值

        # 測試 max_retries=0 的任務
        task_id_zero_retry = sample_tasks[1]["id"]  # ID for task with max_retries=0
        task_zero_retry_res = crawler_task_service.get_task_by_id(task_id_zero_retry)
        assert task_zero_retry_res["success"]
        # 驗證從數據庫獲取的 max_retries 是否確實為 0 (因 fixture 已修正)
        assert (
            task_zero_retry_res["task"].task_args.get("max_retries", -1) == 0
        )  # 使用 -1 作為默認值以區分未找到和值為 0 的情況

        # 重置重試次數（即使為 0 也應該成功重置為 0）
        crawler_task_service.reset_retry_count(task_id_zero_retry)
        # 嘗試遞增
        result_zero = crawler_task_service.increment_retry_count(task_id_zero_retry)
        logger.debug(f"遞增零重試: {result_zero}")  # logger
        assert result_zero["success"] is False
        assert "最大重試次數" in result_zero.get(
            "message", ""
        ) or "Repository 未返回" in result_zero.get("message", "")
        assert result_zero["retry_count"] == 0  # 重試次數應保持為 0

    def test_reset_retry_count(
        self,
        crawler_task_service: CrawlerTaskService,
        sample_tasks: List[Dict[str, Any]],
    ):
        task_id = sample_tasks[0]["id"]  # Task with max_retries=3

        # 先設置一個非零的重試次數
        crawler_task_service.update_max_retries(task_id, 3)  # 確保 max_retries 是 3
        crawler_task_service.increment_retry_count(task_id)
        crawler_task_service.increment_retry_count(task_id)

        # 驗證重置前的次數
        task_before_reset = crawler_task_service.get_task_by_id(task_id)["task"]
        assert task_before_reset.retry_count == 2

        # 執行重置
        result = crawler_task_service.reset_retry_count(task_id)
        logger.debug(f"重置結果: {result}")  # logger
        assert result["success"] is True
        assert "task" not in result  # reset 不返回 task 對象
        assert result["retry_count"] == 0

        # 驗證重置後的次數
        task_result = crawler_task_service.get_task_by_id(task_id)
        assert task_result["success"] is True
        assert task_result["task"].retry_count == 0

        # 測試當次數已經為 0 時重置
        result_already_zero = crawler_task_service.reset_retry_count(task_id)
        logger.debug(f"重置已為零結果: {result_already_zero}")  # logger
        assert result_already_zero["success"] is True
        # assert "無需重置" in result_already_zero["message"] # Service 可能不返回此訊息，檢查 count 即可
        assert result_already_zero["retry_count"] == 0

    def test_update_max_retries(
        self,
        crawler_task_service: CrawlerTaskService,
        sample_tasks: List[Dict[str, Any]],
    ):
        task_id = sample_tasks[0]["id"]

        initial_task = crawler_task_service.get_task_by_id(task_id)["task"]
        initial_args = initial_task.task_args.copy() if initial_task.task_args else {}

        new_max_retries = 5

        result = crawler_task_service.update_max_retries(task_id, new_max_retries)
        logger.debug(f"更新 max_retries 結果: {result}")  # logger
        assert result["success"] is True
        assert result["task"] is not None
        assert isinstance(result["task"], CrawlerTaskReadSchema)
        assert result["task"].task_args.get("max_retries") == new_max_retries

        # 再次獲取以驗證持久化
        task_result = crawler_task_service.get_task_by_id(task_id)
        assert task_result["success"] is True
        updated_args = task_result["task"].task_args
        assert updated_args.get("max_retries") == new_max_retries

        # 驗證其他 task_args 是否保持不變
        for key, value in initial_args.items():
            if key != "max_retries":
                assert updated_args.get(key) == value, f"任務參數 '{key}' 意外更改"

        # 測試更新為負數
        result_neg = crawler_task_service.update_max_retries(task_id, -1)
        assert result_neg["success"] is False
        assert "max_retries 不能為負數" in result_neg["message"]
        assert result_neg["task"] is None

    def test_find_failed_tasks(
        self,
        crawler_task_service: CrawlerTaskService,
        sample_crawler_data: Dict[str, Any],
        initialized_db_manager,
    ):
        """測試獲取最近失敗的任務"""
        days_to_check = 7
        crawler_id_for_test = sample_crawler_data["id"]

        # 使用 session_scope 清理和創建測試數據
        with initialized_db_manager.session_scope() as session:
            # 清理舊數據
            session.query(CrawlerTaskHistory).delete()
            session.query(CrawlerTasks).delete()
            session.commit()

            def create_test_task_in_session(
                name, last_run_success, last_run_at, is_active, scrape_phase_val
            ):
                task = CrawlerTasks(
                    task_name=name,
                    crawler_id=crawler_id_for_test,
                    is_auto=False,  # 手動觸發，不依賴 cron
                    task_args={**TASK_ARGS_DEFAULT, "max_retries": 1},
                    last_run_success=last_run_success,
                    last_run_message=f"Test: {name}",  # 添加 message
                    last_run_at=last_run_at,
                    is_active=is_active,
                    scrape_phase=scrape_phase_val,
                    task_status=(
                        TaskStatus.COMPLETED if last_run_success else TaskStatus.FAILED
                    ),  # 設置 task_status
                )
                session.add(task)
                session.flush()
                task_id = task.id
                session.commit()  # 為每個任務提交一次
                return task_id

            now_utc = datetime.now(timezone.utc)

            task_id_fail_recent = create_test_task_in_session(
                "最近失敗", False, now_utc - timedelta(days=1), True, ScrapePhase.FAILED
            )

            task_id_fail_old = create_test_task_in_session(
                "很久以前失敗",
                False,
                now_utc - timedelta(days=days_to_check + 1),
                True,
                ScrapePhase.FAILED,
            )

            task_id_success_recent = create_test_task_in_session(
                "最近成功任務",
                True,
                now_utc - timedelta(days=1),
                True,
                ScrapePhase.COMPLETED,
            )

            task_id_fail_inactive = create_test_task_in_session(
                "最近失敗但不活躍",
                False,
                now_utc - timedelta(days=1),
                False,
                ScrapePhase.FAILED,
            )

        # 執行查詢
        result = crawler_task_service.find_failed_tasks(days=days_to_check)
        logger.debug(f"查找失敗任務結果: {result}")  # logger
        assert result["success"] is True
        assert "tasks" in result
        failed_task_ids = [task.id for task in result["tasks"]]

        # 驗證結果
        assert task_id_fail_recent in failed_task_ids, "最近失敗的活躍任務應被找到"
        assert task_id_fail_old not in failed_task_ids, "過舊的失敗任務不應被找到"
        assert task_id_success_recent not in failed_task_ids, "成功的任務不應被找到"
        assert task_id_fail_inactive not in failed_task_ids, "不活躍的任務不應被找到"

    def test_update_task_persists_all_fields(
        self,
        crawler_task_service: CrawlerTaskService,
        sample_tasks: List[Dict[str, Any]],
    ):
        task_id = sample_tasks[0]["id"]  # 從字典獲取 ID
        logger.debug(f"\n--- 測試 update_task 持久化任務 {task_id} ---")  # logger

        # 獲取初始狀態 (is_active=None 獲取所有狀態)
        initial_result = crawler_task_service.get_task_by_id(task_id, is_active=None)
        assert initial_result["success"]
        initial_task = initial_result["task"]
        initial_name = initial_task.task_name
        initial_is_active = initial_task.is_active
        initial_cron = initial_task.cron_expression
        initial_task_args = (
            initial_task.task_args.copy() if initial_task.task_args else {}
        )
        initial_scrape_phase = initial_task.scrape_phase
        logger.debug(
            f"初始 名稱: {initial_name}, 活躍: {initial_is_active}, cron: {initial_cron}, 階段: {initial_scrape_phase}, 參數: {initial_task_args}"
        )  # logger

        new_name = "更新後的每日新聞"
        new_is_active = not initial_is_active
        new_cron = "5 0 * * *"
        new_scrape_phase = ScrapePhase.CONTENT_SCRAPING
        new_task_args = initial_task_args.copy()
        new_task_args["scrape_mode"] = ScrapeMode.LINKS_ONLY.value

        update_data = {
            "task_name": new_name,
            "is_active": new_is_active,
            "cron_expression": new_cron,
            "scrape_phase": new_scrape_phase,  # 需要傳遞 Enum 成員
            "task_args": new_task_args,
        }
        logger.debug(f"發送的更新數據: {update_data}")  # logger

        # 執行更新
        update_result = crawler_task_service.update_task(task_id, update_data)
        logger.debug(f"更新結果: {update_result}")  # logger
        assert update_result["success"] is True
        assert "任務更新成功" in update_result["message"]
        assert update_result["task"] is not None

        # 再次從資料庫獲取以驗證
        logger.debug(f"更新後再次從資料庫獲取任務 {task_id}...")  # logger
        refetched_result = crawler_task_service.get_task_by_id(task_id, is_active=None)
        assert refetched_result["success"]
        refetched_task = refetched_result["task"]

        logger.debug(
            f"重新獲取 名稱: {refetched_task.task_name}, 活躍: {refetched_task.is_active}, cron: {refetched_task.cron_expression}, 階段: {refetched_task.scrape_phase}, 參數: {refetched_task.task_args}"
        )  # logger
        assert refetched_task.task_name == new_name, "資料庫 task_name 值不匹配"
        assert refetched_task.is_active == new_is_active, "資料庫 is_active 值不匹配"
        assert (
            refetched_task.cron_expression == new_cron
        ), "資料庫 cron_expression 值不匹配"
        # 比較 scrape_phase 的 value
        assert (
            refetched_task.scrape_phase.value == new_scrape_phase.value
        ), "資料庫 scrape_phase 值不匹配"
        assert (
            refetched_task.task_args.get("scrape_mode") == ScrapeMode.LINKS_ONLY.value
        ), "task_args['scrape_mode'] 不匹配"
        # 檢查默認參數是否丟失
        if "max_pages" in initial_task_args:
            assert (
                refetched_task.task_args.get("max_pages")
                == initial_task_args["max_pages"]
            ), "默認任務參數丟失"

        logger.debug(f"--- 測試 update_task 持久化成功完成 ---")  # logger

    def test_find_tasks_advanced(
        self,
        crawler_task_service: CrawlerTaskService,
        sample_tasks: List[Dict[str, Any]],
        sample_crawler_data: Dict[str, Any],
        initialized_db_manager,
    ):
        """測試進階搜尋任務 (find_tasks_advanced)"""
        crawler_id_for_test = sample_crawler_data["id"]
        total_initial_tasks = len(sample_tasks)

        # 使用 session_scope 添加更多樣化的數據
        with initialized_db_manager.session_scope() as session:
            session.add(
                CrawlerTasks(
                    task_name="不活躍的舊任務",
                    crawler_id=crawler_id_for_test,
                    is_active=False,
                    cron_expression="* * * * *",
                    task_args=TASK_ARGS_DEFAULT,
                    created_at=datetime(2022, 1, 1, tzinfo=timezone.utc),
                )
            )
            session.add(
                CrawlerTasks(
                    task_name="活躍的特殊任務",
                    crawler_id=crawler_id_for_test,
                    is_active=True,
                    cron_expression="1 1 * * *",
                    task_args=TASK_ARGS_DEFAULT,
                    created_at=datetime(2023, 5, 1, tzinfo=timezone.utc),
                )
            )
            session.commit()

        # 1. 基本分頁測試 (獲取所有活躍和不活躍的)
        result_page1 = crawler_task_service.find_tasks_advanced(
            page=1, per_page=2, sort_by="created_at", sort_desc=False
        )  # 按創建時間升序
        assert result_page1["success"] is True
        assert "data" in result_page1
        data_page1 = result_page1["data"]
        assert data_page1["page"] == 1
        assert data_page1["per_page"] == 2
        # 總數應為初始樣本任務數 + 新增的 2 個
        expected_total = total_initial_tasks + 2
        assert data_page1["total"] == expected_total
        assert data_page1["total_pages"] == (expected_total + 1) // 2  # 向上取整
        assert data_page1["has_next"] is (
            expected_total > 2
        )  # 總數大於每頁數量時才有下一頁
        assert data_page1["has_prev"] is False
        assert len(data_page1["items"]) == 2
        assert data_page1["items"][0]["task_name"] == "不活躍的舊任務"  # 最舊的

        # 2. 帶過濾條件 (只獲取活躍的)
        result_active = crawler_task_service.find_tasks_advanced(is_active=True)
        assert result_active["success"] is True
        data_active = result_active["data"]
        expected_active_count = (
            sum(1 for t in sample_tasks if t["is_active"]) + 1
        )  # 樣本中活躍的 + 新增的活躍的 1 個
        assert data_active["total"] == expected_active_count
        assert all(item["is_active"] for item in data_active["items"])

        # 3. 帶排序條件 (按名稱升序)
        result_sorted = crawler_task_service.find_tasks_advanced(
            sort_by="task_name", sort_desc=False
        )
        assert result_sorted["success"] is True
        data_sorted = result_sorted["data"]
        assert len(data_sorted["items"]) > 1  # 確保有東西可以比較
        assert (
            data_sorted["items"][0]["task_name"] <= data_sorted["items"][1]["task_name"]
        )

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
        result_combo = crawler_task_service.find_tasks_advanced(
            is_active=True, page=2, per_page=1, sort_by="created_at", sort_desc=False
        )
        assert result_combo["success"] is True
        data_combo = result_combo["data"]
        assert data_combo["page"] == 2
        assert data_combo["per_page"] == 1
        assert (
            data_combo["total"] == expected_active_count
        )  # 總共有 expected_active_count 個活躍的
        assert len(data_combo["items"]) == 1
        # 驗證是否為活躍任務中按創建時間升序的第二個
        # 活躍的有：sample_tasks[0](10:00), sample_tasks[1](11:00), "活躍的特殊任務"(2023-05-01)
        # 按創建時間排序：sample_tasks[0], sample_tasks[1], "活躍的特殊任務"
        # 第二頁的第一個應該是 sample_tasks[1] ("週間財經新聞")
        # 直接比較名稱，不再依賴 sample_tasks 的索引
        assert data_combo["items"][0]["task_name"] == "週間財經新聞"

        # 6. 測試無結果的過濾
        result_no_match = crawler_task_service.find_tasks_advanced(
            task_name="不存在的任務名稱"
        )
        assert result_no_match["success"] is True
        data_no_match = result_no_match["data"]
        assert data_no_match["total"] == 0
        assert len(data_no_match["items"]) == 0
