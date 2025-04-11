from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Type, cast, Optional
import threading
import time
import logging

from src.services.base_service import BaseService
from src.database.base_repository import BaseRepository, SchemaType
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.database.crawlers_repository import CrawlersRepository
from src.database.crawler_task_history_repository import CrawlerTaskHistoryRepository
from src.models.base_model import Base
from src.models.crawler_tasks_model import CrawlerTasks, TaskPhase
from src.models.crawlers_model import Crawlers
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.error.errors import ValidationError

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
                
                # 創建任務
                task = tasks_repo.create(task_data)
                return {
                    'success': True,
                    'message': '任務創建成功',
                    'task_id': task.id if task else None
                }
        except ValidationError as e:
            error_msg = f"創建任務資料驗證失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
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
                
                # 更新任務
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
        except ValidationError as e:
            error_msg = f"更新任務資料驗證失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'task': None
            }
        except Exception as e:
            error_msg = f"更新任務失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'task': None
            }
    
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
            使用情境：
                1. 手動任務：當使用者手動選擇要執行的任務時，會使用此方法
                2. 自動任務：當任務執行時，會使用此方法

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
                
                # 先驗證歷史記錄資料
                validated_history_data = self.validate_data('TaskHistory', history_data, SchemaType.CREATE)
                # 創建歷史記錄
                history = history_repo.create(validated_history_data)
                history_id = history.id if history else None
                
                try:
                    # 更新任務階段為初始階段
                    self.update_task_phase(task_id, TaskPhase.INIT)
                    
                    # 執行任務邏輯
                    # TODO: 實作實際的任務執行邏輯
                    
                    # 更新任務歷史記錄
                    history_update_data = {
                        'end_time': datetime.now(timezone.utc),
                        'status': 'completed',
                        'message': '任務執行完成'
                    }
                    
                    # 驗證歷史記錄更新資料
                    validated_history_update = self.validate_data('TaskHistory', history_update_data, SchemaType.UPDATE)
                    # 更新歷史記錄
                    history_repo.update(history_id, validated_history_update)
                    
                    # 更新任務階段為完成
                    self.update_task_phase(task_id, TaskPhase.COMPLETED)
                    
                    # 成功執行後重置重試次數
                    self.reset_retry_count(task_id)
                    
                    # 更新任務最後執行狀態
                    tasks_repo.update_last_run(task_id, True, '任務執行成功')
                    
                    return {
                        'success': True,
                        'message': '任務執行完成'
                    }
                except Exception as e:
                    # 更新任務歷史記錄
                    history_update_data = {
                        'end_time': datetime.now(timezone.utc),
                        'status': 'failed',
                        'message': f'任務執行失敗: {str(e)}'
                    }
                    
                    # 驗證歷史記錄更新資料
                    validated_history_update = self.validate_data('TaskHistory', history_update_data, SchemaType.UPDATE)
                    # 更新歷史記錄
                    history_repo.update(history_id, validated_history_update)
                    
                    # 增加重試次數
                    retry_result = self.increment_retry_count(task_id)
                    
                    # 更新任務最後執行狀態
                    tasks_repo.update_last_run(task_id, False, f'任務執行失敗: {str(e)}')
                    
                    return {
                        'success': False,
                        'message': f'任務執行失敗: {str(e)}',
                        'retry_info': retry_result
                    }
        except Exception as e:
            error_msg = f"執行任務失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    def fetch_article_content(self, task_id: int, link_ids: List[int]) -> Dict[str, Any]:
        """ 抓取文章內容，並更新文章內容
            使用情境：
                1. 手動任務：當使用者手動選擇要抓取的文章連結時，會使用此方法
                2. 自動任務：當任務執行時，會使用此方法

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
                
                # 先驗證歷史記錄資料
                validated_history_data = self.validate_data('TaskHistory', history_data, SchemaType.CREATE)
                # 創建歷史記錄
                history = history_repo.create(validated_history_data)
                history_id = history.id if history else None
                
                try:
                    # 更新任務階段為內容爬取階段
                    self.update_task_phase(task_id, TaskPhase.CONTENT_SCRAPING)
                    
                    # 執行抓取內容邏輯
                    # TODO: 實作實際的抓取內容邏輯
                    
                    # 更新任務歷史記錄
                    history_update_data = {
                        'end_time': datetime.now(timezone.utc),
                        'status': 'completed',
                        'message': '文章內容抓取完成'
                    }
                    
                    # 驗證歷史記錄更新資料
                    validated_history_update = self.validate_data('TaskHistory', history_update_data, SchemaType.UPDATE)
                    # 更新歷史記錄
                    history_repo.update(history_id, validated_history_update)
                    
                    # 更新任務階段為完成
                    self.update_task_phase(task_id, TaskPhase.COMPLETED)
                    
                    # 成功執行後重置重試次數
                    self.reset_retry_count(task_id)
                    
                    # 更新任務最後執行狀態
                    tasks_repo.update_last_run(task_id, True, '文章內容抓取完成')
                    
                    return {
                        'success': True,
                        'message': '文章內容抓取完成'
                    }
                except Exception as e:
                    # 更新任務歷史記錄
                    history_update_data = {
                        'end_time': datetime.now(timezone.utc),
                        'status': 'failed',
                        'message': f'文章內容抓取失敗: {str(e)}'
                    }
                    
                    # 驗證歷史記錄更新資料
                    validated_history_update = self.validate_data('TaskHistory', history_update_data, SchemaType.UPDATE)
                    # 更新歷史記錄
                    history_repo.update(history_id, validated_history_update)
                    
                    # 增加重試次數
                    retry_result = self.increment_retry_count(task_id)
                    
                    # 更新任務最後執行狀態
                    tasks_repo.update_last_run(task_id, False, f'文章內容抓取失敗: {str(e)}')
                    
                    return {
                        'success': False,
                        'message': f'文章內容抓取失敗: {str(e)}',
                        'retry_info': retry_result
                    }
        except Exception as e:
            error_msg = f"抓取文章內容失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    def test_crawler_task(self, crawler_data: Dict[str, Any], task_data: Dict[str, Any]) -> Dict[str, Any]:
        """測試爬蟲任務
        
        Args:
            crawler_data: 爬蟲資料
            task_data: 任務資料
            
        Returns:
            Dict[str, Any]: 測試結果
        """
        try:
            # 驗證爬蟲配置和任務資料
            tasks_repo, crawlers_repo, _ = self._get_repositories()
            
            try:
                # 驗證爬蟲配置
                self.validate_data('Crawler', crawler_data, SchemaType.CREATE)
            except ValidationError as e:
                return {
                    'success': False,
                    'message': '爬蟲配置驗證失敗',
                    'errors': str(e)
                }
            
            try:
                # 驗證任務資料
                self.validate_data('CrawlerTask', task_data, SchemaType.CREATE)
            except ValidationError as e:
                return {
                    'success': False,
                    'message': '任務資料驗證失敗',
                    'errors': str(e)
                }
            
            # 設定階段為初始階段
            task_data['current_phase'] = TaskPhase.INIT
            
            # 實際測試爬蟲，收集連結
            try:
                # TODO: 實作實際的爬蟲測試邏輯
                # 這裡僅為示例
                sample_links = [
                    'https://example.com/article1',
                    'https://example.com/article2',
                    'https://example.com/article3'
                ]
                links_found = len(sample_links)
                
                # 測試成功
                return {
                    'success': True,
                    'message': '爬蟲測試成功',
                    'test_results': {
                        'links_found': links_found,
                        'sample_links': sample_links
                    },
                    'task_phase': TaskPhase.LINK_COLLECTION.value
                }
            except Exception as e:
                # 測試爬蟲連結收集失敗
                return {
                    'success': False,
                    'message': f'爬蟲連結收集測試失敗: {str(e)}',
                    'task_phase': TaskPhase.INIT.value
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
                
                # 驗證歷史記錄更新資料
                validated_history_data = self.validate_data('TaskHistory', history_data, SchemaType.UPDATE)
                # 更新歷史記錄
                history_repo.update(latest_history.id, validated_history_data)
                
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

    def get_failed_tasks(self, days: int = 1) -> Dict:
        """獲取最近失敗的任務"""
        try:
            with self._transaction():
                tasks_repo, _, _ = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'tasks': []
                    }
                    
                failed_tasks = tasks_repo.get_failed_tasks(days)
                return {
                    'success': True,
                    'message': f'成功獲取最近 {days} 天失敗的任務',
                    'tasks': failed_tasks
                }
        except Exception as e:
            error_msg = f"獲取失敗任務時發生錯誤: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'tasks': []
            }

    def toggle_auto_status(self, task_id: int) -> Dict:
        """切換任務的自動執行狀態"""
        try:
            with self._transaction():
                tasks_repo, _, _ = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                    
                success = tasks_repo.toggle_auto_status(task_id)
                return {
                    'success': success,
                    'message': '自動執行狀態切換成功' if success else '任務不存在'
                }
        except Exception as e:
            error_msg = f"切換任務自動執行狀態失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
            
    def toggle_ai_only_status(self, task_id: int) -> Dict:
        """切換任務的AI收集狀態"""
        try:
            with self._transaction():
                tasks_repo, _, _ = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                    
                success = tasks_repo.toggle_ai_only_status(task_id)
                return {
                    'success': success,
                    'message': 'AI收集狀態切換成功' if success else '任務不存在'
                }
        except Exception as e:
            error_msg = f"切換任務AI收集狀態失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    def update_task_notes(self, task_id: int, notes: str) -> Dict:
        """更新任務備註"""
        try:
            with self._transaction():
                tasks_repo, _, _ = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                    
                success = tasks_repo.update_notes(task_id, notes)
                return {
                    'success': success,
                    'message': '備註更新成功' if success else '任務不存在'
                }
        except Exception as e:
            error_msg = f"更新任務備註失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    def find_tasks_by_multiple_crawlers(self, crawler_ids: List[int]) -> Dict:
        """根據多個爬蟲ID查詢任務"""
        try:
            with self._transaction():
                tasks_repo, _, _ = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'tasks': []
                    }
                    
                tasks = tasks_repo.find_tasks_by_multiple_crawlers(crawler_ids)
                return {
                    'success': True,
                    'message': '任務查詢成功',
                    'tasks': tasks
                }
        except Exception as e:
            error_msg = f"根據多個爬蟲ID查詢任務失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'tasks': []
            }
    
    def find_tasks_by_cron_expression(self, cron_expression: str) -> Dict:
        """根據 cron 表達式查詢任務"""
        try:
            with self._transaction():
                tasks_repo, _, _ = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'tasks': []
                    }
                    
                tasks = tasks_repo.find_tasks_by_cron_expression(cron_expression)
                return {
                    'success': True,
                    'message': '任務查詢成功',
                    'tasks': tasks
                }
        except ValidationError as e:
            error_msg = f"cron 表達式驗證失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'tasks': []
            }
        except Exception as e:
            error_msg = f"根據 cron 表達式查詢任務失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'tasks': []
            }
    
    def find_pending_tasks(self, cron_expression: str) -> Dict:
        """查詢需要執行的任務（根據 cron 表達式和上次執行時間）"""
        try:
            with self._transaction():
                tasks_repo, _, _ = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'tasks': []
                    }
                    
                tasks = tasks_repo.find_pending_tasks(cron_expression)
                return {
                    'success': True,
                    'message': '待執行任務查詢成功',
                    'tasks': tasks
                }
        except ValidationError as e:
            error_msg = f"cron 表達式驗證失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'tasks': []
            }
        except Exception as e:
            error_msg = f"查詢待執行任務失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'tasks': []
            }
    
    def update_task_last_run(self, task_id: int, success: bool, message: Optional[str] = None) -> Dict:
        """更新任務的最後執行狀態"""
        try:
            with self._transaction():
                tasks_repo, _, _ = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                    
                result = tasks_repo.update_last_run(task_id, success, message)
                return {
                    'success': result,
                    'message': '任務執行狀態更新成功' if result else '任務不存在'
                }
        except Exception as e:
            error_msg = f"更新任務執行狀態失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    def update_task_phase(self, task_id: int, phase: TaskPhase) -> Dict:
        """更新任務階段
        
        Args:
            task_id: 任務ID
            phase: 任務階段
            
        Returns:
            更新結果
        """
        try:
            with self._transaction():
                tasks_repo, _, _ = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在'
                    }
                
                # 更新任務階段
                task_data = {'current_phase': phase}
                result = tasks_repo.update(task_id, task_data)
                
                return {
                    'success': True,
                    'message': f'任務階段更新為 {phase.value}',
                    'task': result
                }
        except Exception as e:
            error_msg = f"更新任務階段失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    def increment_retry_count(self, task_id: int) -> Dict:
        """增加任務重試次數
        
        Args:
            task_id: 任務ID
            
        Returns:
            更新結果，包含當前重試次數和是否超過最大重試次數
        """
        try:
            with self._transaction():
                tasks_repo, _, _ = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在'
                    }
                
                # 檢查是否已超過最大重試次數
                if task.retry_count >= task.max_retries:
                    return {
                        'success': False,
                        'message': f'已超過最大重試次數 {task.max_retries}',
                        'exceeded_max_retries': True,
                        'retry_count': task.retry_count,
                        'max_retries': task.max_retries
                    }
                
                # 增加重試次數
                current_retry = task.retry_count + 1
                task_data = {'retry_count': current_retry}
                result = tasks_repo.update(task_id, task_data)
                
                # 檢查是否達到最大重試次數
                has_reached_max = current_retry >= task.max_retries
                
                return {
                    'success': True,
                    'message': f'重試次數更新為 {current_retry}/{task.max_retries}',
                    'retry_count': current_retry,
                    'max_retries': task.max_retries,
                    'exceeded_max_retries': has_reached_max,
                    'task': result
                }
        except Exception as e:
            error_msg = f"更新重試次數失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    def reset_retry_count(self, task_id: int) -> Dict:
        """重置任務重試次數
        
        Args:
            task_id: 任務ID
            
        Returns:
            更新結果
        """
        try:
            with self._transaction():
                tasks_repo, _, _ = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在'
                    }
                
                # 重置重試次數
                task_data = {'retry_count': 0}
                result = tasks_repo.update(task_id, task_data)
                
                return {
                    'success': True,
                    'message': '重試次數已重置',
                    'task': result
                }
        except Exception as e:
            error_msg = f"重置重試次數失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    def update_max_retries(self, task_id: int, max_retries: int) -> Dict:
        """更新任務最大重試次數
        
        Args:
            task_id: 任務ID
            max_retries: 最大重試次數
            
        Returns:
            更新結果
        """
        if max_retries < 0:
            return {
                'success': False,
                'message': '最大重試次數不能小於 0'
            }
        
        try:
            with self._transaction():
                tasks_repo, _, _ = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在'
                    }
                
                # 更新最大重試次數
                task_data = {'max_retries': max_retries}
                result = tasks_repo.update(task_id, task_data)
                
                return {
                    'success': True,
                    'message': f'最大重試次數更新為 {max_retries}',
                    'task': result
                }
        except Exception as e:
            error_msg = f"更新最大重試次數失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    def get_retryable_tasks(self) -> Dict:
        """獲取可重試的任務 (最近失敗但未超過最大重試次數的任務)
        
        Returns:
            可重試的任務清單
        """
        try:
            with self._transaction():
                tasks_repo, _, _ = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'tasks': []
                    }
                
                # 獲取最近失敗的任務
                failed_tasks = tasks_repo.get_failed_tasks(days=1)
                
                # 過濾出可重試的任務 (重試次數未達最大值)
                retryable_tasks = [task for task in failed_tasks if task.retry_count < task.max_retries]
                
                return {
                    'success': True,
                    'message': f'找到 {len(retryable_tasks)} 個可重試的任務',
                    'tasks': retryable_tasks
                }
        except Exception as e:
            error_msg = f"獲取可重試任務失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'tasks': []
            }

    def collect_article_links(self, task_id: int) -> Dict[str, Any]:
        """ 收集文章連結
            使用情境：
                1. 手動任務：當使用者手動選擇要收集連結時，會使用此方法
                2. 自動任務：當任務執行時，會使用此方法

        Args:
            task_id: 任務ID
            
        Returns:
            Dict[str, Any]: 執行結果，包含收集到的連結數量
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
                    'message': '開始收集文章連結'
                }
                
                # 先驗證歷史記錄資料
                validated_history_data = self.validate_data('TaskHistory', history_data, SchemaType.CREATE)
                # 創建歷史記錄
                history = history_repo.create(validated_history_data)
                history_id = history.id if history else None
                
                try:
                    # 更新任務階段為連結收集階段
                    self.update_task_phase(task_id, TaskPhase.LINK_COLLECTION)
                    
                    # TODO: 執行連結收集邏輯
                    # 假設收集到的連結數量
                    links_found = 0
                    
                    # 更新任務歷史記錄
                    history_update_data = {
                        'end_time': datetime.now(timezone.utc),
                        'status': 'completed',
                        'message': f'文章連結收集完成，共收集 {links_found} 個連結',
                        'articles_count': links_found  # 更新收集到的文章數量
                    }
                    
                    # 驗證歷史記錄更新資料
                    validated_history_update = self.validate_data('TaskHistory', history_update_data, SchemaType.UPDATE)
                    # 更新歷史記錄
                    history_repo.update(history_id, validated_history_update)
                    
                    # 根據配置決定是否繼續進行內容抓取，這裡簡單檢查任務是否為自動執行
                    should_fetch_content = task.is_auto
                    
                    if links_found > 0 and should_fetch_content:
                        # 這裡可以直接調用抓取內容的方法，或者返回連結列表讓呼叫者決定
                        # 以下只是示例，實際使用時可能需要調整
                        # self.fetch_article_content(task_id, link_ids)
                        next_step = "content_scraping"
                    else:
                        # 如果沒有找到連結或不需要抓取內容，則將任務標記為完成
                        self.update_task_phase(task_id, TaskPhase.COMPLETED)
                        next_step = "completed"
                    
                    # 成功執行後重置重試次數
                    self.reset_retry_count(task_id)
                    
                    # 更新任務最後執行狀態
                    tasks_repo.update_last_run(task_id, True, f'文章連結收集完成，共收集 {links_found} 個連結')
                    
                    return {
                        'success': True,
                        'message': f'文章連結收集完成，共收集 {links_found} 個連結',
                        'links_found': links_found,
                        'next_step': next_step
                    }
                except Exception as e:
                    # 更新任務歷史記錄
                    history_update_data = {
                        'end_time': datetime.now(timezone.utc),
                        'status': 'failed',
                        'message': f'文章連結收集失敗: {str(e)}'
                    }
                    
                    # 驗證歷史記錄更新資料
                    validated_history_update = self.validate_data('TaskHistory', history_update_data, SchemaType.UPDATE)
                    # 更新歷史記錄
                    history_repo.update(history_id, validated_history_update)
                    
                    # 增加重試次數
                    retry_result = self.increment_retry_count(task_id)
                    
                    # 更新任務最後執行狀態
                    tasks_repo.update_last_run(task_id, False, f'文章連結收集失敗: {str(e)}')
                    
                    return {
                        'success': False,
                        'message': f'文章連結收集失敗: {str(e)}',
                        'retry_info': retry_result
                    }
        except Exception as e:
            error_msg = f"收集文章連結失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }