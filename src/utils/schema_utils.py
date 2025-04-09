from typing import Dict, Any, List, Optional
from src.error.errors import ValidationError


def validate_update_schema(immutable_fields: list, update_fields: list, data: dict):
    """驗證更新操作"""
    if isinstance(data, dict):
        for field in immutable_fields:
            if field in data:
                raise ValidationError(f"不允許更新 {field} 欄位")

        updated_fields = [
            field for field in data.keys()
            if field not in immutable_fields and field in update_fields
        ]
        if not updated_fields:
            raise ValidationError("必須提供至少一個要更新的欄位")
    return data

def validate_required_fields_schema(required_fields: List[str], data: Dict[str, Any]) -> Dict[str, Any]:
    """
    驗證必填欄位
    
    Args:
        required_fields: 必填欄位列表
        data: 待驗證資料
        
    Returns:
        驗證後的資料
    """
    for field in required_fields:
        if field not in data or data[field] is None or (isinstance(data[field], str) and data[field].strip() == ""):
            raise ValidationError(f"{field}: 不能為空")
    return data

def validate_crawler_config(data: Dict[str, Any], is_update: bool = False) -> List[str]:
    """
    驗證爬蟲配置
    
    Args:
        data: 爬蟲配置資料
        is_update: 是否為更新操作
        
    Returns:
        錯誤訊息列表，如果沒有錯誤則為空列表
    """
    errors = []
    
    # 檢查必填欄位
    required_fields = ['crawler_name', 'base_url', 'crawler_type', 'config_file_name']
    if not is_update:  # 創建時所有字段都是必須的
        for field in required_fields:
            if field not in data or not data[field]:
                errors.append(f"{field} 是必填欄位")
    
    # 檢查 crawler_name 長度
    if 'crawler_name' in data and data['crawler_name']:
        if len(data['crawler_name']) > 100:
            errors.append("crawler_name 長度不能超過 100 字元")
    
    # 檢查 base_url 格式和長度
    if 'base_url' in data and data['base_url']:
        if len(data['base_url']) > 1000:
            errors.append("base_url 長度不能超過 1000 字元")
        # 簡單檢查 URL 格式
        if not data['base_url'].startswith(('http://', 'https://')):
            errors.append("base_url 必須是有效的 URL")
    
    # 檢查 crawler_type 長度
    if 'crawler_type' in data and data['crawler_type']:
        if len(data['crawler_type']) > 100:
            errors.append("crawler_type 長度不能超過 100 字元")
    
    # 檢查 config_file_name 長度
    if 'config_file_name' in data and data['config_file_name']:
        if len(data['config_file_name']) > 100:
            errors.append("config_file_name 長度不能超過 100 字元")
    
    # 檢查 is_active 是否為布爾值
    if 'is_active' in data and data['is_active'] is not None:
        if not isinstance(data['is_active'], bool):
            errors.append("is_active 必須是布爾值")
    
    return errors