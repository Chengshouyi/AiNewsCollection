import pytest
from src.utils.validators import validate_task_data, validate_crawler_data
from src.error.errors import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.base_model import Base
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.database.crawlers_repository import CrawlersRepository
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawlers_model import Crawlers

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

def test_validate_task_data_with_valid_minimal_data(tasks_repo):
    """測試最小化的有效任務資料"""
    data = {
        'crawler_id': 1,
        'task_name': 'test_task',
        'task_args': {},
        'ai_only': False
    }
    validated_data = validate_task_data(data, tasks_repo)
    assert validated_data['crawler_id'] == data['crawler_id']
    assert validated_data['task_name'] == data['task_name']
    assert validated_data['task_args'] == data['task_args']
    assert validated_data['ai_only'] == data['ai_only']

def test_validate_task_data_with_complete_valid_data(tasks_repo):
    """測試完整的有效任務資料"""
    data = {
        'crawler_id': 1,
        'task_name': 'test_task',
        'task_args': {'url': 'https://example.com'},
        'is_auto': True,
        'ai_only': True,
        'cron_expression': '0 0 * * *',
        'notes': 'test notes',
        'last_run_message': 'success'
    }
    validated_data = validate_task_data(data, tasks_repo)
    assert validated_data['crawler_id'] == data['crawler_id']
    assert validated_data['task_name'] == data['task_name']
    assert validated_data['task_args'] == data['task_args']
    assert validated_data['is_auto'] == data['is_auto']
    assert validated_data['ai_only'] == data['ai_only']
    assert validated_data['cron_expression'] == data['cron_expression']
    assert validated_data['notes'] == data['notes']
    assert validated_data['last_run_message'] == data['last_run_message']

def test_validate_task_data_auto_without_cron(tasks_repo):
    """測試自動執行但未提供 cron 表達式"""
    data = {
        'crawler_id': 1,
        'task_name': 'test_task',
        'task_args': {},
        'is_auto': True,
        'ai_only': False
    }
    with pytest.raises(ValidationError, match="cron_expression: 當設定為自動執行時,此欄位不能為空"):
        validate_task_data(data, tasks_repo)

def test_validate_task_data_with_invalid_task_name_length(tasks_repo):
    """測試任務名稱超過長度限制"""
    data = {
        'crawler_id': 1,
        'task_name': 'x' * 256,  # 超過255字元
        'task_args': {},
        'ai_only': False
    }
    with pytest.raises(ValidationError):
        validate_task_data(data, tasks_repo)

def test_validate_task_data_with_invalid_notes_length(tasks_repo):
    """測試備註超過長度限制"""
    data = {
        'crawler_id': 1,
        'task_name': 'test_task',
        'task_args': {},
        'ai_only': False,
        'notes': 'x' * 65537  # 超過65536字元
    }
    with pytest.raises(ValidationError):
        validate_task_data(data, tasks_repo)

def test_validate_task_data_missing_required_fields(tasks_repo):
    """測試缺少必填欄位"""
    data = {
        'task_name': 'test_task'
    }
    with pytest.raises(ValidationError):
        validate_task_data(data, tasks_repo)

def test_validate_task_data_invalid_task_name_length(tasks_repo):
    """測試任務名稱超過長度限制"""
    data = {
        'crawler_id': 1,
        'task_name': 'x' * 101  # 超過100字元
    }
    with pytest.raises(ValidationError):
        validate_task_data(data, tasks_repo)

def test_validate_task_data_invalid_cron_expression(tasks_repo):
    """測試無效的 cron 表達式"""
    data = {
        'crawler_id': 1,
        'task_name': 'test_task',
        'cron_expression': 'invalid_cron',
        'is_auto': True
    }
    with pytest.raises(ValidationError):
        validate_task_data(data, tasks_repo)

def test_validate_task_data_scheduled_without_cron(tasks_repo):
    """測試排程任務但未提供 cron 表達式"""
    data = {
        'crawler_id': 1,
        'task_name': 'test_task',
        'is_auto': True
    }
    with pytest.raises(ValidationError):
        validate_task_data(data, tasks_repo)

def test_validate_task_data_invalid_task_args(tasks_repo):
    """測試無效的任務參數"""
    data = {
        'crawler_id': 1,
        'task_name': 'test_task',
        'task_args': 'not_a_dict'  # 應該是字典類型
    }
    with pytest.raises(ValidationError):
        validate_task_data(data, tasks_repo)

def test_validate_crawler_data_with_valid_minimal_data(crawlers_repo):
    """測試最小化的有效爬蟲資料"""
    data = {
        'crawler_name': 'test_crawler',
        'base_url': 'https://example.com',
        'crawler_type': 'rss',
        'is_active': True,
        'config_file_name': 'test_config.json'
    }
    validated_data = validate_crawler_data(data, crawlers_repo)
    assert validated_data['crawler_name'] == data['crawler_name']
    assert validated_data['base_url'] == data['base_url']
    assert validated_data['crawler_type'] == data['crawler_type']
    assert validated_data['is_active'] == data['is_active']
    assert validated_data['config_file_name'] == data['config_file_name']

def test_validate_crawler_data_with_complete_valid_data(crawlers_repo):
    """測試完整的有效爬蟲資料"""
    data = {
        'crawler_name': 'test_crawler',
        'base_url': 'https://example.com',
        'crawler_type': 'rss',
        'is_active': True,
        'config_file_name': 'test_config.json'
    }
    validated_data = validate_crawler_data(data, crawlers_repo)
    assert validated_data['crawler_name'] == data['crawler_name']
    assert validated_data['base_url'] == data['base_url']
    assert validated_data['crawler_type'] == data['crawler_type']
    assert validated_data['is_active'] == data['is_active']
    assert validated_data['config_file_name'] == data['config_file_name']

def test_validate_crawler_data_missing_required_fields(crawlers_repo):
    """測試缺少必填欄位"""
    data = {
        'crawler_name': 'test_crawler'
    }
    with pytest.raises(ValidationError):
        validate_crawler_data(data, crawlers_repo)