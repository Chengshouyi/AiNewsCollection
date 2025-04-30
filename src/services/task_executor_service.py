"""
此模組提供 TaskExecutorService，負責管理和執行爬蟲任務。

它處理任務的異步執行、狀態更新、進度報告（透過 WebSocket）以及任務取消。
服務與資料庫互動以獲取任務詳細資訊、更新狀態和記錄執行歷史。
它還利用 ProgressListener 接口從執行中的爬蟲接收進度更新。
"""

# 標準函式庫 imports
import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Type, cast

# 第三方函式庫 imports
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import DetachedInstanceError

# 本地應用程式 imports
from src.crawlers.crawler_factory import CrawlerFactory
from src.database.base_repository import BaseRepository, SchemaType
from src.database.crawler_task_history_repository import CrawlerTaskHistoryRepository
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.database.crawlers_repository import CrawlersRepository
from src.interface.progress_reporter import ProgressListener
from src.models.base_model import Base  # Base 可能在類型提示中使用，予以保留
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.models.crawler_tasks_model import CrawlerTasks, ScrapePhase
from src.models.crawler_tasks_schema import CrawlerTaskReadSchema
from src.models.crawlers_model import Crawlers
from src.services.base_service import BaseService
from src.services.service_container import get_article_service, get_crawlers_service
from src.utils.enum_utils import TaskStatus
  # 使用統一的 logger
from src.web.socket_instance import generate_session_id, socketio

logger = logging.getLogger(__name__)  # 使用統一的 logger  # 使用統一的 logger


class TaskExecutorService(BaseService[CrawlerTasks], ProgressListener):
    """統一的任務執行服務，處理所有類型的任務執行，同時監聽爬蟲進度"""

    def __init__(self, db_manager=None, max_workers=10):
        """初始化任務執行服務

        Args:
            db_manager: 資料庫管理器
            max_workers: 最大工作執行緒數量
        """
        super().__init__(db_manager)
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.running_tasks: Dict[int, Future] = {}  # 執行中的任務 {task_id: future}
        self.running_crawlers: Dict[int, Any] = (
            {}
        )  # 執行中的爬蟲實例 {task_id: crawler}
        self.task_lock = threading.Lock()
        self.task_execution_status: Dict[int, Dict[str, Any]] = (
            {}
        )  # 任務執行狀態 {task_id: {'progress': int, 'message': str, 'scrape_phase': ScrapePhase}}
        self.task_session_ids: Dict[int, str] = (
            {}
        )  # 任務對應的會話ID {task_id: session_id}

    def _get_repository_mapping(
        self,
    ) -> Dict[str, Tuple[Type[BaseRepository], Type[Base]]]:
        """提供儲存庫映射"""
        return {
            "CrawlerTask": (CrawlerTasksRepository, CrawlerTasks),
            "Crawler": (CrawlersRepository, Crawlers),
            "TaskHistory": (CrawlerTaskHistoryRepository, CrawlerTaskHistory),
        }

    def on_progress_update(self, task_id: int, progress_data: Dict[str, Any]) -> None:
        """
        接收爬蟲進度更新並處理

        Args:
            task_id: 任務ID
            progress_data: 進度數據，包含progress、message、scrape_phase等
        """
        logger.info(
            "收到進度更新: 任務 %s, 進度 %s%%, 階段 %s, 訊息: %s",
            task_id,
            progress_data.get("progress", 0),
            progress_data.get("scrape_phase", "unknown"),
            progress_data.get("message", "無訊息"),
        )

        with self.task_lock:
            if task_id not in self.task_execution_status:
                self.task_execution_status[task_id] = {}

            self.task_execution_status[task_id].update(
                {
                    "progress": progress_data.get("progress", 0),
                    "message": progress_data.get("message", "無訊息"),
                    "scrape_phase": progress_data.get(
                        "scrape_phase", ScrapePhase.UNKNOWN.value
                    ),
                }
            )

        session_id = None
        with self.task_lock:
            if task_id in self.task_session_ids:
                session_id = self.task_session_ids[task_id]

        base_room_name = f"task_{task_id}"
        logger.info("準備發送進度到基礎房間: %s", base_room_name)

        socketio_data = {
            "task_id": task_id,
            "progress": progress_data.get("progress", 0),
            "status": TaskStatus.RUNNING.value,
            "scrape_phase": progress_data.get(
                "scrape_phase", ScrapePhase.UNKNOWN.value
            ),
            "message": progress_data.get("message", "無訊息"),
            "session_id": session_id,
        }

        socketio.emit(
            "task_progress", socketio_data, namespace="/tasks", to=base_room_name
        )
        logger.info(
            "已發送WebSocket進度更新: %s%%, %s 到房間 %s",
            socketio_data["progress"],
            socketio_data["message"],
            base_room_name,
        )

    def execute_task(
        self, task_id: int, is_async: bool = True, **kwargs
    ) -> Dict[str, Any]:
        """執行指定的爬蟲任務

        Args:
            task_id: 任務ID
            is_async: 是否異步執行
            **kwargs: 額外的執行參數

        Returns:
            Dict[str, Any]: 執行結果
        """
        with self.task_lock:
            if task_id in self.running_tasks:
                return {"success": False, "message": "任務已在執行中"}

        session_id = generate_session_id()
        with self.task_lock:
            self.task_session_ids[task_id] = session_id

        base_room_name = f"task_{task_id}"
        logger.info(
            "為任務 %s 準備基礎房間: %s (會話ID: %s)",
            task_id,
            base_room_name,
            session_id,
        )

        history_id = None
        task_orm_for_sync = None

        try:
            with self._transaction() as session:
                tasks_repo = cast(
                    CrawlerTasksRepository, self._get_repository("CrawlerTask", session)
                )
                history_repo = cast(
                    CrawlerTaskHistoryRepository,
                    self._get_repository("TaskHistory", session),
                )

                task = tasks_repo.get_task_by_id(task_id, is_active=True)
                if not task:
                    return {"success": False, "message": "任務不存在"}

                if task.task_status == TaskStatus.RUNNING.value:
                    return {"success": False, "message": "任務已在執行中"}

                history_data_for_validation = {
                    "task_id": task_id,
                    "start_time": datetime.now(timezone.utc),
                    "task_status": TaskStatus.RUNNING.value,
                    "message": "任務開始執行",
                }
                validated_history_data = history_repo.validate_data(
                    history_data_for_validation, SchemaType.CREATE
                )

                history = history_repo.create(validated_history_data)
                session.flush()
                history_id = history.id if history else None

                if history_id is None:
                    logger.error("任務 %s 的歷史記錄創建失敗。", task_id)
                    return {
                        "success": False,
                        "message": f"任務 {task_id} 的歷史記錄創建失敗。",
                    }

                task_data = {
                    "task_status": TaskStatus.RUNNING.value,
                    "scrape_phase": ScrapePhase.INIT.value,
                }
                updated_task = tasks_repo.update(task_id, task_data)
                if not updated_task:
                    logger.error("更新任務 %s 狀態為 RUNNING 失敗。", task_id)
                    return {
                        "success": False,
                        "message": f"更新任務 {task_id} 狀態為 RUNNING 失敗。",
                    }

                task_orm_for_sync = updated_task
                session.flush()

            if is_async:
                with self.task_lock:
                    future = self.thread_pool.submit(
                        self._execute_task_internal, task_id, history_id, **kwargs
                    )
                    self.running_tasks[task_id] = future
                    future.add_done_callback(
                        lambda f: self._task_completion_callback(task_id, f)
                    )

                return {
                    "success": True,
                    "message": f"任務 {task_id} 已提交執行",
                    "task_id": task_id,
                    "status": "executing",
                    "session_id": session_id,
                    "room": base_room_name,
                }
            else:
                # 注意：同步執行時，_execute_task_internal 會建立自己的事務
                if task_orm_for_sync:
                    sync_result = self._execute_task_internal(
                        task_id, history_id, **kwargs
                    )
                    sync_result["session_id"] = session_id
                    sync_result["room"] = base_room_name
                    return sync_result
                else:
                    return {
                        "success": False,
                        "message": f"無法獲取任務 {task_id} 進行同步執行。",
                    }
        except Exception as e:
            error_msg = f"準備執行任務失敗, ID={task_id}: {str(e)}"
            logger.error("準備執行任務失敗, ID=%s: %s", task_id, str(e), exc_info=True)
            if history_id:
                try:
                    with self._transaction() as cleanup_session:
                        history_repo_cleanup = cast(
                            CrawlerTaskHistoryRepository,
                            self._get_repository("TaskHistory", cleanup_session),
                        )
                        history_repo_cleanup.delete(history_id)
                        logger.info("已清理因準備失敗而創建的歷史記錄 %s", history_id)
                except Exception as cleanup_error:
                    logger.error("清理歷史記錄 %s 失敗: %s", history_id, cleanup_error)
            return {"success": False, "message": error_msg}

    def _task_completion_callback(self, task_id: int, future: Future):
        """任務完成回調函數，清理執行中的任務記錄

        Args:
            task_id: 任務ID
            future: Future對象
        """
        session_id = None
        with self.task_lock:
            if task_id in self.running_tasks:
                logger.info("清除執行中的任務 %s", task_id)
                del self.running_tasks[task_id]
            if task_id in self.running_crawlers:
                logger.info("清除爬蟲實例 %s", task_id)
                del self.running_crawlers[task_id]
            if task_id in self.task_session_ids:
                session_id = self.task_session_ids[task_id]

        base_room_name = f"task_{task_id}"

        if future.exception():
            error_info = future.exception()
            error_msg = f"任務 {task_id} 執行失敗: {error_info}"
            fail_data = {
                "task_id": task_id,
                "progress": 100,
                "status": TaskStatus.FAILED.value,
                "scrape_phase": ScrapePhase.FAILED.value,
                "message": error_msg,
                "session_id": session_id,
            }
            socketio.emit(
                "task_progress", fail_data, namespace="/tasks", to=base_room_name
            )
            socketio.emit(
                "task_finished",
                {
                    "task_id": task_id,
                    "status": TaskStatus.FAILED.value,
                    "session_id": session_id,
                },
                namespace="/tasks",
                to=base_room_name,
            )
            logger.info(
                "異步任務回調: 已發送 WebSocket 事件: task_progress (失敗) 和 task_finished 至 room %s",
                base_room_name,
            )

        # 任務正常完成時，_execute_task_internal 內部已發送完成事件，此處無需處理
        # 但需要確保會話ID被清理
        with self.task_lock:
            if task_id in self.task_session_ids:
                logger.info("任務 %s 回調完成，清理會話ID %s", task_id, session_id)
                del self.task_session_ids[task_id]

    def _execute_task_internal(
        self, task_id: int, history_id: Optional[int], **kwargs
    ) -> Dict[str, Any]:
        """內部任務執行函數 (工作緒)

        Args:
            task_id: 任務ID
            history_id: 任務歷史ID (可能為 None)
            **kwargs: 額外參數

        Returns:
            Dict[str, Any]: 執行結果
        """

        logger.info(
            "TaskExecutorService: 開始執行內部任務 task_id=%s, history_id=%s",
            task_id,
            history_id,
        )

        crawler_name = None
        task: Optional[CrawlerTasks] = None
        crawler_instance = None

        session_id = None
        with self.task_lock:
            if task_id in self.task_session_ids:
                session_id = self.task_session_ids[task_id]

        base_room_name = f"task_{task_id}"

        try:
            with self._transaction() as session:
                tasks_repo = cast(
                    CrawlerTasksRepository, self._get_repository("CrawlerTask", session)
                )
                history_repo = cast(
                    CrawlerTaskHistoryRepository,
                    self._get_repository("TaskHistory", session),
                )
                crawler_repo = cast(
                    CrawlersRepository, self._get_repository("Crawler", session)
                )

                task = tasks_repo.get_by_id(task_id)
                if not task:
                    logger.error("內部執行時找不到任務 %s", task_id)
                    if history_id:
                        try:
                            history_data = {
                                "end_time": datetime.now(timezone.utc),
                                "task_status": TaskStatus.FAILED.value,
                                "message": f"執行時找不到任務 {task_id}",
                            }
                            validated_history_data = history_repo.validate_data(
                                history_data, SchemaType.UPDATE
                            )
                            updated_history = history_repo.update(
                                history_id, validated_history_data
                            )
                            if not updated_history:
                                logger.error(
                                    "更新找不到任務 %s 的歷史記錄 %s 失敗 (history_repo.update 返回 None)",
                                    task_id,
                                    history_id,
                                )
                            session.flush()
                        except Exception as history_update_err:
                            logger.error(
                                "更新找不到任務 %s 的歷史記錄 %s 失敗: %s",
                                task_id,
                                history_id,
                                history_update_err,
                            )
                    return {"success": False, "message": f"執行時找不到任務 {task_id}"}

                local_task_args = None

                try:
                    session.refresh(task)
                    logger.debug("成功刷新任務 %s 的狀態", task_id)
                    local_task_args = task.task_args or {}
                    logger.debug("成功獲取任務 %s 的 task_args (提前獲取)", task_id)
                except DetachedInstanceError as detached_e:
                    logger.error("在 session.refresh 後立即訪問 task_args 仍發生 DetachedInstanceError: %s", detached_e, exc_info=True)
                    error_msg = f"刷新任務後訪問 task_args 時發生 DetachedInstanceError: {detached_e}"
                    return {"success": False, "message": error_msg, "task_status": TaskStatus.FAILED.value}
                except Exception as refresh_or_access_err:
                    logger.error("刷新任務 %s 或提前獲取 task_args 時出錯: %s", task_id, refresh_or_access_err, exc_info=True)
                    error_msg = f"刷新任務或獲取 task_args 失敗: {refresh_or_access_err}"
                    return {"success": False, "message": error_msg, "task_status": TaskStatus.FAILED.value}

                crawler = crawler_repo.get_by_id(task.crawler_id)
                if crawler:
                    crawler_name = crawler.crawler_name
                else:
                    logger.error(
                        "任務 %s 關聯的爬蟲 ID %s 不存在", task_id, task.crawler_id
                    )
                    task_data = {
                        "task_status": TaskStatus.FAILED.value,
                        "scrape_phase": ScrapePhase.FAILED.value,
                    }
                    updated_task_fail = tasks_repo.update(task_id, task_data)
                    if not updated_task_fail:
                        logger.error(
                            "更新任務 %s 狀態為 FAILED (因找不到爬蟲) 失敗 (tasks_repo.update 返回 None)",
                            task_id,
                        )
                    if history_id:
                        history_data = {
                            "end_time": datetime.now(timezone.utc),
                            "task_status": TaskStatus.FAILED.value,
                            "message": f"爬蟲 ID {task.crawler_id} 不存在",
                        }
                        validated_history_data = history_repo.validate_data(
                            history_data, SchemaType.UPDATE
                        )
                        updated_history_fail = history_repo.update(
                            history_id, validated_history_data
                        )
                        if not updated_history_fail:
                            logger.error(
                                "更新歷史記錄 %s 狀態為 FAILED (因找不到爬蟲) 失敗 (history_repo.update 返回 None)",
                                history_id,
                            )
                    session.flush()
                    return {
                        "success": False,
                        "message": f"爬蟲 ID {task.crawler_id} 不存在",
                    }

                logger.info("開始執行任務 %s (爬蟲: %s)", task_id, crawler_name)
                crawlers_service = get_crawlers_service()
                article_service = get_article_service()

                CrawlerFactory.initialize(crawlers_service, article_service)
                crawler_instance = CrawlerFactory.get_crawler(crawler_name)

                crawler_instance.add_progress_listener(task_id, self)

                with self.task_lock:
                    self.running_crawlers[task_id] = crawler_instance

                task_args = local_task_args

                if kwargs:
                    if task_args is None: task_args = {}
                    task_args.update(kwargs)
                elif task_args is None:
                    task_args = {}

                result = crawler_instance.execute_task(task_id, task_args)

                task_status_enum = (
                    TaskStatus.COMPLETED
                    if result.get("success", False)
                    else TaskStatus.FAILED
                )
                scrape_phase_enum = (
                    ScrapePhase.COMPLETED
                    if result.get("success", False)
                    else ScrapePhase.FAILED
                )
                message = result.get(
                    "message",
                    (
                        "任務執行完成"
                        if task_status_enum == TaskStatus.COMPLETED
                        else "任務執行失敗"
                    ),
                )
                articles_count = result.get("articles_count", 0)

                task_data = {
                    "task_status": task_status_enum.value,
                    "scrape_phase": scrape_phase_enum.value,
                    "last_run_at": datetime.now(timezone.utc),
                    "last_run_success": result.get("success", False),
                    "last_run_message": message,
                }
                validated_task_data = tasks_repo.validate_data(
                    task_data, SchemaType.UPDATE
                )
                updated_task_final = tasks_repo.update(task_id, validated_task_data)
                if not updated_task_final:
                    logger.error(
                        "更新任務 %s 最終狀態失敗 (tasks_repo.update 返回 None)",
                        task_id,
                    )

                if history_id:
                    history_data = {
                        "end_time": datetime.now(timezone.utc),
                        "task_status": task_status_enum.value,
                        "message": message,
                        "articles_count": articles_count,
                        "success": result.get("success", False),
                    }
                    validated_history_data = history_repo.validate_data(
                        history_data, SchemaType.UPDATE
                    )
                    updated_history_final = history_repo.update(
                        history_id, validated_history_data
                    )
                    if not updated_history_final:
                        logger.error(
                            "更新歷史記錄 %s 最終狀態失敗 (history_repo.update 返回 None)",
                            history_id,
                        )

                session.flush()

            with self.task_lock:
                if task_id in self.running_crawlers:
                    del self.running_crawlers[task_id]

            result["task_status"] = task_status_enum.value

            start_data = {
                "task_id": task_id,
                "progress": 5,  # 進度 5% 表示開始
                "status": TaskStatus.RUNNING.value,
                "scrape_phase": ScrapePhase.INIT.value,
                "message": f"任務 {task_id} 開始執行 (爬蟲: {crawler_name})",
                "session_id": session_id,
            }
            socketio.emit(
                "task_progress", start_data, namespace="/tasks", to=base_room_name
            )
            logger.info(
                "已發送 WebSocket 事件: task_progress (開始) 至 room %s", base_room_name
            )

            final_data = {
                "task_id": task_id,
                "progress": 100,
                "status": task_status_enum.value,
                "scrape_phase": scrape_phase_enum.value,
                "message": message,
                "articles_count": articles_count,
                "session_id": session_id,
            }
            socketio.emit(
                "task_progress", final_data, namespace="/tasks", to=base_room_name
            )
            socketio.emit(
                "task_finished",
                {
                    "task_id": task_id,
                    "status": task_status_enum.value,
                    "session_id": session_id,
                },
                namespace="/tasks",
                to=base_room_name,
            )
            logger.info(
                "已發送 WebSocket 事件: task_progress (完成/失敗) 和 task_finished 至 room %s",
                base_room_name,
            )

            return result
        except Exception as e:
            error_msg = f"執行任務 {task_id} 時發生內部錯誤: {str(e)}"
            logger.exception("執行任務 %s 時發生內部錯誤: %s", task_id, str(e))

            try:
                with self._transaction() as error_session:
                    tasks_repo = cast(
                        CrawlerTasksRepository,
                        self._get_repository("CrawlerTask", error_session),
                    )
                    history_repo = cast(
                        CrawlerTaskHistoryRepository,
                        self._get_repository("TaskHistory", error_session),
                    )

                    if tasks_repo.get_by_id(task_id):
                        task_data = {
                            "task_status": TaskStatus.FAILED.value,
                            "scrape_phase": ScrapePhase.FAILED.value,
                            "last_run_at": datetime.now(timezone.utc),
                            "last_run_success": False,
                            "last_run_message": error_msg,
                        }
                        validated_task_data = tasks_repo.validate_data(
                            task_data, SchemaType.UPDATE
                        )
                        updated_task_err = tasks_repo.update(
                            task_id, validated_task_data
                        )
                        if not updated_task_err:
                            logger.error(
                                "異常處理中更新任務 %s 狀態為 FAILED 失敗 (tasks_repo.update 返回 None)",
                                task_id,
                            )

                    if history_id and history_repo.get_by_id(history_id):
                        history_data = {
                            "end_time": datetime.now(timezone.utc),
                            "task_status": TaskStatus.FAILED.value,
                            "message": error_msg,
                            "success": False,
                        }
                        validated_history_data = history_repo.validate_data(
                            history_data, SchemaType.UPDATE
                        )
                        updated_history_err = history_repo.update(
                            history_id, validated_history_data
                        )
                        if not updated_history_err:
                            logger.error(
                                "異常處理中更新歷史記錄 %s 狀態為 FAILED 失敗 (history_repo.update 返回 None)",
                                history_id,
                            )

                    error_session.flush()
            except Exception as update_error:
                logger.error(
                    "寫入任務 %s 失敗狀態時發生錯誤: %s", task_id, str(update_error)
                )

            with self.task_lock:
                if task_id in self.running_crawlers:
                    del self.running_crawlers[task_id]

            error_data = {
                "task_id": task_id,
                "progress": 100,  # 進度設為 100 表示已結束
                "status": TaskStatus.FAILED.value,
                "scrape_phase": ScrapePhase.FAILED.value,
                "message": error_msg,
                "session_id": session_id,
            }

            # 由於我們已經在方法開頭獲取了 session_id 和構建了 room_name，這裡直接使用
            socketio.emit(
                "task_progress", error_data, namespace="/tasks", to=base_room_name
            )
            socketio.emit(
                "task_finished",
                {
                    "task_id": task_id,
                    "status": TaskStatus.FAILED.value,
                    "session_id": session_id,
                },
                namespace="/tasks",
                to=base_room_name,
            )
            logger.info(
                "異常處理: 已發送 WebSocket 事件: task_progress (失敗) 和 task_finished 至 room %s",
                base_room_name,
            )

            return {
                "success": False,
                "message": error_msg,
                "task_status": TaskStatus.FAILED.value,
            }
        finally:
            if crawler_instance:
                crawler_instance.remove_progress_listener(task_id, self)

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
            with self.task_lock:
                has_future = task_id in self.running_tasks
                has_crawler = task_id in self.running_crawlers

                if has_future:
                    future_to_cancel = self.running_tasks.get(task_id)

                if has_crawler:
                    crawler_instance_to_cancel = self.running_crawlers.get(task_id)
                else:
                    logger.warning(
                        "嘗試取消任務 %s 時，找不到對應的運行中爬蟲實例，可能無法完整取消。",
                        task_id,
                    )

            thread_cancelled = False
            if future_to_cancel:
                thread_cancelled = future_to_cancel.cancel()
                logger.info(
                    "嘗試取消任務 %s 的執行緒，結果: %s", task_id, thread_cancelled
                )

            with self._transaction() as session:
                tasks_repo = cast(
                    CrawlerTasksRepository, self._get_repository("CrawlerTask", session)
                )
                history_repo = cast(
                    CrawlerTaskHistoryRepository,
                    self._get_repository("TaskHistory", session),
                )

                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {"success": False, "message": "任務不存在"}

                crawler_cancelled = False
                if crawler_instance_to_cancel:
                    try:
                        current_task_args = task.task_args or {}
                        save_partial_results = current_task_args.get(
                            "save_partial_results_on_cancel", False
                        )
                        save_partial_to_database = current_task_args.get(
                            "save_partial_to_database", False
                        )

                        if not hasattr(crawler_instance_to_cancel, "global_params"):
                            setattr(crawler_instance_to_cancel, "global_params", {})

                        crawler_instance_to_cancel.global_params[
                            "save_partial_results_on_cancel"
                        ] = save_partial_results
                        crawler_instance_to_cancel.global_params[
                            "save_partial_to_database"
                        ] = save_partial_to_database

                        crawler_cancelled = crawler_instance_to_cancel.cancel_task(
                            task_id
                        )
                        logger.info(
                            "調用爬蟲 %s 的 cancel_task 方法，任務 %s，結果: %s",
                            crawler_instance_to_cancel.__class__.__name__,
                            task_id,
                            crawler_cancelled,
                        )
                    except Exception as cancel_err:
                        logger.error(
                            "調用爬蟲取消方法時出錯，任務 %s: %s",
                            task_id,
                            cancel_err,
                            exc_info=True,
                        )
                        # 即使爬蟲取消失敗，如果執行緒已取消，也可能繼續標記為已取消

                # 如果執行緒已成功取消，即使爬蟲取消失敗，也認為任務已停止
                cancelled = thread_cancelled or crawler_cancelled

                if cancelled:
                    latest_history_orm = cast(
                        Optional[CrawlerTaskHistory],
                        history_repo.get_latest_history(task_id, is_preview=False),
                    )
                    history_id_to_update = None
                    if (
                        latest_history_orm
                        and latest_history_orm.task_status == TaskStatus.RUNNING.value
                        and not latest_history_orm.end_time
                    ):
                        history_id_to_update = latest_history_orm.id

                    if history_id_to_update:
                        history_data = {
                            "end_time": datetime.now(timezone.utc),
                            "task_status": TaskStatus.CANCELLED.value,
                            "message": "任務已被使用者取消",
                            "success": False,
                        }
                        validated_history_data = history_repo.validate_data(
                            history_data, SchemaType.UPDATE
                        )
                        history_repo.update(
                            history_id_to_update, validated_history_data
                        )
                        logger.info(
                            "已更新任務 %s 的運行中歷史記錄 %s 狀態為 CANCELLED",
                            task_id,
                            history_id_to_update,
                        )
                    else:
                        logger.warning(
                            "找不到任務 %s 對應的運行中歷史記錄，將創建新的取消記錄。",
                            task_id,
                        )
                        history_data = {
                            "task_id": task_id,
                            "start_time": task.last_run_at
                            or datetime.now(timezone.utc),
                            "end_time": datetime.now(timezone.utc),
                            "task_status": TaskStatus.CANCELLED.value,
                            "message": "任務已被使用者取消 (未找到運行記錄)",
                            "success": False,
                        }
                        validated_history_data = history_repo.validate_data(
                            history_data, SchemaType.CREATE
                        )
                        created_history = history_repo.create(validated_history_data)
                        if not created_history:
                            logger.error(
                                "創建任務 %s 的取消歷史記錄失敗 (history_repo.create 返回 None)",
                                task_id,
                            )

                    task_data = {
                        "task_status": TaskStatus.CANCELLED.value,
                        "scrape_phase": ScrapePhase.CANCELLED.value,
                        "last_run_at": datetime.now(timezone.utc),
                        "last_run_success": False,
                        "last_run_message": "任務已被使用者取消",
                    }
                    validated_task_data = tasks_repo.validate_data(
                        task_data, SchemaType.UPDATE
                    )
                    tasks_repo.update(task_id, validated_task_data)
                    session.flush()

                    message = f"任務 {task_id} 已取消"
                    success = True
                else:
                    message = (
                        f"無法取消任務 {task_id}，可能任務已完成、未開始或不支持取消。"
                    )
                    success = False

            with self.task_lock:
                if task_id in self.running_tasks:
                    del self.running_tasks[task_id]
                if task_id in self.running_crawlers:
                    del self.running_crawlers[task_id]

            session_id = None
            with self.task_lock:
                if task_id in self.task_session_ids:
                    session_id = self.task_session_ids[task_id]

            base_room_name = f"task_{task_id}"

            if cancelled:
                cancel_data = {
                    "task_id": task_id,
                    "progress": 100,  # 取消也視為結束
                    "status": TaskStatus.CANCELLED.value,
                    "scrape_phase": ScrapePhase.CANCELLED.value,
                    "message": "任務已被使用者取消",
                    "session_id": session_id,
                }
                socketio.emit(
                    "task_progress", cancel_data, namespace="/tasks", to=base_room_name
                )
                socketio.emit(
                    "task_finished",
                    {
                        "task_id": task_id,
                        "status": TaskStatus.CANCELLED.value,
                        "session_id": session_id,
                    },
                    namespace="/tasks",
                    to=base_room_name,
                )
                logger.info(
                    "任務取消: 已發送 WebSocket 事件: task_progress (取消) 和 task_finished 至 room %s",
                    base_room_name,
                )

            with self.task_lock:
                if task_id in self.task_session_ids:
                    del self.task_session_ids[task_id]

            return {"success": success, "message": message}

        except Exception as e:
            error_msg = f"取消任務失敗, ID={task_id}: {str(e)}"
            logger.error("取消任務失敗, ID=%s: %s", task_id, str(e), exc_info=True)

            with self.task_lock:
                if task_id in self.running_tasks:
                    del self.running_tasks[task_id]
                if task_id in self.running_crawlers:
                    del self.running_crawlers[task_id]

            return {"success": False, "message": error_msg}

    def get_task_status(self, task_id: int) -> Dict[str, Any]:
        """獲取任務執行狀態

        Args:
            task_id: 任務ID

        Returns:
            Dict[str, Any]: 任務狀態，包含task_status、scrape_phase、進度等資訊
        """
        with self.task_lock:
            is_running_in_memory = task_id in self.running_tasks
            has_status_in_memory = task_id in self.task_execution_status
            session_id = self.task_session_ids.get(task_id)

        if is_running_in_memory and has_status_in_memory:
            status_data = self.task_execution_status.get(task_id, {})
            return {
                "success": True,
                "task_status": TaskStatus.RUNNING.value,
                "scrape_phase": status_data.get(
                    "scrape_phase", ScrapePhase.UNKNOWN.value
                ),
                "progress": status_data.get("progress", 0),
                "message": status_data.get("message", "任務執行中"),
                "session_id": session_id,
            }

        if is_running_in_memory:
            progress = 50
            scrape_phase = ScrapePhase.LINK_COLLECTION
            message = f"任務 {task_id} 正在執行中 (從內存狀態獲取)"
            try:
                with self.task_lock:
                    if task_id in self.running_crawlers:
                        crawler = self.running_crawlers[task_id]
                        if hasattr(crawler, "get_progress"):
                            runtime_status = crawler.get_progress(task_id)
                            progress = runtime_status.get("progress", progress)
                            scrape_phase = runtime_status.get(
                                "scrape_phase", scrape_phase
                            )
                            message = runtime_status.get("message", message)
            except Exception as e:
                logger.warning("獲取任務 %s 運行時狀態失敗: %s", task_id, e)

            return {
                "success": True,
                "task_status": TaskStatus.RUNNING.value,
                "scrape_phase": (
                    scrape_phase.value
                    if isinstance(scrape_phase, ScrapePhase)
                    else scrape_phase
                ),
                "progress": progress,
                "message": message,
                "session_id": session_id,
            }

        try:
            with self._transaction() as session:
                tasks_repo = cast(
                    CrawlerTasksRepository, self._get_repository("CrawlerTask", session)
                )
                history_repo = cast(
                    CrawlerTaskHistoryRepository,
                    self._get_repository("TaskHistory", session),
                )

                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        "success": False,
                        "message": "任務不存在",
                        "task_status": TaskStatus.UNKNOWN.value,
                        "scrape_phase": ScrapePhase.UNKNOWN.value,
                        "progress": 0,
                        "task": None,
                    }

                latest_history_orm = cast(
                    Optional[CrawlerTaskHistory],
                    history_repo.get_latest_history(task_id, is_preview=False),
                )

                task_status_value = task.task_status
                scrape_phase_value = task.scrape_phase
                message = task.last_run_message or ""
                progress = 0
                latest_session_id = None

                if latest_history_orm:
                    message = latest_history_orm.message or message
                    # 從歷史記錄中獲取會話 ID (假設歷史記錄有 session_id 欄位)
                    # latest_session_id = getattr(latest_history_orm, 'session_id', None)

                    latest_history_status_value = None
                    if latest_history_orm.task_status is not None:
                        latest_history_status_value = getattr(
                            latest_history_orm.task_status,
                            "value",
                            latest_history_orm.task_status,
                        )

                    if latest_history_orm.end_time and latest_history_status_value in [
                        TaskStatus.COMPLETED.value,
                        TaskStatus.FAILED.value,
                        TaskStatus.CANCELLED.value,
                    ]:
                        task_status_value = latest_history_status_value
                        if task_status_value == TaskStatus.COMPLETED.value:
                            scrape_phase_value = ScrapePhase.COMPLETED.value
                        elif task_status_value == TaskStatus.FAILED.value:
                            scrape_phase_value = ScrapePhase.FAILED.value
                        else:
                            scrape_phase_value = ScrapePhase.CANCELLED.value
                        progress = 100
                    elif (
                        not latest_history_orm.end_time
                        and latest_history_status_value == TaskStatus.RUNNING.value
                    ):
                        task_status_value = TaskStatus.RUNNING.value
                        current_time = datetime.now(timezone.utc)
                        if latest_history_orm.start_time:
                            elapsed = current_time - latest_history_orm.start_time
                            progress = min(
                                95, int((elapsed.total_seconds() / 300) * 100)
                            )
                        message = f"任務可能仍在運行 (基於歷史記錄) {progress}%"
                else:
                    message = "無執行歷史，狀態來自任務表"
                    if task_status_value != TaskStatus.RUNNING.value:
                        progress = (
                            100
                            if task_status_value == TaskStatus.COMPLETED.value
                            else 0
                        )

                return {
                    "success": True,
                    "task_status": task_status_value,
                    "scrape_phase": scrape_phase_value,
                    "progress": progress,
                    "message": message,
                    "session_id": latest_session_id,
                    "task": (
                        CrawlerTaskReadSchema.model_validate(task) if task else None
                    ),
                }
        except Exception as e:
            error_msg = f"從資料庫獲取任務狀態失敗, ID={task_id}: {str(e)}"
            logger.error(
                "從資料庫獲取任務狀態失敗, ID=%s: %s", task_id, str(e), exc_info=True
            )
            return {
                "success": False,
                "message": error_msg,
                "task_status": TaskStatus.UNKNOWN.value,
                "scrape_phase": ScrapePhase.UNKNOWN.value,
                "progress": 0,
                "task": None,
            }

    def get_running_tasks(self) -> Dict[str, Any]:
        """獲取所有正在執行的任務

        Returns:
            Dict[str, Any]: 正在執行的任務列表
        """
        with self.task_lock:
            running_task_ids = list(self.running_tasks.keys())

        return {
            "success": True,
            "message": f"找到 {len(running_task_ids)} 個執行中的任務",
            "running_tasks": running_task_ids,
        }

    def fetch_full_article(
        self, task_id: int, is_async: bool = True, **kwargs
    ) -> Dict[str, Any]:
        """獲取完整文章內容的任務

        Args:
            task_id: 任務ID
            is_async: 是否異步執行
            **kwargs: 額外的執行參數

        Returns:
            Dict[str, Any]: 執行結果
        """
        kwargs["operation_type"] = "fetch_full_article"
        kwargs["scrape_mode"] = "full_scrape"
        return self.execute_task(task_id, is_async, **kwargs)

    def collect_links_only(
        self, task_id: int, is_async: bool = True, **kwargs
    ) -> Dict[str, Any]:
        """僅收集連結的任務

        Args:
            task_id: 任務ID
            is_async: 是否異步執行
            **kwargs: 額外的執行參數

        Returns:
            Dict[str, Any]: 執行結果
        """
        kwargs["operation_type"] = "collect_links_only"
        kwargs["scrape_mode"] = "links_only"
        return self.execute_task(task_id, is_async, **kwargs)

    def fetch_content_only(
        self, task_id: int, is_async: bool = True, **kwargs
    ) -> Dict[str, Any]:
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
        kwargs["operation_type"] = "fetch_content_only"
        kwargs["scrape_mode"] = "content_only"
        return self.execute_task(task_id, is_async, **kwargs)

    def test_crawler(
        self, crawler_name: str, test_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """測試爬蟲

        Args:
            crawler_name: 爬蟲名稱
            test_params: 測試參數

        Returns:
            Dict[str, Any]: 測試結果
        """
        try:
            if test_params is None:
                test_params = {}

            # 注意：這裡不需要事務，因為 test_crawler 不應寫入數據庫

            # 預防設置錯誤，強制設定測試參數
            test_params["scrape_mode"] = "links_only"
            test_params["is_test"] = True
            test_params["max_pages"] = min(1, test_params.get("max_pages", 1))
            test_params["num_articles"] = min(5, test_params.get("num_articles", 5))
            test_params["save_to_csv"] = False
            test_params["save_to_database"] = False
            test_params["get_links_by_task_id"] = False
            test_params["timeout"] = 30

            crawlers_service = get_crawlers_service()
            article_service = get_article_service()
            CrawlerFactory.initialize(crawlers_service, article_service)
            crawler = CrawlerFactory.get_crawler(crawler_name)

            test_result = crawler.execute_task(
                0, test_params
            )  # task_id 設為 0 表示測試

            response = {
                "success": test_result.get("success", False),
                "message": test_result.get("message", "爬蟲測試完成"),
            }

            if "scrape_phase" in test_result:
                if isinstance(test_result["scrape_phase"], dict):
                    response["progress"] = test_result["scrape_phase"].get(
                        "progress", 0
                    )
                    response["scrape_phase"] = test_result["scrape_phase"].get(
                        "scrape_phase", ScrapePhase.UNKNOWN.value
                    )
                    response["phase_message"] = test_result["scrape_phase"].get(
                        "message", ""
                    )
                else:
                    response["scrape_phase"] = test_result["scrape_phase"]

            if "articles_count" in test_result:
                response["links_count"] = test_result["articles_count"]
            elif "links" in test_result:
                response["links_count"] = len(test_result["links"])

            response["result"] = test_result

            return response
        except Exception as e:
            error_msg = f"測試爬蟲 {crawler_name} 時發生錯誤: {str(e)}"
            logger.exception("測試爬蟲 %s 時發生錯誤: %s", crawler_name, str(e))
            return {"success": False, "message": error_msg}

    def update_task_last_run(
        self, task_id: int, success: bool, message: Optional[str] = None
    ) -> Dict[str, Any]:
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
                tasks_repo = cast(
                    CrawlerTasksRepository, self._get_repository("CrawlerTask", session)
                )

                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {"success": False, "message": "任務不存在"}

                now = datetime.now(timezone.utc)
                task_data = {"last_run_at": now, "last_run_success": success}
                if message:
                    task_data["last_run_message"] = message

                validated_data = tasks_repo.validate_data(task_data, SchemaType.UPDATE)

                updated_task = tasks_repo.update(task_id, validated_data)
                session.flush()
                if updated_task:
                    session.refresh(updated_task)

                return {
                    "success": True,
                    "message": "任務最後執行狀態更新成功",
                    "task": (
                        CrawlerTaskReadSchema.model_validate(updated_task)
                        if updated_task
                        else None
                    ),
                }
        except Exception as e:
            error_msg = f"更新任務最後執行狀態失敗, ID={task_id}: {str(e)}"
            logger.error(
                "更新任務最後執行狀態失敗, ID=%s: %s", task_id, str(e), exc_info=True
            )
            return {"success": False, "message": error_msg}
