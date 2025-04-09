from flask import Blueprint, jsonify, request
from src.services.crawlers_service import CrawlersService
from src.utils.schema_utils import validate_crawler_config
from src.error.handle_api_error import handle_api_error

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
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        errors = validate_crawler_config(data)
        if errors:
            return jsonify({"errors": errors}), 400
        
        service = get_crawlers_service()
        result = service.create_crawler(data)
        
        if not result.get('success'):
            return jsonify({"error": result.get('message')}), 400
        
        new_crawler = result.get('crawler')
        if new_crawler is None:
            return jsonify({"error": "Failed to create crawler"}), 500
            
        return jsonify(new_crawler.to_dict()), 201
    except Exception as e:
        return handle_api_error(e)

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
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        
        errors = validate_crawler_config(data, is_update=True)
        if errors:
            return jsonify({"errors": errors}), 400
        
        service = get_crawlers_service()
        result = service.update_crawler(crawler_id, data)
        
        if not result.get('success'):
            return jsonify({"error": "Not Found"}), 404
        
        updated = result.get('crawler')
        if updated is None:
            return jsonify({"error": "Failed to update crawler"}), 500
            
        return jsonify(updated.to_dict()), 200
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
