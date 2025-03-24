import pytest
from datetime import datetime, timezone, timedelta
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.error.errors import ValidationError

class TestCrawlerTaskHistoryModel:
    """CrawlerTaskHistory 模型的測試類"""
    
    def test_crawler_task_history_creation_with_required_fields(self):
        """測試使用必填欄位創建 CrawlerTaskHistory"""
        history = CrawlerTaskHistory(
            task_id=1
        )
        
        assert history.task_id == 1
        assert history.start_time is not None
        assert history.end_time is None
        assert history.success is False
        assert history.message is None
        assert history.articles_count == 0
    
    def test_default_values(self):
        """測試默認值設置"""
        history = CrawlerTaskHistory(
            task_id=1
        )
        
        assert history.success is False  # 測試默認值為 False
        assert history.articles_count == 0  # 測試默認值為 0
        assert history.start_time is not None
        assert isinstance(history.start_time, datetime)
    
    def test_start_time_cannot_update(self):
        """測試 start_time 屬性無法更新"""
        history = CrawlerTaskHistory(
            task_id=1
        )
        
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
    
    def test_crawler_task_history_repr(self):
        """測試 CrawlerTaskHistory 的 __repr__ 方法"""
        test_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        history = CrawlerTaskHistory(
            id=1,
            task_id=2,
            start_time=test_time,
            success=True
        )
        
        expected_repr = f"<CrawlerTaskHistory(id=1, task_id=2, start_time={test_time}, success=True)>"
        assert repr(history) == expected_repr
    
    def test_to_dict_method(self):
        """測試 to_dict 方法"""
        start_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2023, 1, 1, 12, 30, 0, tzinfo=timezone.utc)
        
        history = CrawlerTaskHistory(
            id=1,
            task_id=2,
            start_time=start_time,
            end_time=end_time,
            success=True,
            message="抓取完成",
            articles_count=10
        )
        
        result_dict = history.to_dict()
        
        assert result_dict['id'] == 1
        assert result_dict['task_id'] == 2
        assert result_dict['start_time'] == start_time
        assert result_dict['end_time'] == end_time
        assert result_dict['success'] is True
        assert result_dict['message'] == "抓取完成"
        assert result_dict['articles_count'] == 10
        assert result_dict['duration'] == 1800  # 30分鐘 = 1800秒
    
    def test_to_dict_without_end_time(self):
        """測試沒有結束時間時的 to_dict 方法"""
        start_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        history = CrawlerTaskHistory(
            id=1,
            task_id=2,
            start_time=start_time,
            success=False,
            articles_count=0
        )
        
        result_dict = history.to_dict()
        
        assert result_dict['end_time'] is None
        assert result_dict['duration'] is None
    
    def test_task_id_is_required(self):
        """測試 task_id 為必填欄位"""
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTaskHistory()
        
        assert "task_id is required" in str(exc_info.value)
    
    def test_update_allowed_fields(self):
        """測試允許更新的欄位"""
        history = CrawlerTaskHistory(task_id=1)
        
        end_time = datetime.now(timezone.utc)
        history.end_time = end_time
        history.success = True
        history.message = "任務完成"
        history.articles_count = 15
        
        assert history.end_time == end_time
        assert history.success is True
        assert history.message == "任務完成"
        assert history.articles_count == 15 
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.error.errors import ValidationError