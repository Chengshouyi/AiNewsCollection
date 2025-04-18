from typing import List, Optional, Dict, Any, Type, TypeVar, Tuple, cast
from datetime import datetime, timezone
from pydantic import ValidationError
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.models.crawler_task_history_schema import CrawlerTaskHistoryUpdateSchema, CrawlerTaskHistoryCreateSchema
from src.database.crawler_task_history_repository import CrawlerTaskHistoryRepository
from src.database.base_repository import BaseRepository, SchemaType
from src.models.base_model import Base
from src.error.errors import DatabaseOperationError
from src.services.base_service import BaseService

import logging
# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 通用類型變數，用於泛型方法
T = TypeVar('T', bound=Base)

class CrawlerTaskHistoryService(BaseService[CrawlerTaskHistory]):
    """CrawlerTaskHistory 的Service"""
    
    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    def _get_repository_mapping(self) -> Dict[str, Tuple[Type[BaseRepository], Type[Base]]]:
        """提供儲存庫映射"""
        return {
            'CrawlerTaskHistory': (CrawlerTaskHistoryRepository, CrawlerTaskHistory)
        }

    def validate_history_data(self, data: Dict[str, Any], is_update: bool = False) -> Dict[str, Any]:
        """驗證歷史記錄資料
        
        Args:
            data: 要驗證的資料
            is_update: 是否為更新操作
            
        Returns:
            Dict[str, Any]: 驗證後的資料
        """
        schema_type = SchemaType.UPDATE if is_update else SchemaType.CREATE
        return self.validate_data('CrawlerTaskHistory', data, schema_type)

    def get_all_histories(self, limit: Optional[int] = None, offset: Optional[int] = None, 
                          sort_by: Optional[str] = None, sort_desc: bool = True) -> Dict[str, Any]:
        """獲取所有歷史記錄"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'histories': []
                    }
                histories = history_repo.get_all(
                    limit=limit,
                    offset=offset,
                    sort_by=sort_by,
                    sort_desc=sort_desc
                )
                return {
                    'success': True,
                    'message': '獲取所有歷史記錄成功',
                    'histories': histories
                }
        except Exception as e:
            error_msg = f"獲取所有歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'histories': []
            }
    
    def get_successful_histories(self) -> Dict[str, Any]:
        """獲取所有成功的歷史記錄"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'histories': []
                    }
                histories = history_repo.find_successful_histories()
                return {
                    'success': True,
                    'message': '獲取成功的歷史記錄成功',
                    'histories': histories
                }
        except Exception as e:
            error_msg = f"獲取成功的歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'histories': []
            }
    
    def get_failed_histories(self) -> Dict[str, Any]:
        """
        獲取所有失敗的歷史記錄
        
        Returns:
            失敗的歷史記錄列表
        """
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'histories': []
                    }
                histories = history_repo.find_failed_histories()
                return {
                    'success': True,
                    'message': '獲取失敗的歷史記錄成功',
                    'histories': histories
                }
        except Exception as e:
            error_msg = f"獲取失敗的歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'histories': []
            }
    
    def get_histories_with_articles(self, min_articles: int = 1) -> Dict[str, Any]:
        """
        獲取爬取文章數量大於指定值的歷史記錄
        
        Args:
            min_articles: 最小文章數量
            
        Returns:
            符合條件的歷史記錄列表
        """
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'histories': []
                    }
                histories = history_repo.find_histories_with_articles(min_articles)
                return {
                    'success': True,
                    'message': '獲取有文章的歷史記錄成功',
                    'histories': histories
                }
        except Exception as e:
            error_msg = f"獲取有文章的歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'histories': []
            }
    

    def get_histories_by_date_range(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        根據日期範圍獲取歷史記錄
        
        Args:
            start_date: 開始日期
            end_date: 結束日期
            
        Returns:
            符合條件的歷史記錄列表
        """
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'histories': []
                    }
                histories = history_repo.find_histories_by_date_range(start_date, end_date)
                return {
                    'success': True,
                    'message': '獲取日期範圍內的歷史記錄成功',
                    'histories': histories
                }
        except Exception as e:
            error_msg = f"獲取日期範圍內的歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'histories': []
            }
    

    def get_total_articles_count(self, task_id: Optional[int] = None) -> Dict[str, Any]:
        """
        獲取總文章數量
        
        Args:
            task_id: 可選的任務ID
            
        Returns:
            總文章數量
        """
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'count': 0
                    }
                count = history_repo.get_total_articles_count(task_id)
                return {
                    'success': True,
                    'message': '獲取總文章數量成功',
                    'count': count
                }
        except Exception as e:
            error_msg = f"獲取總文章數量失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'count': 0
            }
    

    def get_latest_history(self, task_id: int) -> Dict[str, Any]:
        """
        獲取指定任務的最新歷史記錄
        
        Args:
            task_id: 任務ID
            
        Returns:
            最新的歷史記錄或 None
        """
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'history': None
                    }
                history = history_repo.get_latest_history(task_id)
                if history is None:
                    return {
                        'success': False,
                        'message': '無法取得最新歷史記錄',
                        'history': None
                    }
                return {
                    'success': True,
                    'message': '獲取最新歷史記錄成功',
                    'history': history
                }
        except Exception as e:
            error_msg = f"獲取最新歷史記錄失敗, 任務ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'history': None
            }
    
    def get_histories_older_than(self, days: int) -> Dict[str, Any]:
        """
        獲取超過指定天數的歷史記錄
        
        Args:
            days: 天數
            
        Returns:
            超過指定天數的歷史記錄列表
        """
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'histories': []
                    }
                histories = history_repo.get_histories_older_than(days)
                return {
                    'success': True,
                    'message': '獲取超過指定天數的歷史記錄成功',
                    'histories': histories
                }
        except Exception as e:
            error_msg = f"獲取超過{days}天的歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'histories': []
            }
        
    def update_history_status(self, history_id: int, success: bool, message: Optional[str] = None, articles_count: Optional[int] = None) -> Dict[str, Any]:
        """更新歷史記錄的狀態"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                
                # 準備更新資料
                update_data = {
                    'success': success,
                    'end_time': datetime.now(timezone.utc)
                }
                
                if message is not None:
                    update_data['message'] = message
                    
                if articles_count is not None:
                    update_data['articles_count'] = articles_count

                # 執行更新
                result = history_repo.update(history_id, update_data)
                if not result:
                    return {
                        'success': False,
                        'message': f"歷史記錄不存在，ID={history_id}",
                        'history': None
                    }
                    
                return {
                    'success': True,
                    'message': '更新歷史記錄狀態成功',
                    'history': result
                }
                
        except Exception as e:
            error_msg = f"更新歷史記錄狀態失敗, ID={history_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'history': None
            }
    
    def delete_history(self, history_id: int) -> Dict[str, Any]:
        """
        刪除歷史記錄
        
        Args:
            history_id: 歷史記錄ID
            
        Returns:
            是否成功刪除
        """
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'result': False
                    }
                result = history_repo.delete(history_id)
                if not result:
                    return {
                        'success': False,
                        'message': f"欲刪除的歷史記錄不存在，ID={history_id}",
                        'result': False
                    }
                
                return {
                    'success': True,
                    'message': f"成功刪除歷史記錄，ID={history_id}",
                    'result': True
                }
        except Exception as e:
            error_msg = f"刪除歷史記錄失敗，ID={history_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'result': False
            }
    
    def delete_old_histories(self, days: int) -> Dict[str, Any]:
        """
        刪除超過指定天數的歷史記錄
        
        Args:
            days: 天數
            
        Returns:
            包含刪除結果的字典
        """
        try:
            deleted_count = 0 # 初始化計數器
            failed_ids = [] # 初始化失敗列表

            # --- Step 1: Get IDs to delete within a transaction ---
            old_history_ids_to_delete = []
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器 (查詢階段)',
                        'resultMsg': {'deleted_count': 0, 'failed_ids': []}
                    }
                old_histories = history_repo.get_histories_older_than(days)
                old_history_ids_to_delete = [h.id for h in old_histories] # 只獲取 ID

            if not old_history_ids_to_delete:
                return {
                    "success": True,
                    "message": f"沒有超過 {days} 天的歷史記錄可刪除",
                    "resultMsg": {"deleted_count": 0, "failed_ids": []}
                }
                
            # --- Step 2: Delete IDs one by one, possibly in separate transactions ---
            # 這裡我們依然在一個 transaction 內處理，但如果需要可以分開
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                if not history_repo:
                     # 雖然不太可能，但還是加上防禦性檢查
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器 (刪除階段)',
                         'resultMsg': {'deleted_count': 0, 'failed_ids': old_history_ids_to_delete} # 將所有待刪除 ID 標記為失敗
                    }
            
                for history_id in old_history_ids_to_delete:
                    try:
                        # 在同一個 session 下執行刪除
                        success = history_repo.delete(history_id) 
                        if success:
                            deleted_count += 1
                        else:
                            # 即使在同一個 session，delete 返回 False 通常意味著 ID 不存在了
                            logger.warning(f"嘗試刪除舊歷史記錄 ID {history_id} 時發現其已不存在。")
                            # 這裡可以選擇是否將其計入 failed_ids，取決於業務邏輯
                            # failed_ids.append(history_id) 
                    except Exception as e:
                        logger.error(f"刪除歷史記錄失敗，ID={history_id}: {str(e)}")
                        failed_ids.append(history_id)
            
            # 刪除迴圈結束後 commit (由 with self._transaction() 自動處理)
            
            success = len(failed_ids) == 0 # 只有當沒有任何失敗才算完全成功
            message = (
                f"批量刪除舊歷史記錄完成: 成功刪除 {deleted_count} 條"
                f"{f', 失敗 {len(failed_ids)} 條' if failed_ids else ''}"
            )

            return {
                "success": success,
                "message": message,
                "resultMsg": {
                    "deleted_count": deleted_count,
                    "failed_ids": failed_ids,
                }
            }
        except Exception as e:
            error_msg = f"批量刪除超過 {days} 天歷史記錄的過程中發生未預期錯誤: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'resultMsg': {
                    'deleted_count': deleted_count, # 返回當前計數
                    'failed_ids': failed_ids # 返回當前失敗列表
                }
            }
