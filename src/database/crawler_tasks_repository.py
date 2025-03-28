from .base_repository import BaseRepository, SchemaType
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawler_tasks_schema import CrawlerTasksCreateSchema, CrawlerTasksUpdateSchema
from typing import List, Optional, Type, Any, Dict
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from src.config import get_system_process_timezone
import logging
from src.error.errors import ValidationError

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

    def _validate_required_fields(self, entity_data: Any, existing_entity: Optional[CrawlerTasks] = None) -> Dict[str, Any]:
        """驗證並補充必填欄位"""
        # 轉換為字典
        if isinstance(entity_data, dict):
            processed_data = entity_data.copy()
        elif hasattr(entity_data, 'dict') and callable(entity_data.dict):
            # 處理 Pydantic 模型
            processed_data = entity_data.dict(exclude_unset=True)
        elif hasattr(entity_data, '__dict__'):
            # 處理普通物件
            processed_data = {k: v for k, v in entity_data.__dict__.items() 
                             if not k.startswith('_')}
        else:
            raise ValidationError("無效的資料格式，需要字典或支援轉換的物件")
        
        # 檢查必填欄位
        if not existing_entity:  # 只在創建時檢查
            if 'crawler_id' not in processed_data or not processed_data.get('crawler_id'):
                raise ValidationError("crawler_id: 不能為空")
            
        # 檢查 cron_expression
        if processed_data.get('is_auto') is True:
            if 'cron_expression' not in processed_data or not processed_data.get('cron_expression'):
                raise ValidationError("當設定為自動執行時，cron_expression 不能為空")
            
        return processed_data

    def create(self, entity_data: Dict[str, Any]) -> Optional[CrawlerTasks]:
        """
        創建爬蟲任務，添加針對 CrawlerTasks 的特殊驗證
        
        Args:
            entity_data: 實體資料
            
        Returns:
            創建的爬蟲任務實體
        """
        # 驗證並補充必填欄位
        validated_data = self._validate_required_fields(entity_data)
        
        # 獲取並使用適當的schema進行驗證和創建
        schema_class = self.get_schema_class(SchemaType.CREATE)
        return self._create_internal(validated_data, schema_class)

    def update(self, entity_id: int, entity_data: Dict[str, Any]) -> Optional[CrawlerTasks]:
        """
        更新爬蟲任務，添加針對 CrawlerTasks 的特殊驗證
        
        Args:
            entity_id: 實體ID
            entity_data: 要更新的實體資料
            
        Returns:
            更新後的爬蟲任務實體，如果實體不存在則返回None
        """
        # 檢查實體是否存在
        existing_entity = self.get_by_id(entity_id)
        if not existing_entity:
            logger.warning(f"更新爬蟲任務失敗，ID不存在: {entity_id}")
            return None
        
        # 如果更新資料為空，直接返回已存在的實體
        if not entity_data:
            return existing_entity
            
        # 驗證並補充必填欄位
        validated_data = self._validate_required_fields(entity_data, existing_entity)
        
        # 獲取並使用適當的schema進行驗證和更新
        schema_class = self.get_schema_class(SchemaType.UPDATE)
        return self._update_internal(entity_id, validated_data, schema_class)

    def find_by_crawler_id(self, crawler_id: int) -> List[CrawlerTasks]:
        """根據爬蟲ID查詢相關的任務"""
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter_by(crawler_id=crawler_id).all(),
            err_msg=f"查詢爬蟲ID {crawler_id} 的任務時發生錯誤"
        )
    
    def find_auto_tasks(self) -> List[CrawlerTasks]:
        """查詢所有自動執行的任務"""
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter_by(is_auto=True).all(),
            err_msg="查詢自動執行任務時發生錯誤"
        )
    
    def find_ai_only_tasks(self) -> List[CrawlerTasks]:
        """查詢所有僅收集AI相關的任務"""
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter_by(ai_only=True).all(),
            err_msg="查詢僅收集AI相關的任務時發生錯誤"
        )
    
    def find_tasks_by_crawler_and_auto(self, crawler_id: int, is_auto: bool) -> List[CrawlerTasks]:
        """根據爬蟲ID和自動執行狀態查詢任務"""
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter_by(
                crawler_id=crawler_id,
                is_auto=is_auto
            ).all(),
            err_msg=f"查詢爬蟲ID {crawler_id} 和自動執行狀態 {is_auto} 的任務時發生錯誤"
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
        """切換任務的AI收集狀態"""
        task = self.get_by_id(task_id)
        if not task:
            return False
            
        return self.execute_query(
            lambda: self._toggle_status(task, 'ai_only'),
            err_msg=f"切換任務ID {task_id} 的AI收集狀態時發生錯誤"
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
            from croniter import croniter
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
            now = datetime.now(get_system_process_timezone())
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
                    last_run = last_run.replace(tzinfo=get_system_process_timezone())
                    
                # 使用 croniter 計算下次執行時間（使用 UTC）
                cron = croniter(cron_expression, last_run)
                next_run = cron.get_next(datetime)
                # 確保 next_run 也有時區
                if next_run.tzinfo is None:
                    next_run = next_run.replace(tzinfo=get_system_process_timezone())
                    
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
