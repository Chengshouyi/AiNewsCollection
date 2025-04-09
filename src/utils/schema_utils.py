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
