from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.models.base_model import Base
from .base_entity import BaseEntity

class Crawlers(Base, BaseEntity):
    """爬蟲設定模型for 管理及實例化特定爬蟲
    
    欄位說明：
    - crawler_name: 爬蟲名稱
    - base_url: 爬取目標
    - is_active: 是否啟用
    - crawler_type: 爬蟲類型
    - config_file_name: 爬蟲設定檔案名稱
    """
    __tablename__ = 'crawlers'

    crawler_name: Mapped[str] = mapped_column(
        String(100), 
        nullable=False
    )
    base_url: Mapped[str] = mapped_column(
        String(1000), 
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, 
        default=True, 
        nullable=False,
        server_default="1"
    )
    crawler_type: Mapped[str] = mapped_column(
        String(100), 
        nullable=False
    )
    config_file_name: Mapped[str] = mapped_column(
        String(100), 
        nullable=False
    )
    crawler_tasks = relationship("CrawlerTasks", back_populates="crawlers", lazy="joined")

    def __init__(self, **kwargs):
        # 設置默認值
        if 'is_active' not in kwargs:
            kwargs['is_active'] = True
            
        super().__init__(**kwargs)

    # 系統設定資料repr  
    def __repr__(self):
        return (
            f"<Crawlers("
            f"id={self.id}, "
            f"crawler_name='{self.crawler_name}', "
            f"base_url='{self.base_url}', "
            f"crawler_type='{self.crawler_type}', "
            f"config_file_name='{self.config_file_name}', "
            f"is_active={self.is_active}"
            f")>"
        )
    
    def to_dict(self):
        return {
            **super().to_dict(),
            'crawler_name': self.crawler_name,
            'base_url': self.base_url,
            'is_active': self.is_active,
            'crawler_type': self.crawler_type,
            'config_file_name': self.config_file_name
        }

    

