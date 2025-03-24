from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import datetime
from src.error.errors import ValidationError

class CrawlerTaskHistoryCreateSchema(BaseModel):
    task_id: int = Field(..., gt=0, description="爬蟲任務ID")
    start_time: datetime = Field(default_factory=datetime.now, description="開始時間")
    end_time: Optional[datetime] = Field(None, description="結束時間")
    success: bool = Field(False, description="是否成功")
    message: Optional[str] = Field(None, description="訊息")
    articles_count: int = Field(0, ge=0, description="文章數量")
    
    @model_validator(mode='before')
    @classmethod
    def validate_required_fields(cls, data):
        if isinstance(data, dict):
            required_fields = ['task_id']
            for field in required_fields:
                if field not in data:
                    raise ValidationError(f"{field}: do not be empty.")
        return data
    
    @field_validator('task_id', mode='before')
    @classmethod
    def validate_task_id(cls, value):
        if value is None:
            raise ValidationError("task_id: do not be empty.")
        if value <= 0:
            raise ValidationError("task_id: must be greater than 0.")
        return value
    
    @field_validator('start_time', mode='before')
    @classmethod
    def validate_start_time(cls, value):
        if not value:
            raise ValidationError("start_time: do not be empty.")
        return value
    
    @field_validator('end_time', mode='before')
    @classmethod
    def validate_end_time(cls, value):
        if value is not None and isinstance(value, datetime):
            # 如果提供了結束時間，可以在這裡加入其他驗證邏輯
            pass
        return value
    
    @field_validator('success', mode='before')
    @classmethod
    def validate_success(cls, value):
        if not isinstance(value, bool):
            raise ValidationError("success: must be a boolean value.")
        return value
    
    @field_validator('articles_count', mode='before')
    @classmethod
    def validate_articles_count(cls, value):
        if value is None:
            return 0
        try:
            articles_count = int(value)
            if articles_count < 0:
                raise ValidationError("articles_count: must be greater than or equal to 0.")
            return articles_count
        except (ValueError, TypeError):
            raise ValidationError("articles_count: must be an integer.")

class CrawlerTaskHistoryUpdateSchema(BaseModel):
    end_time: Optional[datetime] = Field(None, description="結束時間")
    success: Optional[bool] = Field(None, description="是否成功")
    message: Optional[str] = Field(None, description="訊息")
    articles_count: Optional[int] = Field(None, ge=0, description="文章數量")

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        if isinstance(data, dict):
            # 防止更新 id, task_id 和 start_time
            forbidden_fields = ['id', 'task_id', 'start_time']
            for field in forbidden_fields:
                if field in data:
                    raise ValidationError(f"do not allow to update {field} field.")
            
            # 確保至少有一個欄位被更新
            update_fields = [k for k in data.keys()]
            if not update_fields:
                raise ValidationError("must provide at least one field to update.")
        
        return data

    @field_validator('end_time', mode='before')
    @classmethod
    def validate_end_time(cls, value):
        if value is not None and not isinstance(value, datetime):
            raise ValidationError("end_time: must be a datetime value.")
        return value

    @field_validator('success', mode='before')
    @classmethod
    def validate_success(cls, value):
        if value is not None and not isinstance(value, bool):
            raise ValidationError("success: must be a boolean value.")
        return value
    
    @field_validator('articles_count', mode='before')
    @classmethod
    def validate_articles_count(cls, value):
        if value is None:
            return value
        try:
            articles_count = int(value)
            if articles_count < 0:
                raise ValidationError("articles_count: must be greater than or equal to 0.")
            return articles_count
        except (ValueError, TypeError):
            raise ValidationError("articles_count: must be an integer.") 