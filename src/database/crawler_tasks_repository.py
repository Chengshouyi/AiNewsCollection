from .base_repository import BaseRepository, SchemaType
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawler_tasks_schema import CrawlerTasksCreateSchema, CrawlerTasksUpdateSchema
from typing import List, Optional, Type, Any, Dict
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
import logging
from src.error.errors import ValidationError, DatabaseOperationError
from src.utils.datetime_utils import enforce_utc_datetime_transform
from croniter import croniter
from src.utils.transform_utils import convert_to_dict
# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CrawlerTasksRepository(BaseRepository['CrawlerTasks']):
    """CrawlerTasks 特定的Repository"""
    
    def get_schema_class(self, schema_type: SchemaType = SchemaType.CREATE) -> Type[BaseModel]:
        """提供對應的 schema class"""
        if schema_type == SchemaType.CREATE:
            return CrawlerTasksCreateSchema
        elif schema_type == SchemaType.UPDATE:
            return CrawlerTasksUpdateSchema
        raise ValueError(f"未支援的 schema 類型: {schema_type}")

    def create(self, entity_data: Dict[str, Any]) -> Optional[CrawlerTasks]:
        """
        創建爬蟲任務，先進行 Pydantic 驗證，然後調用內部創建。
        
        Args:
            entity_data: 實體資料
            
        Returns:
            創建的爬蟲任務實體
        """
        try:
            # 1. 設定特定預設值（如果需要）
            # 例如: entity_data.setdefault('is_auto', False)
            
            # 2. 執行 Pydantic 驗證
            validated_data = self.validate_data(entity_data, SchemaType.CREATE)
            
            # 3. 將已驗證的資料傳給內部方法
            return self._create_internal(validated_data)
        except ValidationError as e:
            logger.error(f"創建 CrawlerTask 驗證失敗: {e}")
            raise # 重新拋出讓 Service 層處理
        except DatabaseOperationError: # 捕捉來自 _create_internal 的錯誤
            raise # 重新拋出
        except Exception as e: # 捕捉其他意外錯誤
            logger.error(f"創建 CrawlerTask 時發生未預期錯誤: {e}", exc_info=True)
            raise DatabaseOperationError(f"創建 CrawlerTask 時發生未預期錯誤: {e}") from e

    def update(self, entity_id: int, entity_data: Dict[str, Any]) -> Optional[CrawlerTasks]:
        """
        更新爬蟲任務，先進行 Pydantic 驗證，然後調用內部更新。
        
        Args:
            entity_id: 實體ID
            entity_data: 要更新的實體資料
            
        Returns:
            更新後的爬蟲任務實體，如果實體不存在則返回None
        """
        try:
            # 1. 檢查實體是否存在
            existing_entity = self.get_by_id(entity_id)
            if not existing_entity:
                logger.warning(f"更新爬蟲任務失敗，ID不存在: {entity_id}")
                return None
                
            # 如果更新資料為空，直接返回已存在的實體
            if not entity_data:
                return existing_entity
            
            # 2. 執行 Pydantic 驗證 (獲取 update payload)
            update_payload = self.validate_data(entity_data, SchemaType.UPDATE)
            
            # 3. 將已驗證的 payload 傳給內部方法
            return self._update_internal(entity_id, update_payload)
        except ValidationError as e:
            logger.error(f"更新 CrawlerTask (ID={entity_id}) 驗證失敗: {e}")
            raise # 重新拋出
        except DatabaseOperationError: # 捕捉來自 _update_internal 的錯誤
            raise # 重新拋出
        except Exception as e: # 捕捉其他意外錯誤
            logger.error(f"更新 CrawlerTask (ID={entity_id}) 時發生未預期錯誤: {e}", exc_info=True)
            raise DatabaseOperationError(f"更新 CrawlerTask (ID={entity_id}) 時發生未預期錯誤: {e}") from e

    def find_tasks_by_id(self, task_id: int, is_active: Optional[bool] = True) -> Optional[CrawlerTasks]:
        """查詢特定任務
        
        Args:
            task_id: 任務ID
            is_active: 是否只返回啟用狀態的任務
            
        Returns:
            CrawlerTasks: 任務實體
        """
        if is_active is None:
            return self.execute_query(
                lambda: self.session.query(self.model_class).filter_by(id=task_id).first(),
                err_msg=f"查詢任務ID {task_id} 時發生錯誤"
            )
        
        else:
            return self.execute_query(
                lambda: self.session.query(self.model_class).filter_by(id=task_id, is_active=is_active).first(),
                err_msg=f"查詢任務ID {task_id} 時發生錯誤"
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
            if task.task_args and isinstance(task.task_args, dict) and task.task_args.get('ai_only') is True:
                result.append(task)
                
        return result
    
    def find_scheduled_tasks(self, is_active: bool = True) -> List[CrawlerTasks]:
        """查詢已排程的任務"""
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter_by(is_active=is_active, is_scheduled=True).all(),
            err_msg="查詢已排程的任務時發生錯誤"
        )
    
    def toggle_scheduled_status(self, task_id: int) -> bool:
        """切換任務的排程狀態"""
        task = self.get_by_id(task_id)
        if not task:
            return False    
        
        return self.execute_query(
            lambda: self._toggle_status(task, 'is_scheduled'),
            err_msg=f"切換任務ID {task_id} 的排程狀態時發生錯誤"
        )
    

    def toggle_auto_status(self, task_id: int) -> bool:
        """切換任務的自動執行狀態"""
        task = self.get_by_id(task_id)
        if not task:
            return False
            
        return self.execute_query(
            lambda: self._toggle_status(task, 'is_auto'),
            err_msg=f"切換任務ID {task_id} 的自動執行狀態時發生錯誤"
        )
    
    def toggle_ai_only_status(self, task_id: int) -> bool:
        """切換任務的 AI 專用狀態"""
        task = self.get_by_id(task_id)
        if not task:
            return False
        
        try:
            # 獲取當前 task_args
            current_args = task.task_args.copy() if task.task_args else {}
            
            # 獲取當前 ai_only 值並切換
            current_ai_only = current_args.get('ai_only', False)
            current_args['ai_only'] = not current_ai_only
            
            # 更新整個 task_args 字典
            task.task_args = current_args
            task.updated_at = datetime.now(timezone.utc)
            
            # 直接提交更改
            self.session.commit()
            logger.info(f"成功切換任務 ID {task_id} 的 AI 專用狀態: {current_ai_only} -> {not current_ai_only}")
            return True
        except Exception as e:
            logger.error(f"切換任務ID {task_id} 的 AI 專用狀態時發生錯誤: {e}")
            self.session.rollback()
            raise DatabaseOperationError(f"切換任務ID {task_id} 的 AI 專用狀態時發生錯誤: {e}") from e
            

    def toggle_active_status(self, task_id: int) -> bool:
        """切換任務的啟用狀態"""
        task = self.get_by_id(task_id)
        if not task:
            return False
        
        return self.execute_query(
            lambda: self._toggle_status(task, 'is_active'),
            err_msg=f"切換任務ID {task_id} 的啟用狀態時發生錯誤"
        )

    def _toggle_status(self, task: CrawlerTasks, field: str) -> bool:
        """內部方法：切換狀態"""
        setattr(task, field, not getattr(task, field))
        task.updated_at = datetime.now(timezone.utc)
        self.session.commit()
        return True
        
    def update_last_run(self, task_id: int, success: bool, message: Optional[str] = None) -> bool:
        """更新任務的最後執行狀態，需要同時更新多個相關欄位"""
        task = self.get_by_id(task_id)
        if not task:
            return False
            
        def update_last_run_status():
            # 使用 UTC 時間
            now = datetime.now(timezone.utc)
            task.last_run_at = now
            task.last_run_success = success
            if message:
                task.last_run_message = message
            task.updated_at = now
            self.session.commit()
            return True
            
        return self.execute_query(
            update_last_run_status,
            err_msg=f"更新任務ID {task_id} 的最後執行狀態時發生錯誤"
        )

    def update_notes(self, task_id: int, new_notes: str) -> bool:
        """更新任務備註"""
        task = self.get_by_id(task_id)
        if not task:
            return False
            
        return self.execute_query(
            lambda: self._update_field(task, 'notes', new_notes),
            err_msg=f"更新任務ID {task_id} 的備註時發生錯誤"
        )
    
    def _update_field(self, task: CrawlerTasks, field: str, value: Any) -> bool:
        """內部方法：更新欄位"""
        setattr(task, field, value)
        task.updated_at = datetime.now(timezone.utc)
        self.session.commit()
        return True
    
    def find_tasks_with_notes(self) -> List[CrawlerTasks]:
        """查詢所有有備註的任務"""
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter(
                self.model_class.notes.isnot(None)
            ).all(),
            err_msg="查詢有備註的任務時發生錯誤"
        )
    
    def find_tasks_by_multiple_crawlers(self, crawler_ids: List[int]) -> List[CrawlerTasks]:
        """根據多個爬蟲ID查詢任務"""
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
        """根據 cron 表達式查詢任務"""
        try:
            # 驗證 cron 表達式
            from croniter import croniter
            croniter(cron_expression)
        except ValueError:
            error_msg = f"無效的 cron 表達式: {cron_expression}"
            logger.error(error_msg)
            raise ValidationError(error_msg)
        
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter_by(
                cron_expression=cron_expression,
                is_auto=True  # 只查詢自動執行的任務
            ).all(),
            err_msg=f"查詢 cron 表達式 {cron_expression} 的任務時發生錯誤"
        )

    def find_pending_tasks(self, cron_expression: str) -> List[CrawlerTasks]:
        """查詢需要執行的任務（根據 cron 表達式和上次執行時間）"""
        try:
            croniter(cron_expression)
        except ValueError:
            error_msg = f"無效的 cron 表達式: {cron_expression}"
            logger.error(error_msg)
            raise ValidationError(error_msg)
        
        def get_pending_tasks():
            all_tasks = self.session.query(self.model_class).filter(
                self.model_class.cron_expression == cron_expression,
                self.model_class.is_auto == True
            ).all()
            
            # 使用 UTC 時間
            now = datetime.now(timezone.utc)
            result_tasks = []
            
            for task in all_tasks:
                # 從未執行的任務直接加入
                if task.last_run_at is None:
                    result_tasks.append(task)
                    continue
                    
                # 確保 last_run_at 也是帶時區的
                last_run = task.last_run_at
                if last_run.tzinfo is None:
                    # 如果 last_run_at 沒有時區信息，假設它是 UTC
                    last_run = enforce_utc_datetime_transform(last_run)
                    
                # 特殊處理每小時執行的任務 (0 * * * *)
                if cron_expression == "0 * * * *":
                    # 檢查上次執行時間是否超過1小時
                    if now - last_run >= timedelta(hours=1):
                        result_tasks.append(task)
                    continue
                    
                # 對於其他 cron 表達式，使用 croniter 計算下次執行時間
                cron = croniter(cron_expression, last_run)
                next_run = cron.get_next(datetime)
                # 確保 next_run 也有時區
                if next_run.tzinfo is None:
                    next_run = enforce_utc_datetime_transform(next_run)
                # 只有下次執行時間已經過了，才加入待執行列表
                if next_run <= now:
                    result_tasks.append(task)
                    
            return result_tasks
            
        return self.execute_query(
            get_pending_tasks,
            err_msg=f"查詢待執行的 cron 表達式 {cron_expression} 的任務時發生錯誤"
        )

    def get_failed_tasks(self, days: int = 1) -> List[CrawlerTasks]:
        """獲取最近失敗的任務"""
        time_threshold = datetime.now(timezone.utc) - timedelta(days=days)
        
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter(
                self.model_class.last_run_success == False,
                self.model_class.last_run_at >= time_threshold
            ).order_by(self.model_class.last_run_at.desc()).all(),
            err_msg=f"查詢最近 {days} 天失敗的任務時發生錯誤"
        )

    def convert_to_local_time(self, utc_time, timezone_str='Asia/Taipei'):
        """將 UTC 時間轉換為指定時區時間"""
        import pytz
        local_tz = pytz.timezone(timezone_str)
        return utc_time.astimezone(local_tz)
