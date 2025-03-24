from sqlalchemy import Integer, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from typing import Optional, List
from src.models.base_model import Base
from src.error.errors import ValidationError
from .base_entity import BaseEntity

class CrawlerTaskHistory(Base, BaseEntity):
    """爬蟲任務執行歷史記錄
    
    欄位說明：
    - id: 主鍵
    - task_id: 外鍵，關聯爬蟲任務
    - start_time: 開始時間
    - end_time: 結束時間
    - success: 是否成功
    - message: 訊息
    - articles_count: 文章數量
    """
    
    def __init__(self, **kwargs):
        # 檢查必填欄位
        if 'task_id' not in kwargs:
            raise ValidationError("task_id is required")
            
        # 設置預設的 start_time
        if 'start_time' not in kwargs:
            kwargs['start_time'] = datetime.now(timezone.utc)
        
        # 確保 success 有默認值
        if 'success' not in kwargs:
            kwargs['success'] = False
        
        # 確保 articles_count 有默認值
        if 'articles_count' not in kwargs:
            kwargs['articles_count'] = 0
            
        super().__init__(**kwargs)
        self.is_initialized = True
    
    __tablename__ = 'crawler_task_history'
    
    def __setattr__(self, key, value):
        if not hasattr(self, 'is_initialized'):
            super().__setattr__(key, value)
            return

        if key in ['id', 'start_time'] and hasattr(self, key):
            raise ValidationError(f"{key} cannot be updated")

        super().__setattr__(key, value)
    
    id: Mapped[int] = mapped_column(
        Integer, 
        primary_key=True, 
        autoincrement=True
    )
    task_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey('crawler_tasks.id'), 
        nullable=False
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime, 
        nullable=False
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime
    )
    success: Mapped[bool] = mapped_column(
        Boolean, 
        default=lambda: False
    )
    message: Mapped[Optional[str]] = mapped_column(
        Text
    )
    articles_count: Mapped[int] = mapped_column(
        Integer, 
        default=lambda: 0
    )
    
    # 關聯到爬蟲任務
    task = relationship("CrawlerTasks", back_populates="history", lazy="joined")
    
    # 系統設定資料repr
    def __repr__(self):
        return (
            f"<CrawlerTaskHistory("
            f"id={self.id}, "
            f"task_id={self.task_id}, "
            f"start_time={self.start_time}, "
            f"success={self.success}"
            f")>"
        )
    
    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'success': self.success,
            'message': self.message,
            'articles_count': self.articles_count,
            'duration': (self.end_time - self.start_time).total_seconds() if self.end_time else None
        } 
    
    def validate(self, is_update: bool = False) -> List[str]:
        """爬蟲任務執行歷史記錄驗證"""
        errors = []
        # 個性化驗證
        return errors