"""測試 API 請求參數解析工具 (api_utils) 的功能。"""

import pytest
from werkzeug.datastructures import MultiDict
from src.utils.api_utils import parse_and_validate_common_query_params
from src.utils.log_utils import LoggerSetup

logger = LoggerSetup.setup_logger(__name__)

def test_parse_default_params():
    """測試沒有提供參數時的預設值。"""
    args = MultiDict([])
    validated_params, filter_criteria = parse_and_validate_common_query_params(args)
    assert validated_params == {
        'page': 1,
        'per_page': 10,
        'limit': None,
        'offset': None,
        'sort_by': None,
        'sort_desc': False,
        'is_preview': False,
        'preview_fields': None,
        'q': None
    }
    assert filter_criteria == {}

def test_parse_valid_params():
    """測試提供所有有效的標準參數。"""
    args = MultiDict([
        ('page', '2'),
        ('per_page', '20'),
        ('limit', '100'),
        ('offset', '5'),
        ('sort_by', 'name'),
        ('sort_desc', 'true'),
        ('is_preview', '1'),
        ('preview_fields', 'id,name,email'),
        ('q', 'search term')
    ])
    validated_params, filter_criteria = parse_and_validate_common_query_params(args)
    assert validated_params == {
        'page': 2,
        'per_page': 20,
        'limit': 100,
        'offset': 5,
        'sort_by': 'name',
        'sort_desc': True,
        'is_preview': True,
        'preview_fields': ['id', 'name', 'email'],
        'q': 'search term'
    }
    assert filter_criteria == {}

def test_parse_with_filter_criteria():
    """測試包含額外過濾條件的參數。"""
    args = MultiDict([
        ('page', '1'),
        ('per_page', '15'),
        ('status', 'active'),
        ('category_id', '123'),
        ('sort_by', 'date')
    ])
    validated_params, filter_criteria = parse_and_validate_common_query_params(args)
    assert validated_params == {
        'page': 1,
        'per_page': 15,
        'limit': None,
        'offset': None,
        'sort_by': 'date',
        'sort_desc': False,
        'is_preview': False,
        'preview_fields': None,
        'q': None
    }
    # 注意：MultiDict 對於同名鍵的處理，這裡 parse 函數只取第一個值
    assert filter_criteria == {
        'status': 'active',
        'category_id': '123'
    }

# --- 測試無效參數 ---
@pytest.mark.parametrize("param, value, expected_error_msg", [
    ('page', '0', 'page 必須是正整數'),
    ('page', '-1', 'page 必須是正整數'),
    ('page', 'abc', "invalid literal for int() with base 10: 'abc'"),
    ('per_page', '0', 'per_page 必須是正整數'),
    ('per_page', '-5', 'per_page 必須是正整數'),
    ('per_page', 'xyz', "invalid literal for int() with base 10: 'xyz'"),
    ('limit', '-10', 'limit 必須是非負整數'),
    ('limit', 'def', "invalid literal for int() with base 10: 'def'"),
    ('offset', '-1', 'offset 必須是非負整數'),
    ('offset', 'ghi', "invalid literal for int() with base 10: 'ghi'"),
])
def test_parse_invalid_numeric_params(param, value, expected_error_msg):
    """測試無效的數值參數是否引發 ValueError。"""
    args = MultiDict([(param, value)])
    with pytest.raises(ValueError) as excinfo:
        parse_and_validate_common_query_params(args)
    # 檢查異常訊息是否包含預期的子字串
    assert expected_error_msg in str(excinfo.value)

# --- 測試布林參數的不同表示 ---
@pytest.mark.parametrize("param_name, value, expected_bool", [
    ('sort_desc', 'true', True),
    ('sort_desc', 'TRUE', True),
    ('sort_desc', '1', True),
    ('sort_desc', 'yes', True),
    ('sort_desc', 'false', False),
    ('sort_desc', 'FALSE', False),
    ('sort_desc', '0', False),
    ('sort_desc', 'no', False),
    ('sort_desc', 'any_other_string', False), # 非特定真值應視為 False
    ('is_preview', 'true', True),
    ('is_preview', '1', True),
    ('is_preview', 'yes', True),
    ('is_preview', 'false', False),
    ('is_preview', '0', False),
    ('is_preview', 'no', False),
])
def test_parse_boolean_params(param_name, value, expected_bool):
    """測試布林參數的不同輸入值。"""
    args = MultiDict([(param_name, value)])
    validated_params, _ = parse_and_validate_common_query_params(args)
    assert validated_params[param_name] == expected_bool

def test_parse_preview_fields():
    """測試 preview_fields 的解析。"""
    # 情況 1：提供 preview_fields
    args1 = MultiDict([('preview_fields', 'field1,field2')])
    validated_params1, _ = parse_and_validate_common_query_params(args1)
    assert validated_params1['preview_fields'] == ['field1', 'field2']

    # 情況 2：提供空的 preview_fields
    args2 = MultiDict([('preview_fields', '')])
    validated_params2, _ = parse_and_validate_common_query_params(args2)
    assert validated_params2['preview_fields'] is None # 空字串應解析為 None

    # 情況 3：未提供 preview_fields
    args3 = MultiDict([])
    validated_params3, _ = parse_and_validate_common_query_params(args3)
    assert validated_params3['preview_fields'] is None

def test_parse_q_param():
    """測試通用搜尋關鍵字 'q' 的解析。"""
    # 情況 1：提供 q
    args1 = MultiDict([('q', 'my search query')])
    validated_params1, _ = parse_and_validate_common_query_params(args1)
    assert validated_params1['q'] == 'my search query'

    # 情況 2：提供空的 q
    args2 = MultiDict([('q', '')])
    validated_params2, _ = parse_and_validate_common_query_params(args2)
    assert validated_params2['q'] == '' # 空字串應保留

    # 情況 3：未提供 q
    args3 = MultiDict([])
    validated_params3, _ = parse_and_validate_common_query_params(args3)
    assert validated_params3['q'] is None
