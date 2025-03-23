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
    - created_at: 建立時間
    - updated_at: 更新時間
    """
    def __init__(self, **kwargs):
        # 檢查必填欄位
        if 'crawler_id' not in kwargs:
            raise ValidationError("crawler_id is required")
            
        # 設置預設的 created_at
        if 'created_at' not in kwargs:
            kwargs['created_at'] = datetime.now(timezone.utc)
        if 'is_auto' not in kwargs:
            kwargs['is_auto'] = True
        if 'ai_only' not in kwargs:
            kwargs['ai_only'] = False
            
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
    crawlers = relationship("Crawlers", back_populates="crawler_tasks", lazy="joined")

    # 系統設定資料repr  
    def __repr__(self):
        return (
            f"<CrawlerTasks("
            f"id={self.id}, "
            f"crawler_id={self.crawler_id}, "
            f"is_auto={self.is_auto}, "
            f"ai_only={self.ai_only}"
            f")>"
        )
  
    def validate(self, is_update: bool = False) -> List[str]:
        """爬蟲任務驗證"""
        errors = []
        # 個性化驗證
        return errors
