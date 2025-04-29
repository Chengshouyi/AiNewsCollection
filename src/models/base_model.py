"""
本模組定義 SQLAlchemy 的基礎模型 Base，統一處理主鍵、建立與更新時間（UTC），並自動轉換 datetime 欄位為 UTC aware。
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Set, Any

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, DateTime, func

from src.utils.datetime_utils import enforce_utc_datetime_transform
from src.utils.type_utils import AwareDateTime
from src.utils.log_utils import LoggerSetup  # 使用統一的 logger

logger = LoggerSetup.setup_logger(__name__)  # 使用統一的 logger


class Base(DeclarativeBase):
    """基礎模型

    欄位說明：
    - id: 主鍵
    - created_at: 建立時間(UTC)
    - updated_at: 更新時間(UTC)

    使用 AwareDateTime 類型處理與資料庫之間的 UTC 時間轉換。
    使用 __setattr__ 確保在 Python 物件層級賦值時，datetime 立即轉換為 UTC aware。
    """

    __abstract__ = True

    # 定義需要由 __setattr__ 特別處理的 AwareDateTime 欄位
    # 子類別如果添加了其他 AwareDateTime 欄位，應在其定義中擴展此集合
    # 例如: _aware_datetime_fields = Base._aware_datetime_fields.union({'my_custom_date'})
    _aware_datetime_fields: Set[str] = {"created_at", "updated_at"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        AwareDateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        AwareDateTime,
        default=lambda: datetime.now(timezone.utc),  # 新增時的預設值
        onupdate=lambda: datetime.now(timezone.utc),  # 更新時的時間戳
    )
    # 移除對特定欄位的監聽集合，因為 AwareDateTime 會處理所有 AwareDateTime 類型的欄位
    # _datetime_fields_to_watch: Set[str] = {'created_at', 'updated_at'} # 不再需要

    def __init__(self, **kwargs):
        # Apply defaults for fields managed by Base if not provided in kwargs
        if "created_at" not in kwargs:
            setattr(self, "created_at", datetime.now(timezone.utc))
        if "updated_at" not in kwargs:
            setattr(self, "updated_at", datetime.now(timezone.utc))

        for key, value in kwargs.items():
            setattr(self, key, value)  # Use setattr to trigger __setattr__

    def __setattr__(self, key: str, value: Any):
        """
        覆寫 __setattr__，在設置指定 datetime 欄位時強制轉換為 UTC aware。
        """
        if key in self._aware_datetime_fields and isinstance(value, datetime):
            value = enforce_utc_datetime_transform(value)
        # Call the original __setattr__ (from object)
        object.__setattr__(self, key, value)

    def to_dict(self):
        # Base implementation might only include base fields
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ... potentially other model definitions inheriting from Base ...
