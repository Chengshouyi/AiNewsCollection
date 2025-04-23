from typing import Dict, Any, Optional
import logging
from sqlalchemy.orm.attributes import flag_modified
# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def deep_update_dict_field(current_value: Optional[Dict[str, Any]], 
                           new_value: Dict[str, Any], 
                           field_name: str = "unknown") -> Dict[str, Any]:
    """
    深度更新字典欄位，適合在 _update_internal 中使用
    
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
        更新後的字典
    """
    # 如果當前值為 None 或不是字典，直接返回新值的副本
    if current_value is None:
        logger.debug(f"欄位 '{field_name}' 當前值為 None，直接替換為新值")
        return new_value.copy()
    
    if not isinstance(current_value, dict):
        logger.warning(f"欄位 '{field_name}' 當前值不是字典，直接替換為新值")
        return new_value.copy()
    
    # 創建當前值的深複製，以避免修改原始對象
    result = current_value.copy()
    changes_made = False
    
    # 遍歷新值字典
    for key, value in new_value.items():
        # 如果鍵不存在於當前字典中，直接添加
        if key not in result:
            result[key] = value
            changes_made = True
            logger.debug(f"欄位 '{field_name}' 添加新鍵 '{key}' = {value}")
            continue
        
        # 比較值
        current_key_value = result[key]
        
        # 如果兩邊都是字典，則遞迴更新
        if isinstance(value, dict) and isinstance(current_key_value, dict):
            updated_nested_dict = deep_update_dict_field(current_key_value, value, f"{field_name}.{key}")
            if updated_nested_dict != current_key_value:
                result[key] = updated_nested_dict
                changes_made = True
        # 否則，直接比較值
        elif current_key_value != value:
            result[key] = value
            changes_made = True
            logger.debug(f"欄位 '{field_name}' 更新鍵 '{key}' 從 {current_key_value} 到 {value}")
    
    if not changes_made:
        logger.debug(f"欄位 '{field_name}' 無變更")
        
    return result

def update_dict_field(entity: Any, field_name: str, new_value: Dict[str, Any]) -> bool:
    """
    更新實體上的字典欄位，並返回是否有變更
    
    適合直接在 _update_internal 中使用：
    ```python
    if isinstance(value, dict) and hasattr(entity, key):
        has_field_changes = update_dict_field(entity, key, value)
        has_changes = has_changes or has_field_changes
        continue  # 跳過後面的處理
    ```
    
    Args:
        entity: 要更新的實體
        field_name: 字典欄位的名稱
        new_value: 新的字典值
        
    Returns:
        bool: 是否有變更
    """
    if not hasattr(entity, field_name):
        logger.warning(f"實體上沒有欄位 '{field_name}'")
        return False
    
    current_value = getattr(entity, field_name)
    updated_value = deep_update_dict_field(current_value, new_value, field_name)

    print(f"--- update_dict_field ({field_name}) ---")
    print(f"Current Value: {current_value}")
    print(f"New Value (payload): {new_value}")
    print(f"Updated Value (calculated): {updated_value}")
    are_equal = current_value == updated_value
    print(f"Are Equal: {are_equal}")

    # 檢查是否有變更
    if are_equal:
         print("Values are equal, no changes made.")
         return False

    # 更新實體的字典欄位
    print("Setting attribute...")
    setattr(entity, field_name, updated_value)
    print("Flagging modified...")
    flag_modified(entity, field_name)
    print("--- update_dict_field finished ---")
    return True

def _apply_deep_changes_inplace(target_dict: Dict[str, Any],
                                     source_changes: Dict[str, Any],
                                     field_path: str) -> bool:
    """遞迴地將 source_changes 的變更應用到 target_dict (原地修改)"""
    made_changes = False
    for key, value in source_changes.items():
        current_path = f"{field_path}.{key}"
        print(f"current_path: {current_path}")
        if key not in target_dict:
            print(f"key not in target_dict: {key}")
            target_dict[key] = value
            made_changes = True
            logger.debug(f"欄位 '{current_path}' 添加新值: {value}")
        elif isinstance(value, dict) and isinstance(target_dict.get(key), dict):
            print(f"value is dict and target_dict[key] is dict: {value} and {target_dict.get(key)}")
            # 遞迴處理巢狀字典
            nested_changed = _apply_deep_changes_inplace(target_dict[key], value, current_path)
            if nested_changed:
                made_changes = True
        elif target_dict.get(key) != value:
            print(f"target_dict.get(key) != value: {target_dict.get(key)} and {value}")
            target_dict[key] = value
            made_changes = True
            logger.debug(f"欄位 '{current_path}' 值從 {target_dict.get(key)} 更新為: {value}")
    return made_changes

def update_dict_field_inplace(entity: Any, field_name: str, changes_payload: Dict[str, Any]) -> bool:
    """
    更新實體上的字典欄位 (原地修改)，並返回是否有變更。
    如果字典欄位不存在或不是字典，會嘗試初始化。
    """
    if not hasattr(entity, field_name):
        logger.warning(f"實體上沒有欄位 '{field_name}'")
        return False

    current_dict = getattr(entity, field_name)

    # 如果當前值是 None 或不是字典，嘗試創建一個新的字典
    # 注意：這依賴於模型有預設值或者這個欄位允許從 None 開始
    if not isinstance(current_dict, dict):
         logger.warning(f"欄位 '{field_name}' 的當前值不是字典或為 None (值: {current_dict})，將創建新字典。")
         current_dict = {}
         setattr(entity, field_name, current_dict) # 賦予一個新的空字典

    # 應用變更到 current_dict (原地修改)
    made_changes = _apply_deep_changes_inplace(current_dict, changes_payload, field_name)

    if made_changes:
        logger.info(f"欄位 '{field_name}' 內容已修改 (in-place)。標記為 modified。")
        flag_modified(entity, field_name) # 標記變更

    return made_changes
