"""本模組定義了基礎的 Pydantic schema，提供通用的建立與更新資料結構，並整合欄位驗證邏輯。"""

from datetime import datetime, timezone
from typing import Optional, Annotated
import logging

from pydantic import BaseModel, model_validator, Field, BeforeValidator

from src.utils.model_utils import validate_positive_int, validate_datetime
  # 使用統一的 logger

logger = logging.getLogger(__name__)  # 使用統一的 logger  # 使用統一的 logger

# 通用字段定義
Id = Annotated[
    Optional[int],
    BeforeValidator(validate_positive_int("id", is_zero_allowed=False, required=False)),
]
CreatedAt = Annotated[datetime, BeforeValidator(validate_datetime("created_at"))]
UpdatedAt = Annotated[datetime, BeforeValidator(validate_datetime("updated_at"))]


class BaseCreateSchema(BaseModel):
    id: Optional[Id] = None
    created_at: CreatedAt = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="before")
    @classmethod
    def validate_required_fields(cls, data):
        """驗證必填欄位"""
        if isinstance(data, dict) and "created_at" not in data:
            data["created_at"] = datetime.now(timezone.utc)
        return data

    @classmethod
    def get_required_fields(cls):
        return []

    @classmethod
    def get_immutable_fields(cls):
        return []


class BaseUpdateSchema(BaseModel):
    updated_at: UpdatedAt = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="before")
    @classmethod
    def validate_update(cls, data):
        """驗證更新操作"""
        if isinstance(data, dict) and "updated_at" not in data:
            data["updated_at"] = datetime.now(timezone.utc)
        return data

    @classmethod
    def get_required_fields(cls):
        return []

    @classmethod
    def get_immutable_fields(cls):
        return ["created_at", "id"]

    @classmethod
    def get_updated_fields(cls):
        return ["updated_at"]
