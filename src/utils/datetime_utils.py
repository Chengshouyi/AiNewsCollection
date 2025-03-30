from datetime import datetime, timezone
import logging

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
     # Option 1: Assume naive is UTC (Safer if unsure)
    if value.tzinfo is None:  # Naive datetime
        utc_value = value.replace(tzinfo=timezone.utc)
    # Option 2: Assume naive is local and convert (More complex, needs local tz)
        # try:
        #     import tzlocal
        #     local_tz = tzlocal.get_localzone()
        #     aware_local_dt = local_tz.localize(dt)
        #     return aware_local_dt.astimezone(timezone.utc)
        # except ImportError:
        #     # Fallback if tzlocal is not installed - treat as UTC
        #     return dt.replace(tzinfo=timezone.utc)
    elif value.tzinfo == timezone.utc:
        return value # Already UTC
    else:  # Aware datetime
        utc_value = value.astimezone(timezone.utc)
    
    logger.debug(f"轉換時間為 UTC：{value} -> {utc_value}")
    return utc_value 