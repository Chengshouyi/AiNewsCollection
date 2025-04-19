from sqlalchemy.types import TypeDecorator, String
from datetime import datetime, timezone
from src.utils.datetime_utils import enforce_utc_datetime_transform
import logging
from typing import Optional, Any
# (保留您現有的 enforce_utc_datetime_transform 和其他函數)
logger = logging.getLogger(__name__)

class AwareDateTime(TypeDecorator):
    """
    一個 SQLAlchemy TypeDecorator，用於處理 SQLite 中的時區感知 UTC datetime。

    它將 datetime 物件強制轉換為 UTC，然後以 ISO 8601 格式（包含時區偏移）
    的字串形式儲存到 SQLite。
    從 SQLite 讀取時，它會解析 ISO 字串並返回一個時區感知的 UTC datetime 物件。
    """
    # 我們選擇 String 作為底層實現，因為 SQLite 沒有真正的 DateTime with timezone。
    # 這樣我們可以完全控制儲存的格式。
    impl = String
    cache_ok = True # 表示此類型可以在 SQLAlchemy 的快取中使用

    # 定義此裝飾器代表的 Python 類型
    python_type = datetime # type: ignore

    def process_bind_param(self, value: Optional[datetime], dialect) -> Optional[str]:
        """
        在將 Python datetime 值綁定到 SQL 語句參數之前進行處理。

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
        # 範例： "2023-10-27T10:30:00.123456+00:00"
        iso_string = aware_utc_dt.isoformat()
        logger.debug(f"[AwareDateTime] Binding: {value} -> {iso_string}")
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
            # 解析 ISO 8601 格式字串，datetime.fromisoformat 會處理時區
            dt = datetime.fromisoformat(value)
            logger.debug(f"[AwareDateTime] Loading: {value} -> {dt}")
            # 我們期望 dt 已經是 aware 的，但以防萬一，再次強制轉換為 UTC
            # （如果 fromisoformat 因某些原因返回 naive，這步會確保其為 aware UTC）
            return enforce_utc_datetime_transform(dt)
        except (ValueError, TypeError) as e:
            logger.error(f"[AwareDateTime] 無法從資料庫值 '{value}' 解析 datetime: {e}", exc_info=True)
            # 根據需要決定是返回 None 還是引發錯誤
            return None

    def compare_values(self, x: Any, y: Any) -> bool:
        """比較兩個 Python 值是否相等。"""
        # 確保比較時都是 aware UTC
        if isinstance(x, datetime) and isinstance(y, datetime):
            x_aware = enforce_utc_datetime_transform(x)
            y_aware = enforce_utc_datetime_transform(y)
            return x_aware == y_aware
        else:
            return x == y

