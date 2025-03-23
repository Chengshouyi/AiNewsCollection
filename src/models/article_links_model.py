from sqlalchemy import UniqueConstraint, CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base_model import Base
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import relationship
from sqlalchemy import Integer, String, Boolean, DateTime
from src.models.base_entity import BaseEntity
from src.error.errors import ValidationError

class ArticleLinks(Base, BaseEntity):
    """文章連結模型
    
    欄位說明：
    - id: 主鍵
    - source_name: 來源名稱
    - source_url: 來源URL
    - article_link: 文章連結
    - is_scraped: 是否已爬取
    - created_at: 建立時間
    """
    def __init__(self, **kwargs):
        # 設置預設的 created_at
        if 'created_at' not in kwargs:
            kwargs['created_at'] = datetime.now(timezone.utc)
        if 'is_scraped' not in kwargs:
            kwargs['is_scraped'] = False
            
        super().__init__(**kwargs)
        self.is_initialized = True

    __tablename__ = 'article_links'
    __table_args__ = (
        # 保留資料庫層面的唯一性約束
        UniqueConstraint(
            'article_link', 
            name='uq_article_link'
            ),
        # 驗證source_name長度
        CheckConstraint(
            'length(source_name) >= 1 AND length(source_name) <= 50', 
            name='chk_article_link_source_name_length'
            ),
        # 驗證source_url長度
        CheckConstraint(
            'length(source_url) >= 1 AND length(source_url) <= 1000', 
            name='chk_article_link_source_url_length'
            ),
        # 驗證article_link長度
        CheckConstraint(
            'length(article_link) >= 1 AND length(article_link) <= 1000', name='chk_article_link_article_link_length'
            ),
        # 驗證is_scraped類型
        CheckConstraint(
            'is_scraped IN (0, 1)', 
            name='chk_article_link_is_scraped_type'
            )
    )
    def __setattr__(self, key, value):
        if not hasattr(self, 'is_initialized'):
            super().__setattr__(key, value)
            return

        if key in ['id', 'article_link', 'created_at'] and hasattr(self, key):
            raise ValidationError(f"{key} cannot be updated")

        super().__setattr__(key, value)


    id: Mapped[int] = mapped_column(
        Integer, 
        primary_key=True, 
        autoincrement=True
        )
    source_name: Mapped[str] = mapped_column(
        String(50), 
        nullable=False
        )
    source_url: Mapped[str] = mapped_column(
        String(1000), 
        unique=True, 
        nullable=False
        )
    article_link: Mapped[str] = mapped_column(
        String(1000), 
        ForeignKey("articles.link"),
        unique=True, 
        nullable=False, 
        index=True
    )
    is_scraped: Mapped[bool] = mapped_column(
        Boolean, 
        default=lambda: False, 
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    # 使用字串參考而不是直接引用類別
    article = relationship("Articles", back_populates="article_links")
    
    # 文章連結資料repr
    def __repr__(self):
        return f"<ArticleLink(id={self.id}, source_name='{self.source_name}', source_url='{self.source_url}', article_link='{self.article_link}', is_scraped={self.is_scraped})>"
    
    def validate(self, is_update: bool = False) -> List[str]:
        """文章連結驗證"""
        errors = []
        # 個性化驗證
        return errors