import pytest
from datetime import datetime, timedelta, timezone
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.models.crawlers_model import Crawlers
from src.models.base_model import Base
from src.services.crawlers_service import CrawlersService
from src.error.errors import ValidationError, DatabaseOperationError
from src.database.database_manager import DatabaseManager
from src.database.crawlers_repository import CrawlersRepository
from pydantic import BaseModel, Field, validator

# 設定測試資料庫
@pytest.fixture(scope="session")
def engine():
    """建立全局測試引擎，使用記憶體 SQLite 資料庫"""
    return create_engine('sqlite:///:memory:')

@pytest.fixture(scope="session")
def tables(engine):
    """建立測試資料表，使用 session scope 減少重複建立和銷毀資料庫結構"""
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="session")
def session_factory(engine):
    """建立會話工廠，使用 session scope 共享會話工廠"""
    return sessionmaker(bind=engine)

@pytest.fixture(scope="function")
def session(session_factory, tables):
    """建立測試會話，每個測試函數獲取全新的獨立會話"""
    session = session_factory()
    
    try:
        yield session
    finally:
        session.close()

@pytest.fixture(scope="function")
def db_manager(engine, session_factory, monkeypatch):
    """創建真實的 DatabaseManager 實例用於測試，每個測試獲取獨立的數據庫管理器"""
    # 設定環境變數指向記憶體資料庫
    monkeypatch.setenv('DATABASE_PATH', 'sqlite:///:memory:')
    
    # 創建 DatabaseManager 實例
    manager = DatabaseManager()
    
    # 替換引擎和會話工廠，使用測試用的記憶體資料庫
    manager.engine = engine
    manager.Session = session_factory
    
    # 確保表格已經創建完成
    Base.metadata.create_all(engine)
    
    return manager

@pytest.fixture(scope="function")
def crawlers_service(db_manager):
    """創建爬蟲服務實例，每個測試獲取獨立實例"""
    return CrawlersService(db_manager)

@pytest.fixture(scope="function")
def sample_crawlers(db_manager, session):
    """創建樣本爬蟲資料並保存 ID 和屬性值"""
    # 清除可能存在的資料，確保測試隔離
    session.query(Crawlers).delete()
    session.commit()
    
    crawlers_data = [
        {
            "crawler_name": "數位時代爬蟲",
            "base_url": "https://www.bnext.com.tw/articles",
            "is_active": True,
            "crawler_type": "bnext",
            "config_file_name": "bnext_crawler_config.json"
        },
        {
            "crawler_name": "科技報導爬蟲",
            "base_url": "https://technews.tw",
            "is_active": False,
            "crawler_type": "bnext",
            "config_file_name": "bnext_crawler_config.json"
        },
        {
            "crawler_name": "商業週刊爬蟲",
            "base_url": "https://www.businessweekly.com.tw",
            "is_active": True,
            "crawler_type": "bnext",
            "config_file_name": "bnext_crawler_config.json"
        }
    ]
    
    # 創建 Crawlers 物件並插入資料庫
    crawler_objects = []
    for crawler_data in crawlers_data:
        crawler = Crawlers(
            crawler_name=crawler_data["crawler_name"],
            base_url=crawler_data["base_url"],
            is_active=crawler_data["is_active"],
            crawler_type=crawler_data["crawler_type"],
            config_file_name=crawler_data["config_file_name"]
        )
        crawler_objects.append(crawler)
    
    # 使用 DatabaseManager 的會話插入爬蟲設定
    with db_manager.session_scope() as session:
        session.add_all(crawler_objects)
        session.commit()
        
        # 明確刷新物件，確保 ID 已正確賦值
        for crawler in crawler_objects:
            session.refresh(crawler)
            
        # 獲取 ID
        for i, crawler in enumerate(crawler_objects):
            crawlers_data[i]["id"] = crawler.id
    
    # 返回資料字典而非物件，避免分離實例問題
    return crawlers_data

@pytest.fixture(scope="function")
def valid_crawler_data():
    """提供有效的爬蟲資料用於測試"""
    return {
        "crawler_name": "測試爬蟲",
        "base_url": "https://example.com/test",
        "is_active": True,
        "crawler_type": "bnext",
        "config_file_name": "bnext_crawler_config.json"
    }

class TestCrawlersService:
    """爬蟲服務的測試類"""
    
    def test_init(self, db_manager):
        """測試服務初始化"""
        service = CrawlersService(db_manager)
        assert service.db_manager == db_manager
    
    def test_get_repository(self, crawlers_service, db_manager):
        """測試獲取儲存庫"""
        repo, session = crawlers_service._get_repository()
        assert isinstance(repo, CrawlersRepository)
        assert session is not None
        # 測試完後關閉會話
        session.close()
    
    def test_create_crawler(self, crawlers_service, valid_crawler_data, session):
        """測試創建爬蟲設定"""
        # 清除可能存在的同名爬蟲設定
        session.query(Crawlers).filter_by(crawler_name=valid_crawler_data["crawler_name"]).delete()
        session.commit()
        
        result = crawlers_service.create_crawler(valid_crawler_data)
        assert result is not None
        
        # 獲取新創建的爬蟲 ID
        crawler_id = result.id
        
        # 清除會話緩存，確保從數據庫獲取最新數據
        session.expire_all()
        
        # 透過 ID 重新查詢爬蟲設定，避免使用分離的實例
        retrieved_crawler = crawlers_service.get_crawler_by_id(crawler_id)
        
        assert retrieved_crawler is not None
        assert retrieved_crawler.crawler_name == valid_crawler_data["crawler_name"]
        assert retrieved_crawler.base_url == valid_crawler_data["base_url"]
        assert retrieved_crawler.is_active == valid_crawler_data["is_active"]
    
    def test_get_all_crawlers(self, crawlers_service, sample_crawlers, session):
        """測試獲取所有爬蟲設定"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        # 獲取所有爬蟲設定
        crawlers = crawlers_service.get_all_crawlers()
        assert len(crawlers) == 3
        
        # 測試分頁
        crawlers = crawlers_service.get_all_crawlers(limit=2)
        assert len(crawlers) == 2
        
        crawlers = crawlers_service.get_all_crawlers(offset=1, limit=1)
        assert len(crawlers) == 1
        
        # 測試排序 - 改為檢查結果是否為排序後的狀態
        crawlers = crawlers_service.get_all_crawlers(sort_by="crawler_name", sort_desc=True)
        # 取得爬蟲名稱並檢查順序
        names = [crawler.crawler_name for crawler in crawlers]
        # 驗證是否按名稱降序排序
        assert sorted(names, reverse=True) == names
    
    def test_get_crawler_by_id(self, crawlers_service, sample_crawlers, session):
        """測試根據ID獲取爬蟲設定"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        crawler_id = sample_crawlers[0]["id"]  # 使用字典中的 id
        crawler = crawlers_service.get_crawler_by_id(crawler_id)
        
        assert crawler is not None
        assert crawler.id == crawler_id
        
        # 測試無效ID
        crawler = crawlers_service.get_crawler_by_id(999999)
        assert crawler is None
    
    def test_get_active_crawlers(self, crawlers_service, sample_crawlers, session):
        """測試獲取活動中的爬蟲設定"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        active_crawlers = crawlers_service.get_active_crawlers()
        
        # 驗證所有返回的爬蟲設定都是活動中的
        assert len(active_crawlers) > 0
        assert all(crawler.is_active for crawler in active_crawlers)
        
        # 驗證數量是否正確 (應該有2個活動中的爬蟲)
        assert len(active_crawlers) == 2
    
    def test_get_crawlers_by_name(self, crawlers_service, sample_crawlers, session):
        """測試根據名稱模糊查詢爬蟲設定"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        # 查詢包含"爬蟲"的爬蟲設定
        crawlers = crawlers_service.get_crawlers_by_name("爬蟲")
        assert len(crawlers) == 3  # 所有爬蟲設定名稱都包含"爬蟲"
        
        # 查詢包含"數位"的爬蟲設定
        digital_crawlers = crawlers_service.get_crawlers_by_name("數位")
        assert len(digital_crawlers) == 1
        assert digital_crawlers[0].crawler_name == "數位時代爬蟲"
        
        # 測試不存在的名稱
        no_crawlers = crawlers_service.get_crawlers_by_name("不存在")
        assert len(no_crawlers) == 0
    
    
    def test_update_crawler(self, crawlers_service, sample_crawlers, session):
        """測試更新爬蟲設定"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        crawler_id = sample_crawlers[0]["id"]  # 使用字典中的 id
        
        # 準備更新資料
        update_data = {
            "crawler_name": "更新後的爬蟲名稱",
            "base_url": "https://example.com/updated",
            "is_active": False,
            "config_file_name": "bnext_crawler_config.json"
        }
        
        updated_crawler = crawlers_service.update_crawler(crawler_id, update_data)
        assert updated_crawler is not None
        
        # 清除會話緩存，確保從數據庫獲取最新數據
        session.expire_all()
        
        # 重新查詢更新後的爬蟲設定，避免使用分離的實例
        retrieved_crawler = crawlers_service.get_crawler_by_id(crawler_id)
        assert retrieved_crawler is not None
        assert retrieved_crawler.crawler_name == "更新後的爬蟲名稱"
        assert retrieved_crawler.is_active is False
        assert retrieved_crawler.updated_at is not None
        
        # 測試不存在的ID
        updated_crawler = crawlers_service.update_crawler(999999, update_data)
        assert updated_crawler is None
    
    def test_delete_crawler(self, crawlers_service, sample_crawlers, session):
        """測試刪除爬蟲設定"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        crawler_id = sample_crawlers[0]["id"]  # 使用字典中的 id
        
        # 確認刪除成功
        result = crawlers_service.delete_crawler(crawler_id)
        assert result is True
        
        # 清除會話緩存，確保從數據庫獲取最新數據
        session.expire_all()
        
        # 確認爬蟲設定已被刪除
        assert crawlers_service.get_crawler_by_id(crawler_id) is None
        
        # 測試刪除不存在的爬蟲設定
        result = crawlers_service.delete_crawler(999999)
        assert result is False
    
    def test_toggle_crawler_status(self, crawlers_service, sample_crawlers, session):
        """測試切換爬蟲活躍狀態"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        crawler_id = sample_crawlers[1]["id"]  # 使用字典中的 id，選擇非活躍的爬蟲
        
        # 獲取原始爬蟲設定
        original_crawler = crawlers_service.get_crawler_by_id(crawler_id)
        original_is_active = original_crawler.is_active
        
        # 切換活躍狀態
        updated_crawler = crawlers_service.toggle_crawler_status(crawler_id)
        assert updated_crawler is not None
        assert updated_crawler.is_active != original_is_active
        
        # 清除會話緩存，確保從數據庫獲取最新數據
        session.expire_all()
        
        # 再次切換
        updated_crawler = crawlers_service.toggle_crawler_status(crawler_id)
        assert updated_crawler.is_active == original_is_active
        
        # 測試切換不存在的爬蟲設定
        result = crawlers_service.toggle_crawler_status(999999)
        assert result is None


class TestCrawlersServiceErrorHandling:
    """測試爬蟲服務的錯誤處理"""
    
    def test_invalid_crawler_data(self, crawlers_service, session):
        """測試無效爬蟲設定資料處理"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        # 缺少必要欄位
        invalid_data = {
            "crawler_name": "測試爬蟲",
            "base_url": "https://example.com/test",
            "config_file_name": "test_config.json",
            "is_active": True
            # 缺少 crawler_type
        }
        
        with pytest.raises(ValidationError) as excinfo:
            crawlers_service.create_crawler(invalid_data)
        assert "crawler_type" in str(excinfo.value)
        
         # 缺少必要欄位 config_file_name
        invalid_data = {
            "crawler_name": "測試爬蟲",
            "base_url": "https://example.com/test",
            "crawler_type": "test",
            "is_active": True
            # 缺少 config_file_name
        }
    
        with pytest.raises(ValidationError) as excinfo:
            crawlers_service.create_crawler(invalid_data)
        assert "config_file_name" in str(excinfo.value)
    
    def test_update_immutable_fields(self, crawlers_service, sample_crawlers, session):
        """測試更新不可變欄位處理"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        crawler_id = sample_crawlers[0]["id"]  # 使用字典中的 id
        
        # 嘗試更新不可變欄位
        immutable_update = {
            "created_at": datetime.now(timezone.utc)  # created_at 是不可變欄位
        }
        
        # 更新不可變欄位時應該引發例外
        with pytest.raises(ValidationError):
            crawlers_service.update_crawler(crawler_id, immutable_update)
    
    def test_validation_with_schema(self, crawlers_service, session):
        """測試使用Schema進行驗證"""
        session.expire_all()
        
        # 無效的base_url    
        invalid_data = {
            "crawler_name": "測試爬蟲",
            "base_url": "",  # 無效的URL
            "is_active": True,
            "crawler_type": "test",
            "config_file_name": "test_config.json"
        }
        
        with pytest.raises(ValidationError) as excinfo:
            crawlers_service.create_crawler(invalid_data)
        assert "base_url" in str(excinfo.value)
        
        # 測試更新不可變欄位 crawler_type
        invalid_update = {
            "crawler_type": "new_type"  # 試圖更新不可變欄位
        }
        
        # 需先創建一個有效的爬蟲，然後嘗試更新它的不可變欄位
        valid_data = {
            "crawler_name": "可更新測試爬蟲",
            "base_url": "https://example.com/test",
            "crawler_type": "test",
            "config_file_name": "test_config.json",
            "is_active": True
        }
        
        created_crawler = crawlers_service.create_crawler(valid_data)
        
        with pytest.raises(ValidationError) as excinfo:
            crawlers_service.update_crawler(created_crawler.id, invalid_update)
        assert "crawler_type" in str(excinfo.value)
    
    def test_empty_update_data(self, crawlers_service, sample_crawlers, session):
        """測試空更新資料處理"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        crawler_id = sample_crawlers[0]["id"]  # 使用字典中的 id
        
        # 沒有任何欄位的更新資料
        empty_update = {}
        
        with pytest.raises(ValidationError) as excinfo:
            crawlers_service.update_crawler(crawler_id, empty_update)
        
        # 檢查錯誤訊息中是否包含有關提供至少一個更新欄位的內容
        error_message = str(excinfo.value).lower()
        assert "crawler_name, base_url" in error_message

class TestCrawlersServiceTransactions:
    """測試爬蟲服務的事務處理"""
    
    def test_update_transaction(self, crawlers_service, sample_crawlers, session):
        """測試更新的事務性"""
        session.expire_all()
    
        crawler_id = sample_crawlers[0]["id"]
        
        original_crawler = crawlers_service.get_crawler_by_id(crawler_id)
        original_name = original_crawler.crawler_name
        original_url = original_crawler.base_url
        
        # 無效的更新資料 - 空的base_url
        invalid_update = {
            "crawler_name": "有效名稱",
            "base_url": ""  # 無效值 
        }
        
        with pytest.raises(ValidationError):
            crawlers_service.update_crawler(crawler_id, invalid_update)
        
        session.expire_all()
        
        updated_crawler = crawlers_service.get_crawler_by_id(crawler_id)
        assert updated_crawler.crawler_name == original_name
        assert updated_crawler.base_url == original_url