from typing import Dict, Any, List
from src.error.errors import ValidationError
from src.utils.schema_utils import validate_required_fields_schema
from src.utils.model_utils import validate_cron_expression, validate_dict, validate_boolean, validate_str, validate_url


def validate_task_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    驗證任務資料
    
    Args:
        data: 任務資料
        
    Returns:
        驗證後的資料
        
    Raises:
        ValidationError: 當驗證失敗時
    """
    # 檢查必填欄位
    required_fields = ['crawler_id', 'task_name', 'task_args', 'ai_only']
    validate_required_fields_schema(required_fields, data)
    
    # 檢查任務名稱長度
    validate_str('task_name', max_length=255)(data['task_name'])
    
    # 檢查是否為自動執行
    if 'is_auto' in data:
        validate_boolean('is_auto', required=True)(data['is_auto'])
        if data['is_auto'] and 'cron_expression' not in data:
            raise ValidationError("當設定為自動執行時，cron_expression 不能為空")
    
    # 檢查是否只爬取 AI 相關文章
    validate_boolean('ai_only', required=True)(data['ai_only'])
    
    # 檢查 cron 表達式（如果有）
    if 'cron_expression' in data:
        validate_cron_expression('cron_expression', max_length=255, min_length=5)(data['cron_expression'])
    
    # 檢查任務參數
    validate_dict('task_args', required=True)(data.get('task_args', {}))
    
    # 檢查備註（如果有）
    if 'notes' in data:
        validate_str('notes', max_length=65536, required=False)(data['notes'])
    
    # 檢查上次執行訊息（如果有）
    if 'last_run_message' in data:
        validate_str('last_run_message', max_length=65536, required=False)(data['last_run_message'])
    
    # 檢查任務狀態（如果有）
    if 'status' in data:
        valid_statuses = ['pending', 'running', 'completed', 'failed', 'cancelled']
        if data['status'] not in valid_statuses:
            raise ValidationError(f"無效的任務狀態，必須是以下之一：{', '.join(valid_statuses)}")
    
    return data 

def validate_crawler_data(data: Dict[str, Any], is_update: bool = False) -> Dict[str, Any]:
    """
    驗證爬蟲配置資料
    
    Args:
        data: 爬蟲配置資料
        is_update: 是否為更新操作
        
    Returns:
        驗證後的資料
        
    Raises:
        ValidationError: 當驗證失敗時
    """
    # 檢查必填欄位
    required_fields = ['crawler_name', 'base_url', 'crawler_type', 'config_file_name']
    if not is_update:
        validate_required_fields_schema(required_fields, data)
    
    # 檢查爬蟲名稱
    if 'crawler_name' in data:
        validate_str('crawler_name', max_length=100, required=not is_update)(data['crawler_name'])
    
    # 檢查基礎 URL
    if 'base_url' in data:
        validate_url('base_url', max_length=1000, required=not is_update)(data['base_url'])
    
    # 檢查爬蟲類型
    if 'crawler_type' in data:
        validate_str('crawler_type', max_length=100, required=not is_update)(data['crawler_type'])
        
    # 檢查配置文件名稱
    if 'config_file_name' in data:
        validate_str('config_file_name', max_length=100, required=not is_update)(data['config_file_name'])
    
    # 檢查是否啟用狀態
    if 'is_active' in data:
        validate_boolean('is_active', required=False)(data['is_active'])
    elif not is_update:
        # 設置默認值
        data['is_active'] = True
    
    return data

    
