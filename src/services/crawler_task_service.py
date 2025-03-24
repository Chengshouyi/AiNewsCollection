from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import threading
import time
import logging

from src.database.database_manager import DatabaseManager
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.database.crawlers_repository import CrawlersRepository
from src.database.crawler_task_history_repository import CrawlerTaskHistoryRepository
from src.crawlers.crawler_factory import CrawlerFactory
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawlers_model import Crawlers
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.error.errors import DatabaseOperationError, ValidationError
from src.models.crawler_tasks_schema import CrawlerTasksCreateSchema, CrawlerTasksUpdateSchema
from src.models.crawler_task_history_schema import CrawlerTaskHistoryCreateSchema

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CrawlerTaskService:
    """爬蟲任務服務，負責管理爬蟲任務的執行和狀態追蹤"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.running_tasks = {}
        self.task_threads = {}
        self.crawler_factory = CrawlerFactory()
        
    def _get_repositories(self) -> Tuple[CrawlerTasksRepository, CrawlersRepository, CrawlerTaskHistoryRepository, Any]:
        """取得儲存庫的上下文管理器"""
        session = self.db_manager.Session()
        try:
            tasks_repo = CrawlerTasksRepository(session, CrawlerTasks)
            crawlers_repo = CrawlersRepository(session, Crawlers)
            history_repo = CrawlerTaskHistoryRepository(session, CrawlerTaskHistory)
            return tasks_repo, crawlers_repo, history_repo, session
        except Exception as e:
            error_msg = f"取得儲存庫失敗: {e}"
            logger.error(error_msg)
            session.close()
            raise DatabaseOperationError(error_msg) from e
        
    def get_all_tasks(self) -> List[CrawlerTasks]:
        """獲取所有任務的列表"""
        try:
            tasks_repo, _, _, session = self._get_repositories()
            tasks = tasks_repo.get_all()
            return tasks
        except Exception as e:
            error_msg = f"獲取所有任務失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e
        
    def get_task_by_id(self, task_id: int) -> Optional[CrawlerTasks]:
        """根據ID獲取任務"""
        try:
            tasks_repo, _, _, session = self._get_repositories()
            task = tasks_repo.get_by_id(task_id)
            return task
        except Exception as e:
            error_msg = f"獲取任務失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e
        
    def create_task(self, task_data: Dict) -> Optional[CrawlerTasks]:
        """創建新任務"""
        tasks_repo, crawlers_repo, _, session = None, None, None, None
        
        try:
            tasks_repo, crawlers_repo, _, session = self._get_repositories()
            
            # 驗證爬蟲是否存在
            crawler = crawlers_repo.get_by_id(task_data.get('crawler_id'))
            if not crawler:
                error_msg = f"爬蟲ID不存在: {task_data.get('crawler_id')}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # 添加必要的欄位
            now = datetime.now()
            task_data.update({
                'created_at': now,
                'updated_at': now
            })
            
            # 使用 Pydantic 驗證資料
            try:
                validated_data = CrawlerTasksCreateSchema.model_validate(task_data).model_dump()
                logger.info(f"任務資料驗證成功: {validated_data}")
            except Exception as e:
                error_msg = f"任務資料驗證失敗: {e}"
                logger.error(error_msg)
                raise ValidationError(error_msg) from e
            
            task = tasks_repo.create(validated_data)
            session.commit()
            log_info = f"成功創建任務, ID={task.id}"
            logger.info(log_info)
            return task
            
        except ValidationError as e:
            # 直接重新引發驗證錯誤
            if session:
                session.rollback()
            raise e
        except Exception as e:
            error_msg = f"創建任務失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if session:
                session.rollback()
            # 將其他例外轉換為 ValidationError，保持一致性
            raise ValidationError(f"創建任務失敗: {str(e)}")
        
    def update_task(self, task_id: int, task_data: Dict) -> Optional[CrawlerTasks]:
        """更新任務信息"""
        tasks_repo, _, _, session = None, None, None, None
        
        try:
            tasks_repo, _, _, session = self._get_repositories()
            
            # 先檢查任務是否存在
            task = tasks_repo.get_by_id(task_id)
            if not task:
                error_msg = f"欲更新的任務不存在, ID={task_id}"
                logger.error(error_msg)
                return None
            
            # 自動更新 updated_at 欄位
            task_data['updated_at'] = datetime.now()
            
            # 使用 Pydantic 驗證資料
            try:
                validated_data = CrawlerTasksUpdateSchema.model_validate(task_data).model_dump()
                logger.info(f"任務更新資料驗證成功: {validated_data}")
            except Exception as e:
                error_msg = f"任務更新資料驗證失敗: {str(e)}"
                logger.error(error_msg)
                raise ValidationError(error_msg)
            
            # 嘗試執行更新
            try:
                updated_task = tasks_repo.update(task_id, validated_data)
                
                if not updated_task:
                    error_msg = f"任務更新失敗，ID不存在: {task_id}"
                    logger.error(error_msg)
                    return None
                    
                session.commit()
                log_info = f"成功更新任務, ID={task_id}"
                logger.info(log_info)
                return updated_task
            except ValidationError as e:
                # 重要：回滾會話並重新引發例外
                session.rollback()
                raise e
        except ValidationError as e:
            # 重新引發驗證錯誤
            if session:
                session.rollback()
            raise e
        except Exception as e:
            error_msg = f"更新任務失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if session:
                session.rollback()
            # 將其他例外轉換為 ValidationError，保持一致性
            raise ValidationError(f"更新任務失敗: {str(e)}")
        
    def delete_task(self, task_id: int) -> bool:
        """刪除任務"""
        tasks_repo, _, _, session = None, None, None, None
        
        try:
            tasks_repo, _, _, session = self._get_repositories()
            
            # 檢查任務是否正在運行
            if task_id in self.running_tasks:
                error_msg = f"無法刪除正在運行的任務, ID={task_id}"
                logger.error(error_msg)
                raise ValidationError(error_msg)
                
            result = tasks_repo.delete(task_id)
            if not result:
                error_msg = f"欲刪除的任務不存在, ID={task_id}"
                logger.error(error_msg)
                return False
                
            session.commit()
            log_info = f"成功刪除任務, ID={task_id}"
            logger.info(log_info)
            return True
            
        except ValidationError as e:
            # 直接重新引發驗證錯誤
            raise e
        except Exception as e:
            error_msg = f"刪除任務失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if session:
                session.rollback()
            raise e
        
    def execute_task(self, task_id: int) -> Dict:
        """手動執行任務"""
        try:
            tasks_repo, crawlers_repo, history_repo, session = self._get_repositories()
            
            task = tasks_repo.get_by_id(task_id)
            if not task:
                error_msg = f"任務ID不存在: {task_id}"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            # 檢查任務是否已在運行
            if task_id in self.running_tasks:
                log_info = f"任務已在運行中, ID={task_id}"
                logger.info(log_info)
                return {
                    'success': False,
                    'message': '任務已在運行中',
                    'status': self.running_tasks[task_id]
                }
                
            # 獲取爬蟲實例
            crawler = crawlers_repo.get_by_id(task.crawler_id)
            if not crawler:
                error_msg = f"爬蟲ID不存在: {task.crawler_id}"
                logger.error(error_msg)
                raise ValueError(error_msg)

            crawler_instance = self.crawler_factory.get_crawler(crawler.crawler_type)
            
            # 準備任務參數
            task_args = {
                'max_pages': task.max_pages if hasattr(task, 'max_pages') else 3,
                'ai_only': task.ai_only,
                'fetch_details': task.fetch_details if hasattr(task, 'fetch_details') else False,
                'num_articles': task.num_articles if hasattr(task, 'num_articles') else 10,
                'min_keywords': task.min_keywords if hasattr(task, 'min_keywords') else 3
            }
            
            # 創建任務歷史記錄
            history_data = {
                'task_id': task_id,
                'start_time': datetime.now(),
                'success': False,  # 預設為失敗，執行完成後更新
                'message': '任務開始執行',
                'articles_count': 0
            }
            
            try:
                validated_history_data = CrawlerTaskHistoryCreateSchema.model_validate(history_data).model_dump()
                history = history_repo.create(validated_history_data)
                session.commit()
                history_id = history.id
                logger.info(f"成功創建任務歷史記錄, ID={history_id}")
            except Exception as e:
                logger.error(f"創建任務歷史記錄失敗: {str(e)}")
                history_id = None
                
            # 在新線程中執行任務
            thread = threading.Thread(
                target=self._execute_task_thread,
                args=(task_id, crawler_instance, task_args, history_id)
            )
            thread.start()
            
            self.task_threads[task_id] = thread
            self.running_tasks[task_id] = {
                'status': 'starting',
                'progress': 0,
                'message': '正在啟動任務',
                'start_time': datetime.now().isoformat(),
                'history_id': history_id
            }
            
            log_info = f"任務已啟動, ID={task_id}"
            logger.info(log_info)
            return {
                'success': True,
                'message': '任務已啟動',
                'task_id': task_id,
                'history_id': history_id
            }
            
        except Exception as e:
            error_msg = f"執行任務失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if session:
                session.rollback()
            raise e
        
    def _execute_task_thread(self, task_id, crawler_instance, task_args, history_id=None):
        """在線程中執行任務"""
        tasks_repo, _, history_repo, session = None, None, None, None
        
        try:
            tasks_repo, _, history_repo, session = self._get_repositories()
            
            # 更新任務開始狀態
            self._update_task_status(task_id, 'running', 0, '開始執行任務')
            log_info = f"任務開始執行, ID={task_id}"
            logger.info(log_info)
            
            # 執行爬蟲任務
            result_df = crawler_instance.execute_task(task_id, task_args, self.db_manager)
            articles_count = len(result_df) if result_df is not None else 0
            
            # 更新任務完成狀態
            completion_msg = f'任務完成，爬取了 {articles_count} 篇文章'
            self._update_task_status(task_id, 'completed', 100, completion_msg)
            
            # 更新任務在數據庫中的狀態
            tasks_repo.update_last_run(task_id, True, completion_msg)
            
            # 更新任務歷史記錄
            if history_id:
                history_repo.update_history_status(
                    history_id, 
                    True, 
                    completion_msg, 
                    articles_count
                )
                
            session.commit()
            
            log_info = f"任務執行完成, ID={task_id}, 爬取了 {articles_count} 篇文章"
            logger.info(log_info)
            
        except Exception as e:
            error_msg = f"任務執行失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # 更新失敗狀態
            failure_msg = f'任務失敗: {str(e)}'
            self._update_task_status(task_id, 'failed', 0, failure_msg)
            
            # 更新數據庫中的失敗狀態
            try:
                if tasks_repo:
                    tasks_repo.update_last_run(task_id, False, failure_msg)
                
                # 更新任務歷史記錄
                if history_id and history_repo:
                    history_repo.update_history_status(
                        history_id, 
                        False, 
                        failure_msg, 
                        0
                    )
                    
                if session:
                    session.commit()
            except Exception as db_e:
                logger.error(f"更新數據庫任務狀態失敗: {str(db_e)}", exc_info=True)
                if session:
                    session.rollback()
            
        finally:
            # 清理線程資源
            if task_id in self.task_threads:
                del self.task_threads[task_id]
                
    def _update_task_status(self, task_id, status, progress, message):
        """更新任務狀態"""
        if task_id in self.running_tasks:
            self.running_tasks[task_id].update({
                'status': status,
                'progress': progress,
                'message': message,
                'update_time': datetime.now().isoformat()
            })
            log_info = f"任務狀態更新: ID={task_id}, 狀態={status}, 進度={progress}%, 訊息={message}"
            logger.info(log_info)
            
    def get_task_status(self, task_id: int) -> Dict:
        """獲取任務的當前狀態"""
        try:
            # 如果任務正在運行中，返回內存中的狀態
            if task_id in self.running_tasks:
                return self.running_tasks[task_id]
                
            # 如果不在運行中，檢查數據庫狀態
            tasks_repo, _, _, _ = self._get_repositories()
            task = tasks_repo.get_by_id(task_id)
            
            if not task:
                return {
                    'status': 'unknown',
                    'progress': 0,
                    'message': '任務不存在'
                }
                
            if task.last_run_at:
                status = 'completed' if task.last_run_success else 'failed'
                return {
                    'status': status,
                    'progress': 100 if status == 'completed' else 0,
                    'message': task.last_run_message or f'上次運行於 {task.last_run_at}',
                    'last_run_at': task.last_run_at.isoformat() if task.last_run_at else None
                }
            else:
                return {
                    'status': 'pending',
                    'progress': 0,
                    'message': '未曾執行'
                }
                
        except Exception as e:
            error_msg = f"獲取任務狀態失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'status': 'error',
                'progress': 0,
                'message': f'獲取狀態時發生錯誤: {str(e)}'
            }
    
    def get_task_history(self, task_id: int) -> List[CrawlerTaskHistory]:
        """獲取任務的歷史記錄"""
        try:
            _, _, history_repo, _ = self._get_repositories()
            history_list = history_repo.find_by_task_id(task_id)
            return history_list
        except Exception as e:
            error_msg = f"獲取任務歷史記錄失敗, ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e
        
    def start_scheduler(self):
        """啟動自動任務的排程器"""
        try:
            self.scheduler_running = True
            scheduler_thread = threading.Thread(target=self._scheduler_loop)
            scheduler_thread.daemon = True
            scheduler_thread.start()
            log_info = "爬蟲任務排程器已啟動"
            logger.info(log_info)
        except Exception as e:
            error_msg = f"啟動排程器失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e
        
    def stop_scheduler(self):
        """停止排程器"""
        try:
            self.scheduler_running = False
            log_info = "爬蟲任務排程器正在停止"
            logger.info(log_info)
        except Exception as e:
            error_msg = f"停止排程器失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e
        
    def _scheduler_loop(self):
        """排程器主循環"""
        while self.scheduler_running:
            try:
                # 獲取需要執行的自動任務
                tasks_repo, _, _, _ = self._get_repositories()
                pending_tasks = tasks_repo.find_auto_tasks()
                
                for task in pending_tasks:
                    # 檢查任務是否已在運行
                    if task.id in self.running_tasks:
                        continue
                        
                    # 檢查是否達到執行條件
                    if self._should_execute_task(task):
                        log_info = f"自動執行任務(ID: {task.id})"
                        logger.info(log_info)
                        self.execute_task(task.id)
                        
                # 每分鐘檢查一次
                time.sleep(60)
                
            except Exception as e:
                error_msg = f"排程器運行錯誤: {str(e)}"
                logger.error(error_msg, exc_info=True)
                time.sleep(300)  # 發生錯誤後等待5分鐘再繼續
                
    def _should_execute_task(self, task):
        """檢查任務是否該執行"""
        # 實現排程邏輯
        if not task.schedule:
            return False
            
        now = datetime.now()
        
        # 如果從未運行過，立即執行
        if not task.last_run_at:
            log_info = f"任務從未運行過，準備執行(ID: {task.id})"
            logger.info(log_info)
            return True
            
        # 計算時間差
        time_diff = (now - task.last_run_at).total_seconds()
        
        # 根據調度類型計算是否應該執行
        if task.schedule == 'hourly':
            return time_diff >= 3600
        elif task.schedule == 'daily':
            return time_diff >= 86400
        elif task.schedule == 'weekly':
            return time_diff >= 604800
        else:
            # 嘗試解析 cron 表達式或其他排程格式
            # 這裡需要額外的邏輯
            return False 