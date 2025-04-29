"""
提供資料庫連接和會話管理的類別。

這個模組包含 DatabaseManager 類別，負責處理資料庫的初始化、
連接池管理、會話生命週期控制以及錯誤處理。
"""

import os
from contextlib import contextmanager
from functools import wraps
from typing import Optional, Type

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, scoped_session, sessionmaker
from sqlalchemy.pool import QueuePool

from src.error.errors import (
    DatabaseConfigError,
    DatabaseConnectionError,
    DatabaseOperationError,
    IntegrityValidationError,
    InvalidOperationError,
    ValidationError,
)
from src.utils.log_utils import LoggerSetup

logger = LoggerSetup.setup_logger(__name__)


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
            self.database_url = os.environ.get("DATABASE_URL")
            if not self.database_url:
                raise DatabaseConfigError(
                    "DATABASE_URL environment variable is not set."
                )

            logger.info("DatabaseManager initializing with URL: %s", self.database_url)
            echo_str = os.environ.get("SQLALCHEMY_ECHO", "False")
            if echo_str == "True":
                echo = True
            else:
                echo = False
            logger.info("SQLALCHEMY_ECHO: %s", echo)
            self.engine = create_engine(
                self.database_url,
                poolclass=QueuePool,
                pool_size=10,
                max_overflow=20,
                pool_recycle=3600,
                pool_pre_ping=True,
                echo=echo,
            )
            self._verify_connection()
            self._session_factory = sessionmaker(bind=self.engine)
            self._scoped_session = scoped_session(self._session_factory)
            logger.info("DatabaseManager initialized successfully.")

        except OperationalError as e:
            error_msg = f"數據庫連接驗證失敗: {e}"
            logger.error("數據庫連接驗證失敗: %s", e)
            raise DatabaseConnectionError(error_msg) from e

        except SQLAlchemyError as e:
            error_msg = f"Database engine creation or connection failed: {e}"
            logger.error(
                "Database engine creation or connection failed: %s", e, exc_info=True
            )
            raise DatabaseConfigError(error_msg) from e

        except Exception as e:
            error_msg = f"數據庫初始化錯誤: {e}"
            logger.error("數據庫初始化錯誤: %s", e)
            raise DatabaseConfigError(error_msg) from e

    def _verify_connection(self) -> None:
        """
        驗證數據庫連接

        Raises:
            DatabaseConnectionError: 連接驗證失敗
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1")).fetchone()
                if result is None or result[0] != 1:
                    raise DatabaseConnectionError(
                        "資料庫連接測試失敗：無法獲取預期結果"
                    )

        except OperationalError as e:
            error_msg = f"數據庫連接驗證失敗 (操作錯誤): {e}"
            logger.error("數據庫連接驗證失敗 (操作錯誤): %s", e)
            raise DatabaseConnectionError(error_msg) from e
        except SQLAlchemyError as e:
            error_msg = f"數據庫連接驗證失敗 (SQL錯誤): {e}"
            logger.error("數據庫連接驗證失敗 (SQL錯誤): %s", e)
            raise DatabaseConnectionError(error_msg) from e
        except Exception as e:
            error_msg = f"數據庫連接驗證失敗 (未知錯誤): {e}"
            logger.error("數據庫連接驗證失敗 (未知錯誤): %s", e)
            raise DatabaseConnectionError(error_msg) from e

    def get_session(self) -> Session:
        """獲取一個線程安全的會話"""
        return self._scoped_session()

    def close_session(self):
        """關閉當前線程的會話"""
        if hasattr(self, "_scoped_session"):
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
        logger.debug("Session scope started. Session: %s", session)
        try:
            yield session
            if session.is_active:
                session.commit()
                logger.debug("Session scope committed. Session: %s", session)
            else:
                logger.warning(
                    "Session scope ended but session was not active. Session: %s",
                    session,
                )

        except Exception as e:
            logger.error(
                "Exception in session scope: %s. Rolling back. Session: %s", e, session
            )
            wrapped_error = e  # Preserve original error by default
            try:
                if session.is_active:
                    session.rollback()
                    logger.debug("Session rollback successful. Session: %s", session)
                else:
                    logger.warning(
                        "Attempted rollback on inactive session. Session: %s", session
                    )

            except Exception as rb_exc:
                logger.error(
                    "Rollback failed: %s. Original error: %s. Session: %s",
                    rb_exc,
                    e,
                    session,
                )

            # Wrap SQLAlchemy errors specifically
            if isinstance(e, SQLAlchemyError):
                wrapped_error = DatabaseOperationError(f"數據庫操作錯誤: {e}")
                logger.error(
                    "Raising wrapped DatabaseOperationError: %s", wrapped_error
                )
            else:
                logger.error("Raising original error: %s", wrapped_error)

            raise wrapped_error from e  # Chain the original exception

        finally:
            try:
                logger.debug("Closing session in finally block. Session: %s", session)
                self.close_session()  # Use the close_session method to ensure proper cleanup via scoped_session
                logger.debug(
                    "Session closed successfully via close_session. Session ID was: %s",
                    session,
                )
            except Exception as close_exc:
                logger.error(
                    "Failed to close session: %s. Session ID was: %s",
                    close_exc,
                    session,
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
            logger.error("創建表格失敗: %s", e, exc_info=True)
            raise DatabaseOperationError(error_msg) from e

    def check_database_health(self) -> bool:
        """檢查資料庫健康狀態"""
        try:
            self._verify_connection()
            logger.info("Database health check successful.")
            return True
        except DatabaseConnectionError as e:
            logger.error("資料庫健康檢查失敗: %s", e)
            return False
        except Exception as e:  # Catch other potential unexpected errors during check
            logger.error("資料庫健康檢查時發生意外錯誤: %s", e)
            return False

    def cleanup(self):
        """清理資源，例如關閉 session 和 dispose 引擎"""
        logger.info("Cleaning up DatabaseManager resources...")
        if hasattr(self, "_scoped_session"):
            self.close_session()  # Use the method to remove session
            logger.info("Scoped session removed.")
        if hasattr(self, "engine"):
            self.engine.dispose()
            logger.info("Database engine disposed.")

    def drop_tables(self, base: Type[DeclarativeBase]) -> None:
        """
        移除所有表格

        Args:
            base: SQLAlchemy 模型基礎類

        Raises:
            DatabaseOperationError: 移除表格失敗
        """
        try:
            base.metadata.drop_all(self.engine)
            logger.info("所有表格已成功移除")
        except SQLAlchemyError as e:
            error_msg = f"移除表格失敗: {e}"
            logger.error("移除表格失敗: %s", e, exc_info=True)
            raise DatabaseOperationError(error_msg) from e


def check_session(func):
    """
    檢查資料庫會話狀態的裝飾器 (注意: 此裝飾器假設 'self' 具有 'session' 屬性，
    但 DatabaseManager 本身不直接持有 'session'，而是透過 'get_session()' 提供。
    如果此裝飾器用於 DatabaseManager 之外的類別，請確保該類別有 'session'。)

    Args:
        func: 被裝飾的函數

    Returns:
        裝飾後的函數

    Raises:
        DatabaseConnectionError: 資料庫連接已關閉或發生錯誤
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        session_instance: Optional[Session] = None
        try:  # Try block for getting/checking session
            # This decorator assumes 'self' has a 'session' attribute.
            # DatabaseManager uses get_session() or session_scope().
            # Ensure the class using this decorator manages 'session' correctly.
            if hasattr(self, "session") and isinstance(
                getattr(self, "session", None), Session
            ):
                session_instance = self.session
            elif hasattr(self, "get_session") and callable(self.get_session):
                # Attempt to get session if applicable, but be cautious
                # as this might not be the intended use case for the decorator.
                # Consider if the decorator is applied correctly.
                logger.warning(
                    "check_session decorator used on class potentially without direct 'session' attribute. Attempting get_session()."
                )
                # We cannot reliably get and manage the session here without knowing
                # the context (e.g., if it should be within a session_scope).
                # This check might be better performed inside the decorated function itself.
                # For now, we'll just check if a session attribute exists.
                if not hasattr(self, "session"):
                    raise DatabaseConnectionError(
                        "Class using check_session lacks a 'session' attribute."
                    )
                session_instance = getattr(
                    self, "session", None
                )  # Re-check after warning
            else:
                raise DatabaseConnectionError(
                    "Class using check_session lacks a 'session' attribute or a 'get_session' method."
                )

            # Check if the session instance obtained is valid
            if (
                not session_instance
                or not session_instance.is_active
                or not session_instance.bind  # This check itself might raise AttributeError
            ):
                logger.error(
                    "Database connection is closed or session is invalid. Session: %s",
                    session_instance,
                )
                raise DatabaseConnectionError("資料庫連接已關閉或 Session 無效")

            logger.debug("Session check passed for function: %s", func.__name__)

        except OperationalError as e:  # Catch errors during session check/retrieval
            error_msg = f"資料庫連接錯誤: {e}"
            logger.error("資料庫連接錯誤: %s", e)
            raise DatabaseConnectionError(error_msg) from e
        except (
            AttributeError
        ) as e:  # Catch errors during session check/retrieval (e.g., session.bind)
            error_msg = f"資料庫會話屬性錯誤: {e}"
            logger.error("資料庫會話屬性錯誤: %s", e)
            raise DatabaseConnectionError(error_msg) from e
        except (
            DatabaseConnectionError
        ) as e:  # Re-raise specifically caught errors from check
            raise e
        except (
            Exception
        ) as e:  # Catch OTHER unexpected errors *during the check itself*
            error_msg = f"執行 {func.__name__} 的會話檢查時發生意外錯誤: {e}"
            logger.error("執行 %s 的會話檢查時發生意外錯誤: %s", func.__name__, e)
            # Wrap ONLY if the error occurred *during the check*, not from func()
            raise DatabaseConnectionError(error_msg) from e

        # If session check passed, call the original function *outside* the main check's try-except
        # Allow exceptions raised by func() to propagate naturally, especially those
        # that execute_query intends to preserve.
        return func(self, *args, **kwargs)

    return wrapper
