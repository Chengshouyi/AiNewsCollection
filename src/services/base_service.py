import logging
from typing import Dict, Any, Optional, TypeVar, Generic, List, Type, Tuple, cast
from contextlib import contextmanager

from sqlalchemy.orm import Session

from src.database.database_manager import DatabaseManager
from src.database.base_repository import BaseRepository, SchemaType
from src.models.base_model import Base
from src.error.errors import DatabaseOperationError, ValidationError
from src.error.service_errors import ServiceInitializationError
from src.config import get_db_manager

from src.utils.log_utils import LoggerSetup # 使用統一的 logger
logger = LoggerSetup.setup_logger(__name__)

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
        try:
            self.db_manager = db_manager or get_db_manager()
            if not self.db_manager:
                raise ServiceInitializationError("DatabaseManager could not be initialized.")
            self.repositories: Dict[str, BaseRepository] = {}
            self._repositories_mapping = self._get_repository_mapping()
        except Exception as e:
            logger.error(f"BaseService initialization failed: {e}", exc_info=True)
            raise ServiceInitializationError(f"Failed to initialize BaseService: {e}") from e


    
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
            session: 資料庫會話實例
        
        Raises:
            Exception: 任何在事務中發生的異常
        """
        try:
            with self.db_manager.session_scope() as session:
                yield session
        except DatabaseOperationError as e:
            # 將底層錯誤包裝或直接拋出
            logger.error(f"Transaction failed within BaseService: {e}", exc_info=True)
            raise # 或者 raise 特定服務層的錯誤 from e
        except Exception as e:
            logger.error(f"未預期的錯誤，事務執行失敗: {str(e)}", exc_info=True)
            # 根據需要決定是否重新拋出異常，這裡選擇重新拋出以通知上層調用者
            raise DatabaseOperationError(f"Unexpected error in transaction: {e}") from e
        
    
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
        """清理服務資源，主要是關閉 session"""
        # 實際的清理應該由 DatabaseManager 處理
        # Scoped Session 的清理通常在 request teardown 或線程結束時進行
        # 可以考慮在這裡顯式移除 session，如果不是在 web context 中
        if hasattr(self.db_manager, 'close_session'): # 假設有 close_session 方法
             logger.info("Cleaning up session via BaseService...")
             self.db_manager.close_session()

    def __del__(self):
        """確保清理方法被呼叫"""
        self.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        # 保持 False 以便異常能傳播
        return False
