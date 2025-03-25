from sqlalchemy import Integer, String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base_model import Base
from typing import Optional
from datetime import datetime, timezone
from .base_entity import BaseEntity

class Crawlers(Base, BaseEntity):
    """爬蟲設定模型
    
    欄位說明：
    - id: 主鍵
    - crawler_name: 爬蟲名稱
    - scrape_target: 爬取目標
    - crawl_interval: 爬取間隔
    - is_active: 是否啟用
    - created_at: 建立時間
    - updated_at: 更新時間
    - last_crawl_time: 最後爬取時間
    - crawler_type: 爬蟲類型
    """
    __tablename__ = 'crawlers'

    id: Mapped[int] = mapped_column(
        Integer, 
        primary_key=True, 
        autoincrement=True
    )
    crawler_name: Mapped[str] = mapped_column(
        String(100), 
        nullable=False
    )
    scrape_target: Mapped[str] = mapped_column(
        String(1000), 
        nullable=False
    )
    crawl_interval: Mapped[int] = mapped_column(
        Integer, 
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, 
        default=True, 
        nullable=False,
        server_default="1"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    last_crawl_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    crawler_type: Mapped[str] = mapped_column(
        String(100), 
        nullable=False
    )
    crawler_tasks = relationship("CrawlerTasks", back_populates="crawlers", lazy="joined")

    def __init__(self, **kwargs):
        # 設置默認值
        if 'created_at' not in kwargs:
            kwargs['created_at'] = datetime.now(timezone.utc)
        if 'is_active' not in kwargs:
            kwargs['is_active'] = True
            
        super().__init__(**kwargs)

    # 系統設定資料repr  
    def __repr__(self):
        return (
            f"<Crawlers("
            f"id={self.id}, "
            f"crawler_name='{self.crawler_name}', "
            f"scrape_target='{self.scrape_target}', "
            f"crawler_type='{self.crawler_type}', "
            f"is_active={self.is_active}"
            f")>"
        )
    
    def to_dict(self):
        return {
            'id': self.id,
            'crawler_name': self.crawler_name,
            'scrape_target': self.scrape_target,
            'is_active': self.is_active,
            'crawl_interval': self.crawl_interval,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'last_crawl_time': self.last_crawl_time,
            'crawler_type': self.crawler_type
        }

    

