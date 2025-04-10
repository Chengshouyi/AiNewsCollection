import pytest
from src.utils.schema_utils import validate_update_schema, validate_required_fields_schema
from src.error.errors import ValidationError

def test_update_success_valid_field():
    """成功：提供允許更新的欄位"""
    immutable = ["id", "created_at"]
    allowed = ["name", "description", "value"]
    data = {"name": "new name", "value": 100}
    result = validate_update_schema(immutable, allowed, data)
    assert result == data # Should return original data on success

def test_update_success_mixed_fields():
    """成功：提供允許更新欄位和非定義欄位"""
    immutable = ["id"]
    allowed = ["name", "value"]
    data = {"name": "new name", "extra_field": "some data"} # Contains allowed 'name'
    result = validate_update_schema(immutable, allowed, data)
    assert result == data

def test_update_fail_immutable_field():
    """失敗：嘗試更新不可變欄位"""
    immutable = ["id", "created_at"]
    allowed = ["name", "description"]
    data = {"name": "new name", "id": 123} # 'id' is immutable
    with pytest.raises(ValidationError, match="不允許更新 id 欄位"):
        validate_update_schema(immutable, allowed, data)

def test_update_fail_only_immutable_field():
    """失敗：只提供不可變欄位 (也觸發不可變規則)"""
    immutable = ["id"]
    allowed = ["name"]
    data = {"id": 456}
    with pytest.raises(ValidationError, match="不允許更新 id 欄位"):
        validate_update_schema(immutable, allowed, data)

def test_update_fail_no_updatable_fields_provided():
    """失敗：未提供任何允許更新的欄位 (data 為空或只包含非 allowed 欄位)"""
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
    allowed = ["name", "id"] # id is technically allowed but also immutable
    data = {"id": 789}
    with pytest.raises(ValidationError, match="不允許更新 id 欄位"):
        validate_update_schema(immutable, allowed, data)


def test_required_success_all_present():
    """成功：所有必填欄位都存在"""
    required = ["name", "email"]
    data = {"name": "Test User", "email": "test@example.com", "optional": "value"}
    result = validate_required_fields_schema(required, data)
    assert result == data # Should return original data on success

def test_required_success_no_required_fields():
    """成功：沒有定義必填欄位"""
    required = []
    data = {"name": "Test User"}
    result = validate_required_fields_schema(required, data)
    assert result == data

def test_required_fail_one_missing():
    """失敗：缺少一個必填欄位"""
    required = ["name", "email", "age"]
    data = {"name": "Test User", "email": "test@example.com"} # Missing 'age'
    with pytest.raises(ValidationError, match="age: 不能為空"):
        validate_required_fields_schema(required, data)

def test_required_fail_multiple_missing():
    """失敗：缺少多個必填欄位 (應捕捉到第一個缺少的)"""
    required = ["name", "email", "city"]
    data = {"name": "Test User"} # Missing 'email', 'city'
    # pytest will catch the first missing field encountered in the loop
    with pytest.raises(ValidationError, match="email: 不能為空"):
         validate_required_fields_schema(required, data)

def test_required_fail_data_empty():
    """失敗：data 為空，但有必填欄位"""
    required = ["name"]
    data = {}
    with pytest.raises(ValidationError, match="name: 不能為空"):
        validate_required_fields_schema(required, data)



