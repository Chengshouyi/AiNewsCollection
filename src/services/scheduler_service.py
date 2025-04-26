import logging
from typing import Dict, Any, Tuple, Optional, Type, cast, List
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from datetime import datetime, timezone
import pytz
from sqlalchemy.orm import Session

from src.services.base_service import BaseService
from src.database.base_repository import BaseRepository
from src.models.base_model import Base
from src.models.crawler_tasks_model import CrawlerTasks
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.services.task_executor_service import TaskExecutorService
from src.error.errors import DatabaseOperationError
from src.services.service_container import get_task_executor_service
from src.config import get_db_manager
# 設定 logger
from src.utils.log_utils import LoggerSetup # 使用統一的 logger
logger = LoggerSetup.setup_logger(__name__) # 使用統一的 logger

class SchedulerService(BaseService[CrawlerTasks]):
    """排程服務，使用 Cron 表達式調度爬蟲任務執行"""
    
    def __init__(self, 
                 task_executor_service: Optional[TaskExecutorService] = None, 
                 db_manager = None):
        """初始化排程服務
        
        Args:
            task_executor: TaskExecutorService 實例，用於執行任務
            db_manager: 資料庫管理器
        """
        super().__init__(db_manager)
        
        # 儲存傳入的參數或創建新實例
        self.task_executor_service = task_executor_service or get_task_executor_service()
        
        # 設定 SQLAlchemy 任務存儲
        jobstore = SQLAlchemyJobStore(
            url=self.db_manager.database_url,
            engine=self.db_manager.engine,
            tablename='apscheduler_jobs'
        )
        
        # 設定執行器
        executors = {
            'default': ThreadPoolExecutor(20),
            'processpool': ProcessPoolExecutor(5)
        }
        
        # 作業預設值
        job_defaults = {
            'coalesce': True,  # 合併延遲的作業
            'max_instances': 3,  # 同一作業的最大實例數
            'misfire_grace_time': 3600  # 允許 1 小時的誤差
        }
        
        # 初始化 cron 調度器，加入持久化設定
        self.cron_scheduler = BackgroundScheduler(
            jobstores={'default': jobstore},
            executors=executors,
            job_defaults=job_defaults,
            timezone=pytz.UTC
        )
        
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
            # 檢查是否有持久化的任務
            persisted_jobs = self.cron_scheduler.get_jobs()
            persisted_jobs_count = len(persisted_jobs)
            
            if persisted_jobs_count > 0:
                logger.info(f"發現 {persisted_jobs_count} 個持久化任務")
            
            scheduled_count = 0
            removed_count = 0
            
            # 使用事務管理資料庫操作
            with self._transaction() as session:
                repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                
                # 從資料庫獲取需要自動執行的任務
                auto_tasks_raw = repo.find_auto_tasks()
                auto_tasks = cast(List[CrawlerTasks], auto_tasks_raw)
                
                # 記錄資料庫任務和持久化任務的 ID 對應關係
                db_task_ids = {task.id for task in auto_tasks}
                persisted_job_ids = {int(job.id.split('_')[1]) for job in persisted_jobs 
                                   if job.id.startswith('task_') and job.id.split('_')[1].isdigit()}

                # 根據任務的 cron 表達式設定調度
                for task in auto_tasks:
                    job_id = f"task_{task.id}"
                    job = self.cron_scheduler.get_job(job_id)

                    # 如果任務已經在持久化存儲中存在
                    if task.id in persisted_job_ids:
                        if job and hasattr(job.trigger, 'expression') and job.trigger.expression != task.cron_expression:
                            logger.info(f"任務 {task.id} 的 cron 表達式已變更，重新排程")
                            self.cron_scheduler.remove_job(job_id) # 先移除舊的
                            if self._schedule_task(task): # 嘗試排程新的
                                # 確保排程狀態正確 (即使之前已排程)
                                try:
                                    if not task.is_scheduled: # 檢查是否需要切換
                                        repo.toggle_scheduled_status(task.id)
                                        session.flush() # 提交狀態變更
                                        logger.info(f"任務 {task.id} 狀態已更新為排程")
                                    scheduled_count += 1
                                except DatabaseOperationError as db_err:
                                    logger.error(f"更新任務 {task.id} 排程狀態失敗: {db_err}")
                                    self.cron_scheduler.remove_job(job_id) # 如果DB更新失敗，移除剛加入的排程
                                except Exception as e:
                                    logger.error(f"更新任務 {task.id} 排程狀態時發生未知錯誤: {e}")
                                    self.cron_scheduler.remove_job(job_id)
                        else:
                             # 已存在且設置正確的任務，只需確保 DB 狀態為 True
                            try:
                                if not task.is_scheduled: # 檢查是否需要切換
                                    repo.toggle_scheduled_status(task.id) # 確保 DB 狀態一致
                                    session.flush()
                                    logger.info(f"任務 {task.id} 狀態已同步為排程")
                                scheduled_count += 1 # 仍然計入已排程數量
                            except DatabaseOperationError as db_err:
                                logger.error(f"同步任務 {task.id} 排程狀態失敗: {db_err}")
                            except Exception as e:
                                logger.error(f"同步任務 {task.id} 排程狀態時發生未知錯誤: {e}")
                    else:
                        # 新增任務到排程器
                        if self._schedule_task(task):
                            logger.info(f"新增任務 {task.id} 到排程")
                            # 更新資料庫中的排程狀態
                            try:
                                if not task.is_scheduled: # 檢查是否需要切換
                                    repo.toggle_scheduled_status(task.id)
                                    session.flush() # 提交狀態變更
                                    logger.info(f"任務 {task.id} 狀態已設為排程")
                                scheduled_count += 1
                            except DatabaseOperationError as db_err:
                                logger.error(f"設定任務 {task.id} 排程狀態失敗: {db_err}")
                                self.cron_scheduler.remove_job(job_id) # 如果DB更新失敗，移除剛加入的排程
                            except Exception as e:
                                logger.error(f"設定任務 {task.id} 排程狀態時發生未知錯誤: {e}")
                                self.cron_scheduler.remove_job(job_id)
                
                # 移除已不存在於資料庫的持久化任務
                for task_id in persisted_job_ids:
                     if task_id not in db_task_ids:
                        job_id = f"task_{task_id}"
                        try:
                            self.cron_scheduler.remove_job(job_id)
                            logger.info(f"移除不存在於資料庫的持久化任務: {job_id}")
                            # 不需要更新 DB 狀態，因為任務本身已不存在
                            removed_count += 1
                        except Exception as e:
                            logger.warning(f"移除持久化任務 {job_id} 失敗: {str(e)}")

            # 啟動調度器 (在事務外部)
            self.cron_scheduler.start()
            
            # 更新狀態
            self.scheduler_status['running'] = True
            self.scheduler_status['job_count'] = len(self.cron_scheduler.get_jobs())
            self.scheduler_status['last_start_time'] = datetime.now(timezone.utc)
            
            # --- 新增 Log ---
            logger.info(f"SchedulerService: 調度器已啟動，處理 {scheduled_count} 個任務，移除 {removed_count} 個過期任務。總共 {self.scheduler_status['job_count']} 個作業。")
            # --- 新增 Log 結束 ---
            
            return {
                'success': True,
                'message': f'調度器已啟動，處理 {scheduled_count} 個任務 (新增/更新)，移除 {removed_count} 個過期任務。總共 {self.scheduler_status["job_count"]} 個作業',
                'status': self.scheduler_status
            }
        except DatabaseOperationError as db_e:
            error_msg = f"啟動調度器時資料庫操作失敗: {str(db_e)}"
            logger.error(error_msg, exc_info=True)
            # 確保調度器未意外啟動
            if self.cron_scheduler.running:
                 try:
                     self.cron_scheduler.shutdown(wait=False)
                 except Exception:
                     pass # 忽略關閉錯誤
            self.scheduler_status['running'] = False
            return {
                'success': False,
                'message': error_msg
            }
        except Exception as e:
            error_msg = f"啟動調度器失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # 確保調度器未意外啟動
            if self.cron_scheduler.running:
                 try:
                     self.cron_scheduler.shutdown(wait=False)
                 except Exception:
                     pass # 忽略關閉錯誤
            self.scheduler_status['running'] = False
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
            # 獲取當前任務數量用於記錄
            current_job_count = len(self.cron_scheduler.get_jobs())
            
            # 暫停調度器而不清除任務定義
            self.cron_scheduler.pause()
            
            # 更新狀態
            self.scheduler_status['running'] = False
            # 保留任務數量值，以便在重啟時知道有多少任務
            self.scheduler_status['job_count'] = current_job_count
            self.scheduler_status['last_shutdown_time'] = datetime.now(timezone.utc)
            
            return {
                'success': True,
                'message': f'調度器已暫停，保留 {current_job_count} 個持久化任務',
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
                name=task.task_name,
                replace_existing=True,
                misfire_grace_time=1800,
                kwargs={'task_args': task.task_args},
                jobstore='default'
            )
            
            logger.info(f"已排程任務 {task.id}，cron 表達式: {task.cron_expression}")
            return True
        except Exception as e:
            logger.error(f"排程任務 {task.id} 失敗: {str(e)}", exc_info=True)
            return False

    @staticmethod
    def _trigger_task(task_id: int, task_args: Optional[Dict[str, Any]] = None) -> None:
        """在 cron 調度器觸發時，將該任務交由 TaskExecutor 執行 (靜態版本)
        
        Args:
            task_id: 任務 ID
            task_args: 附加的任務參數 (持久化存儲的任務可能提供)
        """
        # --- 新增 Log ---
        logger.info(f"SchedulerService (Static): 準備觸發任務 ID: {task_id}，附加參數: {task_args}")
        # --- 新增 Log 結束 ---
        task: Optional[CrawlerTasks] = None
        db_manager = None # 初始化
        try:
            # --- 使用服務容器獲取 db_manager ---
            db_manager = get_db_manager()
            # 使用 context manager 管理 session 生命周期
            with db_manager.session_scope() as session:
                # --- 直接使用 session 初始化 Repository ---
                repo = CrawlerTasksRepository(session, CrawlerTasks)
                task = repo.get_by_id(task_id)

                if not task:
                    error_msg = f"找不到任務 {task_id}，無法執行"
                    logger.error(error_msg)
                    return # 直接返回，避免後續操作

                # --- 將屬性讀取移入 session scope ---
                is_auto = task.is_auto
                task_name = task.task_name
                # --- 移入結束 ---

            # 檢查任務是否設置為自動執行 (讀取 task 物件，無需再次查詢DB)
            # --- 使用讀取到的變數 ---
            if not is_auto:
                logger.warning(f"任務 {task_id} ({task_name}) 已設置為非自動執行，跳過本次執行")
                return

            # --- 使用服務容器獲取 task_executor_service ---
            task_executor_service = get_task_executor_service()
            # 交由 TaskExecutor 執行 (在事務外部)
            # --- 使用讀取到的變數 ---
            logger.info(f"調度器觸發執行任務 {task_id} ({task_name}), 附加參數: {task_args}")
            # 確保傳遞的是 ID 而不是 detached 的 task 物件
            task_executor_service.execute_task(task_id, task_args)
            # --- 修改結束 ---
            
        except DatabaseOperationError as db_e:
            error_msg = f"觸發任務 {task_id} 前讀取資料庫失敗: {str(db_e)}"
            logger.error(error_msg, exc_info=True)
        except Exception as e:
            error_msg = f"觸發執行任務 {task_id} 時發生錯誤: {str(e)}"
            logger.error(error_msg, exc_info=True)
        finally:
            # 如果 db_manager 被成功獲取，確保清理
            if db_manager:
                # db_manager.cleanup() # 不應在此處清理，事務管理器會處理 session
                pass
    
    def add_or_update_task_to_scheduler(self, task: CrawlerTasks, session: Session) -> Dict[str, Any]:
        """新增或更新任務到排程 (需要傳入 session)"""
        job_id = f"task_{task.id}"
        job = self.cron_scheduler.get_job(job_id)
        updated_count = 0
        added_count = 0
        success = False
        
        # 使用傳入的 session 獲取 repo
        repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))

        try:
            if job:
                # 檢查任務是否需要更新 (以更新時間或 cron 表達式為準)
                needs_update = False
                if hasattr(job.kwargs, 'update_at') and job.kwargs.update_at != task.updated_at:
                     needs_update = True
                     logger.info(f"任務 {task.id} updated_at 不同，標記為需要更新。")
                if hasattr(job.trigger, 'expression') and job.trigger.expression != task.cron_expression:
                    needs_update = True
                    logger.info(f"任務 {task.id} cron 表達式不同，標記為需要更新。")

                if needs_update:
                    self.cron_scheduler.remove_job(job_id)
                    if self._schedule_task(task):
                        logger.info(f"更新排程任務: {job_id}")
                        # 更新DB狀態
                        if not task.is_scheduled: # 檢查是否需要切換
                            repo.toggle_scheduled_status(task.id)
                            session.flush() # 確保狀態寫入
                            logger.info(f"任務 {task.id} 狀態已更新為排程")
                        updated_count += 1
                        success = True
                    else:
                        logger.warning(f"重新排程任務 {job_id} 失敗。")
                        # 嘗試恢復舊排程? 或標記為失敗? 目前僅記錄警告
                else:
                    # 無需更新排程器，但要確保 DB 狀態是 True
                    if not task.is_scheduled: # 檢查是否需要切換
                        repo.toggle_scheduled_status(task.id)
                        session.flush()
                        logger.info(f"任務 {task.id} 狀態已同步為排程")
                    # 不需要增加 updated_count，因為排程器未變
                    success = True # 操作本身算成功
            else:
                # 新增任務
                if self._schedule_task(task):
                    logger.info(f"新增任務到排程: {job_id}")
                    # 更新DB狀態
                    if not task.is_scheduled: # 檢查是否需要切換
                        repo.toggle_scheduled_status(task.id)
                        session.flush()
                        logger.info(f"任務 {task.id} 狀態已設為排程")
                    added_count += 1
                    success = True
                else:
                     logger.warning(f"新增排程任務 {job_id} 失敗。")

        except DatabaseOperationError as db_err:
            logger.error(f"更新/新增任務 {task.id} 時操作資料庫排程狀態失敗: {db_err}", exc_info=True)
            # 如果 DB 操作失敗，是否應該移除排程？是，避免狀態不一致
            if job or self.cron_scheduler.get_job(job_id): # 檢查任務是否仍在排程中
                 try:
                     self.cron_scheduler.remove_job(job_id)
                     logger.info(f"因資料庫錯誤，已從排程移除任務 {job_id}")
                 except Exception as remove_err:
                     logger.error(f"嘗試移除失敗排程任務 {job_id} 時出錯: {remove_err}")
            success = False # DB 操作失敗，整體算失敗
            # 重置計數器
            updated_count = 0
            added_count = 0
        except Exception as e:
            logger.error(f"處理任務 {task.id} 排程時發生未知錯誤: {str(e)}", exc_info=True)
            success = False
            updated_count = 0
            added_count = 0

        return {
            'success': success, # 返回操作是否成功
            'message': f'處理任務 {task.id} 到排程',
            'added_count': added_count,
            'updated_count': updated_count
        }
    
    def remove_task_from_scheduler(self, task_id: int) -> Dict[str, Any]:
        """移除任務從排程，並更新資料庫狀態"""
        job_id = f"task_{task_id}"
        try:
            # 先從排程器移除
            self.cron_scheduler.remove_job(job_id)
            logger.info(f"從排程器移除任務: {job_id}")
            
            # 再更新資料庫狀態
            with self._transaction() as session:
                 repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                 task = repo.get_by_id(task_id) # 獲取任務以檢查狀態
                 try:
                     if task and task.is_scheduled: # 檢查是否存在且需要切換
                         repo.toggle_scheduled_status(task_id)
                         session.flush()
                         logger.info(f"已更新資料庫，任務 {task_id} 標記為未排程")
                     elif task:
                         logger.info(f"任務 {task_id} 狀態已是未排程，無需更新DB")
                     else:
                         logger.warning(f"嘗試更新狀態時找不到任務 {task_id}")
                     
                     return {
                         'success': True,
                         'message': f'從排程移除任務 {task_id} 並更新狀態成功'
                     }
                 except DatabaseOperationError as db_err:
                     logger.error(f"移除任務 {task_id} 後更新資料庫狀態失敗: {db_err}", exc_info=True)
                     # 排程已移除，但DB狀態更新失敗
                     return {
                         'success': False, # 操作未完全成功
                         'message': f'從排程移除任務 {task_id} 成功，但更新資料庫狀態失敗: {db_err}'
                     }
                 except Exception as e:
                     logger.error(f"移除任務 {task_id} 後更新資料庫狀態時發生未知錯誤: {e}", exc_info=True)
                     return {
                         'success': False,
                         'message': f'從排程移除任務 {task_id} 成功，但更新資料庫狀態時發生未知錯誤: {e}'
                     }
        except Exception as e:
             # 移除排程本身失敗
            logger.error(f"從排程移除任務 {task_id} 失敗: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f'從排程移除任務 {task_id} 失敗: {str(e)}'
            }
    

    def reload_scheduler(self) -> Dict[str, Any]:
        """當任務資料變更時，重新載入或調整調度任務，使用事務管理"""
        # 如果調度器未運行，直接返回錯誤
        if not self.scheduler_status['running']:
            return {
                'success': False,
                'message': '調度器未運行，無法重載'
            }
            
        try:
            # 獲取現有的持久化任務 (在事務外部，因為只讀取調度器狀態)
            persisted_jobs = self.cron_scheduler.get_jobs()
            persisted_job_ids = {int(job.id.split('_')[1]) for job in persisted_jobs 
                               if job.id.startswith('task_') and job.id.split('_')[1].isdigit()}
            
            removed_count = 0
            updated_count = 0
            added_count = 0
            
            # 使用事務管理所有資料庫操作
            with self._transaction() as session:
                repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                
                # 從資料庫獲取最新的自動執行任務
                auto_tasks_raw = repo.find_auto_tasks()
                auto_tasks = cast(List[CrawlerTasks], auto_tasks_raw)
                db_task_ids = {task.id for task in auto_tasks}
                
                # 1. 移除已不存在於資料庫或不再是 auto_tasks 的持久化任務
                tasks_to_remove_ids = persisted_job_ids - db_task_ids
                for task_id in tasks_to_remove_ids:
                    job_id = f"task_{task_id}"
                    try:
                        self.cron_scheduler.remove_job(job_id)
                        logger.info(f"重載時移除不存在/非自動的任務: {job_id}")
                        # 確保這些任務在 DB 中的狀態也是 False (如果任務還存在的話)
                        task_exists = repo.get_by_id(task_id) # 檢查任務是否還在DB
                        if task_exists and task_exists.is_scheduled: # 檢查是否需要切換
                            repo.toggle_scheduled_status(task_id)
                            session.flush()
                            logger.info(f"已將任務 {task_id} 狀態設為未排程 (因不再自動執行)")
                        removed_count += 1
                    except DatabaseOperationError as db_err:
                         logger.error(f"重載時更新任務 {task_id} 狀態失敗: {db_err}")
                         # 即使DB更新失敗，排程已移除，繼續處理
                    except Exception as e:
                        logger.warning(f"重載時移除任務 {job_id} 或更新狀態失敗: {str(e)}")
                
                # 2. 更新現有任務或新增任務
                for task in auto_tasks:
                    # 調用需要 session 的版本
                    result = self.add_or_update_task_to_scheduler(task, session)
                    if result['success']:
                        updated_count += result['updated_count']
                        added_count += result['added_count']
                    else:
                        # 如果 add_or_update 失敗，記錄錯誤，但不中斷重載
                        logger.error(f"重載過程中處理任務 {task.id} 失敗。")

            # 更新狀態 (在事務外部)
            self.scheduler_status['job_count'] = len(self.cron_scheduler.get_jobs())
            
            return {
                'success': True, # 即使部分任務處理失敗，重載操作本身算完成
                'message': f'調度器已重載，移除 {removed_count} 個任務，更新 {updated_count} 個任務，新增 {added_count} 個任務。總共 {self.scheduler_status["job_count"]} 個作業',
                'status': self.scheduler_status
            }
        except DatabaseOperationError as db_e:
            error_msg = f"重載調度器時資料庫操作失敗: {str(db_e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg}
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
    
    def get_persisted_jobs_info(self) -> Dict[str, Any]:
        """獲取持久化任務的詳細信息
        
        Returns:
            Dict[str, Any]: 包含任務詳情的字典
        """
        try:
            jobs = self.cron_scheduler.get_jobs()
            jobs_info = []
            
            # 在事務外獲取 repo 可能導致讀到舊數據，移入事務
            with self._transaction() as session:
                 repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                 
                 for job in jobs:
                     job_info = {
                         'id': job.id,
                         'name': job.name,
                         'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                         'trigger': str(job.trigger),
                         'cron_expression': job.trigger.expression if hasattr(job.trigger, 'expression') else None,
                         'misfire_grace_time': job.misfire_grace_time,
                         'active': job.next_run_time is not None
                     }
                     
                     # 嘗試提取任務 ID 並查詢 DB
                     if job.id.startswith('task_') and job.id.split('_')[1].isdigit():
                         task_id = int(job.id.split('_')[1])
                         job_info['task_id'] = task_id
                         
                         # 從資料庫檢查任務狀態
                         task = repo.get_by_id(task_id)
                         job_info['exists_in_db'] = task is not None
                         if task:
                             job_info['task_name'] = task.task_name
                             job_info['is_auto'] = task.is_auto
                             job_info['is_scheduled_in_db'] = task.is_scheduled # 添加 DB 中的排程狀態
                     
                     jobs_info.append(job_info)
                
            return {
                'success': True,
                'message': f'獲取 {len(jobs_info)} 個持久化任務信息',
                'scheduler_running': self.scheduler_status['running'],
                'jobs': jobs_info
            }
        except DatabaseOperationError as db_e:
             error_msg = f"獲取持久化任務信息時資料庫操作失敗: {str(db_e)}"
             logger.error(error_msg, exc_info=True)
             return {'success': False, 'message': error_msg}
        except Exception as e:
            error_msg = f"獲取持久化任務信息失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    def __del__(self):
        """析構方法，確保調度器被停止"""
        if hasattr(self, 'scheduler_status') and self.scheduler_status.get('running'):
            try:
                # 使用 shutdown 而非 pause，因為這是最終銷毀
                self.cron_scheduler.shutdown(wait=False)
                logger.info("調度器已在銷毀時關閉")
            except Exception as e:
                logger.warning(f"關閉調度器時發生錯誤 (忽略): {str(e)}")
                
        # 呼叫父類的清理方法
        super().__del__() 