import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.crawler_tasks_model import CrawlerTasks, Base
from src.models.crawlers_model import Crawlers
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.services.crawler_task_service import CrawlerTaskService
from src.database.database_manager import DatabaseManager

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
    session.query(CrawlerTaskHistory).delete()
    session.query(CrawlerTasks).delete()
    session.query(Crawlers).delete()
    session.commit()
    
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
    
    tasks = [
        CrawlerTasks(
            task_name="每日新聞爬取",
            crawler_id=crawler.id,
            schedule="0 0 * * *",
            is_active=True,
            config={"max_items": 100},
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2023, 1, 1, tzinfo=timezone.utc)
        ),
        CrawlerTasks(
            task_name="週間財經新聞",
            crawler_id=crawler.id,
            schedule="0 0 * * 1-5",
            is_active=False,
            config={"max_items": 50},
            created_at=datetime(2023, 1, 2, tzinfo=timezone.utc),
            updated_at=datetime(2023, 1, 2, tzinfo=timezone.utc)
        )
    ]
    
    session.add_all(tasks)
    session.commit()
    return tasks

class TestCrawlerTaskService:
    """測試爬蟲任務服務的核心功能"""

    def test_create_task(self, crawler_task_service):
        """測試創建爬蟲任務"""
        task_data = {
            "task_name": "測試任務",
            "crawler_id": 1,
            "schedule": "0 0 * * *",
            "is_active": True,
            "config": {"max_items": 100},
            "ai_only": False,
            "task_args": {}
        }
        
        result = crawler_task_service.create_task(task_data)
        assert result["success"] is True
        assert "task_id" in result
        assert result["message"] == "任務創建成功"

    def test_update_task(self, crawler_task_service, sample_tasks):
        """測試更新爬蟲任務"""
        task_id = sample_tasks[0].id
        update_data = {
            "task_name": "更新後的任務名稱",
            "is_active": False,
            "ai_only": False,
            "task_args": {}
        }
        
        result = crawler_task_service.update_task(task_id, update_data)
        assert result["success"] is True
        assert result["message"] == "任務更新成功"

    def test_delete_task(self, crawler_task_service, sample_tasks):
        """測試刪除爬蟲任務"""
        task_id = sample_tasks[0].id
        result = crawler_task_service.delete_task(task_id)
        assert result["success"] is True
        assert result["message"] == "任務刪除成功"
        
        # 確認任務已被刪除
        result = crawler_task_service.get_task_by_id(task_id)
        assert result["success"] is False
        assert result["message"] == "任務不存在"

    def test_get_task_by_id(self, crawler_task_service, sample_tasks):
        """測試根據ID獲取任務"""
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
        assert len(result["tasks"]) == 2

    def test_get_task_history(self, crawler_task_service, sample_tasks, session):
        """測試獲取任務歷史記錄"""
        task_id = sample_tasks[0].id
        
        # 創建一些測試用的歷史記錄
        histories = [
            CrawlerTaskHistory(
                task_id=task_id,
                start_time=datetime(2023, 1, 1, tzinfo=timezone.utc),
                end_time=datetime(2023, 1, 1, 1, tzinfo=timezone.utc),
                success=True,
                message="執行成功",
                articles_count=10
            ),
            CrawlerTaskHistory(
                task_id=task_id,
                start_time=datetime(2023, 1, 2, tzinfo=timezone.utc),
                end_time=datetime(2023, 1, 2, 1, tzinfo=timezone.utc),
                success=False,
                message="執行失敗",
                articles_count=0
            )
        ]
        session.add_all(histories)
        session.commit()
        
        result = crawler_task_service.get_task_history(task_id)
        assert result["success"] is True
        assert len(result["history"]) == 2

    def test_get_task_status(self, crawler_task_service, sample_tasks, session):
        """測試獲取任務狀態"""
        task_id = sample_tasks[0].id
        
        # 創建一個進行中的任務歷史記錄
        history = CrawlerTaskHistory(
            task_id=task_id,
            start_time=datetime.now(timezone.utc),
            success=None,
            message="正在執行中"
        )
        session.add(history)
        session.commit()
        
        result = crawler_task_service.get_task_status(task_id)
        assert result["status"] == "running"
        assert 0 <= result["progress"] <= 95
        assert result["message"] == "正在執行中"

    def test_error_handling(self, crawler_task_service):
        """測試錯誤處理"""
        # 測試獲取不存在的任務
        result = crawler_task_service.get_task_by_id(999999)
        assert result["success"] is False
        assert result["message"] == "任務不存在"
        
        # 測試更新不存在的任務
        result = crawler_task_service.update_task(999999, {"name": "新名稱"})
        assert result["success"] is False
        assert result["message"] == "任務不存在"

    def test_test_crawler_task(self, crawler_task_service):
        """測試爬蟲任務的測試功能"""
        test_data = {
            "task_name": "測試爬蟲",
            "crawler_id": 1,
            "task_args": {"test_mode": True}
        }
        
        result = crawler_task_service.test_crawler_task(test_data)
        assert result["success"] is True
        assert "test_results" in result
        assert "links_found" in result["test_results"]
        assert "sample_links" in result["test_results"]

    def test_cancel_task(self, crawler_task_service, sample_tasks, session):
        """測試取消任務功能"""
        task_id = sample_tasks[0].id
        
        # 創建一個進行中的任務歷史記錄
        history = CrawlerTaskHistory(
            task_id=task_id,
            start_time=datetime.now(timezone.utc),
            success=None,
            message="正在執行中"
        )
        session.add(history)
        session.commit()
        
        result = crawler_task_service.cancel_task(task_id)
        assert result["success"] is True
        assert result["message"] == "任務已取消"
        
        # 確認任務狀態已更新
        status_result = crawler_task_service.get_task_status(task_id)
        assert status_result["status"] == "cancelled"

    def test_get_task_history_with_filters(self, crawler_task_service, sample_tasks, session):
        """測試帶過濾條件的任務歷史記錄獲取"""
        task_id = sample_tasks[0].id
        
        # 創建多個測試用的歷史記錄
        histories = [
            CrawlerTaskHistory(
                task_id=task_id,
                start_time=datetime(2023, 1, 1, tzinfo=timezone.utc),
                end_time=datetime(2023, 1, 1, 1, tzinfo=timezone.utc),
                success=True,
                message="執行成功",
                articles_count=10
            ),
            CrawlerTaskHistory(
                task_id=task_id,
                start_time=datetime(2023, 1, 2, tzinfo=timezone.utc),
                end_time=datetime(2023, 1, 2, 1, tzinfo=timezone.utc),
                success=False,
                message="執行失敗",
                articles_count=0
            ),
            CrawlerTaskHistory(
                task_id=task_id,
                start_time=datetime(2023, 1, 3, tzinfo=timezone.utc),
                end_time=datetime(2023, 1, 3, 1, tzinfo=timezone.utc),
                success=True,
                message="執行成功",
                articles_count=15
            )
        ]
        session.add_all(histories)
        session.commit()
        
        # 測試按日期範圍過濾
        filters = {
            "start_date": datetime(2023, 1, 2, tzinfo=timezone.utc),
            "end_date": datetime(2023, 1, 3, tzinfo=timezone.utc)
        }
        result = crawler_task_service.get_task_history(task_id, filters)
        assert result["success"] is True
        assert len(result["history"]) == 2
        
        # 測試按成功狀態過濾
        filters = {"success": True}
        result = crawler_task_service.get_task_history(task_id, filters)
        assert result["success"] is True
        assert len(result["history"]) == 2
        assert all(h.success for h in result["history"])
