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

def convert_str_to_utc_ISO_str(value: str, tz: str = 'Asia/Taipei') -> str:
    """將字串轉換為 UTC 時區的 datetime 值，並返回 ISO 格式字串
    
    Args:
        value (str): 要轉換的字串，支援格式：
            - 'YYYY-MM-DD'
            - 'YYYY.MM.DD'
            - 'YYYY-MM-DD HH:MM:SS'
            - 'YYYY.MM.DD HH:MM:SS'
        tz (str): 時區字串，預設為 'Asia/Taipei'

    Returns:
        str: ISO 格式的 UTC 時間字串
    """
    # 預處理：將點號轉換為橫線
    value = value.replace('.', '-')
    
    try:
        # 嘗試解析完整日期時間格式
        dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        try:
            # 如果失敗，嘗試解析只有日期的格式
            dt = datetime.strptime(value, '%Y-%m-%d')
        except ValueError as e:
            logger.error(f"日期格式解析錯誤: {value}")
            raise ValueError(f"不支援的日期格式: {value}，請使用 YYYY-MM-DD 或 YYYY.MM.DD 格式") from e
    
    # 設定時區
    timezone_obj = pytz.timezone(tz)
    localized_dt = timezone_obj.localize(dt)
    
    # 轉換為 UTC
    utc_dt = localized_dt.astimezone(pytz.UTC)
    
    # 轉換為 ISO 格式字串
    iso_str = utc_dt.isoformat()
    
    logger.debug(f"轉換時間為 UTC ISO 格式：{value} ({tz}) -> {iso_str}")
    return iso_str

def convert_str_to_utc_datetime(value: str, tz: str = 'Asia/Taipei') -> datetime:
    """將字串轉換為 UTC 時區的 datetime 值
    
    Args:
        value (str): 要轉換的字串，支援格式：   
            - 'YYYY-MM-DD'
            - 'YYYY.MM.DD'
            - 'YYYY-MM-DD HH:MM:SS'
            - 'YYYY.MM.DD HH:MM:SS'
        tz (str): 時區字串，預設為 'Asia/Taipei'    

    Returns:
        datetime: UTC 時區的 datetime 值
    """
    # 預處理：將點號轉換為橫線
    value = value.replace('.', '-') 
    
    try:
        # 嘗試解析完整日期時間格式
        dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        try:
            # 如果失敗，嘗試解析只有日期的格式
            dt = datetime.strptime(value, '%Y-%m-%d')
        except ValueError as e:
            logger.error(f"日期格式解析錯誤: {value}")
            raise ValueError(f"不支援的日期格式: {value}，請使用 YYYY-MM-DD 或 YYYY.MM.DD 格式") from e
    
    # 設定時區  
    timezone_obj = pytz.timezone(tz)
    localized_dt = timezone_obj.localize(dt)
    
    # 轉換為 UTC
    utc_dt = localized_dt.astimezone(pytz.UTC)  
    
    logger.debug(f"轉換時間為 UTC：{value} ({tz}) -> {utc_dt}")
    return utc_dt



