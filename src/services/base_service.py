import logging
from typing import Dict, Any, Optional, TypeVar, Generic, List
from contextlib import contextmanager

from sqlalchemy.orm import Session

from src.database.database_manager import DatabaseManager
from src.database.base_repository import BaseRepository, SchemaType
from src.models.base_model import Base
from src.error.errors import DatabaseOperationError, ValidationError

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
        self.db_manager = db_manager or DatabaseManager()
    
    def _get_repository_mapping(self) -> Dict[str, tuple]:
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
    
    def cleanup(self):
        """
        清理服務使用的資源 (此版本無需特別操作)
        """
        # 因為 session 由 _transaction 管理，這裡不再需要關閉 session
        # self._repositories 已經移除，無需清理
        logger.info("BaseService cleanup called (no specific action needed in this version).")
    
    def __del__(self):
        """
        析構方法，確保資源被釋放
        """
        self.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        # 保持 False 以便異常能傳播
        return False
