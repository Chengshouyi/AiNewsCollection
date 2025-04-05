from typing import Optional, Any, Callable, Dict, Hashable
from datetime import datetime,  timezone
from src.error.errors import ValidationError
from croniter import croniter
import re

def is_str_dict(data: Dict[Hashable, Any]) -> bool:
    """檢查字典的所有鍵是否都是字符串類型"""
    return all(isinstance(k, str) for k in data.keys())

def convert_hashable_dict_to_str_dict(data: Dict[Hashable, Any]) -> Dict[str, Any]:
    """
    將 Dict[Hashable, Any] 轉換為 Dict[str, Any]
    
    Args:
        data: 包含 Hashable 鍵的字典
        
    Returns:
        Dict[str, Any]: 包含字符串鍵的字典
    """
    if not is_str_dict(data):
        raise ValueError("字典的所有鍵必須是字符串類型")
    
    return {str(k): v for k, v in data.items()}

def validate_str(
    field_name: str, 
    max_length: int = 255, 
    min_length: int = 0, 
    required: bool = False,
    regex: Optional[str] = None
):
    """
    字串驗證器
    
    Args:
        field_name: 欄位名稱
        max_length: 最大長度限制
        min_length: 最小長度限制
        required: 是否為必填
        regex: 可選的正則表達式驗證
    """
    import re

    def validator(value: Optional[str]) -> Optional[str]:
        # 處理 None 值
        if value is None:
            if required:
                raise ValidationError(f"{field_name}: 不能為 None")
            return None
        
        # 轉換並去除空白
        value = str(value).strip()
        
        # 檢查是否為空
        if not value:
            if required:
                raise ValidationError(f"{field_name}: 不能為空")
            return None
        
        # 長度驗證
        if len(value) > max_length:
            raise ValidationError(f"{field_name}: 長度不能超過 {max_length} 字元")
        
        if len(value) < min_length:
            raise ValidationError(f"{field_name}: 長度不能小於 {min_length} 字元")
        
        # 正則表達式驗證
        if regex:
            if not re.match(regex, value):
                raise ValidationError(f"{field_name}: 不符合指定的格式")
        
        return value
    
    return validator

def validate_cron_expression(
    field_name: str, 
    max_length: int = 255, 
    min_length: int = 0, 
    required: bool = False,
    regex: Optional[str] = None
) -> Callable[[Optional[str]], Optional[str]]:
    """
    Cron 表達式驗證器

    Args:
        field_name: 欄位名稱
        max_length: 最大長度限制
        min_length: 最小長度限制
        required: 是否為必填
        regex: 可選的正則表達式驗證 (預設為標準的 5 字段 cron 格式)

    Returns:
        驗證函數
    """
    
    def validator(value: Optional[str]) -> Optional[str]:
        # 允許 None 值，但不是必填
        if value is None:
            if required:
                raise ValidationError(f"{field_name}: 不能為 None")
            return None

        # 轉換為字串並去除空白
        value = str(value).strip()

        # 檢查是否為空
        if not value:
            if required:
                raise ValidationError(f"{field_name}: 不能為空")
            return None

        # 長度驗證
        if len(value) > max_length:
            raise ValidationError(f"{field_name}: 長度不能超過 {max_length} 字元")
        
        if len(value) < min_length:
            raise ValidationError(f"{field_name}: 長度不能小於 {min_length} 字元")

        # 檢查字段數量
        parts = value.split()
        if len(parts) != 5:
            raise ValidationError(f"{field_name}: Cron 表達式必須包含 5 個字段")
        
# 更靈活的 cron 格式正則表達式
        default_regex = r'^(\*|(\*\/\d+)|([0-5]?\d)(-([0-5]?\d))?(/\d+)?)(,(\*|(\*\/\d+)|([0-5]?\d)(-([0-5]?\d))?(/\d+)?))* ' + \
                       r'(\*|(\*\/\d+)|([01]?\d|2[0-3])(-([01]?\d|2[0-3]))?(/\d+)?)(,(\*|(\*\/\d+)|([01]?\d|2[0-3])(-([01]?\d|2[0-3]))?(/\d+)?))* ' + \
                       r'(\*|(\*\/\d+)|([0-2]?\d|3[01])(-([0-2]?\d|3[01]))?(/\d+)?)(,(\*|(\*\/\d+)|([0-2]?\d|3[01])(-([0-2]?\d|3[01]))?(/\d+)?))* ' + \
                       r'(\*|(\*\/\d+)|([1-9]|1[0-2])(-([1-9]|1[0-2]))?(/\d+)?)(,(\*|(\*\/\d+)|([1-9]|1[0-2])(-([1-9]|1[0-2]))?(/\d+)?))* ' + \
                       r'(\*|(\*\/\d+)|([0-7])(-([0-7]))?(/\d+)?)(,(\*|(\*\/\d+)|([0-7])(-([0-7]))?(/\d+)?))*$'

        # 如果提供了自定義 regex，則使用自定義 regex
        # 否則使用預設的 cron 格式 regex
        check_regex = regex or default_regex

        # 正則表達式驗證
        if not re.match(check_regex, value):
            raise ValidationError(f"{field_name}: 不符合標準 cron 格式")
        
        # 詳細驗證每個字段的範圍和格式
        field_ranges = [
            (0, 59),   # 分鐘
            (0, 23),   # 小時
            (1, 31),   # 日
            (1, 12),   # 月
            (0, 7)     # 星期 (0 和 7 都表示星期日)
        ]

        for i, (part, (min_val, max_val)) in enumerate(zip(parts, field_ranges)):
            # 驗證個別字段
            _validate_cron_field(field_name, i, part, min_val, max_val)

        # 使用 croniter 進行額外驗證
        try:
            croniter.expand(value)
        except (ValueError, TypeError) as e:
            raise ValidationError(f"{field_name}: Croniter 驗證失敗 - {str(e)}")

        return value

    def _validate_cron_field(field_name: str, field_index: int, part: str, min_val: int, max_val: int):
        """
        驗證個別 cron 字段
        """
        # 處理通配符和步進情況
        if part == '*':
            return  # 簡單的 * 是完全合法的，直接返回

        if part.startswith('*/'):
            try:
                step = int(part[2:])
                if step < 1:
                    raise ValidationError(f"{field_name}: 步進值必須大於0")
                    
                # 檢查步進值是否超出範圍
                if field_index == 0 and step > 59:  # 分鐘字段
                    raise ValidationError(f"{field_name}: 分鐘字段的步進值不能超過59")
                elif field_index == 1 and step > 23:  # 小時字段
                    raise ValidationError(f"{field_name}: 小時字段的步進值不能超過23")
                elif field_index == 2 and step > 31:  # 日字段
                    raise ValidationError(f"{field_name}: 日字段的步進值不能超過31")
                elif field_index == 3 and step > 12:  # 月字段
                    raise ValidationError(f"{field_name}: 月字段的步進值不能超過12")
                elif field_index == 4 and step > 7:  # 星期字段
                    raise ValidationError(f"{field_name}: 星期字段的步進值不能超過7")
                    
                return  # 步進通配符也是合法的，直接返回
            except ValueError:
                raise ValidationError(f"{field_name}: 無效的步進值")

        # 對於非通配符的情況，繼續後續驗證
        # 分割多個值
        sub_parts = part.split(',')
        for sub_part in sub_parts:
            # 處理範圍
            if '-' in sub_part:
                try:
                    start, end = map(int, sub_part.split('-'))
                    if not (min_val <= start <= max_val and min_val <= end <= max_val):
                        raise ValidationError(f"{field_name}: 欄位 {field_index + 1} 的範圍必須在 {min_val}-{max_val} 之間")
                    if start > end:
                        raise ValidationError(f"{field_name}: 欄位 {field_index + 1} 的起始值不能大於結束值")
                except ValueError:
                    raise ValidationError(f"{field_name}: 無效的範圍")
                continue

            # 處理單個值
            try:
                val = int(sub_part)
                if not (min_val <= val <= max_val):
                    raise ValidationError(f"{field_name}: 欄位 {field_index + 1} 的值必須在 {min_val}-{max_val} 之間")
            except ValueError:
                raise ValidationError(f"{field_name}: 無效的值")

    return validator

def validate_boolean(field_name: str, required: bool = False):
    """布林值驗證"""
    def validator(value: Any) -> Optional[bool]:
        if value is None:
            if required:
                raise ValidationError(f"{field_name}: 不能為 None")
            return None
        if value is not None and not isinstance(value, bool):
            try:
                # 嘗試轉換常見的布爾值字符串
                if isinstance(value, str):
                    value = value.lower()
                    if value in ('true', '1', 'yes'):
                        return True
                    if value in ('false', '0', 'no'):
                        return False
            except:
                pass
            raise ValidationError(f"{field_name}: 必須是布爾值")
        return value
    return validator

def validate_positive_int(field_name: str, required: bool = False):
    """正整數驗證"""
    def validator(value: Any) -> Optional[int]:
        if value is None:
            if required:
                raise ValidationError(f"{field_name}: 不能為空")
            return 0
        
        # 檢查浮點數
        if isinstance(value, float) and value != int(value):
            raise ValidationError(f"{field_name}: 必須是整數")
        
        # 字串轉換檢查
        if isinstance(value, str):
            try:
                # 檢查是否包含小數點
                if '.' in value:
                    raise ValidationError(f"{field_name}: 必須是整數")
                value = int(value)
            except ValueError:
                raise ValidationError(f"{field_name}: 必須是整數")
        
        # 其他類型轉換
        try:
            value = int(value)
        except (ValueError, TypeError):
            raise ValidationError(f"{field_name}: 必須是整數")
        
        if value <= 0:
            raise ValidationError(f"{field_name}: 必須大於0")
        
        return value
    return validator


def validate_datetime(field_name: str, required: bool = False):
    """日期時間驗證
    
    Args:
        field_name: 欄位名稱
        required: 是否為必填
        
    Returns:
        驗證函數
    """
    def is_utc_timezone(dt: datetime) -> bool:
        """檢查日期時間是否為 UTC 時區"""
        if dt.tzinfo is None:
            return False
        return dt.tzinfo == timezone.utc
    
    def validator(value: Any) -> Optional[datetime]:
        # 處理 None 值
        if value is None:
            if required:
                raise ValidationError(f"{field_name}: 不能為 None")
            return None
        
        # 處理空字串
        if isinstance(value, str) and not value.strip():
            raise ValidationError(f"{field_name}: 不能為空")

        
        # 處理字串輸入
        if isinstance(value, str):
            try:
                # 嘗試解析 ISO 格式
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                raise ValidationError(f"{field_name}: 無效的日期時間格式。請使用 ISO 格式（例如：2025-03-30T08:00:00Z）。")
        # 處理 datetime 物件
        elif isinstance(value, datetime):
            dt = value
        else:
            raise ValidationError(f"{field_name}: 必須是字串或日期時間物件。")
        
        # 檢查時區
        if not is_utc_timezone(dt):
            if dt.tzinfo is None:
                raise ValidationError(f"{field_name}: 日期時間必須包含時區資訊。")
            raise ValidationError(f"{field_name}: 日期時間必須是 UTC 時區。")
        
        return dt
    
    return validator

def validate_url(
    field_name: str, 
    max_length: int = 1000, 
    required: bool = False,
    regex: Optional[str] = None
):
    """
    URL驗證器
    
    Args:
        field_name: 欄位名稱
        max_length: 最大長度限制
        required: 是否為必填
        regex: 可選的正則表達式驗證
    """

    def validator(value: Optional[str]) -> Optional[str]:
        if not value:
            if required:
                raise ValidationError(f"{field_name}: URL不能為空")
            return None
        
        # 先檢查長度
        if len(value) > max_length:
            raise ValidationError(f"{field_name}: 長度不能超過 {max_length} 字元")
        
        # 檢查 URL 格式
        if regex:
            if not re.match(regex, value):
                raise ValidationError(f"{field_name}: 無效的URL格式")    
        else:
            url_pattern = re.compile(
                r'^https?://'
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
                r'localhost|'
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
                r'(?::\d+)?'
                r'(?:/?|[/?]\S+)?$', re.IGNORECASE)
        
            if not url_pattern.match(value):
                raise ValidationError(f"{field_name}: 無效的URL格式")
        
        return value
    
    return validator

