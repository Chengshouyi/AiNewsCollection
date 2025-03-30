from typing import Annotated, Optional, Any
from pydantic import Field, BeforeValidator, model_validator
from datetime import datetime, timezone
from src.utils.model_utils import validate_url, validate_str, validate_boolean
from src.models.base_schema import BaseCreateSchema, BaseUpdateSchema
from src.utils.schema_utils import validate_update_schema, validate_required_fields_schema


# 通用字段定義
CrawlerName = Annotated[str, BeforeValidator(validate_str("crawler_name", max_length=100, required=True))]
BaseUrl = Annotated[str, BeforeValidator(validate_url("base_url", max_length=1000, required=True))]
CrawlerType = Annotated[str, BeforeValidator(validate_str("crawler_type", max_length=100, required=True))]
IsActive = Annotated[bool, BeforeValidator(validate_boolean("is_active", required=True))]
ConfigFileName = Annotated[str, BeforeValidator(validate_str("config_file_name", max_length=1000, required=True))]

class CrawlersCreateSchema(BaseCreateSchema):
    crawler_name: CrawlerName
    base_url: BaseUrl
    crawler_type: CrawlerType
    config_file_name: ConfigFileName
    is_active: IsActive = True

    @model_validator(mode='before')
    @classmethod
    def validate_required_fields(cls, data):
        """驗證必填欄位"""
        if isinstance(data, dict):
            required_fields = ['crawler_name', 'base_url', 'crawler_type', 'config_file_name']
            return validate_required_fields_schema(required_fields, data)

class CrawlersUpdateSchema(BaseUpdateSchema):
    """爬蟲更新模型"""
    crawler_name: Optional[CrawlerName] = None
    base_url: Optional[BaseUrl] = None
    is_active: Optional[IsActive] = None
    config_file_name: Optional[ConfigFileName] = None

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        """驗證更新操作"""
        if isinstance(data, dict):
            immutable_fields = ['crawler_type'] + cls._get_immutable_fields()
            updated_fields = ['crawler_name', 'base_url', 'is_active', 'config_file_name'] + cls._get_updated_fields()
            return validate_update_schema(immutable_fields, updated_fields, data)






