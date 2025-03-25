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
    
    def test_task_id_validation(self):
        """測試 task_id 驗證"""
        invalid_cases = [
            ({"task_id": 0}, "task_id: 不能為空且必須大於0"),
            ({"task_id": -1}, "task_id: 不能為空且必須大於0"),
            ({"task_id": "abc"}, "task_id: 必須是整數"),
            ({}, "task_id: 不能為空")
        ]
        
        for data, expected_error in invalid_cases:
            with pytest.raises(ValidationError) as exc_info:
                CrawlerTaskHistoryCreateSchema.model_validate(data)
            assert expected_error in str(exc_info.value)
    
    def test_articles_count_validation(self):
        """測試 articles_count 驗證"""
        invalid_cases = [
            ({"task_id": 1, "articles_count": -1}, "articles_count: 不能小於0"),
            ({"task_id": 1, "articles_count": "abc"}, "articles_count: 必須是整數"),
            ({"task_id": 1, "articles_count": 1.5}, "articles_count: 必須是整數")
        ]
        
        for data, expected_error in invalid_cases:
            with pytest.raises(ValidationError) as exc_info:
                CrawlerTaskHistoryCreateSchema.model_validate(data)
            assert expected_error in str(exc_info.value)
    
    def test_datetime_validation(self):
        """測試日期時間驗證"""
        invalid_cases = [
            ({"task_id": 1, "start_time": "invalid-date"}, "start_time: 無效的日期時間格式"),
            ({"task_id": 1, "end_time": "invalid-date"}, "end_time: 無效的日期時間格式"),
            ({"task_id": 1, "start_time": 123}, "start_time: 必須是字串或日期時間"),
            ({"task_id": 1, "end_time": 123}, "end_time: 必須是字串或日期時間")
        ]
        
        for data, expected_error in invalid_cases:
            with pytest.raises(ValidationError) as exc_info:
                CrawlerTaskHistoryCreateSchema.model_validate(data)
            assert expected_error in str(exc_info.value)

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
    
    def test_immutable_fields_update(self):
        """測試不可變欄位更新"""
        immutable_fields = [
            ({"id": 1}, "不允許更新 id 欄位"),
            ({"task_id": 1}, "不允許更新 task_id 欄位"),
            ({"start_time": datetime.now()}, "不允許更新 start_time 欄位"),
            ({"created_at": datetime.now()}, "不允許更新 created_at 欄位")
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
            ({"articles_count": -1}, "articles_count: 不能小於0"),
            ({"articles_count": "abc"}, "articles_count: 必須是整數"),
            ({"end_time": "invalid-date"}, "end_time: 無效的日期時間格式"),
            ({"message": "a" * 65537}, "message: 長度不能超過 65536 字元")
        ]
        
        for data, expected_error in invalid_cases:
            with pytest.raises(ValidationError) as exc_info:
                CrawlerTaskHistoryUpdateSchema.model_validate(data)
            assert expected_error in str(exc_info.value) 