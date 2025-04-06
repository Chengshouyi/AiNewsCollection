from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple, Type, cast
import threading
import time
import logging

from src.services.base_service import BaseService
from src.database.database_manager import DatabaseManager
from src.database.base_repository import BaseRepository
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.database.crawlers_repository import CrawlersRepository
from src.database.crawler_task_history_repository import CrawlerTaskHistoryRepository
from src.crawlers.crawler_factory import CrawlerFactory
from src.models.base_model import Base
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawlers_model import Crawlers
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.error.errors import DatabaseOperationError, ValidationError
from src.models.crawler_tasks_schema import CrawlerTasksCreateSchema, CrawlerTasksUpdateSchema
from src.models.crawler_task_history_schema import CrawlerTaskHistoryCreateSchema
from src.utils.datetime_utils import enforce_utc_datetime_transform

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CrawlerTaskService(BaseService[CrawlerTasks]):
    """爬蟲任務服務，負責管理爬蟲任務的數據操作（CRUD）"""
    
    def __init__(self, db_manager=None):
        super().__init__(db_manager)
    
    def _get_repository_mapping(self) -> Dict[str, Tuple[Type[BaseRepository], Type[Base]]]:
        """提供儲存庫映射"""
        return {
            'CrawlerTask': (CrawlerTasksRepository, CrawlerTasks),
            'Crawler': (CrawlersRepository, Crawlers),
            'TaskHistory': (CrawlerTaskHistoryRepository, CrawlerTaskHistory)
        }
                                
    def _get_repositories(self) -> Tuple[CrawlerTasksRepository, CrawlersRepository, CrawlerTaskHistoryRepository]:
        """獲取相關資料庫訪問對象"""
        tasks_repo = cast(CrawlerTasksRepository, super()._get_repository('CrawlerTask'))
        crawlers_repo = cast(CrawlersRepository, super()._get_repository('Crawler'))
        history_repo = cast(CrawlerTaskHistoryRepository, super()._get_repository('TaskHistory'))
        return (tasks_repo, crawlers_repo, history_repo)
        
    def create_task(self, task_data: Dict) -> Dict:
        """創建新任務"""
        try:
            with self._transaction():
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
            return {
                'success': False,
                'message': error_msg
            }
    
    def update_task(self, task_id: int, task_data: Dict) -> Dict:
        """更新任務數據"""
        try:
            with self._transaction():
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
            with self._transaction():
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
            with self._transaction():
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
                        'task': task
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
            with self._transaction():
                tasks_repo, _, _ = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                    
                tasks = tasks_repo.get_all(filters)
                return {
                    'success': True,
                    'tasks': tasks
                }
        except Exception as e:
            error_msg = f"獲取所有任務失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e
        
    def get_task_history(self, task_id: int) -> Dict:
        """獲取任務的執行歷史記錄"""
        try:
            with self._transaction():
                _, _, history_repo = self._get_repositories()
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                    
                history = history_repo.find_by_task_id(task_id)
                return {
                    'success': True,
                    'history': history
                }
        except Exception as e:
            error_msg = f"獲取任務歷史失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e

    def get_task_status(self, task_id: int) -> Dict:
        """獲取任務的當前狀態（從歷史記錄中）"""
        try:
            with self._transaction():
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
                latest_history = history_repo.get_latest_history(task_id)
                
                if not latest_history or not latest_history.start_time:
                    return {
                        'status': 'unknown',
                        'progress': 0,
                        'message': '無執行歷史'
                    }
                
                # 計算進度
                if latest_history.end_time:
                    status = 'completed' if latest_history.success else 'failed'
                    progress = 100
                else:
                    status = 'running'
                    # 如果正在執行中，根據開始時間計算大約進度
                    current_time = datetime.now(timezone.utc)
                    elapsed = current_time - latest_history.start_time  # start_time 已經確認不是 None
                    # 假設每個任務平均執行時間為 5 分鐘
                    progress = min(95, int((elapsed.total_seconds() / 300) * 100))
                
                return {
                    'status': status,
                    'progress': progress,
                    'message': latest_history.message or '',
                    'articles_count': latest_history.articles_count or 0,
                    'start_time': latest_history.start_time,
                    'end_time': latest_history.end_time
                }
                
        except Exception as e:
            error_msg = f"獲取任務狀態失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'status': 'error',
                'progress': 0,
                'message': f'獲取狀態時發生錯誤: {str(e)}'
            }