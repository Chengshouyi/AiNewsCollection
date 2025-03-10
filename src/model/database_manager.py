import os
import logging
from typing import Optional, Type
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.decl_api import DeclarativeBase

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """資料庫操作基礎異常類"""
    pass


class DatabaseConnectionError(DatabaseError):
    """資料庫連接異常"""
    pass


class DatabaseConfigError(DatabaseError):
    """資料庫設定異常"""
    pass


class DatabaseOperationError(DatabaseError):
    """資料庫操作異常"""
    pass


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
                logger.error(error_msg, exc_info=True)
                raise DatabaseConfigError(error_msg) from engine_error
            
            # 連接驗證
            self._verify_connection()
        
        except SQLAlchemyError as e:
            error_msg = f"數據庫連接驗證失敗: {e}"
            logger.error(error_msg, exc_info=True)
            raise DatabaseConnectionError(error_msg) from e
        except DatabaseError:
            # 直接傳遞已定義的資料庫異常
            raise
        except Exception as e:
            error_msg = f"數據庫初始化錯誤: {e}"
            logger.error(error_msg, exc_info=True)
            raise DatabaseConfigError(error_msg) from e
    
    def _get_db_url(self, db_path: Optional[str] = None) -> str:
        """
        獲取數據庫URL
        
        Args:
            db_path: 資料庫路徑 (可選)
            
        Returns:
            資料庫URL字串
            
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
            db_dir = os.path.dirname(file_path)
            
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
                
            return db_path
        except Exception as e:
            error_msg = f"數據庫路徑解析錯誤: {e}"
            logger.error(error_msg, exc_info=True)
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
                conn.execute(text("SELECT 1"))
        except SQLAlchemyError as e:
            error_msg = f"數據庫連接驗證失敗: {e}"
            logger.error(error_msg, exc_info=True)
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
            session.commit()
        except Exception as e:
            session.rollback()
            error_msg = f"數據庫操作失敗: {e}"
            logger.error(error_msg, exc_info=True)
            raise DatabaseOperationError(error_msg) from e
        finally:
            session.close()
    
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
            logger.error(error_msg, exc_info=True)
            raise DatabaseOperationError(error_msg) from e