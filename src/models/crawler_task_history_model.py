from sqlalchemy import Integer, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional
from src.models.base_model import Base
from .base_entity import BaseEntity

class CrawlerTaskHistory(Base, BaseEntity):
    """爬蟲任務執行歷史記錄
    
    欄位說明：
    - task_id: 外鍵，關聯爬蟲任務
    - start_time: 開始時間
    - end_time: 結束時間
    - success: 是否成功
    - message: 訊息
    - articles_count: 文章數量
    """
    __tablename__ = 'crawler_task_history'

    task_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey('crawler_tasks.id'), 
        nullable=False
    )
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    success: Mapped[Optional[bool]] = mapped_column(Boolean)
    message: Mapped[Optional[str]] = mapped_column(Text)
    articles_count: Mapped[Optional[int]] = mapped_column(Integer)

    # 關聯到爬蟲任務
    task = relationship("CrawlerTasks", back_populates="history", lazy="joined")

    # 定義需要監聽的 datetime 欄位  
    _datetime_fields_to_watch = {'start_time', 'end_time'}

    def __init__(self, **kwargs):
        # 告知父類需要監聽的 datetime 欄位
        super().__init__(datetime_fields_to_watch=
                         self._datetime_fields_to_watch, **kwargs)

    def __repr__(self):
        return f"<CrawlerTaskHistory(id={self.id}, task_id={self.task_id}, start_time='{self.start_time}')>"
    
    def to_dict(self):
        return {
            **super().to_dict(),
            'task_id': self.task_id,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'success': self.success,
            'message': self.message,
            'articles_count': self.articles_count,
            'duration': (self.end_time - self.start_time).total_seconds() if self.end_time and self.start_time else None
        }