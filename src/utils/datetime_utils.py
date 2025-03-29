from datetime import datetime, timezone
import logging
import pytz

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



def enforce_utc_datetime_transform(value: datetime) -> datetime:
    """將 datetime 轉換為 UTC 時區
    
    Args:
        value (datetime): 要轉換的 datetime 值
        
    Returns:
        datetime: 轉換為 UTC 時區的 datetime 值
    """
    if value.tzinfo is None:  # Naive datetime
        utc_value = value.replace(tzinfo=timezone.utc)
    else:  # Aware datetime
        utc_value = value.astimezone(timezone.utc)
    
    logger.debug(f"轉換時間為 UTC：{value} -> {utc_value}")
    return utc_value 