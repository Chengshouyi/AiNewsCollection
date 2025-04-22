# 文章路由
from flask import Blueprint, jsonify, request
from src.services.article_service import ArticleService
from src.services.service_container import get_article_service
from src.error.handle_api_error import handle_api_error
from src.models.articles_schema import ArticleReadSchema, PaginatedArticleResponse
from src.utils.api_utils import parse_and_validate_common_query_params
from typing import Optional, List, Dict, Any, Union, cast
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 創建藍圖
article_bp = Blueprint('article_api', __name__, url_prefix='/api/articles')

@article_bp.route('', methods=['GET'])
def get_articles():
    """取得文章列表 (支援分頁/篩選/排序)"""
    try:
        # --- 使用工具函數解析和驗證參數 ---
        validated_params, filter_criteria = parse_and_validate_common_query_params(request.args)
        # --- 結束參數處理 ---

        service: ArticleService = get_article_service()

        result = service.find_articles_paginated(
            page=validated_params['page'],
            per_page=validated_params['per_page'],
            filter_criteria=filter_criteria if filter_criteria else None, # 只有在非空時傳遞
            sort_by=validated_params['sort_by'],
            sort_desc=validated_params['sort_desc'],
            is_preview=validated_params['is_preview'],
            preview_fields=validated_params['preview_fields']
        )

        if not result.get('success'):
            # Service 層返回 False，可能是內部錯誤或驗證問題
            status_code = 500 # 預設為內部錯誤
            # 可以根據 message 細化錯誤碼，但 find_articles_paginated 通常是 500
            return jsonify(result), status_code

        paginated_response: Optional[PaginatedArticleResponse] = result.get('resultMsg')

        if paginated_response is None:
             # 成功但沒有 resultMsg，這不應該發生
             logger.error("find_articles_paginated 成功但未返回 resultMsg")
             return jsonify({"success": False, "message": "無法獲取分頁文章資料"}), 500

        # 將 PaginatedArticleResponse 轉換為字典以供 JSON 序列化
        # 注意: paginated_response.items 已經是 Schema 或 dict 了，取決於 is_preview
        # Pydantic v2 的 model_dump 會處理內部的 Schema 轉換
        response_data = paginated_response.model_dump(mode='json')

        # 即使 items 為空，也算成功獲取
        return jsonify({
            "success": True,
            "message": result.get('message', '獲取文章列表成功'),
            "data": response_data
        }), 200

    except ValueError as ve: # <-- 捕獲來自工具函數的 ValueError
        # 工具函數已記錄詳細錯誤，這裡直接返回 400
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        return handle_api_error(e)

@article_bp.route('/<int:article_id>', methods=['GET'])
def get_article(article_id):
    """取得單篇文章詳情"""
    try:
        service: ArticleService = get_article_service()
        result = service.get_article_by_id(article_id)

        if not result.get('success'):
            # Service 返回 False 通常是因為找不到
            status_code = 404 if "不存在" in result.get('message', '') else 500
            return jsonify(result), status_code

        article_schema: Optional[ArticleReadSchema] = result.get('article')
        if article_schema is None:
            # 成功但沒有 article，理論上不會發生在 get_by_id 成功時
            logger.warning(f"get_article_by_id 成功但未返回 article 物件 (ID: {article_id})")
            # 保持與 Service 層一致，如果 service 說成功，這裡也該成功，只是 data 為 null
            # 但若 service 說成功，article 卻是 None，更可能是內部邏輯問題
            return jsonify({"success": False, "message": "成功獲取但找不到文章資料"}), 404 # 或者 500

        # 將 Schema 轉為字典並返回完整結果
        response_data = article_schema.model_dump(mode='json')
        return jsonify({
            "success": True,
            "message": result.get('message'),
            "data": response_data
        }), 200
    except Exception as e:
        return handle_api_error(e)

@article_bp.route('/search', methods=['GET'])
def search_articles():
    """專用搜尋端點 (根據關鍵字搜尋標題/內容/摘要)"""
    try:
        # --- 使用工具函數解析和驗證參數 ---
        validated_params, _ = parse_and_validate_common_query_params(request.args) # 忽略 filter_criteria
        # --- 結束參數處理 ---

        service: ArticleService = get_article_service()

        # 驗證必要的 'q' 參數
        query = validated_params.get('q')
        if not query:
            return jsonify({"success": False, "message": "缺少搜尋關鍵字 'q'"}), 400

        # 使用 find_articles_by_keywords 進行搜尋
        result = service.find_articles_by_keywords(
            keywords=query,
            limit=validated_params['limit'],
            offset=validated_params['offset'],
            sort_by=validated_params['sort_by'],       
            sort_desc=validated_params['sort_desc'],   
            is_preview=validated_params['is_preview'],
            preview_fields=validated_params['preview_fields']
        )

        if not result.get('success'):
            # Service 層返回 False，可能是內部錯誤
             # 檢查是否是因為 Repository 未實現方法
            if "未實現" in result.get('message', ''):
                 logger.error(f"搜尋文章失敗: {result.get('message')}")
                 return jsonify(result), 501 # Not Implemented
            status_code = 500 # 預設為內部錯誤
            return jsonify(result), status_code

        articles_result: Optional[List[Union[ArticleReadSchema, Dict[str, Any]]]] = result.get('articles')

        if articles_result is None:
            # 成功但沒有 articles 鍵
            logger.error("find_articles_by_keywords 成功但未返回 articles")
            return jsonify({"success": False, "message": "無法獲取搜尋結果資料"}), 500

        # 轉換結果列表 (如果不是 preview 模式，items 是 Schema)
        response_data = []
        if articles_result:
            if isinstance(articles_result[0], ArticleReadSchema):
                 response_data = [cast(ArticleReadSchema, a).model_dump(mode='json') for a in articles_result]
            else: # 否則假定是字典列表 (preview 模式)
                 response_data = articles_result

        # 即使列表為空，也算成功執行搜尋
        return jsonify({
            "success": True,
            "message": result.get('message', '搜尋文章成功'),
            "data": response_data
        }), 200

    except ValueError as ve: # <-- 捕獲來自工具函數的 ValueError
        # 工具函數已記錄詳細錯誤，這裡直接返回 400
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        return handle_api_error(e)


