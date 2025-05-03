"""測試 src.utils.schema_utils 中的驗證函式。"""
import pytest
import logging

from src.error.errors import ValidationError
 # 使用統一的 logger
from src.utils.schema_utils import validate_required_fields_schema, validate_update_schema

# 設定 logger
logger = logging.getLogger(__name__)  # 使用統一的 logger

def test_update_success_valid_field():
    """成功：提供允許更新的欄位"""
    immutable = ["id", "created_at"]
    allowed = ["name", "description", "value"]
    data = {"name": "new name", "value": 100}
    result = validate_update_schema(immutable, allowed, data)
    assert result == data

def test_update_success_mixed_fields():
    """成功：提供允許更新欄位和非定義欄位"""
    immutable = ["id"]
    allowed = ["name", "value"]
    data = {"name": "new name", "extra_field": "some data"}
    result = validate_update_schema(immutable, allowed, data)
    assert result == data

def test_update_fail_immutable_field():
    """失敗：嘗試更新不可變欄位"""
    immutable = ["id", "created_at"]
    allowed = ["name", "description"]
    data = {"name": "new name", "id": 123}
    with pytest.raises(ValidationError, match="不允許更新 id 欄位"):
        validate_update_schema(immutable, allowed, data)

def test_update_fail_only_immutable_field():
    """失敗：只提供不可變欄位"""
    immutable = ["id"]
    allowed = ["name"]
    data = {"id": 456}
    with pytest.raises(ValidationError, match="不允許更新 id 欄位"):
        validate_update_schema(immutable, allowed, data)

def test_update_fail_no_updatable_fields_provided():
    """失敗：未提供任何允許更新的欄位"""
    immutable = ["id"]
    allowed = ["name", "value"]
    data_empty = {}
    data_other = {"another_field": "x"}

    with pytest.raises(ValidationError, match="必須提供至少一個要更新的欄位"):
        validate_update_schema(immutable, allowed, data_empty)

    with pytest.raises(ValidationError, match="必須提供至少一個要更新的欄位"):
        validate_update_schema(immutable, allowed, data_other)

def test_update_fail_only_immutable_provided_but_allowed():
    """失敗：提供的欄位是不可變的，即使它也在允許列表中"""
    immutable = ["id"]
    allowed = ["name", "id"] # id 技術上允許但同時也是不可變的
    data = {"id": 789}
    with pytest.raises(ValidationError, match="不允許更新 id 欄位"):
        validate_update_schema(immutable, allowed, data)


def test_required_success_all_present():
    """成功：所有必填欄位都存在"""
    required = ["name", "email"]
    data = {"name": "Test User", "email": "test@example.com", "optional": "value"}
    result = validate_required_fields_schema(required, data)
    assert result == data

def test_required_success_no_required_fields():
    """成功：沒有定義必填欄位"""
    required = []
    data = {"name": "Test User"}
    result = validate_required_fields_schema(required, data)
    assert result == data

def test_required_fail_one_missing():
    """失敗：缺少一個必填欄位"""
    required = ["name", "email", "age"]
    data = {"name": "Test User", "email": "test@example.com"}
    with pytest.raises(ValidationError, match="以下必填欄位缺失或值為空/空白: age"):
        validate_required_fields_schema(required, data)

def test_required_fail_multiple_missing():
    """失敗：缺少多個必填欄位"""
    required = ["name", "email", "city"]
    data = {"name": "Test User"}
    with pytest.raises(ValidationError, match="以下必填欄位缺失或值為空/空白: email, city"):
        validate_required_fields_schema(required, data)

def test_required_fail_data_empty():
    """失敗：data 為空，但有必填欄位"""
    required = ["name"]
    data = {}
    with pytest.raises(ValidationError, match="以下必填欄位缺失或值為空/空白: name"):
        validate_required_fields_schema(required, data)



