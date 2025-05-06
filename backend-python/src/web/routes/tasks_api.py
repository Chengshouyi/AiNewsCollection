"""定義與爬蟲任務相關的 Flask API 端點。"""
import logging
from typing import Dict, Any, List, Optional
from enum import Enum

from flask import Blueprint, jsonify, request
from flask_pydantic_spec import Response, Request
from src.web.spec import spec  # 你已在 crawler_api.py 用這個

# 本地應用程式導入
from src.error.handle_api_error import handle_api_error
from src.error.errors import ValidationError
from src.models.crawler_tasks_model import ScrapeMode, ScrapePhase, TaskStatus
from src.models.crawler_tasks_model import TASK_ARGS_DEFAULT
from src.services.crawler_task_service import CrawlerTaskService
from src.services.service_container import (
    get_scheduler_service, get_task_executor_service,
    get_crawler_task_service, get_article_service
)
from src.models.crawler_tasks_schema import (
    CrawlerTasksCreateSchema, CrawlerTasksUpdateSchema, CrawlerTaskReadSchema,
    ArticlePreviewSchema, FetchContentRequestSchema, TestCrawlerRequestSchema, TaskHistorySchema
)
# 引入新的回應 schema
from src.web.routes.base_response_schema import BaseResponseSchema
# 再次嘗試使用基於 src 的絕對導入
from src.web.routes.task_response_schema import (
    GetScheduledTasksSuccessResponseSchema, CreateScheduledTaskSuccessResponseSchema,
    UpdateScheduledTaskSuccessResponseSchema, DeleteScheduledTaskSuccessResponseSchema,
    StartManualTaskSuccessResponseSchema, GetTaskStatusSuccessResponseSchema,
    CollectLinksManualTaskSuccessResponseSchema, GetUnscrapedLinksSuccessResponseSchema,
    FetchContentManualTaskSuccessResponseSchema, GetScrapedResultsSuccessResponseSchema,
    TestCrawlerSuccessResponseSchema, CancelTaskSuccessResponseSchema,
    GetTaskHistorySuccessResponseSchema, RunTaskSuccessResponseSchema,
    CreateTaskSuccessResponseSchema, UpdateTaskSuccessResponseSchema,
    GetAllTasksSuccessResponseSchema, DeleteTaskSuccessResponseSchema
)

# 使用統一的 logger
logger = logging.getLogger(__name__)  # 使用統一的 logger


tasks_bp = Blueprint('tasks_api', __name__, url_prefix='/api/tasks')

# 排程任務相關端點
@tasks_bp.route('/scheduled', methods=['GET'])
@spec.validate(
    resp=Response(
        HTTP_200=GetScheduledTasksSuccessResponseSchema,
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema
    ),
    tags=['爬蟲任務']
)
def get_scheduled_tasks():
    try:
        service = get_crawler_task_service()
        # 使用 find_tasks_advanced 查找自動、活躍的排程任務
        # 注意：這裡沒有傳遞分頁參數，會獲取所有符合條件的任務
        result = service.find_tasks_advanced(is_scheduled=True, is_active=True, is_auto=True, is_preview=False) # is_preview=False 返回 Schema
        if not result['success']:
            # 如果服務層返回失敗，根據 message 返回錯誤
            return jsonify({"success": False, "message": result.get('message', '獲取排程任務失敗')}), 500
        
        # 從 result['data']['items'] 獲取任務列表 (Pydantic Schema)
        tasks_list_schemas = result.get('data', {}).get('items', [])
        # 將返回的 Pydantic Schema 列表轉換為字典列表 (不需要了，直接用 schema)
        # tasks_list = [task.model_dump() for task in tasks_list_schemas]
        return jsonify({
            "success": True,
            "message": result.get('message', '獲取排程任務成功'),
            "data": [task.model_dump() for task in tasks_list_schemas] # 直接返回模型 dump 後的列表
        }), 200
    except Exception as e:
        return handle_api_error(e)
    
@tasks_bp.route('/scheduled', methods=['POST'])
@spec.validate(
    body=Request(CrawlerTasksCreateSchema),
    resp=Response(
        HTTP_201=CreateScheduledTaskSuccessResponseSchema,
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema
    ),
    tags=['爬蟲任務']
)
def create_scheduled_task():
    if not request.is_json:
         return jsonify(success=False, message='請求必須是 application/json'), 415 # Unsupported Media Type
    if not request.data: # 檢查是否有實際的請求體
         return jsonify(success=False, message='缺少任務資料'), 400 # Bad Request
    data = request.get_json() or {}
    try:
        task_service = get_crawler_task_service()
        # 驗證任務資料，設定 scrape_mode 和 is_auto
        validated_result = _setup_validate_task_data(
            task_data=data,
            service=task_service,
            scrape_mode=data.get('task_args', {}).get('scrape_mode', ScrapeMode.FULL_SCRAPE.value),
            is_auto=True,
            is_update=False
        )

        if not validated_result.get('success'):
            # 如果驗證失敗，返回包含錯誤信息的結果
            return jsonify(validated_result), 400

        # 創建任務
        create_task_result = task_service.create_task(validated_result['data'])
        if not create_task_result.get('success'):
            # 如果創建失敗，返回錯誤
            return jsonify(create_task_result), 500

        # 從結果中獲取創建的任務對象 (Pydantic Schema)
        task = create_task_result.get('task')
        task_data = _prepare_task_for_response(task)
        
        # 如果是自動任務，添加到排程器
        if task:
            scheduler = get_scheduler_service()
            scheduler_result = scheduler.add_or_update_task_to_scheduler(task)
            if not scheduler_result.get('success'):
                logger.error("任務 %s 已創建但添加到排程器失敗: %s", task.id, scheduler_result.get('message'))
                response_message = f"{create_task_result.get('message', '任務創建成功')}, 但添加到排程器失敗: {scheduler_result.get('message')}"
                return jsonify({
                    "success": True,
                    "message": response_message,
                    "data": task_data # 使用 'data' key
                }), 201
        
        # 創建成功
        return jsonify({
            "success": True,
            "message": create_task_result.get('message', '任務創建成功'),
            "data": task_data # 使用 'data' key
        }), 201
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/scheduled/<int:task_id>', methods=['PUT'])
@spec.validate(
    body=Request(CrawlerTasksUpdateSchema),
    resp=Response(
        HTTP_200=UpdateScheduledTaskSuccessResponseSchema,
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema
    ),
    tags=['爬蟲任務']
)
def update_scheduled_task(task_id):
    if not request.is_json:
         return jsonify(success=False, message='請求必須是 application/json'), 415
    if not request.data: # 檢查是否有實際的請求體
         return jsonify(success=False, message='缺少任務資料'), 400
    data = request.get_json() or {}
    try:
        service = get_crawler_task_service()

        # 獲取當前任務資料
        get_task_result = service.get_task_by_id(task_id, is_active=True)
        if not get_task_result.get('success'):
            return jsonify({"success": False, "message": get_task_result.get('message', '找不到任務')}), 404

        db_task = get_task_result.get('task')
        if not db_task:
             return jsonify({"success": False, "message": "找不到任務對象"}), 404
        db_task_args = db_task.task_args or {} # 確保 task_args 是字典

        new_task_args = data.get('task_args', {})
        
        # 合併 task_args: 以資料庫中的為基礎，用請求中的覆蓋
        merged_task_args = db_task_args.copy()
        merged_task_args.update(new_task_args)
        data['task_args'] = merged_task_args # 將合併後的放回 data

        # 驗證更新後的數據
        validated_result = _setup_validate_task_data(
            task_data=data,
            service=service,
            scrape_mode=merged_task_args.get('scrape_mode', ScrapeMode.FULL_SCRAPE.value),
            is_auto=True, # 排程任務應為 is_auto=True
            is_update=True
        )
        if not validated_result.get('success'):
            return jsonify(validated_result), 400

        # 更新任務
        update_result = service.update_task(task_id, validated_result['data'])
        if not update_result.get('success'):
             # 如果更新失敗，返回錯誤
             status_code = 404 if "不存在" in update_result.get('message', '') else 500
             return jsonify(update_result), status_code
            
        # 從結果中獲取更新的任務對象 (Pydantic Schema)
        updated_task = update_result.get('task')
        task_data = _prepare_task_for_response(updated_task)
        
        # 如果是自動任務，更新排程器
        if updated_task:
            scheduler = get_scheduler_service()
            scheduler_result = scheduler.add_or_update_task_to_scheduler(updated_task)
            if not scheduler_result.get('success'):
                logger.error("任務 %s 已更新但更新排程器失敗: %s", task_id, scheduler_result.get('message'))
                response_message = f"{update_result.get('message', '任務更新成功')}, 但更新排程器失敗: {scheduler_result.get('message')}"
                return jsonify({
                    "success": True,
                    "message": response_message,
                    "data": task_data # 使用 'data' key
                }), 200
        
        # 更新成功
        return jsonify({
            "success": True,
            "message": update_result.get('message', '任務更新成功'),
            "data": task_data # 使用 'data' key
        }), 200
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/scheduled/<int:task_id>', methods=['DELETE'])
@spec.validate(
    resp=Response(
        HTTP_200=DeleteScheduledTaskSuccessResponseSchema,
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema
    ),
    tags=['爬蟲任務']
)
def delete_scheduled_task(task_id):
    try:
        service = get_crawler_task_service()
        scheduler = get_scheduler_service()
        
        # 先嘗試從排程器移除
        scheduled_result = scheduler.remove_task_from_scheduler(task_id)
        # 即使排程器移除失敗 (可能原本就不在排程中)，也繼續嘗試刪除任務
        if not scheduled_result['success']:
             logger.warning("從排程器移除任務 %s 失敗或未找到: %s", task_id, scheduled_result.get('message'))

        # 刪除資料庫中的任務
        result = service.delete_task(task_id)
        if not result['success']:
            # 如果刪除失敗 (例如任務不存在)，返回 404
            return jsonify(result), 404

        # 成功刪除
        # 結合排程移除和任務刪除的結果訊息
        final_message = result.get('message', f'任務 {task_id} 刪除成功')
        if not scheduled_result['success']:
            final_message += f" (排程器移除訊息: {scheduled_result.get('message')})"
            
        return jsonify({
            "success": True,
            "message": final_message
        }), 200
    except Exception as e:
        return handle_api_error(e)

# 手動任務相關端點
@tasks_bp.route('/manual/start', methods=['POST'])
@spec.validate(
    body=Request(CrawlerTasksCreateSchema),
    resp=Response(
        HTTP_202=StartManualTaskSuccessResponseSchema,
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema
    ),
    tags=['手動任務']
)
def fetch_full_article_manual_task():
    """抓取完整文章的手動任務端點 (創建新任務並立即執行)"""
    if not request.is_json:
         return jsonify(success=False, message='請求必須是 application/json'), 415
    if not request.data:
         return jsonify(success=False, message='缺少任務資料'), 400
    try:
        data = request.get_json() or {}
        if not data:
            return jsonify({"success": False, "message": "缺少任務資料"}), 400

        task_service = get_crawler_task_service()

        # 驗證任務資料 (手動, FULL_SCRAPE)
        validated_result = _setup_validate_task_data(
            task_data=data,
            service=task_service,
            scrape_mode=ScrapeMode.FULL_SCRAPE.value,
            is_auto=False,
            is_update=False
        )
        if not validated_result.get('success'):
            return jsonify(validated_result), 400

        # 創建任務
        create_result = task_service.create_task(validated_result['data'])
        if not create_result.get('success'):
            return jsonify(create_result), 500
            
        task = create_result.get('task')
        if not task:
            return jsonify({"success": False, "message": "任務創建後無法獲取任務對象"}), 500
        task_id = task.id

        # 提交任務執行 (同步執行)
        task_executor = get_task_executor_service()
        # fetch_full_article 內部會調用 execute_task
        executor_result = task_executor.fetch_full_article(task_id, is_async=False)

        # executor_result 結構: {'success': bool, 'message': str, 'task_status': str, ...可能還有爬蟲返回的其他數據}
        if executor_result.get('success'):
            response_data = {
                "success": True,
                "message": executor_result.get('message', '手動任務已啟動'),
                "data": {
                    "task_id": task_id,
                    "task_status": executor_result.get('task_status', 'UNKNOWN')
                }
            }
            return jsonify(response_data), 202
        else:
            return jsonify({"success": False, "message": executor_result.get('message', '任務執行失敗')}), 500
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/<int:task_id>/status', methods=['GET'])
@spec.validate(
    resp=Response(
        HTTP_200=GetTaskStatusSuccessResponseSchema,
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema
    ),
    tags=['手動任務']
)
def get_task_status(task_id):
    try:
        task_executor = get_task_executor_service()
        executor_result = task_executor.get_task_status(task_id)
        # get_task_status 返回: {'success': bool, 'task_status': str, 'scrape_phase': str, 'progress': int, 'message': str, 'task': Optional[Schema]}
        if executor_result.get('success'):
            task_obj = executor_result.get('task')
            response_data = {
                "success": True,
                "message": executor_result.get('message', '成功獲取狀態'),
                "data": {
                    "task_status": executor_result.get('task_status', 'UNKNOWN'),
                    "scrape_phase": executor_result.get('scrape_phase', 'UNKNOWN'),
                    "progress": executor_result.get('progress', 0),
                    "task": task_obj.model_dump() if task_obj else None
                }
            }
            return jsonify(response_data), 200
        else:
            return jsonify({"success": False, "message": executor_result.get('message', '找不到任務或獲取狀態失敗')}), 404

    except Exception as e:
        return handle_api_error(e)

# 修改：移除 task_id，因為這是創建一個新任務
@tasks_bp.route('/manual/collect-links', methods=['POST'])
@spec.validate(
    body=Request(CrawlerTasksCreateSchema),
    resp=Response(
        HTTP_202=CollectLinksManualTaskSuccessResponseSchema,
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema
    ),
    tags=['手動任務']
)
def fetch_links_manual_task():
    """抓取連結的手動任務端點 (創建新任務並立即執行)"""
    if not request.is_json:
         return jsonify(success=False, message='請求必須是 application/json'), 415
    if not request.data:
         return jsonify(success=False, message='缺少任務資料'), 400
    try:
        service = get_crawler_task_service()
        data = request.get_json() or {}
        if not data:
            return jsonify({"success": False, "message": "缺少任務資料"}), 400

        # 驗證任務資料 (手動, LINKS_ONLY)
        validated_result = _setup_validate_task_data(
            task_data=data,
            service=service,
            scrape_mode=ScrapeMode.LINKS_ONLY.value,
            is_auto=False,
            is_update=False
        )
        if not validated_result.get('success'):
            return jsonify(validated_result), 400

        # 創建任務
        create_result = service.create_task(validated_result['data'])
        if not create_result.get('success'):
            return jsonify(create_result), 500
            
        task = create_result.get('task') # 獲取創建的任務對象
        if not task:
            return jsonify({"success": False, "message": "任務創建後無法獲取任務對象"}), 500
        task_id = task.id

        # 提交任務執行 (同步執行)
        task_executor = get_task_executor_service()
        # collect_links_only 內部會調用 execute_task
        executor_result = task_executor.collect_links_only(task_id, is_async=False)
        
        if executor_result.get('success'):
            response_data = {
                "success": True,
                "message": executor_result.get('message', '手動連結抓取任務已啟動'),
                "data": {
                    "task_id": task_id,
                    "task_status": executor_result.get('task_status', 'UNKNOWN')
                }
            }
            return jsonify(response_data), 202
        else:
            return jsonify({"success": False, "message": executor_result.get('message', '任務執行失敗')}), 500
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/<int:task_id>/links', methods=['GET'])
@spec.validate(
    resp=Response(
        HTTP_200=GetUnscrapedLinksSuccessResponseSchema,
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema
    ),
    tags=['手動任務']
)
def get_unscraped_links(task_id):
    """獲取指定任務關聯的、未抓取的文章連結 (預覽)"""
    try:
        article_service = get_article_service()
        # is_preview=True 返回包含預覽欄位的字典列表
        result = article_service.find_unscraped_articles(task_id=task_id, is_preview=True)
        
        if result.get('success'):
             # articles 是 ArticlePreviewSchema 的列表
             articles_data = result.get('articles', []) # 這裡直接是預期的列表
             return jsonify({
                  "success": True,
                  "message": result.get('message', '成功獲取未抓取連結'),
                  "data": articles_data
             }), 200
        else:
             status_code = 404 if "未找到" in result.get('message', '') else 500
             return jsonify({"success": False, "message": result.get('message', '獲取連結失敗')}), status_code
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/<int:task_id>/fetch-content', methods=['POST'])
@spec.validate(
    body=Request(FetchContentRequestSchema),
    resp=Response(
        HTTP_202=FetchContentManualTaskSuccessResponseSchema,
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema
    ),
    tags=['手動任務']
)
def fetch_content_manual_task(task_id):
    """針對現有任務，觸發僅抓取內容的操作 (同步執行)"""
    if not request.is_json:
         return jsonify(success=False, message='請求必須是 application/json'), 415
    if not request.data:
         return jsonify(success=False, message='缺少任務資料'), 400
    try:
        data = request.get_json() or {}

        service = get_crawler_task_service()
        # 檢查任務是否存在且活躍
        get_task_result = service.get_task_by_id(task_id, is_active=True)
        if not get_task_result.get('success'):
            return jsonify({"success": False, "message": get_task_result.get('message', f'找不到有效的任務 {task_id}')}), 404

        db_task = get_task_result.get('task')
        if not db_task:
             return jsonify({"success": False, "message": f"找不到任務 {task_id} 的對象"}), 404
        db_task_args = db_task.task_args or {}

        # 獲取請求中的 task_args，如果沒有則使用空字典
        request_task_args = data.get('task_args', {})

        # 處理 article_links
        article_links = []
        # 檢查是否需要從資料庫獲取連結 (預設為 False)
        get_links_from_db = request_task_args.get('get_links_by_task_id', False)

        if get_links_from_db:
            article_service = get_article_service()
            # 獲取未抓取的文章預覽信息
            unscraped_result = article_service.find_unscraped_articles(task_id=task_id, is_preview=True)
            if not unscraped_result.get('success') or not unscraped_result.get('articles'):
                # 如果從 DB 獲取不到連結，且請求中也沒有提供，則報錯
                if not request_task_args.get('article_links'):
                     return jsonify({"success": False, "message": f"任務 {task_id} 沒有找到未抓取的文章連結，且請求中未提供 article_links"}), 400
            else:
                # 從預覽結果中提取連結
                article_links = [article.get('link') for article in unscraped_result.get('articles', []) if article.get('link')]
        else:
            # 如果不從 DB 獲取，則必須從請求中提供 article_links
            article_links = request_task_args.get('article_links')
            if not article_links or not isinstance(article_links, list):
                return jsonify({"success": False, "message": "未從資料庫獲取連結，且請求中未提供有效的 article_links 列表"}), 400

        if not article_links:
             return jsonify({"success": False, "message": "未能確定要抓取的文章連結"}), 400

        # --- 準備更新任務 ---
        # 合併 task_args: 以資料庫中的為基礎，用請求中的覆蓋，並強制加入 article_links
        final_task_args = db_task_args.copy()
        final_task_args.update(request_task_args) # 用請求參數覆蓋
        final_task_args['article_links'] = article_links # 強制設定 article_links
        final_task_args['scrape_mode'] = ScrapeMode.CONTENT_ONLY.value # 強制設定模式

        # 構造用於驗證和更新的數據
        update_data = {
            'task_name': data.get('task_name', db_task.task_name), # 允許更新名稱
            'notes': data.get('notes', db_task.notes), # 允許更新備註
            'task_args': final_task_args
        }
        
        # 驗證更新數據 (手動, CONTENT_ONLY, 更新操作)
        validated_result = _setup_validate_task_data(
            task_data=update_data,
            service=service,
            scrape_mode=ScrapeMode.CONTENT_ONLY.value,
            is_auto=False, # 手動任務
            is_update=True
        )
        if not validated_result.get('success'):
            return jsonify(validated_result), 400

        # 更新任務 (主要是更新 task_args 和可能的名稱/備註)
        update_result = service.update_task(task_id, validated_result['data'])
        if not update_result.get('success'):
             # 如果更新失敗，返回錯誤
             status_code = 404 if "不存在" in update_result.get('message', '') else 500
             return jsonify(update_result), status_code

        # --- 執行任務 ---
        task_executor = get_task_executor_service()
        # fetch_content_only 內部調用 execute_task
        executor_result = task_executor.fetch_content_only(task_id, is_async=False)

        if executor_result.get('success'):
            response_data = {
                "success": True,
                "message": executor_result.get('message', '手動內容抓取任務已啟動'),
                "data": {
                    "task_id": task_id,
                    "task_status": executor_result.get('task_status', 'UNKNOWN')
                }
            }
            return jsonify(response_data), 202
        else:
            status_code = 404 if "找不到" in executor_result.get('message', '') else 500
            return jsonify({"success": False, "message": executor_result.get('message', '任務執行失敗')}), status_code

    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/<int:task_id>/results', methods=['GET'])
@spec.validate(
    resp=Response(
        HTTP_200=GetScrapedResultsSuccessResponseSchema,
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema
    ),
    tags=['手動任務']
)
def get_scraped_task_results(task_id):
    """獲取指定任務關聯的、已抓取的文章結果 (預覽)"""
    try:
        article_service = get_article_service()
        # is_preview=True 返回包含預覽欄位的字典列表
        result = article_service.find_scraped_articles(task_id=task_id, is_preview=True)
        
        if result.get('success'):
             articles_data = result.get('articles', []) # 這裡直接是預期的列表
             return jsonify({
                  "success": True,
                  "message": result.get('message', '成功獲取已抓取結果'),
                  "data": articles_data
             }), 200
        else:
             status_code = 404 if "未找到" in result.get('message', '') else 500
             return jsonify({"success": False, "message": result.get('message', '獲取結果失敗')}), status_code
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/test', methods=['POST'])
@spec.validate(
    body=Request(TestCrawlerRequestSchema),
    resp=Response(
        HTTP_200=TestCrawlerSuccessResponseSchema,
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema
    ),
    tags=['手動任務']
)
def test_crawler():
    """測試爬蟲任務 (不會創建或執行實際任務)"""
    if not request.is_json:
         return jsonify({"success": False, "message": "請求必須是 application/json"}), 415
    if not request.data:
         return jsonify({"success": False, "message": "缺少任務資料"}), 400
    try:
        data = request.get_json() or {}
        if not data:
            logger.error("缺少測試資料: %s", data)
            return jsonify({"success": False, "message": "缺少測試資料"}), 400
            
        crawler_name = data.get('crawler_name')
        if not crawler_name:
             logger.error("缺少 crawler_name: %s", data)
             return jsonify({"success": False, "message": "缺少 crawler_name"}), 400

        service = get_crawler_task_service()

        test_task_args = data.get('task_args', TASK_ARGS_DEFAULT).copy()
        test_task_args.update({**TASK_ARGS_DEFAULT,
            'scrape_mode': ScrapeMode.LINKS_ONLY.value,
            'is_test': True,
            'max_pages': min(1, test_task_args.get('max_pages', 1)),
            'num_articles': min(5, test_task_args.get('num_articles', 5)),
            'save_to_csv': False,
            'save_to_database': False,
            'get_links_by_task_id': False,
            'timeout': 30,
            'ai_only': test_task_args.get('ai_only', False)  
        })
        
        task_data_for_validation = {
            'crawler_id': data.get('crawler_id', 0),
            'crawler_name': crawler_name,
            'task_name': f"測試_{crawler_name}",
            'task_args': test_task_args,
            'scrape_phase': ScrapePhase.INIT.value,
            'task_status': TaskStatus.INIT.value,
            'is_auto': False,
            'is_active': True,
            'is_scheduled': False,
            'retry_count': 0,
            'notes': f"測試爬蟲 {crawler_name}",
            'last_run_at': None,
            'last_run_success': None,
        }

        logger.info("驗證模擬的任務數據: %s", task_data_for_validation)
        try:
            validated_result = service.validate_task_data(task_data_for_validation, is_update=False)
        except Exception as e:
            return jsonify({
                'success': False,
                'message': str(e)
            }), 400
        
        # 如果驗證失敗，確保返回的錯誤訊息是可序列化的
        if not validated_result.get('success'):
            return jsonify({
                'success': False,
                'message': str(validated_result.get('message', '驗證失敗'))
            }), 400

        # 獲取驗證後的參數
        validated_test_params = validated_result.get('data', {}).get('task_args', {})

        # 執行測試
        task_executor = get_task_executor_service()
        executor_result = task_executor.test_crawler(crawler_name, validated_test_params)
        
        # 確保返回的結果是可序列化的
        response_data = {
            'success': executor_result.get('success', False),
            'message': str(executor_result.get('message', '')),
            # 'result' 鍵現在放到 'data' 下面
            # 'result': {
            #     k: str(v) if isinstance(v, Enum) else v  # 將所有枚舉值轉換為字串
            #     for k, v in (executor_result.get('result', {}) or {}).items()
            # }
        }
        test_result_data = {
             k: str(v) if isinstance(v, Enum) else v
             for k, v in (executor_result.get('result', {}) or {}).items()
        }

        if response_data['success']:
            return jsonify({
                "success": True,
                "message": response_data['message'],
                "data": test_result_data # 將 result 字典放在 data 下
            }), 200
        else:
            # 如果測試失敗，仍然可以用 BaseResponseSchema，但可以包含 data (空字典) 或省略
            return jsonify({
                "success": False,
                "message": response_data['message'],
                # "data": {} # 或者省略 data
            }), 500
    except Exception as e:
        logger.error("測試爬蟲時發生錯誤: %s", str(e), exc_info=True)
        return jsonify({
            'success': False,
            'message': f"測試時發生錯誤: {str(e)}"
        }), 500

# 通用任務端點
@tasks_bp.route('/<int:task_id>/cancel', methods=['POST'])
@spec.validate(
    resp=Response(
        HTTP_202=CancelTaskSuccessResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_400=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema
    ),
    tags=['任務管理']
)
def cancel_task(task_id):
    try:
        task_executor = get_task_executor_service()
        result = task_executor.cancel_task(task_id)
        # cancel_task 返回 {'success': bool, 'message': str}
        status_code = 202 if result.get('success') else 404 # 404 如果任務未找到或無法取消
        return jsonify(result), status_code
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/<int:task_id>/history', methods=['GET'])
@spec.validate(
    resp=Response(
        HTTP_200=GetTaskHistorySuccessResponseSchema,
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema
    ),
    tags=['任務管理']
)
def get_task_history(task_id):
    try:
        # 從 CrawlerTaskService 獲取歷史記錄
        service = get_crawler_task_service()
        # 使用 find_task_history
        # 注意：這裡沒有傳遞分頁/預覽參數
        result = service.find_task_history(task_id)
        
        if not result.get('success'):
            return jsonify(result), 404

        # 將 history schema 列表轉換為 dict 列表 (從 'history' 鍵獲取)
        histories_list = [h.model_dump() for h in result.get('history', [])]
        
        # 構造最終的 JSON 響應以匹配 Schema
        response_data = {
            'success': True,
            'message': result.get('message', '獲取任務歷史成功'),
            'data': { # 將 history 和 total_count 放入 data
                'history': histories_list,
                'total_count': len(histories_list)
            }
        }
        return jsonify(response_data), 200
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/<int:task_id>/run', methods=['POST'])
@spec.validate(
    resp=Response(
        HTTP_202=RunTaskSuccessResponseSchema,
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema
    ),
    tags=['任務管理']
)
def run_task(task_id):
    """手動執行特定任務的API端點。允許客戶端請求立即執行任務。"""
    try:
        service = get_task_executor_service()
        
        # 執行任務
        result = service.execute_task(task_id, is_async=True)
        
        if not result['success']:
            return jsonify(result), 400
            
        # 獲取會話ID (如果有的話)
        session_id = None
        if hasattr(service, 'task_session_ids') and task_id in service.task_session_ids:
            session_id = service.task_session_ids[task_id]
            
        # 增強結果響應以匹配 Schema
        enhanced_result = {
            'success': True,
            'message': result['message'],
            'data': { # 將 task_id, session_id, room 放入 data
                'task_id': task_id,
                'session_id': session_id,  # 返回會話ID給前端
                'room': f"task_{task_id}_{session_id}" if session_id else f"task_{task_id}"
            }
        }
        
        return jsonify(enhanced_result), 202  # Accepted
    except Exception as e:
        logger.exception("執行任務 %s 時出錯: %s", task_id, str(e))
        return jsonify({
            'success': False, 
            'message': f'執行任務時出錯: {str(e)}',
            'task_id': task_id
        }), 500

def _setup_validate_task_data(task_data: Dict[str, Any], service: CrawlerTaskService, scrape_mode: str, is_auto: bool, is_update: bool = False) -> Dict[str, Any]:
    """設置並驗證任務資料

    Args:
        task_data: 請求傳入的任務資料
        service: CrawlerTaskService 實例
        scrape_mode: 當前操作的抓取模式
        is_auto: 是否為自動任務
        is_update: 是否為更新操作

    Returns:
        Dict[str, Any]: 包含驗證結果的字典
            success: bool
            message: str
            data: Optional[Dict] - 驗證通過的數據
    """
    if 'task_args' not in task_data or not task_data['task_args']:
        task_data['task_args'] = TASK_ARGS_DEFAULT.copy() # 使用副本避免修改預設值
    
    # 確保 scrape_mode 在 task_args 中也設置一致 (如果 task_args 裡沒有)
    if 'scrape_mode' not in task_data['task_args']:
         task_data['task_args']['scrape_mode'] = scrape_mode

    # 設置基本必要字段
    task_data['scrape_mode'] = scrape_mode
    task_data['is_auto'] = is_auto
    
    # 設置task_name (如果來自前端的是name，則轉換為task_name)
    if 'name' in task_data and not task_data.get('task_name'):
        task_data['task_name'] = task_data['name']
    
    # 確保scrape_phase有值，如果沒有則設為初始值
    if 'scrape_phase' not in task_data:
        task_data['scrape_phase'] = ScrapePhase.INIT.value  # 使用.value獲取字符串值
    elif isinstance(task_data['scrape_phase'], ScrapePhase):
        # 如果是枚舉對象，則轉換為字符串值
        task_data['scrape_phase'] = task_data['scrape_phase'].value
    
    # 調用服務進行驗證
    validation_result = service.validate_task_data(task_data, is_update=is_update)

    return validation_result

# 通用任務端點
@tasks_bp.route('', methods=['POST'])
@spec.validate(
    body=Request(CrawlerTasksCreateSchema),
    resp=Response(
        HTTP_201=CreateTaskSuccessResponseSchema,
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema
    ),
    tags=['任務管理']
)
def create_task():
    """創建一個新任務（通用任務創建端點）"""
    if not request.is_json:
         return jsonify(success=False, message='請求必須是 application/json'), 415
    if not request.data:
         return jsonify(success=False, message='缺少任務資料'), 400
    data = request.get_json() or {}
    try:
        task_service = get_crawler_task_service()
        
        # 修正：直接使用布爾值
        is_auto = data.get('is_auto', False)  # 直接獲取布爾值
        
        # 從task_args中獲取scrape_mode，如果沒有則使用默認值FULL_SCRAPE
        scrape_mode = data.get('task_args', {}).get('scrape_mode', ScrapeMode.FULL_SCRAPE.value)
        
        # 確保task_args存在
        if 'task_args' not in data:
            data['task_args'] = {}
            
        # 設置初始scrape_phase - 使用值而不是枚舉對象
        data['scrape_phase'] = ScrapePhase.INIT.value
        data['is_active'] = True
        data['is_auto'] = is_auto  # 確保設置正確的布爾值
        
        # 驗證任務資料
        validated_result = _setup_validate_task_data(
            task_data=data,
            service=task_service,
            scrape_mode=scrape_mode,
            is_auto=is_auto,
            is_update=False
        )

        if not validated_result.get('success'):
            # 如果驗證失敗，返回包含錯誤信息的結果
            return jsonify(validated_result), 400

        # 創建任務
        create_task_result = task_service.create_task(validated_result['data'])
        if not create_task_result.get('success'):
            # 如果創建失敗，返回錯誤
            return jsonify(create_task_result), 500

        task_model_instance = create_task_result.get('task') 
        
        if not task_model_instance:
            logger.error("任務創建成功，但無法從服務獲取任務模型實例。")
            return jsonify({"success": False, "message": "任務創建成功，但無法獲取返回的任務數據。"}), 500

        # 將 Pydantic 模型實例轉換為 JSON 兼容的字典
        task_data_dict = task_model_instance.model_dump(mode="json")
        
        return jsonify({
            "success": True,
            "message": create_task_result.get('message', '任務創建成功'),
            "data": task_data_dict
        }), 201
    except Exception as e:
        logger.exception("創建任務時出錯: %s", str(e))
        return handle_api_error(e)

# 通用任務更新端點
@tasks_bp.route('/<int:task_id>', methods=['PUT'])
@spec.validate(
    body=Request(CrawlerTasksUpdateSchema),
    resp=Response(
        HTTP_200=UpdateTaskSuccessResponseSchema,
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema
    ),
    tags=['任務管理']
)
def update_task(task_id):
    """更新特定任務"""
    if not request.is_json:
         return jsonify(success=False, message='請求必須是 application/json'), 415
    if not request.data:
         return jsonify(success=False, message='缺少任務資料'), 400
    data = request.get_json() or {}
    try:
        service = get_crawler_task_service()

        # 更新任務
        update_result = service.update_task(task_id, data)
        if not update_result.get('success'):
            status_code = 404 if "不存在" in update_result.get('message', '') else 500
            return jsonify(update_result), status_code

        # 從結果中獲取更新的任務對象 (Pydantic Schema)
        # updated_task = update_result.get('task') # 這行變數未使用
        # task_data = _prepare_task_for_response(updated_task) # 這行變數未使用

        final_task_data = _prepare_task_for_response(update_result.get('task'))
        return jsonify({
            "success": True,
            "message": update_result.get('message', '任務更新成功'),
            "data": final_task_data # 使用 'data' key
        }), 200
    except ValidationError as ve: # 捕獲特定的驗證錯誤
         error_message = f"更新任務 {task_id} 時資料驗證失敗: {ve}"
         logger.error(error_message, exc_info=True)
         return jsonify({"success": False, "message": error_message}), 400
    except Exception as e:
        logger.exception("更新任務 %s 時出錯: %s", task_id, str(e))
        return handle_api_error(e)

@tasks_bp.route('', methods=['GET'])
@spec.validate(
    resp=Response(
        HTTP_200=GetAllTasksSuccessResponseSchema,
        HTTP_400=BaseResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema
    ),
    tags=['任務管理']
)
def get_all_tasks():
    """獲取所有任務列表"""
    try:
        service = get_crawler_task_service()
        result = service.find_all_tasks()
        
        if not result.get('success'):
            return jsonify({"success": False, "message": result.get('message', '獲取任務列表失敗')}), 500
        
        tasks_list_models = result.get('tasks', []) # 假設這是一個 Pydantic 模型實例的列表
        
        # 將每個 Pydantic 模型實例轉換為 JSON 兼容的字典
        # model_dump(mode="json") 會處理 datetime, Enum 等類型，使其可以直接被 json.dumps 序列化
        tasks_dict_list = [task.model_dump(mode="json") for task in tasks_list_models]
        
        logger.info("成功獲取 %s 個任務", len(tasks_dict_list))
        
        return jsonify({"success": True, "message": "獲取任務列表成功", "data": tasks_dict_list}), 200
    except Exception as e:
        logger.exception("獲取任務列表時出錯: %s", str(e))
        return handle_api_error(e)

@tasks_bp.route('/<int:task_id>', methods=['DELETE'])
@spec.validate(
    resp=Response(
        HTTP_200=DeleteTaskSuccessResponseSchema,
        HTTP_404=BaseResponseSchema,
        HTTP_400=BaseResponseSchema,
        HTTP_500=BaseResponseSchema,
        HTTP_502=BaseResponseSchema,
        HTTP_503=BaseResponseSchema,
        HTTP_504=BaseResponseSchema
    ),
    tags=['任務管理']
)
def delete_task(task_id):
    """刪除特定任務"""
    try:
        service = get_crawler_task_service()
        scheduler = get_scheduler_service()
        
        # 判斷任務是否為自動任務
        get_task_result = service.get_task_by_id(task_id, is_active=True)
        is_auto = False
        if get_task_result.get('success') and get_task_result.get('task'):
            task_obj = get_task_result.get('task')
            # 檢查task是否有type屬性，並且值為'auto'
            is_auto = hasattr(task_obj, 'type') and getattr(task_obj, 'type') == 'auto'
        
        # 如果是自動任務，先嘗試從排程器移除
        if is_auto:
            scheduled_result = scheduler.remove_task_from_scheduler(task_id)
            if not scheduled_result['success']:
                logger.warning("從排程器移除任務 %s 失敗或未找到: %s", task_id, scheduled_result.get('message'))

        # 刪除資料庫中的任務
        result = service.delete_task(task_id)
        if not result['success']:
            return jsonify(result), 404

        # 成功刪除
        return jsonify({
            "success": True,
            "message": result.get('message', f'任務 {task_id} 刪除成功')
        }), 200
    except Exception as e:
        logger.exception("刪除任務 %s 時出錯: %s", task_id, str(e))
        return handle_api_error(e)

def _ensure_serializable(obj):
    """確保對象可以被序列化為JSON
    
    處理特殊類型，如枚舉轉換為字符串值
    """
    if obj is None:
        return None
        
    # 如果是枚舉類型，轉換為字符串值
    if isinstance(obj, (ScrapePhase, TaskStatus, ScrapeMode)):
        return obj.value
        
    # 如果是字典，遞迴處理所有值
    if isinstance(obj, dict):
        return {k: _ensure_serializable(v) for k, v in obj.items()}
        
    # 如果是列表，遞迴處理所有元素
    if isinstance(obj, list):
        return [_ensure_serializable(item) for item in obj]
        
    # 其他類型直接返回
    return obj

def _prepare_task_for_response(task_data):
    """為API響應準備任務數據，確保所有內容都可序列化"""
    if task_data is None:
        return None
        
    # 如果已經是字典，直接處理枚舉等
    if isinstance(task_data, dict):
        return _ensure_serializable(task_data)
        
    # 如果有model_dump方法，先轉換為字典，再處理
    if hasattr(task_data, 'model_dump'):
        return _ensure_serializable(task_data.model_dump())
        
    # 如果有to_dict方法，先轉換為字典，再處理
    if hasattr(task_data, 'to_dict'):
        return _ensure_serializable(task_data.to_dict())
        
    # 其他情況，嘗試轉換為字典
    try:
        return _ensure_serializable(dict(task_data))
    except Exception as e:
        logger.warning("無法將 %s 轉換為字典，返回None. 錯誤: %s", type(task_data), e)
        return None
