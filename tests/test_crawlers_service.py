import pytest
from datetime import datetime, timezone
import os
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.crawlers_model import Crawlers
from src.models.base_model import Base
from src.services.crawlers_service import CrawlersService, DatetimeProvider
from src.error.errors import ValidationError, DatabaseOperationError
from src.database.database_manager import DatabaseManager
from src.database.crawlers_repository import CrawlersRepository
from src.models.crawlers_schema import CrawlerReadSchema

# 固定測試時間
MOCK_TIME = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

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
    service = CrawlersService(db_manager)
    # 模擬 DatetimeProvider
    with patch.object(service.datetime_provider, 'now', return_value=MOCK_TIME) as mock_now:
        yield service # 使用 yield 確保模擬在測試期間有效

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
            "crawler_type": "technews",
            "config_file_name": "technews_crawler_config.json"
        },
        {
            "crawler_name": "商業週刊爬蟲",
            "base_url": "https://www.businessweekly.com.tw",
            "is_active": True,
            "crawler_type": "business",
            "config_file_name": "business_crawler_config.json"
        }
    ]
    
    created_crawlers = []
    for crawler_data in crawlers_data:
        with db_manager.session_scope() as session:
            crawler = Crawlers(
                crawler_name=crawler_data["crawler_name"],
                base_url=crawler_data["base_url"],
                is_active=crawler_data["is_active"],
                crawler_type=crawler_data["crawler_type"],
                config_file_name=crawler_data["config_file_name"],
                # 添加時間戳以匹配模型
                created_at=MOCK_TIME,
                updated_at=MOCK_TIME
            )
            session.add(crawler)
            session.commit()
            session.refresh(crawler)
            # 保存 ID 和完整數據
            crawler_dict = CrawlerReadSchema.model_validate(crawler).model_dump()
            created_crawlers.append(crawler_dict) # 儲存 Schema dict
    
    return created_crawlers

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
    
    def test_create_crawler(self, crawlers_service, valid_crawler_data, session):
        """測試創建爬蟲設定"""
        # 清除可能存在的同名爬蟲設定
        session.query(Crawlers).filter_by(crawler_name=valid_crawler_data["crawler_name"]).delete()
        session.commit()
        
        result = crawlers_service.create_crawler(valid_crawler_data)
        assert result['success'] is True
        assert result['message'] == "爬蟲設定創建成功"
        assert result['crawler'] is not None
        
        # 驗證創建的爬蟲資料 (使用 Schema)
        created_crawler = result['crawler']
        assert isinstance(created_crawler, CrawlerReadSchema)
        assert created_crawler.crawler_name == valid_crawler_data["crawler_name"]
        assert created_crawler.base_url == valid_crawler_data["base_url"]
        assert created_crawler.is_active == valid_crawler_data["is_active"]
        assert created_crawler.crawler_type == valid_crawler_data["crawler_type"]
        assert created_crawler.config_file_name == valid_crawler_data["config_file_name"]
        assert created_crawler.created_at == MOCK_TIME
        assert isinstance(created_crawler.updated_at, datetime)
        assert created_crawler.updated_at >= created_crawler.created_at # 確保更新時間不早於創建時間
    
    def test_get_all_crawlers(self, crawlers_service, sample_crawlers, session):
        """測試獲取所有爬蟲設定"""
        result = crawlers_service.get_all_crawlers()
        assert result['success'] is True
        assert len(result['crawlers']) == 3
        assert all(isinstance(c, CrawlerReadSchema) for c in result['crawlers']) # 檢查類型
        
        # 測試分頁
        result = crawlers_service.get_all_crawlers(limit=2)
        assert len(result['crawlers']) == 2
        
        result = crawlers_service.get_all_crawlers(offset=1, limit=1)
        assert len(result['crawlers']) == 1
        
        # 測試排序
        result = crawlers_service.get_all_crawlers(sort_by="crawler_name", sort_desc=True)
        names = [crawler.crawler_name for crawler in result['crawlers']]
        # 從 sample_crawlers 獲取預期排序的名稱
        expected_names = sorted([c['crawler_name'] for c in sample_crawlers], reverse=True)
        assert names == expected_names
    
    def test_get_crawler_by_id(self, crawlers_service, sample_crawlers, session):
        """測試根據ID獲取爬蟲設定"""
        crawler_id = sample_crawlers[0]["id"]
        result = crawlers_service.get_crawler_by_id(crawler_id)
        
        assert result['success'] is True
        assert result['crawler'] is not None
        assert isinstance(result['crawler'], CrawlerReadSchema) # 檢查類型
        assert result['crawler'].id == crawler_id
        assert result['crawler'].crawler_name == sample_crawlers[0]['crawler_name'] # 驗證其他欄位
        
        # 測試無效ID
        result = crawlers_service.get_crawler_by_id(999999)
        assert result['success'] is False
        assert "不存在" in result['message']
        assert result['crawler'] is None # 確保無效時返回 None
    
    def test_get_active_crawlers(self, crawlers_service, sample_crawlers, session):
        """測試獲取活動中的爬蟲設定"""
        result = crawlers_service.get_active_crawlers()
        
        assert result['success'] is True
        assert len(result['crawlers']) == 2
        assert all(isinstance(c, CrawlerReadSchema) for c in result['crawlers']) # 檢查類型
        assert all(crawler.is_active for crawler in result['crawlers'])
    
    def test_get_crawlers_by_name(self, crawlers_service, sample_crawlers, session):
        """測試根據名稱模糊查詢爬蟲設定"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        # --- 測試 is_active=None (預設，查找所有) ---
        result_all = crawlers_service.get_crawlers_by_name("爬蟲")
        assert result_all['success'] is True
        assert len(result_all['crawlers']) == 3, "預期找到所有 3 個包含'爬蟲'的爬蟲"
        assert all(isinstance(c, CrawlerReadSchema) for c in result_all['crawlers']) # 檢查類型
        
        # --- 測試 is_active=True (僅查找活動的) ---
        result_active = crawlers_service.get_crawlers_by_name("爬蟲", is_active=True)
        assert result_active['success'] is True
        assert len(result_active['crawlers']) == 2, "預期找到 2 個活動的'爬蟲'爬蟲"
        assert all(crawler.is_active for crawler in result_active['crawlers'])
        
        # --- 測試 is_active=False (僅查找非活動的) ---
        result_inactive = crawlers_service.get_crawlers_by_name("爬蟲", is_active=False)
        assert result_inactive['success'] is True
        assert len(result_inactive['crawlers']) == 1, "預期找到 1 個非活動的'爬蟲'爬蟲"
        assert not result_inactive['crawlers'][0].is_active

        # 查詢包含"數位"的爬蟲設定 (預設 is_active=None)
        digital_crawlers_result = crawlers_service.get_crawlers_by_name("數位")
        assert digital_crawlers_result['success'] is True
        assert len(digital_crawlers_result['crawlers']) == 1
        assert digital_crawlers_result['crawlers'][0].crawler_name == "數位時代爬蟲"
        
        # 測試不存在的名稱
        no_crawlers_result = crawlers_service.get_crawlers_by_name("不存在")
        # 服務層現在對於找不到結果返回 success: True 和空列表
        assert no_crawlers_result['success'] is True
        assert "找不到任何符合條件的爬蟲設定" in no_crawlers_result['message']
        assert len(no_crawlers_result['crawlers']) == 0
    
    def test_update_crawler(self, crawlers_service, sample_crawlers, session):
        """測試更新爬蟲設定"""
        crawler_id = sample_crawlers[0]["id"]
        
        update_data = {
            "crawler_name": "更新後的爬蟲名稱",
            "base_url": "https://example.com/updated",
            "is_active": False,
            "config_file_name": "bnext_crawler_config_updated.json" # 更新配置檔名
        }
        
        result = crawlers_service.update_crawler(crawler_id, update_data)
        assert result['success'] is True
        assert result['crawler'] is not None
        assert isinstance(result['crawler'], CrawlerReadSchema) # 檢查類型
        assert result['crawler'].id == crawler_id
        assert result['crawler'].crawler_name == "更新後的爬蟲名稱"
        assert result['crawler'].base_url == "https://example.com/updated"
        assert result['crawler'].is_active is False
        assert result['crawler'].config_file_name == "bnext_crawler_config_updated.json"
        assert isinstance(result['crawler'].updated_at, datetime) # 驗證是時間類型
        assert result['crawler'].updated_at >= MOCK_TIME # 驗證更新時間不早於模擬時間
        assert result['crawler'].created_at == MOCK_TIME # 創建時間應保持不變 (取決於 fixture 數據)
        
        # 測試不存在的ID
        result = crawlers_service.update_crawler(999999, update_data)
        assert result['success'] is False
        assert "不存在" in result['message']
        assert result['crawler'] is None
    
    def test_delete_crawler(self, crawlers_service, sample_crawlers, session):
        """測試刪除爬蟲設定"""
        crawler_id = sample_crawlers[0]["id"]
        
        result = crawlers_service.delete_crawler(crawler_id)
        assert result['success'] is True
        
        # 確認爬蟲已被刪除
        get_result = crawlers_service.get_crawler_by_id(crawler_id)
        assert get_result['success'] is False
        
        # 測試刪除不存在的爬蟲
        result = crawlers_service.delete_crawler(999999)
        assert result['success'] is False
        assert "不存在" in result['message'] # 驗證錯誤消息
    
    def test_toggle_crawler_status(self, crawlers_service, sample_crawlers, session):
        """測試切換爬蟲活躍狀態"""
        crawler_id = sample_crawlers[1]["id"] # 選擇一個初始為 inactive 的爬蟲
        original_is_active = sample_crawlers[1]["is_active"] # 獲取 fixture 中的原始狀態
        assert original_is_active is False # 確保選取的樣本是 inactive
        
        # 第一次切換 (Inactive -> Active)
        result = crawlers_service.toggle_crawler_status(crawler_id)
        assert result['success'] is True
        assert result['crawler'] is not None
        assert isinstance(result['crawler'], CrawlerReadSchema) # 檢查類型
        assert result['crawler'].id == crawler_id
        assert result['crawler'].is_active is True # 狀態應變為 Active
        assert result['crawler'].updated_at == MOCK_TIME # 驗證更新時間
        
        # 第二次切換 (Active -> Inactive)
        result = crawlers_service.toggle_crawler_status(crawler_id)
        assert result['success'] is True
        assert result['crawler'] is not None
        assert isinstance(result['crawler'], CrawlerReadSchema) # 檢查類型
        assert result['crawler'].id == crawler_id
        assert result['crawler'].is_active is False # 狀態應恢復為 Inactive
        assert result['crawler'].updated_at == MOCK_TIME # 驗證更新時間
        
        # 測試不存在的爬蟲
        result = crawlers_service.toggle_crawler_status(999999)
        assert result['success'] is False
        assert "不存在" in result['message']
        assert result['crawler'] is None
    
    def test_get_crawlers_by_type(self, crawlers_service, sample_crawlers, session):
        """測試根據爬蟲類型查找爬蟲"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        # 查詢 bnext 類型的爬蟲
        result = crawlers_service.get_crawlers_by_type("bnext")
        assert result['success'] is True
        assert len(result['crawlers']) == 1
        assert isinstance(result['crawlers'][0], CrawlerReadSchema) # 檢查類型
        assert all(crawler.crawler_type == "bnext" for crawler in result['crawlers'])
        
        # 測試不存在的類型
        no_result = crawlers_service.get_crawlers_by_type("不存在類型")
        assert no_result['success'] is True # 服務層找不到時返回 True
        assert f"找不到類型為 不存在類型 的爬蟲設定" in no_result['message']
        assert len(no_result['crawlers']) == 0
    
    def test_get_crawlers_by_target(self, crawlers_service, sample_crawlers, session):
        """測試根據爬取目標模糊查詢爬蟲"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        # 查詢 URL 包含 bnext 的爬蟲
        result = crawlers_service.get_crawlers_by_target("bnext")
        assert result['success'] is True
        assert len(result['crawlers']) == 1
        assert isinstance(result['crawlers'][0], CrawlerReadSchema) # 檢查類型
        assert "bnext" in result['crawlers'][0].base_url
        
        # 測試不存在的目標
        no_result = crawlers_service.get_crawlers_by_target("不存在網址")
        assert no_result['success'] is True # 服務層找不到時返回 True
        assert f"找不到目標包含 不存在網址 的爬蟲設定" in no_result['message']
        assert len(no_result['crawlers']) == 0
    
    def test_get_crawler_statistics(self, crawlers_service, sample_crawlers, session):
        """測試獲取爬蟲統計信息"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        result = crawlers_service.get_crawler_statistics()
        assert result['success'] is True
        assert 'statistics' in result
        
        stats = result['statistics']
        assert stats['total'] == 3
        assert stats['active'] == 2
        assert stats['inactive'] == 1
        assert 'by_type' in stats

        # 直接檢查服務返回的 by_type 字典
        type_counts = stats['by_type'] 
        assert isinstance(type_counts, dict), "stats['by_type'] 應該是一個字典"
        assert len(type_counts) == 3 # 根據 sample_crawlers 有 3 種類型
        assert type_counts['bnext'] == 1
        assert type_counts['technews'] == 1
        assert type_counts['business'] == 1
    
    def test_get_crawler_by_exact_name(self, crawlers_service, sample_crawlers, session):
        """測試根據爬蟲名稱精確查詢"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        # 精確查詢存在的爬蟲名稱
        exact_name = sample_crawlers[0]["crawler_name"]
        result = crawlers_service.get_crawler_by_exact_name(exact_name)
        assert result['success'] is True
        assert result['crawler'] is not None
        assert isinstance(result['crawler'], CrawlerReadSchema) # 檢查類型
        assert result['crawler'].crawler_name == exact_name
        
        # 測試不存在的名稱
        no_result = crawlers_service.get_crawler_by_exact_name("不存在的名稱")
        assert no_result['success'] is False # 服務層精確查找失敗時返回 False
        assert "找不到名稱為" in no_result['message']
        assert no_result['crawler'] is None
    
    def test_create_or_update_crawler(self, crawlers_service, sample_crawlers, session):
        """測試創建或更新爬蟲設定"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        # 測試更新現有爬蟲
        existing_id = sample_crawlers[0]["id"]
        
        # 使用一個唯一的名稱來避免衝突
        unique_name = f"更新測試爬蟲_{datetime.now().timestamp()}"
        
        # 注意：更新爬蟲時不應包含 crawler_type 和 created_at
        update_data = {
            "id": existing_id,
            "crawler_name": unique_name,
            "base_url": "https://example.com/updated",
            "is_active": False,
            "config_file_name": "test_config_updated.json"
        }
        
        result = crawlers_service.create_or_update_crawler(update_data)
        assert result['success'] is True
        assert result['crawler'] is not None
        assert isinstance(result['crawler'], CrawlerReadSchema) # 檢查類型
        assert result['crawler'].id == existing_id
        assert result['crawler'].crawler_name == unique_name
        assert result['crawler'].is_active is False
        assert isinstance(result['crawler'].updated_at, datetime) # 檢查更新時間是 datetime
        assert result['crawler'].updated_at >= MOCK_TIME # 檢查更新時間不早於模擬時間
        assert "更新成功" in result['message']
        
        # 測試創建新爬蟲
        new_unique_name = f"新建測試爬蟲_{datetime.now().timestamp()}"
        
        new_data = {
            "crawler_name": new_unique_name,
            "base_url": "https://example.com/new",
            "is_active": True,
            "crawler_type": "test_new",  # 創建時必須包含 crawler_type
            "config_file_name": "test_config_new.json"
        }
        
        result = crawlers_service.create_or_update_crawler(new_data)
        assert result['success'] is True
        assert result['crawler'] is not None
        assert isinstance(result['crawler'], CrawlerReadSchema) # 檢查類型
        assert result['crawler'].crawler_name == new_unique_name
        assert result['crawler'].crawler_type == "test_new"
        assert result['crawler'].created_at == MOCK_TIME # 檢查創建時間
        assert isinstance(result['crawler'].updated_at, datetime) # 檢查更新時間是 datetime
        assert result['crawler'].updated_at >= MOCK_TIME # 檢查更新時間不早於模擬時間
        assert "創建成功" in result['message']
    
    def test_batch_toggle_crawler_status(self, crawlers_service, sample_crawlers, session):
        """測試批量設置爬蟲的活躍狀態"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        # 獲取所有爬蟲 ID
        crawler_ids = [crawler["id"] for crawler in sample_crawlers]
        
        # 批量停用所有爬蟲
        result = crawlers_service.batch_toggle_crawler_status(crawler_ids, False)
        assert result['success'] is True
        assert result['result']['success_count'] == 3
        assert result['result']['fail_count'] == 0 # 應為 0
        assert "批量停用爬蟲設定完成" in result['message']
        
        # 檢查是否全部已停用
        all_crawlers_result = crawlers_service.get_all_crawlers()
        assert all(not crawler.is_active for crawler in all_crawlers_result['crawlers'])
        
        # 批量啟用所有爬蟲
        result = crawlers_service.batch_toggle_crawler_status(crawler_ids, True)
        assert result['success'] is True
        assert result['result']['success_count'] == 3
        assert result['result']['fail_count'] == 0 # 應為 0
        assert "批量啟用爬蟲設定完成" in result['message']
        
        # 檢查是否全部已啟用
        all_crawlers_result = crawlers_service.get_all_crawlers()
        assert all(crawler.is_active for crawler in all_crawlers_result['crawlers'])
        
        # 測試部分不存在的 ID (預期全部失敗)
        invalid_ids = [999999, 888888]
        result = crawlers_service.batch_toggle_crawler_status(invalid_ids, False)
        assert result['success'] is False # 因為 success_count 為 0
        assert result['result']['success_count'] == 0
        assert result['result']['fail_count'] == 2
        assert 999999 in result['result']['failed_ids'] # 檢查失敗 ID
        assert 888888 in result['result']['failed_ids']
    
    def test_get_filtered_crawlers(self, crawlers_service, sample_crawlers, session):
        """測試根據過濾條件獲取分頁爬蟲列表"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        # 測試按類型過濾
        filter_data = {"crawler_type": "bnext"}
        result = crawlers_service.get_filtered_crawlers(filter_data)
        assert result['success'] is True
        assert result['data'] is not None
        paginated_data = result['data'] # 應為 PaginatedCrawlerResponse
        assert paginated_data.total == 1
        assert paginated_data.page == 1
        assert len(paginated_data.items) == 1
        assert isinstance(paginated_data.items[0], CrawlerReadSchema) # 檢查類型
        assert paginated_data.items[0].crawler_type == "bnext"
        
        # 測試按啟用狀態過濾
        filter_data = {"is_active": True}
        result = crawlers_service.get_filtered_crawlers(filter_data)
        assert result['success'] is True
        paginated_data = result['data']
        assert paginated_data.total == 2
        assert len(paginated_data.items) == 2
        assert all(item.is_active for item in paginated_data.items)
        
        # 測試複合條件過濾
        filter_data = {"is_active": True, "crawler_type": "bnext"}
        result = crawlers_service.get_filtered_crawlers(filter_data)
        assert result['success'] is True
        paginated_data = result['data']
        assert paginated_data.total == 1
        assert len(paginated_data.items) == 1
        assert paginated_data.items[0].crawler_type == "bnext"
        assert paginated_data.items[0].is_active is True
        
        # 測試排序和分頁
        filter_data = {}
        result = crawlers_service.get_filtered_crawlers(
            filter_data, page=1, per_page=2, sort_by="crawler_name", sort_desc=True
        )
        assert result['success'] is True
        paginated_data = result['data']
        assert paginated_data.total == 3
        assert paginated_data.page == 1
        assert len(paginated_data.items) == 2
        assert paginated_data.has_next is True
        assert paginated_data.has_prev is False
        # 驗證排序
        expected_first_page_names = sorted([c['crawler_name'] for c in sample_crawlers], reverse=True)[:2]
        actual_names = [item.crawler_name for item in paginated_data.items]
        assert actual_names == expected_first_page_names

        # 測試獲取第二頁
        result_page_2 = crawlers_service.get_filtered_crawlers(
            filter_data, page=2, per_page=2, sort_by="crawler_name", sort_desc=True
        )
        assert result_page_2['success'] is True
        paginated_data_2 = result_page_2['data']
        assert paginated_data_2.total == 3
        assert paginated_data_2.page == 2
        assert len(paginated_data_2.items) == 1
        assert paginated_data_2.has_next is False
        assert paginated_data_2.has_prev is True
        expected_second_page_names = sorted([c['crawler_name'] for c in sample_crawlers], reverse=True)[2:]
        actual_names_page_2 = [item.crawler_name for item in paginated_data_2.items]
        assert actual_names_page_2 == expected_second_page_names
        
        # 測試不匹配的條件
        filter_data = {"crawler_type": "不存在類型"}
        result = crawlers_service.get_filtered_crawlers(filter_data)
        assert result['success'] is False # 服務層在此情況下返回 False
        assert "找不到符合條件" in result['message']
        assert result['data'] is not None # 即使失敗，也應返回分頁結構
        assert result['data'].total == 0
        assert len(result['data'].items) == 0

class TestCrawlersServiceErrorHandling:
    """測試爬蟲服務的錯誤處理"""
    
    def test_invalid_crawler_data(self, crawlers_service, session):
        """測試無效爬蟲設定資料處理"""
        invalid_data = {
            "crawler_name": "測試爬蟲",
            "base_url": "https://example.com/test",
            "config_file_name": "test_config.json",
            "is_active": True
        }
        
        result = crawlers_service.create_crawler(invalid_data)
        assert result['success'] is False
        assert "crawler_type" in result['message']
    
    def test_validation_with_schema(self, crawlers_service, session):
        """測試使用Schema進行驗證"""
        invalid_data = {
            "crawler_name": "測試爬蟲",
            "base_url": "",  # 無效的URL
            "is_active": True,
            "crawler_type": "test",
            "config_file_name": "test_config.json"
        }
        
        result = crawlers_service.create_crawler(invalid_data)
        assert result['success'] is False
        assert "base_url" in result['message']
    
    def test_empty_update_data(self, crawlers_service, sample_crawlers, session):
        """測試空更新資料處理 (預期僅更新 updated_at)"""
        crawler_id = sample_crawlers[0]["id"]
        empty_update = {}

        # 獲取原始數據以供比較
        original_result = crawlers_service.get_crawler_by_id(crawler_id)
        assert original_result['success'] is True
        original_crawler = original_result['crawler']
        
        # 調用 update_crawler 並檢查返回的字典
        result = crawlers_service.update_crawler(crawler_id, empty_update)
        
        # 使用 exclude_unset=True 後，空字典應該只更新 updated_at，視為成功
        assert result['success'] is True, f"空更新應該成功，只更新 updated_at，但失敗了: {result.get('message')}"
        assert result['crawler'] is not None
        assert result['crawler'].id == crawler_id
        # 驗證其他字段未被更改
        assert result['crawler'].crawler_name == original_crawler.crawler_name
        assert result['crawler'].base_url == original_crawler.base_url
        assert result['crawler'].is_active == original_crawler.is_active
        # 驗證 updated_at 已更新 (會被 onupdate 覆蓋，所以檢查它是否晚於創建時間)
        assert isinstance(result['crawler'].updated_at, datetime)
        assert result['crawler'].updated_at >= original_crawler.created_at

    def test_create_or_update_validation(self, crawlers_service, session):
        """測試創建或更新時的驗證錯誤處理"""
        invalid_data = {
            "crawler_name": "測試爬蟲",
            "base_url": "",  # 無效的URL
            "is_active": True,
            "crawler_type": "test",
            "config_file_name": "test_config.json"
        }
        
        result = crawlers_service.create_or_update_crawler(invalid_data)
        assert result['success'] is False
        assert "爬蟲設定創建資料驗證失敗" in result['message'] # 檢查創建時的驗證失敗
        assert "base_url" in result['message'] # 檢查特定欄位

class TestCrawlersServiceTransactions:
    """測試爬蟲服務的事務處理"""
    
    def test_update_transaction(self, crawlers_service, sample_crawlers, session):
        """測試更新的事務性"""
        crawler_id = sample_crawlers[0]["id"]
        
        original_result = crawlers_service.get_crawler_by_id(crawler_id)
        original_name = original_result['crawler'].crawler_name
        
        invalid_update = {
            "crawler_name": "有效名稱",
            "base_url": ""  # 無效值
        }
        
        result = crawlers_service.update_crawler(crawler_id, invalid_update)
        assert result['success'] is False
        
        # 驗證資料未被更改
        current_result = crawlers_service.get_crawler_by_id(crawler_id)
        assert current_result['crawler'].crawler_name == original_name
    
    def test_batch_toggle_transaction(self, crawlers_service, sample_crawlers, session):
        """測試批量操作的事務性"""
        # 創建一個混合有效和無效 ID 的列表
        valid_id = sample_crawlers[0]["id"]
        invalid_ids = [999999, 888888]
        mixed_ids = [valid_id] + invalid_ids
        
        # 獲取原始狀態
        original_crawler_result = crawlers_service.get_crawler_by_id(valid_id)
        assert original_crawler_result['success'] is True
        original_status = original_crawler_result['crawler'].is_active
        
        # 執行批量操作，預期部分失敗
        result = crawlers_service.batch_toggle_crawler_status(mixed_ids, not original_status)
        
        # 驗證結果
        assert result['success'] is True  # 因為至少有一個成功
        assert result['result']['success_count'] == 1
        assert result['result']['fail_count'] == 2
        assert invalid_ids[0] in result['result']['failed_ids']
        assert invalid_ids[1] in result['result']['failed_ids']
        
        # 檢查有效 ID 的狀態已變更
        updated_result = crawlers_service.get_crawler_by_id(valid_id)
        assert updated_result['success'] is True
        assert updated_result['crawler'].is_active != original_status