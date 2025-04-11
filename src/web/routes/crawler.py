from flask import Blueprint, jsonify, request, Response
from src.services.crawlers_service import CrawlersService
from src.utils.validators import validate_crawler_data_api
from src.error.handle_api_error import handle_api_error
import logging
from src.error.errors import ValidationError
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 創建藍圖
crawler_bp = Blueprint('crawlerapi', __name__, url_prefix='/api/crawlers')

def get_crawlers_service():
    """獲取爬蟲服務實例"""
    return CrawlersService()

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
        data = request.get_json()
        if not data:
            return jsonify({"error": "無效的 JSON"}), 400

        # --- API 層驗證 ---
        try:
            # 透過 Service 獲取 Repository 實例 (需要 Service 提供方法或調整可訪問性)
            # 假設 service._get_repository() 可以獲取
            crawlers_repo = service._get_repository() # 注意: 訪問保護成員可能不是最佳實踐，考慮 Service 提供 Repo 或 Validation 方法
            validated_data = validate_crawler_data_api(data, crawlers_repo, is_update=False)
        except ValidationError as e:
            # 捕獲驗證錯誤，返回 400
            return jsonify({"error": "輸入資料驗證失敗", "details": str(e)}), 400
        # --- 驗證結束 ---

        # 將驗證後的資料傳遞給 service
        result = service.create_crawler(validated_data) # Service 的 create 現在接收驗證後的資料

        if not result.get('success'):
            # Service 層可能還會拋出其他錯誤 (如資料庫操作錯誤)
            return jsonify({"error": result.get('message', '創建爬蟲設定失敗')}), 400 # 或 500

        new_crawler = result.get('crawler')
        if new_crawler is None:
            # 雖然 success=True 但沒拿到 crawler 的情況不太可能，但還是處理一下
            return jsonify({"error": "創建爬蟲後未能獲取結果"}), 500

        return jsonify(new_crawler.to_dict()), 201 # 返回 201 Created

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
            return jsonify({"error": "Not Found"}), 404
        
        crawler = result.get('crawler')
        if crawler is None:
            return jsonify({"error": "Crawler not found"}), 404
            
        return jsonify(crawler.to_dict()), 200
    except Exception as e:
        return handle_api_error(e)

@crawler_bp.route('/<int:crawler_id>', methods=['PUT'])
def update_crawler(crawler_id):
    """更新特定爬蟲設定"""
    service = get_crawlers_service()
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "無效的 JSON"}), 400

        # --- API 層驗證 ---
        try:
            crawlers_repo = service._get_repository() # 同上，獲取 Repo 實例
            validated_payload = validate_crawler_data_api(data, crawlers_repo, is_update=True)
        except ValidationError as e:
            return jsonify({"error": "輸入資料驗證失敗", "details": str(e)}), 400
        # --- 驗證結束 ---

        # 將驗證後的 payload 傳遞給 service
        result = service.update_crawler(crawler_id, validated_payload)

        if not result.get('success'):
            # 處理 Service 返回的錯誤 (例如 Not Found 或 DB Error)
            error_msg = result.get('message', f'更新爬蟲設定 {crawler_id} 失敗')
            status_code = 404 if "不存在" in error_msg else 400 # 或 500
            return jsonify({"error": error_msg}), status_code

        updated_crawler = result.get('crawler')
        if updated_crawler is None:
            return jsonify({"error": "更新爬蟲後未能獲取結果"}), 500

        return jsonify(updated_crawler.to_dict()), 200 # 返回 200 OK

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
def get_crawler_types():
    """取得可用的爬蟲類型"""
    try:
        from src.crawlers.crawler_factory import CrawlerFactory
        types = CrawlerFactory.list_available_crawlers()
        return jsonify(types), 200
    except Exception as e:
        return handle_api_error(e)
