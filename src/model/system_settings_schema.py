from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import datetime

class SystemSettingsCreateSchema(BaseModel):
    crawler_name: str = Field(..., min_length=1, max_length=255)
    crawl_interval: int = Field(..., ge=0)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(default=None)
    last_crawl_time: Optional[datetime] = Field(default=None)
    
    @field_validator('crawler_name')
    @classmethod
    def validate_crawler_name(cls, v):
        if not v:
            raise ValueError("爬蟲名稱不能為空")
        if len(v) > 255 or len(v) < 1:
            raise ValueError("爬蟲名稱長度必須在1到255個字符之間")
        return v
    
    @field_validator('crawl_interval')
    @classmethod
    def validate_crawl_interval(cls, v):
        if not v:
            raise ValueError("爬取間隔不能為空")
        if v < 0:
            raise ValueError("爬取間隔必須大於0")
        return v
    
    @field_validator('is_active')
    @classmethod
    def validate_is_active(cls, v):
        if not isinstance(v, bool):
            raise ValueError("is_active必須是布林值")
        return v

    @field_validator('created_at')
    @classmethod
    def validate_created_at(cls, v):
        if not v:
            raise ValueError("建立時間不能為空")
        return v

class SystemSettingsUpdateSchema(BaseModel):
    crawler_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    crawl_interval: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
    last_crawl_time: Optional[datetime] = Field(default=None)

    @model_validator(mode='before')
    @classmethod
    def remove_created_at(cls, data):
        if isinstance(data, dict) and 'created_at' in data:
            raise ValueError("不允許更新 created_at 欄位")
        return data

    @field_validator('crawler_name')
    @classmethod
    def validate_crawler_name(cls, v):
        if not v:
            return None
        if len(v) > 255 or len(v) < 1:
            raise ValueError("爬蟲名稱長度必須在1到255個字符之間")
        return v
    
    @field_validator('crawl_interval')
    @classmethod
    def validate_crawl_interval(cls, v):
        if not v:
            return None
        if v < 0:
            raise ValueError("爬取間隔必須大於0")
        return v
    
    @field_validator('is_active')
    @classmethod
    def validate_is_active(cls, v):
        if not isinstance(v, bool):
            raise ValueError("is_active必須是布林值")
        return v



