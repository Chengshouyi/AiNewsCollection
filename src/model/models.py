from sqlalchemy import Integer, String, DateTime, Boolean, Text, ForeignKey, ForeignKeyConstraint
from sqlalchemy import UniqueConstraint, CheckConstraint
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import relationship

# 自定義應用程式錯誤層級
class AppError(Exception):
    """Base application error"""
    pass

class OptionError(AppError):
    """Option error"""
    pass

class ValidationError(AppError):
    """Validation error"""
    pass

class NotFoundError(AppError):
    """Resource not found error"""
    pass

class Base(DeclarativeBase):
    pass

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
        #拒絕更新article_link
        CheckConstraint('article_link IS NOT NULL', name='chk_article_link_article_link_not_null')
    )
    def __setattr__(self, key, value):
        if key == 'article_link' and hasattr(self, 'article_link'):
            raise AttributeError("article_link cannot be updated")
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
        if key == 'link' and hasattr(self, 'link'):
            raise AttributeError("link cannot be updated")
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
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 文章資料repr
    def __repr__(self):
        return f"<Article(id={self.id}, title='{self.title}', link='{self.link}')>"
    


class SystemSettings(Base):
    __tablename__ = 'system_settings'
    __table_args__ = (
        #設定crawler_name為唯一
        UniqueConstraint('crawler_name', name='uq_system_settings_crawler_name'),
        # 驗證crawler_name長度
        CheckConstraint('length(crawler_name) >= 1 AND length(crawler_name) <= 50', name='chk_system_settings_crawler_name_length'),
        # 驗證crawl_interval類型
        CheckConstraint('crawl_interval >= 1 AND crawl_interval <= 100', name='chk_system_settings_crawl_interval_type'),
        # 驗證is_active類型
        CheckConstraint('is_active IN (0, 1)', name='chk_system_settings_is_active_type'),
        # 驗證created_at類型
        CheckConstraint('created_at >= 1 AND created_at <= 100', name='chk_system_settings_created_at_type'),
        # 驗證updated_at類型
        CheckConstraint('updated_at >= 1 AND updated_at <= 100', name='chk_system_settings_updated_at_type'),
        # 驗證last_crawl_time類型
        CheckConstraint('last_crawl_time >= 1 AND last_crawl_time <= 100', name='chk_system_settings_last_crawl_time_type')
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crawler_name: Mapped[str] = mapped_column(String, nullable=False)
    crawl_interval: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_crawl_time: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # 系統設定資料repr  
    def __repr__(self):
        return f"<SystemSettings(id={self.id}, crawler_name='{self.crawler_name}', is_active={self.is_active})>"
  
