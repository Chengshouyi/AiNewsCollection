from typing import Dict, Any, List
from src.error.errors import ValidationError
from src.utils.schema_utils import validate_required_fields_schema, validate_crawler_config

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
    required_fields = ['crawler_id', 'task_name']
    validate_required_fields_schema(required_fields, data)
    
    # 檢查任務名稱長度
    if len(data['task_name']) > 100:
        raise ValidationError("任務名稱長度不能超過 100 字元")
    
    # 檢查 cron 表達式（如果有）
    if 'cron_expression' in data:
        if not isinstance(data['cron_expression'], str):
            raise ValidationError("cron_expression 必須是字串")
        if len(data['cron_expression']) > 100:
            raise ValidationError("cron_expression 長度不能超過 100 字元")
    
    # 檢查任務參數（如果有）
    if 'task_args' in data:
        if not isinstance(data['task_args'], dict):
            raise ValidationError("task_args 必須是字典")
    
    # 檢查是否為排程任務
    if 'is_scheduled' in data:
        if not isinstance(data['is_scheduled'], bool):
            raise ValidationError("is_scheduled 必須是布爾值")
        if data['is_scheduled'] and 'cron_expression' not in data:
            raise ValidationError("排程任務必須提供 cron_expression")
    
    # 檢查任務狀態（如果有）
    if 'status' in data:
        valid_statuses = ['pending', 'running', 'completed', 'failed', 'cancelled']
        if data['status'] not in valid_statuses:
            raise ValidationError(f"無效的任務狀態，必須是以下之一：{', '.join(valid_statuses)}")
    
    return data 