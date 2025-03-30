from typing import Annotated, Optional, Any
from pydantic import BaseModel, BeforeValidator, model_validator
from src.utils.model_utils import validate_str, validate_url
from src.utils.schema_utils import validate_required_fields_schema, validate_update_schema
from src.models.base_schema import BaseCreateSchema, BaseUpdateSchema

# 通用字段定義
SourceName = Annotated[str, BeforeValidator(validate_str("source_name", max_length=50, required=True))]
SourceUrl = Annotated[str, BeforeValidator(validate_url("source_url", max_length=1000, required=True))]
ArticleLink = Annotated[str, BeforeValidator(validate_url("article_link", max_length=1000, required=True))]

class ArticleLinksCreateSchema(BaseCreateSchema):
    """文章連結創建模型"""
    source_name: SourceName
    source_url: SourceUrl
    article_link: ArticleLink
    is_scraped: bool = False

    @model_validator(mode='before')
    @classmethod
    def validate_required_fields(cls, data):
        """驗證必填欄位"""
        if isinstance(data, dict):
            required_fields = ['source_name', 'source_url', 'article_link']
            return validate_required_fields_schema(required_fields, data)

class ArticleLinksUpdateSchema(BaseUpdateSchema):
    """文章連結更新模型"""
    source_name: Optional[SourceName] = None
    source_url: Optional[SourceUrl] = None
    is_scraped: Optional[bool] = None

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        """驗證更新操作"""
        if isinstance(data, dict):
            immutable_fields = ['article_link'] + cls._get_immutable_fields()
            updated_fields = ['source_name', 'source_url', 'is_scraped'] + cls._get_updated_fields()
            return validate_update_schema(immutable_fields, updated_fields, data)
        
    
    