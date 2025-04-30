"""Crawlers schema module for data validation and serialization.

This module defines the Pydantic models for crawler creation, update, and reading,
providing data validation, serialization, and schema definitions for the crawler system.
"""

# Standard library imports
from datetime import datetime
from typing import Annotated, Optional, List, Dict, Any, Union
import logging

# Third party imports
from pydantic import (
    BeforeValidator,
    model_validator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

# Local application imports
from src.models.base_schema import BaseCreateSchema, BaseUpdateSchema
from src.utils.model_utils import validate_url, validate_str, validate_boolean
from src.utils.schema_utils import (
    validate_update_schema,
    validate_required_fields_schema,
)


logger = logging.getLogger(__name__)  # 使用統一的 logger

# 通用字段定義
CrawlerName = Annotated[
    str, BeforeValidator(validate_str("crawler_name", max_length=100, required=True))
]
ModuleName = Annotated[
    str, BeforeValidator(validate_str("module_name", max_length=100, required=True))
]
BaseUrl = Annotated[
    str, BeforeValidator(validate_url("base_url", max_length=1000, required=True))
]
CrawlerType = Annotated[
    str, BeforeValidator(validate_str("crawler_type", max_length=100, required=True))
]
IsActive = Annotated[
    bool, BeforeValidator(validate_boolean("is_active", required=True))
]
ConfigFileName = Annotated[
    str,
    BeforeValidator(validate_str("config_file_name", max_length=1000, required=True)),
]


class CrawlersCreateSchema(BaseCreateSchema):
    crawler_name: CrawlerName
    module_name: ModuleName
    base_url: BaseUrl
    crawler_type: CrawlerType
    config_file_name: ConfigFileName
    is_active: IsActive = True

    @model_validator(mode="before")
    @classmethod
    def validate_required_fields(cls, data):
        """驗證必填欄位"""
        if isinstance(data, dict):
            required_fields = CrawlersCreateSchema.get_required_fields()
            return validate_required_fields_schema(required_fields, data)

    @classmethod
    def get_required_fields(cls):
        return [
            "crawler_name",
            "module_name",
            "base_url",
            "crawler_type",
            "config_file_name",
        ]


class CrawlersUpdateSchema(BaseUpdateSchema):
    """爬蟲更新模型"""

    crawler_name: Optional[CrawlerName] = None
    module_name: Optional[ModuleName] = None
    crawler_type: Optional[CrawlerType] = None
    base_url: Optional[BaseUrl] = None
    is_active: Optional[IsActive] = None
    config_file_name: Optional[ConfigFileName] = None

    @model_validator(mode="before")
    @classmethod
    def validate_update(cls, data):
        """驗證更新操作"""
        if isinstance(data, dict):
            return validate_update_schema(
                cls.get_immutable_fields(), cls.get_updated_fields(), data
            )

    @classmethod
    def get_immutable_fields(cls):
        return [] + BaseUpdateSchema.get_immutable_fields()

    @classmethod
    def get_updated_fields(cls):
        return [
            "crawler_name",
            "module_name",
            "crawler_type",
            "base_url",
            "is_active",
            "config_file_name",
        ] + BaseUpdateSchema.get_updated_fields()


# --- 新增用於讀取/響應的 Schema ---


class CrawlerReadSchema(BaseModel):
    """用於 API 響應的爬蟲數據模型"""

    id: int
    crawler_name: str
    module_name: str
    base_url: str
    crawler_type: str
    config_file_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Pydantic V2 配置: 允許從 ORM 屬性創建模型
    model_config = ConfigDict(from_attributes=True)


class PaginatedCrawlerResponse(BaseModel):
    items: List[Union[CrawlerReadSchema, Dict[str, Any]]]
    page: int = Field(..., ge=1, description="當前頁碼")
    per_page: int = Field(..., ge=1, description="每頁項目數")
    total: int = Field(..., ge=0, description="總項目數")
    total_pages: int = Field(..., ge=0, description="總頁數")
    has_next: bool = Field(..., description="是否有下一頁")
    has_prev: bool = Field(..., description="是否有上一頁")

    model_config = ConfigDict(from_attributes=True)

    @field_validator("items", mode="before")
    @classmethod
    def ensure_items_list(cls, v):
        if v is None:
            return []
        return v

    @field_validator("page", "per_page", "total", "total_pages")
    @classmethod
    def check_non_negative_integers(cls, value):
        if value < 0:
            raise ValueError("分頁相關數值必須為非負整數")
        return value
