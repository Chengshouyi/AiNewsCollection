from flask import Blueprint, jsonify, request
from src.services.crawler_task_service import CrawlerTaskService
from src.services.scheduler_service import SchedulerService
from src.services.article_service import ArticleService
from src.error.handle_api_error import handle_api_error
from src.utils.api_validators import validate_task_data_api
import threading
from src.models.crawler_tasks_model import ScrapeMode
from src.error.errors import ValidationError
from src.utils.model_utils import validate_positive_int, validate_boolean

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

        # 確保 task_args 存在
        if 'task_args' not in data:
            data['task_args'] = {}
        task_args = data.get('task_args', {})

        # 確保 is_scheduled 為 True (相當於 is_auto)
        data['is_auto'] = True

        # 確保 cron_expression 存在
        if 'cron_expression' not in data:
            return jsonify({"error": "排程任務必須提供 cron_expression"}), 400

        # 處理 scrape_mode (移出 task_args 判斷)
        if 'scrape_mode' in data:
            # 確保 scrape_mode 是字符串形式
            if isinstance(data['scrape_mode'], str):
                # 驗證 scrape_mode 是否為有效的枚舉值
                try:
                    ScrapeMode(data['scrape_mode'])
                except ValueError:
                    return jsonify({"error": f"無效的抓取模式: {data['scrape_mode']}"}), 400
            else:
                # 如果前端可能傳遞枚舉對象，這裡可以不做處理或添加相應邏輯
                # 但通常API接口傳遞的是字符串
                return jsonify({"error": "抓取模式必須為字符串"}), 400
        else:
            # 默認設置為完整抓取模式 (在 data 層級)
            data['scrape_mode'] = ScrapeMode.FULL_SCRAPE.value

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
            
        # 重新賦值 task_args (如果上面有修改)
        data['task_args'] = task_args

        validate_task_data_api(data, service)
        scheduler = get_scheduler_service()
        result = service.create_task(data)
        if not result['success']:
            return jsonify({"error": result['message']}), 500
        task_id = result['task_id']
        task_info = service.get_task_by_id(task_id)
        if task_info['success']:
            scheduler._schedule_task(task_info['task'])
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
        
        # 確保 task_args 存在於傳入的 data 中
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
        
        # 處理 scrape_mode (移出 task_args 判斷)
        if 'scrape_mode' in data:
            # 確保 scrape_mode 是字符串形式
            if isinstance(data['scrape_mode'], str):
                # 驗證 scrape_mode 是否為有效的枚舉值
                try:
                    ScrapeMode(data['scrape_mode'])
                except ValueError:
                    return jsonify({"error": f"無效的抓取模式: {data['scrape_mode']}"}), 400
            else:
                return jsonify({"error": "抓取模式必須為字符串"}), 400
        else:
             # 如果沒提供，則保留原來的值
             data['scrape_mode'] = current_task_data.get('scrape_mode')
        
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
        
        # 處理 scrape_mode 
        if 'scrape_mode' in data:
            # 確保 scrape_mode 是字符串形式
            if isinstance(data['scrape_mode'], str):
                # 驗證 scrape_mode 是否為有效的枚舉值
                try:
                    current_scrape_mode = ScrapeMode(data['scrape_mode']) # 轉換以供後續使用
                except ValueError:
                    return jsonify({"error": f"無效的抓取模式: {data['scrape_mode']}"}), 400
            else:
                return jsonify({"error": "抓取模式必須為字符串"}), 400
        else:
            # 默認設置為完整抓取模式 (在 data 層級)
            data['scrape_mode'] = ScrapeMode.FULL_SCRAPE.value
            current_scrape_mode = ScrapeMode.FULL_SCRAPE
        
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
        if data.get('scrape_mode') == ScrapeMode.CONTENT_ONLY.value:
            if 'get_links_by_task_id' not in task_args:
                task_args['get_links_by_task_id'] = True
                
            if not task_args.get('get_links_by_task_id'):
                if 'article_ids' not in task_args and 'article_links' not in task_args:
                    return jsonify({"error": "內容抓取模式需要提供 article_ids 或 article_links"}), 400
        
        # 更新 task_args
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
            "scrape_mode": data['scrape_mode']
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
        
        # 準備更新資料
        update_data = {
            'scrape_mode': ScrapeMode.LINKS_ONLY.value,
            'task_args': current_task_args
            # 注意：這裡可能需要包含其他必要的欄位以通過驗證，
            # 或者調整 validate_task_data_api 以適應部分更新。
            # 為了簡單起見，我們先假設僅更新這兩者可以通過驗證。
            # 如果 validate_task_data_api 強制要求其他欄位，則需要從 current_task 複製。
            # 例如: 'task_name': current_task.get('task_name'), 'crawler_id': current_task.get('crawler_id')
        }

        # 加入驗證步驟 (is_update=True)
        validate_task_data_api(update_data, service, is_update=True)
        
        # 更新任務
        service.update_task(task_id, update_data)
            
        thread = threading.Thread(target=run_collect_links_thread, args=(task_id,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "message": "Link collection initiated", 
            "scrape_mode": ScrapeMode.LINKS_ONLY.value,
            "task_args": current_task_args # 返回合併後的 task_args
        }), 202
    except Exception as e:
        return handle_api_error(e)
    
@tasks_bp.route('/manual/<int:task_id>/fetch-content', methods=['POST'])
def fetch_manual_task_content(task_id):
    try:
        data = request.get_json()
        link_ids = data.get('link_ids')
        if not link_ids or not isinstance(link_ids, list): # 驗證 link_ids 是否為非空列表
            return jsonify({"error": "Missing or invalid link_ids (must be a non-empty list)"}), 400
        
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
        
        # 準備更新資料
        update_data = {
            'scrape_mode': ScrapeMode.CONTENT_ONLY.value,
            'task_args': current_task_args
            # 同上，可能需要從 current_task 複製其他欄位以通過驗證
            # 'task_name': current_task.get('task_name'), 'crawler_id': current_task.get('crawler_id')
        }

        # 加入驗證步驟 (is_update=True)
        validate_task_data_api(update_data, service, is_update=True)
        
        # 更新任務
        service.update_task(task_id, update_data)
            
        thread = threading.Thread(target=run_fetch_content_thread, args=(task_id, link_ids))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "message": "Content fetching initiated", 
            "scrape_mode": ScrapeMode.CONTENT_ONLY.value,
            "link_count": len(link_ids),
            "task_args": current_task_args # 返回合併後的 task_args
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
        service = get_task_service() # 獲取 service 實例

        # 確保 task_args 存在
        if 'task_args' not in task_data:
            task_data['task_args'] = {}
        task_args = task_data.get('task_args', {})

        # --- 開始直接在此處進行基本驗證 ---

        # 1. 驗證 scrape_mode (如果存在於 task_data 頂層)
        if 'scrape_mode' in task_data:
            try:
                if isinstance(task_data['scrape_mode'], str):
                    ScrapeMode(task_data['scrape_mode']) # 嘗試轉換字符串
                elif not isinstance(task_data['scrape_mode'], ScrapeMode):
                     # 如果不是字符串也不是 ScrapeMode 枚舉實例，則無效
                     raise ValueError("無效的 scrape_mode 類型")
            except ValueError:
                return jsonify({"error": f"無效的抓取模式: {task_data['scrape_mode']}"}), 400
        else:
            # 測試時默認設置為僅抓取連結模式 (如果未提供)
            task_data['scrape_mode'] = ScrapeMode.LINKS_ONLY.value

        # 2. 驗證 task_args 內部參數 (複製自 api_validators.py 的邏輯)
        if isinstance(task_args, dict):

            # 驗證數值類型參數
            numeric_params = ['max_pages', 'num_articles', 'min_keywords', 'timeout', 'max_retries'] # 加入 max_retries
            for param in numeric_params:
                if param in task_args:
                    try:
                        # 使用 validate_positive_int，假設這些都應為正整數
                        validate_positive_int(param)(task_args[param])
                    except Exception as e:
                         # 將 Pydantic 或其他驗證錯誤包裝成 API 可理解的錯誤
                        raise ValidationError(f"task_args.{param}: {str(e)}")

            # 驗證可為小數的數值類型參數
            float_params = ['retry_delay']
            for param in float_params:
                if param in task_args:
                     # 基礎類型和範圍檢查
                    if not isinstance(task_args[param], (int, float)) or task_args[param] <= 0:
                        raise ValidationError(f"task_args.'{param}' 必須是正數")

            # 驗證布爾類型參數
            bool_params = ['ai_only', 'save_to_csv', 'save_to_database', 'get_links_by_task_id'] # 加入 ai_only
            for param in bool_params:
                if param in task_args:
                    try:
                        validate_boolean(param)(task_args[param])
                    except Exception as e:
                        raise ValidationError(f"task_args.{param}: {str(e)}")

            # 注意：這裡省略了 CONTENT_ONLY 模式下對 article_ids/article_links 的檢查，
            # 因為 test_crawler_task 服務方法可能不依賴這些。如果需要，可以加回來。

        # 重新賦值 task_args (如果上面有修改)
        task_data['task_args'] = task_args

        # --- 基本驗證結束 ---

        # 不再需要為 validate_task_data_api 添加默認 task_name 和 crawler_id
        # 移除 validate_task_data_api 的調用

        result = service.test_crawler_task(crawler_data, task_data)
        return jsonify(result), 200
    except ValidationError as e: # 捕獲我們自己引發的 ValidationError
        return handle_api_error(e) # 使用統一的錯誤處理器
    except Exception as e:
        # 捕獲其他意外錯誤
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