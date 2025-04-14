from flask import Blueprint, jsonify, request
from src.services.crawler_task_service import CrawlerTaskService
from src.services.scheduler_service import SchedulerService
from src.services.article_service import ArticleService
from src.error.handle_api_error import handle_api_error
import threading
from src.models.crawler_tasks_model import ScrapeMode
from src.error.errors import ValidationError
from src.utils.model_utils import validate_positive_int, validate_boolean
from src.models.crawler_tasks_model import TASK_ARGS_DEFAULT
from typing import Dict, Any
tasks_bp = Blueprint('tasks_api', __name__, url_prefix='/api/tasks')

def get_task_service():
    return CrawlerTaskService()

def get_scheduler_service():
    return SchedulerService()

def get_article_service():
    return ArticleService()


def run_fetch_full_article_task_thread(task_id):
    """執行完整文章的背景執行緒"""
    service = get_task_service()
    service.fetch_full_article(task_id)

def run_fetch_content_thread(task_id):
    """執行抓取內容的背景執行緒"""
    service = get_task_service()
    service.fetch_content_only(task_id)

def run_collect_links_thread(task_id):
    """執行收集文章連結的背景執行緒"""
    service = get_task_service()
    service.collect_links_only(task_id)

def run_test_crawler_thread(task_id):
    """執行測試爬蟲的背景執行緒"""
    service = get_task_service()
    service.test_crawler(task_id)

# 排程任務相關端點
@tasks_bp.route('/scheduled', methods=['GET'])
def get_scheduled_tasks():
    try:
        service = get_task_service()
        result = service.get_all_tasks({'is_scheduled': True})
        if not result['success']:
            return jsonify({"error": result['message']}), 500
        return jsonify(result['tasks'].to_dict()), 200
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/scheduled', methods=['POST'])
def create_scheduled_task():
    try:
        data = request.get_json()
        if len(data) == 0:
            return jsonify({"error": "缺少任務資料"}), 400
        
        service = get_task_service()
        # 設置情境有關的參數-排程任務
        validated_data = _setup_validate_task_data(task_data=data, service=service, scrape_mode=data.get('task_args', TASK_ARGS_DEFAULT).get('scrape_mode', ScrapeMode.FULL_SCRAPE.value), is_auto=True, is_update=False)

        scheduler = get_scheduler_service()
        result = service.create_task(validated_data)
        if not result['success']:
            return jsonify({"error": result['message']}), 5
        task = result['task']
        if task:
            scheduler._schedule_task(task)
        return jsonify({"task": task.to_dict()}), 201
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/scheduled/<int:task_id>', methods=['GET'])
def get_scheduled_task(task_id, is_active: bool = True):
    try:
        service = get_task_service()
        result = service.get_task_by_id(task_id, is_active=is_active)
        if not result['success']:
            return jsonify({"error": result['message']}), 404
        return jsonify(result['task'].to_dict()), 200
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/scheduled/<int:task_id>', methods=['PUT'])
def update_scheduled_task(task_id, is_active: bool = True):
    try:
        data = request.get_json()
        service = get_task_service()
        
        # 獲取當前任務資料，以保留未更新的參數
        get_task_result = service.get_task_by_id(task_id, is_active=is_active)
        if not get_task_result['success']:
            return jsonify({"error": "找不到任務"}), 404
        
        db_task = get_task_result['task']
        db_task_args = db_task.task_args

        # 將現有的 task_args 與新的合併
        for key, value in db_task_args.items():
            if key not in data.task_args:
                data['task_args'][key] = value
        
        validated_data = _setup_validate_task_data(task_data=data, service=service, scrape_mode=data.get('task_args', TASK_ARGS_DEFAULT).get('scrape_mode', ScrapeMode.FULL_SCRAPE.value), is_auto=True, is_update=True)
        
 
        scheduler = get_scheduler_service()
        result = service.update_task(task_id, validated_data)
        if not result['success']:
            return jsonify({"error": result['message']}), 404
        scheduler._schedule_task(result['task'])
        return jsonify(result['task'].to_dict()), 200
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/scheduled/<int:task_id>', methods=['DELETE'])
def delete_scheduled_task(task_id):
    try:
        service = get_task_service()
        scheduler = get_scheduler_service()
        result = service.delete_task(task_id)
        if not result['success']:
            return jsonify({"error": result['message']}), 404
        scheduler.cron_scheduler.remove_job(f"task_{task_id}")
        return jsonify({"message": "Deleted"}), 200
    except Exception as e:
        return handle_api_error(e)

# 手動任務相關端點
@tasks_bp.route('/manual/start', methods=['POST'])
def fetch_full_article_manual_task():
    """抓取完整文章的手動任務端點
        scrape_mode: FULL_SCRAPE
    Returns:
        dict: 包含任務ID、狀態和抓取模式
    """
    try:
        data = request.get_json()
        if len(data) == 0:
            return jsonify({"error": "缺少任務資料"}), 400
        
        task_service = get_task_service()

        # 設置情境有關的參數-手動任務+抓取完整文章
        validated_data = _setup_validate_task_data(task_data=data, service=task_service, scrape_mode=ScrapeMode.FULL_SCRAPE.value, is_auto=False, is_update=False)

        #創建任務
        result = task_service.create_task(validated_data)
        if not result['success']:
            return jsonify({"error": result['message']}), 500
        task = result['task']
        task_id = task.id
        
        thread = threading.Thread(target=run_fetch_full_article_task_thread, args=(task_id))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "task": task.to_dict(), 
            "status": "pending", 
            "scrape_mode": data['scrape_mode']
        }), 202
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/<int:task_id>/status', methods=['GET'])
def get_scrape_phase(task_id):
    try:
        service = get_task_service()
        result = service.get_scrape_phase(task_id)
        if not result['success']:
            return jsonify({"error": result['message']}), 404
        return jsonify(result), 200
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
        service = get_task_service()
        
        # 獲取請求數據，可能包含額外參數
        data = request.get_json() or {}
        if len(data) == 0:
            return jsonify({"error": "缺少任務資料"}), 400
        
        #設置情境有關的參數-手動任務+只抓取連結
        validated_data = _setup_validate_task_data(task_data=data, service=service, scrape_mode=ScrapeMode.LINKS_ONLY.value, is_auto=False, is_update=False)
        #創建任務
        result = service.create_task(validated_data)
        if not result['success']:
            return jsonify({"error": result['message']}), 500
        task = result['task']
        task_id = task.id

            
        thread = threading.Thread(target=run_collect_links_thread, args=(task_id,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "message": "Link collection initiated", 
            "scrape_mode": ScrapeMode.LINKS_ONLY.value,
            "task": task.to_dict()
        }), 202
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/<int:task_id>/links', methods=['GET'])
def get_unscraped_task_links(task_id):
    """獲取未抓取的連結<fetch_content_manual_task的前置作業>
        scrape_mode: LINKS_ONLY
    Returns:
        dict: 包含任務ID、狀態和抓取模式
    """
    try:
        article_service = get_article_service()
        result = article_service.get_articles_by_task({'task_id': task_id, 'scraped': False, 'preview': True})
        if not result['success']:
            return jsonify({"error": result['message']}), 404
        return jsonify(result['articles']), 200
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
    """
    try:
        data = request.get_json()
        if len(data) == 0:
            return jsonify({"error": "缺少任務資料"}), 400
        
        task_args = data.get('task_args', TASK_ARGS_DEFAULT)

        if not task_args.get('get_links_by_task_id'):
            return jsonify({"error": "缺少 get_links_by_task_id 參數，無法判定要從資料庫獲取文章連結還是直接使用 article_links"}), 400
        
        if task_args.get('get_links_by_task_id'):
            # 從資料庫根據任務ID獲取要抓取內容的文章(scrape_mode=CONTENT_ONLY時有效)
            article_links = get_unscraped_task_links(task_id)
            if not article_links:
                return jsonify({"error": "沒有找到未抓取的文章"}), 404
        else:
            # 直接使用 article_links 參數
            article_links = data.get('article_links')
            if not article_links:
                return jsonify({"error": "沒有提供文章連結"}), 400
            
        task_args['article_links'] = article_links
        data['task_args'] = task_args

        service = get_task_service()
        # 檢查任務是否存在
        get_task_result = service.get_task_by_id(task_id, is_active=True)
        if not get_task_result['success']:
            return jsonify({"error": "找不到有效任務" + get_task_result['message']}), 404
        
        # 獲取資料庫中的任務資料
        db_task = get_task_result['task']
        db_task_args = db_task.task_args

        # 將現有的 task_args 與新的合併
        for key, value in db_task_args.items():
            if key not in data.task_args:
                data['task_args'][key] = value
        
        validated_data = _setup_validate_task_data(task_data=data, service=service, scrape_mode=ScrapeMode.CONTENT_ONLY.value, is_auto=False, is_update=True)
        
        # 更新任務
        service.update_task(task_id, validated_data)
            
        thread = threading.Thread(target=run_fetch_content_thread, args=(task_id))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "message": "Content fetching initiated", 
            "scrape_mode": ScrapeMode.CONTENT_ONLY.value,
            "link_count": len(article_links),
            "task_args": validated_data.get('task_args') # 返回合併後的 task_args
        }), 202
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/<int:task_id>/results', methods=['GET'])
def get_scraped_task_results(task_id):
    """獲取已抓取的文章結果
    Returns:
        dict: 包含任務ID、狀態和抓取模式
    """     
    try:
        article_service = get_article_service()
        result = article_service.get_articles_by_task({'task_id': task_id, 'scraped': True})
        if not result['success']:
            return jsonify({"error": result['message']}), 404
        return jsonify(result['articles']), 200
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/test', methods=['POST'])
def test_crawler():
    """測試爬蟲任務(不會有crawler_data，會直接把Crawler_id當作參數)
        新增一個測試任務，不會實際執行，只會進行驗證
    Returns:
        dict: 包含任務ID、狀態和抓取模式
    """
    try:
        data = request.get_json()

        if len(data) == 0:
            return jsonify({"error": "缺少任務資料或爬蟲資料"}), 400

        service = get_task_service() # 獲取 service 實例

        #設置情境有關的參數-手動任務+只抓取連結
        validated_data = _setup_validate_task_data(task_data=data, service=service, scrape_mode=ScrapeMode.LINKS_ONLY.value, is_auto=False, is_update=False)


        result = service.test_crawler(validated_data)
        return jsonify(result), 200
    except Exception as e:
        # 捕獲其他意外錯誤
        return handle_api_error(e)

# 通用任務端點
@tasks_bp.route('/<int:task_id>/cancel', methods=['POST'])
def cancel_task(task_id):
    try:
        service = get_task_service()
        result = service.toggle_active_status(task_id)
        if not result['success']:
            return jsonify({"error": result['message']}), 404
        return jsonify({"message": "Cancellation requested"}), 202
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/<int:task_id>/history', methods=['GET'])
def get_task_history(task_id):
    try:
        service = get_task_service()
        result = service.get_task_history(task_id)
        if not result['success']:
            return jsonify({"error": result['message']}), 404
        return jsonify(result['history']), 200
    except Exception as e:
        return handle_api_error(e) 
    

def _setup_validate_task_data(task_data: Dict[str, Any], service: CrawlerTaskService, scrape_mode: str, is_auto: bool, is_update: bool = False) -> Dict[str, Any]:
    """設置任務資料
    """
    if not task_data.get('task_args'):
        task_data['task_args'] = TASK_ARGS_DEFAULT
    task_data['scrape_mode'] = scrape_mode
    # 設置為手動/自動任務
    task_data['is_auto'] = is_auto
    #驗證任務資料
    service.validate_task_data(task_data, is_update=is_update)
    return task_data
