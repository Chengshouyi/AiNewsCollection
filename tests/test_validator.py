import pytest
from src.utils.validators import validate_task_data
from src.error.errors import ValidationError

def test_validate_task_data_with_valid_minimal_data():
    """測試最小化的有效任務資料"""
    data = {
        'crawler_id': 1,
        'task_name': 'test_task',
        'task_args': {},
        'ai_only': False
    }
    validated_data = validate_task_data(data)
    assert validated_data == data

def test_validate_task_data_with_complete_valid_data():
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
    validated_data = validate_task_data(data)
    assert validated_data == data

def test_validate_task_data_auto_without_cron():
    """測試自動執行但未提供 cron 表達式"""
    data = {
        'crawler_id': 1,
        'task_name': 'test_task',
        'task_args': {},
        'is_auto': True,
        'ai_only': False
    }
    with pytest.raises(ValidationError, match="當設定為自動執行時，cron_expression 不能為空"):
        validate_task_data(data)

def test_validate_task_data_with_invalid_task_name_length():
    """測試任務名稱超過長度限制"""
    data = {
        'crawler_id': 1,
        'task_name': 'x' * 256,
        'task_args': {},
        'ai_only': False
    }
    with pytest.raises(ValidationError):
        validate_task_data(data)

def test_validate_task_data_with_invalid_notes_length():
    """測試備註超過長度限制"""
    data = {
        'crawler_id': 1,
        'task_name': 'test_task',
        'task_args': {},
        'ai_only': False,
        'notes': 'x' * 65537
    }
    with pytest.raises(ValidationError):
        validate_task_data(data)

def test_validate_task_data_missing_required_fields():
    """測試缺少必填欄位"""
    data = {
        'task_name': 'test_task'
    }
    with pytest.raises(ValidationError):
        validate_task_data(data)

def test_validate_task_data_invalid_task_name_length():
    """測試任務名稱超過長度限制"""
    data = {
        'crawler_id': 'test_crawler',
        'task_name': 'x' * 101  # 超過100字元
    }
    with pytest.raises(ValidationError):
        validate_task_data(data)

def test_validate_task_data_invalid_cron_expression():
    """測試無效的 cron 表達式"""
    data = {
        'crawler_id': 'test_crawler',
        'task_name': 'test_task',
        'cron_expression': 'invalid_cron',
        'is_scheduled': True
    }
    with pytest.raises(ValidationError):
        validate_task_data(data)

def test_validate_task_data_scheduled_without_cron():
    """測試排程任務但未提供 cron 表達式"""
    data = {
        'crawler_id': 'test_crawler',
        'task_name': 'test_task',
        'is_scheduled': True
    }
    with pytest.raises(ValidationError):
        validate_task_data(data)

def test_validate_task_data_invalid_status():
    """測試無效的任務狀態"""
    data = {
        'crawler_id': 'test_crawler',
        'task_name': 'test_task',
        'status': 'invalid_status'
    }
    with pytest.raises(ValidationError):
        validate_task_data(data)

def test_validate_task_data_invalid_task_args():
    """測試無效的任務參數"""
    data = {
        'crawler_id': 'test_crawler',
        'task_name': 'test_task',
        'task_args': 'not_a_dict'  # 應該是字典類型
    }
    with pytest.raises(ValidationError):
        validate_task_data(data)
