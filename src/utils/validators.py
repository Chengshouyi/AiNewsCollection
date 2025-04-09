from typing import Dict, Any, List
from src.error.errors import ValidationError
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.database.crawlers_repository import CrawlersRepository
from src.utils.schema_utils import validate_required_fields_schema
from src.utils.model_utils import validate_cron_expression, validate_dict, validate_boolean, validate_str, validate_url


def validate_task_data(data: Dict[str, Any], tasks_repo: CrawlerTasksRepository) -> Dict[str, Any]:
    """
    驗證任務資料
    
    Args:
        data: 任務資料
        
    Returns:
        驗證後的資料
        
    Raises:
        ValidationError: 當驗證失敗時
    """
    # 檢查必填欄位
    validated_data = tasks_repo.validate_entity_data(data)
    
    return validated_data 

def validate_crawler_data(data: Dict[str, Any], crawlers_repo: CrawlersRepository) -> Dict[str, Any]:
    """
    驗證爬蟲配置資料
    
    Args:
        data: 爬蟲配置資料
        
    Returns:
        驗證後的資料
        
    Raises:
        ValidationError: 當驗證失敗時
    """
    # 檢查必填欄位
    validated_data = crawlers_repo.validate_entity_data(data)
    
    return validated_data 
    
