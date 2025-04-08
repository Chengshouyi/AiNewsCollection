import logging
from typing import Dict, Any, List, Tuple, Optional, Type, cast
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
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
        
        # 初始化 cron 調度器
        self.cron_scheduler = BackgroundScheduler(timezone=pytz.UTC)
        
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
            # 清空所有現有任務
            self.cron_scheduler.remove_all_jobs()
            
            # 從資料庫獲取需要自動執行的任務
            auto_tasks = self.crawler_tasks_repo.find_auto_tasks()
            
            # 根據任務的 cron 表達式設定調度
            for task in auto_tasks:
                self._schedule_task(task)
            
            # 啟動調度器
            self.cron_scheduler.start()
            
            # 更新狀態
            self.scheduler_status['running'] = True
            self.scheduler_status['job_count'] = len(self.cron_scheduler.get_jobs())
            self.scheduler_status['last_start_time'] = datetime.now(timezone.utc)
            
            return {
                'success': True,
                'message': f'調度器已啟動，已排程 {self.scheduler_status["job_count"]} 個任務',
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
            # 關閉調度器
            self.cron_scheduler.shutdown()
            
            # 更新狀態
            self.scheduler_status['running'] = False
            self.scheduler_status['job_count'] = 0
            self.scheduler_status['last_shutdown_time'] = datetime.now(timezone.utc)
            
            return {
                'success': True,
                'message': '調度器已停止',
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
            
            # 排程任務，並設定觸發時調用 _trigger_task 方法
            job_id = f"task_{task.id}"
            self.cron_scheduler.add_job(
                func=self._trigger_task,
                trigger=trigger,
                args=[task.id],
                id=job_id,
                replace_existing=True,
                misfire_grace_time=3600  # 允許 1 小時的誤差
            )
            
            logger.info(f"已排程任務 {task.id}，cron 表達式: {task.cron_expression}")
            return True
        except Exception as e:
            logger.error(f"排程任務 {task.id} 失敗: {str(e)}", exc_info=True)
            return False
    
    def _trigger_task(self, task_id: int) -> None:
        """在 cron 調度器觸發時，將該任務交由 TaskExecutor 執行
        
        Args:
            task_id: 任務 ID
        """
        try:
            logger.info(f"調度器觸發執行任務 {task_id}")
            
            # 從資料庫獲取任務詳情
            task = self.crawler_tasks_repo.get_by_id(task_id)
            
            if not task:
                logger.error(f"找不到任務 {task_id}，無法執行")
                return
                
            # 檢查任務是否設置為自動執行
            if not task.is_auto:
                logger.warning(f"任務 {task_id} 已設置為非自動執行，跳過本次執行")
                return
                
            # 交由 TaskExecutor 執行
            self.task_executor.execute_task(task)
            
        except Exception as e:
            logger.error(f"觸發執行任務 {task_id} 時發生錯誤: {str(e)}", exc_info=True)
    
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
            # 先停止調度器
            result = self.stop_scheduler()
            if not result['success']:
                return result
                
            # 重新啟動調度器
            return self.start_scheduler()
            
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
    
    def __del__(self):
        """析構方法，確保調度器被停止"""
        if self.scheduler_status['running']:
            try:
                self.cron_scheduler.shutdown()
            except Exception as e:
                logger.warning(f"關閉調度器時發生錯誤 (忽略): {str(e)}")
                
        # 呼叫父類的清理方法
        super().__del__() 