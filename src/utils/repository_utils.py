"""提供用於處理 SQLAlchemy 實體中字典欄位的輔助函數。"""

# Standard library
import logging
from typing import Dict, Any, Optional

# Third-party libraries
from sqlalchemy.orm.attributes import flag_modified

# Local application imports


# Setup logger
logger = logging.getLogger(__name__)  # 使用統一的 logger # pylint: disable=invalid-name

def deep_update_dict_field(current_value: Optional[Dict[str, Any]], 
                           new_value: Dict[str, Any], 
                           field_name: str = "unknown") -> Dict[str, Any]:
    """
    深度更新字典欄位。

    此函數會遞迴比較兩個字典，並應用以下規則：
    1. 如果 current_value 為 None，直接返回 new_value 的副本
    2. 如果 new_value 中的某個鍵不存在於 current_value，則將其添加
    3. 如果 new_value 中的值是字典且 current_value 中相應的值也是字典，則遞迴進行比較和更新
    4. 如果 new_value 中的值與 current_value 中相應的值不同，則更新為 new_value 的值
    
    Args:
        current_value: 目前實體中的字典值
        new_value: 要更新的新字典值
        field_name: 欄位名稱（用於日誌記錄）
        
    Returns:
        更新後的字典 (一個新的字典實例)
    """
    if current_value is None:
        logger.debug("欄位 '%s' 當前值為 None，直接替換為新值", field_name)
        return new_value.copy()
    
    if not isinstance(current_value, dict):
        logger.warning("欄位 '%s' 當前值不是字典，直接替換為新值", field_name)
        return new_value.copy()
    
    result = current_value.copy() # 創建副本以避免修改原始對象
    changes_made = False
    
    for key, value in new_value.items():
        if key not in result:
            result[key] = value
            changes_made = True
            logger.debug("欄位 '%s' 添加新鍵 '%s' = %s", field_name, key, value)
            continue
        
        current_key_value = result[key]
        
        if isinstance(value, dict) and isinstance(current_key_value, dict):
            updated_nested_dict = deep_update_dict_field(current_key_value, value, f"{field_name}.{key}")
            if updated_nested_dict != current_key_value:
                result[key] = updated_nested_dict
                changes_made = True
        elif current_key_value != value:
            result[key] = value
            changes_made = True
            logger.debug("欄位 '%s' 更新鍵 '%s' 從 %s 到 %s", field_name, key, current_key_value, value)
    
    if not changes_made:
        logger.debug("欄位 '%s' 無變更", field_name)
        
    return result

def update_dict_field(entity: Any, field_name: str, new_value: Dict[str, Any]) -> bool:
    """
    (已棄用 - 請使用 update_dict_field_inplace) 更新實體上的字典欄位，返回是否有變更。

    此方法創建一個新的字典副本，而不是原地修改。
    
    Args:
        entity: 要更新的實體
        field_name: 字典欄位的名稱
        new_value: 新的字典值
        
    Returns:
        bool: 是否有變更
    """
    logger.warning("函數 'update_dict_field' 已棄用，請考慮使用 'update_dict_field_inplace' 進行原地更新。")
    if not hasattr(entity, field_name):
        logger.warning("實體上沒有欄位 '%s'", field_name)
        return False
    
    current_value = getattr(entity, field_name)
    updated_value = deep_update_dict_field(current_value, new_value, field_name)

    are_equal = current_value == updated_value
    logger.debug("欄位 '%s' 比較結果: Current=%s, Updated=%s, Equal=%s", 
                 field_name, current_value, updated_value, are_equal)

    if are_equal:
         return False

    setattr(entity, field_name, updated_value)
    flag_modified(entity, field_name)
    logger.info("欄位 '%s' 已更新並標記為 modified。", field_name)
    return True

def _apply_deep_changes_inplace(target_dict: Dict[str, Any],
                                     source_changes: Dict[str, Any],
                                     field_path: str) -> bool:
    """遞迴地將 source_changes 的變更應用到 target_dict (原地修改)"""
    made_changes = False
    for key, value in source_changes.items():
        current_path = f"{field_path}.{key}"
        target_value = target_dict.get(key) # 使用 get 避免 KeyErrors

        if key not in target_dict:
            target_dict[key] = value
            made_changes = True
            logger.debug("欄位 '%s' 添加新值: %s", current_path, value)
        elif isinstance(value, dict) and isinstance(target_value, dict):
            # 遞迴處理巢狀字典
            nested_changed = _apply_deep_changes_inplace(target_value, value, current_path)
            if nested_changed:
                made_changes = True
        elif target_value != value:
            target_dict[key] = value
            made_changes = True
            logger.debug("欄位 '%s' 值從 %s 更新為: %s", current_path, target_value, value)
    return made_changes

def update_dict_field_inplace(entity: Any, field_name: str, changes_payload: Dict[str, Any]) -> bool:
    """
    更新實體上的字典欄位 (原地修改)，並返回是否有變更。
    如果字典欄位不存在或不是字典，會嘗試初始化。
    這是推薦的更新字典欄位的方法。
    """
    if not hasattr(entity, field_name):
        logger.warning("實體上沒有欄位 '%s'", field_name)
        return False

    current_dict = getattr(entity, field_name)

    # 如果當前值是 None 或不是字典，創建一個新的空字典
    if not isinstance(current_dict, dict):
         logger.info("欄位 '%s' 的當前值不是字典或為 None (值: %s)，將創建新字典。", field_name, current_dict)
         current_dict = {}
         setattr(entity, field_name, current_dict) # 賦予一個新的空字典
         # 即使創建了新字典，也需要應用 changes_payload，因此 flag_modified 移至下方

    # 應用變更到 current_dict (原地修改)
    made_changes = _apply_deep_changes_inplace(current_dict, changes_payload, field_name)

    if made_changes:
        logger.info("欄位 '%s' 內容已修改 (in-place)。標記為 modified。", field_name)
        flag_modified(entity, field_name) # 標記變更

    return made_changes
