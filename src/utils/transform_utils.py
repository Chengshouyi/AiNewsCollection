"""提供資料轉換相關的工具函式，例如型別轉換、物件轉字典等。"""
import enum
import logging
from typing import Any, Dict, Hashable, Optional, Type, TypeVar

from src.error.errors import ValidationError


# 設定 logger
logger = logging.getLogger(__name__)  # 使用統一的 logger

def is_str_dict(data: Dict[Hashable, Any]) -> bool:
    """檢查字典的所有鍵是否都是字符串類型"""
    return all(isinstance(k, str) for k in data.keys())

E = TypeVar('E', bound=enum.Enum)

def str_to_enum(value: Any, enum_type: Type[E], field_name: str) -> Optional[E]:
    """字串轉換為枚舉，會嘗試原始、大寫、小寫形式。"""
    if isinstance(value, enum_type):
        return value

    if not isinstance(value, str):
        logger.warning("欄位 '%s' 的輸入類型無效: '%s'，應為字串或 %s",
                     field_name, type(value).__name__, enum_type.__name__)
        raise ValidationError(f"{field_name}: 無效的輸入類型，需要字串或 {enum_type.__name__}")

    try:
        return enum_type(value)
    except ValueError:
        try:
            # 嘗試大寫
            return enum_type(value.upper())
        except ValueError:
            try:
                # 嘗試小寫
                return enum_type(value.lower())
            except ValueError:
                valid_values = ', '.join([e.value for e in enum_type])
                logger.warning("欄位 '%s' 的枚舉值無效: '%s'。可用值: %s",
                             field_name, value, valid_values)
                raise ValidationError(f"{field_name}: 無效的枚舉值 '{value}'，可用值: {valid_values}")

def convert_to_dict(data: Any) -> Dict[str, Any]:
    """將物件或 Pydantic 模型轉換為字典，排除底線開頭的屬性。"""
    if isinstance(data, dict):
        processed_data = data.copy()
    elif hasattr(data, 'dict') and callable(data.dict):
        processed_data = data.dict(exclude_unset=True)
    elif hasattr(data, '__dict__'):
        processed_data = {k: v for k, v in data.__dict__.items()
                            if not k.startswith('_')}
    else:
        logger.warning("嘗試轉換不支援的資料類型: %s", type(data).__name__)
        raise ValidationError(f"無效的資料格式，無法將類型 {type(data).__name__} 轉換為字典，需要字典或支援轉換的物件")
    return processed_data

def convert_hashable_dict_to_str_dict(data: Dict[Any, Any]) -> Dict[str, Any]:
    """
    將 Dict[Hashable, Any] 轉換為 Dict[str, Any]。
    如果鍵不是字串，則拋出 ValueError。

    Args:
        data: 包含 Hashable 鍵的字典。

    Returns:
        Dict[str, Any]: 包含字符串鍵的字典。

    Raises:
        ValueError: 如果字典包含非字串鍵。
    """
    if not is_str_dict(data):
        non_str_keys = [k for k in data.keys() if not isinstance(k, str)]
        logger.error("字典包含非字串鍵: %s", non_str_keys)
        # 維持拋出 ValueError 以符合現有測試和可能的外部預期
        raise ValueError(f"字典的所有鍵必須是字符串類型。找到非字串鍵: {non_str_keys}")

    return {str(k): v for k, v in data.items()}