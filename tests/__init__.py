import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.database_manager import DatabaseManager
from src.model.base_models import Base
import tempfile
import os

@pytest.fixture(scope="function")
def create_in_memory_db():
    """創建記憶體資料庫"""
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.create_tables(Base)
    return db_manager

@pytest.fixture
def create_temp_file_db():
    """提供臨時檔案資料庫管理器"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test.db")
        db_manager = DatabaseManager(db_path)
        yield db_manager, db_path


@pytest.fixture(scope="function")
def create_database_session():
    """創建資料庫會話"""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

__all__ = ["create_in_memory_db", "create_temp_file_db", "create_database_session"]