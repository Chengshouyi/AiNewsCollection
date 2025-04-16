import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, JSON, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.models.crawler_tasks_model import CrawlerTasks, ScrapePhase, ScrapeMode, TASK_ARGS_DEFAULT
from src.models.crawlers_model import Crawlers
from src.models.base_model import Base
from src.database.base_repository import SchemaType
from debug.model_info import get_model_info
from src.error.errors import ValidationError, DatabaseOperationError
from unittest.mock import patch
from src.utils.transform_utils import convert_to_dict
import json
import logging
import time

# 設定基礎日誌
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
# 將 SQLAlchemy 引擎的日誌級別設為 DEBUG，以顯示執行的 SQL 和參數
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# 設置測試資料庫
@pytest.fixture(scope="session")
def engine():
    return create_engine('sqlite:///:memory:')

@pytest.fixture(scope="session")
def tables(engine):
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="function")
def session_factory(engine, tables):
    """創建新的會話工廠"""
    return sessionmaker(bind=engine)

@pytest.fixture(scope="function")
def session(session_factory):
    """每次測試使用新的會話"""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture(scope="function")
def crawler_tasks_repo(session):
    return CrawlerTasksRepository(session, CrawlerTasks)

@pytest.fixture(scope="function")
def clean_db(session):
    """清空資料庫的 fixture"""
    session.query(CrawlerTasks).delete()
    session.query(Crawlers).delete()
    session.commit()
    session.expire_all()

@pytest.fixture(scope="function")
def sample_crawler(session, clean_db):
    crawler = Crawlers(
        crawler_name="測試爬蟲",
        base_url="https://example.com",
        is_active=True,
        crawler_type="news",
        config_file_name="test_crawler_config.json"
    )
    session.add(crawler)
    session.commit()
    return crawler

@pytest.fixture(scope="function")
def sample_tasks(session, clean_db, sample_crawler):
    # 先清理表
    session.query(CrawlerTasks).delete()
    session.commit()

    tasks = [
        CrawlerTasks(
            task_name="自動AI任務(活動)",
            crawler_id=sample_crawler.id,
            is_auto=True,
            is_scheduled=True,
            task_args={**TASK_ARGS_DEFAULT, "ai_only": True},
            notes="自動AI任務",
            cron_expression="* * * * *",
            scrape_phase=ScrapePhase.INIT,
            max_retries=3,
            retry_count=0,
            is_active=True # 活動
        ),
        CrawlerTasks(
            task_name="自動一般任務(活動)",
            crawler_id=sample_crawler.id,
            is_auto=True,
            is_scheduled=True,
            task_args={**TASK_ARGS_DEFAULT, "ai_only": False},
            notes="自動一般任務",
            cron_expression="* * * * *",
            scrape_phase=ScrapePhase.INIT,
            max_retries=3,
            retry_count=0,
            is_active=True # 活動
        ),
        CrawlerTasks(
            task_name="手動AI任務(活動)",
            crawler_id=sample_crawler.id,
            is_auto=False,
            is_scheduled=False,
            task_args={**TASK_ARGS_DEFAULT, "ai_only": True},
            notes="手動AI任務",
            # cron_expression="* * * * *", # 手動任務不需要cron
            scrape_phase=ScrapePhase.INIT,
            max_retries=3,
            retry_count=0,
            is_active=True # 活動
        ),
        CrawlerTasks(
            task_name="自動一般任務(非活動)",
            crawler_id=sample_crawler.id,
            is_auto=True, # 雖然是自動，但不活動
            is_scheduled=True,
            task_args={**TASK_ARGS_DEFAULT, "ai_only": False},
            notes="非活動任務",
            cron_expression="0 0 * * *",
            scrape_phase=ScrapePhase.INIT,
            max_retries=3,
            retry_count=0,
            is_active=False # 非活動
        ),
         CrawlerTasks(
            task_name="手動AI任務(非活動)",
            crawler_id=sample_crawler.id,
            is_auto=False,
            is_scheduled=False,
            task_args={**TASK_ARGS_DEFAULT, "ai_only": True},
            notes="非活動手動AI任務",
            scrape_phase=ScrapePhase.INIT,
            max_retries=3,
            retry_count=0,
            is_active=False # 非活動
        )
    ]
    session.add_all(tasks)
    session.commit()

    # 明確刷新所有物件以確保 ID 都已賦值
    for task in tasks:
        session.refresh(task)

    return tasks

class TestCrawlerTasksRepository:
    """CrawlerTasksRepository 測試類"""
    
    def test_find_by_crawler_id(self, crawler_tasks_repo, sample_tasks, sample_crawler):
        """測試根據爬蟲ID查詢任務 (包含is_active)"""
        crawler_id = sample_crawler.id
        active_count = sum(1 for t in sample_tasks if t.crawler_id == crawler_id and t.is_active)
        inactive_count = sum(1 for t in sample_tasks if t.crawler_id == crawler_id and not t.is_active)
        total_count = active_count + inactive_count

        # 預設 is_active=True
        tasks_active = crawler_tasks_repo.find_tasks_by_crawler_id(crawler_id)
        assert len(tasks_active) == active_count
        assert all(task.crawler_id == crawler_id and task.is_active for task in tasks_active)

        # is_active=False
        tasks_inactive = crawler_tasks_repo.find_tasks_by_crawler_id(crawler_id, is_active=False)
        assert len(tasks_inactive) == inactive_count
        assert all(task.crawler_id == crawler_id and not task.is_active for task in tasks_inactive)

        # is_active=None (BaseRepository 方法) - 需確認 BaseRepository 是否支援 is_active=None
        # BaseRepository 的 get_all 可能沒有 is_active 過濾，find_by 可能有，這裡假設 find_tasks_by_crawler_id 不直接支援 None
        # 如果需要測試 is_active=None，可能需要直接調用更底層的方法或修改 repository

    def test_find_auto_tasks(self, crawler_tasks_repo, sample_tasks):
        """測試查詢自動執行的任務 (包含is_active)"""
        active_auto_count = sum(1 for t in sample_tasks if t.is_auto and t.is_active)
        inactive_auto_count = sum(1 for t in sample_tasks if t.is_auto and not t.is_active)

        # 預設 is_active=True
        auto_tasks_active = crawler_tasks_repo.find_auto_tasks()
        assert len(auto_tasks_active) == active_auto_count
        assert all(task.is_auto and task.is_active for task in auto_tasks_active)

        # is_active=False
        auto_tasks_inactive = crawler_tasks_repo.find_auto_tasks(is_active=False)
        assert len(auto_tasks_inactive) == inactive_auto_count
        assert all(task.is_auto and not task.is_active for task in auto_tasks_inactive)

    def test_find_scheduled_tasks(self, crawler_tasks_repo, sample_tasks):
        """測試查詢已排程的任務 (包含is_active)"""
        active_scheduled_count = sum(1 for t in sample_tasks if t.is_scheduled and t.is_active)
        inactive_scheduled_count = sum(1 for t in sample_tasks if t.is_scheduled and not t.is_active)

        # 預設 is_active=True
        scheduled_tasks_active = crawler_tasks_repo.find_scheduled_tasks()
        assert len(scheduled_tasks_active) == active_scheduled_count
        assert all(task.is_scheduled and task.is_active for task in scheduled_tasks_active)

        # is_active=False
        scheduled_tasks_inactive = crawler_tasks_repo.find_scheduled_tasks(is_active=False)
        assert len(scheduled_tasks_inactive) == inactive_scheduled_count
        assert all(task.is_scheduled and not task.is_active for task in scheduled_tasks_inactive)

    def test_find_ai_only_tasks(self, crawler_tasks_repo, sample_tasks):
        """測試查詢AI相關的任務 (包含is_active)"""
        active_ai_count = sum(1 for t in sample_tasks if t.task_args.get('ai_only') is True and t.is_active)
        inactive_ai_count = sum(1 for t in sample_tasks if t.task_args.get('ai_only') is True and not t.is_active)

        # 預設 is_active=True
        ai_tasks_active = crawler_tasks_repo.find_ai_only_tasks()
        print(f"\n找到 {len(ai_tasks_active)} 個活動的 AI 專用任務")
        assert len(ai_tasks_active) == active_ai_count
        assert all(task.task_args.get('ai_only') is True and task.is_active for task in ai_tasks_active)

        # is_active=False
        ai_tasks_inactive = crawler_tasks_repo.find_ai_only_tasks(is_active=False)
        print(f"\n找到 {len(ai_tasks_inactive)} 個非活動的 AI 專用任務")
        assert len(ai_tasks_inactive) == inactive_ai_count
        assert all(task.task_args.get('ai_only') is True and not task.is_active for task in ai_tasks_inactive)

    def test_find_tasks_by_crawler_and_auto(self, crawler_tasks_repo, sample_tasks, sample_crawler):
        """測試根據爬蟲ID和自動執行狀態查詢任務"""
        # 使用現有方法並在 Python 中過濾
        all_tasks = crawler_tasks_repo.find_tasks_by_crawler_id(sample_crawler.id)
        auto_tasks = [task for task in all_tasks if task.is_auto]
        
        assert len(auto_tasks) == 2
        assert all(task.crawler_id == sample_crawler.id and task.is_auto for task in auto_tasks)

    def test_toggle_auto_status(self, crawler_tasks_repo, sample_tasks, session):
        """測試切換自動執行狀態"""
        task = sample_tasks[0]
        original_status = task.is_auto
        
        # 確保任務存在於數據庫
        task_id = task.id
        
        # 切換狀態
        result = crawler_tasks_repo.toggle_auto_status(task_id)
        assert result is True
        
        # 重新獲取任務並驗證狀態
        session.expire_all()  # 確保重新從數據庫加載
        updated_task = crawler_tasks_repo.get_by_id(task_id)
        assert updated_task.is_auto != original_status
        assert updated_task.updated_at is not None

    def test_toggle_scheduled_status(self, crawler_tasks_repo, sample_tasks, session):
        """測試切換排程狀態"""
        task = sample_tasks[0]
        original_status = task.is_scheduled
        task_id = task.id
        
        # 切換狀態
        result = crawler_tasks_repo.toggle_scheduled_status(task_id)
        assert result is True
        
        # 重新獲取任務並驗證狀態
        session.expire_all()  # 確保重新從數據庫加載
        updated_task = crawler_tasks_repo.get_by_id(task_id)    
        assert updated_task.is_scheduled != original_status
        assert updated_task.updated_at is not None

    def test_update_ai_only_status(self, crawler_tasks_repo, sample_tasks, session):
        """測試更新 task_args 中的 ai_only 狀態 (模擬正確的 JSON 更新流程)"""
        # 選擇一個 ai_only 為 False 的活動任務
        task_to_update_orig = next((t for t in sample_tasks if not t.task_args.get('ai_only') and t.is_active), None)
        assert task_to_update_orig is not None, "找不到適合測試的任務 (ai_only=False, is_active=True)"

        task_id = task_to_update_orig.id
        original_args = task_to_update_orig.task_args.copy()
        print(f"\n--- test_update_ai_only_status (Corrected for JSON) ---")
        print(f"Task ID: {task_id}, Original task_args: {original_args}")

        # 1. 準備新的 task_args 數據
        new_task_args = original_args.copy()
        new_task_args['ai_only'] = True
        print(f"New task_args payload: {new_task_args}")

        # --- 模擬 Service 層的正確更新步驟 ---
        # a. 從當前 session 獲取實體
        task_in_session = session.get(CrawlerTasks, task_id)
        assert task_in_session is not None

        # b. 將新字典賦值給屬性
        task_in_session.task_args = new_task_args

        # c. 標記欄位已修改 (關鍵步驟 for JSON)
        flag_modified(task_in_session, 'task_args')

        # d. 提交事務 (由測試 session 控制)
        session.commit()
        # --- 模擬結束 ---

        # 4. 清除快取並重新從 DB 讀取驗證
        session.expire(task_in_session) # 使其從 DB 重新加載
        reloaded_task = crawler_tasks_repo.get_by_id(task_id) # 使用 repo 方法重新獲取

        # 5. 斷言重新載入後的物件狀態
        assert reloaded_task is not None
        print(f"Reloaded task_args from DB: {reloaded_task.task_args}")
        assert reloaded_task.task_args.get('ai_only') is True, "DB value for 'ai_only' should be updated to True"
        # 確保其他 task_args 不變
        for key, value in original_args.items():
            if key != 'ai_only':
                assert reloaded_task.task_args.get(key) == value, f"Key '{key}' in task_args should remain unchanged"
        print(f"--- Test finished successfully ---")

    def test_update_notes(self, crawler_tasks_repo, sample_tasks, session):
        """測試更新備註"""
        task = sample_tasks[0]
        task_id = task.id
        new_notes = "更新的備註"
        
        # 更新備註
        result = crawler_tasks_repo.update_notes(task_id, new_notes)
        assert result is True
        
        # 重新獲取任務並驗證備註
        session.expire_all()  # 確保重新從數據庫加載
        updated_task = crawler_tasks_repo.get_by_id(task_id)
        assert updated_task.notes == new_notes
        assert updated_task.updated_at is not None

    def test_find_tasks_with_notes(self, crawler_tasks_repo, sample_tasks):
        """測試查詢有備註的任務"""
        tasks = crawler_tasks_repo.find_tasks_with_notes()
        assert len(tasks) == 5
        assert all(task.notes is not None for task in tasks)

    def test_find_tasks_by_multiple_crawlers(self, crawler_tasks_repo, sample_tasks, sample_crawler):
        """測試根據多個爬蟲ID查詢任務"""
        tasks = crawler_tasks_repo.find_tasks_by_multiple_crawlers([sample_crawler.id])
        assert len(tasks) == 5
        assert all(task.crawler_id == sample_crawler.id for task in tasks)

    def test_get_tasks_count_by_crawler(self, crawler_tasks_repo, sample_tasks, sample_crawler):
        """測試獲取特定爬蟲的任務數量"""
        count = crawler_tasks_repo.get_tasks_count_by_crawler(sample_crawler.id)
        assert count == 5

    def test_find_tasks_by_cron_expression(self, crawler_tasks_repo, session, sample_crawler):
        """測試根據 cron 表達式查詢任務"""
        # 建立測試資料
        tasks = [
            CrawlerTasks(
                task_name="每小時執行任務",
                crawler_id=sample_crawler.id,
                is_auto=True,
                cron_expression="0 * * * *",  # 每小時執行
                task_args={**TASK_ARGS_DEFAULT,"ai_only": False},  
                scrape_phase=ScrapePhase.INIT,
                max_retries=3,
                retry_count=0
            ),
            CrawlerTasks(
                task_name="每天執行任務",
                crawler_id=sample_crawler.id,
                is_auto=True,
                cron_expression="0 0 * * *",  # 每天執行
                task_args={**TASK_ARGS_DEFAULT,"ai_only": False},  
                scrape_phase=ScrapePhase.INIT,
                max_retries=3,
                retry_count=0
            ),
            CrawlerTasks(
                task_name="每週執行任務",
                crawler_id=sample_crawler.id,
                is_auto=True,
                cron_expression="0 0 * * 1",  # 每週一執行
                task_args={**TASK_ARGS_DEFAULT,"ai_only": False},  
                scrape_phase=ScrapePhase.INIT,
                max_retries=3,
                retry_count=0
            )
        ]
        session.add_all(tasks)
        session.commit()
        
        # 測試查詢
        hourly_tasks = crawler_tasks_repo.find_tasks_by_cron_expression("0 * * * *")
        assert len(hourly_tasks) == 1
        assert all(task.cron_expression == "0 * * * *" and task.is_auto for task in hourly_tasks)

        # 測試無效的 cron 表達式
        with pytest.raises(ValidationError) as excinfo:
            crawler_tasks_repo.find_tasks_by_cron_expression("invalid")
        assert "無效的 cron 表達式" in str(excinfo.value)

    def test_find_pending_tasks(self, crawler_tasks_repo, session, sample_crawler):
        """測試查詢待執行的任務"""
        # 清除干擾資料
        session.query(CrawlerTasks).delete()
        session.commit()
        
        now = datetime.now(timezone.utc)  # 使用 UTC 時間
        
        # 創建三種情況的任務：
        # 1. 上次執行超過1小時（應該被找到）
        task1 = CrawlerTasks(
            task_name="超過1小時任務",
            crawler_id=sample_crawler.id,
            is_auto=True,
            cron_expression="0 * * * *",  # 每小時執行（整點）
            last_run_at=now - timedelta(hours=2),
            task_args={**TASK_ARGS_DEFAULT,"ai_only": False}, 
            scrape_phase=ScrapePhase.INIT,
            max_retries=3,
            retry_count=0
        )
        
        # 2. 上次執行不到1小時（不應該被找到）
        task2 = CrawlerTasks(
            task_name="不到1小時任務",
            crawler_id=sample_crawler.id,
            is_auto=True,
            cron_expression="0 * * * *",
            last_run_at=now - timedelta(minutes=30),
            task_args={**TASK_ARGS_DEFAULT,"ai_only": False},  
            scrape_phase=ScrapePhase.INIT,
            max_retries=3,
            retry_count=0
        )
        
        # 3. 從未執行過（應該被找到）
        task3 = CrawlerTasks(
            task_name="從未執行任務",
            crawler_id=sample_crawler.id,
            is_auto=True,
            cron_expression="0 * * * *",
            last_run_at=None,
            task_args={**TASK_ARGS_DEFAULT,"ai_only": False},  
            scrape_phase=ScrapePhase.INIT,
            max_retries=3,
            retry_count=0
        )
        
        session.add_all([task1, task2, task3])
        session.commit()
        
        # 確保刷新資料
        session.refresh(task1)
        session.refresh(task2)
        session.refresh(task3)
        
        # 執行測試
        pending_tasks = crawler_tasks_repo.find_pending_tasks("0 * * * *")
        
        # 取得找到的任務 ID 集合
        found_ids = {task.id for task in pending_tasks}
        
        # 驗證結果
        assert task1.id in found_ids, f"未找到超過1小時的任務 (ID: {task1.id})"
        assert task3.id in found_ids, f"未找到從未執行過的任務 (ID: {task3.id})"
        assert task2.id not in found_ids, f"錯誤找到未超過1小時的任務 (ID: {task2.id})"
        assert len(pending_tasks) == 2, f"預期找到 2 個待執行任務，但實際找到 {len(pending_tasks)} 個"

    def test_get_failed_tasks(self, crawler_tasks_repo, session, sample_crawler):
        """測試獲取失敗的任務"""
        # 清除干擾資料
        session.query(CrawlerTasks).delete()
        session.commit()
        
        base_time = datetime.now(timezone.utc)  # 使用 UTC 時間作為基準
        tasks = [
            CrawlerTasks(
                task_name="失敗任務1",
                crawler_id=sample_crawler.id,
                last_run_success=False,
                last_run_at=base_time - timedelta(days=2),  # 超過1天，不應該被查到
                task_args={**TASK_ARGS_DEFAULT,"ai_only": False},  
                scrape_phase=ScrapePhase.INIT,
                max_retries=3,
                retry_count=0
            ),
            CrawlerTasks(
                task_name="失敗任務2",
                crawler_id=sample_crawler.id,
                last_run_success=False,
                last_run_at=base_time - timedelta(hours=12),  # 應該被查到
                task_args={**TASK_ARGS_DEFAULT,"ai_only": False}, 
                scrape_phase=ScrapePhase.INIT,
                max_retries=3,
                retry_count=0
            ),
            CrawlerTasks(
                task_name="成功任務",
                crawler_id=sample_crawler.id,
                last_run_success=True,
                last_run_at=base_time - timedelta(hours=1),  # 成功的任務，不應該被查到
                task_args={**TASK_ARGS_DEFAULT,"ai_only": False}, 
                scrape_phase=ScrapePhase.INIT,
                max_retries=3,
                retry_count=0
            )
        ]
        session.add_all(tasks)
        session.commit()

        # 測試查詢
        failed_tasks = crawler_tasks_repo.get_failed_tasks(days=1)
        assert len(failed_tasks) == 1
        assert all(not task.last_run_success for task in failed_tasks)
        assert all(task.last_run_at >= datetime.now(timezone.utc) - timedelta(days=1) for task in failed_tasks)

    def test_create_task_with_validation(self, crawler_tasks_repo, sample_crawler):
        """測試創建任務時的驗證規則"""
        # 測試缺少必填欄位
        with pytest.raises(ValidationError) as excinfo:
            crawler_tasks_repo.create({
                "task_name": "測試任務",
                "is_auto": True,
                "cron_expression": "0 * * * *",
                "task_args": {**TASK_ARGS_DEFAULT,"ai_only": False},  
                "scrape_phase": ScrapePhase.INIT,
                "max_retries": 3,
                "retry_count": 0,
                "scrape_mode": ScrapeMode.FULL_SCRAPE
            })
        assert "CREATE 資料驗證失敗: crawler_id: 不能為空" in str(excinfo.value)
    
        
        # 測試成功創建
        task = crawler_tasks_repo.create({
            "task_name": "測試任務",
            "crawler_id": sample_crawler.id,
            "task_args": {**TASK_ARGS_DEFAULT,"ai_only": False},  
            "is_auto": True,
            "cron_expression": "0 * * * *",
            "scrape_phase": ScrapePhase.INIT,
            "max_retries": 3,
            "retry_count": 0,
            "scrape_mode": ScrapeMode.FULL_SCRAPE
        })
        assert task.crawler_id == sample_crawler.id
        assert task.is_auto is True
        assert task.cron_expression == "0 * * * *"
        assert task.task_args.get('ai_only') is False

    def test_update_task_with_validation(self, crawler_tasks_repo, session, sample_crawler):
        """測試更新任務時的驗證規則"""
        # 創建新任務
        task = CrawlerTasks(
            task_name="測試任務",
            crawler_id=sample_crawler.id,
            is_auto=False,
            task_args={**TASK_ARGS_DEFAULT, "ai_only": False}  # 設置 ai_only
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        
        task_id = task.id
        
        # 測試更新不可變欄位
        with pytest.raises(ValidationError) as excinfo:
            crawler_tasks_repo.update(task_id, {
                "crawler_id": 999,  # 嘗試更新 crawler_id
                "cron_expression": "0 * * * *"
            })
        assert "不允許更新 crawler_id 欄位" in str(excinfo.value)
        
        # 測試自動執行時缺少 cron_expression
        session.expire_all()  # 確保重新從數據庫加載
        
        # 測試自動執行時缺少 cron_expression->移到service
        # with pytest.raises(ValidationError) as excinfo:
        #     crawler_tasks_repo.update(task_id, {
        #         "is_auto": True,
        #         "cron_expression": None
        #     })
        # assert "cron_expression: 當設定為自動執行時,此欄位不能為空" in str(excinfo.value)
        
        # 測試成功更新
        session.expire_all()  # 確保重新從數據庫加載
        
        updated_task = crawler_tasks_repo.update(task_id, {
            "is_auto": True,
            "cron_expression": "0 * * * *",
            "task_args": {**TASK_ARGS_DEFAULT,"ai_only": True} 
        })
        assert updated_task.is_auto is True
        assert updated_task.cron_expression == "0 * * * *"
        assert updated_task.task_args.get('ai_only') is True

    def test_default_values(self, crawler_tasks_repo, sample_crawler):
        """測試新建任務時的預設值"""
        task = crawler_tasks_repo.create({
            "task_name": "測試任務",
            "crawler_id": sample_crawler.id,
            "is_auto": False,  # 手動執行不需要 cron_expression
            "task_args": {**TASK_ARGS_DEFAULT,"max_retries": 3, "retry_count": 0, "scrape_mode": ScrapeMode.FULL_SCRAPE.value},
            "scrape_phase": ScrapePhase.INIT
        })
        assert task.is_auto is False
        assert task.task_args.get('ai_only') is False  # 預設值應為 False
        assert task.scrape_phase == ScrapePhase.INIT
        assert task.task_args.get('max_retries') == 3
        assert task.task_args.get('retry_count') == 0
        assert task.task_args.get('scrape_mode') == ScrapeMode.FULL_SCRAPE.value

    def test_find_tasks_by_id(self, crawler_tasks_repo, sample_tasks, session):
        """測試根據任務ID查詢任務"""
        active_task = next(t for t in sample_tasks if t.is_active)
        inactive_task = next(t for t in sample_tasks if not t.is_active)

        # 1. 查詢存在的活動任務 (預設 is_active=True)
        found_task = crawler_tasks_repo.find_tasks_by_id(active_task.id)
        assert found_task is not None
        assert found_task.id == active_task.id
        assert found_task.is_active is True

        # 2. 查詢存在的活動任務 (明確 is_active=True)
        found_task = crawler_tasks_repo.find_tasks_by_id(active_task.id, is_active=True)
        assert found_task is not None
        assert found_task.id == active_task.id
        assert found_task.is_active is True

        # 3. 查詢存在的非活動任務 (使用 is_active=False)
        found_task = crawler_tasks_repo.find_tasks_by_id(inactive_task.id, is_active=False)
        assert found_task is not None
        assert found_task.id == inactive_task.id
        assert found_task.is_active is False

        # 4. 查詢存在的非活動任務 (使用 is_active=True 應找不到)
        found_task = crawler_tasks_repo.find_tasks_by_id(inactive_task.id, is_active=True)
        assert found_task is None

        # 5. 查詢存在的活動任務 (使用 is_active=None)
        found_task = crawler_tasks_repo.find_tasks_by_id(active_task.id, is_active=None)
        assert found_task is not None
        assert found_task.id == active_task.id

        # 6. 查詢存在的非活動任務 (使用 is_active=None)
        found_task = crawler_tasks_repo.find_tasks_by_id(inactive_task.id, is_active=None)
        assert found_task is not None
        assert found_task.id == inactive_task.id

        # 7. 查詢不存在的任務ID
        found_task = crawler_tasks_repo.find_tasks_by_id(99999)
        assert found_task is None

    def test_toggle_ai_only_status(self, crawler_tasks_repo, sample_tasks, session):
        """測試直接切換 AI 專用狀態"""
        task_false_to_true = next(t for t in sample_tasks if t.task_args.get('ai_only') is False and t.is_active)
        task_true_to_false = next(t for t in sample_tasks if t.task_args.get('ai_only') is True and t.is_active)
        task_id_1 = task_false_to_true.id
        task_id_2 = task_true_to_false.id

        # 1. 從 False 切換到 True
        result1 = crawler_tasks_repo.toggle_ai_only_status(task_id_1)
        assert result1 is True
        session.expire(task_false_to_true) # 清除緩存
        updated_task_1 = crawler_tasks_repo.get_by_id(task_id_1)
        assert updated_task_1.task_args.get('ai_only') is True
        assert updated_task_1.updated_at is not None

        # 2. 從 True 切換到 False
        last_updated_at = updated_task_1.updated_at # 記錄時間以便比較
        result2 = crawler_tasks_repo.toggle_ai_only_status(task_id_2)
        assert result2 is True
        session.expire(task_true_to_false) # 清除緩存
        updated_task_2 = crawler_tasks_repo.get_by_id(task_id_2)
        assert updated_task_2.task_args.get('ai_only') is False
        assert updated_task_2.updated_at is not None
        assert updated_task_2.updated_at > last_updated_at # 確保 updated_at 已更新

        # 3. 測試 task_args 為 None 的情況 (需要創建一個新任務)
        new_task = CrawlerTasks(
            task_name="無task_args測試",
            crawler_id=sample_tasks[0].crawler_id,
            task_args=None,
            is_active=True
        )
        session.add(new_task)
        session.commit()
        session.refresh(new_task)
        task_id_3 = new_task.id

        result3 = crawler_tasks_repo.toggle_ai_only_status(task_id_3)
        assert result3 is True
        session.expire(new_task)
        updated_task_3 = crawler_tasks_repo.get_by_id(task_id_3)
        assert updated_task_3.task_args.get('ai_only') is True # 應從預設 False 切換為 True

        # 4. 測試 task_args 存在但無 'ai_only' 鍵的情況 (修改現有任務)
        task_to_modify = crawler_tasks_repo.get_by_id(task_id_1) # 這個現在是 True
        task_to_modify.task_args = {"other_key": "value"} # 移除 ai_only
        session.commit()
        session.refresh(task_to_modify)

        result4 = crawler_tasks_repo.toggle_ai_only_status(task_id_1)
        assert result4 is True
        session.expire(task_to_modify)
        updated_task_4 = crawler_tasks_repo.get_by_id(task_id_1)
        assert updated_task_4.task_args.get('ai_only') is True # 應從預設 False 切換為 True

    def test_toggle_active_status(self, crawler_tasks_repo, sample_tasks, session):
        """測試切換啟用狀態"""
        active_task = next(t for t in sample_tasks if t.is_active)
        inactive_task = next(t for t in sample_tasks if not t.is_active)
        active_task_id = active_task.id
        inactive_task_id = inactive_task.id

        # 1. 從 True 切換到 False
        result1 = crawler_tasks_repo.toggle_active_status(active_task_id)
        assert result1 is True
        session.expire(active_task)
        updated_task_1 = crawler_tasks_repo.get_by_id(active_task_id)
        assert updated_task_1.is_active is False
        assert updated_task_1.updated_at is not None
        original_updated_at = updated_task_1.updated_at

        # 2. 從 False 切換到 True
        result2 = crawler_tasks_repo.toggle_active_status(inactive_task_id)
        assert result2 is True
        session.expire(inactive_task)
        updated_task_2 = crawler_tasks_repo.get_by_id(inactive_task_id)
        assert updated_task_2.is_active is True
        assert updated_task_2.updated_at is not None
        assert updated_task_2.updated_at > original_updated_at

        # 3. 切換不存在的任務
        result3 = crawler_tasks_repo.toggle_active_status(99999)
        assert result3 is False

    def test_update_last_run(self, crawler_tasks_repo, sample_tasks, session):
        """測試更新最後執行狀態"""
        task = sample_tasks[0]
        task_id = task.id
        original_last_run_at = task.last_run_at

        # 1. 更新為成功
        success_message = "執行成功"
        result1 = crawler_tasks_repo.update_last_run(task_id, success=True, message=success_message)
        assert result1 is True
        session.expire(task)
        updated_task_1 = crawler_tasks_repo.get_by_id(task_id)
        assert updated_task_1.last_run_success is True
        assert updated_task_1.last_run_message == success_message
        assert updated_task_1.last_run_at is not None
        assert updated_task_1.updated_at is not None
        if original_last_run_at:
             assert updated_task_1.last_run_at > original_last_run_at
        last_run_time_1 = updated_task_1.last_run_at
        updated_at_1 = updated_task_1.updated_at # 記錄第一次更新後的時間

        # 在兩次更新之間加入微小的延遲
        time.sleep(0.01) # 增加延遲到 10 毫秒

        # 2. 更新為失敗 (無消息)
        result2 = crawler_tasks_repo.update_last_run(task_id, success=False)
        assert result2 is True
        session.expire(updated_task_1) # 或者 session.expire(task_in_session) 也可以
        updated_task_2 = crawler_tasks_repo.get_by_id(task_id)
        assert updated_task_2.last_run_success is False
        # 訊息應該保持上次成功的訊息，因為這次沒提供
        assert updated_task_2.last_run_message == success_message
        assert updated_task_2.last_run_at is not None
        assert updated_task_2.last_run_at > last_run_time_1
        assert updated_task_2.updated_at is not None
        assert updated_task_2.updated_at > updated_at_1 # 使用記錄的時間比較

        # 在兩次更新之間加入微小的延遲
        time.sleep(0.01) # 增加延遲到 10 毫秒

        # 3. 更新為失敗 (有新消息)
        failure_message = "執行失敗：超時"
        updated_at_2 = updated_task_2.updated_at # 記錄第二次更新後的時間
        last_run_time_2 = updated_task_2.last_run_at # <--- 記錄第二次的 last_run_at
        result3 = crawler_tasks_repo.update_last_run(task_id, success=False, message=failure_message)
        assert result3 is True
        session.expire(updated_task_2)
        updated_task_3 = crawler_tasks_repo.get_by_id(task_id)
        assert updated_task_3.last_run_success is False
        assert updated_task_3.last_run_message == failure_message
        assert updated_task_3.last_run_at is not None
        assert updated_task_3.last_run_at > last_run_time_2 # <--- 與記錄的時間比較
        assert updated_task_3.updated_at is not None
        assert updated_task_3.updated_at > updated_at_2 # 使用記錄的時間比較

        # 4. 更新不存在的任務
        result4 = crawler_tasks_repo.update_last_run(99999, success=True)
        assert result4 is False

class TestCrawlerTasksConstraints:
    """測試CrawlerTasks的模型約束"""
    
    def test_boolean_defaults(self, session, sample_crawler):
        """測試布林欄位的默認值"""
        task = CrawlerTasks(
            task_name="測試任務",
            crawler_id=sample_crawler.id,
            task_args=TASK_ARGS_DEFAULT,
            scrape_phase=ScrapePhase.INIT,
            max_retries=3,
            retry_count=0,
            scrape_mode=ScrapeMode.FULL_SCRAPE
        )
        session.add(task)
        session.flush()
        
        assert task.is_auto is True  # 默認為True
        assert task.task_args.get('ai_only') is False  # 預設為False
        assert task.scrape_mode == ScrapeMode.FULL_SCRAPE

class TestModelStructure:
    """測試模型結構"""
    
    def test_crawler_tasks_model_structure(self):
        """測試CrawlerTasks模型結構"""
        model_info = get_model_info(CrawlerTasks)
        
        # 測試表名
        assert model_info["table"] == "crawler_tasks"
        
        # 測試主鍵
        assert "id" in model_info["primary_key"]
        
        # 測試外鍵
        foreign_keys = model_info.get("foreign_keys", [])
        # 檢查是否有指向 crawlers 表的外鍵
        has_crawler_fk = False
        for fk in foreign_keys:
            if "crawler_id" in str(fk):  # 使用更寬鬆的檢查
                has_crawler_fk = True
                break
        assert has_crawler_fk, "應該有指向 crawlers 表的外鍵"
        
        # 測試必填欄位
        required_fields = []
        for field, info in model_info["columns"].items():
            if not info["nullable"] and info["default"] is None:
                required_fields.append(field)
        
        assert "crawler_id" in required_fields

class TestSpecialCases:
    """測試特殊情況"""
    
    def test_empty_database(self, crawler_tasks_repo, session):
        """測試空數據庫的情況"""
        # 確保清空資料
        session.query(CrawlerTasks).delete()
        session.commit()
        
        assert crawler_tasks_repo.get_all() == []
        assert crawler_tasks_repo.find_auto_tasks() == []
        assert crawler_tasks_repo.find_ai_only_tasks() == []

    def test_invalid_operations(self, crawler_tasks_repo):
        """測試無效操作"""
        # 測試不存在的任務ID
        assert crawler_tasks_repo.toggle_auto_status(999) is False
        assert crawler_tasks_repo.toggle_ai_only_status(999) is False
        assert crawler_tasks_repo.update_notes(999, "test") is False

    def test_invalid_cron_operations(self, crawler_tasks_repo):
        """測試無效的 cron 操作"""
        with pytest.raises(ValidationError):
            crawler_tasks_repo.find_tasks_by_cron_expression("invalid")
            
        with pytest.raises(ValidationError):
            crawler_tasks_repo.find_pending_tasks("invalid")

    def test_empty_cron_results(self, crawler_tasks_repo, session):
        """測試空的 cron 結果"""
        # 確保清空資料
        session.query(CrawlerTasks).delete()
        session.commit()
        
        assert crawler_tasks_repo.find_tasks_by_cron_expression("0 * * * *") == []
        assert crawler_tasks_repo.find_pending_tasks("0 0 * * *") == []

    def test_cron_with_no_auto_tasks(self, crawler_tasks_repo, session, sample_crawler):
        """測試沒有自動執行的 cron 任務"""
        # 確保清空資料
        session.query(CrawlerTasks).delete()
        session.commit()
        
        task = CrawlerTasks(
            task_name="測試任務",
            crawler_id=sample_crawler.id,
            is_auto=False,
            cron_expression="0 * * * *"
        )
        session.add(task)
        session.commit()

        assert len(crawler_tasks_repo.find_tasks_by_cron_expression("0 * * * *")) == 0
        assert len(crawler_tasks_repo.find_pending_tasks("0 * * * *")) == 0

class TestCrawlerTasksRepositoryValidation:
    """CrawlerTasksRepository 驗證相關的測試類"""
    
    def test_validate_data_create(self, crawler_tasks_repo, sample_crawler):
        """測試 validate_data 方法用於創建操作時的行為"""
        # 準備有效的數據
        valid_data = {
            "task_name": "測試驗證任務",
            "crawler_id": sample_crawler.id,
            "is_auto": True,
            "cron_expression": "0 * * * *",
            "ai_only": False,
            "task_args": TASK_ARGS_DEFAULT,
            "scrape_phase": ScrapePhase.INIT,
            "max_retries": 3,
            "retry_count": 0,
            "scrape_mode": ScrapeMode.FULL_SCRAPE
        }
        
        # 執行驗證
        validated_result = crawler_tasks_repo.validate_data(valid_data, SchemaType.CREATE)
        
        # 檢查驗證後的數據是否完整
        assert validated_result.get('data', {}).get("task_name") == "測試驗證任務"
        assert validated_result.get('data', {}).get("crawler_id") == sample_crawler.id
        assert validated_result.get('data', {}).get("is_auto") is True
        assert validated_result.get('data', {}).get("cron_expression") == "0 * * * *"
        assert "task_args" in validated_result.get('data', {})
        assert validated_result.get('data', {}).get("scrape_phase") == ScrapePhase.INIT
        assert validated_result.get('data', {}).get("task_args", {}).get("scrape_mode") == ScrapeMode.FULL_SCRAPE.value
        # 測試無效數據
        invalid_data = {
            "task_name": "測試驗證任務",
            # 缺少 crawler_id
            "is_auto": True,
            "cron_expression": "0 * * * *"
        }
        
        # 執行驗證應拋出異常
        with pytest.raises(ValidationError) as excinfo:
            crawler_tasks_repo.validate_data(invalid_data, SchemaType.CREATE)
        assert "不能為空" in str(excinfo.value)
        
    def test_validate_data_update(self, crawler_tasks_repo, sample_crawler):
        """測試 validate_data 方法用於更新操作時的行為"""
        # 準備有效的更新數據
        valid_update = {
            "task_name": "更新的任務名稱",
            "is_auto": False,
            # 不需要 cron_expression，因為 is_auto=False
        }
        
        # 執行驗證
        validated_result = crawler_tasks_repo.validate_data(valid_update, SchemaType.UPDATE)
        
        # 檢查驗證後的數據
        assert validated_result.get('data', {}).get("task_name") == "更新的任務名稱"
        assert validated_result.get('data', {}).get("is_auto") is False
        assert "crawler_id" not in validated_result.get('data', {})  # 不可變欄位不應包含在更新中
        
        # 測試無效更新 - 嘗試更新不可變欄位
        invalid_update = {
            "crawler_id": 999  # 不允許更新
        }
        
        # 執行驗證應拋出異常
        with pytest.raises(ValidationError) as excinfo:
            crawler_tasks_repo.validate_data(invalid_update, SchemaType.UPDATE)
        assert "不允許更新 crawler_id 欄位" in str(excinfo.value)
        
    def test_exception_handling_create(self, crawler_tasks_repo, sample_crawler):
        """測試創建時的異常處理"""
        # 準備測試數據
        test_data = {
            "task_name": "測試異常處理",
            "crawler_id": sample_crawler.id,
            "is_auto": True,
            "cron_expression": "0 * * * *",
            "ai_only": False,
            "task_args": TASK_ARGS_DEFAULT,
            "scrape_phase": ScrapePhase.INIT,
            "max_retries": 3,
            "retry_count": 0,
            "scrape_mode": ScrapeMode.FULL_SCRAPE
        }
        
        # 模擬 _create_internal 拋出 DatabaseOperationError
        with patch.object(crawler_tasks_repo, '_create_internal', side_effect=DatabaseOperationError("測試異常")):
            with pytest.raises(DatabaseOperationError):
                crawler_tasks_repo.create(test_data)
        
        # 模擬 validate_data 拋出 ValidationError
        with patch.object(crawler_tasks_repo, 'validate_data', side_effect=ValidationError("測試驗證錯誤")):
            with pytest.raises(ValidationError) as excinfo:
                crawler_tasks_repo.create(test_data)
            assert "測試驗證錯誤" in str(excinfo.value)
            
        # 模擬意外異常
        with patch.object(crawler_tasks_repo, 'validate_data', side_effect=Exception("意外錯誤")):
            with pytest.raises(DatabaseOperationError) as excinfo:
                crawler_tasks_repo.create(test_data)
            assert "未預期錯誤" in str(excinfo.value)
            assert "意外錯誤" in str(excinfo.value)
    
    def test_exception_handling_update(self, crawler_tasks_repo, sample_tasks):
        """測試更新時的異常處理"""
        # 準備測試數據
        task_id = sample_tasks[0].id
        test_data = {
            "task_name": "更新的任務名稱",
            "is_auto": False
        }
        
        # 模擬 _update_internal 拋出 DatabaseOperationError
        with patch.object(crawler_tasks_repo, '_update_internal', side_effect=DatabaseOperationError("測試異常")):
            with pytest.raises(DatabaseOperationError):
                crawler_tasks_repo.update(task_id, test_data)
        
        # 模擬 validate_data 拋出 ValidationError
        with patch.object(crawler_tasks_repo, 'validate_data', side_effect=ValidationError("測試驗證錯誤")):
            with pytest.raises(ValidationError) as excinfo:
                crawler_tasks_repo.update(task_id, test_data)
            assert "測試驗證錯誤" in str(excinfo.value)
            
        # 模擬意外異常
        with patch.object(crawler_tasks_repo, 'validate_data', side_effect=Exception("意外錯誤")):
            with pytest.raises(DatabaseOperationError) as excinfo:
                crawler_tasks_repo.update(task_id, test_data)
            assert "未預期錯誤" in str(excinfo.value)
            assert "意外錯誤" in str(excinfo.value)
            
    def test_update_nonexistent_task(self, crawler_tasks_repo):
        """測試更新不存在的任務"""
        result = crawler_tasks_repo.update(999, {"task_name": "新名稱"})
        assert result is None
        
    def test_update_empty_data(self, crawler_tasks_repo, sample_tasks):
        """測試使用空數據更新任務"""
        task_id = sample_tasks[0].id
        original_name = sample_tasks[0].task_name
        
        # 使用空數據更新
        result = crawler_tasks_repo.update(task_id, {})
        
        # 應該返回原始任務而不進行任何更改
        assert result is not None
        assert result.id == task_id
        assert result.task_name == original_name

class TestComplexValidationScenarios:
    """測試複雜驗證場景"""
    
    def test_create_with_string_scrape_phase(self, crawler_tasks_repo, sample_crawler):
        """測試使用字符串表示的任務階段創建任務"""
        # 使用字符串而不是枚舉
        task = crawler_tasks_repo.create({
            "task_name": "字符串階段測試",
            "crawler_id": sample_crawler.id,
            "is_auto": False,
            "ai_only": False,
            "task_args": TASK_ARGS_DEFAULT,
            "scrape_phase": "init",  # 使用字符串
            "max_retries": 3,
            "retry_count": 0,
            "scrape_mode": ScrapeMode.FULL_SCRAPE
        })
        
        # 驗證是否正確轉換為枚舉
        assert task.scrape_phase == ScrapePhase.INIT
        
        # 測試不同大小寫
        task = crawler_tasks_repo.create({
            "task_name": "字符串階段測試2",
            "crawler_id": sample_crawler.id,
            "is_auto": False,
            "ai_only": False,
            "task_args": TASK_ARGS_DEFAULT,
            "scrape_phase": "INIT",  # 大寫
            "max_retries": 3,
            "retry_count": 0,
            "scrape_mode": ScrapeMode.FULL_SCRAPE
        })
        
        assert task.scrape_phase == ScrapePhase.INIT
        
        # 測試無效階段值
        with pytest.raises(ValidationError) as excinfo:
            crawler_tasks_repo.create({
                "task_name": "無效階段測試",
                "crawler_id": sample_crawler.id,
                "is_auto": False,
                "ai_only": False,
                "task_args": TASK_ARGS_DEFAULT,
                "scrape_phase": "invalid_phase",  # 無效值
                "max_retries": 3,
                "retry_count": 0,
                "scrape_mode": ScrapeMode.FULL_SCRAPE
            })
        assert "CREATE 資料驗證失敗" in str(excinfo.value)

    def test_create_with_empty_result(self, crawler_tasks_repo, session):
        """測試當資料庫操作未能返回實體時的情況"""
        # 使用 patch 讓 _create_internal 返回 None (模擬失敗但未拋出異常)
        with patch.object(crawler_tasks_repo, '_create_internal', return_value=None):
            result = crawler_tasks_repo.create({
                "task_name": "測試無結果",
                "crawler_id": 1,
                "is_auto": False,
                "ai_only": False,
                "task_args": TASK_ARGS_DEFAULT,
                "scrape_phase": ScrapePhase.INIT,
                "max_retries": 3,
                "retry_count": 0,
                "scrape_mode": ScrapeMode.FULL_SCRAPE
            })
            
            # 應該返回 None 而不是異常
            assert result is None