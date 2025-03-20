from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from .base_models import ValidationError as CustomValidationError
from datetime import datetime

class ArticleLinksCreateSchema(BaseModel):
    article_link: str = Field(..., min_length=1, max_length=1000, description="文章連結")
    source_name: str = Field(..., min_length=1, max_length=50, description="來源名稱")
    source_url: str = Field(..., min_length=1, max_length=1000, description="來源URL")
    is_scraped: bool = Field(..., description="是否已爬取")

    @field_validator('article_link', mode='before')
    @classmethod
    def validate_article_link(cls, value):
        if not value or not value.strip():
            raise CustomValidationError("文章連結不能為空")
        if 1 > len(value) or len(value) > 1000:
            raise CustomValidationError("文章連結長度需在 1 到 1000 個字元之間")
        return value

    @field_validator('source_name', mode='before')
    @classmethod
    def validate_source_name(cls, value):
        if not value or not value.strip():
            raise CustomValidationError("來源名稱不能為空")
        if 1 > len(value) or len(value) > 50:
            raise CustomValidationError("來源名稱長度需在 1 到 50 個字元之間")
        return value

    @field_validator('source_url', mode='before')
    @classmethod
    def validate_source_url(cls, value):
        if not value or not value.strip():
            raise CustomValidationError("來源URL不能為空")
        if 1 > len(value) or len(value) > 1000:
            raise CustomValidationError("來源URL長度需在 1 到 1000 個字元之間")
        return value

class ArticleLinksUpdateSchema(BaseModel):
    article_link: Optional[str] = Field(None, min_length=1, max_length=1000, description="文章連結")
    source_name: Optional[str] = Field(None, min_length=1, max_length=50, description="來源名稱")
    source_url: Optional[str] = Field(None, min_length=1, max_length=1000, description="來源URL")
    is_scraped: Optional[bool] = Field(None, description="是否已爬取")

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        if isinstance(data, dict):
            # 防止更新 article_link
            if 'article_link' in data:
                raise CustomValidationError("不允許更新 article_link 欄位")
            # 防止更新 created_at
            if 'created_at' in data:
                raise CustomValidationError("不允許更新 created_at 欄位")
            # 確保至少有一個欄位被更新
            update_fields = [k for k in data.keys() if k not in ['created_at']]
            if not update_fields:
                raise CustomValidationError("必須提供至少一個要更新的欄位")
        
        return data

    @field_validator('article_link', mode='before')
    @classmethod
    def validate_article_link(cls, value):
        if not value or not value.strip():
            raise CustomValidationError("文章連結不能為空")
        if 1 > len(value) or len(value) > 1000:
            raise CustomValidationError("文章連結長度需在 1 到 1000 個字元之間")
        return value

    @field_validator('source_name', mode='before')
    @classmethod
    def validate_source_name(cls, value):
        if not value or not value.strip():
            raise CustomValidationError("來源名稱不能為空")
        if 1 > len(value) or len(value) > 50:
            raise CustomValidationError("來源名稱長度需在 1 到 50 個字元之間")
        return value

    @field_validator('source_url', mode='before')
    @classmethod
    def validate_source_url(cls, value):
        if not value or not value.strip():
            raise CustomValidationError("來源URL不能為空")
        if 1 > len(value) or len(value) > 1000:
            raise CustomValidationError("來源URL長度需在 1 到 1000 個字元之間")
        return value
    
    