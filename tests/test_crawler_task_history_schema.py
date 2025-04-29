"""本模組測試 CrawlerTaskHistoryCreateSchema 和 CrawlerTaskHistoryUpdateSchema 的功能，包括欄位驗證和資料轉換。"""

# flake8: noqa: F811
# pylint: disable=redefined-outer-name

from datetime import datetime, timedelta, timezone

import pytest

from src.error.errors import ValidationError
from src.models.crawler_task_history_schema import (
    CrawlerTaskHistoryCreateSchema,
    CrawlerTaskHistoryUpdateSchema,
)
from src.utils.enum_utils import TaskStatus
from src.utils.log_utils import LoggerSetup

logger = LoggerSetup.setup_logger(__name__)


class TestCrawlerTaskHistoryCreateSchema:
    """CrawlerTaskHistoryCreateSchema 的測試類"""

    def test_valid_minimal_create(self):
        """測試最小化有效創建"""
        data = {"task_id": 1}
        schema = CrawlerTaskHistoryCreateSchema.model_validate(data)

        assert schema.task_id == 1
        assert schema.start_time is None
        assert schema.end_time is None
        assert schema.success is None
        assert schema.message is None
        assert schema.articles_count is None
        assert schema.task_status == TaskStatus.INIT

    def test_valid_complete_create(self):
        """測試完整有效創建"""
        now = datetime.now(timezone.utc)
        data = {
            "task_id": 1,
            "start_time": now,
            "end_time": now,
            "success": True,
            "message": "測試訊息",
            "articles_count": 10,
            "task_status": TaskStatus.COMPLETED,
        }
        schema = CrawlerTaskHistoryCreateSchema.model_validate(data)

        assert schema.task_id == 1
        assert schema.start_time == now
        assert schema.end_time == now
        assert schema.success is True
        assert schema.message == "測試訊息"
        assert schema.articles_count == 10
        assert schema.task_status == TaskStatus.COMPLETED

    def test_task_id_validation(self):
        """測試 task_id 驗證"""
        invalid_cases = [
            ({"task_id": 0}, "task_id: 必須是正整數且大於0"),
            ({"task_id": -1}, "task_id: 必須是正整數且大於0"),
            ({"task_id": "abc"}, "task_id: 必須是整數"),
            ({}, "以下必填欄位缺失或值為空/空白: task_id"),
        ]

        for data, expected_error in invalid_cases:
            with pytest.raises(ValidationError) as exc_info:
                CrawlerTaskHistoryCreateSchema.model_validate(data)
            assert expected_error in str(exc_info.value)

    def test_articles_count_validation(self):
        """測試 articles_count 驗證"""
        invalid_cases = [
            (
                {"task_id": 1, "articles_count": -1},
                "articles_count: 必須是正整數且大於等於0",
            ),
            ({"task_id": 1, "articles_count": "abc"}, "articles_count: 必須是整數"),
            ({"task_id": 1, "articles_count": 1.5}, "articles_count: 必須是整數"),
        ]

        for data, expected_error in invalid_cases:
            with pytest.raises(ValidationError) as exc_info:
                CrawlerTaskHistoryCreateSchema.model_validate(data)
            assert expected_error in str(exc_info.value)

    def test_datetime_validation(self):
        """測試日期時間驗證"""
        invalid_cases = [
            (
                {"task_id": 1, "start_time": "invalid-date"},
                "start_time: 無效的日期時間格式",
            ),
            (
                {"task_id": 1, "end_time": "invalid-date"},
                "end_time: 無效的日期時間格式",
            ),
            ({"task_id": 1, "start_time": 123}, "start_time: 必須是字串或日期時間"),
            ({"task_id": 1, "end_time": 123}, "end_time: 必須是字串或日期時間"),
            (
                {
                    "task_id": 1,
                    "start_time": datetime(
                        2025, 3, 28, 14, 0, 0, tzinfo=timezone(timedelta(hours=8))
                    ),
                },
                "start_time: 日期時間必須是 UTC 時區",
            ),
            (
                {
                    "task_id": 1,
                    "end_time": datetime(
                        2025, 3, 28, 14, 0, 0, tzinfo=timezone(timedelta(hours=8))
                    ),
                },
                "end_time: 日期時間必須是 UTC 時區",
            ),
        ]

        for data, expected_error in invalid_cases:
            with pytest.raises(ValidationError) as exc_info:
                CrawlerTaskHistoryCreateSchema.model_validate(data)
            assert expected_error in str(exc_info.value)

    def test_task_status_validation(self):
        """測試任務狀態驗證"""
        invalid_cases = [
            (
                {"task_id": 1, "task_status": "invalid_status"},
                "task_status: 無效的枚舉值",
            ),
            ({"task_id": 1, "task_status": 123}, "task_status: 無效的輸入類型"),
        ]

        for data, expected_error in invalid_cases:
            with pytest.raises(ValidationError) as exc_info:
                CrawlerTaskHistoryCreateSchema.model_validate(data)
            assert expected_error in str(exc_info.value)


class TestCrawlerTaskHistoryUpdateSchema:
    """CrawlerTaskHistoryUpdateSchema 的測試類"""

    def test_valid_minimal_update(self):
        """測試最小化有效更新"""
        data = {"success": True}
        schema = CrawlerTaskHistoryUpdateSchema.model_validate(data)
        assert schema.success is True
        assert schema.end_time is None
        assert schema.message is None
        assert schema.articles_count is None
        assert schema.task_status is None

    def test_valid_complete_update(self):
        """測試完整有效更新"""
        now = datetime.now(timezone.utc)
        data = {
            "end_time": now,
            "start_time": now,
            "success": True,
            "message": "更新訊息",
            "articles_count": 20,
            "task_status": TaskStatus.COMPLETED,
        }
        schema = CrawlerTaskHistoryUpdateSchema.model_validate(data)

        assert schema.end_time == now
        assert schema.start_time == now
        assert schema.success is True
        assert schema.message == "更新訊息"
        assert schema.articles_count == 20
        assert schema.task_status == TaskStatus.COMPLETED

    def test_immutable_fields_update(self):
        """測試不可變欄位更新"""
        immutable_fields = [
            ({"id": 1}, "不允許更新 id 欄位"),
            ({"created_at": datetime.now(timezone.utc)}, "不允許更新 created_at 欄位"),
            ({"task_id": 1}, "不允許更新 task_id 欄位"),
        ]

        for data, expected_error in immutable_fields:
            with pytest.raises(ValidationError) as exc_info:
                CrawlerTaskHistoryUpdateSchema.model_validate(data)
            assert expected_error in str(exc_info.value)

    def test_empty_update(self):
        """測試空更新"""
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTaskHistoryUpdateSchema.model_validate({})
        assert "必須提供至少一個要更新的欄位" in str(exc_info.value)

    def test_update_field_validations(self):
        """測試更新欄位驗證"""
        invalid_cases = [
            ({"articles_count": -1}, "articles_count: 必須是正整數且大於等於0"),
            ({"articles_count": "abc"}, "articles_count: 必須是整數"),
            ({"end_time": "invalid-date"}, "end_time: 無效的日期時間格式"),
            ({"message": "a" * 65537}, "message: 長度不能超過 65536 字元"),
            ({"task_status": "invalid_status"}, "task_status: 無效的枚舉值"),
        ]

        for data, expected_error in invalid_cases:
            with pytest.raises(ValidationError) as exc_info:
                CrawlerTaskHistoryUpdateSchema.model_validate(data)
            assert expected_error in str(exc_info.value)
