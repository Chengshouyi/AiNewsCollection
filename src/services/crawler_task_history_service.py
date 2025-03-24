from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import ValidationError
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.models.crawler_task_history_schema import CrawlerTaskHistoryUpdateSchema, CrawlerTaskHistoryCreateSchema
from src.database.crawler_task_history_repository import CrawlerTaskHistoryRepository
from src.database.database_manager import DatabaseManager
from src.error.errors import DatabaseOperationError

import logging
# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CrawlerTaskHistoryService:
    """爬蟲任務歷史記錄服務"""
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def _get_repository(self):
        """取得儲存庫的上下文管理器"""
        session = self.db_manager.Session()
        try:
            return CrawlerTaskHistoryRepository(session, CrawlerTaskHistory), session
        except Exception as e:
            error_msg = f"取得儲存庫失敗: {e}"
            logger.error(error_msg)
            session.close()
            raise DatabaseOperationError(error_msg) from e

    def get_all_histories(self, limit: Optional[int] = None, offset: Optional[int] = None, 
                          sort_by: Optional[str] = None, sort_desc: bool = True) -> List[CrawlerTaskHistory]:
        """
        獲取所有歷史記錄
        
        Args:
            limit: 限制返回數量
            offset: 起始偏移
            sort_by: 排序欄位
            sort_desc: 是否降序排序
            
        Returns:
            歷史記錄列表
        """
        try:
            repo, session = self._get_repository()
            histories = repo.get_all(
                limit=limit,
                offset=offset,
                sort_by=sort_by,
                sort_desc=sort_desc
            )
            return histories
        except Exception as e:
            error_msg = f"獲取所有歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e
    
    def get_successful_histories(self) -> List[CrawlerTaskHistory]:
        """
        獲取所有成功的歷史記錄
        
        Returns:
            成功的歷史記錄列表
        """
        try:
            repo, session = self._get_repository()
            histories = repo.find_successful_histories()
            return histories
        except Exception as e:
            error_msg = f"獲取成功的歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e
    
    def get_failed_histories(self) -> List[CrawlerTaskHistory]:
        """
        獲取所有失敗的歷史記錄
        
        Returns:
            失敗的歷史記錄列表
        """
        try:
            repo, session = self._get_repository()
            histories = repo.find_failed_histories()
            return histories
        except Exception as e:
            error_msg = f"獲取失敗的歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e
    
    def get_histories_with_articles(self, min_articles: int = 1) -> List[CrawlerTaskHistory]:
        """
        獲取爬取文章數量大於指定值的歷史記錄
        
        Args:
            min_articles: 最小文章數量
            
        Returns:
            符合條件的歷史記錄列表
        """
        try:
            repo, session = self._get_repository()
            histories = repo.find_histories_with_articles(min_articles)
            return histories
        except Exception as e:
            error_msg = f"獲取有文章的歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e
    
    def get_histories_by_date_range(self, start_date: Optional[datetime] = None, 
                                  end_date: Optional[datetime] = None) -> List[CrawlerTaskHistory]:
        """
        根據日期範圍獲取歷史記錄
        
        Args:
            start_date: 開始日期
            end_date: 結束日期
            
        Returns:
            符合條件的歷史記錄列表
        """
        try:
            repo, session = self._get_repository()
            histories = repo.find_histories_by_date_range(start_date, end_date)
            return histories
        except Exception as e:
            error_msg = f"獲取日期範圍內的歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e
    
    def get_total_articles_count(self, task_id: Optional[int] = None) -> int:
        """
        獲取總文章數量
        
        Args:
            task_id: 可選的任務ID
            
        Returns:
            總文章數量
        """
        try:
            repo, session = self._get_repository()
            count = repo.get_total_articles_count(task_id)
            return count
        except Exception as e:
            error_msg = f"獲取總文章數量失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e
    
    def get_latest_history(self, task_id: int) -> Optional[CrawlerTaskHistory]:
        """
        獲取指定任務的最新歷史記錄
        
        Args:
            task_id: 任務ID
            
        Returns:
            最新的歷史記錄或 None
        """
        try:
            repo, session = self._get_repository()
            history = repo.get_latest_history(task_id)
            return history
        except Exception as e:
            error_msg = f"獲取最新歷史記錄失敗, 任務ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e
    
    def get_histories_older_than(self, days: int) -> List[CrawlerTaskHistory]:
        """
        獲取超過指定天數的歷史記錄
        
        Args:
            days: 天數
            
        Returns:
            超過指定天數的歷史記錄列表
        """
        try:
            repo, session = self._get_repository()
            histories = repo.get_histories_older_than(days)
            return histories
        except Exception as e:
            error_msg = f"獲取超過{days}天的歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e
    
    def update_history_status(self, history_id: int, success: bool, 
                            message: Optional[str] = None, 
                            articles_count: Optional[int] = None) -> bool:
        """
        更新歷史記錄的狀態
        
        Args:
            history_id: 歷史記錄ID
            success: 是否成功
            message: 消息
            articles_count: 文章數量
            
        Returns:
            是否更新成功
        """
        try:
            repo, session = self._get_repository()
            
            # 準備更新資料
            update_data = {
                'success': success,
                'end_time': datetime.now()
            }
            
            if message is not None:
                update_data['message'] = message
                
            if articles_count is not None:
                update_data['articles_count'] = articles_count
            
            # 使用 Pydantic 驗證資料
            try:
                validated_data = CrawlerTaskHistoryUpdateSchema.model_validate(update_data).model_dump()
                logger.info(f"歷史記錄狀態更新資料驗證成功: {validated_data}")
            except Exception as e:
                error_msg = f"歷史記錄狀態更新資料驗證失敗: {str(e)}"
                logger.error(error_msg)
                raise ValidationError(error_msg)
            
            # 執行更新
            result = repo.update(history_id, validated_data)
            if not result:
                error_msg = f"歷史記錄狀態更新失敗，ID不存在: {history_id}"
                logger.error(error_msg)
                return False
                
            session.commit()
            log_info = f"成功更新歷史記錄狀態, ID={history_id}"
            logger.info(log_info)
            return True
            
        except ValidationError as e:
            # 重新引發驗證錯誤
            if session:
                session.rollback()
            raise e
        except Exception as e:
            error_msg = f"更新歷史記錄狀態失敗, ID={history_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if session:
                session.rollback()
            raise e
    
    def delete_history(self, history_id: int) -> bool:
        """
        刪除歷史記錄
        
        Args:
            history_id: 歷史記錄ID
            
        Returns:
            是否成功刪除
        """
        try:
            repo, session = self._get_repository()
            result = repo.delete(history_id)
            
            if not result:
                error_msg = f"欲刪除的歷史記錄不存在，ID={history_id}"
                logger.error(error_msg)
                return False
                
            session.commit()
            log_info = f"成功刪除歷史記錄，ID={history_id}"
            logger.info(log_info)
            return True
        except Exception as e:
            error_msg = f"刪除歷史記錄失敗，ID={history_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if session:
                session.rollback()
            raise e
    
    def delete_old_histories(self, days: int) -> Dict[str, Any]:
        """
        刪除超過指定天數的歷史記錄
        
        Args:
            days: 天數
            
        Returns:
            包含刪除結果的字典
        """
        try:
            repo, session = self._get_repository()
            old_histories = repo.get_histories_older_than(days)
            
            if not old_histories:
                return {
                    "success": True,
                    "deleted_count": 0,
                    "message": f"沒有超過 {days} 天的歷史記錄"
                }
            
            deleted_count = 0
            failed_ids = []
            
            for history in old_histories:
                try:
                    result = repo.delete(history.id)
                    if result:
                        deleted_count += 1
                    else:
                        failed_ids.append(history.id)
                except Exception as e:
                    logger.error(f"刪除歷史記錄失敗，ID={history.id}: {str(e)}")
                    failed_ids.append(history.id)
            
            session.commit()
            
            return {
                "success": True,
                "deleted_count": deleted_count,
                "failed_ids": failed_ids,
                "message": f"成功刪除 {deleted_count} 條歷史記錄"
            }
        except Exception as e:
            error_msg = f"批量刪除歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if session:
                session.rollback()
            raise e 