"""定義 CrawlerTasksRepository 類別，用於處理與 CrawlerTasks 模型相關的資料庫操作。"""

from datetime import datetime, timedelta, timezone
from typing import (
    List,
    Optional,
    Type,
    Any,
    Dict,
    Literal,
    overload,
    Tuple,
    Union,
    cast,
)  # Keep List, Optional, Type, Any, Dict, Literal, overload, Tuple, Union, cast
import logging  # Keep logging for potential direct use or type hints if LoggerSetup doesn't cover all bases

from croniter import croniter
from pydantic import BaseModel
from sqlalchemy import (
    desc,
    asc,
    cast as sql_cast,
    JSON,
    Text,
    Boolean,
    or_,
    func,
)  # 引入 JSON, Text, desc, asc, Boolean, or_, func. Alias sqlalchemy.cast to sql_cast
from sqlalchemy.orm.attributes import flag_modified  # 導入 flag_modified

from .base_repository import BaseRepository, SchemaType
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawler_tasks_schema import (
    CrawlerTasksCreateSchema,
    CrawlerTasksUpdateSchema,
)
from src.error.errors import (
    ValidationError,
    DatabaseOperationError,
    InvalidOperationError,
)
from src.utils.datetime_utils import enforce_utc_datetime_transform
from src.utils.enum_utils import TaskStatus, ScrapePhase, ScrapeMode
from src.utils.model_utils import validate_cron_expression
from src.utils.log_utils import LoggerSetup  # 使用統一的 logger

# 設定 logger
logger = LoggerSetup.setup_logger(__name__)


class CrawlerTasksRepository(BaseRepository["CrawlerTasks"]):
    """CrawlerTasks 特定的Repository"""

    @classmethod
    @overload
    def get_schema_class(
        cls, schema_type: Literal[SchemaType.CREATE]
    ) -> Type[CrawlerTasksCreateSchema]: ...

    @classmethod
    @overload
    def get_schema_class(
        cls, schema_type: Literal[SchemaType.UPDATE]
    ) -> Type[CrawlerTasksUpdateSchema]: ...

    @classmethod
    def get_schema_class(
        cls, schema_type: SchemaType = SchemaType.CREATE
    ) -> Type[BaseModel]:
        """提供對應的 schema class"""
        if schema_type == SchemaType.CREATE:
            return CrawlerTasksCreateSchema
        elif schema_type == SchemaType.UPDATE:
            return CrawlerTasksUpdateSchema
        raise ValueError(
            f"未支援的 schema 類型: {schema_type}"
        )  # Keep f-string for error message detail

    def create(self, entity_data: Dict[str, Any]) -> Optional[CrawlerTasks]:
        """
        創建爬蟲任務，先進行 Pydantic 驗證，然後調用內部創建。
        此方法不執行 commit。
        """
        try:
            # 1. 設定特定預設值（如果需要）
            # 例如: entity_data.setdefault('is_auto', False)

            # 2. 執行 Pydantic 驗證
            validated_data = self.validate_data(entity_data, SchemaType.CREATE)

            # 3. 將已驗證的資料傳給內部方法
            if validated_data is None:
                error_msg = "創建 CrawlerTask 時驗證步驟返回意外的 None 值"
                logger.error(error_msg)
                raise ValidationError(error_msg)
            else:
                # _create_internal 僅創建物件實例，不 commit
                return self._create_internal(validated_data)
        except ValidationError as e:
            logger.error("創建 CrawlerTask 驗證失敗: %s", e)
            raise
        except Exception as e:
            logger.error("創建 CrawlerTask 時發生未預期錯誤: %s", e, exc_info=True)
            raise DatabaseOperationError(
                f"創建 CrawlerTask 時發生未預期錯誤: {e}"
            ) from e  # Keep f-string for error message detail

    def update(
        self, entity_id: int, entity_data: Dict[str, Any]
    ) -> Optional[CrawlerTasks]:
        """
        更新爬蟲任務，先進行 Pydantic 驗證，然後調用內部更新。
        此方法不執行 commit。
        """
        try:
            existing_entity = self.get_by_id(entity_id)
            if not existing_entity:
                logger.warning("更新爬蟲任務失敗，ID不存在: %d", entity_id)
                return None

            if not entity_data:
                return existing_entity

            update_payload = self.validate_data(entity_data, SchemaType.UPDATE)

            if update_payload is None:
                error_msg = f"更新 CrawlerTask (ID={entity_id}) 時驗證步驟失敗"  # Keep f-string for error message detail
                logger.error(error_msg)
                raise ValidationError(error_msg)
            else:
                return self._update_internal(entity_id, update_payload)
        except ValidationError as e:
            logger.error("更新 CrawlerTask (ID=%d) 驗證失敗: %s", entity_id, e)
            raise
        except Exception as e:
            logger.error(
                "更新 CrawlerTask (ID=%d) 時發生未預期錯誤: %s",
                entity_id,
                e,
                exc_info=True,
            )
            raise DatabaseOperationError(
                f"更新 CrawlerTask (ID={entity_id}) 時發生未預期錯誤: {e}"
            ) from e  # Keep f-string for error message detail

    def get_task_by_id(
        self, task_id: int, is_active: Optional[bool] = True
    ) -> Optional[CrawlerTasks]:
        """查詢特定任務"""
        filter_criteria: Dict[str, Any] = {"id": task_id}
        if is_active is not None:
            filter_criteria["is_active"] = is_active

        total, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=1,
            per_page=1,
            is_preview=False,  # get_task_by_id should return the full instance
        )
        if items:
            item = items[0]
            if isinstance(item, self.model_class):
                return item
        return None

    def find_tasks_by_crawler_id(
        self,
        crawler_id: int,
        is_active: bool = True,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List[CrawlerTasks], List[Dict[str, Any]]]:
        """根據爬蟲ID查詢相關的任務，支援分頁和預覽"""
        filter_criteria: Dict[str, Any] = {
            "crawler_id": crawler_id,
            "is_active": is_active,
        }

        page = 1
        per_page = limit if limit is not None and limit > 0 else 10
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(
                "find_tasks_by_crawler_id: Offset (%s) provided but limit/per_page (%s) is invalid, defaulting to page 1.",
                offset,
                limit,
            )
            page = 1

        total, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=page,
            per_page=per_page,
            is_preview=is_preview,
            preview_fields=preview_fields,
            sort_by="created_at",
            sort_desc=True,
        )
        return items

    def find_auto_tasks(
        self,
        is_active: bool = True,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List[CrawlerTasks], List[Dict[str, Any]]]:
        """查詢所有自動執行的任務，支援分頁和預覽"""
        filter_criteria: Dict[str, Any] = {"is_auto": True, "is_active": is_active}

        page = 1
        per_page = limit if limit is not None and limit > 0 else 10
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(
                "find_auto_tasks: Offset (%s) provided but limit/per_page (%s) is invalid, defaulting to page 1.",
                offset,
                limit,
            )
            page = 1

        total, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=page,
            per_page=per_page,
            is_preview=is_preview,
            preview_fields=preview_fields,
            sort_by="created_at",
            sort_desc=True,
        )
        return items

    def find_ai_only_tasks(
        self,
        is_active: bool = True,
        limit: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List[CrawlerTasks], List[Dict[str, Any]]]:
        """查詢 AI 專用任務，支援分頁和預覽"""

        def query_builder():
            query_entities = [self.model_class]
            valid_preview_fields = []
            local_is_preview = is_preview
            if local_is_preview and preview_fields:
                valid_preview_fields = [
                    f for f in preview_fields if hasattr(self.model_class, f)
                ]
                if valid_preview_fields:
                    query_entities = [
                        getattr(self.model_class, f) for f in valid_preview_fields
                    ]
                else:
                    logger.warning(
                        "find_ai_only_tasks 預覽欄位無效: %s，返回完整物件。",
                        preview_fields,
                    )
                    local_is_preview = False

            query = self.session.query(*query_entities).filter(
                self.model_class.is_active == is_active,
                self.model_class.task_args.isnot(None),
                self.model_class.task_args["ai_only"].as_boolean() == True,
            )

            if limit is not None:
                query = query.limit(limit)

            raw_results = query.all()

            if local_is_preview and valid_preview_fields:
                return [dict(zip(valid_preview_fields, row)) for row in raw_results]
            else:
                return raw_results

        return self.execute_query(query_builder, err_msg="查詢 AI 專用任務時發生錯誤")

    def find_scheduled_tasks(
        self,
        is_active: bool = True,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List[CrawlerTasks], List[Dict[str, Any]]]:
        """查詢已排程的任務，支援分頁和預覽"""
        filter_criteria: Dict[str, Any] = {"is_active": is_active, "is_scheduled": True}

        page = 1
        per_page = limit if limit is not None and limit > 0 else 10
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(
                "find_scheduled_tasks: Offset (%s) provided but limit/per_page (%s) is invalid, defaulting to page 1.",
                offset,
                limit,
            )
            page = 1

        total, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=page,
            per_page=per_page,
            is_preview=is_preview,
            preview_fields=preview_fields,
            sort_by="created_at",
            sort_desc=True,
        )
        return items

    def toggle_scheduled_status(self, task_id: int) -> Optional[CrawlerTasks]:
        """
        切換任務的排程狀態。此方法不執行 commit。
        """
        task = self.get_by_id(task_id)
        if not task:
            logger.warning("切換排程狀態失敗，任務ID不存在: %d", task_id)
            return None
        return self._toggle_status(task, "is_scheduled")

    def toggle_auto_status(self, task_id: int) -> Optional[CrawlerTasks]:
        """
        切換任務的自動執行狀態。此方法不執行 commit。
        """
        task = self.get_by_id(task_id)
        if not task:
            logger.warning("切換自動執行狀態失敗，任務ID不存在: %d", task_id)
            return None
        return self._toggle_status(task, "is_auto")

    def toggle_ai_only_status(self, task_id: int) -> Optional[CrawlerTasks]:
        """
        切換任務的 AI 專用狀態 (在 task_args 中)。此方法不執行 commit。
        """
        task = self.get_by_id(task_id)
        if not task:
            logger.warning("切換 AI 專用狀態失敗，任務ID不存在: %d", task_id)
            return None

        current_args = task.task_args or {}
        new_args = current_args.copy()

        current_ai_only = new_args.get("ai_only", False)
        new_args["ai_only"] = not current_ai_only

        task.task_args = new_args
        task.updated_at = datetime.now(timezone.utc)
        flag_modified(task, "task_args")
        logger.info(
            "任務 ID %d 的 AI 專用狀態已在 Session 中更新: %s -> %s",
            task_id,
            current_ai_only,
            not current_ai_only,
        )

        return task

    def toggle_active_status(self, task_id: int) -> Optional[CrawlerTasks]:
        """
        切換任務的啟用狀態。此方法不執行 commit。
        """
        task = self.get_by_id(task_id)
        if not task:
            logger.warning("切換啟用狀態失敗，任務ID不存在: %d", task_id)
            return None
        return self._toggle_status(task, "is_active")

    def _toggle_status(self, task: CrawlerTasks, field: str) -> CrawlerTasks:
        """內部方法：切換狀態 (不 commit)"""
        setattr(task, field, not getattr(task, field))
        task.updated_at = datetime.now(timezone.utc)
        return task

    def update_last_run(
        self, task_id: int, success: bool, message: Optional[str] = None
    ) -> Optional[CrawlerTasks]:
        """
        更新任務的最後執行狀態。此方法不執行 commit。
        """
        task = self.get_by_id(task_id)
        if not task:
            logger.warning("更新最後執行狀態失敗，任務ID不存在: %d", task_id)
            return None

        now = datetime.now(timezone.utc)
        task.last_run_at = now
        task.last_run_success = success
        if message is not None:
            task.last_run_message = message
        task.updated_at = now
        logger.info(
            "任務 ID %d 的最後執行狀態已在 Session 中更新: success=%s", task_id, success
        )

        return task

    def update_notes(self, task_id: int, new_notes: str) -> Optional[CrawlerTasks]:
        """
        更新任務備註。此方法不執行 commit。
        """
        task = self.get_by_id(task_id)
        if not task:
            logger.warning("更新備註失敗，任務ID不存在: %d", task_id)
            return None
        return self._update_field(task, "notes", new_notes)

    def _update_field(self, task: CrawlerTasks, field: str, value: Any) -> CrawlerTasks:
        """內部方法：更新欄位 (不 commit)"""
        setattr(task, field, value)
        task.updated_at = datetime.now(timezone.utc)
        return task

    def find_tasks_with_notes(
        self,
        limit: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List[CrawlerTasks], List[Dict[str, Any]]]:
        """查詢所有有備註的任務，支援分頁和預覽"""

        def query_builder():
            query_entities = [self.model_class]
            valid_preview_fields = []
            local_is_preview = is_preview
            if local_is_preview and preview_fields:
                valid_preview_fields = [
                    f for f in preview_fields if hasattr(self.model_class, f)
                ]
                if valid_preview_fields:
                    query_entities = [
                        getattr(self.model_class, f) for f in valid_preview_fields
                    ]
                else:
                    logger.warning(
                        "find_tasks_with_notes 預覽欄位無效: %s，返回完整物件。",
                        preview_fields,
                    )
                    local_is_preview = False

            query = self.session.query(*query_entities).filter(
                self.model_class.notes.isnot(None), self.model_class.notes != ""
            )

            if limit is not None:
                query = query.limit(limit)

            raw_results = query.all()

            if local_is_preview and valid_preview_fields:
                return [dict(zip(valid_preview_fields, row)) for row in raw_results]
            else:
                return raw_results

        return self.execute_query(query_builder, err_msg="查詢有備註的任務時發生錯誤")

    def find_tasks_by_multiple_crawlers(
        self,
        crawler_ids: List[int],
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List[CrawlerTasks], List[Dict[str, Any]]]:
        """根據多個爬蟲ID查詢任務，支援分頁和預覽"""
        if not crawler_ids:
            return []
        filter_criteria: Dict[str, Any] = {"crawler_id": {"$in": crawler_ids}}

        page = 1
        per_page = limit if limit is not None and limit > 0 else 10
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(
                "find_tasks_by_multiple_crawlers: Offset (%s) provided but limit/per_page (%s) is invalid, defaulting to page 1.",
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
            sort_by="created_at",
            sort_desc=True,
        )
        return items

    def count_tasks_by_crawler(self, crawler_id: int) -> int:
        """獲取特定爬蟲的任務數量"""
        return self.execute_query(
            lambda: self.session.query(func.count(self.model_class.id))
            .filter_by(crawler_id=crawler_id)  # 使用 func.count
            .scalar()
            or 0,
            err_msg=f"獲取爬蟲ID {crawler_id} 的任務數量時發生錯誤",  # Keep f-string for error message detail
        )

    def find_tasks_by_cron_expression(
        self,
        cron_expression: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List[CrawlerTasks], List[Dict[str, Any]]]:
        """根據 cron 表達式查詢任務 (只查詢 is_auto=True 的)，支援分頁和預覽"""
        try:
            croniter(cron_expression)
        except ValueError:
            error_msg = f"無效的 cron 表達式: {cron_expression}"  # Keep f-string for error message detail
            logger.error(error_msg)
            raise ValidationError(error_msg)

        filter_criteria: Dict[str, Any] = {
            "cron_expression": cron_expression,
            "is_auto": True,
        }

        page = 1
        per_page = limit if limit is not None and limit > 0 else 10
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(
                "find_tasks_by_cron_expression: Offset (%s) provided but limit/per_page (%s) is invalid, defaulting to page 1.",
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
            sort_by="created_at",
            sort_desc=True,
        )
        return items

    def find_due_tasks(
        self,
        cron_expression: str,
        limit: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List[CrawlerTasks], List[Dict[str, Any]]]:
        """查詢需要執行的任務（根據 cron 表達式和上次執行時間, 只查 is_auto=True），支援分頁和預覽"""
        try:
            validate_cron_expression(
                "cron_expression", max_length=255, min_length=5, required=True
            )(cron_expression)
        except ValueError:
            error_msg = f"無效的 cron 表達式: {cron_expression}"  # Keep f-string for error message detail
            logger.error(error_msg)
            raise ValidationError(error_msg)

        def get_due_tasks_logic():
            query_entities = [self.model_class]
            valid_preview_fields = []
            local_is_preview = is_preview
            if local_is_preview and preview_fields:
                valid_preview_fields = [
                    f for f in preview_fields if hasattr(self.model_class, f)
                ]
                if valid_preview_fields:
                    query_entities = [
                        getattr(self.model_class, f) for f in valid_preview_fields
                    ]
                else:
                    logger.warning(
                        "find_due_tasks 預覽欄位無效: %s，返回完整物件。",
                        preview_fields,
                    )
                    local_is_preview = False

            candidate_tasks_info = (
                self.session.query(self.model_class.id, self.model_class.last_run_at)
                .filter(
                    self.model_class.cron_expression == cron_expression,
                    self.model_class.is_auto == True,
                    self.model_class.is_active == True,
                )
                .all()
            )

            now = datetime.now(timezone.utc)
            due_task_ids = []
            logger.debug("[find_due_tasks] Current UTC time (now): %s", now.isoformat())

            for task_id, last_run_at in candidate_tasks_info:
                if last_run_at is None:
                    logger.debug(
                        "[find_due_tasks] Task ID %d added (never run).", task_id
                    )
                    due_task_ids.append(task_id)
                    continue

                last_run = last_run_at
                if last_run.tzinfo is None:
                    last_run = enforce_utc_datetime_transform(last_run)
                    logger.debug(
                        "[find_due_tasks] Task ID %d: Forced last_run_at to UTC: %s",
                        task_id,
                        last_run.isoformat(),
                    )

                try:
                    # 計算相對於 last_run 的下一個執行時間
                    cron_iter = croniter(cron_expression, last_run)
                    next_scheduled_run_after_last = cron_iter.get_next(datetime)

                    if next_scheduled_run_after_last.tzinfo is None:
                       next_scheduled_run_after_last = enforce_utc_datetime_transform(
                           next_scheduled_run_after_last
                       )
                       logger.debug(
                           "[find_due_tasks] Task ID %d: Forced next_scheduled_run_after_last to UTC: %s",
                           task_id,
                           next_scheduled_run_after_last.isoformat(),
                       )


                    logger.debug(
                        "[find_due_tasks] Task ID %d: last_run=%s, next_scheduled_run_after_last=%s, now=%s",
                        task_id,
                        last_run.isoformat(),
                        next_scheduled_run_after_last.isoformat(),
                        now.isoformat(),
                    )

                    # 比較 now 是否達到或超過下一個排定時間
                    if now >= next_scheduled_run_after_last:
                        logger.debug(
                            "[find_due_tasks] Task ID %d added. Condition (now >= next_run) met.", task_id
                        )
                        due_task_ids.append(task_id)
                    else:
                        logger.debug(
                            "[find_due_tasks] Task ID %d skipped. Condition (now >= next_run) not met.",
                            task_id,
                        )
                        continue

                except Exception as e:
                    logger.error(
                        "計算任務 %d 的下次執行時間時出錯 (%s, %s): %s",
                        task_id,
                        cron_expression,
                        last_run,
                        e,
                        exc_info=True,
                    )
                    continue

            if not due_task_ids:
                return []

            final_query = self.session.query(*query_entities).filter(
                self.model_class.id.in_(due_task_ids)
            )

            if limit is not None:
                final_query = final_query.limit(limit)

            final_query = final_query.order_by(self.model_class.id)

            raw_results = final_query.all()

            if local_is_preview and valid_preview_fields:
                return [dict(zip(valid_preview_fields, row)) for row in raw_results]
            else:
                return raw_results

        return self.execute_query(
            get_due_tasks_logic,
            err_msg=f"查詢待執行的 cron 表達式 {cron_expression} 的任務時發生錯誤",  # Keep f-string for error message detail
        )

    def find_failed_tasks(
        self,
        days: int = 1,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List[CrawlerTasks], List[Dict[str, Any]]]:
        """獲取最近失敗的任務 (只查 is_active=True 的任務)，支援分頁和預覽"""
        if days < 0:
            days = 0
        time_threshold = datetime.now(timezone.utc) - timedelta(days=days)

        filter_criteria: Dict[str, Any] = {
            "is_active": True,
            "last_run_success": False,
            "last_run_at": {"$gte": time_threshold},
        }

        page = 1
        per_page = limit if limit is not None and limit > 0 else 10
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(
                "find_failed_tasks: Offset (%s) provided but limit/per_page (%s) is invalid, defaulting to page 1.",
                offset,
                limit,
            )
            page = 1

        _, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=page,
            per_page=per_page,
            sort_by="last_run_at",
            sort_desc=True,
            is_preview=is_preview,
            preview_fields=preview_fields,
        )
        return items

    def convert_to_local_time(self, utc_time, timezone_str="Asia/Taipei"):
        """將 UTC 時間轉換為指定時區時間"""
        import pytz

        if utc_time is None:
            return None
        if utc_time.tzinfo is None:
            utc_time = pytz.utc.localize(utc_time)
        try:
            local_tz = pytz.timezone(timezone_str)
            return utc_time.astimezone(local_tz)
        except pytz.UnknownTimeZoneError:
            logger.error("未知的時區: %s", timezone_str)
            return utc_time

    def advanced_search(
        self,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
        **filters,
    ) -> Dict[str, Any]:
        """
        進階搜尋任務 (已更新以支援預覽和 find_paginated)
        """
        limit = filters.pop("limit", None)
        offset = filters.pop("offset", None)
        sort_by = filters.pop("sort_by", "created_at")
        sort_desc = filters.pop("sort_desc", True)

        page = 1
        per_page = limit if limit is not None and limit > 0 else 10
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(
                "advanced_search: Offset (%s) provided but limit/per_page (%s) is invalid, defaulting to page 1.",
                offset,
                limit,
            )
            page = 1

        filter_criteria: Dict[str, Any] = {}
        extra_filters_list: List[Any] = []

        for key, value in filters.items():
            if value is None or value == "":
                continue

            if key in [
                "crawler_id",
                "is_auto",
                "is_active",
                "last_run_success",
                "cron_expression",
                "task_status",
                "scrape_phase",
            ]:
                if key == "task_status" and isinstance(value, TaskStatus):
                    filter_criteria[key] = value.value
                elif key == "scrape_phase" and isinstance(value, ScrapePhase):
                    filter_criteria[key] = value.value
                else:
                    filter_criteria[key] = value
            elif key == "task_name":
                extra_filters_list.append(
                    self.model_class.task_name.like(f"%{value}%")
                )  # Keep f-string for SQL LIKE pattern
            elif key == "date_range":
                start_date, end_date = value
                date_filter = {}
                if start_date:
                    date_filter["$gte"] = enforce_utc_datetime_transform(start_date)
                if end_date:
                    date_filter["$lte"] = enforce_utc_datetime_transform(end_date)
                if date_filter:
                    filter_criteria["last_run_at"] = date_filter
            elif key == "has_notes":
                if value is True:
                    extra_filters_list.append(self.model_class.notes.isnot(None))
                    extra_filters_list.append(self.model_class.notes != "")
                else:
                    extra_filters_list.append(
                        or_(
                            self.model_class.notes == None, self.model_class.notes == ""
                        )
                    )
            elif key == "retry_count":
                retry_filter_val = value
                if isinstance(retry_filter_val, dict):
                    retry_criteria = {}
                    if "min" in retry_filter_val:
                        retry_criteria["$gte"] = retry_filter_val["min"]
                    if "max" in retry_filter_val:
                        retry_criteria["$lte"] = retry_filter_val["max"]
                    if retry_criteria:
                        filter_criteria["retry_count"] = retry_criteria
                elif isinstance(retry_filter_val, int):
                    filter_criteria["retry_count"] = retry_filter_val
            elif key == "ai_only":
                extra_filters_list.append(self.model_class.task_args.isnot(None))
                extra_filters_list.append(
                    self.model_class.task_args["ai_only"].as_boolean() == value
                )
            elif key == "max_pages":
                extra_filters_list.append(self.model_class.task_args.isnot(None))
                extra_filters_list.append(
                    self.model_class.task_args["max_pages"].as_integer() == value
                )
            elif key == "save_to_csv":
                extra_filters_list.append(self.model_class.task_args.isnot(None))
                extra_filters_list.append(
                    self.model_class.task_args["save_to_csv"].as_boolean() == value
                )
            elif key == "scrape_mode":
                mode_value = value.value if isinstance(value, ScrapeMode) else value
                extra_filters_list.append(self.model_class.task_args.isnot(None))
                extra_filters_list.append(
                    self.model_class.task_args["scrape_mode"].as_string() == mode_value
                )
            else:
                logger.warning("advanced_search: 未知的過濾條件 '%s'，已忽略。", key)

        try:
            total, tasks = self.find_paginated(
                filter_criteria=filter_criteria,
                extra_filters=extra_filters_list if extra_filters_list else None,
                page=page,
                per_page=per_page,
                sort_by=sort_by,
                sort_desc=sort_desc,
                is_preview=is_preview,
                preview_fields=preview_fields,
            )
            return {"tasks": tasks, "total_count": total}
        except InvalidOperationError as e:
            logger.error("進階搜尋時發生錯誤: %s", e)
            raise DatabaseOperationError(
                f"進階搜尋失敗: {e}"
            ) from e  # Keep f-string for error message detail
        except Exception as e:
            logger.error("進階搜尋任務時發生未預期錯誤: %s", e, exc_info=True)
            raise DatabaseOperationError(
                f"進階搜尋任務時發生未預期錯誤: {e}"
            ) from e  # Keep f-string for error message detail
