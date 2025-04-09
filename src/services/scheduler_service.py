import logging
from typing import Dict, Any, List, Tuple, Optional, Type, cast
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from datetime import datetime, timezone
import pytz

from src.services.base_service import BaseService
from src.database.base_repository import BaseRepository
from src.models.base_model import Base
from src.models.crawler_tasks_model import CrawlerTasks
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.services.task_executor import TaskExecutor

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SchedulerService(BaseService[CrawlerTasks]):
    """排程服務，使用 Cron 表達式調度爬蟲任務執行"""
    
    def __init__(self, crawler_tasks_repo: Optional[CrawlerTasksRepository] = None, 
                 task_executor: Optional[TaskExecutor] = None, 
                 db_manager = None):
        """初始化排程服務
        
        Args:
            crawler_tasks_repo: CrawlerTasksRepository 實例，用於查詢任務
            task_executor: TaskExecutor 實例，用於執行任務
            db_manager: 資料庫管理器
        """
        super().__init__(db_manager)
        
        # 儲存傳入的參數或創建新實例
        self.crawler_tasks_repo = crawler_tasks_repo or self._get_task_repo()
        self.task_executor = task_executor or TaskExecutor()
        
        # 設定 SQLAlchemy 任務存儲
        jobstore = SQLAlchemyJobStore(
            url=self.db_manager.db_url,
            engine=self.db_manager.engine,
            tablename='apscheduler_jobs'
        )
        
        # 設定執行器
        executors = {
            'default': ThreadPoolExecutor(20),
            'processpool': ProcessPoolExecutor(5)
        }
        
        # 作業預設值
        job_defaults = {
            'coalesce': True,  # 合併延遲的作業
            'max_instances': 3,  # 同一作業的最大實例數
            'misfire_grace_time': 3600  # 允許 1 小時的誤差
        }
        
        # 初始化 cron 調度器，加入持久化設定
        self.cron_scheduler = BackgroundScheduler(
            jobstores={'default': jobstore},
            executors=executors,
            job_defaults=job_defaults,
            timezone=pytz.UTC
        )
        
        # 記錄調度器狀態
        self.scheduler_status = {
            'running': False,
            'job_count': 0,
            'last_start_time': None,
            'last_shutdown_time': None
        }
    
    def _get_repository_mapping(self) -> Dict[str, Tuple[Type[BaseRepository], Type[Base]]]:
        """提供儲存庫映射"""
        return {
            'CrawlerTask': (CrawlerTasksRepository, CrawlerTasks)
        }
    
    def _get_task_repo(self) -> CrawlerTasksRepository:
        """獲取爬蟲任務資料庫訪問對象"""
        return cast(CrawlerTasksRepository, super()._get_repository('CrawlerTask'))
    
    def start_scheduler(self) -> Dict[str, Any]:
        """啟動 cron 調度器，並根據資料庫中各任務的 cron 表達式安排執行
        
        Returns:
            Dict[str, Any]: 包含啟動結果的字典
        """
        if self.scheduler_status['running']:
            return {
                'success': False,
                'message': '調度器已在運行中'
            }
            
        try:
            # 檢查是否有持久化的任務
            persisted_jobs = self.cron_scheduler.get_jobs()
            persisted_jobs_count = len(persisted_jobs)
            
            if persisted_jobs_count > 0:
                logger.info(f"發現 {persisted_jobs_count} 個持久化任務")
            
            # 從資料庫獲取需要自動執行的任務
            auto_tasks = self.crawler_tasks_repo.find_auto_tasks()
            
            # 記錄資料庫任務和持久化任務的 ID 對應關係
            db_task_ids = {task.id for task in auto_tasks}
            persisted_job_ids = {int(job.id.split('_')[1]) for job in persisted_jobs 
                               if job.id.startswith('task_') and job.id.split('_')[1].isdigit()}
            
            # 根據任務的 cron 表達式設定調度
            scheduled_count = 0
            for task in auto_tasks:
                # 如果任務已經在持久化存儲中存在，我們只需要確保其設置正確
                if task.id in persisted_job_ids:
                    # 檢查 cron 表達式是否有變更
                    job_id = f"task_{task.id}"
                    job = self.cron_scheduler.get_job(job_id)
                    
                    if job and hasattr(job.trigger, 'expression') and job.trigger.expression != task.cron_expression:
                        logger.info(f"任務 {task.id} 的 cron 表達式已變更，重新排程")
                        self.cron_scheduler.remove_job(job_id)
                        if self._schedule_task(task):
                            scheduled_count += 1
                    else:
                        # 已存在且設置正確的任務，無需操作
                        scheduled_count += 1
                else:
                    # 新增任務
                    if self._schedule_task(task):
                        scheduled_count += 1
            
            # 移除已不存在於資料庫的持久化任務
            for job_id in [f"task_{task_id}" for task_id in persisted_job_ids if task_id not in db_task_ids]:
                try:
                    self.cron_scheduler.remove_job(job_id)
                    logger.info(f"移除不存在於資料庫的持久化任務: {job_id}")
                except Exception as e:
                    logger.warning(f"移除持久化任務 {job_id} 失敗: {str(e)}")
            
            # 啟動調度器
            self.cron_scheduler.start()
            
            # 更新狀態
            self.scheduler_status['running'] = True
            self.scheduler_status['job_count'] = len(self.cron_scheduler.get_jobs())
            self.scheduler_status['last_start_time'] = datetime.now(timezone.utc)
            
            return {
                'success': True,
                'message': f'調度器已啟動，已排程 {scheduled_count} 個任務，總共 {self.scheduler_status["job_count"]} 個作業',
                'status': self.scheduler_status
            }
        except Exception as e:
            error_msg = f"啟動調度器失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    def stop_scheduler(self) -> Dict[str, Any]:
        """停止 cron 調度器，清理資源
        
        Returns:
            Dict[str, Any]: 包含停止結果的字典
        """
        if not self.scheduler_status['running']:
            return {
                'success': False,
                'message': '調度器未運行'
            }
            
        try:
            # 獲取當前任務數量用於記錄
            current_job_count = len(self.cron_scheduler.get_jobs())
            
            # 暫停調度器而不清除任務定義
            self.cron_scheduler.pause()
            
            # 更新狀態
            self.scheduler_status['running'] = False
            # 保留任務數量值，以便在重啟時知道有多少任務
            self.scheduler_status['job_count'] = current_job_count
            self.scheduler_status['last_shutdown_time'] = datetime.now(timezone.utc)
            
            return {
                'success': True,
                'message': f'調度器已暫停，保留 {current_job_count} 個持久化任務',
                'status': self.scheduler_status
            }
        except Exception as e:
            error_msg = f"停止調度器失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    def _schedule_task(self, task: CrawlerTasks) -> bool:
        """根據任務內的 cron 表達式設定排程工作，並註冊回呼方法
        
        Args:
            task: 爬蟲任務實例
            
        Returns:
            bool: 設定成功返回 True，否則返回 False
        """
        if not task.cron_expression:
            logger.warning(f"任務 {task.id} 沒有設定 cron 表達式，跳過排程")
            return False
            
        try:
            # 設定 cron 觸發器
            trigger = CronTrigger.from_crontab(task.cron_expression, timezone=pytz.UTC)
            
            # 建立任務執行參數
            task_args = {
                'task_id': task.id,
                'task_name': task.task_name,
                'crawler_id': task.crawler_id
            }
            
            # 排程任務，並設定觸發時調用 _trigger_task 方法
            job_id = f"task_{task.id}"
            self.cron_scheduler.add_job(
                func=self._trigger_task,
                trigger=trigger,
                args=[task.id, task_args],
                id=job_id,
                name=task.task_name,
                replace_existing=True,
                misfire_grace_time=3600,  # 允許 1 小時的誤差
                kwargs={'task_args': task_args},
                jobstore='default'  # 使用默認的 SQLAlchemyJobStore
            )
            
            logger.info(f"已排程任務 {task.id}，cron 表達式: {task.cron_expression}")
            return True
        except Exception as e:
            logger.error(f"排程任務 {task.id} 失敗: {str(e)}", exc_info=True)
            return False
    
    def _trigger_task(self, task_id: int, task_args: Optional[Dict[str, Any]] = None) -> None:
        """在 cron 調度器觸發時，將該任務交由 TaskExecutor 執行
        
        Args:
            task_id: 任務 ID
            task_args: 附加的任務參數 (持久化存儲的任務可能提供)
        """
        try:
            logger.info(f"調度器觸發執行任務 {task_id}, 附加參數: {task_args}")
            
            # 從資料庫獲取任務詳情
            task = self.crawler_tasks_repo.get_by_id(task_id)
            
            if not task:
                error_msg = f"找不到任務 {task_id}，無法執行"
                logger.error(error_msg)
                
                # 如果是持久化恢復的任務但資料庫中已不存在，應該移除該排程
                if task_args and self.scheduler_status['running']:
                    job_id = f"task_{task_id}"
                    try:
                        self.cron_scheduler.remove_job(job_id)
                        logger.info(f"已移除不存在的持久化任務: {job_id}")
                    except Exception as e:
                        logger.warning(f"移除不存在的任務 {job_id} 失敗: {str(e)}")
                return
                
            # 檢查任務是否設置為自動執行
            if not task.is_auto:
                logger.warning(f"任務 {task_id} 已設置為非自動執行，跳過本次執行")
                return
                
            # 交由 TaskExecutor 執行
            self.task_executor.execute_task(task)
            
        except Exception as e:
            error_msg = f"觸發執行任務 {task_id} 時發生錯誤: {str(e)}"
            logger.error(error_msg, exc_info=True)
    
    def reload_scheduler(self) -> Dict[str, Any]:
        """當任務資料變更（新增、更新或刪除任務）時，重新載入或調整調度任務
        
        Returns:
            Dict[str, Any]: 包含重載結果的字典
        """
        # 如果調度器未運行，直接返回錯誤
        if not self.scheduler_status['running']:
            return {
                'success': False,
                'message': '調度器未運行，無法重載'
            }
            
        try:
            # 獲取現有的持久化任務
            persisted_jobs = self.cron_scheduler.get_jobs()
            persisted_job_ids = {int(job.id.split('_')[1]) for job in persisted_jobs 
                               if job.id.startswith('task_') and job.id.split('_')[1].isdigit()}
            
            # 從資料庫獲取最新的自動執行任務
            auto_tasks = self.crawler_tasks_repo.find_auto_tasks()
            db_task_ids = {task.id for task in auto_tasks}
            db_task_dict = {task.id: task for task in auto_tasks}
            
            # 1. 移除已不存在於資料庫的持久化任務
            removed_count = 0
            for task_id in persisted_job_ids:
                if task_id not in db_task_ids:
                    job_id = f"task_{task_id}"
                    try:
                        self.cron_scheduler.remove_job(job_id)
                        logger.info(f"重載時移除不存在於資料庫的任務: {job_id}")
                        removed_count += 1
                    except Exception as e:
                        logger.warning(f"重載時移除任務 {job_id} 失敗: {str(e)}")
            
            # 2. 更新現有任務或新增任務
            updated_count = 0
            added_count = 0
            
            for task in auto_tasks:
                job_id = f"task_{task.id}"
                job = self.cron_scheduler.get_job(job_id)
                
                if job:
                    # 檢查任務是否需要更新 (例如 cron 表達式變更)
                    if hasattr(job.trigger, 'expression') and job.trigger.expression != task.cron_expression:
                        try:
                            self.cron_scheduler.remove_job(job_id)
                            if self._schedule_task(task):
                                logger.info(f"重載時更新任務: {job_id}")
                                updated_count += 1
                        except Exception as e:
                            logger.warning(f"重載時更新任務 {job_id} 失敗: {str(e)}")
                else:
                    # 新增任務
                    if self._schedule_task(task):
                        logger.info(f"重載時新增任務: {job_id}")
                        added_count += 1
            
            # 更新狀態
            self.scheduler_status['job_count'] = len(self.cron_scheduler.get_jobs())
            
            return {
                'success': True,
                'message': f'調度器已重載，移除 {removed_count} 個任務，更新 {updated_count} 個任務，新增 {added_count} 個任務',
                'status': self.scheduler_status
            }
        except Exception as e:
            error_msg = f"重載調度器失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """獲取調度器當前狀態
        
        Returns:
            Dict[str, Any]: 包含調度器狀態的字典
        """
        # 更新作業數量
        if self.scheduler_status['running']:
            self.scheduler_status['job_count'] = len(self.cron_scheduler.get_jobs())
            
        return {
            'success': True,
            'message': '獲取調度器狀態成功',
            'status': self.scheduler_status
        }
    
    def get_persisted_jobs_info(self) -> Dict[str, Any]:
        """獲取持久化任務的詳細信息
        
        Returns:
            Dict[str, Any]: 包含任務詳情的字典
        """
        try:
            jobs = self.cron_scheduler.get_jobs()
            jobs_info = []
            
            for job in jobs:
                job_info = {
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                    'trigger': str(job.trigger),
                    'cron_expression': job.trigger.expression if hasattr(job.trigger, 'expression') else None,
                    'misfire_grace_time': job.misfire_grace_time,
                    'active': job.next_run_time is not None
                }
                
                # 嘗試提取任務 ID
                if job.id.startswith('task_') and job.id.split('_')[1].isdigit():
                    task_id = int(job.id.split('_')[1])
                    job_info['task_id'] = task_id
                    
                    # 檢查資料庫中是否還存在此任務
                    task = self.crawler_tasks_repo.get_by_id(task_id)
                    job_info['exists_in_db'] = task is not None
                    if task:
                        job_info['task_name'] = task.task_name
                        job_info['is_auto'] = task.is_auto
                
                jobs_info.append(job_info)
                
            return {
                'success': True,
                'message': f'獲取 {len(jobs_info)} 個持久化任務信息',
                'scheduler_running': self.scheduler_status['running'],
                'jobs': jobs_info
            }
        except Exception as e:
            error_msg = f"獲取持久化任務信息失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    def __del__(self):
        """析構方法，確保調度器被停止"""
        if self.scheduler_status['running']:
            try:
                # 使用 shutdown 而非 pause，因為這是最終銷毀
                self.cron_scheduler.shutdown(wait=False)
                logger.info("調度器已在銷毀時關閉")
            except Exception as e:
                logger.warning(f"關閉調度器時發生錯誤 (忽略): {str(e)}")
                
        # 呼叫父類的清理方法
        super().__del__() 