from typing import Dict, Any, Optional, List, Tuple, Type, cast
from concurrent.futures import ThreadPoolExecutor
import logging
import threading
from datetime import datetime, timezone
from src.models.base_model import Base
from src.services.base_service import BaseService
from src.database.base_repository import BaseRepository
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.database.crawlers_repository import CrawlersRepository
from src.database.crawler_task_history_repository import CrawlerTaskHistoryRepository
from src.models.crawler_tasks_model import CrawlerTasks, ScrapePhase
from src.models.crawlers_model import Crawlers
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.database.base_repository import SchemaType

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TaskExecutorService(BaseService[CrawlerTasks]):
    """統一的任務執行服務，處理所有類型的任務執行"""

    def __init__(self, db_manager=None, max_workers=10):
        """初始化任務執行服務

        Args:
            db_manager: 資料庫管理器
            max_workers: 最大工作執行緒數量
        """
        super().__init__(db_manager)
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.running_tasks = {}  # 執行中的任務 {task_id: future}
        self.task_lock = threading.Lock()  # 用於同步訪問 running_tasks
        
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

    def execute_task(self, task_id: int, is_async: bool = True, **kwargs) -> Dict[str, Any]:
        """執行指定的爬蟲任務

        Args:
            task_id: 任務ID
            is_async: 是否異步執行
            **kwargs: 額外的執行參數

        Returns:
            Dict[str, Any]: 執行結果
        """
        # 檢查任務是否已在執行中
        with self.task_lock:
            if task_id in self.running_tasks:
                return {
                    'success': False,
                    'message': '任務已在執行中'
                }

        try:
            # 使用事務獲取任務資訊
            with self._transaction():
                tasks_repo, crawlers_repo, history_repo = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                
                # 檢查任務是否存在
                task = tasks_repo.find_tasks_by_id(task_id, is_active=True)
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
                
                # 如果是異步執行，提交到執行緒池
                if is_async:
                    with self.task_lock:
                        future = self.thread_pool.submit(self._execute_task_internal, task, **kwargs)
                        self.running_tasks[task_id] = future
                        # 設置完成回調，清理執行中的任務
                        future.add_done_callback(lambda f: self._task_completion_callback(task_id, f))

                    return {
                        'success': True,
                        'message': f'任務 {task_id} 已提交執行',
                        'task_id': task_id,
                        'status': 'executing'
                    }
                else:
                    # 同步執行，直接返回結果
                    return self._execute_task_internal(task, **kwargs)
        except Exception as e:
            error_msg = f"準備執行任務失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    def _task_completion_callback(self, task_id: int, future):
        """任務完成回調函數，清理執行中的任務記錄

        Args:
            task_id: 任務ID
            future: Future對象
        """
        with self.task_lock:
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]

        # 檢查是否有異常
        if future.exception():
            logger.error(f"任務 {task_id} 執行失敗: {future.exception()}")

    def _execute_task_internal(self, task, **kwargs) -> Dict[str, Any]:
        """內部任務執行函數

        Args:
            task: 任務對象
            **kwargs: 額外參數

        Returns:
            Dict[str, Any]: 執行結果
        """
        task_id = task.id
        crawler_name = task.crawler.crawler_name if task.crawler else None

        # 記錄開始執行
        logger.info(f"開始執行任務 {task_id} (爬蟲: {crawler_name})")

        try:
            # 使用 with self._transaction() 確保資料庫操作的一致性
            with self._transaction():
                # 獲取爬蟲實例
                from src.crawlers.crawler_factory import CrawlerFactory
                crawler = CrawlerFactory.get_crawler(crawler_name)

                # 準備任務參數
                task_args = task.task_args

                # 合併傳入的額外參數
                if kwargs:
                    task_args.update(kwargs)

                # 執行爬蟲任務
                result = crawler.execute_task(task_id, task_args)

                return result
        except Exception as e:
            error_msg = f"執行任務 {task_id} 時發生錯誤: {str(e)}"
            logger.exception(error_msg)

            return {
                'success': False,
                'message': error_msg
            }

    def cancel_task(self, task_id: int) -> Dict[str, Any]:
        """取消正在執行的任務

        Args:
            task_id: 任務ID

        Returns:
            Dict[str, Any]: 取消結果
        """
        try:
            with self.task_lock:
                if task_id not in self.running_tasks:
                    return {
                        'success': False,
                        'message': '任務未在執行中或已完成'
                    }

                future = self.running_tasks[task_id]
                cancelled = future.cancel()

            # 使用事務更新任務狀態
            with self._transaction():
                tasks_repo, = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                
                # 更新任務狀態為已取消
                task_data = {'scrape_phase': ScrapePhase.CANCELLED}
                tasks_repo.update(task_id, task_data)

                if cancelled:
                    return {
                        'success': True,
                        'message': f'任務 {task_id} 已取消'
                    }
                else:
                    return {
                        'success': False,
                        'message': f'無法取消任務 {task_id}，可能已在執行中'
                    }
        except Exception as e:
            error_msg = f"取消任務失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    def get_scrape_phase(self, task_id: int) -> Dict[str, Any]:
        """獲取任務執行狀態

        Args:
            task_id: 任務ID

        Returns:
            Dict[str, Any]: 任務狀態
        """
        with self.task_lock:
            is_running = task_id in self.running_tasks

        if is_running:
            return {
                'success': True,
                'status': 'executing',
                'message': f'任務 {task_id} 正在執行中'
            }

        try:
            # 使用事務從資料庫獲取最新狀態
            with self._transaction():
                tasks_repo, = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'status': 'unknown'
                    }
                
                # 檢查任務是否存在
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在',
                        'status': 'unknown'
                    }
                
                # 根據任務階段返回狀態
                status = task.scrape_phase.value if task.scrape_phase else 'unknown'
                return {
                    'success': True,
                    'status': status,
                    'message': f'任務 {task_id} 狀態: {status}',
                    'task': task.to_dict()
                }
        except Exception as e:
            error_msg = f"獲取任務狀態失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'status': 'error'
            }

    def get_running_tasks(self) -> Dict[str, Any]:
        """獲取所有正在執行的任務

        Returns:
            Dict[str, Any]: 正在執行的任務列表
        """
        with self.task_lock:
            running_task_ids = list(self.running_tasks.keys())

        return {
            'success': True,
            'message': f'找到 {len(running_task_ids)} 個執行中的任務',
            'running_tasks': running_task_ids
        }