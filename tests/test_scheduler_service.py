import pytest
from datetime import datetime, timezone, timedelta
import pytz
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, Session
from unittest.mock import patch, MagicMock, ANY

from src.models.base_model import Base
from src.models.crawler_tasks_model import CrawlerTasks, ScrapePhase, ScrapeMode
from src.models.crawlers_model import Crawlers
from src.database.database_manager import DatabaseManager
from src.services.scheduler_service import SchedulerService
from src.services.task_executor_service import TaskExecutorService
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.utils.enum_utils import TaskStatus
import logging

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Fixtures ---

@pytest.fixture(scope="session")
def engine():
    """建立全局測試引擎 (使用共享記憶體模式確保線程安全)"""
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
    
    # 清理相關表格
    try:
        # 嘗試刪除 apscheduler_jobs，如果表格不存在則忽略
        session.execute(text("DELETE FROM apscheduler_jobs")) 
        session.commit() # Commit the delete if successful
    except OperationalError as e:
        # 檢查錯誤是否真的是 "no such table"
        if "no such table" in str(e):
            logger.warning("Table 'apscheduler_jobs' not found for deletion, skipping.")
            session.rollback() # Rollback any potential transaction start
        else:
            raise # 如果是其他 OperationalError，重新拋出
    except Exception as e:
        # 捕獲其他可能的異常並回滾
        logger.error(f"Error during apscheduler_jobs cleanup: {e}", exc_info=True)
        session.rollback()
        raise

    # 清理你自己的模型表格 (這些應該總是存在)
    session.query(CrawlerTasks).delete()
    session.query(Crawlers).delete()
    session.commit() 
    
    try:
        yield session
    finally:
        session.close()

@pytest.fixture(scope="function")
def db_manager(engine, session_factory):
    """創建 DatabaseManager 實例，指向共享引擎和工廠"""
    manager = DatabaseManager()
    manager.engine = engine
    manager.Session = session_factory
    manager.db_url = 'sqlite:///file::memory:?cache=shared'
    return manager

@pytest.fixture(scope="function")
def task_executor_service(db_manager):
    """創建任務執行服務實例，用於傳入排程服務"""
    service = TaskExecutorService(db_manager=db_manager)
    return service

@pytest.fixture(scope="function")
def scheduler_service_with_mocks(db_manager, task_executor_service):
    """創建排程服務實例並返回服務和 mock 排程器"""
    with patch('apscheduler.schedulers.background.BackgroundScheduler') as mock_scheduler_class:
        # 創建模擬的 scheduler 實例
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler
        
        # 設置 get_jobs 返回空列表
        mock_scheduler.get_jobs.return_value = []
        
        # 創建排程服務
        service = SchedulerService(task_executor_service, db_manager)
        
        yield service, mock_scheduler
        
        # 確保每次測試後調度器被關閉
        if service.scheduler_status['running']:
            service.stop_scheduler()

@pytest.fixture(scope="function")
def sample_crawler(session):
    """創建一個測試用的爬蟲"""
    crawler = Crawlers(
        crawler_name="TestCrawler",
        module_name="test_module",
        base_url="https://test.com",
        is_active=True,
        crawler_type="RSS",
        config_file_name="test_config.json"
    )
    session.add(crawler)
    session.commit()
    return crawler

@pytest.fixture(scope="function")
def sample_tasks(session, sample_crawler):
    """創建多個測試用的爬蟲任務"""
    tasks = []
    
    # 自動執行的任務
    auto_task = CrawlerTasks(
        task_name="Auto Task",
        crawler_id=sample_crawler.id,
        cron_expression="0 */6 * * *",  # 每6小時執行一次
        is_auto=True,
        is_active=True,
        is_scheduled=False,  # 初始未排程
        task_args={"scrape_mode": ScrapeMode.FULL_SCRAPE.value},
        scrape_phase=ScrapePhase.INIT,
        task_status=TaskStatus.INIT,
        retry_count=0
    )
    
    # 非自動執行的任務
    manual_task = CrawlerTasks(
        task_name="Manual Task",
        crawler_id=sample_crawler.id,
        cron_expression="0 0 * * *",  # 每天午夜執行
        is_auto=False,  # 非自動執行
        is_active=True,
        is_scheduled=False,
        task_args={"scrape_mode": ScrapeMode.LINKS_ONLY.value},
        scrape_phase=ScrapePhase.INIT,
        task_status=TaskStatus.INIT,
        retry_count=0
    )
    
    # 已排程的任務
    scheduled_task = CrawlerTasks(
        task_name="Scheduled Task",
        crawler_id=sample_crawler.id,
        cron_expression="*/30 * * * *",  # 每30分鐘執行
        is_auto=True,
        is_active=True,
        is_scheduled=True,  # 已排程
        task_args={"scrape_mode": ScrapeMode.CONTENT_ONLY.value},
        scrape_phase=ScrapePhase.INIT,
        task_status=TaskStatus.INIT,
        retry_count=0
    )
    
    session.add_all([auto_task, manual_task, scheduled_task])
    session.commit()
    
    tasks = [auto_task, manual_task, scheduled_task]
    return tasks

# --- Tests ---

class TestSchedulerService:
    """測試排程服務"""
    
    @pytest.fixture(scope="function")
    def scheduler_service_for_init(self, db_manager, task_executor_service):
        """創建排程服務實例 (僅用於 test_init)"""
        with patch('apscheduler.schedulers.background.BackgroundScheduler') as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler
            mock_scheduler.get_jobs.return_value = []
            service = SchedulerService(task_executor_service, db_manager)
            yield service
            if service.scheduler_status['running']:
                 service.stop_scheduler()

    def test_init(self, scheduler_service_for_init, db_manager):
        """測試排程服務初始化"""
        scheduler_service = scheduler_service_for_init
        assert scheduler_service.db_manager is db_manager
        assert scheduler_service.task_executor_service is not None
        assert scheduler_service.cron_scheduler is not None
        assert scheduler_service.scheduler_status['running'] is False
        assert scheduler_service.scheduler_status['job_count'] == 0
    
    def test_start_scheduler(self, scheduler_service_with_mocks, sample_tasks, session):
        """測試啟動排程器"""
        scheduler_service, _ = scheduler_service_with_mocks # 我們不再需要 fixture 返回的 mock
        
        # 直接 Mock service 實例上的 cron_scheduler.start
        with patch.object(scheduler_service, '_schedule_task', return_value=True), \
             patch.object(scheduler_service.cron_scheduler, 'start') as mock_start_on_instance:
            
            result = scheduler_service.start_scheduler()
            
        # --- 加入診斷訊息 ---
        print(f"DEBUG: Actual result from start_scheduler: {result}") 
        # --------------------
        
        # 驗證結果
        assert result['success'] is True
        assert "調度器已啟動" in result['message']
        assert scheduler_service.scheduler_status['running'] is True
        
        # 驗證資料庫狀態更新
        session.expire_all()
        auto_task = session.query(CrawlerTasks).filter_by(task_name="Auto Task").first()
        manual_task = session.query(CrawlerTasks).filter_by(task_name="Manual Task").first()
        
        assert auto_task.is_scheduled is True
        assert manual_task.is_scheduled is False
        
        # --- 加入診斷訊息 ---
        # 檢查 service 實例上的 mock 是否被呼叫
        print(f"DEBUG: Calls on service.cron_scheduler.start mock: {mock_start_on_instance.mock_calls}")
        # --------------------
        
        # 驗證調度器方法被調用 (在實例的 mock 上斷言)
        mock_start_on_instance.assert_called_once()
        
    def test_stop_scheduler(self, scheduler_service_with_mocks):
        """測試停止排程器"""
        scheduler_service, _ = scheduler_service_with_mocks
        # 設置排程器為運行狀態
        scheduler_service.scheduler_status['running'] = True
        scheduler_service.scheduler_status['job_count'] = 5
        
        # 直接 mock pause 方法
        with patch.object(scheduler_service.cron_scheduler, 'pause') as mock_pause_on_instance:
            result = scheduler_service.stop_scheduler()
        
        assert result['success'] is True
        assert "調度器已暫停" in result['message']
        assert scheduler_service.scheduler_status['running'] is False
        
        # 驗證調度器方法被調用
        mock_pause_on_instance.assert_called_once()
    
    def test_schedule_task(self, scheduler_service_with_mocks, sample_tasks):
        """測試設定任務排程"""
        scheduler_service, _ = scheduler_service_with_mocks
        auto_task = sample_tasks[0]
        
        # 直接 mock add_job 方法
        with patch.object(scheduler_service.cron_scheduler, 'add_job') as mock_add_job_on_instance:
            result = scheduler_service._schedule_task(auto_task)
        
        assert result is True
        mock_add_job_on_instance.assert_called_once()
        
        # 重置 mock 以進行下一個測試
        mock_add_job_on_instance.reset_mock()

        # 測試無 cron 表達式的情況
        auto_task.cron_expression = None
        # 不需要再次 patch，因為 add_job 不應被調用
        result = scheduler_service._schedule_task(auto_task)
        
        assert result is False
        mock_add_job_on_instance.assert_not_called()
    
    @patch('src.database.crawler_tasks_repository.CrawlerTasksRepository.get_by_id')
    def test_trigger_task(self, mock_get_by_id, scheduler_service_with_mocks, sample_tasks):
        """測試觸發任務執行"""
        scheduler_service, _ = scheduler_service_with_mocks
        auto_task = sample_tasks[0]
        mock_get_by_id.return_value = auto_task
        
        # Mock task_executor_service.execute_task
        with patch.object(scheduler_service.task_executor_service, 'execute_task') as mock_execute:
            scheduler_service._trigger_task(auto_task.id, auto_task.task_args)
            mock_execute.assert_called_once_with(auto_task.id)
        
        # 測試任務不存在的情況
        mock_get_by_id.return_value = None
        with patch.object(scheduler_service.task_executor_service, 'execute_task') as mock_execute:
            scheduler_service._trigger_task(999)
            mock_execute.assert_not_called()
        
        # 測試非自動執行的情況
        manual_task = sample_tasks[1]
        mock_get_by_id.return_value = manual_task
        with patch.object(scheduler_service.task_executor_service, 'execute_task') as mock_execute:
            scheduler_service._trigger_task(manual_task.id, manual_task.task_args)
            mock_execute.assert_not_called()
    
    def test_add_or_update_task_to_scheduler(self, scheduler_service_with_mocks, sample_tasks, session):
        """測試新增或更新任務到排程器"""
        scheduler_service, _ = scheduler_service_with_mocks # Fixture 確保類被 patch
        auto_task = sample_tasks[0]
        job_id = f"task_{auto_task.id}"

        # --- 測試新增任務 ---
        # Mock get_job on instance to return None for add case
        with patch.object(scheduler_service, '_schedule_task', return_value=True) as mock_schedule_add, \
             patch.object(scheduler_service.cron_scheduler, 'get_job', return_value=None) as mock_get_job_add:

            result_add = scheduler_service.add_or_update_task_to_scheduler(auto_task, session)

        assert result_add['success'] is True
        assert result_add['added_count'] == 1
        assert result_add['updated_count'] == 0
        mock_get_job_add.assert_called_once_with(job_id)
        mock_schedule_add.assert_called_once_with(auto_task)

        # 驗證資料庫狀態
        session.expire_all()
        updated_task_add = session.query(CrawlerTasks).filter_by(id=auto_task.id).first()
        assert updated_task_add.is_scheduled is True

        # --- 測試更新任務 ---
        # 模擬任務已在排程器中
        mock_job_exists = MagicMock()
        mock_job_exists.trigger = MagicMock()
        mock_job_exists.trigger.expression = "0 0 * * *"  # Different expression
        mock_job_exists.kwargs = {'update_at': datetime.now(timezone.utc) - timedelta(days=1)} # Different update_at

        # Mock get_job, remove_job, and _schedule_task on the instance for update case
        with patch.object(scheduler_service, '_schedule_task', return_value=True) as mock_schedule_update, \
             patch.object(scheduler_service.cron_scheduler, 'get_job', return_value=mock_job_exists) as mock_get_job_update, \
             patch.object(scheduler_service.cron_scheduler, 'remove_job') as mock_remove_job_update:

            result_update = scheduler_service.add_or_update_task_to_scheduler(auto_task, session)

        assert result_update['success'] is True
        assert result_update['added_count'] == 0
        assert result_update['updated_count'] == 1 # 預期 update count 為 1
        mock_get_job_update.assert_called_once_with(job_id)
        mock_remove_job_update.assert_called_once_with(job_id) # 驗證 remove 被呼叫
        mock_schedule_update.assert_called_once_with(auto_task) # 驗證 schedule 被呼叫

        # --- 測試排程失敗的情況 ---
        # Mock get_job returns None again, _schedule_task returns False
        with patch.object(scheduler_service, '_schedule_task', return_value=False) as mock_schedule_fail, \
             patch.object(scheduler_service.cron_scheduler, 'get_job', return_value=None) as mock_get_job_fail:

            result_fail = scheduler_service.add_or_update_task_to_scheduler(auto_task, session)

        assert result_fail['success'] is False
        mock_get_job_fail.assert_called_once_with(job_id)
        mock_schedule_fail.assert_called_once_with(auto_task)
    
    def test_remove_task_from_scheduler(self, scheduler_service_with_mocks, sample_tasks, session):
        """測試從排程器移除任務"""
        scheduler_service, _ = scheduler_service_with_mocks
        scheduled_task = sample_tasks[2]  # 使用已排程的任務
        
        with patch.object(scheduler_service.cron_scheduler, 'remove_job') as mock_remove_job_on_instance:
            result = scheduler_service.remove_task_from_scheduler(scheduled_task.id)
        
        assert result['success'] is True
        assert f"從排程移除任務 {scheduled_task.id}" in result['message']
        
        session.expire_all()
        updated_task = session.query(CrawlerTasks).filter_by(id=scheduled_task.id).first()
        assert updated_task.is_scheduled is False
        
        mock_remove_job_on_instance.assert_called_once_with(f"task_{scheduled_task.id}")
    
    def test_reload_scheduler(self, scheduler_service_with_mocks, sample_tasks, session):
        """測試重新載入排程器"""
        scheduler_service, _ = scheduler_service_with_mocks
        scheduler_service.scheduler_status['running'] = True

        # 從 sample_tasks 中明確找出預期會被處理的 auto tasks
        auto_task = next(t for t in sample_tasks if t.task_name == "Auto Task")
        scheduled_task = next(t for t in sample_tasks if t.task_name == "Scheduled Task")

        mock_job1 = MagicMock()
        mock_job1.id = f"task_{auto_task.id}"
        mock_job2 = MagicMock()
        mock_job2.id = f"task_999"

        # 用於記錄被呼叫時的 task ID
        recorded_task_ids = []

        # 定義 side_effect 函數
        def add_update_side_effect(task, session_arg):
            # 記錄 task ID
            recorded_task_ids.append(task.id)
            # 返回 mock 預期回傳的值
            return {'success': True, 'added_count': 1, 'updated_count': 1}

        # Mock get_jobs, remove_job, 和 add_or_update (使用 side_effect)
        with patch.object(scheduler_service.cron_scheduler, 'get_jobs', return_value=[mock_job1, mock_job2]) as mock_get_jobs, \
             patch.object(scheduler_service.cron_scheduler, 'remove_job') as mock_remove_job, \
             patch.object(scheduler_service, 'add_or_update_task_to_scheduler',
                          side_effect=add_update_side_effect) as mock_add_update: # <--- 使用 side_effect

            result = scheduler_service.reload_scheduler()

        assert result['success'] is True
        assert "調度器已重載" in result['message']

        # 驗證 remove_job 被呼叫
        mock_remove_job.assert_called_with(f"task_999")

        # 驗證 add_or_update 被呼叫了兩次
        assert mock_add_update.call_count == 2

        # 驗證記錄下來的 Task ID 集合是否符合預期
        expected_task_ids_called = {auto_task.id, scheduled_task.id}
        assert set(recorded_task_ids) == expected_task_ids_called # <--- 驗證記錄的 ID

        # (可選) 驗證每次呼叫的 session 參數 (如果需要)
        actual_calls_args = mock_add_update.call_args_list
        assert all(isinstance(call[0][1], Session) for call in actual_calls_args) # 檢查第二個參數是否為 Session
        assert all(call[1] == {} for call in actual_calls_args) # 確保沒有 kwargs


        # 測試非運行狀態
        scheduler_service.scheduler_status['running'] = False
        result = scheduler_service.reload_scheduler()
        assert result['success'] is False
        assert "調度器未運行" in result['message']
    
    def test_get_scheduler_status(self, scheduler_service_with_mocks):
        """測試獲取排程器狀態"""
        scheduler_service, _ = scheduler_service_with_mocks
        now = datetime.now(timezone.utc)
        scheduler_service.scheduler_status = {
            'running': True, 'job_count': 0, 'last_start_time': now, 'last_shutdown_time': None
        }
        # Mock get_jobs on the instance
        with patch.object(scheduler_service.cron_scheduler, 'get_jobs', return_value=[MagicMock(), MagicMock()]) as mock_get_jobs:
             result = scheduler_service.get_scheduler_status()
        
        assert result['success'] is True
        assert result['message'] == '獲取調度器狀態成功'
        assert result['status']['running'] is True
        assert result['status']['job_count'] == 2
        assert result['status']['last_start_time'] == now
        mock_get_jobs.assert_called_once() # Verify get_jobs was called

    def test_get_persisted_jobs_info(self, scheduler_service_with_mocks, sample_tasks, session):
        """測試獲取持久化任務的詳細信息"""
        scheduler_service, _ = scheduler_service_with_mocks
        auto_task = sample_tasks[0]
        mock_job = MagicMock()
        mock_job.id = f"task_{auto_task.id}"
        mock_job.name = auto_task.task_name
        mock_job.next_run_time = datetime.now(timezone.utc)
        mock_job.trigger = MagicMock()
        mock_job.trigger.__str__.return_value = "CronTrigger(...)"
        mock_job.trigger.expression = auto_task.cron_expression
        mock_job.misfire_grace_time = 3600
        
        # Mock get_jobs on the instance
        with patch.object(scheduler_service.cron_scheduler, 'get_jobs', return_value=[mock_job]) as mock_get_jobs:
            result = scheduler_service.get_persisted_jobs_info()

        assert result['success'] is True
        assert len(result['jobs']) == 1
        job_info = result['jobs'][0]
        assert job_info['id'] == f"task_{auto_task.id}"
        assert job_info['task_id'] == auto_task.id
        assert job_info['exists_in_db'] is True
        assert job_info['task_name'] == auto_task.task_name
        assert job_info['is_auto'] == auto_task.is_auto
        assert job_info['is_scheduled_in_db'] == auto_task.is_scheduled # Check DB state too
        assert job_info['cron_expression'] == auto_task.cron_expression
        mock_get_jobs.assert_called_once() # Verify get_jobs was called
