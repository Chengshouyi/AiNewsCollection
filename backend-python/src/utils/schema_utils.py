"""提供資料架構驗證相關的工具函式。"""

import logging
from typing import Dict, Any, List, Optional


from src.error.errors import ValidationError


# 設定 logger
logger = logging.getLogger(__name__)  # 使用統一的 logger

def validate_update_schema(immutable_fields: list, update_fields: list, data: dict):
    """驗證更新操作，檢查是否包含不可變欄位及至少一個可更新欄位。"""
    if isinstance(data, dict):
        for field in immutable_fields:
            if field in data:
                logger.warning(f"嘗試更新不可變欄位: {field}") # 加入log紀錄
                raise ValidationError(f"不允許更新 {field} 欄位")

        updated_fields = [
            field for field in data.keys()
            if field not in immutable_fields and field in update_fields
        ]
        if not updated_fields:
            logger.warning("更新請求未包含任何有效的可更新欄位。 Data: %s", data) # 加入log紀錄
            raise ValidationError("必須提供至少一個要更新的欄位")
    return data

def validate_required_fields_schema(required_fields: List[str], data: Dict[str, Any]) -> Dict[str, Any]:
    """
    驗證必填欄位，收集所有缺失或值為空/空白的欄位並在單一錯誤中報告。
    
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
        logger.warning("必填欄位驗證失敗: %s. Data: %s", error_message, data) # 加入log紀錄
        raise ValidationError(error_message)
        
    return data
