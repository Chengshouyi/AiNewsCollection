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

# 設定測試資料庫
@pytest.fixture
def engine():
    return create_engine('sqlite:///:memory:')

@pytest.fixture
def tables(engine):
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture
def session(engine, tables):
    """建立測試會話"""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()

@pytest.fixture
def db_manager(engine, monkeypatch):
    """創建真實的 DatabaseManager 實例用於測試"""
    # 設定環境變數指向記憶體資料庫
    monkeypatch.setenv('DATABASE_PATH', 'sqlite:///:memory:')
    
    # 創建 DatabaseManager 實例
    manager = DatabaseManager()
    
    # 替換引擎和會話工廠，使用測試用的記憶體資料庫
    manager.engine = engine
    manager.Session = sessionmaker(bind=engine)
    
    # 創建所有表格
    Base.metadata.create_all(engine)
    
    return manager

@pytest.fixture
def crawlers_service(db_manager):
    """創建爬蟲服務實例"""
    return CrawlersService(db_manager)

@pytest.fixture
def sample_crawlers(db_manager):
    """創建樣本爬蟲資料並保存 ID 和屬性值"""
    crawlers_data = [
        {
            "id": None,
            "crawler_name": "數位時代爬蟲",
            "base_url": "https://www.bnext.com.tw/articles",
            "is_active": True,
            "created_at": datetime(2023, 1, 2, tzinfo=timezone.utc)
        },
        {
            "id": None,
            "crawler_name": "科技報導爬蟲",
            "base_url": "https://technews.tw",
            "is_active": False,
            "created_at": datetime(2023, 1, 3, tzinfo=timezone.utc)
        },
        {
            "id": None,
            "crawler_name": "商業週刊爬蟲",
            "base_url": "https://www.businessweekly.com.tw",
            "is_active": True,
            "created_at": datetime(2023, 1, 4, tzinfo=timezone.utc)
        }
    ]
    
    # 創建 Crawlers 物件並插入資料庫
    crawler_objects = []
    for crawler_data in crawlers_data:
        crawler = Crawlers(
            crawler_name=crawler_data["crawler_name"],
            base_url=crawler_data["base_url"],
            is_active=crawler_data["is_active"],
            created_at=crawler_data["created_at"]
        )
        crawler_objects.append(crawler)
    
    # 使用 DatabaseManager 的會話插入爬蟲設定
    with db_manager.session_scope() as session:
        session.add_all(crawler_objects)
        session.commit()
        # 獲取 ID
        for i, crawler in enumerate(crawler_objects):
            crawlers_data[i]["id"] = crawler.id
    
    # 返回資料字典而非物件，避免分離實例問題
    return crawlers_data

@pytest.fixture
def valid_crawler_data():
    return {
        "crawler_name": "測試爬蟲",
        "base_url": "https://example.com/test",
        "is_active": True
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
    
    def test_create_crawler(self, crawlers_service, valid_crawler_data):
        """測試創建爬蟲設定"""
        result = crawlers_service.create_crawler(valid_crawler_data)
        assert result is not None
        
        # 透過 ID 重新查詢爬蟲設定，避免使用分離的實例
        crawler_id = result.id
        retrieved_crawler = crawlers_service.get_crawler_by_id(crawler_id)
        
        assert retrieved_crawler is not None
        assert retrieved_crawler.crawler_name == valid_crawler_data["crawler_name"]
        assert retrieved_crawler.base_url == valid_crawler_data["base_url"]
        assert retrieved_crawler.is_active == valid_crawler_data["is_active"]
    
    def test_get_all_crawlers(self, crawlers_service, sample_crawlers):
        """測試獲取所有爬蟲設定"""
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
    
    def test_get_crawler_by_id(self, crawlers_service, sample_crawlers):
        """測試根據ID獲取爬蟲設定"""
        crawler_id = sample_crawlers[0]["id"]  # 使用字典中的 id
        crawler = crawlers_service.get_crawler_by_id(crawler_id)
        
        assert crawler is not None
        assert crawler.id == crawler_id
        
        # 測試無效ID
        crawler = crawlers_service.get_crawler_by_id(999999)
        assert crawler is None
    
    def test_get_active_crawlers(self, crawlers_service, sample_crawlers):
        """測試獲取活動中的爬蟲設定"""
        active_crawlers = crawlers_service.get_active_crawlers()
        
        # 驗證所有返回的爬蟲設定都是活動中的
        assert len(active_crawlers) > 0
        assert all(crawler.is_active for crawler in active_crawlers)
        
        # 驗證數量是否正確 (應該有2個活動中的爬蟲)
        assert len(active_crawlers) == 2
    
    def test_get_crawlers_by_name(self, crawlers_service, sample_crawlers):
        """測試根據名稱模糊查詢爬蟲設定"""
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
    
    def test_get_pending_crawlers(self, crawlers_service, sample_crawlers, monkeypatch):
        """測試獲取待執行的爬蟲設定"""
        # 模擬當前時間為最後爬取時間後的足夠時間
        future_time = datetime.now(timezone.utc) + timedelta(hours=5)
        
        # 創建一個模擬的 now 方法
        def mock_now(tz=None):
            return future_time
        
        # 使用 monkeypatch 替換時間提供者的 now 方法
        monkeypatch.setattr(crawlers_service.datetime_provider, 'now', mock_now)
        
        # 獲取待執行的爬蟲設定
        pending_crawlers = crawlers_service.get_pending_crawlers()
        
        # 應該找到所有活動中的爬蟲（在這個模擬的時間點，所有活動爬蟲都應該是待執行的）
        assert len(pending_crawlers) == 2
        assert all(crawler.is_active for crawler in pending_crawlers)
    
    def test_update_crawler(self, crawlers_service, sample_crawlers):
        """測試更新爬蟲設定"""
        crawler_id = sample_crawlers[0]["id"]  # 使用字典中的 id
        
        # 準備更新資料
        update_data = {
            "crawler_name": "更新後的爬蟲名稱",
            "is_active": False
        }
        
        updated_crawler = crawlers_service.update_crawler(crawler_id, update_data)
        assert updated_crawler is not None
        
        # 重新查詢更新後的爬蟲設定，避免使用分離的實例
        retrieved_crawler = crawlers_service.get_crawler_by_id(crawler_id)
        assert retrieved_crawler is not None
        assert retrieved_crawler.crawler_name == "更新後的爬蟲名稱"
        assert retrieved_crawler.is_active is False
        assert retrieved_crawler.updated_at is not None
        
        # 測試不存在的ID
        updated_crawler = crawlers_service.update_crawler(999999, update_data)
        assert updated_crawler is None
    
    def test_delete_crawler(self, crawlers_service, sample_crawlers):
        """測試刪除爬蟲設定"""
        crawler_id = sample_crawlers[0]["id"]  # 使用字典中的 id
        
        # 確認刪除成功
        result = crawlers_service.delete_crawler(crawler_id)
        assert result is True
        
        # 確認爬蟲設定已被刪除
        assert crawlers_service.get_crawler_by_id(crawler_id) is None
        
        # 測試刪除不存在的爬蟲設定
        result = crawlers_service.delete_crawler(999999)
        assert result is False
    
    def test_toggle_crawler_status(self, crawlers_service, sample_crawlers):
        """測試切換爬蟲活躍狀態"""
        crawler_id = sample_crawlers[0]["id"]  # 使用字典中的 id
        
        # 獲取原始爬蟲設定
        original_crawler = crawlers_service.get_crawler_by_id(crawler_id)
        original_is_active = original_crawler.is_active
        
        # 切換活躍狀態
        updated_crawler = crawlers_service.toggle_crawler_status(crawler_id)
        assert updated_crawler is not None
        assert updated_crawler.is_active != original_is_active
        
        # 再次切換
        updated_crawler = crawlers_service.toggle_crawler_status(crawler_id)
        assert updated_crawler.is_active == original_is_active
        
        # 測試切換不存在的爬蟲設定
        result = crawlers_service.toggle_crawler_status(999999)
        assert result is None


class TestCrawlersServiceErrorHandling:
    """測試爬蟲服務的錯誤處理"""
    
    def test_invalid_crawler_data(self, crawlers_service):
        """測試無效爬蟲設定資料處理"""
        # 缺少必要欄位
        invalid_data = {
            "crawler_name": "測試爬蟲"
            # 缺少 base_url 等必要欄位
        }
        
        with pytest.raises(Exception) as excinfo:
            crawlers_service.create_crawler(invalid_data)
        assert "ValidationError" in str(excinfo.value) or "do not be empty" in str(excinfo.value)
    
    def test_update_immutable_fields(self, crawlers_service, sample_crawlers):
        """測試更新不可變欄位處理"""
        crawler_id = sample_crawlers[0]["id"]  # 使用字典中的 id
        
        # 嘗試更新不可變欄位
        immutable_update = {
            "created_at": datetime.now(timezone.utc)  # created_at 是不可變欄位
        }
        
        # 更新不可變欄位時應該引發例外
        with pytest.raises(ValidationError):
            crawlers_service.update_crawler(crawler_id, immutable_update)
    
    def test_validation_with_schema(self, crawlers_service):
        """測試使用Schema進行驗證"""
        # 無效的base_url    
        invalid_data = {
            "crawler_name": "測試爬蟲",
            "base_url": "",
            "is_active": True
        }
        
        with pytest.raises(Exception) as excinfo:
            crawlers_service.create_crawler(invalid_data)
        assert "ValidationError" in str(excinfo.value) or "must be greater than 0" in str(excinfo.value)
    
    def test_empty_update_data(self, crawlers_service, sample_crawlers):
        """測試空更新資料處理"""
        crawler_id = sample_crawlers[0]["id"]  # 使用字典中的 id
        
        # 沒有任何欄位的更新資料
        empty_update = {}
        
        with pytest.raises(Exception) as excinfo:
            crawlers_service.update_crawler(crawler_id, empty_update)
        
        # 檢查錯誤訊息中是否包含有關提供至少一個更新欄位的內容
        error_message = str(excinfo.value).lower()
        assert "必須提供至少一個欄位進行更新" in error_message or "validation" in error_message


class TestCrawlersServiceTransactions:
    """測試爬蟲服務的事務處理"""
    
    def test_update_transaction(self, crawlers_service, sample_crawlers):
        """測試更新的事務性"""
        crawler_id = sample_crawlers[0]["id"]  # 使用字典中的 id
        
        # 無效的更新資料 - 爬取間隔為負數
        invalid_update = {
            "crawler_name": "有效名稱",
            "base_url": ""  # 無效值 
        }
        
        # 由於更新資料無效，更新應該失敗
        with pytest.raises(Exception):
            crawlers_service.update_crawler(crawler_id, invalid_update)
        
        # 驗證爬蟲設定未被更新（事務回滾）
        updated_crawler = crawlers_service.get_crawler_by_id(crawler_id)
        # 確保名稱和爬取間隔未被更新為無效值
        assert updated_crawler.crawler_name != "有效名稱"
        assert updated_crawler.base_url != ""


def test_crawlers_model_immutable_fields():
    """直接測試 Crawlers 模型的不可變欄位"""
    crawler = Crawlers(
        crawler_name="測試爬蟲",
        base_url="https://example.com/test",
        is_active=True
    )
    
    # 測試修改 id 欄位
    with pytest.raises(ValidationError):
        crawler.id = 999
    
    # 測試修改 created_at 欄位
    with pytest.raises(ValidationError):
        crawler.created_at = datetime.now(timezone.utc)
