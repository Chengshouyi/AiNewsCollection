from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import threading
import time
import logging

from src.database.database_manager import DatabaseManager
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.database.crawlers_repository import CrawlersRepository
from src.database.crawler_task_history_repository import CrawlerTaskHistoryRepository
from src.crawlers.crawler_factory import CrawlerFactory
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawlers_model import Crawlers
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.error.errors import DatabaseOperationError, ValidationError
from src.models.crawler_tasks_schema import CrawlerTasksCreateSchema, CrawlerTasksUpdateSchema
from src.models.crawler_task_history_schema import CrawlerTaskHistoryCreateSchema

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CrawlerTaskService:
    """爬蟲任務服務，負責管理爬蟲任務的數據操作（CRUD）"""
    
    def __init__(self, db_manager=None):
        self.db_manager = db_manager
    
    def _get_repositories(self):
        """獲取相關資料庫訪問對象"""
        if self.db_manager:
            tasks_repo = self.db_manager.get_repository('CrawlerTask')
            crawlers_repo = self.db_manager.get_repository('Crawler')
            history_repo = self.db_manager.get_repository('TaskHistory')
            return tasks_repo, crawlers_repo, history_repo
        return None, None, None
        
    def create_task(self, task_data: Dict) -> Dict:
        """創建新任務"""
        try:
            tasks_repo, _, _ = self._get_repositories()
            if not tasks_repo:
                return {
                    'success': False,
                    'message': '無法取得資料庫存取器'
                }
                
            task_id = tasks_repo.create(task_data)
            return {
                'success': True,
                'message': '任務創建成功',
                'task_id': task_id
            }
        except Exception as e:
            error_msg = f"創建任務失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e
    
    def update_task(self, task_id: int, task_data: Dict) -> Dict:
        """更新任務數據"""
        try:
            tasks_repo, _, _ = self._get_repositories()
            if not tasks_repo:
                return {
                    'success': False,
                    'message': '無法取得資料庫存取器'
                }
                
            success = tasks_repo.update(task_id, task_data)
            return {
                'success': success,
                'message': '任務更新成功' if success else '任務不存在'
            }
        except Exception as e:
            error_msg = f"更新任務失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e
    
    def delete_task(self, task_id: int) -> Dict:
        """刪除任務"""
        try:
            tasks_repo, _, _ = self._get_repositories()
            if not tasks_repo:
                return {
                    'success': False,
                    'message': '無法取得資料庫存取器'
                }
                
            success = tasks_repo.delete(task_id)
            return {
                'success': success,
                'message': '任務刪除成功' if success else '任務不存在'
            }
        except Exception as e:
            error_msg = f"刪除任務失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e
    
    def get_task_by_id(self, task_id: int) -> Dict:
        """獲取指定ID的任務"""
        try:
            tasks_repo, _, _ = self._get_repositories()
            if not tasks_repo:
                return {
                    'success': False,
                    'message': '無法取得資料庫存取器'
                }
                
            task = tasks_repo.get_by_id(task_id)
            if task:
                return {
                    'success': True,
                    'task': task.as_dict() if hasattr(task, 'as_dict') else task
                }
            return {
                'success': False,
                'message': '任務不存在'
            }
        except Exception as e:
            error_msg = f"獲取任務失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e
    
    def get_all_tasks(self, filters=None) -> Dict:
        """獲取所有任務，可選過濾條件"""
        try:
            tasks_repo, _, _ = self._get_repositories()
            if not tasks_repo:
                return {
                    'success': False,
                    'message': '無法取得資料庫存取器'
                }
                
            tasks = tasks_repo.get_all(filters)
            return {
                'success': True,
                'tasks': [task.as_dict() if hasattr(task, 'as_dict') else task for task in tasks]
            }
        except Exception as e:
            error_msg = f"獲取所有任務失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e
        
    def get_task_history(self, task_id: int) -> Dict:
        """獲取任務的執行歷史記錄"""
        try:
            _, _, history_repo = self._get_repositories()
            if not history_repo:
                return {
                    'success': False,
                    'message': '無法取得資料庫存取器'
                }
                
            history = history_repo.get_by_task_id(task_id)
            return {
                'success': True,
                'history': [h.as_dict() if hasattr(h, 'as_dict') else h for h in history]
            }
        except Exception as e:
            error_msg = f"獲取任務歷史失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e

    def get_task_status(self, task_id: int) -> Dict:
        """獲取任務的當前狀態（從歷史記錄中）"""
        try:
            tasks_repo, _, history_repo = self._get_repositories()
            if not tasks_repo or not history_repo:
                return {
                    'status': 'error',
                    'progress': 0,
                    'message': '無法取得資料庫存取器'
                }
                
            # 檢查任務是否存在
            task = tasks_repo.get_by_id(task_id)
            if not task:
                return {
                    'status': 'unknown',
                    'progress': 0,
                    'message': '任務不存在'
                }
                
            # 從資料庫獲取最新一筆歷史記錄
            latest_history = history_repo.get_latest_by_task_id(task_id)
            
            if latest_history:
                return {
                    'status': latest_history.status,
                    'progress': 100 if latest_history.status == 'completed' else 0,
                    'message': latest_history.message,
                    'last_run_at': latest_history.created_at.isoformat() if latest_history.created_at else None
                }
            else:
                return {
                    'status': 'pending',
                    'progress': 0,
                    'message': '未曾執行'
                }
                
        except Exception as e:
            error_msg = f"獲取任務狀態失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'status': 'error',
                'progress': 0,
                'message': f'獲取狀態時發生錯誤: {str(e)}'
            }