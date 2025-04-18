from .base_repository import BaseRepository, SchemaType
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawler_tasks_schema import CrawlerTasksCreateSchema, CrawlerTasksUpdateSchema
from typing import List, Optional, Type, Any, Dict, Literal, overload
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
import logging
from src.error.errors import ValidationError, DatabaseOperationError
from src.utils.datetime_utils import enforce_utc_datetime_transform
from croniter import croniter

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

    def find_tasks_by_id(self, task_id: int, is_active: Optional[bool] = True) -> Optional[CrawlerTasks]:
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
        # 獲取所有活動的任務
        all_tasks = self.execute_query(
            lambda: self.session.query(self.model_class).filter(
                self.model_class.is_active == is_active
            ).all(),
            err_msg="查詢所有任務時發生錯誤"
        )

        # 在Python中過濾ai_only=True的任務
        result = []
        for task in all_tasks:
            # 確保 task_args 是字典
            if task.task_args and isinstance(task.task_args, dict) and task.task_args.get('ai_only') is True:
                result.append(task)

        return result

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
        切換任務的 AI 專用狀態。此方法不執行 commit。

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
        current_args = task.task_args.copy() if isinstance(task.task_args, dict) else {}

        # 獲取當前 ai_only 值並切換
        current_ai_only = current_args.get('ai_only', False)
        current_args['ai_only'] = not current_ai_only

        # 更新整個 task_args 字典
        task.task_args = current_args
        task.updated_at = datetime.now(timezone.utc)
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

    def get_tasks_count_by_crawler(self, crawler_id: int) -> int:
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

    def find_pending_tasks(self, cron_expression: str) -> List[CrawlerTasks]:
        """查詢需要執行的任務（根據 cron 表達式和上次執行時間, 只查 is_auto=True）"""
        try:
            croniter(cron_expression)
        except ValueError:
            error_msg = f"無效的 cron 表達式: {cron_expression}"
            logger.error(error_msg)
            raise ValidationError(error_msg)

        def get_pending_tasks():
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
            logger.debug(f"[find_pending_tasks] Current UTC time (now): {now.isoformat()}") # Log current time

            for task in all_relevant_tasks:
                # 從未執行的任務直接加入
                if task.last_run_at is None:
                    logger.debug(f"[find_pending_tasks] Task ID {task.id} ({task.task_name}) added (never run).")
                    result_tasks.append(task)
                    continue

                # 確保 last_run_at 也是帶時區的
                last_run = task.last_run_at
                if last_run.tzinfo is None:
                    # 如果 last_run_at 沒有時區信息，假設它是 UTC
                    last_run = enforce_utc_datetime_transform(last_run)
                    logger.debug(f"[find_pending_tasks] Task ID {task.id}: Forced last_run_at to UTC: {last_run.isoformat()}")

                # 對於所有 cron 表達式，使用 croniter 計算下次執行時間
                try:
                    cron = croniter(cron_expression, last_run)
                    next_run = cron.get_next(datetime)
                    # 確保 next_run 也有時區
                    if next_run.tzinfo is None:
                        next_run = enforce_utc_datetime_transform(next_run)
                        logger.debug(f"[find_pending_tasks] Task ID {task.id}: Forced next_run to UTC: {next_run.isoformat()}")

                    # Log the comparison values
                    logger.debug(f"[find_pending_tasks] Task ID {task.id} ({task.task_name}): last_run={last_run.isoformat()}, next_run={next_run.isoformat()}, now={now.isoformat()}, tolerance_window=1s")

                    # 只有下次執行時間已經過了（包含1秒容錯），才加入待執行列表
                    time_threshold = now + timedelta(seconds=1)
                    if next_run <= time_threshold:
                        logger.debug(f"[find_pending_tasks] Task ID {task.id} added. Condition met: next_run ({next_run.isoformat()}) <= now + 1s ({time_threshold.isoformat()})")
                        result_tasks.append(task)
                    else:
                        logger.debug(f"[find_pending_tasks] Task ID {task.id} skipped. Condition not met: next_run ({next_run.isoformat()}) > now + 1s ({time_threshold.isoformat()})")

                except Exception as e:
                    # 防止 croniter 計算出錯導致整個查詢失敗
                    logger.error(f"計算任務 {task.id} 的下次執行時間時出錯 ({cron_expression}, {last_run}): {e}", exc_info=True)
                    continue


            return result_tasks

        return self.execute_query(
            get_pending_tasks,
            err_msg=f"查詢待執行的 cron 表達式 {cron_expression} 的任務時發生錯誤"
        )

    def get_failed_tasks(self, days: int = 1) -> List[CrawlerTasks]:
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