"""本模組定義爬蟲任務執行歷史記錄模型，用於追蹤和記錄爬蟲任務的執行狀態、時間和結果。"""

from datetime import datetime
from typing import Optional
import logging

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base_model import Base
from src.models.base_entity import BaseEntity
from src.utils.enum_utils import TaskStatus

from src.utils.type_utils import AwareDateTime

logger = logging.getLogger(__name__)  # 使用統一的 logger


class CrawlerTaskHistory(Base, BaseEntity):
    """爬蟲任務執行歷史記錄

    欄位說明：
    - task_id: 外鍵，關聯爬蟲任務
    - start_time: 開始時間
    - end_time: 結束時間
    - success: 是否成功
    - message: 訊息
    - task_status: 任務狀態
    - articles_count: 文章數量
    """

    __tablename__ = "crawler_task_history"

    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("crawler_tasks.id"), nullable=False
    )
    start_time: Mapped[Optional[datetime]] = mapped_column(AwareDateTime)
    end_time: Mapped[Optional[datetime]] = mapped_column(AwareDateTime)
    success: Mapped[Optional[bool]] = mapped_column(Boolean)
    message: Mapped[Optional[str]] = mapped_column(Text)
    articles_count: Mapped[Optional[int]] = mapped_column(Integer)
    task_status: Mapped[TaskStatus] = mapped_column(
        SQLAlchemyEnum(
            TaskStatus,
            values_callable=lambda x: [str(e.value) for e in TaskStatus],
            native_enum=False,
        ),
        default=TaskStatus.INIT,
        nullable=False,
    )
    # 關聯到爬蟲任務
    task = relationship("CrawlerTasks", back_populates="history", lazy="joined")

    # 定義需要監聽的 datetime 欄位
    _aware_datetime_fields = Base._aware_datetime_fields.union(
        {"start_time", "end_time"}
    )

    def __init__(self, **kwargs):
        if "task_status" not in kwargs:
            kwargs["task_status"] = TaskStatus.INIT
        # 告知父類需要監聽的 datetime 欄位
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<CrawlerTaskHistory(id={self.id}, task_id={self.task_id}, start_time='{self.start_time}')>"

    def to_dict(self):
        return {
            **super().to_dict(),
            "task_id": self.task_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "success": self.success,
            "message": self.message,
            "articles_count": self.articles_count,
            "task_status": self.task_status.value if self.task_status else None,
            "duration": (
                (self.end_time - self.start_time).total_seconds()
                if self.end_time and self.start_time
                else None
            ),
        }
