from sqlalchemy import Integer, String, DateTime, Boolean
from sqlalchemy import CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .base_models import Base
from typing import Optional
from datetime import datetime

class CrawlerSettings(Base):
    __tablename__ = 'crawler_settings'
    __table_args__ = (
        # 驗證crawler_name長度
        CheckConstraint('length(crawler_name) >= 1 AND length(crawler_name) <= 100', name='chk_system_settings_crawler_name_length'),
        # 驗證scrape_target長度
        CheckConstraint('length(scrape_target) >= 1 AND length(scrape_target) <= 1000', name='chk_system_settings_scrape_target_length'),
        # 驗證crawl_interval類型
        CheckConstraint('crawl_interval >= 1 AND crawl_interval <= 100', name='chk_system_settings_crawl_interval_type'),
        # 驗證is_active類型
        CheckConstraint('is_active IN (0, 1)', name='chk_system_settings_is_active_type'),
        # 驗證created_at類型
        CheckConstraint('created_at >= 1 AND created_at <= 100', name='chk_system_settings_created_at_type'),
        # 驗證updated_at類型
        CheckConstraint('updated_at >= 1 AND updated_at <= 100', name='chk_system_settings_updated_at_type'),
        # 驗證last_crawl_time類型
        CheckConstraint('last_crawl_time >= 1 AND last_crawl_time <= 100', name='chk_system_settings_last_crawl_time_type')
    )
    def __setattr__(self, key, value):
        if key == 'id' and hasattr(self, 'id'):
            raise AttributeError("id cannot be updated")
        if key == 'created_at' and hasattr(self, 'created_at'):
            raise AttributeError("created_at cannot be updated")
        super().__setattr__(key, value)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, description="主鍵")
    crawler_name: Mapped[str] = mapped_column(String(100), nullable=False, description="爬蟲名稱")
    scrape_target: Mapped[str] = mapped_column(String(1000), nullable=False, description="爬取目標")
    crawl_interval: Mapped[int] = mapped_column(Integer, nullable=False, description="爬取間隔")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, description="是否啟用")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, description="建立時間")
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, description="更新時間")
    last_crawl_time: Mapped[Optional[datetime]] = mapped_column(DateTime, description="最後爬取時間")

    # 系統設定資料repr  
    def __repr__(self):
        return f"<CrawlerSettings(id={self.id}, crawler_name='{self.crawler_name}', 
        scrape_target='{self.scrape_target}', is_active={self.is_active})>"
  
