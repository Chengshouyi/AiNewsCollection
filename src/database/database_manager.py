import os
import logging
from typing import Optional, Type
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.decl_api import DeclarativeBase
from sqlalchemy.exc import OperationalError
from src.error.errors import DatabaseError, DatabaseConnectionError, DatabaseConfigError, DatabaseOperationError
from functools import wraps

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



class DatabaseManager:
    """數據庫連接和會話管理"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化數據庫管理器
        
        Args:
            db_path: 數據庫路徑 (可選，預設使用環境變數)
        
        Raises:
            DatabaseConfigError: 資料庫配置錯誤
            DatabaseConnectionError: 資料庫連接錯誤
        """
        try:
            self.db_url = self._get_db_url(db_path)
            
            # 路徑和目錄檢查
            if not self.db_url.startswith('sqlite:///:memory:'):
                db_file_path = self.db_url.replace('sqlite:///', '')
                db_dir = os.path.dirname(db_file_path)
                
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)
                
                # 檢查目錄寫入權限
                if db_dir and not os.access(db_dir, os.W_OK):
                    raise DatabaseConfigError(f"資料庫目錄沒有寫入權限: {db_dir}")
            
            # 創建引擎時增加更多錯誤處理
            try:
                self.engine = create_engine(self.db_url)
                self.Session = sessionmaker(bind=self.engine)
            except Exception as engine_error:
                error_msg = f"創建數據庫引擎失敗: {engine_error}"
                logger.error(error_msg)
                raise DatabaseConfigError(error_msg) from engine_error
            
            # 連接驗證
            self._verify_connection()
        
        except OperationalError as e:
            error_msg = f"數據庫連接驗證失敗: {e}"
            logger.error(error_msg)
            raise DatabaseConnectionError(error_msg) from e
        except DatabaseError:
            # 直接傳遞已定義的資料庫異常
            raise
        except Exception as e:
            error_msg = f"數據庫初始化錯誤: {e}"
            logger.error(error_msg)
            raise DatabaseConfigError(error_msg) from e
    
    def _get_db_url(self, db_path: Optional[str] = None) -> str:
        """
        獲取數據庫URL
        
        Args:
            db_path: 資料庫路徑 (可選)
            
        Returns:
            資料庫URL字串，會將所有非記憶體資料庫的路徑轉換為絕對路徑
            
        Raises:
            DatabaseConfigError: 資料庫路徑無效
        """
        try:
            if db_path is None:
                db_path = os.getenv('DATABASE_PATH', '/workspace/data/news.db')
                
            if db_path.startswith('sqlite:///:memory:'):
                return db_path
            
            if not db_path.startswith('sqlite:///'):
                db_path = f"sqlite:///{db_path}"
            
            file_path = db_path.replace('sqlite:///', '')
            
            # 處理相對路徑和絕對路徑
            if not os.path.isabs(file_path):
                # 如果是相對路徑，轉換為絕對路徑
                file_path = os.path.abspath(file_path)
                db_path = f"sqlite:///{file_path}"
            
            db_dir = os.path.dirname(file_path)
            
            if db_dir:
                # 檢查目錄是否存在，若不存在則創建
                if not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)
                
                # 檢查目錄寫入權限
                if not os.access(db_dir, os.W_OK):
                    raise DatabaseConfigError(f"資料庫目錄沒有寫入權限: {db_dir}")
                
                # 如果文件存在，檢查文件寫入權限
                if os.path.exists(file_path) and not os.access(file_path, os.W_OK):
                    raise DatabaseConfigError(f"資料庫文件沒有寫入權限: {file_path}")
            
            return db_path
        except OSError as e:
            error_msg = f"資料庫路徑錯誤: {e}"
            logger.error(error_msg)
            raise DatabaseConfigError(error_msg) from e
        except Exception as e:
            error_msg = f"處理資料庫URL時發生錯誤: {e}"
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
                    raise DatabaseConnectionError("資料庫連接測試失敗：無法獲取預期結果")
                
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
    
    @contextmanager
    def session_scope(self):
        """
        提供事務範圍的會話上下文管理器
        
        Yields:
            SQLAlchemy 會話物件
            
        Raises:
            DatabaseOperationError: 數據庫操作失敗
        """
        session = self.Session()
        try:
            yield session
            # 如果session已經不活躍，不需要進行commit
            if session.is_active:
                session.commit()
        except Exception as e:
            # 如果session已經不活躍，不需要進行rollback
            if session.is_active:
                session.rollback()
            error_msg = f"數據庫操作失敗: {e}"
            logger.error(error_msg)
            
            # 根據不同異常類型提供更詳細的錯誤資訊
            if isinstance(e, SQLAlchemyError):
                raise DatabaseOperationError(f"數據庫操作錯誤: {e}") from e
            else:
                raise DatabaseOperationError(f"非數據庫相關的操作錯誤: {e}") from e
        finally:
            try:
                # 確保在任何情況下都會關閉session
                if session:
                    session.close()
                    # 在某些情況下，expire_all可能會拋出異常
                    try:
                        session.expire_all()
                    except Exception as expire_error:
                        logger.warning(f"Session expire_all 錯誤 (忽略): {expire_error}")
                    
                    # 在某些情況下，設置bind=None可能會拋出異常
                    try:
                        session.bind = None
                    except Exception as bind_error:
                        logger.warning(f"Session unbind 錯誤 (忽略): {bind_error}")
            except Exception as cleanup_error:
                # 記錄清理錯誤但不拋出，避免掩蓋原始異常
                logger.warning(f"Session 清理錯誤 (忽略): {cleanup_error}")
    
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
        except SQLAlchemyError as e:
            error_msg = f"創建表格失敗: {e}"
            logger.error(error_msg)
            raise DatabaseOperationError(error_msg) from e

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
            if not hasattr(self, 'session'):
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