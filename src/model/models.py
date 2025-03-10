from sqlalchemy import Integer, String, DateTime, Boolean
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import validates
from datetime import datetime
from typing import Optional


class Base(DeclarativeBase):
    pass

class Article(Base):
    __tablename__ = 'articles'
    # 設定資料庫欄位
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(String(1024))
    link: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(String)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.now, 
        nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # 文章資料repr
    def __repr__(self):
        return f"<Article(id={self.id}, title='{self.title}', link='{self.link}')>"
    
    @validates('title')
    def validate_title(self, key, title):
        if len(title.strip()) < 1 or len(title.strip()) > 255:
            raise ValueError("標題長度需在 1 到 255 個字元之間")
        return title

    @validates('link')
    def validate_link(self, key, link):
        if len(link.strip()) < 1 or len(link.strip()) > 512:
            raise ValueError("連結長度需在 1 到 512 個字元之間")
        return link
    
    @validates('summary')
    def validate_summary(self, key, summary):
        if len(summary.strip()) > 1024:
            raise ValueError("摘要長度需在 0 到 1024 個字元之間")
        return summary
    
    @validates('content')
    def validate_content(self, key, content):
        if len(content.strip()) > 65536:
            raise ValueError("內容長度需在 0 到 65536 個字元之間")
        return content
    
    @validates('published_at')
    def validate_published_at(self, key, published_at):
        if published_at is None:
            raise ValueError("發布時間不能為空")
        return published_at
    
    @validates('source')
    def validate_source(self, key, source):
        if len(source.strip()) > 255 or len(source.strip()) < 1:
            raise ValueError("來源長度需在 1 到 255 個字元之間")
        return source
    

class SystemSettings(Base):
    __tablename__ = 'system_settings'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crawler_name: Mapped[str] = mapped_column(String, nullable=False)
    crawl_interval: Mapped[int] = mapped_column(Integer, nullable=False)
    crawl_start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    crawl_end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_crawl_time: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # 系統設定資料repr  
    def __repr__(self):
        return f"<SystemSettings(id={self.id}, crawler_name='{self.crawler_name}', is_active={self.is_active})>"

    @validates('crawler_name')
    def validate_crawler_name(self, key, crawler_name):
        if len(crawler_name.strip()) < 1 or len(crawler_name.strip()) > 255:
            raise ValueError("爬蟲名稱長度需在 1 到 255 個字元之間")
        return crawler_name
    
    @validates('crawl_interval')
    def validate_crawl_interval(self, key, crawl_interval):
        if crawl_interval < 0:
            raise ValueError("爬取間隔需大於 0")
        return crawl_interval

    @validates('crawl_start_time')
    def validate_crawl_start_time(self, key, crawl_start_time):
        if crawl_start_time is None:
            raise ValueError("爬取開始時間不能為空")
        return crawl_start_time
    
    @validates('crawl_end_time')
    def validate_crawl_end_time(self, key, crawl_end_time):
        if crawl_end_time is None:
            raise ValueError("爬取結束時間不能為空")
        return crawl_end_time

    @validates('is_active')
    def validate_is_active(self, key, is_active):
        if is_active is None:
            raise ValueError("是否啟用不能為空")
        return is_active
    
    @validates('created_at')
    def validate_created_at(self, key, created_at):
        if created_at is None:
            raise ValueError("建立時間不能為空")
        return created_at


    
    
    
    
    
    
    
    
    
    
    
    
