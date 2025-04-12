from flask import Blueprint, jsonify, request
from src.services.crawler_task_service import CrawlerTaskService
from src.services.scheduler_service import SchedulerService
from src.services.article_service import ArticleService
from src.error.handle_api_error import handle_api_error
from src.utils.api_validators import validate_task_data_api
import threading
from src.models.crawler_tasks_model import ScrapeMode

tasks_bp = Blueprint('tasks_api', __name__, url_prefix='/api/tasks')

def get_task_service():
    return CrawlerTaskService()

def get_scheduler_service():
    return SchedulerService()

def get_article_service():
    return ArticleService()


def run_manual_task_thread(task_id, task_args):
    """執行手動任務的背景執行緒"""
    service = get_task_service()
    service.run_task(task_id, task_args)


def run_fetch_content_thread(task_id, link_ids):
    """執行抓取內容的背景執行緒"""
    service = get_task_service()
    # 設定抓取模式為僅抓取內容
    task_args = {'article_ids': link_ids, 'scrape_mode': ScrapeMode.CONTENT_ONLY.value}
    service.fetch_article_content(task_id, link_ids)

def run_collect_links_thread(task_id):
    """執行收集文章連結的背景執行緒"""
    service = get_task_service()
    service.collect_article_links(task_id)

# 排程任務相關端點
@tasks_bp.route('/scheduled', methods=['GET'])
def get_scheduled_tasks():
    try:
        service = get_task_service()
        result = service.get_all_tasks({'is_scheduled': True})
        if not result['success']:
            return jsonify({"error": result['message']}), 500
        return jsonify(result['tasks']), 200
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/scheduled', methods=['POST'])
def create_scheduled_task():
    try:
        data = request.get_json()
        service = get_task_service()
        
        # 確保必要的排程任務參數存在
        if 'task_args' not in data:
            data['task_args'] = {}
        task_args = data.get('task_args', {})
        
        # 確保 is_scheduled 為 True (相當於 is_auto)
        data['is_auto'] = True
        
        # 確保 cron_expression 存在
        if 'cron_expression' not in data:
            return jsonify({"error": "排程任務必須提供 cron_expression"}), 400
        
        # 處理抓取模式
        if 'scrape_mode' in task_args:
            # 確保scrape_mode是字符串形式
            if isinstance(task_args['scrape_mode'], str):
                # 驗證scrape_mode是否為有效的枚舉值
                try:
                    ScrapeMode(task_args['scrape_mode'])
                except ValueError:
                    return jsonify({"error": f"無效的抓取模式: {task_args['scrape_mode']}"}), 400
            else:
                return jsonify({"error": "抓取模式必須為字符串"}), 400
        else:
            # 默認設置為完整抓取模式
            task_args['scrape_mode'] = ScrapeMode.FULL_SCRAPE.value
        
        # 設置其他必要參數
        if 'ai_only' not in data:
            data['ai_only'] = task_args.get('ai_only', False)
        
        if 'max_retries' not in data:
            data['max_retries'] = task_args.get('max_retries', 3)
        
        # 處理爬蟲執行的必要參數
        if 'max_pages' not in task_args:
            task_args['max_pages'] = 10  # 默認值
            
        if 'num_articles' not in task_args:
            task_args['num_articles'] = 100  # 默認值
            
        if 'min_keywords' not in task_args:
            task_args['min_keywords'] = 1  # 默認值
            
        if 'retry_delay' not in task_args:
            task_args['retry_delay'] = 2.0  # 默認值
            
        if 'timeout' not in task_args:
            task_args['timeout'] = 30  # 默認值，單位秒
            
        if 'save_to_csv' not in task_args:
            task_args['save_to_csv'] = True  # 默認值
            
        if 'save_to_database' not in task_args:
            task_args['save_to_database'] = True  # 默認值
            
        data['task_args'] = task_args
        
        validate_task_data_api(data, service)
        scheduler = get_scheduler_service()
        result = service.create_task(data)
        if not result['success']:
            return jsonify({"error": result['message']}), 500
        task_id = result['task_id']
        scheduler._schedule_task(service.get_task_by_id(task_id)['task'])
        return jsonify({"task_id": task_id}), 201
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/scheduled/<int:task_id>', methods=['GET'])
def get_scheduled_task(task_id):
    try:
        service = get_task_service()
        result = service.get_task_by_id(task_id)
        if not result['success']:
            return jsonify({"error": result['message']}), 404
        return jsonify(result['task']), 200
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/scheduled/<int:task_id>', methods=['PUT'])
def update_scheduled_task(task_id):
    try:
        data = request.get_json()
        service = get_task_service()
        
        # 獲取當前任務資料，以保留未更新的參數
        current_task = service.get_task_by_id(task_id)
        if not current_task['success']:
            return jsonify({"error": "找不到任務"}), 404
        
        current_task_data = current_task['task']
        current_task_args = current_task_data.get('task_args', {})
        
        # 確保 task_args 存在
        if 'task_args' not in data:
            data['task_args'] = {}
        task_args = data.get('task_args', {})
        
        # 將現有的 task_args 與新的合併
        for key, value in current_task_args.items():
            if key not in task_args:
                task_args[key] = value
        
        # 確保 is_scheduled 為 True (相當於 is_auto)
        data['is_auto'] = True
        
        # 檢查 cron_expression 是否存在，如果不存在則使用當前值
        if 'cron_expression' not in data:
            data['cron_expression'] = current_task_data.get('cron_expression')
        
        # 處理抓取模式
        if 'scrape_mode' in task_args:
            # 確保scrape_mode是字符串形式
            if isinstance(task_args['scrape_mode'], str):
                # 驗證scrape_mode是否為有效的枚舉值
                try:
                    ScrapeMode(task_args['scrape_mode'])
                except ValueError:
                    return jsonify({"error": f"無效的抓取模式: {task_args['scrape_mode']}"}), 400
            else:
                return jsonify({"error": "抓取模式必須為字符串"}), 400
        
        # 確保其他參數存在或使用當前值
        if 'ai_only' not in data:
            data['ai_only'] = current_task_data.get('ai_only', False)
        
        if 'max_retries' not in data:
            data['max_retries'] = current_task_data.get('max_retries', 3)
        
        # 更新 task_args
        data['task_args'] = task_args
        
        validate_task_data_api(data, service, is_update=True)
        scheduler = get_scheduler_service()
        result = service.update_task(task_id, data)
        if not result['success']:
            return jsonify({"error": result['message']}), 404
        scheduler._schedule_task(result['task'])
        return jsonify(result['task']), 200
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
def start_manual_task():
    try:
        data = request.get_json()
        task_service = get_task_service()
        
        # 確保 task_args 存在
        if 'task_args' not in data:
            data['task_args'] = {}
        task_args = data.get('task_args', {})
        
        # 處理任務參數中的抓取模式
        if 'scrape_mode' in task_args:
            # 確保scrape_mode是字符串形式
            if isinstance(task_args['scrape_mode'], str):
                # 驗證scrape_mode是否為有效的枚舉值
                try:
                    ScrapeMode(task_args['scrape_mode'])
                except ValueError:
                    return jsonify({"error": f"無效的抓取模式: {task_args['scrape_mode']}"}), 400
            else:
                return jsonify({"error": "抓取模式必須為字符串"}), 400
        else:
            # 默認設置為完整抓取模式
            task_args['scrape_mode'] = ScrapeMode.FULL_SCRAPE.value
            
        # 確保其他重要的爬蟲執行參數也被處理
        if 'ai_only' not in data:
            data['ai_only'] = task_args.get('ai_only', False)
        
        if 'max_retries' not in data:
            data['max_retries'] = task_args.get('max_retries', 3)
        
        # 處理爬蟲執行的必要參數
        if 'max_pages' not in task_args:
            task_args['max_pages'] = 10  # 默認值
            
        if 'num_articles' not in task_args:
            task_args['num_articles'] = 100  # 默認值
            
        if 'min_keywords' not in task_args:
            task_args['min_keywords'] = 1  # 默認值
            
        if 'retry_delay' not in task_args:
            task_args['retry_delay'] = 2.0  # 默認值
            
        if 'timeout' not in task_args:
            task_args['timeout'] = 30  # 默認值，單位秒
            
        if 'save_to_csv' not in task_args:
            task_args['save_to_csv'] = True  # 默認值
            
        if 'save_to_database' not in task_args:
            task_args['save_to_database'] = True  # 默認值
            
        # 根據抓取模式處理相關參數
        if task_args.get('scrape_mode') == ScrapeMode.CONTENT_ONLY.value:
            if 'get_links_by_task_id' not in task_args:
                task_args['get_links_by_task_id'] = True
                
            if not task_args.get('get_links_by_task_id'):
                if 'article_ids' not in task_args and 'article_links' not in task_args:
                    return jsonify({"error": "內容抓取模式需要提供 article_ids 或 article_links"}), 400
        
        data['task_args'] = task_args
            
        validate_task_data_api(data, task_service)
        result = task_service.create_task(data)
        if not result['success']:
            return jsonify({"error": result['message']}), 500
        task_id = result['task_id']
        
        thread = threading.Thread(target=run_manual_task_thread, args=(task_id, task_args))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "task_id": task_id, 
            "status": "pending", 
            "scrape_mode": task_args['scrape_mode']
        }), 202
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/<int:task_id>/status', methods=['GET'])
def get_manual_task_status(task_id):
    try:
        service = get_task_service()
        result = service.get_task_status(task_id)
        if not result['success']:
            return jsonify({"error": result['message']}), 404
        return jsonify(result['status']), 200
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/<int:task_id>/links', methods=['GET'])
def get_manual_task_links(task_id):
    try:
        article_service = get_article_service()
        result = article_service.get_articles_by_task({'task_id': task_id, 'scraped': False, 'preview': True})
        if not result['success']:
            return jsonify({"error": result['message']}), 404
        return jsonify(result['articles']), 200
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/<int:task_id>/collect-links', methods=['POST'])
def collect_manual_task_links(task_id):
    try:
        service = get_task_service()
        # 檢查任務是否存在
        task_check = service.get_task_by_id(task_id)
        if not task_check['success']:
            return jsonify({"error": task_check['message']}), 404
        
        # 獲取請求數據，可能包含額外參數
        data = request.get_json() or {}
        task_args = data.get('task_args', {})
        
        # 獲取現有任務資料
        current_task = task_check['task']
        current_task_args = current_task.get('task_args', {})
        
        # 合併現有參數和新參數
        for key, value in task_args.items():
            current_task_args[key] = value
        
        # 設置任務模式為僅抓取連結
        update_data = {
            'scrape_mode': ScrapeMode.LINKS_ONLY.value,
            'task_args': current_task_args
        }
        
        # 更新任務
        service.update_task(task_id, update_data)
            
        thread = threading.Thread(target=run_collect_links_thread, args=(task_id,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "message": "Link collection initiated", 
            "scrape_mode": ScrapeMode.LINKS_ONLY.value,
            "task_args": current_task_args
        }), 202
    except Exception as e:
        return handle_api_error(e)
    
@tasks_bp.route('/manual/<int:task_id>/fetch-content', methods=['POST'])
def fetch_manual_task_content(task_id):
    try:
        data = request.get_json()
        link_ids = data.get('link_ids')
        if not link_ids:
            return jsonify({"error": "Missing link_ids"}), 400
        
        # 獲取其他任務參數
        task_args = data.get('task_args', {})
        
        service = get_task_service()
        # 檢查任務是否存在
        task_check = service.get_task_by_id(task_id)
        if not task_check['success']:
            return jsonify({"error": task_check['message']}), 404
        
        # 獲取現有任務資料
        current_task = task_check['task']
        current_task_args = current_task.get('task_args', {})
        
        # 合併現有參數和新參數
        for key, value in task_args.items():
            current_task_args[key] = value
        
        # 設置必要的參數
        current_task_args['article_ids'] = link_ids
        current_task_args['get_links_by_task_id'] = False
        
        # 設置任務模式為僅抓取內容
        update_data = {
            'scrape_mode': ScrapeMode.CONTENT_ONLY.value,
            'task_args': current_task_args
        }
        
        # 更新任務
        service.update_task(task_id, update_data)
            
        thread = threading.Thread(target=run_fetch_content_thread, args=(task_id, link_ids))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "message": "Content fetching initiated", 
            "scrape_mode": ScrapeMode.CONTENT_ONLY.value,
            "link_count": len(link_ids),
            "task_args": current_task_args
        }), 202
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/<int:task_id>/results', methods=['GET'])
def get_manual_task_results(task_id):
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
    try:
        data = request.get_json()
        task_data = data.get('task_data', {})
        crawler_data = data.get('crawler_data', {})
        
        # 確保 task_args 存在
        if 'task_args' not in task_data:
            task_data['task_args'] = {}
        task_args = task_data.get('task_args', {})
        
        # 處理任務參數中的抓取模式
        if 'scrape_mode' in task_args:
            # 確保scrape_mode是字符串形式
            if isinstance(task_args['scrape_mode'], str):
                # 驗證scrape_mode是否為有效的枚舉值
                try:
                    ScrapeMode(task_args['scrape_mode'])
                except ValueError:
                    return jsonify({"error": f"無效的抓取模式: {task_args['scrape_mode']}"}), 400
            else:
                return jsonify({"error": "抓取模式必須為字符串"}), 400
        else:
            # 測試時默認設置為僅抓取連結模式
            task_args['scrape_mode'] = ScrapeMode.LINKS_ONLY.value
            
        # 設置其他必要參數
        if 'ai_only' not in task_data:
            task_data['ai_only'] = task_args.get('ai_only', False)
        
        if 'max_retries' not in task_data:
            task_data['max_retries'] = task_args.get('max_retries', 3)
        
        # 處理爬蟲執行的必要參數，測試時可以使用較小的數值
        if 'max_pages' not in task_args:
            task_args['max_pages'] = 2  # 測試用較小值
            
        if 'num_articles' not in task_args:
            task_args['num_articles'] = 10  # 測試用較小值
            
        if 'min_keywords' not in task_args:
            task_args['min_keywords'] = 1
            
        if 'retry_delay' not in task_args:
            task_args['retry_delay'] = 1.0  # 測試用較小值
            
        if 'timeout' not in task_args:
            task_args['timeout'] = 15  # 測試用較小值
            
        if 'save_to_csv' not in task_args:
            task_args['save_to_csv'] = False  # 測試時不需要保存到CSV
            
        if 'save_to_database' not in task_args:
            task_args['save_to_database'] = False  # 測試時不需要保存到資料庫
        
        task_data['task_args'] = task_args
        
        service = get_task_service()
        result = service.test_crawler_task(crawler_data, task_data)
        return jsonify(result), 200
    except Exception as e:
        return handle_api_error(e)

# 通用任務端點
@tasks_bp.route('/<int:task_id>/cancel', methods=['POST'])
def cancel_task(task_id):
    try:
        service = get_task_service()
        result = service.cancel_task(task_id)
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