import pytest
from sqlalchemy.exc import OperationalError
from src.database.database_manager import DatabaseManager
from src.error.errors import DatabaseConnectionError, DatabaseConfigError, DatabaseOperationError
import os

class TestDatabaseManager:
    def test_init_with_invalid_path(self):
        """測試無效的資料庫路徑"""
        with pytest.raises(DatabaseConfigError) as excinfo:
            DatabaseManager("/invalid/path/with/no/permissions")
        assert "資料庫目錄沒有寫入權限" in str(excinfo.value)

    def test_init_with_memory_db(self):
        """測試記憶體資料庫初始化"""
        db_manager = DatabaseManager("sqlite:///:memory:")
        assert db_manager.db_url == "sqlite:///:memory:"

    def test_verify_connection_failure(self, mocker):
        """測試連接驗證失敗"""
        # 直接 mock _verify_connection 方法
        mocker.patch.object(
            DatabaseManager, 
            '_verify_connection', 
            side_effect=OperationalError("mock error", None, Exception("Original error"))
        )
        
        with pytest.raises(DatabaseConnectionError) as excinfo:
            DatabaseManager("sqlite:///:memory:")
        assert "數據庫連接驗證失敗" in str(excinfo.value)

    def test_session_scope(self):
        """測試會話範圍管理器"""
        db_manager = DatabaseManager("sqlite:///:memory:")
        
        with db_manager.session_scope() as session:
            assert session.bind is not None

        # 檢查會話綁定是否為 None 來確認會話已關閉
        assert session.bind is None

    def test_session_scope_with_error(self):
        """測試會話範圍管理器的錯誤處理"""
        db_manager = DatabaseManager("sqlite:///:memory:")
        
        with pytest.raises(DatabaseOperationError):
            with db_manager.session_scope() as session:
                raise Exception("測試錯誤")

        # 檢查會話綁定是否為 None 來確認會話已關閉
        assert session.bind is None

    def test_create_tables(self, mocker):
        """測試建立資料表"""
        mock_base = mocker.Mock()
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.create_tables(mock_base)
        
        mock_base.metadata.create_all.assert_called_once_with(db_manager.engine) 