from typing import Annotated, Optional, Any
from pydantic import BaseModel, BeforeValidator, model_validator
from src.error.errors import ValidationError
from src.models.model_utiles import validate_optional_str

def validate_source_name(value: str) -> str:
    """來源名稱驗證"""
    if not value or not value.strip():
        raise ValidationError("source_name: 不能為空")
    value = value.strip()
    if len(value) > 50:
        raise ValidationError("source_name: 長度不能超過 50 字元")
    return value

def validate_source_url(value: str) -> str:
    """來源URL驗證"""
    if not value or not value.strip():
        raise ValidationError("source_url: 不能為空")
    value = value.strip()
    if len(value) > 1000:
        raise ValidationError("source_url: 長度不能超過 1000 字元")
    return value

def validate_article_link(value: str) -> str:
    """文章連結驗證"""
    if not value or not value.strip():
        raise ValidationError("article_link: 不能為空")
    value = value.strip()
    if len(value) > 1000:
        raise ValidationError("article_link: 長度不能超過 1000 字元")
    return value

# 通用字段定義
SourceName = Annotated[str, BeforeValidator(validate_source_name)]
SourceUrl = Annotated[str, BeforeValidator(validate_source_url)]
ArticleLink = Annotated[str, BeforeValidator(validate_article_link)]

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
    
    