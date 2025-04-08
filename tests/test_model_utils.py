import pytest
from src.error.errors import ValidationError
from src.utils.model_utils import (
    validate_str,
    validate_cron_expression,
    validate_datetime,
    validate_url,
    validate_list,
    convert_hashable_dict_to_str_dict,
)
from datetime import datetime, timezone, timedelta

class TestValidateStr:
    def test_valid_string(self):
        validator = validate_str("name")
        assert validator("test") == "test"

    def test_string_with_whitespace(self):
        validator = validate_str("name")
        assert validator("  test  ") == "test"

    def test_empty_string_not_required(self):
        validator = validate_str("name")
        assert validator("") is None

    def test_none_not_required(self):
        validator = validate_str("name")
        assert validator(None) is None

    def test_empty_string_required(self):
        validator = validate_str("name", required=True)
        with pytest.raises(ValidationError, match="name: 不能為空"):
            validator("")

    def test_none_required(self):
        validator = validate_str("name", required=True)
        with pytest.raises(ValidationError, match="name: 不能為 None"):
            validator(None)

    def test_max_length(self):
        validator = validate_str("name", max_length=5)
        assert validator("short") == "short"
        with pytest.raises(ValidationError, match="name: 長度不能超過 5 字元"):
            validator("toolong")

    def test_min_length(self):
        validator = validate_str("name", min_length=3)
        assert validator("long") == "long"
        with pytest.raises(ValidationError, match="name: 長度不能小於 3 字元"):
            validator("to")

    def test_regex_match(self):
        validator = validate_str("code", regex=r"^[A-Z]{2}-\d{3}$")
        assert validator("AB-123") == "AB-123"

    def test_regex_no_match(self):
        validator = validate_str("code", regex=r"^[A-Z]{2}-\d{3}$")
        with pytest.raises(ValidationError, match="code: 不符合指定的格式"):
            validator("ab-123")

class TestValidateCronExpression:
    def test_valid_cron(self):
        validator = validate_cron_expression("schedule")
        assert validator("* * * * *") == "* * * * *"

    def test_invalid_cron(self):
        validator = validate_cron_expression("schedule")
        with pytest.raises(ValidationError, match="schedule: Cron 表達式必須包含 5 個字段"):
            validator("invalid cron")

    def test_empty_cron_not_required(self):
        validator = validate_cron_expression("schedule")
        assert validator("") is None

    def test_none_cron_not_required(self):
        validator = validate_cron_expression("schedule")
        assert validator(None) is None

    def test_empty_cron_required(self):
        validator = validate_cron_expression("schedule", required=True)
        with pytest.raises(ValidationError, match="schedule: 不能為空"):
            validator("")

    def test_none_cron_required(self):
        validator = validate_cron_expression("schedule", required=True)
        with pytest.raises(ValidationError, match="schedule: 不能為 None"):
            validator(None)

    def test_cron_max_length(self):
        long_cron = "* * * * * " * 50
        validator = validate_cron_expression("schedule", max_length=100)
        with pytest.raises(ValidationError, match="schedule: 長度不能超過 100 字元"):
            validator(long_cron)

class TestValidateDatetime:
    def test_valid_utc_datetime_string(self):
        validator = validate_datetime("timestamp")
        dt_str = "2025-03-30T08:00:00Z"
        expected_dt = datetime(2025, 3, 30, 8, 0, 0, tzinfo=timezone.utc)
        assert validator(dt_str) == expected_dt

    def test_valid_utc_datetime_object(self):
        validator = validate_datetime("timestamp")
        dt_obj = datetime(2025, 3, 30, 8, 0, 0, tzinfo=timezone.utc)
        assert validator(dt_obj) == dt_obj

    def test_datetime_without_timezone(self):
        validator = validate_datetime("timestamp")
        dt_naive = datetime(2025, 3, 30, 8, 0, 0)
        with pytest.raises(ValidationError, match="timestamp: 日期時間必須包含時區資訊。"):
            validator(dt_naive)

    def test_datetime_with_non_utc_timezone(self):
        validator = validate_datetime("timestamp")
        taiwan_tz = timezone(timedelta(hours=8))
        dt_non_utc = datetime(2025, 3, 30, 16, 0, 0, tzinfo=taiwan_tz)
        with pytest.raises(ValidationError, match="timestamp: 日期時間必須是 UTC 時區"):
            validator(dt_non_utc)

    def test_invalid_datetime_format(self):
        validator = validate_datetime("timestamp")
        with pytest.raises(ValidationError, match="timestamp: 日期時間必須包含時區資訊。"):
            validator("2025-03-30 08:00:00")

    def test_empty_datetime_not_required(self):
        validator = validate_datetime("timestamp")
        with pytest.raises(ValidationError, match="timestamp: 不能為空"):
            validator("")

    def test_none_datetime_not_required(self):
        validator = validate_datetime("timestamp", required=True)
        with pytest.raises(ValidationError, match="timestamp: 不能為 None"):
            validator(None)

    def test_empty_datetime_required(self):
        validator = validate_datetime("timestamp", required=True)
        with pytest.raises(ValidationError, match="timestamp: 不能為空"):
            validator("")

    def test_none_datetime_required(self):
        validator = validate_datetime("timestamp", required=True)
        with pytest.raises(ValidationError, match="timestamp: 不能為 None"):
            validator(None)

    def test_invalid_datetime_type(self):
        validator = validate_datetime("timestamp")
        with pytest.raises(ValidationError, match="timestamp: 必須是字串或日期時間物件。"):
            validator(123)

class TestValidateUrl:
    def test_valid_url_http(self):
        validator = validate_url("website")
        assert validator("http://example.com") == "http://example.com"

    def test_valid_url_https(self):
        validator = validate_url("website")
        assert validator("https://example.com/path?query=value#fragment") == "https://example.com/path?query=value#fragment"

    def test_invalid_url_format(self):
        validator = validate_url("website")
        with pytest.raises(ValidationError, match="website: 無效的URL格式"):
            validator("not a url")

    def test_url_max_length(self):
        long_url = "https://example.com/" + "a" * 1000
        validator = validate_url("website", max_length=100)
        with pytest.raises(ValidationError, match="website: 長度不能超過 100 字元"):
            validator(long_url)

    def test_empty_url_not_required(self):
        validator = validate_url("website")
        assert validator("") is None

    def test_none_url_not_required(self):
        validator = validate_url("website")
        assert validator(None) is None

    def test_empty_url_required(self):
        validator = validate_url("website", required=True)
        with pytest.raises(ValidationError, match="website: URL不能為空"):
            validator("")

    def test_none_url_required(self):
        validator = validate_url("website", required=True)
        with pytest.raises(ValidationError, match="website: URL不能為空"):
            validator(None)

    def test_custom_regex_match(self):
        validator = validate_url("image", regex=r".*\.(jpg|png)$")
        assert validator("https://example.com/image.jpg") == "https://example.com/image.jpg"

    def test_custom_regex_no_match(self):
        validator = validate_url("image", regex=r".*\.(jpg|png)$")
        with pytest.raises(ValidationError, match="image: 無效的URL格式"):
            validator("https://example.com/image.gif")

class TestValidateList:
    """測試列表驗證功能"""
    
    def test_valid_list(self):
        """測試有效的列表"""
        validator = validate_list("items")
        assert validator([1, 2, 3]) == [1, 2, 3]

    def test_empty_list_not_required(self):
        """測試非必填時的空列表"""
        validator = validate_list("items", required=False, min_length=0)
        assert validator([]) == []

    def test_none_not_required(self):
        """測試非必填時的 None 值"""
        validator = validate_list("items", required=True)
        with pytest.raises(ValidationError, match="items: 不能為 None"):
            validator(None)

    def test_none_required(self):
        """測試必填時的 None 值"""
        validator = validate_list("items", required=True)
        with pytest.raises(ValidationError, match="items: 不能為 None"):
            validator(None)

    def test_invalid_type(self):
        """測試非列表類型"""
        validator = validate_list("items")
        with pytest.raises(ValidationError, match="items: 必須是列表"):
            validator("not a list")

    def test_type_validation(self):
        """測試列表元素類型驗證"""
        validator = validate_list("items", type=str)
        # 測試有效的字符串列表
        assert validator(["a", "b", "c"]) == ["a", "b", "c"]
        # 測試包含非字符串的列表
        with pytest.raises(ValidationError, match="items: 列表中的所有元素必須是 str"):
            validator(["a", 1, "c"])

    def test_min_length_validation(self):
        """測試最小長度驗證"""
        validator = validate_list("items", min_length=2)
        # 測試符合最小長度的列表
        assert validator([1, 2]) == [1, 2]
        # 測試不符合最小長度的列表
        with pytest.raises(ValidationError, match="items: 列表長度不能小於 2"):
            validator([1])

class TestConvertHashableDictToStrDict:
    """測試字典轉換功能"""
    
    def test_valid_str_dict(self):
        """測試已經是字符串鍵的字典"""
        input_dict = {"a": 1, "b": 2}
        result = convert_hashable_dict_to_str_dict(input_dict)
        assert result == {"a": 1, "b": 2}

    def test_mixed_key_types(self):
        """測試混合鍵類型的字典"""
        input_dict = {"a": 1, 2: "b"}
        with pytest.raises(ValueError, match="字典的所有鍵必須是字符串類型"):
            convert_hashable_dict_to_str_dict(input_dict)

    def test_empty_dict(self):
        """測試空字典"""
        input_dict = {}
        result = convert_hashable_dict_to_str_dict(input_dict)
        assert result == {}

    def test_nested_dict(self):
        """測試嵌套字典"""
        input_dict = {
            "a": {"b": 1},
            "c": {"d": 2}
        }
        result = convert_hashable_dict_to_str_dict(input_dict)
        assert result == {
            "a": {"b": 1},
            "c": {"d": 2}
        }

    def test_complex_values(self):
        """測試複雜值類型"""
        input_dict = {
            "a": [1, 2, 3],
            "b": {"x": 1},
            "c": (4, 5, 6)
        }
        result = convert_hashable_dict_to_str_dict(input_dict)
        assert result == {
            "a": [1, 2, 3],
            "b": {"x": 1},
            "c": (4, 5, 6)
        }