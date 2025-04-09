from flask import Blueprint, jsonify, request
from src.services.crawler_task_service import CrawlerTaskService
from src.services.scheduler_service import SchedulerService
from src.services.article_service import ArticleService
from src.error.handle_api_error import handle_api_error
from src.utils.validators import validate_task_data
import threading
from functools import wraps

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
    service.fetch_article_content(task_id, link_ids)

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
        tasks_repo = get_task_service()._get_repositories()[0]
        validate_task_data(data, tasks_repo)
        service = get_task_service()
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
        tasks_repo = get_task_service()._get_repositories()[0]
        validate_task_data(data, tasks_repo)
        service = get_task_service()
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
        tasks_repo = get_task_service()._get_repositories()[0]
        validate_task_data(data, tasks_repo)
        task_service = get_task_service()
        result = task_service.create_task(data)
        if not result['success']:
            return jsonify({"error": result['message']}), 500
        task_id = result['task_id']
        task_args = data.get('task_args', {})
        
        thread = threading.Thread(target=run_manual_task_thread, args=(task_id, task_args))
        thread.daemon = True
        thread.start()
        
        return jsonify({"task_id": task_id, "status": "pending"}), 202
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

@tasks_bp.route('/manual/<int:task_id>/fetch-content', methods=['POST'])
def fetch_manual_task_content(task_id):
    try:
        data = request.get_json()
        link_ids = data.get('link_ids')
        if not link_ids:
            return jsonify({"error": "Missing link_ids"}), 400
            
        thread = threading.Thread(target=run_fetch_content_thread, args=(task_id, link_ids))
        thread.daemon = True
        thread.start()
        
        return jsonify({"message": "Content fetching initiated"}), 202
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
        task_data = data.get('task_data')
        crawler_data = data.get('crawler_data')
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