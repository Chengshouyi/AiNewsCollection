from typing import Annotated, Optional
from pydantic import BeforeValidator, model_validator
from datetime import datetime
from src.utils.model_utils import validate_str, validate_url, validate_datetime, validate_boolean
from src.models.base_schema import BaseCreateSchema, BaseUpdateSchema
from src.utils.schema_utils import validate_update_schema, validate_required_fields_schema

# 通用字段定義
Title = Annotated[str, BeforeValidator(validate_str("title", max_length=500, required=True))]
Link = Annotated[str, BeforeValidator(validate_url("link", max_length=1000, required=True))]
Source = Annotated[str, BeforeValidator(validate_str("source", max_length=50, required=True))]
SourceUrl = Annotated[str, BeforeValidator(validate_url("source_url", max_length=1000, required=True))]
PublishedAt = Annotated[Optional[datetime], BeforeValidator(validate_datetime("published_at", required=False))]
Summary = Annotated[str, BeforeValidator(validate_str("summary", 10000))]
Content = Annotated[Optional[str], BeforeValidator(validate_str("content", 65536))]
Category = Annotated[str, BeforeValidator(validate_str("category", 100))]
Author = Annotated[Optional[str], BeforeValidator(validate_str("author", 100))]
ArticleType = Annotated[Optional[str], BeforeValidator(validate_str("article_type", 20))]
Tags = Annotated[Optional[str], BeforeValidator(validate_str("tags", 500))]
IsAiRelated = Annotated[bool, BeforeValidator(validate_boolean("is_ai_related", required=True))]
IsScraped = Annotated[bool, BeforeValidator(validate_boolean("is_scraped", required=True))]

class ArticleCreateSchema(BaseCreateSchema):
    """文章創建模型"""
    title: Title
    link: Link
    summary: Summary
    content: Content = None
    source: Source
    source_url: SourceUrl
    published_at: PublishedAt = None
    category: Category
    author: Author = None
    article_type: ArticleType = None
    tags: Tags = None
    is_ai_related: IsAiRelated
    is_scraped: IsScraped

    @model_validator(mode='before')
    @classmethod
    def validate_required_fields(cls, data):
        """驗證必填欄位"""
        if isinstance(data, dict):
            required_fields = ['title', 'link', 'source', 'source_url', 'summary', 'category', 'is_ai_related', 'is_scraped']
            return validate_required_fields_schema(required_fields, data)

class ArticleUpdateSchema(BaseUpdateSchema):
    """文章更新模型"""
    title: Optional[Title] = None
    summary: Optional[Summary] = None
    content: Optional[Content] = None
    source: Optional[Source] = None
    source_url: Optional[SourceUrl] = None
    published_at: Optional[PublishedAt] = None
    category: Optional[Category] = None
    author: Optional[Author] = None
    article_type: Optional[ArticleType] = None
    tags: Optional[Tags] = None
    is_ai_related: Optional[IsAiRelated] = None
    is_scraped: Optional[IsScraped] = None

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        """驗證更新操作"""
        if isinstance(data, dict):
            immutable_fields = ['link'] + cls._get_immutable_fields()
            updated_fields = ['title', 'summary', 'content', 'source', 'source_url', 'published_at', 'category', 'author', 'article_type', 'tags', 'is_ai_related', 'is_scraped'] + cls._get_updated_fields()
            return validate_update_schema(immutable_fields, updated_fields, data)

