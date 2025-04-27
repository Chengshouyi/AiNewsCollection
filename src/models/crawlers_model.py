"""Crawlers model module for managing crawler configurations.

This module defines the Crawlers model which handles crawler configurations and instances,
including crawler settings, relationships, and data serialization.
"""

# Third party imports
from sqlalchemy import String, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Local application imports
from src.models.base_model import Base
from src.models.base_entity import BaseEntity
from src.utils.log_utils import LoggerSetup

logger = LoggerSetup.setup_logger(__name__)


class Crawlers(Base, BaseEntity):
    """爬蟲設定模型for 管理及實例化特定爬蟲

    欄位說明：
    - crawler_name: 爬蟲名稱：爬蟲的class名稱，用來實例化爬蟲，例如：BnextCrawler
    - base_url: 爬取目標：爬蟲的爬取目標，例如：https://www.bnext.com.tw
    - is_active: 是否啟用：爬蟲是否啟用，例如：True
    - crawler_type: 爬蟲類型：爬蟲的類型，例如：bnext
    - config_file_name: 爬蟲設定檔案名稱：爬蟲的設定檔案名稱，例如：bnext_config.json
    """

    __tablename__ = "crawlers"
    __table_args__ = (
        # 保留資料庫層面的唯一性約束
        UniqueConstraint("crawler_name", name="uq_crawler_name"),
    )
    crawler_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    module_name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default="1"
    )
    crawler_type: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="web"
    )
    config_file_name: Mapped[str] = mapped_column(String(100), nullable=False)

    crawler_tasks = relationship(
        "CrawlerTasks", back_populates="crawler", lazy="joined"
    )

    # *** 關鍵：擴展需要 Base__setattr__ 處理的 AwareDateTime 欄位 ***
    _aware_datetime_fields = Base._aware_datetime_fields.union()

    # 定義需要監聽的 datetime 欄位

    def __init__(self, **kwargs):
        # 設置默認值
        if "is_active" not in kwargs:
            kwargs["is_active"] = True

        super().__init__(**kwargs)

    # 系統設定資料repr
    def __repr__(self):
        return (
            f"<Crawlers("
            f"id={self.id}, "
            f"crawler_name='{self.crawler_name}', "
            f"module_name='{self.module_name}', "
            f"base_url='{self.base_url}', "
            f"crawler_type='{self.crawler_type}', "
            f"config_file_name='{self.config_file_name}', "
            f"is_active={self.is_active}"
            f")>"
        )

    def to_dict(self):
        return {
            **super().to_dict(),
            "crawler_name": self.crawler_name,
            "module_name": self.module_name,
            "base_url": self.base_url,
            "is_active": self.is_active,
            "crawler_type": self.crawler_type,
            "config_file_name": self.config_file_name,
        }
