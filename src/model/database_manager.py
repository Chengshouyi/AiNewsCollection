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


class DatabaseManager:
    """數據庫連接和會話管理"""
    
    def __init__(self, db_path: Optional[str] = None):
        try:
            self.db_url = self._get_db_url(db_path)
            
            # 路徑和目錄檢查
            if not self.db_url.startswith('sqlite:///:memory:'):
                db_file_path = self.db_url.replace('sqlite:///', '')
                db_dir = os.path.dirname(db_file_path)
                
                if db_dir and not os.path.exists(db_dir):
                    raise RuntimeError(f"資料庫目錄不存在: {db_dir}")
            
            # 創建引擎時增加更多錯誤處理
            try:
                self.engine = create_engine(self.db_url)
                self.Session = sessionmaker(bind=self.engine)
            except Exception as engine_error:
                error_msg = f"創建數據庫引擎失敗: {engine_error}"
                logger.error(error_msg, exc_info=True)
                raise RuntimeError(error_msg) from engine_error
            
            # 連接驗證
            self._verify_connection()
        
        except SQLAlchemyError as e:
            error_msg = f"數據庫連接驗證失敗: {e}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = f"數據庫初始化錯誤: {e}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e
    
    def _get_db_url(self, db_path: Optional[str] = None) -> str:
        """獲取數據庫URL"""
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
    
    def _verify_connection(self) -> None:
        """驗證數據庫連接"""
        try:
            # 嘗試建立連接並執行簡單查詢
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except SQLAlchemyError as e:
            error_msg = f"數據庫連接驗證失敗: {e}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e
    
    @contextmanager
    def session_scope(self):
        """提供事務範圍的會話上下文管理器"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            error_msg = f"數據庫操作失敗: {e}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e
        finally:
            session.close()
    
    def create_tables(self, base: Type[DeclarativeBase]) -> None:
        """創建所有表格"""
        try:
            base.metadata.create_all(self.engine)
        except SQLAlchemyError as e:
            error_msg = f"創建表格失敗: {e}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e
