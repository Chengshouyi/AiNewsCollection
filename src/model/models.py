from sqlalchemy import Integer, String, DateTime, Boolean, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional

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

class Article(Base):
    __tablename__ = 'articles'
    __table_args__ = (
        # 保留資料庫層面的唯一性約束
        UniqueConstraint('link', name='uq_article_link'),
    )
    # 設定資料庫欄位
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    content: Mapped[Optional[str]] = mapped_column(Text)
    link: Mapped[str] = mapped_column(String(1000), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    published_at: Mapped[Optional[str]] = mapped_column(String(100))
    author: Mapped[Optional[str]] = mapped_column(String(100))
    source: Mapped[Optional[str]] = mapped_column(String(50))
    article_type: Mapped[Optional[str]] = mapped_column(String(20))
    tags: Mapped[Optional[str]] = mapped_column(String(500))
    content_length: Mapped[Optional[int]] = mapped_column(Integer)
    is_ai_related: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 文章資料repr
    def __repr__(self):
        return f"<Article(id={self.id}, title='{self.title}', link='{self.link}')>"
    


class SystemSettings(Base):
    __tablename__ = 'system_settings'
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
  
