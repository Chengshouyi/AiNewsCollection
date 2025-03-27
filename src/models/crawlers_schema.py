from typing import Annotated, Optional, Any
from pydantic import BaseModel, Field, BeforeValidator, model_validator, field_validator
from datetime import datetime
import re
from src.error.errors import ValidationError
from src.utils.model_utils import validate_url, validate_str, validate_boolean



# 通用字段定義
CrawlerName = Annotated[str, BeforeValidator(validate_str("crawler_name", max_length=100, required=True))]
BaseUrl = Annotated[str, BeforeValidator(validate_url("base_url", max_length=1000, required=True))]
CrawlerType = Annotated[str, BeforeValidator(validate_str("crawler_type", max_length=100, required=True))]
IsActive = Annotated[bool, BeforeValidator(validate_boolean("is_active", required=True))]
ConfigFileName = Annotated[str, BeforeValidator(validate_str("config_file_name", max_length=1000, required=True))]

class CrawlersCreateSchema(BaseModel):
    crawler_name: CrawlerName
    base_url: BaseUrl
    crawler_type: CrawlerType
    config_file_name: ConfigFileName
    is_active: IsActive = True
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

    @model_validator(mode='before')
    @classmethod
    def validate_required_fields(cls, data):
        """驗證必填欄位"""
        if isinstance(data, dict):
            required_fields = ['crawler_name', 'base_url', 'crawler_type', 'config_file_name']
            for field in required_fields:
                if field not in data:
                    raise ValidationError(f"{field}: 不能為空")
        return data

class CrawlersUpdateSchema(BaseModel):
    """爬蟲更新模型"""
    crawler_name: Optional[CrawlerName] = None
    base_url: Optional[BaseUrl] = None
    is_active: Optional[IsActive] = None
    config_file_name: Optional[ConfigFileName] = None
    updated_at: datetime = Field(default_factory=datetime.now)

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





