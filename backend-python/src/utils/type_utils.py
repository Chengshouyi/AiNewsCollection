"""定義 SQLAlchemy 自訂類型，例如用於處理時區感知的 DateTime。"""

# 標準函式庫導入
from datetime import datetime, timezone
import logging # 移除非統一的 logger
from typing import Optional, Any

# 第三方函式庫導入
from sqlalchemy.types import TypeDecorator, String

# 本地應用程式導入
from src.utils.datetime_utils import enforce_utc_datetime_transform


# 設定統一的 logger
logger = logging.getLogger(__name__)  # 使用統一的 logger


class AwareDateTime(TypeDecorator):
    """
    一個 SQLAlchemy TypeDecorator，用於處理 SQLite 中的時區感知 UTC datetime。

    它將 datetime 物件強制轉換為 UTC，然後以 ISO 8601 格式（包含時區偏移）
    的字串形式儲存到 SQLite。
    從 SQLite 讀取時，它會解析 ISO 字串並返回一個時區感知的 UTC datetime 物件。
    """
    # 使用 String 作為底層實現，因 SQLite 無原生 DateTime with timezone
    impl = String
    cache_ok = True # 表示此類型可在 SQLAlchemy 快取中使用

    # 定義此裝飾器代表的 Python 類型
    python_type = datetime

    def process_bind_param(self, value: Optional[datetime], dialect) -> Optional[str]:
        """
        在將 Python datetime 值綁定到 SQL 語句參數前處理。

        Args:
            value: 要處理的 Python datetime 值。
            dialect: 當前的 SQLAlchemy 方言。

        Returns:
            ISO 8601 格式的 UTC 時間字串，或 None。
        """
        if value is None:
            return None

        if not isinstance(value, datetime):
           raise TypeError("AwareDateTime 只能處理 datetime 物件")

        # 確保值是 UTC aware datetime
        aware_utc_dt = enforce_utc_datetime_transform(value)

        # 轉換為包含時區偏移的 ISO 8601 格式字串
        iso_string = aware_utc_dt.isoformat()
        # 使用 logger.debug 記錄綁定過程，避免 f-string
        # logger.debug("[AwareDateTime] Binding: %s -> %s", value, iso_string)
        return iso_string

    def process_result_value(self, value: Optional[str], dialect) -> Optional[datetime]:
        """
        在從資料庫讀取結果後處理值。

        Args:
            value: 從資料庫讀取的字串值。
            dialect: 當前的 SQLAlchemy 方言。

        Returns:
            時區感知的 UTC datetime 物件，或 None。
        """
        if value is None:
            return None
        try:
            # 解析 ISO 8601 格式字串
            dt = datetime.fromisoformat(value)
            # 使用 logger.debug 記錄載入過程，避免 f-string
            # logger.debug("[AwareDateTime] Loading: %s -> %s", value, dt)
            # 再次強制轉換為 UTC 以確保一致性
            return enforce_utc_datetime_transform(dt)
        except (ValueError, TypeError) as e:
            # 使用 logger.error 記錄錯誤，避免 f-string
            logger.error("[AwareDateTime] 無法從資料庫值 '%s' 解析 datetime: %s", value, e, exc_info=True)
            # 根據需要決定是返回 None 還是引發錯誤
            return None

    def compare_values(self, x: Any, y: Any) -> bool:
        """比較兩個 Python 值是否相等，在比較 datetime 時確保轉換為 UTC。"""
        # 確保比較時都是 aware UTC
        if isinstance(x, datetime) and isinstance(y, datetime):
            x_aware = enforce_utc_datetime_transform(x)
            y_aware = enforce_utc_datetime_transform(y)
            return x_aware == y_aware
        # 對於非 datetime 類型，使用標準比較
        return x == y

