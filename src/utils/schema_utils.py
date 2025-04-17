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
    驗證必填欄位，收集所有缺失或無效的欄位並在單一錯誤中報告。
    
    Args:
        required_fields: 必填欄位列表
        data: 待驗證資料
        
    Returns:
        驗證後的資料
        
    Raises:
        ValidationError: 如果任何必填欄位缺失或值為空/空白。
    """
    missing_or_empty_fields = []
    for field in required_fields:
        field_value = data.get(field) # 使用 get 避免 KeyError
        if field_value is None or (isinstance(field_value, str) and not field_value.strip()):
            missing_or_empty_fields.append(field)
            
    if missing_or_empty_fields:
        # 構造包含所有缺失/無效欄位的錯誤訊息
        error_message = f"以下必填欄位缺失或值為空/空白: {', '.join(missing_or_empty_fields)}"
        raise ValidationError(error_message)
        
    return data
