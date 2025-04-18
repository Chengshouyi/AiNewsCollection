from sqlalchemy import Integer, DateTime, Boolean, ForeignKey, Text, VARCHAR, String, Enum as SQLAlchemyEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base_model import Base
from typing import Optional
from datetime import datetime
from .base_entity import BaseEntity
from src.utils.enum_utils import ScrapePhase, ScrapeMode, TaskStatus

TASK_ARGS_DEFAULT = {
    'max_pages': 10,
    'ai_only': False,
    'num_articles': 10,
    'min_keywords': 3,
    'max_retries': 3,
    'retry_delay': 2.0,
    'timeout': 10,
    'is_test': False,
    'save_to_csv': False,
    'csv_file_prefix': '',
    'save_to_database': True,
    'scrape_mode': ScrapeMode.FULL_SCRAPE.value,
    'get_links_by_task_id': True,
    'article_links': [],
    'save_partial_results_on_cancel': False,
    'save_partial_to_database': False,
    'max_cancel_wait': 30,
    'cancel_interrupt_interval': 5,
    'cancel_timeout': 60
}

class CrawlerTasks(Base, BaseEntity):
    """爬蟲任務模型
    
    欄位說明：
    - task_name: 任務名稱
    - crawler_id: 外鍵，關聯爬蟲
    - is_auto: 是否自動爬取
    - is_active: 是否啟用
    - is_scheduled: 是否已排程
    - notes: 備註
    - last_run_at: 上次執行時間
    - last_run_success: 上次執行成功與否
    - last_run_message: 上次執行訊息
    - cron_expression: 排程-cron表達式
    - scrape_phase: 當前爬取階段
    - task_status: 當前任務狀態
    - retry_count: 重試次數
    - task_args: 任務參數 
        - max_pages: 最大頁數
        - ai_only: 是否只抓取AI相關文章
        - num_articles: 抓取的文章數量
        - min_keywords: 最小關鍵字數量
        - max_retries: 最大重試次數
        - retry_delay: 重試延遲時間
        - timeout: 超時時間 
        - is_test: 是否為測試模式
        - save_to_csv: 是否保存到CSV文件
        - csv_file_prefix: CSV檔案名稱前綴，最終文件名格式為 {前綴}_{任務ID}_{時間戳}.csv
        - save_to_database: 是否保存到資料庫
        - scrape_mode: 抓取模式 (LINKS_ONLY, CONTENT_ONLY, FULL_SCRAPE)
        - get_links_by_task_id: 是否從資料庫根據任務ID獲取要抓取內容的文章(scrape_mode=CONTENT_ONLY時有效)
        - article_links: 要抓取內容的文章連結列表 (scrape_mode=CONTENT_ONLY且get_links_by_task_id=False時有效)
        - save_partial_results_on_cancel: 是否在取消時保存部分結果
        - save_partial_to_database: 是否在取消時將部分結果保存到資料庫
        - max_cancel_wait: 最大取消等待時間
        - cancel_interrupt_interval: 取消等待間隔
        - cancel_timeout: 取消超時時間
    """
    __tablename__ = 'crawler_tasks'

    task_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
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
    is_active: Mapped[bool] = mapped_column(
        Boolean, 
        default=True, 
        nullable=False
    )
    is_scheduled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    task_args: Mapped[dict] = mapped_column(JSON, default=TASK_ARGS_DEFAULT)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_run_success: Mapped[Optional[bool]] = mapped_column(Boolean)
    last_run_message: Mapped[Optional[str]] = mapped_column(Text)
    cron_expression: Mapped[Optional[str]] = mapped_column(VARCHAR(255))
    
    scrape_phase: Mapped[ScrapePhase] = mapped_column(
        SQLAlchemyEnum(ScrapePhase, values_callable=lambda x: [str(e.value) for e in ScrapePhase]),
        default=ScrapePhase.INIT.value,
        nullable=False
    )
    task_status: Mapped[TaskStatus] = mapped_column(
        SQLAlchemyEnum(TaskStatus, values_callable=lambda x: [str(e.value) for e in TaskStatus]),
        default=TaskStatus.INIT.value,
        nullable=False
    )

    # 新增與 Articles 的反向關聯
    articles = relationship("Articles", back_populates="task")

    crawler = relationship("Crawlers", back_populates="crawler_tasks", lazy="joined")

    history = relationship("CrawlerTaskHistory", back_populates="task", lazy="joined")

        
    # 定義需要監聽的 datetime 欄位
    _child_datetime_fields_to_watch = {'last_run_at'}

    def __init__(self, **kwargs):
        # 設置預設值
        if 'is_auto' not in kwargs:
            kwargs['is_auto'] = True
        if 'is_active' not in kwargs:
            kwargs['is_active'] = True
        if 'is_scheduled' not in kwargs:
            kwargs['is_scheduled'] = False
        if 'scrape_phase' not in kwargs:
            kwargs['scrape_phase'] = ScrapePhase.INIT
        if 'task_status' not in kwargs:
            kwargs['task_status'] = TaskStatus.INIT
        if 'retry_count' not in kwargs:
            kwargs['retry_count'] = 0
        if 'task_args' not in kwargs:
            kwargs['task_args'] = TASK_ARGS_DEFAULT

        # 告知父類需要監聽的 datetime 欄位
        super().__init__(datetime_fields_to_watch=
                         self._child_datetime_fields_to_watch, **kwargs)

    def __repr__(self):
        return f"<CrawlerTask(id={self.id}, task_name={self.task_name}, crawler_id={self.crawler_id})>"
    
    def to_dict(self):
        return {
            **super().to_dict(),
            'task_name': self.task_name,
            'crawler_id': self.crawler_id,
            'is_auto': self.is_auto,
            'is_active': self.is_active,
            'is_scheduled': self.is_scheduled,
            'task_args': self.task_args,
            'notes': self.notes,
            'last_run_at': self.last_run_at,
            'last_run_success': self.last_run_success,
            'last_run_message': self.last_run_message,
            'cron_expression': self.cron_expression,
            'scrape_phase': self.scrape_phase.value if self.scrape_phase else None,
            'retry_count': self.retry_count,
            'task_status': self.task_status.value if self.task_status else None,
        }
