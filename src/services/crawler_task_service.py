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
from src.models.crawler_tasks_schema import CrawlerTasksCreateSchema, CrawlerTasksUpdateSchema, CrawlerTaskReadSchema, PaginatedCrawlerTaskResponse
from src.models.crawler_task_history_schema import CrawlerTaskHistoryReadSchema
from src.error.errors import ValidationError, DatabaseOperationError, InvalidOperationError
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
        """驗證任務資料，因此介面公開給API使用，因此一律包裝成字典返回，供前端使用
        
        Args:
            data: 要驗證的資料
            is_update: 是否為更新操作
            
        Returns:
            Dict[str, Any]: 驗證的訊息及資料
                success: 是否成功
                message: 消息
                data: 任務資料
        """
        try:
            if data.get('is_auto') is True:
                if data.get('cron_expression') is None:
                    return {
                        'success': False,
                        'message': "資料驗證失敗：cron_expression: 當設定為自動執行時,此欄位不能為空",
                        'data': None
                    }

            task_args = data.get('task_args', TASK_ARGS_DEFAULT)
            # 驗證 task_args 參數
            try:
                validate_task_args('task_args', required=True)(task_args)
            except ValidationError as e:
                return {
                    'success': False,
                    'message': f"資料驗證失敗：task_args: {str(e)}",
                    'data': None
                }
            
            # 根據抓取模式處理相關參數(業務特殊邏輯)
            if task_args.get('scrape_mode') == ScrapeMode.CONTENT_ONLY.value:
                if 'get_links_by_task_id' not in task_args:
                    task_args['get_links_by_task_id'] = True
                    
                if not task_args.get('get_links_by_task_id'):
                    if 'article_links' not in task_args:
                        return {
                            'success': False,
                            'message': "資料驗證失敗：內容抓取模式需要提供 article_links，或get_links_by_task_id=True由任務ID獲取文章連結",
                            'data': None
                        }
            
            # 更新 task_args
            data['task_args'] = task_args
            schema_type = SchemaType.UPDATE if is_update else SchemaType.CREATE
            try:
                validated_data = self.validate_data('CrawlerTask', data, schema_type)
            except ValidationError as e:
                return {
                    'success': False,
                    'message': f"資料驗證失敗：task_args: {str(e)}",
                    'data': None
                }
            return {
                'success': True,
                'message': '資料驗證成功',
                'data': validated_data
            }
        except Exception as e:
            return {
                'success': False,
                'message': f"資料驗證失敗：{str(e)}",
                'data': None
            }
    
    def create_task(self, task_data: Dict) -> Dict:
        """創建新任務"""
        validated_result = self.validate_task_data(task_data, is_update=False)
        if not validated_result['success']:
            return validated_result
        validated_data = validated_result['data']
        
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
        """更新任務數據，包含對 task_args 的特殊處理
        
        Args:
            task_id: 任務ID
            task_data: 要更新的任務數據
            
        Returns:
            Dict: 包含更新結果的字典
        """
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
                validated_result = self.validate_task_data(task_data, is_update=True)
                if not validated_result['success']:
                    return validated_result
                validated_data = validated_result['data']
                
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
                            logger.info(f"Task {task_id}: task_args 資料相同，跳過更新。")

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
                    
                task = tasks_repo.get_task_by_id(task_id, is_active)
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
    
    def find_tasks_advanced(
        self,
        page: int = 1,
        per_page: int = 10,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
        **filters
    ) -> Dict:
        """進階搜尋任務"""
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))

                # 提取分頁和排序參數，剩下的作為過濾器
                sort_by = filters.pop('sort_by', 'created_at') # Default sort
                sort_desc = filters.pop('sort_desc', True)    # Default order
                limit = per_page
                offset = (page - 1) * per_page

                # 調用 Repository 的 advanced_search 方法，傳入預覽參數
                result_dict = tasks_repo.advanced_search(
                    is_preview=is_preview,
                    preview_fields=preview_fields,
                    limit=limit,
                    offset=offset,
                    sort_by=sort_by,
                    sort_desc=sort_desc,
                    **filters # 傳遞剩餘的過濾條件
                )

                items = result_dict['tasks']
                total_count = result_dict['total_count']
                total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

                # 如果不是預覽模式，將模型實例轉換為 Schema
                if not is_preview:
                    items_schema = [CrawlerTaskReadSchema.model_validate(item) for item in items]
                else:
                    items_schema = items # 預覽模式下直接使用字典列表

                # 使用 PaginatedCrawlerTaskResponse 封裝結果
                paginated_response = PaginatedCrawlerTaskResponse(
                    items=items_schema,
                    page=page,
                    per_page=per_page,
                    total=total_count,
                    total_pages=total_pages,
                    has_next=page < total_pages,
                    has_prev=page > 1
                )

                return {
                    'success': True,
                    'message': '任務搜尋成功',
                    'data': paginated_response.model_dump() # 返回 Pydantic 模型字典
                }
        except ValidationError as e:
             logger.error(f"進階搜尋任務驗證失敗: {e}")
             return {'success': False, 'message': f"搜尋參數驗證失敗: {e}", 'data': None}
        except (DatabaseOperationError, InvalidOperationError) as e:
            logger.error(f"進階搜尋任務失敗: {e}")
            return {'success': False, 'message': str(e), 'data': None}
        except Exception as e:
            logger.error(f"進階搜尋任務時發生未預期錯誤: {e}", exc_info=True)
            return {'success': False, 'message': '搜尋任務時發生未預期錯誤', 'data': None}

    def find_task_history(self, task_id: int,
                          limit: Optional[int] = None,
                          offset: Optional[int] = None,
                          sort_desc: bool = True, # Keep original default sort
                          is_preview: bool = False,
                          preview_fields: Optional[List[str]] = None
                          ) -> Dict:
        """獲取任務的執行歷史"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('TaskHistory', session))

                # 使用 find_by_task_id 方法
                histories = history_repo.find_by_task_id(
                    task_id=task_id,
                    limit=limit,
                    offset=offset,
                    sort_desc=sort_desc, # Pass sort preference
                    is_preview=is_preview,
                    preview_fields=preview_fields
                )

                # 如果不是預覽模式，轉換為 Schema (假設有 CrawlerTaskHistoryReadSchema)
                if not is_preview:
                    # Ensure CrawlerTaskHistoryReadSchema exists and works
                    histories_schema = [CrawlerTaskHistoryReadSchema.model_validate(h) for h in histories]
                else:
                    histories_schema = histories # Use dict list directly

                return {
                    'success': True,
                    'message': '任務歷史獲取成功',
                    'history': histories_schema
                }
        except (DatabaseOperationError, InvalidOperationError) as e:
            logger.error(f"獲取任務 {task_id} 歷史失敗: {e}")
            return {'success': False, 'message': str(e), 'history': []}
        except Exception as e:
            logger.error(f"獲取任務 {task_id} 歷史時發生未預期錯誤: {e}", exc_info=True)
            return {'success': False, 'message': '獲取任務歷史時發生未預期錯誤', 'history': []}

    def get_task_status(self, task_id: int) -> Dict:
        """獲取任務的狀態"""
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                task = tasks_repo.get_by_id(task_id) # Get regardless of active status

                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在',
                        'status': None
                    }

                # 提取狀態相關信息
                status_info = {
                    'task_id': task.id,
                    'task_name': task.task_name,
                    'is_active': task.is_active,
                    'is_auto': task.is_auto,
                    'is_scheduled': task.is_scheduled,
                    'task_status': task.task_status.value if task.task_status else None,
                    'scrape_phase': task.scrape_phase.value if task.scrape_phase else None,
                    'last_run_at': task.last_run_at,
                    'last_run_success': task.last_run_success,
                    'last_run_message': task.last_run_message,
                    'retry_count': task.retry_count,
                    'cron_expression': task.cron_expression,
                    'updated_at': task.updated_at
                }

                return {
                    'success': True,
                    'message': '任務狀態獲取成功',
                    'status': status_info
                }
        except (DatabaseOperationError, InvalidOperationError) as e:
            logger.error(f"獲取任務 {task_id} 狀態失敗: {e}")
            return {'success': False, 'message': str(e), 'status': None}
        except Exception as e:
            logger.error(f"獲取任務 {task_id} 狀態時發生未預期錯誤: {e}", exc_info=True)
            return {'success': False, 'message': '獲取任務狀態時發生未預期錯誤', 'status': None}

    def find_failed_tasks(self, days: int = 1,
                          limit: Optional[int] = None,
                          is_preview: bool = False,
                          preview_fields: Optional[List[str]] = None
                          ) -> Dict:
        """獲取最近失敗的任務 (只查詢 is_active=True 的任務)"""
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))

                failed_tasks = tasks_repo.find_failed_tasks(
                    days=days,
                    limit=limit,
                    is_preview=is_preview,
                    preview_fields=preview_fields
                )

                # Convert to Schema if not preview
                if not is_preview:
                    tasks_schema = [CrawlerTaskReadSchema.model_validate(task) for task in failed_tasks]
                else:
                    tasks_schema = failed_tasks

                return {
                    'success': True,
                    'message': f'最近 {days} 天失敗的活動任務查詢成功',
                    'tasks': tasks_schema
                }
        except (DatabaseOperationError, InvalidOperationError) as e:
            logger.error(f"查詢最近 {days} 天失敗任務失敗: {e}")
            return {'success': False, 'message': str(e), 'tasks': []}
        except Exception as e:
            logger.error(f"查詢最近 {days} 天失敗任務時發生未預期錯誤: {e}", exc_info=True)
            return {'success': False, 'message': '查詢失敗任務時發生未預期錯誤', 'tasks': []}

    def toggle_auto_status(self, task_id: int) -> Dict:
        """切換任務的自動執行狀態"""
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                # Repo method does not commit
                updated_task = tasks_repo.toggle_auto_status(task_id)

                if updated_task:
                    session.flush()
                    session.refresh(updated_task)
                    logger.info(f"任務 ID {task_id} 自動執行狀態已切換並準備提交。")
                    task_schema = CrawlerTaskReadSchema.model_validate(updated_task)
                    return {
                        'success': True,
                        'message': '自動執行狀態切換成功',
                        'task': task_schema
                    }
                else:
                    return {'success': False, 'message': '任務不存在', 'task': None}
        except (DatabaseOperationError, InvalidOperationError) as e:
            logger.error(f"切換任務 {task_id} 自動狀態失敗: {e}")
            return {'success': False, 'message': str(e), 'task': None}
        except Exception as e:
            logger.error(f"切換任務 {task_id} 自動狀態時發生未預期錯誤: {e}", exc_info=True)
            return {'success': False, 'message': '切換自動狀態時發生未預期錯誤', 'task': None}

    def toggle_active_status(self, task_id: int) -> Dict:
        """切換任務的啟用狀態"""
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                updated_task = tasks_repo.toggle_active_status(task_id)

                if updated_task:
                    session.flush()
                    session.refresh(updated_task)
                    logger.info(f"任務 ID {task_id} 啟用狀態已切換並準備提交。")
                    task_schema = CrawlerTaskReadSchema.model_validate(updated_task)
                    return {
                        'success': True,
                        'message': '啟用狀態切換成功',
                        'task': task_schema
                    }
                else:
                    return {'success': False, 'message': '任務不存在', 'task': None}
        except (DatabaseOperationError, InvalidOperationError) as e:
            logger.error(f"切換任務 {task_id} 啟用狀態失敗: {e}")
            return {'success': False, 'message': str(e), 'task': None}
        except Exception as e:
            logger.error(f"切換任務 {task_id} 啟用狀態時發生未預期錯誤: {e}", exc_info=True)
            return {'success': False, 'message': '切換啟用狀態時發生未預期錯誤', 'task': None}

    def update_task_notes(self, task_id: int, notes: str) -> Dict:
        """更新任務備註"""
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                # Validate notes using schema logic (optional here, repo update validates)
                # tasks_repo.validate_data({"notes": notes}, SchemaType.UPDATE) # Example validation

                updated_task = tasks_repo.update_notes(task_id, notes)

                if updated_task:
                    session.flush()
                    session.refresh(updated_task)
                    logger.info(f"任務 ID {task_id} 備註已更新並準備提交。")
                    task_schema = CrawlerTaskReadSchema.model_validate(updated_task)
                    return {
                        'success': True,
                        'message': '任務備註更新成功',
                        'task': task_schema
                    }
                else:
                    return {'success': False, 'message': '任務不存在', 'task': None}
        except ValidationError as e:
             logger.error(f"更新任務 {task_id} 備註驗證失敗: {e}")
             return {'success': False, 'message': f"驗證失敗: {e}", 'task': None}
        except (DatabaseOperationError, InvalidOperationError) as e:
            logger.error(f"更新任務 {task_id} 備註失敗: {e}")
            return {'success': False, 'message': str(e), 'task': None}
        except Exception as e:
            logger.error(f"更新任務 {task_id} 備註時發生未預期錯誤: {e}", exc_info=True)
            return {'success': False, 'message': '更新備註時發生未預期錯誤', 'task': None}

    def find_all_tasks(self,
                       limit: Optional[int] = None,
                       offset: Optional[int] = None,
                       sort_by: Optional[str] = None,
                       sort_desc: bool = False,
                       is_preview: bool = False,
                       preview_fields: Optional[List[str]] = None
                       ) -> Dict:
        """獲取所有任務"""
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                tasks = tasks_repo.find_all(
                    limit=limit,
                    offset=offset,
                    sort_by=sort_by,
                    sort_desc=sort_desc,
                    is_preview=is_preview,
                    preview_fields=preview_fields
                )

                # Convert to Schema if not preview
                if not is_preview:
                    tasks_schema = [CrawlerTaskReadSchema.model_validate(task) for task in tasks]
                else:
                    tasks_schema = tasks

                return {
                    'success': True,
                    'message': '所有任務獲取成功',
                    'tasks': tasks_schema
                }
        except (DatabaseOperationError, InvalidOperationError) as e:
            logger.error(f"獲取所有任務失敗: {e}")
            return {'success': False, 'message': str(e), 'tasks': []}
        except Exception as e:
            logger.error(f"獲取所有任務時發生未預期錯誤: {e}", exc_info=True)
            return {'success': False, 'message': '獲取所有任務時發生未預期錯誤', 'tasks': []}

    def find_tasks_by_multiple_crawlers(self, crawler_ids: List[int],
                                        limit: Optional[int] = None,
                                        is_preview: bool = False,
                                        preview_fields: Optional[List[str]] = None
                                        ) -> Dict:
        """根據多個爬蟲ID查詢任務"""
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                tasks = tasks_repo.find_tasks_by_multiple_crawlers(
                    crawler_ids=crawler_ids,
                    limit=limit,
                    is_preview=is_preview,
                    preview_fields=preview_fields
                )

                # Convert to Schema if not preview
                if not is_preview:
                    tasks_schema = [CrawlerTaskReadSchema.model_validate(task) for task in tasks]
                else:
                    tasks_schema = tasks

                return {
                    'success': True,
                    'message': '任務查詢成功',
                    'tasks': tasks_schema
                }
        except (DatabaseOperationError, InvalidOperationError) as e:
            logger.error(f"根據爬蟲 ID 列表 {crawler_ids} 查詢任務失敗: {e}")
            return {'success': False, 'message': str(e), 'tasks': []}
        except Exception as e:
            logger.error(f"根據爬蟲 ID 列表查詢任務時發生未預期錯誤: {e}", exc_info=True)
            return {'success': False, 'message': '查詢任務時發生未預期錯誤', 'tasks': []}

    def find_tasks_by_cron_expression(self, cron_expression: str,
                                      limit: Optional[int] = None,
                                      is_preview: bool = False,
                                      preview_fields: Optional[List[str]] = None
                                      ) -> Dict:
        """根據 cron 表達式查詢任務"""
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                tasks = tasks_repo.find_tasks_by_cron_expression(
                    cron_expression=cron_expression,
                    limit=limit,
                    is_preview=is_preview,
                    preview_fields=preview_fields
                )

                # Convert to Schema if not preview
                if not is_preview:
                    tasks_schema = [CrawlerTaskReadSchema.model_validate(task) for task in tasks]
                else:
                    tasks_schema = tasks

                return {
                    'success': True,
                    'message': '任務查詢成功',
                    'tasks': tasks_schema
                }
        except ValidationError as e: # Catch cron validation error from repo
             logger.error(f"查詢 cron 表達式任務驗證失敗: {e}")
             return {'success': False, 'message': f"無效的 cron 表達式: {e}", 'tasks': []}
        except (DatabaseOperationError, InvalidOperationError) as e:
            logger.error(f"根據 cron 表達式 {cron_expression} 查詢任務失敗: {e}")
            return {'success': False, 'message': str(e), 'tasks': []}
        except Exception as e:
            logger.error(f"根據 cron 表達式查詢任務時發生未預期錯誤: {e}", exc_info=True)
            return {'success': False, 'message': '查詢任務時發生未預期錯誤', 'tasks': []}

    def find_due_tasks(self, cron_expression: str,
                       limit: Optional[int] = None,
                       is_preview: bool = False,
                       preview_fields: Optional[List[str]] = None
                       ) -> Dict:
        """查詢需要執行的任務（根據 cron 表達式和上次執行時間）"""
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                due_tasks = tasks_repo.find_due_tasks(
                    cron_expression=cron_expression,
                    limit=limit,
                    is_preview=is_preview,
                    preview_fields=preview_fields
                )

                # Convert to Schema if not preview
                if not is_preview:
                    tasks_schema = [CrawlerTaskReadSchema.model_validate(task) for task in due_tasks]
                else:
                    tasks_schema = due_tasks

                return {
                    'success': True,
                    'message': '待執行任務查詢成功',
                    'tasks': tasks_schema
                }
        except ValidationError as e: # Catch cron validation error from repo
             logger.error(f"查詢待執行任務時 cron 表達式驗證失敗: {e}")
             return {'success': False, 'message': f"無效的 cron 表達式: {e}", 'tasks': []}
        except (DatabaseOperationError, InvalidOperationError) as e:
            logger.error(f"查詢待執行任務 (cron: {cron_expression}) 失敗: {e}")
            return {'success': False, 'message': str(e), 'tasks': []}
        except Exception as e:
            logger.error(f"查詢待執行任務時發生未預期錯誤: {e}", exc_info=True)
            return {'success': False, 'message': '查詢待執行任務時發生未預期錯誤', 'tasks': []}

    def update_task_last_run(self, task_id: int, success: bool, message: Optional[str] = None) -> Dict:
        """更新任務的最後執行狀態"""
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                updated_task = tasks_repo.update_last_run(task_id, success, message)

                if updated_task:
                    session.flush()
                    session.refresh(updated_task)
                    logger.info(f"任務 ID {task_id} 最後執行狀態已更新並準備提交。")
                    task_schema = CrawlerTaskReadSchema.model_validate(updated_task)
                    return {
                        'success': True,
                        'message': '最後執行狀態更新成功',
                        'task': task_schema
                    }
                else:
                    return {'success': False, 'message': '任務不存在', 'task': None}
        except (DatabaseOperationError, InvalidOperationError) as e:
            logger.error(f"更新任務 {task_id} 最後執行狀態失敗: {e}")
            return {'success': False, 'message': str(e), 'task': None}
        except Exception as e:
            logger.error(f"更新任務 {task_id} 最後執行狀態時發生未預期錯誤: {e}", exc_info=True)
            return {'success': False, 'message': '更新最後執行狀態時發生未預期錯誤', 'task': None}

    def update_task_status(
        self,
        task_id: int,
        task_status: Optional[TaskStatus] = None,
        scrape_phase: Optional[ScrapePhase] = None,
        history_id: Optional[int] = None,
        history_data: Optional[dict] = None
    ) -> Dict:
        """更新任務狀態、階段，並可選擇性地更新歷史記錄"""
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('TaskHistory', session))

                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {'success': False, 'message': '任務不存在', 'task': None}

                update_payload = {}
                if task_status is not None:
                    update_payload['task_status'] = task_status
                if scrape_phase is not None:
                    update_payload['scrape_phase'] = scrape_phase

                # 更新任務狀態和階段
                updated_task = None
                if update_payload:
                     # 使用 repo 的 update 方法（該方法會驗證）
                    validated_payload = tasks_repo.validate_data(update_payload, SchemaType.UPDATE)
                    updated_task = tasks_repo.update(task_id, validated_payload)
                    if updated_task:
                        session.flush() # 確保 task 更新先於 history
                        session.refresh(updated_task)
                        logger.info(f"任務 ID {task_id} 狀態/階段已更新。")
                    else:
                         # 如果 update 返回 None 但 task 存在，說明沒有變化
                         logger.debug(f"任務 ID {task_id} 狀態/階段無變化。")
                         updated_task = task # 使用原始 task 繼續

                # 更新歷史記錄
                updated_history = None
                if history_id and history_data:
                    # 使用 repo 的 update 方法（該方法會驗證）
                    # 確保 end_time 正確設置
                    if 'end_time' not in history_data:
                        history_data['end_time'] = datetime.now(timezone.utc)
                    # history_repo 的 update 方法預期包含驗證
                    validated_history_payload = history_repo.validate_data(history_data, SchemaType.UPDATE)
                    updated_history_obj = history_repo.update(history_id, validated_history_payload)
                    if updated_history_obj:
                         session.flush() # 確保 history 更新也被 flush
                         session.refresh(updated_history_obj)
                         logger.info(f"任務歷史 ID {history_id} 已更新。")
                         # 可以選擇性地將更新後的 history 對象轉換為 schema
                         updated_history = CrawlerTaskHistoryReadSchema.model_validate(updated_history_obj).model_dump()
                    else:
                         logger.warning(f"更新任務歷史 ID {history_id} 失敗或無變化。")


                final_task_schema = CrawlerTaskReadSchema.model_validate(updated_task if updated_task else task)

                return {
                    'success': True,
                    'message': '任務狀態更新成功',
                    'task': final_task_schema.model_dump(),
                    'history': updated_history # 返回更新後的 history 數據 (dict) 或 None
                }

        except ValidationError as e:
            logger.error(f"更新任務 {task_id} 狀態/歷史記錄驗證失敗: {e}")
            return {'success': False, 'message': f"驗證失敗: {e}", 'task': None, 'history': None}
        except (DatabaseOperationError, InvalidOperationError) as e:
            logger.error(f"更新任務 {task_id} 狀態/歷史記錄失敗: {e}")
            return {'success': False, 'message': str(e), 'task': None, 'history': None}
        except Exception as e:
            logger.error(f"更新任務 {task_id} 狀態/歷史記錄時發生未預期錯誤: {e}", exc_info=True)
            return {'success': False, 'message': '更新任務狀態時發生未預期錯誤', 'task': None, 'history': None}

    def increment_retry_count(self, task_id: int) -> Dict:
        """增加任務重試次數"""
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {'success': False, 'message': '任務不存在', 'retry_count': None}

                # --- 新增檢查邏輯 ---
                current_retry_count = task.retry_count or 0
                max_retries = task.task_args.get('max_retries', TASK_ARGS_DEFAULT.get('max_retries', 0)) # 從 task_args 或預設值獲取

                if current_retry_count >= max_retries:
                    logger.warning(f"任務 ID {task_id} 已達到最大重試次數 ({max_retries})，無法再增加。")
                    return {
                        'success': False,
                        'message': f'已達到最大重試次數 ({max_retries})',
                        'retry_count': current_retry_count # 返回當前次數
                    }
                # --- 檢查邏輯結束 ---

                new_retry_count = current_retry_count + 1
                # 使用 repo 的 update 方法更新
                updated_task = tasks_repo.update(task_id, {'retry_count': new_retry_count})

                if updated_task:
                    session.flush()
                    session.refresh(updated_task)
                    logger.info(f"任務 ID {task_id} 重試次數已增加到 {updated_task.retry_count} 並準備提交。")
                    return {
                        'success': True,
                        'message': '重試次數增加成功',
                        'retry_count': updated_task.retry_count
                    }
                else:
                    # update 返回 None 可能是因為驗證失敗或內部錯誤
                    # 理論上如果 task 存在且檢查已通過，這裡不應返回 None
                    # 但為了健壯性，保留一個錯誤處理
                    logger.error(f"更新任務 {task_id} 重試次數後，repo.update 返回 None")
                    return {
                        'success': False,
                        'message': '更新重試次數時 Repository 未返回更新後的實例',
                        'retry_count': current_retry_count # 返回增加前的次數
                    }

        except ValidationError as e: # 捕捉來自 update 的驗證錯誤
             logger.error(f"增加任務 {task_id} 重試次數驗證失敗: {e}")
             # retry_count 在驗證失敗時應返回 None 或更新前的值
             current_retry_count = None
             try: # 嘗試獲取更新前的值
                 with self._transaction() as read_session:
                     read_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', read_session))
                     task_read = read_repo.get_by_id(task_id)
                     if task_read: current_retry_count = task_read.retry_count
             except Exception: pass # 忽略讀取錯誤
             return {'success': False, 'message': f"驗證失敗: {e}", 'retry_count': current_retry_count}
        except (DatabaseOperationError, InvalidOperationError) as e:
            logger.error(f"增加任務 {task_id} 重試次數失敗: {e}")
            # 同上，嘗試獲取更新前的值
            current_retry_count = None
            try:
                 with self._transaction() as read_session:
                     read_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', read_session))
                     task_read = read_repo.get_by_id(task_id)
                     if task_read: current_retry_count = task_read.retry_count
            except Exception: pass
            return {'success': False, 'message': str(e), 'retry_count': current_retry_count}
        except Exception as e:
            logger.error(f"增加任務 {task_id} 重試次數時發生未預期錯誤: {e}", exc_info=True)
            # 同上，嘗試獲取更新前的值
            current_retry_count = None
            try:
                 with self._transaction() as read_session:
                     read_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', read_session))
                     task_read = read_repo.get_by_id(task_id)
                     if task_read: current_retry_count = task_read.retry_count
            except Exception: pass
            return {'success': False, 'message': '增加重試次數時發生未預期錯誤', 'retry_count': current_retry_count}

    def reset_retry_count(self, task_id: int) -> Dict:
        """重置任務重試次數為 0"""
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {'success': False, 'message': '任務不存在', 'retry_count': None}

                # 只有當 retry_count 不為 0 時才更新
                if task.retry_count != 0:
                    # 使用 repo 的 update 方法更新
                    updated_task = tasks_repo.update(task_id, {'retry_count': 0})

                    if updated_task:
                        session.flush()
                        session.refresh(updated_task)
                        logger.info(f"任務 ID {task_id} 重試次數已重置為 0 並準備提交。")
                        return {
                            'success': True,
                            'message': '重試次數重置成功',
                            'retry_count': updated_task.retry_count
                        }
                    else:
                         # update 返回 None 可能是因為驗證失敗或內部錯誤
                         return {
                            'success': False, 
                            'message': '重置重試次數時 Repository 未返回更新後的實例', 
                            'retry_count': task.retry_count}
                else:
                    logger.info(f"任務 ID {task_id} 重試次數已經是 0，無需重置。")
                    return {
                        'success': True,
                        'message': '重試次數已為 0，無需重置',
                        'retry_count': 0
                    }

        except ValidationError as e: # 捕捉來自 update 的驗證錯誤
             logger.error(f"重置任務 {task_id} 重試次數驗證失敗: {e}")
             return {'success': False, 'message': f"驗證失敗: {e}", 'retry_count': None}
        except (DatabaseOperationError, InvalidOperationError) as e:
            logger.error(f"重置任務 {task_id} 重試次數失敗: {e}")
            return {'success': False, 'message': str(e), 'retry_count': None}
        except Exception as e:
            logger.error(f"重置任務 {task_id} 重試次數時發生未預期錯誤: {e}", exc_info=True)
            return {'success': False, 'message': '重置重試次數時發生未預期錯誤', 'retry_count': None}

    def update_max_retries(self, task_id: int, max_retries: int) -> Dict:
        """更新任務最大重試次數 (存儲在 task_args 中)"""
        if max_retries < 0:
             return {'success': False, 'message': 'max_retries 不能為負數', 'task': None}
        try:
            with self._transaction() as session:
                tasks_repo = cast(CrawlerTasksRepository, self._get_repository('CrawlerTask', session))
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {'success': False, 'message': '任務不存在', 'task': None}

                # 獲取當前的 task_args，如果為 None 則初始化
                current_args = task.task_args if task.task_args is not None else {}
                # 創建副本進行修改
                new_args = current_args.copy()
                new_args['max_retries'] = max_retries

                # 使用 repo 的 update 方法更新 task_args
                # update 方法會調用 validate_data，其中 validate_task_args 會驗證 task_args
                updated_task = tasks_repo.update(task_id, {'task_args': new_args})

                if updated_task:
                    session.flush()
                    session.refresh(updated_task)
                    logger.info(f"任務 ID {task_id} 的最大重試次數已更新為 {max_retries} 並準備提交。")
                    task_schema = CrawlerTaskReadSchema.model_validate(updated_task)
                    return {
                        'success': True,
                        'message': '最大重試次數更新成功',
                        'task': task_schema
                    }
                else:
                    # update 返回 None 可能是因為 task_args 驗證失敗或內部錯誤
                    # 檢查是否是因為值未變
                    if task.task_args and task.task_args.get('max_retries') == max_retries:
                        logger.info(f"任務 ID {task_id} 的最大重試次數已為 {max_retries}，無需更新。")
                        task_schema = CrawlerTaskReadSchema.model_validate(task)
                        return {
                            'success': True,
                            'message': '最大重試次數未變更',
                            'task': task_schema
                        }
                    else:
                        return {
                            'success': False, 
                            'message': '更新最大重試次數時 Repository 未返回更新後的實例', 
                            'task': None}

        except ValidationError as e: # 捕捉來自 update/validate_data 的錯誤
            logger.error(f"更新任務 {task_id} 最大重試次數驗證失敗: {e}")
            return {'success': False, 'message': f"驗證失敗: {e}", 'task': None}
        except (DatabaseOperationError, InvalidOperationError) as e:
            logger.error(f"更新任務 {task_id} 最大重試次數失敗: {e}")
            return {'success': False, 'message': str(e), 'task': None}
        except Exception as e:
            logger.error(f"更新任務 {task_id} 最大重試次數時發生未預期錯誤: {e}", exc_info=True)
            return {'success': False, 'message': '更新最大重試次數時發生未預期錯誤', 'task': None}



