from typing import Dict, Any, List
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.services.crawlers_service import CrawlersService
from src.database.base_repository import SchemaType
from pydantic import ValidationError as PydanticValidationError
from src.error.errors import ValidationError, DatabaseOperationError
import logging
from src.models.crawler_tasks_model import ScrapeMode
import re
from src.utils.model_utils import (
    validate_str, validate_int, validate_boolean, validate_positive_int,
    validate_url, validate_cron_expression, validate_list, validate_dict
)

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def is_valid_cron_expression(cron_expression: str) -> bool:
    """驗證cron表達式是否有效
    
    使用 model_utils 中的 validate_cron_expression 函數包裝
    
    Args:
        cron_expression: 要驗證的cron表達式
        
    Returns:
        bool: 表示表達式是否有效
    """
    try:
        # Set required=True to reject empty strings
        validator = validate_cron_expression("cron_expression", required=True)
        validator(cron_expression)
        return True
    except Exception:
        return False


def validate_crawler_data_api(
    data: Dict[str, Any],
    service: CrawlersService,  # 改為接收Service而非Repository
    is_update: bool = False
) -> Dict[str, Any]:
    """使用CrawlersService驗證API的爬蟲資料
    
    直接使用 repository.validate_data 方法，確保與底層模型驗證邏輯一致
    
    Args:
        data: 要驗證的爬蟲資料
        service: 爬蟲服務實例
        is_update: 是否為更新操作
        
    Returns:
        Dict[str, Any]: 驗證後的爬蟲資料
    """
    try:
        # 確保非更新操作時 source_name 欄位存在
        if not is_update and 'source_name' not in data:
            logger.warning("來源名稱 (source_name) 是必填欄位")
            raise ValidationError("來源名稱 (source_name) 是必填欄位")
        
        # 獲取 repository 並調用其 validate_data 方法
        repository = service._get_repository()
        schema_type = SchemaType.UPDATE if is_update else SchemaType.CREATE
        
        # 使用 repository 的 validate_data 進行基本驗證
        validated_data = repository.validate_data(data, schema_type)
        
        # 返回驗證後的資料
        return validated_data
    except Exception as e:
        logger.warning(f"API請求的爬蟲資料驗證失敗: {e}")
        if isinstance(e, ValidationError):
            raise e
        raise ValidationError(str(e))

def validate_task_data_api(
    data: Dict[str, Any],
    service,  # 改為接收Service而非Repository
    is_update: bool = False
) -> Dict[str, Any]:
    """使用CrawlerTaskService驗證API的任務資料
    
    驗證頂層欄位（包括 scrape_mode），並對 task_args 進行內部驗證，
    最後使用 repository.validate_data 方法進行基本模型欄位驗證。
    
    Args:
        data: 要驗證的任務資料
        service: 任務服務實例
        is_update: 是否為更新操作
        
    Returns:
        Dict[str, Any]: 驗證後的任務資料
    """
    try:
        # --- 驗證頂層 scrape_mode ---
        if 'scrape_mode' in data:
            scrape_mode_value = data['scrape_mode']
            try:
                if isinstance(scrape_mode_value, str):
                    # 嘗試將字符串轉換為枚舉以驗證其有效性
                    ScrapeMode(scrape_mode_value)
                    # 驗證通過後，可以保留字符串形式，讓 service 層處理轉換
                    # data['scrape_mode'] = ScrapeMode(scrape_mode_value) # 或者在這裡轉換
                elif isinstance(scrape_mode_value, ScrapeMode):
                    # 如果傳入的是枚舉實例，轉換為其 value (字符串) 以便後續處理
                    data['scrape_mode'] = scrape_mode_value.value
                else:
                    # 不接受其他類型
                    logger.warning(f"無效的 scrape_mode 類型: {type(scrape_mode_value)}")
                    raise ValidationError(f"無效的抓取模式類型: {type(scrape_mode_value)}")
            except ValueError:
                # 字符串不是有效的枚舉值
                logger.warning(f"無效的scrape_mode值: {scrape_mode_value}")
                raise ValidationError(f"無效的抓取模式值: {scrape_mode_value}")
        # 如果 scrape_mode 不在 data 中，我們假設路由層會設置默認值或保留現有值，
        # 驗證器本身不強制要求此欄位必須存在，除非在 repository.validate_data 中有要求。

        # --- 確保必要的欄位存在 (主要用於創建操作) ---
        if not is_update:
            # 基本的必要欄位檢查 (可以根據需要擴展)
            required_fields = ['task_name', 'crawler_id']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                 # 將詳細資訊合併到錯誤訊息中
                 error_message = f"缺少必要欄位: {', '.join(missing_fields)}"
                 logger.warning(error_message)
                 raise ValidationError(error_message) # 移除 details 參數
            
            # 為測試數據或簡化調用添加默認值 (如果服務層不處理)
            if 'max_retries' not in data:
                data['max_retries'] = 3
            if 'retry_count' not in data:
                data['retry_count'] = 0
            # 如果 scrape_mode 未提供，路由層應已處理，這裡不再設置默認值

        # --- 處理 task_args 內部驗證 ---
        if 'task_args' in data and isinstance(data['task_args'], dict):
            task_args = data['task_args']
            
            # 移除 task_args 內部對 scrape_mode 的驗證邏輯
            # if 'scrape_mode' in task_args: ... (舊邏輯已移除)
            
            # 驗證數值類型參數
            numeric_params = ['max_pages', 'num_articles', 'min_keywords', 'timeout']
            for param in numeric_params:
                if param in task_args:
                    try:
                        # 允許為 None 或正整數
                        if task_args[param] is not None:
                           validate_positive_int(param)(task_args[param])
                    except Exception as e:
                        raise ValidationError(f"task_args.{param}: {str(e)}")
            
            # 驗證可為小數的數值類型參數
            float_params = ['retry_delay']
            for param in float_params:
                if param in task_args:
                     # 允許為 None 或正數
                    if task_args[param] is not None and (not isinstance(task_args[param], (int, float)) or task_args[param] <= 0):
                        logger.warning(f"task_args.'{param}' 必須是正數")
                        raise ValidationError(f"task_args.'{param}' 必須是正數")
            
            # 驗證布爾類型參數
            bool_params = ['ai_only', 'save_to_csv', 'save_to_database', 'get_links_by_task_id']
            for param in bool_params:
                if param in task_args:
                    try:
                         # 允許為 None 或布爾值
                         if task_args[param] is not None:
                            validate_boolean(param)(task_args[param])
                    except Exception as e:
                        raise ValidationError(f"task_args.{param}: {str(e)}")
            
            # 驗證特定模式下的必要參數 (如果頂層 scrape_mode 是 CONTENT_ONLY)
            # 注意：這裡依賴於頂層 scrape_mode 已經被驗證（如果存在）
            current_scrape_mode = data.get('scrape_mode')
            if current_scrape_mode == ScrapeMode.CONTENT_ONLY.value:
                # 如果不從任務ID獲取連結，則必須提供 article_ids 或 article_links
                if task_args.get('get_links_by_task_id') is False:
                    if 'article_ids' not in task_args and 'article_links' not in task_args:
                        logger.warning("內容抓取模式且不從任務ID獲取連結時，必須提供 'article_ids' 或 'article_links'")
                        raise ValidationError("內容抓取模式且不從任務ID獲取連結時，必須提供 'article_ids' 或 'article_links'")
                    
                    # 驗證 article_ids 和 article_links 的類型
                    if 'article_ids' in task_args:
                        try:
                            # Allow empty list or None
                            if task_args['article_ids'] is not None:
                               # 移除 item_type 參數
                               validate_list("article_ids", min_length=0)(task_args['article_ids']) 
                        except Exception as e:
                            raise ValidationError(f"task_args.article_ids: {str(e)}")
                    
                    if 'article_links' in task_args:
                        try:
                            # Allow empty list or None
                            if task_args['article_links'] is not None:
                               # 移除 item_type 參數
                               validate_list("article_links", min_length=0)(task_args['article_links'])
                        except Exception as e:
                            raise ValidationError(f"task_args.article_links: {str(e)}")
        
        # --- 調用 Repository 的基本驗證 ---
        repository = service._get_repository('CrawlerTask')
        schema_type = SchemaType.UPDATE if is_update else SchemaType.CREATE
        
        try:
            validated_data = repository.validate_data(data, schema_type)
            return validated_data
        except PydanticValidationError as e: 
            error_details = e.errors() 
            first_error = error_details[0] if error_details else {}
            field = first_error.get('loc', ['unknown'])[0] if first_error.get('loc') else 'unknown'
            msg = first_error.get('msg', '驗證失敗')
            # details = {field: msg} # 移除 details 參數
            logger.warning(f"Repository Pydantic 驗證失敗: {e}")
             # 將詳細資訊合併到錯誤訊息中
            raise ValidationError(f"欄位 '{field}' 驗證失敗: {msg}") # 移除 details 參數

        except Exception as e: # 捕獲 Repository 其他驗證錯誤
            logger.warning(f"Repository驗證失敗: {e}")
            if isinstance(e, ValidationError):
                raise e # 如果 repository 直接拋出 ValidationError，重新拋出
            raise ValidationError(f"Repository 驗證失敗: {str(e)}")
            
    except ValidationError as e: # 重新拋出 API 層級的 ValidationError
         raise e
    except Exception as e: # 捕獲 API 層級的其他意外錯誤
        logger.error(f"API請求的任務資料驗證時發生意外錯誤: {e}", exc_info=True)
        raise ValidationError(f"任務資料驗證時發生意外錯誤: {str(e)}")
    
