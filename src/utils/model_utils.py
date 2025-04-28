"""此模組提供用於驗證各種數據模型的實用函數。"""

from typing import Optional, Any, Callable, Dict, List, Type
from datetime import datetime,  timezone
from src.error.errors import ValidationError
from croniter import croniter
from src.utils.transform_utils import str_to_enum
import re

from src.utils.log_utils import LoggerSetup  # 使用統一的 logger

logger = LoggerSetup.setup_logger(__name__)  # 使用統一的 logger


def validate_int(field_name: str, required: bool = False):
    """整數驗證"""
    def validator(value: Any) -> Optional[int]:
        if value is None:
            if required:
                msg = f"{field_name}: 不能為 None"
                logger.error(msg)
                raise ValidationError(msg)
            return None
        if not isinstance(value, int):
            msg = f"{field_name}: 必須是整數"
            logger.error(msg)
            raise ValidationError(msg)
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
                msg = f"{field_name}: 不能為 None"
                logger.error(msg)
                raise ValidationError(msg)
            
        if not isinstance(value, list):
            msg = f"{field_name}: 必須是列表"
            logger.error(msg)
            raise ValidationError(msg)
        if type:
            if not all(isinstance(item, type) for item in value):
                msg = f"{field_name}: 列表中的所有元素必須是 {type.__name__}"
                logger.error(msg)
                raise ValidationError(msg)
        if len(value) < min_length:
            msg = f"{field_name}: 列表長度不能小於 {min_length}"
            logger.error(msg)
            raise ValidationError(msg)
        return value
    return validator

def validate_dict(field_name: str, required: bool = True):
    """驗證字典格式"""
    def validate_dict_validator(v):
        if not isinstance(v, dict):
            if required:
                msg = f"{field_name}: 必須是字典格式"
                logger.error(msg)
                raise ValidationError(msg)
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
    def validator(value: Optional[str]) -> Optional[str]:
        if value is None:
            if required:
                msg = f"{field_name}: 不能為 None"
                logger.error(msg)
                raise ValidationError(msg)
            return None
        
        value = str(value).strip()
        
        if not value:
            if required:
                msg = f"{field_name}: 不能為空"
                logger.error(msg)
                raise ValidationError(msg)
            return None
        
        if len(value) > max_length:
            msg = f"{field_name}: 長度不能超過 {max_length} 字元"
            logger.error(msg)
            raise ValidationError(msg)
        
        if len(value) < min_length:
            msg = f"{field_name}: 長度不能小於 {min_length} 字元"
            logger.error(msg)
            raise ValidationError(msg)
        
        if regex:
            if not re.match(regex, value):
                msg = f"{field_name}: 不符合指定的格式"
                logger.error(msg)
                raise ValidationError(msg)
        
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
        if value is None:
            if required:
                msg = f"{field_name}: 不能為 None"
                logger.error(msg)
                raise ValidationError(msg)
            return None

        value = str(value).strip()

        if not value:
            if required:
                msg = f"{field_name}: 不能為空"
                logger.error(msg)
                raise ValidationError(msg)
            return None

        if len(value) > max_length:
            msg = f"{field_name}: 長度不能超過 {max_length} 字元"
            logger.error(msg)
            raise ValidationError(msg)
        
        if len(value) < min_length:
            msg = f"{field_name}: 長度不能小於 {min_length} 字元"
            logger.error(msg)
            raise ValidationError(msg)

        parts = value.split()
        if len(parts) != 5:
            msg = f"{field_name}: Cron 表達式必須包含 5 個字段"
            logger.error(msg)
            raise ValidationError(msg)
        
        default_regex = r'^(\*|(\*\/\d+)|([0-5]?\d)(-([0-5]?\d))?(/\d+)?)(,(\*|(\*\/\d+)|([0-5]?\d)(-([0-5]?\d))?(/\d+)?))* ' + \
                       r'(\*|(\*\/\d+)|([01]?\d|2[0-3])(-([01]?\d|2[0-3]))?(/\d+)?)(,(\*|(\*\/\d+)|([01]?\d|2[0-3])(-([01]?\d|2[0-3]))?(/\d+)?))* ' + \
                       r'(\*|(\*\/\d+)|([0-2]?\d|3[01])(-([0-2]?\d|3[01]))?(/\d+)?)(,(\*|(\*\/\d+)|([0-2]?\d|3[01])(-([0-2]?\d|3[01]))?(/\d+)?))* ' + \
                       r'(\*|(\*\/\d+)|([1-9]|1[0-2])(-([1-9]|1[0-2]))?(/\d+)?)(,(\*|(\*\/\d+)|([1-9]|1[0-2])(-([1-9]|1[0-2]))?(/\d+)?))* ' + \
                       r'(\*|(\*\/\d+)|([0-7])(-([0-7]))?(/\d+)?)(,(\*|(\*\/\d+)|([0-7])(-([0-7]))?(/\d+)?))*$'

        check_regex = regex or default_regex

        if not re.match(check_regex, value):
            msg = f"{field_name}: 不符合標準 cron 格式"
            logger.error(msg)
            raise ValidationError(msg)
        
        field_ranges = [
            (0, 59),   # 分鐘
            (0, 23),   # 小時
            (1, 31),   # 日
            (1, 12),   # 月
            (0, 7)     # 星期 (0 和 7 都表示星期日)
        ]

        for i, (part, (min_val, max_val)) in enumerate(zip(parts, field_ranges)):
            _validate_cron_field(field_name, i, part, min_val, max_val)

        try:
            croniter.expand(value)
        except (ValueError, TypeError) as e:
            msg = f"{field_name}: Croniter 驗證失敗 - {str(e)}"
            logger.error(msg)
            raise ValidationError(msg)

        return value

    def _validate_cron_field(field_name: str, field_index: int, part: str, min_val: int, max_val: int):
        """
        驗證個別 cron 字段
        """
        if part == '*':
            return

        if part.startswith('*/'):
            try:
                step = int(part[2:])
                if step < 1:
                    msg = f"{field_name}: 步進值必須大於0"
                    logger.error(msg)
                    raise ValidationError(msg)
                    
                if field_index == 0 and step > 59:
                    msg = f"{field_name}: 分鐘字段的步進值不能超過59"
                    logger.error(msg)
                    raise ValidationError(msg)
                elif field_index == 1 and step > 23:
                    msg = f"{field_name}: 小時字段的步進值不能超過23"
                    logger.error(msg)
                    raise ValidationError(msg)
                elif field_index == 2 and step > 31:
                    msg = f"{field_name}: 日字段的步進值不能超過31"
                    logger.error(msg)
                    raise ValidationError(msg)
                elif field_index == 3 and step > 12:
                    msg = f"{field_name}: 月字段的步進值不能超過12"
                    logger.error(msg)
                    raise ValidationError(msg)
                elif field_index == 4 and step > 7:
                    msg = f"{field_name}: 星期字段的步進值不能超過7"
                    logger.error(msg)
                    raise ValidationError(msg)
                    
                return
            except ValueError:
                msg = f"{field_name}: 無效的步進值"
                logger.error(msg)
                raise ValidationError(msg)

        sub_parts = part.split(',')
        for sub_part in sub_parts:
            if '-' in sub_part:
                try:
                    start, end = map(int, sub_part.split('-'))
                    if not (min_val <= start <= max_val and min_val <= end <= max_val):
                        msg = f"{field_name}: 欄位 {field_index + 1} 的範圍必須在 {min_val}-{max_val} 之間"
                        logger.error(msg)
                        raise ValidationError(msg)
                    if start > end:
                        msg = f"{field_name}: 欄位 {field_index + 1} 的起始值不能大於結束值"
                        logger.error(msg)
                        raise ValidationError(msg)
                except ValueError:
                    msg = f"{field_name}: 無效的範圍"
                    logger.error(msg)
                    raise ValidationError(msg)
                continue

            try:
                val = int(sub_part)
                if not (min_val <= val <= max_val):
                    msg = f"{field_name}: 欄位 {field_index + 1} 的值必須在 {min_val}-{max_val} 之間"
                    logger.error(msg)
                    raise ValidationError(msg)
            except ValueError:
                msg = f"{field_name}: 無效的值"
                logger.error(msg)
                raise ValidationError(msg)

    return validator

def validate_boolean(field_name: str, required: bool = False):
    """布林值驗證"""
    def validator(value: Any) -> Optional[bool]:
        if value is None:
            if required:
                msg = f"{field_name}: 不能為 None"
                logger.error(msg)
                raise ValidationError(msg)
            return None
        if value is not None and not isinstance(value, bool):
            try:
                if isinstance(value, str):
                    value = value.lower()
                    if value in ('true', '1', 'yes'):
                        return True
                    if value in ('false', '0', 'no'):
                        return False
            except:
                pass
            msg = f"{field_name}: 必須是布爾值"
            logger.error(msg)
            raise ValidationError(msg)
        return value
    return validator

def validate_positive_int(field_name: str, is_zero_allowed: bool = False, required: bool = False):
    """正整數驗證"""
    def validator(value: Any) -> Optional[int]:
        if value is None:
            if required:
                msg = f"{field_name}: 不能為空"
                logger.error(msg)
                raise ValidationError(msg)
            return 0
        
        original_value = value # 保留原始值用於錯誤消息

        try:
            if isinstance(value, float) and value != int(value):
                msg = f"{field_name}: 必須是整數，但收到浮點數 {original_value}"
                logger.error(msg)
                raise ValidationError(msg)
            
            if isinstance(value, str):
                if '.' in value:
                    msg = f"{field_name}: 必須是整數，但收到包含小數點的字串 '{original_value}'"
                    logger.error(msg)
                    raise ValidationError(msg)
                value = int(value)
            else:
                value = int(value)
        except (ValueError, TypeError):
            msg = f"{field_name}: 必須是整數，但收到類型 {type(original_value).__name__}，值為 {original_value}"
            logger.error(msg)
            raise ValidationError(msg)
        
        if not is_zero_allowed:
            if value <= 0:
                msg = f"{field_name}: 必須是正整數且大於0，但收到 {value}"
                logger.error(msg)
                raise ValidationError(msg)
        else:
            if value < 0:
                msg = f"{field_name}: 必須是正整數且大於等於0，但收到 {value}"
                logger.error(msg)
                raise ValidationError(msg)
        
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
        if value is None:
            if required:
                msg = f"{field_name}: 不能為 None"
                logger.error(msg)
                raise ValidationError(msg)
            return None
        
        if isinstance(value, str) and not value.strip():
            msg = f"{field_name}: 不能為空"
            logger.error(msg)
            raise ValidationError(msg)

        
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                msg = f"{field_name}: 無效的日期時間格式。請使用 ISO 格式（例如：2025-03-30T08:00:00Z）。"
                logger.error(msg)
                raise ValidationError(msg)
        elif isinstance(value, datetime):
            dt = value
        else:
            msg = f"{field_name}: 必須是字串或日期時間物件。"
            logger.error(msg)
            raise ValidationError(msg)
        
        if not is_utc_timezone(dt):
            if dt.tzinfo is None:
                msg = f"{field_name}: 日期時間必須包含時區資訊。"
                logger.error(msg)
                raise ValidationError(msg)
            else:
                msg = f"{field_name}: 日期時間必須是 UTC 時區。"
                logger.error(msg)
                raise ValidationError(msg)
        
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
                msg = f"{field_name}: URL不能為空"
                logger.error(msg)
                raise ValidationError(msg)
            return None
        
        if len(value) > max_length:
            msg = f"{field_name}: 長度不能超過 {max_length} 字元"
            logger.error(msg)
            raise ValidationError(msg)
        
        if regex:
            if not re.match(regex, value):
                msg = f"{field_name}: URL 不符合提供的正則表達式"
                logger.error(msg)
                raise ValidationError(msg)
        else:
            # 基礎的 URL 驗證正則表達式 (允許 http 和 https)
            url_pattern = re.compile(
                r'^https?://' # 協議
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|' # 域名
                r'localhost|' # localhost
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # IP 地址
                r'(?::\d+)?' # 可選端口
                r'(?:/?|[/?]\S*)?$', re.IGNORECASE) # 可選路徑和查詢參數
        
            if not url_pattern.match(value):
                msg = f"{field_name}: 無效的 URL 格式: '{value}'"
                logger.error(msg)
                raise ValidationError(msg)
        
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
                    msg = f"{field_name}: 不能為 None"
                    logger.error(msg)
                    raise ValidationError(msg)
                return None
                
            if not isinstance(task_args, dict):
                msg = f"{field_name}: 必須是字典格式，但收到 {type(task_args).__name__}"
                logger.error(msg)
                raise ValidationError(msg)

            required_fields = {
                'scrape_mode': str, 
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

            optional_fields = {
                'ai_only': bool,
                'is_limit_num_articles': bool,
                'max_pages': int,
                'min_keywords': int,
                'num_articles': int,
                'csv_file_prefix': str,
                'max_cancel_wait': int,
                'cancel_interrupt_interval': int,
                'cancel_timeout': int
            }

            validated_args = {}
            all_known_fields = set(required_fields.keys()) | set(optional_fields.keys())

            for field, expected_type in required_fields.items():
                if field in task_args:
                    value = task_args[field]
                    if not isinstance(value, expected_type):
                        msg = f"{field_name}.{field}: 類型不匹配。期望類型: {expected_type.__name__}"
                        logger.error(msg)
                        raise ValidationError(msg)
                    validated_args[field] = value
                elif not is_update:
                    msg = f"{field_name}.{field}: 必填欄位不能缺少"
                    logger.error(msg)
                    raise ValidationError(msg)

            for field, expected_type in optional_fields.items():
                if field in task_args:
                    value = task_args[field]
                    if not isinstance(value, expected_type):
                        msg = f"{field_name}.{field}: 類型不匹配。期望類型: {expected_type.__name__}"
                        logger.error(msg)
                        raise ValidationError(msg)
                    validated_args[field] = value

            if 'scrape_mode' in validated_args:
                try:
                    validated_scrape_mode = validate_scrape_mode('scrape_mode', required=True)(validated_args['scrape_mode'])
                    validated_args['scrape_mode'] = validated_scrape_mode
                except Exception as e:
                    msg = f"{field_name}.scrape_mode: {str(e)}"
                    logger.error(msg)
                    raise ValidationError(msg)

            cancel_params = ['max_cancel_wait', 'cancel_interrupt_interval', 'cancel_timeout']
            for param in cancel_params:
                if param in validated_args:
                    try:
                        validated_value = validate_positive_int(param, required=False)(validated_args[param])
                        validated_args[param] = validated_value
                    except Exception as e:
                        msg = f"{field_name}.{param}: {str(e)}"
                        logger.error(msg)
                        raise ValidationError(msg)

            numeric_params = {
                'max_pages': False,
                'num_articles': False,
                'min_keywords': False,
                'timeout': False,
                'max_retries': True
            }
            for param, is_zero_allowed in numeric_params.items():
                if param in validated_args:
                    try:
                        validated_value = validate_positive_int(param, is_zero_allowed=is_zero_allowed, required=True)(validated_args[param])
                        validated_args[param] = validated_value
                    except Exception as e:
                        msg = f"{field_name}.{param}: {str(e)}"
                        logger.error(msg)
                        raise ValidationError(msg)
            
            float_params = ['retry_delay']
            for param in float_params:
                if param in validated_args:
                    try:
                        validated_value = validate_positive_float(param, is_zero_allowed=False, required=True)(validated_args[param])
                        validated_args[param] = validated_value
                    except Exception as e:
                        msg = f"{field_name}.{param}: {str(e)}"
                        logger.error(msg)
                        raise ValidationError(msg)

            bool_params = ['ai_only', 'is_limit_num_articles', 'save_to_csv', 'save_to_database', 'get_links_by_task_id', 'is_test', 'save_partial_results_on_cancel', 'save_partial_to_database']
            for param in bool_params:
                if param in validated_args:
                    try:
                        validated_value = validate_boolean(param, required=True)(validated_args[param])
                        validated_args[param] = validated_value
                    except Exception as e:
                        msg = f"{field_name}.{param}: {str(e)}"
                        logger.error(msg)
                        raise ValidationError(msg)
            
            if 'article_links' in validated_args:
                links_field_name = f"{field_name}.article_links"
                original_links = validated_args['article_links']
                try:
                    validated_links_list = validate_list(links_field_name, min_length=0, required=True)(original_links)
                except ValidationError as e:
                    raise e

                if validated_links_list is not None:
                    item_field_name = f"{links_field_name} item"
                    url_validator = validate_url(item_field_name, required=True)
                    validated_link_results = []
                    for i, link in enumerate(validated_links_list):
                        if not isinstance(link, str):
                            msg = f"{item_field_name} #{i}: 必須是字串，但收到 {type(link).__name__}"
                            logger.error(msg)
                            raise ValidationError(msg)
                        try:
                            validated_url = url_validator(link)
                            if validated_url is not None:
                                validated_link_results.append(validated_url)
                        except ValidationError as e:
                            msg = f"{item_field_name} #{i}: {str(e)}"
                            logger.error(msg)
                            raise ValidationError(msg) from e
                    validated_args['article_links'] = validated_link_results

            return validated_args
        except Exception as e:
            if isinstance(e, ValidationError):
                raise e
            raise ValidationError(f"Unexpected error during validation of {field_name}: {str(e)}")

    return validator

def validate_positive_float(field_name: str, is_zero_allowed: bool = False, required: bool = False):
    """正浮點數驗證"""
    def validator(value: Any) -> Optional[float]:
        if value is None:
            if required:
                msg = f"{field_name}: 不能為空"
                logger.error(msg)
                raise ValidationError(msg)
            return 0.0
        if not isinstance(value, (int, float)):
            msg = f"{field_name}: 必須是數值"
            logger.error(msg)
            raise ValidationError(msg)
        if not is_zero_allowed:
            if value <= 0:
                msg = f"{field_name}: 必須是正數且大於0"
                logger.error(msg)
                raise ValidationError(msg)
        else:
            if value < 0:
                msg = f"{field_name}: 必須是正數且大於等於0"
                logger.error(msg)
                raise ValidationError(msg)
        return value
    return validator

def validate_scrape_phase(field_name: str, required: bool = False):
    """任務階段驗證"""
    from src.utils.enum_utils import ScrapePhase
    def validator(value: Any) -> Optional[ScrapePhase]:
        if value is None:
            if required:
                msg = f"{field_name}: 不能為空"
                logger.error(msg)
                raise ValidationError(msg)
            return None
        if isinstance(value, ScrapePhase):
            return value
        else:
            try:
                # 嘗試從字串或其他值轉換為枚舉
                return str_to_enum(value, ScrapePhase, field_name)
            except ValidationError as e:
                logger.error(str(e)) # 記錄轉換錯誤
                raise e # 重新拋出原始異常
            except Exception as e:
                 # 捕獲其他轉換錯誤
                msg = f"{field_name}: 無法將值 '{value}' (類型 {type(value).__name__}) 轉換為 ScrapePhase: {str(e)}"
                logger.error(msg)
                raise ValidationError(msg) from e
    return validator

def validate_scrape_mode(field_name: str, required: bool = False):
    """抓取模式驗證"""
    from src.utils.enum_utils import ScrapeMode
    def validator(value: Any) -> Optional[ScrapeMode]:
        if value is None:
            if required:
                msg = f"{field_name}: 不能為空"
                logger.error(msg)
                raise ValidationError(msg)
            return None
        if isinstance(value, ScrapeMode):
            return value
        else:
            try:
                 # 嘗試從字串或其他值轉換為枚舉
                return str_to_enum(value, ScrapeMode, field_name)
            except ValidationError as e:
                logger.error(str(e))
                raise e
            except Exception as e:
                msg = f"{field_name}: 無法將值 '{value}' (類型 {type(value).__name__}) 轉換為 ScrapeMode: {str(e)}"
                logger.error(msg)
                raise ValidationError(msg) from e
    return validator


def validate_article_scrape_status(field_name: str, required: bool = False):
    """文章爬取狀態驗證"""
    from src.utils.enum_utils import ArticleScrapeStatus
    def validator(value: Any) -> Optional[ArticleScrapeStatus]:
        if value is None:
            if required:
                msg = f"{field_name}: 不能為空"
                logger.error(msg)
                raise ValidationError(msg)
            return None 
        if isinstance(value, ArticleScrapeStatus):
            return value
        else:
            try:
                 # 嘗試從字串或其他值轉換為枚舉
                return str_to_enum(value, ArticleScrapeStatus, field_name)
            except ValidationError as e:
                logger.error(str(e))
                raise e
            except Exception as e:
                msg = f"{field_name}: 無法將值 '{value}' (類型 {type(value).__name__}) 轉換為 ArticleScrapeStatus: {str(e)}"
                logger.error(msg)
                raise ValidationError(msg) from e
    return validator


def validate_task_status(field_name: str, required: bool = False):
    """任務狀態驗證"""
    from src.utils.enum_utils import TaskStatus
    def validator(value: Any) -> Optional[TaskStatus]:
        if value is None:
            if required:
                msg = f"{field_name}: 不能為空"
                logger.error(msg)
                raise ValidationError(msg)
            return None
        if isinstance(value, TaskStatus):
            return value
        else:
            try:
                 # 嘗試從字串或其他值轉換為枚舉
                return str_to_enum(value, TaskStatus, field_name)
            except ValidationError as e:
                logger.error(str(e))
                raise e
            except Exception as e:
                msg = f"{field_name}: 無法將值 '{value}' (類型 {type(value).__name__}) 轉換為 TaskStatus: {str(e)}"
                logger.error(msg)
                raise ValidationError(msg) from e
    return validator

