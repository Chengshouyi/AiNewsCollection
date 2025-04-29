"""測試 src.utils.transform_utils 中的轉換函式。"""
import enum

import pytest

from src.error.errors import ValidationError
from src.utils.log_utils import LoggerSetup
from src.utils.transform_utils import (
    convert_hashable_dict_to_str_dict,
    convert_to_dict,
    is_str_dict,
    str_to_enum,
)

# 設定 logger
logger = LoggerSetup.setup_logger(__name__)

# --- 測試用的輔助類別 ---
class SampleEnum(enum.Enum):
    ONE = "one"
    TWO = "two"
    THREE = "three"

class SampleClass:
    def __init__(self):
        self.attr1 = "value1"
        self.attr2 = "value2"
        self._private = "private"

class MockPydanticModel:
    def __init__(self):
        self.field1 = "value1"
        self.field2 = "value2"

    def dict(self, exclude_unset=False):
        # 模擬 Pydantic 的 dict() 方法
        return {"field1": self.field1, "field2": self.field2}

# --- 測試函式 ---
def test_is_str_dict():
    """測試 is_str_dict 函式"""
    assert is_str_dict({"a": 1, "b": 2}) is True # 所有鍵都是字串
    assert is_str_dict({1: "a", "b": 2}) is False # 包含非字串鍵
    assert is_str_dict({}) is True # 空字典

def test_str_to_enum():
    """測試 str_to_enum 函式"""
    assert str_to_enum("one", SampleEnum, "test_field") == SampleEnum.ONE # 正常字串轉換
    assert str_to_enum("ONE", SampleEnum, "test_field") == SampleEnum.ONE # 大寫字串轉換
    assert str_to_enum("tWo", SampleEnum, "test_field") == SampleEnum.TWO # 包含大小寫字串轉換
    assert str_to_enum(SampleEnum.THREE, SampleEnum, "test_field") == SampleEnum.THREE # 已經是枚舉類型

    # 測試無效的字串值
    with pytest.raises(ValidationError, match=r"test_field: 無效的枚舉值 'four'，可用值: one, two, three"):
        str_to_enum("four", SampleEnum, "test_field")

    # 測試非字串類型
    with pytest.raises(ValidationError, match=r"test_field: 無效的輸入類型，需要字串或 SampleEnum"):
        str_to_enum(123, SampleEnum, "test_field")

def test_convert_to_dict():
    """測試 convert_to_dict 函式"""
    # 已經是字典
    input_dict = {"key1": "value1", "key2": "value2"}
    assert convert_to_dict(input_dict) == input_dict

    # 測試普通類
    test_obj = SampleClass()
    result = convert_to_dict(test_obj)
    assert result == {"attr1": "value1", "attr2": "value2"}
    assert "_private" not in result # 確認私有屬性未被轉換

    # 測試 Pydantic 模型 (模擬)
    pydantic_model = MockPydanticModel()
    assert convert_to_dict(pydantic_model) == {"field1": "value1", "field2": "value2"}

    # 測試不支持的類型
    with pytest.raises(ValidationError, match=r"無效的資料格式，無法將類型 str 轉換為字典，需要字典或支援轉換的物件"):
        convert_to_dict("不是字典也不是對象")

def test_convert_hashable_dict_to_str_dict():
    """測試 convert_hashable_dict_to_str_dict 函式"""
    # 所有鍵都是字串的字典
    input_dict = {"a": 1, "b": 2}
    assert convert_hashable_dict_to_str_dict(input_dict) == {"a": 1, "b": 2}

    # 空字典
    assert convert_hashable_dict_to_str_dict({}) == {}

    # 包含非字串鍵的字典，應拋出 ValueError
    with pytest.raises(ValueError, match="字典的所有鍵必須是字符串類型"):
        convert_hashable_dict_to_str_dict({1: "a", "b": 2})
