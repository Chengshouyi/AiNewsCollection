import pytest
from src.utils.schema_utils import validate_update_schema, validate_required_fields_schema, validate_crawler_config
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

# 測試爬蟲配置驗證

def test_validate_crawler_config_success():
    """測試：爬蟲配置驗證成功"""
    data = {
        "crawler_name": "TestCrawler",
        "base_url": "https://example.com",
        "crawler_type": "web", 
        "config_file_name": "test_config.json",
        "is_active": True
    }
    errors = validate_crawler_config(data)
    assert len(errors) == 0, "有效的爬蟲配置應該沒有錯誤"

def test_validate_crawler_config_missing_fields():
    """測試：爬蟲配置缺少必填欄位"""
    data = {
        "crawler_name": "TestCrawler",
        "base_url": "https://example.com"
        # 缺少 crawler_type 和 config_file_name
    }
    errors = validate_crawler_config(data)
    assert len(errors) == 2, "應該有兩個錯誤"
    assert any("crawler_type 是必填欄位" in error for error in errors)
    assert any("config_file_name 是必填欄位" in error for error in errors)

def test_validate_crawler_config_invalid_url():
    """測試：爬蟲配置含有無效的 URL"""
    data = {
        "crawler_name": "TestCrawler",
        "base_url": "invalid-url",
        "crawler_type": "web",
        "config_file_name": "test_config.json"
    }
    errors = validate_crawler_config(data)
    assert len(errors) == 1, "應該有一個錯誤"
    assert "base_url 必須是有效的 URL" in errors[0]

def test_validate_crawler_config_field_too_long():
    """測試：爬蟲配置欄位超過長度限制"""
    data = {
        "crawler_name": "T" * 101,  # 超過 100 字元
        "base_url": "https://example.com",
        "crawler_type": "web",
        "config_file_name": "test_config.json"
    }
    errors = validate_crawler_config(data)
    assert len(errors) == 1, "應該有一個錯誤"
    assert "crawler_name 長度不能超過 100 字元" in errors[0]

def test_validate_crawler_config_invalid_is_active():
    """測試：爬蟲配置的 is_active 不是布爾值"""
    data = {
        "crawler_name": "TestCrawler",
        "base_url": "https://example.com",
        "crawler_type": "web",
        "config_file_name": "test_config.json",
        "is_active": "true"  # 應該是布爾值，不是字串
    }
    errors = validate_crawler_config(data)
    assert len(errors) == 1, "應該有一個錯誤"
    assert "is_active 必須是布爾值" in errors[0]

def test_validate_crawler_config_update_mode():
    """測試：更新模式下的爬蟲配置驗證"""
    # 在更新模式下，不需要提供所有必填欄位
    data = {
        "crawler_name": "UpdatedCrawler"
        # 不需要提供其他必填欄位
    }
    errors = validate_crawler_config(data, is_update=True)
    assert len(errors) == 0, "更新模式下應該沒有錯誤"

