import pytest
from sqlalchemy import create_engine, String
from sqlalchemy.orm import sessionmaker, Mapped, mapped_column
from datetime import datetime, timezone, timedelta
import time # For forcing update timestamp change
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from sqlalchemy import DateTime
from typing import Optional
from src.models.base_model import Base
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Task(Base):
    """A concrete class for testing Base functionality"""
    __tablename__ = 'tasks'
    title: Mapped[str] = mapped_column(String(50))
    # Add another datetime field to test custom watching
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Override __init__ to add 'due_date' to watched fields
    def __init__(self, **kwargs):
        # Explicitly tell Base to watch 'due_date' as well for this subclass
        super().__init__(datetime_fields_to_watch={'due_date'}, **kwargs)


@pytest.fixture(scope="session")
def engine():
    """Session-scoped engine fixture (in-memory SQLite)."""
    # Using check_same_thread=False for SQLite in-memory testing simplicity
    return create_engine("sqlite:///:memory:", echo=False, future=True, connect_args={"check_same_thread": False})

@pytest.fixture(scope="session")
def tables(engine):
    """Session-scoped fixture to create tables."""
    # logger.debug("Creating tables...") # Optional: for debugging fixture execution
    Base.metadata.create_all(engine)
    yield
    # logger.debug("Dropping tables...") # Optional: for debugging fixture execution
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="session")
def session_factory(engine):
    """Session-scoped session factory."""
    return sessionmaker(bind=engine, expire_on_commit=False, future=True) # expire_on_commit=False often useful in tests

@pytest.fixture(scope="function")
def db_session(session_factory, tables):
    """Function-scoped session fixture. Ensures clean state for each test."""
    # Connect to the database and begin a transaction
    session = session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()




def test_task_creation_defaults(db_session):
    """Test creating a Task instance and default values."""
    start_time = datetime.now(timezone.utc)
    task = Task(title="Test Task Default Time")
    db_session.add(task)
    db_session.commit()

    # Use the ID to fetch a fresh instance from the DB
    task_id = task.id
    assert task_id is not None

    # Expire instance data to ensure fresh load (alternative to fetching by id)
    # db_session.expire(task)
    # fetched_task = db_session.get(Task, task_id) # Using get is cleaner with PK

    fetched_task = db_session.get(Task, task_id) # Fetch by ID
    assert fetched_task is not None
    assert fetched_task.title == "Test Task Default Time"
    assert fetched_task.id == task_id

    # Check created_at
    assert fetched_task.created_at is not None
    assert fetched_task.created_at.tzinfo == timezone.utc
    # Check it was created recently
    assert start_time <= fetched_task.created_at <= datetime.now(timezone.utc)

    # Check updated_at is None initially
    assert fetched_task.updated_at is not None
    assert fetched_task.updated_at.tzinfo == timezone.utc

def test_task_creation_explicit_created_at_utc(db_session):
    """Test creating a Task with an explicit UTC created_at."""
    explicit_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    task = Task(title="Explicit UTC Time", created_at=explicit_time)
    db_session.add(task)
    db_session.commit()
    task_id = task.id

    fetched_task = db_session.get(Task, task_id)
    assert fetched_task is not None
    assert fetched_task.created_at == explicit_time
    assert fetched_task.created_at.tzinfo == timezone.utc

def test_task_creation_explicit_created_at_naive(db_session):
    """Test creating a Task with a naive datetime (should be converted to UTC)."""
    naive_time = datetime(2024, 1, 1, 10, 0, 0) # No timezone
    expected_utc_time = naive_time.replace(tzinfo=timezone.utc) # Based on enforce_utc...

    task = Task(title="Naive Time", created_at=naive_time)
    db_session.add(task)
    db_session.commit()
    task_id = task.id

    # Expire all to ensure data comes from DB after potential session caching
    db_session.expire_all()

    fetched_task = db_session.get(Task, task_id)
    assert fetched_task is not None
    assert fetched_task.created_at == expected_utc_time
    assert fetched_task.created_at.tzinfo == timezone.utc # Verify timezone is set

def test_task_creation_explicit_created_at_other_tz(db_session):
    """Test creating a Task with a non-UTC timezone-aware datetime."""
    cet_tz = timezone(timedelta(hours=1)) # Example: CET
    other_tz_time = datetime(2024, 1, 1, 11, 0, 0, tzinfo=cet_tz)
    expected_utc_time = other_tz_time.astimezone(timezone.utc)

    task = Task(title="Other TZ Time", created_at=other_tz_time)
    db_session.add(task)
    db_session.commit()
    task_id = task.id

    db_session.expire_all() # Force reload from DB

    fetched_task = db_session.get(Task, task_id)
    assert fetched_task is not None
    assert fetched_task.created_at == expected_utc_time
    assert fetched_task.created_at.tzinfo == timezone.utc

def test_task_update_sets_updated_at(db_session):
    """Test that updating a Task sets the updated_at field."""
    task = Task(title="Update Me")
    db_session.add(task)
    db_session.commit()
    task_id = task.id
    initial_created_at = task.created_at # Get value before potential expiry

    # Ensure some time passes for updated_at to be different
    time.sleep(0.01)
    update_time_start = datetime.now(timezone.utc)

    # Fetch by ID before update
    task_to_update = db_session.get(Task, task_id)
    assert task_to_update.updated_at is not None # Verify initial state
    assert task_to_update.updated_at.tzinfo == timezone.utc

    # Perform update
    task_to_update.title = "Updated Title"
    db_session.commit()

    # Expire and fetch again to get DB-generated updated_at
    db_session.expire(task_to_update) # Expire specific object
    fetched_task = db_session.get(Task, task_id)

    assert fetched_task.title == "Updated Title"
    assert fetched_task.updated_at is not None
    assert fetched_task.updated_at.tzinfo == timezone.utc
    assert fetched_task.updated_at > initial_created_at
    assert update_time_start <= fetched_task.updated_at <= datetime.now(timezone.utc)

def test_manual_set_updated_at_naive(db_session):
    """Test manually setting updated_at with a naive datetime."""
    task = Task(title="Manual Naive Update")
    db_session.add(task)
    db_session.commit()
    task_id = task.id

    naive_update_time = datetime(2025, 2, 15, 8, 30, 0)
    expected_utc_time = naive_update_time.replace(tzinfo=timezone.utc)

    task_to_update = db_session.get(Task, task_id)
    task_to_update.updated_at = naive_update_time # Manually set using __setattr__
    db_session.commit()

    # Expire and fetch
    db_session.expire(task_to_update)
    fetched_task = db_session.get(Task, task_id)

    assert fetched_task.updated_at is not None
    assert fetched_task.updated_at.tzinfo == timezone.utc
    assert isinstance(fetched_task.updated_at, datetime)


def test_getattribute_adds_utc_if_naive(db_session):
    """Test __getattribute__ adding UTC timezone to a naive datetime."""
    # This test simulates a scenario where data might somehow become naive
    # BEFORE being accessed via the attribute. (e.g., direct DB read without ORM TZ handling)
    # It also tests the __init__ path for setting timezone.
    naive_dt = datetime(2024, 5, 5, 5, 5, 5)
    task = Task(title="Getattribute Test", created_at=naive_dt)

    # Access attribute - __init__ should have already converted it via __setattr__
    assert task.created_at.tzinfo == timezone.utc
    assert task.created_at == naive_dt.replace(tzinfo=timezone.utc)

    # Simulate the attribute becoming naive *after* init (less common with DateTime(timezone=True))
    # We can use object.__setattr__ to bypass our custom logic for testing purposes ONLY
    object.__setattr__(task, 'created_at', naive_dt)
    assert object.__getattribute__(task, 'created_at').tzinfo is None # Verify it's naive internally

    # Now access normally, __getattribute__ should add tzinfo
    assert task.created_at.tzinfo == timezone.utc
    assert task.created_at == naive_dt.replace(tzinfo=timezone.utc)


def test_custom_datetime_field_watching(db_session):
    """Test that custom datetime fields added via init are watched."""
    naive_due_date = datetime(2025, 12, 31, 23, 59, 59)
    cet_tz = timezone(timedelta(hours=1))
    aware_due_date = datetime(2026, 1, 1, 10, 0, 0, tzinfo=cet_tz)

    # Test setting via init (naive)
    task1 = Task(title="Due Date Naive Init", due_date=naive_due_date)
    assert task1.due_date is not None 
    assert task1.due_date.tzinfo == timezone.utc
    assert task1.due_date == naive_due_date.replace(tzinfo=timezone.utc)

    # Test setting via init (aware)
    task2 = Task(title="Due Date Aware Init", due_date=aware_due_date)
    assert task2.due_date is not None
    assert task2.due_date.tzinfo == timezone.utc
    assert task2.due_date == aware_due_date.astimezone(timezone.utc)

    db_session.add_all([task1, task2])
    db_session.commit()
    task1_id = task1.id

    # Test setting via attribute assignment after init
    task_to_update = db_session.get(Task, task1_id)
    assert task_to_update is not None

    # Assign naive
    new_naive_due = datetime(2027, 1, 1, 0, 0, 0)
    task_to_update.due_date = new_naive_due
    assert task_to_update.due_date is not None # Add check after assignment
    assert task_to_update.due_date.tzinfo == timezone.utc # Check __setattr__
    assert task_to_update.due_date == new_naive_due.replace(tzinfo=timezone.utc)

    # Assign aware
    new_aware_due = datetime(2027, 2, 1, 15, 0, 0, tzinfo=cet_tz)
    task_to_update.due_date = new_aware_due
    assert task_to_update.due_date is not None # Add check after assignment
    assert task_to_update.due_date.tzinfo == timezone.utc # Check __setattr__
    assert task_to_update.due_date == new_aware_due.astimezone(timezone.utc)

    db_session.commit() # Save changes

    # Verify from DB
    db_session.expire(task_to_update)
    fetched_task = db_session.get(Task, task1_id)
    assert fetched_task is not None
    assert fetched_task.due_date is not None # Check after fetching from DB
    assert fetched_task.due_date.tzinfo == timezone.utc
    assert fetched_task.due_date == new_aware_due.astimezone(timezone.utc)


def test_to_dict_method(db_session):
    """Test the to_dict method."""
    task = Task(title="Dict Task")
    db_session.add(task)
    db_session.commit()
    task_id = task.id

    # Fetch to ensure IDs and timestamps are populated
    fetched_task = db_session.get(Task, task_id)

    task_dict = fetched_task.to_dict()

    assert isinstance(task_dict, dict)
    assert task_dict['id'] == fetched_task.id
    assert task_dict['created_at'] == fetched_task.created_at
    assert task_dict['updated_at'] == fetched_task.updated_at # Will be None initially
    assert 'title' not in task_dict # Base to_dict only includes Base fields

    # Test after update
    time.sleep(0.01)
    fetched_task.title = "Updated Dict Task"
    db_session.commit()
    db_session.expire(fetched_task)
    updated_task = db_session.get(Task, task_id)
    updated_dict = updated_task.to_dict()

    assert updated_dict['id'] == updated_task.id
    assert updated_dict['created_at'] == updated_task.created_at
    assert updated_dict['updated_at'] == updated_task.updated_at
    assert updated_dict['updated_at'] is not None # Should be set now