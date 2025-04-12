from typing import Any, Type, TypeVar, Optional, Dict, Hashable
import enum
from src.error.errors import ValidationError

def is_str_dict(data: Dict[Hashable, Any]) -> bool:
    """檢查字典的所有鍵是否都是字符串類型"""
    return all(isinstance(k, str) for k in data.keys())

E = TypeVar('E', bound=enum.Enum)

def str_to_enum(value: Any, enum_type: Type[E], field_name: str) -> Optional[E]:
    """字串轉換為枚舉"""
    if isinstance(value, enum_type):
        return value
    # 確保 value 是字串才進行後續處理
    if not isinstance(value, str):
        raise ValidationError(f"{field_name}: 無效的輸入類型，需要字串或 {enum_type.__name__}")
    try:
        return enum_type(value)
    except ValueError:
        try:
            return enum_type(value.upper())
        except ValueError:
            try:
                return enum_type(value.lower())
            except ValueError:
                valid_values = ', '.join([e.value for e in enum_type])
                raise ValidationError(f"{field_name}: 無效的枚舉值 '{value}'，可用值: {valid_values}")


def convert_to_dict(data: Any) -> Dict[str, Any]:
    """將任意類型轉換為字典"""
    # 轉換為字典
    if isinstance(data, dict):
        processed_data = data.copy()
    elif hasattr(data, 'dict') and callable(data.dict):
        # 處理 Pydantic 模型
        processed_data = data.dict(exclude_unset=True)
    elif hasattr(data, '__dict__'):
        # 處理普通物件
        processed_data = {k: v for k, v in data.__dict__.items() 
                            if not k.startswith('_')}
    else:
        raise ValidationError("無效的資料格式，需要字典或支援轉換的物件")
    return processed_data


def convert_hashable_dict_to_str_dict(data: Dict[Any, Any]) -> Dict[str, Any]:
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