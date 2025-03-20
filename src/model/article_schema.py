from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from .base_models import ValidationError

class ArticleCreateSchema(BaseModel):
    title: str = Field(..., min_length=1, max_length=500, description="文章標題")
    summary: Optional[str] = Field(None, max_length=10000, description="文章摘要")
    content: Optional[str] = Field(None, max_length=65536, description="文章內容")
    link: str = Field(..., min_length=1, max_length=1000, description="文章連結")
    category: Optional[str] = Field(None, max_length=100, description="文章類別")
    published_at: str = Field(..., description="發布時間")
    author: Optional[str] = Field(None, max_length=100, description="作者")
    source: str = Field(..., min_length=1, max_length=50, description="來源")
    article_type: Optional[str] = Field(None, max_length=20, description="文章類型")
    tags: Optional[str] = Field(None, max_length=500, description="標籤")

    @field_validator('title', mode='before')
    @classmethod
    def validate_title(cls, value):
        if not value or not value.strip():
            raise ValidationError("title: do not be empty.")
        if 1 > len(value) or len(value) > 500:
            raise ValidationError("title: length must be between 1 and 500.")
        return value

    @field_validator('link', mode='before')
    @classmethod
    def validate_link(cls, value):
        if not value or not value.strip():
            raise ValidationError("link: do not be empty.")
        if 1 > len(value) or len(value) > 1000:
            raise ValidationError("link: length must be between 1 and 1000.")
        return value

    @field_validator('summary', mode='before')
    @classmethod
    def validate_summary(cls, value):
        if 1 > len(value) or len(value) > 10000:
            raise ValidationError("summary: length must be between 1 and 10000.")
        return value

    @field_validator('source', mode='before')
    @classmethod
    def validate_source(cls, value):
        if not value or not value.strip():
            raise ValidationError("source: do not be empty.")
        if 1 > len(value) or len(value) > 50:
            raise ValidationError("source: length must be between 1 and 50.")
        return value
    
    @field_validator('published_at', mode='before')
    @classmethod
    def validate_published_at(cls, value):
        if not value or not value.strip():
            raise ValidationError("published_at: do not be empty.")
        return value
    
    @field_validator('author', mode='before')
    @classmethod
    def validate_author(cls, value):
        if 1 > len(value) or len(value) > 100:
            raise ValidationError("author: length must be between 1 and 100.")
        return value    
        
    @field_validator('article_type', mode='before')
    @classmethod
    def validate_article_type(cls, value):
        if 1 > len(value) or len(value) > 20:
            raise ValidationError("article_type: length must be between 1 and 20.")
        return value        
        
    @field_validator('tags', mode='before')
    @classmethod
    def validate_tags(cls, value):
        if 1 > len(value) or len(value) > 500:
            raise ValidationError("tags: length must be between 1 and 500.")
        return value    
    
    @field_validator('content', mode='before')
    @classmethod
    def validate_content(cls, value):
        if 1 > len(value) or len(value) > 65536:
            raise ValidationError("content: length must be between 1 and 65536.")
        return value


class ArticleUpdateSchema(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500, description="文章標題")
    summary: Optional[str] = Field(None, max_length=10000, description="文章摘要")
    content: Optional[str] = Field(None, max_length=65536, description="文章內容")
    link: Optional[str] = Field(None, min_length=1, max_length=1000, description="文章連結")
    category: Optional[str] = Field(None, max_length=100, description="文章類別")
    published_at: Optional[str] = Field(None, description="發布時間")
    author: Optional[str] = Field(None, max_length=100, description="作者")
    source: Optional[str] = Field(None, min_length=1, max_length=50, description="來源")
    article_type: Optional[str] = Field(None, max_length=20, description="文章類型")
    tags: Optional[str] = Field(None, max_length=500, description="標籤")
    
    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        if isinstance(data, dict):
            # 防止更新 created_at
            if 'created_at' in data:
                raise ValidationError("do not allow to update created_at field.")
            
            # 確保至少有一個欄位被更新
            update_fields = [k for k in data.keys() if k not in ['updated_at', 'created_at']]
            if not update_fields:
                raise ValidationError("must provide at least one field to update.")
        
        return data

    @field_validator('title', mode='before')
    @classmethod
    def validate_title(cls, value):
        if not value or not value.strip():
            raise ValidationError("title: do not be empty.")
        if 1 > len(value) or len(value) > 500:
            raise ValidationError("title: length must be between 1 and 500.")
        return value
    
    @field_validator('link', mode='before')
    @classmethod
    def validate_link(cls, value):  
        if not value or not value.strip():
            raise ValidationError("link: do not be empty.")
        if 1 > len(value) or len(value) > 1000:
            raise ValidationError("link: length must be between 1 and 1000.")
        return value
    
    @field_validator('summary', mode='before')
    @classmethod
    def validate_summary(cls, value):
        if 1 > len(value) or len(value) > 10000:
            raise ValidationError("summary: length must be between 1 and 10000.")
        return value
    
    @field_validator('source', mode='before')
    @classmethod
    def validate_source(cls, value):
        if not value or not value.strip():
            raise ValidationError("source: do not be empty.")
        if 1 > len(value) or len(value) > 50:
            raise ValidationError("source: length must be between 1 and 50.")
        return value    
    
    @field_validator('published_at', mode='before')
    @classmethod
    def validate_published_at(cls, value):
        if not value or not value.strip():
            raise ValidationError("published_at: do not be empty.")
        return value
    
    @field_validator('author', mode='before')
    @classmethod
    def validate_author(cls, value):
        if 1 > len(value) or len(value) > 100:
            raise ValidationError("author: length must be between 1 and 100.")
        return value    
    
    @field_validator('article_type', mode='before')
    @classmethod
    def validate_article_type(cls, value):
        if 1 > len(value) or len(value) > 20:
            raise ValidationError("article_type: length must be between 1 and 20.")
        return value    
    
    @field_validator('tags', mode='before')
    @classmethod
    def validate_tags(cls, value):
        if 1 > len(value) or len(value) > 500:
            raise ValidationError("tags: length must be between 1 and 500.")
        return value    
        


