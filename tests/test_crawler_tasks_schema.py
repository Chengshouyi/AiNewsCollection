import pytest
from datetime import datetime, timezone
from src.models.crawler_tasks_schema import CrawlerTasksCreateSchema, CrawlerTasksUpdateSchema
from src.models.crawler_tasks_model import TASK_ARGS_DEFAULT, TaskPhase, ScrapeMode
from src.error.errors import ValidationError

class TestCrawlerTasksCreateSchema:
    """CrawlerTasksCreateSchema 的測試類"""
    
    def test_crawler_tasks_schema_with_valid_data(self):
        """測試有效的爬蟲任務資料"""
        task_args = {
            'max_pages': 5,
            'ai_only': False,
            'num_articles': 20,
            'min_keywords': 4,
            'max_retries': 2,
            'retry_delay': 1.5,
            'timeout': 15,
            'is_test': False,
            'save_to_csv': True,
            'csv_file_prefix': 'test',
            'save_to_database': True,
            'scrape_mode': 'full_scrape',
            'get_links_by_task_id': True,
            'article_links': [],
            'max_cancel_wait': 30,
            'cancel_interrupt_interval': 5,
            'cancel_timeout': 60,
            'save_partial_results_on_cancel': True,
            'save_partial_to_database': True
        }
        
        data = {
            "task_name": "測試任務",
            "crawler_id": 1,
            "is_auto": True,
            "is_active": True,
            "task_args": task_args,
            "notes": "測試任務",
            "cron_expression": "*/10 * * * *",
            "last_run_message": "測試訊息",
            "current_phase": TaskPhase.INIT,
            "retry_count": 0
        }
        
        schema = CrawlerTasksCreateSchema.model_validate(data)
        
        # 基本字段測試
        assert schema.task_name == "測試任務"
        assert schema.crawler_id == 1
        assert schema.is_auto is True
        assert schema.is_active is True
        assert schema.notes == "測試任務"
        assert schema.cron_expression == "*/10 * * * *"
        assert schema.last_run_message == "測試訊息"
        assert schema.current_phase == TaskPhase.INIT
        assert schema.retry_count == 0
        
        # task_args 測試
        assert schema.task_args is not None
        assert isinstance(schema.task_args, dict)
        
        # 檢查 task_args 中的欄位
        assert schema.task_args['max_pages'] == 5
        assert schema.task_args['ai_only'] is False
        assert schema.task_args['num_articles'] == 20
        assert schema.task_args['min_keywords'] == 4
        assert schema.task_args['max_retries'] == 2
        assert schema.task_args['retry_delay'] == 1.5
        assert schema.task_args['timeout'] == 15
        assert schema.task_args['is_test'] is False
        assert schema.task_args['save_to_csv'] is True
        assert schema.task_args['csv_file_prefix'] == 'test'
        assert schema.task_args['save_to_database'] is True
        assert schema.task_args['scrape_mode'] == 'full_scrape'
        assert schema.task_args['get_links_by_task_id'] is True
        assert schema.task_args['article_links'] == []
        assert schema.task_args['max_cancel_wait'] == 30
        assert schema.task_args['cancel_interrupt_interval'] == 5
        assert schema.task_args['cancel_timeout'] == 60
        assert schema.task_args['save_partial_results_on_cancel'] is True
        assert schema.task_args['save_partial_to_database'] is True


    def test_missing_required_fields(self):
        """測試缺少必要欄位"""
        data = {
            "task_name": "測試任務",
            "is_auto": False
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksCreateSchema.model_validate(data)
        assert any(["crawler_id: 不能為空" in str(exc_info.value), "crawler_id: 不能為 None" in str(exc_info.value)])

        # 測試缺少task_args
        data = {
            "task_name": "測試任務",
            "crawler_id": 1,
            "is_auto": False
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksCreateSchema.model_validate(data)
        assert "task_args: 不能為空" in str(exc_info.value) or "task_args: 不能為 None" in str(exc_info.value)
        
        # 測試缺少current_phase
        data = {
            "task_name": "測試任務",
            "crawler_id": 1,
            "is_auto": False,
            "task_args": {}
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksCreateSchema.model_validate(data)
        assert "current_phase: 不能為空" in str(exc_info.value) or "current_phase: 不能為 None" in str(exc_info.value)

    def test_crawler_tasks_with_all_fields(self):
        """測試包含所有欄位的爬蟲任務資料"""
        task_args = {
            'max_pages': 5,
            'ai_only': True,
            'num_articles': 15,
            'min_keywords': 3,
            'max_retries': 2,
            'retry_delay': 1.0,
            'timeout': 8,
            'is_test': True,
            'save_to_csv': True,
            'csv_file_prefix': 'test_prefix',
            'save_to_database': False,
            'scrape_mode': ScrapeMode.FULL_SCRAPE.value,
            'get_links_by_task_id': False,
            'article_links': ['http://example.com/1', 'http://example.com/2'],
            'max_cancel_wait': 30,
            'cancel_interrupt_interval': 5,
            'cancel_timeout': 60,
            'save_partial_results_on_cancel': True,
            'save_partial_to_database': True
        }
        
        data = {
            "task_name": "測試任務",
            "crawler_id": 1,
            "is_auto": True,
            "is_active": True,
            "task_args": task_args,
            "notes": "測試任務",
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
            "cron_expression": "* * * * *",
            "current_phase": TaskPhase.INIT,
            "retry_count": 0
        }
        
        schema = CrawlerTasksCreateSchema.model_validate(data)
        
        # 基本字段測試
        assert schema.task_name == "測試任務"
        assert schema.crawler_id == 1
        assert schema.is_auto is True
        assert schema.is_active is True
        assert schema.notes == "測試任務"
        assert schema.current_phase == TaskPhase.INIT
        assert schema.retry_count == 0
        
        # task_args 測試
        assert schema.task_args['ai_only'] is True
        assert schema.task_args['max_pages'] == 5
        assert schema.task_args['article_links'] == ['http://example.com/1', 'http://example.com/2']
        assert schema.task_args['max_cancel_wait'] == 30
        assert schema.task_args['cancel_interrupt_interval'] == 5
        assert schema.task_args['cancel_timeout'] == 60
        assert schema.task_args['save_partial_results_on_cancel'] is True
        assert schema.task_args['save_partial_to_database'] is True

    def test_crawler_id_validation(self):
        """測試 crawler_id 的驗證"""
        # 測試 crawler_id 為 0
        data_zero = {
            "task_name": "測試任務",
            "crawler_id": 0,
            "is_auto": True,
            "is_active": True,
            "task_args": TASK_ARGS_DEFAULT,
            "cron_expression": "* * * * *",
            "current_phase": TaskPhase.INIT,
            "retry_count": 0
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksCreateSchema.model_validate(data_zero)
        assert "crawler_id: 必須是正整數且大於0" in str(exc_info.value)

    def test_retry_count_validation(self):
        """測試 retry_count 的驗證"""
        # 測試 retry_count 為負數
        data_negative = {
            "task_name": "測試任務",
            "crawler_id": 1,
            "is_auto": True,
            "is_active": True,
            "task_args": TASK_ARGS_DEFAULT,
            "cron_expression": "* * * * *",
            "current_phase": TaskPhase.INIT,
            "retry_count": -1
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksCreateSchema.model_validate(data_negative)
        assert "retry_count: 必須是正整數且大於等於0" in str(exc_info.value)

    def test_boolean_fields_validation(self):
        """測試布林欄位的驗證"""
        # 測試 is_auto 非布林值
        data_invalid_is_auto = {
            "task_name": "測試任務",
            "crawler_id": 1,
            "is_auto": "tru",
            "is_active": True,
            "task_args": TASK_ARGS_DEFAULT,
            "cron_expression": "* * * * *",
            "current_phase": TaskPhase.INIT,
            "retry_count": 0
        }
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksCreateSchema.model_validate(data_invalid_is_auto)
        assert "is_auto: 必須是布爾值" in str(exc_info.value)

    def test_default_values(self):
        """測試默認值設置"""
        data = {
            "task_name": "測試任務",
            "crawler_id": 1,
            "task_args": TASK_ARGS_DEFAULT,
            "current_phase": TaskPhase.INIT
        }
        schema = CrawlerTasksCreateSchema.model_validate(data)
        assert schema.is_auto is True
        assert schema.is_active is True
        assert schema.task_args == TASK_ARGS_DEFAULT
        assert schema.notes is None
        assert schema.cron_expression is None
        assert schema.last_run_at is None
        assert schema.last_run_success is None
        assert schema.last_run_message is None
        assert schema.retry_count == 0

    def test_field_validations(self):
        """測試欄位驗證"""
        # 測試 crawler_id 為 None
        try:
            CrawlerTasksCreateSchema.model_validate({
                "task_name": "測試任務", 
                "task_args": TASK_ARGS_DEFAULT, 
                "crawler_id": None, 
                "current_phase": TaskPhase.INIT
            })
            pytest.fail("預期 ValidationError for crawler_id=None")
        except ValidationError as e:
            assert any(["crawler_id: 不能為空" in str(e), "crawler_id: 不能為 None" in str(e)])
            
        # 測試 crawler_id 為空字串
        try:
            CrawlerTasksCreateSchema.model_validate({
                "task_name": "測試任務", 
                "task_args": TASK_ARGS_DEFAULT, 
                "crawler_id": "", 
                "current_phase": TaskPhase.INIT
            })
            pytest.fail("預期 ValidationError for crawler_id=''")
        except ValidationError as e:
            assert any(["crawler_id: 必須是整數" in str(e), "crawler_id: 不能為空" in str(e)])
            
        # 測試 crawler_id 為 0
        try:
            CrawlerTasksCreateSchema.model_validate({
                "task_name": "測試任務", 
                "task_args": TASK_ARGS_DEFAULT, 
                "crawler_id": 0, 
                "current_phase": TaskPhase.INIT
            })
            pytest.fail("預期 ValidationError for crawler_id=0")
        except ValidationError as e:
            assert "crawler_id: 必須是正整數且大於0" in str(e)
            
        # 測試 crawler_id 為負數
        try:
            CrawlerTasksCreateSchema.model_validate({
                "task_name": "測試任務", 
                "task_args": TASK_ARGS_DEFAULT, 
                "crawler_id": -1, 
                "current_phase": TaskPhase.INIT
            })
            pytest.fail("預期 ValidationError for crawler_id=-1")
        except ValidationError as e:
            assert "crawler_id: 必須是正整數且大於0" in str(e)
            
        # 測試 crawler_id 為非數字
        try:
            CrawlerTasksCreateSchema.model_validate({
                "task_name": "測試任務", 
                "task_args": TASK_ARGS_DEFAULT, 
                "crawler_id": "abc", 
                "current_phase": TaskPhase.INIT
            })
            pytest.fail("預期 ValidationError for crawler_id='abc'")
        except ValidationError as e:
            assert "crawler_id: 必須是整數" in str(e)

        # 測試 task_args 驗證
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksCreateSchema.model_validate({
                "task_name": "測試任務", 
                "crawler_id": 1, 
                "task_args": "not_a_dict", 
                "current_phase": TaskPhase.INIT
            })
        assert "task_args: 必須是字典格式" in str(exc_info.value)

        # 測試文字欄位驗證
        text_fields = {
            "notes": "a" * 65537,
            "last_run_message": "a" * 65537
        }
        for field, value in text_fields.items():
            data = {
                "task_name": "測試任務", 
                "crawler_id": 1, 
                "task_args": TASK_ARGS_DEFAULT, 
                "current_phase": TaskPhase.INIT,
                field: value
            }
            with pytest.raises(ValidationError) as exc_info:
                CrawlerTasksCreateSchema.model_validate(data)
            assert f"{field}: 長度不能超過 65536 字元" in str(exc_info.value)
        # 測試 task_name 驗證
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksCreateSchema.model_validate({
                "task_name": "a" * 256, 
                "crawler_id": 1, 
                "task_args": TASK_ARGS_DEFAULT, 
                "current_phase": TaskPhase.INIT
            })
        assert "task_name: 長度不能超過 255 字元" in str(exc_info.value)
        
        # 測試 current_phase 驗證
        with pytest.raises(ValidationError) as exc_info:
            CrawlerTasksCreateSchema.model_validate({
                "task_name": "測試任務", 
                "crawler_id": 1, 
                "task_args": TASK_ARGS_DEFAULT, 
                "current_phase": "a" * 256
            })
        assert "current_phase: 無效的枚舉值" in str(exc_info.value)

    def test_task_phase_validation(self):
        """測試任務階段的驗證"""
        # 測試所有有效值
        valid_phases = [
            TaskPhase.INIT,
            TaskPhase.LINK_COLLECTION,
            TaskPhase.CONTENT_SCRAPING,
            TaskPhase.COMPLETED,
            "init",
            "link_collection",
            "content_scraping",
            "completed",
            "INIT",  # 測試大寫
            "Link_Collection"  # 測試混合大小寫
        ]
        
        for phase in valid_phases:
            data = {
                "task_name": "測試任務",
                "crawler_id": 1,
                "task_args": TASK_ARGS_DEFAULT,
                "current_phase": phase
            }
            schema = CrawlerTasksCreateSchema.model_validate(data)
            if isinstance(phase, str):
                try:
                    expected_phase = TaskPhase(phase)
                except ValueError:
                    expected_phase = TaskPhase(phase.lower())
            else:
                expected_phase = phase
            assert schema.current_phase == expected_phase

class TestCrawlerTasksUpdateSchema:
    """CrawlerTasksUpdateSchema 的測試類"""
    
    def test_valid_update(self):
        """測試有效的更新資料"""
        task_args = {
            'max_pages': 5,
            'ai_only': True,
            'num_articles': 15,
            'min_keywords': 3,
            'max_retries': 2,
            'retry_delay': 1.0,
            'timeout': 8,
            'is_test': True,
            'save_to_csv': True,
            'csv_file_prefix': 'test_prefix',
            'save_to_database': False,
            'scrape_mode': ScrapeMode.FULL_SCRAPE.value,
            'get_links_by_task_id': False,
            'article_links': ['http://example.com/1', 'http://example.com/2'],
            'max_cancel_wait': 30,
            'cancel_interrupt_interval': 5,
            'cancel_timeout': 60,
            'save_partial_results_on_cancel': True,
            'save_partial_to_database': True
        }
        
        data = {
            "task_name": "更新任務",
            "is_auto": False,
            "is_active": False,
            "task_args": task_args,
            "notes": "更新的備註",
            "cron_expression": "* */2 * * *",
            "last_run_message": "更新測試",
            "current_phase": TaskPhase.INIT,
            "retry_count": 2,
            "max_cancel_wait": 30,
            "cancel_interrupt_interval": 5,
            "cancel_timeout": 60,
            "save_partial_results_on_cancel": True,
            "save_partial_to_database": True
        }
        
        schema = CrawlerTasksUpdateSchema.model_validate(data)
        
        # 基本字段測試
        assert schema.task_name == "更新任務"
        assert schema.is_auto is False
        assert schema.is_active is False
        assert schema.notes == "更新的備註"
        assert schema.cron_expression == "* */2 * * *"
        assert schema.last_run_message == "更新測試"
        assert schema.current_phase == TaskPhase.INIT
        assert schema.retry_count == 2
        
        # task_args 測試
        assert schema.task_args is not None
        assert isinstance(schema.task_args, dict)
        
        # 檢查 task_args 中的欄位
        assert schema.task_args['max_pages'] == 5
        assert schema.task_args['ai_only'] is True
        assert schema.task_args['num_articles'] == 15
        assert schema.task_args['article_links'] == ['http://example.com/1', 'http://example.com/2']
        assert schema.task_args['max_cancel_wait'] == 30
        assert schema.task_args['cancel_interrupt_interval'] == 5
        assert schema.task_args['cancel_timeout'] == 60
        assert schema.task_args['save_partial_results_on_cancel'] is True
        assert schema.task_args['save_partial_to_database'] is True

    def test_invalid_cron_expressions(self):
        """測試無效的 cron 表達式"""
        # 這些表達式肯定是無效的
        definitely_invalid_expressions = [
            "invalid_cron",       # 不是cron格式
            "*/70 * * * *",       # 分鐘超出範圍
            "60 * * * *",         # 分鐘超出範圍
            "* 24 * * *",         # 小時超出範圍
            "* * 32 * *",         # 日期超出範圍
            "* * * 13 *",         # 月份超出範圍
            "* * * * 8",          # 星期超出範圍
            "1 2 3 4 5 6",        # 字段過多
            "1 2 3 4 5 6 7"       # 字段過多
        ]
        
        # 測試肯定無效的表達式
        for expression in definitely_invalid_expressions:
            try:
                data = {"cron_expression": expression}
                CrawlerTasksUpdateSchema.model_validate(data)
                pytest.fail(f"預期 ValidationError for 錯誤的cron表達式: {expression}")
            except ValidationError as e:
                # 確保錯誤消息包含cron_expression欄位名
                assert "cron_expression:" in str(e), f"Unexpected error for {expression}"

    def test_valid_cron_expressions(self):
        """測試有效的 cron 表達式"""
        valid_expressions = [
            "*/5 * * * *",               # 每 5 分鐘執行一次
            "* */2 * * *",               # 每隔兩分鐘執行一次 
            "0 0 * * *",                 # 每天午夜執行
            "0 12 1 */2 *",             # 每隔兩個月的第一天中午執行
            "0 0 1,15 * *",             # 每月 1 號和 15 號的午夜執行
            "0 22 * * 1-5"              # 工作日每天 22:00 執行
        ]

        for expression in valid_expressions:
            schema = CrawlerTasksUpdateSchema(cron_expression=expression)
            assert schema.cron_expression == expression

    def test_optional_cron_expression(self):
        """測試可選的 cron 表達式"""
        # 測試 None 值
        schema = CrawlerTasksUpdateSchema(cron_expression=None)
        assert schema.cron_expression is None

    def test_cron_expression_edge_cases(self):
        """測試 cron 表達式的邊界情況"""
        valid_edge_cases = [
            "* * * * 0",    # 星期日（0）
            "* * * * 7",    # 星期日（7）
            "0 0 1 1 *",    # 每年第一天的午夜
            "* * * * *"     # 每分鐘執行
        ]

        for expression in valid_edge_cases:
            schema = CrawlerTasksUpdateSchema(cron_expression=expression)
            assert schema.cron_expression == expression
    
    def test_immutable_fields(self):
        """測試不可變欄位"""
        immutable_fields = {
            "created_at": datetime.now(timezone.utc),
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
        test_cases = [
            {"field": "is_auto", "value": False},
            {"field": "is_active", "value": False},
            {"field": "notes", "value": "新備註"},
            {"field": "task_args", "value": TASK_ARGS_DEFAULT},
            {"field": "cron_expression", "value": "30 18 * * 0"},
            {"field": "last_run_message", "value": "部分更新測試"},
            {"field": "current_phase", "value": TaskPhase.INIT},
            {"field": "retry_count", "value": 3}
        ]
        
        for case in test_cases:
            field = case["field"]
            value = case["value"]
            
            data = {field: value}
            schema = CrawlerTasksUpdateSchema.model_validate(data)
            
            # 驗證指定的字段已正確設置
            assert getattr(schema, field) == value
            
            # 驗證其他字段為 None
            for other_case in test_cases:
                other_field = other_case["field"]
                if other_field != field:
                    assert getattr(schema, other_field) is None



