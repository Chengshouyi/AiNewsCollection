# flake8: noqa: F811

"""Tests for the Base model functionality."""

# Standard library imports
import logging
import time  # For forcing update timestamp change
from datetime import datetime, timezone, timedelta
from typing import Optional

# Third party imports
import pytest
from sqlalchemy import String  # Removed create_engine, sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

# Local application imports
from src.models.base_model import Base
from src.utils.type_utils import AwareDateTime


logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class Task(Base):
    """A concrete class for testing Base functionality"""

    __tablename__ = "tasks"
    title: Mapped[str] = mapped_column(String(50))
    # Add another datetime field to test custom watching
    due_date: Mapped[Optional[datetime]] = mapped_column(AwareDateTime)

    # Override __init__ to add 'due_date' to watched fields
    # def __init__(self, **kwargs):
    #     # Explicitly tell Base to watch 'due_date' as well for this subclass
    #     super().__init__(datetime_fields_to_watch={'due_date'}, **kwargs)

    # *** 關鍵：擴展需要 __setattr__ 處理的欄位 ***
    _aware_datetime_fields = Base._aware_datetime_fields.union({"due_date"})


# Removed engine, tables, session_factory, db_session fixtures


# Use function scope for clean tables each test
@pytest.fixture(scope="function")
def initialized_db_manager(db_manager_for_test):  # noqa: F811
    """
    Fixture that depends on db_manager_for_test, creates tables, and yields the manager.
    """
    logger.debug("Creating tables for test function...")
    try:
        db_manager_for_test.create_tables(Base)
        yield db_manager_for_test
    finally:
        logger.debug(
            "Test function finished, tables might be dropped by manager cleanup or next test setup."
        )


# --- Test Functions Updated to use underscored parameter ---


def test_task_creation_defaults(initialized_db_manager):
    """Test creating a Task instance and default values."""
    start_time = datetime.now(timezone.utc)

    with initialized_db_manager.session_scope() as session:
        task = Task(title="Test Task Default Time")
        session.add(task)
        session.flush()
        task_id = task.id
        assert task_id is not None

    with initialized_db_manager.session_scope() as session:
        fetched_task = session.get(Task, task_id)  # Fetch by ID
        assert fetched_task is not None
        assert fetched_task.title == "Test Task Default Time"
        assert fetched_task.id == task_id

        # Check created_at
        assert fetched_task.created_at is not None
        assert fetched_task.created_at.tzinfo == timezone.utc
        # Check it was created recently
        assert start_time <= fetched_task.created_at <= datetime.now(timezone.utc)

        # Check updated_at is set by the listener upon creation in this setup
        assert fetched_task.updated_at is not None
        assert fetched_task.updated_at.tzinfo == timezone.utc
        # updated_at should be very close or equal to created_at on initial creation
        assert abs(fetched_task.updated_at - fetched_task.created_at) < timedelta(
            seconds=1
        )


def test_task_creation_explicit_created_at_utc(initialized_db_manager):
    """Test creating a Task with an explicit UTC created_at."""
    db_manager = initialized_db_manager
    explicit_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    with db_manager.session_scope() as session:
        task = Task(title="Explicit UTC Time", created_at=explicit_time)
        session.add(task)
        session.flush()  # Get ID
        task_id = task.id

    with db_manager.session_scope() as session:
        fetched_task = session.get(Task, task_id)
        assert fetched_task is not None
        assert fetched_task.created_at == explicit_time
        assert fetched_task.created_at.tzinfo == timezone.utc


def test_task_creation_explicit_created_at_naive(initialized_db_manager):
    """Test creating a Task with a naive datetime (should be converted to UTC)."""
    db_manager = initialized_db_manager
    naive_time = datetime(2024, 1, 1, 10, 0, 0)  # No timezone
    expected_utc_time = naive_time.replace(
        tzinfo=timezone.utc
    )  # Based on enforce_utc...

    with db_manager.session_scope() as session:
        task = Task(title="Naive Time", created_at=naive_time)
        session.add(task)
        session.flush()
        task_id = task.id

    with db_manager.session_scope() as session:
        # Expire all might not be necessary if fetching in a new session
        # session.expire_all() # If you were reusing the same session instance

        fetched_task = session.get(Task, task_id)
        assert fetched_task is not None
        assert fetched_task.created_at == expected_utc_time
        assert fetched_task.created_at.tzinfo == timezone.utc  # Verify timezone is set


def test_task_creation_explicit_created_at_other_tz(initialized_db_manager):
    """Test creating a Task with a non-UTC timezone-aware datetime."""
    db_manager = initialized_db_manager
    cet_tz = timezone(timedelta(hours=1))  # Example: CET
    other_tz_time = datetime(2024, 1, 1, 11, 0, 0, tzinfo=cet_tz)
    expected_utc_time = other_tz_time.astimezone(timezone.utc)

    with db_manager.session_scope() as session:
        task = Task(title="Other TZ Time", created_at=other_tz_time)
        session.add(task)
        session.flush()
        task_id = task.id

    with db_manager.session_scope() as session:
        # session.expire_all() # Force reload from DB if reusing session

        fetched_task = session.get(Task, task_id)
        assert fetched_task is not None
        assert fetched_task.created_at == expected_utc_time
        assert fetched_task.created_at.tzinfo == timezone.utc


def test_task_update_sets_updated_at(initialized_db_manager):
    """Test that updating a Task sets the updated_at field."""
    db_manager = initialized_db_manager
    task_id = None
    initial_created_at = None
    initial_updated_at = None

    # Create task
    with db_manager.session_scope() as session:
        task = Task(title="Update Me")
        session.add(task)
        session.flush()
        task_id = task.id
        initial_created_at = task.created_at  # Get value before potential expiry
        initial_updated_at = task.updated_at  # Should be set on creation too
        assert initial_updated_at is not None
        assert initial_created_at is not None

    # Ensure some time passes for updated_at to be different
    time.sleep(0.01)
    update_time_start = datetime.now(timezone.utc)

    # Perform update in a new session scope
    with db_manager.session_scope() as session:
        task_to_update = session.get(Task, task_id)
        assert task_to_update is not None
        # Verify initial state loaded correctly
        assert (
            task_to_update.updated_at is not None
        )  # Verify initial state loaded correctly
        assert task_to_update.updated_at.tzinfo == timezone.utc

        # Perform update
        task_to_update.title = "Updated Title"
        session.flush()  # updated_at should be updated by the listener here
        updated_at_after_flush = task_to_update.updated_at
        # Commit happens automatically

    # Fetch again to verify persisted update
    with db_manager.session_scope() as session:
        fetched_task = session.get(Task, task_id)

        assert fetched_task.title == "Updated Title"
        assert fetched_task.updated_at is not None
        assert fetched_task.updated_at.tzinfo == timezone.utc
        # Compare with the value *after* the update flush/commit in the previous session
        assert fetched_task.updated_at == updated_at_after_flush
        # Compare with the initial value before update
        assert fetched_task.updated_at > initial_updated_at
        assert (
            fetched_task.updated_at > initial_created_at
        )  # Also should be greater than created_at
        # Check time bounds
        assert (
            update_time_start <= fetched_task.updated_at <= datetime.now(timezone.utc)
        )


def test_manual_set_updated_at_naive(initialized_db_manager):
    """Test manually setting updated_at with a naive datetime."""
    db_manager = initialized_db_manager
    task_id = None

    with db_manager.session_scope() as session:
        task = Task(title="Manual Naive Update")
        session.add(task)
        session.flush()
        task_id = task.id

    naive_update_time = datetime(2025, 2, 15, 8, 30, 0)
    expected_utc_time = naive_update_time.replace(tzinfo=timezone.utc)

    with db_manager.session_scope() as session:
        task_to_update = session.get(Task, task_id)
        task_to_update.updated_at = naive_update_time  # Manually set using __setattr__
        session.flush()  # Ensure change is flushed before commit
        updated_at_value = (
            task_to_update.updated_at
        )  # Capture value after potential changes by __setattr__
        # Commit happens automatically

    with db_manager.session_scope() as session:
        fetched_task = session.get(Task, task_id)

        assert fetched_task.updated_at is not None
        assert fetched_task.updated_at.tzinfo == timezone.utc
        # Verify __setattr__ correctly converted the naive time
        # Note: SQLAlchemy might intercept direct attribute sets sometimes.
        # The Base model's __setattr__ should handle this conversion.
        assert fetched_task.updated_at == expected_utc_time
        # Also check against the value captured after flush
        assert fetched_task.updated_at == updated_at_value
        assert isinstance(fetched_task.updated_at, datetime)


# Removed test_getattribute_adds_utc_if_naive as it manipulates internals
# in a way less relevant with the current __setattr__ approach.


def test_custom_datetime_field_watching(initialized_db_manager):
    """Test that custom datetime fields added via init/setattr are watched."""
    db_manager = initialized_db_manager
    naive_due_date = datetime(2025, 12, 31, 23, 59, 59)
    cet_tz = timezone(timedelta(hours=1))
    aware_due_date = datetime(2026, 1, 1, 10, 0, 0, tzinfo=cet_tz)
    task1_id = None

    # Test setting via init (naive and aware) and add to session
    with db_manager.session_scope() as session:
        task1 = Task(title="Due Date Naive Init", due_date=naive_due_date)
        assert task1.due_date is not None
        assert task1.due_date.tzinfo == timezone.utc
        assert task1.due_date == naive_due_date.replace(tzinfo=timezone.utc)

        task2 = Task(title="Due Date Aware Init", due_date=aware_due_date)
        assert task2.due_date is not None
        assert task2.due_date.tzinfo == timezone.utc
        assert task2.due_date == aware_due_date.astimezone(timezone.utc)

        session.add_all([task1, task2])
        session.flush()
        task1_id = task1.id  # Get ID for later use

    # Test setting via attribute assignment after init
    new_naive_due = datetime(2027, 1, 1, 0, 0, 0)
    new_aware_due = datetime(2027, 2, 1, 15, 0, 0, tzinfo=cet_tz)
    due_date_after_aware_set = None

    with db_manager.session_scope() as session:
        task_to_update = session.get(Task, task1_id)
        assert task_to_update is not None

        # Assign naive
        task_to_update.due_date = new_naive_due
        assert task_to_update.due_date is not None  # Add check after assignment
        assert task_to_update.due_date.tzinfo == timezone.utc  # Check __setattr__
        assert task_to_update.due_date == new_naive_due.replace(tzinfo=timezone.utc)

        # Assign aware
        task_to_update.due_date = new_aware_due
        assert task_to_update.due_date is not None  # Add check after assignment
        assert task_to_update.due_date.tzinfo == timezone.utc  # Check __setattr__
        assert task_to_update.due_date == new_aware_due.astimezone(timezone.utc)
        due_date_after_aware_set = (
            task_to_update.due_date
        )  # Capture the final value before commit
        # Commit happens automatically

    # Verify from DB
    with db_manager.session_scope() as session:
        fetched_task = session.get(Task, task1_id)
        assert fetched_task is not None
        assert fetched_task.due_date is not None  # Check after fetching from DB
        assert fetched_task.due_date.tzinfo == timezone.utc
        # Compare against the value *before* commit in the previous session
        assert fetched_task.due_date == due_date_after_aware_set
        # Also compare against the expected UTC conversion of the last set value
        assert fetched_task.due_date == new_aware_due.astimezone(timezone.utc)


def test_to_dict_method(initialized_db_manager):
    """Test the to_dict method."""
    db_manager = initialized_db_manager
    task_id = None
    # Remove initial ISO captures here
    # created_at_iso = None
    # updated_at_iso_initial = None

    # Create task
    with db_manager.session_scope() as session:
        task = Task(title="Dict Task")
        session.add(task)
        session.flush()
        task_id = task.id
        # Don't capture ISO strings immediately after flush

    # Fetch and test initial to_dict
    updated_at_iso_initial = None  # Define here for later comparison
    with db_manager.session_scope() as session:
        fetched_task = session.get(Task, task_id)
        assert fetched_task is not None
        # Assert timestamps are populated after fetch
        assert fetched_task.created_at is not None
        assert fetched_task.updated_at is not None

        # Now capture the initial updated_at ISO string
        updated_at_iso_initial = fetched_task.updated_at.isoformat()
        created_at_iso = fetched_task.created_at.isoformat()  # Capture created_at too

        task_dict = fetched_task.to_dict()

        assert isinstance(task_dict, dict)
        assert task_dict["id"] == task_id
        assert task_dict["created_at"] == created_at_iso
        assert task_dict["updated_at"] == updated_at_iso_initial
        assert "title" not in task_dict  # Base to_dict only includes Base fields

    # Update the task
    time.sleep(0.01)
    updated_at_iso_after_update = None
    with db_manager.session_scope() as session:
        task_to_update = session.get(Task, task_id)
        task_to_update.title = "Updated Dict Task"
        session.flush()  # Flush to update timestamp
        assert task_to_update.updated_at is not None  # Should be updated now
        updated_at_iso_after_update = (
            task_to_update.updated_at.isoformat()
        )  # Capture new timestamp

    # Fetch again and test updated to_dict
    with db_manager.session_scope() as session:
        updated_task = session.get(Task, task_id)
        updated_dict = updated_task.to_dict()

        assert updated_dict["id"] == task_id
        assert (
            updated_dict["created_at"] == created_at_iso
        )  # Created_at should not change
        assert updated_dict["updated_at"] is not None
        assert (
            updated_dict["updated_at"] == updated_at_iso_after_update
        )  # Check against captured value
        # Ensure updated_at actually changed compared to the initial value captured after fetch
        assert updated_at_iso_initial is not None  # Make sure it was captured
        assert updated_dict["updated_at"] > updated_at_iso_initial
        assert "title" not in updated_dict
