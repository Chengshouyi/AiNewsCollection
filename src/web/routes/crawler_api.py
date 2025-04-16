from flask import Blueprint, jsonify, request, Response
from src.services.crawlers_service import CrawlersService
from src.services.service_container import get_crawlers_service
from src.error.handle_api_error import handle_api_error
import logging
from src.error.errors import ValidationError
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 創建藍圖
crawler_bp = Blueprint('crawlerapi', __name__, url_prefix='/api/crawlers')


@crawler_bp.route('', methods=['GET'])
def get_crawlers():
    """取得所有爬蟲設定列表"""
    try:
        service = get_crawlers_service()  # 獲取服務實例
        result = service.get_all_crawlers()
        
        if not result.get('success'):
            return jsonify({"error": result.get('message')}), 400
        
        crawlers = result.get('crawlers', [])
        return jsonify([c.to_dict() for c in crawlers if c is not None]), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('', methods=['POST'])
def create_crawler():
    """新增一個爬蟲設定"""
    service = get_crawlers_service() # 先獲取 Service
    try:
        data = request.get_json() or {}
        if len(data) == 0:
            return jsonify({"success": False, "message": "缺少爬蟲資料"}), 400

        # --- API 層驗證 ---
        try:
            validated_result = _setup_validate_crawler_data(data, service, is_update=False)
            if not validated_result['success']:
                return jsonify(validated_result), 400
        except ValidationError as e:
            # 捕獲驗證錯誤，返回 400
            return jsonify({"success": False, "message": "輸入資料驗證失敗", "details": str(e)}), 400
        # --- 驗證結束 ---

        # 將驗證後的資料傳遞給 service
        result = service.create_crawler(validated_result['data']) # Service 的 create 現在接收驗證後的資料

        if not result.get('success'):
            # Service 層可能還會拋出其他錯誤 (如資料庫操作錯誤)
            return jsonify(result), 400 # 或 500

        new_crawler = result.get('crawler')
        if new_crawler is None:
            # 雖然 success=True 但沒拿到 crawler 的情況不太可能，但還是處理一下
            return jsonify({"success": False, "message": "創建爬蟲後未能獲取結果"}), 500

        return jsonify(result), 201 # 返回 201 Created

    except Exception as e:
        # 捕獲 Service 層或驗證過程中未處理的其他錯誤
        return handle_api_error(e) # 使用統一錯誤處理器

@crawler_bp.route('/<int:crawler_id>', methods=['GET'])
def get_crawler(crawler_id):
    """取得特定爬蟲設定"""
    try:
        service = get_crawlers_service()
        result = service.get_crawler_by_id(crawler_id)
        
        if not result.get('success'):
            return jsonify(result), 404
        
        crawler = result.get('crawler')
        if crawler is None:
            return jsonify({"success": False, "message": "找不到爬蟲資料"}), 404
            
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/<int:crawler_id>', methods=['PUT'])
def update_crawler(crawler_id):
    """更新特定爬蟲設定"""
    service = get_crawlers_service()
    try:
        data = request.get_json() or {}
        if len(data) == 0:
            return jsonify({"success": False, "message": "缺少爬蟲資料"}), 400

        # --- API 層驗證 ---
        validated_result = _setup_validate_crawler_data(data, service, is_update=True)
        if not validated_result['success']:
            return jsonify(validated_result), 400
            
        # --- 驗證結束 ---

        # 將驗證後的 payload 傳遞給 service
        update_result = service.update_crawler(crawler_id, validated_result['data'])

        if not update_result.get('success'):
            return jsonify(update_result), 400

        updated_crawler = update_result.get('crawler')
        if updated_crawler is None:
            return jsonify({"success": False, "message": "更新爬蟲後未能獲取結果"}), 500

        return jsonify(update_result), 200 # 返回 200 OK

    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/<int:crawler_id>', methods=['DELETE'])
def delete_crawler(crawler_id):
    """刪除特定爬蟲設定"""
    try:
        service = get_crawlers_service()
        result = service.delete_crawler(crawler_id)
        
        if not result.get('success'):
            return jsonify({"error": "Not Found"}), 404
        
        return jsonify({"message": "Deleted"}), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/types', methods=['GET'])
def get_available_crawler_types():
    """取得可用的爬蟲名稱"""
    try:
        from src.crawlers.crawler_factory import CrawlerFactory
        types = CrawlerFactory.list_available_crawler_types()
        if len(types) == 0:
            return jsonify({"success": False, "message": "找不到任何可用的爬蟲名稱"}), 404
        return jsonify({"success": True, "message": "找到可用的爬蟲名稱清單", "data": types}), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/active', methods=['GET'])
def get_active_crawlers():
    """取得所有活動中的爬蟲設定"""
    try:
        service = get_crawlers_service()
        result = service.get_active_crawlers()
        
        if not result.get('success'):
            return jsonify(result), 400
        
        crawlers = result.get('crawlers', [])
        if len(crawlers) == 0:
            return jsonify({"success": False, "message": "找不到任何活動中的爬蟲設定"}), 404
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/<int:crawler_id>/toggle', methods=['POST'])
def toggle_crawler_status(crawler_id):
    """切換爬蟲活躍狀態"""
    try:
        service = get_crawlers_service()
        result = service.toggle_crawler_status(crawler_id)
        
        if not result.get('success'):
            return jsonify(result), 404
        
        crawler = result.get('crawler')
        if crawler is None:
            return jsonify({"success": False, "message": "找不到爬蟲資料"}), 404
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/name/<string:name>', methods=['GET'])
def get_crawlers_by_name(name):
    """根據名稱模糊查詢爬蟲設定"""
    try:
        service = get_crawlers_service()
        result = service.get_crawlers_by_name(name)
        
        if not result.get('success'):
            return jsonify(result), 400
        
        crawlers = result.get('crawlers', [])
        if len(crawlers) == 0:
            return jsonify({"success": False, "message": "找不到任何符合名稱的爬蟲設定"}), 404
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/type/<string:crawler_type>', methods=['GET'])
def get_crawlers_by_type(crawler_type):
    """根據爬蟲類型查找爬蟲"""
    try:
        service = get_crawlers_service()
        result = service.get_crawlers_by_type(crawler_type)
        
        if not result.get('success'):
            return jsonify(result), 400
        
        crawlers = result.get('crawlers', [])
        if len(crawlers) == 0:
            return jsonify({"success": False, "message": "找不到任何符合類型的爬蟲設定"}), 404
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/target/<string:target_pattern>', methods=['GET'])
def get_crawlers_by_target(target_pattern):
    """根據爬取目標模糊查詢爬蟲"""
    try:
        service = get_crawlers_service()
        result = service.get_crawlers_by_target(target_pattern)
        
        if not result.get('success'):
            return jsonify(result), 400
        
        crawlers = result.get('crawlers', [])
        if len(crawlers) == 0:
            return jsonify({"success": False, "message": "找不到任何符合目標的爬蟲設定"}), 404
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/statistics', methods=['GET'])
def get_crawler_statistics():
    """獲取爬蟲統計信息"""
    try:
        service = get_crawlers_service()
        result = service.get_crawler_statistics()
        
        if not result.get('success'):
            return jsonify(result), 400
        
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/exact-name/<string:crawler_name>', methods=['GET'])
def get_crawler_by_exact_name(crawler_name):
    """根據爬蟲名稱精確查詢"""
    try:
        service = get_crawlers_service()
        result = service.get_crawler_by_exact_name(crawler_name)
        
        if not result.get('success'):
            return jsonify(result), 404
        
        crawler = result.get('crawler')
        if crawler is None:
            return jsonify({"success": False, "message": "找不到爬蟲資料"}), 404
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/create-or-update', methods=['POST'])
def create_or_update_crawler():
    """創建或更新爬蟲設定"""
    service = get_crawlers_service()
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "無效的 JSON"}), 400

        # 判斷是更新還是創建操作
        is_update = 'id' in data and data['id']
        
        # --- API 層驗證 ---
 
        validated_result = _setup_validate_crawler_data(data, service, is_update=is_update)
        if not validated_result['success']:
            return jsonify(validated_result), 400

        # --- 驗證結束 ---

        # 將驗證後的資料傳遞給 service
        result = service.create_or_update_crawler(validated_result['data'])

        if not result.get('success'):
            return jsonify(result), 400

        crawler = result.get('crawler')
        status_code = 201 if not is_update else 200
        if crawler is None:
            return jsonify({"success": False, "message": "找不到爬蟲資料"}), 404
        return jsonify(result), status_code
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/batch-toggle', methods=['POST'])
def batch_toggle_crawler_status():
    """批量設置爬蟲的活躍狀態"""
    try:
        service = get_crawlers_service()
        data = request.get_json()
        
        if not data or 'crawler_ids' not in data or 'active_status' not in data:
            return jsonify({"success": False, "message": "缺少必要參數"}), 400
        
        crawler_ids = data.get('crawler_ids', [])
        active_status = data.get('active_status', False)
        
        result = service.batch_toggle_crawler_status(crawler_ids, active_status)
        
        if not result.get('success'):
            return jsonify(result), 400
        
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/filter', methods=['POST'])
def get_filtered_crawlers():
    """根據過濾條件獲取分頁爬蟲列表"""
    try:
        service = get_crawlers_service()
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "無效的 JSON"}), 400
        
        filter_dict = data.get('filter', {})
        page = data.get('page', 1)
        per_page = data.get('per_page', 10)
        sort_by = data.get('sort_by')
        sort_desc = data.get('sort_desc', False)
        
        result = service.get_filtered_crawlers(
            filter_dict=filter_dict,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_desc=sort_desc
        )
        
        if not result.get('success'):
            return jsonify(result), 400
        
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)
    
def _setup_validate_crawler_data(crawler_data: Dict[str, Any], service: CrawlersService, is_update: bool = False) -> Dict[str, Any]:
    """設置爬蟲資料並進行驗證
    Args:
        crawler_data: 爬蟲的設定資料
        service: 爬蟲服務實例
        is_update: 是否為更新操作，預設為False
    Returns:
        Dict[str, Any]: 驗證後的爬蟲資料
            success: 是否成功
            message: 訊息
            data: 爬蟲資料

    """
    # 驗證爬蟲資料
    return service.validate_crawler_data(crawler_data, is_update=is_update)