from typing import Annotated, Optional, Any
from pydantic import BaseModel, BeforeValidator, model_validator
from datetime import datetime
from src.utils.model_utils import validate_str, validate_datetime, validate_boolean, validate_positive_int
from src.utils.schema_utils import validate_required_fields_schema, validate_update_schema
from src.models.base_schema import BaseCreateSchema, BaseUpdateSchema


# 通用字段定義
TaskId = Annotated[int, BeforeValidator(validate_positive_int("task_id", required=True))]
ArticlesCount = Annotated[Optional[int], BeforeValidator(validate_positive_int("articles_count"))]
Message = Annotated[Optional[str], BeforeValidator(validate_str("message", max_length=65536, required=False))]
StartTime = Annotated[Optional[datetime], BeforeValidator(validate_datetime("start_time", required=True))]
EndTime = Annotated[Optional[datetime], BeforeValidator(validate_datetime("end_time", required=False))]
Success = Annotated[Optional[bool], BeforeValidator(validate_boolean("success"))]

class CrawlerTaskHistoryCreateSchema(BaseCreateSchema):
    """爬蟲任務歷史創建模型"""
    task_id: TaskId
    start_time: StartTime = None
    end_time: EndTime = None
    success: Success = None
    message: Message = None
    articles_count: ArticlesCount = None

    @model_validator(mode='before')
    @classmethod
    def validate_required_fields(cls, data):
        """驗證必填欄位"""
        if isinstance(data, dict):
            required_fields = ['task_id']
            return validate_required_fields_schema(required_fields, data)

class CrawlerTaskHistoryUpdateSchema(BaseUpdateSchema):
    """爬蟲任務歷史更新模型"""
    end_time: Optional[EndTime] = None
    start_time: Optional[StartTime] = None
    success: Optional[Success] = None
    message: Optional[Message] = None
    articles_count: Optional[ArticlesCount] = None

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        """驗證更新操作"""
        if isinstance(data, dict):
            immutable_fields = ['task_id'] + cls._get_immutable_fields()
            updated_fields = ['end_time', 'start_time', 'success', 'message', 'articles_count'] + cls._get_updated_fields()
            return validate_update_schema(immutable_fields, updated_fields, data)
            