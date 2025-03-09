import pytest
from src.model.database_manager import DatabaseManager
from src.model.models import Base
import os
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

def test_database_manager_initialization():
    # 測試預設記憶體資料庫
    db_manager = DatabaseManager("sqlite:///:memory:")
    assert db_manager.engine is not None
    assert db_manager.Session is not None

def test_database_manager_custom_path(tmp_path):
    # 測試自定義資料庫路徑
    db_path = str(tmp_path / "test.db")
    db_manager = DatabaseManager(db_path)
    assert os.path.exists(db_path)

def test_database_manager_create_tables(tmp_path):
    # 測試創建表格
    db_path = str(tmp_path / "test.db")
    db_manager = DatabaseManager(db_path)
    db_manager.create_tables(Base)
    
    # 驗證表格是否成功創建
    with db_manager.session_scope() as session:
        tables = session.execute(text("SELECT name FROM sqlite_master WHERE type='table';")).fetchall()
        table_names = [table[0] for table in tables]
        assert "articles" in table_names
        assert "system_settings" in table_names

def test_database_manager_session_scope(tmp_path):
    # 測試 session_scope 事務管理
    db_path = str(tmp_path / "test.db")
    db_manager = DatabaseManager(db_path)
    
    # 測試正常事務
    with db_manager.session_scope() as session:
        assert session is not None
    
    # 測試異常回滾
    with pytest.raises(Exception):
        with db_manager.session_scope() as session:
            raise ValueError("模擬異常")

def test_database_manager_invalid_path():
    # 測試無效的資料庫路徑
    with pytest.raises(RuntimeError):
        DatabaseManager("/invalid/path/that/does/not/exist/test.db")

def test_database_manager_env_path_handling(monkeypatch, tmp_path):
    # 測試環境變數設置的資料庫路徑
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DATABASE_PATH", db_path)
    
    db_manager = DatabaseManager()
    assert os.path.exists(db_path)

def test_database_manager_connection_error(monkeypatch):
    # 直接模擬_verify_connection方法
    def mock_verify_connection(self):
        raise SQLAlchemyError("模擬連接錯誤")
    
    # 替換DatabaseManager._verify_connection方法
    monkeypatch.setattr('src.model.database_manager.DatabaseManager._verify_connection', 
                        mock_verify_connection)
    
    # 預期拋出RuntimeError
    with pytest.raises(RuntimeError):
        DatabaseManager("sqlite:///:memory:")


def test_database_manager_invalid_connection_handling():
    # 測試無效的資料庫路徑
    with pytest.raises(RuntimeError):
        DatabaseManager("/invalid/path/that/does/not/exist/test.db")

def test_database_manager_session_scope_error_handling(tmp_path):
    # 測試 session_scope 的異常處理
    db_path = str(tmp_path / "test.db")
    db_manager = DatabaseManager(db_path)
    
    with pytest.raises(Exception):
        with db_manager.session_scope() as session:
            raise ValueError("模擬異常")
