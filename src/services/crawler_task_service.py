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
from src.models.base_model import Base
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawlers_model import Crawlers
from src.models.crawler_task_history_model import CrawlerTaskHistory        
from src.utils.validators import validate_crawler_data, validate_task_data

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
                        'message': '無法取得資料庫存取器',
                        'task': None
                    }
                    
                result = tasks_repo.update(task_id, task_data)
                if result is None:
                    return {
                        'success': False,
                        'message': '任務不存在',
                        'task': None
                    }
                    
                return {
                    'success': True,
                    'message': '任務更新成功',
                    'task': result
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
                        'message': '無法取得資料庫存取器',
                        'task': None
                    }
                    
                task = tasks_repo.get_by_id(task_id)
                if task:
                    return {
                        'success': True,
                        'message': '任務獲取成功',
                        'task': task
                    }
                return {
                    'success': False,
                    'message': '任務不存在',
                    'task': None
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
                        'message': '無法取得資料庫存取器',
                        'tasks': []
                    }
                    
                tasks = tasks_repo.get_all(filters)
                return {
                    'success': True,
                    'message': '任務獲取成功',
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
                        'message': '無法取得資料庫存取器',
                        'history': []
                    }
                    
                history = history_repo.find_by_task_id(task_id)
                return {
                    'success': True,
                    'message': '任務歷史獲取成功',
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
                        'message': '無法取得資料庫存取器',
                        'task': None
                    }
                    
                # 檢查任務是否存在
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'status': 'unknown',
                        'progress': 0,
                        'message': '任務不存在',
                        'task': None
                    }
                    
                # 從資料庫獲取最新一筆歷史記錄
                latest_history = history_repo.get_latest_history(task_id)
                
                if not latest_history or not latest_history.start_time:
                    return {
                        'status': 'unknown',
                        'progress': 0,
                        'message': '無執行歷史',
                        'task': task
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

    def run_task(self, task_id: int, task_args: Dict[str, Any]) -> Dict[str, Any]:
        """執行任務
        
        Args:
            task_id: 任務ID
            task_args: 任務參數
            
        Returns:
            Dict[str, Any]: 執行結果
        """
        try:
            with self._transaction():
                tasks_repo, _, history_repo = self._get_repositories()
                if not tasks_repo or not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                
                # 檢查任務是否存在
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在'
                    }
                
                # 創建任務歷史記錄
                history_data = {
                    'task_id': task_id,
                    'start_time': datetime.now(timezone.utc),
                    'status': 'running',
                    'message': '任務開始執行'
                }
                history_id = history_repo.create(history_data)
                
                try:
                    # 執行任務邏輯
                    # TODO: 實作實際的任務執行邏輯
                    
                    # 更新任務歷史記錄
                    history_data.update({
                        'end_time': datetime.now(timezone.utc),
                        'status': 'completed',
                        'message': '任務執行完成'
                    })
                    history_repo.update(history_id, history_data)
                    
                    return {
                        'success': True,
                        'message': '任務執行完成'
                    }
                except Exception as e:
                    # 更新任務歷史記錄
                    history_data.update({
                        'end_time': datetime.now(timezone.utc),
                        'status': 'failed',
                        'message': f'任務執行失敗: {str(e)}'
                    })
                    history_repo.update(history_id, history_data)
                    
                    return {
                        'success': False,
                        'message': f'任務執行失敗: {str(e)}'
                    }
        except Exception as e:
            error_msg = f"執行任務失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    def fetch_article_content(self, task_id: int, link_ids: List[int]) -> Dict[str, Any]:
        """抓取文章內容
        
        Args:
            task_id: 任務ID
            link_ids: 文章連結ID列表
            
        Returns:
            Dict[str, Any]: 執行結果
        """
        try:
            with self._transaction():
                tasks_repo, _, history_repo = self._get_repositories()
                if not tasks_repo or not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                
                # 檢查任務是否存在
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在'
                    }
                
                # 創建任務歷史記錄
                history_data = {
                    'task_id': task_id,
                    'start_time': datetime.now(timezone.utc),
                    'status': 'running',
                    'message': '開始抓取文章內容'
                }
                history_id = history_repo.create(history_data)
                
                try:
                    # 執行抓取內容邏輯
                    # TODO: 實作實際的抓取內容邏輯
                    
                    # 更新任務歷史記錄
                    history_data.update({
                        'end_time': datetime.now(timezone.utc),
                        'status': 'completed',
                        'message': '文章內容抓取完成'
                    })
                    history_repo.update(history_id, history_data)
                    
                    return {
                        'success': True,
                        'message': '文章內容抓取完成'
                    }
                except Exception as e:
                    # 更新任務歷史記錄
                    history_data.update({
                        'end_time': datetime.now(timezone.utc),
                        'status': 'failed',
                        'message': f'文章內容抓取失敗: {str(e)}'
                    })
                    history_repo.update(history_id, history_data)
                    
                    return {
                        'success': False,
                        'message': f'文章內容抓取失敗: {str(e)}'
                    }
        except Exception as e:
            error_msg = f"抓取文章內容失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    def test_crawler_task(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """測試爬蟲任務
        
        Args:
            data: 任務資料
            
        Returns:
            Dict[str, Any]: 測試結果
        """
        try:
            # 驗證爬蟲配置
            crawler_errors = validate_crawler_data(data)
            if crawler_errors:
                return {
                    'success': False,
                    'message': '爬蟲配置驗證失敗',
                    'errors': crawler_errors
                }
            
            # 驗證任務資料
            task_errors = validate_task_data(data)
            if task_errors:
                return {
                    'success': False,
                    'message': '任務資料驗證失敗',
                    'errors': task_errors
                }
            
            # TODO: 實作實際的爬蟲測試邏輯
            
            return {
                'success': True,
                'message': '爬蟲測試成功',
                'test_results': {
                    'links_found': 10,
                    'sample_links': [
                        'https://example.com/article1',
                        'https://example.com/article2',
                        'https://example.com/article3'
                    ]
                }
            }
        except Exception as e:
            error_msg = f"爬蟲測試失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    def cancel_task(self, task_id: int) -> Dict[str, Any]:
        """取消任務
        
        Args:
            task_id: 任務ID
            
        Returns:
            Dict[str, Any]: 取消結果
        """
        try:
            with self._transaction():
                tasks_repo, _, history_repo = self._get_repositories()
                if not tasks_repo or not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                
                # 檢查任務是否存在
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在'
                    }
                
                # 檢查任務是否正在執行
                latest_history = history_repo.get_latest_history(task_id)
                if not latest_history or latest_history.status != 'running':
                    return {
                        'success': False,
                        'message': '任務未在執行中'
                    }
                
                # 更新任務歷史記錄
                history_data = {
                    'end_time': datetime.now(timezone.utc),
                    'status': 'cancelled',
                    'message': '任務已取消'
                }
                history_repo.update(latest_history.id, history_data)
                
                return {
                    'success': True,
                    'message': '任務已取消'
                }
        except Exception as e:
            error_msg = f"取消任務失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }