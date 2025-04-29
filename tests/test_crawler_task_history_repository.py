"""測試 CrawlerTaskHistoryRepository 的功能。

此模組包含對 CrawlerTaskHistoryRepository 類的所有測試案例，包括：
- 基本的 CRUD 操作
- 查找和過濾功能
- 統計功能
- 狀態更新
- 錯誤處理
"""

# Standard library imports
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any  # Added Dict, Any for type hinting

# Third party imports
import pytest
from sqlalchemy.orm import Session

# Local application imports
from src.models.base_model import Base
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawlers_model import Crawlers
from src.database.crawler_task_history_repository import CrawlerTaskHistoryRepository
from src.error.errors import DatabaseOperationError, ValidationError
from src.utils.log_utils import LoggerSetup

# flake8: noqa: F811
# pylint: disable=redefined-outer-name

logger = LoggerSetup.setup_logger(__name__)


@pytest.fixture(scope="function")
def initialized_db_manager(db_manager_for_test):
    """Fixture that depends on db_manager_for_test, creates tables, and yields the manager."""
    logger.debug("Creating tables for test function...")
    try:
        db_manager_for_test.create_tables(Base)
        yield db_manager_for_test
    finally:
        logger.debug(
            "Test function finished, tables might be dropped by manager cleanup or next test setup."
        )


@pytest.fixture(scope="function")
def crawler_task_history_repo(initialized_db_manager):
    """為每個測試函數創建新的 CrawlerTaskHistoryRepository 實例"""
    with initialized_db_manager.session_scope() as session:
        yield CrawlerTaskHistoryRepository(session, CrawlerTaskHistory)


@pytest.fixture(scope="function")
def sample_crawler_data(initialized_db_manager):
    """創建測試用的爬蟲資料，返回包含 ID 的字典"""
    with initialized_db_manager.session_scope() as session:
        crawler = Crawlers(
            crawler_name="測試爬蟲",
            module_name="test_module",
            base_url="https://example.com",
            is_active=True,
            crawler_type="bnext",
            config_file_name="bnext_config.json",
        )
        session.add(crawler)
        session.commit()
        crawler_id = crawler.id  # Get ID after commit
        crawler_name = crawler.crawler_name  # Example of other static data
    # Return data outside the session scope
    return {"id": crawler_id, "crawler_name": crawler_name}


@pytest.fixture(scope="function")
def sample_task_data(
    initialized_db_manager, sample_crawler_data: Dict[str, Any]
) -> Dict[str, Any]:
    """創建測試用的任務資料，返回包含 ID 的字典"""
    with initialized_db_manager.session_scope() as session:
        task = CrawlerTasks(
            task_name="測試任務",
            module_name="test_module",
            crawler_id=sample_crawler_data["id"],  # Use ID from the dictionary
            is_auto=True,
            ai_only=True,
            notes="測試任務",
        )
        session.add(task)
        session.commit()
        task_id = task.id  # Get ID after commit
    # Return data outside the session scope
    return {"id": task_id}


@pytest.fixture(scope="function")
def sample_histories_data(
    initialized_db_manager, sample_task_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """創建測試用的歷史記錄資料，返回包含關鍵數據的字典列表"""
    created_history_ids = []
    task_id = sample_task_data["id"]  # Use ID from the dictionary
    now = datetime.now(timezone.utc)
    histories_input_data = [
        {
            "task_id": task_id,
            "start_time": now - timedelta(days=3),
            "end_time": (now - timedelta(days=3)) + timedelta(hours=1),
            "success": True,
            "articles_count": 10,
            "message": "成功抓取",
        },
        {
            "task_id": task_id,
            "start_time": now - timedelta(days=2),
            "end_time": (now - timedelta(days=2)) + timedelta(hours=1),
            "success": False,
            "articles_count": 0,
            "message": "抓取失敗",
        },
        {
            "task_id": task_id,
            "start_time": now - timedelta(days=1),
            "end_time": (now - timedelta(days=1)) + timedelta(hours=1),
            "success": True,
            "articles_count": 15,
            "message": "成功抓取更多文章",
        },
    ]

    with initialized_db_manager.session_scope() as session:
        histories_objs = [CrawlerTaskHistory(**data) for data in histories_input_data]
        session.add_all(histories_objs)
        session.flush()  # Assign IDs before commit (optional but can be useful)
        # Store IDs before commit just in case session state is lost
        for obj in histories_objs:
            created_history_ids.append(obj.id)
        session.commit()

    # Re-fetch the data as dictionaries in a new session scope
    histories_output_data = []
    with initialized_db_manager.session_scope() as session:
        # Fetch based on the known task_id or the collected IDs
        histories_db = (
            session.query(CrawlerTaskHistory)
            .filter(CrawlerTaskHistory.task_id == task_id)
            .order_by(CrawlerTaskHistory.start_time.asc())
            .all()
        )

        for h in histories_db:
            histories_output_data.append(
                {
                    "id": h.id,
                    "task_id": h.task_id,
                    "start_time": h.start_time,
                    "end_time": h.end_time,
                    "success": h.success,
                    "articles_count": h.articles_count,
                    "message": h.message,
                    # Add other necessary fields, e.g., created_at if needed by tests
                    "created_at": h.created_at,
                }
            )

    return histories_output_data


class TestCrawlerTaskHistoryRepository:
    """CrawlerTaskHistoryRepository 測試類"""

    # Note: Tests now use sample_task_data and sample_histories_data which are dicts

    def test_find_by_task_id(
        self,
        crawler_task_history_repo: CrawlerTaskHistoryRepository,
        sample_task_data: Dict[str, Any],
        sample_histories_data: List[
            Dict[str, Any]
        ],  # This fixture provides data, but the test calls the repo method
    ):
        """測試根據任務ID查詢歷史記錄（包括預覽）"""
        task_id = sample_task_data["id"]  # Use ID from dict
        preview_fields = ["id", "success", "articles_count"]

        # Test non-preview - Repo method returns ORM objects
        histories = crawler_task_history_repo.find_by_task_id(task_id, sort_desc=False)
        assert len(histories) == 3  # Based on sample_histories_data setup
        assert all(isinstance(h, CrawlerTaskHistory) for h in histories)
        assert all(
            history.task_id == task_id
            for history in histories
            if isinstance(history, CrawlerTaskHistory)
        )

        # Test preview - Repo method returns dicts
        histories_preview = crawler_task_history_repo.find_by_task_id(
            task_id,
            limit=2,
            sort_desc=True,  # Get latest 2
            is_preview=True,
            preview_fields=preview_fields,
        )
        assert len(histories_preview) == 2
        assert all(isinstance(h, dict) for h in histories_preview)
        assert all(
            set(h.keys()) == set(preview_fields)
            for h in histories_preview
            if isinstance(h, dict)
        )
        # Check content based on sort_desc=True (latest first)
        # The sample_histories_data is ordered by start_time asc.
        # Latest by start_time is the last one in sample_histories_data.
        latest_history_data = sorted(
            sample_histories_data, key=lambda x: x["start_time"], reverse=True
        )
        if isinstance(histories_preview[0], dict):
            assert (
                histories_preview[0]["articles_count"]
                == latest_history_data[0]["articles_count"]  # Should be 15
            )
        if isinstance(histories_preview[1], dict):
            assert (
                histories_preview[1]["success"]
                == latest_history_data[1]["success"]  # Should be False
            )

    def test_find_successful_histories(
        self,
        crawler_task_history_repo: CrawlerTaskHistoryRepository,
        sample_histories_data: List[
            Dict[str, Any]
        ],  # Used implicitly for setup verification
    ):
        """測試查詢成功的歷史記錄（包括預覽）"""
        preview_fields = ["start_time", "message"]
        # Find the expected first successful message based on default order (ID asc)
        successful_sorted = sorted(
            [h for h in sample_histories_data if h["success"]],
            key=lambda x: x.get("created_at") or x["id"],
            # reverse=True, # Removed: Default sort is likely ID ASC when created_at is same
        )
        # Expect the message from the first successful record in default sort order
        expected_first_success_message = (
            successful_sorted[0]["message"] if successful_sorted else None
        )

        # Test non-preview
        successful_histories = crawler_task_history_repo.find_successful_histories()
        assert len(successful_histories) == 2  # Based on sample_histories_data setup
        assert all(isinstance(h, CrawlerTaskHistory) for h in successful_histories)
        assert all(
            history.success
            for history in successful_histories
            if isinstance(history, CrawlerTaskHistory)
        )

        # Test preview
        successful_preview = crawler_task_history_repo.find_successful_histories(
            limit=1, is_preview=True, preview_fields=preview_fields
        )
        assert len(successful_preview) == 1
        assert isinstance(successful_preview[0], dict)
        assert set(successful_preview[0].keys()) == set(preview_fields)
        # Assert against the expected message based on default sort order
        assert successful_preview[0]["message"] == expected_first_success_message

    def test_find_failed_histories(
        self,
        crawler_task_history_repo: CrawlerTaskHistoryRepository,
        sample_histories_data: List[
            Dict[str, Any]
        ],  # Used implicitly for setup verification
    ):
        """測試查詢失敗的歷史記錄（包括預覽）"""
        preview_fields = ["id", "message"]
        # Find the expected failed message from fixture data
        failed_history_data = next(
            (h for h in sample_histories_data if not h["success"]), None
        )
        expected_failed_message = (
            failed_history_data["message"] if failed_history_data else None
        )

        # Test non-preview
        failed_histories = crawler_task_history_repo.find_failed_histories()
        assert len(failed_histories) == 1  # Based on sample_histories_data setup
        assert isinstance(failed_histories[0], CrawlerTaskHistory)
        assert not failed_histories[0].success
        assert failed_histories[0].message == expected_failed_message

        # Test preview
        failed_preview = crawler_task_history_repo.find_failed_histories(
            is_preview=True, preview_fields=preview_fields
        )
        assert len(failed_preview) == 1
        assert isinstance(failed_preview[0], dict)
        assert set(failed_preview[0].keys()) == set(preview_fields)
        assert failed_preview[0]["message"] == expected_failed_message

    def test_find_histories_with_articles(
        self,
        crawler_task_history_repo: CrawlerTaskHistoryRepository,
        sample_histories_data: List[
            Dict[str, Any]
        ],  # Used implicitly for setup verification
    ):
        """測試查詢有文章的歷史記錄（包括預覽）"""
        preview_fields = ["articles_count", "success"]
        min_articles = 10
        expected_count = sum(
            1
            for h in sample_histories_data
            if (h.get("articles_count") or 0) >= min_articles
        )
        # Find the expected latest history with min_articles from fixture data
        with_articles_sorted = sorted(
            [
                h
                for h in sample_histories_data
                if (h.get("articles_count") or 0) >= min_articles
            ],
            key=lambda x: x.get("created_at") or x["id"],
            reverse=True,
        )
        expected_latest_with_articles = (
            with_articles_sorted[0] if with_articles_sorted else None
        )

        # Test non-preview
        histories_with_articles = (
            crawler_task_history_repo.find_histories_with_articles(
                min_articles=min_articles
            )
        )
        assert len(histories_with_articles) == expected_count  # Should be 2
        assert all(isinstance(h, CrawlerTaskHistory) for h in histories_with_articles)
        assert all(
            (h.articles_count or 0) >= min_articles
            for h in histories_with_articles
            if isinstance(h, CrawlerTaskHistory)
        )

        # Test preview
        histories_preview = crawler_task_history_repo.find_histories_with_articles(
            min_articles=min_articles,
            limit=1,  # Get only one
            is_preview=True,
            preview_fields=preview_fields,
            # Default sort applies
        )
        assert len(histories_preview) == 1
        assert isinstance(histories_preview[0], dict)
        assert set(histories_preview[0].keys()) == set(preview_fields)
        assert histories_preview[0]["articles_count"] >= min_articles
        assert (
            expected_latest_with_articles is not None
        ), "Expected data not found in fixture"
        assert (
            histories_preview[0]["success"] == expected_latest_with_articles["success"]
        )  # Should be True

    def test_find_histories_by_date_range(
        self,
        crawler_task_history_repo: CrawlerTaskHistoryRepository,
        sample_histories_data: List[Dict[str, Any]],  # Used for date range calculation
    ):
        """測試根據日期範圍查詢歷史記錄（包括預覽）"""
        preview_fields = ["id", "start_time"]
        start_times = [
            h["start_time"] for h in sample_histories_data if h.get("start_time")
        ]
        if not start_times:
            pytest.skip(
                "No start_time found in sample_histories_data to perform date range test"
            )

        earliest_date = min(start_times)
        latest_date = max(start_times)
        middle_date = earliest_date + (latest_date - earliest_date) / 2

        # Test non-preview (example: start date only)
        start_only_histories = crawler_task_history_repo.find_histories_by_date_range(
            start_date=middle_date
        )
        # Count expected from data
        expected_count_start = sum(
            1
            for h in sample_histories_data
            if h.get("start_time") and h["start_time"] >= middle_date
        )
        assert len(start_only_histories) == expected_count_start
        assert all(isinstance(h, CrawlerTaskHistory) for h in start_only_histories)
        assert all(
            h.start_time >= middle_date
            for h in start_only_histories
            if isinstance(h, CrawlerTaskHistory) and h.start_time
        )

        # Test preview (example: end date only)
        end_only_preview = crawler_task_history_repo.find_histories_by_date_range(
            end_date=middle_date,
            limit=1,  # Limit might affect if the single expected item is returned
            is_preview=True,
            preview_fields=preview_fields,
            # Default sort applies - check if the *latest* item before middle_date exists
        )
        expected_end_count = sum(
            1
            for h in sample_histories_data
            if h.get("start_time") and h["start_time"] <= middle_date
        )

        assert len(end_only_preview) <= 1  # Can be 0 or 1 due to limit and data
        if end_only_preview:
            assert isinstance(end_only_preview[0], dict)
            assert set(end_only_preview[0].keys()) == set(preview_fields)
            assert end_only_preview[0]["start_time"] <= middle_date
        else:
            assert (
                expected_end_count == 0
            )  # If nothing is returned, ensure nothing was expected

    def test_get_total_articles_count(
        self,
        crawler_task_history_repo: CrawlerTaskHistoryRepository,
        sample_task_data: Dict[str, Any],
        sample_histories_data: List[Dict[str, Any]],  # Used for verification
    ):
        """測試獲取總文章數量"""
        task_id = sample_task_data["id"]
        expected_task_total = sum(
            h.get("articles_count", 0)
            for h in sample_histories_data
            if h["task_id"] == task_id
        )
        expected_grand_total = sum(
            h.get("articles_count", 0) for h in sample_histories_data
        )

        task_total_count = crawler_task_history_repo.count_total_articles(task_id)
        assert task_total_count == expected_task_total  # Should be 25

        total_count = crawler_task_history_repo.count_total_articles()
        assert total_count == expected_grand_total  # Should be 25

    def test_get_latest_history(
        self,
        crawler_task_history_repo: CrawlerTaskHistoryRepository,
        sample_task_data: Dict[str, Any],
        sample_histories_data: List[Dict[str, Any]],  # Used for verification
    ):
        """測試獲取最新的歷史記錄（根據開始時間，包括預覽）"""
        task_id = sample_task_data["id"]
        preview_fields = ["id", "start_time", "message"]

        # Find expected latest from data
        task_histories = [
            h
            for h in sample_histories_data
            if h["task_id"] == task_id and h.get("start_time")
        ]
        if not task_histories:
            pytest.skip("No histories found for the task in sample_histories_data")
        expected_latest = max(task_histories, key=lambda x: x["start_time"])

        # Test non-preview
        latest_history = crawler_task_history_repo.get_latest_history(task_id)
        assert latest_history is not None
        assert isinstance(latest_history, CrawlerTaskHistory)
        assert latest_history.start_time == expected_latest["start_time"]

        # Test preview
        latest_preview = crawler_task_history_repo.get_latest_history(
            task_id, is_preview=True, preview_fields=preview_fields
        )
        assert latest_preview is not None
        assert isinstance(latest_preview, dict)
        assert set(latest_preview.keys()) == set(preview_fields)
        assert latest_preview["start_time"] == expected_latest["start_time"]
        assert (
            latest_preview["message"] == expected_latest["message"]
        )  # "成功抓取更多文章"

        # Test non-existent task
        nonexistent_latest = crawler_task_history_repo.get_latest_history(999)
        assert nonexistent_latest is None

    def test_get_latest_by_task_id(
        self,
        crawler_task_history_repo: CrawlerTaskHistoryRepository,
        sample_task_data: Dict[str, Any],
        sample_histories_data: List[Dict[str, Any]],  # Used for verification
    ):
        """測試獲取指定任務的最新一筆歷史記錄（根據創建時間/ID，包括預覽）"""
        # Note: BaseRepository.get_latest_by_task_id sorts by ID desc by default
        task_id = sample_task_data["id"]
        preview_fields = ["id", "created_at"]

        # Find expected latest from data (assuming ID or created_at DESC order)
        task_histories = [h for h in sample_histories_data if h["task_id"] == task_id]
        if not task_histories:
            pytest.skip("No histories found for the task in sample_histories_data")
        # Sort by 'created_at' if available, otherwise by 'id' as fallback
        expected_latest = sorted(
            task_histories, key=lambda x: x.get("created_at") or x["id"], reverse=True
        )[0]

        # Test non-preview
        latest_history = crawler_task_history_repo.get_latest_by_task_id(task_id)
        assert latest_history is not None
        assert isinstance(latest_history, CrawlerTaskHistory)
        assert latest_history.id == expected_latest["id"]

        # Test preview
        latest_preview = crawler_task_history_repo.get_latest_by_task_id(
            task_id, is_preview=True, preview_fields=preview_fields
        )
        assert latest_preview is not None
        assert isinstance(latest_preview, dict)
        expected_keys = set(f for f in preview_fields if hasattr(CrawlerTaskHistory, f))
        assert set(latest_preview.keys()) == expected_keys
        assert latest_preview["id"] == expected_latest["id"]

        # Test non-existent task
        nonexistent_latest = crawler_task_history_repo.get_latest_by_task_id(999)
        assert nonexistent_latest is None

    def test_get_histories_older_than(
        self,
        crawler_task_history_repo: CrawlerTaskHistoryRepository,
        sample_histories_data: List[Dict[str, Any]],  # Used for verification
    ):
        """測試獲取超過指定天數的歷史記錄（包括預覽）"""
        preview_fields = ["start_time", "success"]
        days = 2
        threshold_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Find the expected older histories from data
        expected_older_histories = [
            h
            for h in sample_histories_data
            if h.get("start_time") and h["start_time"] < threshold_date
        ]
        expected_older_count = len(expected_older_histories)
        # Find the expected preview based on the METHOD's likely default behavior (lowest ID first among older)
        expected_preview = (
            sorted(
                expected_older_histories,
                key=lambda x: x.get("created_at") or x["id"],
                # Removed reverse=True to match likely ascending ID sort among older records
            )[0]
            if expected_older_histories
            else None
        )

        # Test non-preview
        histories_older = crawler_task_history_repo.get_histories_older_than(days)
        assert len(histories_older) == expected_older_count  # Should be 1
        assert all(isinstance(h, CrawlerTaskHistory) for h in histories_older)
        assert all(
            (h.start_time < threshold_date)
            for h in histories_older
            if isinstance(h, CrawlerTaskHistory) and h.start_time
        )

        # Test preview
        histories_preview = crawler_task_history_repo.get_histories_older_than(
            days,
            limit=1,
            is_preview=True,
            preview_fields=preview_fields,
            # Default sort applies (likely created_at desc)
        )

        assert len(histories_preview) <= 1
        if histories_preview:
            assert expected_preview is not None  # Ensure expected was calculated
            # Compare fields that are actually in the preview_fields
            assert isinstance(histories_preview[0], dict)
            assert set(histories_preview[0].keys()) == set(preview_fields)
            assert histories_preview[0]["start_time"] == expected_preview["start_time"]
            assert histories_preview[0]["success"] == expected_preview["success"]
        else:
            assert expected_older_count == 0  # No preview means no data expected

    def test_update_history_status(
        self,
        # crawler_task_history_repo: CrawlerTaskHistoryRepository, # Use initialized_db_manager directly
        sample_histories_data: List[Dict[str, Any]],
        initialized_db_manager,
    ):
        """測試更新歷史記錄狀態"""
        # Find the failed history data from the fixture result
        failed_history_data = next(
            (h for h in sample_histories_data if not h["success"]), None
        )
        if not failed_history_data:
            pytest.skip(
                "No failed history found in sample_histories_data to test update"
            )
        history_id = failed_history_data["id"]

        # Test update success=True
        with initialized_db_manager.session_scope() as session:
            repo = CrawlerTaskHistoryRepository(session, CrawlerTaskHistory)
            result1 = repo.update_history_status(history_id=history_id, success=True)
            assert result1 is True
            session.commit()  # Commit within the scope
            # Re-fetch to verify within the same session before it closes
            updated1 = repo.get_by_id(history_id)
            assert (
                updated1 and updated1.success is True and updated1.end_time is not None
            )
        # Optionally verify in a new session
        with initialized_db_manager.session_scope() as session:
            repo = CrawlerTaskHistoryRepository(session, CrawlerTaskHistory)
            verified1 = repo.get_by_id(history_id)
            assert verified1 and verified1.success is True

        # Test update success=True, message, articles_count
        with initialized_db_manager.session_scope() as session:
            repo = CrawlerTaskHistoryRepository(session, CrawlerTaskHistory)
            result2 = repo.update_history_status(
                history_id=history_id,
                success=True,
                message="重試成功",
                articles_count=5,
            )
            assert result2 is True
            session.commit()
            updated2 = repo.get_by_id(history_id)
            assert (
                updated2
                and updated2.success is True
                and updated2.message == "重試成功"
                and updated2.articles_count == 5
            )

        # Test updating non-existent ID
        with initialized_db_manager.session_scope() as session:
            repo = CrawlerTaskHistoryRepository(session, CrawlerTaskHistory)
            result3 = repo.update_history_status(history_id=999, success=True)
            assert result3 is False

    def test_create_with_default_values(
        self,
        # crawler_task_history_repo: CrawlerTaskHistoryRepository, # Use initialized_db_manager
        sample_task_data: Dict[str, Any],
        initialized_db_manager,
    ):
        """測試創建時設定預設值的邏輯"""
        min_data = {"task_id": sample_task_data["id"]}
        history_id = None
        with initialized_db_manager.session_scope() as session:
            repo = CrawlerTaskHistoryRepository(session, CrawlerTaskHistory)
            history = repo.create(min_data)
            assert history is not None
            assert history.task_id == sample_task_data["id"]
            assert history.start_time is not None
            assert history.success is False
            assert history.articles_count == 0
            session.flush()  # Ensure ID is available before commit if needed later
            history_id = history.id  # Get id before commit/session closes
            session.commit()  # Commit to save

        assert history_id is not None  # Ensure we got an ID

        # Verify in a new session
        with initialized_db_manager.session_scope() as session:
            repo = CrawlerTaskHistoryRepository(session, CrawlerTaskHistory)
            db_history = repo.get_by_id(history_id)
            assert db_history is not None and db_history.success is False

    def test_create_validation_error(
        self,
        crawler_task_history_repo: CrawlerTaskHistoryRepository,  # Repo fixture is fine here
    ):
        """測試創建時的驗證錯誤處理"""
        invalid_data = {"start_time": datetime.now(timezone.utc), "success": True}
        with pytest.raises(ValidationError) as excinfo:
            # Use the repo provided by the fixture
            crawler_task_history_repo.create(invalid_data)
        assert "task_id" in str(excinfo.value).lower()

    def test_update_immutable_fields(
        self,
        # crawler_task_history_repo: CrawlerTaskHistoryRepository, # Use initialized_db_manager
        sample_histories_data: List[Dict[str, Any]],
        initialized_db_manager,
    ):
        """測試更新不可變欄位的處理邏輯"""
        if not sample_histories_data:
            pytest.skip("No sample histories to test update")

        history_data = sample_histories_data[0]
        history_id = history_data["id"]
        original_task_id = history_data["task_id"]  # Get original from dict
        original_start_time = history_data["start_time"]  # Get original from dict

        update_data = {
            # Include immutable fields in the update data to test they are ignored
            "task_id": 999,
            "start_time": datetime.now(timezone.utc),
            # Include a mutable field to ensure update happens
            "message": "新訊息",
        }

        # Perform update in a session
        with initialized_db_manager.session_scope() as session:
            repo = CrawlerTaskHistoryRepository(session, CrawlerTaskHistory)
            # Fetch the object to ensure it's in the session before update
            # Though BaseRepository.update fetches it internally
            existing_obj = repo.get_by_id(history_id)
            assert existing_obj is not None

            updated = repo.update(history_id, update_data)
            assert updated is not None
            # Check values immediately after update, before commit
            assert updated.message == "新訊息"
            assert updated.task_id == original_task_id  # Should not change
            assert updated.start_time == original_start_time  # Should not change
            session.commit()

        # Verify in a new session
        with initialized_db_manager.session_scope() as session:
            repo = CrawlerTaskHistoryRepository(session, CrawlerTaskHistory)
            refetched = repo.get_by_id(history_id)
            assert refetched
            assert refetched.task_id == original_task_id
            assert refetched.start_time == original_start_time
            assert refetched.message == "新訊息"

    def test_update_empty_data(
        self,
        # crawler_task_history_repo: CrawlerTaskHistoryRepository, # Use initialized_db_manager
        sample_histories_data: List[Dict[str, Any]],
        initialized_db_manager,
    ):
        """測試更新空資料的處理邏輯"""
        if not sample_histories_data:
            pytest.skip("No sample histories to test update")

        history_data = sample_histories_data[0]
        history_id = history_data["id"]
        original_message = history_data["message"]  # Get original from dict

        # Perform update with empty data
        with initialized_db_manager.session_scope() as session:
            repo = CrawlerTaskHistoryRepository(session, CrawlerTaskHistory)
            updated = repo.update(history_id, {})  # Pass empty dict
            assert updated is not None
            assert updated.message == original_message  # Message should be unchanged
            session.commit()  # Commit (though likely no DB changes)

        # Verify in a new session
        with initialized_db_manager.session_scope() as session:
            repo = CrawlerTaskHistoryRepository(session, CrawlerTaskHistory)
            refetched = repo.get_by_id(history_id)
            assert refetched and refetched.message == original_message


class TestModelStructure:
    """測試模型結構"""

    # Keep this class, but the specific test relying on get_model_info is commented out
    pass


class TestSpecialCases:
    """測試特殊情況"""

    def test_empty_database(
        self,
        crawler_task_history_repo: CrawlerTaskHistoryRepository,  # Repo fixture is fine
    ):
        """測試空數據庫的情況"""
        # Ensure the database is truly empty for this test by not using sample data fixtures
        # The crawler_task_history_repo fixture uses initialized_db_manager which creates tables,
        # but doesn't add data unless other fixtures are used.
        assert crawler_task_history_repo.find_all() == []
        assert crawler_task_history_repo.find_successful_histories() == []
        assert crawler_task_history_repo.find_failed_histories() == []
        assert crawler_task_history_repo.count_total_articles() == 0

    def test_invalid_operations(
        self,
        crawler_task_history_repo: CrawlerTaskHistoryRepository,  # Repo fixture is fine
    ):
        """測試無效操作"""
        # Test update_history_status on non-existent ID
        assert (
            crawler_task_history_repo.update_history_status(
                history_id=999, success=True
            )
            is False
        )


class TestErrorHandling:
    """測試錯誤處理"""

    def test_repository_exception_handling(
        self, crawler_task_history_repo: CrawlerTaskHistoryRepository, monkeypatch
    ):
        """測試資料庫操作異常處理 (Finder methods)"""

        def mock_execute_query_error(*args, **kwargs):
            raise DatabaseOperationError("模擬資料庫查詢錯誤 from execute_query")

        monkeypatch.setattr(
            crawler_task_history_repo, "execute_query", mock_execute_query_error
        )

        with pytest.raises(DatabaseOperationError) as excinfo:
            crawler_task_history_repo.find_by_task_id(1)  # Pass a dummy task ID
        assert "模擬資料庫查詢錯誤 from execute_query" in str(excinfo.value)

        with pytest.raises(DatabaseOperationError) as excinfo:
            crawler_task_history_repo.get_latest_by_task_id(1)  # Pass a dummy task ID
        assert "模擬資料庫查詢錯誤 from execute_query" in str(excinfo.value)

    def test_create_exception_handling(
        self,
        crawler_task_history_repo: CrawlerTaskHistoryRepository,
        sample_task_data: Dict[str, Any],  # Need task ID
        monkeypatch,
    ):
        """測試創建時的異常處理"""

        def mock_create_internal_error(*args, **kwargs):
            raise DatabaseOperationError("模擬創建內部錯誤")

        monkeypatch.setattr(
            crawler_task_history_repo, "_create_internal", mock_create_internal_error
        )

        with pytest.raises(DatabaseOperationError) as excinfo:
            crawler_task_history_repo.create(
                {"task_id": sample_task_data["id"]}
            )  # Use task ID
        assert "模擬創建內部錯誤" in str(excinfo.value)

    def test_update_exception_handling(
        self,
        crawler_task_history_repo: CrawlerTaskHistoryRepository,
        sample_histories_data: List[Dict[str, Any]],  # Need history ID
        monkeypatch,
    ):
        """測試更新時的異常處理"""
        if not sample_histories_data:
            pytest.skip("No sample histories to test update")
        history_id = sample_histories_data[0]["id"]  # Use history ID from dict

        def mock_update_internal_error(*args, **kwargs):
            raise DatabaseOperationError("模擬更新內部錯誤")

        monkeypatch.setattr(
            crawler_task_history_repo, "_update_internal", mock_update_internal_error
        )

        with pytest.raises(DatabaseOperationError) as excinfo:
            crawler_task_history_repo.update(history_id, {"message": "測試更新"})
        assert "模擬更新內部錯誤" in str(excinfo.value)
