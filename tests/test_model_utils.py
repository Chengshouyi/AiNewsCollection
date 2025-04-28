"""測試 src.utils.model_utils 中的驗證函數。"""
# Standard library imports
from datetime import datetime, timedelta, timezone

# Third-party imports
import pytest

# Local application imports
from src.error.errors import ValidationError
from src.utils.enum_utils import (
    ArticleScrapeStatus,
    ScrapeMode,
    ScrapePhase,
)
from src.utils.log_utils import LoggerSetup  # 使用統一的 logger
from src.utils.model_utils import (
    validate_article_scrape_status,
    validate_boolean,
    validate_cron_expression,
    validate_datetime,
    validate_dict,
    validate_int,
    validate_list,
    validate_positive_float,
    validate_positive_int,
    validate_scrape_mode,
    validate_scrape_phase,
    validate_str,
    validate_task_args,
    validate_url,
)


logger = LoggerSetup.setup_logger(__name__)  # 使用統一的 logger


class TestValidateStr:
    """測試字串驗證功能。"""

    def test_valid_string(self):
        """測試有效的字串。"""
        validator = validate_str("name")
        assert validator("test") == "test"

    def test_string_with_whitespace(self):
        """測試包含前後空白的字串。"""
        validator = validate_str("name")
        assert validator("  test  ") == "test"

    def test_empty_string_not_required(self):
        """測試非必填時的空字串。"""
        validator = validate_str("name")
        assert validator("") is None

    def test_none_not_required(self):
        """測試非必填時的 None 值。"""
        validator = validate_str("name")
        assert validator(None) is None

    def test_empty_string_required(self):
        """測試必填時的空字串。"""
        validator = validate_str("name", required=True)
        with pytest.raises(ValidationError, match="name: 不能為空"):
            validator("")

    def test_none_required(self):
        """測試必填時的 None 值。"""
        validator = validate_str("name", required=True)
        with pytest.raises(ValidationError, match="name: 不能為 None"):
            validator(None)

    def test_max_length(self):
        """測試最大長度限制。"""
        validator = validate_str("name", max_length=5)
        assert validator("short") == "short"
        with pytest.raises(ValidationError, match="name: 長度不能超過 5 字元"):
            validator("toolong")

    def test_min_length(self):
        """測試最小長度限制。"""
        validator = validate_str("name", min_length=3)
        assert validator("long") == "long"
        with pytest.raises(ValidationError, match="name: 長度不能小於 3 字元"):
            validator("to")

    def test_regex_match(self):
        """測試符合正規表示式的字串。"""
        validator = validate_str("code", regex=r"^[A-Z]{2}-\d{3}$")
        assert validator("AB-123") == "AB-123"

    def test_regex_no_match(self):
        """測試不符合正規表示式的字串。"""
        validator = validate_str("code", regex=r"^[A-Z]{2}-\d{3}$")
        with pytest.raises(ValidationError, match="code: 不符合指定的格式"):
            validator("ab-123")

class TestValidateCronExpression:
    """測試 Cron 表達式驗證功能。"""

    def test_valid_cron(self):
        """測試有效的 Cron 表達式。"""
        validator = validate_cron_expression("schedule")
        assert validator("* * * * *") == "* * * * *"

    def test_invalid_cron(self):
        """測試無效的 Cron 表達式 (欄位數量錯誤)。"""
        validator = validate_cron_expression("schedule")
        with pytest.raises(ValidationError, match="schedule: Cron 表達式必須包含 5 個字段"):
            validator("invalid cron")

    def test_empty_cron_not_required(self):
        """測試非必填時的空 Cron 表達式。"""
        validator = validate_cron_expression("schedule")
        assert validator("") is None

    def test_none_cron_not_required(self):
        """測試非必填時的 None 值。"""
        validator = validate_cron_expression("schedule")
        assert validator(None) is None

    def test_empty_cron_required(self):
        """測試必填時的空 Cron 表達式。"""
        validator = validate_cron_expression("schedule", required=True)
        with pytest.raises(ValidationError, match="schedule: 不能為空"):
            validator("")

    def test_none_cron_required(self):
        """測試必填時的 None 值。"""
        validator = validate_cron_expression("schedule", required=True)
        with pytest.raises(ValidationError, match="schedule: 不能為 None"):
            validator(None)

    def test_cron_max_length(self):
        """測試 Cron 表達式最大長度限制。"""
        long_cron = "* * * * * " * 50
        validator = validate_cron_expression("schedule", max_length=100)
        with pytest.raises(ValidationError, match="schedule: 長度不能超過 100 字元"):
            validator(long_cron)

class TestValidateDatetime:
    """測試日期時間驗證功能。"""

    def test_valid_utc_datetime_string(self):
        """測試有效的 UTC 日期時間字串。"""
        validator = validate_datetime("timestamp")
        dt_str = "2025-03-30T08:00:00Z"
        expected_dt = datetime(2025, 3, 30, 8, 0, 0, tzinfo=timezone.utc)
        assert validator(dt_str) == expected_dt

    def test_valid_utc_datetime_object(self):
        """測試有效的 UTC datetime 物件。"""
        validator = validate_datetime("timestamp")
        dt_obj = datetime(2025, 3, 30, 8, 0, 0, tzinfo=timezone.utc)
        assert validator(dt_obj) == dt_obj

    def test_datetime_without_timezone(self):
        """測試不含時區資訊的 datetime 物件。"""
        validator = validate_datetime("timestamp")
        dt_naive = datetime(2025, 3, 30, 8, 0, 0)
        with pytest.raises(ValidationError, match="timestamp: 日期時間必須包含時區資訊。"):
            validator(dt_naive)

    def test_datetime_with_non_utc_timezone(self):
        """測試包含非 UTC 時區的 datetime 物件。"""
        validator = validate_datetime("timestamp")
        taiwan_tz = timezone(timedelta(hours=8))
        dt_non_utc = datetime(2025, 3, 30, 16, 0, 0, tzinfo=taiwan_tz)
        with pytest.raises(ValidationError, match="timestamp: 日期時間必須是 UTC 時區"):
            validator(dt_non_utc)

    def test_invalid_datetime_format(self):
        """測試無效的日期時間格式字串。"""
        validator = validate_datetime("timestamp")
        with pytest.raises(ValidationError, match="timestamp: 日期時間必須包含時區資訊。"):
            validator("2025-03-30 08:00:00")

    def test_empty_datetime_not_required(self):
        """測試非必填時的空日期時間字串。"""
        validator = validate_datetime("timestamp")
        with pytest.raises(ValidationError, match="timestamp: 不能為空"):
            validator("")

    def test_none_datetime_not_required(self):
        """測試非必填時的 None 值 (應返回 None)。"""
        validator = validate_datetime("timestamp", required=False)
        assert validator(None) is None

    def test_empty_datetime_required(self):
        """測試必填時的空日期時間字串。"""
        validator = validate_datetime("timestamp", required=True)
        with pytest.raises(ValidationError, match="timestamp: 不能為空"):
            validator("")

    def test_none_datetime_required(self):
        """測試必填時的 None 值。"""
        validator = validate_datetime("timestamp", required=True)
        with pytest.raises(ValidationError, match="timestamp: 不能為 None"):
            validator(None)

    def test_invalid_datetime_type(self):
        """測試無效的日期時間類型。"""
        validator = validate_datetime("timestamp")
        with pytest.raises(ValidationError, match="timestamp: 必須是字串或日期時間物件。"):
            validator(123)

class TestValidateUrl:
    """測試 URL 驗證功能。"""

    def test_valid_url_http(self):
        """測試有效的 HTTP URL。"""
        validator = validate_url("website")
        assert validator("http://example.com") == "http://example.com"

    def test_valid_url_https(self):
        """測試有效的 HTTPS URL。"""
        validator = validate_url("website")
        assert validator("https://example.com/path?query=value#fragment") == "https://example.com/path?query=value#fragment"

    def test_invalid_url_format(self):
        """測試無效的 URL 格式。"""
        validator = validate_url("website")
        with pytest.raises(ValidationError, match="website: 無效的 URL 格式: 'not a url'"):
            validator("not a url")

    def test_url_max_length(self):
        """測試 URL 最大長度限制。"""
        long_url = "https://example.com/" + "a" * 1000
        validator = validate_url("website", max_length=100)
        with pytest.raises(ValidationError, match="website: 長度不能超過 100 字元"):
            validator(long_url)

    def test_empty_url_not_required(self):
        """測試非必填時的空 URL。"""
        validator = validate_url("website")
        assert validator("") is None

    def test_none_url_not_required(self):
        """測試非必填時的 None 值。"""
        validator = validate_url("website")
        assert validator(None) is None

    def test_empty_url_required(self):
        """測試必填時的空 URL。"""
        validator = validate_url("website", required=True)
        with pytest.raises(ValidationError, match="website: URL不能為空"):
            validator("")

    def test_none_url_required(self):
        """測試必填時的 None 值。"""
        validator = validate_url("website", required=True)
        with pytest.raises(ValidationError, match="website: URL不能為空"):
            validator(None)

    def test_custom_regex_match(self):
        """測試符合自訂正規表示式的 URL。"""
        validator = validate_url("image", regex=r".*\.(jpg|png)$")
        assert validator("https://example.com/image.jpg") == "https://example.com/image.jpg"

    def test_custom_regex_no_match(self):
        """測試不符合自訂正規表示式的 URL。"""
        validator = validate_url("image", regex=r".*\.(jpg|png)$")
        with pytest.raises(ValidationError, match="image: URL 不符合提供的正則表達式"):
            validator("https://example.com/image.gif")

class TestValidateList:
    """測試列表驗證功能。"""

    def test_valid_list(self):
        """測試有效的列表。"""
        validator = validate_list("items")
        assert validator([1, 2, 3]) == [1, 2, 3]

    def test_empty_list_not_required(self):
        """測試非必填時的空列表。"""
        validator = validate_list("items", required=False, min_length=0)
        assert validator([]) == []

    def test_none_not_required(self):
        """測試非必填時的 None 值 (應引發錯誤，因列表不能為 None)。"""
        validator = validate_list("items", required=False)
        with pytest.raises(ValidationError, match="items: 必須是列表"):
             validator(None)

    def test_none_required(self):
        """測試必填時的 None 值。"""
        validator = validate_list("items", required=True)
        with pytest.raises(ValidationError, match="items: 不能為 None"):
            validator(None)

    def test_invalid_type(self):
        """測試非列表類型。"""
        validator = validate_list("items")
        with pytest.raises(ValidationError, match="items: 必須是列表"):
            validator("not a list")

    def test_type_validation(self):
        """測試列表元素類型驗證。"""
        validator = validate_list("items", type=str)
        assert validator(["a", "b", "c"]) == ["a", "b", "c"]
        with pytest.raises(ValidationError, match="items: 列表中的所有元素必須是 str"):
            validator(["a", 1, "c"])

    def test_min_length_validation(self):
        """測試最小長度驗證。"""
        validator = validate_list("items", min_length=2)
        assert validator([1, 2]) == [1, 2]
        with pytest.raises(ValidationError, match="items: 列表長度不能小於 2"):
            validator([1])

class TestValidateInt:
    """測試整數驗證功能。"""

    def test_valid_int(self):
        """測試有效的整數。"""
        validator = validate_int("count")
        assert validator(10) == 10

    def test_none_not_required(self):
        """測試非必填時的 None 值。"""
        validator = validate_int("count")
        assert validator(None) is None

    def test_none_required(self):
        """測試必填時的 None 值。"""
        validator = validate_int("count", required=True)
        with pytest.raises(ValidationError, match="count: 不能為 None"):
            validator(None)

    def test_invalid_type(self):
        """測試非整數類型。"""
        validator = validate_int("count")
        with pytest.raises(ValidationError, match="count: 必須是整數"):
            validator("not an int")
        with pytest.raises(ValidationError, match="count: 必須是整數"):
            validator(10.5)

class TestValidateDict:
    """測試字典驗證功能。"""

    def test_valid_dict(self):
        """測試有效的字典。"""
        validator = validate_dict("data")
        assert validator({"key": "value"}) == {"key": "value"}

    def test_none_not_required(self):
        """測試非必填時的 None 值 (應返回空字典)。"""
        validator = validate_dict("data", required=False)
        assert validator(None) == {}

    def test_none_required(self):
        """測試必填時的 None 值。"""
        validator = validate_dict("data")
        with pytest.raises(ValidationError, match="data: 必須是字典格式"):
            validator(None)

    def test_invalid_type(self):
        """測試非字典類型。"""
        validator = validate_dict("data")
        with pytest.raises(ValidationError, match="data: 必須是字典格式"):
            validator("not a dict")
        with pytest.raises(ValidationError, match="data: 必須是字典格式"):
            validator([1, 2, 3])

class TestValidateBoolean:
    """測試布爾值驗證功能。"""

    def test_valid_boolean(self):
        """測試有效的布爾值。"""
        validator = validate_boolean("flag")
        assert validator(True) is True
        assert validator(False) is False

    def test_string_conversion(self):
        """測試可接受的字串轉換為布爾值。"""
        validator = validate_boolean("flag")
        assert validator("true") is True
        assert validator("false") is False
        assert validator("yes") is True
        assert validator("no") is False
        assert validator("1") is True
        assert validator("0") is False

    def test_none_not_required(self):
        """測試非必填時的 None 值。"""
        validator = validate_boolean("flag")
        assert validator(None) is None

    def test_none_required(self):
        """測試必填時的 None 值。"""
        validator = validate_boolean("flag", required=True)
        with pytest.raises(ValidationError, match="flag: 不能為 None"):
            validator(None)

    def test_invalid_type(self):
        """測試無法轉換為布爾值的無效類型。"""
        validator = validate_boolean("flag")
        with pytest.raises(ValidationError, match="flag: 必須是布爾值"):
            validator("not a boolean")
        with pytest.raises(ValidationError, match="flag: 必須是布爾值"):
            validator(123)

class TestValidatePositiveInt:
    """測試正整數驗證功能。"""

    def test_valid_positive_int(self):
        """測試有效的正整數。"""
        validator = validate_positive_int("count")
        assert validator(10) == 10

    def test_zero_not_allowed(self):
        """測試不允許零值的情況。"""
        validator = validate_positive_int("count", is_zero_allowed=False)
        with pytest.raises(ValidationError, match="count: 必須是正整數且大於0"):
            validator(0)

    def test_zero_allowed(self):
        """測試允許零值的情況。"""
        validator = validate_positive_int("count", is_zero_allowed=True)
        assert validator(0) == 0

    def test_negative_value(self):
        """測試負數值。"""
        validator = validate_positive_int("count")
        with pytest.raises(ValidationError, match="count: 必須是正整數且大於0"):
            validator(-10)

    def test_string_conversion(self):
        """測試字串轉換為正整數。"""
        validator = validate_positive_int("count")
        assert validator("10") == 10

    def test_float_rejection(self):
        """測試拒絕浮點數輸入。"""
        validator = validate_positive_int("count")
        with pytest.raises(ValidationError, match="count: 必須是整數"):
            validator(10.5)
        with pytest.raises(ValidationError, match="count: 必須是整數"):
            validator("10.5")

    def test_none_not_required(self):
        """測試非必填時的 None 值 (應返回 0)。"""
        validator = validate_positive_int("count")
        assert validator(None) == 0

    def test_none_required(self):
        """測試必填時的 None 值。"""
        validator = validate_positive_int("count", required=True)
        with pytest.raises(ValidationError, match="count: 不能為空"):
            validator(None)

class TestValidatePositiveFloat:
    """測試正浮點數驗證功能。"""

    def test_valid_positive_float(self):
        """測試有效的正浮點數 (包括整數)。"""
        validator = validate_positive_float("value")
        assert validator(10.5) == 10.5
        assert validator(10) == 10.0  # 整數會被轉換為浮點數

    def test_zero_not_allowed(self):
        """測試不允許零值的情況。"""
        validator = validate_positive_float("value", is_zero_allowed=False)
        with pytest.raises(ValidationError, match="value: 必須是正數且大於0"):
            validator(0)

    def test_zero_allowed(self):
        """測試允許零值的情況。"""
        validator = validate_positive_float("value", is_zero_allowed=True)
        assert validator(0) == 0.0

    def test_negative_value(self):
        """測試負數值。"""
        validator = validate_positive_float("value")
        with pytest.raises(ValidationError, match="value: 必須是正數且大於0"):
            validator(-10.5)

    def test_none_not_required(self):
        """測試非必填時的 None 值 (應返回 0.0)。"""
        validator = validate_positive_float("value")
        assert validator(None) == 0.0

    def test_none_required(self):
        """測試必填時的 None 值。"""
        validator = validate_positive_float("value", required=True)
        with pytest.raises(ValidationError, match="value: 不能為空"):
            validator(None)

    def test_invalid_type(self):
        """測試非數值類型。"""
        validator = validate_positive_float("value")
        with pytest.raises(ValidationError, match="value: 必須是數值"):
            validator("not a number")

class TestValidateScrapePhase:
    """測試任務階段枚舉值驗證功能。"""

    def test_valid_enum(self):
        """測試有效的枚舉成員。"""
        validator = validate_scrape_phase("phase")
        assert validator(ScrapePhase.INIT) == ScrapePhase.INIT

    def test_valid_string(self):
        """測試有效的枚舉名稱字串。"""
        validator = validate_scrape_phase("phase")
        assert validator("init") == ScrapePhase.INIT
        assert validator("link_collection") == ScrapePhase.LINK_COLLECTION
        assert validator("content_scraping") == ScrapePhase.CONTENT_SCRAPING
        assert validator("completed") == ScrapePhase.COMPLETED

    def test_none_not_required(self):
        """測試非必填時的 None 值。"""
        validator = validate_scrape_phase("phase")
        assert validator(None) is None

    def test_none_required(self):
        """測試必填時的 None 值。"""
        validator = validate_scrape_phase("phase", required=True)
        with pytest.raises(ValidationError, match="phase: 不能為空"):
            validator(None)

    def test_invalid_value(self):
        """測試無效的枚舉值或字串。"""
        validator = validate_scrape_phase("phase")
        with pytest.raises(ValidationError, match="phase: 無效的枚舉值 'invalid_phase'，可用值: init, link_collection, content_scraping, failed, save_to_csv, save_to_database, completed, cancelled, unknown"):
            validator("invalid_phase")

class TestValidateScrapeMode:
    """測試抓取模式枚舉值驗證功能。"""

    def test_valid_enum(self):
        """測試有效的枚舉成員。"""
        validator = validate_scrape_mode("mode")
        assert validator(ScrapeMode.LINKS_ONLY) == ScrapeMode.LINKS_ONLY

    def test_valid_string(self):
        """測試有效的枚舉名稱字串。"""
        validator = validate_scrape_mode("mode")
        assert validator("links_only") == ScrapeMode.LINKS_ONLY
        assert validator("content_only") == ScrapeMode.CONTENT_ONLY
        assert validator("full_scrape") == ScrapeMode.FULL_SCRAPE

    def test_none_not_required(self):
        """測試非必填時的 None 值。"""
        validator = validate_scrape_mode("mode")
        assert validator(None) is None

    def test_none_required(self):
        """測試必填時的 None 值。"""
        validator = validate_scrape_mode("mode", required=True)
        with pytest.raises(ValidationError, match="mode: 不能為空"):
            validator(None)

    def test_invalid_value(self):
        """測試無效的枚舉值或字串。"""
        validator = validate_scrape_mode("mode")
        with pytest.raises(ValidationError, match="mode: 無效的枚舉值 'invalid_mode'，可用值: links_only, content_only, full_scrape"):
            validator("invalid_mode")

class TestValidateArticleScrapeStatus:
    """測試文章爬取狀態枚舉值驗證功能。"""

    def test_valid_enum(self):
        """測試有效的枚舉成員。"""
        validator = validate_article_scrape_status("status")
        assert validator(ArticleScrapeStatus.PENDING) == ArticleScrapeStatus.PENDING

    def test_valid_string(self):
        """測試有效的枚舉名稱字串。"""
        validator = validate_article_scrape_status("status")
        assert validator("pending") == ArticleScrapeStatus.PENDING
        assert validator("link_saved") == ArticleScrapeStatus.LINK_SAVED
        assert validator("content_scraped") == ArticleScrapeStatus.CONTENT_SCRAPED
        assert validator("failed") == ArticleScrapeStatus.FAILED

    def test_none_not_required(self):
        """測試非必填時的 None 值。"""
        validator = validate_article_scrape_status("status")
        assert validator(None) is None

    def test_none_required(self):
        """測試必填時的 None 值。"""
        validator = validate_article_scrape_status("status", required=True)
        with pytest.raises(ValidationError, match="status: 不能為空"):
            validator(None)

    def test_invalid_value(self):
        """測試無效的枚舉值或字串。"""
        validator = validate_article_scrape_status("status")
        with pytest.raises(ValidationError, match="status: 無效的枚舉值 'invalid_status'，可用值: pending, link_saved, partial_saved, content_scraped, failed"):
            validator("invalid_status")

class TestValidateTaskArgs:
    """測試任務參數字典驗證功能。"""

    @pytest.fixture
    def default_valid_args(self):
        """提供一組預設的有效參數字典。"""
        return {
            "scrape_mode": "full_scrape",
            "max_pages": 10,
            "num_articles": 20,
            "min_keywords": 5,
            "timeout": 30,
            "max_retries": 3,
            "retry_delay": 1.5,
            "ai_only": True,
            "save_to_csv": True,
            "save_to_database": True,
            "get_links_by_task_id": False,
            "is_test": False,
            "article_links": ["https://example.com/article1", "https://example.com/article2"],
            "save_partial_results_on_cancel": True,
            "save_partial_to_database": True
        }

    def test_valid_task_args(self, default_valid_args):
        """測試有效的任務參數字典。"""
        validator = validate_task_args("task_args")
        result = validator(default_valid_args)
        # 比較枚舉的值而不是枚舉本身
        expected_args = default_valid_args.copy()
        # expected_args['scrape_mode'] = expected_args['scrape_mode'] # 或者直接比較 .value
        assert result == expected_args
        # 或者更簡單，只比較轉換後的枚舉值的字串表示
        # assert result['scrape_mode'].value == default_valid_args['scrape_mode']
        # 或者比較除了 scrape_mode 以外的其他欄位
        # result_copy = result.copy()
        # default_copy = default_valid_args.copy()
        # del result_copy['scrape_mode']
        # del default_copy['scrape_mode']
        # assert result_copy == default_copy

    def test_none_not_required(self):
        """測試非必填時的 None 值 (應返回 None)。"""
        validator = validate_task_args("task_args")
        assert validator(None) is None # 根據 validate_task_args 實現，None 應返回 None

    def test_missing_required_field(self, default_valid_args):
        """測試缺少必填欄位 'scrape_mode'。"""
        validator = validate_task_args("task_args")
        invalid_args = default_valid_args.copy()
        del invalid_args["scrape_mode"]
        with pytest.raises(ValidationError, match="task_args.scrape_mode: 必填欄位不能缺少"):
            validator(invalid_args)

    def test_invalid_scrape_mode(self, default_valid_args):
        """測試無效的抓取模式值。"""
        validator = validate_task_args("task_args")
        invalid_args = default_valid_args.copy()
        invalid_args["scrape_mode"] = "invalid_mode"
        with pytest.raises(ValidationError, match="task_args.scrape_mode: scrape_mode: 無效的枚舉值 'invalid_mode'，可用值: links_only, content_only, full_scrape"):
            validator(invalid_args)

    def test_invalid_positive_int_param(self, default_valid_args):
        """測試無效的正整數參數 (max_pages < 0)。"""
        validator = validate_task_args("task_args")
        invalid_args = default_valid_args.copy()
        invalid_args["max_pages"] = -10
        with pytest.raises(ValidationError, match="task_args.max_pages: max_pages: 必須是正整數且大於0"):
            validator(invalid_args)

    def test_invalid_positive_float_param(self, default_valid_args):
        """測試無效的正浮點數參數 (retry_delay < 0)。"""
        validator = validate_task_args("task_args")
        invalid_args = default_valid_args.copy()
        invalid_args["retry_delay"] = -1.5
        with pytest.raises(ValidationError, match="task_args.retry_delay: retry_delay: 必須是正數且大於0"):
            validator(invalid_args)

    def test_invalid_boolean_param(self, default_valid_args):
        """測試無效的布爾參數值 (ai_only)。"""
        validator = validate_task_args("task_args")
        invalid_args = default_valid_args.copy()
        invalid_args["ai_only"] = "not_boolean"
        with pytest.raises(ValidationError, match="task_args.ai_only: 類型不匹配。期望類型: bool"):
            validator(invalid_args)

    def test_invalid_article_links_type(self, default_valid_args):
        """測試無效的文章連結列表類型。"""
        validator = validate_task_args("task_args")
        invalid_args = default_valid_args.copy()
        invalid_args["article_links"] = "not_a_list"
        with pytest.raises(ValidationError, match="task_args.article_links: 類型不匹配。期望類型: list"):
            validator(invalid_args)

    def test_invalid_article_link_item(self, default_valid_args):
        """測試文章連結列表中包含無效的 URL。"""
        validator = validate_task_args("task_args")
        invalid_args = default_valid_args.copy()
        invalid_args["article_links"] = ["https://example.com", "not a url"]
        with pytest.raises(ValidationError, match="task_args.article_links item: 無效的 URL 格式: 'not a url'"):
            validator(invalid_args)

    def test_missing_optional_field(self, default_valid_args):
        """測試缺少可選欄位 (例如 min_keywords)，應能正常驗證。"""
        validator = validate_task_args("task_args")
        args = default_valid_args.copy()
        del args["min_keywords"] # min_keywords 是可選的
        result = validator(args)
        # 檢查驗證後的結果是否包含預期的預設值或 None
        # 假設 validate_task_args 在參數有效時返回字典
        assert result is not None # 確保 result 不是 None
        assert "min_keywords" not in result or result["min_keywords"] is None # 或預設值
        # 確保其他欄位仍然存在且正確
        assert result["scrape_mode"] == args["scrape_mode"]

    def test_extra_field(self, default_valid_args):
        """測試包含額外未定義欄位的字典。"""
        validator = validate_task_args("task_args")
        args = default_valid_args.copy()
        args["extra_param"] = "some_value"
        # 假設 validate_task_args 會忽略額外欄位
        result = validator(args)
        assert result is not None # 確保 result 不是 None
        assert "extra_param" not in result # 驗證後的結果不應包含額外欄位
        assert result["scrape_mode"] == args["scrape_mode"]