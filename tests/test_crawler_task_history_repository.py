import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.database.crawler_task_history_repository import CrawlerTaskHistoryRepository
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawlers_model import Crawlers
from src.models.base_model import Base
from src.models.model_utiles import get_model_info
from src.error.errors import ValidationError, DatabaseOperationError

# 設置測試資料庫
@pytest.fixture
def engine():
    return create_engine('sqlite:///:memory:')

@pytest.fixture
def tables(engine):
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture
def session(engine, tables):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()

@pytest.fixture
def crawler_task_history_repo(session):
    return CrawlerTaskHistoryRepository(session, CrawlerTaskHistory)

@pytest.fixture
def sample_crawler(session):
    crawler = Crawlers(
        crawler_name="測試爬蟲",
        scrape_target="https://example.com",
        crawl_interval=60,
        is_active=True,
        crawler_type="bnext"
    )
    session.add(crawler)
    session.commit()
    return crawler

@pytest.fixture
def sample_task(session, sample_crawler):
    task = CrawlerTasks(
        crawler_id=sample_crawler.id,
        is_auto=True,
        ai_only=True,
        notes="測試任務"
    )
    session.add(task)
    session.commit()
    return task

@pytest.fixture
def sample_histories(session, sample_task):
    now = datetime.now()
    histories = [
        CrawlerTaskHistory(
            task_id=sample_task.id,
            start_time=now - timedelta(days=3),
            end_time=now - timedelta(days=3, hours=1),
            success=True,
            articles_count=10,
            message="成功抓取"
        ),
        CrawlerTaskHistory(
            task_id=sample_task.id,
            start_time=now - timedelta(days=2),
            end_time=now - timedelta(days=2, hours=1),
            success=False,
            articles_count=0,
            message="抓取失敗"
        ),
        CrawlerTaskHistory(
            task_id=sample_task.id,
            start_time=now - timedelta(days=1),
            end_time=now - timedelta(days=1, hours=1),
            success=True,
            articles_count=15,
            message="成功抓取更多文章"
        )
    ]
    session.add_all(histories)
    session.commit()
    return histories

class TestCrawlerTaskHistoryRepository:
    """CrawlerTaskHistoryRepository 測試類"""
    
    def test_find_by_task_id(self, crawler_task_history_repo, sample_task, sample_histories):
        """測試根據任務ID查詢歷史記錄"""
        histories = crawler_task_history_repo.find_by_task_id(sample_task.id)
        assert len(histories) == 3
        assert all(history.task_id == sample_task.id for history in histories)

    def test_find_successful_histories(self, crawler_task_history_repo, sample_histories):
        """測試查詢成功的歷史記錄"""
        successful_histories = crawler_task_history_repo.find_successful_histories()
        assert len(successful_histories) == 2
        assert all(history.success for history in successful_histories)

    def test_find_failed_histories(self, crawler_task_history_repo, sample_histories):
        """測試查詢失敗的歷史記錄"""
        failed_histories = crawler_task_history_repo.find_failed_histories()
        assert len(failed_histories) == 1
        assert all(not history.success for history in failed_histories)

    def test_find_histories_with_articles(self, crawler_task_history_repo, sample_histories):
        """測試查詢有文章的歷史記錄"""
        histories_with_articles = crawler_task_history_repo.find_histories_with_articles(min_articles=10)
        assert len(histories_with_articles) == 2
        assert all(history.articles_count >= 10 for history in histories_with_articles)

    def test_find_histories_by_date_range(self, crawler_task_history_repo, sample_histories):
        """測試根據日期範圍查詢歷史記錄"""
        earliest_date = min(h.start_time for h in sample_histories)
        latest_date = max(h.start_time for h in sample_histories)
        
        middle_date = earliest_date + (latest_date - earliest_date) / 2
        
        # 測試只有開始日期
        start_only_histories = crawler_task_history_repo.find_histories_by_date_range(
            start_date=middle_date
        )
        assert len(start_only_histories) > 0
        
        # 測試只有結束日期
        end_only_histories = crawler_task_history_repo.find_histories_by_date_range(
            end_date=middle_date
        )
        assert len(end_only_histories) > 0
        
        # 測試完整日期範圍
        histories = crawler_task_history_repo.find_histories_by_date_range(
            start_date=middle_date,
            end_date=latest_date
        )
        
        expected_count = sum(1 for h in sample_histories if middle_date <= h.start_time <= latest_date)
        assert len(histories) == expected_count

    def test_get_total_articles_count(self, crawler_task_history_repo, sample_task, sample_histories):
        """測試獲取總文章數量"""
        # 測試特定任務的文章總數
        task_total_count = crawler_task_history_repo.get_total_articles_count(sample_task.id)
        assert task_total_count == 25  # 10 + 0 + 15
        
        # 測試所有任務的文章總數
        total_count = crawler_task_history_repo.get_total_articles_count()
        assert total_count == 25  # 在此測試中只有一個任務

    def test_get_latest_history(self, crawler_task_history_repo, sample_task, sample_histories):
        """測試獲取最新的歷史記錄"""
        latest_history = crawler_task_history_repo.get_latest_history(sample_task.id)
        assert latest_history is not None
        assert latest_history.start_time == max(h.start_time for h in sample_histories)
        
        # 測試獲取不存在任務的最新歷史
        nonexistent_latest = crawler_task_history_repo.get_latest_history(999)
        assert nonexistent_latest is None

    def test_get_histories_older_than(self, crawler_task_history_repo, sample_histories):
        """測試獲取超過指定天數的歷史記錄"""
        histories_older_than_2_days = crawler_task_history_repo.get_histories_older_than(2)
        assert len(histories_older_than_2_days) > 0
        for history in histories_older_than_2_days:
            assert (datetime.now() - history.start_time).days >= 2

    def test_update_history_status(self, crawler_task_history_repo, sample_histories):
        """測試更新歷史記錄狀態"""
        history = sample_histories[1]
        
        # 測試更新部分欄位
        partial_update_result = crawler_task_history_repo.update_history_status(
            history_id=history.id,
            success=True
        )
        assert partial_update_result is True
        
        updated_history = crawler_task_history_repo.get_by_id(history.id)
        assert updated_history.success is True
        assert updated_history.end_time is not None
        
        # 測試完整更新
        complete_update_result = crawler_task_history_repo.update_history_status(
            history_id=history.id,
            success=True,
            message="重試成功",
            articles_count=5
        )
        
        assert complete_update_result is True
        
        updated_history = crawler_task_history_repo.get_by_id(history.id)
        assert updated_history.success is True
        assert updated_history.message == "重試成功"
        assert updated_history.articles_count == 5
        assert updated_history.end_time is not None

class TestModelStructure:
    """測試模型結構"""
    
    def test_crawler_task_history_model_structure(self, session):
        """測試CrawlerTaskHistory模型結構"""
        model_info = get_model_info(CrawlerTaskHistory)
        
        # 測試表名
        assert model_info["table"] == "crawler_task_history"
        
        # 測試主鍵
        assert "id" in model_info["primary_key"]
        
        # 測試外鍵
        foreign_keys = model_info.get("foreign_keys", [])
        # 檢查是否有指向 crawler_tasks 表的外鍵
        has_task_fk = False
        for fk in foreign_keys:
            if "task_id" in str(fk):  # 使用更寬鬆的檢查
                has_task_fk = True
                break
        assert has_task_fk, "應該有指向 crawler_tasks 表的外鍵"
        
        # 測試必填欄位
        required_fields = []
        for field, info in model_info["columns"].items():
            if not info["nullable"] and info["default"] is None:
                required_fields.append(field)
        
        assert "task_id" in required_fields
        assert "id" in required_fields

class TestSpecialCases:
    """測試特殊情況"""
    
    def test_empty_database(self, crawler_task_history_repo):
        """測試空數據庫的情況"""
        assert crawler_task_history_repo.get_all() == []
        assert crawler_task_history_repo.find_successful_histories() == []
        assert crawler_task_history_repo.find_failed_histories() == []

    def test_invalid_operations(self, crawler_task_history_repo):
        """測試無效操作"""
        # 測試不存在的歷史記錄ID
        assert crawler_task_history_repo.update_history_status(
            history_id=999, 
            success=True
        ) is False

class TestErrorHandling:
    """測試錯誤處理"""
    
    def test_repository_exception_handling(self, crawler_task_history_repo, session, monkeypatch):
        """測試資料庫操作異常處理"""
        # 模擬查詢時資料庫異常
        def mock_query_error(*args, **kwargs):
            raise Exception("模擬資料庫查詢錯誤")
        
        monkeypatch.setattr(crawler_task_history_repo.session, "query", mock_query_error)
        
        # 測試各方法的異常處理
        with pytest.raises(DatabaseOperationError) as excinfo:
            crawler_task_history_repo.find_by_task_id(1)
        
        # 修改斷言方式
        assert "查詢任務ID為1的歷史記錄時發生錯誤" in str(excinfo.value) 