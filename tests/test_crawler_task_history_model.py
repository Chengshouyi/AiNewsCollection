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
        
        # 測試必填欄位
        assert history.task_id == 1
        
        # 測試自動生成的欄位
        assert history.start_time is not None
        assert isinstance(history.start_time, datetime)
        
        # 測試預設值
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
    
    def test_task_id_required(self):
        """測試 task_id 是必填欄位"""
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTaskHistory()
        assert "task_id is required" in str(exc_info.value)
    
    def test_start_time_cannot_update(self):
        """測試 start_time 屬性無法更新"""
        history = CrawlerTaskHistory(task_id=1)
        original_time = history.start_time
        
        with pytest.raises(ValidationError) as exc_info:
            history.start_time = datetime.now(timezone.utc)
        
        assert "start_time cannot be updated" in str(exc_info.value)
        assert history.start_time == original_time
    
    def test_id_cannot_update(self):
        """測試 id 屬性無法更新"""
        history = CrawlerTaskHistory(
            id=1,
            task_id=1
        )
        
        with pytest.raises(ValidationError) as exc_info:
            history.id = 2
        
        assert "id cannot be updated" in str(exc_info.value)
        assert history.id == 1
    
    def test_history_repr(self):
        """測試 CrawlerTaskHistory 的 __repr__ 方法"""
        now = datetime.now(timezone.utc)
        history = CrawlerTaskHistory(
            id=1,
            task_id=1,
            start_time=now,
            success=False
        )
        
        expected_repr = (
            f"<CrawlerTaskHistory("
            f"id=1, "
            f"task_id=1, "
            f"start_time={now}, "
            f"success=False"
            f")>"
        )
        
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
        
        # 驗證所有欄位都在字典中
        expected_keys = {
            'id', 'task_id', 'start_time', 'end_time',
            'success', 'message', 'articles_count', 'duration'
        }
        
        assert set(history_dict.keys()) == expected_keys
        
        # 測試 duration 計算
        assert history_dict['duration'] == 0.0  # 因為 start_time 和 end_time 相同
    
    def test_duration_calculation(self):
        """測試持續時間計算"""
        start_time = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 1, 10, 1, tzinfo=timezone.utc)
        
        history = CrawlerTaskHistory(
            task_id=1,
            start_time=start_time,
            end_time=end_time
        )
        
        history_dict = history.to_dict()
        assert history_dict['duration'] == 60.0  # 1分鐘 = 60秒
    
    def test_duration_with_no_end_time(self):
        """測試未結束任務的持續時間"""
        history = CrawlerTaskHistory(task_id=1)
        history_dict = history.to_dict()
        assert history_dict['duration'] is None