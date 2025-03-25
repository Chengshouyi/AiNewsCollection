from typing import Annotated, Optional, Any
from pydantic import BaseModel, Field, BeforeValidator, model_validator, field_validator
from datetime import datetime
import re
from src.error.errors import ValidationError
from sqlalchemy import String, Integer, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

def validate_url(value: str) -> str:
    """URL驗證"""
    if not value:
        raise ValidationError("scrape_target: URL不能為空")
    
    # 先檢查長度
    if len(value) > 1000:
        raise ValidationError("scrape_target: 長度必須在 1-1000 字元之間")
    
    # 檢查 URL 格式
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)?$', re.IGNORECASE)
    
    if not url_pattern.match(value):
        raise ValidationError("scrape_target: 無效的URL格式")
    
    return value

def validate_crawler_name(value: str) -> str:
    """爬蟲名稱驗證"""
    if not value or not value.strip():
        raise ValidationError("crawler_name: 不能為空")
    value = value.strip()
    if len(value) < 1 or len(value) > 100:
        raise ValidationError("crawler_name: 長度必須在 1-100 字元之間")
    return value

def validate_crawler_type(value: str) -> str:
    """爬蟲類型驗證"""
    if not value or not value.strip():
        raise ValidationError("crawler_type: 不能為空")
    value = value.strip()
    if len(value) < 1 or len(value) > 100:
        raise ValidationError("crawler_type: 長度必須在 1-100 字元之間")
    return value

def validate_crawl_interval(value: int) -> int:
    """爬取間隔驗證"""
    if value <= 0:
        raise ValidationError("crawl_interval: 必須大於 0")
    return value

# 通用字段定義
CrawlerName = Annotated[
    str,
    BeforeValidator(validate_crawler_name)
]

ScrapeTarget = Annotated[
    str,
    BeforeValidator(validate_url)
]

CrawlerType = Annotated[
    str,
    BeforeValidator(validate_crawler_type)
]

CrawlInterval = Annotated[
    int,
    BeforeValidator(validate_crawl_interval)
]

class BaseCrawlerSchema(BaseModel):
    """爬蟲基礎模型"""
    
    @field_validator('crawler_name', mode='before', check_fields=False)
    @classmethod
    def validate_crawler_name(cls, value):
        """驗證爬蟲名稱"""
        if value is None:
            return None
        if not value or not value.strip():
            raise ValidationError("crawler_name: 不能為空。")
        if len(value) < 1 or len(value) > 100:
            raise ValidationError("crawler_name: 長度必須在 1-100 字元之間。")
        return value

    @field_validator('scrape_target', mode='before', check_fields=False)
    @classmethod
    def validate_scrape_target(cls, value):
        """驗證爬取目標"""
        if value is None:
            return None
        if not value or not value.strip():
            raise ValidationError("scrape_target: 不能為空。")
        if len(value) < 1 or len(value) > 1000:
            raise ValidationError("scrape_target: 長度必須在 1-1000 字元之間。")
        if not validate_url(value):
            raise ValidationError("scrape_target: 無效的URL格式")
        return value

    @field_validator('crawl_interval', mode='before', check_fields=False)
    @classmethod
    def validate_crawl_interval(cls, value):
        """驗證爬取間隔"""
        if value is None:
            return None
        if value <= 0:
            raise ValidationError("crawl_interval: 必須大於 0。")
        return value

    @field_validator('is_active', mode='before', check_fields=False)
    @classmethod
    def validate_is_active(cls, value):
        """驗證是否啟用"""
        if value is not None and not isinstance(value, bool):
            raise ValidationError("is_active: 必須是布爾值。")
        return value

class CrawlersCreateSchema(BaseCrawlerSchema):
    crawler_name: CrawlerName
    scrape_target: ScrapeTarget
    crawler_type: CrawlerType
    crawl_interval: CrawlInterval = Field(default=1)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    last_crawl_time: Optional[datetime] = None

    @model_validator(mode='before')
    @classmethod
    def validate_required_fields(cls, data):
        """驗證必填欄位"""
        if isinstance(data, dict):
            required_fields = ['crawler_name', 'scrape_target', 'crawl_interval', 'crawler_type']
            for field in required_fields:
                if field not in data or (field == 'crawl_interval' and data.get(field) is None):
                    raise ValidationError(f"{field}: 不能為空。")
        return data

class CrawlersUpdateSchema(BaseModel):
    """爬蟲更新模型"""
    crawler_name: Optional[CrawlerName] = None
    scrape_target: Optional[ScrapeTarget] = None
    crawl_interval: Optional[CrawlInterval] = None
    is_active: Optional[bool] = Field(None, description="是否啟用")
    updated_at: datetime = Field(default_factory=datetime.now)
    last_crawl_time: Optional[datetime] = None

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data: dict) -> dict:
        update_fields = [
            field for field in data.keys()
            if field not in ['updated_at', 'last_crawl_time']
        ]
        
        if not update_fields:
            raise ValidationError("必須提供至少一個要更新的欄位")
        
        return data

    @model_validator(mode='before')
    @classmethod
    def validate_immutable(cls, data: dict) -> dict:
        if isinstance(data, dict):
            immutable_fields = ['created_at', 'id', 'crawler_type']
            for field in immutable_fields:
                if field in data:
                    raise ValidationError(f"不允許更新 {field} 欄位")
        return data

    @field_validator('is_active', mode='before')
    @classmethod
    def validate_is_active(cls, value):
        if value is not None and not isinstance(value, bool):
            try:
                # 嘗試轉換常見的布爾值字符串
                if isinstance(value, str):
                    value = value.lower()
                    if value in ('true', '1', 'yes'):
                        return True
                    if value in ('false', '0', 'no'):
                        return False
            except:
                pass
            raise ValidationError("is_active: 必須是布爾值")
        return value



