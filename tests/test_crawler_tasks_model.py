from src.models.crawler_tasks_model import CrawlerTasks
from datetime import datetime, timezone

class TestCrawlerTasksModel:
    """CrawlerTasks 模型的測試類"""
    
    def test_crawler_tasks_creation_with_required_fields(self):
        """測試使用必填欄位創建 CrawlerTasks"""
        task = CrawlerTasks(
            task_name="測試任務",
            crawler_id=1,
            is_auto=True,
            task_args={
                "article_settings": {
                    "max_pages": 3,
                    "ai_only": True,
                    "num_articles": 10,
                    "min_keywords": 3,
                    "from_db_link": False
                },
                "extraction_settings": {
                    "num_articles": 3,
                    "min_keywords": 3
                },
                "storage_settings": {
                    "save_to_csv": True,
                    "csv_file_name": "articles_bnext.csv",
                    "save_to_database": False
                }
            },
            notes="測試任務"
        )
        
        # 測試必填欄位
        assert task.task_name == "測試任務"
        assert task.crawler_id == 1
        assert task.is_auto is True
        assert task.task_args == {
            "article_settings": {
                "max_pages": 3,
                "ai_only": True,
                "num_articles": 10,
                "min_keywords": 3,
                "from_db_link": False
            },
            "extraction_settings": {
                "num_articles": 3,
                "min_keywords": 3
            },
            "storage_settings": {
                "save_to_csv": True,
                "csv_file_name": "articles_bnext.csv",
                "save_to_database": False
            }
        }
        assert task.notes == "測試任務"
        
        # 測試自動生成的欄位
        assert task.created_at is not None
        assert task.updated_at is None
        
        # 測試可選欄位預設值
        assert task.last_run_at is None
        assert task.last_run_success is None
        assert task.last_run_message is None
        assert task.cron_expression is None
    
    def test_default_values(self):
        """測試默認值設置"""
        task = CrawlerTasks(crawler_id=1)
        
        # 測試布林欄位預設值
        assert task.is_auto is True
        
        # 測試默認的 task_args
        assert task.task_args == {}
        
        # 測試可選欄位預設值
        assert task.notes is None
        assert task.cron_expression is None
        assert task.last_run_at is None
        assert task.last_run_success is None
        assert task.last_run_message is None
    
    def test_crawler_tasks_repr(self):
        """測試 CrawlerTasks 的 __repr__ 方法"""
        task = CrawlerTasks(
            id=1,
            task_name="測試任務",
            crawler_id=1
        )
        
        expected_repr = "<CrawlerTask(id=1, task_name=測試任務, crawler_id=1)>"
        assert repr(task) == expected_repr
    
    def test_field_updates(self):
        """測試欄位更新"""
        task = CrawlerTasks(crawler_id=1)
        
        # 測試布林欄位更新
        task.is_auto = False
        assert task.is_auto is False
        
        # 測試 task_args 更新
        task.task_args = {
            "article_settings": {
                "max_pages": 5,
                "num_articles": 20
            }
        }
        assert task.task_args["article_settings"]["max_pages"] == 5
        assert task.task_args["article_settings"]["num_articles"] == 20
        
        # 測試文字欄位更新
        task.task_name = "更新後的任務名稱"
        task.notes = "更新的備註"
        task.cron_expression = "hourly"
        task.last_run_message = "執行成功"
        assert task.task_name == "更新後的任務名稱"
        assert task.notes == "更新的備註"
        assert task.last_run_message == "執行成功"
        
        task.cron_expression = "*/5 * * * *"
        assert task.cron_expression == "*/5 * * * *"

    def test_to_dict(self):
        """測試 to_dict 方法"""
        task = CrawlerTasks(
            id=1,
            task_name="測試任務",
            crawler_id=1,
            notes="測試任務"
        )
        
        task_dict = task.to_dict()
        
        # 驗證所有欄位都在字典中
        expected_keys = {
            'id', 'task_name', 'crawler_id', 'is_auto', 'ai_only','task_args', 'notes',
            'created_at', 'updated_at', 'last_run_at', 'last_run_success',
            'last_run_message', 'cron_expression'
        }
        
        assert set(task_dict.keys()) == expected_keys 
    

    def test_crawler_tasks_utc_datetime_conversion(self):
        """測試 CrawlerTasks 的 last_run_at 欄位 UTC 時間轉換"""
        from datetime import timedelta
        
        # 測試 1: 傳入無時區資訊的 datetime (naive datetime)
        naive_time = datetime(2025, 3, 28, 12, 0, 0)  # 無時區資訊
        task = CrawlerTasks(
            crawler_id=1,
            last_run_at=naive_time
        )
        if task.last_run_at is not None:
            assert task.last_run_at.tzinfo == timezone.utc  # 確認有 UTC 時區
        assert task.last_run_at == naive_time.replace(tzinfo=timezone.utc)  # 確認值正確

        # 測試 2: 傳入帶非 UTC 時區的 datetime (aware datetime, UTC+8)
        utc_plus_8_time = datetime(2025, 3, 28, 14, 0, 0, tzinfo=timezone(timedelta(hours=8)))
        task.last_run_at = utc_plus_8_time
        expected_utc_time = datetime(2025, 3, 28, 6, 0, 0, tzinfo=timezone.utc)  # UTC+8 轉 UTC
        assert task.last_run_at.tzinfo == timezone.utc  # 確認轉換為 UTC 時區
        assert task.last_run_at == expected_utc_time  # 確認時間正確轉換

        # 測試 3: 傳入已是 UTC 的 datetime，確保不變
        utc_time = datetime(2025, 3, 28, 12, 0, 0, tzinfo=timezone.utc)
        task.last_run_at = utc_time
        assert task.last_run_at == utc_time  # 確認值未被改變

        # 測試 4: 確認非監聽欄位（如 notes）不觸發轉換邏輯
        task.notes = "新備註"
        assert task.last_run_at == utc_time  # last_run_at 不受影響