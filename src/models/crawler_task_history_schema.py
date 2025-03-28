from typing import Annotated, Optional, Any
from pydantic import BaseModel, BeforeValidator, model_validator, Field
from datetime import datetime
from src.error.errors import ValidationError
from src.utils.model_utils import validate_str, validate_datetime, validate_boolean, validate_positive_int



# 通用字段定義
TaskId = Annotated[int, BeforeValidator(validate_positive_int("task_id", required=True))]
ArticlesCount = Annotated[int, BeforeValidator(validate_positive_int("articles_count", required=True))]
Message = Annotated[Optional[str], BeforeValidator(validate_str("message", max_length=65536, required=False))]
StartTime = Annotated[datetime, BeforeValidator(validate_datetime("start_time", required=True))]
EndTime = Annotated[Optional[datetime], BeforeValidator(validate_datetime("end_time", required=False))]
Success = Annotated[bool, BeforeValidator(validate_boolean("success", required=True))]

class CrawlerTaskHistoryCreateSchema(BaseModel):
    """爬蟲任務歷史創建模型"""
    task_id: TaskId
    start_time: StartTime = Field(default_factory=datetime.now)
    end_time: EndTime = None
    success: Success = False
    message: Message = None
    articles_count: ArticlesCount = Field(default=0, ge=0)

    @model_validator(mode='before')
    @classmethod
    def validate_required_fields(cls, data):
        """驗證必填欄位"""
        if isinstance(data, dict):
            if 'task_id' not in data:
                raise ValidationError("task_id: 不能為空")
            if 'start_time' not in data:
                data['start_time'] = datetime.now()
        return data

class CrawlerTaskHistoryUpdateSchema(BaseModel):
    """爬蟲任務歷史更新模型"""
    end_time: EndTime = None
    success: Optional[Success] = None
    message: Message = None
    articles_count: Optional[ArticlesCount] = Field(default=None, ge=0)

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        """驗證更新操作"""
        if isinstance(data, dict):
            immutable_fields = ['id', 'task_id', 'start_time', 'created_at']
            for field in immutable_fields:
                if field in data:
                    raise ValidationError(f"不允許更新 {field} 欄位")
            
            update_fields = [
                field for field in data.keys()
                if field not in ['updated_at'] + immutable_fields
            ]
            if not update_fields:
                raise ValidationError("必須提供至少一個要更新的欄位")
        return data