from flask import Blueprint, jsonify, request
from src.error.handle_api_error import handle_api_error
from src.models.crawler_tasks_model import ScrapeMode
from src.models.crawler_tasks_model import TASK_ARGS_DEFAULT
from typing import Dict, Any
from src.services.crawler_task_service import CrawlerTaskService
from src.services.service_container import get_scheduler_service, get_task_executor_service, get_crawler_task_service, get_article_service

tasks_bp = Blueprint('tasks_api', __name__, url_prefix='/api/tasks')

# 排程任務相關端點
@tasks_bp.route('/scheduled', methods=['GET'])
def get_scheduled_tasks():
    try:
        service = get_crawler_task_service()
        result = service.advanced_search_tasks(**{'is_scheduled': True, 'is_active': True, 'is_auto': True})
        if not result['success']:
            return jsonify(result), 500
        return jsonify(result['tasks'].to_dict()), 200
    except Exception as e:
        return handle_api_error(e)
    
@tasks_bp.route('/scheduled', methods=['POST'])
def create_scheduled_task():
    try:
        # 獲取請求數據，可能包含額外參數
        data = request.get_json() or {}
        if len(data) == 0:
            return jsonify({"success": False, "message": "缺少任務資料"}), 400
        
        task_service = get_crawler_task_service()
        # 設置情境有關的參數-排程任務
        validated_result = _setup_validate_task_data(task_data=data, service=task_service, scrape_mode=data.get('task_args', TASK_ARGS_DEFAULT).get('scrape_mode', ScrapeMode.FULL_SCRAPE.value), is_auto=True, is_update=False)

        if not validated_result['success']:
            return jsonify(validated_result), 400

        create_task_result = task_service.create_task(validated_result['data'])
        if not create_task_result['success']:
            return jsonify(create_task_result), 500
        task = create_task_result['data']
        if task:
            scheduler = get_scheduler_service()
            scheduler_result = scheduler.add_or_update_task_to_scheduler(task)
            if not scheduler_result['success']:
                return jsonify(scheduler_result), 500
        return jsonify(create_task_result), 201
    except Exception as e:
        return handle_api_error(e)



@tasks_bp.route('/scheduled/<int:task_id>', methods=['PUT'])
def update_scheduled_task(task_id, is_active: bool = True):
    try:
        data = request.get_json() or {}
        if len(data) == 0:
            return jsonify({"success": False, "message": "缺少任務資料"}), 400
        
        service = get_crawler_task_service()
        
        # 獲取當前任務資料，以保留未更新的參數
        get_task_result = service.get_task_by_id(task_id, is_active=is_active)
        if not get_task_result['success']:
            return jsonify({"success": False, "message": "找不到任務"}), 404
        
        db_task = get_task_result['task']
        db_task_args = db_task.task_args

        new_task_args = data.get('task_args', {})

        # 將現有的 task_args 與新的合併
        for key, value in db_task_args.items():
            if key not in new_task_args:
                data['task_args'][key] = value
        
        validated_result = _setup_validate_task_data(task_data=data, service=service, scrape_mode=data.get('task_args', TASK_ARGS_DEFAULT).get('scrape_mode', ScrapeMode.FULL_SCRAPE.value), is_auto=True, is_update=True)
        if not validated_result['success']:
            return jsonify(validated_result), 400
        
        result = service.update_task(task_id, validated_result['data'])
        if not result['success']:
            return jsonify(result), 404
        scheduled_result = get_scheduler_service().add_or_update_task_to_scheduler(result['task'])
        if not scheduled_result['success']:
            return jsonify(scheduled_result), 500
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/scheduled/<int:task_id>', methods=['DELETE'])
def delete_scheduled_task(task_id):
    try:
        service = get_crawler_task_service()
        scheduler = get_scheduler_service()
        result = service.delete_task(task_id)
        if not result['success']:
            return jsonify(result), 404
        scheduled_result = scheduler.remove_task_from_scheduler(task_id)
        if not scheduled_result['success']:
            return jsonify(scheduled_result), 404
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)

# 手動任務相關端點
@tasks_bp.route('/manual/start', methods=['POST'])
def fetch_full_article_manual_task():
    """抓取完整文章的手動任務端點
        scrape_mode: FULL_SCRAPE
    Returns:
        dict: 包含任務ID、狀態和抓取模式
            success: 是否成功
            message: 任務執行結果訊息
            articles_count: 文章數量
            scrape_phase: 任務狀態
    """
    try:
        data = request.get_json() or {}
        if len(data) == 0:
            return jsonify({"success": False, "message": "缺少任務資料"}), 400
        
        task_service = get_crawler_task_service()

        # 設置情境有關的參數-手動任務+抓取完整文章
        validated_result = _setup_validate_task_data(task_data=data, service=task_service, scrape_mode=ScrapeMode.FULL_SCRAPE.value, is_auto=False, is_update=False)
        if not validated_result['success']:
            return jsonify(validated_result), 400

        #創建任務
        result = task_service.create_task(validated_result['data'])
        if not result['success']:
            return jsonify(result), 500
        task = result['task']
        task_id = task.id
        
        task_executor = get_task_executor_service()
        executor_result = task_executor.fetch_full_article(task_id, is_async=False)
        if not executor_result['success']:
            return jsonify(executor_result), 500
        
        return jsonify(executor_result), 202
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/<int:task_id>/status', methods=['GET'])
def get_task_status(task_id):
    try:
        task_executor = get_task_executor_service()
        executor_result = task_executor.get_task_status(task_id)
        if not executor_result['success']:
            return jsonify(executor_result), 404
        return jsonify(executor_result), 200
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/<int:task_id>/collect-links', methods=['POST'])
def fetch_links_manual_task():
    """抓取連結的手動任務端點(全新任務)
        scrape_mode: LINKS_ONLY
    Returns:
        dict: 包含任務ID、狀態和抓取模式
    """
    try:
        service = get_crawler_task_service()
        
        # 獲取請求數據，可能包含額外參數
        data = request.get_json() or {}
        if len(data) == 0:
            return jsonify({"success": False, "message": "缺少任務資料"}), 400
        
        #設置情境有關的參數-手動任務+只抓取連結
        validated_result = _setup_validate_task_data(task_data=data, service=service, scrape_mode=ScrapeMode.LINKS_ONLY.value, is_auto=False, is_update=False)
        if not validated_result['success']:
            return jsonify(validated_result), 400
        #創建任務
        result = service.create_task(validated_result['data'])
        if not result['success']:
            return jsonify(result), 500
        task = result['data']
        task_id = task.id

        task_executor = get_task_executor_service()
        executor_result = task_executor.collect_links_only(task_id, is_async=False)
        if not executor_result['success']:
            return jsonify(executor_result), 500
        return jsonify(executor_result), 202
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/<int:task_id>/links', methods=['GET'])
def get_unscraped_task_links(task_id):
    """獲取未抓取的連結<fetch_content_manual_task的前置作業>
        scrape_mode: LINKS_ONLY
    Returns:
        dict: 包含任務ID、狀態和抓取模式
            success: 是否成功
            message: 任務執行結果訊息
            articles: 文章列表
    """
    try:
        article_service = get_article_service()
        result = article_service.get_articles_by_task({'task_id': task_id, 'is_scraped': False, 'is_preview': True})
        if not result['success']:
            return jsonify(result), 404
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)
    
@tasks_bp.route('/manual/<int:task_id>/fetch-content', methods=['POST'])
def fetch_content_manual_task(task_id):
    """抓取內容的手動任務端點
        scrape_mode: CONTENT_ONLY

        兩種模式：
        1. get_links_by_task_id = True
            - 從資料庫根據任務ID獲取要抓取內容的文章(scrape_mode=CONTENT_ONLY時有效)
            - 需要提供 article_links 參數
        2. get_links_by_task_id = False
            - 直接使用 article_links 參數
    Returns:
        dict: 包含任務ID、狀態和抓取模式
            success: 是否成功
            message: 任務執行結果訊息
            link_count: 文章連結數量
            task_args: 任務參數
    """
    try:
        data = request.get_json() or {}
        if len(data) == 0:
            return jsonify({"success": False, "message": "缺少任務資料"}), 400
        
        task_args = data.get('task_args', TASK_ARGS_DEFAULT)

        if not task_args.get('get_links_by_task_id'):
            return jsonify({"success": False, "message": "缺少 get_links_by_task_id 參數，無法判定要從資料庫獲取文章連結還是直接使用 article_links"}), 400
        
        if task_args.get('get_links_by_task_id'):
            # 從資料庫根據任務ID獲取要抓取內容的文章(scrape_mode=CONTENT_ONLY時有效)
            article_links = get_unscraped_task_links(task_id)
            if not article_links:
                return jsonify({"success": False, "message": "沒有找到未抓取的文章"}), 404
        else:
            # 直接使用 article_links 參數
            article_links = data.get('article_links')
            if not article_links:
                return jsonify({"success": False, "message": "沒有提供文章連結"}), 400
            
        task_args['article_links'] = article_links
        data['task_args'] = task_args

        service = get_crawler_task_service()
        # 檢查任務是否存在
        get_task_result = service.get_task_by_id(task_id, is_active=True)
        if not get_task_result['success']:
            return jsonify({"success": False, "message": "找不到有效任務" + get_task_result['message']}), 404
        
        # 獲取資料庫中的任務資料
        db_task = get_task_result['task']
        db_task_args = db_task.task_args

        # 將現有的 task_args 與新的合併
        for key, value in db_task_args.items():
            if key not in data.get('task_args', {}):
                data['task_args'][key] = value
        
        validated_result = _setup_validate_task_data(task_data=data, service=service, scrape_mode=ScrapeMode.CONTENT_ONLY.value, is_auto=False, is_update=True)
        if not validated_result['success']:
            return jsonify(validated_result), 400
        
        # 更新任務
        update_result = service.update_task(task_id, validated_result['data'])
        if not update_result['success']:
            return jsonify(update_result), 404
            
        task_executor = get_task_executor_service()
        executor_result = task_executor.fetch_content_only(task_id, is_async=False)
        if not executor_result['success']:
            return jsonify(executor_result), 500
        
        return jsonify(executor_result), 202

    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/<int:task_id>/results', methods=['GET'])
def get_scraped_task_results(task_id):
    """獲取已抓取的文章結果
    Returns:
        dict: 包含任務ID、狀態和抓取模式
            success: 是否成功
            message: 任務執行結果訊息
            articles: 文章列表
    """     
    try:
        article_service = get_article_service()
        result = article_service.get_articles_by_task({'task_id': task_id, 'is_scraped': True})
        if not result['success']:
            return jsonify(result), 404
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/test', methods=['POST'])
def test_crawler():
    """測試爬蟲任務(不會有crawler_data，會直接把Crawler_id當作參數)
        新增一個測試任務，不會實際執行，只會進行驗證
        data:
            crawler_name: str
            task_args: dict
    Returns:
        dict: 包含任務ID、狀態和抓取模式
            success: 是否成功
            message: 任務執行結果訊息
            articles: 文章列表
    """
    try:
        data = request.get_json()

        if len(data) == 0:
            return jsonify({"success": False, "message": "缺少任務資料或爬蟲資料"}), 400

        service = get_crawler_task_service() # 獲取 service 實例

        #設置情境有關的參數-手動任務+只抓取連結
        validated_result = _setup_validate_task_data(task_data=data, service=service, scrape_mode=ScrapeMode.LINKS_ONLY.value, is_auto=False, is_update=False)
        if not validated_result['success']:
            return jsonify(validated_result), 400

        task_executor = get_task_executor_service()
        executor_result = task_executor.test_crawler(data['crawler_name'], validated_result['data'])
        return jsonify(executor_result), 200
    except Exception as e:
        # 捕獲其他意外錯誤
        return handle_api_error(e)

# 通用任務端點
@tasks_bp.route('/<int:task_id>/cancel', methods=['POST'])
def cancel_task(task_id):
    try:
        task_executor = get_task_executor_service()
        result = task_executor.cancel_task(task_id)
        if not result['success']:
            return jsonify(result), 404
        return jsonify(result), 202
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/<int:task_id>/history', methods=['GET'])
def get_task_history(task_id):
    try:
        service = get_crawler_task_service()
        result = service.get_task_history(task_id)
        if not result['success']:
            return jsonify(result), 404
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e) 
    

def _setup_validate_task_data(task_data: Dict[str, Any], service: CrawlerTaskService, scrape_mode: str, is_auto: bool, is_update: bool = False) -> Dict[str, Any]:
    
    """設置任務資料
    
    Args:
        task_data: 任務資料
        service: 任務服務
        scrape_mode: 抓取模式
        is_auto: 是否自動任務
        is_update: 是否為更新操作
    Returns:
        Dict[str, Any]: 驗證後的任務資料
            success: 是否成功
            message: 訊息
            data: 任務資料
    """
    if not task_data.get('task_args'):
        task_data['task_args'] = TASK_ARGS_DEFAULT
    task_data['scrape_mode'] = scrape_mode
    # 設置為手動/自動任務
    task_data['is_auto'] = is_auto
    #驗證任務資料
    return service.validate_task_data(task_data, is_update=is_update)
