import pytest
from datetime import datetime, timezone
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.error.errors import ValidationError
from src.utils.enum_utils import TaskStatus

class TestCrawlerTaskHistoryModel:
    """CrawlerTaskHistory 模型的測試類"""
    
    def test_history_creation_with_required_fields(self):
        """測試使用必填欄位創建 CrawlerTaskHistory"""
        history = CrawlerTaskHistory(
            task_id=1
        )
        
        assert history.task_id == 1
        assert history.start_time is None
        assert history.success is None
        assert history.articles_count is None
        assert history.end_time is None
        assert history.message is None
        assert history.task_status == TaskStatus.INIT  # 檢查預設狀態
    
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
            task_status=TaskStatus.COMPLETED
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
        
        # 測試明確設置 task_status
        history2 = CrawlerTaskHistory(task_id=1, task_status=TaskStatus.RUNNING)
        assert history2.task_status == TaskStatus.RUNNING
    
    def test_history_repr(self):
        """測試 CrawlerTaskHistory 的 __repr__ 方法"""
        now = datetime.now(timezone.utc)
        history = CrawlerTaskHistory(
            id=1,
            task_id=1,
            start_time=now
        )
        
        expected_repr = f"<CrawlerTaskHistory(id=1, task_id=1, start_time='{now}')>"
        assert repr(history) == expected_repr
    
    def test_field_updates(self):
        """測試可更新欄位"""
        history = CrawlerTaskHistory(task_id=1)
        
        # 測試布林欄位更新
        history.success = True
        assert history.success is True
        
        # 測試數值欄位更新
        history.articles_count = 5
        assert history.articles_count == 5
        
        # 測試文字欄位更新
        history.message = "更新的訊息"
        assert history.message == "更新的訊息"
        
        # 測試時間欄位更新
        now = datetime.now(timezone.utc)
        history.end_time = now
        assert history.end_time == now
        
        # 測試任務狀態欄位更新
        history.task_status = TaskStatus.RUNNING
        assert history.task_status == TaskStatus.RUNNING
    
    def test_relationship_attributes(self):
        """測試關聯屬性存在"""
        history = CrawlerTaskHistory(task_id=1)
        assert hasattr(history, 'task')
    
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
            task_status=TaskStatus.COMPLETED
        )
        
        history_dict = history.to_dict()
        expected_keys = {
            'id', 'created_at', 'updated_at', 'task_id', 'start_time', 'end_time',
            'success', 'message', 'articles_count', 'duration', 'task_status'
        }
        
        assert set(history_dict.keys()) == expected_keys
        assert history_dict['duration'] == 0.0  # start_time 和 end_time 相同
        assert history_dict['task_status'] == TaskStatus.COMPLETED.value
        
        # 測試沒有 end_time 的情況
        history.end_time = None
        assert history.to_dict()['duration'] is None
    

    def test_history_utc_datetime_conversion(self):
        """測試 CrawlerTaskHistory 的 start_time 和 end_time 欄位 UTC 時間轉換"""
        from datetime import timedelta
        
        # 測試 1: 傳入無時區資訊的 datetime (naive datetime)
        naive_time = datetime(2025, 3, 28, 12, 0, 0)  # 無時區資訊
        history = CrawlerTaskHistory(
            task_id=1,
            start_time=naive_time,
            end_time=naive_time
        )
        if history.start_time is not None:
            assert history.start_time.tzinfo == timezone.utc  # 確認有 UTC 時區
        assert history.start_time == naive_time.replace(tzinfo=timezone.utc)  # 確認值正確

        if history.end_time is not None:
            assert history.end_time.tzinfo == timezone.utc  # 確認有 UTC 時區
        assert history.end_time == naive_time.replace(tzinfo=timezone.utc)  # 確認值正確

        # 測試 2: 傳入帶非 UTC 時區的 datetime (aware datetime, UTC+8)
        utc_plus_8_time = datetime(2025, 3, 28, 14, 0, 0, tzinfo=timezone(timedelta(hours=8)))
        history.start_time = utc_plus_8_time
        history.end_time = utc_plus_8_time
        expected_utc_time = datetime(2025, 3, 28, 6, 0, 0, tzinfo=timezone.utc)  # UTC+8 轉 UTC
        assert history.start_time.tzinfo == timezone.utc  # 確認轉換為 UTC 時區
        assert history.start_time == expected_utc_time  # 確認時間正確轉換

        assert history.end_time.tzinfo == timezone.utc  # 確認轉換為 UTC 時區
        assert history.end_time == expected_utc_time  # 確認時間正確轉換

        # 測試 3: 傳入已是 UTC 的 datetime，確保不變
        utc_time = datetime(2025, 3, 28, 12, 0, 0, tzinfo=timezone.utc)
        history.start_time = utc_time
        history.end_time = utc_time
        assert history.start_time == utc_time  # 確認值未被改變
        assert history.end_time == utc_time  # 確認值未被改變

        # 測試 4: 確認非監聽欄位（如 title）不觸發轉換邏輯
        history.message = "新訊息"
        assert history.start_time == utc_time  # start_time 不受影響
        assert history.end_time == utc_time  # end_time 不受影響


