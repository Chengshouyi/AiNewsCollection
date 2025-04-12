from sqlalchemy import Integer, DateTime, Boolean, ForeignKey, Text, VARCHAR, String, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base_model import Base
from typing import Optional
from datetime import datetime
from .base_entity import BaseEntity
from sqlalchemy.dialects.mysql import JSON
from src.utils.model_utils import TaskPhase, ScrapeMode

TASK_ARGS_DEFAULT = {
    'max_pages': 10,
    'ai_only': False,
    'num_articles': 10,
    'min_keywords': 10,
    'max_retries': 3,
    'retry_delay': 2.0,
    'timeout': 10,
    'save_to_csv': False,
    'csv_file_prefix': '',
    'save_to_database': False,
    'scrape_mode': ScrapeMode.FULL_SCRAPE,
    'get_links_by_task_id': True,
    'article_links': []
}

class CrawlerTasks(Base, BaseEntity):
    """爬蟲任務模型
    
    欄位說明：
    - task_name: 任務名稱
    - crawler_id: 外鍵，關聯爬蟲
    - is_auto: 是否自動爬取
    - ai_only: 是否只爬取AI相關文章
    - notes: 備註
    - last_run_at: 上次執行時間
    - last_run_success: 上次執行成功與否
    - last_run_message: 上次執行訊息
    - cron_expression: 排程-cron表達式
    - current_phase: 當前任務階段
    - max_retries: 最大重試次數
    - retry_count: 當前重試次數
    - scrape_mode: 抓取模式
    - task_args: 任務參數 
        - max_pages: 最大頁數
        - ai_only: 是否只抓取AI相關文章
        - num_articles: 抓取的文章數量
        - min_keywords: 最小關鍵字數量
        - max_retries: 最大重試次數
        - retry_delay: 重試延遲時間
        - timeout: 超時時間 
        - save_to_csv: 是否保存到CSV文件
        - csv_file_prefix: CSV檔案名稱前綴，最終文件名格式為 {前綴}_{任務ID}_{時間戳}.csv
        - save_to_database: 是否保存到資料庫
        - scrape_mode: 抓取模式 (LINKS_ONLY, CONTENT_ONLY, FULL_SCRAPE)
        - get_links_by_task_id: 是否從資料庫根據任務ID獲取要抓取內容的文章(scrape_mode=CONTENT_ONLY時有效)
        - article_links: 要抓取內容的文章連結列表 (scrape_mode=CONTENT_ONLY且get_links_by_task_id=False時有效)
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
    ai_only: Mapped[bool] = mapped_column(
        Boolean, 
        default=False, 
        nullable=False
    )
    task_args: Mapped[dict] = mapped_column(JSON, default=TASK_ARGS_DEFAULT)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_run_success: Mapped[Optional[bool]] = mapped_column(Boolean)
    last_run_message: Mapped[Optional[str]] = mapped_column(Text)
    cron_expression: Mapped[Optional[str]] = mapped_column(VARCHAR(255))
    
    current_phase: Mapped[TaskPhase] = mapped_column(
        Enum(TaskPhase),
        default=TaskPhase.INIT,
        nullable=False
    )
    
    max_retries: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False
    )
    
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    
    scrape_mode: Mapped[ScrapeMode] = mapped_column(
        Enum(ScrapeMode),
        default=ScrapeMode.FULL_SCRAPE,
        nullable=False
    )

    # 新增與 Articles 的反向關聯
    articles = relationship("Articles", back_populates="task")

    crawler = relationship("Crawlers", back_populates="crawler_tasks", lazy="joined")

    history = relationship("CrawlerTaskHistory", back_populates="task", lazy="joined")

        
    # 定義需要監聽的 datetime 欄位
    _datetime_fields_to_watch = {'last_run_at'}

    def __init__(self, **kwargs):
        # 設置預設值
        if 'is_auto' not in kwargs:
            kwargs['is_auto'] = True
        if 'ai_only' not in kwargs:
            kwargs['ai_only'] = False
        if 'task_args' not in kwargs:
            kwargs['task_args'] = {}
        if 'current_phase' not in kwargs:
            kwargs['current_phase'] = TaskPhase.INIT
        if 'max_retries' not in kwargs:
            kwargs['max_retries'] = 3
        if 'retry_count' not in kwargs:
            kwargs['retry_count'] = 0
        if 'scrape_mode' not in kwargs:
            kwargs['scrape_mode'] = ScrapeMode.FULL_SCRAPE

        # 告知父類需要監聽的 datetime 欄位
        super().__init__(datetime_fields_to_watch=
                         self._datetime_fields_to_watch, **kwargs)

    def __repr__(self):
        return f"<CrawlerTask(id={self.id}, task_name={self.task_name}, crawler_id={self.crawler_id})>"
    
    def to_dict(self):
        return {
            **super().to_dict(),
            'task_name': self.task_name,
            'crawler_id': self.crawler_id,
            'is_auto': self.is_auto,
            'ai_only': self.ai_only,
            'task_args': self.task_args,
            'notes': self.notes,
            'last_run_at': self.last_run_at,
            'last_run_success': self.last_run_success,
            'last_run_message': self.last_run_message,
            'cron_expression': self.cron_expression,
            'current_phase': self.current_phase.value,
            'max_retries': self.max_retries,
            'retry_count': self.retry_count,
            'scrape_mode': self.scrape_mode.value
        }
