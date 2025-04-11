from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Type, cast, Optional
import threading
import time
import logging

from src.services.base_service import BaseService
from src.database.base_repository import BaseRepository, SchemaType
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.database.crawlers_repository import CrawlersRepository
from src.database.crawler_task_history_repository import CrawlerTaskHistoryRepository
from src.database.articles_repository import ArticlesRepository
from src.models.base_model import Base
from src.models.crawler_tasks_model import CrawlerTasks, TaskPhase, ScrapeMode
from src.models.crawlers_model import Crawlers
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.models.articles_model import Articles
from src.error.errors import ValidationError

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CrawlerTaskService(BaseService[CrawlerTasks]):
    """爬蟲任務服務，負責管理爬蟲任務的數據操作（CRUD）"""
    
    def __init__(self, db_manager=None):
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
        
    def validate_task_data(self, data: Dict[str, Any], is_update: bool = False) -> Dict[str, Any]:
        """驗證任務資料
        
        Args:
            data: 要驗證的資料
            is_update: 是否為更新操作
            
        Returns:
            Dict[str, Any]: 驗證後的資料
        """
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
                        'message': '無法取得資料庫存取器'
                    }
                
                # 創建任務
                task = tasks_repo.create(task_data)
                return {
                    'success': True,
                    'message': '任務創建成功',
                    'task_id': task.id if task else None
                }
        except ValidationError as e:
            error_msg = f"創建任務資料驗證失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
        except Exception as e:
            error_msg = f"創建任務失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
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
            raise e
    
    def get_task_by_id(self, task_id: int) -> Dict:
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
                    
                task = tasks_repo.get_by_id(task_id)
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
            raise e
    
    def get_all_tasks(self, filters=None) -> Dict:
        """獲取所有任務，可選過濾條件"""
        try:
            with self._transaction():
                tasks_repo, _, _ = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'tasks': []
                    }
                    
                tasks = tasks_repo.get_all(filters)
                return {
                    'success': True,
                    'message': '任務獲取成功',
                    'tasks': tasks
                }
        except Exception as e:
            error_msg = f"獲取所有任務失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e
        
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
            raise e

    def get_task_status(self, task_id: int) -> Dict:
        """獲取任務的當前狀態（從歷史記錄中）"""
        try:
            with self._transaction():
                tasks_repo, _, history_repo = self._get_repositories()
                if not tasks_repo or not history_repo:
                    return {
                        'status': 'error',
                        'progress': 0,
                        'message': '無法取得資料庫存取器',
                        'task': None
                    }
                    
                # 檢查任務是否存在
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'status': 'unknown',
                        'progress': 0,
                        'message': '任務不存在',
                        'task': None
                    }
                    
                # 從資料庫獲取最新一筆歷史記錄
                latest_history = history_repo.get_latest_history(task_id)
                
                if not latest_history or not latest_history.start_time:
                    return {
                        'status': 'unknown',
                        'progress': 0,
                        'message': '無執行歷史',
                        'task': task
                    }
                
                # 計算進度
                if latest_history.end_time:
                    status = 'completed' if latest_history.success else 'failed'
                    progress = 100
                else:
                    status = 'running'
                    # 如果正在執行中，根據開始時間計算大約進度
                    current_time = datetime.now(timezone.utc)
                    elapsed = current_time - latest_history.start_time  # start_time 已經確認不是 None
                    # 假設每個任務平均執行時間為 5 分鐘
                    progress = min(95, int((elapsed.total_seconds() / 300) * 100))
                
                return {
                    'status': status,
                    'progress': progress,
                    'message': latest_history.message or '',
                    'articles_count': latest_history.articles_count or 0,
                    'start_time': latest_history.start_time,
                    'end_time': latest_history.end_time
                }
                
        except Exception as e:
            error_msg = f"獲取任務狀態失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'status': 'error',
                'progress': 0,
                'message': f'獲取狀態時發生錯誤: {str(e)}'
            }

    def run_task(self, task_id: int, task_args: Dict[str, Any]) -> Dict[str, Any]:
        """執行任務
            使用情境：
                1. 手動任務：當使用者手動選擇要執行的任務時，會使用此方法
                2. 自動任務：當任務執行時，會使用此方法

        Args:
            task_id: 任務ID
            task_args: 任務參數
            
        Returns:
            Dict[str, Any]: 執行結果
        """
        try:
            with self._transaction():
                tasks_repo, _, history_repo = self._get_repositories()
                if not tasks_repo or not history_repo:
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
                
                try:
                    # 更新任務階段為初始階段
                    self.update_task_phase(task_id, TaskPhase.INIT)
                    
                    # 根據抓取模式執行不同的流程
                    scrape_mode = task.scrape_mode
                    logger.info(f"執行任務模式: {scrape_mode.value}")
                    
                    result = {'success': False, 'message': '未知執行結果'}
                    
                    # 根據抓取模式執行對應流程
                    if scrape_mode == ScrapeMode.LINKS_ONLY:
                        # 只抓取連結
                        result = self.collect_article_links(task_id)
                    elif scrape_mode == ScrapeMode.CONTENT_ONLY:
                        # 只抓取內容 (需從資料庫獲取未抓取的連結)
                        # 1. 從資料庫獲取與此任務相關的未抓取連結ID
                        
                        # 獲取文章儲存庫
                        article_repo = self._get_articles_repository()
                        
                        # 根據任務ID獲取未抓取內容的文章
                        unscraped_articles = article_repo.find_articles_by_task_id(
                            task_id=task_id,
                            is_scraped=False,
                            limit=100
                        )
                        
                        # 如果沒有未抓取的文章，直接返回
                        if not unscraped_articles:
                            history_update_data = {
                                'end_time': datetime.now(timezone.utc),
                                'status': 'completed',
                                'message': '沒有未抓取的文章連結'
                            }
                            
                            validated_history_update = self.validate_data('TaskHistory', history_update_data, SchemaType.UPDATE)
                            history_repo.update(history_id, validated_history_update)
                            
                            # 更新任務最後執行狀態
                            tasks_repo.update_last_run(task_id, True, '沒有未抓取的文章連結')
                            
                            return {
                                'success': True,
                                'message': '沒有未抓取的文章連結',
                                'articles_count': 0
                            }
                        
                        # 2. 抓取內容
                        link_ids = [article.id for article in unscraped_articles]
                        result = self.fetch_article_content(task_id, link_ids)
                    elif scrape_mode == ScrapeMode.FULL_SCRAPE:
                        # 完整流程：先抓取連結，再抓取內容
                        # 1. 抓取連結
                        links_result = self.collect_article_links(task_id)
                        
                        # 如果連結抓取失敗或沒有連結，直接返回結果
                        if not links_result.get('success', False) or links_result.get('links_found', 0) == 0:
                            return links_result
                        
                        # 2. 獲取新抓取的連結ID
                        # 根據任務ID從資料庫查詢未抓取內容的文章
                        
                        # 獲取文章儲存庫
                        article_repo = self._get_articles_repository()
                        newly_added_articles = article_repo.find_articles_by_task_id(
                            task_id=task_id,
                            is_scraped=False,
                            limit=100
                        )
                        
                        if not newly_added_articles:
                            # 沒有找到新連結，直接返回
                            return links_result
                        
                        # 3. 抓取內容
                        link_ids = [article.id for article in newly_added_articles]
                        result = self.fetch_article_content(task_id, link_ids)
                    
                    # 更新任務歷史記錄
                    history_update_data = {
                        'end_time': datetime.now(timezone.utc),
                        'status': 'completed' if result.get('success', False) else 'failed',
                        'message': result.get('message', '任務執行完成'),
                        'articles_count': result.get('articles_count', 0)
                    }
                    
                    # 驗證歷史記錄更新資料
                    validated_history_update = self.validate_data('TaskHistory', history_update_data, SchemaType.UPDATE)
                    # 更新歷史記錄
                    history_repo.update(history_id, validated_history_update)
                    
                    # 更新任務階段為完成
                    if result.get('success', False):
                        self.update_task_phase(task_id, TaskPhase.COMPLETED)
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
                    history_update_data = {
                        'end_time': datetime.now(timezone.utc),
                        'status': 'failed',
                        'message': f'任務執行失敗: {str(e)}'
                    }
                    
                    # 驗證歷史記錄更新資料
                    validated_history_update = self.validate_data('TaskHistory', history_update_data, SchemaType.UPDATE)
                    # 更新歷史記錄
                    history_repo.update(history_id, validated_history_update)
                    
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
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    def fetch_article_content(self, task_id: int, link_ids: List[int]) -> Dict[str, Any]:
        """ 抓取文章內容，並更新文章內容
            使用情境：
                1. 手動任務：當使用者手動選擇要抓取的文章連結時，會使用此方法
                2. 自動任務：當任務執行時，會使用此方法

        Args:
            task_id: 任務ID
            link_ids: 文章連結ID列表
            
        Returns:
            Dict[str, Any]: 執行結果
        """
        try:
            with self._transaction():
                tasks_repo, _, history_repo = self._get_repositories()
                if not tasks_repo or not history_repo:
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
                
                # 創建任務歷史記錄
                history_data = {
                    'task_id': task_id,
                    'start_time': datetime.now(timezone.utc),
                    'status': 'running',
                    'message': '開始抓取文章內容'
                }
                
                # 先驗證歷史記錄資料
                validated_history_data = self.validate_data('TaskHistory', history_data, SchemaType.CREATE)
                # 創建歷史記錄
                history = history_repo.create(validated_history_data)
                history_id = history.id if history else None
                
                try:
                    # 更新任務階段為內容爬取階段
                    self.update_task_phase(task_id, TaskPhase.CONTENT_SCRAPING)
                    
                    # 獲取爬蟲資訊
                    crawler = task.crawler
                    if not crawler:
                        return {
                            'success': False,
                            'message': '任務未關聯有效的爬蟲'
                        }
                    
                    # 獲取要抓取內容的文章
                    article_repo = self._get_articles_repository()
                    articles_to_fetch = []
                    
                    # 驗證連結ID是否有效
                    if not link_ids:
                        return {
                            'success': False,
                            'message': '沒有提供要抓取的文章連結ID'
                        }
                    
                    # 獲取每個ID對應的文章
                    for link_id in link_ids:
                        article = article_repo.get_by_id(link_id)
                        if article and not article.is_scraped:
                            articles_to_fetch.append(article)
                    
                    if not articles_to_fetch:
                        history_update_data = {
                            'end_time': datetime.now(timezone.utc),
                            'status': 'completed',
                            'message': '沒有需要抓取內容的文章'
                        }
                        
                        validated_history_update = self.validate_data('TaskHistory', history_update_data, SchemaType.UPDATE)
                        history_repo.update(history_id, validated_history_update)
                        
                        # 更新任務階段為完成
                        self.update_task_phase(task_id, TaskPhase.COMPLETED)
                        
                        # 更新任務最後執行狀態
                        tasks_repo.update_last_run(task_id, True, '沒有需要抓取內容的文章')
                        
                        return {
                            'success': True,
                            'message': '沒有需要抓取內容的文章',
                            'articles_count': 0
                        }
                    
                    # 創建爬蟲實例
                    from src.crawlers.crawler_factory import CrawlerFactory
                    crawler_instance = CrawlerFactory.get_crawler(crawler.crawler_name)
                    
                    # 設置爬蟲參數
                    crawler_params = task.task_args or {}
                    # 將任務的ai_only設置傳給爬蟲
                    crawler_params['ai_only'] = task.ai_only
                    # 設置為只抓取內容模式
                    crawler_params['content_only'] = True
                    # 將文章ID傳給爬蟲
                    crawler_params['article_ids'] = [article.id for article in articles_to_fetch]
                    # 將文章連結傳給爬蟲
                    crawler_params['article_links'] = [article.link for article in articles_to_fetch]
                    
                    # 增加task_id，讓爬蟲可以把抓取的文章關聯到當前任務
                    crawler_params['task_id'] = task_id
                    
                    # 執行爬蟲
                    result = crawler_instance.execute_task(task_id, crawler_params)
                    
                    # 檢查執行結果
                    success = result.get('success', False)
                    articles_count = result.get('articles_count', 0)
                    
                    # 更新任務歷史記錄
                    history_update_data = {
                        'end_time': datetime.now(timezone.utc),
                        'status': 'completed' if success else 'failed',
                        'message': result.get('message', '文章內容抓取完成' if success else '文章內容抓取失敗'),
                        'articles_count': articles_count
                    }
                    
                    # 驗證歷史記錄更新資料
                    validated_history_update = self.validate_data('TaskHistory', history_update_data, SchemaType.UPDATE)
                    # 更新歷史記錄
                    history_repo.update(history_id, validated_history_update)
                    
                    # 更新任務階段為完成
                    self.update_task_phase(task_id, TaskPhase.COMPLETED)
                    
                    # 成功執行後重置重試次數
                    self.reset_retry_count(task_id)
                    
                    # 更新任務最後執行狀態
                    tasks_repo.update_last_run(task_id, success, result.get('message', '文章內容抓取完成' if success else '文章內容抓取失敗'))
                    
                    return {
                        'success': success,
                        'message': result.get('message', '文章內容抓取完成' if success else '文章內容抓取失敗'),
                        'articles_count': articles_count
                    }
                except Exception as e:
                    # 更新任務歷史記錄
                    history_update_data = {
                        'end_time': datetime.now(timezone.utc),
                        'status': 'failed',
                        'message': f'文章內容抓取失敗: {str(e)}'
                    }
                    
                    # 驗證歷史記錄更新資料
                    validated_history_update = self.validate_data('TaskHistory', history_update_data, SchemaType.UPDATE)
                    # 更新歷史記錄
                    history_repo.update(history_id, validated_history_update)
                    
                    # 增加重試次數
                    retry_result = self.increment_retry_count(task_id)
                    
                    # 更新任務最後執行狀態
                    tasks_repo.update_last_run(task_id, False, f'文章內容抓取失敗: {str(e)}')
                    
                    return {
                        'success': False,
                        'message': f'文章內容抓取失敗: {str(e)}',
                        'retry_info': retry_result
                    }
        except Exception as e:
            error_msg = f"抓取文章內容失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    def test_crawler_task(self, crawler_data: Dict[str, Any], task_data: Dict[str, Any]) -> Dict[str, Any]:
        """測試爬蟲任務
        
        Args:
            crawler_data: 爬蟲資料
            task_data: 任務資料
            
        Returns:
            Dict[str, Any]: 測試結果
        """
        try:
            # 驗證爬蟲配置和任務資料
            tasks_repo, crawlers_repo, _ = self._get_repositories()
            
            try:
                # 驗證爬蟲配置
                self.validate_data('Crawler', crawler_data, SchemaType.CREATE)
            except ValidationError as e:
                return {
                    'success': False,
                    'message': '爬蟲配置驗證失敗',
                    'errors': str(e)
                }
            
            try:
                # 驗證任務資料
                self.validate_data('CrawlerTask', task_data, SchemaType.CREATE)
            except ValidationError as e:
                return {
                    'success': False,
                    'message': '任務資料驗證失敗',
                    'errors': str(e)
                }
            
            # 設定階段為初始階段
            task_data['current_phase'] = TaskPhase.INIT
            
            # 實際測試爬蟲功能
            try:
                # 從爬蟲資料中獲取爬蟲名稱
                crawler_name = crawler_data.get('crawler_name')
                if not crawler_name:
                    return {
                        'success': False,
                        'message': '未提供爬蟲名稱',
                        'task_phase': TaskPhase.INIT.value
                    }
                
                # 創建爬蟲實例進行實際測試
                from src.crawlers.crawler_factory import CrawlerFactory
                from src.services.article_service import ArticleService
                
                # 獲取文章服務實例
                article_service = ArticleService(self.db_manager)
                
                # 測試爬蟲是否能成功初始化
                try:
                    crawler_instance = CrawlerFactory.get_crawler(crawler_name)
                except ValueError:
                    # 如果爬蟲不存在，則臨時註冊一個測試用的爬蟲
                    logger.info(f"爬蟲 {crawler_name} 尚未註冊，將以模擬方式進行測試")
                    # 這裡可以選擇僅進行參數驗證而不實際測試爬蟲
                    return {
                        'success': True,
                        'message': '爬蟲配置驗證成功，但爬蟲尚未註冊，無法執行完整測試',
                        'task_phase': TaskPhase.INIT.value,
                        'test_results': {
                            'links_found': 0,
                            'sample_links': [],
                            'execution_time': 0
                        }
                    }
                
                # 準備測試參數 (只收集連結，不抓取內容)
                test_args = task_data.get('task_args', {}).copy()
                test_args['links_only'] = True
                test_args['ai_only'] = task_data.get('ai_only', False)
                
                # 修改參數，限制測試範圍
                if 'max_pages' in test_args:
                    # 限制測試時只抓取1頁
                    test_args['max_pages'] = min(1, test_args['max_pages'])
                    
                if 'num_articles' in test_args:
                    # 限制測試時只抓取最多5篇文章
                    test_args['num_articles'] = min(5, test_args['num_articles'])
                
                # 加入測試標記，允許爬蟲識別這是測試模式
                test_args['is_test'] = True
                
                # 執行爬蟲測試，收集連結
                start_time = datetime.now(timezone.utc)
                try:
                    # 設定超時時間為30秒
                    import signal
                    
                    class TimeoutException(Exception):
                        pass
                    
                    def timeout_handler(signum, frame):
                        raise TimeoutException("爬蟲測試超時")
                    
                    # 為了安全，設置測試超時
                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(30)  # 30秒超時
                    
                    result = crawler_instance.execute_task(0, test_args)  # 使用0作為測試任務ID
                    
                    # 關閉超時
                    signal.alarm(0)
                    
                    # 處理結果
                    end_time = datetime.now(timezone.utc)
                    execution_time = (end_time - start_time).total_seconds()
                    
                    if result.get('success', False):
                        links_found = result.get('articles_count', 0)
                        
                        # 獲取樣本連結
                        sample_links = []
                        if hasattr(crawler_instance, 'articles_df') and not crawler_instance.articles_df.empty:
                            # 從爬蟲的文章DataFrame中獲取樣本連結
                            sample_df = crawler_instance.articles_df.head(3)
                            if 'link' in sample_df.columns:
                                sample_links = sample_df['link'].tolist()
                        
                        return {
                            'success': True,
                            'message': f'爬蟲測試成功，執行時間: {execution_time:.2f}秒',
                            'test_results': {
                                'links_found': links_found,
                                'sample_links': sample_links,
                                'execution_time': execution_time
                            },
                            'task_phase': TaskPhase.LINK_COLLECTION.value
                        }
                    else:
                        # 爬蟲執行失敗
                        return {
                            'success': False,
                            'message': f'爬蟲測試失敗: {result.get("message", "未知錯誤")}',
                            'task_phase': TaskPhase.INIT.value
                        }
                except TimeoutException:
                    return {
                        'success': False,
                        'message': '爬蟲測試超時，請檢查爬蟲配置或網站狀態',
                        'task_phase': TaskPhase.INIT.value
                    }
                except Exception as e:
                    # 爬蟲執行出錯
                    return {
                        'success': False,
                        'message': f'爬蟲測試執行異常: {str(e)}',
                        'task_phase': TaskPhase.INIT.value
                    }
            except Exception as e:
                # 測試爬蟲連結收集失敗
                return {
                    'success': False,
                    'message': f'爬蟲連結收集測試失敗: {str(e)}',
                    'task_phase': TaskPhase.INIT.value
                }
                
        except Exception as e:
            error_msg = f"爬蟲測試失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    def cancel_task(self, task_id: int) -> Dict[str, Any]:
        """取消任務
        
        Args:
            task_id: 任務ID
            
        Returns:
            Dict[str, Any]: 取消結果
        """
        try:
            with self._transaction():
                tasks_repo, _, history_repo = self._get_repositories()
                if not tasks_repo or not history_repo:
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
                
                # 檢查任務是否正在執行
                latest_history = history_repo.get_latest_history(task_id)
                if not latest_history or latest_history.status != 'running':
                    return {
                        'success': False,
                        'message': '任務未在執行中'
                    }
                
                # 更新任務歷史記錄
                history_data = {
                    'end_time': datetime.now(timezone.utc),
                    'status': 'cancelled',
                    'message': '任務已取消'
                }
                
                # 驗證歷史記錄更新資料
                validated_history_data = self.validate_data('TaskHistory', history_data, SchemaType.UPDATE)
                # 更新歷史記錄
                history_repo.update(latest_history.id, validated_history_data)
                
                return {
                    'success': True,
                    'message': '任務已取消'
                }
        except Exception as e:
            error_msg = f"取消任務失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
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
            
    def toggle_ai_only_status(self, task_id: int) -> Dict:
        """切換任務的AI收集狀態"""
        try:
            with self._transaction():
                tasks_repo, _, _ = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                    
                success = tasks_repo.toggle_ai_only_status(task_id)
                return {
                    'success': success,
                    'message': 'AI收集狀態切換成功' if success else '任務不存在'
                }
        except Exception as e:
            error_msg = f"切換任務AI收集狀態失敗, ID={task_id}: {str(e)}"
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

    def update_task_phase(self, task_id: int, phase: TaskPhase) -> Dict:
        """更新任務階段
        
        Args:
            task_id: 任務ID
            phase: 任務階段
            
        Returns:
            更新結果
        """
        try:
            with self._transaction():
                tasks_repo, _, _ = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在'
                    }
                
                # 更新任務階段
                task_data = {'current_phase': phase}
                result = tasks_repo.update(task_id, task_data)
                
                return {
                    'success': True,
                    'message': f'任務階段更新為 {phase.value}',
                    'task': result
                }
        except Exception as e:
            error_msg = f"更新任務階段失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
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
                        'message': '無法取得資料庫存取器'
                    }
                
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在'
                    }
                
                # 檢查是否已超過最大重試次數
                if task.retry_count >= task.max_retries:
                    return {
                        'success': False,
                        'message': f'已超過最大重試次數 {task.max_retries}',
                        'exceeded_max_retries': True,
                        'retry_count': task.retry_count,
                        'max_retries': task.max_retries
                    }
                
                # 增加重試次數
                current_retry = task.retry_count + 1
                task_data = {'retry_count': current_retry}
                result = tasks_repo.update(task_id, task_data)
                
                # 檢查是否達到最大重試次數
                has_reached_max = current_retry >= task.max_retries
                
                return {
                    'success': True,
                    'message': f'重試次數更新為 {current_retry}/{task.max_retries}',
                    'retry_count': current_retry,
                    'max_retries': task.max_retries,
                    'exceeded_max_retries': has_reached_max,
                    'task': result
                }
        except Exception as e:
            error_msg = f"更新重試次數失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
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
                        'message': '無法取得資料庫存取器'
                    }
                
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在'
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
                'message': error_msg
            }

    def update_max_retries(self, task_id: int, max_retries: int) -> Dict:
        """更新任務最大重試次數
        
        Args:
            task_id: 任務ID
            max_retries: 最大重試次數
            
        Returns:
            更新結果
        """
        if max_retries < 0:
            return {
                'success': False,
                'message': '最大重試次數不能小於 0'
            }
        
        try:
            with self._transaction():
                tasks_repo, _, _ = self._get_repositories()
                if not tasks_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                
                task = tasks_repo.get_by_id(task_id)
                if not task:
                    return {
                        'success': False,
                        'message': '任務不存在'
                    }
                
                # 更新最大重試次數
                task_data = {'max_retries': max_retries}
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
                'message': error_msg
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
                retryable_tasks = [task for task in failed_tasks if task.retry_count < task.max_retries]
                
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

    def collect_article_links(self, task_id: int) -> Dict[str, Any]:
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
                        'message': '無法取得資料庫存取器'
                    }
                
                # 檢查任務是否存在
                task = tasks_repo.get_by_id(task_id)
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
                    'message': '開始收集文章連結'
                }
                
                # 先驗證歷史記錄資料
                validated_history_data = self.validate_data('TaskHistory', history_data, SchemaType.CREATE)
                # 創建歷史記錄
                history = history_repo.create(validated_history_data)
                history_id = history.id if history else None
                
                try:
                    # 更新任務階段為連結收集階段
                    self.update_task_phase(task_id, TaskPhase.LINK_COLLECTION)
                    
                    # 獲取爬蟲資訊
                    crawler = task.crawler
                    if not crawler:
                        return {
                            'success': False,
                            'message': '任務未關聯有效的爬蟲'
                        }
                    
                    # 創建爬蟲實例
                    from src.crawlers.crawler_factory import CrawlerFactory
                    crawler_instance = CrawlerFactory.get_crawler(crawler.crawler_name)
                    
                    # 設置爬蟲參數
                    crawler_params = task.task_args or {}
                    # 將任務的ai_only設置傳給爬蟲
                    crawler_params['ai_only'] = task.ai_only
                    
                    # 執行連結收集
                    # 讓爬蟲只執行連結收集部分
                    from src.services.article_service import ArticleService
                    article_service = ArticleService(self.db_manager)
                    
                    # 獲取最初文章數量作為基準
                    article_repo = self._get_articles_repository()
                    initial_count = article_repo.count({
                        'source': crawler.crawler_name
                    })
                    
                    # 修改task_args確保只抓取連結不抓內容
                    crawler_params['links_only'] = True
                    
                    # 增加task_id，讓爬蟲可以把抓取的文章關聯到當前任務
                    crawler_params['task_id'] = task_id
                    
                    # 執行爬蟲
                    result = crawler_instance.execute_task(task_id, crawler_params)
                    
                    # 獲取新增的文章數量
                    new_count = article_repo.count({
                        'source': crawler.crawler_name
                    })
                    links_found = new_count - initial_count
                    
                    # 獲取新增的文章ID
                    # 這裡假設最新的文章ID就是剛抓取的連結，實務上可能需要更精確的過濾
                    # 例如根據時間範圍或特定標記
                    newly_added_articles = article_repo.find_unscraped_links(
                        limit=links_found,
                        source=crawler.crawler_name
                    )
                    newly_added_ids = [article.id for article in newly_added_articles]
                    
                    # 更新任務歷史記錄
                    history_update_data = {
                        'end_time': datetime.now(timezone.utc),
                        'status': 'completed',
                        'message': f'文章連結收集完成，共收集 {links_found} 個連結',
                        'articles_count': links_found  # 更新收集到的文章數量
                    }
                    
                    # 驗證歷史記錄更新資料
                    validated_history_update = self.validate_data('TaskHistory', history_update_data, SchemaType.UPDATE)
                    # 更新歷史記錄
                    history_repo.update(history_id, validated_history_update)
                    
                    # 根據配置決定是否繼續進行內容抓取，這裡簡單檢查任務是否為自動執行
                    should_fetch_content = task.is_auto and task.scrape_mode == ScrapeMode.FULL_SCRAPE
                    
                    if links_found > 0 and should_fetch_content:
                        # 這裡可以直接調用抓取內容的方法，或者返回連結列表讓呼叫者決定
                        next_step = "content_scraping"
                    else:
                        # 如果沒有找到連結或不需要抓取內容，則將任務標記為完成
                        self.update_task_phase(task_id, TaskPhase.COMPLETED)
                        next_step = "completed"
                    
                    # 成功執行後重置重試次數
                    self.reset_retry_count(task_id)
                    
                    # 更新任務最後執行狀態
                    tasks_repo.update_last_run(task_id, True, f'文章連結收集完成，共收集 {links_found} 個連結')
                    
                    return {
                        'success': True,
                        'message': f'文章連結收集完成，共收集 {links_found} 個連結',
                        'links_found': links_found,
                        'article_ids': newly_added_ids,
                        'next_step': next_step
                    }
                except Exception as e:
                    # 更新任務歷史記錄
                    history_update_data = {
                        'end_time': datetime.now(timezone.utc),
                        'status': 'failed',
                        'message': f'文章連結收集失敗: {str(e)}'
                    }
                    
                    # 驗證歷史記錄更新資料
                    validated_history_update = self.validate_data('TaskHistory', history_update_data, SchemaType.UPDATE)
                    # 更新歷史記錄
                    history_repo.update(history_id, validated_history_update)
                    
                    # 增加重試次數
                    retry_result = self.increment_retry_count(task_id)
                    
                    # 更新任務最後執行狀態
                    tasks_repo.update_last_run(task_id, False, f'文章連結收集失敗: {str(e)}')
                    
                    return {
                        'success': False,
                        'message': f'文章連結收集失敗: {str(e)}',
                        'retry_info': retry_result
                    }
        except Exception as e:
            error_msg = f"收集文章連結失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    def test_content_only_mode_with_limit(self, crawler_task_service, sample_tasks, mocker):
        """測試CONTENT_ONLY模式時的文章限制邊界條件"""
        task_id = sample_tasks[0].id
        
        # 修改任務為僅抓取內容模式
        crawler_task_service.update_task(task_id, {"scrape_mode": "content_only"})
        
        # 創建超過100篇的文章模擬對象
        mock_articles = [mocker.Mock(id=i) for i in range(1, 120)]
        
        # Mock文章存儲庫以返回測試數據
        mock_article_repo = mocker.Mock()
        mock_article_repo.find_articles_by_task_id.return_value = mock_articles[:100]  # 應該只返回100篇
        mocker.patch.object(crawler_task_service, '_get_articles_repository', return_value=mock_article_repo)
        
        # Mock fetch_article_content 函數以避免實際執行
        mocker.patch.object(
            crawler_task_service, 
            'fetch_article_content', 
            return_value={'success': True, 'articles_count': 100}
        )
        
        result = crawler_task_service.run_task(task_id, {})
        
        # 驗證文章數量確實被限制在100
        mock_article_repo.find_articles_by_task_id.assert_called_once()
        # 檢查調用參數中限制值是否為100
        assert mock_article_repo.find_articles_by_task_id.call_args[1]['limit'] == 100
        assert result["success"] is True