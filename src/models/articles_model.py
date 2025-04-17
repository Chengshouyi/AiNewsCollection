from sqlalchemy import UniqueConstraint, Integer, String, DateTime, Text, Boolean, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base_model import Base
from typing import Optional
from datetime import datetime
from .base_entity import BaseEntity
import logging
from src.utils.enum_utils import ArticleScrapeStatus

# 設定 logger
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



class Articles(Base, BaseEntity):
    """文章模型
    
    欄位說明：
    - title: 文章標題
    - summary: 文章摘要
    - content: 文章內容
    - link: 文章連結
    - category: 文章分類
    - published_at: 文章發布時間
    - author: 文章作者
    - source: 文章來源
    - source_url: 來源URL
    - article_type: 文章類型
    - tags: 文章標籤
    - is_ai_related: 是否與ai相關
    - is_scraped: 是否已爬取
    - scrape_status: 爬取狀態
    - scrape_error: 爬取錯誤訊息
    - last_scrape_attempt: 最後爬取嘗試時間
    - task_id: 爬取任務ID
    """
    __tablename__ = 'articles'
    __table_args__ = (
        # 保留資料庫層面的唯一性約束
        UniqueConstraint('link', name='uq_article_link'),
    )

    
    title: Mapped[str] = mapped_column(
        String(500), 
        nullable=False
    )
    summary: Mapped[Optional[str]] = mapped_column(Text)
    content: Mapped[Optional[str]] = mapped_column(Text)
    link: Mapped[str] = mapped_column(
        String(1000), 
        unique=True, 
        nullable=False, 
        index=True
    )
    category: Mapped[Optional[str]] = mapped_column(String(100))
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    author: Mapped[Optional[str]] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(50))
    source_url: Mapped[str] = mapped_column(
        String(1000),
        nullable=False
    )
    article_type: Mapped[Optional[str]] = mapped_column(String(20))
    tags: Mapped[Optional[str]] = mapped_column(String(500))
    is_ai_related: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    is_scraped: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    
    scrape_status: Mapped[ArticleScrapeStatus] = mapped_column(
        Enum(ArticleScrapeStatus),
        default=ArticleScrapeStatus.PENDING,
        nullable=False
    )
    
    scrape_error: Mapped[Optional[str]] = mapped_column(Text)
    
    last_scrape_attempt: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    
    # 新增與 CrawlerTasks 的關聯
    task_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey('crawler_tasks.id'),
        nullable=True
    )
    
    # 新增關聯關係
    task = relationship("CrawlerTasks", back_populates="articles")
    
    # 定義需要監聽的 datetime 欄位
    _child_datetime_fields_to_watch = {'published_at', 'last_scrape_attempt'}

    def __init__(self, **kwargs):
        # 設置默認值
        if 'is_ai_related' not in kwargs:
            kwargs['is_ai_related'] = False

        if 'is_scraped' not in kwargs:
            kwargs['is_scraped'] = False
        # 告知父類需要監聽的 datetime 欄位
        super().__init__(datetime_fields_to_watch=
                         self._child_datetime_fields_to_watch, **kwargs)

    # 文章資料repr
    def __repr__(self):
        return f"<Article(id={self.id}, title='{self.title[:30]}{'...' if len(self.title) > 30 else ''}', link='{self.link}')>"
    
    def to_dict(self):
        return {
            **super().to_dict(),
            'title': self.title,
            'summary': self.summary,
            'content': self.content,
            'link': self.link,
            'category': self.category,
            'published_at': self.published_at,
            'author': self.author,
            'source': self.source,
            'source_url': self.source_url,
            'article_type': self.article_type,
            'tags': self.tags,
            'is_ai_related': self.is_ai_related,
            'is_scraped': self.is_scraped,
            'scrape_status': self.scrape_status.value if self.scrape_status else None,
            'scrape_error': self.scrape_error,
            'last_scrape_attempt': self.last_scrape_attempt,
            'task_id': self.task_id
        }
