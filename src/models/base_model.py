from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime, timezone
from sqlalchemy import Integer, DateTime, func
from typing import Optional, Set
from src.utils.datetime_utils import enforce_utc_datetime_transform
import logging

# 設定 logger
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    """基礎模型
    
    欄位說明：
    - id: 主鍵
    - created_at: 建立時間(UTC)
    - updated_at: 更新時間(UTC)
    """
    __abstract__ = True
    
    id: Mapped[int] = mapped_column(
        Integer, 
        primary_key=True, 
        autoincrement=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        server_default=func.timezone('UTC', func.now()),
        nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    # 用來儲存需要監聽的 datetime 欄位
    _datetime_fields_to_watch: Set[str] = set()

    def __init__(self, datetime_fields_to_watch=None, **kwargs):
        if 'created_at' not in kwargs:
            kwargs['created_at'] = datetime.now(timezone.utc)
            
        # 如果子類指定了需要監聽的欄位，記錄下來
        if datetime_fields_to_watch:
            self._datetime_fields_to_watch = self._datetime_fields_to_watch.union(datetime_fields_to_watch.copy())
        
        # 在初始化時處理 datetime 欄位的 UTC 轉換，並設定所有屬性
        for key, value in kwargs.items():
            if key in self._datetime_fields_to_watch and isinstance(value, datetime):
                value = enforce_utc_datetime_transform(value)
            setattr(self, key, value)
            
    def __setattr__(self, key, value):
        """覆寫 __setattr__ 方法，在設置屬性時進行時區轉換"""
        if key in getattr(self, '_datetime_fields_to_watch', set()) and isinstance(value, datetime):
            value = enforce_utc_datetime_transform(value)
            
        super().__setattr__(key, value)

    def __getattribute__(self, key):
        """覆寫 __getattribute__ 方法，在獲取屬性時為 datetime 欄位加上 UTC 時區"""
        # 使用 object.__getattribute__ 來避免遞迴調用
        value = object.__getattribute__(self, key)
        
        # 檢查是否是需要監聽的 datetime 欄位
        datetime_fields = object.__getattribute__(self, '_datetime_fields_to_watch')
        if key in datetime_fields and isinstance(value, datetime) and value.tzinfo is None:
            # 如果是 naive datetime，轉換為帶 UTC 時區的版本
            value = enforce_utc_datetime_transform(value)
            # 將轉換後的值寫回物件，避免下次存取時重複轉換
            object.__setattr__(self, key, value)
        
        return value

    def to_dict(self):
        return {
            'id': self.id,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


