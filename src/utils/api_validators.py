from typing import Dict, Any, List
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.services.crawlers_service import CrawlersService
from src.database.base_repository import SchemaType
from pydantic import ValidationError
import logging
from src.models.crawler_tasks_model import ScrapeMode

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
        # 特殊處理task_args中的scrape_mode參數
        if 'task_args' in data and isinstance(data['task_args'], dict):
            task_args = data['task_args']
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
            
        return service.validate_task_data(data, is_update)
    except ValidationError as e:
        logger.warning(f"API請求的任務資料驗證失敗: {e}")
        raise e
    
