from typing import Optional, Any, Callable, Dict, List, Type
from datetime import datetime,  timezone
from src.error.errors import ValidationError
from croniter import croniter
from src.utils.transform_utils import str_to_enum
import re



def validate_int(field_name: str, required: bool = False):
    """整數驗證"""
    def validator(value: Any) -> Optional[int]:
        if value is None:
            if required:
                raise ValidationError(f"{field_name}: 不能為 None") 
            return None
        if not isinstance(value, int):
            raise ValidationError(f"{field_name}: 必須是整數")
        return value
    return validator


def validate_list(
    field_name: str, 
    type: Optional[Type[Any]] = None, 
    min_length: int = 1, 
    required: bool = False
):
    """列表驗證"""
    def validator(value: Any) -> Optional[List[Any]]:
        if value is None:
            if required:
                raise ValidationError(f"{field_name}: 不能為 None") 
            
        if not isinstance(value, list):
            raise ValidationError(f"{field_name}: 必須是列表")
        if type:
            if not all(isinstance(item, type) for item in value):
                raise ValidationError(f"{field_name}: 列表中的所有元素必須是 {type.__name__}")
        if len(value) < min_length:
            raise ValidationError(f"{field_name}: 列表長度不能小於 {min_length}")
        return value
    return validator

def validate_dict(field_name: str, required: bool = True):
    """驗證字典格式"""
    def validate_dict_validator(v):
        if not isinstance(v, dict):
            if required:
                raise ValidationError(f"{field_name}: 必須是字典格式")
            else:
                return {}
        return v
    return validate_dict_validator

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

def validate_positive_int(field_name: str, is_zero_allowed: bool = False, required: bool = False):
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
        
        #如果不允許0，則檢查是否大於0
        if not is_zero_allowed:
            if value <= 0:
                raise ValidationError(f"{field_name}: 必須是正整數且大於0")
        #如果允許0，則檢查是否大於等於0
        else:
            if value < 0:
                raise ValidationError(f"{field_name}: 必須是正整數且大於等於0")
        
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


def validate_task_args(field_name: str, required: bool = False):
    """
    任務參數驗證器
    
    Args:
        field_name: 欄位名稱
        required: 是否為必填
    
    Returns:
        驗證函數
    """
    def validator(task_args: Any, is_update: bool = False) -> Optional[Dict[str, Any]]:
        try:
            if task_args is None:
                if required:
                    raise ValidationError(f"{field_name}: 不能為 None")
                return None
                
            if not isinstance(task_args, dict):
                raise ValidationError(f"{field_name}: 必須是字典格式")

            # 必要欄位及其類型定義
            required_fields = {
                'scrape_mode': str, 
                'min_keywords': int,
                'max_retries': int,
                'retry_delay': (int, float),
                'timeout': (int, float),
                'is_test': bool,
                'save_to_csv': bool,
                'save_to_database': bool,
                'get_links_by_task_id': bool,
                'article_links': list,
                'save_partial_results_on_cancel': bool,
                'save_partial_to_database': bool
            }

            # 可選欄位及其類型定義
            optional_fields = {
                'ai_only': bool,
                'max_pages': int,
                'num_articles': int,
                'csv_file_prefix': str,
                'max_cancel_wait': int,
                'cancel_interrupt_interval': int,
                'cancel_timeout': int
            }

            # 驗證所有必填欄位 (在更新模式下欄位可以不存在)
            for field, expected_type in required_fields.items():
                if field in task_args:
                    if not isinstance(task_args[field], expected_type):
                        raise ValidationError(f"{field_name}.{field}: 類型不匹配。期望類型: {expected_type.__name__}")
                elif not is_update:  # 只有在非更新模式下檢查必填欄位
                    raise ValidationError(f"{field_name}.{field}: 必填欄位不能缺少")

            # 驗證所有可選欄位
            for field, expected_type in optional_fields.items():
                if field in task_args and not isinstance(task_args[field], expected_type):
                    raise ValidationError(f"{field_name}.{field}: 類型不匹配。期望類型: {expected_type.__name__}")

            # 驗證scrape_mode (如果存在)
            if 'scrape_mode' in task_args:
                try:
                    validate_scrape_mode('scrape_mode', required=True)(task_args['scrape_mode'])
                except Exception as e:
                    raise ValidationError(f"{field_name}.scrape_mode: {str(e)}")

            # 驗證取消相關參數
            cancel_params = ['max_cancel_wait', 'cancel_interrupt_interval', 'cancel_timeout']
            for param in cancel_params:
                if param in task_args:
                    try:
                        validate_positive_int(param, required=False)(task_args[param])
                    except Exception as e:
                        raise ValidationError(f"{field_name}.{param}: {str(e)}")

            # 驗證數值參數
            numeric_params = {
                'max_pages': False,
                'num_articles': False,
                'min_keywords': False,
                'timeout': False,
                'max_retries': True # 允許 max_retries 為 0
            }
            for param, is_zero_allowed in numeric_params.items():
                if param in task_args:
                    try:
                        # 傳遞 is_zero_allowed 給驗證器
                        validate_positive_int(param, is_zero_allowed=is_zero_allowed, required=True)(task_args[param])
                    except Exception as e:
                        raise ValidationError(f"{field_name}.{param}: {str(e)}")
            
            # 驗證可為小數的數值類型參數 
            float_params = ['retry_delay']
            for param in float_params:
                if param in task_args:
                    try:
                        validate_positive_float(param, is_zero_allowed=False, required=True)(task_args[param]) 
                    except Exception as e:
                        raise ValidationError(f"{field_name}.{param}: {str(e)}")

            # 驗證布爾類型參數
            bool_params = ['ai_only', 'save_to_csv', 'save_to_database', 'get_links_by_task_id', 'is_test', 'save_partial_results_on_cancel', 'save_partial_to_database']
            for param in bool_params:
                if param in task_args:
                    try:
                        validate_boolean(param, required=True)(task_args[param])
                    except Exception as e:
                        raise ValidationError(f"{field_name}.{param}: {str(e)}")
            
            # 驗證文章連結列表
            if 'article_links' in task_args:
                try:
                    validate_list("article_links", min_length=0, type=str)(task_args['article_links'])
                except Exception as e:
                    raise ValidationError(f"{field_name}.article_links: {str(e)}")
                    
            return task_args
        except Exception as e:
            raise ValidationError(f"{field_name}: {str(e)}")
    
    return validator

def validate_positive_float(field_name: str, is_zero_allowed: bool = False, required: bool = False):
    """正浮點數驗證"""
    def validator(value: Any) -> Optional[float]:
        if value is None:
            if required:
                raise ValidationError(f"{field_name}: 不能為空")
            return 0
        if not isinstance(value, (int, float)):
            raise ValidationError(f"{field_name}: 必須是數值")
        if not is_zero_allowed:
            if value <= 0:
                raise ValidationError(f"{field_name}: 必須是正數且大於0")
        else:
            if value < 0:
                raise ValidationError(f"{field_name}: 必須是正數且大於等於0")
        return value
    return validator

def validate_scrape_phase(field_name: str, required: bool = False):
    """任務階段驗證"""
    from src.utils.enum_utils import ScrapePhase
    def validator(value: Any) -> Optional[ScrapePhase]:
        if value is None:
            if required:
                raise ValidationError(f"{field_name}: 不能為空")
            return None
        if isinstance(value, ScrapePhase):
            return value
        else:
            return str_to_enum(value, ScrapePhase, field_name)
    return validator

def validate_scrape_mode(field_name: str, required: bool = False):
    """抓取模式驗證"""
    from src.utils.enum_utils import ScrapeMode
    def validator(value: Any) -> Optional[ScrapeMode]:
        if value is None:
            if required:
                raise ValidationError(f"{field_name}: 不能為空")
            return None
        if isinstance(value, ScrapeMode):
            return value
        else:
           return str_to_enum(value, ScrapeMode, field_name)
    return validator


def validate_article_scrape_status(field_name: str, required: bool = False):
    """文章爬取狀態驗證"""
    from src.utils.enum_utils import ArticleScrapeStatus
    def validator(value: Any) -> Optional[ArticleScrapeStatus]:
        if value is None:
            if required:
                raise ValidationError(f"{field_name}: 不能為空")
            return None 
        if isinstance(value, ArticleScrapeStatus):
            return value
        else:
            return str_to_enum(value, ArticleScrapeStatus, field_name)
    return validator


def validate_task_status(field_name: str, required: bool = False):
    """任務狀態驗證"""
    from src.utils.enum_utils import TaskStatus
    def validator(value: Any) -> Optional[TaskStatus]:
        if value is None:
            if required:
                raise ValidationError(f"{field_name}: 不能為空")
            return None
        if isinstance(value, TaskStatus):
            return value
        else:
            return str_to_enum(value, TaskStatus, field_name)
    return validator

