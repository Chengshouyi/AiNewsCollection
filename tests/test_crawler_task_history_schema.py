import pytest
from datetime import datetime, timezone
from src.models.crawler_task_history_schema import (
    CrawlerTaskHistoryCreateSchema,
    CrawlerTaskHistoryUpdateSchema
)
from src.error.errors import ValidationError

class TestCrawlerTaskHistoryCreateSchema:
    """CrawlerTaskHistoryCreateSchema 的測試類"""
    
    def test_valid_minimal_create(self):
        """測試最小化有效創建"""
        data = {
            "task_id": 1
        }
        schema = CrawlerTaskHistoryCreateSchema.model_validate(data)
        
        assert schema.task_id == 1
        assert isinstance(schema.start_time, datetime)
        assert schema.end_time is None
        assert schema.success is False
        assert schema.message is None
        assert schema.articles_count == 0
    
    def test_valid_complete_create(self):
        """測試完整有效創建"""
        now = datetime.now(timezone.utc)
        data = {
            "task_id": 1,
            "start_time": now,
            "end_time": now,
            "success": True,
            "message": "測試訊息",
            "articles_count": 10
        }
        schema = CrawlerTaskHistoryCreateSchema.model_validate(data)
        
        assert schema.task_id == 1
        assert schema.start_time == now
        assert schema.end_time == now
        assert schema.success is True
        assert schema.message == "測試訊息"
        assert schema.articles_count == 10
    
    def test_missing_task_id(self):
        """測試缺少必填的task_id"""
        data = {}
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTaskHistoryCreateSchema.model_validate(data)
        assert "task_id: do not be empty" in str(exc_info.value)
    
    def test_invalid_task_id(self):
        """測試無效的task_id值"""
        test_cases = [
            {"task_id": 0},
            {"task_id": -1},
            {"task_id": None}
        ]
        
        for data in test_cases:
            with pytest.raises(ValidationError) as exc_info:
                CrawlerTaskHistoryCreateSchema.model_validate(data)
            assert any([
                "task_id: must be greater than 0" in str(exc_info.value),
                "task_id: do not be empty" in str(exc_info.value)
            ])
    
    def test_invalid_articles_count(self):
        """測試無效的articles_count值"""
        test_cases = [
            {"task_id": 1, "articles_count": -1},
            {"task_id": 1, "articles_count": "invalid"},
            {"task_id": 1, "articles_count": 1.5}
        ]
        
        for data in test_cases:
            with pytest.raises(ValidationError) as exc_info:
                CrawlerTaskHistoryCreateSchema.model_validate(data)
            assert any([
                "articles_count: must be greater than or equal to 0" in str(exc_info.value),
                "articles_count: must be an integer" in str(exc_info.value)
            ])
    
    def test_invalid_success_type(self):
        """測試無效的success類型"""
        data = {
            "task_id": 1,
            "success": "not_boolean"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTaskHistoryCreateSchema.model_validate(data)
        assert "success: must be a boolean value" in str(exc_info.value)

class TestCrawlerTaskHistoryUpdateSchema:
    """CrawlerTaskHistoryUpdateSchema 的測試類"""
    
    def test_valid_minimal_update(self):
        """測試最小化有效更新"""
        data = {
            "success": True
        }
        schema = CrawlerTaskHistoryUpdateSchema.model_validate(data)
        assert schema.success is True
        assert schema.end_time is None
        assert schema.message is None
        assert schema.articles_count is None
    
    def test_valid_complete_update(self):
        """測試完整有效更新"""
        now = datetime.now(timezone.utc)
        data = {
            "end_time": now,
            "success": True,
            "message": "更新訊息",
            "articles_count": 20
        }
        schema = CrawlerTaskHistoryUpdateSchema.model_validate(data)
        
        assert schema.end_time == now
        assert schema.success is True
        assert schema.message == "更新訊息"
        assert schema.articles_count == 20
    
    def test_forbidden_fields_update(self):
        """測試禁止更新的欄位"""
        forbidden_fields = ['id', 'task_id', 'start_time']
        
        for field in forbidden_fields:
            data = {field: 1}
            with pytest.raises(ValidationError) as exc_info:
                CrawlerTaskHistoryUpdateSchema.model_validate(data)
            assert f"do not allow to update {field} field" in str(exc_info.value)
    
    def test_empty_update(self):
        """測試空更新"""
        data = {}
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTaskHistoryUpdateSchema.model_validate(data)
        assert "must provide at least one field to update" in str(exc_info.value)
    
    def test_invalid_end_time_type(self):
        """測試無效的end_time類型"""
        data = {
            "end_time": "not_datetime"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTaskHistoryUpdateSchema.model_validate(data)
        assert "end_time: must be a datetime value" in str(exc_info.value)
    
    def test_invalid_success_type_update(self):
        """測試無效的success類型"""
        data = {
            "success": "not_boolean"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTaskHistoryUpdateSchema.model_validate(data)
        assert "success: must be a boolean value" in str(exc_info.value)
    
    def test_invalid_articles_count_update(self):
        """測試無效的articles_count值"""
        test_cases = [
            {"articles_count": -1},
            {"articles_count": "invalid"},
            {"articles_count": 1.5}
        ]
        
        for data in test_cases:
            with pytest.raises(ValidationError) as exc_info:
                CrawlerTaskHistoryUpdateSchema.model_validate(data)
            assert any([
                "articles_count: must be greater than or equal to 0" in str(exc_info.value),
                "articles_count: must be an integer" in str(exc_info.value)
            ]) 