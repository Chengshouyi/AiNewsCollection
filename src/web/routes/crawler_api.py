from flask import Blueprint, jsonify, request, Response
from src.services.crawlers_service import CrawlersService
from src.services.service_container import get_crawlers_service
from src.error.handle_api_error import handle_api_error
import logging
from src.error.errors import ValidationError
from typing import Dict, Any, Optional, List
from src.models.crawlers_schema import CrawlerReadSchema, PaginatedCrawlerResponse # 引入 Schema
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 創建藍圖
crawler_bp = Blueprint('crawlerapi', __name__, url_prefix='/api/crawlers')


@crawler_bp.route('', methods=['GET'])
def get_crawlers():
    """取得所有爬蟲設定列表"""
    try:
        service: CrawlersService = get_crawlers_service() # 指定類型提示
        result = service.find_all_crawlers()

        if not result.get('success'):
            # Service 失數通常是內部錯誤，但這裡也可能是找不到資料庫存取器
            return jsonify({"success": False, "message": result.get('message', '獲取爬蟲列表失敗')}), 500

        crawlers_schemas: Optional[List[CrawlerReadSchema]] = result.get('crawlers')
        if crawlers_schemas is None:
             # 成功但沒有 crawlers 鍵，理論上不應發生
             return jsonify({"success": False, "message": "無法獲取爬蟲列表資料"}), 500

        # 將 Schema 列表轉換為字典列表
        crawlers_list = [c.model_dump() for c in crawlers_schemas]
        # 返回包含 success, message 和 data 的標準結構
        return jsonify({"success": True, "message": result.get('message'), "data": crawlers_list}), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('', methods=['POST'])
def create_crawler():
    """新增一個爬蟲設定"""
    if not request.is_json:
         return jsonify(success=False, message='請求必須是 application/json'), 415 # Unsupported Media Type
    if not request.data: # 檢查是否有實際的請求體
         return jsonify(success=False, message='缺少任務資料'), 400 # Bad Request
    service: CrawlersService = get_crawlers_service()
    try:
        data = request.get_json()
        if not data: # 檢查是否有請求體
            return jsonify({"success": False, "message": "請求體為空或非 JSON 格式"}), 400

        # 直接調用 Service 的 create 方法，驗證在 Service 內部進行
        result = service.create_crawler(data)

        if not result.get('success'):
            # Service 層返回的失敗，可能是驗證失敗或資料庫錯誤
            # Pydantic 驗證錯誤通常會導致 message 包含詳細信息
            status_code = 400 if "驗證失敗" in result.get('message', '') else 500
            return jsonify(result), status_code # 直接返回 Service 的錯誤訊息

        # 創建成功，Service 返回包含 CrawlerReadSchema 的字典
        crawler_schema: Optional[CrawlerReadSchema] = result.get('crawler')
        if crawler_schema is None:
            # 雖然 success=True 但沒拿到 crawler 的情況不太可能，但還是處理一下
            logger.error("創建爬蟲成功但 Service 未返回爬蟲物件")
            return jsonify({"success": False, "message": "創建爬蟲後未能獲取結果"}), 500

        # 將 Schema 轉為字典並返回完整結果
        result['crawler'] = crawler_schema.model_dump()
        return jsonify(result), 201 # 返回 201 Created

    except Exception as e:
        # 捕獲 Service 層或底層可能拋出的其他未預期錯誤
        return handle_api_error(e)

@crawler_bp.route('/<int:crawler_id>', methods=['GET'])
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
             # 成功但沒有 crawler，理論上不會發生在 get_by_id
             logger.warning(f"get_crawler_by_id 成功但未返回 crawler 物件 (ID: {crawler_id})")
             return jsonify({"success": False, "message": "成功獲取但找不到爬蟲資料"}), 404 # 或者 500

        # 將 Schema 轉為字典並返回完整結果
        result['crawler'] = crawler_schema.model_dump()
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/<int:crawler_id>', methods=['PUT'])
def update_crawler(crawler_id):
    """更新特定爬蟲設定"""
    if not request.is_json:
         return jsonify(success=False, message='請求必須是 application/json'), 415 # Unsupported Media Type
    if not request.data: # 檢查是否有實際的請求體
         return jsonify(success=False, message='缺少任務資料'), 400 # Bad Request
    service: CrawlersService = get_crawlers_service()
    try:
        data = request.get_json()
        if not data:
             return jsonify({"success": False, "message": "請求體為空或非 JSON 格式"}), 400

        # 直接調用 Service 的 update 方法，驗證在 Service 內部進行
        result = service.update_crawler(crawler_id, data)

        if not result.get('success'):
             # 可能是找不到 ID (404) 或驗證失敗 (400) 或其他錯誤 (500)
             status_code = 404 if "不存在" in result.get('message', '') else \
                           400 if "驗證失敗" in result.get('message', '') else 500
             return jsonify(result), status_code

        updated_crawler_schema: Optional[CrawlerReadSchema] = result.get('crawler')
        if updated_crawler_schema is None:
             # 更新成功但未返回 crawler 的情況
             logger.error(f"更新爬蟲成功但 Service 未返回爬蟲物件 (ID: {crawler_id})")
             return jsonify({"success": False, "message": "更新爬蟲後未能獲取結果"}), 500

        # 將 Schema 轉為字典並返回完整結果
        result['crawler'] = updated_crawler_schema.model_dump()
        return jsonify(result), 200 # 返回 200 OK

    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/<int:crawler_id>', methods=['DELETE'])
def delete_crawler(crawler_id):
    """刪除特定爬蟲設定"""
    try:
        service: CrawlersService = get_crawlers_service()
        result = service.delete_crawler(crawler_id)

        if not result.get('success'):
            # Service 返回 False 通常是因為找不到
            return jsonify(result), 404 # 直接返回 Service 的訊息，例如 "爬蟲設定不存在..."

        # 刪除成功，返回 Service 的成功訊息
        return jsonify(result), 200 # 狀態碼 200 OK
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/types', methods=['GET'])
def get_available_crawler_types():
    """取得可用的爬蟲名稱"""
    try:
        # 此路由不直接使用 CrawlersService，而是 CrawlerFactory
        from src.crawlers.crawler_factory import CrawlerFactory
        types = CrawlerFactory.list_available_crawler_types() # 假設返回 List[Dict[str, str]]
        if not types: # 檢查列表是否為空
            return jsonify({"success": False, "message": "找不到任何可用的爬蟲類型"}), 404
        return jsonify({"success": True, "message": "成功獲取可用的爬蟲類型列表", "data": types}), 200
    except ImportError:
         logger.error("無法導入 CrawlerFactory")
         return jsonify({"success": False, "message": "伺服器內部錯誤，無法獲取爬蟲類型"}), 500
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/active', methods=['GET'])
def get_active_crawlers():
    """取得所有活動中的爬蟲設定"""
    try:
        service: CrawlersService = get_crawlers_service()
        result = service.find_active_crawlers()

        if not result.get('success'):
             # 如果 Service 內部出錯（例如無法訪問 DB）
             return jsonify(result), 500

        crawlers_schemas: Optional[List[CrawlerReadSchema]] = result.get('crawlers')
        if crawlers_schemas is None:
             # 成功但沒有 crawlers 鍵
             return jsonify({"success": False, "message": "無法獲取活動爬蟲列表資料"}), 500

        # 將 Schema 列表轉換為字典列表
        crawlers_list = [c.model_dump() for c in crawlers_schemas]

        # 即使列表為空，也算成功獲取，只是沒有活動的爬蟲
        # Service 的 message 會是 "找不到任何活動中的爬蟲設定"
        status_code = 200 # 總是返回 200，讓前端根據 data 是否為空來判斷
        return jsonify({
            "success": True, # 維持 True 表示操作成功
            "message": result.get('message'),
            "data": crawlers_list
        }), status_code
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/<int:crawler_id>/toggle', methods=['POST'])
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
            # 成功但未返回 crawler
            logger.error(f"切換狀態成功但 Service 未返回爬蟲物件 (ID: {crawler_id})")
            return jsonify({"success": False, "message": "切換狀態後未能獲取更新後的爬蟲資料"}), 500

        # 將 Schema 轉為字典並返回完整結果
        result['crawler'] = crawler_schema.model_dump()
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/name/<string:name>', methods=['GET'])
def get_crawlers_by_name(name):
    """根據名稱模糊查詢爬蟲設定"""
    try:
        service: CrawlersService = get_crawlers_service()
        # 可以在這裡接收查詢參數，例如 is_active
        is_active_str = request.args.get('is_active')
        is_active: Optional[bool] = None
        if is_active_str:
            is_active = is_active_str.lower() in ['true', '1', 'yes']

        result = service.find_crawlers_by_name(name, is_active=is_active)

        if not result.get('success'):
             # Service 內部錯誤
             return jsonify(result), 500

        crawlers_schemas: Optional[List[CrawlerReadSchema]] = result.get('crawlers')
        if crawlers_schemas is None:
             return jsonify({"success": False, "message": "無法獲取按名稱查詢的爬蟲列表資料"}), 500

        crawlers_list = [c.model_dump() for c in crawlers_schemas]

        # 即使列表為空也返回 200，表示查詢成功執行
        status_code = 200
        return jsonify({
            "success": True,
            "message": result.get('message'), # 例如 "找不到任何符合條件的爬蟲設定"
            "data": crawlers_list
        }), status_code
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/type/<string:crawler_type>', methods=['GET'])
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

        status_code = 200 # 即使空列表也 200
        return jsonify({
            "success": True,
            "message": result.get('message'),
            "data": crawlers_list
        }), status_code
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/target/<string:target_pattern>', methods=['GET'])
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

        status_code = 200 # 即使空列表也 200
        return jsonify({
            "success": True,
            "message": result.get('message'),
            "data": crawlers_list
        }), status_code
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/statistics', methods=['GET'])
def get_crawler_statistics():
    """獲取爬蟲統計信息"""
    try:
        service: CrawlersService = get_crawlers_service()
        result = service.get_crawler_statistics()

        if not result.get('success'):
            # Service 失敗通常是內部錯誤
            return jsonify(result), 500

        # 直接返回 Service 的結果，其中包含 statistics 字典
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/exact-name/<string:crawler_name>', methods=['GET'])
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
            # 成功但沒有 crawler
            logger.warning(f"get_crawler_by_exact_name 成功但未返回 crawler 物件 (Name: {crawler_name})")
            return jsonify({"success": False, "message": "成功獲取但找不到爬蟲資料"}), 404

        # 將 Schema 轉為字典並返回完整結果
        result['crawler'] = crawler_schema.model_dump()
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/create-or-update', methods=['POST'])
def create_or_update_crawler():
    """創建或更新爬蟲設定"""
    if not request.is_json:
         return jsonify(success=False, message='請求必須是 application/json'), 415 # Unsupported Media Type
    if not request.data: # 檢查是否有實際的請求體
         return jsonify(success=False, message='缺少任務資料'), 400 # Bad Request
    service: CrawlersService = get_crawlers_service()
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "請求體為空或非 JSON 格式"}), 400

        # 判斷是更新還是創建操作，主要影響返回的狀態碼
        is_update_operation = 'id' in data and data.get('id')

        # 直接調用 Service 的方法，驗證在 Service 內部進行
        result = service.create_or_update_crawler(data)

        if not result.get('success'):
            # 處理 Service 返回的失敗情況
            status_code = 404 if "不存在" in result.get('message', '') else \
                          400 if "驗證失敗" in result.get('message', '') else 500
            return jsonify(result), status_code

        crawler_schema: Optional[CrawlerReadSchema] = result.get('crawler')
        if crawler_schema is None:
            # 操作成功但未返回 crawler
            op_type = "更新" if is_update_operation else "創建"
            logger.error(f"{op_type}爬蟲成功但 Service 未返回爬蟲物件")
            return jsonify({"success": False, "message": f"{op_type}爬蟲後未能獲取結果"}), 500

        # 將 Schema 轉為字典
        result['crawler'] = crawler_schema.model_dump()
        # 根據是創建還是更新返回不同狀態碼
        status_code = 200 if is_update_operation else 201
        return jsonify(result), status_code
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/batch-toggle', methods=['POST'])
def batch_toggle_crawler_status():
    """批量設置爬蟲的活躍狀態"""
    if not request.is_json:
         return jsonify(success=False, message='請求必須是 application/json'), 415 # Unsupported Media Type
    if not request.data: # 檢查是否有實際的請求體
         return jsonify(success=False, message='缺少任務資料'), 400 # Bad Request
    try:
        service: CrawlersService = get_crawlers_service()
        data = request.get_json()

        if not data or 'crawler_ids' not in data or 'active_status' not in data:
            return jsonify({"success": False, "message": "請求體缺少必要參數 'crawler_ids' 或 'active_status'"}), 400

        try:
            # 基本類型驗證
            crawler_ids = data['crawler_ids']
            active_status = data['active_status']
            if not isinstance(crawler_ids, list) or not all(isinstance(item, int) for item in crawler_ids):
                 raise ValueError("crawler_ids 必須是整數列表")
            if not isinstance(active_status, bool):
                 raise ValueError("active_status 必須是布林值")
        except (ValueError, KeyError) as ve:
             return jsonify({"success": False, "message": f"參數格式錯誤: {ve}"}), 400

        result = service.batch_toggle_crawler_status(crawler_ids, active_status)

        # Service 層的 success=False 通常表示所有操作都失敗或內部錯誤
        if not result.get('success') and result.get('result', {}).get('success_count', 0) == 0:
            return jsonify(result), 400 # 或 500 如果是內部錯誤

        # 即使部分失敗，只要有成功的，整體操作算成功 (200)
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/filter', methods=['POST'])
def get_filtered_crawlers():
    """根據過濾條件獲取分頁爬蟲列表"""
    if not request.is_json:
         return jsonify(success=False, message='請求必須是 application/json'), 415 # Unsupported Media Type
    if not request.data: # 檢查是否有實際的請求體
         return jsonify(success=False, message='缺少任務資料'), 400 # Bad Request
    try:
        service: CrawlersService = get_crawlers_service()
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "message": "請求體為空或非 JSON 格式"}), 400

        # 從請求體中提取參數，提供預設值
        filter_dict = data.get('filter', {})
        try:
             page = int(data.get('page', 1))
             per_page = int(data.get('per_page', 10))
             if page < 1 or per_page < 1:
                 raise ValueError("頁碼和每頁數量必須是正整數")
        except (ValueError, TypeError):
             return jsonify({"success": False, "message": "page 和 per_page 必須是有效的正整數"}), 400

        sort_by = data.get('sort_by') # Optional[str]
        sort_desc = data.get('sort_desc', False) # bool

        result = service.find_filtered_crawlers(
            filter_criteria=filter_dict,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_desc=sort_desc
        )

        # Service 層現在即使找不到也會返回 success=True 和空的 PaginatedCrawlerResponse
        if not result.get('success'):
             # 這種情況通常表示 Service 內部錯誤，而不是找不到
             return jsonify(result), 500

        paginated_data: Optional[PaginatedCrawlerResponse] = result.get('data')
        if paginated_data is None:
             # 成功但沒有 data 鍵
             return jsonify({"success": False, "message": "無法獲取分頁爬蟲資料"}), 500

        result['data'] = paginated_data.model_dump(mode='json')

        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/<int:crawler_id>/config', methods=['GET'])
def get_crawler_config(crawler_id):
    """獲取爬蟲的配置檔案內容"""
    try:
        logger.info(f"開始獲取爬蟲配置，ID={crawler_id}")
        service: CrawlersService = get_crawlers_service()
        result = service.get_crawler_config(crawler_id)
        
        logger.info(f"獲取爬蟲配置結果: {result}")
        
        if not result.get('success'):
            status_code = 404 if "不存在" in result.get('message', '') else 500
            logger.error(f"獲取爬蟲配置失敗: {result.get('message')}")
            return jsonify(result), status_code

        return jsonify(result), 200
    except Exception as e:
        logger.error(f"獲取爬蟲配置時發生異常: {str(e)}", exc_info=True)
        return handle_api_error(e)

@crawler_bp.route('/<int:crawler_id>/config', methods=['PUT'])
def update_crawler_config(crawler_id):
    """更新爬蟲的配置檔案"""
    try:
        if 'config_file' not in request.files:
            return jsonify({"success": False, "message": "未提供配置檔案"}), 400
            
        config_file = request.files['config_file']
        if not config_file.filename:
            return jsonify({"success": False, "message": "未選擇檔案"}), 400
            
        if not config_file.filename.endswith('.json'):
            return jsonify({"success": False, "message": "配置檔案必須是 JSON 格式"}), 400
            
        # 獲取爬蟲資料
        crawler_data = request.form.get('crawler_data')
        if not crawler_data:
            return jsonify({"success": False, "message": "未提供爬蟲資料"}), 400
            
        try:
            crawler_data = json.loads(crawler_data)
        except json.JSONDecodeError:
            return jsonify({"success": False, "message": "爬蟲資料格式錯誤"}), 400
            
        service: CrawlersService = get_crawlers_service()
        result = service.update_crawler_config(crawler_id, config_file, crawler_data)
        
        if not result.get('success'):
            return jsonify(result), 500
            
        # 將 CrawlerReadSchema 轉換為字典
        if result.get('crawler'):
            result['crawler'] = result['crawler'].model_dump()
            
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)