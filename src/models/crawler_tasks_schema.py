from typing import Annotated, Optional, Any
from pydantic import BeforeValidator, model_validator
from datetime import datetime
from src.error.errors import ValidationError
from src.utils.model_utils import validate_str, validate_boolean, validate_positive_int, validate_cron_expression, validate_dict
from src.utils.schema_utils import validate_required_fields_schema, validate_update_schema
from src.models.base_schema import BaseCreateSchema, BaseUpdateSchema
from src.models.crawler_tasks_model import TaskPhase

def validate_task_phase(v, field_name="current_phase", required=False):
    """驗證任務階段"""
    if v is None:
        if required:
            raise ValidationError(f"{field_name}: 不能為空")
        return None
    
    # 如果已經是枚舉類型，直接返回
    if isinstance(v, TaskPhase):
        return v
    
    # 如果是字串，嘗試轉換為枚舉
    try:
        # 處理不同大小寫的情況
        if isinstance(v, str):
            # 嘗試直接轉換
            try:
                return TaskPhase(v)
            except ValueError:
                # 嘗試大寫轉換
                try:
                    return TaskPhase(v.upper())
                except ValueError:
                    # 嘗試小寫轉換
                    return TaskPhase(v.lower())
    except ValueError:
        raise ValidationError(f"{field_name}: 無效的任務階段值，可用值: {', '.join([e.value for e in TaskPhase])}")
    
    raise ValidationError(f"{field_name}: 必須是TaskPhase枚舉或其字串值")



# 通用字段定義
TaskName = Annotated[str, BeforeValidator(validate_str("task_name", max_length=255, required=True))]
CrawlerId = Annotated[int, BeforeValidator(validate_positive_int("crawler_id", is_zero_allowed=False, required=True))]
TaskArgs = Annotated[dict, BeforeValidator(validate_dict("task_args", required=True))]
IsAuto = Annotated[bool, BeforeValidator(validate_boolean("is_auto", required=True))]
AiOnly = Annotated[bool, BeforeValidator(validate_boolean("ai_only", required=True))]
Notes = Annotated[Optional[str], BeforeValidator(validate_str("notes", max_length=65536, required=False))]
CronExpression = Annotated[Optional[str], BeforeValidator(validate_cron_expression("cron_expression", max_length=255, min_length=5, required=False))]
LastRunMessage = Annotated[Optional[str], BeforeValidator(validate_str("last_run_message", max_length=65536, required=False))]
TaskPhaseDef = Annotated[Optional[TaskPhase], BeforeValidator(validate_task_phase)]
MaxRetries = Annotated[Optional[int], BeforeValidator(validate_positive_int("max_retries", is_zero_allowed=False, required=True))]
RetryCount = Annotated[Optional[int], BeforeValidator(validate_positive_int("retry_count", is_zero_allowed=True, required=True))]

class CrawlerTasksCreateSchema(BaseCreateSchema):
    """爬蟲任務創建模型"""
    task_name: TaskName
    crawler_id: CrawlerId
    is_auto: IsAuto = True
    ai_only: AiOnly = False
    task_args: TaskArgs = {}
    notes: Notes = None
    last_run_at: Optional[datetime] = None
    last_run_success: Optional[bool] = None
    last_run_message: LastRunMessage = None
    cron_expression: CronExpression = None
    current_phase: TaskPhaseDef
    max_retries: MaxRetries
    retry_count: RetryCount

    @model_validator(mode='before')
    @classmethod
    def validate_required_fields(cls, data):
        """驗證必填欄位"""
        if isinstance(data, dict):
            required_fields = CrawlerTasksCreateSchema.get_required_fields()
            if data.get('is_auto') is True:
                if data.get('cron_expression') is None:
                    raise ValidationError("cron_expression: 當設定為自動執行時,此欄位不能為空")
            return validate_required_fields_schema(required_fields, data)

    @classmethod
    def get_required_fields(cls):
        return ['task_name', 'crawler_id', 'task_args', 'ai_only', 'current_phase', 'max_retries', 'retry_count']

class CrawlerTasksUpdateSchema(BaseUpdateSchema):
    """爬蟲任務更新模型"""
    task_name: Optional[TaskName] = None
    is_auto: Optional[IsAuto] = None
    ai_only: Optional[AiOnly] = None
    task_args: Optional[TaskArgs] = None
    notes: Optional[Notes] = None
    last_run_at: Optional[datetime] = None
    last_run_success: Optional[bool] = None
    last_run_message: Optional[LastRunMessage] = None
    cron_expression: Optional[CronExpression] = None
    current_phase: Optional[TaskPhaseDef] = None
    max_retries: Optional[MaxRetries] = None
    retry_count: Optional[RetryCount] = None


    @classmethod
    def get_immutable_fields(cls):
        return ['crawler_id'] + BaseUpdateSchema.get_immutable_fields()
    
    @classmethod
    def get_updated_fields(cls):
        return ['task_name', 'is_auto', 'ai_only', 'task_args', 'notes', 'last_run_at', 'last_run_success', 'last_run_message', 'cron_expression', 'current_phase', 'max_retries', 'retry_count'] + BaseUpdateSchema.get_updated_fields()
    

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        """驗證更新操作"""
        if isinstance(data, dict):
            if data.get('is_auto') is True:
                if data.get('cron_expression') is None:
                    raise ValidationError("cron_expression: 當設定為自動執行時,此欄位不能為空")
            return validate_update_schema(cls.get_immutable_fields(), cls.get_updated_fields(), data)
    