"""測試 src.utils.repository_utils 中的字典更新函數。"""

# Standard library
import logging
from unittest.mock import MagicMock, patch

# Third-party libraries
import pytest

# Local application imports

from src.utils.repository_utils import (
    _apply_deep_changes_inplace,
    deep_update_dict_field,
    update_dict_field_inplace,
)

# Setup logger
logger = logging.getLogger(__name__)  # 使用統一的 logger # pylint: disable=invalid-name

# --- Tests for deep_update_dict_field (returns new dict) ---

def test_deep_update_new_key():
    """測試添加新鍵"""
    current = {'a': 1}
    new = {'b': 2}
    expected = {'a': 1, 'b': 2}
    result = deep_update_dict_field(current, new, 'test_field')
    assert result == expected
    assert result is not current # Should return a new dict

def test_deep_update_existing_key():
    """測試更新現有鍵"""
    current = {'a': 1, 'b': 2}
    new = {'b': 3}
    expected = {'a': 1, 'b': 3}
    result = deep_update_dict_field(current, new, 'test_field')
    assert result == expected

def test_deep_update_nested_dict_new_key():
    """測試添加巢狀字典中的新鍵"""
    current = {'a': 1, 'nested': {'x': 10}}
    new = {'nested': {'y': 20}}
    expected = {'a': 1, 'nested': {'x': 10, 'y': 20}}
    result = deep_update_dict_field(current, new, 'test_field')
    assert result == expected

def test_deep_update_nested_dict_update_key():
    """測試更新巢狀字典中的現有鍵"""
    current = {'a': 1, 'nested': {'x': 10, 'y': 20}}
    new = {'nested': {'y': 30}}
    expected = {'a': 1, 'nested': {'x': 10, 'y': 30}}
    result = deep_update_dict_field(current, new, 'test_field')
    assert result == expected

def test_deep_update_replace_non_dict_with_dict():
    """測試用字典替換非字典值"""
    current = {'a': 1, 'nested': 100}
    new = {'nested': {'x': 10}}
    expected = {'a': 1, 'nested': {'x': 10}}
    result = deep_update_dict_field(current, new, 'test_field')
    assert result == expected

def test_deep_update_replace_dict_with_non_dict():
    """測試用非字典值替換字典"""
    current = {'a': 1, 'nested': {'x': 10}}
    new = {'nested': 100}
    expected = {'a': 1, 'nested': 100}
    result = deep_update_dict_field(current, new, 'test_field')
    assert result == expected

def test_deep_update_current_none():
    """測試當前值為 None 的情況"""
    current = None
    new = {'a': 1, 'b': 2}
    expected = {'a': 1, 'b': 2}
    result = deep_update_dict_field(current, new, 'test_field')
    assert result == expected

def test_deep_update_current_not_dict():
    """測試當前值不是字典的情況"""
    current = "not a dict"
    new = {'a': 1, 'b': 2}
    expected = {'a': 1, 'b': 2}
    result = deep_update_dict_field(current, new, 'test_field')# type: ignore # 保留類型忽略，因為這是預期行為
    assert result == expected

def test_deep_update_no_changes():
    """測試沒有變更的情況"""
    current = {'a': 1, 'nested': {'x': 10}}
    new = {'a': 1} # Only provide existing value
    expected = {'a': 1, 'nested': {'x': 10}}
    result = deep_update_dict_field(current, new, 'test_field') 
    assert result == expected


# --- Tests for _apply_deep_changes_inplace (modifies dict in-place) ---

def test_inplace_update_new_key():
    """測試原地添加新鍵"""
    target = {'a': 1}
    changes = {'b': 2}
    made_changes = _apply_deep_changes_inplace(target, changes, 'test_field')
    assert target == {'a': 1, 'b': 2}
    assert made_changes is True

def test_inplace_update_existing_key():
    """測試原地更新現有鍵"""
    target = {'a': 1, 'b': 2}
    changes = {'b': 3}
    made_changes = _apply_deep_changes_inplace(target, changes, 'test_field')
    assert target == {'a': 1, 'b': 3}
    assert made_changes is True

def test_inplace_update_nested_new_key():
    """測試原地添加巢狀字典中的新鍵"""
    target = {'a': 1, 'nested': {'x': 10}}
    changes = {'nested': {'y': 20}}
    made_changes = _apply_deep_changes_inplace(target, changes, 'test_field')
    assert target == {'a': 1, 'nested': {'x': 10, 'y': 20}}
    assert made_changes is True

def test_inplace_update_nested_update_key():
    """測試原地更新巢狀字典中的現有鍵"""
    target = {'a': 1, 'nested': {'x': 10, 'y': 20}}
    changes = {'nested': {'y': 30}}
    made_changes = _apply_deep_changes_inplace(target, changes, 'test_field')
    assert target == {'a': 1, 'nested': {'x': 10, 'y': 30}}
    assert made_changes is True

def test_inplace_replace_non_dict_with_dict():
    """測試原地用字典替換非字典值"""
    target = {'a': 1, 'nested': 100}
    changes = {'nested': {'x': 10}}
    made_changes = _apply_deep_changes_inplace(target, changes, 'test_field')
    assert target == {'a': 1, 'nested': {'x': 10}}
    assert made_changes is True

def test_inplace_replace_dict_with_non_dict():
    """測試原地用非字典值替換字典"""
    target = {'a': 1, 'nested': {'x': 10}}
    changes = {'nested': 100}
    made_changes = _apply_deep_changes_inplace(target, changes, 'test_field')
    assert target == {'a': 1, 'nested': 100}
    assert made_changes is True

def test_inplace_no_changes():
    """測試原地沒有變更的情況"""
    target = {'a': 1, 'nested': {'x': 10}}
    original_target = target.copy() # 保留原始副本以進行比較
    changes = {'a': 1} # 僅提供現有值
    made_changes = _apply_deep_changes_inplace(target, changes, 'test_field')
    assert target == original_target
    assert made_changes is False

def test_inplace_empty_changes():
    """測試空的變更 payload"""
    target = {'a': 1}
    original_target = target.copy()
    changes = {}
    made_changes = _apply_deep_changes_inplace(target, changes, 'test_field')
    assert target == original_target
    assert made_changes is False


# --- Tests for update_dict_field_inplace (orchestrator) ---

class MockEntity:
    """用於測試的模擬實體類。"""
    def __init__(self, data=None):
        self.task_args = data

@patch('src.utils.repository_utils.flag_modified') # 保留 patch decorator
def test_orchestrator_inplace_updates_and_flags(mock_flag_modified):
    """測試 orchestrator 是否正確調用 inplace 更新並標記"""
    entity = MockEntity({'ai_only': False, 'max_pages': 10})
    changes = {'ai_only': True, 'new_param': 5}
    
    result = update_dict_field_inplace(entity, 'task_args', changes)
    
    assert result is True # Changes were made
    assert entity.task_args == {'ai_only': True, 'max_pages': 10, 'new_param': 5}
    mock_flag_modified.assert_called_once_with(entity, 'task_args')

@patch('src.utils.repository_utils.flag_modified') # 保留 patch decorator
def test_orchestrator_inplace_no_changes_no_flag(mock_flag_modified):
    """測試 orchestrator 在無變更時不標記"""
    entity = MockEntity({'ai_only': False, 'max_pages': 10})
    changes = {'ai_only': False} # No actual change
    
    result = update_dict_field_inplace(entity, 'task_args', changes)
    
    assert result is False # No changes were made
    assert entity.task_args == {'ai_only': False, 'max_pages': 10}
    mock_flag_modified.assert_not_called()

@patch('src.utils.repository_utils.flag_modified') # 保留 patch decorator
def test_orchestrator_inplace_field_not_dict_initializes(mock_flag_modified):
    """測試當欄位不是字典時，orchestrator 是否初始化並更新"""
    entity = MockEntity(None) # Field starts as None
    changes = {'ai_only': True}
    
    result = update_dict_field_inplace(entity, 'task_args', changes)
    
    assert result is True
    assert entity.task_args == {'ai_only': True}
    mock_flag_modified.assert_called_once_with(entity, 'task_args')

def test_orchestrator_inplace_field_does_not_exist():
    """測試當實體沒有該欄位時"""
    entity = object() # 一個沒有 task_args 的普通物件
    changes = {'ai_only': True}
    result = update_dict_field_inplace(entity, 'task_args', changes)
    assert result is False
