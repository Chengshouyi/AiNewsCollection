import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.models.base_model import Base
from src.models.crawler_tasks_model import CrawlerTasks, ScrapePhase, ScrapeMode
from src.models.crawlers_model import Crawlers
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.services.task_executor_service import TaskExecutorService
from src.database.database_manager import DatabaseManager
from src.models.crawler_tasks_schema import TASK_ARGS_DEFAULT
from src.utils.enum_utils import TaskStatus
from unittest.mock import patch, MagicMock, AsyncMock, ANY, call
from concurrent.futures import Future
import time
import logging
# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Fixtures ---

# 設定測試資料庫
@pytest.fixture(scope="session")
def engine():
    """建立全局測試引擎 (使用共享記憶體模式確保線程安全)"""
    # 使用 URI filename 確保多線程共享同一個記憶體資料庫
    return create_engine('sqlite:///file::memory:?cache=shared')

@pytest.fixture(scope="session")
def tables(engine):
    """建立測試資料表，使用 session scope 減少重複建立和銷毀資料庫結構"""
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="session")
def session_factory(engine):
    """建立會話工廠，使用 session scope 共享會話工廠"""
    return sessionmaker(bind=engine)

@pytest.fixture(scope="function")
def session(session_factory, tables):
    """建立測試會話，並在每次測試前清理相關表格"""
    session = session_factory()
    
    # --- 在每次測試運行前清理數據 --- 
    # 清理順序：依賴性最低的先刪除 (例如 history 依賴 task, task 依賴 crawler)
    session.query(CrawlerTaskHistory).delete()
    session.query(CrawlerTasks).delete()
    session.query(Crawlers).delete()
    session.commit()
    # --------------------------------
    
    try:
        yield session
    finally:
        session.close()

@pytest.fixture(scope="function")
def db_manager(engine, session_factory):
    """創建 DatabaseManager 實例，指向共享引擎和工廠"""
    manager = DatabaseManager() # 依賴環境變數或默認值，但會被下面覆蓋
    manager.engine = engine
    manager.Session = session_factory # 指向 session scope 的工廠
    return manager

@pytest.fixture(scope="function")
def task_executor_service(db_manager):
    """創建任務執行服務實例"""
    # 使用模擬的 db_manager
    service = TaskExecutorService(db_manager=db_manager, max_workers=1) # 使用 1 worker 簡化異步測試
    # Mock ThreadPoolExecutor for better control if needed
    # service.thread_pool = MagicMock(spec=ThreadPoolExecutor)
    yield service
    # Cleanup: ensure thread pool is shutdown if tests might leave threads running
    service.thread_pool.shutdown(wait=False)


@pytest.fixture(scope="function")
def sample_crawler(session: Session):
    """創建一個測試用的爬蟲"""
    crawler = Crawlers(
        crawler_name="TestCrawler",
        base_url="https://test.com",
        is_active=True,
        crawler_type="RSS",
        config_file_name="test_config.json"
    )
    session.add(crawler)
    session.commit()
    return crawler

@pytest.fixture(scope="function")
def sample_task(session: Session, sample_crawler: Crawlers):
    """創建一個測試用的爬蟲任務"""
    task = CrawlerTasks(
        task_name="Test Task",
        crawler_id=sample_crawler.id,
        cron_expression="0 0 * * *",
        is_auto=False, # 預設非自動，避免干擾調度器測試（如果有的話）
        is_active=True,
        task_args={**TASK_ARGS_DEFAULT, "scrape_mode": ScrapeMode.FULL_SCRAPE.value},
        scrape_phase=ScrapePhase.INIT,
        task_status = TaskStatus.INIT,
        retry_count=0
    )
    session.add(task)
    session.commit()
    return task

# --- Mock Crawler ---
class MockCrawler:
    """用於模擬 BaseCrawler 行為的 Mock 類"""
    def __init__(self, success=True, message="成功", articles_count=5, raise_exception=None):
        self.success = success
        self.message = message
        self.articles_count = articles_count
        self.raise_exception = raise_exception
        self.cancelled = False
        self.global_params = {} # For cancellation testing

    def execute_task(self, task_id, task_args):
        logger.info(f"MockCrawler executing task {task_id} with args {task_args}")
        if self.raise_exception:
            raise self.raise_exception
        # 模擬執行時間
        time.sleep(0.1)
        if self.cancelled:
             logger.info(f"MockCrawler task {task_id} was cancelled during execution.")
             # Return structure similar to a cancelled/failed state
             return {
                 'success': False,
                 'message': '任務在執行期間被取消',
                 'articles_count': 0 # Or potentially partial count if supported
             }
        logger.info(f"MockCrawler task {task_id} finished.")
        return {
            'success': self.success,
            'message': self.message,
            'articles_count': self.articles_count
        }

    def cancel_task(self, task_id):
        logger.info(f"MockCrawler cancelling task {task_id}")
        self.cancelled = True
        # Simulate potential data saving based on global_params
        if self.global_params.get('save_partial_results_on_cancel'):
             logger.info("MockCrawler: Pretending to save partial results...")
             # Add logic here if needed
        return True # Indicate cancellation attempt was acknowledged


# --- Test Class ---

class TestTaskExecutorService:
    """測試任務執行服務"""

    @patch('src.crawlers.crawler_factory.CrawlerFactory.get_crawler')
    def test_execute_task_async_success(self, mock_get_crawler, task_executor_service: TaskExecutorService, sample_task: CrawlerTasks, session: Session):
        """測試異步執行任務成功"""
        mock_crawler_instance = MockCrawler(success=True, message="異步成功", articles_count=10)
        mock_get_crawler.return_value = mock_crawler_instance

        task_id = sample_task.id

        # 執行任務
        result = task_executor_service.execute_task(task_id, is_async=True)

        assert result['success'] is True
        assert result['message'] == f'任務 {task_id} 已提交執行'
        assert task_id in task_executor_service.running_tasks

        # 等待異步任務完成 (由於使用實際 ThreadPoolExecutor，需要等待)
        future = task_executor_service.running_tasks[task_id]
        future.result(timeout=5) # 等待結果，設置超時

        # --- 驗證數據庫狀態 ---
        session.expire_all() # 清除緩存，確保從數據庫讀取
        db_task = session.get(CrawlerTasks, task_id)
        assert db_task is not None # 添加斷言
        assert db_task.task_status == TaskStatus.COMPLETED # 任務狀態應為 COMPLETED
        assert db_task.scrape_phase == ScrapePhase.COMPLETED
        assert db_task.last_run_success is True
        assert db_task.last_run_message == "異步成功"
        assert db_task.last_run_at is not None

        history = session.query(CrawlerTaskHistory).filter_by(task_id=task_id).order_by(CrawlerTaskHistory.id.desc()).first()
        assert history is not None
        assert history.task_status == TaskStatus.COMPLETED
        assert history.success is True
        assert history.message == "異步成功"
        assert history.articles_count == 10
        assert history.end_time is not None

        # 驗證清理
        assert task_id not in task_executor_service.running_tasks
        assert task_id not in task_executor_service.running_crawlers

    @patch('src.crawlers.crawler_factory.CrawlerFactory.get_crawler')
    def test_execute_task_async_failure(self, mock_get_crawler, task_executor_service: TaskExecutorService, sample_task: CrawlerTasks, session: Session):
        """測試異步執行任務失敗"""
        mock_crawler_instance = MockCrawler(success=False, message="異步失敗", articles_count=0, raise_exception=ValueError("爬蟲內部錯誤"))
        mock_get_crawler.return_value = mock_crawler_instance

        task_id = sample_task.id
        result = task_executor_service.execute_task(task_id, is_async=True)

        assert result['success'] is True # 提交本身是成功的
        assert task_id in task_executor_service.running_tasks

        # 等待異步任務完成
        future = task_executor_service.running_tasks[task_id]
        # 不再期望 future.result() 拋出異常，因為異常在內部被處理
        # 只需等待其完成即可
        returned_value = future.result(timeout=5) 

        # (可選) 斷言內部函數返回了失敗狀態
        assert returned_value is not None
        assert returned_value['success'] is False
        assert "爬蟲內部錯誤" in returned_value['message']

        # --- 主要驗證：檢查數據庫狀態 --- 
        # 給完成回調一點時間執行 (如果需要的話)
        time.sleep(0.1) 
        session.expire_all()
        db_task = session.get(CrawlerTasks, task_id)
        assert db_task is not None # 添加斷言
        assert db_task.task_status == TaskStatus.FAILED # 任務狀態應為 FAILED
        assert db_task.scrape_phase == ScrapePhase.FAILED
        assert db_task.last_run_success is False
        assert db_task.last_run_message is not None # 添加斷言
        assert "爬蟲內部錯誤" in db_task.last_run_message # 檢查錯誤消息是否記錄
        assert db_task.last_run_at is not None

        history = session.query(CrawlerTaskHistory).filter_by(task_id=task_id).order_by(CrawlerTaskHistory.id.desc()).first()
        assert history is not None
        assert history.task_status == TaskStatus.FAILED
        assert history.success is False
        assert history.message is not None # 添加斷言
        assert "爬蟲內部錯誤" in history.message
        assert history.articles_count == 0
        assert history.end_time is not None

        # 驗證清理
        # _task_completion_callback 應該在 future.result() 之後被調用（或在其內部）
        # 可能需要稍微等待回調執行
        time.sleep(0.1)
        assert task_id not in task_executor_service.running_tasks
        assert task_id not in task_executor_service.running_crawlers

    @patch('src.crawlers.crawler_factory.CrawlerFactory.get_crawler')
    def test_execute_task_sync_success(self, mock_get_crawler, task_executor_service: TaskExecutorService, sample_task: CrawlerTasks, session: Session):
        """測試同步執行任務成功"""
        mock_crawler_instance = MockCrawler(success=True, message="同步成功", articles_count=8)
        mock_get_crawler.return_value = mock_crawler_instance
        task_id = sample_task.id

        # 執行同步任務
        result = task_executor_service.execute_task(task_id, is_async=False)

        assert result['success'] is True
        assert result['message'] == "同步成功"
        assert result['articles_count'] == 8
        assert result['task_status'] == TaskStatus.COMPLETED.value # 同步執行會直接返回最終狀態

        # --- 驗證數據庫狀態 ---
        session.expire_all()
        db_task = session.get(CrawlerTasks, task_id)
        assert db_task is not None # 添加斷言
        assert db_task.task_status.value == TaskStatus.COMPLETED.value
        assert db_task.scrape_phase.value == ScrapePhase.COMPLETED.value
        assert db_task.last_run_success is True
        assert db_task.last_run_message == "同步成功"

        history = session.query(CrawlerTaskHistory).filter_by(task_id=task_id).order_by(CrawlerTaskHistory.id.desc()).first()
        assert history is not None
        assert history.task_status.value == TaskStatus.COMPLETED.value
        assert history.message == "同步成功"
        assert history.end_time is not None

        # 驗證清理 (同步執行不涉及 running_tasks)
        assert task_id not in task_executor_service.running_tasks
        assert task_id not in task_executor_service.running_crawlers # 內部函數執行完畢應清除

    def test_execute_task_already_running(self, task_executor_service: TaskExecutorService, sample_task: CrawlerTasks):
        """測試執行已在運行的任務"""
        task_id = sample_task.id
        # 手動模擬任務正在運行
        task_executor_service.running_tasks[task_id] = Future()

        result = task_executor_service.execute_task(task_id)
        assert result['success'] is False
        assert result['message'] == '任務已在執行中'

        # 清理模擬狀態
        del task_executor_service.running_tasks[task_id]

    def test_execute_task_does_not_exist(self, task_executor_service: TaskExecutorService):
        """測試執行不存在的任務"""
        result = task_executor_service.execute_task(99999)
        assert result['success'] is False
        assert result['message'] == '任務不存在'

    @patch('src.crawlers.crawler_factory.CrawlerFactory.get_crawler')
    def test_cancel_task_success(self, mock_get_crawler, task_executor_service: TaskExecutorService, sample_task: CrawlerTasks, session: Session):
        """測試成功取消正在執行的任務"""
        mock_crawler_instance = MockCrawler()
        mock_get_crawler.return_value = mock_crawler_instance

        task_id = sample_task.id

        # 模擬啟動異步任務
        with patch.object(task_executor_service.thread_pool, 'submit', return_value=Future()) as mock_submit:
            task_executor_service.execute_task(task_id, is_async=True)
            mock_submit.assert_called_once()
            # 手動添加爬蟲實例，因為 submit 被 mock 了
            task_executor_service.running_crawlers[task_id] = mock_crawler_instance
            # 手動添加 future，因為 submit 被 mock 了
            mock_future = mock_submit.return_value
            task_executor_service.running_tasks[task_id] = mock_future

        # 模擬 Future 和 Crawler 的 cancel 方法
        mock_future.cancel = MagicMock(return_value=True) # 假設線程取消成功
        mock_crawler_instance.cancel_task = MagicMock(return_value=True) # 假設爬蟲取消成功

        # 執行取消
        cancel_result = task_executor_service.cancel_task(task_id)

        assert cancel_result['success'] is True
        assert cancel_result['message'] == f'任務 {task_id} 已取消'
        mock_future.cancel.assert_called_once()
        mock_crawler_instance.cancel_task.assert_called_once_with(task_id)

        # --- 驗證數據庫狀態 ---
        session.expire_all()
        db_task = session.get(CrawlerTasks, task_id)
        assert db_task is not None # 添加斷言
        assert db_task.task_status == TaskStatus.CANCELLED
        assert db_task.scrape_phase == ScrapePhase.CANCELLED
        assert db_task.last_run_success is False # 取消通常視為不成功
        assert db_task.last_run_message == '任務已被使用者取消'

        history = session.query(CrawlerTaskHistory).filter_by(task_id=task_id).order_by(CrawlerTaskHistory.id.desc()).first()
        assert history is not None
        assert history.task_status == TaskStatus.CANCELLED
        assert history.message is not None
        assert "任務已被使用者取消" in history.message
        assert history.end_time is not None # 取消時應記錄結束時間

        # 驗證清理
        assert task_id not in task_executor_service.running_tasks
        assert task_id not in task_executor_service.running_crawlers

    def test_cancel_task_not_running(self, task_executor_service: TaskExecutorService, sample_task: CrawlerTasks, session: Session):
        """測試取消未在執行的任務"""
        task_id = sample_task.id
        # 確保任務不在 running_tasks 中
        assert task_id not in task_executor_service.running_tasks

        cancel_result = task_executor_service.cancel_task(task_id)

        # 取決於實現，如果任務不在運行，cancel 可能返回成功（無事可做）或失敗
        # 當前的實現，如果 task_id 不在 running_tasks 或 running_crawlers，會認為無法取消
        assert cancel_result['success'] is False
        assert "無法取消任務" in cancel_result['message']

        # 驗證數據庫狀態未改變
        session.expire_all()
        db_task = session.get(CrawlerTasks, task_id)
        assert db_task is not None # 添加斷言
        assert db_task.task_status != TaskStatus.CANCELLED
        assert db_task.scrape_phase != ScrapePhase.CANCELLED

    def test_get_task_status_running(self, task_executor_service: TaskExecutorService, sample_task: CrawlerTasks):
        """測試獲取正在運行任務的狀態 (從內存)"""
        task_id = sample_task.id
        # 模擬任務正在運行
        task_executor_service.running_tasks[task_id] = Future()

        status_result = task_executor_service.get_task_status(task_id)
        assert status_result['success'] is True
        assert status_result['task_status'] == TaskStatus.RUNNING.value # 確認返回 Enum 值
        assert f'任務 {task_id} 正在執行中' in status_result['message']

        # 清理
        del task_executor_service.running_tasks[task_id]

    def test_get_task_status_completed_from_db(self, task_executor_service: TaskExecutorService, sample_task: CrawlerTasks, session: Session):
        """測試獲取已完成任務的狀態 (從DB)"""
        task_id = sample_task.id
        now = datetime.now(timezone.utc)

        # 確保任務不在運行
        assert task_id not in task_executor_service.running_tasks

        # 更新任務狀態和創建歷史記錄
        task = session.get(CrawlerTasks, task_id)
        assert task is not None # 添加斷言
        task.task_status = TaskStatus.COMPLETED
        task.scrape_phase = ScrapePhase.COMPLETED
        task.last_run_success = True
        task.last_run_message = "DB 完成"
        task.last_run_at = now
        session.add(task)

        history = CrawlerTaskHistory(
            task_id=task_id,
            start_time=now - timedelta(minutes=5),
            end_time=now,
            success=True,
            message="DB 完成歷史",
            task_status=TaskStatus.COMPLETED,
            articles_count=15
        )
        session.add(history)
        session.commit()

        status_result = task_executor_service.get_task_status(task_id)

        assert status_result['success'] is True
        # get_task_status 優先讀取 Task 表的狀態，除非歷史記錄有明確的結束狀態
        assert status_result['task_status'] == TaskStatus.COMPLETED.value # 應該從 history 推斷出 COMPLETED
        assert status_result['scrape_phase'] == ScrapePhase.COMPLETED.value # 應該從 task 表讀取
        assert status_result['progress'] == 100 # 有 end_time 應該是 100
        assert "DB 完成歷史" in status_result['message']
        assert status_result['task'].id == task_id

    def test_get_running_tasks(self, task_executor_service: TaskExecutorService):
        """測試獲取所有正在運行的任務"""
        task_executor_service.running_tasks = {1: Future(), 3: Future(), 5: Future()}

        result = task_executor_service.get_running_tasks()
        assert result['success'] is True
        assert sorted(result['running_tasks']) == [1, 3, 5]

        task_executor_service.running_tasks = {} # 清理

    @patch('src.services.task_executor_service.TaskExecutorService._execute_task_internal', return_value={'success': True, 'message': '模擬執行'})
    def test_specialized_execution_methods(self, mock_execute_internal, task_executor_service: TaskExecutorService, sample_task: CrawlerTasks, session: Session):
        """測試特定執行方法 (如 collect_links_only) 是否正確調用 execute_task"""
        task_id = sample_task.id

        # 需要 patch execute_task 來檢查 kwargs，而不是 internal
        with patch.object(task_executor_service, 'execute_task', wraps=task_executor_service.execute_task) as mock_execute_task:

            # --- collect_links_only ---
            result_links = task_executor_service.collect_links_only(task_id, is_async=False) # Use sync for easier check
            # 驗證 execute_task 被調用，並檢查 kwargs
            mock_execute_task.assert_called_with(task_id, False, operation_type='collect_links_only', scrape_mode='links_only')

            # --- fetch_content_only ---
            task_executor_service.execute_task.reset_mock() # 重置 mock
            result_content = task_executor_service.fetch_content_only(task_id, is_async=False)
            mock_execute_task.assert_called_with(task_id, False, operation_type='fetch_content_only', scrape_mode='content_only')

            # --- fetch_full_article ---
            task_executor_service.execute_task.reset_mock() # 重置 mock
            result_full = task_executor_service.fetch_full_article(task_id, is_async=False)
            # full_article 應該沒有額外 kwargs
            mock_execute_task.assert_called_with(task_id, False, operation_type='fetch_full_article', scrape_mode='full_scrape') 


    @patch('src.crawlers.crawler_factory.CrawlerFactory.get_crawler')
    def test_test_crawler(self, mock_get_crawler, task_executor_service: TaskExecutorService):
        """測試 test_crawler 方法"""
        mock_crawler_instance = MockCrawler(success=True, message="測試成功", articles_count=3)
        mock_crawler_instance.execute_task = MagicMock(return_value={
            'success': True, 'message': '測試成功', 'articles_count': 3
        })
        mock_get_crawler.return_value = mock_crawler_instance
        crawler_name = "MyTestCrawler"

        result = task_executor_service.test_crawler(crawler_name, test_params={"max_pages": 5, "num_articles": 10})

        assert result['success'] is True
        assert result['message'] == '測試成功' # 應該是來自 crawler 的 message
        assert 'result' in result
        assert result['result']['articles_count'] == 3

        # 驗證 crawler 的 execute_task 被調用，且參數被強制修改
        mock_crawler_instance.execute_task.assert_called_once()
        call_args = mock_crawler_instance.execute_task.call_args[0] # 獲取位置參數
        passed_task_args = call_args[1] # 第二個參數是 task_args

        assert passed_task_args['is_test'] is True
        assert passed_task_args['scrape_mode'] == 'links_only'
        assert passed_task_args['max_pages'] == 1 # 被強制設為 1
        assert passed_task_args['num_articles'] == 5 # 被強制設為 5
        assert passed_task_args['save_to_csv'] is False
        assert passed_task_args['save_to_database'] is False


    def test_update_task_last_run(self, task_executor_service: TaskExecutorService, sample_task: CrawlerTasks, session: Session):
        """測試更新任務最後執行狀態"""
        task_id = sample_task.id
        message = "最後運行成功"
        initial_time = sample_task.last_run_at

        result = task_executor_service.update_task_last_run(task_id, True, message)

        assert result['success'] is True
        assert result['message'] == '任務最後執行狀態更新成功'

        session.expire_all()
        db_task = session.get(CrawlerTasks, task_id)
        assert db_task is not None # 添加斷言
        assert db_task.last_run_success is True
        assert db_task.last_run_message == message
        assert db_task.last_run_at is not None
        assert db_task.last_run_at > initial_time if initial_time else db_task.last_run_at is not None

        # 測試失敗狀態
        message_fail = "最後運行失敗"
        result_fail = task_executor_service.update_task_last_run(task_id, False, message_fail)
        assert result_fail['success'] is True

        session.expire_all()
        db_task_fail = session.get(CrawlerTasks, task_id)
        assert db_task_fail is not None # 添加斷言
        assert db_task_fail.last_run_success is False
        assert db_task_fail.last_run_message == message_fail
