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
            "notes": "測試任務",
            "max_pages": 5,
            "num_articles": 20,
            "min_keywords": 4,
            "fetch_details": True,
            "schedule": "daily",
            "last_run_message": "測試訊息"
        }
        schema = CrawlerTasksCreateSchema.model_validate(data)
        assert schema.crawler_id == 1
        assert schema.is_auto is True
        assert schema.ai_only is False
        assert schema.notes == "測試任務"
        assert schema.max_pages == 5
        assert schema.num_articles == 20
        assert schema.min_keywords == 4
        assert schema.fetch_details is True
        assert schema.schedule == "daily"
        assert schema.last_run_message == "測試訊息"

    def test_missing_required_fields(self):
        """測試缺少必要欄位"""
        data = {
            "is_auto": True,
            "ai_only": False
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksCreateSchema.model_validate(data)
        assert "crawler_id: 不能為空" in str(exc_info.value)

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

    def test_crawler_id_validation(self):
        """測試 crawler_id 的驗證"""
        # 測試 crawler_id 為 0
        data_zero = {
            "crawler_id": 0,
            "is_auto": True
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksCreateSchema.model_validate(data_zero)
        assert "crawler_id: 不能為空" in str(exc_info.value)

    def test_boolean_fields_validation(self):
        """測試布林欄位的驗證"""
        # 測試 is_auto 非布林值
        data_invalid_is_auto = {
            "crawler_id": 1,
            "is_auto": "true"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksCreateSchema.model_validate(data_invalid_is_auto)
        assert "is_auto: 必須是布林值" in str(exc_info.value)

        # 測試 ai_only 非布林值
        data_invalid_ai_only = {
            "crawler_id": 1,
            "ai_only": "false"
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksCreateSchema.model_validate(data_invalid_ai_only)
        assert "ai_only: 必須是布林值" in str(exc_info.value)

    def test_default_values(self):
        """測試默認值設置"""
        data = {
            "crawler_id": 1
        }
        schema = CrawlerTasksCreateSchema.model_validate(data)
        assert schema.is_auto is True
        assert schema.ai_only is False
        assert schema.notes is None
        assert schema.max_pages == 3
        assert schema.num_articles == 10
        assert schema.min_keywords == 3
        assert schema.fetch_details is False
        assert schema.schedule is None
        assert schema.last_run_at is None
        assert schema.last_run_success is None
        assert schema.last_run_message is None

    def test_field_validations(self):
        """測試欄位驗證"""
        # 測試 crawler_id 驗證
        empty_values = [None, "", 0]
        for value in empty_values:
            with pytest.raises(ValidationError) as exc_info:
                CrawlerTasksCreateSchema.model_validate({"crawler_id": value})
            assert "crawler_id: 不能為空" in str(exc_info.value)

        # 測試負數
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksCreateSchema.model_validate({"crawler_id": -1})
        assert "crawler_id: 必須大於0" in str(exc_info.value)

        # 測試非數字
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksCreateSchema.model_validate({"crawler_id": "abc"})
        assert "crawler_id: 必須是整數" in str(exc_info.value)

        # 測試正整數欄位驗證
        number_fields = {
            "max_pages": [0, -1, "abc"],
            "num_articles": [0, -1, "abc"],
            "min_keywords": [0, -1, "abc"]
        }
        for field, invalid_values in number_fields.items():
            for value in invalid_values:
                data = {"crawler_id": 1, field: value}
                with pytest.raises(ValidationError) as exc_info:
                    CrawlerTasksCreateSchema.model_validate(data)
                if isinstance(value, str):
                    assert f"{field}: 必須是整數" in str(exc_info.value)
                else:
                    assert f"{field}: 必須大於0" in str(exc_info.value)

        # 測試布林欄位驗證
        boolean_fields = ["is_auto", "ai_only", "fetch_details"]
        for field in boolean_fields:
            data = {"crawler_id": 1, field: "not_boolean"}
            with pytest.raises(ValidationError) as exc_info:
                CrawlerTasksCreateSchema.model_validate(data)
            assert f"{field}: 必須是布林值" in str(exc_info.value)

        # 測試文字欄位驗證
        text_fields = {
            "notes": "a" * 65537,
            "last_run_message": "a" * 65537
        }
        for field, value in text_fields.items():
            data = {"crawler_id": 1, field: value}
            with pytest.raises(ValidationError) as exc_info:
                CrawlerTasksCreateSchema.model_validate(data)
            assert f"{field}: 長度不能超過 65536 字元" in str(exc_info.value)

        # 測試排程驗證
        invalid_schedules = ["invalid", "monthly", "yearly"]
        for schedule in invalid_schedules:
            with pytest.raises(ValidationError) as exc_info:
                CrawlerTasksCreateSchema.model_validate({
                    "crawler_id": 1,
                    "schedule": schedule
                })
            assert "schedule: 必須是 'hourly', 'daily', 'weekly' 或 None" in str(exc_info.value)

class TestCrawlerTasksUpdateSchema:
    """CrawlerTasksUpdateSchema 的測試類"""
    
    def test_valid_update(self):
        """測試有效的更新資料"""
        data = {
            "is_auto": False,
            "ai_only": True,
            "notes": "更新的備註",
            "max_pages": 5,
            "num_articles": 15,
            "min_keywords": 4,
            "fetch_details": True,
            "schedule": "weekly",
            "last_run_message": "更新測試"
        }
        schema = CrawlerTasksUpdateSchema.model_validate(data)
        assert schema.is_auto is False
        assert schema.ai_only is True
        assert schema.notes == "更新的備註"
        assert schema.max_pages == 5
        assert schema.num_articles == 15
        assert schema.min_keywords == 4
        assert schema.fetch_details is True
        assert schema.schedule == "weekly"
        assert schema.last_run_message == "更新測試"

    def test_immutable_fields(self):
        """測試不可變欄位"""
        immutable_fields = {
            "created_at": datetime.now(),
            "crawler_id": 2
        }
        for field, value in immutable_fields.items():
            with pytest.raises(ValidationError) as exc_info:
                CrawlerTasksUpdateSchema.model_validate({field: value})
            assert f"不允許更新 {field} 欄位" in str(exc_info.value)

    def test_empty_update(self):
        """測試空更新"""
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksUpdateSchema.model_validate({})
        assert "必須提供至少一個要更新的欄位" in str(exc_info.value)

    def test_partial_update(self):
        """測試部分欄位更新"""
        test_cases = {
            "is_auto": False,
            "notes": "新備註",
            "max_pages": 5,
            "schedule": "daily",
            "last_run_message": "部分更新測試"
        }
        
        for field, value in test_cases.items():
            schema = CrawlerTasksUpdateSchema.model_validate({field: value})
            assert getattr(schema, field) == value
            # 確認其他欄位為 None
            for other_field in test_cases.keys():
                if other_field != field:
                    assert getattr(schema, other_field) is None 