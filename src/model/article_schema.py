from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime, timedelta
from typing import Optional

class ArticleCreateSchema(BaseModel):
    title: str
    summary: Optional[str] = None
    content: Optional[str] = None
    link: str
    category: Optional[str] = None
    published_at: Optional[str] = None
    author: Optional[str] = None
    source: Optional[str] = None
    article_type: Optional[str] = None
    tags: Optional[str] = None
    content_length: Optional[int] = None
    is_ai_related: Optional[bool] = True
    created_at: datetime = Field(default=datetime.now())
    updated_at: Optional[datetime] = Field(default=None)

    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        if not v:
            raise ValueError("標題不能為空")
        return v

    @field_validator('link')
    @classmethod
    def validate_link(cls, v):
        # 檢查是否為空
        if not v:
            raise ValueError("連結不能為空")
        # 檢查是否以 http:// 或 https:// 開頭
        if not v.startswith(('http://', 'https://')):
            raise ValueError("URL 必須以 http:// 或 https:// 開頭")
        return v

    @field_validator('published_at')
    @classmethod
    def validate_published_at(cls, v):
        # 確保 published_at 不為 None
        if v is None:
            raise ValueError("發布時間不能為空")
        # 檢查是否為未來日期（允許誤差1天）
        if v > datetime.now() + timedelta(days=1):
            raise ValueError("發布時間不能是未來日期")
        return v

    @field_validator('created_at')
    @classmethod
    def validate_created_at(cls, v):
        if v is None:
            raise ValueError("建立時間不能為空")
        return v    


class ArticleUpdateSchema(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    link: Optional[str] = None
    category: Optional[str] = None
    published_at: Optional[str] = None
    author: Optional[str] = None
    source: Optional[str] = None
    article_type: Optional[str] = None
    tags: Optional[str] = None
    content_length: Optional[int] = None
    is_ai_related: Optional[bool] = None
    updated_at: Optional[datetime] = Field(default=datetime.now())

    @model_validator(mode='before')
    @classmethod
    def validate_created_at(cls, data):
        if isinstance(data, dict) and 'created_at' in data:
            raise ValueError("不允許更新 created_at 欄位")
        return data

    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        if not v:
            raise ValueError("標題不能為空")
        if len(v) > 255 or len(v) < 1:
            raise ValueError("標題長度必須在1到255個字符之間")
        return v

    @field_validator('link')
    @classmethod
    def validate_link(cls, v):  
        if not v:
            raise ValueError("連結不能為空")
        if not v.startswith(('http://', 'https://')):
            raise ValueError("URL 必須以 http:// 或 https:// 開頭")
        return v
    
    @field_validator('published_at')
    @classmethod
    def validate_published_at(cls, v):
        if not v:
            raise ValueError("發布時間不能為空")
        if v > datetime.now() + timedelta(days=1):
            raise ValueError("發布時間不能是未來日期")
        return v

    
    @field_validator('source')
    @classmethod
    def validate_source(cls, v):
        if not v:
            raise ValueError("來源不能為空")
        if len(v) > 255 or len(v) < 1:
            raise ValueError("來源長度必須在1到255個字符之間")
        return v

    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        if not v:
            raise ValueError("內容不能為空")
        if len(v) > 65536:
            raise ValueError("內容長度不能超過65536個字符")
        return v

    @field_validator('updated_at')
    @classmethod
    def validate_updated_at(cls, v):
        if not v:
            raise ValueError("更新時間不能為空")
        # 允許誤差1小時
        if v < datetime.now() - timedelta(hours=1):
            raise ValueError("更新時間不能是過去時間")
        return v






