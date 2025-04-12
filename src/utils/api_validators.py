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
    service: CrawlersService,
    is_update: bool = False
) -> Dict[str, Any]:
    """使用CrawlersService驗證API的爬蟲資料
    
    Args:
        data: 要驗證的爬蟲資料
        service: 爬蟲服務實例
        is_update: 是否為更新操作
        
    Returns:
        Dict[str, Any]: 驗證後的爬蟲資料
    """
    try:
        # 確保非更新操作時 source_name 欄位存在 (API 層級檢查)
        if not is_update and data.get('source_name') is None: # 檢查 None 或不存在
            logger.warning("來源名稱 (source_name) 是必填欄位")
            raise ValidationError("來源名稱 (source_name) 是必填欄位")
        

        # 調用 service 提供的驗證方法，該方法內部會使用 Pydantic Schema
        validation_result = service.validate_crawler_data(data, is_update)
        if not validation_result['success']:
             # 從 service 返回的結果中提取錯誤信息
             error_message = validation_result.get('message', '爬蟲資料驗證失敗')
             logger.warning(f"API請求的爬蟲資料驗證失敗: {error_message}")
             raise ValidationError(error_message) # 移除 details

        validated_data = validation_result['validated_data']
        
        # 返回驗證後的資料
        return validated_data
        
    except ValidationError as e: # 捕獲上面 raise 的 ValidationError
        logger.warning(f"API請求的爬蟲資料驗證失敗: {e}")
        raise e # 直接重新拋出
    except Exception as e: # 捕獲其他意外錯誤
        logger.error(f"API請求的爬蟲資料驗證時發生意外錯誤: {e}", exc_info=True)
        # 將 PydanticValidationError 或其他錯誤包裝成 ValidationError
        if isinstance(e, PydanticValidationError):
             error_details = e.errors()
             first_error = error_details[0] if error_details else {}
             field = first_error.get('loc', ['unknown'])[0] if first_error.get('loc') else 'unknown'
             msg = first_error.get('msg', '驗證失敗')
             raise ValidationError(f"欄位 '{field}' 驗證失敗: {msg}")
        raise ValidationError(f"爬蟲資料驗證時發生錯誤: {str(e)}")



        logger.error(f"API請求的任務資料驗證時發生意外錯誤: {e}", exc_info=True)
        raise ValidationError(f"任務資料驗證時發生意外錯誤: {str(e)}")
    
