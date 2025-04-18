from typing import List, Optional, Dict, Any, Type, TypeVar, Tuple, cast
from datetime import datetime, timezone
from pydantic import ValidationError
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.models.crawler_task_history_schema import CrawlerTaskHistoryReadSchema, PaginatedCrawlerTaskHistoryResponse, CrawlerTaskHistoryUpdateSchema, CrawlerTaskHistoryCreateSchema
from src.database.crawler_task_history_repository import CrawlerTaskHistoryRepository
from src.database.base_repository import BaseRepository, SchemaType
from src.models.base_model import Base
from src.error.errors import DatabaseOperationError
from src.services.base_service import BaseService
from sqlalchemy.orm.attributes import instance_state

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
        """獲取所有歷史記錄，返回包含 CrawlerTaskHistoryReadSchema 列表的字典"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'histories': []
                    }
                histories_orm = history_repo.get_all(
                    limit=limit,
                    offset=offset,
                    sort_by=sort_by,
                    sort_desc=sort_desc
                )
                histories_schema = [CrawlerTaskHistoryReadSchema.model_validate(h) for h in histories_orm]
                return {
                    'success': True,
                    'message': '獲取所有歷史記錄成功',
                    'histories': histories_schema
                }
        except Exception as e:
            error_msg = f"獲取所有歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'histories': []
            }
    
    def get_successful_histories(self, limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        """獲取所有成功的歷史記錄，返回包含 CrawlerTaskHistoryReadSchema 列表的字典"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'histories': []
                    }
                histories_orm = history_repo.find_successful_histories(limit=limit, offset=offset)
                histories_schema = [CrawlerTaskHistoryReadSchema.model_validate(h) for h in histories_orm]
                return {
                    'success': True,
                    'message': '獲取成功的歷史記錄成功',
                    'histories': histories_schema
                }
        except Exception as e:
            error_msg = f"獲取成功的歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'histories': []
            }
    
    def get_failed_histories(self, limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        """獲取所有失敗的歷史記錄，返回包含 CrawlerTaskHistoryReadSchema 列表的字典"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'histories': []
                    }
                histories_orm = history_repo.find_failed_histories(limit=limit, offset=offset)
                histories_schema = [CrawlerTaskHistoryReadSchema.model_validate(h) for h in histories_orm]
                return {
                    'success': True,
                    'message': '獲取失敗的歷史記錄成功',
                    'histories': histories_schema
                }
        except Exception as e:
            error_msg = f"獲取失敗的歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'histories': []
            }
    
    def get_histories_with_articles(self, min_articles: int = 1, limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        """獲取爬取文章數量大於指定值的歷史記錄，返回包含 CrawlerTaskHistoryReadSchema 列表的字典"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'histories': []
                    }
                histories_orm = history_repo.find_histories_with_articles(min_articles, limit=limit, offset=offset)
                histories_schema = [CrawlerTaskHistoryReadSchema.model_validate(h) for h in histories_orm]
                return {
                    'success': True,
                    'message': '獲取有文章的歷史記錄成功',
                    'histories': histories_schema
                }
        except Exception as e:
            error_msg = f"獲取有文章的歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'histories': []
            }
    

    def get_histories_by_date_range(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        """根據日期範圍獲取歷史記錄，返回包含 CrawlerTaskHistoryReadSchema 列表的字典"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'histories': []
                    }
                histories_orm = history_repo.find_histories_by_date_range(start_date, end_date, limit=limit, offset=offset)
                histories_schema = [CrawlerTaskHistoryReadSchema.model_validate(h) for h in histories_orm]
                return {
                    'success': True,
                    'message': '獲取日期範圍內的歷史記錄成功',
                    'histories': histories_schema
                }
        except Exception as e:
            error_msg = f"獲取日期範圍內的歷史記錄失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'histories': []
            }
    
    def get_histories_paginated(self, page: int, per_page: int, task_id: Optional[int] = None, success: Optional[bool] = None, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, sort_by: Optional[str] = None, sort_desc: bool = True) -> Dict[str, Any]:
        """分頁獲取歷史記錄，返回包含 PaginatedCrawlerTaskHistoryResponse 的字典"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'resultMsg': None
                    }
                
                filter_criteria = {}
                if task_id is not None:
                    filter_criteria['task_id'] = task_id
                if success is not None:
                    filter_criteria['success'] = success
                if start_date is not None:
                    filter_criteria['start_date'] = start_date
                if end_date is not None:
                     filter_criteria['end_date'] = end_date

                repo_result: Dict[str, Any] = history_repo.get_paginated(
                    filter_criteria, page, per_page, sort_by, sort_desc
                )
                
                if not repo_result or 'items' not in repo_result:
                    return {
                        'success': False,
                        'message': '分頁獲取歷史記錄失敗 (內部錯誤或無數據)',
                        'resultMsg': None
                    }

                items_orm = repo_result.get('items', [])
                items_schema = [CrawlerTaskHistoryReadSchema.model_validate(item) for item in items_orm]
                
                paginated_response = PaginatedCrawlerTaskHistoryResponse(
                    items=items_schema,
                    page=repo_result.get("page", 1),
                    per_page=repo_result.get("per_page", per_page),
                    total=repo_result.get("total", 0),
                    total_pages=repo_result.get("total_pages", 0),
                    has_next=repo_result.get("has_next", False),
                    has_prev=repo_result.get("has_prev", False)
                )

                return {
                    'success': True,
                    'message': '分頁獲取歷史記錄成功',
                    'resultMsg': paginated_response
                }
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
        """獲取指定任務的最新歷史記錄，返回包含 CrawlerTaskHistoryReadSchema 的字典"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'history': None
                    }
                history_orm = history_repo.get_latest_history(task_id)
                if history_orm is None:
                    return {
                        'success': False,
                        'message': '無法取得最新歷史記錄',
                        'history': None
                    }
                history_schema = CrawlerTaskHistoryReadSchema.model_validate(history_orm)
                return {
                    'success': True,
                    'message': '獲取最新歷史記錄成功',
                    'history': history_schema
                }
        except Exception as e:
            error_msg = f"獲取最新歷史記錄失敗, 任務ID={task_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'history': None
            }
    
    def get_histories_older_than(self, days: int, limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        """獲取超過指定天數的歷史記錄，返回包含 CrawlerTaskHistoryReadSchema 列表的字典"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'histories': []
                    }
                histories_orm = history_repo.get_histories_older_than(days, limit=limit, offset=offset)
                histories_schema = [CrawlerTaskHistoryReadSchema.model_validate(h) for h in histories_orm]
                return {
                    'success': True,
                    'message': '獲取超過指定天數的歷史記錄成功',
                    'histories': histories_schema
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
                    validated_data = self.validate_data('CrawlerTaskHistory', update_data, SchemaType.UPDATE)
                except ValidationError as e:
                    error_msg = f"更新歷史記錄狀態時資料驗證失敗, ID={history_id}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    existing_history_schema = CrawlerTaskHistoryReadSchema.model_validate(existing_history_orm)
                    return {'success': False, 'message': error_msg, 'history': existing_history_schema}

                updated_history_orm = history_repo.update(history_id, validated_data)
                
                if updated_history_orm:
                    session.flush()
                    session.refresh(updated_history_orm)
                    history_schema = CrawlerTaskHistoryReadSchema.model_validate(updated_history_orm)
                    return {
                        'success': True,
                        'message': '更新歷史記錄狀態成功',
                        'history': history_schema
                    }
                else:
                    logger.warning(f"更新歷史記錄狀態 ID={history_id} 時 repo.update 返回 None 或 False，可能無變更或更新失敗。")
                    session.refresh(existing_history_orm)
                    history_schema = CrawlerTaskHistoryReadSchema.model_validate(existing_history_orm)
                    return {
                        'success': True,
                        'message': '更新歷史記錄狀態操作完成 (可能無實際變更)',
                        'history': history_schema
                    }
                
        except DatabaseOperationError as e:
            error_msg = f"更新歷史記錄狀態時資料庫操作失敗, ID={history_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'history': None}
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
            deleted_count = 0
            failed_ids = []

            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器 (查詢階段)',
                        'resultMsg': {'deleted_count': 0, 'failed_ids': []}
                    }
                old_histories = history_repo.get_histories_older_than(days, limit=None, offset=None)
                old_history_ids_to_delete = [h.id for h in old_histories]

            if not old_history_ids_to_delete:
                return {
                    "success": True,
                    "message": f"沒有超過 {days} 天的歷史記錄可刪除",
                    "resultMsg": {"deleted_count": 0, "failed_ids": []}
                }
                
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器 (刪除階段)',
                         'resultMsg': {'deleted_count': 0, 'failed_ids': old_history_ids_to_delete}
                    }
            
                for history_id in old_history_ids_to_delete:
                    try:
                        success = history_repo.delete(history_id) 
                        if success:
                            deleted_count += 1
                        else:
                            logger.warning(f"嘗試刪除舊歷史記錄 ID {history_id} 時發現其已不存在。")
                    except Exception as e:
                        logger.error(f"刪除歷史記錄失敗，ID={history_id}: {str(e)}")
                        failed_ids.append(history_id)
            
            success = len(failed_ids) == 0
            message = (
                f"批量刪除舊歷史記錄完成: 成功刪除 {deleted_count} 條"
                f"{f', 失敗 {len(failed_ids)} 條 (包含不存在)' if failed_ids else ''}"
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
                    'deleted_count': deleted_count,
                    'failed_ids': failed_ids
                }
            }

    def get_history_by_id(self, history_id: int) -> Dict[str, Any]:
        """根據 ID 獲取歷史記錄，返回包含 CrawlerTaskHistoryReadSchema 的字典"""
        try:
            with self._transaction() as session:
                history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                if not history_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'history': None
                    }
                
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
                    'message': '歷史記錄不存在',
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
                
                validated_data = self.validate_data('CrawlerTaskHistory', history_data, SchemaType.CREATE)
                new_history_orm = history_repo.create(validated_data)
                
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
                        'message': '歷史記錄創建失敗 (未知原因)',
                        'history': None
                    }

        except ValidationError as e:
            error_msg = f"創建歷史記錄時資料驗證失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
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
                
                existing_history_orm = history_repo.get_by_id(history_id)
                if not existing_history_orm:
                    return {
                        'success': False,
                        'message': '歷史記錄不存在，無法更新',
                        'history': None
                    }

                validated_data = self.validate_data('CrawlerTaskHistory', history_data, SchemaType.UPDATE)
                updated_history_orm = history_repo.update(history_id, validated_data)
                
                if updated_history_orm:
                    session.flush()
                    session.refresh(updated_history_orm)
                    history_schema = CrawlerTaskHistoryReadSchema.model_validate(updated_history_orm)
                    return {
                        'success': True,
                        'message': '歷史記錄更新成功',
                        'history': history_schema
                    }
                else:
                    logger.warning(f"更新歷史記錄 ID={history_id} 時 repo.update 返回 None 或 False，可能無變更或更新失敗。")
                    session.refresh(existing_history_orm)
                    history_schema = CrawlerTaskHistoryReadSchema.model_validate(existing_history_orm)
                    return {
                        'success': True, 
                        'message': '歷史記錄更新操作完成 (可能無實際變更)',
                        'history': history_schema
                    }

        except ValidationError as e:
            error_msg = f"更新歷史記錄 ID={history_id} 時資料驗證失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            with self._transaction() as session:
                 history_repo = cast(CrawlerTaskHistoryRepository, self._get_repository('CrawlerTaskHistory', session))
                 existing_orm = history_repo.get_by_id(history_id)
                 existing_schema = CrawlerTaskHistoryReadSchema.model_validate(existing_orm) if existing_orm else None
            return {'success': False, 'message': error_msg, 'history': existing_schema}
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
