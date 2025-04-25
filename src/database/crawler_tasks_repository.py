from .base_repository import BaseRepository, SchemaType
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawler_tasks_schema import CrawlerTasksCreateSchema, CrawlerTasksUpdateSchema
from typing import List, Optional, Type, Any, Dict, Literal, overload, Tuple, Union, cast
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
import logging
from src.error.errors import ValidationError, DatabaseOperationError, InvalidOperationError
from src.utils.datetime_utils import enforce_utc_datetime_transform
from src.utils.enum_utils import TaskStatus, ScrapePhase, ScrapeMode
from src.utils.model_utils import validate_cron_expression
from croniter import croniter
from sqlalchemy import desc, asc, cast, JSON, Text, Boolean, or_, func # 引入 JSON, Text, desc, asc, Boolean, or_, func
from sqlalchemy.orm.attributes import flag_modified # 導入 flag_modified

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CrawlerTasksRepository(BaseRepository['CrawlerTasks']):
    """CrawlerTasks 特定的Repository"""

    @classmethod
    @overload
    def get_schema_class(cls, schema_type: Literal[SchemaType.CREATE]) -> Type[CrawlerTasksCreateSchema]: ...

    @classmethod
    @overload
    def get_schema_class(cls, schema_type: Literal[SchemaType.UPDATE]) -> Type[CrawlerTasksUpdateSchema]: ...

    @classmethod
    def get_schema_class(cls, schema_type: SchemaType = SchemaType.CREATE) -> Type[BaseModel]:
        """提供對應的 schema class"""
        if schema_type == SchemaType.CREATE:
            return CrawlerTasksCreateSchema
        elif schema_type == SchemaType.UPDATE:
            return CrawlerTasksUpdateSchema
        raise ValueError(f"未支援的 schema 類型: {schema_type}")

    def create(self, entity_data: Dict[str, Any]) -> Optional[CrawlerTasks]:
        """
        創建爬蟲任務，先進行 Pydantic 驗證，然後調用內部創建。
        此方法不執行 commit。

        Args:
            entity_data: 實體資料

        Returns:
            創建的爬蟲任務實體 (尚未持久化到 DB)
        """
        try:
            # 1. 設定特定預設值（如果需要）
            # 例如: entity_data.setdefault('is_auto', False)

            # 2. 執行 Pydantic 驗證
            validated_data = self.validate_data(entity_data, SchemaType.CREATE)

            # 3. 將已驗證的資料傳給內部方法
            if validated_data is None:
                # validate_data 在失敗時會拋出 ValidationError，理論上不會到這裡
                error_msg = "創建 CrawlerTask 時驗證步驟返回意外的 None 值"
                logger.error(error_msg)
                raise ValidationError(error_msg) # 或 DatabaseOperationError
            else:
                # _create_internal 僅創建物件實例，不 commit
                return self._create_internal(validated_data)
        except ValidationError as e:
            logger.error(f"創建 CrawlerTask 驗證失敗: {e}")
            raise # 重新拋出讓 Service 層處理
        except Exception as e: # 捕捉 _create_internal 或其他意外錯誤
            logger.error(f"創建 CrawlerTask 時發生未預期錯誤: {e}", exc_info=True)
            # 將其他錯誤包裝成 DatabaseOperationError
            raise DatabaseOperationError(f"創建 CrawlerTask 時發生未預期錯誤: {e}") from e

    def update(self, entity_id: int, entity_data: Dict[str, Any]) -> Optional[CrawlerTasks]:
        """
        更新爬蟲任務，先進行 Pydantic 驗證，然後調用內部更新。
        此方法不執行 commit。

        Args:
            entity_id: 實體ID
            entity_data: 要更新的實體資料

        Returns:
            更新後的爬蟲任務實體 (尚未持久化到 DB)，如果實體不存在則返回None
        """
        try:
            # 1. 檢查實體是否存在 (使用 session.get 更高效)
            existing_entity = self.get_by_id(entity_id)
            if not existing_entity:
                logger.warning(f"更新爬蟲任務失敗，ID不存在: {entity_id}")
                return None

            # 如果更新資料為空，直接返回已存在的實體 (無需更新)
            if not entity_data:
                return existing_entity

            # 2. 執行 Pydantic 驗證 (獲取 update payload)
            update_payload = self.validate_data(entity_data, SchemaType.UPDATE)

            # 3. 將已驗證的 payload 傳給內部方法
            if update_payload is None:
                 # validate_data 在失敗時會拋出 ValidationError，理論上不會到這裡
                error_msg = f"更新 CrawlerTask (ID={entity_id}) 時驗證步驟失敗"
                logger.error(error_msg)
                raise ValidationError(error_msg) # 或 DatabaseOperationError
            else:
                 # _update_internal 僅更新物件屬性，不 commit
                return self._update_internal(entity_id, update_payload)
        except ValidationError as e:
            logger.error(f"更新 CrawlerTask (ID={entity_id}) 驗證失敗: {e}")
            raise # 重新拋出
        except Exception as e: # 捕捉 _update_internal 或其他意外錯誤
            logger.error(f"更新 CrawlerTask (ID={entity_id}) 時發生未預期錯誤: {e}", exc_info=True)
            # 將其他錯誤包裝成 DatabaseOperationError
            raise DatabaseOperationError(f"更新 CrawlerTask (ID={entity_id}) 時發生未預期錯誤: {e}") from e

    def get_task_by_id(self, task_id: int, is_active: Optional[bool] = True) -> Optional[CrawlerTasks]:
        """查詢特定任務

        Args:
            task_id: 任務ID
            is_active: 是否只返回啟用狀態的任務 (None 表示不限制)

        Returns:
            CrawlerTasks: 任務實體
        """
        filter_criteria: Dict[str, Any] = {"id": task_id}
        if is_active is not None:
            filter_criteria["is_active"] = is_active

        # Use find_paginated with page=1, per_page=1
        total, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=1,
            per_page=1,
            is_preview=False # get_task_by_id should return the full instance
        )
        # find_paginated returns a list
        if items:
            item = items[0]
            # Ensure it's the correct type (though find_paginated should handle this)
            if isinstance(item, self.model_class):
                return item
        return None

    def find_tasks_by_crawler_id(self, crawler_id: int, is_active: bool = True,
                                 limit: Optional[int] = None,
                                 offset: Optional[int] = None,
                                 is_preview: bool = False,
                                 preview_fields: Optional[List[str]] = None
                                 ) -> Union[List[CrawlerTasks], List[Dict[str, Any]]]:
        """根據爬蟲ID查詢相關的任務，支援分頁和預覽"""
        filter_criteria: Dict[str, Any] = {"crawler_id": crawler_id, "is_active": is_active}

        # Convert limit/offset to page/per_page
        page = 1
        per_page = limit if limit is not None and limit > 0 else 10 # Default per_page
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(f"find_tasks_by_crawler_id: Offset ({offset}) provided but limit/per_page ({limit}) is invalid, defaulting to page 1.")
            page = 1

        total, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=page,
            per_page=per_page,
            is_preview=is_preview,
            preview_fields=preview_fields,
            sort_by='created_at', # Keep original default sort
            sort_desc=True
        )
        return items # Return only the items list

    def find_auto_tasks(self, is_active: bool = True,
                        limit: Optional[int] = None,
                        offset: Optional[int] = None,
                        is_preview: bool = False,
                        preview_fields: Optional[List[str]] = None
                        ) -> Union[List[CrawlerTasks], List[Dict[str, Any]]]:
        """查詢所有自動執行的任務，支援分頁和預覽"""
        filter_criteria: Dict[str, Any] = {"is_auto": True, "is_active": is_active}

        # Convert limit/offset to page/per_page
        page = 1
        per_page = limit if limit is not None and limit > 0 else 10 # Default per_page
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(f"find_auto_tasks: Offset ({offset}) provided but limit/per_page ({limit}) is invalid, defaulting to page 1.")
            page = 1

        total, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=page,
            per_page=per_page,
            is_preview=is_preview,
            preview_fields=preview_fields,
            sort_by='created_at', # Keep original default sort
            sort_desc=True
        )
        return items # Return only the items list

    def find_ai_only_tasks(self, is_active: bool = True,
                           limit: Optional[int] = None,
                           is_preview: bool = False,
                           preview_fields: Optional[List[str]] = None
                           ) -> Union[List[CrawlerTasks], List[Dict[str, Any]]]:
        """查詢 AI 專用任務，支援分頁和預覽"""
        def query_builder():
            # --- Preview Logic ---
            query_entities = [self.model_class]
            valid_preview_fields = []
            local_is_preview = is_preview
            if local_is_preview and preview_fields:
                valid_preview_fields = [f for f in preview_fields if hasattr(self.model_class, f)]
                if valid_preview_fields:
                    query_entities = [getattr(self.model_class, f) for f in valid_preview_fields]
                else:
                    logger.warning(f"find_ai_only_tasks 預覽欄位無效: {preview_fields}，返回完整物件。")
                    local_is_preview = False
            # --- End Preview Logic ---

            query = self.session.query(*query_entities).filter(
                self.model_class.is_active == is_active,
                # 確保 task_args 不是 NULL 且 ai_only 鍵的值為 True
                self.model_class.task_args.isnot(None),
                self.model_class.task_args['ai_only'].as_boolean() == True
            )

            # Apply limit
            if limit is not None:
                query = query.limit(limit)

            raw_results = query.all()

            # --- Result Transformation ---
            if local_is_preview and valid_preview_fields:
                return [dict(zip(valid_preview_fields, row)) for row in raw_results]
            else:
                return raw_results
            # --- End Result Transformation ---

        return self.execute_query(
            query_builder,
            err_msg="查詢 AI 專用任務時發生錯誤"
        )

    def find_scheduled_tasks(self, is_active: bool = True,
                             limit: Optional[int] = None,
                             offset: Optional[int] = None,
                             is_preview: bool = False,
                             preview_fields: Optional[List[str]] = None
                             ) -> Union[List[CrawlerTasks], List[Dict[str, Any]]]:
        """查詢已排程的任務，支援分頁和預覽"""
        filter_criteria: Dict[str, Any] = {"is_active": is_active, "is_scheduled": True}

        # Convert limit/offset to page/per_page
        page = 1
        per_page = limit if limit is not None and limit > 0 else 10 # Default per_page
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(f"find_scheduled_tasks: Offset ({offset}) provided but limit/per_page ({limit}) is invalid, defaulting to page 1.")
            page = 1

        total, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=page,
            per_page=per_page,
            is_preview=is_preview,
            preview_fields=preview_fields,
            sort_by='created_at', # Keep original default sort
            sort_desc=True
        )
        return items # Return only the items list

    def toggle_scheduled_status(self, task_id: int) -> Optional[CrawlerTasks]:
        """
        切換任務的排程狀態。此方法不執行 commit。

        Args:
            task_id: 任務ID

        Returns:
            修改後的 CrawlerTasks 物件，如果任務不存在則返回 None。
        """
        task = self.get_by_id(task_id)
        if not task:
            logger.warning(f"切換排程狀態失敗，任務ID不存在: {task_id}")
            return None
        return self._toggle_status(task, 'is_scheduled')

    def toggle_auto_status(self, task_id: int) -> Optional[CrawlerTasks]:
        """
        切換任務的自動執行狀態。此方法不執行 commit。

        Args:
            task_id: 任務ID

        Returns:
            修改後的 CrawlerTasks 物件，如果任務不存在則返回 None。
        """
        task = self.get_by_id(task_id)
        if not task:
            logger.warning(f"切換自動執行狀態失敗，任務ID不存在: {task_id}")
            return None
        return self._toggle_status(task, 'is_auto')

    def toggle_ai_only_status(self, task_id: int) -> Optional[CrawlerTasks]:
        """
        切換任務的 AI 專用狀態 (在 task_args 中)。此方法不執行 commit。

        Args:
            task_id: 任務ID

        Returns:
            修改後的 CrawlerTasks 物件，如果任務不存在則返回 None。
        """
        task = self.get_by_id(task_id)
        if not task:
            logger.warning(f"切換 AI 專用狀態失敗，任務ID不存在: {task_id}")
            return None

        # 獲取當前 task_args，如果 task_args 是 None，則初始化為空字典
        current_args = task.task_args or {}
        # 創建副本以避免直接修改 session 中的對象 (雖然 flag_modified 會處理)
        new_args = current_args.copy() 

        # 獲取當前 ai_only 值並切換
        current_ai_only = new_args.get('ai_only', False)
        new_args['ai_only'] = not current_ai_only

        # 更新整個 task_args 字典
        task.task_args = new_args
        task.updated_at = datetime.now(timezone.utc)
        # 標記 task_args 已修改
        flag_modified(task, 'task_args')
        logger.info(f"任務 ID {task_id} 的 AI 專用狀態已在 Session 中更新: {current_ai_only} -> {not current_ai_only}")

        # 返回修改後的 task 物件 (尚未 commit)
        return task

    def toggle_active_status(self, task_id: int) -> Optional[CrawlerTasks]:
        """
        切換任務的啟用狀態。此方法不執行 commit。

        Args:
            task_id: 任務ID

        Returns:
            修改後的 CrawlerTasks 物件，如果任務不存在則返回 None。
        """
        task = self.get_by_id(task_id)
        if not task:
            logger.warning(f"切換啟用狀態失敗，任務ID不存在: {task_id}")
            return None
        return self._toggle_status(task, 'is_active')

    def _toggle_status(self, task: CrawlerTasks, field: str) -> CrawlerTasks:
        """內部方法：切換狀態 (不 commit)"""
        setattr(task, field, not getattr(task, field))
        task.updated_at = datetime.now(timezone.utc)
        return task # 返回修改後的物件

    def update_last_run(self, task_id: int, success: bool, message: Optional[str] = None) -> Optional[CrawlerTasks]:
        """
        更新任務的最後執行狀態。此方法不執行 commit。

        Args:
            task_id: 任務ID
            success: 執行是否成功
            message: 執行訊息

        Returns:
            修改後的 CrawlerTasks 物件，如果任務不存在則返回 None。
        """
        task = self.get_by_id(task_id)
        if not task:
            logger.warning(f"更新最後執行狀態失敗，任務ID不存在: {task_id}")
            return None

        # 使用 UTC 時間
        now = datetime.now(timezone.utc)
        task.last_run_at = now
        task.last_run_success = success
        if message is not None: # 允許傳入空字串來清除 message
            task.last_run_message = message
        task.updated_at = now
        logger.info(f"任務 ID {task_id} 的最後執行狀態已在 Session 中更新: success={success}")

        # 返回修改後的 task 物件 (尚未 commit)
        return task

    def update_notes(self, task_id: int, new_notes: str) -> Optional[CrawlerTasks]:
        """
        更新任務備註。此方法不執行 commit。

        Args:
            task_id: 任務ID
            new_notes: 新備註

        Returns:
            修改後的 CrawlerTasks 物件，如果任務不存在則返回 None。
        """
        task = self.get_by_id(task_id)
        if not task:
            logger.warning(f"更新備註失敗，任務ID不存在: {task_id}")
            return None
        return self._update_field(task, 'notes', new_notes)

    def _update_field(self, task: CrawlerTasks, field: str, value: Any) -> CrawlerTasks:
        """內部方法：更新欄位 (不 commit)"""
        setattr(task, field, value)
        task.updated_at = datetime.now(timezone.utc)
        return task # 返回修改後的物件

    def find_tasks_with_notes(self, limit: Optional[int] = None,
                              is_preview: bool = False,
                              preview_fields: Optional[List[str]] = None
                              ) -> Union[List[CrawlerTasks], List[Dict[str, Any]]]:
        """查詢所有有備註的任務，支援分頁和預覽"""
        def query_builder():
             # --- Preview Logic ---
            query_entities = [self.model_class]
            valid_preview_fields = []
            local_is_preview = is_preview
            if local_is_preview and preview_fields:
                valid_preview_fields = [f for f in preview_fields if hasattr(self.model_class, f)]
                if valid_preview_fields:
                    query_entities = [getattr(self.model_class, f) for f in valid_preview_fields]
                else:
                    logger.warning(f"find_tasks_with_notes 預覽欄位無效: {preview_fields}，返回完整物件。")
                    local_is_preview = False
            # --- End Preview Logic ---

            query = self.session.query(*query_entities).filter(
                self.model_class.notes.isnot(None),
                self.model_class.notes != '' # 同時排除空字串
            )

            # Apply limit
            if limit is not None:
                query = query.limit(limit)

            raw_results = query.all()

            # --- Result Transformation ---
            if local_is_preview and valid_preview_fields:
                return [dict(zip(valid_preview_fields, row)) for row in raw_results]
            else:
                return raw_results
            # --- End Result Transformation ---

        return self.execute_query(
            query_builder,
            err_msg="查詢有備註的任務時發生錯誤"
        )

    def find_tasks_by_multiple_crawlers(self, crawler_ids: List[int],
                                        limit: Optional[int] = None,
                                        offset: Optional[int] = None,
                                        is_preview: bool = False,
                                        preview_fields: Optional[List[str]] = None
                                        ) -> Union[List[CrawlerTasks], List[Dict[str, Any]]]:
        """根據多個爬蟲ID查詢任務，支援分頁和預覽"""
        if not crawler_ids:
            return []
        filter_criteria: Dict[str, Any] = {"crawler_id": {"$in": crawler_ids}}

        # Convert limit/offset to page/per_page
        page = 1
        per_page = limit if limit is not None and limit > 0 else 10 # Default per_page
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(f"find_tasks_by_multiple_crawlers: Offset ({offset}) provided but limit/per_page ({limit}) is invalid, defaulting to page 1.")
            page = 1

        total, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=page,
            per_page=per_page,
            is_preview=is_preview,
            preview_fields=preview_fields,
            sort_by='created_at', # Keep original default sort
            sort_desc=True
        )
        return items # Return only the items list

    def count_tasks_by_crawler(self, crawler_id: int) -> int:
        """獲取特定爬蟲的任務數量"""
        # Count 不涉及預覽或限制，保持原樣
        return self.execute_query(
            lambda: self.session.query(func.count(self.model_class.id)).filter_by( # 使用 func.count
                crawler_id=crawler_id
            ).scalar() or 0, # 使用 scalar() 並處理 None
            err_msg=f"獲取爬蟲ID {crawler_id} 的任務數量時發生錯誤"
        )

    def find_tasks_by_cron_expression(self, cron_expression: str,
                                      limit: Optional[int] = None,
                                      offset: Optional[int] = None,
                                      is_preview: bool = False,
                                      preview_fields: Optional[List[str]] = None
                                      ) -> Union[List[CrawlerTasks], List[Dict[str, Any]]]:
        """根據 cron 表達式查詢任務 (只查詢 is_auto=True 的)，支援分頁和預覽"""
        try:
            # 僅驗證 cron 表達式格式
            croniter(cron_expression)
        except ValueError:
            error_msg = f"無效的 cron 表達式: {cron_expression}"
            logger.error(error_msg)
            raise ValidationError(error_msg)

        filter_criteria: Dict[str, Any] = {
            "cron_expression": cron_expression,
            "is_auto": True # 只查詢自動執行的任務
        }

        # Convert limit/offset to page/per_page
        page = 1
        per_page = limit if limit is not None and limit > 0 else 10 # Default per_page
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(f"find_tasks_by_cron_expression: Offset ({offset}) provided but limit/per_page ({limit}) is invalid, defaulting to page 1.")
            page = 1

        total, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=page,
            per_page=per_page,
            is_preview=is_preview,
            preview_fields=preview_fields,
            sort_by='created_at', # Keep original default sort
            sort_desc=True
        )
        return items # Return only the items list

    def find_due_tasks(self, cron_expression: str,
                       limit: Optional[int] = None,
                       is_preview: bool = False,
                       preview_fields: Optional[List[str]] = None
                       ) -> Union[List[CrawlerTasks], List[Dict[str, Any]]]:
        """查詢需要執行的任務（根據 cron 表達式和上次執行時間, 只查 is_auto=True），支援分頁和預覽"""
        try:
            validate_cron_expression('cron_expression', max_length=255, min_length=5, required=True)(cron_expression)
        except ValueError:
            error_msg = f"無效的 cron 表達式: {cron_expression}"
            logger.error(error_msg)
            raise ValidationError(error_msg)

        def get_due_tasks_logic():
            # --- Preview Logic ---
            query_entities = [self.model_class]
            valid_preview_fields = []
            local_is_preview = is_preview
            if local_is_preview and preview_fields:
                valid_preview_fields = [f for f in preview_fields if hasattr(self.model_class, f)]
                if valid_preview_fields:
                    query_entities = [getattr(self.model_class, f) for f in valid_preview_fields]
                else:
                    logger.warning(f"find_due_tasks 預覽欄位無效: {preview_fields}，返回完整物件。")
                    local_is_preview = False
            # --- End Preview Logic ---

            # 只查詢 is_auto=True 且 is_active=True 的任務
            base_query = self.session.query(*query_entities).filter(
                self.model_class.cron_expression == cron_expression,
                self.model_class.is_auto == True,
                self.model_class.is_active == True
            )
            # 注意：預覽模式下，我們不能直接使用 .all() 然後在 Python 中過濾，
            # 因為 limit 需要在資料庫層面應用。
            # 因此，我們需要將 croniter 邏輯轉換為 SQLAlchemy 條件，或者先獲取 ID 再查詢。
            # 轉換 croniter 邏輯為 SQL 非常複雜。一個務實的方法是：
            # 1. 獲取所有符合基本條件 (cron_expression, is_auto, is_active) 的任務 ID 和 last_run_at。
            # 2. 在 Python 中使用 croniter 篩選出需要執行的任務 ID。
            # 3. 使用這些 ID 再次查詢資料庫，應用 limit 和 preview。

            # 步驟 1: 獲取候選任務的 ID 和 last_run_at
            candidate_tasks_info = self.session.query(
                self.model_class.id, self.model_class.last_run_at
            ).filter(
                self.model_class.cron_expression == cron_expression,
                self.model_class.is_auto == True,
                self.model_class.is_active == True
            ).all()

            # 步驟 2: 在 Python 中篩選
            now = datetime.now(timezone.utc)
            due_task_ids = []
            logger.debug(f"[find_due_tasks] Current UTC time (now): {now.isoformat()}")

            for task_id, last_run_at in candidate_tasks_info:
                if last_run_at is None:
                    logger.debug(f"[find_due_tasks] Task ID {task_id} added (never run).")
                    due_task_ids.append(task_id)
                    continue

                last_run = last_run_at
                if last_run.tzinfo is None:
                    last_run = enforce_utc_datetime_transform(last_run)
                    logger.debug(f"[find_due_tasks] Task ID {task_id}: Forced last_run_at to UTC: {last_run.isoformat()}")

                try:
                    cron_now = croniter(cron_expression, now)
                    previous_scheduled_run = cron_now.get_prev(datetime)
                    if previous_scheduled_run.tzinfo is None:
                        previous_scheduled_run = enforce_utc_datetime_transform(previous_scheduled_run)
                        logger.debug(f"[find_due_tasks] Task ID {task_id}: Forced previous_scheduled_run to UTC: {previous_scheduled_run.isoformat()}")

                    logger.debug(f"[find_due_tasks] Task ID {task_id}: last_run={last_run.isoformat()}, previous_scheduled_run={previous_scheduled_run.isoformat()}, now={now.isoformat()}")

                    if last_run < previous_scheduled_run:
                        logger.debug(f"[find_due_tasks] Task ID {task_id} added. Condition met.")
                        due_task_ids.append(task_id)
                    else:
                        logger.debug(f"[find_due_tasks] Task ID {task_id} skipped. Condition not met.")
                        continue

                except Exception as e:
                    logger.error(f"計算任務 {task_id} 的下次執行時間時出錯 ({cron_expression}, {last_run}): {e}", exc_info=True)
                    continue

            # 如果沒有到期的任務，直接返回空列表
            if not due_task_ids:
                return []

            # 步驟 3: 使用 ID 查詢，應用 limit 和 preview
            final_query = self.session.query(*query_entities).filter(
                self.model_class.id.in_(due_task_ids)
            )

            # Apply limit
            if limit is not None:
                final_query = final_query.limit(limit)

            # 添加排序（可選，例如按 ID 或其他欄位）
            final_query = final_query.order_by(self.model_class.id) # 或者其他排序

            raw_results = final_query.all()

            # --- Result Transformation ---
            if local_is_preview and valid_preview_fields:
                return [dict(zip(valid_preview_fields, row)) for row in raw_results]
            else:
                return raw_results
            # --- End Result Transformation ---

        return self.execute_query(
            get_due_tasks_logic,
            err_msg=f"查詢待執行的 cron 表達式 {cron_expression} 的任務時發生錯誤"
        )

    def find_failed_tasks(self, days: int = 1,
                          limit: Optional[int] = None,
                          offset: Optional[int] = None,
                          is_preview: bool = False,
                          preview_fields: Optional[List[str]] = None
                          ) -> Union[List[CrawlerTasks], List[Dict[str, Any]]]:
        """獲取最近失敗的任務 (只查 is_active=True 的任務)，支援分頁和預覽"""
        if days < 0:
            days = 0 # 防止負數天數
        time_threshold = datetime.now(timezone.utc) - timedelta(days=days)

        filter_criteria: Dict[str, Any] = {
            "is_active": True, # 只關心活動任務的失敗狀態
            "last_run_success": False,
            "last_run_at": {"$gte": time_threshold} # 修改為 $gte 以匹配時間閾值
        }

        # Convert limit/offset to page/per_page
        page = 1
        per_page = limit if limit is not None and limit > 0 else 10 # Default per_page
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(f"find_failed_tasks: Offset ({offset}) provided but limit/per_page ({limit}) is invalid, defaulting to page 1.")
            page = 1

        total, items = self.find_paginated(
            filter_criteria=filter_criteria,
            page=page,
            per_page=per_page,
            sort_by='last_run_at', # Sort by failure time
            sort_desc=True,
            is_preview=is_preview,
            preview_fields=preview_fields
        )
        return items # Return only the items list

    def convert_to_local_time(self, utc_time, timezone_str='Asia/Taipei'):
        """將 UTC 時間轉換為指定時區時間"""
        import pytz
        if utc_time is None:
            return None
        if utc_time.tzinfo is None:
             # 如果輸入時間沒有時區，假設它是 UTC
             utc_time = pytz.utc.localize(utc_time)
        try:
            local_tz = pytz.timezone(timezone_str)
            return utc_time.astimezone(local_tz)
        except pytz.UnknownTimeZoneError:
            logger.error(f"未知的時區: {timezone_str}")
            # 可以選擇返回 UTC 或拋出錯誤
            return utc_time # 返回原始 UTC 時間

    def advanced_search(self, is_preview: bool = False, preview_fields: Optional[List[str]] = None, **filters) -> Dict[str, Any]:
        """
        進階搜尋任務 (已更新以支援預覽和 find_paginated)

        Args:
            is_preview: 是否啟用預覽模式
            preview_fields: 預覽模式下要返回的欄位列表
            **filters: 包含過濾、排序和分頁參數的字典
            可用過濾條件：
            - task_name: 任務名稱 (模糊搜尋)
            - crawler_id: 爬蟲ID
            - is_auto: 是否自動執行
            - is_active: 是否啟用
            - ai_only: 是否只抓取AI相關文章 (task_args)
            - last_run_success: 上次執行是否成功
            - date_range: 上次執行時間範圍，格式為(start_date, end_date)
            - has_notes: 是否有備註
            - task_status: 任務狀態 (TaskStatus Enum 或其 value)
            - scrape_phase: 爬取階段 (ScrapePhase Enum 或其 value)
            - cron_expression: cron表達式
            - retry_count: 重試次數 (可以是整數或範圍字典 {"min": x, "max": y})
            - max_pages: 最大頁數 (task_args)
            - save_to_csv: 是否保存到CSV (task_args)
            - scrape_mode: 抓取模式 (task_args, ScrapeMode Enum 或其 value)
            - sort_by: 排序欄位名稱 (預設 'created_at')
            - sort_desc: 是否降冪排序 (預設 False)
            - limit: 限制數量
            - offset: 偏移量

        Returns:
            包含 'tasks' 列表和 'total_count' 的字典。
            如果 is_preview=True，'tasks' 將是字典列表，否則為模型實例列表。
        """
        # 1. 提取分頁和排序參數
        limit = filters.pop('limit', None)
        offset = filters.pop('offset', None)
        sort_by = filters.pop('sort_by', 'created_at') # Default sort
        sort_desc = filters.pop('sort_desc', True)    # Default sort desc

        page = 1
        per_page = limit if limit is not None and limit > 0 else 10 # Default per_page
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(f"advanced_search: Offset ({offset}) provided but limit/per_page ({limit}) is invalid, defaulting to page 1.")
            page = 1

        # 2. 構建 filter_criteria 和 extra_filters
        filter_criteria: Dict[str, Any] = {}
        extra_filters_list: List[Any] = [] # For complex filters like JSON access

        for key, value in filters.items():
            if value is None or value == '': # Skip None or empty string values
                continue

            # Standard fields handled by base _apply_filters
            if key in ['crawler_id', 'is_auto', 'is_active', 'last_run_success', 'cron_expression', 'task_status', 'scrape_phase']:
                if key == 'task_status' and isinstance(value, TaskStatus):
                     filter_criteria[key] = value.value
                elif key == 'scrape_phase' and isinstance(value, ScrapePhase):
                    filter_criteria[key] = value.value
                else:
                    filter_criteria[key] = value
            elif key == 'task_name':
                # Requires specific handling if base doesn't support 'like' via dict
                # Assume base _apply_filters doesn't handle this, add to extra_filters
                extra_filters_list.append(self.model_class.task_name.like(f"%{value}%"))
            elif key == 'date_range':
                start_date, end_date = value
                date_filter = {}
                if start_date: date_filter["$gte"] = enforce_utc_datetime_transform(start_date)
                if end_date:   date_filter["$lte"] = enforce_utc_datetime_transform(end_date)
                if date_filter: filter_criteria['last_run_at'] = date_filter
            elif key == 'has_notes':
                if value is True:
                    # Use extra_filters for combined condition
                    extra_filters_list.append(self.model_class.notes.isnot(None))
                    extra_filters_list.append(self.model_class.notes != '')
                else:
                    extra_filters_list.append(or_(self.model_class.notes == None, self.model_class.notes == ''))
            elif key == 'retry_count':
                retry_filter_val = value
                if isinstance(retry_filter_val, dict):
                    retry_criteria = {}
                    if 'min' in retry_filter_val: retry_criteria['$gte'] = retry_filter_val['min']
                    if 'max' in retry_filter_val: retry_criteria['$lte'] = retry_filter_val['max']
                    if retry_criteria: filter_criteria['retry_count'] = retry_criteria
                elif isinstance(retry_filter_val, int):
                    filter_criteria['retry_count'] = retry_filter_val
            # JSON fields -> use extra_filters
            elif key == 'ai_only':
                extra_filters_list.append(self.model_class.task_args.isnot(None))
                extra_filters_list.append(self.model_class.task_args['ai_only'].as_boolean() == value)
            elif key == 'max_pages':
                 extra_filters_list.append(self.model_class.task_args.isnot(None))
                 extra_filters_list.append(self.model_class.task_args['max_pages'].as_integer() == value)
            elif key == 'save_to_csv':
                 extra_filters_list.append(self.model_class.task_args.isnot(None))
                 extra_filters_list.append(self.model_class.task_args['save_to_csv'].as_boolean() == value)
            elif key == 'scrape_mode':
                 mode_value = value.value if isinstance(value, ScrapeMode) else value
                 extra_filters_list.append(self.model_class.task_args.isnot(None))
                 extra_filters_list.append(self.model_class.task_args['scrape_mode'].as_string() == mode_value)
            else:
                logger.warning(f"advanced_search: 未知的過濾條件 '{key}'，已忽略。")

        # 3. 呼叫 find_paginated
        try:
            total, tasks = self.find_paginated(
                filter_criteria=filter_criteria,
                extra_filters=extra_filters_list if extra_filters_list else None,
                page=page,
                per_page=per_page,
                sort_by=sort_by,
                sort_desc=sort_desc,
                is_preview=is_preview,
                preview_fields=preview_fields
            )
            return {'tasks': tasks, 'total_count': total}
        except InvalidOperationError as e:
             # Catch specific errors like invalid sort_by
             logger.error(f"進階搜尋時發生錯誤: {e}")
             # Re-raise or return an error structure
             raise DatabaseOperationError(f"進階搜尋失敗: {e}") from e
        except Exception as e:
            logger.error(f"進階搜尋任務時發生未預期錯誤: {e}", exc_info=True)
            raise DatabaseOperationError(f"進階搜尋任務時發生未預期錯誤: {e}") from e