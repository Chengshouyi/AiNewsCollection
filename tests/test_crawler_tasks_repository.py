import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawlers_model import Crawlers
from src.models.base_model import Base
from debug.model_info import get_model_info
from src.error.errors import ValidationError

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
            task_name="AI任務1",
            crawler_id=sample_crawler.id,
            is_auto=True,
            ai_only=True,
            notes="AI任務1",
            cron_expression="* * * * *"
        ),
        CrawlerTasks(
            task_name="一般任務",
            crawler_id=sample_crawler.id,
            is_auto=True,
            ai_only=False,
            notes="一般任務",
            cron_expression="* * * * *"
        ),
        CrawlerTasks(
            task_name="手動AI任務",
            crawler_id=sample_crawler.id,
            is_auto=False,
            ai_only=True,
            notes="手動AI任務",
            cron_expression="* * * * *"
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
        """測試根據爬蟲ID查詢任務"""
        tasks = crawler_tasks_repo.find_by_crawler_id(sample_crawler.id)
        assert len(tasks) == 3
        assert all(task.crawler_id == sample_crawler.id for task in tasks)

    def test_find_auto_tasks(self, crawler_tasks_repo, sample_tasks):
        """測試查詢自動執行的任務"""
        auto_tasks = crawler_tasks_repo.find_auto_tasks()
        assert len(auto_tasks) == 2
        assert all(task.is_auto for task in auto_tasks)

    def test_find_ai_only_tasks(self, crawler_tasks_repo, sample_tasks):
        """測試查詢AI相關的任務"""
        ai_tasks = crawler_tasks_repo.find_ai_only_tasks()
        assert len(ai_tasks) == 2
        assert all(task.ai_only for task in ai_tasks)

    def test_find_tasks_by_crawler_and_auto(self, crawler_tasks_repo, sample_tasks, sample_crawler):
        """測試根據爬蟲ID和自動執行狀態查詢任務"""
        auto_tasks = crawler_tasks_repo.find_tasks_by_crawler_and_auto(
            crawler_id=sample_crawler.id,
            is_auto=True
        )
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

    def test_toggle_ai_only_status(self, crawler_tasks_repo, sample_tasks, session):
        """測試切換AI收集狀態"""
        task = sample_tasks[0]
        original_status = task.ai_only
        task_id = task.id
        
        # 切換狀態
        result = crawler_tasks_repo.toggle_ai_only_status(task_id)
        assert result is True
        
        # 重新獲取任務並驗證狀態
        session.expire_all()  # 確保重新從數據庫加載
        updated_task = crawler_tasks_repo.get_by_id(task_id)
        assert updated_task.ai_only != original_status
        assert updated_task.updated_at is not None

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
        assert len(tasks) == 3
        assert all(task.notes is not None for task in tasks)

    def test_find_tasks_by_multiple_crawlers(self, crawler_tasks_repo, sample_tasks, sample_crawler):
        """測試根據多個爬蟲ID查詢任務"""
        tasks = crawler_tasks_repo.find_tasks_by_multiple_crawlers([sample_crawler.id])
        assert len(tasks) == 3
        assert all(task.crawler_id == sample_crawler.id for task in tasks)

    def test_get_tasks_count_by_crawler(self, crawler_tasks_repo, sample_tasks, sample_crawler):
        """測試獲取特定爬蟲的任務數量"""
        count = crawler_tasks_repo.get_tasks_count_by_crawler(sample_crawler.id)
        assert count == 3

    def test_find_tasks_by_cron_expression(self, crawler_tasks_repo, session, sample_crawler):
        """測試根據 cron 表達式查詢任務"""
        # 建立測試資料
        tasks = [
            CrawlerTasks(
                task_name="每小時執行任務",
                crawler_id=sample_crawler.id,
                is_auto=True,
                cron_expression="0 * * * *"  # 每小時執行
            ),
            CrawlerTasks(
                task_name="每天執行任務",
                crawler_id=sample_crawler.id,
                is_auto=True,
                cron_expression="0 0 * * *"  # 每天執行
            ),
            CrawlerTasks(
                task_name="每週執行任務",
                crawler_id=sample_crawler.id,
                is_auto=True,
                cron_expression="0 0 * * 1"  # 每週一執行
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
            last_run_at=now - timedelta(hours=2)
        )
        
        # 2. 上次執行不到1小時（不應該被找到）
        task2 = CrawlerTasks(
            task_name="不到1小時任務",
            crawler_id=sample_crawler.id,
            is_auto=True,
            cron_expression="0 * * * *",
            last_run_at=now - timedelta(minutes=30)
        )
        
        # 3. 從未執行過（應該被找到）
        task3 = CrawlerTasks(
            task_name="從未執行任務",
            crawler_id=sample_crawler.id,
            is_auto=True,
            cron_expression="0 * * * *",
            last_run_at=None
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
                last_run_at=base_time - timedelta(days=2)  # 超過1天，不應該被查到
            ),
            CrawlerTasks(
                task_name="失敗任務2",
                crawler_id=sample_crawler.id,
                last_run_success=False,
                last_run_at=base_time - timedelta(hours=12)  # 應該被查到
            ),
            CrawlerTasks(
                task_name="成功任務",
                crawler_id=sample_crawler.id,
                last_run_success=True,
                last_run_at=base_time - timedelta(hours=1)  # 成功的任務，不應該被查到
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
            crawler_tasks_repo.create(CrawlerTasks(
                is_auto=True
            ))
        assert "crawler_id: 不能為空" in str(excinfo.value)
        
        # 測試自動執行時缺少 cron_expression
        with pytest.raises(ValidationError) as excinfo:
            crawler_tasks_repo.create({
                "crawler_id": sample_crawler.id,
                "is_auto": True,
                "cron_expression": None,
                "ai_only": False,
                "task_args": {}
            })
        assert "當設定為自動執行時，cron_expression 不能為空" in str(excinfo.value)
        
        # 測試成功創建
        task = crawler_tasks_repo.create({
            "task_name": "測試任務",
            "crawler_id": sample_crawler.id,
            "task_args": {},
            "is_auto": True,
            "cron_expression": "0 * * * *",
            "ai_only": False
        })
        assert task.crawler_id == sample_crawler.id
        assert task.is_auto is True
        assert task.cron_expression == "0 * * * *"
        assert task.ai_only is False

    def test_update_task_with_validation(self, crawler_tasks_repo, session, sample_crawler):
        """測試更新任務時的驗證規則"""
        # 創建新任務
        task = CrawlerTasks(
            task_name="測試任務",
            crawler_id=sample_crawler.id,
            is_auto=False
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
        
        with pytest.raises(ValidationError) as excinfo:
            crawler_tasks_repo.update(task_id, {
                "is_auto": True,
                "cron_expression": None
            })
        assert "當設定為自動執行時，cron_expression 不能為空" in str(excinfo.value)
        
        # 測試成功更新
        session.expire_all()  # 確保重新從數據庫加載
        
        updated_task = crawler_tasks_repo.update(task_id, {
            "is_auto": True,
            "cron_expression": "0 * * * *"
        })
        assert updated_task.is_auto is True
        assert updated_task.cron_expression == "0 * * * *"

    def test_default_values(self, crawler_tasks_repo, sample_crawler):
        """測試新建任務時的預設值"""
        task = crawler_tasks_repo.create({
            "task_name": "測試任務",
            "crawler_id": sample_crawler.id,
            "is_auto": False,  # 手動執行不需要 cron_expression
            "ai_only": False,
            "task_args": {}
        })
        assert task.is_auto is False
        assert task.ai_only is False
        assert task.task_args == {}

class TestCrawlerTasksConstraints:
    """測試CrawlerTasks的模型約束"""
    
    def test_boolean_defaults(self, session, sample_crawler):
        """測試布林欄位的默認值"""
        task = CrawlerTasks(
            task_name="測試任務",
            crawler_id=sample_crawler.id
        )
        session.add(task)
        session.flush()
        
        assert task.is_auto is True  # 默認為True
        assert task.ai_only is False  # 默認為False

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