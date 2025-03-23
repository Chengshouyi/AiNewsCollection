from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import datetime
from src.error.errors import ValidationError

class CrawlerTasksCreateSchema(BaseModel):
    crawler_id: int = Field(..., gt=0, description="爬蟲ID")
    is_auto: bool = Field(True, description="是否自動爬取")
    ai_only: bool = Field(False, description="是否僅收集 AI 相關")
    notes: Optional[str] = Field(None, description="備註")
    created_at: datetime = Field(default_factory=datetime.now, description="建立時間")
    updated_at: Optional[datetime] = Field(default=None, description="更新時間")
    
    @model_validator(mode='before')
    @classmethod
    def validate_required_fields(cls, data):
        if isinstance(data, dict):
            required_fields = ['crawler_id']
            for field in required_fields:
                if field not in data:
                    raise ValidationError(f"{field}: do not be empty.")
        return data
    
    @field_validator('crawler_id', mode='before')
    @classmethod
    def validate_crawler_id(cls, value):
        if value is None:
            raise ValidationError("crawler_id: do not be empty.")
        if value <= 0:
            raise ValidationError("crawler_id: must be greater than 0.")
        return value
    
    @field_validator('is_auto', mode='before')
    @classmethod
    def validate_is_auto(cls, value):
        if not isinstance(value, bool):
            raise ValidationError("is_auto: must be a boolean value.")
        return value

    @field_validator('ai_only', mode='before')
    @classmethod
    def validate_ai_only(cls, value):
        if not isinstance(value, bool):
            raise ValidationError("ai_only: must be a boolean value.")
        return value

    @field_validator('created_at', mode='before')
    @classmethod
    def validate_created_at(cls, value):
        if not value:
            raise ValidationError("created_at: do not be empty.")
        return value

class CrawlerTasksUpdateSchema(BaseModel):
    is_auto: Optional[bool] = Field(None, description="是否自動爬取")
    ai_only: Optional[bool] = Field(None, description="是否僅收集 AI 相關")
    notes: Optional[str] = Field(None, description="備註")

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        if isinstance(data, dict):
            # 防止更新 created_at 和 crawler_id
            forbidden_fields = ['created_at', 'crawler_id']
            for field in forbidden_fields:
                if field in data:
                    raise ValidationError(f"do not allow to update {field} field.")
            
            # 確保至少有一個欄位被更新
            update_fields = [k for k in data.keys() if k not in ['updated_at', 'created_at']]
            if not update_fields:
                raise ValidationError("must provide at least one field to update.")
        
        return data

    @field_validator('is_auto', mode='before')
    @classmethod
    def validate_is_auto(cls, value):
        if value is not None and not isinstance(value, bool):
            raise ValidationError("is_auto: must be a boolean value.")
        return value

    @field_validator('ai_only', mode='before')
    @classmethod
    def validate_ai_only(cls, value):
        if value is not None and not isinstance(value, bool):
            raise ValidationError("ai_only: must be a boolean value.")
        return value 