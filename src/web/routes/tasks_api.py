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


def run_fetch_content_thread(task_id, links):
    """執行抓取內容的背景執行緒"""
    service = get_task_service()
    # 設定抓取模式為僅抓取內容
    task_args = {'article_links': links, 'scrape_mode': ScrapeMode.CONTENT_ONLY.value}
    service.fetch_article_content(task_id, task_args)

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
            return jsonify({"error": "排程任務必須提供 task_args"}), 400
        task_args = data.get('task_args', {})

        # 確保 is_scheduled 為 True (相當於 is_auto)
        data['is_auto'] = True

        # 確保 cron_expression 存在
        if 'cron_expression' not in data:
            return jsonify({"error": "排程任務必須提供 cron_expression"}), 400
            

        service.validate_task_data(data, is_update=False)
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
        
        # 確保 is_auto 為 True 
        data['is_auto'] = True
        
        # 檢查 cron_expression 是否存在，如果不存在則使用當前值
        if 'cron_expression' not in data:
            data['cron_expression'] = current_task_data.get('cron_expression')
        
        # 處理 scrape_mode 
        if 'scrape_mode' not in data:
             # 如果沒提供，則保留原來的值
             data['scrape_mode'] = current_task_data.get('scrape_mode')
        
        # 更新 task_args
        data['task_args'] = task_args
        
        service.validate_task_data(data, is_update=True)
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
def fetch_full_article_manual_task():
    """抓取完整文章的手動任務端點
        scrape_mode: FULL_SCRAPE
    Returns:
        dict: 包含任務ID、狀態和抓取模式
    """
    try:
        data = request.get_json()
        task_service = get_task_service()
        # 設置為手動任務
        data['is_auto'] = False
        data['scrape_mode'] = ScrapeMode.FULL_SCRAPE.value
        task_service.validate_task_data(data, is_update=False)
        result = task_service.create_task(data)
        if not result['success']:
            return jsonify({"error": result['message']}), 500
        task_id = result['task_id']
        
        thread = threading.Thread(target=run_manual_task_thread, args=(task_id, data['task_args']))
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
def get_task_status(task_id):
    try:
        service = get_task_service()
        result = service.get_task_status(task_id)
        if not result['success']:
            return jsonify({"error": result['message']}), 404
        return jsonify(result['status']), 200
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
        if not data.get('task_args'):
            data['task_args'] = TASK_ARGS_DEFAULT
        data['scrape_mode'] = ScrapeMode.LINKS_ONLY.value
        # 設置為手動任務
        data['is_auto'] = False
        
        service.validate_task_data(data, is_update=False)
        result = service.create_task(data)
        if not result['success']:
            return jsonify({"error": result['message']}), 500
        task_id = result['task_id']

            
        thread = threading.Thread(target=run_collect_links_thread, args=(task_id,))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "message": "Link collection initiated", 
            "scrape_mode": ScrapeMode.LINKS_ONLY.value,
            "task_data": data
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
        if not data.get('get_links_by_task_id'):
            return jsonify({"error": "缺少 get_links_by_task_id 參數，無法判定要從資料庫獲取文章連結還是直接使用 article_links"}), 400
        
        if data.get('get_links_by_task_id'):
            # 從資料庫根據任務ID獲取要抓取內容的文章(scrape_mode=CONTENT_ONLY時有效)
            article_links = get_unscraped_task_links(task_id)
            if not article_links:
                return jsonify({"error": "沒有找到未抓取的文章"}), 404
        else:
            # 直接使用 article_links 參數
            article_links = data.get('article_links')
            if not article_links:
                return jsonify({"error": "沒有提供文章連結"}), 400
        
        # 獲取其他任務參數
        task_args = data.get('task_args', TASK_ARGS_DEFAULT)
        
        service = get_task_service()
        # 檢查任務是否存在
        task_check = service.get_task_by_id(task_id)
        if not task_check['success']:
            return jsonify({"error": task_check['message']}), 404
        
        # 獲取現有任務資料
        current_task = task_check['task']
        current_task_args = current_task.get('task_args', TASK_ARGS_DEFAULT)
        
        # 合併現有參數和新參數
        for key, value in task_args.items():
            current_task_args[key] = value
        
        # 準備更新資料
        update_data = {
            'scrape_mode': ScrapeMode.CONTENT_ONLY.value,
            'task_args': current_task_args
        }

        # 加入驗證步驟 (is_update=True)
        service.validate_task_data(update_data, is_update=True)
        
        # 更新任務
        service.update_task(task_id, update_data)
            
        thread = threading.Thread(target=run_fetch_content_thread, args=(task_id, article_links))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "message": "Content fetching initiated", 
            "scrape_mode": ScrapeMode.CONTENT_ONLY.value,
            "link_count": len(article_links),
            "task_args": current_task_args # 返回合併後的 task_args
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