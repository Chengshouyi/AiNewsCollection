from typing import Dict, Any, List
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.database.crawlers_repository import CrawlersRepository
from src.database.base_repository import SchemaType
from pydantic import ValidationError
import logging
# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def validate_crawler_data_api(
    data: Dict[str, Any],
    crawlers_repo: CrawlersRepository, # 接收 Repo 實例
    is_update: bool = False
) -> Dict[str, Any]:
    """使用 CrawlersRepository 的 validate_data 驗證 API 的爬蟲資料。"""
    schema_type = SchemaType.UPDATE if is_update else SchemaType.CREATE
    try:
        # 調用 Repository 的公開驗證方法
        return crawlers_repo.validate_data(data, schema_type)
    except ValidationError as e:
        # 可以選擇在這裡記錄更詳細的 API 層級日誌
        logger.warning(f"API 請求的爬蟲資料驗證失敗 ({schema_type.name}): {e}")
        raise e # 重新拋出，由 Flask 錯誤處理器接管

def validate_task_data_api(
    data: Dict[str, Any],
    tasks_repo: CrawlerTasksRepository, # 接收 Repo 實例
    is_update: bool = False
) -> Dict[str, Any]:
    """使用 CrawlerTasksRepository 的 validate_data 驗證 API 的任務資料。"""
    schema_type = SchemaType.UPDATE if is_update else SchemaType.CREATE
    try:
        # 調用 Repository 的公開驗證方法
        return tasks_repo.validate_data(data, schema_type)
    except ValidationError as e:
        logger.warning(f"API 請求的任務資料驗證失敗 ({schema_type.name}): {e}")
        raise e # 重新拋出
    
