from .base_repository import BaseRepository, SchemaType
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.models.crawler_task_history_schema import CrawlerTaskHistoryCreateSchema, CrawlerTaskHistoryUpdateSchema
from typing import List, Optional, Dict, Any, Type, Literal, overload, Tuple, Union
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
import logging
from src.error.errors import ValidationError, DatabaseOperationError
# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CrawlerTaskHistoryRepository(BaseRepository['CrawlerTaskHistory']):
    """CrawlerTaskHistory 特定的Repository"""

    @classmethod
    @overload
    def get_schema_class(cls, schema_type: Literal[SchemaType.CREATE]) -> Type[CrawlerTaskHistoryCreateSchema]: ...
    
    @classmethod
    @overload
    def get_schema_class(cls, schema_type: Literal[SchemaType.UPDATE]) -> Type[CrawlerTaskHistoryUpdateSchema]: ...


    @classmethod
    def get_schema_class(cls, schema_type: SchemaType = SchemaType.CREATE) -> Type[BaseModel]:
        """獲取對應的schema類別"""
        if schema_type == SchemaType.UPDATE:
            return CrawlerTaskHistoryUpdateSchema
        elif schema_type == SchemaType.CREATE:
            return CrawlerTaskHistoryCreateSchema
        raise ValueError(f"未支援的 schema 類型: {schema_type}")
    
    def create(self, entity_data: Dict[str, Any]) -> Optional[CrawlerTaskHistory]:
        """
        創建爬蟲任務歷史記錄，先進行 Pydantic 驗證，然後調用內部創建。
        
        Args:
            entity_data: 實體資料
            
        Returns:
            創建的爬蟲任務歷史實體
        """
        try:
            # 1. 設定特定預設值
            copied_data = entity_data.copy()
            if 'start_time' not in copied_data:
                copied_data['start_time'] = datetime.now(timezone.utc)
            if 'success' not in copied_data:
                copied_data['success'] = False
            if 'articles_count' not in copied_data:
                copied_data['articles_count'] = 0
            
            # 2. 執行 Pydantic 驗證
            validated_data = self.validate_data(copied_data, SchemaType.CREATE)
            
            # 3. 將已驗證的資料傳給內部方法
            if validated_data is None:
                error_msg = "創建 CrawlerTaskHistory 時驗證步驟失敗"
                logger.error(error_msg)
                raise ValidationError(error_msg)
            else:
                return self._create_internal(validated_data)
        except ValidationError as e:
            logger.error(f"創建 CrawlerTaskHistory 驗證失敗: {e}")
            raise # 重新拋出讓 Service 層處理
        except DatabaseOperationError: # 捕捉來自 _create_internal 的錯誤
            raise # 重新拋出
        except Exception as e: # 捕捉其他意外錯誤
            logger.error(f"創建 CrawlerTaskHistory 時發生未預期錯誤: {e}", exc_info=True)
            raise DatabaseOperationError(f"創建 CrawlerTaskHistory 時發生未預期錯誤: {e}") from e
    
    def update(self, entity_id: Any, entity_data: Dict[str, Any]) -> Optional[CrawlerTaskHistory]:
        """
        更新爬蟲任務歷史記錄，先進行 Pydantic 驗證，然後調用內部更新。
        
        Args:
            entity_id: 實體ID
            entity_data: 要更新的實體資料
            
        Returns:
            更新後的爬蟲任務歷史實體，如果實體不存在則返回None
        """
        try:
            # 1. 檢查實體是否存在
            existing_entity = self.get_by_id(entity_id)
            if not existing_entity:
                logger.warning(f"更新爬蟲任務歷史記錄失敗，ID不存在: {entity_id}")
                return None
            
            # 如果更新資料為空，直接返回已存在的實體
            if not entity_data:
                return existing_entity
                
            # 2. 檢查不可更新的欄位
            copied_data = entity_data.copy()
            immutable_fields = ['id', 'task_id', 'start_time', 'created_at']
            for field in immutable_fields:
                if field in copied_data:
                    logger.warning(f"嘗試更新不可修改的欄位: {field}，該欄位將被忽略")
                    copied_data.pop(field)
            
            # 如果剩餘更新資料為空，直接返回已存在的實體
            if not copied_data:
                return existing_entity
                
            # 3. 執行 Pydantic 驗證 (獲取 update payload)
            update_payload = self.validate_data(copied_data, SchemaType.UPDATE)
            
            # 4. 將已驗證的 payload 傳給內部方法
            if update_payload is None:
                error_msg = f"更新 CrawlerTaskHistory (ID={entity_id}) 時驗證步驟失敗"
                logger.error(error_msg)
                raise ValidationError(error_msg)
            else:
                return self._update_internal(entity_id, update_payload)
        except ValidationError as e:
            logger.error(f"更新 CrawlerTaskHistory (ID={entity_id}) 驗證失敗: {e}")
            raise # 重新拋出
        except DatabaseOperationError: # 捕捉來自 _update_internal 的錯誤
            raise # 重新拋出
        except Exception as e: # 捕捉其他意外錯誤
            logger.error(f"更新 CrawlerTaskHistory (ID={entity_id}) 時發生未預期錯誤: {e}", exc_info=True)
            raise DatabaseOperationError(f"更新 CrawlerTaskHistory (ID={entity_id}) 時發生未預期錯誤: {e}") from e

    def find_by_task_id(self, task_id: int,
                        limit: Optional[int] = None,
                        offset: Optional[int] = None,
                        sort_desc: bool = False, # Keep sort_desc
                        is_preview: bool = False,
                        preview_fields: Optional[List[str]] = None
                        ) -> Union[List['CrawlerTaskHistory'], List[Dict[str, Any]]]:
        """根據任務ID查詢相關的歷史記錄，支援分頁、排序和預覽"""
        filter_criteria = {"task_id": task_id}

        # Convert limit/offset to page/per_page
        page = 1
        per_page = limit if limit is not None and limit > 0 else 10 # Default per_page
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(f"find_by_task_id: Offset ({offset}) provided but limit/per_page ({limit}) is invalid, defaulting to page 1.")
            page = 1

        total, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=page,
            per_page=per_page,
            sort_by="start_time", # Keep the original default sort
            sort_desc=sort_desc,  # Pass sort_desc
            is_preview=is_preview,
            preview_fields=preview_fields
        )
        return items # Return only the items list

    def find_successful_histories(self,
                                  limit: Optional[int] = None,
                                  offset: Optional[int] = None,
                                  is_preview: bool = False,
                                  preview_fields: Optional[List[str]] = None
                                  ) -> Union[List['CrawlerTaskHistory'], List[Dict[str, Any]]]:
        """查詢所有成功的任務歷史記錄，支援分頁和預覽"""
        filter_criteria = {"success": True}

        # Convert limit/offset to page/per_page
        page = 1
        per_page = limit if limit is not None and limit > 0 else 10 # Default per_page
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(f"find_successful_histories: Offset ({offset}) provided but limit/per_page ({limit}) is invalid, defaulting to page 1.")
            page = 1

        total, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=page,
            per_page=per_page,
            is_preview=is_preview,
            preview_fields=preview_fields
            # Default sort (created_at desc) is handled by find_paginated
        )
        return items # Return only the items list

    def find_failed_histories(self,
                              limit: Optional[int] = None,
                              offset: Optional[int] = None,
                              is_preview: bool = False,
                              preview_fields: Optional[List[str]] = None
                              ) -> Union[List['CrawlerTaskHistory'], List[Dict[str, Any]]]:
        """查詢所有失敗的任務歷史記錄，支援分頁和預覽"""
        filter_criteria = {"success": False}

        # Convert limit/offset to page/per_page
        page = 1
        per_page = limit if limit is not None and limit > 0 else 10 # Default per_page
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(f"find_failed_histories: Offset ({offset}) provided but limit/per_page ({limit}) is invalid, defaulting to page 1.")
            page = 1

        total, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=page,
            per_page=per_page,
            is_preview=is_preview,
            preview_fields=preview_fields
            # Default sort (created_at desc) is handled by find_paginated
        )
        return items # Return only the items list

    def find_histories_with_articles(self,
                                     min_articles: int = 1,
                                     limit: Optional[int] = None,
                                     offset: Optional[int] = None,
                                     is_preview: bool = False,
                                     preview_fields: Optional[List[str]] = None
                                     ) -> Union[List['CrawlerTaskHistory'], List[Dict[str, Any]]]:
        """查詢文章數量大於等於指定值的歷史記錄，支援分頁和預覽"""
        if min_articles < 0:
            raise ValueError("min_articles 不能為負數")

        filter_criteria = {"articles_count": {"$gte": min_articles}}

        # Convert limit/offset to page/per_page
        page = 1
        per_page = limit if limit is not None and limit > 0 else 10 # Default per_page
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(f"find_histories_with_articles: Offset ({offset}) provided but limit/per_page ({limit}) is invalid, defaulting to page 1.")
            page = 1

        total, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=page,
            per_page=per_page,
            is_preview=is_preview,
            preview_fields=preview_fields
            # Default sort (created_at desc) is handled by find_paginated
        )
        return items # Return only the items list

    def find_histories_by_date_range(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None
    ) -> Union[List['CrawlerTaskHistory'], List[Dict[str, Any]]]:
        """根據日期範圍查詢歷史記錄，支援分頁和預覽"""
        filter_criteria: Dict[str, Any] = {}
        if start_date:
            filter_criteria["start_time"] = {"$gte": start_date}
        if end_date:
            # If start_date was also provided, merge the conditions
            if "start_time" in filter_criteria:
                filter_criteria["start_time"]["$lte"] = end_date
            else:
                filter_criteria["start_time"] = {"$lte": end_date}

        # Convert limit/offset to page/per_page
        page = 1
        per_page = limit if limit is not None and limit > 0 else 10 # Default per_page
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(f"find_histories_by_date_range: Offset ({offset}) provided but limit/per_page ({limit}) is invalid, defaulting to page 1.")
            page = 1

        total, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=page,
            per_page=per_page,
            is_preview=is_preview,
            preview_fields=preview_fields
            # Default sort (created_at desc) is handled by find_paginated
        )
        return items # Return only the items list

    def count_total_articles(self, task_id: Optional[int] = None) -> int:
        """
        獲取總文章數量
        
        :param task_id: 可選的任務ID，如果提供則只計算該任務的文章數
        :return: 文章總數
        """
        def query_builder():
            # Use query directly for aggregation
            query = self.session.query(self.model_class)
            
            if task_id is not None:
                # Ensure task_id attribute exists
                if not hasattr(self.model_class, 'task_id'):
                    raise AttributeError(f"模型 {self.model_class.__name__} 沒有 'task_id' 屬性")
                query = query.filter_by(task_id=task_id)
                
            # Ensure articles_count attribute exists
            if not hasattr(self.model_class, 'articles_count'):
                raise AttributeError(f"模型 {self.model_class.__name__} 沒有 'articles_count' 屬性")

            # Efficiently sum using SQL SUM function if possible, requires articles_count to be numeric
            # from sqlalchemy import func, cast, Integer
            # total_sum = self.session.query(func.sum(cast(self.model_class.articles_count, Integer))).select_from(query.subquery()).scalar()
            # return total_sum or 0

            # Fallback to Python sum if SQL SUM is complex or type issues arise
            # Be mindful of performance with large datasets
            histories = query.all() # This might load many objects
            return sum(int(history.articles_count or 0) for history in histories)

        # execute_query handles potential errors
        result = self.execute_query(
            query_builder,
            err_msg="獲取總文章數量時發生錯誤"
        )
        # Ensure result is an int, return 0 if query failed or returned None
        return int(result) if result is not None else 0

    def get_latest_history(self, task_id: int,
                           is_preview: bool = False,
                           preview_fields: Optional[List[str]] = None
                           ) -> Optional[Union['CrawlerTaskHistory', Dict[str, Any]]]:
        """
        獲取指定任務的最新歷史記錄 (按 start_time 降序)，支援預覽
        
        :param task_id: 任務ID
        :param is_preview: 是否預覽模式
        :param preview_fields: 預覽欄位
        :return: 最新的歷史記錄實例或字典，如果不存在則返回 None
        """
        filter_criteria = {"task_id": task_id}
        # Use find_paginated with page=1, per_page=1 to get the latest
        total, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=1,
            per_page=1,
            sort_by="start_time",
            sort_desc=True, # Sort by start_time descending
            is_preview=is_preview,
            preview_fields=preview_fields
        )
        return items[0] if items else None

    def get_histories_older_than(self, days: int,
                                 limit: Optional[int] = None,
                                 offset: Optional[int] = None,
                                 is_preview: bool = False,
                                 preview_fields: Optional[List[str]] = None
                                 ) -> Union[List['CrawlerTaskHistory'], List[Dict[str, Any]]]:
        """
        獲取超過指定天數的歷史記錄，支援分頁和預覽
        
        :param days: 天數
        :param limit: 限制數量
        :param offset: 偏移量
        :param is_preview: 是否預覽模式
        :param preview_fields: 預覽欄位
        :return: 超過指定天數的歷史記錄列表 (實例或字典)
        """
        if days < 0:
            raise ValueError("天數不能為負數")

        threshold_date = datetime.now(timezone.utc) - timedelta(days=days)
        filter_criteria = {"start_time": {"$lt": threshold_date}}

        # Convert limit/offset to page/per_page
        page = 1
        per_page = limit if limit is not None and limit > 0 else 10 # Default per_page
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(f"get_histories_older_than: Offset ({offset}) provided but limit/per_page ({limit}) is invalid, defaulting to page 1.")
            page = 1

        total, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=page,
            per_page=per_page,
            is_preview=is_preview,
            preview_fields=preview_fields
            # Default sort (created_at desc) is handled by find_paginated
        )
        return items # Return only the items list

    def update_history_status(
        self, 
        history_id: int, 
        success: bool, 
        message: Optional[str] = None, 
        articles_count: Optional[int] = None
    ) -> bool:
        """
        更新歷史記錄的狀態
        
        :param history_id: 歷史記錄ID
        :param success: 是否成功
        :param message: 可選的訊息
        :param articles_count: 可選的文章數量
        :return: 是否更新成功
        """
        try:
            # 構建更新數據
            update_data = {'success': success, 'end_time': datetime.now(timezone.utc)}
            
            if message is not None:
                update_data['message'] = message
                
            if articles_count is not None:
                update_data['articles_count'] = articles_count
                
            # 使用更新方法
            updated_entity = self.update(history_id, update_data)
            logger.debug(f"更新歷史記錄狀態已完成，等待提交: {updated_entity}")
            return updated_entity is not None
        except Exception as e:
            logger.error(f"更新歷史記錄狀態時發生錯誤: {e}")
            return False

    def get_latest_by_task_id(self, task_id: int,
                              is_preview: bool = False,
                              preview_fields: Optional[List[str]] = None
                              ) -> Optional[Union['CrawlerTaskHistory', Dict[str, Any]]]:
        """獲取指定任務的最新一筆歷史記錄 (按 created_at 降序)，支援預覽"""
        filter_criteria = {"task_id": task_id}
        # Use find_paginated with page=1, per_page=1 to get the latest
        total, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=1,
            per_page=1,
            sort_by="created_at", # Sort by creation time as per original logic
            sort_desc=True,
            is_preview=is_preview,
            preview_fields=preview_fields
        )
        return items[0] if items else None 