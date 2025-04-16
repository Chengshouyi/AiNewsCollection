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
from src.utils.enum_utils import TaskStatus

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
        self.running_crawlers = {}  # 執行中的爬蟲實例 {task_id: crawler}
        self.task_lock = threading.Lock()  # 用於同步訪問 running_tasks
        self.task_execution_status = {}  # 任務執行狀態 {task_id: {'task_status': TaskStatus, 'scrape_phase': ScrapePhase}}
        
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
                
                # 檢查任務是否已在執行中
                if task.task_status == TaskStatus.RUNNING.value:
                    return {
                        'success': False,
                        'message': '任務已在執行中'
                    }
                
                # 創建任務歷史記錄
                history_data = {
                    'task_id': task_id,
                    'start_time': datetime.now(timezone.utc),
                    'task_status': TaskStatus.RUNNING.value,
                    'message': '任務開始執行'
                }
                # 先驗證歷史記錄資料
                validated_history_data = self.validate_data('TaskHistory', history_data, SchemaType.CREATE)
                # 創建歷史記錄
                history = history_repo.create(validated_history_data)
                history_id = history.id if history else None
                
                # 更新任務狀態
                task_data = {
                    'task_status': TaskStatus.RUNNING.value,
                    'scrape_phase': ScrapePhase.INIT.value
                }
                tasks_repo.update(task_id, task_data)
                
                # 如果是異步執行，提交到執行緒池
                if is_async:
                    with self.task_lock:
                        future = self.thread_pool.submit(self._execute_task_internal, task, history_id, **kwargs)
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
                    return self._execute_task_internal(task, history_id, **kwargs)
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
                logger.info(f"清除執行中的任務 {task_id}")
                del self.running_tasks[task_id]
            # 清除爬蟲實例
            if task_id in self.running_crawlers:
                logger.info(f"清除爬蟲實例 {task_id}")
                del self.running_crawlers[task_id]

        # 檢查是否有異常
        if future.exception():
            logger.error(f"任務 {task_id} 執行失敗: {future.exception()}")
            try:
                # 更新任務狀態為失敗
                with self._transaction():
                    tasks_repo, _, history_repo = self._get_repositories()
                    if tasks_repo:
                        task_data = {
                            'task_status': TaskStatus.FAILED.value,
                            'scrape_phase': ScrapePhase.FAILED.value
                        }
                        tasks_repo.update(task_id, task_data)
            except Exception as e:
                logger.error(f"更新失敗任務狀態失敗: {str(e)}")

    def _execute_task_internal(self, task, history_id, **kwargs) -> Dict[str, Any]:
        """內部任務執行函數

        Args:
            task: 任務對象
            history_id: 任務歷史ID
            **kwargs: 額外參數

        Returns:
            Dict[str, Any]: 執行結果
        """
        task_id = task.id
        _, crawler_repo, _ = self._get_repositories()
        crawler = crawler_repo.get_by_id(task.crawler_id)
        crawler_name = crawler.crawler_name if crawler else None

        # 記錄開始執行
        logger.info(f"開始執行任務 {task_id} (爬蟲: {crawler_name})")

        try:
            # 使用 with self._transaction() 確保資料庫操作的一致性
            with self._transaction():
                tasks_repo, _, history_repo = self._get_repositories()
                
                # 獲取爬蟲實例
                from src.crawlers.crawler_factory import CrawlerFactory
                # 確保crawler_name不為None
                if crawler_name is None:
                    # 更新任務狀態為失敗
                    task_data = {
                        'task_status': TaskStatus.FAILED.value,
                        'scrape_phase': ScrapePhase.FAILED.value
                    }
                    tasks_repo.update(task_id, task_data)
                    
                    # 更新任務歷史記錄
                    if history_id:
                        history_data = {
                            'end_time': datetime.now(timezone.utc),
                            'task_status': TaskStatus.FAILED.value,
                            'message': '爬蟲名稱不存在，任務執行失敗'
                        }
                        validated_history_data = self.validate_data('TaskHistory', history_data, SchemaType.UPDATE)
                        history_repo.update(history_id, validated_history_data)
                    
                    # 更新任務最後執行狀態
                    self.update_task_last_run(task_id, False, '爬蟲名稱不存在，任務執行失敗')
                    
                    return {
                        'success': False,
                        'message': '爬蟲名稱不存在，任務執行失敗'
                    }
                
                crawler = CrawlerFactory.get_crawler(crawler_name)
                
                # 儲存爬蟲實例以便取消任務時使用
                with self.task_lock:
                    self.running_crawlers[task_id] = crawler

                # 準備任務參數
                task_args = task.task_args

                # 合併傳入的額外參數
                if kwargs:
                    task_args.update(kwargs)

                # 執行爬蟲任務
                result = crawler.execute_task(task_id, task_args)
                
                # 更新任務狀態
                task_status = TaskStatus.COMPLETED.value if result.get('success', False) else TaskStatus.FAILED.value
                scrape_phase = ScrapePhase.COMPLETED.value if result.get('success', False) else ScrapePhase.FAILED.value
                
                task_data = {
                    'task_status': task_status,
                    'scrape_phase': scrape_phase
                }
                tasks_repo.update(task_id, task_data)
                
                # 更新任務歷史記錄
                if history_id:
                    history_data = {
                        'end_time': datetime.now(timezone.utc),
                        'task_status': task_status,
                        'message': result.get('message', '任務執行完成' if result.get('success', False) else '任務執行失敗'),
                        'articles_count': result.get('articles_count', 0)
                    }
                    validated_history_data = self.validate_data('TaskHistory', history_data, SchemaType.UPDATE)
                    history_repo.update(history_id, validated_history_data)
                
                # 更新任務最後執行狀態
                self.update_task_last_run(
                    task_id, 
                    result.get('success', False), 
                    result.get('message', '任務執行完成' if result.get('success', False) else '任務執行失敗')
                )
                
                # 清除爬蟲實例
                with self.task_lock:
                    if task_id in self.running_crawlers:
                        del self.running_crawlers[task_id]

                result['task_status'] = task_status
                return result
        except Exception as e:
            error_msg = f"執行任務 {task_id} 時發生錯誤: {str(e)}"
            logger.exception(error_msg)
            
            try:
                # 更新任務狀態為失敗
                with self._transaction():
                    tasks_repo, _, history_repo = self._get_repositories()
                    if tasks_repo:
                        task_data = {
                            'task_status': TaskStatus.FAILED.value,
                            'scrape_phase': ScrapePhase.FAILED.value
                        }
                        tasks_repo.update(task_id, task_data)
                    
                    # 更新任務歷史記錄
                    if history_id and history_repo:
                        history_data = {
                            'end_time': datetime.now(timezone.utc),
                            'task_status': TaskStatus.FAILED.value,
                            'message': error_msg
                        }
                        validated_history_data = self.validate_data('TaskHistory', history_data, SchemaType.UPDATE)
                        history_repo.update(history_id, validated_history_data)
                    
                    # 更新任務最後執行狀態
                    self.update_task_last_run(task_id, False, error_msg)
            except Exception as update_error:
                logger.error(f"更新失敗任務狀態失敗: {str(update_error)}")
            
            # 清除爬蟲實例
            with self.task_lock:
                if task_id in self.running_crawlers:
                    del self.running_crawlers[task_id]

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
            # 檢查任務是否在執行中並嘗試取消執行緒
            with self.task_lock:
                is_running = task_id in self.running_tasks
                has_crawler = task_id in self.running_crawlers
                
                if is_running:
                    future = self.running_tasks[task_id]
                    # 嘗試取消執行緒
                    thread_cancelled = future.cancel()
                else:
                    thread_cancelled = False
                
                # 如果沒有對應的爬蟲實例，無法進行完整的取消操作
                if not has_crawler:
                    logger.warning(f"任務 {task_id} 沒有對應的運行中爬蟲實例")

            # 使用事務更新任務狀態
            with self._transaction():
                tasks_repo, _, history_repo = self._get_repositories()
                if not tasks_repo:
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
                
                # 如果有爬蟲實例，嘗試取消爬蟲任務
                crawler_cancelled = False
                if has_crawler:
                    crawler = self.running_crawlers[task_id]
                    
                    # 確保任務存在且task_args可訪問
                    task_args = getattr(task, 'task_args', {})
                    
                    # 配置任務的取消參數 - 使其支援新的部分數據保存功能
                    # 根據任務的設定決定是否保存部分結果
                    save_partial_results = task_args.get('save_partial_results_on_cancel', False)
                    save_partial_to_database = task_args.get('save_partial_to_database', False)
                    
                    # 更新全局參數以支持取消時的數據處理
                    crawler.global_params = getattr(crawler, 'global_params', {})
                    crawler.global_params['save_partial_results_on_cancel'] = save_partial_results
                    crawler.global_params['save_partial_to_database'] = save_partial_to_database
                    
                    # 呼叫爬蟲取消方法
                    crawler_cancelled = crawler.cancel_task(task_id)
                
                # 確定是否取消成功 (執行緒或爬蟲取消其中一個成功即可)
                cancelled = thread_cancelled or crawler_cancelled
                
                if cancelled:
                    # 創建任務取消的歷史記錄
                    history_data = {
                        'task_id': task_id,
                        'start_time': datetime.now(timezone.utc),
                        'end_time': datetime.now(timezone.utc),
                        'task_status': TaskStatus.CANCELLED.value,
                        'message': '任務已被使用者取消'
                    }
                    validated_history_data = self.validate_data('TaskHistory', history_data, SchemaType.CREATE)
                    history_repo.create(validated_history_data)
                    
                    # 更新任務狀態為已取消
                    task_data = {
                        'task_status': TaskStatus.CANCELLED.value,
                        'scrape_phase': ScrapePhase.CANCELLED.value
                    }
                    tasks_repo.update(task_id, task_data)
                    
                    # 更新任務最後執行狀態
                    self.update_task_last_run(task_id, False, '任務已被使用者取消')
                    
                    # 清除爬蟲實例
                    with self.task_lock:
                        if task_id in self.running_crawlers:
                            del self.running_crawlers[task_id]
                    
                    return {
                        'success': True,
                        'message': f'任務 {task_id} 已取消'
                    }
                else:
                    return {
                        'success': False,
                        'message': f'無法取消任務 {task_id}，可能任務已完成或尚未開始執行'
                    }
        except Exception as e:
            error_msg = f"取消任務失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # 清除爬蟲實例
            with self.task_lock:
                if task_id in self.running_crawlers:
                    del self.running_crawlers[task_id]
                    
            return {
                'success': False,
                'message': error_msg
            }

    def get_task_status(self, task_id: int) -> Dict[str, Any]:
        """獲取任務執行狀態

        Args:
            task_id: 任務ID

        Returns:
            Dict[str, Any]: 任務狀態，包含task_status、scrape_phase、進度等資訊
        """
        with self.task_lock:
            is_running = task_id in self.running_tasks

        if is_running:
            return {
                'success': True,
                'task_status': TaskStatus.RUNNING.value,
                'scrape_phase': ScrapePhase.LINK_COLLECTION.value,  # 預設為連結收集階段
                'progress': 50,  # 預設進度
                'message': f'任務 {task_id} 正在執行中'
            }

        try:
            # 使用事務從資料庫獲取最新狀態
            with self._transaction():
                tasks_repo, crawlers_repo, history_repo = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'task_status': TaskStatus.FAILED.value,
                        'scrape_phase': ScrapePhase.FAILED.value,
                        'progress': 0
                    }
                
                # 檢查任務是否存在
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在',
                        'task_status': TaskStatus.FAILED.value,
                        'scrape_phase': ScrapePhase.FAILED.value,
                        'progress': 0
                    }
                
                # 從資料庫獲取最新一筆歷史記錄
                latest_history = history_repo.get_latest_history(task_id)
                
                # 首先從任務狀態獲取最新的任務狀態
                task_status = task.task_status
                
                # 如果歷史記錄中有更新的任務狀態，則使用歷史記錄中的狀態
                if latest_history and latest_history.end_time and latest_history.task_status in [
                    TaskStatus.COMPLETED.value, 
                    TaskStatus.FAILED.value,
                    TaskStatus.CANCELLED.value
                ]:
                    task_status = latest_history.task_status
                
                # 從任務本身獲取爬取階段信息
                scrape_phase = task.scrape_phase
                
                # 計算進度
                progress = 0
                if latest_history:
                    if latest_history.end_time:
                        progress = 100
                    else:
                        # 如果正在執行中，根據開始時間計算大約進度
                        current_time = datetime.now(timezone.utc)
                        if latest_history.start_time:
                            elapsed = current_time - latest_history.start_time
                            # 假設每個任務平均執行時間為 5 分鐘
                            progress = min(95, int((elapsed.total_seconds() / 300) * 100))
                
                return {
                    'success': True,
                    'task_status': task_status,
                    'scrape_phase': scrape_phase,
                    'progress': progress,
                    'message': latest_history.message if latest_history and latest_history.message else '',
                    'task': task.to_dict()
                }
        except Exception as e:
            error_msg = f"獲取任務狀態失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'task_status': TaskStatus.FAILED.value,
                'scrape_phase': ScrapePhase.FAILED.value,
                'progress': 0
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
    
    def fetch_full_article(self, task_id: int, is_async: bool = True, **kwargs) -> Dict[str, Any]:
        """獲取完整文章內容的任務

        Args:
            task_id: 任務ID
            is_async: 是否異步執行
            **kwargs: 額外的執行參數

        Returns:
            Dict[str, Any]: 執行結果
        """
        return self.execute_task(task_id, is_async, **kwargs)
    
    def collect_links_only(self, task_id: int, is_async: bool = True, **kwargs) -> Dict[str, Any]:
        """僅收集連結的任務

        Args:
            task_id: 任務ID
            is_async: 是否異步執行
            **kwargs: 額外的執行參數

        Returns:
            Dict[str, Any]: 執行結果
        """
        # 在執行任務時指定操作類型
        kwargs['operation_type'] = 'collect_links_only'
        kwargs['scrape_mode'] = 'links_only'
        return self.execute_task(task_id, is_async, **kwargs)
    
    def fetch_content_only(self, task_id: int, is_async: bool = True, **kwargs) -> Dict[str, Any]:
        """僅獲取內容的任務

        Args:
            task_id: 任務ID
            is_async: 是否異步執行
            **kwargs: 額外的執行參數

        Returns:
            Dict[str, Any]: 執行結果
                success: 是否成功
                message: 任務執行結果訊息
                articles: 文章列表
        """
        # 在執行任務時指定操作類型
        kwargs['operation_type'] = 'fetch_content_only'
        kwargs['scrape_mode'] = 'content_only'
        return self.execute_task(task_id, is_async, **kwargs)
    
    def test_crawler(self, crawler_name: str, test_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """測試爬蟲

        Args:
            crawler_name: 爬蟲名稱
            test_params: 測試參數

        Returns:
            Dict[str, Any]: 測試結果
        """
        try:
            # 確保test_params不為None
            if test_params is None:
                test_params = {}
                
            # 使用事務確保一致性
            with self._transaction():
                # 獲取爬蟲實例
                from src.crawlers.crawler_factory import CrawlerFactory
                
                
                # 預防設置錯誤，強制設定測試參數
                test_params['scrape_mode'] = 'links_only'
                test_params['is_test'] = True
                test_params['max_pages'] = min(1, test_params.get('max_pages', 1))
                test_params['num_articles'] = min(5, test_params.get('num_articles', 5))
                test_params['save_to_csv'] = False
                test_params['save_to_database'] = False
                test_params['timeout'] = 30
                
                crawler = CrawlerFactory.get_crawler(crawler_name)
                
                # 執行測試，明確將返回值轉換為字典
                test_result = crawler.execute_task(0, test_params)
                
                # 確保返回字典
                if test_result is None:
                    test_result = {}
                
                return {
                    'success': test_result.get('success', False),
                    'message': test_result.get('message', '爬蟲測試完成'),
                    'result': test_result
                }
        except Exception as e:
            error_msg = f"測試爬蟲 {crawler_name} 時發生錯誤: {str(e)}"
            logger.exception(error_msg)
            
            return {
                'success': False,
                'message': error_msg
            }

    def update_task_last_run(self, task_id: int, success: bool, message: Optional[str] = None) -> Dict[str, Any]:
        """更新任務的最後執行狀態

        Args:
            task_id: 任務ID
            success: 執行是否成功
            message: 執行結果訊息

        Returns:
            Dict[str, Any]: 更新結果
        """
        try:
            with self._transaction():
                tasks_repo, _, _ = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                
                # 更新任務的最後執行時間和狀態
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在'
                    }
                
                # 更新最後執行時間和狀態
                now = datetime.now(timezone.utc)
                task_data = {
                    'last_run_at': now,
                    'last_run_success': success
                }
                
                if message:
                    task_data['last_run_message'] = message
                
                result = tasks_repo.update(task_id, task_data)
                
                return {
                    'success': True,
                    'message': '任務最後執行狀態更新成功',
                    'task': result
                }
        except Exception as e:
            error_msg = f"更新任務最後執行狀態失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }