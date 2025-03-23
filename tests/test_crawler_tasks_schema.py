import pytest
from datetime import datetime
from src.models.crawler_tasks_schema import CrawlerTasksCreateSchema, CrawlerTasksUpdateSchema
from src.error.errors import ValidationError

class TestCrawlerTasksCreateSchema:
    """CrawlerTasksCreateSchema 的測試類"""
    
    def test_crawler_tasks_schema_with_valid_data(self):
        """測試有效的爬蟲任務資料"""
        data = {
            "crawler_id": 1,
            "is_auto": True,
            "ai_only": False,
            "notes": "測試任務"
        }
        schema = CrawlerTasksCreateSchema.model_validate(data)
        assert schema.crawler_id == 1
        assert schema.is_auto is True
        assert schema.ai_only is False
        assert schema.notes == "測試任務"

    def test_missing_required_fields(self):
        """測試缺少必要欄位"""
        data = {
            "is_auto": True,
            "ai_only": False
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksCreateSchema.model_validate(data)
        assert "crawler_id: do not be empty" in str(exc_info.value)

    def test_crawler_tasks_with_all_fields(self):
        """測試包含所有欄位的爬蟲任務資料"""
        data = {
            "crawler_id": 1,
            "is_auto": True,
            "ai_only": False,
            "notes": "測試任務",
            "created_at": datetime.now(),
            "updated_at": None
        }
        schema = CrawlerTasksCreateSchema.model_validate(data)
        assert schema.crawler_id == 1
        assert schema.is_auto is True
        assert schema.ai_only is False
        assert schema.notes == "測試任務"
        assert schema.created_at is not None
        assert schema.updated_at is None

    def test_crawler_id_validation(self):
        """測試 crawler_id 的驗證"""
        # 測試 crawler_id 為 0
        data_zero = {
            "crawler_id": 0,
            "is_auto": True
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksCreateSchema.model_validate(data_zero)
        assert "crawler_id: must be greater than 0" in str(exc_info.value)

        # 測試 crawler_id 為負數
        data_negative = {
            "crawler_id": -1,
            "is_auto": True
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksCreateSchema.model_validate(data_negative)
        assert "crawler_id: must be greater than 0" in str(exc_info.value)

    def test_boolean_fields_validation(self):
        """測試布林欄位的驗證"""
        # 測試 is_auto 非布林值
        data_invalid_is_auto = {
            "crawler_id": 1,
            "is_auto": "true"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksCreateSchema.model_validate(data_invalid_is_auto)
        assert "is_auto: must be a boolean value" in str(exc_info.value)

        # 測試 ai_only 非布林值
        data_invalid_ai_only = {
            "crawler_id": 1,
            "ai_only": "false"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksCreateSchema.model_validate(data_invalid_ai_only)
        assert "ai_only: must be a boolean value" in str(exc_info.value)

    def test_default_values(self):
        """測試默認值設置"""
        data = {
            "crawler_id": 1
        }
        schema = CrawlerTasksCreateSchema.model_validate(data)
        assert schema.is_auto is True  # 默認為 True
        assert schema.ai_only is False  # 默認為 False
        assert schema.notes is None  # 默認為 None
        assert schema.created_at is not None
        assert schema.updated_at is None

class TestCrawlerTasksUpdateSchema:
    """CrawlerTasksUpdateSchema 的測試類"""
    
    def test_update_schema_with_valid_data(self):
        """測試有效的更新資料"""
        data = {
            "is_auto": False,
            "ai_only": True,
            "notes": "更新的備註"
        }
        schema = CrawlerTasksUpdateSchema.model_validate(data)
        assert schema.is_auto is False
        assert schema.ai_only is True
        assert schema.notes == "更新的備註"

    def test_update_with_no_fields(self):
        """測試沒有提供任何欄位的情況"""
        data = {}
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksUpdateSchema.model_validate(data)
        assert "must provide at least one field to update" in str(exc_info.value)

    def test_update_forbidden_fields(self):
        """測試更新禁止的欄位"""
        # 測試更新 created_at
        data_created_at = {
            "is_auto": True,
            "created_at": datetime.now()
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksUpdateSchema.model_validate(data_created_at)
        assert "do not allow to update created_at field" in str(exc_info.value)

        # 測試更新 crawler_id
        data_crawler_id = {
            "is_auto": True,
            "crawler_id": 2
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksUpdateSchema.model_validate(data_crawler_id)
        assert "do not allow to update crawler_id field" in str(exc_info.value)

    def test_update_boolean_fields_validation(self):
        """測試更新布林欄位的驗證"""
        # 測試 is_auto 非布林值
        data_invalid_is_auto = {
            "is_auto": "true"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksUpdateSchema.model_validate(data_invalid_is_auto)
        assert "is_auto: must be a boolean value" in str(exc_info.value)

        # 測試 ai_only 非布林值
        data_invalid_ai_only = {
            "ai_only": "false"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksUpdateSchema.model_validate(data_invalid_ai_only)
        assert "ai_only: must be a boolean value" in str(exc_info.value)

    def test_partial_update(self):
        """測試部分欄位更新"""
        # 只更新 is_auto
        data_is_auto = {
            "is_auto": False
        }
        schema_is_auto = CrawlerTasksUpdateSchema.model_validate(data_is_auto)
        assert schema_is_auto.is_auto is False
        assert schema_is_auto.ai_only is None
        assert schema_is_auto.notes is None

        # 只更新 notes
        data_notes = {
            "notes": "新的備註"
        }
        schema_notes = CrawlerTasksUpdateSchema.model_validate(data_notes)
        assert schema_notes.is_auto is None
        assert schema_notes.ai_only is None
        assert schema_notes.notes == "新的備註" 