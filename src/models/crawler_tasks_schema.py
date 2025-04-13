from typing import Annotated, Optional, Any
from pydantic import BeforeValidator, model_validator
from datetime import datetime
from src.error.errors import ValidationError
from src.utils.model_utils import validate_str, validate_boolean, validate_positive_int, validate_cron_expression, validate_dict, validate_task_phase, validate_task_args
from src.utils.schema_utils import validate_required_fields_schema, validate_update_schema
from src.models.base_schema import BaseCreateSchema, BaseUpdateSchema
from src.utils.model_utils import TaskPhase
from src.models.crawler_tasks_model import TASK_ARGS_DEFAULT

# 通用字段定義
TaskName = Annotated[str, BeforeValidator(validate_str("task_name", max_length=255, required=True))]
CrawlerId = Annotated[int, BeforeValidator(validate_positive_int("crawler_id", is_zero_allowed=False, required=True))]
TaskArgs = Annotated[dict, BeforeValidator(validate_task_args("task_args", required=True))]
IsAuto = Annotated[bool, BeforeValidator(validate_boolean("is_auto", required=True))]
IsActive = Annotated[bool, BeforeValidator(validate_boolean("is_active", required=True))]
RetryCount = Annotated[int, BeforeValidator(validate_positive_int("retry_count", is_zero_allowed=True, required=False))]
Notes = Annotated[Optional[str], BeforeValidator(validate_str("notes", max_length=65536, required=False))]
CronExpression = Annotated[Optional[str], BeforeValidator(validate_cron_expression("cron_expression", max_length=255, min_length=5, required=False))]
LastRunMessage = Annotated[Optional[str], BeforeValidator(validate_str("last_run_message", max_length=65536, required=False))]
CurrentPhase = Annotated[Optional[TaskPhase], BeforeValidator(validate_task_phase("current_phase", required=True))]

class CrawlerTasksCreateSchema(BaseCreateSchema):
    """爬蟲任務創建模型"""
    task_name: TaskName
    crawler_id: CrawlerId
    is_auto: IsAuto = True
    is_active: IsActive = True
    task_args: TaskArgs = TASK_ARGS_DEFAULT
    notes: Notes = None
    last_run_at: Optional[datetime] = None
    last_run_success: Optional[bool] = None
    last_run_message: LastRunMessage = None
    cron_expression: CronExpression = None
    current_phase: CurrentPhase = TaskPhase.INIT
    retry_count: RetryCount = 0

    @model_validator(mode='before')
    @classmethod
    def validate_required_fields(cls, data):
        """驗證必填欄位"""
        if isinstance(data, dict):
            required_fields = CrawlerTasksCreateSchema.get_required_fields()
            return validate_required_fields_schema(required_fields, data)
        else:
            raise ValidationError("無效的資料格式，需要字典")

    @classmethod
    def get_required_fields(cls):
        return ['task_name', 'crawler_id', 'task_args', 'current_phase']

class CrawlerTasksUpdateSchema(BaseUpdateSchema):
    """爬蟲任務更新模型"""
    task_name: Optional[TaskName] = None
    is_auto: Optional[IsAuto] = None
    is_active: Optional[IsActive] = None
    task_args: Optional[TaskArgs] = None
    notes: Optional[Notes] = None
    last_run_at: Optional[datetime] = None
    last_run_success: Optional[bool] = None
    last_run_message: Optional[LastRunMessage] = None
    cron_expression: Optional[CronExpression] = None
    current_phase: Optional[CurrentPhase] = None
    retry_count: Optional[RetryCount] = None

    @classmethod
    def get_immutable_fields(cls):
        return ['crawler_id'] + BaseUpdateSchema.get_immutable_fields()
    
    @classmethod
    def get_updated_fields(cls):
        return ['task_name', 'is_auto', 'is_active', 'task_args', 'notes', 'last_run_at', 'last_run_success', 
                'last_run_message', 'cron_expression', 'current_phase', 'retry_count'] + BaseUpdateSchema.get_updated_fields()
    

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        """驗證更新操作"""
        if isinstance(data, dict):
            return validate_update_schema(cls.get_immutable_fields(), cls.get_updated_fields(), data)
        else:
            raise ValidationError("無效的資料格式，需要字典")
    