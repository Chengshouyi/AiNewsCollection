from sqlalchemy import UniqueConstraint, ForeignKey, Integer, String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base_model import Base
from typing import Optional
from datetime import datetime, timezone
from .base_entity import BaseEntity

class ArticleLinks(Base, BaseEntity):
    """文章連結模型
    
    欄位說明：
    - source_name: 來源名稱
    - source_url: 來源URL
    - article_link: 文章連結
    - title: 標題
    - summary: 摘要
    - category: 分類
    - published_age: 發佈的年齡
    - is_scraped: 是否已爬取
    """
    __tablename__ = 'article_links'
    __table_args__ = (
        # 保留資料庫層面的唯一性約束
        UniqueConstraint('article_link', name='uq_article_link'),
    )
    source_name: Mapped[str] = mapped_column(
        String(50), 
        nullable=False
    )
    source_url: Mapped[str] = mapped_column(
        String(1000), 
        unique=True, 
        nullable=False
    )
    article_link: Mapped[str] = mapped_column(
        String(1000), 
        ForeignKey("articles.link"),
        unique=True, 
        nullable=False, 
        index=True
    )
    title: Mapped[str] = mapped_column(
        String(1000),
        nullable=False
    )
    summary: Mapped[str] = mapped_column(
        String(1000),
        nullable=False
    )
    category: Mapped[str] = mapped_column(
        String(1000),
        nullable=False
    )
    published_age: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    is_scraped: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        default=False
    )
    articles = relationship("Articles", back_populates="article_links", lazy="joined")

    def __init__(self, **kwargs):
        # 設置默認值
        if 'is_scraped' not in kwargs:
            kwargs['is_scraped'] = False
            
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<ArticleLink(id={self.id}, source_name='{self.source_name}', article_link='{self.article_link}')>"
    
    def to_dict(self):
        return {
            **super().to_dict(),
            'source_name': self.source_name,
            'source_url': self.source_url,
            'article_link': self.article_link,
            'title': self.title,
            'summary': self.summary,
            'category': self.category,
            'published_age': self.published_age,
            'is_scraped': self.is_scraped,
        }
    