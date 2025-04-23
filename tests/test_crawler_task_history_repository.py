import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from src.database.crawler_task_history_repository import CrawlerTaskHistoryRepository
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawlers_model import Crawlers
from src.models.base_model import Base
from debug.model_info import get_model_info
from src.error.errors import DatabaseOperationError, ValidationError
from typing import Dict, Any, List

# 使用 session scope 以提高效率
@pytest.fixture(scope="session")
def engine():
    return create_engine('sqlite:///:memory:')

@pytest.fixture(scope="function")
def tables(engine):
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

# 使用 session scope 的 session factory
@pytest.fixture(scope="session")
def session_factory(engine):
    return sessionmaker(bind=engine)

# 為每個測試函數創建獨立的 session 和 transaction
@pytest.fixture(scope="function")
def session(session_factory, tables):
    """Creates a new session for each test function, managing transactions."""
    # Create a session instance from the factory
    session = session_factory()
    try:
        # Yield the session to the test
        yield session
        # If the test completes without exception, commit the transaction
        session.commit()
    except Exception:
        # If any exception occurs during the test, rollback
        session.rollback()
        raise # Re-raise the exception to fail the test
    finally:
        # Ensure the session is closed in any case
        session.close()

@pytest.fixture(scope="function")
def crawler_task_history_repo(session):
    return CrawlerTaskHistoryRepository(session, CrawlerTaskHistory)

# Fixture for sample data, using function scope to ensure clean data for each test
@pytest.fixture(scope="function")
def sample_crawler(session):
    crawler = Crawlers(
        crawler_name="測試爬蟲",
        module_name="test_module",
        base_url="https://example.com",
        is_active=True,
        crawler_type="bnext",
        config_file_name="bnext_config.json"
    )
    session.add(crawler)
    session.commit() # Commit within fixture to get ID
    return crawler

@pytest.fixture(scope="function")
def sample_task(session, sample_crawler):
    task = CrawlerTasks(
        task_name="測試任務",
        module_name="test_module",
        crawler_id=sample_crawler.id,
        is_auto=True,
        ai_only=True,
        notes="測試任務"
    )
    session.add(task)
    session.commit() # Commit within fixture to get ID
    return task

@pytest.fixture(scope="function")
def sample_histories(session, sample_task):
    now = datetime.now(timezone.utc) # Ensure timezone aware
    histories_data = [
        { # ID 1 (assuming sequential IDs)
            'task_id': sample_task.id,
            'start_time': now - timedelta(days=3),
            'end_time': now - timedelta(days=3, hours=-1), # Corrected end time
            'success': True,
            'articles_count': 10,
            'message': "成功抓取"
        },
        { # ID 2
            'task_id': sample_task.id,
            'start_time': now - timedelta(days=2),
            'end_time': now - timedelta(days=2, hours=-1), # Corrected end time
            'success': False,
            'articles_count': 0,
            'message': "抓取失敗"
        },
        { # ID 3
            'task_id': sample_task.id,
            'start_time': now - timedelta(days=1),
            'end_time': now - timedelta(days=1, hours=-1), # Corrected end time
            'success': True,
            'articles_count': 15,
            'message': "成功抓取更多文章"
        }
    ]
    # Add and flush to get IDs, then return objects
    histories_objs = [CrawlerTaskHistory(**data) for data in histories_data]
    session.add_all(histories_objs)
    session.flush() # Assign IDs
    session.commit() # Commit to make data available for tests
    # Re-fetch ordered by start_time to ensure consistent test results
    return session.query(CrawlerTaskHistory).order_by(CrawlerTaskHistory.start_time.asc()).all()


class TestCrawlerTaskHistoryRepository:
    """CrawlerTaskHistoryRepository 測試類"""

    def test_find_by_task_id(self, crawler_task_history_repo: CrawlerTaskHistoryRepository, sample_task, sample_histories: List[CrawlerTaskHistory]):
        """測試根據任務ID查詢歷史記錄（包括預覽）"""
        task_id = sample_task.id
        preview_fields = ["id", "success", "articles_count"]

        # Test non-preview
        histories = crawler_task_history_repo.find_by_task_id(task_id, sort_desc=False)
        assert len(histories) == 3
        assert all(isinstance(h, CrawlerTaskHistory) for h in histories)
        assert all(history.task_id == task_id for history in histories if isinstance(history, CrawlerTaskHistory))

        # Test preview
        histories_preview = crawler_task_history_repo.find_by_task_id(
            task_id,
            limit=2,
            sort_desc=True, # Get latest 2
            is_preview=True,
            preview_fields=preview_fields
        )
        assert len(histories_preview) == 2
        assert all(isinstance(h, dict) for h in histories_preview)
        assert all(set(h.keys()) == set(preview_fields) for h in histories_preview if isinstance(h, dict))
        # Check content based on sort_desc=True (latest first)
        if isinstance(histories_preview[0], dict):
            assert histories_preview[0]["articles_count"] == 15 # Should be the last history created
        if isinstance(histories_preview[1], dict):
            assert histories_preview[1]["success"] is False      # Should be the middle history

    def test_find_successful_histories(self, crawler_task_history_repo: CrawlerTaskHistoryRepository, sample_histories: List[CrawlerTaskHistory]):
        """測試查詢成功的歷史記錄（包括預覽）"""
        preview_fields = ["start_time", "message"]

        # Test non-preview
        successful_histories = crawler_task_history_repo.find_successful_histories()
        assert len(successful_histories) == 2
        assert all(isinstance(h, CrawlerTaskHistory) for h in successful_histories)
        assert all(history.success for history in successful_histories if isinstance(history, CrawlerTaskHistory))

        # Test preview
        successful_preview = crawler_task_history_repo.find_successful_histories(
            limit=1,
            is_preview=True,
            preview_fields=preview_fields
            # Default sort is likely created_at desc or id desc
        )
        assert len(successful_preview) == 1
        assert isinstance(successful_preview[0], dict)
        assert set(successful_preview[0].keys()) == set(preview_fields)
        # Assuming default sort gets the latest successful one
        assert successful_preview[0]["message"] == "成功抓取更多文章"

    def test_find_failed_histories(self, crawler_task_history_repo: CrawlerTaskHistoryRepository, sample_histories: List[CrawlerTaskHistory]):
        """測試查詢失敗的歷史記錄（包括預覽）"""
        preview_fields = ["id", "message"]

        # Test non-preview
        failed_histories = crawler_task_history_repo.find_failed_histories()
        assert len(failed_histories) == 1
        assert isinstance(failed_histories[0], CrawlerTaskHistory)
        assert not failed_histories[0].success
        assert failed_histories[0].message == "抓取失敗"

        # Test preview
        failed_preview = crawler_task_history_repo.find_failed_histories(
            is_preview=True,
            preview_fields=preview_fields
        )
        assert len(failed_preview) == 1
        assert isinstance(failed_preview[0], dict)
        assert set(failed_preview[0].keys()) == set(preview_fields)
        assert failed_preview[0]["message"] == "抓取失敗"

    def test_find_histories_with_articles(self, crawler_task_history_repo: CrawlerTaskHistoryRepository, sample_histories: List[CrawlerTaskHistory]):
        """測試查詢有文章的歷史記錄（包括預覽）"""
        preview_fields = ["articles_count", "success"]
        min_articles = 10

        # Test non-preview
        histories_with_articles = crawler_task_history_repo.find_histories_with_articles(min_articles=min_articles)
        assert len(histories_with_articles) == 2
        assert all(isinstance(h, CrawlerTaskHistory) for h in histories_with_articles)
        assert all((h.articles_count or 0) >= min_articles for h in histories_with_articles if isinstance(h, CrawlerTaskHistory))

        # Test preview
        histories_preview = crawler_task_history_repo.find_histories_with_articles(
            min_articles=min_articles,
            limit=1, # Get only one
            is_preview=True,
            preview_fields=preview_fields
            # Default sort applies
        )
        assert len(histories_preview) == 1
        assert isinstance(histories_preview[0], dict)
        assert set(histories_preview[0].keys()) == set(preview_fields)
        assert histories_preview[0]["articles_count"] >= min_articles
        assert histories_preview[0]["success"] is True # Assuming default sort gets the latest one (15 articles)

    def test_find_histories_by_date_range(self, crawler_task_history_repo: CrawlerTaskHistoryRepository, sample_histories: List[CrawlerTaskHistory]):
        """測試根據日期範圍查詢歷史記錄（包括預覽）"""
        preview_fields = ["id", "start_time"]
        earliest_date = min(h.start_time for h in sample_histories if h.start_time)
        latest_date = max(h.start_time for h in sample_histories if h.start_time)
        middle_date = earliest_date + (latest_date - earliest_date) / 2

        # Test non-preview (example: start date only)
        start_only_histories = crawler_task_history_repo.find_histories_by_date_range(start_date=middle_date)
        assert len(start_only_histories) > 0 # Exact count depends on timing
        assert all(isinstance(h, CrawlerTaskHistory) for h in start_only_histories)
        assert all(h.start_time >= middle_date for h in start_only_histories if isinstance(h, CrawlerTaskHistory) and h.start_time)

        # Test preview (example: end date only)
        end_only_preview = crawler_task_history_repo.find_histories_by_date_range(
            end_date=middle_date,
            limit=1,
            is_preview=True,
            preview_fields=preview_fields
            # Default sort applies
        )
        assert len(end_only_preview) <= 1 # Could be 0 or 1 depending on middle_date
        if end_only_preview:
             assert isinstance(end_only_preview[0], dict)
             assert set(end_only_preview[0].keys()) == set(preview_fields)
             assert end_only_preview[0]["start_time"] <= middle_date

    def test_get_total_articles_count(self, crawler_task_history_repo: CrawlerTaskHistoryRepository, sample_task, sample_histories: List[CrawlerTaskHistory]):
        """測試獲取總文章數量"""
        task_total_count = crawler_task_history_repo.count_total_articles(sample_task.id)
        assert task_total_count == 25  # 10 + 0 + 15

        total_count = crawler_task_history_repo.count_total_articles()
        assert total_count == 25

    def test_get_latest_history(self, crawler_task_history_repo: CrawlerTaskHistoryRepository, sample_task, sample_histories: List[CrawlerTaskHistory]):
        """測試獲取最新的歷史記錄（根據開始時間，包括預覽）"""
        task_id = sample_task.id
        preview_fields = ["id", "start_time", "message"]

        # Test non-preview
        latest_history = crawler_task_history_repo.get_latest_history(task_id)
        assert latest_history is not None
        assert isinstance(latest_history, CrawlerTaskHistory)
        expected_latest_start_time = max(h.start_time for h in sample_histories if h.start_time)
        assert latest_history.start_time == expected_latest_start_time

        # Test preview
        latest_preview = crawler_task_history_repo.get_latest_history(
            task_id,
            is_preview=True,
            preview_fields=preview_fields
        )
        assert latest_preview is not None
        assert isinstance(latest_preview, dict)
        assert set(latest_preview.keys()) == set(preview_fields)
        assert latest_preview["start_time"] == expected_latest_start_time
        assert latest_preview["message"] == "成功抓取更多文章"

        # Test non-existent task
        nonexistent_latest = crawler_task_history_repo.get_latest_history(999)
        assert nonexistent_latest is None

    def test_get_latest_by_task_id(self, crawler_task_history_repo: CrawlerTaskHistoryRepository, sample_task, sample_histories: List[CrawlerTaskHistory]):
        """測試獲取指定任務的最新一筆歷史記錄（根據創建時間，包括預覽）"""
        task_id = sample_task.id
        preview_fields = ["id", "created_at"] # Use created_at if available, else id might be the default

        # Test non-preview
        latest_history = crawler_task_history_repo.get_latest_by_task_id(task_id)
        assert latest_history is not None
        assert isinstance(latest_history, CrawlerTaskHistory)
        # Assuming the last one added is the latest by created_at
        assert latest_history.id == sample_histories[-1].id

        # Test preview
        latest_preview = crawler_task_history_repo.get_latest_by_task_id(
            task_id,
            is_preview=True,
            preview_fields=preview_fields
        )
        assert latest_preview is not None
        assert isinstance(latest_preview, dict)
        # Check if created_at exists in the model and preview fields
        expected_keys = set(f for f in preview_fields if hasattr(CrawlerTaskHistory, f))
        assert set(latest_preview.keys()) == expected_keys
        # We might not be able to reliably check created_at value without more control
        assert latest_preview["id"] == sample_histories[-1].id

        # Test non-existent task
        nonexistent_latest = crawler_task_history_repo.get_latest_by_task_id(999)
        assert nonexistent_latest is None

    def test_get_histories_older_than(self, crawler_task_history_repo: CrawlerTaskHistoryRepository, sample_histories: List[CrawlerTaskHistory]):
        """測試獲取超過指定天數的歷史記錄（包括預覽）"""
        preview_fields = ["start_time", "success"]
        days = 2

        # Test non-preview
        histories_older = crawler_task_history_repo.get_histories_older_than(days)
        assert len(histories_older) > 0 # Should find at least the first one
        assert all(isinstance(h, CrawlerTaskHistory) for h in histories_older)
        threshold_date = datetime.now(timezone.utc) - timedelta(days=days)
        assert all((h.start_time < threshold_date) for h in histories_older if isinstance(h, CrawlerTaskHistory) and h.start_time)

        # Test preview
        histories_preview = crawler_task_history_repo.get_histories_older_than(
            days,
            limit=1,
            is_preview=True,
            preview_fields=preview_fields
            # Default sort applies (likely created_at desc)
        )
        assert len(histories_preview) <= 1
        if histories_preview:
            assert isinstance(histories_preview[0], dict)
            assert set(histories_preview[0].keys()) == set(preview_fields)
            assert histories_preview[0]["start_time"] < threshold_date

    def test_update_history_status(self, crawler_task_history_repo: CrawlerTaskHistoryRepository, sample_histories: List[CrawlerTaskHistory], session):
        """測試更新歷史記錄狀態"""
        history = sample_histories[1] # The failed one
        history_id = history.id

        # Test update success=True
        result1 = crawler_task_history_repo.update_history_status(
            history_id=history_id, success=True
        )
        assert result1 is True
        session.commit()
        updated1 = crawler_task_history_repo.get_by_id(history_id)
        assert updated1 and updated1.success is True and updated1.end_time is not None

        # Test update success=True, message, articles_count
        result2 = crawler_task_history_repo.update_history_status(
            history_id=history_id, success=True, message="重試成功", articles_count=5
        )
        assert result2 is True
        session.commit()
        updated2 = crawler_task_history_repo.get_by_id(history_id)
        assert updated2 and updated2.success is True and updated2.message == "重試成功" and updated2.articles_count == 5

        # Test updating non-existent ID
        result3 = crawler_task_history_repo.update_history_status(
            history_id=999, success=True
        )
        assert result3 is False # Should return False if update method returns None for non-existent ID

    # ... other tests like create, update, validation, immutable fields, empty data ...
    # These tests should generally work without changes as they test create/update logic,
    # which was less affected by the refactoring of finder methods.

    def test_create_with_default_values(self, crawler_task_history_repo: CrawlerTaskHistoryRepository, sample_task, session):
        """測試創建時設定預設值的邏輯"""
        min_data = {'task_id': sample_task.id}
        history = crawler_task_history_repo.create(min_data)
        assert history is not None
        assert history.task_id == sample_task.id
        assert history.start_time is not None
        assert history.success is False
        assert history.articles_count == 0
        session.commit() # Commit to save
        db_history = crawler_task_history_repo.get_by_id(history.id)
        assert db_history is not None and db_history.success is False

    def test_create_validation_error(self, crawler_task_history_repo: CrawlerTaskHistoryRepository):
        """測試創建時的驗證錯誤處理"""
        invalid_data = {'start_time': datetime.now(timezone.utc), 'success': True}
        with pytest.raises(ValidationError) as excinfo:
            crawler_task_history_repo.create(invalid_data)
        assert 'task_id' in str(excinfo.value).lower() # Check for field name in error

    def test_update_immutable_fields(self, crawler_task_history_repo: CrawlerTaskHistoryRepository, sample_histories: List[CrawlerTaskHistory], session):
        """測試更新不可變欄位的處理邏輯"""
        history = sample_histories[0]
        history_id = history.id
        original_task_id = history.task_id
        original_start_time = history.start_time

        update_data = {
            'task_id': 999,
            'start_time': datetime.now(timezone.utc),
            'message': "新訊息"
        }
        updated = crawler_task_history_repo.update(history_id, update_data)
        assert updated is not None # Update should proceed ignoring immutable fields
        session.commit()
        refetched = crawler_task_history_repo.get_by_id(history_id)
        assert refetched
        assert refetched.task_id == original_task_id
        assert refetched.start_time == original_start_time
        assert refetched.message == "新訊息"

    def test_update_empty_data(self, crawler_task_history_repo: CrawlerTaskHistoryRepository, sample_histories: List[CrawlerTaskHistory], session):
        """測試更新空資料的處理邏輯"""
        history = sample_histories[0]
        history_id = history.id
        original_message = history.message
        updated = crawler_task_history_repo.update(history_id, {})
        # BaseRepository.update might return None if no changes are made.
        # The current implementation returns the existing entity. Let's keep that expectation.
        assert updated is not None
        assert updated.message == original_message
        session.commit() # Commit (though likely no changes)
        refetched = crawler_task_history_repo.get_by_id(history_id)
        assert refetched and refetched.message == original_message


class TestModelStructure:
    """測試模型結構"""
    def test_crawler_task_history_model_structure(self, session):
        model_info = get_model_info(CrawlerTaskHistory)
        assert model_info["table"] == "crawler_task_history"
        assert "id" in model_info["primary_key"]
        foreign_keys = model_info.get("foreign_keys", [])
        assert any("task_id" in str(fk) for fk in foreign_keys)
        required_fields = [f for f, info in model_info["columns"].items() if not info["nullable"] and info["default"] is None]
        assert "task_id" in required_fields


class TestSpecialCases:
    """測試特殊情況"""
    def test_empty_database(self, crawler_task_history_repo: CrawlerTaskHistoryRepository):
        """測試空數據庫的情況"""
        assert crawler_task_history_repo.find_all() == []
        assert crawler_task_history_repo.find_successful_histories() == []
        assert crawler_task_history_repo.find_failed_histories() == []
        assert crawler_task_history_repo.count_total_articles() == 0

    def test_invalid_operations(self, crawler_task_history_repo: CrawlerTaskHistoryRepository):
        """測試無效操作"""
        # Test updating non-existent history ID
        assert crawler_task_history_repo.update_history_status(history_id=999, success=True) is False


class TestErrorHandling:
    """測試錯誤處理"""
    def test_repository_exception_handling(self, crawler_task_history_repo: CrawlerTaskHistoryRepository, monkeypatch):
        """測試資料庫操作異常處理 (Finder methods)"""
        def mock_execute_query_error(*args, **kwargs):
            # Simulate error during query execution within find_by_filter/find_all
            raise DatabaseOperationError("模擬資料庫查詢錯誤 from execute_query")

        monkeypatch.setattr(crawler_task_history_repo, "execute_query", mock_execute_query_error)

        # Test a finder method that now uses find_by_filter -> execute_query
        with pytest.raises(DatabaseOperationError) as excinfo:
            crawler_task_history_repo.find_by_task_id(1)
        # The error message comes from execute_query wrapper now
        assert "模擬資料庫查詢錯誤 from execute_query" in str(excinfo.value)

        # Test another finder
        with pytest.raises(DatabaseOperationError) as excinfo:
            crawler_task_history_repo.get_latest_by_task_id(1)
        assert "模擬資料庫查詢錯誤 from execute_query" in str(excinfo.value)

    def test_create_exception_handling(self, crawler_task_history_repo: CrawlerTaskHistoryRepository, sample_task, monkeypatch):
        """測試創建時的異常處理"""
        def mock_create_internal_error(*args, **kwargs):
            raise DatabaseOperationError("模擬創建內部錯誤") # Raise specific error type

        monkeypatch.setattr(crawler_task_history_repo, "_create_internal", mock_create_internal_error)

        with pytest.raises(DatabaseOperationError) as excinfo:
            crawler_task_history_repo.create({'task_id': sample_task.id})
        # Error comes from _create_internal via create
        assert "模擬創建內部錯誤" in str(excinfo.value)

    def test_update_exception_handling(self, crawler_task_history_repo: CrawlerTaskHistoryRepository, sample_histories: List[CrawlerTaskHistory], monkeypatch):
        """測試更新時的異常處理"""
        history = sample_histories[0]
        history_id = history.id

        def mock_update_internal_error(*args, **kwargs):
            raise DatabaseOperationError("模擬更新內部錯誤") # Raise specific error type

        monkeypatch.setattr(crawler_task_history_repo, "_update_internal", mock_update_internal_error)

        with pytest.raises(DatabaseOperationError) as excinfo:
            crawler_task_history_repo.update(history_id, {'message': '測試更新'})
        # Error comes from _update_internal via update
        assert "模擬更新內部錯誤" in str(excinfo.value) 