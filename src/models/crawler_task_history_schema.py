from typing import Annotated, Optional, Any
from pydantic import BaseModel, BeforeValidator, model_validator, Field
from datetime import datetime
from src.error.errors import ValidationError
from src.utiles.model_utiles import validate_optional_str, validate_datetime, validate_boolean

def validate_task_id(value: Any) -> int:
    """任務ID驗證"""
    try:
        value = int(value)
    except (ValueError, TypeError):
        raise ValidationError("task_id: 必須是整數")
    
    if not value or value <= 0:
        raise ValidationError("task_id: 不能為空且必須大於0")
    
    return value

def validate_articles_count(value: Any) -> int:
    """文章數量驗證"""
    if value is None:
        return 0
    
    # 檢查浮點數
    if isinstance(value, float) and value != int(value):
        raise ValidationError("articles_count: 必須是整數")
    
    # 字串轉換檢查
    if isinstance(value, str):
        try:
            # 檢查是否包含小數點
            if '.' in value:
                raise ValidationError("articles_count: 必須是整數")
            value = int(value)
        except ValueError:
            raise ValidationError("articles_count: 必須是整數")
    
    # 其他類型轉換
    try:
        value = int(value)
    except (ValueError, TypeError):
        raise ValidationError("articles_count: 必須是整數")
    
    if value < 0:
        raise ValidationError("articles_count: 不能小於0")
    
    return value

# 通用字段定義
TaskId = Annotated[int, BeforeValidator(validate_task_id)]
ArticlesCount = Annotated[int, BeforeValidator(validate_articles_count)]
Message = Annotated[Optional[str], BeforeValidator(validate_optional_str("message", 65536))]
StartTime = Annotated[datetime, BeforeValidator(lambda v: validate_datetime("start_time", v))]
EndTime = Annotated[Optional[datetime], BeforeValidator(lambda v: validate_datetime("end_time", v))]
Success = Annotated[bool, BeforeValidator(validate_boolean("success"))]

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