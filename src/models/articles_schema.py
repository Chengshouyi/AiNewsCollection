from typing import Annotated, Optional, Any
from pydantic import BaseModel,BeforeValidator, model_validator
from datetime import datetime
from src.error.errors import ValidationError
from src.utiles.model_utiles import validate_optional_str


def validate_title(value: str) -> str:
    """標題驗證"""
    if not value or not value.strip():
        raise ValidationError("title: 不能為空")
    value = value.strip()
    if len(value) > 500:
        raise ValidationError("title: 長度不能超過 500 字元")
    return value

def validate_link(value: str) -> str:
    """連結驗證"""
    if not value or not value.strip():
        raise ValidationError("link: 不能為空")
    value = value.strip()
    if len(value) > 1000:
        raise ValidationError("link: 長度不能超過 1000 字元")
    return value

def validate_source(value: str) -> str:
    """來源驗證"""
    if not value or not value.strip():
        raise ValidationError("source: 不能為空")
    value = value.strip()
    if len(value) > 50:
        raise ValidationError("source: 長度不能超過 50 字元")
    return value

def validate_published_at(value: Any) -> datetime:
    """發布時間驗證"""
    if value is None or value == "":
        raise ValidationError("published_at: 不能為空")
    
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            raise ValidationError("published_at: 無效的日期時間格式。請使用 ISO 格式。")
    
    if isinstance(value, datetime):
        return value
    
    raise ValidationError("published_at: 必須是字串或日期時間。")


# 通用字段定義
Title = Annotated[str, BeforeValidator(validate_title)]
Link = Annotated[str, BeforeValidator(validate_link)]
Source = Annotated[str, BeforeValidator(validate_source)]
PublishedAt = Annotated[datetime, BeforeValidator(validate_published_at)]
Summary = Annotated[Optional[str], BeforeValidator(validate_optional_str("summary", 10000))]
Content = Annotated[Optional[str], BeforeValidator(validate_optional_str("content", 65536))]
Category = Annotated[Optional[str], BeforeValidator(validate_optional_str("category", 100))]
Author = Annotated[Optional[str], BeforeValidator(validate_optional_str("author", 100))]
ArticleType = Annotated[Optional[str], BeforeValidator(validate_optional_str("article_type", 20))]
Tags = Annotated[Optional[str], BeforeValidator(validate_optional_str("tags", 500))]

class ArticleCreateSchema(BaseModel):
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
            for field in required_fields:
                if field not in data:
                    raise ValidationError(f"{field}: 不能為空")
        return data

class ArticleUpdateSchema(BaseModel):
    """文章更新模型"""
    title: Optional[Title] = None
    link: Optional[Link] = None
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
            immutable_fields = ['created_at', 'id']
            for field in immutable_fields:
                if field in data:
                    raise ValidationError(f"不允許更新 {field} 欄位")
            
            update_fields = [
                field for field in data.keys()
                if field not in ['updated_at'] + immutable_fields
            ]
            if not update_fields:
                raise ValidationError("必須提供至少一個要更新的欄位")
        return data