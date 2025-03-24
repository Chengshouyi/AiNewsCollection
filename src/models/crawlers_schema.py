from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import datetime
from src.error.errors import ValidationError

class CrawlersCreateSchema(BaseModel):
    crawler_name: str = Field(..., min_length=1, max_length=255, description="爬蟲名稱")
    scrape_target: str = Field(..., min_length=1, max_length=1000, description="爬取目標")
    crawl_interval: int = Field(..., gt=0, description="爬取間隔")
    is_active: bool = Field(True, description="是否啟用")
    created_at: datetime = Field(default_factory=datetime.now, description="建立時間")
    updated_at: Optional[datetime] = Field(default=None, description="更新時間")
    last_crawl_time: Optional[datetime] = Field(default=None, description="最後爬取時間")
    crawler_type: str = Field(..., min_length=1, max_length=100, description="爬蟲類型")

    @model_validator(mode='before')
    @classmethod
    def validate_required_fields(cls, data):
        if isinstance(data, dict):
            required_fields = ['crawler_name', 'scrape_target', 'crawl_interval', 'crawler_type']
            for field in required_fields:
                if field not in data:
                    raise ValidationError(f"{field}: do not be empty.")
        return data
    
    @field_validator('crawler_name', mode='before')
    @classmethod
    def validate_crawler_name(cls, value):
        if not value or not value.strip():
            raise ValidationError("crawler_name: do not be empty.")
        if 1 > len(value) or len(value) > 255:
            raise ValidationError("crawler_name: length must be between 1 and 255.")
        return value
    
    @field_validator('crawl_interval', mode='before')
    @classmethod
    def validate_crawl_interval(cls, value):
        if value is None:
            raise ValidationError("crawl_interval: do not be empty.")
        if value <= 0:
            raise ValidationError("crawl_interval: must be greater than 0.")
        return value
    
    @field_validator('is_active', mode='before')
    @classmethod
    def validate_is_active(cls, value):
        if not isinstance(value, bool):
            raise ValidationError("is_active: must be a boolean value.")
        return value

    @field_validator('created_at', mode='before')
    @classmethod
    def validate_created_at(cls, value):
        if not value:
            raise ValidationError("created_at: do not be empty.")
        return value
    
    @field_validator('scrape_target', mode='before')
    @classmethod
    def validate_scrape_target(cls, value):
        if not value or not value.strip():
            raise ValidationError("scrape_target: do not be empty.")
        if 1 > len(value) or len(value) > 1000:
            raise ValidationError("scrape_target: length must be between 1 and 1000.")
        return value
    
    @field_validator('crawler_type', mode='before')
    @classmethod
    def validate_crawler_type(cls, value):
        if not value or not value.strip():
            raise ValidationError("crawler_type: do not be empty.")
        if 1 > len(value) or len(value) > 100:
            raise ValidationError("crawler_type: length must be between 1 and 100.")
        return value


class CrawlersUpdateSchema(BaseModel):
    crawler_name: Optional[str] = Field(None, min_length=1, max_length=255, description="爬蟲名稱")
    scrape_target: Optional[str] = Field(None, min_length=1, max_length=1000, description="爬取目標")
    crawl_interval: Optional[int] = Field(None, gt=0, description="爬取間隔")
    is_active: Optional[bool] = Field(None, description="是否啟用")
    last_crawl_time: Optional[datetime] = Field(default=None, description="最後爬取時間")
    updated_at: Optional[datetime] = Field(default=None, description="更新時間")

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        if isinstance(data, dict):
            # 防止更新 created_at 和 id
            for immutable_field in ['created_at', 'id', 'crawler_type']:
                if immutable_field in data:
                    raise ValidationError(f"do not allow to update {immutable_field} field.")
            
            # 確保至少有一個欄位被更新
            update_fields = [k for k in data.keys() if k not in ['updated_at', 'created_at', 'id', 'crawler_type']]
            if not update_fields:
                raise ValidationError("must provide at least one field to update.")
        
        return data

    @field_validator('crawler_name', mode='before')
    @classmethod
    def validate_crawler_name(cls, value):
        if value is None:
            return None
        if not value.strip():
            raise ValidationError("crawler_name: do not be empty.")
        if len(value) > 255:
            raise ValidationError("crawler_name: length must be between 1 and 255.")
        return value
    
    @field_validator('crawl_interval', mode='before')
    @classmethod
    def validate_crawl_interval(cls, value):
        if value is None:
            return None
        if value <= 0:
            raise ValidationError("crawl_interval: must be greater than 0.")
        return value
    
    @field_validator('is_active', mode='before')
    @classmethod
    def validate_is_active(cls, value):
        if not isinstance(value, bool):
            raise ValidationError("is_active: must be a boolean value.")
        return value



