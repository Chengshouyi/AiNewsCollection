import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.crawler_tasks_model import CrawlerTasks, Base, ScrapePhase, ScrapeMode
from src.models.crawlers_model import Crawlers
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.services.crawler_task_service import CrawlerTaskService
from src.database.database_manager import DatabaseManager
from src.models.crawler_tasks_schema import TASK_ARGS_DEFAULT
from src.models.crawler_task_history_schema import TaskStatus
from src.utils.enum_utils import TaskStatus as StatusBeforeRead
from unittest.mock import call
from croniter import croniter

# 設置測試資料庫
@pytest.fixture(scope="session")
def engine():
    """創建測試用的資料庫引擎"""
    return create_engine('sqlite:///:memory:')

@pytest.fixture(scope="session")
def tables(engine):
    """創建資料表"""
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="session")
def session_factory(engine):
    """創建會話工廠"""
    return sessionmaker(bind=engine)

@pytest.fixture(scope="function")
def session(session_factory, tables):
    """為每個測試函數創建新的會話"""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture(scope="function")
def crawler_task_service(session):
    """創建爬蟲任務服務實例"""
    db_manager = DatabaseManager('sqlite:///:memory:')
    db_manager.Session = sessionmaker(bind=session.get_bind())
    return CrawlerTaskService(db_manager)

@pytest.fixture(scope="function")
def sample_tasks(session):
    """創建測試用的爬蟲任務資料"""
    # 清除現有資料
    print(f"sample_tasks() before clean data ：Session ID: {id(session)}")
    session.query(CrawlerTaskHistory).delete()
    session.query(CrawlerTasks).delete()
    session.query(Crawlers).delete()
    session.commit()
    print(f"sample_tasks() after clean data ：Session ID: {id(session)}")
    # 創建測試用的爬蟲
    crawler = Crawlers(
        crawler_name="測試爬蟲",
        base_url="https://test.com",
        is_active=True,
        crawler_type="RSS",
        config_file_name="test_config.json"
    )
    session.add(crawler)
    session.flush()
    print(f"sample_tasks() after add crawler ：Session ID: {id(session)}")
    tasks = [
        CrawlerTasks(
            task_name="每日新聞爬取",
            crawler_id=crawler.id,
            cron_expression="0 0 * * *",
            is_auto=True,
            task_args={"max_items": 100, "scrape_mode": ScrapeMode.FULL_SCRAPE.value},
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            scrape_phase=ScrapePhase.INIT,
            max_retries=3,
            retry_count=0,
            ai_only=False
        ),
        CrawlerTasks(
            task_name="週間財經新聞",
            crawler_id=crawler.id,
            cron_expression="0 0 * * 1-5",
            is_auto=True,
            task_args={"max_items": 50, "scrape_mode": ScrapeMode.LINKS_ONLY.value},
            created_at=datetime(2023, 1, 2, tzinfo=timezone.utc),
            updated_at=datetime(2023, 1, 2, tzinfo=timezone.utc),
            scrape_phase=ScrapePhase.INIT,
            max_retries=3,
            retry_count=0,
            ai_only=True
        )
    ]
    
    session.add_all(tasks)
    session.commit()
    print(f"sample_tasks() after add tasks ：Session ID: {id(session)}")
    return tasks

class TestCrawlerTaskService:
    """測試爬蟲任務服務的核心功能"""

    def test_create_task(self, crawler_task_service):
        """測試創建爬蟲任務"""
        task_data = {
            "task_name": "測試任務",
            "crawler_id": 1,
            "is_auto": True,
            "cron_expression": "0 0 * * *",
            "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False, "max_retries": 3, "retry_count": 0, "scrape_mode": "full_scrape"},
            "scrape_phase": "init"
        }
        
        result = crawler_task_service.create_task(task_data)
        assert result["success"] is True
        assert "task" in result and result["task"] is not None
        task_id = result["task"].id 
        assert task_id is not None
        assert result["message"] == "任務創建成功"

    def test_delete_task(self, crawler_task_service, sample_tasks):
        """測試刪除爬蟲任務"""
        task_id = sample_tasks[0].id
        result = crawler_task_service.delete_task(task_id)
        assert result["success"] is True
        assert result["message"] == "任務刪除成功"
        
        # 確認任務已被刪除
        result = crawler_task_service.get_task_by_id(task_id)
        assert result["success"] is False
        assert result["message"] == "任務不存在或不符合條件"

    def test_get_task_by_id(self, crawler_task_service, sample_tasks):
        """測試根據ID獲取爬蟲任務"""
        task_id = sample_tasks[0].id
        result = crawler_task_service.get_task_by_id(task_id)
        
        assert result["success"] is True
        assert "task" in result
        assert result["task"].id == task_id
        assert result["task"].task_name == sample_tasks[0].task_name

    def test_get_all_tasks(self, crawler_task_service, sample_tasks):
        """測試獲取所有任務"""
        result = crawler_task_service.get_all_tasks()
        assert result["success"] is True
        assert len(result["tasks"]) >= len(sample_tasks)

    def test_get_task_history(self, crawler_task_service, sample_tasks, session):
        """測試獲取任務歷史記錄"""
        task_id = sample_tasks[0].id

        # 本地導入以確保繫結
        from src.models.crawler_task_history_model import CrawlerTaskHistory
        from src.models.crawler_task_history_schema import TaskStatus

         # --- 添加測試數據 ---
        histories = [
            CrawlerTaskHistory(
                task_id=task_id,
                start_time=datetime(2023, 1, 1, tzinfo=timezone.utc),
                end_time=datetime(2023, 1, 1, 1, tzinfo=timezone.utc),
                success=True,
                message="執行成功",
                articles_count=10,
                task_status=TaskStatus.COMPLETED # 使用正確的 Enum 成員
            ),
            CrawlerTaskHistory(
                task_id=task_id,
                start_time=datetime(2023, 1, 2, tzinfo=timezone.utc),
                end_time=datetime(2023, 1, 2, 1, tzinfo=timezone.utc),
                success=False,
                message="執行失敗",
                articles_count=0,
                task_status=TaskStatus.FAILED # 使用正確的 Enum 成員
            )
        ]
        session.add_all(histories)
        session.commit()
        print("Commit successful!") # 確認提交成功
        
        print(f"test_get_task_history() before query ：Session ID: {id(session)}")
        # 直接查詢
        # try:
        #     print(f"test_get_task_history() before direct query ：Session ID: {id(session)}")
        #     histories_direct = session.query(CrawlerTaskHistory).filter(CrawlerTaskHistory.task_id == task_id).all()
        #     print("Direct query successful:", histories_direct) 
        #     print(f"test_get_task_history() after direct query ：Session ID: {id(session)}")
        # except Exception as e:
        #     print("Direct query failed:", e)

        print(f"test_get_task_history() befor task_service.get_task_history query ：Session ID: {id(session)}")
        result = crawler_task_service.get_task_history(task_id)
        print(f"test_get_task_history() after task_service.get_task_history query ：Session ID: {id(session)}")
        # print(f"test_get_task_history() result: {result}")
        assert result["success"] is True
        assert result["total_count"] == 2
        assert len(result["histories"]) == 2

    def test_get_task_status(self, crawler_task_service, sample_tasks, session):
        """測試獲取任務狀態"""
        task_id = sample_tasks[0].id
        
        # 本地導入以確保繫結
        from src.models.crawler_task_history_model import CrawlerTaskHistory
        from src.models.crawler_task_history_schema import TaskStatus
        # 創建一個進行中的任務歷史記錄
        history = CrawlerTaskHistory(
            task_id=task_id,
            start_time=datetime.now(timezone.utc),
            success=None,
            message="正在執行中",
            task_status=TaskStatus.RUNNING
        )
        session.add(history)
        session.commit()

        # 更新任務本身的狀態以匹配
        update_result = crawler_task_service.update_task_status(task_id, task_status=TaskStatus.RUNNING, scrape_phase=ScrapePhase.LINK_COLLECTION)
        assert update_result["success"] is True
        
        result = crawler_task_service.get_task_status(task_id)
        assert result["task_status"] == TaskStatus.RUNNING.value
        assert result["scrape_phase"] == ScrapePhase.LINK_COLLECTION.value
        assert 0 <= result["progress"] <= 95
        assert "任務運行中" in result["message"]

    def test_error_handling(self, crawler_task_service):
        """測試錯誤處理"""
        # 測試獲取不存在的任務
        result = crawler_task_service.get_task_by_id(999999)
        assert result["success"] is False
        assert "任務不存在" in result["message"]
        
        # 測試更新不存在的任務，使用正確的字段名稱
        result = crawler_task_service.update_task(999999, {"task_name": "新名稱"})
        assert result["success"] is False
        assert "任務不存在" in result["message"]

    def test_create_task_with_scrape_mode(self, crawler_task_service):
        """測試創建帶有抓取模式的任務"""
        task_data = {
            "task_name": "測試抓取模式任務",
            "crawler_id": 1,
            "is_auto": True,
            "cron_expression": "0 0 * * *",
            "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False, "max_retries": 3, "retry_count": 0, "scrape_mode": "links_only"},
            "scrape_phase": "init"
        }
        
        result = crawler_task_service.create_task(task_data)
        assert result["success"] is True
        assert "task" in result and result["task"] is not None
        
        # 獲取創建的任務 ID
        task_id = result["task"].id
        task_result = crawler_task_service.get_task_by_id(task_id)
        
        # 確認抓取模式已正確設置
        assert task_result["success"] is True
        assert task_result["task"].task_args.get("scrape_mode") == "links_only"

    def test_validate_task_data(self, crawler_task_service):
        """測試任務資料驗證功能"""
        from src.error.errors import ValidationError
        # 有效的任務資料
        valid_data = {
            "task_name": "測試驗證",
            "crawler_id": 1,
            "is_auto": True,
            "cron_expression": "0 0 * * *",
            "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False, "max_retries": 3, "retry_count": 0, "scrape_mode": "full_scrape"},
            "scrape_phase": "init"
        }
        
        try:
            validated = crawler_task_service.validate_task_data(valid_data.copy())
            assert isinstance(validated, dict)
            assert "task_name" in validated
        except ValidationError as e:
            pytest.fail(f"驗證應該通過，但卻失敗了: {e}")
        
        # 無效的任務資料 - 自動執行但沒有cron表達式
        invalid_data_no_cron = {
            "task_name": "測試驗證",
            "crawler_id": 1,
            "is_auto": True,  # 自動執行
            "cron_expression": None,  # 沒有cron表達式
            "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False, "max_retries": 3, "retry_count": 0, "scrape_mode": "full_scrape"},
            "scrape_phase": "init"
        }
        
        with pytest.raises(ValidationError, match="cron_expression: 當設定為自動執行時,此欄位不能為空"):
            crawler_task_service.validate_task_data(invalid_data_no_cron.copy())
            
        # 測試內容抓取模式邏輯 - 沒有get_links_by_task_id時應自動設為True
        content_only_auto_get_links = {
            "task_name": "內容抓取測試",
            "crawler_id": 1,
            "is_auto": False,
            "task_args": {**TASK_ARGS_DEFAULT, "scrape_mode": "content_only"},
            "scrape_phase": "init"
        }
        
        result_auto_get = crawler_task_service.validate_task_data(content_only_auto_get_links.copy())
        assert result_auto_get["task_args"].get("get_links_by_task_id") is True, "get_links_by_task_id should default to True for content_only"
        
        # 測試內容抓取模式邏輯 - get_links_by_task_id=False 但沒有提供 article_links
        content_only_missing_links = {
            "task_name": "內容抓取測試",
            "crawler_id": 1,
            "is_auto": False,
            "task_args": {**TASK_ARGS_DEFAULT, "scrape_mode": "content_only", "get_links_by_task_id": False, "article_links": None},
            "scrape_phase": "init"
        }
        
        with pytest.raises(ValidationError, match="task_args: task_args: task_args.article_links: 類型不匹配。期望類型: list"):
            crawler_task_service.validate_task_data(content_only_missing_links.copy())

        # 無效的 task_args (例如缺少必要欄位)
        invalid_task_args_data = {
            "task_name": "測試無效Args",
            "crawler_id": 1,
            "is_auto": False,
            "task_args": {"scrape_mode": "full_scrape"},
            "scrape_phase": "init"
        }
        with pytest.raises(ValidationError, match="task_args: task_args: task_args.max_pages: 必填欄位不能缺少"):
             crawler_task_service.validate_task_data(invalid_task_args_data.copy())

    def test_find_pending_tasks(self, crawler_task_service, sample_tasks, session):
        """測試查詢待執行任務 (需要模擬時間和上次執行狀態)"""
        from croniter import croniter
        from datetime import timedelta

        cron_expression = "0 0 * * *"  # 每天午夜執行
        task_id = sample_tasks[0].id

        # 確保任務的 cron 表達式匹配
        crawler_task_service.update_task(task_id, {"cron_expression": cron_expression, "is_auto": True, "is_active": True})

        now = datetime.now(timezone.utc) # Get current time once for consistency in the test case

        # --- Calculate the PREVIOUS scheduled time relative to NOW ---
        # Use the SAME cron expression and NOW as the function would use
        iter_for_test = croniter(cron_expression, now)
        # This is the schedule time slot immediately before 'now'
        prev_run_time_expected_utc = iter_for_test.get_prev(datetime)
        # Ensure it has timezone info if croniter doesn't add it
        if prev_run_time_expected_utc.tzinfo is None:
             prev_run_time_expected_utc = prev_run_time_expected_utc.replace(tzinfo=timezone.utc) # Or use enforce_utc_datetime_transform

        # 情況 1: 上次執行時間是很久以前 -> 應該被找到
        print(f"\n--- Testing find_pending_tasks: Case 1 (Old last run) ---")
        # Use a time clearly before the last slot
        old_last_run = prev_run_time_expected_utc - timedelta(days=1)
        crawler_task_service.update_task(task_id, {"last_run_at": old_last_run}) # Changed from last_run_time
        result1 = crawler_task_service.find_pending_tasks(cron_expression)
        print(f"Result 1 (Old last run): {result1}")
        assert result1["success"] is True
        # Make sure the correct field 'last_run_at' is checked in the task data if needed for debugging
        # print(f"Task {task_id} last_run_at after update 1: {crawler_task_service.get_task_by_id(task_id)['task'].last_run_at}")
        assert any(task.id == task_id for task in result1["tasks"]), "Task should be pending (old last run)"

        # 情況 2: 上次執行時間就是上次應該執行的時間 -> 不應該被找到
        print(f"\n--- Testing find_pending_tasks: Case 2 (Correct last run) ---")
        # Set last run to the *actual* previous schedule time relative to now
        crawler_task_service.update_task(task_id, {"last_run_at": prev_run_time_expected_utc}) # Changed from last_run_time
        result2 = crawler_task_service.find_pending_tasks(cron_expression)
        print(f"Result 2 (Correct last run): {result2}")
        # print(f"Task {task_id} last_run_at after update 2: {crawler_task_service.get_task_by_id(task_id)['task'].last_run_at}")
        # print(f"Tasks returned in result2: {[t.id for t in result2['tasks']]}")
        assert result2["success"] is True
        assert not any(task.id == task_id for task in result2["tasks"]), f"Task should NOT be pending (correct last run). last_run_at={prev_run_time_expected_utc.isoformat()}" # Added more detail

        # --- 情況 3: 從未執行過 (last_run_at is None) -> 應該被找到 ---
        print(f"\n--- Testing find_pending_tasks: Case 3 (Never run) ---")
        crawler_task_service.update_task(task_id, {"last_run_at": None}) # Changed from last_run_time
        result3 = crawler_task_service.find_pending_tasks(cron_expression)
        print(f"Result 3 (Never run): {result3}")
        assert result3["success"] is True
        assert any(task.id == task_id for task in result3["tasks"]), "Task should be pending (never run)"

        # --- 情況 4: 任務 inactive -> 不應該被找到 ---
        print(f"\n--- Testing find_pending_tasks: Case 4 (Inactive) ---")
        # Ensure last_run_at makes it pending if active, then set inactive
        crawler_task_service.update_task(task_id, {"last_run_at": None, "is_active": False})
        result4 = crawler_task_service.find_pending_tasks(cron_expression)
        print(f"Result 4 (Inactive): {result4}")
        assert result4["success"] is True
        assert not any(task.id == task_id for task in result4["tasks"]), "Task should NOT be pending (inactive)"
        # Clean up: set task back to active for potential subsequent tests if needed
        crawler_task_service.update_task(task_id, {"is_active": True})

    def test_update_task_status_and_history(self, crawler_task_service, sample_tasks):
        """測試更新任務狀態和歷史記錄"""
        task_id = sample_tasks[0].id
        now = datetime.now(timezone.utc)

        # 1. 初始狀態 (假設是 INIT)
        initial_status = crawler_task_service.get_task_status(task_id)
        assert initial_status['task_status'] == TaskStatus.INIT.value
        assert initial_status['scrape_phase'] == ScrapePhase.INIT.value

        # 2. 更新為 RUNNING, LINK_COLLECTION, 創建歷史記錄
        start_time = now - timedelta(minutes=1)
        history_data_start = {
            "task_id": task_id,
            "start_time": start_time,
            "task_status": TaskStatus.RUNNING,
            "message": "開始連結收集"
        }
        result_start = crawler_task_service.update_task_status(
            task_id,
            task_status=TaskStatus.RUNNING,
            scrape_phase=ScrapePhase.LINK_COLLECTION,
            history_data=history_data_start
        )
        assert result_start['success'] is True
        assert result_start['updated'] is True
        assert result_start['task'].task_status == TaskStatus.RUNNING
        assert result_start['task'].scrape_phase == ScrapePhase.LINK_COLLECTION
        assert result_start['history'] is not None
        history_id_start = result_start['history'].id
        assert result_start['history'].task_status == TaskStatus.RUNNING
        assert result_start['history'].start_time == start_time
        assert result_start['history'].end_time is None

        # 驗證 get_task_status 返回正確的運行狀態
        status_running = crawler_task_service.get_task_status(task_id)
        assert status_running['task_status'] == TaskStatus.RUNNING.value
        assert status_running['scrape_phase'] == ScrapePhase.LINK_COLLECTION.value

        # 3. 更新為 COMPLETED, COMPLETED, 更新歷史記錄
        end_time = now
        history_data_end = {
            "end_time": end_time,
            "success": True,
            "articles_count": 10,
            "task_status": TaskStatus.COMPLETED,
            "message": "任務執行成功"
        }
        result_end = crawler_task_service.update_task_status(
            task_id,
            task_status=TaskStatus.COMPLETED,
            scrape_phase=ScrapePhase.COMPLETED,
            history_id=history_id_start,
            history_data=history_data_end
        )
        assert result_end['success'] is True
        assert result_end['updated'] is True
        assert result_end['task'].task_status == TaskStatus.COMPLETED
        assert result_end['task'].scrape_phase == ScrapePhase.COMPLETED
        assert result_end['history'] is not None
        assert result_end['history'].id == history_id_start
        assert result_end['history'].task_status == TaskStatus.COMPLETED
        assert result_end['history'].success is True
        assert result_end['history'].articles_count == 10
        assert result_end['history'].end_time == end_time

        # 驗證 get_task_status 返回完成狀態
        status_completed = crawler_task_service.get_task_status(task_id)
        assert status_completed['task_status'] == TaskStatus.COMPLETED.value
        assert status_completed['scrape_phase'] == ScrapePhase.COMPLETED.value

    def test_increment_retry_count(self, crawler_task_service, sample_tasks):
        """測試增加任務重試次數 (包括邊界條件)"""
        task_id = sample_tasks[0].id
        max_retries = 3

        # 先確保 max_retries 已設置在 task_args 中
        crawler_task_service.update_max_retries(task_id, max_retries)
        crawler_task_service.reset_retry_count(task_id)

        # 獲取初始狀態
        initial_task_result = crawler_task_service.get_task_by_id(task_id)
        assert initial_task_result["success"]
        initial_retry_count = initial_task_result["task"].retry_count
        assert initial_retry_count == 0

        # 增加第一次
        result1 = crawler_task_service.increment_retry_count(task_id)
        assert result1["success"] is True
        assert result1["retry_count"] == 1
        assert result1["exceeded_max_retries"] is False

        # 檢查資料庫
        task_result1 = crawler_task_service.get_task_by_id(task_id)
        assert task_result1["task"].retry_count == 1

        # 增加第二次
        result2 = crawler_task_service.increment_retry_count(task_id)
        assert result2["success"] is True
        assert result2["retry_count"] == 2
        assert result2["exceeded_max_retries"] is False

        # 增加第三次 (達到 max_retries)
        result3 = crawler_task_service.increment_retry_count(task_id)
        assert result3["success"] is True
        assert result3["retry_count"] == 3
        assert result3["exceeded_max_retries"] is True

        # 檢查資料庫
        task_result3 = crawler_task_service.get_task_by_id(task_id)
        assert task_result3["task"].retry_count == 3

        # 嘗試再次增加 (應該失敗)
        result4 = crawler_task_service.increment_retry_count(task_id)
        assert result4["success"] is False
        assert "已達到最大重試次數" in result4["message"]
        assert result4["retry_count"] == 3

        # 測試 max_retries=0 的情況
        crawler_task_service.update_max_retries(task_id, 0)
        crawler_task_service.reset_retry_count(task_id)
        result_zero = crawler_task_service.increment_retry_count(task_id)
        assert result_zero["success"] is False
        assert "任務設定為不允許重試" in result_zero["message"]
        assert result_zero["retry_count"] == 0

    def test_reset_retry_count(self, crawler_task_service, sample_tasks):
        """測試重置任務重試次數"""
        task_id = sample_tasks[0].id
        
        # 先增加重試次數
        crawler_task_service.update_max_retries(task_id, 3)
        crawler_task_service.increment_retry_count(task_id)
        crawler_task_service.increment_retry_count(task_id)
        
        task_before_reset = crawler_task_service.get_task_by_id(task_id)
        assert task_before_reset["task"].retry_count == 2

        # 測試重置重試次數
        result = crawler_task_service.reset_retry_count(task_id)
        assert result["success"] is True
        assert result["task"].retry_count == 0
        
        # 檢查資料庫更新是否成功
        task_result = crawler_task_service.get_task_by_id(task_id)
        assert task_result["success"] is True
        assert task_result["task"].retry_count == 0
        
        # 測試重置已經是 0 的情況
        result_already_zero = crawler_task_service.reset_retry_count(task_id)
        assert result_already_zero["success"] is False
        assert "重試次數已是 0，無需重置" in result_already_zero["message"]
        assert result_already_zero["task"] is None

    def test_update_max_retries(self, crawler_task_service, sample_tasks):
        """測試更新任務最大重試次數"""
        task_id = sample_tasks[0].id
        
        initial_task = crawler_task_service.get_task_by_id(task_id)["task"]
        initial_args = initial_task.task_args.copy() if initial_task.task_args else {}
        
        new_max_retries = 5
        
        result = crawler_task_service.update_max_retries(task_id, new_max_retries)
        assert result["success"] is True
        assert result["task"].task_args.get('max_retries') == new_max_retries
        
        # 檢查更新是否成功 (並驗證其他 task_args 不變)
        task_result = crawler_task_service.get_task_by_id(task_id)
        assert task_result["success"] is True
        updated_args = task_result["task"].task_args
        assert updated_args.get('max_retries') == new_max_retries
        
        # 確保其他參數還在 (如果初始存在的話)
        for key, value in initial_args.items():
            if key != 'max_retries':
                 assert updated_args.get(key) == value

        # 測試無效輸入
        result_neg = crawler_task_service.update_max_retries(task_id, -1)
        assert result_neg["success"] is False
        assert "必須是非負整數" in result_neg["message"]

        result_large = crawler_task_service.update_max_retries(task_id, 100)
        assert result_large["success"] is False
        assert "不能超過" in result_large["message"]

    def test_get_failed_tasks(self, crawler_task_service, sample_tasks):
        """測試獲取最近失敗的任務"""
        days_to_check = 7

        # 準備數據：一個最近失敗的任務
        task_id_fail_recent = sample_tasks[0].id
        crawler_task_service.update_task(task_id_fail_recent, {
            "last_run_success": False,
            "last_run_message": "最近失敗",
            "last_run_at": datetime.now(timezone.utc) - timedelta(days=1),
            "is_active": True,
            "scrape_phase": ScrapePhase.FAILED
        })

        # 準備數據：一個很久以前失敗的任務
        task_id_fail_old = sample_tasks[1].id
        crawler_task_service.update_task(task_id_fail_old, {
            "last_run_success": False,
            "last_run_message": "很久以前失敗",
            "last_run_at": datetime.now(timezone.utc) - timedelta(days=days_to_check + 1),
            "is_active": True,
            "scrape_phase": ScrapePhase.FAILED
        })

        # 準備數據：一個最近成功的任務
        task_id_success_recent = crawler_task_service.create_task({
            "task_name": "最近成功任務", "crawler_id": 1, "is_auto": False,
            "task_args": TASK_ARGS_DEFAULT,
            "last_run_success": True,
            "last_run_message": "最近成功",
            "last_run_at": datetime.now(timezone.utc) - timedelta(days=1),
            "scrape_phase": ScrapePhase.COMPLETED
        })["task"].id

        # 準備數據：一個最近失敗但不活躍的任務
        task_id_fail_inactive = crawler_task_service.create_task({
            "task_name": "最近失敗但不活躍", "crawler_id": 1, "is_auto": False,
            "task_args": TASK_ARGS_DEFAULT,
            "last_run_success": False,
            "last_run_message": "最近失敗但不活躍",
            "last_run_at": datetime.now(timezone.utc) - timedelta(days=1),
            "is_active": False,
            "scrape_phase": ScrapePhase.FAILED
        })["task"].id

        # 執行查詢
        result = crawler_task_service.get_failed_tasks(days=days_to_check)
        assert result["success"] is True
        
        failed_task_ids = [task.id for task in result["tasks"]]
        
        # 驗證：只有 task_id_fail_recent 應該在結果中
        assert task_id_fail_recent in failed_task_ids
        assert task_id_fail_old not in failed_task_ids
        assert task_id_success_recent not in failed_task_ids
        assert task_id_fail_inactive not in failed_task_ids

    def test_update_task_persists_all_fields(self, crawler_task_service, sample_tasks):
        """測試 update_task 是否能正確持久化普通欄位和 task_args 的變更"""
        task_id = sample_tasks[0].id
        print(f"\n--- Testing update_task persistence for task {task_id} ---")

        # 1. 獲取初始狀態
        initial_result = crawler_task_service.get_task_by_id(task_id, is_active=None)
        assert initial_result["success"]
        initial_task = initial_result["task"]
        initial_name = initial_task.task_name
        initial_is_active = initial_task.is_active
        initial_cron = initial_task.cron_expression
        initial_task_args = initial_task.task_args.copy() if initial_task.task_args else {}
        initial_scrape_phase = initial_task.scrape_phase
        print(f"Initial name: {initial_name}, is_active: {initial_is_active}, cron: {initial_cron}, phase: {initial_scrape_phase}, task_args: {initial_task_args}")

        # 2. 準備更新數據 (包含普通欄位和 task_args)
        new_name = "更新後的每日新聞"
        new_is_active = not initial_is_active
        new_cron = "5 0 * * *"
        new_scrape_phase = ScrapePhase.CONTENT_SCRAPING
        new_task_args = initial_task_args.copy()
        new_task_args["max_items"] = 200
        new_task_args["new_param"] = "test_value"
        new_task_args["scrape_mode"] = ScrapeMode.LINKS_ONLY.value

        update_data = {
            "task_name": new_name,
            "is_active": new_is_active,
            "cron_expression": new_cron,
            "scrape_phase": new_scrape_phase.value,
            "task_args":{**TASK_ARGS_DEFAULT, **new_task_args}
        }
        print(f"Update data: {update_data}")

        # 3. 調用 update_task
        update_result = crawler_task_service.update_task(task_id, update_data)
        print(f"Update result: {update_result}")
        assert update_result["success"] is True
        assert update_result["message"] == "任務更新成功"

        # 4. 從資料庫重新獲取並驗證持久化狀態
        print(f"Fetching task {task_id} from DB again after update...")
        refetched_result = crawler_task_service.get_task_by_id(task_id, is_active=None)
        assert refetched_result["success"]
        refetched_task = refetched_result["task"]

        print(f"Refetched name: {refetched_task.task_name}, is_active: {refetched_task.is_active}, cron: {refetched_task.cron_expression}, phase: {refetched_task.scrape_phase}, task_args: {refetched_task.task_args}")
        assert refetched_task.task_name == new_name, "DB value for task_name was not updated correctly"
        assert refetched_task.is_active == new_is_active, "DB value for is_active was not updated correctly"
        assert refetched_task.cron_expression == new_cron, "DB value for cron_expression was not updated correctly"
        assert refetched_task.scrape_phase == new_scrape_phase, "DB value for scrape_phase was not updated correctly"
        assert refetched_task.task_args == {**TASK_ARGS_DEFAULT, **new_task_args}, "DB value for task_args was not updated correctly"
        assert refetched_task.task_args.get("max_items") == 200
        assert refetched_task.task_args.get("new_param") == "test_value"
        assert refetched_task.task_args.get("scrape_mode") == ScrapeMode.LINKS_ONLY.value

        print(f"--- Test update_task persistence finished successfully ---")
