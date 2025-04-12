import pytest
from src.utils.validators import validate_task_data_api, validate_crawler_data_api
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

# 修改TaskService的_get_repository方法，使其能夠直接返回Repository
class CrawlerTaskServiceForTest(CrawlerTaskService):
    def __init__(self, db_manager=None, repos=None):
        super().__init__(db_manager)
        self._test_repos = repos or {}
        
    def _get_repositories(self):
        """獲取相關資料庫訪問對象"""
        tasks_repo = self._test_repos.get('CrawlerTask')
        crawlers_repo = self._test_repos.get('Crawler') 
        history_repo = self._test_repos.get('TaskHistory')
        return (tasks_repo, crawlers_repo, history_repo)
    
    def validate_task_data(self, data, is_update=False):
        """覆寫驗證方法，直接使用儲存庫而不通過Service.validate_data"""
        schema_type = SchemaType.UPDATE if is_update else SchemaType.CREATE
        tasks_repo = self._test_repos.get('CrawlerTask')
        if tasks_repo:
            return tasks_repo.validate_data(data, schema_type)
        return super().validate_task_data(data, is_update)

# 修改CrawlerService的_get_repository方法
class CrawlersServiceForTest(CrawlersService):
    def __init__(self, db_manager=None, repos=None):
        super().__init__(db_manager)
        self._test_repos = repos or {}
        
    def _get_repository(self):
        """覆寫獲取儲存庫方法，直接返回測試儲存庫"""
        if 'Crawler' in self._test_repos:
            return self._test_repos['Crawler']
        return super()._get_repository()
    
    def validate_crawler_data(self, data, is_update=False):
        """覆寫驗證方法，直接使用儲存庫而不通過Service.validate_data"""
        schema_type = SchemaType.UPDATE if is_update else SchemaType.CREATE
        crawler_repo = self._test_repos.get('Crawler')
        if crawler_repo:
            return crawler_repo.validate_data(data, schema_type)
        return super().validate_crawler_data(data, is_update)

@pytest.fixture
def db_manager(engine, session_factory):
    """建立測試用 DatabaseManager"""
    mock_db_manager = MagicMock(spec=DatabaseManager)
    mock_db_manager.engine = engine
    mock_db_manager.Session = MagicMock(return_value=session_factory())
    return mock_db_manager

@pytest.fixture
def task_service(db_manager, tasks_repo):
    """創建CrawlerTaskService的實例"""
    service = CrawlerTaskServiceForTest(db_manager, {'CrawlerTask': tasks_repo})
    return service

@pytest.fixture
def crawler_service(db_manager, crawlers_repo):
    """創建CrawlersService的實例"""
    service = CrawlersServiceForTest(db_manager, {'Crawler': crawlers_repo})
    return service

def test_validate_task_data_api_with_valid_minimal_data(task_service):
    """測試最小化的有效任務資料"""
    data = {
        'crawler_id': 1,
        'task_name': 'test_task',
        'task_args': {},
        'ai_only': False,
        'current_phase': TaskPhase.INIT,
        'max_retries': 3,
        'retry_count': 0,
        'scrape_mode': ScrapeMode.FULL_SCRAPE
    }
    validated_data = validate_task_data_api(data, task_service)
    assert validated_data['crawler_id'] == data['crawler_id']
    assert validated_data['task_name'] == data['task_name']
    assert validated_data['task_args'] == data['task_args']
    assert validated_data['ai_only'] == data['ai_only']

def test_validate_task_data_api_with_complete_valid_data(task_service):
    """測試完整的有效任務資料"""
    data = {
        'crawler_id': 1,
        'task_name': 'test_task',
        'task_args': {'url': 'https://example.com'},
        'is_auto': True,
        'ai_only': True,
        'cron_expression': '0 0 * * *',
        'notes': 'test notes',
        'last_run_message': 'success',
        'current_phase': TaskPhase.INIT,
        'max_retries': 3,
        'retry_count': 0,
        'scrape_mode': ScrapeMode.FULL_SCRAPE
    }
    validated_data = validate_task_data_api(data, task_service)
    assert validated_data['crawler_id'] == data['crawler_id']
    assert validated_data['task_name'] == data['task_name']
    assert validated_data['task_args'] == data['task_args']
    assert validated_data['is_auto'] == data['is_auto']
    assert validated_data['ai_only'] == data['ai_only']
    assert validated_data['cron_expression'] == data['cron_expression']
    assert validated_data['notes'] == data['notes']
    assert validated_data['last_run_message'] == data['last_run_message']

def test_validate_task_data_api_auto_without_cron(task_service):
    """測試自動執行但未提供 cron 表達式"""
    data = {
        'crawler_id': 1,
        'task_name': 'test_task',
        'task_args': {},
        'is_auto': True,
        'ai_only': False,
        'scrape_mode': ScrapeMode.FULL_SCRAPE
    }
    with pytest.raises(ValidationError, match="cron_expression: 當設定為自動執行時,此欄位不能為空"):
        validate_task_data_api(data, task_service)

def test_validate_task_data_api_with_invalid_task_name_length(task_service):
    """測試任務名稱超過長度限制"""
    data = {
        'crawler_id': 1,
        'task_name': 'x' * 256,  # 超過255字元
        'task_args': {},
        'ai_only': False,
        'scrape_mode': ScrapeMode.FULL_SCRAPE
    }
    with pytest.raises(ValidationError):
        validate_task_data_api(data, task_service)

def test_validate_task_data_api_with_invalid_notes_length(task_service):
    """測試備註超過長度限制"""
    data = {
        'crawler_id': 1,
        'task_name': 'test_task',
        'task_args': {},
        'ai_only': False,
        'notes': 'x' * 65537,  # 超過65536字元
        'scrape_mode': ScrapeMode.FULL_SCRAPE
    }
    with pytest.raises(ValidationError):
        validate_task_data_api(data, task_service)

def test_validate_task_data_api_missing_required_fields(task_service):
    """測試缺少必填欄位"""
    data = {
        'task_name': 'test_task'
    }
    with pytest.raises(ValidationError):
        validate_task_data_api(data, task_service)

def test_validate_task_data_api_invalid_task_name_length(task_service):
    """測試任務名稱超過長度限制"""
    data = {
        'crawler_id': 1,
        'task_name': 'x' * 101,  # 超過100字元
        'scrape_mode': ScrapeMode.FULL_SCRAPE
    }
    with pytest.raises(ValidationError):
        validate_task_data_api(data, task_service)

def test_validate_task_data_api_invalid_cron_expression(task_service):
    """測試無效的 cron 表達式"""
    data = {
        'crawler_id': 1,
        'task_name': 'test_task',
        'cron_expression': 'invalid_cron',
        'is_auto': True,
        'scrape_mode': ScrapeMode.FULL_SCRAPE
    }
    with pytest.raises(ValidationError):
        validate_task_data_api(data, task_service)

def test_validate_task_data_api_scheduled_without_cron(task_service):
    """測試排程任務但未提供 cron 表達式"""
    data = {
        'crawler_id': 1,
        'task_name': 'test_task',
        'is_auto': True,
        'scrape_mode': ScrapeMode.FULL_SCRAPE
    }
    with pytest.raises(ValidationError):
        validate_task_data_api(data, task_service)

def test_validate_task_data_api_invalid_task_args(task_service):
    """測試無效的任務參數"""
    data = {
        'crawler_id': 1,
        'task_name': 'test_task',
        'task_args': 'not_a_dict',  # 應該是字典類型
        'scrape_mode': ScrapeMode.FULL_SCRAPE
    }
    with pytest.raises(ValidationError):
        validate_task_data_api(data, task_service)

def test_validate_crawler_data_api_with_valid_minimal_data(crawler_service):
    """測試最小化的有效爬蟲資料"""
    data = {
        'crawler_name': 'test_crawler',
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

def test_validate_crawler_data_api_with_complete_valid_data(crawler_service):
    """測試完整的有效爬蟲資料"""
    data = {
        'crawler_name': 'test_crawler',
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

def test_validate_task_data_api_with_valid_scrape_mode_as_string(task_service):
    """測試使用字符串形式有效的 scrape_mode 值"""
    data = {
        'crawler_id': 1,
        'task_name': 'test_task',
        'task_args': {
            'scrape_mode': ScrapeMode.LINKS_ONLY.value  # 使用枚舉的實際值
        },
        'is_auto': False,
        'ai_only': False,
        'max_retries': 3,
        'retry_count': 0,
        'current_phase': TaskPhase.INIT,
        'scrape_mode': ScrapeMode.LINKS_ONLY  # 在根層級添加
    }
    validated_data = validate_task_data_api(data, task_service)
    assert validated_data['task_args']['scrape_mode'] == ScrapeMode.LINKS_ONLY.value

def test_validate_task_data_api_with_valid_scrape_mode_as_enum(task_service):
    """測試使用枚舉對象形式有效的 scrape_mode 值"""
    data = {
        'crawler_id': 1,
        'task_name': 'test_task',
        'task_args': {
            'scrape_mode': ScrapeMode.CONTENT_ONLY  # 使用枚舉對象
        },
        'is_auto': False,
        'ai_only': False,
        'max_retries': 3,
        'retry_count': 0,
        'current_phase': TaskPhase.INIT,
        'scrape_mode': ScrapeMode.CONTENT_ONLY  # 在根層級添加
    }
    validated_data = validate_task_data_api(data, task_service)
    # 驗證器應該將枚舉轉換為其字符串值
    assert validated_data['task_args']['scrape_mode'] == ScrapeMode.CONTENT_ONLY.value

def test_validate_task_data_api_with_invalid_scrape_mode_string(task_service):
    """測試使用無效的 scrape_mode 字符串值"""
    with patch('src.utils.validators.ValidationError', MockValidationError):
        data = {
            'crawler_id': 1,
            'task_name': 'test_task',
            'task_args': {
                'scrape_mode': 'invalid_mode'  # 無效的模式字符串
            },
            'is_auto': False,
            'ai_only': False,
            'max_retries': 3,
            'retry_count': 0,
            'current_phase': TaskPhase.INIT,
            'scrape_mode': ScrapeMode.FULL_SCRAPE  # 在根層級添加有效值
        }
        with pytest.raises(MockValidationError, match="無效的scrape_mode值"):
            validate_task_data_api(data, task_service)

def test_validate_task_data_api_with_invalid_scrape_mode_type(task_service):
    """測試使用非字符串非枚舉的 scrape_mode 值"""
    with patch('src.utils.validators.ValidationError', MockValidationError):
        data = {
            'crawler_id': 1,
            'task_name': 'test_task',
            'task_args': {
                'scrape_mode': 42  # 整數不是有效的scrape_mode類型
            },
            'is_auto': False,
            'ai_only': False,
            'max_retries': 3,
            'retry_count': 0,
            'current_phase': TaskPhase.INIT,
            'scrape_mode': ScrapeMode.FULL_SCRAPE  # 在根層級添加有效值
        }
        with pytest.raises(MockValidationError, match="無效的抓取模式"):
            validate_task_data_api(data, task_service)

def test_validate_task_data_api_with_invalid_scrape_mode_type_none(task_service):
    """測試使用None作為scrape_mode值"""
    with patch('src.utils.validators.ValidationError', MockValidationError):
        data = {
            'crawler_id': 1,
            'task_name': 'test_task',
            'task_args': {
                'scrape_mode': None  # None不是有效的scrape_mode類型
            },
            'is_auto': False,
            'ai_only': False,
            'max_retries': 3,
            'retry_count': 0,
            'current_phase': TaskPhase.INIT,
            'scrape_mode': ScrapeMode.FULL_SCRAPE  # 在根層級添加有效值
        }
        with pytest.raises(MockValidationError, match="無效的抓取模式"):
            validate_task_data_api(data, task_service)

def test_validate_task_data_api_with_invalid_scrape_mode_value(task_service):
    """測試使用無效的字符串作為scrape_mode值"""
    with patch('src.utils.validators.ValidationError', MockValidationError):
        data = {
            'crawler_id': 1,
            'task_name': 'test_task',
            'task_args': {
                'scrape_mode': 'INVALID_MODE'  # 不是有效的ScrapeMode值
            },
            'is_auto': False,
            'ai_only': False,
            'max_retries': 3,
            'retry_count': 0,
            'current_phase': TaskPhase.INIT,
            'scrape_mode': ScrapeMode.FULL_SCRAPE  # 在根層級添加有效值
        }
        with pytest.raises(MockValidationError, match="無效的scrape_mode值"):
            validate_task_data_api(data, task_service)

def test_validate_task_data_api_with_integer_scrape_mode(task_service):
    """測試使用整數作為scrape_mode值"""
    with patch('src.utils.validators.ValidationError', MockValidationError):
        data = {
            'crawler_id': 1,
            'task_name': 'test_task',
            'task_args': {
                'scrape_mode': 123  # 整數不是有效的scrape_mode類型
            },
            'is_auto': False,
            'ai_only': False,
            'max_retries': 3,
            'retry_count': 0,
            'current_phase': TaskPhase.INIT,
            'scrape_mode': ScrapeMode.FULL_SCRAPE  # 在根層級添加有效值
        }
        with pytest.raises(MockValidationError, match="無效的抓取模式"):
            validate_task_data_api(data, task_service)

def test_validate_task_data_api_with_valid_scrape_mode_string(task_service):
    """測試使用有效的字符串作為scrape_mode值"""
    # 查看ScrapeMode枚舉對象的值
    print(f"枚舉值: {ScrapeMode.FULL_SCRAPE.value}")
    
    # 使用正確的枚舉值格式
    data = {
        'crawler_id': 1,
        'task_name': 'test_task',
        'task_args': {
            'scrape_mode': ScrapeMode.FULL_SCRAPE.value  # 使用枚舉的實際值
        },
        'is_auto': False,
        'ai_only': False,
        'max_retries': 3,
        'retry_count': 0,
        'current_phase': TaskPhase.INIT,
        'scrape_mode': ScrapeMode.FULL_SCRAPE  # 在根層級添加
    }
    validated_data = validate_task_data_api(data, task_service)
    assert validated_data['task_args']['scrape_mode'] == ScrapeMode.FULL_SCRAPE.value