"""
定義 CrawlerTaskHistory 模型的資料庫操作 Repository。
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Type, Union, overload, Literal

from pydantic import BaseModel

from .base_repository import BaseRepository, SchemaType
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.models.crawler_task_history_schema import (
    CrawlerTaskHistoryCreateSchema,
    CrawlerTaskHistoryUpdateSchema,
)
from src.error.errors import ValidationError, DatabaseOperationError
  # 使用統一的 logger

logger = logging.getLogger(__name__)  # 使用統一的 logger  # 使用統一的 logger


class CrawlerTaskHistoryRepository(BaseRepository["CrawlerTaskHistory"]):
    """CrawlerTaskHistory 特定的Repository"""

    @classmethod
    @overload
    def get_schema_class(
        cls, schema_type: Literal[SchemaType.CREATE]
    ) -> Type[CrawlerTaskHistoryCreateSchema]: ...

    @classmethod
    @overload
    def get_schema_class(
        cls, schema_type: Literal[SchemaType.UPDATE]
    ) -> Type[CrawlerTaskHistoryUpdateSchema]: ...

    @classmethod
    def get_schema_class(
        cls, schema_type: SchemaType = SchemaType.CREATE
    ) -> Type[BaseModel]:
        """獲取對應的schema類別"""
        if schema_type == SchemaType.UPDATE:
            return CrawlerTaskHistoryUpdateSchema
        elif schema_type == SchemaType.CREATE:
            return CrawlerTaskHistoryCreateSchema
        raise ValueError(
            f"未支援的 schema 類型: {schema_type}"
        )  # 保留此處 f-string，因為是 raise 語句，非 logger

    def create(self, entity_data: Dict[str, Any]) -> Optional[CrawlerTaskHistory]:
        """
        創建爬蟲任務歷史記錄，先進行 Pydantic 驗證，然後調用內部創建。

        Args:
            entity_data: 實體資料

        Returns:
            創建的爬蟲任務歷史實體
        """
        try:
            copied_data = entity_data.copy()
            if "start_time" not in copied_data:
                copied_data["start_time"] = datetime.now(timezone.utc)
            if "success" not in copied_data:
                copied_data["success"] = False
            if "articles_count" not in copied_data:
                copied_data["articles_count"] = 0

            validated_data = self.validate_data(copied_data, SchemaType.CREATE)

            if validated_data is None:
                error_msg = "創建 CrawlerTaskHistory 時驗證步驟失敗"
                logger.error(error_msg)
                raise ValidationError(error_msg)
            else:
                return self._create_internal(validated_data)
        except ValidationError as e:
            logger.error("創建 CrawlerTaskHistory 驗證失敗: %s", e)
            raise
        except DatabaseOperationError:
            raise
        except Exception as e:
            logger.error(
                "創建 CrawlerTaskHistory 時發生未預期錯誤: %s", e, exc_info=True
            )
            raise DatabaseOperationError(
                f"創建 CrawlerTaskHistory 時發生未預期錯誤: {e}"
            ) from e

    def update(
        self, entity_id: Any, entity_data: Dict[str, Any]
    ) -> Optional[CrawlerTaskHistory]:
        """
        更新爬蟲任務歷史記錄，先進行 Pydantic 驗證，然後調用內部更新。

        Args:
            entity_id: 實體ID
            entity_data: 要更新的實體資料

        Returns:
            更新後的爬蟲任務歷史實體，如果實體不存在則返回None
        """
        try:
            existing_entity = self.get_by_id(entity_id)
            if not existing_entity:
                logger.warning("更新爬蟲任務歷史記錄失敗，ID不存在: %s", entity_id)
                return None

            if not entity_data:
                return existing_entity

            copied_data = entity_data.copy()
            immutable_fields = ["id", "task_id", "start_time", "created_at"]
            for field in immutable_fields:
                if field in copied_data:
                    logger.warning("嘗試更新不可修改的欄位: %s，該欄位將被忽略", field)
                    copied_data.pop(field)

            if not copied_data:
                return existing_entity

            update_payload = self.validate_data(copied_data, SchemaType.UPDATE)

            if update_payload is None:
                error_msg = f"更新 CrawlerTaskHistory (ID={entity_id}) 時驗證步驟失敗"  # 非 logger 輸出，保留 f-string
                logger.error(error_msg)
                raise ValidationError(error_msg)
            else:
                return self._update_internal(entity_id, update_payload)
        except ValidationError as e:
            logger.error("更新 CrawlerTaskHistory (ID=%s) 驗證失敗: %s", entity_id, e)
            raise
        except DatabaseOperationError:
            raise
        except Exception as e:
            logger.error(
                "更新 CrawlerTaskHistory (ID=%s) 時發生未預期錯誤: %s",
                entity_id,
                e,
                exc_info=True,
            )
            raise DatabaseOperationError(
                f"更新 CrawlerTaskHistory (ID={entity_id}) 時發生未預期錯誤: {e}"
            ) from e

    def find_by_task_id(
        self,
        task_id: int,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        sort_desc: bool = False,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List["CrawlerTaskHistory"], List[Dict[str, Any]]]:
        """根據任務ID查詢相關的歷史記錄，支援分頁、排序和預覽"""
        filter_criteria = {"task_id": task_id}

        page = 1
        per_page = limit if limit is not None and limit > 0 else 10
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(
                "find_by_task_id: Offset (%s) provided but limit/per_page (%s) is invalid, defaulting to page 1.",
                offset,
                limit,
            )
            page = 1

        _, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=page,
            per_page=per_page,
            sort_by="start_time",
            sort_desc=sort_desc,
            is_preview=is_preview,
            preview_fields=preview_fields,
        )
        return items

    def find_successful_histories(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List["CrawlerTaskHistory"], List[Dict[str, Any]]]:
        """查詢所有成功的任務歷史記錄，支援分頁和預覽"""
        filter_criteria = {"success": True}

        page = 1
        per_page = limit if limit is not None and limit > 0 else 10
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(
                "find_successful_histories: Offset (%s) provided but limit/per_page (%s) is invalid, defaulting to page 1.",
                offset,
                limit,
            )
            page = 1

        _, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=page,
            per_page=per_page,
            is_preview=is_preview,
            preview_fields=preview_fields,
        )
        return items

    def find_failed_histories(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List["CrawlerTaskHistory"], List[Dict[str, Any]]]:
        """查詢所有失敗的任務歷史記錄，支援分頁和預覽"""
        filter_criteria = {"success": False}

        page = 1
        per_page = limit if limit is not None and limit > 0 else 10
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(
                "find_failed_histories: Offset (%s) provided but limit/per_page (%s) is invalid, defaulting to page 1.",
                offset,
                limit,
            )
            page = 1

        _, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=page,
            per_page=per_page,
            is_preview=is_preview,
            preview_fields=preview_fields,
        )
        return items

    def find_histories_with_articles(
        self,
        min_articles: int = 1,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List["CrawlerTaskHistory"], List[Dict[str, Any]]]:
        """查詢文章數量大於等於指定值的歷史記錄，支援分頁和預覽"""
        if min_articles < 0:
            raise ValueError("min_articles 不能為負數")

        filter_criteria = {"articles_count": {"$gte": min_articles}}

        page = 1
        per_page = limit if limit is not None and limit > 0 else 10
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(
                "find_histories_with_articles: Offset (%s) provided but limit/per_page (%s) is invalid, defaulting to page 1.",
                offset,
                limit,
            )
            page = 1

        _, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=page,
            per_page=per_page,
            is_preview=is_preview,
            preview_fields=preview_fields,
        )
        return items

    def find_histories_by_date_range(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List["CrawlerTaskHistory"], List[Dict[str, Any]]]:
        """根據日期範圍查詢歷史記錄，支援分頁和預覽"""
        filter_criteria: Dict[str, Any] = {}
        if start_date:
            filter_criteria["start_time"] = {"$gte": start_date}
        if end_date:
            if "start_time" in filter_criteria:
                filter_criteria["start_time"]["$lte"] = end_date
            else:
                filter_criteria["start_time"] = {"$lte": end_date}

        page = 1
        per_page = limit if limit is not None and limit > 0 else 10
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(
                "find_histories_by_date_range: Offset (%s) provided but limit/per_page (%s) is invalid, defaulting to page 1.",
                offset,
                limit,
            )
            page = 1

        _, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=page,
            per_page=per_page,
            is_preview=is_preview,
            preview_fields=preview_fields,
        )
        return items

    def count_total_articles(self, task_id: Optional[int] = None) -> int:
        """
        獲取總文章數量

        :param task_id: 可選的任務ID，如果提供則只計算該任務的文章數
        :return: 文章總數
        """

        def query_builder():
            query = self.session.query(self.model_class)
            if task_id is not None:
                query = query.filter_by(task_id=task_id)

            # Fallback to Python sum if SQL SUM is complex or type issues arise
            # Be mindful of performance with large datasets
            histories = query.all()  # This might load many objects
            return sum(int(history.articles_count or 0) for history in histories)

        result = self.execute_query(query_builder, err_msg="獲取總文章數量時發生錯誤")
        return int(result) if result is not None else 0

    def get_latest_history(
        self,
        task_id: int,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Optional[Union["CrawlerTaskHistory", Dict[str, Any]]]:
        """
        獲取指定任務的最新歷史記錄 (按 start_time 降序)，支援預覽

        :param task_id: 任務ID
        :param is_preview: 是否預覽模式
        :param preview_fields: 預覽欄位
        :return: 最新的歷史記錄實例或字典，如果不存在則返回 None
        """
        filter_criteria = {"task_id": task_id}
        _, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=1,
            per_page=1,
            sort_by="start_time",
            sort_desc=True,
            is_preview=is_preview,
            preview_fields=preview_fields,
        )
        return items[0] if items else None

    def get_histories_older_than(
        self,
        days: int,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List["CrawlerTaskHistory"], List[Dict[str, Any]]]:
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

        page = 1
        per_page = limit if limit is not None and limit > 0 else 10
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(
                "get_histories_older_than: Offset (%s) provided but limit/per_page (%s) is invalid, defaulting to page 1.",
                offset,
                limit,
            )
            page = 1

        _, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=page,
            per_page=per_page,
            is_preview=is_preview,
            preview_fields=preview_fields,
        )
        return items

    def update_history_status(
        self,
        history_id: int,
        success: bool,
        message: Optional[str] = None,
        articles_count: Optional[int] = None,
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
            update_data = {"success": success, "end_time": datetime.now(timezone.utc)}

            if message is not None:
                update_data["message"] = message

            if articles_count is not None:
                update_data["articles_count"] = articles_count

            updated_entity = self.update(history_id, update_data)
            logger.debug("更新歷史記錄狀態已完成，等待提交: %s", updated_entity)
            return updated_entity is not None
        except Exception as e:
            logger.error("更新歷史記錄狀態時發生錯誤: %s", e)
            return False

    def get_latest_by_task_id(
        self,
        task_id: int,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Optional[Union["CrawlerTaskHistory", Dict[str, Any]]]:
        """獲取指定任務的最新一筆歷史記錄 (按 created_at 降序)，支援預覽"""
        filter_criteria = {"task_id": task_id}
        _, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=1,
            per_page=1,
            sort_by="created_at",
            sort_desc=True,
            is_preview=is_preview,
            preview_fields=preview_fields,
        )
        return items[0] if items else None
