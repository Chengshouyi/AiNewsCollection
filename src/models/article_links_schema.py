from typing import Annotated, Optional, Any
from pydantic import BeforeValidator, model_validator
from src.utils.model_utils import validate_str, validate_url, validate_boolean
from src.utils.schema_utils import validate_required_fields_schema, validate_update_schema
from src.models.base_schema import BaseCreateSchema, BaseUpdateSchema

# 通用字段定義
SourceName = Annotated[str, BeforeValidator(validate_str("source_name", max_length=50, required=True))]
SourceUrl = Annotated[str, BeforeValidator(validate_url("source_url", max_length=1000, required=True))]
ArticleLink = Annotated[str, BeforeValidator(validate_url("article_link", max_length=1000, required=True))]
Title = Annotated[str, BeforeValidator(validate_str("title", max_length=1000, required=True))]
Summary = Annotated[str, BeforeValidator(validate_str("summary", max_length=1000, required=True))]
Category = Annotated[str, BeforeValidator(validate_str("category", max_length=1000, required=True))]
PublishedAge = Annotated[str, BeforeValidator(validate_str("published_age", max_length=50, required=True))]
IsScraped = Annotated[Optional[bool], BeforeValidator(validate_boolean("is_scraped", required=False))]

class ArticleLinksCreateSchema(BaseCreateSchema):
    """文章連結創建模型"""
    source_name: SourceName
    source_url: SourceUrl
    article_link: ArticleLink
    title: Title
    summary: Summary
    category: Category
    published_age: PublishedAge
    is_scraped: IsScraped = False

    @model_validator(mode='before')
    @classmethod
    def validate_required_fields(cls, data):
        """驗證必填欄位"""
        if isinstance(data, dict):
            required_fields = ['source_name', 'source_url', 'article_link', 'title', 'summary', 'category', 'published_age']
            return validate_required_fields_schema(required_fields, data)

class ArticleLinksUpdateSchema(BaseUpdateSchema):
    """文章連結更新模型"""
    source_name: Optional[SourceName] = None
    source_url: Optional[SourceUrl] = None
    title: Optional[Title] = None
    summary: Optional[Summary] = None
    category: Optional[Category] = None
    published_age: Optional[PublishedAge] = None
    is_scraped: Optional[IsScraped] = None

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        """驗證更新操作"""
        if isinstance(data, dict):
            immutable_fields = ['article_link'] + cls._get_immutable_fields()
            updated_fields = ['source_name', 'source_url', 'title', 'summary', 'category', 'published_age', 'is_scraped'] + cls._get_updated_fields()
            return validate_update_schema(immutable_fields, updated_fields, data)
        
    
    