from typing import Annotated, Optional, Any
from pydantic import BaseModel, Field, BeforeValidator, model_validator, field_validator
from datetime import datetime
import re
from src.error.errors import ValidationError
from src.utiles.model_utiles import validate_url


def validate_crawler_name(value: str) -> str:
    """爬蟲名稱驗證"""
    if not value or not value.strip():
        raise ValidationError("crawler_name: 不能為空")
    value = value.strip()
    if len(value) > 100:
        raise ValidationError("crawler_name: 長度不能超過 100 字元")
    return value

def validate_scrape_target(value: str) -> str:
    """爬取目標驗證"""
    if not value or not value.strip():
        raise ValidationError("scrape_target: 不能為空")
    value = value.strip()
    if len(value) > 1000:
        raise ValidationError("scrape_target: 長度不能超過 1000 字元")
    return value

def validate_crawler_type(value: str) -> str:
    """爬蟲類型驗證"""
    if not value or not value.strip():
        raise ValidationError("crawler_type: 不能為空")
    value = value.strip()
    if len(value) > 100:
        raise ValidationError("crawler_type: 長度不能超過 100 字元")
    return value

def validate_crawl_interval(value: int) -> int:
    """爬取間隔驗證"""
    if value <= 0:
        raise ValidationError("crawl_interval: 必須大於 0")
    return value

def validate_is_active(value: Any) -> bool:
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

# 通用字段定義
CrawlerName = Annotated[str, BeforeValidator(validate_crawler_name)]
ScrapeTarget = Annotated[str, BeforeValidator(validate_url)]
CrawlerType = Annotated[str, BeforeValidator(validate_crawler_type)]
CrawlInterval = Annotated[int, BeforeValidator(validate_crawl_interval)]
IsActive = Annotated[bool, BeforeValidator(validate_is_active)]
class CrawlersCreateSchema(BaseModel):
    crawler_name: CrawlerName
    scrape_target: ScrapeTarget
    crawler_type: CrawlerType
    crawl_interval: CrawlInterval
    is_active: IsActive = True
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    last_crawl_time: Optional[datetime] = None

    @model_validator(mode='before')
    @classmethod
    def validate_required_fields(cls, data):
        """驗證必填欄位"""
        if isinstance(data, dict):
            required_fields = ['crawler_name', 'scrape_target', 'crawler_type', 'crawl_interval']
            for field in required_fields:
                if field not in data:
                    raise ValidationError(f"{field}: 不能為空")
        return data

class CrawlersUpdateSchema(BaseModel):
    """爬蟲更新模型"""
    crawler_name: Optional[CrawlerName] = None
    scrape_target: Optional[ScrapeTarget] = None
    crawl_interval: Optional[CrawlInterval] = None
    is_active: Optional[IsActive] = None
    updated_at: datetime = Field(default_factory=datetime.now)
    last_crawl_time: Optional[datetime] = None

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        """驗證更新操作"""
        if isinstance(data, dict):
            immutable_fields = ['created_at', 'id', 'crawler_type']
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





