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
                return {
                    'success': True,
                    'message': '任務創建成功',
                    'task': task if task else None
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
                return {
                    'success': success,
                    'message': '任務刪除成功' if success else '任務不存在'
                }
        except Exception as e:
            error_msg = f"刪除任務失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
    
    def get_task_by_id(self, task_id: int, is_active: bool = True) -> Dict:
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

    def fetch_full_article(self, task_id: int) -> Dict[str, Any]:
        """執行任務
            使用情境：
                1. 手動任務：當使用者手動選擇要執行的任務時，會使用此方法
                2. 自動任務：當任務執行時，會使用此方法

        Args:
            task_id: 任務ID
            
        Returns:
            Dict[str, Any]: 執行結果
        """
        try:
            with self._transaction():
                tasks_repo, crawlers_repo, history_repo = self._get_repositories()
                if not tasks_repo or not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'task': None,
                        'history': None
                    }
                
                # 檢查任務是否存在
                task = tasks_repo.find_tasks_by_id(task_id, is_active=True)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在',
                        'task': None,
                        'history': None
                    }
                
                # 檢查任務是否已在執行中
                if task.task_status == TaskStatus.RUNNING.value:
                    return {
                        'success': False,
                        'message': '任務已在執行中',
                        'task': task,
                        'history': None
                    }
                
                # 檢查是否有運行中的爬蟲實例
                if task_id in self.running_crawlers:
                    return {
                        'success': False,
                        'message': '任務已有運行中的爬蟲實例',
                        'task': task,
                        'history': None
                    }
                
                # 創建任務歷史記錄
                history_data = {
                    'task_id': task_id,
                    'start_time': datetime.now(timezone.utc),
                    'task_status': TaskStatus.RUNNING.value,
                    'message': '任務開始執行'
                }
                update_task_status_result = self.update_task_status(task_id, TaskStatus.RUNNING, ScrapePhase.INIT, history_data=history_data)
                if not update_task_status_result.get('success', False):
                    return update_task_status_result
            
                history_id = update_task_status_result.get('history', {}).id if update_task_status_result.get('history') else None
                
                try:
                    
                    # 獲取爬蟲資訊
                    crawler = crawlers_repo.find_by_crawler_id(task.crawler_id, is_active=True)
                    if not crawler:
                        history_data = {
                            'end_time': datetime.now(timezone.utc),
                            'task_status': TaskStatus.FAILED.value,
                            'message': '任務未關聯有效的爬蟲'
                        }
                        update_task_status_result = self.update_task_status(task_id, TaskStatus.FAILED, ScrapePhase.INIT, history_id=history_id, history_data=history_data)
                        if not update_task_status_result.get('success', False):
                            return update_task_status_result
                        return {
                            'success': False,
                            'message': '任務未關聯有效的爬蟲',
                            'task': None,
                            'history': None
                        }
                    
                    # 創建爬蟲實例
                    crawler_instance = self._get_crawler_instance(crawler.crawler_name, task_id)

                    if not crawler_instance:
                        history_data = {
                            'end_time': datetime.now(timezone.utc),
                            'task_status': TaskStatus.FAILED.value,
                            'message': '無法創建爬蟲實例'
                        }
                        update_task_status_result = self.update_task_status(task_id, TaskStatus.FAILED, ScrapePhase.INIT, history_id=history_id, history_data=history_data)
                        if not update_task_status_result.get('success', False):
                            return update_task_status_result
                        return {
                            'success': False,
                            'message': '無法創建爬蟲實例',
                            'task': None,
                            'history': None
                        }
                        
                    task.task_args['scrape_mode'] = ScrapeMode.FULL_SCRAPE.value
                    result = crawler_instance.execute_task(task_id, task.task_args)

                    # 更新任務歷史記錄
                    history_data = {
                        'end_time': datetime.now(timezone.utc),
                        'task_status': TaskStatus.COMPLETED.value if result.get('success', False) else TaskStatus.FAILED.value,
                        'message': result.get('message', '任務執行完成'),
                        'articles_count': result.get('articles_count', 0)
                    }

                    self.update_task_status(task_id, TaskStatus.COMPLETED if result.get('success', False) else TaskStatus.FAILED, ScrapePhase.COMPLETED if result.get('success', False) else ScrapePhase.FAILED, history_id=history_id, history_data=history_data)
                    
                    # 更新任務階段為完成
                    if result.get('success', False):
                        # 成功執行後重置重試次數
                        self.reset_retry_count(task_id)
                    
                    # 更新任務最後執行狀態
                    tasks_repo.update_last_run(
                        task_id, 
                        result.get('success', False), 
                        result.get('message', '任務執行完成' if result.get('success', False) else '任務執行失敗')
                    )
                    
                    return result
                except Exception as e:
                    # 更新任務歷史記錄
                    history_data = {
                        'end_time': datetime.now(timezone.utc),
                        'task_status': TaskStatus.FAILED.value,
                        'message': f'任務執行失敗: {str(e)}'
                    }
                    self.update_task_status(task_id, TaskStatus.FAILED, ScrapePhase.FAILED, history_id=history_id, history_data=history_data)
                    
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
            history_data = {
                'end_time': datetime.now(timezone.utc),
                'task_status': TaskStatus.FAILED.value,
                'message': f'任務執行失敗: {str(e)}'
            }
            self.update_task_status(task_id, TaskStatus.FAILED, ScrapePhase.FAILED, history_data=history_data)
            return {
                'success': False,
                'message': error_msg
            }
        finally:
            # 釋放爬蟲資源
            self.cleanup_crawler_instance(task_id)

    def collect_links_only(self, task_id: int) -> Dict[str, Any]:
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
                tasks_repo, crawlers_repo, history_repo = self._get_repositories()
                if not tasks_repo or not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'task': None,
                        'history': None
                    }
                
                # 檢查任務是否存在
                task = tasks_repo.find_tasks_by_id(task_id, is_active=True)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在',
                        'task': None,
                        'history': None
                    }
                
                # 檢查任務是否已在執行中
                if task.task_status == TaskStatus.RUNNING.value:
                    return {
                        'success': False,
                        'message': '任務已在執行中',
                        'task': task,
                        'history': None
                    }
                
                # 檢查是否有運行中的爬蟲實例
                if task_id in self.running_crawlers:
                    return {
                        'success': False,
                        'message': '任務已有運行中的爬蟲實例',
                        'task': task,
                        'history': None
                    }
                
                # 創建任務歷史記錄
                history_data = {
                    'task_id': task_id,
                    'start_time': datetime.now(timezone.utc),
                    'task_status': TaskStatus.RUNNING.value,
                    'message': '開始收集文章連結'
                }
                update_task_status_result = self.update_task_status(task_id, TaskStatus.RUNNING, ScrapePhase.LINK_COLLECTION, history_data=history_data)
                if not update_task_status_result.get('success', False):
                    return update_task_status_result
                
                # 安全地獲取歷史記錄和ID
                history = update_task_status_result.get('history')
                history_id = history.id if history else None
                
                try:
                    # 獲取爬蟲資訊
                    crawler = crawlers_repo.find_by_crawler_id(task.crawler_id, is_active=True)
                    if not crawler:
                        history_data = {
                            'end_time': datetime.now(timezone.utc),
                            'task_status': TaskStatus.FAILED.value,
                            'message': '任務未關聯有效的爬蟲'
                        }
                        update_task_status_result = self.update_task_status(task_id, TaskStatus.FAILED, ScrapePhase.LINK_COLLECTION, history_id=history_id, history_data=history_data)
                        if not update_task_status_result.get('success', False):
                            return update_task_status_result
                        return {
                            'success': False,
                            'message': '任務未關聯有效的爬蟲',
                            'task': None,
                            'history': None
                        }
                    
                    # 創建爬蟲實例
                    crawler_instance = self._get_crawler_instance(crawler.crawler_name, task_id)
                    
                    if not crawler_instance:
                        history_data = {
                            'end_time': datetime.now(timezone.utc),
                            'task_status': TaskStatus.FAILED.value,
                            'message': '無法創建爬蟲實例'
                        }
                        update_task_status_result = self.update_task_status(task_id, TaskStatus.FAILED, ScrapePhase.LINK_COLLECTION, history_id=history_id, history_data=history_data)
                        if not update_task_status_result.get('success', False):
                            return update_task_status_result
                        return {
                            'success': False,
                            'message': '無法創建爬蟲實例',
                            'task': None,
                            'history': None
                        }
                    
                    # 獲取文章儲存庫
                    article_repo = self._get_articles_repository()
                    
                    # 獲取該任務ID下最初的文章數量作為基準
                    initial_count = article_repo.count_articles_by_task_id(task_id)
                    
                    # 執行爬蟲
                    task.task_args['scrape_mode'] = ScrapeMode.LINKS_ONLY.value
                    result = crawler_instance.execute_task(task_id, task.task_args)
                    
                    # 獲取新增的文章數量 - 使用task_id作為過濾條件
                    new_count = article_repo.count_articles_by_task_id(task_id)
                    links_found = new_count - initial_count
                    
                    # 獲取新增的文章 - 使用task_id作為過濾條件
                    newly_added_articles = article_repo.find_articles_by_task_id(
                        task_id=task_id,
                        is_scraped=False,
                        limit=links_found
                    )
                    newly_added_links = [article.link for article in newly_added_articles]
                    
                    # 更新任務歷史記錄
                    history_data = {
                        'end_time': datetime.now(timezone.utc),
                        'task_status': TaskStatus.COMPLETED.value if result.get('success', False) else TaskStatus.FAILED.value,
                        'message': f'文章連結收集完成，共收集 {links_found} 個連結',
                        'articles_count': links_found  # 更新收集到的文章數量
                    }

                    self.update_task_status(task_id, TaskStatus.COMPLETED if result.get('success', False) else TaskStatus.FAILED, ScrapePhase.COMPLETED if result.get('success', False) else ScrapePhase.FAILED, history_id=history_id, history_data=history_data)
                    
                    # 成功執行後重置重試次數
                    if result.get('success', False):
                        self.reset_retry_count(task_id)
                    
                    # 更新任務最後執行狀態
                    tasks_repo.update_last_run(
                        task_id, 
                        True, 
                        f'文章連結收集完成，共收集 {links_found} 個連結'
                    )
                    
                    return {
                        'success': True,
                        'message': f'文章連結收集完成，共收集 {links_found} 個連結',
                        'task': task,
                        'history': history,
                        'links_found': links_found,
                        'article_links': newly_added_links
                    }
                except Exception as e:
                    # 更新任務歷史記錄
                    history_data = {
                        'end_time': datetime.now(timezone.utc),
                        'task_status': TaskStatus.FAILED.value,
                        'message': f'文章連結收集失敗: {str(e)}'
                    }
                    self.update_task_status(task_id, TaskStatus.FAILED, ScrapePhase.FAILED, history_id=history_id, history_data=history_data)
                    
                    # 增加重試次數
                    retry_result = self.increment_retry_count(task_id)
                    
                    # 更新任務最後執行狀態
                    tasks_repo.update_last_run(task_id, False, f'文章連結收集失敗: {str(e)}')
                    
                    return {
                        'success': False,
                        'message': f'文章連結收集失敗: {str(e)}',
                        'retry_info': retry_result,
                        'task': None,
                        'history': None
                    }
        except Exception as e:
            error_msg = f"收集文章連結失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            history_data = {
                'end_time': datetime.now(timezone.utc),
                'task_status': TaskStatus.FAILED.value,
                'message': f'文章連結收集失敗: {str(e)}'
            }
            self.update_task_status(task_id, TaskStatus.FAILED, ScrapePhase.FAILED, history_data=history_data)
            return {
                'success': False,
                'message': error_msg,
                'task': None,
                'history': None
            }
        finally:
            # 釋放爬蟲資源
            self.cleanup_crawler_instance(task_id)

    def fetch_content_only(self, task_id: int) -> Dict[str, Any]:
        """ 抓取文章內容，並更新文章內容
            使用情境：
                1. 手動任務：當使用者手動選擇要抓取的文章時，會使用此方法
                2. 自動任務：當任務執行時，會使用此方法

        Args:
            task_id: 任務ID
            
        Returns:
            Dict[str, Any]: 執行結果
        """
        try:
            with self._transaction():
                tasks_repo, crawlers_repo, history_repo = self._get_repositories()
                if not tasks_repo or not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'task': None,
                        'history': None
                    }
                
                # 檢查任務是否存在
                task = tasks_repo.find_tasks_by_id(task_id, is_active=True)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在',
                        'task': None,
                        'history': None
                    }
                
                # 檢查任務是否已在執行中
                if task.task_status == TaskStatus.RUNNING.value:
                    return {
                        'success': False,
                        'message': '任務已在執行中',
                        'task': task,
                        'history': None
                    }
                
                # 檢查是否有運行中的爬蟲實例
                if task_id in self.running_crawlers:
                    return {
                        'success': False,
                        'message': '任務已有運行中的爬蟲實例',
                        'task': task,
                        'history': None
                    }
                
                # 創建任務歷史記錄
                history_data = {
                    'task_id': task_id,
                    'start_time': datetime.now(timezone.utc),
                    'task_status': TaskStatus.RUNNING.value,
                    'message': '開始抓取文章內容'
                }
                update_task_status_result = self.update_task_status(task_id, TaskStatus.RUNNING, ScrapePhase.CONTENT_SCRAPING, history_data=history_data)
                if not update_task_status_result.get('success', False):
                    return update_task_status_result
                
                # 安全地獲取歷史記錄和ID
                history = update_task_status_result.get('history')
                history_id = history.id if history else None
                
                try:
                    # 獲取爬蟲資訊
                    crawler = crawlers_repo.find_by_crawler_id(task.crawler_id, is_active=True)
                    if not crawler:
                        history_data = {
                            'end_time': datetime.now(timezone.utc),
                            'task_status': TaskStatus.FAILED.value,
                            'message': '任務未關聯有效的爬蟲'
                        }
                        update_task_status_result = self.update_task_status(task_id, TaskStatus.FAILED, ScrapePhase.CONTENT_SCRAPING, history_id=history_id, history_data=history_data)
                        if not update_task_status_result.get('success', False):
                            return update_task_status_result
                        return {
                            'success': False,
                            'message': '任務未關聯有效的爬蟲',
                            'task': None,
                            'history': None
                        }
                    
                    # 創建爬蟲實例
                    crawler_instance = self._get_crawler_instance(crawler.crawler_name, task_id)
                    
                    if not crawler_instance:
                        history_data = {
                            'end_time': datetime.now(timezone.utc),
                            'task_status': TaskStatus.FAILED.value,
                            'message': '無法創建爬蟲實例'
                        }
                        update_task_status_result = self.update_task_status(task_id, TaskStatus.FAILED, ScrapePhase.CONTENT_SCRAPING, history_id=history_id, history_data=history_data)
                        if not update_task_status_result.get('success', False):
                            return update_task_status_result
                        return {
                            'success': False,
                            'message': '無法創建爬蟲實例',
                            'task': None,
                            'history': None
                        }
                    
                    # 執行爬蟲
                    task.task_args['scrape_mode'] = ScrapeMode.CONTENT_ONLY.value
                    result = crawler_instance.execute_task(task_id, task.task_args)
                    
                    # 更新任務歷史記錄
                    history_data = {
                        'end_time': datetime.now(timezone.utc),
                        'task_status': TaskStatus.COMPLETED.value if result.get('success', False) else TaskStatus.FAILED.value,
                        'message': result.get('message', '文章內容抓取完成'),
                        'articles_count': result.get('articles_count', 0)
                    }

                    self.update_task_status(task_id, TaskStatus.COMPLETED if result.get('success', False) else TaskStatus.FAILED, ScrapePhase.COMPLETED if result.get('success', False) else ScrapePhase.FAILED, history_id=history_id, history_data=history_data)
                    
                    # 成功執行後重置重試次數
                    if result.get('success', False):
                        self.reset_retry_count(task_id)
                    
                    # 更新任務最後執行狀態
                    tasks_repo.update_last_run(
                        task_id, 
                        result.get('success', False), 
                        result.get('message', '文章內容抓取完成' if result.get('success', False) else '文章內容抓取失敗')
                    )
                    
                    return {
                        'success': result.get('success', False),
                        'message': result.get('message', '文章內容抓取完成' if result.get('success', False) else '文章內容抓取失敗'),
                        'task': task,
                        'history': history,
                        'articles_count': result.get('articles_count', 0)
                    }
                except Exception as e:
                    # 更新任務歷史記錄
                    history_data = {
                        'end_time': datetime.now(timezone.utc),
                        'task_status': TaskStatus.FAILED.value,
                        'message': f'文章內容抓取失敗: {str(e)}'
                    }
                    self.update_task_status(task_id, TaskStatus.FAILED, ScrapePhase.FAILED, history_id=history_id, history_data=history_data)
                    
                    # 增加重試次數
                    retry_result = self.increment_retry_count(task_id)
                    
                    # 更新任務最後執行狀態
                    tasks_repo.update_last_run(task_id, False, f'文章內容抓取失敗: {str(e)}')
                    
                    return {
                        'success': False,
                        'message': f'文章內容抓取失敗: {str(e)}',
                        'retry_info': retry_result,
                        'task': task,
                        'history': history
                    }
        except Exception as e:
            error_msg = f"抓取文章內容失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            history_data = {
                'end_time': datetime.now(timezone.utc),
                'task_status': TaskStatus.FAILED.value,
                'message': f'文章內容抓取失敗: {str(e)}'
            }
            self.update_task_status(task_id, TaskStatus.FAILED, ScrapePhase.FAILED, history_data=history_data)
            return {
                'success': False,
                'message': error_msg,
                'task': None,
                'history': None
            }
        finally:
            # 釋放爬蟲資源
            self.cleanup_crawler_instance(task_id)

    def cancel_task(self, task_id: int) -> Dict[str, Any]:
        """取消正在執行的爬蟲任務
        
        Args:
            task_id: 要取消的任務ID
            
        Returns:
            Dict[str, Any]: 操作結果
        """
        try:
            with self._transaction():
                # 取得任務資訊
                tasks_repo, _, history_repo = self._get_repositories()
                if not tasks_repo or not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'task': None,
                        'history': None
                    }
                
                # 直接從資料庫獲取任務狀態，避免通過歷史記錄間接獲取
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'success': False,
                        'message': f"找不到ID為 {task_id} 的任務",
                        'task': None,
                        'history': None
                    }
                
                # 檢查爬蟲實例是否存在 - 提前檢查以避免不必要的狀態修改
                if task_id not in self.running_crawlers:
                    return {
                        'success': False,
                        'message': f"任務 {task_id} 沒有對應的運行中爬蟲實例",
                        'task': task,
                        'history': None
                    }
                    
                # 預先檢查任務是否可以取消 - 可接受更多狀態
                # 不只限於RUNNING狀態，CANCELING也是可以再次嘗試取消的有效狀態
                if task.task_status not in [TaskStatus.RUNNING.value, TaskStatus.CANCELING.value]:
                    task_status_msg = task.task_status
                    return {
                        'success': False,
                        'message': f"任務 {task_id} 當前狀態為 {task_status_msg}，無法取消",
                        'task': task,
                        'history': None
                    }
                
                # 創建任務歷史記錄
                history_data = {
                    'task_id': task_id,
                    'start_time': datetime.now(timezone.utc),
                    'task_status': TaskStatus.CANCELING.value,
                    'message': '開始取消任務'
                }
                
                # 直接更新任務狀態，避免觸發狀態檢查邏輯
                task_data = {'task_status': TaskStatus.CANCELING.value}
                task = tasks_repo.update(task_id, task_data)
                
                # 創建歷史記錄
                validated_history_data = self.validate_data('TaskHistory', history_data, SchemaType.CREATE)
                history = history_repo.create(validated_history_data)
                history_id = history.id if history else None
                
                try:
                    # 取得爬蟲實例並呼叫取消方法
                    crawler = self.running_crawlers[task_id]
                    
                    # 確保任務存在且task_args可訪問
                    task_args = getattr(task, 'task_args', {})
                    
                    # 配置任務的取消參數 - 使其支援新的部分數據保存功能
                    # 根據任務的設定決定是否保存部分結果
                    save_partial_results = task_args.get('save_partial_results_on_cancel', False)
                    save_partial_to_database = task_args.get('save_partial_to_database', False)
                    
                    # 更新全局參數以支持取消時的數據處理
                    crawler.global_params['save_partial_results_on_cancel'] = save_partial_results
                    crawler.global_params['save_partial_to_database'] = save_partial_to_database
                    
                    # 呼叫取消方法
                    cancelled = crawler.cancel_task(task_id)

                    if not cancelled:
                        # 更新任務歷史記錄
                        history_data = {
                            'end_time': datetime.now(timezone.utc),
                            'task_status': TaskStatus.FAILED.value,
                            'message': '無法取消任務'
                        }
                        # 驗證歷史記錄更新資料
                        validated_history_data = self.validate_data('TaskHistory', history_data, SchemaType.UPDATE)
                        # 更新歷史記錄
                        history_repo.update(history_id, validated_history_data)
                        
                        # 恢復任務狀態
                        task_data = {'task_status': TaskStatus.RUNNING.value}
                        task = tasks_repo.update(task_id, task_data)
                        
                        return {
                            'success': False,
                            'message': f"無法取消任務 {task_id}",
                            'task': task,
                            'history': history
                        }
                    
                    # 獲取任務取消後的狀態（包含部分數據保存信息）
                    crawler_scrape_phase = crawler.get_scrape_phase(task_id)
                    
                    # 準備消息
                    cancel_message = crawler_scrape_phase.get('message', '任務已被使用者取消')
                    if crawler_scrape_phase.get('cancelled_but_saved_partial', False):
                        partial_saved_count = crawler_scrape_phase.get('partial_saved_count', 0)
                        cancel_message += f"，已保存 {partial_saved_count} 篇部分完成的文章"
                    
                    # 更新任務歷史記錄
                    history_data = {
                        'end_time': datetime.now(timezone.utc),
                        'task_status': TaskStatus.CANCELLED.value,
                        'message': cancel_message
                    }
                    
                    # 如果有部分數據被保存，記錄到歷史記錄中
                    if crawler_scrape_phase.get('cancelled_but_saved_partial', False):
                        partial_saved_count = crawler_scrape_phase.get('partial_saved_count', 0)
                        history_data['articles_count'] = partial_saved_count
                    
                    # 驗證歷史記錄更新資料
                    validated_history_data = self.validate_data('TaskHistory', history_data, SchemaType.UPDATE)
                    # 更新歷史記錄
                    history_repo.update(history_id, validated_history_data)
                    
                    # 直接更新任務狀態為已取消
                    task_data = {
                        'task_status': TaskStatus.CANCELLED.value,
                        'scrape_phase': ScrapePhase.CANCELLED.value
                    }
                    task = tasks_repo.update(task_id, task_data)
                    
                    # 重置重試次數
                    self.reset_retry_count(task_id)

                    # 更新任務最後執行狀態
                    tasks_repo.update_last_run(
                        task_id, 
                        False, 
                        cancel_message
                    )
                    
                    # 增加延遲，確保資源清理完成
                    time.sleep(0.5)
                    
                    # 構建返回結果
                    result = {
                        'success': True,
                        'message': f"任務 {task_id} 已成功取消",
                        'task': task,
                        'history': history,
                        'scrape_phase': crawler_scrape_phase
                    }
                    
                    # 如果有部分數據被保存，添加到結果中
                    if 'partial_data_saved' in crawler_scrape_phase and crawler_scrape_phase['partial_data_saved']:
                        result['partial_data_saved'] = True
                        result['partial_saved_info'] = {
                            'count': crawler_scrape_phase.get('partial_saved_count', 0),
                            'saved_to_csv': save_partial_results,
                            'saved_to_database': save_partial_to_database
                        }
                    
                    return result
                    
                except Exception as e:
                    # 更新任務歷史記錄
                    history_data = {
                        'end_time': datetime.now(timezone.utc),
                        'task_status': TaskStatus.FAILED.value,
                        'message': f'取消任務失敗: {str(e)}'
                    }
                    # 驗證歷史記錄更新資料
                    validated_history_data = self.validate_data('TaskHistory', history_data, SchemaType.UPDATE)
                    # 更新歷史記錄
                    history_repo.update(history_id, validated_history_data)
                    
                    # 恢復任務狀態
                    task_data = {'task_status': TaskStatus.RUNNING.value}
                    task = tasks_repo.update(task_id, task_data)
                    
                    # 更新任務最後執行狀態
                    tasks_repo.update_last_run(task_id, False, f'取消任務失敗: {str(e)}')
                    
                    logger.error(f"取消任務失敗 (ID={task_id}): {str(e)}", exc_info=True)
                    return {
                        'success': False,
                        'message': f'取消任務失敗: {str(e)}',
                        'task': task,
                        'history': history
                    }
        except Exception as e:
            error_msg = f"取消任務失敗 (ID={task_id}): {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'task': None,
                'history': None
            }
        finally:
            # 釋放爬蟲資源
            self.cleanup_crawler_instance(task_id)

    def test_crawler(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """測試爬蟲任務
        
        Args:
            data: 任務資料
            
        Returns:
            Dict[str, Any]: 測試結果
        """
        try:
            with self._transaction():
                # 驗證爬蟲配置和任務資料
                tasks_repo, crawlers_repo, history_repo = self._get_repositories()
                if not tasks_repo or not crawlers_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'errors': '無法取得資料庫存取器',
                        'scrape_phase': ScrapePhase.INIT.value,
                        'test_results': None,
                        'crawler': None
                    }
                
                # 查詢爬蟲資料
                crawler_id = data.get('crawler_id')
                if not crawler_id:
                    logger.error("未提供爬蟲ID")
                    return {
                        'success': False,
                        'message': '未提供爬蟲ID',
                        'errors': '未提供爬蟲ID',
                        'scrape_phase': ScrapePhase.INIT.value,
                        'test_results': None,
                        'crawler': None
                    }
                
                try:
                    crawler = crawlers_repo.find_by_crawler_id(crawler_id, is_active=True)
                    if not crawler:
                        logger.error("爬蟲不存在")
                        return {
                            'success': False,
                            'message': '爬蟲不存在',
                            'errors': '爬蟲不存在',
                            'scrape_phase': ScrapePhase.INIT.value,
                            'test_results': None,
                            'crawler': crawler
                        }
                except ValidationError as e:
                    logger.error(f"爬蟲搜尋失敗: {str(e)}")
                    return {
                        'success': False,
                        'message': '爬蟲搜尋失敗',
                        'errors': str(e),
                        'scrape_phase': ScrapePhase.INIT.value,
                        'test_results': None,
                        'crawler': crawler
                    }
                
                try:
                    # 驗證任務資料
                    validated_data = self.validate_data('CrawlerTask', data, SchemaType.CREATE)
                except ValidationError as e:
                    logger.error(f"任務資料驗證失敗: {str(e)}")
                    return {
                        'success': False,
                        'message': '任務資料驗證失敗',
                        'errors': str(e),
                        'scrape_phase': ScrapePhase.INIT.value,
                        'test_results': None,
                        'crawler': crawler
                    }
                
                # 設定階段為初始階段
                validated_data['scrape_phase'] = ScrapePhase.INIT.value
                
                try:
                    # 從爬蟲資料中獲取爬蟲名稱
                    crawler_name = crawler.crawler_name
                    if not crawler_name:
                        logger.error("未提供爬蟲名稱")
                        return {
                            'success': False,
                            'message': '未提供爬蟲名稱',
                            'errors': '未提供爬蟲名稱',
                            'scrape_phase': ScrapePhase.INIT.value,
                            'test_results': None,
                            'crawler': crawler
                        }
                    
                    # 測試爬蟲是否能成功初始化
                    try:
                        crawler_instance = self._get_crawler_instance(crawler_name, 0)
                        if not crawler_instance:
                            logger.error("爬蟲初始化失敗")
                            return {
                                'success': False,
                                'message': '爬蟲初始化失敗',
                                'errors': '爬蟲初始化失敗',
                                'scrape_phase': ScrapePhase.INIT.value,
                                'test_results': None,
                                'crawler': crawler
                            }
                    except ValueError as e:
                        logger.error(f"爬蟲初始化失敗: {str(e)}")
                        return {
                            'success': False,
                            'message': '爬蟲初始化失敗',
                            'errors': str(e),
                            'scrape_phase': ScrapePhase.INIT.value,
                            'test_results': None,
                            'crawler': crawler
                        }

                    # 準備測試參數 (只收集連結，不抓取內容)
                    test_args = validated_data.get('task_args', TASK_ARGS_DEFAULT).copy()
                    # 預防設置錯誤，強制設定測試參數
                    test_args['scrape_mode'] = ScrapeMode.LINKS_ONLY.value
                    test_args['ai_only'] = validated_data.get('ai_only', False)
                    test_args['is_test'] = True
                    test_args['max_pages'] = min(1, test_args.get('max_pages', 1))
                    test_args['num_articles'] = min(5, test_args.get('num_articles', 5))
                    test_args['save_to_csv'] = False
                    test_args['save_to_database'] = False
                    test_args['timeout'] = 30
                    logger.info(f"測試參數: {test_args}")
                    
                    # 執行爬蟲測試，收集連結
                    start_time = datetime.now(timezone.utc)
                    try:
                        # 使用跨平台的超時處理
                        import platform
                        import threading
                        
                        # 定義超時異常
                        class TimeoutException(Exception):
                            pass
                        
                        # 創建超時標誌和結果容器
                        execution_result = {
                            'completed': False,
                            'result': None,
                            'error': None
                        }
                        
                        # 定義執行函數
                        def execute_with_timeout():
                            try:
                                result = crawler_instance.execute_task(0, test_args)
                                execution_result['result'] = result
                                execution_result['completed'] = True
                            except Exception as e:
                                execution_result['error'] = e
                                execution_result['completed'] = True
                        
                        # 創建執行線程
                        thread = threading.Thread(target=execute_with_timeout)
                        thread.daemon = True
                        thread.start()
                        
                        # 等待完成或超時
                        thread.join(timeout=test_args['timeout'])
                        
                        # 檢查結果
                        if not execution_result['completed']:
                            raise TimeoutException("爬蟲測試超時")
                        
                        if execution_result['error']:
                            raise execution_result['error']
                            
                        # 獲取結果
                        result = execution_result['result']
                        logger.info(f"爬蟲測試結果: {result}")
                        
                        # 處理結果
                        end_time = datetime.now(timezone.utc)
                        execution_time = (end_time - start_time).total_seconds()
                        
                        if result.get('success', False):
                            links_found = result.get('articles_count', 0)
                            
                            return {
                                'success': True,
                                'message': f'爬蟲測試成功，執行時間: {execution_time:.2f}秒',
                                'errors': None,
                                'test_results': {
                                    'links_found': links_found,
                                    'execution_time': execution_time,
                                    'crawler_result': result
                                },
                                'scrape_phase': ScrapePhase.LINK_COLLECTION.value,
                                'crawler': crawler
                            }
                        else:
                            # 爬蟲執行失敗
                            error_message = result.get('message', '未知錯誤')
                            logger.error(f"爬蟲測試失敗: {error_message}")
                            return {
                                'success': False,
                                'message': f'爬蟲測試失敗: {error_message}',
                                'errors': error_message,
                                'scrape_phase': ScrapePhase.INIT.value,
                                'test_results': {
                                    'execution_time': execution_time,
                                    'crawler_result': result
                                },
                                'crawler': crawler
                            }
                    except TimeoutException:
                        logger.error("爬蟲測試超時")
                        end_time = datetime.now(timezone.utc)
                        execution_time = (end_time - start_time).total_seconds()
                        return {
                            'success': False,
                            'message': '爬蟲測試超時，請檢查爬蟲配置或網站狀態',
                            'errors': '爬蟲測試超時',
                            'scrape_phase': ScrapePhase.INIT.value,
                            'test_results': {
                                'execution_time': execution_time
                            },
                            'crawler': crawler
                        }
                    except Exception as e:
                        # 爬蟲執行出錯
                        logger.error(f"爬蟲測試執行異常: {str(e)}")
                        end_time = datetime.now(timezone.utc)
                        execution_time = (end_time - start_time).total_seconds()
                        return {
                            'success': False,
                            'message': f'爬蟲測試執行異常: {str(e)}',
                            'scrape_phase': ScrapePhase.INIT.value,
                            'errors': str(e),
                            'test_results': {
                                'execution_time': execution_time
                            },
                            'crawler': crawler
                        }
                except Exception as e:
                    # 測試爬蟲連結收集失敗
                    logger.error(f"爬蟲連結收集測試失敗: {str(e)}")
                    return {
                        'success': False,
                        'message': f'爬蟲連結收集測試失敗: {str(e)}',
                        'scrape_phase': ScrapePhase.INIT.value,
                        'errors': str(e),
                        'test_results': None,
                        'crawler': crawler
                    }
        except Exception as e:
            error_msg = f"爬蟲測試失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'errors': str(e),
                'scrape_phase': ScrapePhase.INIT.value,
                'test_results': None,
                'crawler': None
            }
        finally:
            # 釋放爬蟲資源
            self.cleanup_crawler_instance(0)

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

    def cleanup_crawler_instance(self, task_id: int) -> None:
        """清理爬蟲實例，釋放資源
        
        Args:
            task_id: 任務ID
        """
        if task_id in self.running_crawlers:
            # 釋放資源（如有需要）
            # 例如: self.running_crawlers[task_id].cleanup()
            # 目前沒有需要釋放的資源，因為爬蟲實例是通過_handle_task_cancellation釋放
            # 從運行中爬蟲清單移除
            del self.running_crawlers[task_id]
            logger.info(f"已清理任務 {task_id} 的爬蟲實例")


