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
    
    使用 repository.validate_data 方法進行基本驗證，並對 task_args 進行特殊處理
    
    Args:
        data: 要驗證的任務資料
        service: 任務服務實例
        is_update: 是否為更新操作
        
    Returns:
        Dict[str, Any]: 驗證後的任務資料
    """
    try:
        # 確保必要的欄位存在
        if not is_update:
            # 為測試數據添加必要欄位
            if 'max_retries' not in data:
                data['max_retries'] = 3
            if 'retry_count' not in data:
                data['retry_count'] = 0

        # 處理 task_args (在調用底層驗證前)
        if 'task_args' in data and isinstance(data['task_args'], dict):
            task_args = data['task_args']
            
            # 驗證 scrape_mode
            if 'scrape_mode' in task_args:
                # 確保scrape_mode是合法值
                try:
                    if isinstance(task_args['scrape_mode'], str):
                        # 嘗試將字符串轉換為枚舉
                        ScrapeMode(task_args['scrape_mode'])
                    else:
                        # 如果不是字符串，可能是枚舉本身，轉為字符串
                        if hasattr(task_args['scrape_mode'], 'value'):
                            task_args['scrape_mode'] = task_args['scrape_mode'].value
                        else:
                            # 不是有效的枚舉或字符串
                            logger.warning(f"無效的抓取模式: {task_args['scrape_mode']}")
                            raise ValidationError(f"無效的抓取模式: {task_args['scrape_mode']}")
                except ValueError:
                    # 不是有效的枚舉值
                    logger.warning(f"無效的scrape_mode值: {task_args['scrape_mode']}")
                    raise ValidationError(f"無效的scrape_mode值: {task_args['scrape_mode']}")
            
            # 驗證數值類型參數
            numeric_params = ['max_pages', 'num_articles', 'min_keywords', 'timeout']
            for param in numeric_params:
                if param in task_args:
                    try:
                        validate_positive_int(param)(task_args[param])
                    except Exception as e:
                        raise ValidationError(f"{param}: {str(e)}")
            
            # 驗證可為小數的數值類型參數
            float_params = ['retry_delay']
            for param in float_params:
                if param in task_args:
                    if not isinstance(task_args[param], (int, float)) or task_args[param] <= 0:
                        logger.warning(f"'{param}' 必須是正數")
                        raise ValidationError(f"'{param}' 必須是正數")
            
            # 驗證布爾類型參數
            bool_params = ['ai_only', 'save_to_csv', 'save_to_database', 'get_links_by_task_id']
            for param in bool_params:
                if param in task_args:
                    try:
                        validate_boolean(param)(task_args[param])
                    except Exception as e:
                        raise ValidationError(f"{param}: {str(e)}")
            
            # 驗證特定模式下的必要參數
            if task_args.get('scrape_mode') == ScrapeMode.CONTENT_ONLY.value:
                # 如果不從任務ID獲取連結，則必須提供 article_ids 或 article_links
                if task_args.get('get_links_by_task_id') is False:
                    if 'article_ids' not in task_args and 'article_links' not in task_args:
                        logger.warning("內容抓取模式且不從任務ID獲取連結時，必須提供 'article_ids' 或 'article_links'")
                        raise ValidationError("內容抓取模式且不從任務ID獲取連結時，必須提供 'article_ids' 或 'article_links'")
                    
                    # 驗證 article_ids 和 article_links 的類型
                    if 'article_ids' in task_args:
                        try:
                            # Allow empty list in this context
                            validate_list("article_ids", min_length=0)(task_args['article_ids'])
                        except Exception as e:
                            raise ValidationError(f"article_ids: {str(e)}")
                    
                    if 'article_links' in task_args:
                        try:
                            # Allow empty list in this context
                            validate_list("article_links", min_length=0)(task_args['article_links'])
                        except Exception as e:
                            raise ValidationError(f"article_links: {str(e)}")
        
        # 獲取 repository 並調用其 validate_data 方法(進行基本欄位驗證)
        repository = service._get_repository('CrawlerTask')
        schema_type = SchemaType.UPDATE if is_update else SchemaType.CREATE
        
        try:
            # 使用 repository 的 validate_data 進行基本驗證
            validated_data = repository.validate_data(data, schema_type)
        
            # 確保 task_args 中的自定義驗證結果也被保留
            if 'task_args' in data and 'task_args' in validated_data:
                validated_data['task_args'] = data['task_args']
        
            # 返回驗證後的資料
            return validated_data
        except Exception as e:
            logger.warning(f"Repository驗證失敗: {e}")
            if isinstance(e, ValidationError):
                raise e
            raise ValidationError(str(e))
            
    except Exception as e:
        logger.warning(f"API請求的任務資料驗證失敗: {e}")
        if isinstance(e, ValidationError):
            raise e
        raise ValidationError(str(e))
    
