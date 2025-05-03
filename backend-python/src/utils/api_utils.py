"""提供 API 請求處理相關的工具函數，例如解析通用查詢參數。"""

import logging
from typing import Dict, Any, Optional, List, Tuple

from werkzeug.datastructures import MultiDict



logger = logging.getLogger(__name__)  # 使用統一的 logger

# 定義標準的查詢參數鍵
STANDARD_KEYS = {
    'page', 'per_page', 'limit', 'offset',
    'sort_by', 'sort_desc',
    'is_preview', 'preview_fields',
    'q',  # 通用搜尋關鍵字 'q'
}

def parse_and_validate_common_query_params(args: MultiDict) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    解析和驗證通用的查詢參數 (分頁, 排序, 預覽, 關鍵字 q)。

    Args:
        args: Flask request.args (MultiDict)

    Returns:
        一個元組包含兩個字典:
        1. validated_params: 包含已驗證的標準參數 (page, per_page, limit, etc.) 的字典。
        2. filter_criteria: 包含所有非標準參數的字典，用作過濾條件。

    Raises:
        ValueError: 如果任何參數驗證失敗。
    """
    validated_params: Dict[str, Any] = {}
    filter_criteria: Dict[str, Any] = {}

    # --- 處理分頁參數 ---
    page_str = args.get('page', '1')
    per_page_str = args.get('per_page', '10')
    limit_str = args.get('limit')
    offset_str = args.get('offset')

    try:
        page = int(page_str)
        if page <= 0:
            raise ValueError("page 必須是正整數")
        validated_params['page'] = page

        per_page = int(per_page_str)
        if per_page <= 0:
            raise ValueError("per_page 必須是正整數")
        validated_params['per_page'] = per_page

        limit = None
        if limit_str is not None:
            limit = int(limit_str)
            if limit < 0:
                raise ValueError("limit 必須是非負整數")
        validated_params['limit'] = limit # 若未提供則為 None

        offset = None
        if offset_str is not None:
            offset = int(offset_str)
            if offset < 0:
                raise ValueError("offset 必須是非負整數")
        validated_params['offset'] = offset # 若未提供則為 None

    except ValueError as e:
        logger.warning(
            "分頁參數轉換錯誤: page=%s, per_page=%s, limit=%s, offset=%s - %s",
            page_str, per_page_str, limit_str, offset_str, e
        )
        # 重新拋出 ValueError，讓 API 路由處理
        raise ValueError(f"請求參數錯誤: {e}") from e

    # --- 處理排序參數 ---
    validated_params['sort_by'] = args.get('sort_by') # 由 Repository 處理驗證
    sort_desc_str = args.get('sort_desc', 'false').lower()
    validated_params['sort_desc'] = sort_desc_str in ['true', '1', 'yes']

    # --- 處理預覽參數 ---
    is_preview_str = args.get('is_preview', 'false').lower()
    validated_params['is_preview'] = is_preview_str in ['true', '1', 'yes']
    preview_fields_str = args.get('preview_fields')
    validated_params['preview_fields'] = preview_fields_str.split(',') if preview_fields_str else None

    # --- 處理通用搜尋關鍵字 'q' ---
    validated_params['q'] = args.get('q') # 由具體的 API 端點驗證

    # --- 收集剩餘參數作為過濾條件 ---
    for key, value in args.items():
        if key not in STANDARD_KEYS:
            # 注意: request.args 對於同名參數可能有多個值，這裡只取第一個
            filter_criteria[key] = value

    return validated_params, filter_criteria
