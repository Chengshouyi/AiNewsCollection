"""定義文章相關的 API 路由。"""
# 標準函式庫
from typing import Optional, List, Dict, Any, Union, cast

# 第三方函式庫
from flask import Blueprint, jsonify, request

# 本地應用程式
from src.error.handle_api_error import handle_api_error
from src.models.articles_schema import ArticleReadSchema, PaginatedArticleResponse
from src.services.article_service import ArticleService
from src.services.service_container import get_article_service
from src.utils.api_utils import parse_and_validate_common_query_params
from src.utils.log_utils import LoggerSetup # 使用統一的 logger


logger = LoggerSetup.setup_logger(__name__) # 使用統一的 logger

# 創建藍圖
article_bp = Blueprint('article_api', __name__, url_prefix='/api/articles')

@article_bp.route('', methods=['GET'])
def get_articles():
    """取得文章列表 (支援分頁/篩選/排序)。"""
    try:
        validated_params, filter_criteria = parse_and_validate_common_query_params(request.args)

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
            status_code = 500
            return jsonify(result), status_code

        paginated_response: Optional[PaginatedArticleResponse] = result.get('resultMsg')

        if paginated_response is None:
             logger.error("find_articles_paginated 成功但未返回 resultMsg")
             return jsonify({"success": False, "message": "無法獲取分頁文章資料"}), 500

        # Pydantic v2 的 model_dump 會處理內部 Schema 或字典的轉換
        response_data = paginated_response.model_dump(mode='json')

        return jsonify({
            "success": True,
            "message": result.get('message', '獲取文章列表成功'),
            "data": response_data
        }), 200

    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        return handle_api_error(e)

@article_bp.route('/<int:article_id>', methods=['GET'])
def get_article(article_id):
    """取得單篇文章詳情。"""
    try:
        service: ArticleService = get_article_service()
        result = service.get_article_by_id(article_id)

        if not result.get('success'):
            status_code = 404 if "不存在" in result.get('message', '') else 500
            return jsonify(result), status_code

        article_schema: Optional[ArticleReadSchema] = result.get('article')
        if article_schema is None:
            logger.warning("get_article_by_id 成功但未返回 article 物件 (ID: %s)", article_id)
            return jsonify({"success": False, "message": "成功獲取但找不到文章資料"}), 404

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
    """專用搜尋端點 (根據關鍵字搜尋標題/內容/摘要)。"""
    try:
        validated_params, _ = parse_and_validate_common_query_params(request.args)

        service: ArticleService = get_article_service()

        query = validated_params.get('q')
        if not query:
            return jsonify({"success": False, "message": "缺少搜尋關鍵字 'q'"}), 400

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
            if "未實現" in result.get('message', ''):
                 logger.error("搜尋文章失敗: %s", result.get('message'))
                 return jsonify(result), 501 # Not Implemented
            status_code = 500
            return jsonify(result), status_code

        articles_result: Optional[List[Union[ArticleReadSchema, Dict[str, Any]]]] = result.get('articles')

        if articles_result is None:
            logger.error("find_articles_by_keywords 成功但未返回 articles")
            return jsonify({"success": False, "message": "無法獲取搜尋結果資料"}), 500

        response_data = []
        if articles_result:
            if isinstance(articles_result[0], ArticleReadSchema):
                 response_data = [cast(ArticleReadSchema, a).model_dump(mode='json') for a in articles_result]
            else:
                 response_data = articles_result

        return jsonify({
            "success": True,
            "message": result.get('message', '搜尋文章成功'),
            "data": response_data
        }), 200

    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        return handle_api_error(e)


