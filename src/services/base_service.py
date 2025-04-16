import logging
from typing import Dict, Any, Optional, TypeVar, Generic, List
from contextlib import contextmanager

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
        self._repositories = {}
    
    def _get_repository_mapping(self) -> Dict[str, tuple]:
        """
        獲取儲存庫映射表，需要被子類重寫
        
        Returns:
            儲存庫名稱到 (儲存庫類, 模型類) 的映射字典
        """
        raise NotImplementedError("子類必須實現此方法提供儲存庫映射")
    
    def _get_repository(self, repository_name: str) -> BaseRepository[T]:
        """
        獲取指定的儲存庫實例
        
        Args:
            repository_name: 儲存庫名稱
        
        Returns:
            儲存庫實例
        
        Raises:
            DatabaseOperationError: 獲取儲存庫失敗
        """
        try:
            # 如果已經有此儲存庫實例，直接返回
            if repository_name in self._repositories:
                return self._repositories[repository_name]
            
            # 獲取儲存庫映射
            repository_mapping = self._get_repository_mapping()
            
            if repository_name not in repository_mapping:
                error_msg = f"未知的儲存庫名稱: {repository_name}"
                logger.error(error_msg)
                raise DatabaseOperationError(error_msg)
            
            # 獲取儲存庫類和模型類
            repository_class, model_class = repository_mapping[repository_name]
            
            # 創建會話
            session = self.db_manager.Session()
            
            # 創建儲存庫實例
            repository = repository_class(session, model_class)
            
            # 保存儲存庫實例以便重用
            self._repositories[repository_name] = repository
            
            return repository
        except Exception as e:
            error_msg = f"獲取儲存庫失敗: {str(e)}"
            logger.error(error_msg)
            raise DatabaseOperationError(error_msg) from e
    
    def validate_data(self, repository_name: str, entity_data: Dict[str, Any], 
                     schema_type: SchemaType = SchemaType.CREATE) -> Dict[str, Any]:
        """
        公開方法：透過指定的儲存庫驗證資料
        
        Args:
            repository_name: 儲存庫名稱
            entity_data: 實體資料
            schema_type: Schema類型 (預設為CREATE)
            
        Returns:
            Dict[str, Any]: 驗證後的資料
                success: 是否成功
                message: 消息
                data: 驗證後的資料
            
        Raises:
            ValidationError: 資料驗證失敗
            DatabaseOperationError: 其他資料庫相關錯誤
        """
        try:
            repo = self._get_repository(repository_name)
            return repo.validate_data(entity_data, schema_type)
        except ValidationError:
            # 直接重新抛出 ValidationError
            raise
        except Exception as e:
            error_msg = f"資料驗證失敗: {str(e)}"
            logger.error(error_msg)
            raise DatabaseOperationError(error_msg) from e
    
    @contextmanager
    def _transaction(self):
        """
        事務上下文管理器，用於包裹需要在單一事務中執行的多個操作
        
        Yields:
            無返回值，僅作為上下文管理器使用
        
        Raises:
            Exception: 任何在事務中發生的異常
        """
        # 確保所有儲存庫使用同一個session
        session = None
        if self._repositories:
            # 獲取第一個儲存庫的session
            session = next(iter(self._repositories.values())).session
        
        if not session:
            # 如果沒有儲存庫或儲存庫沒有session，創建一個新的
            session = self.db_manager.Session()
        
        try:
            yield
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
    
    def cleanup(self):
        """
        清理服務使用的資源，關閉所有儲存庫的會話
        """
        for repository in self._repositories.values():
            if repository and repository.session:
                try:
                    repository.session.close()
                except Exception as e:
                    logger.warning(f"關閉session時出錯 (忽略): {e}")
        
        # 清空儲存庫字典
        self._repositories.clear()
    
    def __del__(self):
        """
        析構方法，確保資源被釋放
        """
        self.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False  # 允許異常傳播
