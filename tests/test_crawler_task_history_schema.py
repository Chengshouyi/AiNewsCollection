import pytest
from datetime import datetime
from src.models.crawler_task_history_schema import CrawlerTaskHistoryCreateSchema, CrawlerTaskHistoryUpdateSchema
from src.error.errors import ValidationError

class TestCrawlerTaskHistoryCreateSchema:
    """CrawlerTaskHistoryCreateSchema 的測試類"""
    
    def test_crawler_task_history_schema_with_valid_data(self):
        """測試有效的爬蟲任務歷史記錄資料"""
        data = {
            "task_id": 1,
            "start_time": datetime.now(),
            "success": True,
            "message": "測試任務",
            "articles_count": 10
        }
        schema = CrawlerTaskHistoryCreateSchema.model_validate(data)
        assert schema.task_id == 1
        assert schema.success is True
        assert schema.message == "測試任務"
        assert schema.articles_count == 10

    def test_missing_required_fields(self):
        """測試缺少必要欄位"""
        data = {
            "success": True,
            "articles_count": 5
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTaskHistoryCreateSchema.model_validate(data)
        assert "task_id: do not be empty" in str(exc_info.value)

    def test_crawler_task_history_with_all_fields(self):
        """測試包含所有欄位的爬蟲任務歷史記錄資料"""
        now = datetime.now()
        data = {
            "task_id": 1,
            "start_time": now,
            "end_time": now,
            "success": False,
            "message": "測試失敗",
            "articles_count": 0
        }
        schema = CrawlerTaskHistoryCreateSchema.model_validate(data)
        assert schema.task_id == 1
        assert schema.start_time == now
        assert schema.end_time == now
        assert schema.success is False
        assert schema.message == "測試失敗"
        assert schema.articles_count == 0

    def test_task_id_validation(self):
        """測試 task_id 的驗證"""
        # 測試 task_id 為 0
        data_zero = {
            "task_id": 0,
            "success": True
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTaskHistoryCreateSchema.model_validate(data_zero)
        assert "task_id: must be greater than 0" in str(exc_info.value)

        # 測試 task_id 為負數
        data_negative = {
            "task_id": -1,
            "success": True
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTaskHistoryCreateSchema.model_validate(data_negative)
        assert "task_id: must be greater than 0" in str(exc_info.value)

    def test_boolean_fields_validation(self):
        """測試布林欄位的驗證"""
        # 測試 success 非布林值
        data_invalid_success = {
            "task_id": 1,
            "success": "true"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTaskHistoryCreateSchema.model_validate(data_invalid_success)
        assert "success: must be a boolean value" in str(exc_info.value)

    def test_articles_count_validation(self):
        """測試文章數量的驗證"""
        # 測試文章數量為負數
        data_negative_count = {
            "task_id": 1,
            "articles_count": -1
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTaskHistoryCreateSchema.model_validate(data_negative_count)
        assert "articles_count: must be greater than or equal to 0" in str(exc_info.value)

        # 測試文章數量非整數
        data_invalid_count = {
            "task_id": 1,
            "articles_count": "A"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTaskHistoryCreateSchema.model_validate(data_invalid_count)
        assert "articles_count: must be an integer" in str(exc_info.value)

    def test_default_values(self):
        """測試默認值設置"""
        data = {
            "task_id": 1
        }
        schema = CrawlerTaskHistoryCreateSchema.model_validate(data)
        assert schema.success is False  # 默認為 False
        assert schema.articles_count == 0  # 默認為 0
        assert schema.message is None  # 默認為 None
        assert schema.start_time is not None
        assert schema.end_time is None

class TestCrawlerTaskHistoryUpdateSchema:
    """CrawlerTaskHistoryUpdateSchema 的測試類"""
    
    def test_update_schema_with_valid_data(self):
        """測試有效的更新資料"""
        now = datetime.now()
        data = {
            "end_time": now,
            "success": True,
            "message": "更新的備註",
            "articles_count": 15
        }
        schema = CrawlerTaskHistoryUpdateSchema.model_validate(data)
        assert schema.end_time == now
        assert schema.success is True
        assert schema.message == "更新的備註"
        assert schema.articles_count == 15

    def test_update_with_no_fields(self):
        """測試沒有提供任何欄位的情況"""
        data = {}
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTaskHistoryUpdateSchema.model_validate(data)
        assert "must provide at least one field to update" in str(exc_info.value)

    def test_update_forbidden_fields(self):
        """測試更新禁止的欄位"""
        # 測試更新 id
        data_id = {
            "success": True,
            "id": 2
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTaskHistoryUpdateSchema.model_validate(data_id)
        assert "do not allow to update id field" in str(exc_info.value)

        # 測試更新 task_id
        data_task_id = {
            "success": True,
            "task_id": 2
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTaskHistoryUpdateSchema.model_validate(data_task_id)
        assert "do not allow to update task_id field" in str(exc_info.value)

        # 測試更新 start_time
        data_start_time = {
            "success": True,
            "start_time": datetime.now()
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTaskHistoryUpdateSchema.model_validate(data_start_time)
        assert "do not allow to update start_time field" in str(exc_info.value)

    def test_update_boolean_fields_validation(self):
        """測試更新布林欄位的驗證"""
        # 測試 success 非布林值
        data_invalid_success = {
            "success": "true"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTaskHistoryUpdateSchema.model_validate(data_invalid_success)
        assert "success: must be a boolean value" in str(exc_info.value)

    def test_update_articles_count_validation(self):
        """測試更新文章數量的驗證"""
        # 測試文章數量為負數
        data_negative_count = {
            "articles_count": -1
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTaskHistoryUpdateSchema.model_validate(data_negative_count)
        assert "articles_count: must be greater than or equal to 0" in str(exc_info.value)

        # 測試文章數量非整數
        data_invalid_count = {
            "articles_count": "A"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTaskHistoryUpdateSchema.model_validate(data_invalid_count)
        assert "articles_count: must be an integer" in str(exc_info.value)

    def test_partial_update(self):
        """測試部分欄位更新"""
        # 只更新 success
        data_success = {
            "success": False
        }
        schema_success = CrawlerTaskHistoryUpdateSchema.model_validate(data_success)
        assert schema_success.success is False
        assert schema_success.end_time is None
        assert schema_success.message is None
        assert schema_success.articles_count is None

        # 只更新 message
        data_message = {
            "message": "新的備註"
        }
        schema_message = CrawlerTaskHistoryUpdateSchema.model_validate(data_message)
        assert schema_message.success is None
        assert schema_message.end_time is None
        assert schema_message.message == "新的備註"
        assert schema_message.articles_count is None 