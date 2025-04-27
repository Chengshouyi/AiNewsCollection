import os
from typing import Optional, Type
from contextlib import contextmanager
from functools import wraps
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool
from sqlalchemy.orm import sessionmaker, scoped_session, Session
from sqlalchemy.orm.decl_api import DeclarativeBase
from sqlalchemy.exc import OperationalError
from src.error.errors import (
    DatabaseConnectionError,
    DatabaseConfigError,
    DatabaseOperationError,
)


# 設定 logger
from src.utils.log_utils import LoggerSetup  # 使用統一的 logger

logger = LoggerSetup.setup_logger(__name__)  # 使用統一的 logger


class DatabaseManager:
    """數據庫連接和會話管理"""

    def __init__(self):
        """
        初始化數據庫管理器

        Raises:
            DatabaseConfigError: 資料庫配置錯誤
            DatabaseConnectionError: 資料庫連接錯誤
        """
        try:
            # 優先從環境變數讀取 DATABASE_URL
            self.database_url = os.environ.get("DATABASE_URL")

            if not self.database_url:
                raise DatabaseConfigError(
                    "DATABASE_URL environment variable is not set."
                )

            logger.info(f"DatabaseManager initialized with URL: {self.database_url}")
            # 使用連接池，例如 QueuePool
            self.engine = create_engine(
                self.database_url,
                poolclass=QueuePool,
                pool_size=10,  # 可根據需要調整
                max_overflow=20,  # 可根據需要調整
                pool_recycle=3600,  # 可選：回收閒置連接 (秒)
                pool_pre_ping=True,  # 可選：使用前檢查連接
            )
            self._verify_connection()
            self._session_factory = sessionmaker(bind=self.engine)
            # 使用 scoped_session 來管理 session 的線程安全
            self._scoped_session = scoped_session(self._session_factory)
            logger.info("DatabaseManager initialized successfully.")

        except OperationalError as e:
            error_msg = f"數據庫連接驗證失敗: {e}"
            logger.error(error_msg)
            raise DatabaseConnectionError(error_msg) from e

        except SQLAlchemyError as e:
            error_msg = f"Database engine creation or connection failed: {e}"
            logger.error(error_msg, exc_info=True)
            raise DatabaseConfigError(error_msg) from e

        except Exception as e:
            error_msg = f"數據庫初始化錯誤: {e}"
            logger.error(error_msg)
            raise DatabaseConfigError(error_msg) from e

    def _verify_connection(self) -> None:
        """
        驗證數據庫連接

        Raises:
            DatabaseConnectionError: 連接驗證失敗
        """
        try:
            # 嘗試建立連接並執行簡單查詢
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1")).fetchone()

                # 檢查查詢結果
                if result is None or result[0] != 1:
                    raise DatabaseConnectionError(
                        "資料庫連接測試失敗：無法獲取預期結果"
                    )

        except OperationalError as e:
            error_msg = f"數據庫連接驗證失敗 (操作錯誤): {e}"
            logger.error(error_msg)
            raise DatabaseConnectionError(error_msg) from e
        except SQLAlchemyError as e:
            error_msg = f"數據庫連接驗證失敗 (SQL錯誤): {e}"
            logger.error(error_msg)
            raise DatabaseConnectionError(error_msg) from e
        except Exception as e:
            error_msg = f"數據庫連接驗證失敗 (未知錯誤): {e}"
            logger.error(error_msg)
            raise DatabaseConnectionError(error_msg) from e

    def get_session(self):
        return self._scoped_session()

    def close_session(self):
        if hasattr(self, "_scoped_session"):  # 檢查是否存在
            self._scoped_session.remove()

    @contextmanager
    def session_scope(self):
        """
        提供事務範圍的會話上下文管理器。
        在異常發生時回滾並關閉會話。

        Yields:
            SQLAlchemy 會話物件

        Raises:
            DatabaseOperationError: 數據庫操作失敗
        """
        session: Session = self.get_session()
        logger.debug(f"Session scope started. Session: {session}")
        try:
            yield session
            # 只有活躍的 session 才需要 commit
            if session.is_active:
                session.commit()
                logger.debug(f"Session scope committed. Session: {session}")
            else:
                logger.warning(
                    f"Session scope ended but session was not active. Session: {session}"
                )

        except Exception as e:
            logger.error(
                f"Exception in session scope: {e}. Rolling back. Session: {session}"
            )
            try:
                # 只有活躍的 session 才需要 rollback
                if session.is_active:
                    session.rollback()
                    logger.debug(f"Session rollback successful. Session: {session}")
                else:
                    logger.warning(
                        f"Attempted rollback on inactive session. Session: {session}"
                    )

            except Exception as rb_exc:
                # 如果 rollback 也失敗，記錄額外錯誤
                logger.error(
                    f"Rollback failed: {rb_exc}. Original error: {e}. Session: {session}"
                )
                # 即使 rollback 失敗，仍嘗試關閉 session

            # 將原始錯誤包裝後重新拋出
            if isinstance(e, SQLAlchemyError):
                wrapped_error = DatabaseOperationError(f"數據庫操作錯誤: {e}")
            else:
                wrapped_error = e
            logger.error(f"Raising wrapped error: {wrapped_error}")
            raise wrapped_error

        finally:
            # 無論成功或失敗，最終都要關閉 session
            try:
                logger.debug(f"Closing session in finally block. Session: {session}")
                session.close()
                logger.debug(f"Session closed successfully. Session: {session}")
            except Exception as close_exc:
                # 如果關閉 session 出錯，記錄下來但不影響原始異常的拋出
                logger.error(
                    f"Failed to close session: {close_exc}. Session: {session}"
                )

    def create_tables(self, base: Type[DeclarativeBase]) -> None:
        """
        創建所有表格

        Args:
            base: SQLAlchemy 模型基礎類

        Raises:
            DatabaseOperationError: 創建表格失敗
        """
        try:
            base.metadata.create_all(self.engine)
            logger.info("所有表格已創建成功")
        except SQLAlchemyError as e:
            error_msg = f"創建表格失敗: {e}"
            logger.error(error_msg, exc_info=True)
            raise DatabaseOperationError(error_msg) from e

    # def create_engine(self):
    #     """重新創建並返回資料庫引擎"""
    #     try:
    #         self.engine = create_engine(self.db_url)
    #         self.Session = sessionmaker(bind=self.engine)  # 重新綁定 Session
    #         self._verify_connection()  # 驗證連接
    #         return self.engine
    #     except Exception as e:
    #         logger.error(f"重建引擎失敗: {str(e)}")
    #         raise DatabaseConfigError(str(e))

    def check_database_health(self):
        """檢查資料庫健康狀態"""
        try:
            self._verify_connection()
            return True
        except Exception as e:
            logger.error(f"資料庫健康檢查失敗: {str(e)}")
            return False

    def cleanup(self):
        """清理資源，例如關閉 session 和 dispose 引擎"""
        logger.info("Cleaning up DatabaseManager resources...")
        if hasattr(self, "_scoped_session"):  # 檢查屬性是否存在
            self._scoped_session.remove()
            logger.info("Scoped session removed.")
        if hasattr(self, "engine"):  # 檢查屬性是否存在
            self.engine.dispose()
            logger.info("Database engine disposed.")


def check_session(func):
    """
    檢查資料庫會話狀態的裝飾器

    Args:
        func: 被裝飾的函數

    Returns:
        裝飾後的函數

    Raises:
        DatabaseConnectionError: 資料庫連接已關閉或發生錯誤
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            # 檢查 session 對象是否存在
            if not hasattr(self, "session"):
                raise DatabaseConnectionError("沒有有效的資料庫會話")

            # 檢查 session 是否有效
            if not self.session or not self.session.bind:
                raise DatabaseConnectionError("資料庫連接已關閉")

            return func(self, *args, **kwargs)
        except OperationalError as e:
            error_msg = f"資料庫連接錯誤: {e}"
            logger.error(error_msg)
            raise DatabaseConnectionError(error_msg) from e
        except AttributeError as e:
            error_msg = f"資料庫會話屬性錯誤: {e}"
            logger.error(error_msg)
            raise DatabaseConnectionError(error_msg) from e

    return wrapper
