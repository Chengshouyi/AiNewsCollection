from typing import Annotated, Optional, Any
from pydantic import BeforeValidator, model_validator
from datetime import datetime
from src.utils.model_utils import validate_str, validate_url, validate_datetime
from src.models.base_schema import BaseCreateSchema, BaseUpdateSchema
from src.utils.schema_utils import validate_update_schema, validate_required_fields_schema

# 通用字段定義
Title = Annotated[str, BeforeValidator(validate_str("title", max_length=500, required=True))]
Link = Annotated[str, BeforeValidator(validate_url("link", max_length=1000, required=True))]
Source = Annotated[str, BeforeValidator(validate_str("source", max_length=50, required=True))]
PublishedAt = Annotated[datetime, BeforeValidator(validate_datetime("published_at", required=True))]
Summary = Annotated[Optional[str], BeforeValidator(validate_str("summary", 10000))]
Content = Annotated[Optional[str], BeforeValidator(validate_str("content", 65536))]
Category = Annotated[Optional[str], BeforeValidator(validate_str("category", 100))]
Author = Annotated[Optional[str], BeforeValidator(validate_str("author", 100))]
ArticleType = Annotated[Optional[str], BeforeValidator(validate_str("article_type", 20))]
Tags = Annotated[Optional[str], BeforeValidator(validate_str("tags", 500))]

class ArticleCreateSchema(BaseCreateSchema):
    """文章創建模型"""
    title: Title
    link: Link
    summary: Summary = None
    content: Content = None
    source: Source
    published_at: PublishedAt
    category: Category = None
    author: Author = None
    article_type: ArticleType = None
    tags: Tags = None
    is_ai_related: bool = False

    @model_validator(mode='before')
    @classmethod
    def validate_required_fields(cls, data):
        """驗證必填欄位"""
        if isinstance(data, dict):
            required_fields = ['title', 'link', 'published_at', 'source']
            return validate_required_fields_schema(required_fields, data)

class ArticleUpdateSchema(BaseUpdateSchema):
    """文章更新模型"""
    title: Optional[Title] = None
    summary: Optional[Summary] = None
    content: Optional[Content] = None
    source: Optional[Source] = None
    published_at: Optional[PublishedAt] = None
    category: Optional[Category] = None
    author: Optional[Author] = None
    article_type: Optional[ArticleType] = None
    tags: Optional[Tags] = None
    is_ai_related: Optional[bool] = None

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        """驗證更新操作"""
        if isinstance(data, dict):
            immutable_fields = ['link'] + cls._get_immutable_fields()
            updated_fields = ['title', 'summary', 'content', 'source', 'published_at', 'category', 'author', 'article_type', 'tags', 'is_ai_related'] + cls._get_updated_fields()
            return validate_update_schema(immutable_fields, updated_fields, data)

