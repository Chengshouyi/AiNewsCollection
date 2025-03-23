from sqlalchemy import UniqueConstraint, CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from .base_models import Base
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import relationship
from sqlalchemy import Integer, String, Boolean, DateTime, Text
from .base_entity import BaseEntity
from src.error.errors import ValidationError

class ArticleLinks(Base, BaseEntity):
    """文章連結模型
    
    欄位說明：
    - id: 主鍵
    - source_name: 來源名稱
    - source_url: 來源URL
    - article_link: 文章連結
    - is_scraped: 是否已爬取
    - created_at: 建立時間
    """
    def __init__(self, **kwargs):
        # 設置預設的 created_at
        if 'created_at' not in kwargs:
            kwargs['created_at'] = datetime.now(timezone.utc)
        if 'is_scraped' not in kwargs:
            kwargs['is_scraped'] = False
            
        super().__init__(**kwargs)
        self.is_initialized = True

    __tablename__ = 'article_links'
    __table_args__ = (
        # 保留資料庫層面的唯一性約束
        UniqueConstraint(
            'article_link', 
            name='uq_article_link'
            ),
        # 驗證source_name長度
        CheckConstraint(
            'length(source_name) >= 1 AND length(source_name) <= 50', 
            name='chk_article_link_source_name_length'
            ),
        # 驗證source_url長度
        CheckConstraint(
            'length(source_url) >= 1 AND length(source_url) <= 1000', 
            name='chk_article_link_source_url_length'
            ),
        # 驗證article_link長度
        CheckConstraint(
            'length(article_link) >= 1 AND length(article_link) <= 1000', name='chk_article_link_article_link_length'
            ),
        # 驗證is_scraped類型
        CheckConstraint(
            'is_scraped IN (0, 1)', 
            name='chk_article_link_is_scraped_type'
            )
    )
    def __setattr__(self, key, value):
        if not hasattr(self, 'is_initialized'):
            super().__setattr__(key, value)
            return

        if key in ['id', 'article_link', 'created_at'] and hasattr(self, key):
            raise ValidationError(f"{key} cannot be updated")

        super().__setattr__(key, value)


    id: Mapped[int] = mapped_column(
        Integer, 
        primary_key=True, 
        autoincrement=True
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
    is_scraped: Mapped[bool] = mapped_column(
        Boolean, 
        default=lambda: False, 
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    # 使用已有的 article_link 欄位關聯到 Article
    article: Mapped[Optional["Article"]] = relationship(
        "Article",
        back_populates="article_links",
        primaryjoin="ArticleLinks.article_link==Article.link"
    )
    
    # 文章連結資料repr
    def __repr__(self):
        return f"<ArticleLink(id={self.id}, source_name='{self.source_name}', source_url='{self.source_url}', article_link='{self.article_link}', is_scraped={self.is_scraped})>"
    
    def validate(self, is_update: bool = False) -> List[str]:
        """文章連結驗證"""
        errors = []
        # 個性化驗證
        return errors

class Article(Base, BaseEntity):
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
    def __init__(self, **kwargs):
        # 設置預設的 created_at
        if 'created_at' not in kwargs:
            kwargs['created_at'] = datetime.now(timezone.utc)
            
        super().__init__(**kwargs)
        self.is_initialized = True

    __tablename__ = 'articles'
    __table_args__ = (
        # 保留資料庫層面的唯一性約束
        UniqueConstraint(
            'link', 
            name='uq_article_link'
            ),
        # 驗證title長度
        CheckConstraint(
            'length(title) >= 1 AND length(title) <= 500', 
            name='chk_article_title_length'
            ),
        # 驗證summary長度
        CheckConstraint(
            'length(summary) >= 1 AND length(summary) <= 10000', 
            name='chk_article_summary_length'
            ),
        # 驗證content長度
        CheckConstraint(
            'length(content) >= 1 AND length(content) <= 65536', 
            name='chk_article_content_length'
            ),
        # 驗證tags長度
        CheckConstraint(
            'length(tags) >= 1 AND length(tags) <= 500', 
            name='chk_article_tags_length'
            ),
        # 驗證category長度
        CheckConstraint(
            'length(category) >= 1 AND length(category) <= 20', 
            name='chk_article_category_length'
            ),
        # 驗證author長度
        CheckConstraint(
            'length(author) >= 1 AND length(author) <= 100', 
            name='chk_article_author_length'
            ),
        # 驗證source長度
        CheckConstraint(
            'length(source) >= 1 AND length(source) <= 50', 
            name='chk_article_source_length'
            ),
        # 驗證article_type長度
        CheckConstraint(
            'length(article_type) >= 1 AND length(article_type) <= 20',             name='chk_article_article_type_length'
            ),
        # 驗證link長度
        CheckConstraint(
            'length(link) >= 1 AND length(link) <= 1000', 
            name='chk_article_link_length'
            )
    )
    def __setattr__(self, key, value):
        if not hasattr(self, 'is_initialized'):
            super().__setattr__(key, value)
            return

        if key in ['id', 'link', 'created_at'] and hasattr(self, key):
            raise ValidationError(f"{key} cannot be updated")

        super().__setattr__(key, value)


    # 設定資料庫欄位
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
    published_at: Mapped[Optional[str]] = mapped_column(String(100))
    author: Mapped[Optional[str]] = mapped_column(String(100))
    source: Mapped[Optional[str]] = mapped_column(String(50))
    article_type: Mapped[Optional[str]] = mapped_column(String(20))
    tags: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # 文章連結資料
    article_links: Mapped[Optional["ArticleLinks"]] = relationship(
        "ArticleLinks",
        back_populates="article",
        primaryjoin="Article.link==ArticleLinks.article_link"
    )

    # 文章資料repr
    def __repr__(self):
        return f"<Article(id={self.id}, title='{self.title}', link='{self.link}')>"
    
    def validate(self, is_update: bool = False) -> List[str]:
        """文章驗證"""
        errors = []
        # 個性化驗證
        return errors