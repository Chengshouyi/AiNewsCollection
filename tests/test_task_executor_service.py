"""測試 TaskExecutorService 的功能。

此模組包含對 TaskExecutorService 類的所有測試案例，包括：
- 同步和異步任務執行 (成功、失敗)
- 任務取消
- 任務狀態獲取
- 特定抓取模式的執行 (links_only, content_only, full_scrape)
- 爬蟲測試功能
- 任務最後執行狀態更新
- 錯誤處理 (任務已運行、任務不存在)
"""

# Standard library imports
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
import time
from concurrent.futures import Future
from unittest.mock import patch, MagicMock, ANY, call
import logging  # 移除舊的 logging 導入，改用 LoggerSetup

# Third party imports
import pytest

# from sqlalchemy.orm import Session # 不再需要直接導入 Session

# Local application imports
from src.models.base_model import Base
from src.models.crawler_tasks_model import CrawlerTasks, ScrapePhase, ScrapeMode
from src.models.crawlers_model import Crawlers
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.services.task_executor_service import TaskExecutorService
from src.models.crawler_tasks_schema import TASK_ARGS_DEFAULT
from src.utils.enum_utils import TaskStatus
from src.utils.log_utils import LoggerSetup  # 使用統一的 logger

# flake8: noqa: F811
# pylint: disable=redefined-outer-name

logger = LoggerSetup.setup_logger(__name__)  # 使用統一的 logger


# --- Fixtures ---


@pytest.fixture(scope="function")
def initialized_db_manager(db_manager_for_test):
    """
    提供一個配置好的 DatabaseManager 實例，確保資料表存在並在每次測試前清理。
    假設 db_manager_for_test 配置了線程安全的記憶體資料庫。
    """
    Base.metadata.create_all(db_manager_for_test.engine)
    with db_manager_for_test.session_scope() as session:
        session.query(CrawlerTaskHistory).delete()
        session.query(CrawlerTasks).delete()
        session.query(Crawlers).delete()
        session.commit()  # 確保清理操作被提交
    yield db_manager_for_test


@pytest.fixture(scope="function")
def task_executor_service(initialized_db_manager):
    """創建任務執行服務實例"""
    service = TaskExecutorService(
        db_manager=initialized_db_manager, max_workers=1  # 簡化異步測試
    )
    yield service
    service.thread_pool.shutdown(wait=True)  # 建議使用 wait=True 確保清理完成


@pytest.fixture(scope="function")
def sample_crawler_data(initialized_db_manager) -> Dict[str, Any]:
    """創建測試用的爬蟲數據，返回包含 ID 的字典"""
    crawler_id = None
    with initialized_db_manager.session_scope() as session:
        crawler = Crawlers(
            crawler_name="TestCrawler",
            module_name="test_module",
            base_url="https://test.com",
            is_active=True,
            crawler_type="RSS",
            config_file_name="test_config.json",
        )
        session.add(crawler)
        session.flush()  # 確保在提交前分配 ID
        crawler_id = crawler.id
        session.commit()  # 提交以保存爬蟲
    logger.debug(f"Created sample crawler with ID: {crawler_id}")
    return {"id": crawler_id}


@pytest.fixture(scope="function")
def sample_task_data(
    initialized_db_manager, sample_crawler_data: Dict[str, Any]
) -> Dict[str, Any]:
    """創建測試用的爬蟲任務數據，返回包含 ID 的字典"""
    crawler_id = sample_crawler_data["id"]
    task_id = None
    with initialized_db_manager.session_scope() as session:
        task = CrawlerTasks(
            task_name="Test Task",
            module_name="test_module",
            crawler_id=crawler_id,
            cron_expression="0 0 * * *",
            is_auto=False,
            is_active=True,
            task_args={
                **TASK_ARGS_DEFAULT,
                "scrape_mode": ScrapeMode.FULL_SCRAPE.value,
            },
            scrape_phase=ScrapePhase.INIT,
            task_status=TaskStatus.INIT,
            retry_count=0,
        )
        session.add(task)
        session.flush()  # 確保在提交前分配 ID
        task_id = task.id
        initial_last_run_at = task.last_run_at  # 獲取初始狀態
        session.commit()  # 提交以保存任務
    logger.debug(f"Created sample task with ID: {task_id}")
    # 返回包含 ID 和初始時間的字典
    return {"id": task_id, "initial_last_run_at": initial_last_run_at}


# --- Mock Crawler ---
class MockCrawler:
    """用於模擬 BaseCrawler 行為的 Mock 類"""

    def __init__(
        self, success=True, message="成功", articles_count=5, raise_exception=None
    ):
        self.success = success
        self.message = message
        self.articles_count = articles_count
        self.raise_exception = raise_exception
        self.cancelled = False
        self.global_params = {}
        self.progress_listeners = {}

    def execute_task(self, task_id, task_args):
        logger.info(f"模擬爬蟲執行任務 {task_id}，參數：{task_args}")
        if self.raise_exception:
            logger.error(f"模擬爬蟲在任務 {task_id} 中引發異常：{self.raise_exception}")
            raise self.raise_exception
        time.sleep(0.1)  # 模擬耗時
        if self.cancelled:
            logger.warning(f"模擬爬蟲任務 {task_id} 在執行期間被取消。")
            return {
                "success": False,
                "message": "任務在執行期間被取消",
                "articles_count": 0,
            }
        logger.info(f"模擬爬蟲任務 {task_id} 完成。")
        return {
            "success": self.success,
            "message": self.message,
            "articles_count": self.articles_count,
        }

    def cancel_task(self, task_id):
        logger.info(f"模擬爬蟲取消任務 {task_id}")
        self.cancelled = True
        if self.global_params.get("save_partial_results_on_cancel"):
            logger.info("模擬爬蟲：模擬保存部分結果...")
        return True

    def get_progress(self, task_id):
        return {
            "progress": 50,
            "scrape_phase": ScrapePhase.LINK_COLLECTION,
            "message": f"模擬爬蟲任務 {task_id} 進行中",
        }

    def add_progress_listener(self, task_id, listener):
        logger.info(f"模擬爬蟲：為任務 {task_id} 添加進度監聽器")
        if task_id not in self.progress_listeners:
            self.progress_listeners[task_id] = []
        self.progress_listeners[task_id].append(listener)

    def remove_progress_listener(self, task_id, listener):
        logger.info(f"模擬爬蟲：從任務 {task_id} 移除進度監聽器")
        if (
            task_id in self.progress_listeners
            and listener in self.progress_listeners[task_id]
        ):
            self.progress_listeners[task_id].remove(listener)


# --- Test Class ---
class TestTaskExecutorService:
    """測試任務執行服務"""

    def _wait_for_cleanup(
        self, service: TaskExecutorService, task_id: int, timeout: float = 2.0
    ):
        """輔助函數：輪詢等待指定任務從運行狀態中清理"""
        start_time = time.time()
        while task_id in service.running_tasks or task_id in service.running_crawlers:
            if time.time() - start_time > timeout:
                running_in = []
                if task_id in service.running_tasks:
                    running_in.append("running_tasks")
                if task_id in service.running_crawlers:
                    running_in.append("running_crawlers")
                pytest.fail(
                    f"任務 {task_id} 在 {timeout} 秒內未從 {', '.join(running_in)} 清理"
                )
            time.sleep(0.02)  # 短暫讓出 CPU，避免忙等待

    @patch("src.crawlers.crawler_factory.CrawlerFactory.get_crawler")
    @patch("src.web.socket_instance.socketio.emit")
    def test_execute_task_async_success(
        self,
        mock_emit,
        mock_get_crawler,
        task_executor_service: TaskExecutorService,
        sample_task_data: Dict[str, Any],
        initialized_db_manager,
    ):
        """測試異步執行任務成功"""
        mock_crawler_instance = MockCrawler(
            success=True, message="異步成功", articles_count=10
        )
        mock_get_crawler.return_value = mock_crawler_instance
        task_id = sample_task_data["id"]

        result = task_executor_service.execute_task(task_id, is_async=True)

        assert result["success"] is True
        assert result["message"] == f"任務 {task_id} 已提交執行"
        assert task_id in task_executor_service.running_tasks

        future = task_executor_service.running_tasks[task_id]
        future.result(timeout=5)  # 等待完成

        # 驗證數據庫狀態
        with initialized_db_manager.session_scope() as session:
            db_task = session.get(CrawlerTasks, task_id)
            assert db_task is not None, "數據庫中未找到任務"
            assert db_task.task_status == TaskStatus.COMPLETED
            assert db_task.scrape_phase == ScrapePhase.COMPLETED
            assert db_task.last_run_success is True
            assert db_task.last_run_message == "異步成功"
            assert db_task.last_run_at is not None

            history = (
                session.query(CrawlerTaskHistory)
                .filter_by(task_id=task_id)
                .order_by(CrawlerTaskHistory.id.desc())
                .first()
            )
            assert history is not None, "數據庫中未找到歷史記錄"
            assert history.task_status == TaskStatus.COMPLETED
            assert history.success is True
            assert history.message == "異步成功"
            assert history.articles_count == 10
            assert history.end_time is not None

        # --- 使用輪詢等待清理 ---
        self._wait_for_cleanup(task_executor_service, task_id)
        # --- 清理驗證 ---
        assert task_id not in task_executor_service.running_tasks  # 現在應該已被清理
        assert task_id not in task_executor_service.running_crawlers  # 現在應該已被清理

        # 驗證 WebSocket 事件
        assert mock_emit.call_count >= 3  # 開始、進度、結束

    @patch("src.crawlers.crawler_factory.CrawlerFactory.get_crawler")
    @patch("src.web.socket_instance.socketio.emit")
    def test_execute_task_async_failure(
        self,
        mock_emit,
        mock_get_crawler,
        task_executor_service: TaskExecutorService,
        sample_task_data: Dict[str, Any],
        initialized_db_manager,
    ):
        """測試異步執行任務失敗"""
        mock_crawler_instance = MockCrawler(
            success=False,
            message="異步失敗",
            articles_count=0,
            raise_exception=ValueError("爬蟲內部錯誤"),
        )
        mock_get_crawler.return_value = mock_crawler_instance
        task_id = sample_task_data["id"]

        result = task_executor_service.execute_task(task_id, is_async=True)
        assert result["success"] is True  # 提交成功
        assert task_id in task_executor_service.running_tasks

        future = task_executor_service.running_tasks[task_id]
        returned_value = future.result(timeout=5)  # 等待完成

        assert returned_value is not None
        assert returned_value["success"] is False
        assert "爬蟲內部錯誤" in returned_value["message"]

        # 驗證數據庫狀態
        # 由於失敗路徑也涉及異步回調更新數據庫，這裡也需要等待
        time.sleep(0.2)  # 給異步回調一點時間執行資料庫操作
        with initialized_db_manager.session_scope() as session:
            db_task = session.get(CrawlerTasks, task_id)
            assert db_task is not None, "數據庫中未找到任務"
            assert db_task.task_status == TaskStatus.FAILED
            assert db_task.scrape_phase == ScrapePhase.FAILED
            assert db_task.last_run_success is False
            assert db_task.last_run_message is not None
            assert "爬蟲內部錯誤" in db_task.last_run_message
            assert db_task.last_run_at is not None

            history = (
                session.query(CrawlerTaskHistory)
                .filter_by(task_id=task_id)
                .order_by(CrawlerTaskHistory.id.desc())
                .first()
            )
            assert history is not None, "數據庫中未找到歷史記錄"
            assert history.task_status == TaskStatus.FAILED
            assert history.success is False
            assert history.message is not None
            assert "爬蟲內部錯誤" in history.message
            assert history.articles_count == 0
            assert history.end_time is not None

        # --- 使用輪詢等待清理 ---
        self._wait_for_cleanup(task_executor_service, task_id)
        # --- 清理驗證 ---
        assert task_id not in task_executor_service.running_tasks  # 現在應該已被清理
        assert task_id not in task_executor_service.running_crawlers  # 現在應該已被清理

        # 驗證 WebSocket 事件
        assert mock_emit.call_count >= 2  # 失敗進度、結束
        calls = mock_emit.call_args_list
        # 檢查最後兩個調用（避免計數不准確）
        assert calls[-2][0][0] == "task_progress"
        assert calls[-2][0][1]["status"] == TaskStatus.FAILED.value
        assert calls[-2][0][1]["scrape_phase"] == ScrapePhase.FAILED.value
        assert calls[-1][0][0] == "task_finished"
        assert calls[-1][0][1]["task_id"] == task_id
        assert calls[-1][0][1]["status"] == TaskStatus.FAILED.value

    @patch("src.crawlers.crawler_factory.CrawlerFactory.get_crawler")
    @patch("src.web.socket_instance.socketio.emit")
    def test_execute_task_sync_success(
        self,
        mock_emit,
        mock_get_crawler,
        task_executor_service: TaskExecutorService,
        sample_task_data: Dict[str, Any],
        initialized_db_manager,
    ):
        """測試同步執行任務成功"""
        mock_crawler_instance = MockCrawler(
            success=True, message="同步成功", articles_count=8
        )
        mock_get_crawler.return_value = mock_crawler_instance
        task_id = sample_task_data["id"]

        result = task_executor_service.execute_task(task_id, is_async=False)

        assert result["success"] is True
        assert result["message"] == "同步成功"
        assert result["articles_count"] == 8
        assert result["task_status"] == TaskStatus.COMPLETED.value

        # 驗證數據庫狀態
        with initialized_db_manager.session_scope() as session:
            db_task = session.get(CrawlerTasks, task_id)
            assert db_task is not None, "數據庫中未找到任務"
            assert db_task.task_status == TaskStatus.COMPLETED
            assert db_task.scrape_phase == ScrapePhase.COMPLETED
            assert db_task.last_run_success is True
            assert db_task.last_run_message == "同步成功"

            history = (
                session.query(CrawlerTaskHistory)
                .filter_by(task_id=task_id)
                .order_by(CrawlerTaskHistory.id.desc())
                .first()
            )
            assert history is not None, "數據庫中未找到歷史記錄"
            assert history.task_status == TaskStatus.COMPLETED
            assert history.message == "同步成功"
            assert history.end_time is not None

        # 同步執行不涉及異步清理，直接驗證
        assert task_id not in task_executor_service.running_tasks
        assert task_id not in task_executor_service.running_crawlers

        # 驗證 WebSocket 事件
        assert mock_emit.call_count >= 3  # 開始、進度、結束

    def test_execute_task_already_running(
        self,
        task_executor_service: TaskExecutorService,
        sample_task_data: Dict[str, Any],
    ):
        """測試執行已在運行的任務"""
        task_id = sample_task_data["id"]
        task_executor_service.running_tasks[task_id] = Future()  # 模擬運行中

        result = task_executor_service.execute_task(task_id)
        assert result["success"] is False
        assert result["message"] == "任務已在執行中"

        del task_executor_service.running_tasks[task_id]  # 清理模擬

    def test_execute_task_does_not_exist(
        self, task_executor_service: TaskExecutorService
    ):
        """測試執行不存在的任務"""
        result = task_executor_service.execute_task(99999)
        assert result["success"] is False
        assert result["message"] == "任務不存在"

    @patch("src.crawlers.crawler_factory.CrawlerFactory.get_crawler")
    @patch("src.web.socket_instance.socketio.emit")
    def test_cancel_task_success(
        self,
        mock_emit,
        mock_get_crawler,
        task_executor_service: TaskExecutorService,
        sample_task_data: Dict[str, Any],
        initialized_db_manager,
    ):
        """測試成功取消正在執行的任務"""
        mock_crawler_instance = MockCrawler()
        mock_get_crawler.return_value = mock_crawler_instance
        task_id = sample_task_data["id"]

        # 模擬啟動異步任務 (使用 mock submit)
        with patch.object(
            task_executor_service.thread_pool, "submit", return_value=Future()
        ) as mock_submit:
            task_executor_service.execute_task(task_id, is_async=True)
            mock_submit.assert_called_once()
            task_executor_service.running_crawlers[task_id] = mock_crawler_instance
            mock_future = mock_submit.return_value
            task_executor_service.running_tasks[task_id] = mock_future

        mock_future.cancel = MagicMock(return_value=True)
        mock_crawler_instance.cancel_task = MagicMock(return_value=True)

        cancel_result = task_executor_service.cancel_task(task_id)

        assert cancel_result["success"] is True
        assert cancel_result["message"] == f"任務 {task_id} 已取消"
        mock_future.cancel.assert_called_once()
        mock_crawler_instance.cancel_task.assert_called_once_with(task_id)

        # 驗證數據庫狀態
        with initialized_db_manager.session_scope() as session:
            db_task = session.get(CrawlerTasks, task_id)
            assert db_task is not None, "數據庫中未找到任務"
            assert db_task.task_status == TaskStatus.CANCELLED
            assert db_task.scrape_phase == ScrapePhase.CANCELLED
            assert db_task.last_run_success is False
            assert db_task.last_run_message == "任務已被使用者取消"

            history = (
                session.query(CrawlerTaskHistory)
                .filter_by(task_id=task_id)
                .order_by(CrawlerTaskHistory.id.desc())
                .first()
            )
            assert history is not None, "數據庫中未找到歷史記錄"
            assert history.task_status == TaskStatus.CANCELLED
            assert history.message is not None
            assert "任務已被使用者取消" in history.message
            assert history.end_time is not None

        # 取消操作本身會同步清理，直接驗證
        assert task_id not in task_executor_service.running_tasks
        assert task_id not in task_executor_service.running_crawlers

        # 驗證 WebSocket 事件
        assert mock_emit.call_count >= 2  # 取消狀態、結束

    @patch("src.web.socket_instance.socketio.emit")
    def test_cancel_task_not_running(
        self,
        mock_emit,
        task_executor_service: TaskExecutorService,
        sample_task_data: Dict[str, Any],
        initialized_db_manager,
    ):
        """測試取消未在執行的任務"""
        task_id = sample_task_data["id"]
        assert task_id not in task_executor_service.running_tasks

        cancel_result = task_executor_service.cancel_task(task_id)

        assert cancel_result["success"] is False
        assert "無法取消任務" in cancel_result["message"]

        # 驗證數據庫狀態未改變
        with initialized_db_manager.session_scope() as session:
            db_task = session.get(CrawlerTasks, task_id)
            assert db_task is not None, "數據庫中未找到任務"
            assert db_task.task_status != TaskStatus.CANCELLED
            assert db_task.scrape_phase != ScrapePhase.CANCELLED

        mock_emit.assert_not_called()  # 不應發送事件

    @patch("src.web.socket_instance.socketio.emit")
    def test_get_task_status_running(
        self,
        mock_emit,  # mock_emit 雖然未使用，但 patch 需要它
        task_executor_service: TaskExecutorService,
        sample_task_data: Dict[str, Any],
    ):
        """測試獲取正在運行任務的狀態 (從內存)"""
        task_id = sample_task_data["id"]
        task_executor_service.running_tasks[task_id] = Future()  # 模擬運行
        mock_crawler = MockCrawler()
        task_executor_service.running_crawlers[task_id] = mock_crawler  # 模擬爬蟲

        status_result = task_executor_service.get_task_status(task_id)
        assert status_result["success"] is True
        assert status_result["task_status"] == TaskStatus.RUNNING.value
        assert status_result["scrape_phase"] == ScrapePhase.LINK_COLLECTION.value
        assert status_result["progress"] == 50
        assert f"模擬爬蟲任務 {task_id} 進行中" in status_result["message"]

        # 清理模擬
        del task_executor_service.running_tasks[task_id]
        del task_executor_service.running_crawlers[task_id]

    def test_get_task_status_completed_from_db(
        self,
        task_executor_service: TaskExecutorService,
        sample_task_data: Dict[str, Any],
        initialized_db_manager,
    ):
        """測試獲取已完成任務的狀態 (從DB)"""
        task_id = sample_task_data["id"]
        now = datetime.now(timezone.utc)
        assert task_id not in task_executor_service.running_tasks  # 確保不在運行

        # 更新任務狀態和創建歷史記錄
        with initialized_db_manager.session_scope() as session:
            task = session.get(CrawlerTasks, task_id)
            assert task is not None, "數據庫中未找到任務"
            task.task_status = TaskStatus.COMPLETED
            task.scrape_phase = ScrapePhase.COMPLETED
            task.last_run_success = True
            task.last_run_message = "DB 完成"
            task.last_run_at = now
            # session.add(task) # get 會自動添加

            history = CrawlerTaskHistory(
                task_id=task_id,
                start_time=now - timedelta(minutes=5),
                end_time=now,
                success=True,
                message="DB 完成歷史",
                task_status=TaskStatus.COMPLETED,
                articles_count=15,
            )
            session.add(history)
            session.commit()  # 提交更改

        status_result = task_executor_service.get_task_status(task_id)

        assert status_result["success"] is True
        assert status_result["task_status"] == TaskStatus.COMPLETED.value
        assert status_result["scrape_phase"] == ScrapePhase.COMPLETED.value
        assert status_result["progress"] == 100
        assert "DB 完成歷史" in status_result["message"]
        assert status_result["task"].id == task_id

    def test_get_running_tasks(self, task_executor_service: TaskExecutorService):
        """測試獲取所有正在運行的任務"""
        task_executor_service.running_tasks = {1: Future(), 3: Future(), 5: Future()}

        result = task_executor_service.get_running_tasks()
        assert result["success"] is True
        assert sorted(result["running_tasks"]) == [1, 3, 5]

        task_executor_service.running_tasks = {}  # 清理模擬

    @patch(
        "src.services.task_executor_service.TaskExecutorService._execute_task_internal",
        return_value={"success": True, "message": "模擬執行"},
    )
    def test_specialized_execution_methods(
        self,
        mock_execute_internal,  # mock 雖然未使用，但 patch 需要
        task_executor_service: TaskExecutorService,
        sample_task_data: Dict[str, Any],
    ):
        """測試特定執行方法是否正確調用 execute_task"""
        task_id = sample_task_data["id"]

        with patch.object(
            task_executor_service,
            "execute_task",
            wraps=task_executor_service.execute_task,
        ) as mock_execute_task:

            # --- collect_links_only ---
            task_executor_service.collect_links_only(task_id, is_async=False)
            mock_execute_task.assert_called_with(
                task_id,
                False,
                operation_type="collect_links_only",
                scrape_mode="links_only",
            )

            # --- fetch_content_only ---
            task_executor_service.execute_task.reset_mock()
            task_executor_service.fetch_content_only(task_id, is_async=False)
            mock_execute_task.assert_called_with(
                task_id,
                False,
                operation_type="fetch_content_only",
                scrape_mode="content_only",
            )

            # --- fetch_full_article ---
            task_executor_service.execute_task.reset_mock()
            task_executor_service.fetch_full_article(task_id, is_async=False)
            mock_execute_task.assert_called_with(
                task_id,
                False,
                operation_type="fetch_full_article",
                scrape_mode="full_scrape",
            )

    @patch("src.crawlers.crawler_factory.CrawlerFactory.get_crawler")
    def test_test_crawler(
        self, mock_get_crawler, task_executor_service: TaskExecutorService
    ):
        """測試 test_crawler 方法"""
        mock_crawler_instance = MockCrawler(
            success=True, message="測試成功", articles_count=3
        )
        mock_crawler_instance.execute_task = MagicMock(
            return_value={"success": True, "message": "測試成功", "articles_count": 3}
        )
        mock_get_crawler.return_value = mock_crawler_instance
        crawler_name = "MyTestCrawler"

        result = task_executor_service.test_crawler(
            crawler_name, test_params={"max_pages": 5, "num_articles": 10}
        )

        assert result["success"] is True
        assert result["message"] == "測試成功"
        assert "result" in result
        assert result["result"]["articles_count"] == 3

        mock_crawler_instance.execute_task.assert_called_once()
        call_args = mock_crawler_instance.execute_task.call_args[0]
        passed_task_args = call_args[1]

        # 驗證參數是否被 test_crawler 強制修改
        assert passed_task_args["is_test"] is True
        assert passed_task_args["scrape_mode"] == "links_only"
        assert passed_task_args["max_pages"] == 1
        assert passed_task_args["num_articles"] == 5
        assert passed_task_args["save_to_csv"] is False
        assert passed_task_args["save_to_database"] is False

    def test_update_task_last_run(
        self,
        task_executor_service: TaskExecutorService,
        sample_task_data: Dict[str, Any],
        initialized_db_manager,
    ):
        """測試更新任務最後執行狀態"""
        task_id = sample_task_data["id"]
        message_success = "最後運行成功"
        initial_time = sample_task_data["initial_last_run_at"]

        result_success = task_executor_service.update_task_last_run(
            task_id, True, message_success
        )
        assert result_success["success"] is True
        assert result_success["message"] == "任務最後執行狀態更新成功"

        # 驗證成功更新
        with initialized_db_manager.session_scope() as session:
            db_task_success = session.get(CrawlerTasks, task_id)
            assert db_task_success is not None, "數據庫中未找到任務（成功更新後）"
            assert db_task_success.last_run_success is True
            assert db_task_success.last_run_message == message_success
            assert db_task_success.last_run_at is not None
            assert (
                db_task_success.last_run_at > initial_time
                if initial_time
                else db_task_success.last_run_at is not None
            )
            # 為了後續比較，記錄成功更新的時間
            success_update_time = db_task_success.last_run_at

        # 測試失敗更新
        message_fail = "最後運行失敗"
        # 短暫停頓確保時間戳不同
        time.sleep(0.01)
        result_fail = task_executor_service.update_task_last_run(
            task_id, False, message_fail
        )
        assert result_fail["success"] is True
        assert (
            result_fail["message"] == "任務最後執行狀態更新成功"
        )  # Service 方法本身成功

        # 驗證失敗更新
        with initialized_db_manager.session_scope() as session:
            db_task_fail = session.get(CrawlerTasks, task_id)
            assert db_task_fail is not None, "數據庫中未找到任務（失敗更新後）"
            assert db_task_fail.last_run_success is False
            assert db_task_fail.last_run_message == message_fail
            # last_run_at 也應該被更新
            assert db_task_fail.last_run_at is not None
            assert (
                db_task_fail.last_run_at > success_update_time
            )  # 確保時間戳在成功更新之後
