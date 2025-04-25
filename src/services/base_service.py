import logging
from typing import Dict, Any, Optional, TypeVar, Generic, List, Type, Tuple, cast
from contextlib import contextmanager

from sqlalchemy.orm import Session

from src.database.database_manager import DatabaseManager
from src.database.base_repository import BaseRepository, SchemaType
from src.models.base_model import Base
from src.error.errors import DatabaseOperationError, ValidationError
from src.config import get_db_manager

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

T = TypeVar('T', bound=Base)

class BaseService(Generic[T]):
    """
    基礎服務類，負責管理資料庫存取及儲存庫生命週期
    """
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        初始化服務
        
        Args:
            db_manager: 資料庫管理器實例 (如果為None，則創建一個新的)
        """
        self.db_manager = db_manager or get_db_manager()
    
    def _get_repository_mapping(self) -> Dict[str, Tuple[Type[BaseRepository], Type[Base]]]:
        """
        獲取儲存庫映射表，需要被子類重寫
        
        Returns:
            儲存庫名稱到 (儲存庫類, 模型類) 的映射字典
        """
        raise NotImplementedError("子類必須實現此方法提供儲存庫映射")
    
    def _get_repository(self, repository_name: str, session: Session) -> BaseRepository[T]:
        """
        獲取指定的儲存庫實例
        
        Args:
            repository_name: 儲存庫名稱
            session: 資料庫會話實例
        
        Returns:
            儲存庫實例
        
        Raises:
            DatabaseOperationError: 獲取儲存庫失敗
        """
        try:
            # 獲取儲存庫映射
            repository_mapping = self._get_repository_mapping()
            
            if repository_name not in repository_mapping:
                error_msg = f"未知的儲存庫名稱: {repository_name}"
                logger.error(error_msg)
                raise DatabaseOperationError(error_msg)
            
            # 獲取儲存庫類和模型類
            repository_class, model_class = repository_mapping[repository_name]
            
            # 使用傳入的 session 創建儲存庫實例
            repository = repository_class(session, model_class)
            
            return repository
        except Exception as e:
            # 移除 session 創建相關的錯誤處理
            error_msg = f"獲取儲存庫 {repository_name} 失敗: {str(e)}"
            logger.error(error_msg)
            raise DatabaseOperationError(error_msg) from e
    
    @contextmanager
    def _transaction(self):
        """
        事務上下文管理器，創建並管理 Session 的生命週期。
        
        Yields:
            Session: 資料庫會話實例
        
        Raises:
            Exception: 任何在事務中發生的異常
        """
        session = self.db_manager.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"事務執行失敗，已回滾: {str(e)}")
            # 根據需要決定是否重新拋出異常，這裡選擇重新拋出以通知上層調用者
            raise 
        finally:
            # 確保 session 在事務結束後關閉
            session.close()
    
    def validate_data(self, repository_name: str, entity_data: Dict[str, Any], schema_type: SchemaType) -> Dict[str, Any]:
        """
        公開方法：根據 repository_name 呼叫對應 Repository 的類別驗證方法。

        Args:
            repository_name: 儲存庫的名稱 (對應 _get_repository_mapping 中的鍵)。
            entity_data: 待驗證的原始字典資料。
            schema_type: 決定使用 CreateSchema 還是 UpdateSchema。

        Returns:
            Dict[str, Any]: 驗證並處理過的字典資料。

        Raises:
            DatabaseOperationError: 如果找不到對應的儲存庫類。
            ValidationError: 如果資料驗證失敗。
            Exception: 其他非預期錯誤。
        """
        try:
            repository_mapping = self._get_repository_mapping()
            if repository_name not in repository_mapping:
                error_msg = f"未知的儲存庫名稱: {repository_name}"
                logger.error(error_msg)
                raise DatabaseOperationError(error_msg)

            # 直接獲取 Repository 類別，而不是實例
            repository_class, _ = repository_mapping[repository_name]

            # 調用 Repository 類別上的 validate_data 方法
            # 這裡不需要 session 或 self (因為 validate_data 是 @classmethod)
            validated_data = repository_class.validate_data(entity_data, schema_type)
            return validated_data

        except (DatabaseOperationError, ValidationError) as e:
            # 直接重新拋出已知錯誤
            raise e
        except Exception as e:
            # 包裝其他未知錯誤
            error_msg = f"在 Service 層執行 {repository_name} 的 validate_data 時發生錯誤: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # 可以選擇拋出 ValidationError 或更通用的 ServiceError
            raise ValidationError(error_msg) from e

    def cleanup(self):
        """清理資源 (如果需要)"""
        # logger.info("BaseService cleanup called (no specific action needed in this version).") # <--- 註解或移除此行
        pass # 或者如果 cleanup 沒有其他事做，直接 pass

    def __del__(self):
        """確保清理方法被呼叫"""
        self.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        # 保持 False 以便異常能傳播
        return False
