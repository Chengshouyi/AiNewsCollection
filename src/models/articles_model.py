from sqlalchemy import UniqueConstraint, Integer, String, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base_model import Base
from typing import Optional
from datetime import datetime, timezone
from .base_entity import BaseEntity

class Articles(Base, BaseEntity):
    """文章模型
    
    欄位說明：
    - id: 主鍵
    - title: 文章標題
    - summary: 文章摘要
    - content: 文章內容
    - link: 文章連結
    - category: 文章分類
    - published_at: 文章發布時間
    - author: 文章作者
    - source: 文章來源
    - article_type: 文章類型
    - tags: 文章標籤
    - created_at: 建立時間
    - updated_at: 更新時間
    """
    __tablename__ = 'articles'
    __table_args__ = (
        # 保留資料庫層面的唯一性約束
        UniqueConstraint('link', name='uq_article_link'),
    )

    id: Mapped[int] = mapped_column(
        Integer, 
        primary_key=True, 
        autoincrement=True
    )
    title: Mapped[str] = mapped_column(
        String(500), 
        nullable=False
    )
    summary: Mapped[Optional[str]] = mapped_column(Text)
    content: Mapped[Optional[str]] = mapped_column(Text)
    link: Mapped[str] = mapped_column(
        String(1000), 
        unique=True, 
        nullable=False, 
        index=True
    )
    category: Mapped[Optional[str]] = mapped_column(String(100))
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc)
    )
    author: Mapped[Optional[str]] = mapped_column(String(100))
    source: Mapped[Optional[str]] = mapped_column(String(50))
    article_type: Mapped[Optional[str]] = mapped_column(String(20))
    tags: Mapped[Optional[str]] = mapped_column(String(500))
    is_ai_related: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        onupdate=lambda: datetime.now(timezone.utc)
    )

    article_links = relationship("ArticleLinks", back_populates="articles", lazy="joined")


    def __init__(self, **kwargs):
        # 設置默認值
        if 'created_at' not in kwargs:
            kwargs['created_at'] = datetime.now(timezone.utc)
        if 'is_ai_related' not in kwargs:
            kwargs['is_ai_related'] = False
            
        super().__init__(**kwargs)
    # 文章資料repr
    def __repr__(self):
        return f"<Article(id={self.id}, title='{self.title}', link='{self.link}')>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'summary': self.summary,
            'content': self.content,
            'link': self.link,
            'category': self.category,
            'published_at': self.published_at,
            'author': self.author,
            'source': self.source,
            'article_type': self.article_type,
            'tags': self.tags,
            'is_ai_related': self.is_ai_related,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
