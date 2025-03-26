from sqlalchemy import Integer, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from typing import Optional
from src.models.base_model import Base
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
    __tablename__ = 'crawler_task_history'

    id: Mapped[int] = mapped_column(
        Integer, 
        primary_key=True, 
        autoincrement=True,
        nullable=False
    )
    task_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey('crawler_tasks.id'), 
        nullable=False
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    success: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    message: Mapped[Optional[str]] = mapped_column(Text)
    articles_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    # 關聯到爬蟲任務
    task = relationship("CrawlerTasks", back_populates="history", lazy="joined")

    def __init__(self, **kwargs):
        if 'start_time' not in kwargs:
            kwargs['start_time'] = datetime.now(timezone.utc)
        if 'success' not in kwargs:
            kwargs['success'] = False
        if 'articles_count' not in kwargs:
            kwargs['articles_count'] = 0
            
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<CrawlerTaskHistory(id={self.id}, task_id={self.task_id}, start_time='{self.start_time}')>"
    
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