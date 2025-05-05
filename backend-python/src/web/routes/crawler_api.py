"""定義爬蟲相關 API 路由 (Blueprint: crawler_bp)。"""
import json
from typing import Optional, List
import logging

from flask import Blueprint, jsonify, request
from werkzeug.datastructures import FileStorage
from flask_pydantic_spec import Response, Request  # 新增

from src.crawlers.crawler_factory import CrawlerFactory
from src.error.handle_api_error import handle_api_error
from src.models.crawlers_schema import (
    CrawlerReadSchema, 
    PaginatedCrawlerResponse,
    CrawlersCreateSchema,
    CrawlersUpdateSchema,
    BatchToggleStatusSchema,
    CrawlerFormDataSchema,
    CrawlerFilterRequestSchema
)
from src.services.crawlers_service import CrawlersService
from src.services.service_container import get_crawlers_service
from src.web.spec import spec  
from src.web.routes.base_response_schema import BaseResponseSchema
from src.web.routes.crawler_response_schema import (
    CrawlerActionSuccessResponseSchema,
    GetCrawlersSuccessResponseSchema,
    DeleteCrawlerSuccessResponseSchema,
    GetCrawlerTypesSuccessResponseSchema,
    GetCrawlerStatsSuccessResponseSchema,
    BatchToggleStatusSuccessResponseSchema,
    GetFilteredCrawlersSuccessResponseSchema,
    GetCrawlerConfigSuccessResponseSchema,
    BatchToggleStatusResultSchema # Import if needed directly
)


logger = logging.getLogger(__name__)  # 使用統一的 logger

# 創建藍圖
crawler_bp = Blueprint('crawlerapi', __name__, url_prefix='/api/crawlers')


@crawler_bp.route('', methods=['GET'])
@spec.validate(  # 更新 Response
    resp=Response(
        HTTP_200=GetCrawlersSuccessResponseSchema, 
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema,
    ),
    tags=['爬蟲管理']
)
def get_crawlers():
    """取得所有爬蟲設定列表"""
    try:
        service: CrawlersService = get_crawlers_service()
        result = service.find_all_crawlers()

        if not result.get('success'):
            # Service 失敗通常是內部錯誤
            return jsonify({"success": False, "message": result.get('message', '獲取爬蟲列表失敗')}), 500

        crawlers_schemas: Optional[List[CrawlerReadSchema]] = result.get('crawlers')
        if crawlers_schemas is None:
             return jsonify({"success": False, "message": "無法獲取爬蟲列表資料"}), 500

        # 將 Schema 列表轉換為字典列表
        crawlers_list = [c.model_dump() for c in crawlers_schemas]
        # 返回標準結構 (數據放入 data 鍵)
        return jsonify({"success": True, "message": result.get('message'), "data": crawlers_list}), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('', methods=['POST'])
@spec.validate(
    # 注意：由於是 multipart/form-data，Request Body 的自動驗證較複雜
    # flask-pydantic-spec 可能無法直接驗證 multipart/form-data
    # 但我們仍然可以定義 Schema 用於文檔和潛在的手動驗證
    # body=Request(CrawlerFormDataSchema), 
    resp=Response( # 更新 Response
        HTTP_201=CrawlerActionSuccessResponseSchema, # 成功創建
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema,                # Server Error
    ),
    tags=['爬蟲管理']
)
def create_crawler_with_config_route():
    """新增一個爬蟲設定及其配置檔案 (使用 multipart/form-data)"""
    # --- 修改：檢查 multipart/form-data ---
    if 'config_file' not in request.files:
        return jsonify({"success": False, "message": "請求中未包含 'config_file' 部分"}), 400

    config_file = request.files['config_file']
    if not config_file or not config_file.filename:
        return jsonify({"success": False, "message": "未選擇或上傳有效的配置檔案"}), 400

    # 可以在這裡添加對檔案類型的基本檢查 (例如，是否為 .json)
    if not config_file.filename.lower().endswith('.json'):
        return jsonify({"success": False, "message": "配置檔案必須是 .json 格式"}), 400

    # --- 修改：獲取表單中的 JSON 字串資料 ---
    crawler_data_str = request.form.get('crawler_data')
    if not crawler_data_str:
        return jsonify({"success": False, "message": "請求中未包含 'crawler_data' 表單欄位"}), 400

    try:
        # 解析 JSON 字串為字典
        crawler_data = json.loads(crawler_data_str)
        if not isinstance(crawler_data, dict):
             raise json.JSONDecodeError("crawler_data 必須是 JSON 物件", crawler_data_str, 0)
    except json.JSONDecodeError as e:
        logger.error("解析 'crawler_data' JSON 字串失敗: %s", e)
        return jsonify({"success": False, "message": f"爬蟲資料 (crawler_data) 格式錯誤: {e}"}), 400

    # --- 修改：獲取服務並調用新方法 ---
    service: CrawlersService = get_crawlers_service()
    try:
        # 調用新的服務方法，傳遞字典和檔案對象
        result = service.create_crawler_with_config(crawler_data, config_file)

        if not result.get('success'):
            # Service 層返回失敗，可能是驗證失敗(400)或內部錯誤(500)
            # 根據錯誤訊息判斷狀態碼
            status_code = 400 if "驗證失敗" in result.get('message', '') or \
                                  "格式錯誤" in result.get('message', '') or \
                                  "不正確" in result.get('message', '') or \
                                  "不得為空" in result.get('message', '') or \
                                  "無法生成" in result.get('message', '') else 500
            return jsonify(result), status_code

        crawler_schema: Optional[CrawlerReadSchema] = result.get('crawler')
        if crawler_schema is None:
            logger.error("創建爬蟲與配置成功但 Service 未返回爬蟲物件")
            # 這種情況理論上不應該發生，如果發生了是內部錯誤
            return jsonify({"success": False, "message": "創建爬蟲後未能獲取結果"}), 500

        # 將 Schema 轉為字典並放入 data 鍵
        response_data = crawler_schema.model_dump()
        return jsonify({
            "success": True, 
            "message": result.get('message'), 
            "data": response_data
        }), 201 # 201 Created

    except Exception as e:
        # 捕獲服務層或其他地方可能拋出的未預期異常
        return handle_api_error(e)

@crawler_bp.route('/<int:crawler_id>', methods=['GET'])
@spec.validate(  # 更新 Response
    resp=Response(
        HTTP_200=CrawlerActionSuccessResponseSchema, # 成功獲取
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema,                 # Not Found
    ),
    tags=['爬蟲管理']
)
def get_crawler(crawler_id):
    """取得特定爬蟲設定"""
    try:
        service: CrawlersService = get_crawlers_service()
        result = service.get_crawler_by_id(crawler_id)

        if not result.get('success'):
            # Service 返回 False 通常是因為找不到
            return jsonify(result), 404

        crawler_schema: Optional[CrawlerReadSchema] = result.get('crawler')
        if crawler_schema is None:
             logger.warning("get_crawler_by_id 成功但未返回 crawler 物件 (ID: %s)", crawler_id)
             return jsonify({"success": False, "message": "成功獲取但找不到爬蟲資料"}), 404

        # 將 Schema 轉為字典並放入 data 鍵
        response_data = crawler_schema.model_dump()
        return jsonify({
            "success": True, 
            "message": result.get('message'), 
            "data": response_data
        }), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/<int:crawler_id>', methods=['PUT'])
@spec.validate(
    # body=Request(CrawlerFormDataSchema), # 同 POST，multipart 驗證問題
    resp=Response( # 更新 Response
        HTTP_200=CrawlerActionSuccessResponseSchema, # 成功更新
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema,                
    ),
    tags=['爬蟲管理']
)
def update_crawler_with_config_route(crawler_id):
    """
    更新特定爬蟲設定及其配置檔案 (使用 multipart/form-data)。
    預期包含 'crawler_data' (JSON 字串) 和可選的 'config_file'。
    """
    logger.info("接收到更新爬蟲（含配置）的請求，ID=%s (multipart/form-data)", crawler_id)

    # --- 檢查 multipart/form-data 中的 crawler_data ---
    crawler_data_str = request.form.get('crawler_data')
    if not crawler_data_str:
        logger.error("請求中未包含 'crawler_data' 表單欄位")
        return jsonify({"success": False, "message": "請求中未包含 'crawler_data' 表單欄位"}), 400

    try:
        # 解析 JSON 字串為字典
        crawler_data = json.loads(crawler_data_str)
        if not isinstance(crawler_data, dict):
             raise json.JSONDecodeError("crawler_data 必須是 JSON 物件", crawler_data_str, 0)
        logger.debug("解析後的 crawler_data: %s", crawler_data)
    except json.JSONDecodeError as e:
        logger.error("解析 'crawler_data' JSON 字串失敗: %s", e)
        return jsonify({"success": False, "message": f"爬蟲資料 (crawler_data) 格式錯誤: {e}"}), 400

    # --- 檢查是否有配置檔案上傳 ---
    config_file: Optional[FileStorage] = request.files.get('config_file')
    if config_file:
        if not config_file.filename:
            logger.warning("提供了 config_file 部分，但檔名為空，將忽略此檔案。")
            config_file = None # 視為未提供有效檔案
        else:
             # 基本檢查檔案類型 (例如，是否為 .json)
             if not config_file.filename.lower().endswith('.json'):
                 logger.error("上傳的配置檔案 '%s' 副檔名不是 .json", config_file.filename)
                 return jsonify({"success": False, "message": "配置檔案必須是 .json 格式"}), 400
             logger.info("檢測到上傳的配置檔案: %s", config_file.filename)
    else:
        logger.info("請求中未包含新的 'config_file'，將使用現有配置。")


    # --- 獲取服務並調用新的更新方法 ---
    service: CrawlersService = get_crawlers_service()
    try:
        # 調用新的服務方法，傳遞 crawler_id, 字典和可能的檔案對象
        result = service.update_crawler_with_config(crawler_id, crawler_data, config_file)

        if not result.get('success'):
            # Service 層返回失敗
            status_code = 404 if "不存在" in result.get('message', '') else \
                          400 if "驗證失敗" in result.get('message', '') or \
                                 "格式錯誤" in result.get('message', '') or \
                                 "不正確" in result.get('message', '') or \
                                 "無法生成" in result.get('message', '') else 500
            logger.error("更新爬蟲（含配置）失敗 (Service 層返回): %s", result.get('message'))
            return jsonify(result), status_code

        updated_crawler_schema: Optional[CrawlerReadSchema] = result.get('crawler')
        if updated_crawler_schema is None:
            logger.error("更新爬蟲成功但 Service 未返回爬蟲物件 (ID: %s)", crawler_id)
            return jsonify({"success": False, "message": "更新爬蟲後未能獲取結果"}), 500

        # 將 Schema 轉為字典並放入 data 鍵
        response_data = updated_crawler_schema.model_dump()
        logger.info("爬蟲（含配置）更新成功，ID=%s", crawler_id)
        return jsonify({
            "success": True, 
            "message": result.get('message'), 
            "data": response_data
        }), 200 # 200 OK

    except Exception as e:
        # 捕獲服務層或其他地方可能拋出的未預期異常
        logger.exception("處理更新爬蟲（含配置）請求時發生未預期異常，ID=%s", crawler_id)
        return handle_api_error(e)

@crawler_bp.route('/<int:crawler_id>', methods=['DELETE'])
@spec.validate(  # 更新 Response
    resp=Response(
        HTTP_200=DeleteCrawlerSuccessResponseSchema, 
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema,                  
    ),
    tags=['爬蟲管理']
)
def delete_crawler(crawler_id):
    """刪除特定爬蟲設定"""
    try:
        service: CrawlersService = get_crawlers_service()
        result = service.delete_crawler(crawler_id)

        if not result.get('success'):
            # Service 返回 False 通常是因為找不到
            return jsonify(result), 404

        # 返回成功訊息即可，符合 DeleteCrawlerSuccessResponseSchema
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/types', methods=['GET'])
@spec.validate(  # 更新 Response
    resp=Response(
        HTTP_200=GetCrawlerTypesSuccessResponseSchema, 
        HTTP_404=BaseResponseSchema,                  
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema,                  
    ),
    tags=['爬蟲管理']
)
def get_available_crawler_types():
    """取得可用的爬蟲名稱列表"""
    try:
        types = CrawlerFactory.list_available_crawler_types() # 返回 List[Dict[str, str]]
        if not types:
            return jsonify({"success": False, "message": "找不到任何可用的爬蟲類型"}), 404
        return jsonify({"success": True, "message": "成功獲取可用的爬蟲類型列表", "data": types}), 200
    except ImportError:
         logger.error("無法導入 CrawlerFactory")
         return jsonify({"success": False, "message": "伺服器內部錯誤，無法獲取爬蟲類型"}), 500
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/active', methods=['GET'])
@spec.validate(  # 更新 Response
    resp=Response(
        HTTP_200=GetCrawlersSuccessResponseSchema, 
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema,                  
    ),
    tags=['爬蟲管理']
)
def get_active_crawlers():
    """取得所有活動中的爬蟲設定"""
    try:
        service: CrawlersService = get_crawlers_service()
        result = service.find_active_crawlers()

        if not result.get('success'):
             return jsonify(result), 500

        crawlers_schemas: Optional[List[CrawlerReadSchema]] = result.get('crawlers')
        if crawlers_schemas is None:
             return jsonify({"success": False, "message": "無法獲取活動爬蟲列表資料"}), 500

        # 將 Schema 列表轉換為字典列表
        crawlers_list = [c.model_dump() for c in crawlers_schemas]

        # 即使列表為空，也算成功獲取
        status_code = 200
        return jsonify({
            "success": True,
            "message": result.get('message'),
            "data": crawlers_list
        }), status_code
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/<int:crawler_id>/toggle', methods=['POST'])
@spec.validate(  # 更新 Response
    resp=Response(
        HTTP_200=CrawlerActionSuccessResponseSchema, # 成功切換狀態
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema,                  
    ),
    tags=['爬蟲管理']
)
def toggle_crawler_status(crawler_id):
    """切換爬蟲活躍狀態"""
    try:
        service: CrawlersService = get_crawlers_service()
        result = service.toggle_crawler_status(crawler_id)

        if not result.get('success'):
            # Service 返回 False 通常是因為找不到
            return jsonify(result), 404

        crawler_schema: Optional[CrawlerReadSchema] = result.get('crawler')
        if crawler_schema is None:
            logger.error("切換狀態成功但 Service 未返回爬蟲物件 (ID: %s)", crawler_id)
            return jsonify({"success": False, "message": "切換狀態後未能獲取更新後的爬蟲資料"}), 500

        # 將 Schema 轉為字典並放入 data 鍵
        response_data = crawler_schema.model_dump()
        return jsonify({
            "success": True,
            "message": result.get('message'),
            "data": response_data
        }), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/name/<string:name>', methods=['GET'])
@spec.validate(  # 更新 Response
    resp=Response(
        HTTP_200=GetCrawlersSuccessResponseSchema, # 成功按名稱獲取
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema,                  
    ),
    tags=['爬蟲管理']
)
def get_crawlers_by_name(name):
    """根據名稱模糊查詢爬蟲設定"""
    try:
        service: CrawlersService = get_crawlers_service()
        is_active_str = request.args.get('is_active')
        is_active: Optional[bool] = None
        if is_active_str:
            is_active = is_active_str.lower() in ['true', '1', 'yes']

        result = service.find_crawlers_by_name(name, is_active=is_active)

        if not result.get('success'):
             return jsonify(result), 500

        crawlers_schemas: Optional[List[CrawlerReadSchema]] = result.get('crawlers')
        if crawlers_schemas is None:
             return jsonify({"success": False, "message": "無法獲取按名稱查詢的爬蟲列表資料"}), 500

        crawlers_list = [c.model_dump() for c in crawlers_schemas]

        status_code = 200
        # 返回標準結構 (數據放入 data 鍵)
        return jsonify({
            "success": True,
            "message": result.get('message'),
            "data": crawlers_list # 已是 list of dicts
        }), status_code
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/type/<string:crawler_type>', methods=['GET'])
@spec.validate(  # 更新 Response
    resp=Response(
        HTTP_200=GetCrawlersSuccessResponseSchema, # 成功按類型獲取
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema,                  
    ),
    tags=['爬蟲管理']
)
def get_crawlers_by_type(crawler_type):
    """根據爬蟲類型查找爬蟲"""
    try:
        service: CrawlersService = get_crawlers_service()
        result = service.find_crawlers_by_type(crawler_type)

        if not result.get('success'):
             return jsonify(result), 500

        crawlers_schemas: Optional[List[CrawlerReadSchema]] = result.get('crawlers')
        if crawlers_schemas is None:
            return jsonify({"success": False, "message": "無法獲取按類型查詢的爬蟲列表資料"}), 500

        crawlers_list = [c.model_dump() for c in crawlers_schemas]

        status_code = 200
        # 返回標準結構 (數據放入 data 鍵)
        return jsonify({
            "success": True,
            "message": result.get('message'),
            "data": crawlers_list # 已是 list of dicts
        }), status_code
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/target/<string:target_pattern>', methods=['GET'])
@spec.validate(  # 更新 Response
    resp=Response(
        HTTP_200=GetCrawlersSuccessResponseSchema, # 成功按目標獲取
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema,                  
    ),
    tags=['爬蟲管理']
)
def get_crawlers_by_target(target_pattern):
    """根據爬取目標模糊查詢爬蟲"""
    try:
        service: CrawlersService = get_crawlers_service()
        result = service.find_crawlers_by_target(target_pattern)

        if not result.get('success'):
            return jsonify(result), 500

        crawlers_schemas: Optional[List[CrawlerReadSchema]] = result.get('crawlers')
        if crawlers_schemas is None:
            return jsonify({"success": False, "message": "無法獲取按目標查詢的爬蟲列表資料"}), 500

        crawlers_list = [c.model_dump() for c in crawlers_schemas]

        status_code = 200
        # 返回標準結構 (數據放入 data 鍵)
        return jsonify({
            "success": True,
            "message": result.get('message'),
            "data": crawlers_list # 已是 list of dicts
        }), status_code
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/statistics', methods=['GET'])
@spec.validate(  # 更新 Response
    resp=Response(
        HTTP_200=GetCrawlerStatsSuccessResponseSchema, # 成功獲取統計
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema,                  
    ),
    tags=['爬蟲管理']
)
def get_crawler_statistics():
    """獲取爬蟲統計信息"""
    try:
        service: CrawlersService = get_crawlers_service()
        result = service.get_crawler_statistics()

        if not result.get('success'):
            return jsonify(result), 500

        # 提取 'data' 部分並返回標準結構
        stats_data = result.get('data')
        if stats_data is None:
             logger.error("獲取統計成功但 Service 未返回 data")
             return jsonify({"success": False, "message": "無法獲取統計資料"}), 500
             
        return jsonify({
            "success": True,
            "message": result.get('message'),
            "data": stats_data
        }), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/exact-name/<string:crawler_name>', methods=['GET'])
@spec.validate(  # 更新 Response
    resp=Response(
        HTTP_200=CrawlerActionSuccessResponseSchema, # 成功精確獲取
        HTTP_404=BaseResponseSchema,                 # Not Found
        HTTP_400=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema,                  
    ),
    tags=['爬蟲管理']
)
def get_crawler_by_exact_name(crawler_name):
    """根據爬蟲名稱精確查詢"""
    try:
        service: CrawlersService = get_crawlers_service()
        result = service.get_crawler_by_exact_name(crawler_name)

        if not result.get('success'):
            # Service 返回 False 通常是因為找不到
            return jsonify(result), 404

        crawler_schema: Optional[CrawlerReadSchema] = result.get('crawler')
        if crawler_schema is None:
            logger.warning("get_crawler_by_exact_name 成功但未返回 crawler 物件 (Name: %s)", crawler_name)
            return jsonify({"success": False, "message": "成功獲取但找不到爬蟲資料"}), 404

        # 將 Schema 轉為字典並放入 data 鍵
        response_data = crawler_schema.model_dump()
        return jsonify({
            "success": True,
            "message": result.get('message'),
            "data": response_data
        }), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/create-or-update', methods=['POST'])
@spec.validate(
    # body=Request(CrawlersCreateSchema), # 這裡的 Request Schema 可能需要更精確，允許 id
    resp=Response(
        HTTP_200=CrawlerActionSuccessResponseSchema, # 成功更新
        HTTP_201=CrawlerActionSuccessResponseSchema, # 成功創建
        HTTP_400=BaseResponseSchema,                # Bad Request
        HTTP_404=BaseResponseSchema,                # Not Found (用於更新時)
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema,                  
    ),
    tags=['爬蟲管理']
)
def create_or_update_crawler():
    """創建或更新爬蟲設定"""
    if not request.is_json:
         return jsonify(success=False, message='請求必須是 application/json'), 415
    if not request.data:
         return jsonify(success=False, message='缺少任務資料'), 400
    service: CrawlersService = get_crawlers_service()
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "請求體為空或非 JSON 格式"}), 400

        # 判斷是更新還是創建
        is_update_operation = 'id' in data and data.get('id')

        # 驗證在 Service 內部進行
        result = service.create_or_update_crawler(data)

        if not result.get('success'):
            status_code = 404 if "不存在" in result.get('message', '') else \
                          400 if "驗證失敗" in result.get('message', '') else 500
            return jsonify(result), status_code

        crawler_schema: Optional[CrawlerReadSchema] = result.get('crawler')
        if crawler_schema is None:
            op_type = "更新" if is_update_operation else "創建"
            logger.error("%s爬蟲成功但 Service 未返回爬蟲物件", op_type)
            return jsonify({"success": False, "message": f"{op_type}爬蟲後未能獲取結果"}), 500

        # 將 Schema 轉為字典並放入 data 鍵
        response_data = crawler_schema.model_dump()
        status_code = 200 if is_update_operation else 201
        return jsonify({
            "success": True,
            "message": result.get('message'),
            "data": response_data
        }), status_code
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/batch-toggle', methods=['POST'])
@spec.validate(
    # body=Request(BatchToggleStatusSchema), # Request Body Schema
    resp=Response(
        HTTP_200=BatchToggleStatusSuccessResponseSchema, # 成功 (即使部分失敗)
        HTTP_400=BaseResponseSchema,                     
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema,                  
    ),
    tags=['爬蟲管理']
)
def batch_toggle_crawler_status():
    """批量設置爬蟲的活躍狀態"""
    if not request.is_json:
         return jsonify(success=False, message='請求必須是 application/json'), 415
    if not request.data:
         return jsonify(success=False, message='缺少任務資料'), 400
    try:
        service: CrawlersService = get_crawlers_service()
        data = request.get_json()

        # if not data or 'crawler_ids' not in data or 'active_status' not in data:
        #     return jsonify({"success": False, "message": "請求體缺少必要參數 'crawler_ids' 或 'active_status'"}), 400

        # 使用 Pydantic 模型進行驗證（如果 Service 層沒有做的話）
        try:
            # 嘗試將請求數據解析為 BatchToggleStatusSchema
            # 這一步會自動驗證類型和是否存在必要的字段
            request_schema = BatchToggleStatusSchema(**data) 
            crawler_ids = request_schema.crawler_ids
            active_status = request_schema.active_status
        # except (ValidationError, TypeError) as ve: # Pydantic v2 用 ValidationError
        except Exception as ve: # 捕獲更廣泛的錯誤以防萬一
             logger.error("批量切換狀態請求參數驗證失敗: %s", ve)
             # 根據 Pydantic v2，錯誤消息可能在 ve.errors() 中
             error_msg = str(ve) # 簡化處理
             return jsonify({"success": False, "message": f"參數格式錯誤: {error_msg}"}), 400


        result = service.batch_toggle_crawler_status(crawler_ids, active_status)

        # Service 返回的結果在 'result' 鍵下
        operation_result_data = result.get('result') 

        # 如果 Service 成功（可能部分成功），或者即使 Service 標記為 False 但有成功記錄
        if result.get('success') or (operation_result_data and operation_result_data.get('success_count', 0) > 0):
            if operation_result_data is None:
                # 如果數據丟失，這是一個服務端錯誤
                logger.error("批量切換狀態操作成功但 Service 未返回 result 數據")
                return jsonify({"success": False, "message": "操作完成但無法獲取結果詳情"}), 500
            
            # 將 'result' 的內容放入 'data' 以符合 Schema
            # 確保 operation_result_data 符合 BatchToggleStatusResultSchema 結構
            # (如果 Service 返回的就是字典，這裡不需要轉換)
            return jsonify({
                "success": True, # 標記為整體成功
                "message": result.get('message'),
                "data": operation_result_data # 將 result 字典放入 data
            }), 200
        else:
            # Service 標記失敗且沒有任何成功操作，視為客戶端錯誤或內部錯誤
            # Service 應該返回更具體的錯誤消息
            status_code = 400 # 假設是參數問題或全部 ID 無效
            return jsonify(result), status_code # 返回原始錯誤訊息

    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/filter', methods=['POST'])
@spec.validate(
    body=Request(CrawlerFilterRequestSchema), # Request Body Schema
    resp=Response(
        HTTP_200=GetFilteredCrawlersSuccessResponseSchema, 
        HTTP_400=BaseResponseSchema,                       
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema,                  
    ),
    tags=['爬蟲管理']
)
def get_filtered_crawlers():
    """根據過濾條件獲取分頁爬蟲列表"""
    if not request.is_json:
         return jsonify(success=False, message='請求必須是 application/json'), 415
    if not request.data:
         return jsonify(success=False, message='缺少任務資料'), 400
    try:
        service: CrawlersService = get_crawlers_service()
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "message": "請求體為空或非 JSON 格式"}), 400

        # 提取參數，提供預設值
        filter_dict = data.get('filter', {})
        try:
             page = int(data.get('page', 1))
             per_page = int(data.get('per_page', 10))
             if page < 1 or per_page < 1:
                 raise ValueError("頁碼和每頁數量必須是正整數")
        except (ValueError, TypeError):
             return jsonify({"success": False, "message": "page 和 per_page 必須是有效的正整數"}), 400

        sort_by = data.get('sort_by')
        sort_desc = data.get('sort_desc', False)

        # 使用 Pydantic 模型驗證過濾條件 (如果需要更嚴格的驗證)
        # try:
        #     filter_schema = CrawlerFilterRequestSchema(filter=filter_dict, page=page, per_page=per_page, sort_by=sort_by, sort_desc=sort_desc)
        # except ValidationError as ve:
        #     return jsonify({"success": False, "message": f"過濾參數格式錯誤: {ve}"}), 400


        result = service.find_filtered_crawlers(
            filter_criteria=filter_dict, # filter_schema.filter
            page=page,                   # filter_schema.page
            per_page=per_page,           # filter_schema.per_page
            sort_by=sort_by,             # filter_schema.sort_by
            sort_desc=sort_desc          # filter_schema.sort_desc
        )

        if not result.get('success'):
             # Service 內部錯誤
             return jsonify(result), 500

        paginated_data: Optional[PaginatedCrawlerResponse] = result.get('data')
        if paginated_data is None:
             return jsonify({"success": False, "message": "無法獲取分頁爬蟲資料"}), 500

        # 將 PaginatedCrawlerResponse 實例轉換為字典並放入 data 鍵
        response_data = paginated_data.model_dump(mode='json')
        return jsonify({
            "success": True,
            "message": result.get('message'),
            "data": response_data
        }), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/<int:crawler_id>/config', methods=['GET'])
@spec.validate(  # 更新 Response
    resp=Response(
        HTTP_200=GetCrawlerConfigSuccessResponseSchema, # 成功獲取配置
        HTTP_404=BaseResponseSchema,                    
        HTTP_400=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema,                  
    ),
    tags=['爬蟲管理']
)
def get_crawler_config(crawler_id):
    """獲取爬蟲的配置檔案內容"""
    try:
        logger.info("開始獲取爬蟲配置，ID=%s", crawler_id)
        service: CrawlersService = get_crawlers_service()
        result = service.get_crawler_config(crawler_id)
        
        logger.info("獲取爬蟲配置結果: %s", result)
        
        if not result.get('success'):
            # 修改：無論失敗原因 (ID不存在或配置找不到)，都返回 404
            status_code = 404 
            logger.error("獲取爬蟲配置失敗 (ID: %s): %s", crawler_id, result.get('message')) # Log the specific reason
            return jsonify(result), status_code

        # 提取 'data' 部分並返回標準結構
        config_data = result.get('data')
        if config_data is None:
             logger.error("獲取配置成功但 Service 未返回 data (ID: %s)", crawler_id)
             return jsonify({"success": False, "message": "無法獲取配置資料內容"}), 500 # 認為是服務端問題

        return jsonify({
            "success": True,
            "message": result.get('message'),
            "data": config_data # config_data 應該是 dict
        }), 200
    except Exception as e:
        logger.error("獲取爬蟲配置時發生異常: %s", str(e), exc_info=True)
        return handle_api_error(e)