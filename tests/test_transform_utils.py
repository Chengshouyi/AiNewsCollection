import pytest
import enum
from typing import Dict, Any, Optional
from src.utils.transform_utils import (
    is_str_dict,
    str_to_enum,
    convert_to_dict,
    convert_hashable_dict_to_str_dict
)
from src.error.errors import ValidationError

# 為測試創建一個枚舉類
class SampleEnum(enum.Enum):
    ONE = "one"
    TWO = "two"
    THREE = "three"

# 為測試創建一個簡單的類
class SampleClass:
    def __init__(self):
        self.attr1 = "value1"
        self.attr2 = "value2"
        self._private = "private"

# 為測試創建一個 Pydantic 類模擬
class MockPydanticModel:
    def __init__(self):
        self.field1 = "value1"
        self.field2 = "value2"
    
    def dict(self, exclude_unset=False):
        return {"field1": self.field1, "field2": self.field2}

# 測試 is_str_dict 函數
def test_is_str_dict():
    # 所有鍵都是字串
    assert is_str_dict({"a": 1, "b": 2}) == True
    
    # 包含非字串鍵
    assert is_str_dict({1: "a", "b": 2}) == False
    
    # 空字典
    assert is_str_dict({}) == True

# 測試 str_to_enum 函數
def test_str_to_enum():
    # 正常字串轉換
    assert str_to_enum("one", SampleEnum, "test_field") == SampleEnum.ONE
    
    # 大寫字串轉換
    assert str_to_enum("ONE", SampleEnum, "test_field") == SampleEnum.ONE
    
    # 小寫字串轉換
    assert str_to_enum("tWo", SampleEnum, "test_field") == SampleEnum.TWO
    
    # 已經是枚舉類型
    assert str_to_enum(SampleEnum.THREE, SampleEnum, "test_field") == SampleEnum.THREE
    
    # 無效的字串
    with pytest.raises(ValidationError):
        str_to_enum("four", SampleEnum, "test_field")
    
    # 非字串類型
    with pytest.raises(ValidationError):
        str_to_enum(123, SampleEnum, "test_field")

# 測試 convert_to_dict 函數
def test_convert_to_dict():
    # 已經是字典
    input_dict = {"key1": "value1", "key2": "value2"}
    assert convert_to_dict(input_dict) == input_dict
    
    # 測試普通類
    test_obj = SampleClass()
    result = convert_to_dict(test_obj)
    assert result == {"attr1": "value1", "attr2": "value2"}
    assert "_private" not in result
    
    # 測試 Pydantic 模型
    pydantic_model = MockPydanticModel()
    assert convert_to_dict(pydantic_model) == {"field1": "value1", "field2": "value2"}
    
    # 測試不支持的類型
    with pytest.raises(ValidationError):
        convert_to_dict("不是字典也不是對象")

# 測試 convert_hashable_dict_to_str_dict 函數
def test_convert_hashable_dict_to_str_dict():
    # 所有鍵都是字串的字典
    input_dict = {"a": 1, "b": 2}
    assert convert_hashable_dict_to_str_dict(input_dict) == {"a": 1, "b": 2}
    
    # 空字典
    assert convert_hashable_dict_to_str_dict({}) == {}
    
    # 包含非字串鍵的字典
    with pytest.raises(ValueError):
        convert_hashable_dict_to_str_dict({1: "a", "b": 2})
