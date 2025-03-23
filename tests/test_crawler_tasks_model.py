import pytest
from datetime import datetime, timezone
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawlers_model import Crawlers
from src.error.errors import ValidationError

class TestCrawlerTasksModel:
    """CrawlerTasks 模型的測試類"""
    
    def test_crawler_tasks_creation_with_required_fields(self):
        """測試使用必填欄位創建 CrawlerTasks"""
        task = CrawlerTasks(
            crawler_id=1,
            is_auto=True,
            ai_only=False,
            notes="測試任務"
        )
        
        assert task.crawler_id == 1
        assert task.is_auto is True
        assert task.ai_only is False
        assert task.notes == "測試任務"
        assert task.created_at is not None
        assert task.updated_at is None
    
    def test_default_values(self):
        """測試默認值設置"""
        task = CrawlerTasks(
            crawler_id=1
        )
        
        assert task.is_auto is True  # 測試 is_auto 默認值為 True
        assert task.ai_only is False  # 測試 ai_only 默認值為 False
        assert task.notes is None  # 測試 notes 默認值為 None
        assert task.created_at is not None
        assert isinstance(task.created_at, datetime)
    
    def test_created_at_cannot_update(self):
        """測試 created_at 屬性無法更新"""
        task = CrawlerTasks(
            crawler_id=1,
            is_auto=True
        )
        
        original_time = task.created_at
        
        with pytest.raises(ValidationError) as exc_info:
            task.created_at = datetime.now(timezone.utc)
        
        assert "created_at cannot be updated" in str(exc_info.value)
        assert task.created_at == original_time
    
    def test_id_cannot_update(self):
        """測試 id 屬性無法更新"""
        task = CrawlerTasks(
            id=1,
            crawler_id=1,
            is_auto=True
        )
        
        with pytest.raises(ValidationError) as exc_info:
            task.id = 2
        
        assert "id cannot be updated" in str(exc_info.value)
        assert task.id == 1
    
    def test_crawler_tasks_repr(self):
        """測試 CrawlerTasks 的 __repr__ 方法"""
        task = CrawlerTasks(
            id=1,
            crawler_id=1,
            is_auto=True,
            ai_only=False
        )
        
        expected_repr = "<CrawlerTasks(id=1, crawler_id=1, is_auto=True, ai_only=False)>"
        assert repr(task) == expected_repr
    
    def test_boolean_field_updates(self):
        """測試布林欄位的更新"""
        task = CrawlerTasks(
            crawler_id=1,
            is_auto=True,
            ai_only=False
        )
        
        task.is_auto = False
        task.ai_only = True
        
        assert task.is_auto is False
        assert task.ai_only is True
    
    def test_notes_update(self):
        """測試備註欄位的更新"""
        task = CrawlerTasks(
            crawler_id=1,
            notes="原始備註"
        )
        
        task.notes = "更新的備註"
        assert task.notes == "更新的備註"
    
    def test_crawler_id_required(self):
        """測試 crawler_id 是必填欄位"""
        with pytest.raises(ValidationError):
            CrawlerTasks()
    
    def test_relationship_attribute_exists(self):
        """測試關聯屬性存在"""
        task = CrawlerTasks(crawler_id=1)
        assert hasattr(task, 'crawler') 