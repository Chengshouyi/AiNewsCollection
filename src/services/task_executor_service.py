from typing import Dict, Any, Optional, List, Tuple, Type, cast
from concurrent.futures import ThreadPoolExecutor, Future
import logging
import threading
from datetime import datetime, timezone
from sqlalchemy.orm import Session
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
from src.models.crawler_tasks_schema import CrawlerTaskReadSchema
from src.web.socket_instance import socketio
from src.services.service_container import get_crawlers_service, get_article_service


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

        history_id = None # 初始化 history_id
        task_orm_for_sync = None # 初始化用於同步執行的 ORM 對象

        try:
            # 使用事務獲取任務資訊並創建歷史記錄
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('TaskHistory', session))
                
                # 檢查任務是否存在
                task = tasks_repo.get_task_by_id(task_id, is_active=True)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在'
                    }
                
                # 檢查任務是否已在執行中 (DB state)
                if task.task_status == TaskStatus.RUNNING.value:
                    return {
                        'success': False,
                        'message': '任務已在執行中'
                    }
                
                # 驗證歷史記錄資料
                history_data_for_validation = { 
                    'task_id': task_id,
                    'start_time': datetime.now(timezone.utc),
                    'task_status': TaskStatus.RUNNING.value,
                    'message': '任務開始執行'
                }
                validated_history_data = history_repo.validate_data(history_data_for_validation, SchemaType.CREATE)
                
                # 創建任務歷史記錄
                history = history_repo.create(validated_history_data)
                session.flush() # Flush to get history ID if needed
                history_id = history.id if history else None

                if history_id is None:
                     # 如果 history_id 創建失敗，記錄錯誤並返回
                     logger.error(f"任務 {task_id} 的歷史記錄創建失敗。")
                     return {
                         'success': False,
                         'message': f'任務 {task_id} 的歷史記錄創建失敗。'
                     }
                
                # 更新任務狀態
                task_data = {
                    'task_status': TaskStatus.RUNNING.value,
                    'scrape_phase': ScrapePhase.INIT.value
                }
                # 使用 update 方法返回的對象，確保狀態已更新
                updated_task = tasks_repo.update(task_id, task_data)
                if not updated_task:
                    logger.error(f"更新任務 {task_id} 狀態為 RUNNING 失敗。")
                    # 嘗試回滾或清理歷史記錄？目前僅記錄錯誤並返回
                    return {
                        'success': False,
                        'message': f'更新任務 {task_id} 狀態為 RUNNING 失敗。'
                    }
                
                # 保存 ORM 對象，僅用於可能的同步執行
                task_orm_for_sync = updated_task 
                session.flush() # Ensure task status is updated before proceeding
                
            # --- 事務結束 --- 
            
            # 如果是異步執行，提交到執行緒池 (在事務外部提交)
            if is_async:
                with self.task_lock:
                    # 只傳遞 ID 和 history_id，不傳遞 ORM 對象
                    future = self.thread_pool.submit(self._execute_task_internal, task_id, history_id, **kwargs)
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
                # 同步執行，直接調用內部方法，傳遞 ID 和 history_id
                # 注意：同步執行時，_execute_task_internal 會建立自己的事務
                if task_orm_for_sync:
                    return self._execute_task_internal(task_id, history_id, **kwargs)
                else:
                    # 如果前面的事務中獲取 task 失敗，這裡返回錯誤
                    return {
                        'success': False,
                        'message': f'無法獲取任務 {task_id} 進行同步執行。' 
                    }
        except Exception as e:
            error_msg = f"準備執行任務失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # 嘗試清理可能已創建的歷史記錄 (如果 history_id 有值)
            if history_id:
                try:
                    with self._transaction() as cleanup_session:
                         history_repo_cleanup = cast(CrawlerTaskHistoryRepository, self._get_repository('TaskHistory', cleanup_session))
                         history_repo_cleanup.delete(history_id)
                         logger.info(f"已清理因準備失敗而創建的歷史記錄 {history_id}")
                except Exception as cleanup_error:
                     logger.error(f"清理歷史記錄 {history_id} 失敗: {cleanup_error}")
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
            error_info = future.exception()
            error_msg = f"任務 {task_id} 執行失敗: {error_info}"
            room_name = f'task_{task_id}'
            fail_data = {
                'task_id': task_id,
                'progress': 100,
                'status': TaskStatus.FAILED.value,
                'scrape_phase': ScrapePhase.FAILED.value,
                'message': error_msg
            }
            socketio.emit('task_progress', fail_data, namespace='/tasks', to=room_name)
            socketio.emit('task_finished', {'task_id': task_id, 'status': TaskStatus.FAILED.value}, namespace='/tasks', to=room_name)
            logger.info(f"異步任務回調: 已發送 WebSocket 事件: task_progress (失敗) 和 task_finished 至 room {room_name}")

    def _execute_task_internal(self, task_id: int, history_id: Optional[int], **kwargs) -> Dict[str, Any]:
        """內部任務執行函數 (工作線程)

        Args:
            task_id: 任務ID
            history_id: 任務歷史ID (可能為 None)
            **kwargs: 額外參數

        Returns:
            Dict[str, Any]: 執行結果
        """
        crawler_name = None
        task: Optional[CrawlerTasks] = None # 初始化 task

        try:
            # 在工作線程的事務中重新獲取任務和爬蟲信息
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('TaskHistory', session))
                crawler_repo = cast(CrawlersRepository, self._get_repository('Crawler', session))

                # 重新獲取任務對象
                task = tasks_repo.get_by_id(task_id)
                if not task:
                     # 如果在執行時任務已被刪除
                     logger.error(f"內部執行時找不到任務 {task_id}")
                     # 更新對應的歷史記錄為失敗 (如果存在)
                     if history_id:
                          try:
                              history_data = {
                                  'end_time': datetime.now(timezone.utc),
                                  'task_status': TaskStatus.FAILED.value,
                                  'message': f'執行時找不到任務 {task_id}'
                              }
                              validated_history_data = history_repo.validate_data(history_data, SchemaType.UPDATE)
                              updated_history = history_repo.update(history_id, validated_history_data)
                              if not updated_history:
                                  logger.error(f"更新找不到任務 {task_id} 的歷史記錄 {history_id} 失敗 (history_repo.update 返回 None)")
                              session.flush()
                          except Exception as history_update_err:
                               logger.error(f"更新找不到任務 {task_id} 的歷史記錄 {history_id} 失敗: {history_update_err}")
                     return {
                         'success': False,
                         'message': f'執行時找不到任務 {task_id}'
                     }

                # 獲取爬蟲名稱
                crawler = crawler_repo.get_by_id(task.crawler_id)
                if crawler:
                    crawler_name = crawler.crawler_name
                else:
                    # 如果爬蟲不存在，標記任務和歷史失敗
                    logger.error(f"任務 {task_id} 關聯的爬蟲 ID {task.crawler_id} 不存在")
                    task_data = {
                        'task_status': TaskStatus.FAILED.value,
                        'scrape_phase': ScrapePhase.FAILED.value
                    }
                    updated_task_fail = tasks_repo.update(task_id, task_data)
                    if not updated_task_fail:
                         logger.error(f"更新任務 {task_id} 狀態為 FAILED (因找不到爬蟲) 失敗 (tasks_repo.update 返回 None)")
                    if history_id:
                        history_data = {
                            'end_time': datetime.now(timezone.utc),
                            'task_status': TaskStatus.FAILED.value,
                            'message': f'爬蟲 ID {task.crawler_id} 不存在'
                        }
                        validated_history_data = history_repo.validate_data(history_data, SchemaType.UPDATE)
                        updated_history_fail = history_repo.update(history_id, validated_history_data)
                        if not updated_history_fail:
                             logger.error(f"更新歷史記錄 {history_id} 狀態為 FAILED (因找不到爬蟲) 失敗 (history_repo.update 返回 None)")
                    session.flush()
                    return {
                        'success': False,
                        'message': f'爬蟲 ID {task.crawler_id} 不存在'
                    }
                
                # --- 獲取爬蟲實例並執行 --- 
                logger.info(f"開始執行任務 {task_id} (爬蟲: {crawler_name})")
                from src.crawlers.crawler_factory import CrawlerFactory
                crawler_instance = CrawlerFactory.get_crawler(crawler_name)
                
                # 儲存爬蟲實例以便取消任務時使用
                with self.task_lock:
                    self.running_crawlers[task_id] = crawler_instance

                # 準備任務參數 (從重新獲取的 task 對象中讀取)
                task_args = task.task_args or {}

                # 合併傳入的額外參數
                if kwargs:
                    task_args.update(kwargs)

                # 執行爬蟲任務
                result = crawler_instance.execute_task(task_id, task_args)
                
                # --- 更新任務和歷史記錄狀態 --- 
                task_status_enum = TaskStatus.COMPLETED if result.get('success', False) else TaskStatus.FAILED
                scrape_phase_enum = ScrapePhase.COMPLETED if result.get('success', False) else ScrapePhase.FAILED
                message = result.get('message', '任務執行完成' if task_status_enum == TaskStatus.COMPLETED else '任務執行失敗')
                articles_count = result.get('articles_count', 0)

                # 更新任務狀態
                task_data = {
                    'task_status': task_status_enum.value,
                    'scrape_phase': scrape_phase_enum.value,
                    # 更新最後運行狀態也在此事務內完成
                    'last_run_at': datetime.now(timezone.utc),
                    'last_run_success': result.get('success', False),
                    'last_run_message': message
                }
                # 檢查更新操作的結果
                validated_task_data = tasks_repo.validate_data(task_data, SchemaType.UPDATE)
                updated_task_final = tasks_repo.update(task_id, validated_task_data)
                if not updated_task_final:
                     logger.error(f"更新任務 {task_id} 最終狀態失敗 (tasks_repo.update 返回 None)")

                # 更新任務歷史記錄
                if history_id:
                    history_data = {
                        'end_time': datetime.now(timezone.utc), # 確保結束時間一致
                        'task_status': task_status_enum.value,
                        'message': message,
                        'articles_count': articles_count,
                        'success': result.get('success', False) # 補上 success 欄位
                    }
                    validated_history_data = history_repo.validate_data(history_data, SchemaType.UPDATE)
                    # 檢查更新操作的結果
                    updated_history_final = history_repo.update(history_id, validated_history_data)
                    if not updated_history_final:
                         logger.error(f"更新歷史記錄 {history_id} 最終狀態失敗 (history_repo.update 返回 None)")
                
                session.flush() # 確保所有更新寫入

            # --- 事務結束 --- 
            
            # 清除爬蟲實例
            with self.task_lock:
                if task_id in self.running_crawlers:
                    del self.running_crawlers[task_id]

            result['task_status'] = task_status_enum.value

            # 在 _execute_task_internal 方法中，任務開始時
            room_name = f'task_{task_id}'
            start_data = {
                'task_id': task_id,
                'progress': 5,  # 進度 5% 表示開始
                'status': TaskStatus.RUNNING.value,
                'scrape_phase': ScrapePhase.INIT.value,
                'message': f'任務 {task_id} 開始執行 (爬蟲: {crawler_name})'
            }
            socketio.emit('task_progress', start_data, namespace='/tasks', to=room_name)
            logger.info(f"已發送 WebSocket 事件: task_progress (開始) 至 room {room_name}")

            # 在 _execute_task_internal 方法中，任務成功/失敗時
            final_data = {
                'task_id': task_id,
                'progress': 100,
                'status': task_status_enum.value,
                'scrape_phase': scrape_phase_enum.value,
                'message': message,
                'articles_count': articles_count # 添加文章數量
            }
            socketio.emit('task_progress', final_data, namespace='/tasks', to=room_name)
            socketio.emit('task_finished', {'task_id': task_id, 'status': task_status_enum.value}, namespace='/tasks', to=room_name)
            logger.info(f"已發送 WebSocket 事件: task_progress (完成/失敗) 和 task_finished 至 room {room_name}")

            return result
        except Exception as e:
            # --- 通用異常處理 --- 
            error_msg = f"執行任務 {task_id} 時發生內部錯誤: {str(e)}"
            logger.exception(error_msg)
            
            try:
                # 在新的事務中更新任務和歷史記錄為失敗
                with self._transaction() as error_session:
                    tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', error_session))
                    history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('TaskHistory', error_session))
                    
                    # 更新任務狀態
                    if tasks_repo.get_by_id(task_id): # 再次檢查任務是否存在
                        task_data = {
                            'task_status': TaskStatus.FAILED.value,
                            'scrape_phase': ScrapePhase.FAILED.value,
                            'last_run_at': datetime.now(timezone.utc),
                            'last_run_success': False,
                            'last_run_message': error_msg
                        }
                        validated_task_data = tasks_repo.validate_data(task_data, SchemaType.UPDATE)
                        # 檢查更新操作的結果
                        updated_task_err = tasks_repo.update(task_id, validated_task_data)
                        if not updated_task_err:
                            logger.error(f"異常處理中更新任務 {task_id} 狀態為 FAILED 失敗 (tasks_repo.update 返回 None)")

                    # 更新歷史記錄
                    if history_id and history_repo.get_by_id(history_id):
                        history_data = {
                            'end_time': datetime.now(timezone.utc),
                            'task_status': TaskStatus.FAILED.value,
                            'message': error_msg,
                            'success': False
                        }
                        validated_history_data = history_repo.validate_data(history_data, SchemaType.UPDATE)
                        # 檢查更新操作的結果
                        updated_history_err = history_repo.update(history_id, validated_history_data)
                        if not updated_history_err:
                             logger.error(f"異常處理中更新歷史記錄 {history_id} 狀態為 FAILED 失敗 (history_repo.update 返回 None)")

                    error_session.flush()
            except Exception as update_error:
                logger.error(f"寫入任務 {task_id} 失敗狀態時發生錯誤: {str(update_error)}")
            
            # 清除爬蟲實例
            with self.task_lock:
                if task_id in self.running_crawlers:
                    del self.running_crawlers[task_id]

            # 在 _execute_task_internal 方法的異常處理塊中，發送失敗事件
            error_data = {
                'task_id': task_id,
                'progress': 100, # 進度設為 100 表示已結束
                'status': TaskStatus.FAILED.value,
                'scrape_phase': ScrapePhase.FAILED.value,
                'message': error_msg
            }
            room_name = f'task_{task_id}'
            socketio.emit('task_progress', error_data, namespace='/tasks', to=room_name)
            socketio.emit('task_finished', {'task_id': task_id, 'status': TaskStatus.FAILED.value}, namespace='/tasks', to=room_name)
            logger.info(f"異常處理: 已發送 WebSocket 事件: task_progress (失敗) 和 task_finished 至 room {room_name}")

            return {
                'success': False,
                'message': error_msg,
                'task_status': TaskStatus.FAILED.value # 返回失敗狀態
            }

    def cancel_task(self, task_id: int) -> Dict[str, Any]:
        """取消正在執行的任務

        Args:
            task_id: 任務ID

        Returns:
            Dict[str, Any]: 取消結果
        """
        crawler_instance_to_cancel: Optional[Any] = None
        future_to_cancel: Optional[Future] = None

        try:
            # 檢查任務是否在執行中並嘗試取消執行緒
            with self.task_lock:
                has_future = task_id in self.running_tasks
                has_crawler = task_id in self.running_crawlers
                
                if has_future:
                    future_to_cancel = self.running_tasks.get(task_id)
                
                if has_crawler:
                    crawler_instance_to_cancel = self.running_crawlers.get(task_id)
                else:
                    logger.warning(f"嘗試取消任務 {task_id} 時，找不到對應的運行中爬蟲實例，可能無法完整取消。")
            
            # 嘗試取消 Future (如果存在)
            thread_cancelled = False
            if future_to_cancel:
                thread_cancelled = future_to_cancel.cancel()
                logger.info(f"嘗試取消任務 {task_id} 的執行緒，結果: {thread_cancelled}")

            # 使用事務更新任務狀態
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('TaskHistory', session))

                # 檢查任務是否存在
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在'
                    }
                
                # 執行爬蟲取消邏輯 (如果實例存在)
                crawler_cancelled = False
                if crawler_instance_to_cancel:
                    try:
                        # 獲取最新的 task_args 以配置取消行為
                        current_task_args = task.task_args or {}
                        save_partial_results = current_task_args.get('save_partial_results_on_cancel', False)
                        save_partial_to_database = current_task_args.get('save_partial_to_database', False)
                        
                        # 確保 global_params 存在
                        if not hasattr(crawler_instance_to_cancel, 'global_params'):
                             setattr(crawler_instance_to_cancel, 'global_params', {})
                        
                        crawler_instance_to_cancel.global_params['save_partial_results_on_cancel'] = save_partial_results
                        crawler_instance_to_cancel.global_params['save_partial_to_database'] = save_partial_to_database
                        
                        crawler_cancelled = crawler_instance_to_cancel.cancel_task(task_id)
                        logger.info(f"調用爬蟲 {crawler_instance_to_cancel.__class__.__name__} 的 cancel_task 方法，任務 {task_id}，結果: {crawler_cancelled}")
                    except Exception as cancel_err:
                        logger.error(f"調用爬蟲取消方法時出錯，任務 {task_id}: {cancel_err}", exc_info=True)
                        # 即使爬蟲取消失敗，如果執行緒已取消，也可能繼續標記為已取消
                
                # 確定是否取消成功 (優先考慮執行緒取消，其次是爬蟲取消)
                # 如果執行緒已成功取消，即使爬蟲取消失敗，也認為任務已停止
                cancelled = thread_cancelled or crawler_cancelled
                
                if cancelled:
                    # 獲取最新的歷史記錄 (運行中)
                    # 使用 cast 解決類型提示問題
                    latest_history_orm = cast(Optional[CrawlerTaskHistory], history_repo.get_latest_history(task_id, is_preview=False)) # 明確指定 is_preview=False
                    history_id_to_update = None
                    if latest_history_orm and latest_history_orm.task_status == TaskStatus.RUNNING.value and not latest_history_orm.end_time:
                        history_id_to_update = latest_history_orm.id

                    # 更新歷史記錄為已取消
                    if history_id_to_update:
                        history_data = {
                            'end_time': datetime.now(timezone.utc),
                            'task_status': TaskStatus.CANCELLED.value,
                            'message': '任務已被使用者取消',
                            'success': False # 取消視為不成功
                        }
                        validated_history_data = history_repo.validate_data(history_data, SchemaType.UPDATE)
                        history_repo.update(history_id_to_update, validated_history_data)
                        logger.info(f"已更新任務 {task_id} 的運行中歷史記錄 {history_id_to_update} 狀態為 CANCELLED")
                    else:
                        # 如果找不到運行中的歷史記錄，創建一條新的取消記錄
                        logger.warning(f"找不到任務 {task_id} 對應的運行中歷史記錄，將創建新的取消記錄。")
                        history_data = {
                            'task_id': task_id,
                            'start_time': task.last_run_at or datetime.now(timezone.utc), # 嘗試使用上次運行時間
                            'end_time': datetime.now(timezone.utc),
                            'task_status': TaskStatus.CANCELLED.value,
                            'message': '任務已被使用者取消 (未找到運行記錄)',
                            'success': False
                        }
                        validated_history_data = history_repo.validate_data(history_data, SchemaType.CREATE)
                        created_history = history_repo.create(validated_history_data)
                        if not created_history:
                            logger.error(f"創建任務 {task_id} 的取消歷史記錄失敗 (history_repo.create 返回 None)")

                    # 更新任務狀態為已取消
                    task_data = {
                        'task_status': TaskStatus.CANCELLED.value,
                        'scrape_phase': ScrapePhase.CANCELLED.value,
                        'last_run_at': datetime.now(timezone.utc), # 更新最後運行時間
                        'last_run_success': False,
                        'last_run_message': '任務已被使用者取消'
                    }
                    validated_task_data = tasks_repo.validate_data(task_data, SchemaType.UPDATE)
                    tasks_repo.update(task_id, validated_task_data)
                    session.flush()
                    
                    message = f'任務 {task_id} 已取消'
                    success = True
                else:
                    # 如果取消失敗 (執行緒和爬蟲都未取消)
                    message = f'無法取消任務 {task_id}，可能任務已完成、未開始或不支持取消。'
                    success = False

            # --- 事務結束 --- 

            # 清理內存中的記錄 (無論成功失敗)
            with self.task_lock:
                if task_id in self.running_tasks:
                    del self.running_tasks[task_id]
                if task_id in self.running_crawlers:
                    del self.running_crawlers[task_id]
            
            # 在 cancel_task 方法中，如果取消成功，發送取消事件
            if cancelled:
                room_name = f'task_{task_id}'
                cancel_data = {
                    'task_id': task_id,
                    'progress': 100, # 取消也視為結束
                    'status': TaskStatus.CANCELLED.value,
                    'scrape_phase': ScrapePhase.CANCELLED.value,
                    'message': '任務已被使用者取消'
                }
                socketio.emit('task_progress', cancel_data, namespace='/tasks', to=room_name)
                socketio.emit('task_finished', {'task_id': task_id, 'status': TaskStatus.CANCELLED.value}, namespace='/tasks', to=room_name)
                logger.info(f"任務取消: 已發送 WebSocket 事件: task_progress (取消) 和 task_finished 至 room {room_name}")

            return {
                'success': success,
                'message': message
            }

        except Exception as e:
            error_msg = f"取消任務失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # 清理內存記錄
            with self.task_lock:
                if task_id in self.running_tasks:
                    del self.running_tasks[task_id]
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
            is_running_in_memory = task_id in self.running_tasks

        # 優先檢查內存狀態
        if is_running_in_memory:
            # 嘗試獲取更詳細的運行時信息 (如果爬蟲支持)
            progress = 50 # 默認進度
            scrape_phase = ScrapePhase.LINK_COLLECTION # 默認階段
            message = f'任務 {task_id} 正在執行中 (從內存狀態獲取)'
            try:
                 with self.task_lock:
                     if task_id in self.running_crawlers:
                         crawler = self.running_crawlers[task_id]
                         if hasattr(crawler, 'get_progress'):
                             runtime_status = crawler.get_progress(task_id)
                             progress = runtime_status.get('progress', progress)
                             scrape_phase = runtime_status.get('scrape_phase', scrape_phase)
                             message = runtime_status.get('message', message)
            except Exception as e:
                 logger.warning(f"獲取任務 {task_id} 運行時狀態失敗: {e}")

            return {
                'success': True,
                'task_status': TaskStatus.RUNNING.value,
                'scrape_phase': scrape_phase.value if isinstance(scrape_phase, ScrapePhase) else scrape_phase, # 確保返回 value
                'progress': progress,
                'message': message
            }

        # 如果內存中沒有，則查詢資料庫
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('TaskHistory', session))

                # 檢查任務是否存在
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在',
                        'task_status': TaskStatus.UNKNOWN.value,
                        'scrape_phase': ScrapePhase.UNKNOWN.value,
                        'progress': 0,
                        'task': None
                    }
                
                # 從資料庫獲取最新一筆歷史記錄
                # 注意：這裡 get_task_status 可能不需要 is_preview=False，因為它本來就不預期返回 ORM 物件屬性細節
                # 但為了與其他部分一致，並假設後續可能需要 ORM 物件，保留 is_preview=False 並使用 cast
                latest_history_orm = cast(Optional[CrawlerTaskHistory], history_repo.get_latest_history(task_id, is_preview=False))

                # 確定最終狀態和階段
                task_status_value = task.task_status # 默認使用任務表的狀態
                scrape_phase_value = task.scrape_phase # 默認使用任務表的階段
                message = task.last_run_message or '' # 默認消息
                progress = 0 # 默認進度

                if latest_history_orm:
                    message = latest_history_orm.message or message # 優先使用歷史記錄消息
                    # 檢查 latest_history_orm.task_status 是否有效
                    latest_history_status_value = None
                    # 直接訪問 ORM 屬性
                    if latest_history_orm.task_status is not None:
                         # 假設 task_status 可能存儲 Enum 成員或其值，優先取 .value
                         latest_history_status_value = getattr(latest_history_orm.task_status, 'value', latest_history_orm.task_status)

                    # 如果歷史記錄指示任務已結束
                    if latest_history_orm.end_time and latest_history_status_value in [
                        TaskStatus.COMPLETED.value,
                        TaskStatus.FAILED.value,
                        TaskStatus.CANCELLED.value
                    ]:
                        task_status_value = latest_history_status_value # 使用歷史記錄的最終狀態值
                        # 根據最終狀態值確定 scrape_phase 值
                        if task_status_value == TaskStatus.COMPLETED.value:
                            scrape_phase_value = ScrapePhase.COMPLETED.value
                        elif task_status_value == TaskStatus.FAILED.value:
                            scrape_phase_value = ScrapePhase.FAILED.value
                        else: # CANCELLED
                            scrape_phase_value = ScrapePhase.CANCELLED.value
                        progress = 100
                    # 如果歷史記錄是運行中 (通常不應該出現，因為我們先檢查內存)
                    elif not latest_history_orm.end_time and latest_history_status_value == TaskStatus.RUNNING.value:
                         task_status_value = TaskStatus.RUNNING.value
                         # 嘗試估算進度
                         current_time = datetime.now(timezone.utc)
                         if latest_history_orm.start_time:
                             elapsed = current_time - latest_history_orm.start_time
                             progress = min(95, int((elapsed.total_seconds() / 300) * 100))
                         message = f"任務可能仍在運行 (基於歷史記錄) {progress}%"
                    # 其他情況 (例如歷史記錄狀態異常)，維持任務表的狀態
                else:
                    # 沒有歷史記錄，狀態完全來自任務表
                    message = '無執行歷史，狀態來自任務表'
                    if task_status_value != TaskStatus.RUNNING.value:
                        progress = 100 if task_status_value == TaskStatus.COMPLETED.value else 0

                return {
                    'success': True,
                    'task_status': task_status_value, # 返回確定的狀態值
                    'scrape_phase': scrape_phase_value, # 返回確定的階段值
                    'progress': progress,
                    'message': message,
                    'task': CrawlerTaskReadSchema.model_validate(task) if task else None
                }
        except Exception as e:
            error_msg = f"從資料庫獲取任務狀態失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'task_status': TaskStatus.UNKNOWN.value,
                'scrape_phase': ScrapePhase.UNKNOWN.value,
                'progress': 0,
                'task': None
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
        # 確保 scrape_mode 正確設置
        kwargs['operation_type'] = 'fetch_full_article'
        kwargs['scrape_mode'] = 'full_scrape'
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
        # 在執行任務時指定操作類型和模式
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
        # 在執行任務時指定操作類型和模式
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
                
            # 使用事務確保一致性 (雖然測試通常不寫入DB，但為了與其他方法模式一致)
            # 注意：這裡不需要事務，因為 test_crawler 不應寫入數據庫
            # with self._transaction() as session:
            
            # 獲取爬蟲實例
            from src.crawlers.crawler_factory import CrawlerFactory
            
            
            # 預防設置錯誤，強制設定測試參數
            test_params['scrape_mode'] = 'links_only'
            test_params['is_test'] = True
            test_params['max_pages'] = min(1, test_params.get('max_pages', 1))
            test_params['num_articles'] = min(5, test_params.get('num_articles', 5))
            test_params['save_to_csv'] = False
            test_params['save_to_database'] = False
            test_params['get_links_by_task_id'] = False
            test_params['timeout'] = 30
            
            crawlers_service = get_crawlers_service()
            article_service = get_article_service()
            CrawlerFactory.initialize(crawlers_service, article_service)
            crawler = CrawlerFactory.get_crawler(crawler_name)
            
            # 執行測試，明確將返回值轉換為字典
            test_result = crawler.execute_task(0, test_params) # task_id 設為 0 表示測試
            
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
        *** 注意：此方法已被整合到 _execute_task_internal 的事務中，
            通常不應直接外部調用，除非用於手動更新狀態。***

        Args:
            task_id: 任務ID
            success: 執行是否成功
            message: 執行結果訊息

        Returns:
            Dict[str, Any]: 更新結果
        """
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))

                # 更新任務的最後執行時間和狀態
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在'
                    }
                
                # Prepare data for update
                now = datetime.now(timezone.utc)
                task_data = { 
                    'last_run_at': now,
                    'last_run_success': success
                }
                if message:
                    task_data['last_run_message'] = message
                
                # Validate before update
                validated_data = tasks_repo.validate_data(task_data, SchemaType.UPDATE)

                # 更新最後執行時間和狀態
                updated_task = tasks_repo.update(task_id, validated_data)
                session.flush() # Ensure the update is written
                if updated_task:
                     session.refresh(updated_task) # Refresh to get the latest state if needed
                
                return {
                    'success': True,
                    'message': '任務最後執行狀態更新成功',
                    'task': CrawlerTaskReadSchema.model_validate(updated_task) if updated_task else None
                }
        except Exception as e:
            error_msg = f"更新任務最後執行狀態失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }