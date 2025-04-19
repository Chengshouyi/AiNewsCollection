from flask import Blueprint, jsonify, request
from src.error.handle_api_error import handle_api_error
from src.models.crawler_tasks_model import ScrapeMode
from src.models.crawler_tasks_model import TASK_ARGS_DEFAULT
from typing import Dict, Any
from src.services.crawler_task_service import CrawlerTaskService
from src.services.service_container import get_scheduler_service, get_task_executor_service, get_crawler_task_service, get_article_service
import logging
# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


tasks_bp = Blueprint('tasks_api', __name__, url_prefix='/api/tasks')

# 排程任務相關端點
@tasks_bp.route('/scheduled', methods=['GET'])
def get_scheduled_tasks():
    try:
        service = get_crawler_task_service()
        # 使用 advanced_search_tasks 查找自動、活躍的排程任務
        result = service.advanced_search_tasks(is_scheduled=True, is_active=True, is_auto=True)
        if not result['success']:
            # 如果服務層返回失敗，根據 message 返回錯誤
            return jsonify({"success": False, "message": result.get('message', '獲取排程任務失敗')}), 500
        # 將返回的 Pydantic Schema 列表轉換為字典列表
        tasks_list = [task.model_dump() for task in result.get('tasks', [])]
        return jsonify(tasks_list), 200
    except Exception as e:
        return handle_api_error(e)
    
@tasks_bp.route('/scheduled', methods=['POST'])
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
        if task:
            # 將任務添加到排程器
            scheduler = get_scheduler_service()
            # 假設 add_or_update_task_to_scheduler 會處理自己的 session
            scheduler_result = scheduler.add_or_update_task_to_scheduler(task)
            if not scheduler_result.get('success'):
                # 如果添加到排程器失敗，返回錯誤
                # 注意：這裡可能需要考慮是否回滾已創建的任務，但目前服務層未提供此功能
                logger.error(f"任務 {task.id} 已創建但添加到排程器失敗: {scheduler_result.get('message')}")
                # 即使排程失敗，任務本身已創建成功，仍返回 201，但附帶排程失敗信息
                response_message = f"{create_task_result.get('message', '任務創建成功')}, 但添加到排程器失敗: {scheduler_result.get('message')}"
                return jsonify({
                    "success": True, # 任務創建本身是成功的
                    "message": response_message,
                    "task": task.model_dump() # 返回創建的任務信息
                }), 201 # HTTP 201 Created
            
        # 創建和排程都成功
        return jsonify({
            "success": True,
            "message": create_task_result.get('message', '任務創建並排程成功'),
            "task": task.model_dump() if task else None
        }), 201
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/scheduled/<int:task_id>', methods=['PUT'])
def update_scheduled_task(task_id): # 移除了 is_active 參數，因為 PUT 通常不這樣傳遞狀態
    if not request.is_json:
         return jsonify(success=False, message='請求必須是 application/json'), 415
    if not request.data: # 檢查是否有實際的請求體
         return jsonify(success=False, message='缺少任務資料'), 400
    data = request.get_json() or {}
    try:
        service = get_crawler_task_service()

        # 獲取當前任務資料 (假設總是更新活躍任務)
        get_task_result = service.get_task_by_id(task_id, is_active=True)
        if not get_task_result.get('success'):
            return jsonify({"success": False, "message": get_task_result.get('message', '找不到任務')}), 404

        db_task = get_task_result.get('task')
        if not db_task: # 再次確認 task 是否真的存在
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
            # 如果更新失敗 (例如 task_id 不存在於 update 調用中)，返回 404 或 500
            status_code = 404 if "不存在" in update_result.get('message', '') else 500
            return jsonify(update_result), status_code
            
        updated_task = update_result.get('task')
        if updated_task:
            # 更新排程器中的任務
            scheduled_result = get_scheduler_service().add_or_update_task_to_scheduler(updated_task)
            if not scheduled_result.get('success'):
                 # 排程更新失敗，記錄錯誤但任務更新本身成功
                 logger.error(f"任務 {task_id} 已更新但更新排程失敗: {scheduled_result.get('message')}")
                 response_message = f"{update_result.get('message', '任務更新成功')}, 但更新排程失敗: {scheduled_result.get('message')}"
                 return jsonify({
                     "success": True,
                     "message": response_message,
                     "task": updated_task.model_dump()
                 }), 200
        
        # 任務更新和排程更新都成功
        return jsonify({
            "success": True,
            "message": update_result.get('message', '任務更新並排程成功'),
            "task": updated_task.model_dump() if updated_task else None
        }), 200
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/scheduled/<int:task_id>', methods=['DELETE'])
def delete_scheduled_task(task_id):
    try:
        service = get_crawler_task_service()
        scheduler = get_scheduler_service()
        
        # 先嘗試從排程器移除
        scheduled_result = scheduler.remove_task_from_scheduler(task_id)
        # 即使排程器移除失敗 (可能原本就不在排程中)，也繼續嘗試刪除任務
        if not scheduled_result['success']:
             logger.warning(f"從排程器移除任務 {task_id} 失敗或未找到: {scheduled_result.get('message')}")

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
def fetch_full_article_manual_task():
    """抓取完整文章的手動任務端點 (創建新任務並立即執行)"""
    if not request.is_json:
         return jsonify(success=False, message='請求必須是 application/json'), 415 # Unsupported Media Type
    if not request.data: # 檢查是否有實際的請求體
         return jsonify(success=False, message='缺少任務資料'), 400 # Bad Request
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
        status_code = 202 if executor_result.get('success') else 500
        return jsonify(executor_result), status_code
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/<int:task_id>/status', methods=['GET'])
def get_task_status(task_id):
    try:
        task_executor = get_task_executor_service()
        executor_result = task_executor.get_task_status(task_id)
        # get_task_status 返回: {'success': bool, 'task_status': str, 'scrape_phase': str, 'progress': int, 'message': str, 'task': Optional[Schema]}
        status_code = 200 if executor_result.get('success') else 404
        
        # 如果成功且包含 task schema，將其轉換為 dict
        if executor_result.get('success') and executor_result.get('task'):
             executor_result['task'] = executor_result['task'].model_dump()

        return jsonify(executor_result), status_code
    except Exception as e:
        return handle_api_error(e)

# 修改：移除 task_id，因為這是創建一個新任務
@tasks_bp.route('/manual/collect-links', methods=['POST'])
def fetch_links_manual_task():
    """抓取連結的手動任務端點 (創建新任務並立即執行)"""
    if not request.is_json:
         return jsonify(success=False, message='請求必須是 application/json'), 415 # Unsupported Media Type
    if not request.data: # 檢查是否有實際的請求體
         return jsonify(success=False, message='缺少任務資料'), 400 # Bad Request
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
        
        status_code = 202 if executor_result.get('success') else 500
        return jsonify(executor_result), status_code
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/<int:task_id>/links', methods=['GET'])
def get_unscraped_links(task_id):
    """獲取指定任務關聯的、未抓取的文章連結 (預覽)"""
    try:
        article_service = get_article_service()
        # is_preview=True 返回包含預覽欄位的字典列表
        result = article_service.find_unscraped_articles(task_id=task_id, is_preview=True)
        
        status_code = 200 if result.get('success') else 404
        return jsonify(result), status_code
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/<int:task_id>/fetch-content', methods=['POST'])
def fetch_content_manual_task(task_id):
    """針對現有任務，觸發僅抓取內容的操作 (同步執行)"""
    if not request.is_json:
         return jsonify(success=False, message='請求必須是 application/json'), 415 # Unsupported Media Type
    if not request.data: # 檢查是否有實際的請求體
         return jsonify(success=False, message='缺少任務資料'), 400 # Bad Request
    try:
        data = request.get_json() or {}
        # 移除 data 為空的檢查，因為可能只傳 task_id 而 task_args 由後續邏輯處理

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

        status_code = 202 if executor_result.get('success') else 500
        return jsonify(executor_result), status_code

    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/<int:task_id>/results', methods=['GET'])
def get_scraped_task_results(task_id):
    """獲取指定任務關聯的、已抓取的文章結果 (預覽)"""
    try:
        article_service = get_article_service()
        # is_preview=True 返回包含預覽欄位的字典列表
        result = article_service.find_scraped_articles(task_id=task_id, is_preview=True)
        
        status_code = 200 if result.get('success') else 404
        return jsonify(result), status_code
    except Exception as e:
        return handle_api_error(e)

@tasks_bp.route('/manual/test', methods=['POST'])
def test_crawler():
    """測試爬蟲任務 (不會創建或執行實際任務)"""
    if not request.is_json:
         return jsonify(success=False, message='請求必須是 application/json'), 415 # Unsupported Media Type
    if not request.data: # 檢查是否有實際的請求體
         return jsonify(success=False, message='缺少任務資料'), 400 # Bad Request
    try:
        data = request.get_json() or {}
        if not data:
            logger.error(f"缺少測試資料: {data}")
            return jsonify({"success": False, "message": "缺少測試資料"}), 400
            
        crawler_name = data.get('crawler_name')
        if not crawler_name:
             logger.error(f"缺少 crawler_name: {data}")
             return jsonify({"success": False, "message": "缺少 crawler_name"}), 400

        service = get_crawler_task_service() # 獲取 service 實例用於驗證

        test_task_args = data.get('task_args', TASK_ARGS_DEFAULT).copy()
        test_task_args.update({
            'scrape_mode': ScrapeMode.LINKS_ONLY.value,
            'is_test': True,
            'max_pages': min(1, test_task_args.get('max_pages', 1)), # 最多1頁
            'num_articles': min(5, test_task_args.get('num_articles', 5)), # 最多5篇
            'save_to_csv': False, # 不保存
            'save_to_database': False, # 不保存
            'timeout': 30 # 短超時
        })
        
        # 構造完整的 task_data 以供驗證
        task_data_for_validation = {
            'crawler_id': data.get('crawler_id', 0),
            'crawler_name': crawler_name, # 或 crawler_id 如果前端傳遞 ID
            'task_name': f"測試_{crawler_name}",
            'task_args': test_task_args,
            'scrape_mode': ScrapeMode.LINKS_ONLY.value,
            'is_auto': False
        }

        # 驗證模擬的任務數據 (非更新)
        logger.info(f"驗證模擬的任務數據: {task_data_for_validation}")
        validated_result = service.validate_task_data(task_data_for_validation, is_update=False)
        if not validated_result.get('success'):
            # 如果驗證失敗，說明參數有問題
            logger.error(f"驗證失敗: {validated_result}")
            return jsonify(validated_result), 400
            
        # 獲取驗證後的參數 (主要是 task_args)
        validated_test_params = validated_result.get('data', {}).get('task_args', {})

        # 執行測試
        task_executor = get_task_executor_service()
        # test_crawler 服務方法接收爬蟲名稱和測試參數 (task_args)
        executor_result = task_executor.test_crawler(crawler_name, validated_test_params)
        
        # test_crawler 返回: {'success': bool, 'message': str, 'result': Dict}
        status_code = 200 if executor_result.get('success') else 500
        return jsonify(executor_result), status_code
    except Exception as e:
        return handle_api_error(e)

# 通用任務端點
@tasks_bp.route('/<int:task_id>/cancel', methods=['POST'])
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
def get_task_history(task_id):
    try:
        # 從 CrawlerTaskService 獲取歷史記錄
        service = get_crawler_task_service()
        # 注意: get_task_history 在 CrawlerTaskService 中
        result = service.get_task_history(task_id)
        
        if not result.get('success'):
            return jsonify(result), 404

        # 將 history schema 列表轉換為 dict 列表
        histories_list = [h.model_dump() for h in result.get('histories', [])]
        
        # 構造最終的 JSON 響應
        response_data = {
            'success': True,
            'message': result.get('message', '獲取任務歷史成功'),
            'histories': histories_list,
            'total_count': result.get('total_count', len(histories_list))
        }
        return jsonify(response_data), 200
    except Exception as e:
        return handle_api_error(e)

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
            errors: Optional[Dict]
            data: Optional[Dict] - 驗證通過的數據
    """
    if 'task_args' not in task_data or not task_data['task_args']:
        task_data['task_args'] = TASK_ARGS_DEFAULT.copy() # 使用副本避免修改預設值
    
    # 確保 scrape_mode 在 task_args 中也設置一致 (如果 task_args 裡沒有)
    if 'scrape_mode' not in task_data['task_args']:
         task_data['task_args']['scrape_mode'] = scrape_mode
         
    # task_data 的頂層也需要 scrape_mode 和 is_auto 供驗證器使用
    task_data['scrape_mode'] = scrape_mode
    task_data['is_auto'] = is_auto
    
    # 調用服務進行驗證
    validation_result = service.validate_task_data(task_data, is_update=is_update)
    
    # 清理掉臨時加到頂層的 scrape_mode 和 is_auto (如果驗證成功且返回了 data)
    # 驗證器應該只返回模型定義的字段，所以這步可能不需要
    # if validation_result.get('success') and validation_result.get('data'):
    #     validation_result['data'].pop('scrape_mode', None)
    #     validation_result['data'].pop('is_auto', None)

    return validation_result
