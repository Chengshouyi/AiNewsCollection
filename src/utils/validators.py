from typing import Dict, Any, List
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.services.crawlers_service import CrawlersService
from src.database.base_repository import SchemaType
from pydantic import ValidationError
import logging
# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def validate_crawler_data_api(
    data: Dict[str, Any],
    service: CrawlersService,  # 改為接收Service而非Repository
    is_update: bool = False
) -> Dict[str, Any]:
    """使用CrawlersService驗證API的爬蟲資料"""
    try:
        return service.validate_crawler_data(data, is_update)
    except ValidationError as e:
        logger.warning(f"API請求的爬蟲資料驗證失敗: {e}")
        raise e

def validate_task_data_api(
    data: Dict[str, Any],
    service,  # 改為接收Service而非Repository
    is_update: bool = False
) -> Dict[str, Any]:
    """使用CrawlerTaskService驗證API的任務資料"""
    try:
        return service.validate_task_data(data, is_update)
    except ValidationError as e:
        logger.warning(f"API請求的任務資料驗證失敗: {e}")
        raise e
    
