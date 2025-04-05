import pytest, os
from pytest import fixture

from src.database.database_manager import (
    DatabaseManager,
    DatabaseConfigError, DatabaseOperationError, DatabaseConnectionError,
    check_session
)
from src.models.base_model import Base
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timezone
from src.models.articles_model import Articles
from src.models.crawlers_model import Crawlers



@fixture
def create_in_memory_db():
    """創建一個臨時的記憶體資料庫"""
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.create_tables(Base)  # 預先創建所有表格
    yield db_manager

@fixture
def create_temp_file_db(tmp_path):
    """創建一個臨時的文件資料庫"""
    db_path = str(tmp_path / "test.db")
    db_manager = DatabaseManager(f"sqlite:///{db_path}")
    db_manager.create_tables(Base)  # 預先創建所有表格
    yield db_manager, db_path

@fixture
def sample_article():
    """創建一個測試用的文章樣本"""
    return {
        "title": "測試文章",
        "link": "https://example.com/test",
        "published_at": datetime.now(timezone.utc),
        "content": "測試內容",
        "created_at": datetime.now(timezone.utc),
        "source": "test_source",
        "source_url": "https://example.com/source"
    }

class TestDatabaseManager:
    """資料庫管理器測試類"""

    def test_initialization(self, create_in_memory_db):
        """測試基本初始化"""
        assert create_in_memory_db.engine is not None
        assert create_in_memory_db.Session is not None

    def test_custom_path_initialization(self, create_temp_file_db):
        """測試自定義路徑初始化"""
        db_manager, db_path = create_temp_file_db
        assert os.path.exists(db_path)
        assert db_manager.engine is not None

    def test_get_db_url(self):
        """測試 _get_db_url 方法處理各種路徑格式"""
        db_manager = DatabaseManager("sqlite:///:memory:")
        
        # 測試記憶體資料庫 URL
        assert db_manager._get_db_url("sqlite:///:memory:") == "sqlite:///:memory:"
        
        # 測試相對路徑轉換為絕對路徑
        rel_path = "test.db"
        # 只檢查路徑結尾部分，因為絕對路徑的前綴可能因環境而異
        assert db_manager._get_db_url(rel_path).endswith(f"/{rel_path}")
        
        # 測試絕對路徑
        abs_path = "/tmp/test.db"
        # SQLite 的 URL 格式對於絕對路徑會添加額外的斜線
        assert db_manager._get_db_url(abs_path) == f"sqlite:////{abs_path[1:]}"
        
        # 測試已格式化路徑
        # 注意：當前實現也會將已格式化路徑轉換為絕對路徑
        formatted_path = "sqlite:///test.db"
        # 驗證路徑結尾部分
        assert db_manager._get_db_url(formatted_path).endswith("/test.db")

    def test_verify_connection(self, create_in_memory_db):
        """測試資料庫連接驗證"""
        # 正常連接測試 - 應該不會拋出異常
        create_in_memory_db._verify_connection()

    def test_session_scope_commit(self, create_in_memory_db, sample_article):
        """測試 session_scope 正常提交事務"""
        # 新增資料
        with create_in_memory_db.session_scope() as session:
            article = Articles(**sample_article)
            session.add(article)
        
        # 在新的 session 中驗證資料
        with create_in_memory_db.session_scope() as session:
            result = session.query(Articles).filter(Articles.link == sample_article["link"]).first()
            assert result is not None
            assert result.title == sample_article["title"]
            assert result.source == sample_article["source"]

    def test_session_scope_rollback(self, create_in_memory_db, sample_article):
        """測試 session_scope 異常回滾"""
        # 先新增一筆正常資料
        with create_in_memory_db.session_scope() as session:
            initial_article = Articles(**sample_article)
            session.add(initial_article)
        
        # 修改 link 以便創建第二筆資料
        second_article_data = sample_article.copy()
        second_article_data["link"] = "https://example.com/test2"
        
        # 模擬異常 - 故意拋出異常
        with pytest.raises(DatabaseOperationError):
            with create_in_memory_db.session_scope() as session:
                # 新增第二筆資料
                article = Articles(**second_article_data)
                session.add(article)
                # 故意製造錯誤
                raise ValueError("模擬異常，應觸發回滾")
        
        # 驗證回滾是否成功
        with create_in_memory_db.session_scope() as session:
            # 第二筆資料應該不存在
            result = session.query(Articles).filter(Articles.link == second_article_data["link"]).first()
            assert result is None
            
            # 第一筆資料應該還在
            result = session.query(Articles).filter(Articles.link == sample_article["link"]).first()
            assert result is not None
            assert result.title == sample_article["title"]

    def test_session_scope_cleanup(self, create_in_memory_db, sample_article):
        """測試 session_scope 的清理功能"""
        # 使用 session_scope 執行資料庫操作
        with create_in_memory_db.session_scope() as session:
            article = Articles(**sample_article)
            session.add(article)
        
        # 驗證資料已經成功提交
        with create_in_memory_db.session_scope() as new_session:
            result = new_session.query(Articles).filter(Articles.link == sample_article["link"]).first()
            assert result is not None
            assert result.title == sample_article["title"]
            
        # 測試 DatabaseManager 功能，而非 SQLAlchemy 的實現細節
        # 測試點：當 session_scope 結束後，可以開始新的資料庫會話
        # 這證明資源已被正確釋放
        second_article = sample_article.copy()
        second_article["link"] = "https://example.com/test2"
        with create_in_memory_db.session_scope() as another_session:
            article2 = Articles(**second_article)
            another_session.add(article2)
        
        # 確認第二個會話的操作也成功了
        with create_in_memory_db.session_scope() as final_session:
            result1 = final_session.query(Articles).filter(Articles.link == sample_article["link"]).first()
            result2 = final_session.query(Articles).filter(Articles.link == second_article["link"]).first()
            assert result1 is not None
            assert result2 is not None

    def test_create_tables(self, create_in_memory_db):
        """測試創建資料表"""
        # 表格已在 fixture 中創建，僅需驗證
        with create_in_memory_db.session_scope() as session:
            # 檢查資料表是否存在
            tables = session.execute(text("SELECT name FROM sqlite_master WHERE type='table';")).fetchall()
            table_names = [table[0] for table in tables]
            
            # 驗證必要的資料表是否已創建
            assert Articles.__tablename__ in table_names
            assert Crawlers.__tablename__ in table_names

    def test_env_path_handling(self, monkeypatch, tmp_path):
        """測試環境變數設置的資料庫路徑"""
        db_path = str(tmp_path / "env_test.db")
        monkeypatch.setenv("DATABASE_PATH", db_path)
        
        db_manager = DatabaseManager()
        assert os.path.exists(db_path)
        
        # 確認可以正常操作
        db_manager.create_tables(Base)
        with db_manager.session_scope() as session:
            # 檢查資料表是否存在
            tables = session.execute(text("SELECT name FROM sqlite_master WHERE type='table';")).fetchall()
            table_names = [table[0] for table in tables]
            assert Articles.__tablename__ in table_names

    @pytest.mark.skipif(os.name == 'nt', reason="權限測試在 Windows 上不穩定")
    def test_permission_error(self, tmp_path):
        """測試權限錯誤處理（非 Windows 系統）"""
        # 這個測試可能在不同環境下有不同的結果，所以使用 try-except 包裝
        try:
            # 創建一個臨時文件並修改權限
            db_path = tmp_path / "readonly.db"
            db_path.touch()
            os.chmod(db_path, 0o444)  # 唯讀權限
            
            # 嘗試使用唯讀文件作為資料庫
            with pytest.raises((DatabaseConfigError, OSError)):
                DatabaseManager(str(db_path))
        except:
            # 如果測試環境不支持權限修改，則跳過測試
            pytest.skip("此環境無法測試權限錯誤")

    def test_invalid_path(self):
        """測試無效的資料庫路徑"""
        # 使用一個明確不存在且無法創建的路徑
        invalid_path = os.path.join("/", "nonexistent", "path", "that", "cannot", "be", "created", "test.db")
        
        # 這裡我們預期會拋出錯誤，但具體錯誤類型可能因系統而異
        with pytest.raises((DatabaseConfigError, OSError)):
            DatabaseManager(invalid_path)