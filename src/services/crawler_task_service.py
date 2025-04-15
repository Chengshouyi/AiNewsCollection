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
from src.error.errors import ValidationError
from src.utils.enum_utils import ScrapeMode, ScrapePhase, TaskStatus
from src.utils.model_utils import validate_task_args
from sqlalchemy import desc, asc
from src.services.scheduler_service import SchedulerService
from src.services.task_executor_service import TaskExecutorService

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
                                
    def _get_repositories(self) -> Tuple[CrawlerTasksRepository, CrawlersRepository, CrawlerTaskHistoryRepository]:
        """獲取相關資料庫訪問對象"""
        tasks_repo = cast(CrawlerTasksRepository, super()._get_repository('CrawlerTask'))
        crawlers_repo = cast(CrawlersRepository, super()._get_repository('Crawler'))
        history_repo = cast(CrawlerTaskHistoryRepository, super()._get_repository('TaskHistory'))
        return (tasks_repo, crawlers_repo, history_repo)
    
    def _get_articles_repository(self) -> ArticlesRepository:
        """獲取文章資料庫訪問對象"""
        return cast(ArticlesRepository, super()._get_repository('Articles'))


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
        try:
            with self._transaction():
                tasks_repo, _, _ = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'task': None
                    }
                
                # 創建任務
                task = tasks_repo.create(task_data)
                # 重新加載排程
                if task and task.is_auto:
                    return {
                        'success': True,
                        'message': '任務創建成功',
                        'task': task if task else None
                    }
                return {
                    'success': False,
                    'message': '任務創建失敗',
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
                if success:
                    return {
                        'success': success,
                        'message': '任務刪除成功' if success else '任務不存在'
                    }
                return {
                    'success': False,
                    'message': '任務刪除失敗'
                }
        except Exception as e:
            error_msg = f"刪除任務失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    def get_task_by_id(self, task_id: int, is_active: Optional[bool] = True) -> Dict:
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
                    
                task = tasks_repo.find_tasks_by_id(task_id, is_active)
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
        - ai_only: 是否只抓取AI相關文章
        - last_run_success: 上次執行是否成功
        - date_range: 上次執行時間範圍，格式為(start_date, end_date)
        - has_notes: 是否有備註
        - task_status: 任務狀態
        - scrape_phase: 爬取階段
        - cron_expression: cron表達式
        - retry_count: 重試次數 (可以是整數或範圍字典 {"min": x, "max": y})
        - max_pages: 最大頁數 (task_args)
        - save_to_csv: 是否保存到CSV (task_args)
        - scrape_mode: 抓取模式 (task_args)
        
        Returns:
            Dict: 包含搜尋結果的字典
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
                    
                # 構建查詢
                query = tasks_repo.session.query(tasks_repo.model_class)
                
                # 處理各種過濾條件
                if 'task_name' in filters and filters['task_name']:
                    query = query.filter(tasks_repo.model_class.task_name.like(f"%{filters['task_name']}%"))
                    
                if 'crawler_id' in filters and filters['crawler_id']:
                    query = query.filter(tasks_repo.model_class.crawler_id == filters['crawler_id'])
                    
                if 'is_auto' in filters:
                    query = query.filter(tasks_repo.model_class.is_auto == filters['is_auto'])
                    
                if 'is_active' in filters:
                    query = query.filter(tasks_repo.model_class.is_active == filters['is_active'])
                    
                if 'last_run_success' in filters:
                    query = query.filter(tasks_repo.model_class.last_run_success == filters['last_run_success'])
                    
                if 'date_range' in filters and filters['date_range']:
                    start_date, end_date = filters['date_range']
                    if start_date:
                        query = query.filter(tasks_repo.model_class.last_run_at >= start_date)
                    if end_date:
                        query = query.filter(tasks_repo.model_class.last_run_at <= end_date)
                        
                if 'has_notes' in filters and filters['has_notes']:
                    query = query.filter(tasks_repo.model_class.notes.isnot(None))
                    
                if 'task_status' in filters and filters['task_status']:
                    query = query.filter(tasks_repo.model_class.task_status == filters['task_status'])
                    
                if 'scrape_phase' in filters and filters['scrape_phase']:
                    query = query.filter(tasks_repo.model_class.scrape_phase == filters['scrape_phase'])
                    
                if 'cron_expression' in filters and filters['cron_expression']:
                    query = query.filter(tasks_repo.model_class.cron_expression == filters['cron_expression'])
                    
                if 'retry_count' in filters:
                    if isinstance(filters['retry_count'], dict):
                        if 'min' in filters['retry_count']:
                            query = query.filter(tasks_repo.model_class.retry_count >= filters['retry_count']['min'])
                        if 'max' in filters['retry_count']:
                            query = query.filter(tasks_repo.model_class.retry_count <= filters['retry_count']['max'])
                    else:
                        query = query.filter(tasks_repo.model_class.retry_count == filters['retry_count'])
                
                # 處理task_args中的過濾條件
                if 'ai_only' in filters:
                    query = query.filter(tasks_repo.model_class.task_args.contains({"ai_only": filters['ai_only']}))
                    
                if 'max_pages' in filters:
                    query = query.filter(tasks_repo.model_class.task_args.contains({"max_pages": filters['max_pages']}))
                    
                if 'save_to_csv' in filters:
                    query = query.filter(tasks_repo.model_class.task_args.contains({"save_to_csv": filters['save_to_csv']}))
                    
                if 'scrape_mode' in filters:
                    query = query.filter(tasks_repo.model_class.task_args.contains({"scrape_mode": filters['scrape_mode']}))
                
                # 處理排序
                if 'sort_by' in filters and filters['sort_by']:
                    sort_attr = getattr(tasks_repo.model_class, filters['sort_by'], None)
                    if sort_attr:
                        query = query.order_by(desc(sort_attr) if filters.get('sort_desc', False) else asc(sort_attr))
                else:
                    # 預設按建立時間排序
                    query = query.order_by(desc(tasks_repo.model_class.created_at))
                
                # 處理分頁
                if 'limit' in filters and filters['limit']:
                    query = query.limit(filters['limit'])
                    
                if 'offset' in filters and filters['offset']:
                    query = query.offset(filters['offset'])
                
                # 執行查詢
                tasks = query.all()
                
                return {
                    'success': True,
                    'message': '任務搜尋成功',
                    'tasks': tasks
                }
        except Exception as e:
            error_msg = f"進階搜尋任務失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'tasks': []
            }

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
            return {
                'success': False,
                'message': error_msg,
                'history': []
            }

    def get_task_status(self, task_id: int) -> Dict:
        """獲取任務的當前狀態（從歷史記錄和任務本身獲取）"""
        try:
            with self._transaction():
                tasks_repo, _, history_repo = self._get_repositories()
                if not tasks_repo or not history_repo:
                    return {
                        'task_status': TaskStatus.FAILED.value,
                        'scrape_phase': ScrapePhase.FAILED.value,
                        'progress': 0,
                        'message': '無法取得資料庫存取器',
                        'task': None,
                        'history': None
                    }
                    
                # 檢查任務是否存在
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'task_status': TaskStatus.FAILED.value,
                        'scrape_phase': ScrapePhase.FAILED.value,
                        'progress': 0,
                        'message': '任務不存在',
                        'task': None,
                        'history': None
                    }
                    
                # 從資料庫獲取最新一筆歷史記錄
                latest_history = history_repo.get_latest_history(task_id)
                
                if not latest_history or not latest_history.start_time:
                    # 沒有歷史記錄時，僅返回任務本身的狀態
                    return {
                        'task_status': task.task_status,
                        'scrape_phase': task.scrape_phase,
                        'progress': 0,
                        'message': '無執行歷史',
                        'task': task,
                        'history': None
                    }
                
                # 首先從任務狀態獲取最新的任務狀態
                task_status = task.task_status
                
                # 如果歷史記錄中有更新的任務狀態，則使用歷史記錄中的狀態
                if (latest_history.end_time and 
                    latest_history.task_status in [TaskStatus.COMPLETED.value, 
                                                  TaskStatus.FAILED.value, 
                                                  TaskStatus.CANCELLED.value]):
                    task_status = latest_history.task_status
                
                # 從任務本身獲取爬取階段信息
                scrape_phase = task.scrape_phase
                
                # 計算進度
                if latest_history.end_time:
                    progress = 100
                else:
                    # 如果正在執行中，根據開始時間計算大約進度
                    current_time = datetime.now(timezone.utc)
                    elapsed = current_time - latest_history.start_time  # start_time 已經確認不是 None
                    # 假設每個任務平均執行時間為 5 分鐘
                    progress = min(95, int((elapsed.total_seconds() / 300) * 100))
                
                return {
                    'task_status': task_status,
                    'scrape_phase': scrape_phase,
                    'progress': progress,
                    'message': latest_history.message or '',
                    'task': task,
                    'history': latest_history
                }
                
        except Exception as e:
            error_msg = f"獲取任務狀態失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'task_status': TaskStatus.FAILED.value,
                'scrape_phase': ScrapePhase.FAILED.value,
                'progress': 0,
                'message': f'獲取狀態時發生錯誤: {str(e)}',
                'task': None,
                'history': None
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
        
    def toggle_active_status(self, task_id: int) -> Dict:
        """切換任務的啟用狀態"""
        try:
            with self._transaction():
                tasks_repo, _, _ = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                    
                success = tasks_repo.toggle_active_status(task_id)
                return {
                    'success': success,
                    'message': '啟用狀態切換成功' if success else '任務不存在'
                }
        except Exception as e:
            error_msg = f"切換任務啟用狀態失敗, ID={task_id}: {str(e)}"
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

    def update_task_status(self, task_id: int, task_status: Optional[TaskStatus] = None, scrape_phase: Optional[ScrapePhase] = None, history_id: Optional[int] = None, history_data: Optional[dict] = None) -> Dict:
        """更新任務狀態
        
        Args:
            task_id: 任務ID
            task_status: 任務狀態，None表示不更新
            scrape_phase: 任務階段，None表示不更新
            history_id: 任務歷史ID
            history_data: 任務歷史資料
            
        Returns:
            更新結果
        """
        try:
            with self._transaction():
                tasks_repo, _, history_repo = self._get_repositories()
                if not tasks_repo or not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'task': None,
                        'history': None
                    }
                
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在',
                        'task': None,
                        'history': None
                    }
                
                # 準備任務更新資料
                update_data = {}
                need_update = False
                
                # 情況1: 兩者都不是None，且都需要更新
                if scrape_phase is not None and task_status is not None:
                    phase_changed = scrape_phase != task.scrape_phase
                    status_changed = task_status != task.task_status
                    
                    if phase_changed:
                        update_data['scrape_phase'] = scrape_phase
                        need_update = True
                    
                    if status_changed:
                        update_data['task_status'] = task_status
                        need_update = True
                
                # 情況2: 只有scrape_phase需要更新
                elif scrape_phase is not None and scrape_phase != task.scrape_phase:
                    update_data['scrape_phase'] = scrape_phase
                    need_update = True
                
                # 情況3: 只有task_status需要更新
                elif task_status is not None and task_status != task.task_status:
                    update_data['task_status'] = task_status
                    need_update = True
                
                # 情況4: 兩者都是None或沒有變化，不需要更新
                
                # 執行任務狀態更新
                if need_update:
                    task_result = tasks_repo.update(task_id, update_data)
                else:
                    task_result = task
                
                # 處理歷史記錄
                history_result = None
                if history_data:
                    if not history_id:
                        # 先驗證歷史記錄資料
                        validated_history_data = self.validate_data('TaskHistory', history_data, SchemaType.CREATE)
                        history_result = history_repo.create(validated_history_data)
                        history_id = history_result.id if history_result else None
                    else:
                        # 更新歷史記錄資料
                        validated_history_data = self.validate_data('TaskHistory', history_data, SchemaType.UPDATE)
                        history_result = history_repo.update(history_id, validated_history_data)

                # 更新內部任務狀態記錄
                self.task_execution_status[task_id] = {
                    'task_status': task_status,
                    'scrape_phase': scrape_phase
                }
                
                # 準備日誌訊息和返回訊息
                status_msg = f"狀態未更新"
                phase_msg = f"階段未更新"
                
                if task_status is not None:
                    status_msg = f"任務狀態更新為 {task_status.value}"
                
                if scrape_phase is not None:
                    phase_msg = f"爬取階段更新為 {scrape_phase.value}"
                
                # 記錄日誌
                if need_update:
                    logger.info(f"任務 {task_id} {phase_msg}, {status_msg}")
                
                return {
                    'success': True,
                    'message': f"{phase_msg}, {status_msg}",
                    'task': task_result,
                    'history': history_result,
                    'updated': need_update
                }
        except Exception as e:
            error_msg = f"更新任務階段失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'task': None,
                'history': None
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
                
                # 獲取最大重試次數
                max_retries = task.task_args.get('max_retries', 0)
                
                # 如果最大重試次數為0，表示不允許重試
                if max_retries <= 0:
                    return {
                        'success': False,
                        'message': '任務設定為不允許重試（最大重試次數為0）',
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
                result = tasks_repo.update(task_id, task_data)
                
                # 檢查是否達到最大重試次數
                has_reached_max = current_retry >= max_retries
                
                return {
                    'success': True,
                    'message': f'重試次數更新為 {current_retry}/{max_retries}',
                    'retry_count': current_retry,
                    'max_retries': max_retries,
                    'exceeded_max_retries': has_reached_max,
                    'task': result
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
                'message': error_msg,
                'task': None
            }

    def update_max_retries(self, task_id: int, max_retries: int) -> Dict:
        """更新任務最大重試次數
        
        Args:
            task_id: 任務ID
            max_retries: 最大重試次數
            
        Returns:
            更新結果
        """
        # 檢查數值範圍
        if max_retries < 0:
            return {
                'success': False,
                'message': '最大重試次數不能小於 0'
            }
        
        # 定義合理的上限值，避免設置過大數值
        MAX_ALLOWED_RETRIES = 50
        if max_retries > MAX_ALLOWED_RETRIES:
            return {
                'success': False,
                'message': f'最大重試次數不能超過 {MAX_ALLOWED_RETRIES}'
            }
        
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
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在',
                        'task': None
                    }
                
                # 更新最大重試次數
                task_args = task.task_args.copy()
                task_args['max_retries'] = max_retries
                task_data = {'task_args': task_args}
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
                'message': error_msg,
                'task': None
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
                retryable_tasks = [task for task in failed_tasks if task.retry_count < task.task_args.get('max_retries', 0)]
                
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



