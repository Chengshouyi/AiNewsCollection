"""排程服務模組，負責管理和執行基於 Cron 的爬蟲任務。"""

import logging
from typing import Dict, Any, Tuple, Optional, Type, cast, List
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
import pytz
from sqlalchemy.orm import Session

from src.services.base_service import BaseService
from src.database.base_repository import BaseRepository
from src.models.crawler_tasks_model import CrawlerTasks
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.services.task_executor_service import TaskExecutorService
from src.error.errors import DatabaseOperationError
from src.services.service_container import get_task_executor_service
from src.config import get_db_manager


logger = logging.getLogger(__name__)  # 使用統一的 logger


class SchedulerService(BaseService[CrawlerTasks]):
    """排程服務，使用 Cron 表達式調度爬蟲任務執行"""

    def __init__(
        self,
        task_executor_service: Optional[TaskExecutorService] = None,
        db_manager=None,
    ):
        """初始化排程服務

        Args:
            task_executor: TaskExecutorService 實例，用於執行任務
            db_manager: 資料庫管理器
        """
        super().__init__(db_manager)

        self.task_executor_service = (
            task_executor_service or get_task_executor_service()
        )

        jobstore = SQLAlchemyJobStore(
            url=self.db_manager.database_url,
            engine=self.db_manager.engine,
            tablename="apscheduler_jobs",
        )

        executors = {
            "default": ThreadPoolExecutor(20),
            "processpool": ProcessPoolExecutor(5),
        }

        job_defaults = {
            "coalesce": True,
            "max_instances": 3,
            "misfire_grace_time": 3600,
        }

        self.cron_scheduler = BackgroundScheduler(
            jobstores={"default": jobstore},
            executors=executors,
            job_defaults=job_defaults,
            timezone=pytz.UTC,
        )

        self.scheduler_status = {
            "running": False,
            "job_count": 0,
            "last_start_time": None,
            "last_shutdown_time": None,
        }

    def _get_repository_mapping(
        self,
    ) -> Dict[str, Tuple[Type[BaseRepository], Type[CrawlerTasks]]]:
        """提供儲存庫映射"""
        return {"CrawlerTask": (CrawlerTasksRepository, CrawlerTasks)}
    

        
    def start_scheduler(self) -> Dict[str, Any]:
        """啟動 cron 調度器，並根據資料庫中各任務的 cron 表達式安排執行

        Returns:
            Dict[str, Any]: 包含啟動結果的字典
        """
        if self.scheduler_status["running"]:
            return {"success": False, "message": "調度器已在運行中"}

        try:
            persisted_jobs = self.cron_scheduler.get_jobs()
            persisted_jobs_count = len(persisted_jobs)

            if persisted_jobs_count > 0:
                logger.info("發現 %s 個持久化任務", persisted_jobs_count)

            scheduled_count = 0
            removed_count = 0

            with self._transaction() as session:
                repo = cast(
                    CrawlerTasksRepository, self._get_repository("CrawlerTask", session)
                )

                auto_tasks_raw = repo.find_auto_tasks()
                auto_tasks = cast(List[CrawlerTasks], auto_tasks_raw)

                db_task_ids = {task.id for task in auto_tasks}
                persisted_job_ids = {
                    int(job.id.split("_")[1])
                    for job in persisted_jobs
                    if job.id.startswith("task_") and job.id.split("_")[1].isdigit()
                }

                for task in auto_tasks:
                    job_id = f"task_{task.id}"
                    job = self.cron_scheduler.get_job(job_id)

                    if task.id in persisted_job_ids:
                        if (
                            job
                            and hasattr(job.trigger, "expression")
                            and job.trigger.expression != task.cron_expression
                        ):
                            logger.info(
                                "任務 %s 的 cron 表達式已變更，重新排程", task.id
                            )
                            self.cron_scheduler.remove_job(job_id)
                            if self._schedule_task(task):
                                try:
                                    if not task.is_scheduled:
                                        repo.toggle_scheduled_status(task.id)
                                        session.flush()
                                        logger.info("任務 %s 狀態已更新為排程", task.id)
                                    scheduled_count += 1
                                except DatabaseOperationError as db_err:
                                    logger.error(
                                        "更新任務 %s 排程狀態失敗: %s", task.id, db_err
                                    )
                                    self.cron_scheduler.remove_job(job_id)
                                except Exception as e:
                                    logger.error(
                                        "更新任務 %s 排程狀態時發生未知錯誤: %s",
                                        task.id,
                                        e,
                                    )
                                    self.cron_scheduler.remove_job(job_id)
                        else:
                            try:
                                if not task.is_scheduled:
                                    repo.toggle_scheduled_status(task.id)
                                    session.flush()
                                    logger.info("任務 %s 狀態已同步為排程", task.id)
                                scheduled_count += 1
                            except DatabaseOperationError as db_err:
                                logger.error(
                                    "同步任務 %s 排程狀態失敗: %s", task.id, db_err
                                )
                            except Exception as e:
                                logger.error(
                                    "同步任務 %s 排程狀態時發生未知錯誤: %s", task.id, e
                                )
                    else:
                        if self._schedule_task(task):
                            logger.info("新增任務 %s 到排程", task.id)
                            try:
                                if not task.is_scheduled:
                                    repo.toggle_scheduled_status(task.id)
                                    session.flush()
                                    logger.info("任務 %s 狀態已設為排程", task.id)
                                scheduled_count += 1
                            except DatabaseOperationError as db_err:
                                logger.error(
                                    "設定任務 %s 排程狀態失敗: %s", task.id, db_err
                                )
                                self.cron_scheduler.remove_job(job_id)
                            except Exception as e:
                                logger.error(
                                    "設定任務 %s 排程狀態時發生未知錯誤: %s", task.id, e
                                )
                                self.cron_scheduler.remove_job(job_id)

                for task_id in persisted_job_ids:
                    if task_id not in db_task_ids:
                        job_id = f"task_{task_id}"
                        try:
                            self.cron_scheduler.remove_job(job_id)
                            logger.info("移除不存在於資料庫的持久化任務: %s", job_id)
                            removed_count += 1
                        except Exception as e:
                            logger.warning("移除持久化任務 %s 失敗: %s", job_id, str(e))

            self.cron_scheduler.start()

            self.scheduler_status["running"] = True
            self.scheduler_status["job_count"] = len(self.cron_scheduler.get_jobs())
            self.scheduler_status["last_start_time"] = datetime.now(timezone.utc)

            logger.info(
                "SchedulerService: 調度器已啟動，處理 %s 個任務，移除 %s 個過期任務。總共 %s 個作業。",
                scheduled_count,
                removed_count,
                self.scheduler_status["job_count"],
            )

            return {
                "success": True,
                "message": f'調度器已啟動，處理 {scheduled_count} 個任務 (新增/更新)，移除 {removed_count} 個過期任務。總共 {self.scheduler_status["job_count"]} 個作業',
                "status": self.scheduler_status,
            }
        except DatabaseOperationError as db_e:
            error_msg = f"啟動調度器時資料庫操作失敗: {str(db_e)}"
            logger.error(error_msg, exc_info=True)
            if self.cron_scheduler.running:
                try:
                    self.cron_scheduler.shutdown(wait=False)
                except Exception:
                    pass
            self.scheduler_status["running"] = False
            return {"success": False, "message": error_msg}
        except Exception as e:
            error_msg = f"啟動調度器失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if self.cron_scheduler.running:
                try:
                    self.cron_scheduler.shutdown(wait=False)
                except Exception:
                    pass
            self.scheduler_status["running"] = False
            return {"success": False, "message": error_msg}

    def stop_scheduler(self) -> Dict[str, Any]:
        """停止 cron 調度器，清理資源

        Returns:
            Dict[str, Any]: 包含停止結果的字典
        """
        if not self.scheduler_status["running"]:
            return {"success": False, "message": "調度器未運行"}

        try:
            current_job_count = len(self.cron_scheduler.get_jobs())
            self.cron_scheduler.pause()

            self.scheduler_status["running"] = False
            self.scheduler_status["job_count"] = current_job_count
            self.scheduler_status["last_shutdown_time"] = datetime.now(timezone.utc)

            return {
                "success": True,
                "message": f"調度器已暫停，保留 {current_job_count} 個持久化任務",
                "status": self.scheduler_status,
            }
        except Exception as e:
            error_msg = f"停止調度器失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "message": error_msg}

    def _schedule_task(self, task: CrawlerTasks) -> bool:
        """根據任務內的 cron 表達式設定排程工作，並註冊回呼方法

        Args:
            task: 爬蟲任務實例

        Returns:
            bool: 設定成功返回 True，否則返回 False
        """
        if not task.cron_expression:
            logger.warning("任務 %s 沒有設定 cron 表達式，跳過排程", task.id)
            return False

        try:
            trigger = CronTrigger.from_crontab(task.cron_expression, timezone=pytz.UTC)
            job_id = f"task_{task.id}"
            self.cron_scheduler.add_job(
                func=self._trigger_task,
                trigger=trigger,
                args=[task.id],
                id=job_id,
                name=task.task_name,
                replace_existing=True,
                misfire_grace_time=1800,
                kwargs={"task_args": task.task_args},
                jobstore="default",
            )

            logger.info("已排程任務 %s，cron 表達式: %s", task.id, task.cron_expression)
            return True
        except Exception as e:
            logger.error("排程任務 %s 失敗: %s", task.id, str(e), exc_info=True)
            return False

    @staticmethod
    def _trigger_task(task_id: int, task_args: Optional[Dict[str, Any]] = None) -> None:
        """在 cron 調度器觸發時，將該任務交由 TaskExecutor 執行 (靜態版本)

        Args:
            task_id: 任務 ID
            task_args: 附加的任務參數 (持久化存儲的任務可能提供)
        """
        logger.info(
            "SchedulerService (Static): 準備觸發任務 ID: %s，附加參數: %s",
            task_id,
            task_args,
        )
        task: Optional[CrawlerTasks] = None
        db_manager = None
        try:
            db_manager = get_db_manager()
            with db_manager.session_scope() as session:
                repo = CrawlerTasksRepository(session, CrawlerTasks)
                task = repo.get_by_id(task_id)

                if not task:
                    error_msg = f"找不到任務 {task_id}，無法執行"
                    logger.error(error_msg)
                    return

                is_auto = task.is_auto
                task_name = task.task_name

            if not is_auto:
                logger.warning(
                    "任務 %s (%s) 已設置為非自動執行，跳過本次執行", task_id, task_name
                )
                return

            task_executor_service = get_task_executor_service()
            logger.info(
                "調度器觸發執行任務 %s (%s), 附加參數: %s",
                task_id,
                task_name,
                task_args,
            )
            task_executor_service.execute_task(task_id, task_args)

        except DatabaseOperationError as db_e:
            error_msg = f"觸發任務 {task_id} 前讀取資料庫失敗: {str(db_e)}"
            logger.error(error_msg, exc_info=True)
        except Exception as e:
            error_msg = f"觸發執行任務 {task_id} 時發生錯誤: {str(e)}"
            logger.error(error_msg, exc_info=True)
        finally:
            if db_manager:
                pass

    def add_or_update_task_to_scheduler(
        self, task: CrawlerTasks, session: Session
    ) -> Dict[str, Any]:
        """新增或更新任務到排程 (需要傳入 session)"""
        job_id = f"task_{task.id}"
        job = self.cron_scheduler.get_job(job_id)
        updated_count = 0
        added_count = 0
        success = False

        repo = cast(
            CrawlerTasksRepository, self._get_repository("CrawlerTask", session)
        )

        try:
            if job:
                # 檢查任務是否需要更新 (以 cron 表達式為主要依據)
                needs_update = False
                if (
                    hasattr(job.trigger, "expression")
                    and job.trigger.expression != task.cron_expression
                ):
                    needs_update = True
                    logger.info(
                        "任務 %s cron 表達式不同 ('%s' vs '%s')，標記為需要更新。",
                        task.id,
                        job.trigger.expression,
                        task.cron_expression,
                    )

                if needs_update:
                    self.cron_scheduler.remove_job(job_id)
                    if self._schedule_task(task):
                        logger.info("更新排程任務: %s", job_id)
                        if not task.is_scheduled:
                            repo.toggle_scheduled_status(task.id)
                        session.add(task)
                        session.flush()
                        logger.info(
                            "任務 %s 的變更 (包括 is_scheduled 狀態) 已寫入資料庫",
                            task.id,
                        )
                        updated_count += 1
                        success = True
                    else:
                        logger.warning("重新排程任務 %s 失敗。", job_id)
                else:
                    if not task.is_scheduled:
                        repo.toggle_scheduled_status(task.id)
                        session.flush()
                        logger.info(
                            "任務 %s 狀態已同步為排程 (無需更新排程器)", task.id
                        )
                    success = True
            else:
                if self._schedule_task(task):
                    logger.info("新增任務到排程: %s", job_id)
                    if not task.is_scheduled:
                        repo.toggle_scheduled_status(task.id)
                    session.add(task)
                    session.flush()
                    logger.info(
                        "任務 %s 的狀態 (包括 is_scheduled) 已寫入資料庫", task.id
                    )
                    added_count += 1
                    success = True
                else:
                    logger.warning("新增排程任務 %s 失敗。", job_id)

        except DatabaseOperationError as db_err:
            logger.error(
                "更新/新增任務 %s 時操作資料庫排程狀態失敗: %s",
                task.id,
                db_err,
                exc_info=True,
            )
            if job or self.cron_scheduler.get_job(job_id):
                try:
                    self.cron_scheduler.remove_job(job_id)
                    logger.info("因資料庫錯誤，已從排程移除任務 %s", job_id)
                except Exception as remove_err:
                    logger.error(
                        "嘗試移除失敗排程任務 %s 時出錯: %s", job_id, remove_err
                    )
            success = False
            updated_count = 0
            added_count = 0
        except Exception as e:
            logger.error(
                "處理任務 %s 排程時發生未知錯誤: %s", task.id, str(e), exc_info=True
            )
            success = False
            updated_count = 0
            added_count = 0

        return {
            "success": success,
            "message": f"處理任務 {task.id} 到排程",
            "added_count": added_count,
            "updated_count": updated_count,
        }

    def remove_task_from_scheduler(self, task_id: int) -> Dict[str, Any]:
        """移除任務從排程，並更新資料庫狀態"""
        job_id = f"task_{task_id}"
        try:
            self.cron_scheduler.remove_job(job_id)
            logger.info("從排程器移除任務: %s", job_id)

            with self._transaction() as session:
                repo = cast(
                    CrawlerTasksRepository, self._get_repository("CrawlerTask", session)
                )
                task = repo.get_by_id(task_id)
                try:
                    if task and task.is_scheduled:
                        repo.toggle_scheduled_status(task_id)
                        session.flush()
                        logger.info("已更新資料庫，任務 %s 標記為未排程", task_id)
                    elif task:
                        logger.info("任務 %s 狀態已是未排程，無需更新DB", task_id)
                    else:
                        logger.warning("嘗試更新狀態時找不到任務 %s", task_id)

                    return {
                        "success": True,
                        "message": f"從排程移除任務 {task_id} 並更新狀態成功",
                    }
                except DatabaseOperationError as db_err:
                    logger.error(
                        "移除任務 %s 後更新資料庫狀態失敗: %s",
                        task_id,
                        db_err,
                        exc_info=True,
                    )
                    return {
                        "success": False,
                        "message": f"從排程移除任務 {task_id} 成功，但更新資料庫狀態失敗: {db_err}",
                    }
                except Exception as e:
                    logger.error(
                        "移除任務 %s 後更新資料庫狀態時發生未知錯誤: %s",
                        task_id,
                        e,
                        exc_info=True,
                    )
                    return {
                        "success": False,
                        "message": f"從排程移除任務 {task_id} 成功，但更新資料庫狀態時發生未知錯誤: {e}",
                    }
        except Exception as e:
            logger.error("從排程移除任務 %s 失敗: %s", task_id, str(e), exc_info=True)
            return {
                "success": False,
                "message": f"從排程移除任務 {task_id} 失敗: {str(e)}",
            }

    def reload_scheduler(self) -> Dict[str, Any]:
        """當任務資料變更時，重新載入或調整調度任務，使用事務管理"""
        if not self.scheduler_status["running"]:
            return {"success": False, "message": "調度器未運行，無法重載"}

        try:
            persisted_jobs = self.cron_scheduler.get_jobs()
            persisted_job_ids = {
                int(job.id.split("_")[1])
                for job in persisted_jobs
                if job.id.startswith("task_") and job.id.split("_")[1].isdigit()
            }

            removed_count = 0
            updated_count = 0
            added_count = 0

            with self._transaction() as session:
                repo = cast(
                    CrawlerTasksRepository, self._get_repository("CrawlerTask", session)
                )

                auto_tasks_raw = repo.find_auto_tasks()
                auto_tasks = cast(List[CrawlerTasks], auto_tasks_raw)
                db_task_ids = {task.id for task in auto_tasks}

                tasks_to_remove_ids = persisted_job_ids - db_task_ids
                for task_id in tasks_to_remove_ids:
                    job_id = f"task_{task_id}"
                    try:
                        self.cron_scheduler.remove_job(job_id)
                        logger.info("重載時移除不存在/非自動的任務: %s", job_id)
                        task_exists = repo.get_by_id(task_id)
                        if task_exists and task_exists.is_scheduled:
                            repo.toggle_scheduled_status(task_id)
                            session.flush()
                            logger.info(
                                "已將任務 %s 狀態設為未排程 (因不再自動執行)", task_id
                            )
                        removed_count += 1
                    except DatabaseOperationError as db_err:
                        logger.error("重載時更新任務 %s 狀態失敗: %s", task_id, db_err)
                    except Exception as e:
                        logger.warning(
                            "重載時移除任務 %s 或更新狀態失敗: %s", job_id, str(e)
                        )

                for task in auto_tasks:
                    result = self.add_or_update_task_to_scheduler(task, session)
                    if result["success"]:
                        updated_count += result["updated_count"]
                        added_count += result["added_count"]
                    else:
                        logger.error("重載過程中處理任務 %s 失敗。", task.id)

            self.scheduler_status["job_count"] = len(self.cron_scheduler.get_jobs())

            return {
                "success": True,
                "message": f'調度器已重載，移除 {removed_count} 個任務，更新 {updated_count} 個任務，新增 {added_count} 個任務。總共 {self.scheduler_status["job_count"]} 個作業',
                "status": self.scheduler_status,
            }
        except DatabaseOperationError as db_e:
            error_msg = f"重載調度器時資料庫操作失敗: {str(db_e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "message": error_msg}
        except Exception as e:
            error_msg = f"重載調度器失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "message": error_msg}

    def get_scheduler_status(self) -> Dict[str, Any]:
        """獲取調度器當前狀態

        Returns:
            Dict[str, Any]: 包含調度器狀態的字典
        """
        if self.scheduler_status["running"]:
            self.scheduler_status["job_count"] = len(self.cron_scheduler.get_jobs())

        return {
            "success": True,
            "message": "獲取調度器狀態成功",
            "status": self.scheduler_status,
        }

    def get_persisted_jobs_info(self) -> Dict[str, Any]:
        """獲取持久化任務的詳細信息

        Returns:
            Dict[str, Any]: 包含任務詳情的字典
        """
        try:
            jobs = self.cron_scheduler.get_jobs()
            jobs_info = []

            with self._transaction() as session:
                repo = cast(
                    CrawlerTasksRepository, self._get_repository("CrawlerTask", session)
                )

                for job in jobs:
                    job_info = {
                        "id": job.id,
                        "name": job.name,
                        "next_run_time": (
                            job.next_run_time.isoformat() if job.next_run_time else None
                        ),
                        "trigger": str(job.trigger),
                        "cron_expression": (
                            job.trigger.expression
                            if hasattr(job.trigger, "expression")
                            else None
                        ),
                        "misfire_grace_time": job.misfire_grace_time,
                        "active": job.next_run_time is not None,
                    }

                    if job.id.startswith("task_") and job.id.split("_")[1].isdigit():
                        task_id = int(job.id.split("_")[1])
                        job_info["task_id"] = task_id

                        task = repo.get_by_id(task_id)
                        job_info["exists_in_db"] = task is not None
                        if task:
                            job_info["task_name"] = task.task_name
                            job_info["is_auto_in_db"] = task.is_auto
                            job_info["is_scheduled_in_db"] = task.is_scheduled
                            job_info["cron_expression_in_db"] = task.cron_expression

                    jobs_info.append(job_info)

            return {
                "success": True,
                "message": f"獲取 {len(jobs_info)} 個持久化任務信息",
                "scheduler_running": self.scheduler_status["running"],
                "jobs": jobs_info,
            }
        except DatabaseOperationError as db_e:
            error_msg = f"獲取持久化任務信息時資料庫操作失敗: {str(db_e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "message": error_msg}
        except Exception as e:
            error_msg = f"獲取持久化任務信息失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "message": error_msg}
        
    def is_running(self) -> bool:
        """回傳調度器是否正在運行"""
        return self.scheduler_status.get("running", False)  
    
    def get_next_run_time(self):
        """取得下一個排程任務的執行時間（UTC ISO 格式），若無則回傳 None"""
        jobs = self.cron_scheduler.get_jobs()
        if not jobs:
            return None
        # 取所有任務中最近的 next_run_time
        next_times = [job.next_run_time for job in jobs if job.next_run_time]
        if not next_times:
            return None
        next_time = min(next_times)
        return next_time.isoformat()

    def __del__(self):
        """析構方法，確保調度器被停止"""
        if hasattr(self, "scheduler_status") and self.scheduler_status.get("running"):
            try:
                self.cron_scheduler.shutdown(wait=False)
                logger.info("調度器已在銷毀時關閉")
            except Exception as e:
                logger.warning("關閉調度器時發生錯誤 (忽略): %s", str(e))

        super().__del__()
