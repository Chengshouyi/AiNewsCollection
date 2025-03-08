# SQLAlchemy 模型定義
from sqlalchemy import Integer, String, DateTime, Boolean
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional

class Base(DeclarativeBase):
    @staticmethod
    def verify_insert_data(data: dict):
        """驗證資料"""
        raise NotImplementedError("子類別必須實作 verify_data 方法")
    
    @staticmethod
    def verify_update_data(data: dict):
        """驗證資料"""
        raise NotImplementedError("子類別必須實作 verify_data 方法")

class Article(Base):
    __tablename__ = 'articles'
    # 設定資料庫欄位
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(String)
    link: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(String)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.now, 
        nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # 文章資料repr
    def __repr__(self):
        return f"<Article(id={self.id}, title='{self.title}', link='{self.link}')>"
    
    # 驗證插入文章資料
    @staticmethod
    def verify_insert_data(data: dict):
        return bool(data.get('title') and data.get('link') and data.get('published_at'))
    
    # 驗證更新文章資料
    @staticmethod
    def verify_update_data(data: dict):
        return bool(
            ((data.get('title') is not None and data.get('title') != '') or data.get('title') is None)
            and 
            ((data.get('link') is not None and data.get('link') != '') or data.get('link') is None)
            and 
            ((data.get('published_at') is not None and data.get('published_at') != '') or data.get('published_at') is None)
            )

class SystemSettings(Base):
    __tablename__ = 'system_settings'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crawler_name: Mapped[str] = mapped_column(String, nullable=False)
    crawl_interval: Mapped[int] = mapped_column(Integer, nullable=False)
    crawl_start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    crawl_end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime)
    last_crawl_time: Mapped[datetime] = mapped_column(DateTime)

    # 系統設定資料repr  
    def __repr__(self):
        return f"<SystemSettings(id={self.id}, crawler_name='{self.crawler_name}', crawl_interval={self.crawl_interval}, crawl_start_time={self.crawl_start_time}, crawl_end_time={self.crawl_end_time}, is_active={self.is_active}, created_at={self.created_at}, updated_at={self.updated_at}, is_deleted={self.is_deleted}, deleted_at={self.deleted_at}, last_crawl_time={self.last_crawl_time})>"

    # 驗證系統設定資料
    @staticmethod
    def verify_insert_data(data: dict):
        return bool(data.get('crawler_name') and data.get('crawl_interval') and data.get('crawl_start_time') and data.get('crawl_end_time') and data.get('is_active'))

    # 驗證系統設定資料
    @staticmethod
    def verify_update_data(data: dict):
        return bool(
            ((data.get('crawler_name') is not None and data.get('crawler_name') != '') or data.get('crawler_name') is None)
            and 
            ((data.get('crawl_interval') is not None and data.get('crawl_interval') != '') or data.get('crawl_interval') is None)
            and 
            ((data.get('crawl_start_time') is not None and data.get('crawl_start_time') != '') or data.get('crawl_start_time') is None)
            and 
            ((data.get('crawl_end_time') is not None and data.get('crawl_end_time') != '') or data.get('crawl_end_time') is None)
            and 
            ((data.get('is_active') is not None and data.get('is_active') != '') or data.get('is_active') is None)
            )

