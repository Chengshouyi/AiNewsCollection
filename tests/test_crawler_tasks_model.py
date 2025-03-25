import pytest
from datetime import datetime, timezone
from src.models.crawler_tasks_model import CrawlerTasks

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
        
        # 測試必填欄位
        assert task.crawler_id == 1
        assert task.is_auto is True
        assert task.ai_only is False
        assert task.notes == "測試任務"
        
        # 測試自動生成的欄位
        assert task.created_at is not None
        assert task.updated_at is None
        
        # 測試預設值
        assert task.max_pages == 3
        assert task.num_articles == 10
        assert task.min_keywords == 3
        assert task.fetch_details is False
        
        # 測試可選欄位預設值
        assert task.last_run_at is None
        assert task.last_run_success is None
        assert task.last_run_message is None
        assert task.schedule is None
    
    def test_default_values(self):
        """測試默認值設置"""
        task = CrawlerTasks(crawler_id=1)
        
        # 測試布林欄位預設值
        assert task.is_auto is True
        assert task.ai_only is False
        assert task.fetch_details is False
        
        # 測試數值欄位預設值
        assert task.max_pages == 3
        assert task.num_articles == 10
        assert task.min_keywords == 3
        
        # 測試可選欄位預設值
        assert task.notes is None
        assert task.schedule is None
        assert task.last_run_at is None
        assert task.last_run_success is None
        assert task.last_run_message is None
    
    def test_crawler_tasks_repr(self):
        """測試 CrawlerTasks 的 __repr__ 方法"""
        task = CrawlerTasks(
            id=1,
            crawler_id=1
        )
        
        expected_repr = "<CrawlerTask(id=1, crawler_id=1)>"
        assert repr(task) == expected_repr
    
    def test_field_updates(self):
        """測試欄位更新"""
        task = CrawlerTasks(crawler_id=1)
        
        # 測試布林欄位更新
        task.is_auto = False
        task.ai_only = True
        task.fetch_details = True
        assert task.is_auto is False
        assert task.ai_only is True
        assert task.fetch_details is True
        
        # 測試數值欄位更新
        task.max_pages = 5
        task.num_articles = 20
        task.min_keywords = 4
        assert task.max_pages == 5
        assert task.num_articles == 20
        assert task.min_keywords == 4
        
        # 測試文字欄位更新
        task.notes = "更新的備註"
        task.schedule = "hourly"
        task.last_run_message = "執行成功"
        assert task.notes == "更新的備註"
        assert task.schedule == "hourly"
        assert task.last_run_message == "執行成功"
    
    def test_to_dict(self):
        """測試 to_dict 方法"""
        task = CrawlerTasks(
            id=1,
            crawler_id=1,
            notes="測試任務"
        )
        
        task_dict = task.to_dict()
        
        # 驗證所有欄位都在字典中
        expected_keys = {
            'id', 'crawler_id', 'is_auto', 'ai_only', 'notes',
            'max_pages', 'num_articles', 'min_keywords', 'fetch_details',
            'created_at', 'updated_at', 'last_run_at', 'last_run_success',
            'last_run_message', 'schedule'
        }
        
        assert set(task_dict.keys()) == expected_keys 