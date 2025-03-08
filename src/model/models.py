from abc import ABC, abstractmethod
from sqlalchemy import Integer, String, DateTime, Boolean
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

@runtime_checkable
class BaseProtocol(Protocol):
    @staticmethod
    def verify_insert_data(data: dict) -> bool: ...
    
    @staticmethod
    def verify_update_data(data: dict) -> bool: ...

class Base(DeclarativeBase):
    # 使用 Protocol 替代抽象基類
    pass

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
    def verify_insert_data(data: dict) -> bool:
        """驗證插入資料包含必要欄位"""
        required_fields = ['title', 'link', 'published_at']
        return all(data.get(field) for field in required_fields)
    
    # 驗證更新文章資料
    @staticmethod
    def verify_update_data(data: dict) -> bool:
        """
        驗證更新資料的合法性:
        1. 若提供了 title，則不為空
        2. 若提供了 link，則不為空
        3. 若提供了 published_at，則不為空
        """
        # 更新資料中至少有一個欄位
        if not data:
            return False
            
        # 檢查各欄位若存在則需有值
        for field in ['title', 'link', 'published_at']:
            if field in data and not data[field]:
                return False
                
        return True

class SystemSettings(Base):
    __tablename__ = 'system_settings'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crawler_name: Mapped[str] = mapped_column(String, nullable=False)
    crawl_interval: Mapped[int] = mapped_column(Integer, nullable=False)
    crawl_start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    crawl_end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_crawl_time: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # 系統設定資料repr  
    def __repr__(self):
        return f"<SystemSettings(id={self.id}, crawler_name='{self.crawler_name}', is_active={self.is_active})>"

    # 驗證系統設定資料
    @staticmethod
    def verify_insert_data(data: dict) -> bool:
        """驗證插入系統設定資料包含必要欄位"""
        required_fields = ['crawler_name', 'crawl_interval', 'crawl_start_time', 'crawl_end_time']
        return all(data.get(field) for field in required_fields)

    # 驗證系統設定資料
    @staticmethod
    def verify_update_data(data: dict) -> bool:
        """驗證更新系統設定資料的合法性"""
        if not data:
            return False
            
        # 檢查若提供了欄位則需有值
        fields_to_check = ['crawler_name', 'crawl_interval', 'crawl_start_time', 'crawl_end_time']
        for field in fields_to_check:
            if field in data and not data[field]:
                return False
        
        return True