import pytest
from src.utils.api_validators import validate_crawler_data_api, is_valid_cron_expression
from src.error.errors import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.base_model import Base
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.database.crawlers_repository import CrawlersRepository
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawlers_model import Crawlers
from src.models.crawler_tasks_model import TaskPhase, ScrapeMode
from src.services.crawler_task_service import CrawlerTaskService
from src.services.crawlers_service import CrawlersService
from src.database.database_manager import DatabaseManager
from src.database.base_repository import SchemaType
from unittest.mock import MagicMock, patch

# 創建一個模擬的ValidationError類，用於測試
class MockValidationError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)

# 設置測試資料庫
@pytest.fixture(scope="session")
def engine():
    """創建測試用的資料庫引擎，只需執行一次"""
    return create_engine('sqlite:///:memory:')

@pytest.fixture(scope="session")
def tables(engine):
    """創建資料表結構，只需執行一次"""
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="session")
def session_factory(engine):
    """創建會話工廠，只需執行一次"""
    return sessionmaker(bind=engine)

@pytest.fixture(scope="function")
def session(session_factory, tables):
    """為每個測試函數創建獨立的會話"""
    session = session_factory()
    yield session
    session.rollback()  # 確保每個測試後都回滾未提交的更改
    session.close()

@pytest.fixture
def tasks_repo(session):
    """創建CrawlerTasksRepository的實例"""
    return CrawlerTasksRepository(session, CrawlerTasks)

@pytest.fixture
def crawlers_repo(session):
    """創建CrawlersRepository的實例"""
    return CrawlersRepository(session, Crawlers)

@pytest.fixture
def db_manager(engine, session_factory):
    """建立測試用 DatabaseManager"""
    mock_db_manager = MagicMock(spec=DatabaseManager)
    mock_db_manager.engine = engine
    mock_db_manager.Session = MagicMock(return_value=session_factory())
    return mock_db_manager

@pytest.fixture
def task_service(db_manager):
    """創建真實的 CrawlerTaskService 實例，使用 mocked db_manager"""
    # Use the real service with the mocked db_manager
    service = CrawlerTaskService(db_manager)
    return service

@pytest.fixture
def crawler_service(db_manager):
    """創建真實的 CrawlersService 實例，使用 mocked db_manager"""
    # Use the real service with the mocked db_manager
    service = CrawlersService(db_manager)
    return service

def test_validate_crawler_data_api_with_complete_valid_data(crawler_service):
    """測試完整的有效爬蟲資料"""
    data = {
        'crawler_name': 'test_crawler',
        'source_name': 'Test Source',
        'base_url': 'https://example.com',
        'crawler_type': 'rss',
        'is_active': True,
        'config_file_name': 'test_config.json'
    }
    validated_data = validate_crawler_data_api(data, crawler_service)
    assert validated_data['crawler_name'] == data['crawler_name']
    assert validated_data['base_url'] == data['base_url']
    assert validated_data['crawler_type'] == data['crawler_type']
    assert validated_data['is_active'] == data['is_active']
    assert validated_data['config_file_name'] == data['config_file_name']

def test_validate_crawler_data_api_missing_required_fields(crawler_service):
    """測試缺少必填欄位"""
    data = {
        'crawler_name': 'test_crawler'
    }
    with pytest.raises(ValidationError):
        validate_crawler_data_api(data, crawler_service)

def test_validate_crawler_data_api_with_update_mode(crawler_service):
    """測試爬蟲資料更新模式"""
    data = {
        'crawler_name': 'updated_crawler',
        'is_active': False
    }
    validated_data = validate_crawler_data_api(data, crawler_service, is_update=True)
    assert validated_data['crawler_name'] == data['crawler_name']
    assert validated_data['is_active'] == data['is_active']
    assert 'base_url' not in validated_data  # 更新模式中未提供的欄位不應出現
    assert 'crawler_type' not in validated_data



# --- Tests for is_valid_cron_expression ---

def test_is_valid_cron_expression_valid():
    """測試有效的 cron 表達式"""
    assert is_valid_cron_expression("0 0 * * *") is True
    assert is_valid_cron_expression("*/5 * * * *") is True

def test_is_valid_cron_expression_invalid():
    """測試無效的 cron 表達式"""
    assert is_valid_cron_expression("invalid cron") is False
    assert is_valid_cron_expression("* * * * * *") is False # Too many fields
    assert is_valid_cron_expression("") is False

# --- Additional tests for validate_crawler_data_api ---

def test_validate_crawler_data_api_missing_source_name_on_create(crawler_service):
    """測試創建模式下缺少 source_name"""
    data = {
        # 'source_name': 'missing', # Omitted intentionally
        'base_url': 'https://example.com',
        'crawler_type': 'rss',
        'is_active': True,
        'config_file_name': 'test_config.json'
    }
    # CrawlersRepository 在創建時會檢查 source_name
    # 但 api_validators 在調用 repo 之前就檢查了
    with pytest.raises(ValidationError, match="來源名稱 \\(source_name\\) 是必填欄位"):
        validate_crawler_data_api(data, crawler_service, is_update=False)


