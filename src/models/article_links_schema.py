from typing import Annotated, Optional, Any
from pydantic import BaseModel, BeforeValidator, model_validator
from src.error.errors import ValidationError
from src.utils.model_utils import validate_str, validate_url

# 通用字段定義
SourceName = Annotated[str, BeforeValidator(validate_str("source_name", max_length=50, required=True))]
SourceUrl = Annotated[str, BeforeValidator(validate_url("source_url", max_length=1000, required=True))]
ArticleLink = Annotated[str, BeforeValidator(validate_url("article_link", max_length=1000, required=True))]

class ArticleLinksCreateSchema(BaseModel):
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
            for field in required_fields:
                if field not in data:
                    raise ValidationError(f"{field}: 不能為空")
        return data

class ArticleLinksUpdateSchema(BaseModel):
    """文章連結更新模型"""
    source_name: Optional[SourceName] = None
    source_url: Optional[SourceUrl] = None
    is_scraped: Optional[bool] = None

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        """驗證更新操作"""
        if isinstance(data, dict):
            immutable_fields = ['created_at', 'id', 'article_link']
            for field in immutable_fields:
                if field in data:
                    raise ValidationError(f"不允許更新 {field} 欄位")
            
            update_fields = [
                field for field in data.keys()
                if field not in immutable_fields
            ]
            if not update_fields:
                raise ValidationError("必須提供至少一個要更新的欄位")
        return data
    
    