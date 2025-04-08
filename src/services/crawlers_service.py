import logging
from typing import Optional, Dict, Any, List, TypeVar, Tuple, Type, cast
from src.models.crawlers_model import Base, Crawlers
from datetime import datetime, timezone
from src.models.crawlers_schema import CrawlersCreateSchema, CrawlersUpdateSchema
from src.error.errors import DatabaseOperationError, ValidationError
from src.database.crawlers_repository import CrawlersRepository
from src.services.base_service import BaseService
from src.database.base_repository import BaseRepository

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 通用類型變數，用於泛型方法
T = TypeVar('T', bound=Base)

# 添加 DatetimeProvider 輔助類，用於在測試中替換
class DatetimeProvider:
    @staticmethod
    def now(tz=None):
        return datetime.now(tz)

class CrawlersService(BaseService[Crawlers]):
    """爬蟲服務，提供爬蟲相關業務邏輯"""
    
    def __init__(self, db_manager=None):
        super().__init__(db_manager)
        self.datetime_provider = DatetimeProvider()

    def _get_repository_mapping(self) -> Dict[str, Tuple[Type[BaseRepository], Type[Base]]]:
        """提供儲存庫映射"""
        return {
            'Crawler': (CrawlersRepository, Crawlers)
        }
    
    def _get_repository(self) -> CrawlersRepository:
        """獲取爬蟲資料庫訪問對象"""
        return cast(CrawlersRepository, super()._get_repository('Crawler'))

    def create_crawler(self, crawler_data: Dict[str, Any]) -> Dict[str, Any]:
        """創建新爬蟲設定"""
        try:
            with self._transaction():
                # 添加必要的欄位
                now = self.datetime_provider.now(timezone.utc)
                crawler_data.update({
                    'created_at': now,
                    'updated_at': now
                })
                
                # 使用 Pydantic 驗證資料
                try:
                    validated_data = CrawlersCreateSchema.model_validate(crawler_data).model_dump()
                except Exception as e:
                    return {
                        'success': False,
                        'message': f"爬蟲設定資料驗證失敗: {str(e)}"
                    }

                crawler_repo = self._get_repository()
                if not crawler_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'crawler': None
                    }
                result = crawler_repo.create(validated_data)
                
                if not result:
                    return {
                        'success': False,
                        'message': "創建爬蟲設定失敗",
                        'crawler': None
                    }
                
                return {
                    'success': True,
                    'message': "爬蟲設定創建成功",
                    'crawler': result
                }
                
        except Exception as e:
            logger.error(f"創建爬蟲設定失敗: {str(e)}")
            raise e

    def get_all_crawlers(self, limit: Optional[int] = None, offset: Optional[int] = None,
                        sort_by: Optional[str] = None, sort_desc: bool = False) -> Dict[str, Any]:
        """獲取所有爬蟲設定"""
        try:
            with self._transaction():
                crawler_repo = self._get_repository()
                if not crawler_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'crawlers': []
                    }
                crawlers = crawler_repo.get_all(
                    limit=limit,
                    offset=offset,
                    sort_by=sort_by,
                    sort_desc=sort_desc
                )
                
                return {
                    'success': True,
                    'message': "獲取爬蟲設定列表成功",
                    'crawlers': crawlers or []
                }
        except Exception as e:
            logger.error(f"獲取所有爬蟲設定失敗: {str(e)}")
            raise e

    def get_crawler_by_id(self, crawler_id: int) -> Dict[str, Any]:
        """根據ID獲取爬蟲設定"""
        try:
            with self._transaction():
                crawler_repo = self._get_repository()
                if not crawler_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'crawler': None
                    }
                crawler = crawler_repo.get_by_id(crawler_id)
                
                if not crawler:
                    return {
                        'success': False,
                        'message': f"爬蟲設定不存在，ID={crawler_id}",
                        'crawler': None
                    }
                
                return {
                    'success': True,
                    'message': "獲取爬蟲設定成功",
                    'crawler': crawler
                }
        except Exception as e:
            logger.error(f"獲取爬蟲設定失敗，ID={crawler_id}: {str(e)}")
            raise e

    def update_crawler(self, crawler_id: int, crawler_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新爬蟲設定"""
        try:
            with self._transaction():
                # 自動更新 updated_at 欄位
                crawler_data['updated_at'] = self.datetime_provider.now(timezone.utc)
                
                # 使用 Pydantic 驗證資料
                try:
                    validated_data = CrawlersUpdateSchema.model_validate(crawler_data).model_dump()
                except Exception as e:
                    return {
                        'success': False,
                        'message': f"爬蟲設定更新資料驗證失敗: {str(e)}",
                        'crawler': None
                    }
                
                crawler_repo = self._get_repository()
                if not crawler_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'crawler': None
                    }
                
                # 檢查爬蟲是否存在
                original_crawler = crawler_repo.get_by_id(crawler_id)
                if not original_crawler:
                    return {
                        'success': False,
                        'message': f"爬蟲設定不存在，ID={crawler_id}",
                        'crawler': None
                    }
                
                result = crawler_repo.update(crawler_id, validated_data)
                
                if not result:
                    return {
                        'success': False,
                        'message': f"更新爬蟲設定失敗，ID={crawler_id}",
                        'crawler': None
                    }
                
                return {
                    'success': True,
                    'message': "爬蟲設定更新成功",
                    'crawler': result
                }
                
        except Exception as e:
            logger.error(f"更新爬蟲設定失敗，ID={crawler_id}: {str(e)}")
            raise e

    def delete_crawler(self, crawler_id: int) -> Dict[str, Any]:
        """刪除爬蟲設定"""
        try:
            with self._transaction():
                crawler_repo = self._get_repository()
                if not crawler_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                    }
                result = crawler_repo.delete(crawler_id)
                
                if not result:
                    return {
                        'success': False,
                        'message': f"爬蟲設定不存在，ID={crawler_id}"
                    }
                
                return {
                    'success': True,
                    'message': "爬蟲設定刪除成功"
                }
                
        except Exception as e:
            logger.error(f"刪除爬蟲設定失敗，ID={crawler_id}: {str(e)}")
            raise e

    def get_active_crawlers(self) -> Dict[str, Any]:
        """獲取所有活動中的爬蟲設定"""
        try:
            with self._transaction():
                crawler_repo = self._get_repository()
                if not crawler_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'crawlers': []
                    }
                crawlers = crawler_repo.find_active_crawlers()
                if not crawlers:
                    return {
                        'success': False,
                        'message': "找不到任何活動中的爬蟲設定",
                        'crawlers': []
                    }
                return {
                    'success': True,
                    'message': "獲取活動中的爬蟲設定成功",
                    'crawlers': crawlers or []
                }
        except Exception as e:
            logger.error(f"獲取活動中的爬蟲設定失敗: {str(e)}")
            raise e

    def toggle_crawler_status(self, crawler_id: int) -> Dict[str, Any]:
        """切換爬蟲活躍狀態"""
        try:
            with self._transaction():
                crawler_repo = self._get_repository()
                if not crawler_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'crawler': None
                    }
                result = crawler_repo.toggle_active_status(crawler_id)
                
                if not result:
                    return {
                        'success': False,
                        'message': f"爬蟲設定不存在或切換失敗，ID={crawler_id}",
                        'crawler': None
                    }
                
                updated_crawler = crawler_repo.get_by_id(crawler_id)
                if updated_crawler: 
                    return {
                        'success': True,
                        'message': f"成功切換爬蟲狀態，新狀態={updated_crawler.is_active}",
                        'crawler': updated_crawler
                    }
                else:
                    return {
                        'success': False,
                        'message': f"爬蟲設定不存在，ID={crawler_id}",
                        'crawler': None
                    }
                
        except Exception as e:
            logger.error(f"切換爬蟲狀態失敗，ID={crawler_id}: {str(e)}")
            raise e
    
    def get_crawlers_by_name(self, name: str) -> Dict[str, Any]:
        """根據名稱模糊查詢爬蟲設定"""
        try:
            with self._transaction():
                crawler_repo = self._get_repository()
                if not crawler_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'crawlers': []
                    }
                crawlers = crawler_repo.find_by_crawler_name(name)
                if not crawlers:
                    return {
                        'success': False,
                        'message': "找不到任何符合條件的爬蟲設定",
                        'crawlers': []
                    }
                return {
                    'success': True,
                    'message': "獲取爬蟲設定列表成功",
                    'crawlers': crawlers or []
                }   
        except Exception as e:
            logger.error(f"獲取爬蟲設定列表失敗: {str(e)}")
            raise e
