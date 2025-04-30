"""本模組測試 CrawlerTaskHistory 模型的功能，包括模型創建、欄位驗證、時間轉換等功能。"""

# flake8: noqa: F811
# pylint: disable=redefined-outer-name

import logging
from datetime import datetime, timezone, timedelta

import pytest

from src.error.errors import ValidationError
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.utils.enum_utils import TaskStatus


logger = logging.getLogger(__name__)  # 使用統一的 logger


class TestCrawlerTaskHistoryModel:
    """CrawlerTaskHistory 模型的測試類"""

    def test_history_creation_with_required_fields(self):
        """測試使用必填欄位創建 CrawlerTaskHistory"""
        history = CrawlerTaskHistory(task_id=1)

        assert history.task_id == 1
        assert history.start_time is None
        assert history.success is None
        assert history.articles_count is None
        assert history.end_time is None
        assert history.message is None
        assert history.task_status == TaskStatus.INIT

    def test_history_creation_with_all_fields(self):
        """測試使用所有欄位創建 CrawlerTaskHistory"""
        now = datetime.now(timezone.utc)
        history = CrawlerTaskHistory(
            task_id=1,
            start_time=now,
            end_time=now,
            success=True,
            message="測試完成",
            articles_count=10,
            task_status=TaskStatus.COMPLETED,
        )

        assert history.task_id == 1
        assert history.start_time == now
        assert history.end_time == now
        assert history.success is True
        assert history.message == "測試完成"
        assert history.articles_count == 10
        assert history.task_status == TaskStatus.COMPLETED

    def test_task_status_default(self):
        """測試 task_status 的預設值設置"""
        history = CrawlerTaskHistory(task_id=1)
        assert history.task_status == TaskStatus.INIT

        history2 = CrawlerTaskHistory(task_id=1, task_status=TaskStatus.RUNNING)
        assert history2.task_status == TaskStatus.RUNNING

    def test_history_repr(self):
        """測試 CrawlerTaskHistory 的 __repr__ 方法"""
        now = datetime.now(timezone.utc)
        history = CrawlerTaskHistory(id=1, task_id=1, start_time=now)

        expected_repr = f"<CrawlerTaskHistory(id=1, task_id=1, start_time='{now}')>"
        assert repr(history) == expected_repr

    def test_field_updates(self):
        """測試可更新欄位"""
        history = CrawlerTaskHistory(task_id=1)

        history.success = True
        assert history.success is True

        history.articles_count = 5
        assert history.articles_count == 5

        history.message = "更新的訊息"
        assert history.message == "更新的訊息"

        now = datetime.now(timezone.utc)
        history.end_time = now
        assert history.end_time == now

        history.task_status = TaskStatus.RUNNING
        assert history.task_status == TaskStatus.RUNNING

    def test_relationship_attributes(self):
        """測試關聯屬性存在"""
        history = CrawlerTaskHistory(task_id=1)
        assert hasattr(history, "task")

    def test_to_dict(self):
        """測試 to_dict 方法"""
        now = datetime.now(timezone.utc)
        history = CrawlerTaskHistory(
            id=1,
            task_id=1,
            start_time=now,
            end_time=now,
            success=True,
            message="測試完成",
            articles_count=10,
            task_status=TaskStatus.COMPLETED,
        )

        history_dict = history.to_dict()
        expected_keys = {
            "id",
            "created_at",
            "updated_at",
            "task_id",
            "start_time",
            "end_time",
            "success",
            "message",
            "articles_count",
            "duration",
            "task_status",
        }

        assert set(history_dict.keys()) == expected_keys
        assert history_dict["duration"] == 0.0
        assert history_dict["task_status"] == TaskStatus.COMPLETED.value

        history.end_time = None
        assert history.to_dict()["duration"] is None

    def test_history_utc_datetime_conversion(self):
        """測試 CrawlerTaskHistory 的 start_time 和 end_time 欄位 UTC 時間轉換"""
        naive_time = datetime(2025, 3, 28, 12, 0, 0)
        history = CrawlerTaskHistory(
            task_id=1, start_time=naive_time, end_time=naive_time
        )
        if history.start_time is not None:
            assert history.start_time.tzinfo == timezone.utc
        assert history.start_time == naive_time.replace(tzinfo=timezone.utc)

        if history.end_time is not None:
            assert history.end_time.tzinfo == timezone.utc
        assert history.end_time == naive_time.replace(tzinfo=timezone.utc)

        utc_plus_8_time = datetime(
            2025, 3, 28, 14, 0, 0, tzinfo=timezone(timedelta(hours=8))
        )
        history.start_time = utc_plus_8_time
        history.end_time = utc_plus_8_time
        expected_utc_time = datetime(2025, 3, 28, 6, 0, 0, tzinfo=timezone.utc)
        assert history.start_time.tzinfo == timezone.utc
        assert history.start_time == expected_utc_time

        assert history.end_time.tzinfo == timezone.utc
        assert history.end_time == expected_utc_time

        utc_time = datetime(2025, 3, 28, 12, 0, 0, tzinfo=timezone.utc)
        history.start_time = utc_time
        history.end_time = utc_time
        assert history.start_time == utc_time
        assert history.end_time == utc_time

        history.message = "新訊息"
        assert history.start_time == utc_time
        assert history.end_time == utc_time
