from sqlalchemy import Integer, String, DateTime, Boolean
from sqlalchemy import CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.model.base_models import Base
from src.error.errors import ValidationError
from typing import Optional, List
from datetime import datetime, timezone
from .base_entity import BaseEntity

class CrawlerSettings(Base, BaseEntity):
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
    """
    def __init__(self, **kwargs):
        # 設置預設的 created_at
        if 'created_at' not in kwargs:
            kwargs['created_at'] = datetime.now(timezone.utc)
        if 'is_active' not in kwargs:
            kwargs['is_active'] = True
            
        super().__init__(**kwargs)
        self.is_initialized = True

    __tablename__ = 'crawler_settings'
    __table_args__ = (
        # 驗證crawler_name長度
        CheckConstraint(
            'length(crawler_name) >= 1 AND length(crawler_name) <= 100', name='chk_system_settings_crawler_name_length'
            ),
        # 驗證scrape_target長度
        CheckConstraint(
            'length(scrape_target) >= 1 AND length(scrape_target) <= 1000', name='chk_system_settings_scrape_target_length'
            ),
        # 驗證is_active類型
        CheckConstraint(
            'is_active IN (0, 1)', 
            name='chk_system_settings_is_active_type'
            )
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
        default=lambda: True, 
        nullable=False
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
    last_crawl_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime
    )

    # 系統設定資料repr  
    def __repr__(self):
        return (
            f"<CrawlerSettings("
            f"id={self.id}, "
            f"crawler_name='{self.crawler_name}', "
            f"scrape_target='{self.scrape_target}', "
            f"is_active={self.is_active}"
            f")>"
        )
  
    def validate(self, is_update: bool = False) -> List[str]:
        """爬蟲設定驗證"""
        errors = []
        # 個性化驗證
        return errors

