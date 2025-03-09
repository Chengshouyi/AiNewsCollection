from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timedelta
from typing import Optional

class ArticleCreateSchema(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    summary: Optional[str] = Field(default=None, max_length=1024)
    link: Optional[str] = Field(default=None, min_length=1, max_length=512)
    content: Optional[str] = Field(default=None, max_length=65536)
    published_at: Optional[datetime] = None
    source: Optional[str] = Field(default=None, max_length=255)

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
