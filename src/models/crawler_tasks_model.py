from sqlalchemy import Integer, DateTime, Boolean, ForeignKey, Text
from sqlalchemy import CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base_model import Base
from src.error.errors import ValidationError
from typing import Optional, List
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
    def __init__(self, **kwargs):
        # 檢查必填欄位
        if 'crawler_id' not in kwargs:
            raise ValidationError("crawler_id is required")
            
        # 設置預設的設定
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
        self.is_initialized = True

    __tablename__ = 'crawler_tasks'
    __table_args__ = (
        # 驗證is_auto類型
        CheckConstraint(
            'is_auto IN (0, 1)', 
            name='chk_crawler_tasks_is_auto_type'
        ),
        # 驗證ai_only類型
        CheckConstraint(
            'ai_only IN (0, 1)', 
            name='chk_crawler_tasks_ai_only_type'
        ),
    )
    
    def __setattr__(self, key, value):
        if not hasattr(self, 'is_initialized'):
            super().__setattr__(key, value)
            return

        if key in ['id', 'created_at'] and hasattr(self, key):
            raise ValidationError(f"{key} cannot be updated")

        super().__setattr__(key, value)

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
        default=lambda: True, 
        nullable=False
    )
    ai_only: Mapped[bool] = mapped_column(
        Boolean, 
        default=lambda: False, 
        nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text
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
    max_pages: Mapped[Optional[int]] = mapped_column(
        Integer,
        default=lambda: 3,
        nullable=False
    )
    num_articles: Mapped[Optional[int]] = mapped_column(
        Integer,
        default=lambda: 10,
        nullable=False
    )
    min_keywords: Mapped[Optional[int]] = mapped_column(
        Integer,
        default=lambda: 3,
        nullable=False
    )
    fetch_details: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        default=lambda: False,
        nullable=False
    )
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime
    )
    last_run_success: Mapped[Optional[bool]] = mapped_column(
        Boolean
    )
    last_run_message: Mapped[Optional[str]] = mapped_column(
        Text
    )
    schedule: Mapped[Optional[str]] = mapped_column(
        Text
    )
    
    crawlers = relationship("Crawlers", back_populates="crawler_tasks", lazy="joined")
    history = relationship("CrawlerTaskHistory", back_populates="task", lazy="joined")

    # 系統設定資料repr  
    def __repr__(self):
        return (
            f"<CrawlerTasks("
            f"id={self.id}, "
            f"crawler_id={self.crawler_id}, "
            f"is_auto={self.is_auto}, "
            f"ai_only={self.ai_only}, "
            f"max_pages={self.max_pages}, "
            f"num_articles={self.num_articles}, "
            f"min_keywords={self.min_keywords}, "
            f"fetch_details={self.fetch_details}, "
            f"notes={self.notes}, "
            f"schedule={self.schedule}, "
            f"last_run_at={self.last_run_at}, "
            f"last_run_success={self.last_run_success}, "
            f"last_run_message={self.last_run_message}"
            f")>"
        )
    
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
    
    def validate(self, is_update: bool = False) -> List[str]:
        """爬蟲任務驗證"""
        errors = []
        # 個性化驗證
        return errors
