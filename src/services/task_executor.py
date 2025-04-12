import logging
from typing import Optional, Dict, Any, List
from src.models.crawler_tasks_model import CrawlerTasks, ScrapeMode
from datetime import datetime, timezone
from src.crawlers.crawler_factory import CrawlerFactory
from src.database.crawler_task_history_repository import CrawlerTaskHistoryRepository
from src.services.base_service import BaseService

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TaskExecutor:
    """任務執行器，負責觸發爬蟲任務執行"""
    
    def __init__(self, task_history_repo: Optional[CrawlerTaskHistoryRepository] = None):
        """初始化任務執行器
        
        Args:
            task_history_repo: 任務歷史儲存庫實例，用於記錄執行結果
        """
        self.task_history_repo = task_history_repo
        self.executing_tasks = set()  # 正在執行的任務 ID 集合
    
    def execute_task(self, task: CrawlerTasks) -> Dict[str, Any]:
        """執行指定的爬蟲任務
        
        Args:
            task: 爬蟲任務實例
            
        Returns:
            Dict[str, Any]: 包含執行結果的字典
        """
        task_id = task.id
        
        # 檢查任務是否已在執行中
        if task_id in self.executing_tasks:
            logger.warning(f"任務 {task_id} 已在執行中，跳過本次執行")
            return {
                'success': False,
                'message': '任務已在執行中'
            }
        
        try:
            # 標記任務為執行中
            self.executing_tasks.add(task_id)
            
            # 記錄開始執行時間
            start_time = datetime.now(timezone.utc)
            history_id = None
            
            # 如果有任務歷史儲存庫，創建歷史記錄
            if self.task_history_repo:
                history = self.task_history_repo.create({
                    'task_id': task_id,
                    'start_time': start_time,
                    'success': False,  # 初始設為失敗，成功後更新
                    'message': '任務執行中'
                })
                if history:
                    history_id = history.id
            
            # 獲取關聯的爬蟲名稱
            crawler_name = task.crawler.crawler_name if task.crawler else None
            if not crawler_name:
                error_msg = f"無法獲取任務 {task_id} 的爬蟲名稱"
                self._update_history(history_id, False, error_msg)
                return {
                    'success': False,
                    'message': error_msg
                }
            
            # 嘗試獲取爬蟲實例
            try:
                crawler = CrawlerFactory.get_crawler(crawler_name)
            except Exception as e:
                error_msg = f"無法獲取爬蟲實例 {crawler_name}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                self._update_history(history_id, False, error_msg)
                return {
                    'success': False,
                    'message': error_msg
                }
                
            # 準備任務參數
            task_args = task.task_args or {}
            
            # 確保scrape_mode參數存在
            if hasattr(task, 'scrape_mode') and task.scrape_mode:
                task_args['scrape_mode'] = task.scrape_mode.value if isinstance(task.scrape_mode, ScrapeMode) else task.scrape_mode
            
            # 確保ai_only參數
            if hasattr(task, 'ai_only'):
                task_args['ai_only'] = task.ai_only
                
            # 執行爬蟲任務，並傳遞任務參數
            result = crawler.execute_task(task_id, task_args)
            
            # 記錄結束時間和結果
            end_time = datetime.now(timezone.utc)
            success = result.get('success', False)
            message = result.get('message', '任務執行完成')
            articles_count = result.get('articles_count', 0)
            
            # 更新歷史記錄
            self._update_history(
                history_id, 
                success, 
                message, 
                end_time, 
                articles_count
            )
            
            # 更新任務表中的任務狀態
            self._update_task(task_id, success, message)
            
            return result
        except Exception as e:
            error_msg = f"執行任務 {task_id} 時發生錯誤: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # 更新歷史記錄
            end_time = datetime.now(timezone.utc)
            self._update_history(history_id, False, error_msg, end_time)
            
            return {
                'success': False,
                'message': error_msg
            }
        finally:
            # 無論執行成功與否，都從執行中任務集合中移除
            if task_id in self.executing_tasks:
                self.executing_tasks.remove(task_id)
    
    def _update_history(
        self, 
        history_id: Optional[int], 
        success: bool, 
        message: str, 
        end_time: Optional[datetime] = None,
        articles_count: Optional[int] = None
    ) -> None:
        """更新任務執行歷史記錄
        
        Args:
            history_id: 歷史記錄 ID，如果為 None 則不更新
            success: 執行是否成功
            message: 執行結果消息
            end_time: 執行結束時間，預設為當前時間
            articles_count: 處理的文章數量
        """
        if not history_id or not self.task_history_repo:
            return
            
        try:
            update_data = {
                'success': success,
                'message': message,
            }
            
            if end_time:
                update_data['end_time'] = end_time
                
            if articles_count is not None:
                update_data['articles_count'] = articles_count
                
            self.task_history_repo.update(history_id, update_data)
        except Exception as e:
            logger.error(f"更新任務歷史記錄 {history_id} 時發生錯誤: {str(e)}", exc_info=True)
    
    def is_task_executing(self, task_id: int) -> bool:
        """檢查任務是否正在執行中
        
        Args:
            task_id: 任務 ID
            
        Returns:
            bool: 如果任務正在執行中，返回 True；否則返回 False
        """
        return task_id in self.executing_tasks

    def _update_task(self, task_id: int, success: bool, message: str) -> None:
        """更新任務表中的任務狀態
        
        注意：由於歷史記錄已經包含了任務執行的狀態，這裡不再重複更新任務表，
        任務表的狀態將由CrawlerTaskService定期從歷史記錄中同步。
        
        Args:
            task_id: 任務 ID
            success: 執行是否成功
            message: 執行結果消息
        """
        # 僅記錄狀態更新，但不實際執行更新
        logger.debug(f"任務狀態已更新 (ID={task_id}): success={success}, message='{message}'")
        # 具體的任務狀態更新將通過歷史記錄同步到任務表
