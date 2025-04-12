import pytest
from src.utils.api_validators import validate_task_data_api, validate_crawler_data_api, is_valid_cron_expression
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
    with patch('src.utils.api_validators.ValidationError', MockValidationError):
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
    with patch('src.utils.api_validators.ValidationError', MockValidationError):
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
    with patch('src.utils.api_validators.ValidationError', MockValidationError):
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
    with patch('src.utils.api_validators.ValidationError', MockValidationError):
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
    with patch('src.utils.api_validators.ValidationError', MockValidationError):
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


# --- Additional tests for validate_task_data_api ---

def test_validate_task_data_api_create_adds_default_retries(task_service):
    """測試創建模式下自動添加預設重試次數"""
    data = {
        'crawler_id': 1,
        'task_name': 'test_task_defaults',
        'task_args': {},
        'ai_only': False,
        'current_phase': TaskPhase.INIT,
        'scrape_mode': ScrapeMode.FULL_SCRAPE
        # 'max_retries', 'retry_count' are missing
    }
    validated_data = validate_task_data_api(data, task_service, is_update=False)
    # 驗證器本身會添加預設值
    assert 'max_retries' in data
    assert data['max_retries'] == 3 # Check if default is added to original data
    assert 'retry_count' in data
    assert data['retry_count'] == 0 # Check if default is added to original data
    # 底層驗證後應該也存在
    assert 'max_retries' in validated_data
    assert validated_data['max_retries'] == 3
    assert 'retry_count' in validated_data
    assert validated_data['retry_count'] == 0


@pytest.mark.parametrize("param, value, error_msg_part", [
    ("max_pages", 0, "max_pages: max_pages: 必須是正整數且大於0"),
    ("num_articles", -1, "num_articles: num_articles: 必須是正整數且大於0"),
    ("min_keywords", "abc", "min_keywords: min_keywords: 必須是整數"),
    ("timeout", -5, "timeout: timeout: 必須是正整數且大於0"),
])
def test_validate_task_data_api_task_args_invalid_positive_int(task_service, param, value, error_msg_part):
    """測試 task_args 中無效的正整數參數"""
    data = {
        'crawler_id': 1, 'task_name': 'test_task', 'scrape_mode': ScrapeMode.FULL_SCRAPE,
        'task_args': {param: value}
    }
    with pytest.raises(ValidationError, match=error_msg_part):
         validate_task_data_api(data, task_service)

@pytest.mark.parametrize("param, value, error_msg_part", [
    ("retry_delay", 0, "'retry_delay' 必須是正數"),
    ("retry_delay", -1.5, "'retry_delay' 必須是正數"),
    ("retry_delay", "abc", "'retry_delay' 必須是正數"), # Also checks type
])
def test_validate_task_data_api_task_args_invalid_positive_float(task_service, param, value, error_msg_part):
    """測試 task_args 中無效的正數 (float/int) 參數"""
    data = {
        'crawler_id': 1, 'task_name': 'test_task', 'scrape_mode': ScrapeMode.FULL_SCRAPE,
        'task_args': {param: value}
    }
    with pytest.raises(ValidationError, match=error_msg_part):
         validate_task_data_api(data, task_service)

@pytest.mark.parametrize("param, value, error_msg_part", [
    # Remove the case for 'true' as it's considered valid by validate_boolean
    # ("ai_only", "true", "ai_only: 必須是布爾值"),
    ("save_to_csv", 1, "save_to_csv: 必須是布爾值"),
    ("save_to_database", 0, "save_to_database: 必須是布爾值"),
    # Remove the case for None as it's considered valid (not required) by validate_boolean
    # ("get_links_by_task_id", None, "get_links_by_task_id: 必須是布爾值"),
])
def test_validate_task_data_api_task_args_invalid_boolean(task_service, param, value, error_msg_part):
    """測試 task_args 中無效的布爾參數"""
    data = {
        'crawler_id': 1, 'task_name': 'test_task', 'scrape_mode': ScrapeMode.FULL_SCRAPE,
        'task_args': {param: value},
        # Add required top-level fields to pass schema validation first
        'ai_only': False, # Default valid value for top-level field
        'current_phase': TaskPhase.INIT,
        'max_retries': 3,
        'retry_count': 0
    }
    # Adjust top-level ai_only if it's the param being tested in task_args,
    # ensuring the top-level one is valid.
    if param == 'ai_only':
        data['ai_only'] = False

    # The error message format is f"{param}: {original_error}"
    # original_error format is f"{param}: message"
    expected_error_regex = f"{param}: {error_msg_part}" # error_msg_part already includes the inner param name
    with pytest.raises(ValidationError, match=expected_error_regex):
         validate_task_data_api(data, task_service)


def test_validate_task_data_api_content_only_missing_ids_or_links(task_service):
    """測試 CONTENT_ONLY 模式, get_links_by_task_id=False 但缺少 article_ids/links"""
    data = {
        'crawler_id': 1, 'task_name': 'test_task', 'scrape_mode': ScrapeMode.CONTENT_ONLY,
        'task_args': {
            'scrape_mode': ScrapeMode.CONTENT_ONLY.value,
            'get_links_by_task_id': False
            # Missing 'article_ids' and 'article_links'
        }
    }
    error_msg = "內容抓取模式且不從任務ID獲取連結時，必須提供 'article_ids' 或 'article_links'"
    with pytest.raises(ValidationError, match=error_msg):
         validate_task_data_api(data, task_service)

@pytest.mark.parametrize("param, value, error_msg_part", [
    # Ensure error_msg_part matches the wrapped error: f"{param}: {original_message}"
    ("article_ids", "not_a_list", "article_ids: 必須是列表"),
    ("article_links", {"a": 1}, "article_links: 必須是列表"),
])
def test_validate_task_data_api_content_only_invalid_list_type(task_service, param, value, error_msg_part):
    """測試 CONTENT_ONLY 模式, get_links_by_task_id=False 且 article_ids/links 類型錯誤"""
    task_args = {
        'scrape_mode': ScrapeMode.CONTENT_ONLY.value,
        'get_links_by_task_id': False,
        param: value
    }
    # Ensure the other list parameter is present if needed to avoid the "missing" error
    if param == "article_ids":
        task_args['article_links'] = []
    else:
        task_args['article_ids'] = []

    data = {
        'crawler_id': 1, 'task_name': 'test_task', 'scrape_mode': ScrapeMode.CONTENT_ONLY,
        'task_args': task_args,
        # Add required top-level fields
        'ai_only': False,
        'current_phase': TaskPhase.INIT,
        'max_retries': 3,
        'retry_count': 0
    }
    # Expected regex is f"{param}: {error_msg_part}"
    # Actual error is f"{param}: {param}: {original_message}"
    # So error_msg_part should be f"{param}: {original_message}"
    expected_error_regex = f"{param}: {error_msg_part}"
    with pytest.raises(ValidationError, match=expected_error_regex):
         validate_task_data_api(data, task_service)