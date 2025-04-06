import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.crawler_task_history_model import CrawlerTaskHistory, Base
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawlers_model import Crawlers
from src.services.crawler_task_history_service import CrawlerTaskHistoryService
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
def history_service(session):
    """創建爬蟲任務歷史記錄服務實例"""
    db_manager = DatabaseManager('sqlite:///:memory:')
    db_manager.Session = sessionmaker(bind=session.get_bind())
    return CrawlerTaskHistoryService(db_manager)

@pytest.fixture(scope="function")
def sample_histories(session):
    """創建測試用的爬蟲任務歷史記錄資料"""
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
    
    # 創建測試用的爬蟲任務
    task = CrawlerTasks(
        task_name="測試任務",
        crawler_id=crawler.id,
        schedule="0 0 * * *",
        is_active=True,
        config={"max_items": 100}
    )
    session.add(task)
    session.flush()
    
    # 創建測試用的歷史記錄
    histories = [
        CrawlerTaskHistory(
            task_id=task.id,
            start_time=datetime.now(timezone.utc) - timedelta(days=1),
            end_time=datetime.now(timezone.utc) - timedelta(days=1, hours=1),
            success=True,
            message="執行成功",
            articles_count=10
        ),
        CrawlerTaskHistory(
            task_id=task.id,
            start_time=datetime.now(timezone.utc) - timedelta(days=2),
            end_time=datetime.now(timezone.utc) - timedelta(days=2, hours=1),
            success=False,
            message="執行失敗",
            articles_count=0
        ),
        CrawlerTaskHistory(
            task_id=task.id,
            start_time=datetime.now(timezone.utc) - timedelta(days=10),
            end_time=datetime.now(timezone.utc) - timedelta(days=10, hours=1),
            success=True,
            message="執行成功",
            articles_count=5
        )
    ]
    
    session.add_all(histories)
    session.commit()
    return histories

class TestCrawlerTaskHistoryService:
    """測試爬蟲任務歷史記錄服務的核心功能"""

    def test_get_all_histories(self, history_service, sample_histories):
        """測試獲取所有歷史記錄"""
        result = history_service.get_all_histories()
        assert result["success"] is True
        assert len(result["histories"]) == 3
        assert result["message"] == "獲取所有歷史記錄成功"

    def test_get_successful_histories(self, history_service, sample_histories):
        """測試獲取成功的歷史記錄"""
        result = history_service.get_successful_histories()
        assert result["success"] is True
        assert len(result["histories"]) == 2
        assert all(h.success for h in result["histories"])

    def test_get_failed_histories(self, history_service, sample_histories):
        """測試獲取失敗的歷史記錄"""
        result = history_service.get_failed_histories()
        assert result["success"] is True
        assert len(result["histories"]) == 1
        assert not any(h.success for h in result["histories"])

    def test_get_histories_with_articles(self, history_service, sample_histories):
        """測試獲取有文章的歷史記錄"""
        result = history_service.get_histories_with_articles(min_articles=5)
        assert result["success"] is True
        assert len(result["histories"]) == 2
        assert all(h.articles_count >= 5 for h in result["histories"])

    def test_get_histories_by_date_range(self, history_service, sample_histories):
        """測試根據日期範圍獲取歷史記錄"""
        start_date = datetime.now(timezone.utc) - timedelta(days=3)
        end_date = datetime.now(timezone.utc)
        result = history_service.get_histories_by_date_range(start_date, end_date)
        assert result["success"] is True
        assert len(result["histories"]) == 2

    def test_get_total_articles_count(self, history_service, sample_histories):
        """測試獲取總文章數量"""
        result = history_service.get_total_articles_count()
        assert result["success"] is True
        assert result["count"] == 15  # 10 + 0 + 5

    def test_get_latest_history(self, history_service, sample_histories):
        """測試獲取最新歷史記錄"""
        task_id = sample_histories[0].task_id
        result = history_service.get_latest_history(task_id)
        assert result["success"] is True
        assert result["history"].id == sample_histories[0].id

    def test_get_histories_older_than(self, history_service, sample_histories):
        """測試獲取超過指定天數的歷史記錄"""
        result = history_service.get_histories_older_than(5)
        assert result["success"] is True
        assert len(result["histories"]) == 1

    def test_update_history_status(self, history_service, sample_histories):
        """測試更新歷史記錄狀態"""
        history_id = sample_histories[0].id
        result = history_service.update_history_status(
            history_id=history_id,
            success=True,
            message="更新測試",
            articles_count=20
        )
        assert result["success"] is True
        assert result["history"].articles_count == 20
        assert result["history"].message == "更新測試"

    def test_delete_history(self, history_service, sample_histories):
        """測試刪除歷史記錄"""
        history_id = sample_histories[0].id
        result = history_service.delete_history(history_id)
        assert result["success"] is True
        assert result["result"] is True
        
        # 確認記錄已被刪除
        result = history_service.get_all_histories()
        assert len(result["histories"]) == 2

    def test_delete_old_histories(self, history_service, sample_histories):
        """測試刪除舊的歷史記錄"""
        result = history_service.delete_old_histories(5)
        assert result["success"] is True
        assert result["resultMsg"]["deleted_count"] == 1
        assert len(result["resultMsg"]["failed_ids"]) == 0

    def test_error_handling(self, history_service):
        """測試錯誤處理"""
        # 測試更新不存在的歷史記錄
        result = history_service.update_history_status(
            history_id=999999,
            success=True
        )
        assert result["success"] is False
        assert "不存在" in result["message"]
        
        # 測試刪除不存在的歷史記錄
        result = history_service.delete_history(999999)
        assert result["success"] is False
        assert "不存在" in result["message"]
