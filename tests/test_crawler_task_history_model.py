import pytest
from datetime import datetime, timezone
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.error.errors import ValidationError

class TestCrawlerTaskHistoryModel:
    """CrawlerTaskHistory 模型的測試類"""
    
    def test_history_creation_with_required_fields(self):
        """測試使用必填欄位創建 CrawlerTaskHistory"""
        history = CrawlerTaskHistory(
            task_id=1
        )
        
        assert history.task_id == 1
        assert history.start_time is not None
        assert isinstance(history.start_time, datetime)
        assert history.success is False
        assert history.articles_count == 0
        assert history.end_time is None
        assert history.message is None
    
    def test_history_creation_with_all_fields(self):
        """測試使用所有欄位創建 CrawlerTaskHistory"""
        now = datetime.now(timezone.utc)
        history = CrawlerTaskHistory(
            task_id=1,
            start_time=now,
            end_time=now,
            success=True,
            message="測試完成",
            articles_count=10
        )
        
        assert history.task_id == 1
        assert history.start_time == now
        assert history.end_time == now
        assert history.success is True
        assert history.message == "測試完成"
        assert history.articles_count == 10
    
    
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
            articles_count=10
        )
        
        history_dict = history.to_dict()
        expected_keys = {
            'id', 'task_id', 'start_time', 'end_time',
            'success', 'message', 'articles_count', 'duration'
        }
        
        assert set(history_dict.keys()) == expected_keys
        assert history_dict['duration'] == 0.0  # start_time 和 end_time 相同
        
        # 測試沒有 end_time 的情況
        history.end_time = None
        assert history.to_dict()['duration'] is None