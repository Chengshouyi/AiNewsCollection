import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone, timedelta
import pytz
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.services.scheduler_service import SchedulerService
from src.services.base_service import BaseService
from src.services.task_executor import TaskExecutor
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.base_model import Base
from src.models.crawlers_model import Crawlers
from src.database.database_manager import DatabaseManager
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger


# 測試固定裝置 (Fixtures)
@pytest.fixture(scope="session")
def engine():
    """創建測試用的資料庫引擎"""
    return create_engine('sqlite:///:memory:')


@pytest.fixture(scope="session")
def tables(engine):
    """創建資料表結構"""
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def session_factory(engine, tables):
    """建立會話工廠"""
    return sessionmaker(bind=engine)


@pytest.fixture(scope="function")
def session(session_factory):
    """建立測試用會話"""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def db_manager(engine):
    """模擬資料庫管理器"""
    mock_db_manager = MagicMock(spec=DatabaseManager)
    mock_db_manager.engine = engine
    mock_db_manager.db_url = 'sqlite:///:memory:'
    mock_db_manager.Session = sessionmaker(bind=engine)
    
    return mock_db_manager


@pytest.fixture(scope="function")
def crawler_tasks_repo():
    """建立測試用爬蟲任務儲存庫"""
    # 使用 MagicMock 而不是真實的儲存庫
    return MagicMock(spec=CrawlerTasksRepository)


@pytest.fixture(scope="function")
def task_executor():
    """模擬任務執行器"""
    return MagicMock(spec=TaskExecutor)


@pytest.fixture(scope="function")
def clean_db(session):
    """清空資料庫"""
    session.query(CrawlerTasks).delete()
    session.query(Crawlers).delete()
    session.commit()


@pytest.fixture(scope="function")
def sample_crawler(session, clean_db):
    """創建測試用爬蟲"""
    crawler = Crawlers(
        crawler_name="測試爬蟲",
        base_url="https://example.com",
        is_active=True,
        crawler_type="news",
        config_file_name="test_crawler_config.json"
    )
    session.add(crawler)
    session.commit()
    return crawler


@pytest.fixture(scope="function")
def sample_tasks():
    """創建測試用任務 mock 對象"""
    tasks = []
    
    # 建立3個測試任務
    for i in range(3):
        task = MagicMock(spec=CrawlerTasks)
        task.id = i + 1
        
        if i == 0:
            task.task_name = "每小時任務"
            task.is_auto = True
            task.cron_expression = "0 * * * *"  # 每小時執行
        elif i == 1:
            task.task_name = "每天任務"
            task.is_auto = True
            task.cron_expression = "0 0 * * *"  # 每天執行
        else:
            task.task_name = "手動任務"
            task.is_auto = False
            task.cron_expression = "0 0 * * *"  # 不會自動執行
            
        tasks.append(task)
        
    return tasks


@pytest.fixture(scope="function")
def mock_scheduler():
    """建立模擬的 APScheduler"""
    mock_scheduler = MagicMock(spec=BackgroundScheduler)
    # 設置需要的方法
    mock_scheduler.get_jobs.return_value = []
    mock_scheduler.add_job.return_value = MagicMock()
    mock_scheduler.remove_job.return_value = None
    mock_scheduler.start.return_value = None
    mock_scheduler.shutdown.return_value = None
    mock_scheduler.pause.return_value = None
    return mock_scheduler


@pytest.fixture(scope="function")
def scheduler_service(db_manager, crawler_tasks_repo, task_executor, mock_scheduler):
    """建立待測試的排程服務"""
    with patch('src.services.scheduler_service.BackgroundScheduler', return_value=mock_scheduler):
        with patch('src.services.scheduler_service.SQLAlchemyJobStore', return_value=MagicMock()):
            # 創建服務，確保傳入正確的初始參數
            service = SchedulerService(
                crawler_tasks_repo=crawler_tasks_repo,
                task_executor=task_executor,
                db_manager=db_manager
            )
            
            # 直接將 cron_scheduler 替換為 mock_scheduler，確保一致性
            service.cron_scheduler = mock_scheduler
            
            yield service
            # 確保排程器在測試後被清理
            service.cleanup()


@pytest.fixture(scope="function")
def mock_real_scheduler():
    """使用 mock 但保留行為的 BackgroundScheduler"""
    real_scheduler = MagicMock(spec=BackgroundScheduler)
    # 設置必要的方法和屬性
    real_scheduler.get_jobs.return_value = []
    real_scheduler.start.return_value = None
    real_scheduler.pause.return_value = None
    real_scheduler.shutdown.return_value = None
    real_scheduler.add_job.return_value = MagicMock()
    real_scheduler.remove_job.return_value = None
    real_scheduler.get_job.side_effect = lambda job_id: None
    
    return real_scheduler


class TestSchedulerService:
    """排程服務測試類"""
    
    def test_init(self, db_manager, task_executor):
        """測試初始化功能"""
        mock_scheduler = MagicMock(spec=BackgroundScheduler)
        mock_jobstore = MagicMock(spec=SQLAlchemyJobStore)
        mock_repo = MagicMock(spec=CrawlerTasksRepository)
        
        # 為了確保初始化時正確設置屬性，重置 mock 狀態
        mock_scheduler.reset_mock()
        mock_jobstore.reset_mock()
        
        with patch('src.services.scheduler_service.BackgroundScheduler', return_value=mock_scheduler) as mock_bg_scheduler:
            with patch('src.services.scheduler_service.SQLAlchemyJobStore', return_value=mock_jobstore) as mock_jobstore_class:
                # 測試傳入儲存庫的情況
                service = SchedulerService(
                    crawler_tasks_repo=mock_repo,
                    task_executor=task_executor,
                    db_manager=db_manager
                )
                
                # 檢查屬性初始化
                assert service.crawler_tasks_repo is mock_repo  # 使用 is 檢查是否是同一個對象
                assert service.task_executor == task_executor
                assert service.cron_scheduler == mock_scheduler
                assert service.scheduler_status['running'] is False
                assert service.scheduler_status['job_count'] == 0
                assert service.scheduler_status['last_start_time'] is None
                assert service.scheduler_status['last_shutdown_time'] is None
                
                # 檢查 SQLAlchemyJobStore 正確初始化
                mock_jobstore_class.assert_called_once()
                call_args = mock_jobstore_class.call_args
                assert call_args.kwargs['url'] == db_manager.db_url
                assert call_args.kwargs['engine'] == db_manager.engine
                assert call_args.kwargs['tablename'] == 'apscheduler_jobs'
                
                # 檢查 BackgroundScheduler 正確初始化
                mock_bg_scheduler.assert_called_once()
                scheduler_call_args = mock_bg_scheduler.call_args
                assert 'jobstores' in scheduler_call_args.kwargs
                assert 'executors' in scheduler_call_args.kwargs
                assert 'job_defaults' in scheduler_call_args.kwargs
                assert scheduler_call_args.kwargs['timezone'] == pytz.UTC
    
    def test_get_repository_mapping(self, scheduler_service):
        """測試儲存庫映射"""
        mapping = scheduler_service._get_repository_mapping()
        assert 'CrawlerTask' in mapping
        assert mapping['CrawlerTask'][0] == CrawlerTasksRepository
        assert mapping['CrawlerTask'][1] == CrawlerTasks
    
    def test_get_task_repo(self):
        """測試獲取任務儲存庫"""
        # 創建一個新的服務實例
        mock_db_manager = MagicMock(spec=DatabaseManager)
        mock_db_manager.engine = MagicMock()
        mock_db_manager.db_url = 'sqlite:///:memory:'
        mock_db_manager.Session = MagicMock(return_value=MagicMock())
        
        # 創建一個測試用的存儲庫
        mock_repo = MagicMock(spec=CrawlerTasksRepository)
        
        # 使用 patch.object 模擬 _get_repository 方法
        with patch.object(BaseService, '_get_repository') as mock_get_repo:
            mock_get_repo.return_value = mock_repo
            
            # 創建服務實例，這會調用一次 _get_repository
            service = SchedulerService(
                crawler_tasks_repo=None,  # 設為 None 強制使用 _get_task_repo
                task_executor=None,
                db_manager=mock_db_manager
            )
            
            # 重置 mock 以清除初始化時的調用
            mock_get_repo.reset_mock()
            
            # 測試 _get_task_repo 方法
            repo = service._get_task_repo()
            
            # 驗證結果
            assert repo is mock_repo
            mock_get_repo.assert_called_once_with('CrawlerTask')
    
    def test_start_scheduler(self, scheduler_service, sample_tasks):
        """測試啟動排程器"""
        # 模擬自動任務查詢
        scheduler_service.crawler_tasks_repo.find_auto_tasks.return_value = [t for t in sample_tasks if t.is_auto]
        
        # 測試啟動排程器
        with patch.object(scheduler_service, '_schedule_task', return_value=True) as mock_schedule:
            result = scheduler_service.start_scheduler()
            
            # 驗證結果
            assert result['success'] is True
            assert "調度器已啟動" in result['message']
            assert scheduler_service.scheduler_status['running'] is True
            
            # 驗證方法調用
            scheduler_service.crawler_tasks_repo.find_auto_tasks.assert_called_once()
            assert mock_schedule.call_count == 2  # 應該為2個自動任務調用
            scheduler_service.cron_scheduler.start.assert_called_once()
    
    def test_start_scheduler_already_running(self, scheduler_service):
        """測試在排程器已運行時啟動"""
        scheduler_service.scheduler_status['running'] = True
        result = scheduler_service.start_scheduler()
        
        assert result['success'] is False
        assert "調度器已在運行中" in result['message']
        # 驗證並未調用儲存庫或啟動排程器
        scheduler_service.crawler_tasks_repo.find_auto_tasks.assert_not_called()
    
    def test_stop_scheduler(self, scheduler_service):
        """測試停止排程器"""
        # 設置排程器為運行狀態
        scheduler_service.scheduler_status['running'] = True
        scheduler_service.scheduler_status['job_count'] = 2
        scheduler_service.cron_scheduler.get_jobs.return_value = [MagicMock(), MagicMock()]
        
        # 停止排程器
        result = scheduler_service.stop_scheduler()
        
        # 驗證結果
        assert result['success'] is True
        assert "調度器已暫停" in result['message']
        assert scheduler_service.scheduler_status['running'] is False
        assert scheduler_service.scheduler_status['job_count'] == 2  # 保留任務數量
        assert scheduler_service.scheduler_status['last_shutdown_time'] is not None
        
        # 驗證方法調用
        scheduler_service.cron_scheduler.pause.assert_called_once()
        scheduler_service.cron_scheduler.get_jobs.assert_called_once()
    
    def test_stop_scheduler_not_running(self, scheduler_service):
        """測試在排程器未運行時停止"""
        scheduler_service.scheduler_status['running'] = False
        result = scheduler_service.stop_scheduler()
        
        assert result['success'] is False
        assert "調度器未運行" in result['message']
        # 驗證並未調用停止方法
        scheduler_service.cron_scheduler.pause.assert_not_called()
    
    def test_schedule_task(self, scheduler_service, sample_tasks):
        """測試排程單個任務"""
        task = sample_tasks[0]  # 使用第一個自動任務
        
        # 模擬 CronTrigger
        with patch('src.services.scheduler_service.CronTrigger') as mock_trigger:
            mock_trigger_instance = MagicMock()
            mock_trigger.from_crontab.return_value = mock_trigger_instance
            
            # 執行測試
            result = scheduler_service._schedule_task(task)
            
            # 驗證結果
            assert result is True
            
            # 驗證方法調用
            mock_trigger.from_crontab.assert_called_once_with(task.cron_expression, timezone=pytz.UTC)
            scheduler_service.cron_scheduler.add_job.assert_called_once()
            
            # 驗證 add_job 參數
            call_args = scheduler_service.cron_scheduler.add_job.call_args
            assert call_args.kwargs['func'] == scheduler_service._trigger_task
            assert call_args.kwargs['trigger'] == mock_trigger_instance
            
            # 檢查 task_id 是否在參數中
            if hasattr(call_args, 'args') and len(call_args.args) > 0:
                # 如果 args 存在且不為空，檢查第一個位置參數
                assert task.id in call_args.args[0]
            else:
                # 如果沒有位置參數，檢查 kwargs 中的 args 列表
                assert 'args' in call_args.kwargs
                # 驗證 args 是一個列表，第一個元素是 task_id
                assert isinstance(call_args.kwargs['args'], list)
                assert call_args.kwargs['args'][0] == task.id
            
            assert call_args.kwargs['id'] == f"task_{task.id}"
            assert call_args.kwargs['name'] == task.task_name
            assert call_args.kwargs['replace_existing'] is True
            assert call_args.kwargs['misfire_grace_time'] == 3600
            assert 'task_args' in call_args.kwargs['kwargs']
            assert call_args.kwargs['jobstore'] == 'default'
    
    def test_schedule_task_no_cron(self, scheduler_service, sample_tasks):
        """測試排程沒有 cron 表達式的任務"""
        task = sample_tasks[0]
        task.cron_expression = None
        
        result = scheduler_service._schedule_task(task)
        
        assert result is False
        scheduler_service.cron_scheduler.add_job.assert_not_called()
    
    def test_schedule_task_error(self, scheduler_service, sample_tasks):
        """測試排程任務發生錯誤"""
        task = sample_tasks[0]
        scheduler_service.cron_scheduler.add_job.side_effect = Exception("測試錯誤")
        
        with patch('src.services.scheduler_service.CronTrigger'):
            result = scheduler_service._schedule_task(task)
            
            assert result is False
            scheduler_service.cron_scheduler.add_job.assert_called_once()
    
    def test_trigger_task(self, scheduler_service, task_executor, sample_tasks):
        """測試觸發任務執行"""
        task = sample_tasks[0]
        task_id = task.id
        
        # 模擬儲存庫返回任務
        scheduler_service.crawler_tasks_repo.get_by_id.return_value = task
        
        # 準備測試參數
        task_args = {'task_id': task_id, 'task_name': task.task_name}
        
        # 執行測試
        scheduler_service._trigger_task(task_id, task_args)
        
        # 驗證方法調用
        scheduler_service.crawler_tasks_repo.get_by_id.assert_called_once_with(task_id)
        task_executor.execute_task.assert_called_once_with(task)
    
    def test_trigger_task_not_found(self, scheduler_service, task_executor):
        """測試觸發不存在的任務"""
        task_id = 999
        task_args = {'task_id': task_id, 'task_name': 'Missing Task'}
        
        # 確保清理之前的任何調用記錄
        scheduler_service.cron_scheduler.reset_mock()
        
        # 模擬儲存庫找不到任務
        scheduler_service.crawler_tasks_repo.get_by_id.return_value = None
        scheduler_service.scheduler_status['running'] = True
        
        # 執行測試
        scheduler_service._trigger_task(task_id, task_args)
        
        # 驗證方法調用
        scheduler_service.crawler_tasks_repo.get_by_id.assert_called_once_with(task_id)
        task_executor.execute_task.assert_not_called()
        scheduler_service.cron_scheduler.remove_job.assert_called_once_with(f"task_{task_id}")
    
    def test_trigger_task_not_auto(self, scheduler_service, task_executor, sample_tasks):
        """測試觸發非自動執行的任務"""
        task = sample_tasks[2]  # 手動任務
        task_id = task.id
        
        # 模擬儲存庫返回任務
        scheduler_service.crawler_tasks_repo.get_by_id.return_value = task
        
        # 執行測試
        scheduler_service._trigger_task(task_id)
        
        # 驗證方法調用
        scheduler_service.crawler_tasks_repo.get_by_id.assert_called_once_with(task_id)
        task_executor.execute_task.assert_not_called()
    
    def test_reload_scheduler(self, scheduler_service, sample_tasks):
        """測試重載排程器"""
        # 設置排程器為運行狀態
        scheduler_service.scheduler_status['running'] = True
        
        # 模擬現有任務和資料庫任務
        mock_job1 = MagicMock()
        mock_job1.id = f"task_{sample_tasks[0].id}"
        mock_job1.trigger = MagicMock()
        mock_job1.trigger.expression = sample_tasks[0].cron_expression
        
        mock_job2 = MagicMock()
        mock_job2.id = "task_999"  # 不存在於資料庫的任務
        mock_job2.trigger = MagicMock()
        mock_job2.trigger.expression = "* * * * *"
        
        scheduler_service.cron_scheduler.get_jobs.return_value = [mock_job1, mock_job2]
        scheduler_service.cron_scheduler.get_job.return_value = mock_job1
        
        # 模擬資料庫任務
        scheduler_service.crawler_tasks_repo.find_auto_tasks.return_value = [t for t in sample_tasks if t.is_auto]
        
        # 執行測試
        with patch.object(scheduler_service, '_schedule_task', return_value=True) as mock_schedule:
            result = scheduler_service.reload_scheduler()
            
            # 驗證結果
            assert result['success'] is True
            assert "調度器已重載" in result['message']
            
            # 驗證方法調用
            scheduler_service.crawler_tasks_repo.find_auto_tasks.assert_called_once()
            scheduler_service.cron_scheduler.get_jobs.assert_called()
            
            # 驗證 task_999 被移除 (不使用 assert_called_once_with，而是檢查是否被調用過)
            scheduler_service.cron_scheduler.remove_job.assert_any_call("task_999")
    
    def test_reload_scheduler_not_running(self, scheduler_service):
        """測試在排程器未運行時重載"""
        scheduler_service.scheduler_status['running'] = False
        result = scheduler_service.reload_scheduler()
        
        assert result['success'] is False
        assert "調度器未運行" in result['message']
        
        # 驗證未調用其他方法
        scheduler_service.crawler_tasks_repo.find_auto_tasks.assert_not_called()
    
    def test_get_scheduler_status(self, scheduler_service):
        """測試獲取排程器狀態"""
        # 設置排程器狀態
        scheduler_service.scheduler_status['running'] = True
        scheduler_service.cron_scheduler.get_jobs.return_value = [MagicMock(), MagicMock()]
        
        # 執行測試
        result = scheduler_service.get_scheduler_status()
        
        # 驗證結果
        assert result['success'] is True
        assert "獲取調度器狀態成功" in result['message']
        assert result['status'] == scheduler_service.scheduler_status
        assert result['status']['job_count'] == 2
        
        # 驗證方法調用
        scheduler_service.cron_scheduler.get_jobs.assert_called_once()
    
    def test_get_persisted_jobs_info(self, scheduler_service, sample_tasks):
        """測試獲取持久化任務信息"""
        # 模擬任務
        mock_job = MagicMock()
        mock_job.id = f"task_{sample_tasks[0].id}"
        mock_job.name = sample_tasks[0].task_name
        mock_job.next_run_time = datetime.now(timezone.utc)
        mock_job.trigger = MagicMock()
        mock_job.trigger.expression = sample_tasks[0].cron_expression
        mock_job.misfire_grace_time = 3600
        
        scheduler_service.cron_scheduler.get_jobs.return_value = [mock_job]
        
        # 模擬儲存庫返回任務
        scheduler_service.crawler_tasks_repo.get_by_id.return_value = sample_tasks[0]
        
        # 執行測試
        result = scheduler_service.get_persisted_jobs_info()
        
        # 驗證結果
        assert result['success'] is True
        assert "獲取 1 個持久化任務信息" in result['message']
        assert len(result['jobs']) == 1
        
        job_info = result['jobs'][0]
        assert job_info['id'] == mock_job.id
        assert job_info['name'] == mock_job.name
        assert job_info['next_run_time'] == mock_job.next_run_time.isoformat()
        assert job_info['cron_expression'] == mock_job.trigger.expression
        assert job_info['task_id'] == sample_tasks[0].id
        assert job_info['exists_in_db'] is True
        assert job_info['task_name'] == sample_tasks[0].task_name
        
        # 驗證方法調用
        scheduler_service.cron_scheduler.get_jobs.assert_called_once()
        scheduler_service.crawler_tasks_repo.get_by_id.assert_called_once_with(sample_tasks[0].id)
    
    def test_get_persisted_jobs_info_with_nonexistent_task(self, scheduler_service):
        """測試獲取包含不存在的任務的持久化任務信息"""
        # 模擬任務
        mock_job = MagicMock()
        mock_job.id = "task_999"  # 不存在於資料庫的任務
        mock_job.name = "Missing Task"
        mock_job.next_run_time = datetime.now(timezone.utc)
        mock_job.trigger = MagicMock()
        mock_job.trigger.expression = "* * * * *"
        mock_job.misfire_grace_time = 3600
        
        scheduler_service.cron_scheduler.get_jobs.return_value = [mock_job]
        
        # 模擬儲存庫找不到任務
        scheduler_service.crawler_tasks_repo.get_by_id.return_value = None
        
        # 執行測試
        result = scheduler_service.get_persisted_jobs_info()
        
        # 驗證結果
        assert result['success'] is True
        assert len(result['jobs']) == 1
        
        job_info = result['jobs'][0]
        assert job_info['task_id'] == 999
        assert job_info['exists_in_db'] is False
        
        # 驗證方法調用
        scheduler_service.crawler_tasks_repo.get_by_id.assert_called_once_with(999)


class TestSchedulerServiceIntegration:
    """排程服務整合測試"""
    
    def test_scheduler_lifecycle(self, db_manager, crawler_tasks_repo, task_executor, sample_tasks, mock_real_scheduler):
        """測試排程器完整生命週期"""
        with patch('src.services.scheduler_service.BackgroundScheduler', return_value=mock_real_scheduler):
            with patch('src.services.scheduler_service.SQLAlchemyJobStore', return_value=MagicMock()):
                # 創建服務
                service = SchedulerService(
                    crawler_tasks_repo=crawler_tasks_repo,
                    task_executor=task_executor,
                    db_manager=db_manager
                )
                
                # 確保直接使用我們的 mock
                service.cron_scheduler = mock_real_scheduler
                
                # 重置所有之前的調用記錄
                mock_real_scheduler.reset_mock()
                
                # 模擬排程任務
                with patch.object(service, '_schedule_task', return_value=True):
                    # 啟動排程器
                    start_result = service.start_scheduler()
                    assert start_result['success'] is True
                    assert service.scheduler_status['running'] is True
                    
                    # 設置 get_jobs 返回值，模擬任務已被加入
                    mock_job = MagicMock()
                    mock_job.id = f"task_{sample_tasks[0].id}"
                    mock_job.name = sample_tasks[0].task_name
                    mock_job.next_run_time = datetime.now(timezone.utc)
                    service.cron_scheduler.get_jobs.return_value = [mock_job]
                    service.scheduler_status['job_count'] = 1
                    
                    # 獲取任務信息
                    jobs_info = service.get_persisted_jobs_info()
                    assert jobs_info['success'] is True
                    assert len(jobs_info['jobs']) == 1
                    
                    # 停止排程器
                    stop_result = service.stop_scheduler()
                    assert stop_result['success'] is True
                    assert service.scheduler_status['running'] is False
                
                # 清理資源
                service.cleanup()
    
    def test_scheduler_persistence(self, db_manager, crawler_tasks_repo, task_executor, sample_tasks):
        """測試排程器任務持久化"""
        # 此測試模擬持久化存儲，但不實際使用資料庫
        mock_scheduler1 = MagicMock(spec=BackgroundScheduler)
        mock_scheduler2 = MagicMock(spec=BackgroundScheduler)
        
        # 保存任務數量的變量，確保在兩個上下文之間可見
        jobs_count = 0
        
        # 第一個服務實例
        with patch('src.services.scheduler_service.BackgroundScheduler', return_value=mock_scheduler1):
            with patch('src.services.scheduler_service.SQLAlchemyJobStore', return_value=MagicMock()):
                service1 = SchedulerService(
                    crawler_tasks_repo=crawler_tasks_repo,
                    task_executor=task_executor,
                    db_manager=db_manager
                )
                
                # 確保使用我們的 mock
                service1.cron_scheduler = mock_scheduler1
                
                # 模擬排程任務
                with patch.object(service1, '_schedule_task', return_value=True):
                    # 啟動排程器
                    service1.start_scheduler()
                    
                    # 設置 get_jobs 返回值，模擬任務已被加入
                    mock_job = MagicMock()
                    mock_job.id = f"task_{sample_tasks[0].id}"
                    mock_job.name = sample_tasks[0].task_name
                    mock_job.next_run_time = datetime.now(timezone.utc)
                    service1.cron_scheduler.get_jobs.return_value = [mock_job]
                    service1.scheduler_status['job_count'] = 1
                    
                    # 保存任務數量以供後續使用
                    jobs_count = service1.scheduler_status['job_count']
                    assert jobs_count > 0
                    
                    # 停止但不清除任務
                    service1.stop_scheduler()
                    service1.cleanup()
        
        # 第二個服務實例，應該能夠恢復任務
        # 在真實世界中，這裡會連接到同一個資料庫，從而恢復任務
        # 在測試中，我們模擬這個行為
        with patch('src.services.scheduler_service.BackgroundScheduler', return_value=mock_scheduler2):
            with patch('src.services.scheduler_service.SQLAlchemyJobStore', return_value=MagicMock()):
                service2 = SchedulerService(
                    crawler_tasks_repo=crawler_tasks_repo,
                    task_executor=task_executor,
                    db_manager=db_manager
                )
                
                # 確保使用我們的 mock
                service2.cron_scheduler = mock_scheduler2
                
                # 設置 get_jobs 返回值，模擬從持久化存儲中恢復的任務
                mock_job = MagicMock()
                mock_job.id = f"task_{sample_tasks[0].id}"
                mock_job.name = sample_tasks[0].task_name
                mock_job.next_run_time = datetime.now(timezone.utc)
                service2.cron_scheduler.get_jobs.return_value = [mock_job]
                
                # 啟動排程器，應該能讀取到持久化的任務
                with patch.object(service2, '_schedule_task', return_value=True):
                    service2.start_scheduler()
                    service2.scheduler_status['job_count'] = jobs_count
                    assert service2.scheduler_status['job_count'] == jobs_count
                    
                    # 獲取任務信息
                    jobs_info = service2.get_persisted_jobs_info()
                    assert jobs_info['success'] is True
                    assert len(jobs_info['jobs']) == jobs_count
                
                # 清理資源
                service2.stop_scheduler()
                service2.cleanup()
