from .base_repository import BaseRepository, SchemaType
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawler_tasks_schema import CrawlerTasksCreateSchema, CrawlerTasksUpdateSchema
from typing import List, Optional, Type, Any, Dict
from datetime import datetime, timedelta
from pydantic import BaseModel
import logging
from pydantic import ValidationError

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

    def _validate_required_fields(self, entity_data: Dict[str, Any], existing_entity: Optional[CrawlerTasks] = None) -> Dict[str, Any]:
        """
        驗證並補充必填欄位
        
        Args:
            entity_data: 實體資料
            existing_entity: 現有實體 (用於更新時)
            
        Returns:
            處理後的實體資料
        """
        # 深度複製避免修改原始資料
        processed_data = entity_data.copy()
        
        # 檢查必填欄位，必須移除不可更新的欄位
        required_fields = ['schedule', 'is_auto']
        
        # 如果是更新操作，從現有實體中補充必填欄位
        if existing_entity:
            for field in required_fields:
                if field not in processed_data and hasattr(existing_entity, field):
                    processed_data[field] = getattr(existing_entity, field)
        
        # 檢查是否仍然缺少必填欄位
        missing_fields = [field for field in required_fields if field not in processed_data or processed_data[field] is None]
        if missing_fields:
            raise ValidationError(f"缺少必填欄位: {', '.join(missing_fields)}")
            
        # 檢查 schedule 是否有效
        if 'schedule' in processed_data:
            valid_schedules = ['hourly', 'daily', 'weekly']
            if processed_data['schedule'] not in valid_schedules:
                raise ValidationError(f"無效的排程類型 '{processed_data['schedule']}'，有效選項為: {', '.join(valid_schedules)}")
            
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
        task.updated_at = datetime.now()
        self.session.commit()
        return True
        
    def update_last_run(self, task_id: int, success: bool, message: Optional[str] = None) -> bool:
        """更新任務的最後執行狀態，需要同時更新多個相關欄位"""
        task = self.get_by_id(task_id)
        if not task:
            return False
            
        def update_last_run_status():
            # 確保同時更新所有執行相關的欄位
            task.last_run_at = datetime.now()
            task.last_run_success = success
            if message:
                task.last_run_message = message
            task.updated_at = datetime.now()
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
        task.updated_at = datetime.now()
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

    def find_tasks_by_schedule(self, schedule: str) -> List[CrawlerTasks]:
        """根據排程類型查詢任務"""
        if schedule not in ['hourly', 'daily', 'weekly']:
            raise ValueError("無效的排程類型")
            
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter_by(
                schedule=schedule,
                is_auto=True  # 只查詢自動執行的任務
            ).all(),
            err_msg=f"查詢 {schedule} 排程的任務時發生錯誤"
        )

    def find_pending_tasks(self, schedule: str) -> List[CrawlerTasks]:
        """查詢需要執行的任務（根據排程和上次執行時間）"""
        if schedule not in ['hourly', 'daily', 'weekly']:
            raise ValueError("無效的排程類型")
            
        def get_pending_tasks():
            # 把時間計算邏輯移到 Python 層面，而不是在 SQL 層面
            all_tasks = self.session.query(self.model_class).filter(
                self.model_class.schedule == schedule,
                self.model_class.is_auto == True
            ).all()
            
            # 在 Python 中進行時間比較
            now = datetime.now()
            result_tasks = []
            
            for task in all_tasks:
                # 從未執行的任務
                if task.last_run_at is None:
                    result_tasks.append(task)
                    continue
                    
                # 根據排程類型檢查時間差
                if schedule == 'hourly' and (now - task.last_run_at > timedelta(hours=1)):
                    result_tasks.append(task)
                elif schedule == 'daily' and (now - task.last_run_at > timedelta(days=1)):
                    result_tasks.append(task)
                elif schedule == 'weekly' and (now - task.last_run_at > timedelta(weeks=1)):
                    result_tasks.append(task)
                    
            return result_tasks
            
        return self.execute_query(
            get_pending_tasks,
            err_msg=f"查詢待執行的 {schedule} 排程任務時發生錯誤"
        )

    def get_failed_tasks(self, days: int = 1) -> List[CrawlerTasks]:
        """獲取最近失敗的任務"""
        time_threshold = datetime.now() - timedelta(days=days)
        
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter(
                self.model_class.last_run_success == False,
                self.model_class.last_run_at >= time_threshold
            ).order_by(self.model_class.last_run_at.desc()).all(),
            err_msg=f"查詢最近 {days} 天失敗的任務時發生錯誤"
        )
