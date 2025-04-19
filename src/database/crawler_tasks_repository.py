from .base_repository import BaseRepository, SchemaType
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawler_tasks_schema import CrawlerTasksCreateSchema, CrawlerTasksUpdateSchema
from typing import List, Optional, Type, Any, Dict, Literal, overload, Tuple
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
import logging
from src.error.errors import ValidationError, DatabaseOperationError, InvalidOperationError
from src.utils.datetime_utils import enforce_utc_datetime_transform
from src.utils.enum_utils import TaskStatus, ScrapePhase, ScrapeMode
from src.utils.model_utils import validate_cron_expression
from croniter import croniter
from sqlalchemy import desc, asc, cast, JSON, Text, Boolean # 引入 JSON, Text, desc, asc, Boolean
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
        query = self.session.query(self.model_class).filter_by(id=task_id)
        if is_active is not None:
            query = query.filter_by(is_active=is_active)

        return self.execute_query(
            lambda: query.first(),
            err_msg=f"查詢任務ID {task_id} (is_active={is_active}) 時發生錯誤"
        )

    def find_tasks_by_crawler_id(self, crawler_id: int, is_active: bool = True) -> List[CrawlerTasks]:
        """根據爬蟲ID查詢相關的任務"""
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter_by(crawler_id=crawler_id, is_active=is_active).all(),
            err_msg=f"查詢爬蟲ID {crawler_id} 的啟用任務時發生錯誤"
        )

    def find_auto_tasks(self, is_active: bool = True) -> List[CrawlerTasks]:
        """查詢所有自動執行的任務"""
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter_by(
                is_auto=True, is_active=is_active
            ).all(),
            err_msg="查詢自動執行任務時發生錯誤"
        )

    def find_ai_only_tasks(self, is_active: bool = True) -> List[CrawlerTasks]:
        """查詢 AI 專用任務"""
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter(
                self.model_class.is_active == is_active,
                self.model_class.task_args['ai_only'].as_boolean() == True
            ).all(),
            err_msg="查詢 AI 專用任務時發生錯誤"
        )

    def find_scheduled_tasks(self, is_active: bool = True) -> List[CrawlerTasks]:
        """查詢已排程的任務"""
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter_by(is_active=is_active, is_scheduled=True).all(),
            err_msg="查詢已排程的任務時發生錯誤"
        )

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

    def find_tasks_with_notes(self) -> List[CrawlerTasks]:
        """查詢所有有備註的任務"""
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter(
                self.model_class.notes.isnot(None),
                self.model_class.notes != '' # 同時排除空字串
            ).all(),
            err_msg="查詢有備註的任務時發生錯誤"
        )

    def find_tasks_by_multiple_crawlers(self, crawler_ids: List[int]) -> List[CrawlerTasks]:
        """根據多個爬蟲ID查詢任務"""
        if not crawler_ids:
            return []
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter(
                self.model_class.crawler_id.in_(crawler_ids)
            ).all(),
            err_msg="查詢多個爬蟲ID的任務時發生錯誤"
        )

    def count_tasks_by_crawler(self, crawler_id: int) -> int:
        """獲取特定爬蟲的任務數量"""
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter_by(
                crawler_id=crawler_id
            ).count(),
            err_msg=f"獲取爬蟲ID {crawler_id} 的任務數量時發生錯誤"
        )

    def find_tasks_by_cron_expression(self, cron_expression: str) -> List[CrawlerTasks]:
        """根據 cron 表達式查詢任務 (只查詢 is_auto=True 的)"""
        try:
            # 僅驗證 cron 表達式格式
            croniter(cron_expression)
        except ValueError:
            error_msg = f"無效的 cron 表達式: {cron_expression}"
            logger.error(error_msg)
            raise ValidationError(error_msg)

        return self.execute_query(
            lambda: self.session.query(self.model_class).filter_by(
                cron_expression=cron_expression,
                is_auto=True # 只查詢自動執行的任務
            ).all(),
            err_msg=f"查詢 cron 表達式 {cron_expression} 的自動任務時發生錯誤"
        )

    def find_due_tasks(self, cron_expression: str) -> List[CrawlerTasks]:
        """查詢需要執行的任務（根據 cron 表達式和上次執行時間, 只查 is_auto=True）"""
        try:
            validate_cron_expression('cron_expression', max_length=255, min_length=5, required=True)(cron_expression)
        except ValueError:
            error_msg = f"無效的 cron 表達式: {cron_expression}"
            logger.error(error_msg)
            raise ValidationError(error_msg)

        def get_due_tasks():
            # 只查詢 is_auto=True 且 is_active=True 的任務 (通常排程器只關心活動的自動任務)
            base_query = self.session.query(self.model_class).filter(
                self.model_class.cron_expression == cron_expression,
                self.model_class.is_auto == True,
                self.model_class.is_active == True # 新增 active 條件
            )
            all_relevant_tasks = base_query.all()

            # 使用 UTC 時間
            now = datetime.now(timezone.utc)
            result_tasks = []
            logger.debug(f"[find_due_tasks] Current UTC time (now): {now.isoformat()}") # Log current time

            for task in all_relevant_tasks:
                # 從未執行的任務直接加入
                if task.last_run_at is None:
                    logger.debug(f"[find_due_tasks] Task ID {task.id} ({task.task_name}) added (never run).")
                    result_tasks.append(task)
                    continue

                # 確保 last_run_at 也是帶時區的
                last_run = task.last_run_at
                if last_run.tzinfo is None:
                    # 如果 last_run_at 沒有時區信息，因為寫是 UTC
                    last_run = enforce_utc_datetime_transform(last_run)
                    logger.debug(f"[find_due_tasks] Task ID {task.id}: Forced last_run_at to UTC: {last_run.isoformat()}")

                # 對於所有 cron 表達式，使用 croniter 計算下次執行時間
                try:
                    cron_now = croniter(cron_expression, now)
                    previous_scheduled_run = cron_now.get_prev(datetime)
                    # 確保 previous_scheduled_run 也有時區
                    if previous_scheduled_run.tzinfo is None:
                        previous_scheduled_run = enforce_utc_datetime_transform(previous_scheduled_run)
                        logger.debug(f"[find_due_tasks] Task ID {task.id}: Forced previous_scheduled_run to UTC: {previous_scheduled_run.isoformat()}")

                    # Log the comparison values
                    logger.debug(f"[find_due_tasks] Task ID {task.id} ({task.task_name}): last_run={last_run.isoformat()}, previous_scheduled_run={previous_scheduled_run.isoformat()}, now={now.isoformat()}")

                    # If the last run occurred *before* the most recent scheduled time slot,
                    # it means the task is pending (it missed that slot or hasn't run since).
                    if last_run < previous_scheduled_run:
                        logger.debug(f"[find_due_tasks] Task ID {task.id} added. Condition met: last_run ({last_run.isoformat()}) < previous_scheduled_run ({previous_scheduled_run.isoformat()})")
                        result_tasks.append(task)
                    else:
                        # If the last run was at or after the most recent scheduled time, it's not pending for that slot.
                        logger.debug(f"[find_due_tasks] Task ID {task.id} skipped. Condition not met: last_run ({last_run.isoformat()}) >= previous_scheduled_run ({previous_scheduled_run.isoformat()})")
                        continue

                except Exception as e:
                    # 防止 croniter 計算出錯導致整個查詢失敗
                    logger.error(f"計算任務 {task.id} 的下次執行時間時出錯 ({cron_expression}, {last_run}): {e}", exc_info=True)
                    continue

            return result_tasks

        return self.execute_query(
            get_due_tasks,
            err_msg=f"查詢待執行的 cron 表達式 {cron_expression} 的任務時發生錯誤"
        )

    def find_failed_tasks(self, days: int = 1) -> List[CrawlerTasks]:
        """獲取最近失敗的任務 (只查 is_active=True 的任務)"""
        if days < 0:
            days = 0 # 防止負數天數
        time_threshold = datetime.now(timezone.utc) - timedelta(days=days)

        return self.execute_query(
            lambda: self.session.query(self.model_class).filter(
                self.model_class.is_active == True, # 只關心活動任務的失敗狀態
                self.model_class.last_run_success == False,
                self.model_class.last_run_at.isnot(None), # 確保有執行過
                self.model_class.last_run_at >= time_threshold
            ).order_by(self.model_class.last_run_at.desc()).all(),
            err_msg=f"查詢最近 {days} 天失敗的活動任務時發生錯誤"
        )

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

    def advanced_search(self, **filters) -> Optional[Dict[str, Any]]:
        """
        進階搜尋任務

        Args:
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
            包含 'tasks' 列表和 'total_count' 的字典，或在錯誤時返回 None。
        """
        def build_and_run_query():
            query = self.session.query(self.model_class)

            # --- 過濾 ---
            # task_args_filter_parts = [] # 移除列表

            if 'task_name' in filters and filters['task_name']:
                query = query.filter(self.model_class.task_name.like(f"%{filters['task_name']}%"))
            if 'crawler_id' in filters and filters['crawler_id']:
                query = query.filter_by(crawler_id=filters['crawler_id'])
            if 'is_auto' in filters and filters['is_auto'] is not None:
                query = query.filter_by(is_auto=filters['is_auto'])
            if 'is_active' in filters and filters['is_active'] is not None:
                query = query.filter_by(is_active=filters['is_active'])
            if 'last_run_success' in filters and filters['last_run_success'] is not None:
                query = query.filter_by(last_run_success=filters['last_run_success'])
            if 'cron_expression' in filters and filters['cron_expression']:
                query = query.filter_by(cron_expression=filters['cron_expression'])

            if 'date_range' in filters and filters['date_range']:
                start_date, end_date = filters['date_range']
                if start_date:
                    query = query.filter(self.model_class.last_run_at >= enforce_utc_datetime_transform(start_date))
                if end_date:
                    # 結束日期通常包含當天，所以查詢到 end_date 的下一天 00:00
                    end_date_exclusive = enforce_utc_datetime_transform(end_date) + timedelta(days=1)
                    query = query.filter(self.model_class.last_run_at < end_date_exclusive)

            if 'has_notes' in filters and filters['has_notes'] is not None:
                if filters['has_notes'] is True:
                    query = query.filter(self.model_class.notes.isnot(None) & (self.model_class.notes != ''))
                else:
                    query = query.filter((self.model_class.notes == None) | (self.model_class.notes == ''))

            if 'task_status' in filters and filters['task_status']:
                status_value = filters['task_status'].value if isinstance(filters['task_status'], TaskStatus) else filters['task_status']
                query = query.filter_by(task_status=status_value)

            if 'scrape_phase' in filters and filters['scrape_phase']:
                phase_value = filters['scrape_phase'].value if isinstance(filters['scrape_phase'], ScrapePhase) else filters['scrape_phase']
                query = query.filter_by(scrape_phase=phase_value)

            if 'retry_count' in filters:
                retry_filter = filters['retry_count']
                if isinstance(retry_filter, dict):
                    if 'min' in retry_filter:
                        query = query.filter(self.model_class.retry_count >= retry_filter['min'])
                    if 'max' in retry_filter:
                        query = query.filter(self.model_class.retry_count <= retry_filter['max'])
                elif isinstance(retry_filter, int):
                    query = query.filter_by(retry_count=retry_filter)

            # --- 過濾 task_args (JSON) ---
            if 'ai_only' in filters and filters['ai_only'] is not None:
                # 直接應用過濾
                query = query.filter(self.model_class.task_args['ai_only'].as_boolean() == filters['ai_only'])

            if 'max_pages' in filters and filters['max_pages'] is not None:
                # 直接應用過濾
                query = query.filter(self.model_class.task_args['max_pages'].as_integer() == filters['max_pages'])

            if 'save_to_csv' in filters and filters['save_to_csv'] is not None:
                # 直接應用過濾
                query = query.filter(self.model_class.task_args['save_to_csv'].as_boolean() == filters['save_to_csv'])

            if 'scrape_mode' in filters and filters['scrape_mode']:
                mode_value = filters['scrape_mode'].value if isinstance(filters['scrape_mode'], ScrapeMode) else filters['scrape_mode']
                # 直接應用過濾
                query = query.filter(self.model_class.task_args['scrape_mode'].as_string() == mode_value)

            # --- 計算總數 (在分頁前) ---
            total_count = query.count()

            # --- 排序 ---
            sort_by = filters.get('sort_by', 'created_at') # 預設按創建時間
            sort_desc = filters.get('sort_desc', True) # 預設降冪
            if hasattr(self.model_class, sort_by):
                order_column = getattr(self.model_class, sort_by)
                query = query.order_by(desc(order_column) if sort_desc else asc(order_column))
            else:
                logger.warning(f"無效的排序欄位 '{sort_by}'，將使用預設排序 (created_at desc)。")
                query = query.order_by(desc(self.model_class.created_at))

            # --- 分頁 ---
            limit = filters.get('limit')
            offset = filters.get('offset')
            if offset is not None:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)

            # --- 執行查詢 ---
            tasks = query.all()
            
            return {'tasks': tasks, 'total_count': total_count}
        
        return self.execute_query(
            build_and_run_query,
            err_msg="進階搜尋任務時發生錯誤",
            exception_class=DatabaseOperationError
        )