from sqlalchemy import UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .base_models import Base
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.orm import relationship
from sqlalchemy import Integer, String, Boolean, DateTime, Text

class ArticleLinks(Base):
    __tablename__ = 'article_links'
    __table_args__ = (
        # 保留資料庫層面的唯一性約束
        UniqueConstraint('article_link', name='uq_article_link'),
        # 驗證source_name長度
        CheckConstraint('length(source_name) >= 1 AND length(source_name) <= 50', name='chk_article_link_source_name_length'),
        # 驗證source_url長度
        CheckConstraint('length(source_url) >= 1 AND length(source_url) <= 1000', name='chk_article_link_source_url_length'),
        # 驗證article_link長度
        CheckConstraint('length(article_link) >= 1 AND length(article_link) <= 1000', name='chk_article_link_article_link_length'),
        # 驗證is_scraped類型
        CheckConstraint('is_scraped IN (0, 1)', name='chk_article_link_is_scraped_type'),
        # 驗證created_at類型
        CheckConstraint('created_at >= 1 AND created_at <= 100', name='chk_article_link_created_at_type'),

    )
    def __setattr__(self, key, value):
        if key == 'id' and hasattr(self, 'id'):
            raise AttributeError("id cannot be updated")
        if key == 'article_link' and hasattr(self, 'article_link'):
            raise AttributeError("article_link cannot be updated")
        if key == 'created_at' and hasattr(self, 'created_at'):
            raise AttributeError("created_at cannot be updated")
        super().__setattr__(key, value)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False)
    article_link: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False)
    is_scraped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    
    # 使用已有的 article_link 欄位關聯到 Article
    article: Mapped[Optional["Article"]] = relationship(
        "Article", 
        primaryjoin="ArticleLinks.article_link==Article.link",
        backref="article_links",
        uselist=False
    )
    
    # 文章連結資料repr
    def __repr__(self):
        return f"<ArticleLink(id={self.id}, source_name='{self.source_name}', source_url='{self.source_url}', article_link='{self.article_link}', is_scraped={self.is_scraped})>"
    
    

class Article(Base):
    __tablename__ = 'articles'
    __table_args__ = (
        # 保留資料庫層面的唯一性約束
        UniqueConstraint('link', name='uq_article_link'),
        # 驗證title長度
        CheckConstraint('length(title) >= 1 AND length(title) <= 500', name='chk_article_title_length'),
        # 驗證summary長度
        CheckConstraint('length(summary) >= 1 AND length(summary) <= 10000', name='chk_article_summary_length'),
        # 驗證content長度
        CheckConstraint('length(content) >= 1 AND length(content) <= 65536', name='chk_article_content_length'),
        # 驗證tags長度
        CheckConstraint('length(tags) >= 1 AND length(tags) <= 500', name='chk_article_tags_length'),
        # 驗證category長度
        CheckConstraint('length(category) >= 1 AND length(category) <= 20', name='chk_article_category_length'),
        # 驗證author長度
        CheckConstraint('length(author) >= 1 AND length(author) <= 100', name='chk_article_author_length'),
        # 驗證source長度
        CheckConstraint('length(source) >= 1 AND length(source) <= 50', name='chk_article_source_length'),
        # 驗證article_type長度
        CheckConstraint('length(article_type) >= 1 AND length(article_type) <= 20', name='chk_article_article_type_length'),
        # 驗證link長度
        CheckConstraint('length(link) >= 1 AND length(link) <= 1000', name='chk_article_link_length'),
        # 驗證published_at長度
        CheckConstraint('length(published_at) >= 1 AND length(published_at) <= 100', name='chk_article_published_at_length'),
        # 驗證is_ai_related類型
        CheckConstraint('is_ai_related IN (0, 1)', name='chk_article_is_ai_related_type'),
        # 驗證created_at類型
        CheckConstraint('created_at >= 1 AND created_at <= 100', name='chk_article_created_at_type'),
        # 驗證updated_at類型
        CheckConstraint('updated_at >= 1 AND updated_at <= 100', name='chk_article_updated_at_type'),
    )
    def __setattr__(self, key, value):
        if key == 'id' and hasattr(self, 'id'):
            raise AttributeError("id cannot be updated")
        if key == 'link' and hasattr(self, 'link'):
            raise AttributeError("link cannot be updated")
        if key == 'created_at' and hasattr(self, 'created_at'):
            raise AttributeError("created_at cannot be updated")
        super().__setattr__(key, value)

    # 設定資料庫欄位
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    content: Mapped[Optional[str]] = mapped_column(Text)
    link: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    published_at: Mapped[Optional[str]] = mapped_column(String(100))
    author: Mapped[Optional[str]] = mapped_column(String(100))
    source: Mapped[Optional[str]] = mapped_column(String(50))
    article_type: Mapped[Optional[str]] = mapped_column(String(20))
    tags: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now(timezone.utc))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    # 文章資料repr
    def __repr__(self):
        return f"<Article(id={self.id}, title='{self.title}', link='{self.link}')>"