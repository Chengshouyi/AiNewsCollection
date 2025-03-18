from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import datetime
from .models import ValidationError as CustomValidationError

class SystemSettingsCreateSchema(BaseModel):
    crawler_name: str = Field(..., min_length=1, max_length=255, description="爬蟲名稱")
    crawl_interval: int = Field(..., gt=0, description="爬取間隔")
    is_active: bool = Field(True, description="是否啟用")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(default=None)
    last_crawl_time: Optional[datetime] = Field(default=None)
    
    @field_validator('crawler_name', mode='before')
    @classmethod
    def validate_crawler_name(cls, v):
        if not v or not v.strip():
            raise CustomValidationError("爬蟲名稱不能為空")
        if len(v) > 255:
            raise CustomValidationError("爬蟲名稱長度必須在1到255個字符之間")
        return v
    
    @field_validator('crawl_interval', mode='before')
    @classmethod
    def validate_crawl_interval(cls, v):
        if v is None:
            raise CustomValidationError("爬取間隔不能為空")
        if v <= 0:
            raise CustomValidationError("爬取間隔必須大於0")
        return v
    
    @field_validator('is_active', mode='before')
    @classmethod
    def validate_is_active(cls, v):
        if not isinstance(v, bool):
            raise CustomValidationError("is_active必須是布林值")
        return v

    @field_validator('created_at', mode='before')
    @classmethod
    def validate_created_at(cls, v):
        if not v:
            raise CustomValidationError("建立時間不能為空")
        return v

class SystemSettingsUpdateSchema(BaseModel):
    crawler_name: Optional[str] = Field(None, min_length=1, max_length=255, description="爬蟲名稱")
    crawl_interval: Optional[int] = Field(None, gt=0, description="爬取間隔")
    is_active: Optional[bool] = Field(None, description="是否啟用")
    updated_at: Optional[datetime] = Field(default=None)
    last_crawl_time: Optional[datetime] = Field(default=None)

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        if isinstance(data, dict):
            # 防止更新 created_at
            if 'created_at' in data:
                raise CustomValidationError("不允許更新 created_at 欄位")
            
            # 確保至少有一個欄位被更新
            update_fields = [k for k in data.keys() if k not in ['updated_at', 'created_at']]
            if not update_fields:
                raise CustomValidationError("必須提供至少一個要更新的欄位")
        
        return data

    @field_validator('crawler_name', mode='before')
    @classmethod
    def validate_crawler_name(cls, v):
        if v is None:
            return None
        if not v.strip():
            raise CustomValidationError("爬蟲名稱不能為空字串")
        if len(v) > 255:
            raise CustomValidationError("爬蟲名稱長度必須在1到255個字符之間")
        return v
    
    @field_validator('crawl_interval', mode='before')
    @classmethod
    def validate_crawl_interval(cls, v):
        if v is None:
            return None
        if v <= 0:
            raise CustomValidationError("爬取間隔必須大於0")
        return v
    
    @field_validator('is_active', mode='before')
    @classmethod
    def validate_is_active(cls, v):
        if not isinstance(v, bool):
            raise CustomValidationError("is_active必須是布林值")
        return v



