from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Type, cast, Optional, TYPE_CHECKING
import threading
import time
import logging
from src.crawlers.crawler_factory import CrawlerFactory
if TYPE_CHECKING:
    from src.crawlers.base_crawler import BaseCrawler
from src.services.base_service import BaseService
from src.database.base_repository import BaseRepository, SchemaType
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.database.crawlers_repository import CrawlersRepository
from src.database.crawler_task_history_repository import CrawlerTaskHistoryRepository
from src.database.articles_repository import ArticlesRepository
from src.models.base_model import Base
from src.models.crawler_tasks_model import CrawlerTasks, TASK_ARGS_DEFAULT
from src.models.crawlers_model import Crawlers
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.models.articles_model import Articles
from src.models.crawler_tasks_schema import CrawlerTaskReadSchema, PaginatedCrawlerTaskResponse
from src.error.errors import ValidationError
from src.utils.enum_utils import ScrapeMode, ScrapePhase, TaskStatus
from src.utils.model_utils import validate_task_args
from src.utils.datetime_utils import enforce_utc_datetime_transform
from sqlalchemy import desc, asc
from src.services.scheduler_service import SchedulerService
from src.services.task_executor_service import TaskExecutorService
from sqlalchemy.orm.attributes import flag_modified

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CrawlerTaskService(BaseService[CrawlerTasks]):
    """爬蟲任務服務，負責管理爬蟲任務的數據操作（CRUD）"""
    
    def __init__(self, db_manager=None):
        self.running_crawlers = {}
        self.task_execution_status = {}
        super().__init__(db_manager)
    
    def _get_repository_mapping(self) -> Dict[str, Tuple[Type[BaseRepository], Type[Base]]]:
        """提供儲存庫映射"""
        return {
            'CrawlerTask': (CrawlerTasksRepository, CrawlerTasks),
            'Crawler': (CrawlersRepository, Crawlers),
            'TaskHistory': (CrawlerTaskHistoryRepository, CrawlerTaskHistory),
            'Articles': (ArticlesRepository, Articles)
        }
                                


    def _get_crawler_instance(self, crawler_name: str, task_id: int) -> 'BaseCrawler':
        """獲取爬蟲實例"""
        if task_id not in self.running_crawlers:
            self.running_crawlers[task_id] = CrawlerFactory.get_crawler(crawler_name)
        return self.running_crawlers[task_id]
    
    
    def validate_task_data(self, data: Dict[str, Any], is_update: bool = False) -> Dict[str, Any]:
        """驗證任務資料
        
        Args:
            data: 要驗證的資料
            is_update: 是否為更新操作
            
        Returns:
            Dict[str, Any]: 驗證後的資料
                success: 是否成功
                message: 消息
                data: 任務資料
        """

        if data.get('is_auto') is True:
            if data.get('cron_expression') is None:
                raise ValidationError("cron_expression: 當設定為自動執行時,此欄位不能為空")

        task_args = data.get('task_args', TASK_ARGS_DEFAULT)
        # 驗證 task_args 參數
        try:
            validate_task_args('task_args', required=True)(task_args)
        except ValidationError as e:
            raise ValidationError(f"task_args: {str(e)}")
        
        # 根據抓取模式處理相關參數(業務特殊邏輯)
        if data.get('scrape_mode') == ScrapeMode.CONTENT_ONLY.value:
            if 'get_links_by_task_id' not in task_args:
                task_args['get_links_by_task_id'] = True
                
            if not task_args.get('get_links_by_task_id'):
                if 'article_links' not in task_args:
                    raise ValidationError("內容抓取模式需要提供 article_links")
        
        # 更新 task_args
        data['task_args'] = task_args
        schema_type = SchemaType.UPDATE if is_update else SchemaType.CREATE
        return self.validate_data('CrawlerTask', data, schema_type)
        
    def create_task(self, task_data: Dict) -> Dict:
        """創建新任務"""
        validated_data = self.validate_task_data(task_data, is_update=False)
        try:
            with self._transaction() as session:
                # 1. 驗證資料 (必須在事務內)

                
                # 2. 獲取儲存庫
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'task': None
                    }
                
                # 3. 創建任務 (使用驗證後的資料)
                task = tasks_repo.create(validated_data)
                
                if task:
                    # --- Add flush and refresh here ---
                    session.flush()  # Ensure the task is flushed to DB to get the ID
                    session.refresh(task) # Refresh the task object with the generated ID
                    # --- End of addition ---

                    # 重新加載排程 (這裡的邏輯可能需要調整，取決於 SchedulerService 如何運作)
                    if task.is_auto:
                        # scheduler_service = SchedulerService() # 假設可以這樣獲取實例
                        # scheduler_service.reload_schedule() # 觸發排程重新加載
                        logger.info(f"自動任務 {task.id} 已創建，排程可能需要重新加載。")

                    task_schema = CrawlerTaskReadSchema.model_validate(task) # 轉換
                    return {
                        'success': True,
                        'message': '任務創建成功',
                        'task': task_schema # 返回 Schema
                    }
                else:
                     return {
                        'success': False,
                        'message': '任務創建失敗 (repo.create 返回 None)',
                        'task': None
                    }
        except ValidationError as e:
            error_msg = f"創建任務資料驗證失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'task': None
            }
        except Exception as e:
            error_msg = f"創建任務失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'task': None
            }
    
    def update_task(self, task_id: int, task_data: Dict) -> Dict:
        """更新任務數據，包含對 task_args 的特殊處理"""
        try:
            # ***** 使用新的更新模式 *****
            with self._transaction() as session:
                # Get Repository
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'task': None
                    }

                # 1. 從 session 中獲取實體
                task = session.get(CrawlerTasks, task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在',
                        'task': None
                    }

                # 2. 驗證傳入的數據 (使用 repo 的 schema 驗證)
                #    注意：validate_data 返回的是驗證清理後的字典
                #    ** BaseService.validate_data 需要在事務內，這裡已經是
                validated_data = self.validate_task_data(task_data, is_update=True)
                
                entity_modified = False
                task_args_updated = False
                new_task_args = None

                # 3. 遍歷驗證後的數據，區分 task_args 和其他欄位
                for key, value in validated_data.items():
                    if key == 'task_args':
                        # --- 特殊處理 task_args --- 
                        if task.task_args is None:
                            task.task_args = {} # 初始化
                            # flag_modified(task, 'task_args') # 初始化本身不算修改，後續賦值時再標記
                        
                        current_task_args = task.task_args
                        # 需要比較整個字典是否不同
                        if current_task_args != value: 
                            logger.info(f"Task {task_id}: Updating task_args.")
                            logger.debug(f"  Old: {current_task_args}")
                            logger.debug(f"  New: {value}")
                            new_task_args = value # 保存新的字典，稍後賦值
                            task_args_updated = True 
                            entity_modified = True
                        else:
                            logger.info(f"Task {task_id}: task_args are the same, skipping update.")

                    elif hasattr(task, key):
                        # --- 處理其他欄位 --- 
                        current_value = getattr(task, key)
                        if current_value != value:
                            logger.info(f"Task {task_id}: Updating field '{key}' from '{current_value}' to '{value}'.")
                            setattr(task, key, value)
                            entity_modified = True
                
                # 4. 如果 task_args 有變更，執行標記和重新賦值
                if task_args_updated and new_task_args is not None:
                    logger.info(f"Task {task_id}: Applying flag_modified and re-assignment for task_args.")
                    flag_modified(task, 'task_args')
                    task.task_args = new_task_args # 賦予新的字典

                # 5. 檢查是否有任何修改發生
                if not entity_modified:
                    logger.info(f"任務 {task_id} 無需更新，提供的資料與當前狀態相同。")
                    session.refresh(task) # 確保返回的是最新狀態
                    task_schema = CrawlerTaskReadSchema.model_validate(task) # 轉換
                    return {
                        'success': True,
                        'message': '任務無需更新',
                        'task': task_schema # 返回 Schema
                    }

                # _transaction() 會自動處理 commit
                logger.info(f"任務 {task_id} 已在 Session 中更新，等待提交。")
                session.flush() # 確保更新寫入
                session.refresh(task) # 獲取 DB 最新狀態 (可能包含觸發器等)
                task_schema = CrawlerTaskReadSchema.model_validate(task) # 轉換
                return {
                    'success': True,
                    'message': '任務更新成功',
                    'task': task_schema # 返回更新後的 Schema
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
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                    
                success = tasks_repo.delete(task_id)
                # Delete 不返回對象，無需 flush 或 refresh
                return {
                    'success': success,
                    'message': '任務刪除成功' if success else '任務不存在或刪除失敗'
                }
        except Exception as e:
            error_msg = f"刪除任務失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    def get_task_by_id(self, task_id: int, is_active: Optional[bool] = True) -> Dict:
        """獲取指定ID的任務
        
        Args:
            task_id: 任務ID
            is_active: 是否只返回啟用狀態的任務
            
        Returns:
            Dict: 包含任務資料的字典
                success: 是否成功
                message: 消息
                task: 任務資料
        """
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'task': None
                    }
                    
                task = tasks_repo.find_tasks_by_id(task_id, is_active)
                task_schema = CrawlerTaskReadSchema.model_validate(task) if task else None # 轉換
                if task_schema:
                    return {
                        'success': True,
                        'message': '任務獲取成功',
                        'task': task_schema # 返回 Schema
                    }
                return {
                    'success': False,
                    'message': '任務不存在或不符合條件',
                    'task': None
                }
        except Exception as e:
            error_msg = f"獲取任務失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'task': None
            }
    
    def advanced_search_tasks(self, **filters) -> Dict:
        """進階搜尋任務
        
        可用過濾條件：
        - task_name: 任務名稱 (模糊搜尋)
        - crawler_id: 爬蟲ID
        - is_auto: 是否自動執行
        - is_active: 是否啟用
        - ai_only: 是否只抓取AI相關文章 (task_args)
        - last_run_success: 上次執行是否成功
        - date_range: 上次執行時間範圍，格式為(start_date, end_date)
        - has_notes: 是否有備註
        - task_status: 任務狀態 (TaskStatus Enum 或其 value)
        - scrape_phase: 爬取階段 (ScrapePhase Enum 或其 value)
        - cron_expression: cron表達式
        - retry_count: 重試次數 (可以是整數或範圍字典 {"min": x, "max": y})
        - max_pages: 最大頁數 (task_args)
        - save_to_csv: 是否保存到CSV (task_args)
        - scrape_mode: 抓取模式 (task_args, ScrapeMode Enum 或其 value)
        - sort_by: 排序欄位名稱 (預設 'created_at')
        - sort_desc: 是否降冪排序 (預設 False)
        - limit: 限制數量
        - offset: 偏移量
        
        Returns:
            Dict: 包含搜尋結果的字典 ('success', 'message', 'tasks', 'total_count')
        """
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                if not tasks_repo:  
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'tasks': [],
                        'total_count': 0
                    }       
                
                # 使用 Repository 的 advanced_search 方法
                search_result = tasks_repo.advanced_search(**filters)
                
                # Repository 的方法應該返回 {'tasks': [...], 'total_count': N}
                if search_result is None:
                    # 處理 Repository 返回 None 的情況
                     return {
                        'success': False,
                        'message': '任務搜尋失敗 (Repository 返回 None)',
                        'tasks': [],
                        'total_count': 0
                    }

                tasks_orm = search_result.get('tasks', []) or [] # 確保是列表
                tasks_schema = [CrawlerTaskReadSchema.model_validate(t) for t in tasks_orm] # 轉換

                return {
                    'success': True,
                    'message': '任務搜尋成功',
                    'tasks': tasks_schema, # 返回 Schema 列表
                    'total_count': search_result.get('total_count', 0)
                }
        except Exception as e:
            error_msg = f"進階搜尋任務失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'tasks': [],
                'total_count': 0
            }

    def get_task_history(self, task_id: int, limit: Optional[int] = None, offset: Optional[int] = None, sort_desc: bool = True) -> Dict:
        """獲取任務的執行歷史記錄 (可選分頁和排序)"""
        try:
            with self._transaction() as session:
                logger.debug(f"task_service.get_task_history() before get_repository ：Session ID: {id(session)}")
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('TaskHistory', session))
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'histories': [],
                        'total_count': 0
                    }
                
                logger.debug(f"task_service.get_task_history() before find_by_task_id ：Session ID: {id(session)}")
                histories = history_repo.find_by_task_id(
                    task_id=task_id,
                    limit=limit,
                    offset=offset,
                    sort_desc=sort_desc
                )
                logger.debug(f"task_service.get_task_history() after find_by_task_id ：Session ID: {id(session)}")
                return {
                    'success': True,
                    'message': '任務歷史獲取成功',
                    'histories': histories,
                    'total_count': len(histories)
                }
        except Exception as e:
            error_msg = f"獲取任務歷史失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'histories': [],
                'total_count': 0
            }

    def get_task_status(self, task_id: int) -> Dict:
        """獲取任務的當前狀態（從任務本身和最新歷史記錄推斷）"""
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('TaskHistory', session))
                
                if not tasks_repo or not history_repo:
                    return {
                        'task_status': TaskStatus.UNKNOWN,
                        'scrape_phase': ScrapePhase.UNKNOWN,
                        'progress': 0,
                        'message': '無法取得資料庫存取器',
                        'task': None,
                        'history': None
                    }
                    
                # 檢查任務是否存在
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'task_status': TaskStatus.UNKNOWN, 
                        'scrape_phase': ScrapePhase.UNKNOWN, 
                        'progress': 0,
                        'message': '任務不存在',
                        'task': None,
                        'history': None
                    }
                    
                # 從資料庫獲取最新一筆歷史記錄 (按 end_time 或 start_time 降冪排序)
                latest_history = history_repo.get_latest_history(task_id)
                
                # --- 推斷狀態邏輯 --- 
                task_status = task.task_status # 默認使用任務表中的狀態
                scrape_phase = task.scrape_phase # 默認使用任務表中的階段
                progress = 0
                message = '狀態來自任務表' 
                
                if latest_history:
                    message = latest_history.message or '狀態來自最新歷史記錄'
                    # 如果歷史記錄指示任務已結束 (完成/失敗/取消)
                    if latest_history.end_time and latest_history.task_status in [
                        TaskStatus.COMPLETED, 
                        TaskStatus.FAILED, 
                        TaskStatus.CANCELLED
                    ]:
                        task_status = latest_history.task_status
                        scrape_phase = ScrapePhase.COMPLETED
                        progress = 100
                    # 如果歷史記錄指示任務正在運行 (有開始時間但無結束時間)
                    elif latest_history.start_time and not latest_history.end_time:
                        task_status = TaskStatus.RUNNING
                        # 強制設為 RUNNING
                        # 階段可能需要更精確的判斷，暫時維持任務表中的值或設為 RUNNING
                        current_time = datetime.now(timezone.utc)
                        elapsed = current_time - enforce_utc_datetime_transform(latest_history.start_time)
                        # 這裡的進度計算非常粗略，僅作示意
                        progress = min(95, int((elapsed.total_seconds() / 300) * 100))
                        message = f"任務運行中 ({progress}%)" 
                    # 其他情況 (例如只有 ID 沒有時間戳，或狀態不一致)
                    else:
                        # 維持從 task 表讀取的值，但可以更新 message
                        message = f"狀態來自任務表 (歷史記錄狀態: {latest_history.task_status})"
                else:
                    # 沒有歷史記錄，狀態完全來自任務表
                    message = '無執行歷史，狀態來自任務表'
                    # 如果任務狀態是 IDLE/PENDING 等，進度為 0
                    if task_status not in [TaskStatus.RUNNING]:
                        progress = 0
                    # 否則，可能表示任務从未運行或狀態異常
                
                task_schema = CrawlerTaskReadSchema.model_validate(task) if task else None # 轉換 task
                # history_schema = CrawlerTaskHistoryReadSchema.model_validate(latest_history) if latest_history else None # 假設有 History Schema

                return {
                    'task_status': task_status,
                    'scrape_phase': scrape_phase,
                    'progress': progress,
                    'message': message,
                    'task': task_schema, # 返回 Task Schema
                    'history': latest_history # 暫時仍返回 ORM 或 None
                }
                
        except Exception as e:
            error_msg = f"獲取任務狀態失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'task_status': TaskStatus.UNKNOWN,
                'scrape_phase': ScrapePhase.UNKNOWN,
                'progress': 0,
                'message': f'獲取狀態時發生錯誤: {str(e)}',
                'task': None,
                'history': None
            }


    def get_failed_tasks(self, days: int = 1) -> Dict:
        """獲取最近失敗的任務"""
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'tasks': []
                    }
                    
                failed_tasks = tasks_repo.get_failed_tasks(days)
                tasks_orm = failed_tasks or [] # 確保是列表
                tasks_schema = [CrawlerTaskReadSchema.model_validate(t) for t in tasks_orm] # 轉換
                return {
                    'success': True,
                    'message': f'成功獲取最近 {days} 天失敗的任務',
                    'tasks': tasks_schema # 返回 Schema 列表
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
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'task': None
                    }
                
                # 使用 Repository 的 toggle_auto_status 方法
                task = tasks_repo.toggle_auto_status(task_id) 
                
                if task:
                     # 可能需要重新加載排程
                    # scheduler_service = SchedulerService()
                    # scheduler_service.reload_schedule()
                    logger.info(f"自動任務 {task.id} 已創建，排程可能需要重新加載。")
                    task_schema = CrawlerTaskReadSchema.model_validate(task) # 轉換
                    return {
                        'success': True,
                        'message': f'自動執行狀態切換為 {task.is_auto}',
                        'task': task_schema # 返回 Schema
                    }
                else:
                    return {
                        'success': False,
                        'message': '任務不存在或切換失敗',
                        'task': None
                    }
        except Exception as e:
            error_msg = f"切換任務自動執行狀態失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'task': None
            }
        
    def toggle_active_status(self, task_id: int) -> Dict:
        """切換任務的啟用狀態"""
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'task': None
                    }
                
                # 使用 Repository 的 toggle_active_status 方法
                task = tasks_repo.toggle_active_status(task_id)

                if task:
                     # 可能需要重新加載排程，如果涉及禁用自動任務
                    # if not task.is_active and task.is_auto:
                    #     scheduler_service = SchedulerService()
                    #     scheduler_service.reload_schedule()
                    logger.info(f"任務 {task_id} 啟用狀態切換為 {task.is_active}。")
                    task_schema = CrawlerTaskReadSchema.model_validate(task) # 轉換
                    return {
                        'success': True,
                        'message': f'啟用狀態切換為 {task.is_active}',
                        'task': task_schema # 返回 Schema
                    }
                else:
                     return {
                        'success': False,
                        'message': '任務不存在或切換失敗',
                        'task': None
                    }
        except Exception as e:
            error_msg = f"切換任務啟用狀態失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'task': None
            }
            
    
    def update_task_notes(self, task_id: int, notes: str) -> Dict:
        """更新任務備註"""
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'task': None
                    }
                
                # 使用 Repository 的 update_notes 方法
                task = tasks_repo.update_notes(task_id, notes)
                task_schema = CrawlerTaskReadSchema.model_validate(task) if task else None # 轉換
                
                if task_schema:
                    return {
                        'success': True,
                        'message': '備註更新成功',
                        'task': task_schema # 返回 Schema
                    }
                else:
                    return {
                        'success': False,
                        'message': '任務不存在或更新失敗',
                        'task': None
                    }
        except Exception as e:
            error_msg = f"更新任務備註失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'task': None
            }

    def get_all_tasks(self) -> Dict:
        """獲取所有任務"""
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'tasks': []
                    }   
                    
                tasks = tasks_repo.get_all()
                tasks_orm = tasks or [] # 確保是列表
                tasks_schema = [CrawlerTaskReadSchema.model_validate(t) for t in tasks_orm] # 轉換
                return {
                    'success': True,
                    'message': '任務查詢成功',
                    'tasks': tasks_schema # 返回 Schema 列表
                }
        except Exception as e:
            error_msg = f"獲取所有任務失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'tasks': []
            }

    def find_tasks_by_multiple_crawlers(self, crawler_ids: List[int]) -> Dict:
        """根據多個爬蟲ID查詢任務"""
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'tasks': []
                    }
                    
                tasks = tasks_repo.find_tasks_by_multiple_crawlers(crawler_ids)
                tasks_orm = tasks or [] # 確保是列表
                tasks_schema = [CrawlerTaskReadSchema.model_validate(t) for t in tasks_orm] # 轉換
                return {
                    'success': True,
                    'message': '任務查詢成功',
                    'tasks': tasks_schema # 返回 Schema 列表
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
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'tasks': []
                    }
                    
                tasks = tasks_repo.find_tasks_by_cron_expression(cron_expression)
                tasks_orm = tasks or [] # 確保是列表
                tasks_schema = [CrawlerTaskReadSchema.model_validate(t) for t in tasks_orm] # 轉換
                return {
                    'success': True,
                    'message': '任務查詢成功',
                    'tasks': tasks_schema # 返回 Schema 列表
                }
        except ValidationError as e: # Cron 表達式驗證可能在 Repo 層完成
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
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'tasks': []
                    }
                tasks = tasks_repo.find_pending_tasks(cron_expression)
                tasks_orm = tasks or [] # 確保是列表
                tasks_schema = [CrawlerTaskReadSchema.model_validate(t) for t in tasks_orm] # 轉換
                return {
                    'success': True,
                    'message': '待執行任務查詢成功',
                    'tasks': tasks_schema # 返回 Schema 列表
                }
        except ValidationError as e: # Cron 驗證
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
        """更新任務的最後執行狀態和時間"""
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'task': None
                    }
                
                # 使用 Repository 的 update_last_run 方法，假設它返回更新後的 task
                task = tasks_repo.update_last_run(task_id, success, message)
                task_schema = CrawlerTaskReadSchema.model_validate(task) if task else None # 轉換
                
                if task_schema:
                    return {
                        'success': True,
                        'message': '任務執行狀態更新成功',
                        'task': task_schema # 返回 Schema
                    }
                else:
                    return {
                        'success': False,
                        'message': '任務不存在或更新失敗',
                        'task': None
                    }
        except Exception as e:
            error_msg = f"更新任務執行狀態失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'task': None
            }

    def update_task_status(self, task_id: int, task_status: Optional[TaskStatus] = None, scrape_phase: Optional[ScrapePhase] = None, history_id: Optional[int] = None, history_data: Optional[dict] = None) -> Dict:
        """更新任務狀態和/或歷史記錄
        
        Args:
            task_id: 任務ID
            task_status: 新的任務狀態 (Enum)
            scrape_phase: 新的爬取階段 (Enum)
            history_id: 如果要更新現有歷史記錄，提供其 ID
            history_data: 如果要創建或更新歷史記錄，提供數據字典
            
        Returns:
            包含更新後任務和歷史記錄 (如果操作) 的字典
        """
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('TaskHistory', session))
                
                if not tasks_repo or not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'task': None,
                        'history': None,
                        'updated': False
                    }
                
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在',
                        'task': None,
                        'history': None,
                        'updated': False
                    }
                
                # --- 更新任務狀態和階段 --- 
                update_data = {}
                task_updated = False
                
                if task_status is not None and task_status.value != task.task_status:
                    update_data['task_status'] = task_status.value
                    task_updated = True
                
                if scrape_phase is not None and scrape_phase.value != task.scrape_phase:
                    update_data['scrape_phase'] = scrape_phase.value
                    task_updated = True
                
                task_result = task # 默認返回現有 task
                if task_updated:
                    task_result = tasks_repo.update(task_id, update_data)
                    if not task_result:
                         # 如果更新失敗，記錄錯誤但可能繼續處理歷史記錄
                         logger.error(f"任務 {task_id} 狀態更新失敗，repo 返回 None")
                         task_updated = False # 標記為未更新成功
                         task_result = task # 回退到原始 task
                    else:
                         logger.info(f"任務 {task_id} 狀態更新為: {update_data}")

                # --- 處理歷史記錄 --- 
                history_result = None
                history_created = False
                history_updated = False

                if history_data:
                    try:
                        if history_id:
                            # 更新現有歷史記錄
                            validated_history_data = history_repo.validate_data(history_data, SchemaType.UPDATE)
                            history_result = history_repo.update(history_id, validated_history_data)
                            if history_result:
                                history_updated = True
                                logger.info(f"任務 {task_id} 的歷史記錄 {history_id} 已更新。")
                            else:
                                logger.warning(f"任務 {task_id} 的歷史記錄 {history_id} 更新失敗 (repo 返回 None)。")
                        else:
                            # 創建新歷史記錄
                            validated_history_data = history_repo.validate_data(history_data, SchemaType.CREATE)
                            # 確保 task_id 正確設置
                            validated_history_data['task_id'] = task_id 
                            history_result = history_repo.create(validated_history_data)
                            if history_result:
                                history_created = True
                                history_id = history_result.id # 獲取新 ID
                                logger.info(f"任務 {task_id} 的新歷史記錄 {history_id} 已創建。")
                            else:
                                logger.error(f"任務 {task_id} 的新歷史記錄創建失敗 (repo 返回 None)。")
                    except ValidationError as ve:
                         logger.error(f"任務 {task_id} 的歷史記錄數據驗證失敗: {ve}")
                         # 可以在這裡決定是否中止操作或僅記錄錯誤
                    except Exception as he:
                         logger.error(f"處理任務 {task_id} 的歷史記錄時出錯: {he}")

                # --- 準備返回消息 --- 
                messages = []
                if task_updated: messages.append(f"任務狀態已更新")
                if history_created: messages.append(f"歷史記錄已創建(ID:{history_id})")
                if history_updated: messages.append(f"歷史記錄(ID:{history_id})已更新")
                if not messages: messages.append("無狀態或歷史記錄變更")
                
                final_message = ", ".join(messages)
                
                return {
                    'success': True, # 操作嘗試成功，即使內部可能有部分失敗
                    'message': final_message,
                    'task': CrawlerTaskReadSchema.model_validate(task_result) if task_result else None, # 返回更新後 (或原始) 的 task Schema
                    'history': history_result, # 返回創建/更新後 (或 None) 的 history 對象
                    'updated': task_updated or history_created or history_updated # 是否有任何實際變更
                }
        except Exception as e:
            error_msg = f"更新任務狀態/歷史時發生意外錯誤, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # 即使出錯，也嘗試返回獲取到的 task (如果有的話)
            task_before_error = None
            try:
                # 嘗試在新的事務中再次獲取任務狀態，以防主事務已回滾
                 with self._transaction() as s: 
                    repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', s))
                    if repo: task_before_error = repo.get_by_id(task_id)
            except Exception: pass # 忽略這裡的錯誤
            
            return {
                'success': False,
                'message': error_msg,
                'task': task_before_error, 
                'history': None,
                'updated': False
            }

    def increment_retry_count(self, task_id: int) -> Dict:
        """增加任務重試次數
        
        Args:
            task_id: 任務ID
            
        Returns:
            更新結果，包含當前重試次數和是否超過最大重試次數
        """
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'exceeded_max_retries': None,
                        'retry_count': None,
                        'max_retries': None,
                        'task': None
                    }
                
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在',
                        'exceeded_max_retries': None,
                        'retry_count': None,
                        'max_retries': None,
                        'task': None
                    }
                
                # 獲取最大重試次數 (確保 task_args 存在)
                task_args = task.task_args or {}
                max_retries = task_args.get('max_retries', 0)
                
                # 如果最大重試次數為0，表示不允許重試
                if max_retries <= 0:
                    return {
                        'success': False,
                        'message': '任務設定為不允許重試（最大重試次數為0或未設定）',
                        'exceeded_max_retries': True,
                        'retry_count': task.retry_count,
                        'max_retries': max_retries,
                        'task': task
                    }
                
                # 檢查是否已達到最大重試次數
                if task.retry_count >= max_retries:
                    return {
                        'success': False,
                        'message': f'已達到最大重試次數 {max_retries}',
                        'exceeded_max_retries': True,
                        'retry_count': task.retry_count,
                        'max_retries': max_retries,
                        'task': task
                    }
                
                # 增加重試次數
                current_retry = task.retry_count + 1
                task_data = {'retry_count': current_retry}
                result_task = tasks_repo.update(task_id, task_data) # 假設 update 返回更新後的 task
                result_task_schema = CrawlerTaskReadSchema.model_validate(result_task) if result_task else None # 轉換
                
                if not result_task_schema:
                     # 更新失敗的處理
                     task_schema = CrawlerTaskReadSchema.model_validate(task) # 轉換原始 task
                     return {
                        'success': False,
                        'message': '增加重試次數失敗 (repo.update 返回 None)',
                        'exceeded_max_retries': None,
                        'retry_count': task.retry_count, # 返回原始值
                        'max_retries': max_retries,
                        'task': task_schema # 返回原始 Schema
                    }

                # 檢查是否達到最大重試次數
                has_reached_max = current_retry >= max_retries
                
                return {
                    'success': True,
                    'message': f'重試次數更新為 {current_retry}/{max_retries}',
                    'retry_count': current_retry,
                    'max_retries': max_retries,
                    'exceeded_max_retries': has_reached_max,
                    'task': result_task_schema # 返回更新後的 Schema
                }
        except Exception as e:
            error_msg = f"更新重試次數失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'exceeded_max_retries': None,
                'retry_count': None,
                'max_retries': None,
                'task': None
            }

    def reset_retry_count(self, task_id: int) -> Dict:
        """重置任務重試次數為 0
        
        Args:
            task_id: 任務ID
            
        Returns:
            更新結果
        """
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'task': None
                    }
                
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在',
                        'task': None
                    }
                
                # 僅當 retry_count 不為 0 時才更新
                if task.retry_count == 0:
                     return {
                        'success': True,
                        'message': '重試次數已是 0，無需重置',
                        'task': task
                    }
                
                # 重置重試次數
                task_data = {'retry_count': 0}
                result_task = tasks_repo.update(task_id, task_data)
                result_task_schema = CrawlerTaskReadSchema.model_validate(result_task) if result_task else None # 轉換
                
                if not result_task_schema:
                    task_schema = CrawlerTaskReadSchema.model_validate(task) # 轉換原始 task
                    return {
                        'success': False,
                        'message': '重置重試次數失敗 (repo.update 返回 None)',
                        'task': task_schema # 返回原始 Schema
                    }

                return {
                    'success': True,
                    'message': '重試次數已重置為 0',
                    'task': result_task_schema # 返回更新後的 Schema
                }
        except Exception as e:
            error_msg = f"重置重試次數失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'task': None
            }

    def update_max_retries(self, task_id: int, max_retries: int) -> Dict:
        """更新任務最大重試次數 (存儲在 task_args 中)
        
        Args:
            task_id: 任務ID
            max_retries: 新的最大重試次數 (非負整數)
            
        Returns:
            更新結果
        """
        # 檢查數值範圍
        if not isinstance(max_retries, int) or max_retries < 0:
            return {
                'success': False,
                'message': '最大重試次數必須是非負整數',
                'task': None
            }
        
        # 定義合理的上限值，避免設置過大數值
        MAX_ALLOWED_RETRIES = 50 
        if max_retries > MAX_ALLOWED_RETRIES:
            return {
                'success': False,
                'message': f'最大重試次數不能超過 {MAX_ALLOWED_RETRIES}',
                'task': None
            }
        
        try:
            # 使用更新模式，確保對 JSON 欄位的修改能被正確持久化
            with self._transaction() as session: 
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'task': None
                    }
                
                # 從 session 中獲取實體 (重要：不要用 repo.get_by_id)
                task = session.get(CrawlerTasks, task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在',
                        'task': None
                    }
                
                # 準備新的 task_args 字典
                if task.task_args is None:
                     task.task_args = {} # 初始化
                     # 不需要立即標記，後續賦值會處理

                # 獲取當前值並比較
                current_max_retries = task.task_args.get('max_retries') 
                if current_max_retries == max_retries:
                    logger.info(f"任務 {task_id} 的 max_retries 已是 {max_retries}，無需更新。")
                    session.refresh(task) # 確保返回的是最新狀態
                    task_schema = CrawlerTaskReadSchema.model_validate(task) # 轉換
                    return {
                        'success': True,
                        'message': f'最大重試次數無需更新，當前值: {max_retries}',
                        'task': task_schema # 返回 Schema
                    }
                
                # 更新 task_args 字典
                # 創建副本以避免直接修改 session 中的對象 (雖然 flag_modified 會處理)
                new_task_args = task.task_args.copy()
                new_task_args['max_retries'] = max_retries
                logger.info(f"Updating max_retries for task {task_id} from {current_max_retries} to {max_retries}")
                
                # 關鍵步驟：標記修改 和 重新賦值
                flag_modified(task, 'task_args')
                task.task_args = new_task_args
                
                # _transaction() 會自動處理 commit 和 flush
                logger.info(f"任務 {task_id} 的最大重試次數已在 Session 中更新為 {max_retries}，等待提交。")
                
                session.flush() # 確保更新寫入 DB
                session.refresh(task) # 從 DB 讀取最新狀態 (包括 task_args)
                
                task_schema = CrawlerTaskReadSchema.model_validate(task) # 轉換
                return {
                    'success': True,
                    'message': f'最大重試次數更新為 {max_retries}',
                    'task': task_schema # 返回更新後的 Schema
                }
        except Exception as e:
            error_msg = f"更新最大重試次數失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'task': None
            }



