from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import datetime
from src.error.errors import ValidationError

class CrawlersCreateSchema(BaseModel):
    crawler_name: str = Field(..., min_length=1, max_length=100, description="爬蟲名稱")
    scrape_target: str = Field(..., min_length=1, max_length=1000, description="爬取目標")
    crawl_interval: int = Field(..., gt=0, description="爬取間隔")
    is_active: bool = Field(default=True, description="是否啟用")
    created_at: Optional[datetime] = Field(default_factory=datetime.now, description="建立時間")
    updated_at: Optional[datetime] = Field(default=None, description="更新時間")
    last_crawl_time: Optional[datetime] = Field(default=None, description="最後爬取時間")
    crawler_type: str = Field(..., min_length=1, max_length=100, description="爬蟲類型")

    @model_validator(mode='before')
    @classmethod
    def validate_required_fields(cls, data):
        """驗證必填欄位"""
        if isinstance(data, dict):
            required_fields = ['crawler_name', 'scrape_target', 'crawl_interval', 'crawler_type']
            for field in required_fields:
                if field not in data or (field == 'crawl_interval' and data.get(field) is None):
                    raise ValidationError(f"{field}: 不能為空。raise_function:{__class__.validate_required_fields.__name__}")
        return data
    
    @field_validator('crawler_name', mode='before')
    @classmethod
    def validate_crawler_name(cls, value):
        """驗證爬蟲名稱"""
        if not value or not value.strip():
            raise ValidationError("crawler_name: 不能為空。raise_function:{__class__.validate_crawler_name.__name__}")
        if len(value) < 1 or len(value) > 100:
            raise ValidationError("crawler_name: 長度必須在 1-100 字元之間。raise_function:{__class__.validate_crawler_name.__name__}")
        return value
    
    @field_validator('scrape_target', mode='before')
    @classmethod
    def validate_scrape_target(cls, value):
        """驗證爬取目標"""
        if not value or not value.strip():
            raise ValidationError("scrape_target: 不能為空。raise_function:{__class__.validate_scrape_target.__name__}")
        if len(value) < 1 or len(value) > 1000:
            raise ValidationError("scrape_target: 長度必須在 1-1000 字元之間。raise_function:{__class__.validate_scrape_target.__name__}")
        return value
    
    @field_validator('crawler_type', mode='before')
    @classmethod
    def validate_crawler_type(cls, value):
        """驗證爬蟲類型"""
        if not value or not value.strip():
            raise ValidationError("crawler_type: 不能為空。raise_function:{__class__.validate_crawler_type.__name__}")
        if len(value) < 1 or len(value) > 100:
            raise ValidationError("crawler_type: 長度必須在 1-100 字元之間。raise_function:{__class__.validate_crawler_type.__name__}")
        return value
    
    @field_validator('crawl_interval', mode='before')
    @classmethod
    def validate_crawl_interval(cls, value):
        """驗證爬取間隔"""
        if value is None:
            raise ValidationError("crawl_interval: 不能為空。raise_function:{__class__.validate_crawl_interval.__name__}")
        if value <= 0:
            raise ValidationError("crawl_interval: 必須大於 0。raise_function:{__class__.validate_crawl_interval.__name__}")
        return value
    
    @field_validator('is_active', mode='before')
    @classmethod
    def validate_is_active(cls, value):
        """驗證是否啟用"""
        if not isinstance(value, bool):
            raise ValidationError("is_active: 必須是布爾值。raise_function:{__class__.validate_is_active.__name__}")
        return value


class CrawlersUpdateSchema(BaseModel):
    crawler_name: Optional[str] = Field(None, min_length=1, max_length=100, description="爬蟲名稱")
    scrape_target: Optional[str] = Field(None, min_length=1, max_length=1000, description="爬取目標")
    crawl_interval: Optional[int] = Field(None, gt=0, description="爬取間隔")
    is_active: Optional[bool] = Field(None, description="是否啟用")
    last_crawl_time: Optional[datetime] = Field(default=None, description="最後爬取時間")
    updated_at: Optional[datetime] = Field(default=None, description="更新時間")

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        """驗證更新操作"""
        if isinstance(data, dict):
            # 防止更新不可變欄位
            immutable_fields = ['created_at', 'id', 'crawler_type']
            for field in immutable_fields:
                if field in data:
                    raise ValidationError(f"不允許更新 {field} 欄位。raise_function:{__class__.validate_update.__name__}")
            
            # 確保至少有一個欄位被更新
            update_fields = [k for k in data.keys() if k not in ['updated_at', 'created_at', 'id', 'crawler_type']]
            if not update_fields:
                raise ValidationError("必須提供至少一個要更新的欄位。raise_function:{__class__.validate_update.__name__}")
        
        return data

    @field_validator('crawler_name', mode='before')
    @classmethod
    def validate_crawler_name(cls, value):
        """驗證爬蟲名稱"""
        if value is None:
            return None
        if not value.strip():
            raise ValidationError("crawler_name: 不能為空。raise_function:{__class__.validate_crawler_name.__name__}")
        if len(value) < 1 or len(value) > 100:
            raise ValidationError("crawler_name: 長度必須在 1-100 字元之間。raise_function:{__class__.validate_crawler_name.__name__}")
        return value
    
    @field_validator('scrape_target', mode='before')
    @classmethod
    def validate_scrape_target(cls, value):
        """驗證爬取目標"""
        if value is None:
            return None
        if not value.strip():
            raise ValidationError("scrape_target: 不能為空。raise_function:{__class__.validate_scrape_target.__name__}")
        if len(value) < 1 or len(value) > 1000:
            raise ValidationError("scrape_target: 長度必須在 1-1000 字元之間。raise_function:{__class__.validate_scrape_target.__name__}")
        return value
    
    @field_validator('crawl_interval', mode='before')
    @classmethod
    def validate_crawl_interval(cls, value):
        """驗證爬取間隔"""
        if value is None:
            return None
        if value <= 0:
            raise ValidationError("crawl_interval: 必須大於 0。raise_function:{__class__.validate_crawl_interval.__name__}")
        return value
    
    @field_validator('is_active', mode='before')
    @classmethod
    def validate_is_active(cls, value):
        """驗證是否啟用"""
        if value is not None and not isinstance(value, bool):
            raise ValidationError("is_active: 必須是布爾值。raise_function:{__class__.validate_is_active.__name__}")
        return value



