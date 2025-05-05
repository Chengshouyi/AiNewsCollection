"""定義文章相關的 API 路由。"""

# 標準函式庫
from typing import Optional, List, Dict, Any, Union, cast
import logging

# 第三方函式庫
from flask import Blueprint, jsonify, request
from flask_pydantic_spec import Response, Request

# 本地應用程式
from src.error.handle_api_error import handle_api_error
from src.models.articles_schema import ArticleReadSchema, PaginatedArticleResponse
from src.services.article_service import ArticleService
from src.services.service_container import get_article_service
from src.utils.api_utils import parse_and_validate_common_query_params
from src.web.spec import spec
from src.web.routes.article_response_schema import GetArticlesSuccessResponseSchema, GetArticleSuccessResponseSchema, SearchArticlesSuccessResponseSchema
from src.web.routes.base_response_schema import BaseResponseSchema

logger = logging.getLogger(__name__)

# 創建藍圖
article_bp = Blueprint('article_api', __name__, url_prefix='/api/articles')


@article_bp.route('', methods=['GET'])
@spec.validate(
    resp=Response(HTTP_200=GetArticlesSuccessResponseSchema, 
                  HTTP_400=BaseResponseSchema,
                  HTTP_404=BaseResponseSchema,
                  HTTP_500=BaseResponseSchema,
                  HTTP_502=BaseResponseSchema,
                  HTTP_503=BaseResponseSchema,
                  HTTP_504=BaseResponseSchema),
    tags=['文章管理']
)
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
@spec.validate(
    resp=Response(
        HTTP_200=GetArticleSuccessResponseSchema,
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema
    ),
    tags=['文章管理']
)
def get_article(article_id):
    """取得單篇文章詳情。"""
    try:
        service: ArticleService = get_article_service()
        result = service.get_article_by_id(article_id)

        if not result.get('success'):
            status_code = 404 if "不存在" in result.get('message', '') else 500
            return jsonify({"success": False, "message": result.get('message')}), status_code

        article_schema: Optional[ArticleReadSchema] = result.get('article')
        # === DEBUGGING: 檢查返回的 article 類型 ===
        # logger.debug(f"get_article_by_id returned type: {type(article_schema)}")

        if article_schema is None:
            logger.warning("get_article_by_id 成功但未返回 article 物件 (ID: %s)", article_id)
            return jsonify({"success": False, "message": "成功獲取但找不到文章資料"}), 404

        # 確保調用 model_dump 將 Pydantic 物件 (真實或 Mock) 轉換為字典
        logger.debug(f"Article schema type before model_dump: {type(article_schema)}")
        response_data = article_schema.model_dump(mode='json')
        logger.debug(f"Data after model_dump: {response_data}") # 檢查轉換後的字典
        logger.debug(f"Data type after model_dump: {type(response_data)}")

        return jsonify({
            "success": True,
            "message": result.get('message'),
            "data": response_data
        }), 200

    except Exception as e:
        logger.error(f"Exception in get_article: {e}", exc_info=True) # 記錄詳細的 traceback
        return handle_api_error(e)

@article_bp.route('/search', methods=['GET'])
@spec.validate(
    resp=Response(
        HTTP_200=SearchArticlesSuccessResponseSchema,
        HTTP_400=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_501=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema
    ),
    tags=['文章管理']
)
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
                 return jsonify({"success": False, "message": result.get('message')}), 501 # Not Implemented
            status_code = 500
            return jsonify({"success": False, "message": result.get('message')}), status_code

        articles_result: Optional[List[Union[ArticleReadSchema, Dict[str, Any]]]] = result.get('articles')

        if articles_result is None:
            logger.error("find_articles_by_keywords 成功但未返回 articles")
            return jsonify({"success": False, "message": "無法獲取搜尋結果資料"}), 500

        # 根據 is_preview 分離處理邏輯
        response_data = []
        if validated_params.get('is_preview'):
            # 預覽模式：假定 articles_result 是字典列表
            if articles_result and isinstance(articles_result[0], dict):
                response_data = articles_result
            else:
                # 如果不是預期的字典列表 (可能是空列表或類型錯誤)，記錄並保持空列表
                if articles_result: # 僅在列表非空時記錄錯誤
                    logger.warning(f"Preview mode expected list[dict] but got {type(articles_result[0])}")
                response_data = []
        else:
            # 非預覽模式：假定 articles_result 是 Pydantic 模型列表
            if articles_result and hasattr(articles_result[0], 'model_dump'):
                response_data = [
                    a.model_dump(mode='json')  # type: ignore[attr-defined]
                    for a in articles_result
                    # 再次檢查確保 a 也有 model_dump 方法
                    if hasattr(a, 'model_dump') and callable(getattr(a, 'model_dump'))
                ]
            else:
                # 如果不是預期的模型列表 (可能是空列表或類型錯誤)，記錄並保持空列表
                if articles_result: # 僅在列表非空時記錄錯誤
                    logger.warning(f"Non-preview mode expected list with model_dump but got {type(articles_result[0])}")
                response_data = []

        return jsonify({
            "success": True,
            "message": result.get('message', '搜尋文章成功'),
            "data": response_data
        }), 200

    except ValueError as ve:
        return jsonify({"success": False, "message": str(ve)}), 400
    except Exception as e:
        return handle_api_error(e)


