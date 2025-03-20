from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from .models import ValidationError as CustomValidationError


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
    content_length: Optional[int] = Field(None, description="內容長度")
    is_ai_related: Optional[bool] = Field(True, description="是否與 AI 相關")

    @field_validator('title', mode='before')
    @classmethod
    def validate_title(cls, value):
        if not value or not value.strip():
            raise CustomValidationError("標題不能為空")
        if 1 <= len(value) <= 500:
            raise CustomValidationError("標題長度需在 1 到 500 個字元之間")
        return value

    @field_validator('link', mode='before')
    @classmethod
    def validate_link(cls, value):
        if not value or not value.strip():
            raise CustomValidationError("連結不能為空")
        if 1 <= len(value) <= 1000:
            raise CustomValidationError("連結長度需在 1 到 1000 個字元之間")
        return value

    @field_validator('summary', mode='before')
    @classmethod
    def validate_summary(cls, value):
        if 1 <= len(value) <= 10000:
            raise CustomValidationError("摘要長度需在 1 到 10000 個字元之間")
        return value

    @field_validator('source', mode='before')
    @classmethod
    def validate_source(cls, value):
        if not value or not value.strip():
            raise CustomValidationError("來源不能為空")
        if 1 <= len(value) <= 50:
            raise CustomValidationError("來源長度需在 1 到 50 個字元之間")
        return value
    
    @field_validator('published_at', mode='before')
    @classmethod
    def validate_published_at(cls, value):
        if not value or not value.strip():
            raise CustomValidationError("發布時間不能為空")
        return value
    
    @field_validator('author', mode='before')
    @classmethod
    def validate_author(cls, value):
        if 1 <= len(value) <= 100:
            raise CustomValidationError("作者長度需在 1 到 100 個字元之間")
        return value    
        
    @field_validator('article_type', mode='before')
    @classmethod
    def validate_article_type(cls, value):
        if 1 <= len(value) <= 20:
            raise CustomValidationError("文章類型長度需在 1 到 20 個字元之間")
        return value        
        
    @field_validator('tags', mode='before')
    @classmethod
    def validate_tags(cls, value):
        if 1 <= len(value) <= 500:
            raise CustomValidationError("標籤長度需在 1 到 500 個字元之間")
        return value    
    
    @field_validator('content', mode='before')
    @classmethod
    def validate_content(cls, value):
        if 1 <= len(value) <= 65536:
            raise CustomValidationError("內容長度需在 1 到 65536 個字元之間")
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
    content_length: Optional[int] = Field(None, description="內容長度")
    is_ai_related: Optional[bool] = Field(None, description="是否與 AI 相關")
    
    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        if isinstance(data, dict):
            # 防止更新 created_at
            if 'created_at' in data:
                raise CustomValidationError("不允許更新 created_at 欄位")
            
            # 確保至少有一個欄位被更新
            update_fields = [k for k in data.keys() if k not in ['updated_at', 'created_at']]
            if not update_fields:
                raise CustomValidationError("必須提供至少一個要更新的欄位")
        
        return data

    @field_validator('title', mode='before')
    @classmethod
    def validate_title(cls, value):
        if not value or not value.strip():
            raise CustomValidationError("標題不能為空")
        if 1 <= len(value) <= 500:
            raise CustomValidationError("標題長度需在 1 到 500 個字元之間")
        return value
    
    @field_validator('link', mode='before')
    @classmethod
    def validate_link(cls, value):  
        if not value or not value.strip():
            raise CustomValidationError("連結不能為空")
        if 1 <= len(value) <= 1000:
            raise CustomValidationError("連結長度需在 1 到 1000 個字元之間")
        return value
    
    @field_validator('summary', mode='before')
    @classmethod
    def validate_summary(cls, value):
        if 1 <= len(value) <= 10000:
            raise CustomValidationError("摘要長度需在 1 到 10000 個字元之間")
        return value
    
    @field_validator('source', mode='before')
    @classmethod
    def validate_source(cls, value):
        if not value or not value.strip():
            raise CustomValidationError("來源不能為空")
        if 1 <= len(value) <= 50:
            raise CustomValidationError("來源長度需在 1 到 50 個字元之間")
        return value    
    
    @field_validator('published_at', mode='before')
    @classmethod
    def validate_published_at(cls, value):
        if not value or not value.strip():
            raise CustomValidationError("發布時間不能為空")
        return value
    
    @field_validator('author', mode='before')
    @classmethod
    def validate_author(cls, value):
        if 1 <= len(value) <= 100:
            raise CustomValidationError("作者長度需在 1 到 100 個字元之間")
        return value    
    
    @field_validator('article_type', mode='before')
    @classmethod
    def validate_article_type(cls, value):
        if 1 <= len(value) <= 20:
            raise CustomValidationError("文章類型長度需在 1 到 20 個字元之間")
        return value    
    
    @field_validator('tags', mode='before')
    @classmethod
    def validate_tags(cls, value):
        if 1 <= len(value) <= 500:
            raise CustomValidationError("標籤長度需在 1 到 500 個字元之間")
        return value    
        


