from sqlalchemy import Integer, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base_model import Base
from typing import Optional
from datetime import datetime, timezone
from .base_entity import BaseEntity

class CrawlerTasks(Base, BaseEntity):
    """爬蟲任務模型
    
    欄位說明：
    - id: 主鍵
    - crawler_id: 外鍵，關聯爬蟲
    - is_auto: 是否自動爬取
    - ai_only: 是否僅收集 AI 相關
    - notes: 備註
    - max_pages: 最大爬取頁數
    - num_articles: 最大爬取文章數
    - min_keywords: 最小關鍵字數
    - fetch_details: 是否抓取詳細資料
    - created_at: 建立時間
    - updated_at: 更新時間
    - last_run_at: 上次執行時間
    - last_run_success: 上次執行成功與否
    - last_run_message: 上次執行訊息
    - schedule: 排程
    """
    __tablename__ = 'crawler_tasks'

    id: Mapped[int] = mapped_column(
        Integer, 
        primary_key=True, 
        autoincrement=True
    )
    crawler_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('crawlers.id'),
        nullable=False
    )
    is_auto: Mapped[bool] = mapped_column(
        Boolean, 
        default=True, 
        nullable=False
    )
    ai_only: Mapped[bool] = mapped_column(
        Boolean, 
        default=False, 
        nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)
    max_pages: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False
    )
    num_articles: Mapped[int] = mapped_column(
        Integer,
        default=10,
        nullable=False
    )
    min_keywords: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False
    )
    fetch_details: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_run_success: Mapped[Optional[bool]] = mapped_column(Boolean)
    last_run_message: Mapped[Optional[str]] = mapped_column(Text)
    schedule: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        onupdate=lambda: datetime.now(timezone.utc)
    )

    crawlers = relationship("Crawlers", back_populates="crawler_tasks")
    history = relationship("CrawlerTaskHistory", back_populates="task", lazy="joined")

    def __init__(self, **kwargs):
        if 'created_at' not in kwargs:
            kwargs['created_at'] = datetime.now(timezone.utc)
        if 'is_auto' not in kwargs:
            kwargs['is_auto'] = True
        if 'ai_only' not in kwargs:
            kwargs['ai_only'] = False
        if 'max_pages' not in kwargs:   
            kwargs['max_pages'] = 3
        if 'num_articles' not in kwargs:
            kwargs['num_articles'] = 10
        if 'min_keywords' not in kwargs:
            kwargs['min_keywords'] = 3
        if 'fetch_details' not in kwargs:
            kwargs['fetch_details'] = False
            
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<CrawlerTask(id={self.id}, crawler_id={self.crawler_id})>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'crawler_id': self.crawler_id,
            'is_auto': self.is_auto,
            'ai_only': self.ai_only,
            'max_pages': self.max_pages,
            'num_articles': self.num_articles,
            'min_keywords': self.min_keywords,
            'fetch_details': self.fetch_details,
            'notes': self.notes,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'last_run_at': self.last_run_at,
            'last_run_success': self.last_run_success,
            'last_run_message': self.last_run_message,
            'schedule': self.schedule
        }
