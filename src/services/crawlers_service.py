import logging
from typing import Optional, Dict, Any, List, TypeVar, Tuple, cast
from src.models.crawlers_model import Base, Crawlers
from datetime import datetime, timezone
from src.models.crawlers_schema import CrawlersCreateSchema, CrawlersUpdateSchema
from src.error.errors import DatabaseOperationError, ValidationError
from src.database.database_manager import DatabaseManager
from src.database.crawlers_repository import CrawlersRepository
from sqlalchemy import func, or_

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

class CrawlersService:
    """爬蟲服務，提供爬蟲相關業務邏輯"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.datetime_provider = DatetimeProvider()  # 使用輔助類

    def _get_repository(self):
        """取得儲存庫的上下文管理器"""
        session = self.db_manager.Session()
        try:
            return CrawlersRepository(session, Crawlers), session
        except Exception as e:
            error_msg = f"取得儲存庫失敗: {e}"
            logger.error(error_msg)
            session.close()
            raise DatabaseOperationError(error_msg) from e
    
    def create_crawler(self, crawler_data: Dict[str, Any]) -> Optional[Crawlers]:
        """
        創建新爬蟲設定
        
        Args:
            crawler_data: 爬蟲設定資料字典
            
        Returns:
            創建成功的爬蟲設定或 None
        """
        repo, session = None, None
        try:
            # 添加必要的欄位
            now = self.datetime_provider.now(timezone.utc)
            crawler_data.update({
                'created_at': now,
                'updated_at': now
            })
            
            # 使用 Pydantic 驗證資料
            try:
                validated_data = CrawlersCreateSchema.model_validate(crawler_data).model_dump()
                logger.debug(f"爬蟲設定資料驗證成功: {validated_data}")
            except Exception as e:
                error_msg = f"爬蟲設定資料驗證失敗: {e}"
                logger.error(error_msg)
                raise ValidationError(error_msg) from e

            repo, session = self._get_repository()
            try:
                result = repo.create(validated_data)
                session.commit()
                logger.debug(f"成功創建爬蟲設定, ID={result.id}")
                return self._ensure_fresh_instance(result)
            except Exception as e:
                session.rollback()
                raise e
        except ValidationError as e:
            # 直接重新引發驗證錯誤
            if session:
                session.rollback()
            raise e
        except Exception as e:
            error_msg = f"創建爬蟲設定失敗: {e}"
            logger.error(error_msg)
            if session:
                session.rollback()
            # 將其他例外轉換為 ValidationError，保持一致性
            raise ValidationError(f"創建爬蟲設定失敗: {str(e)}")

    def get_all_crawlers(self, limit: Optional[int] = None, offset: Optional[int] = None, 
                         sort_by: Optional[str] = None, sort_desc: bool = False) -> List[Crawlers]:
        """
        獲取所有爬蟲設定，支持分頁和排序
        
        Args:
            limit: 限制返回數量，預設為 None（返回全部）
            offset: 起始偏移，預設為 None
            sort_by: 排序欄位，預設為 None
            sort_desc: 是否降序排序，預設為 False
            
        Returns:
            爬蟲設定列表
        """
        try:
            repo, session = self._get_repository()
            crawlers = repo.get_all(
                limit=limit,
                offset=offset,
                sort_by=sort_by,
                sort_desc=sort_desc
            )
            if not crawlers:
                return []
            return crawlers
        except Exception as e:
            error_msg = f"獲取所有爬蟲設定失敗: {e}"
            logger.error(error_msg)
            raise e
    
    def get_crawler_by_id(self, crawler_id: int) -> Optional[Crawlers]:
        """
        根據ID獲取爬蟲設定
        
        Args:
            crawler_id: 爬蟲設定ID
            
        Returns:
            爬蟲設定或 None
        """  
        try:
            repo, session = self._get_repository()
            crawler = repo.get_by_id(crawler_id)
            return crawler
        except Exception as e:
            error_msg = f"獲取爬蟲設定失敗，ID={crawler_id}: {e}"
            logger.error(error_msg)
            raise e

    def get_active_crawlers(self) -> List[Crawlers]:
        """
        獲取所有活動中的爬蟲設定
        
        Returns:
            活動中的爬蟲設定列表
        """
        try:
            repo, session = self._get_repository()
            crawlers = repo.find_active_crawlers()
            return crawlers
        except Exception as e:
            error_msg = f"獲取活動中的爬蟲設定失敗: {e}"
            logger.error(error_msg)
            raise e
    
    def get_crawlers_by_name(self, crawler_name: str) -> List[Crawlers]:
        """
        根據名稱模糊查詢爬蟲設定
        
        Args:
            crawler_name: 爬蟲名稱關鍵字
            
        Returns:
            符合條件的爬蟲設定列表
        """
        try:
            repo, session = self._get_repository()
            crawlers = repo.find_by_crawler_name(crawler_name)
            return crawlers
        except Exception as e:
            error_msg = f"根據名稱查詢爬蟲設定失敗: {e}"
            logger.error(error_msg)
            raise e
    
    def get_pending_crawlers(self) -> List[Crawlers]:
        """
        獲取待執行的爬蟲設定
        
        Returns:
            待執行的爬蟲設定列表
        """
        try:
            repo, session = self._get_repository()
            # 使用時間提供者
            current_time = self.datetime_provider.now(timezone.utc)
            
            # 直接使用 repository 方法獲取待執行爬蟲
            pending_crawlers = repo.find_pending_crawlers(current_time)
            return pending_crawlers
        except Exception as e:
            error_msg = f"獲取待執行的爬蟲設定失敗: {e}"
            logger.error(error_msg)
            raise e
    
    def update_crawler(self, crawler_id: int, crawler_data: Dict[str, Any]) -> Optional[Crawlers]:
        """
        更新爬蟲設定
        
        Args:
            crawler_id: 爬蟲設定ID
            crawler_data: 要更新的爬蟲設定資料
            
        Returns:
            更新成功的爬蟲設定或 None
        
        Raises:
            ValidationError: 當嘗試更新不可變欄位或資料驗證失敗時
        """
        repo, session = None, None
        try:
            # 自動更新 updated_at 欄位
            crawler_data['updated_at'] = self.datetime_provider.now(timezone.utc)
            
            # 使用 Pydantic 驗證資料
            try:
                validated_data = CrawlersUpdateSchema.model_validate(crawler_data).model_dump()
                logger.debug(f"爬蟲設定更新資料驗證成功: {validated_data}")
            except Exception as e:
                error_msg = f"爬蟲設定更新資料驗證失敗: {str(e)}"
                logger.error(error_msg)
                raise ValidationError(error_msg)
            
            repo, session = self._get_repository()
            
            # 檢查爬蟲是否存在
            original_crawler = repo.get_by_id(crawler_id)
            if not original_crawler:
                error_msg = f"爬蟲設定不存在，ID={crawler_id}"
                logger.error(error_msg)
                return None
            
            # 嘗試執行更新
            try:
                result = repo.update(crawler_id, validated_data)
                
                if not result:
                    error_msg = f"爬蟲設定更新失敗，ID不存在: {crawler_id}"
                    logger.error(error_msg)
                    return None
                    
                session.commit()
                logger.debug(f"成功更新爬蟲設定，ID={crawler_id}")
                return self._ensure_fresh_instance(result)
            except ValidationError as e:
                session.rollback()
                raise e
        except ValidationError as e:
            if session:
                session.rollback()
            raise e
        except Exception as e:
            error_msg = f"更新爬蟲設定失敗，ID={crawler_id}: {e}"
            logger.error(error_msg)
            if session:
                session.rollback()
            raise ValidationError(f"更新爬蟲設定失敗: {str(e)}")
    
    def delete_crawler(self, crawler_id: int) -> bool:
        """
        刪除爬蟲設定
        
        Args:
            crawler_id: 爬蟲設定ID
            
        Returns:
            是否成功刪除
        """              
        try:
            repo, session = self._get_repository()
            result = repo.delete(crawler_id)
            
            if not result:
                error_msg = f"欲刪除的爬蟲設定不存在，ID={crawler_id}"
                logger.error(error_msg)
                return False
                
            session.commit()
            log_info = f"成功刪除爬蟲設定，ID={crawler_id}"
            logger.debug(log_info)
            return True
        except Exception as e:
            error_msg = f"刪除爬蟲設定失敗，ID={crawler_id}: {str(e)}"
            logger.error(error_msg)
            if repo and session:
                session.rollback()
            raise e

    
    def toggle_crawler_status(self, crawler_id: int) -> Optional[Crawlers]:
        """
        切換爬蟲活躍狀態
        
        Args:
            crawler_id: 爬蟲設定ID
            
        Returns:
            更新後的爬蟲設定或 None
        """
        try:
            repo, session = self._get_repository()
            result = repo.toggle_active_status(crawler_id)
            
            if not result:
                logger.warning(f"切換爬蟲狀態失敗，爬蟲不存在，ID={crawler_id}")
                return None
                
            # 獲取更新後的爬蟲設定
            updated_crawler = repo.get_by_id(crawler_id)
            if updated_crawler:
                logger.debug(f"成功切換爬蟲狀態，ID={crawler_id}, 新狀態={updated_crawler.is_active}")
                return updated_crawler
            else:
                logger.warning(f"切換爬蟲狀態失敗，爬蟲不存在，ID={crawler_id}")
                return None
        except Exception as e:
            error_msg = f"切換爬蟲狀態失敗，ID={crawler_id}: {e}"
            logger.error(error_msg)
            raise e
    
    def get_crawlers_sorted_by_interval(self) -> List[Crawlers]:
        """
        獲取按爬取間隔排序的爬蟲設定
        
        Returns:
            按爬取間隔排序的爬蟲設定列表
        """
        try:
            repo, session = self._get_repository()
            crawlers = repo.get_sorted_by_interval()
            return crawlers
        except Exception as e:
            error_msg = f"獲取按間隔排序的爬蟲設定失敗: {e}"
            logger.error(error_msg)
            raise e
    
    def _ensure_fresh_instance(self, entity: Optional[T]) -> Optional[T]:
        """
        確保實體不是分離的實例
        
        如果實體已分離，則重新查詢；如果實體不存在，則返回 None
        """
        if entity is None:
            return None
        
        try:
            # 使用 getattr 安全訪問 id 屬性
            entity_id = getattr(entity, 'id', None)
            if entity_id is not None:
                return entity
            return None
        except Exception:
            # 如果實體已分離，則重新查詢
            if isinstance(entity, Crawlers):
                entity_id = getattr(entity, 'id', None)
                if entity_id is not None:
                    refreshed = self.get_crawler_by_id(entity_id)
                    return cast(T, refreshed)  # 使用 cast 進行類型轉換
            return None
