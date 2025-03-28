from pydantic import BaseModel, model_validator, Field
from datetime import datetime, timezone
from typing import Optional, Annotated
from pydantic import BeforeValidator
from src.utils.model_utils import validate_positive_int, validate_datetime

# 通用字段定義
Id = Annotated[Optional[int], BeforeValidator(validate_positive_int("id"))]
CreatedAt = Annotated[datetime, BeforeValidator(validate_datetime("created_at"))]
UpdatedAt = Annotated[datetime, BeforeValidator(validate_datetime("updated_at"))]

class BaseCreateSchema(BaseModel):
    id: Optional[Id] = None
    created_at: CreatedAt = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode='before')
    @classmethod
    def validate_required_fields(cls, data):
        """驗證必填欄位"""
        if isinstance(data, dict) and 'created_at' not in data:
            data['created_at'] = datetime.now(timezone.utc)
        return data

class BaseUpdateSchema(BaseModel):
    updated_at: UpdatedAt = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        """驗證更新操作"""
        if isinstance(data, dict) and 'updated_at' not in data:
            data['updated_at'] = datetime.now(timezone.utc)
        return data

    @staticmethod
    def _get_immutable_fields():
        return ['created_at', 'id']

    @staticmethod
    def _get_updated_fields():
        return ['updated_at']