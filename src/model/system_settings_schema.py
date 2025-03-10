from pydantic import BaseModel, Field, field_validator
from typing import Optional
class SystemSettingsCreateSchema(BaseModel):
    crawler_name: str = Field(..., min_length=1, max_length=255)
    crawl_interval: int = Field(..., ge=0)
    crawl_start_time: str = Field(..., min_length=5, max_length=5)
    crawl_end_time: str = Field(..., min_length=5, max_length=5)
    is_active: bool = Field(default=True)
    
    @field_validator('crawl_start_time', 'crawl_end_time')
    @classmethod
    def validate_time(cls, v):
        if not v:
            return None
        if len(v) != 5 or not v.isdigit():
            raise ValueError("時間格式必須是HH:MM")
        return v    

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
    
    @field_validator('crawl_end_time')
    @classmethod
    def validate_crawl_end_time(cls, v):
        if not v:
            return None
        if v <= cls.crawl_start_time:
            raise ValueError("爬取結束時間必須大於爬取開始時間")
        return v

class SystemSettingsUpdateSchema(BaseModel):
    crawler_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    crawl_interval: Optional[int] = Field(default=None, ge=0)
    crawl_start_time: Optional[str] = Field(default=None, min_length=5, max_length=5)
    crawl_end_time: Optional[str] = Field(default=None, min_length=5, max_length=5)
    is_active: Optional[bool] = Field(default=None)
    
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
        return v
        if v < 0:
            raise ValueError("爬取間隔必須大於0")
        return v
    
    @field_validator('crawl_start_time')
    @classmethod
    def validate_crawl_start_time(cls, v):
        if not v:
            return None
        if len(v) != 5 or not v.isdigit():
            raise ValueError("時間格式必須是HH:MM")
        return v
    
    @field_validator('crawl_end_time')
    @classmethod
    def validate_crawl_end_time(cls, v):
        if not v:
            return None
        if v <= cls.crawl_start_time:
            raise ValueError("爬取結束時間必須大於爬取開始時間")
        return v
    
    @field_validator('is_active')
    @classmethod
    def validate_is_active(cls, v):
        if not isinstance(v, bool):
            raise ValueError("is_active必須是布林值")
        return v



