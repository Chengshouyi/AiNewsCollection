"""
提供基礎服務類別，用於管理資料庫存取和儲存庫生命週期。
"""

import logging
from contextlib import contextmanager
from typing import Any, Dict, Generic, List, Optional, Tuple, Type, TypeVar, cast

from sqlalchemy.orm import Session

from src.config import get_db_manager
from src.database.base_repository import BaseRepository, SchemaType
from src.database.database_manager import DatabaseManager
from src.error.errors import DatabaseOperationError, ValidationError
from src.error.service_errors import ServiceInitializationError
from src.models.base_model import Base
from src.utils.log_utils import LoggerSetup

logger = LoggerSetup.setup_logger(__name__)

T = TypeVar("T", bound=Base)


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
                raise ServiceInitializationError(
                    "DatabaseManager could not be initialized."
                )
            self.repositories: Dict[str, BaseRepository] = {}
            self._repositories_mapping = self._get_repository_mapping()
        except Exception as e:
            logger.error("BaseService initialization failed: %s", e, exc_info=True)
            raise ServiceInitializationError(
                f"Failed to initialize BaseService: {e}"
            ) from e

    def _get_repository_mapping(
        self,
    ) -> Dict[str, Tuple[Type[BaseRepository], Type[T]]]:
        """
        獲取儲存庫映射表，需要被子類重寫

        Returns:
            儲存庫名稱到 (儲存庫類, 模型類) 的映射字典
        """
        raise NotImplementedError("子類必須實現此方法提供儲存庫映射")

    def _get_repository(
        self, repository_name: str, session: Session
    ) -> BaseRepository[T]:
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
            repository_mapping = self._get_repository_mapping()

            if repository_name not in repository_mapping:
                error_msg = f"未知的儲存庫名稱: {repository_name}"
                logger.error(error_msg)
                raise DatabaseOperationError(error_msg)

            repository_class, model_class = repository_mapping[repository_name]
            repository = repository_class(session, model_class)
            return repository
        except Exception as e:
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
            DatabaseOperationError: 底層資料庫操作失敗
            Exception: 任何在事務中發生的其他異常 (會被重新引發)
        """
        try:
            # self.db_manager.session_scope() 已經處理了 SQLAlchemyError -> DatabaseOperationError 的轉換
            # 以及回滾和 Session 關閉
            with self.db_manager.session_scope() as session:
                yield session
        except DatabaseOperationError as db_err:
            # 捕獲來自 session_scope 的資料庫操作錯誤
            logger.error(
                "Transaction failed within BaseService due to DatabaseOperationError: %s",
                db_err,
                exc_info=True,
            )
            # 直接重新引發，因為它已經是我們期望的錯誤類型
            raise
        except Exception as e:
            # 捕獲任何其他類型的異常 (例如，應用程式邏輯錯誤，或測試中故意引發的錯誤)
            logger.error(
                "未預期的錯誤，事務因非資料庫錯誤而中止: %s", str(e), exc_info=True
            )
            # 直接重新引發原始異常，而不是包裝它
            # 這樣上層調用者 (包括測試) 可以捕獲到原始的錯誤類型
            raise

    def validate_data(
        self, repository_name: str, entity_data: Dict[str, Any], schema_type: SchemaType
    ) -> Dict[str, Any]:
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

            repository_class, _ = repository_mapping[repository_name]

            # 調用 Repository 類別上的 validate_data 方法
            validated_data = repository_class.validate_data(entity_data, schema_type)
            return validated_data

        except (DatabaseOperationError, ValidationError) as e:
            raise e
        except Exception as e:
            error_msg = f"在 Service 層執行 {repository_name} 的 validate_data 時發生錯誤: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ValidationError(error_msg) from e

    def cleanup(self):
        """清理服務資源"""
        # 實際的清理由 DatabaseManager 處理
        if hasattr(self.db_manager, "close_session"):
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
