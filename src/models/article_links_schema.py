from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from src.error.errors import ValidationError

class ArticleLinksCreateSchema(BaseModel):
    article_link: str = Field(..., min_length=1, max_length=1000, description="文章連結")
    source_name: str = Field(..., min_length=1, max_length=50, description="來源名稱")
    source_url: str = Field(..., min_length=1, max_length=1000, description="來源URL")
    is_scraped: bool = Field(..., description="是否已爬取")

    @model_validator(mode='before')
    @classmethod
    def validate_required_fields(cls, data):
        if isinstance(data, dict):
            required_fields = ['article_link', 'source_name', 'source_url', 'is_scraped']
            for field in required_fields:
                if field not in data:
                    raise ValidationError(f"{field}: do not be empty.")
        return data

    @field_validator('article_link', mode='before')
    @classmethod
    def validate_article_link(cls, value):
        if not value or not value.strip():
            raise ValidationError("article_link: do not be empty.")
        if 1 > len(value) or len(value) > 1000:
            raise ValidationError("article_link: length must be between 1 and 1000.")
        return value

    @field_validator('source_name', mode='before')
    @classmethod
    def validate_source_name(cls, value):
        if not value or not value.strip():
            raise ValidationError("source_name: do not be empty.")
        if 1 > len(value) or len(value) > 50:
            raise ValidationError("source_name: length must be between 1 and 50.")
        return value

    @field_validator('source_url', mode='before')
    @classmethod
    def validate_source_url(cls, value):
        if not value or not value.strip():
            raise ValidationError("source_url: do not be empty.")
        if 1 > len(value) or len(value) > 1000:
            raise ValidationError("source_url: length must be between 1 and 1000.")
        return value
    
    @field_validator('is_scraped', mode='before')
    @classmethod
    def validate_is_scraped(cls, value):
        if value is None:
            raise ValidationError("is_scraped: do not be empty.")
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
                raise ValidationError("do not allow to update article_link field.")
            # 防止更新 created_at
            if 'created_at' in data:
                raise ValidationError("do not allow to update created_at field.")
            # 確保至少有一個欄位被更新
            update_fields = [k for k in data.keys() if k not in ['article_link','created_at']]
            if not update_fields:
                raise ValidationError("must provide at least one field to update.")
        
        return data

    @field_validator('article_link', mode='before')
    @classmethod
    def validate_article_link(cls, value):
        if not value or not value.strip():
            raise ValidationError("article_link: do not be empty.")
        if 1 > len(value) or len(value) > 1000:
            raise ValidationError("article_link: length must be between 1 and 1000.")
        return value

    @field_validator('source_name', mode='before')
    @classmethod
    def validate_source_name(cls, value):
        if not value or not value.strip():
            raise ValidationError("source_name: do not be empty.")
        if 1 > len(value) or len(value) > 50:
            raise ValidationError("source_name: length must be between 1 and 50.")
        return value

    @field_validator('source_url', mode='before')
    @classmethod
    def validate_source_url(cls, value):
        if not value or not value.strip():
            raise ValidationError("source_url: do not be empty.")
        if 1 > len(value) or len(value) > 1000:
            raise ValidationError("source_url: length must be between 1 and 1000.")
        return value
    
    @field_validator('is_scraped', mode='before')
    @classmethod
    def validate_is_scraped(cls, value):
        if value is None:
            raise ValidationError("is_scraped: do not be empty.")
        return value
    
    