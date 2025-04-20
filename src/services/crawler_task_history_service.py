from typing import List, Optional, Dict, Any, Type, TypeVar, Tuple, cast, Union
from datetime import datetime, timezone
from pydantic import ValidationError
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.models.crawler_task_history_schema import CrawlerTaskHistoryReadSchema, PaginatedCrawlerTaskHistoryResponse, CrawlerTaskHistoryUpdateSchema, CrawlerTaskHistoryCreateSchema
from src.database.crawler_task_history_repository import CrawlerTaskHistoryRepository
from src.database.base_repository import BaseRepository, SchemaType
from src.models.base_model import Base
from src.error.errors import DatabaseOperationError, InvalidOperationError
from src.services.base_service import BaseService
from sqlalchemy.orm.attributes import instance_state

import logging
# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 通用類型變數，用於泛型方法
T = TypeVar('T', bound=Base)
# 定義返回類型
# -- Repository 返回類型別名 --
RepoHistoryListResult = Union[List['CrawlerTaskHistory'], List[Dict[str, Any]]]
RepoHistorySingleResult = Union['CrawlerTaskHistory', Dict[str, Any], None]
# -- Service 層最終返回類型別名 --
HistoryListResult = Union[List[CrawlerTaskHistoryReadSchema], List[Dict[str, Any]]]
HistorySingleResult = Union[CrawlerTaskHistoryReadSchema, Dict[str, Any], None]

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

    def find_all_histories(self, limit: Optional[int] = None, offset: Optional[int] = None, 
                           sort_by: Optional[str] = None, sort_desc: bool = True,
                           is_preview: bool = False, preview_fields: Optional[List[str]] = None
                           ) -> Dict[str, Any]:
        """查找所有歷史記錄，返回包含列表的字典 (根據 is_preview 決定類型)"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                # -- 使用 RepoHistoryListResult --
                histories_result: RepoHistoryListResult = history_repo.find_all(
                    limit=limit,
                    offset=offset,
                    sort_by=sort_by,
                    sort_desc=sort_desc,
                    is_preview=is_preview,
                    preview_fields=preview_fields
                )

                # -- histories_response 的類型是 HistoryListResult --
                histories_response: HistoryListResult
                if is_preview:
                     # 當 is_preview 為 True 時，histories_result 是 List[Dict[str, Any]]
                     # 這與 HistoryListResult 的一部分兼容
                     histories_response = cast(List[Dict[str, Any]], histories_result)
                else:
                     # 當 is_preview 為 False 時，histories_result 是 List[CrawlerTaskHistory]
                     orm_list = cast(List[CrawlerTaskHistory], histories_result)
                     # 轉換後符合 HistoryListResult 的 List[CrawlerTaskHistoryReadSchema]
                     histories_response = [CrawlerTaskHistoryReadSchema.model_validate(h) for h in orm_list]

                return {
                    'success': True,
                    'message': '獲取所有歷史記錄成功',
                    'histories': histories_response
                }
        except InvalidOperationError as e:
             error_msg = f"獲取所有歷史記錄失敗: {str(e)}"
             logger.error(error_msg)
             return {'success': False, 'message': error_msg, 'histories': []}
        except Exception as e:
            error_msg = f"獲取所有歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'histories': []
            }
    
    def find_successful_histories(self, limit: Optional[int] = None, offset: Optional[int] = None,
                                 is_preview: bool = False, preview_fields: Optional[List[str]] = None
                                 ) -> Dict[str, Any]:
        """查找所有成功的歷史記錄，返回包含列表的字典 (根據 is_preview 決定類型)"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                # -- 使用 RepoHistoryListResult --
                histories_result: RepoHistoryListResult = history_repo.find_successful_histories(
                    limit=limit, offset=offset, is_preview=is_preview, preview_fields=preview_fields
                )

                # -- histories_response 的類型是 HistoryListResult --
                histories_response: HistoryListResult
                if is_preview:
                    histories_response = cast(List[Dict[str, Any]], histories_result)
                else:
                    orm_list = cast(List[CrawlerTaskHistory], histories_result)
                    histories_response = [CrawlerTaskHistoryReadSchema.model_validate(h) for h in orm_list]

                return {
                    'success': True,
                    'message': '獲取成功的歷史記錄成功',
                    'histories': histories_response
                }
        except Exception as e:
            error_msg = f"獲取成功的歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'histories': []
            }
    
    def find_failed_histories(self, limit: Optional[int] = None, offset: Optional[int] = None,
                             is_preview: bool = False, preview_fields: Optional[List[str]] = None
                             ) -> Dict[str, Any]:
        """查找所有失敗的歷史記錄，返回包含列表的字典 (根據 is_preview 決定類型)"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                # -- 使用 RepoHistoryListResult --
                histories_result: RepoHistoryListResult = history_repo.find_failed_histories(
                    limit=limit, offset=offset, is_preview=is_preview, preview_fields=preview_fields
                )

                # -- histories_response 的類型是 HistoryListResult --
                histories_response: HistoryListResult
                if is_preview:
                    histories_response = cast(List[Dict[str, Any]], histories_result)
                else:
                    orm_list = cast(List[CrawlerTaskHistory], histories_result)
                    histories_response = [CrawlerTaskHistoryReadSchema.model_validate(h) for h in orm_list]

                return {
                    'success': True,
                    'message': '獲取失敗的歷史記錄成功',
                    'histories': histories_response
                }
        except Exception as e:
            error_msg = f"獲取失敗的歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'histories': []
            }
    
    def find_histories_with_articles(self, min_articles: int = 1, limit: Optional[int] = None, offset: Optional[int] = None,
                                    is_preview: bool = False, preview_fields: Optional[List[str]] = None
                                    ) -> Dict[str, Any]:
        """查找爬取文章數量大於指定值的歷史記錄，返回包含列表的字典 (根據 is_preview 決定類型)"""
        if min_articles < 0:
             return {'success': False, 'message': 'min_articles 不能為負數', 'histories': []}
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                # -- 使用 RepoHistoryListResult --
                histories_result: RepoHistoryListResult = history_repo.find_histories_with_articles(
                    min_articles, limit=limit, offset=offset, is_preview=is_preview, preview_fields=preview_fields
                )

                # -- histories_response 的類型是 HistoryListResult --
                histories_response: HistoryListResult
                if is_preview:
                    histories_response = cast(List[Dict[str, Any]], histories_result)
                else:
                    orm_list = cast(List[CrawlerTaskHistory], histories_result)
                    histories_response = [CrawlerTaskHistoryReadSchema.model_validate(h) for h in orm_list]

                return {
                    'success': True,
                    'message': '獲取有文章的歷史記錄成功',
                    'histories': histories_response
                }
        except Exception as e:
            error_msg = f"獲取有文章的歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'histories': []
            }
    

    def find_histories_by_date_range(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None,
                                    limit: Optional[int] = None, offset: Optional[int] = None,
                                    is_preview: bool = False, preview_fields: Optional[List[str]] = None
                                    ) -> Dict[str, Any]:
        """根據日期範圍查找歷史記錄，返回包含列表的字典 (根據 is_preview 決定類型)"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                # -- 使用 RepoHistoryListResult --
                histories_result: RepoHistoryListResult = history_repo.find_histories_by_date_range(
                    start_date, end_date, limit=limit, offset=offset, is_preview=is_preview, preview_fields=preview_fields
                )

                # -- histories_response 的類型是 HistoryListResult --
                histories_response: HistoryListResult
                if is_preview:
                     histories_response = cast(List[Dict[str, Any]], histories_result)
                else:
                     orm_list = cast(List[CrawlerTaskHistory], histories_result)
                     histories_response = [CrawlerTaskHistoryReadSchema.model_validate(h) for h in orm_list]

                return {
                    'success': True,
                    'message': '獲取日期範圍內的歷史記錄成功',
                    'histories': histories_response
                }
        except Exception as e:
            error_msg = f"獲取日期範圍內的歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'histories': []
            }
    
    def find_histories_paginated(self, page: int, per_page: int, task_id: Optional[int] = None,
                                success: Optional[bool] = None, start_date: Optional[datetime] = None,
                                end_date: Optional[datetime] = None, sort_by: Optional[str] = None,
                                sort_desc: bool = True, is_preview: bool = False,
                                preview_fields: Optional[List[str]] = None
                                ) -> Dict[str, Any]:
        """分頁查找歷史記錄，返回包含分頁資訊和結果列表的字典 (根據 is_preview 決定列表類型)"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))

                filter_criteria = {}
                if task_id is not None:
                    filter_criteria['task_id'] = task_id
                if success is not None:
                    filter_criteria['success'] = success
                 # 注意：BaseRepository._apply_filters 使用的是 MongoDB 風格的操作符
                date_filter = {}
                if start_date is not None:
                    date_filter['$gte'] = start_date
                if end_date is not None:
                    date_filter['$lte'] = end_date
                if date_filter:
                    filter_criteria['start_time'] = date_filter # 假設基於 start_time 過濾

                # 使用 find_paginated
                repo_result: Dict[str, Any] = history_repo.find_paginated(
                    filter_criteria=filter_criteria,
                    page=page,
                    per_page=per_page,
                    sort_by=sort_by,
                    sort_desc=sort_desc,
                    is_preview=is_preview,
                    preview_fields=preview_fields
                )

                items_result: HistoryListResult = repo_result.get('items', [])
                items_response: HistoryListResult

                if is_preview:
                     items_response = items_result # 直接使用 dict list
                else:
                    # 確保 items_result 是 ORM 對象列表
                    orm_list = cast(List[CrawlerTaskHistory], items_result)
                    items_response = [CrawlerTaskHistoryReadSchema.model_validate(item) for item in orm_list]

                # 返回包含分頁資訊和結果列表的字典
                paginated_data = {
                    "items": items_response,
                    "page": repo_result.get("page", 1),
                    "per_page": repo_result.get("per_page", per_page),
                    "total": repo_result.get("total", 0),
                    "total_pages": repo_result.get("total_pages", 0),
                    "has_next": repo_result.get("has_next", False),
                    "has_prev": repo_result.get("has_prev", False)
                }

                return {
                    'success': True,
                    'message': '分頁獲取歷史記錄成功',
                    'resultMsg': paginated_data # 將分頁結果包在 resultMsg 中
                }
        except InvalidOperationError as e: # 捕獲分頁參數或排序欄位錯誤
             error_msg = f"分頁獲取歷史記錄失敗: {str(e)}"
             logger.error(error_msg)
             return {'success': False, 'message': error_msg, 'resultMsg': None}
        except Exception as e:
            error_msg = f"分頁獲取歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'resultMsg': None
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
                count = history_repo.count_total_articles(task_id)
                return {
                    'success': True,
                    'message': '獲取總文章數量成功',
                    'count': count
                }
        except AttributeError as e:
             error_msg = f"獲取總文章數量失敗: {str(e)}"
             logger.error(error_msg)
             return {'success': False, 'message': error_msg, 'count': 0}
        except Exception as e:
            error_msg = f"獲取總文章數量失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'count': 0
            }
    

    def find_latest_history(self, task_id: int,
                           is_preview: bool = False, preview_fields: Optional[List[str]] = None
                           ) -> Dict[str, Any]:
        """查找指定任務的最新歷史記錄，返回包含單個結果的字典 (根據 is_preview 決定類型)"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                # -- 使用 RepoHistorySingleResult --
                history_result: RepoHistorySingleResult = history_repo.get_latest_history(
                    task_id, is_preview=is_preview, preview_fields=preview_fields
                )

                if history_result is None:
                    return {
                        'success': False,
                        'message': f'任務ID {task_id} 的最新歷史記錄不存在',
                        'history': None
                    }

                # -- history_response 的類型是 HistorySingleResult --
                history_response: HistorySingleResult
                if is_preview:
                    # history_result 是 Dict[str, Any]，兼容 HistorySingleResult
                    history_response = cast(Dict[str, Any], history_result)
                else:
                    # history_result 是 CrawlerTaskHistory
                    orm_obj = cast(CrawlerTaskHistory, history_result)
                    # 轉換後是 CrawlerTaskHistoryReadSchema，兼容 HistorySingleResult
                    history_response = CrawlerTaskHistoryReadSchema.model_validate(orm_obj)

                return {
                    'success': True,
                    'message': '獲取最新歷史記錄成功',
                    'history': history_response
                }
        except Exception as e:
            error_msg = f"獲取最新歷史記錄失敗, 任務ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'history': None
            }
    
    def find_histories_older_than(self, days: int, limit: Optional[int] = None, offset: Optional[int] = None,
                                 is_preview: bool = False, preview_fields: Optional[List[str]] = None
                                 ) -> Dict[str, Any]:
        """查找超過指定天數的歷史記錄，返回包含列表的字典 (根據 is_preview 決定類型)"""
        if days < 0:
             return {'success': False, 'message': '天數不能為負數', 'histories': []}
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                 # Repository 方法已支持 is_preview, preview_fields
                 # -- 使用 RepoHistoryListResult --
                histories_result: RepoHistoryListResult = history_repo.get_histories_older_than(
                    days, limit=limit, offset=offset, is_preview=is_preview, preview_fields=preview_fields
                )

                # -- histories_response 的類型是 HistoryListResult --
                histories_response: HistoryListResult
                if is_preview:
                     histories_response = cast(List[Dict[str, Any]], histories_result)
                else:
                     orm_list = cast(List[CrawlerTaskHistory], histories_result)
                     histories_response = [CrawlerTaskHistoryReadSchema.model_validate(h) for h in orm_list]

                return {
                    'success': True,
                    'message': '獲取超過指定天數的歷史記錄成功',
                    'histories': histories_response
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
        """更新歷史記錄的狀態，返回包含 CrawlerTaskHistoryReadSchema 的字典"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                
                existing_history_orm = history_repo.get_by_id(history_id)
                if not existing_history_orm:
                     return {
                        'success': False,
                        'message': f"歷史記錄不存在，ID={history_id}",
                        'history': None
                    }

                update_data = {
                    'success': success,
                    'end_time': datetime.now(timezone.utc)
                }
                
                if message is not None:
                    update_data['message'] = message
                    
                if articles_count is not None:
                    update_data['articles_count'] = articles_count

                try:
                    updated_history_orm = history_repo.update(history_id, update_data)
                except (ValidationError, DatabaseOperationError) as e:
                    error_msg = f"更新歷史記錄狀態失敗 (驗證或DB), ID={history_id}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    session.refresh(existing_history_orm)
                    history_schema = CrawlerTaskHistoryReadSchema.model_validate(existing_history_orm)
                    return {'success': False, 'message': error_msg, 'history': history_schema}

                if updated_history_orm:
                    history_schema = CrawlerTaskHistoryReadSchema.model_validate(updated_history_orm)
                    return {
                        'success': True,
                        'message': '更新歷史記錄狀態成功',
                        'history': history_schema
                    }
                else:
                    logger.warning(f"更新歷史記錄狀態 ID={history_id} 時 repo.update 返回 None，可能無變更。")
                    session.refresh(existing_history_orm)
                    history_schema = CrawlerTaskHistoryReadSchema.model_validate(existing_history_orm)
                    return {
                        'success': True,
                        'message': '更新歷史記錄狀態操作完成 (無實際變更)',
                        'history': history_schema
                    }
                
        except Exception as e:
            error_msg = f"更新歷史記錄狀態時發生未預期錯誤, ID={history_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            current_history_result = self.get_history_by_id(history_id)
            return {
                'success': False,
                'message': error_msg,
                'history': current_history_result.get('history') if current_history_result else None
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
                result = history_repo.delete(history_id)

                if result:
                     return {
                        'success': True,
                        'message': f"成功刪除歷史記錄，ID={history_id}",
                        'result': True
                     }
                else:
                    return {
                        'success': False,
                        'message': f"欲刪除的歷史記錄不存在或刪除失敗，ID={history_id}",
                        'result': False
                    }
        except DatabaseOperationError as e:
            error_msg = f"刪除歷史記錄失敗 (資料庫約束或操作錯誤)，ID={history_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'result': False}
        except Exception as e:
            error_msg = f"刪除歷史記錄時發生未預期錯誤，ID={history_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'result': False
            }
    
    def delete_old_histories(self, days: int) -> Dict[str, Any]:
        """
        刪除超過指定天數的歷史記錄 (修正事務處理邏輯)

        Args:
            days: 天數

        Returns:
            包含刪除結果的字典
        """
        if days < 0:
             return {'success': False, 'message': '天數不能為負數', 'resultMsg': {'deleted_count': 0, 'failed_ids': []}}

        deleted_count = 0
        failed_ids = []
        old_history_ids_to_delete = []

        try:
            # 階段一：查詢需要刪除的 ID 列表
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                # -- 預期 is_preview=True 返回 List[Dict[str, Any]] --
                # -- 直接使用 cast 來告知類型檢查器 --
                old_histories_preview_dicts: List[Dict[str, Any]] = cast(
                    List[Dict[str, Any]],
                    history_repo.get_histories_older_than(
                        days, limit=None, offset=None, is_preview=True, preview_fields=['id']
                    )
                )
                # -- 檢查返回的是否真的是字典列表 (運行時檢查) --
                if not isinstance(old_histories_preview_dicts, list) or not all(isinstance(item, dict) for item in old_histories_preview_dicts):
                    logger.error(f"get_histories_older_than(is_preview=True) 未返回預期的 List[Dict[str, Any]]，實際返回: {type(old_histories_preview_dicts)}")
                    raise TypeError("獲取舊歷史記錄 ID 列表時類型不符")
                
                old_history_ids_to_delete = [h['id'] for h in old_histories_preview_dicts if 'id' in h]

            if not old_history_ids_to_delete:
                return {
                    "success": True,
                    "message": f"沒有超過 {days} 天的歷史記錄可刪除",
                    "resultMsg": {"deleted_count": 0, "failed_ids": []}
                }

            # 階段二：執行刪除 (保持不變)
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))

                for history_id in old_history_ids_to_delete:
                    try:
                        success = history_repo.delete(history_id)
                        if success:
                            deleted_count += 1
                        else:
                            # 如果 delete 返回 False，記錄為失敗（可能記錄剛好被其他操作刪除）
                            logger.warning(f"嘗試刪除舊歷史記錄 ID {history_id} 時 delete 返回 False。")
                            failed_ids.append(history_id)
                    except DatabaseOperationError as db_err: # 捕獲資料庫約束等錯誤
                         logger.error(f"刪除歷史記錄 ID={history_id} 時發生資料庫錯誤: {str(db_err)}")
                         failed_ids.append(history_id)
                         # 不在此處 rollback，讓外層事務處理
                    except Exception as e:
                        logger.error(f"刪除歷史記錄時發生未預期錯誤，ID={history_id}: {str(e)}")
                        failed_ids.append(history_id)
                        # 不在此處 rollback

                # 外層的 _transaction() context manager 會在結束時
                # commit 所有成功的刪除操作。如果過程中發生未被捕獲的異常，
                # context manager 會執行 rollback。

            # 階段三：匯總結果
            final_success = len(failed_ids) == 0
            message = (
                f"批量刪除舊歷史記錄完成: 成功刪除 {deleted_count} 條"
                f"{f', 失敗 {len(failed_ids)} 條' if failed_ids else ''}"
            )

            return {
                "success": final_success,
                "message": message,
                "resultMsg": {
                    "deleted_count": deleted_count,
                    "failed_ids": list(set(failed_ids)), # 去重
                }
            }
        except TypeError as e:
            # 捕獲上面可能的 TypeError
            error_msg = f"批量刪除舊歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'resultMsg': {'deleted_count': deleted_count, 'failed_ids': failed_ids}
            }
        except Exception as e:
            # 這個 Exception 塊捕獲階段一或階段二中未被內部 try-except 捕獲的錯誤
            # 或者 _transaction() context manager 本身的錯誤
            error_msg = f"批量刪除超過 {days} 天歷史記錄的過程中發生未預期錯誤: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # 返回當前統計的數據，並將所有未處理的 ID 視為失敗
            processed_ids = deleted_count + len(failed_ids)
            remaining_ids = old_history_ids_to_delete[processed_ids:]
            all_failed_ids = list(set(failed_ids + remaining_ids))

            return {
                'success': False,
                'message': error_msg,
                'resultMsg': {
                    'deleted_count': deleted_count,
                    'failed_ids': all_failed_ids
                }
            }

    def get_history_by_id(self, history_id: int) -> Dict[str, Any]:
        """根據 ID 查找歷史記錄，返回包含 CrawlerTaskHistoryReadSchema 的字典"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                history_orm = history_repo.get_by_id(history_id)
                if history_orm:
                    history_schema = CrawlerTaskHistoryReadSchema.model_validate(history_orm)
                    return {
                        'success': True,
                        'message': '獲取歷史記錄成功',
                        'history': history_schema
                    }
                return {
                    'success': False,
                    'message': f'歷史記錄不存在, ID={history_id}',
                    'history': None
                }
        except DatabaseOperationError as e:
            error_msg = f"獲取歷史記錄 ID={history_id} 時資料庫操作失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'history': None}
        except Exception as e:
            error_msg = f"獲取歷史記錄失敗, ID={history_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'history': None
            }

    def create_history(self, history_data: Dict[str, Any]) -> Dict[str, Any]:
        """創建新的歷史記錄，返回包含 CrawlerTaskHistoryReadSchema 的字典"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                
                new_history_orm = history_repo.create(history_data)
                
                if new_history_orm:
                    session.flush()
                    session.refresh(new_history_orm)
                    history_schema = CrawlerTaskHistoryReadSchema.model_validate(new_history_orm)
                    return {
                        'success': True,
                        'message': '歷史記錄創建成功',
                        'history': history_schema
                    }
                else:
                    return {
                        'success': False,
                        'message': '歷史記錄創建失敗 (Repository 返回 None)',
                        'history': None
                    }

        except ValidationError as e:
            error_msg = f"創建歷史記錄時資料驗證失敗: {str(e)}"
            logger.error(error_msg, exc_info=False)
            return {'success': False, 'message': error_msg, 'history': None}
        except DatabaseOperationError as e:
            error_msg = f"創建歷史記錄時資料庫操作失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'history': None}
        except Exception as e:
            error_msg = f"創建歷史記錄時發生未預期錯誤: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'history': None
            }

    def update_history(self, history_id: int, history_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新歷史記錄，返回包含 CrawlerTaskHistoryReadSchema 的字典"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                
                updated_history_orm = history_repo.update(history_id, history_data)
                
                if updated_history_orm:
                    history_schema = CrawlerTaskHistoryReadSchema.model_validate(updated_history_orm)
                    return {
                        'success': True,
                        'message': '歷史記錄更新成功',
                        'history': history_schema
                    }
                else:
                    existing_orm = history_repo.get_by_id(history_id)
                    if not existing_orm:
                         return {'success': False, 'message': f'歷史記錄不存在，ID={history_id}', 'history': None}
                    else:
                         history_schema = CrawlerTaskHistoryReadSchema.model_validate(existing_orm)
                         return {
                            'success': True,
                            'message': '歷史記錄更新操作完成 (無實際變更)',
                            'history': history_schema
                         }

        except ValidationError as e:
            error_msg = f"更新歷史記錄 ID={history_id} 時資料驗證失敗: {str(e)}"
            logger.error(error_msg, exc_info=False)
            current_history_result = self.get_history_by_id(history_id)
            return {'success': False, 'message': error_msg, 'history': current_history_result.get('history')}
        except DatabaseOperationError as e:
            error_msg = f"更新歷史記錄 ID={history_id} 時資料庫操作失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'history': None}
        except Exception as e:
            error_msg = f"更新歷史記錄失敗, ID={history_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'history': None
            }
