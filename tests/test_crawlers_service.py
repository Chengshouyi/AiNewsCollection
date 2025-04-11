import pytest
from datetime import datetime, timezone
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.crawlers_model import Crawlers
from src.models.base_model import Base
from src.services.crawlers_service import CrawlersService
from src.error.errors import ValidationError, DatabaseOperationError
from src.database.database_manager import DatabaseManager
from src.database.crawlers_repository import CrawlersRepository

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
                config_file_name=crawler_data["config_file_name"]
            )
            session.add(crawler)
            session.commit()
            session.refresh(crawler)
            crawler_data["id"] = crawler.id
            created_crawlers.append(crawler_data)
    
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
    
    def test_get_repository(self, crawlers_service, db_manager):
        """測試獲取儲存庫"""
        repo = crawlers_service._get_repository()
        assert isinstance(repo, CrawlersRepository)
    
    def test_create_crawler(self, crawlers_service, valid_crawler_data, session):
        """測試創建爬蟲設定"""
        # 清除可能存在的同名爬蟲設定
        session.query(Crawlers).filter_by(crawler_name=valid_crawler_data["crawler_name"]).delete()
        session.commit()
        
        result = crawlers_service.create_crawler(valid_crawler_data)
        assert result['success'] is True
        assert result['message'] == "爬蟲設定創建成功"
        assert result['crawler'] is not None
        
        # 驗證創建的爬蟲資料
        created_crawler = result['crawler']
        assert created_crawler.crawler_name == valid_crawler_data["crawler_name"]
        assert created_crawler.base_url == valid_crawler_data["base_url"]
        assert created_crawler.is_active == valid_crawler_data["is_active"]
    
    def test_get_all_crawlers(self, crawlers_service, sample_crawlers, session):
        """測試獲取所有爬蟲設定"""
        result = crawlers_service.get_all_crawlers()
        assert result['success'] is True
        assert len(result['crawlers']) == 3
        
        # 測試分頁
        result = crawlers_service.get_all_crawlers(limit=2)
        assert len(result['crawlers']) == 2
        
        result = crawlers_service.get_all_crawlers(offset=1, limit=1)
        assert len(result['crawlers']) == 1
        
        # 測試排序
        result = crawlers_service.get_all_crawlers(sort_by="crawler_name", sort_desc=True)
        names = [crawler.crawler_name for crawler in result['crawlers']]
        assert sorted(names, reverse=True) == names
    
    def test_get_crawler_by_id(self, crawlers_service, sample_crawlers, session):
        """測試根據ID獲取爬蟲設定"""
        crawler_id = sample_crawlers[0]["id"]
        result = crawlers_service.get_crawler_by_id(crawler_id)
        
        assert result['success'] is True
        assert result['crawler'] is not None
        assert result['crawler'].id == crawler_id
        
        # 測試無效ID
        result = crawlers_service.get_crawler_by_id(999999)
        assert result['success'] is False
        assert "不存在" in result['message']
    
    def test_get_active_crawlers(self, crawlers_service, sample_crawlers, session):
        """測試獲取活動中的爬蟲設定"""
        result = crawlers_service.get_active_crawlers()
        
        assert result['success'] is True
        assert len(result['crawlers']) == 2
        assert all(crawler.is_active for crawler in result['crawlers'])
    
    def test_get_crawlers_by_name(self, crawlers_service, sample_crawlers, session):
        """測試根據名稱模糊查詢爬蟲設定"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        # 查詢包含"爬蟲"的爬蟲設定
        crawlers = crawlers_service.get_crawlers_by_name("爬蟲")
        assert crawlers['success'] is True
        assert len(crawlers['crawlers']) == 3  # 所有爬蟲設定名稱都包含"爬蟲"
        
        # 查詢包含"數位"的爬蟲設定
        digital_crawlers = crawlers_service.get_crawlers_by_name("數位")
        assert digital_crawlers['success'] is True
        assert len(digital_crawlers['crawlers']) == 1
        
        # 測試不存在的名稱
        no_crawlers = crawlers_service.get_crawlers_by_name("不存在")
        assert no_crawlers['success'] is False
        assert "找不到任何符合條件的爬蟲設定" in no_crawlers['message']
    
    def test_update_crawler(self, crawlers_service, sample_crawlers, session):
        """測試更新爬蟲設定"""
        crawler_id = sample_crawlers[0]["id"]
        
        update_data = {
            "crawler_name": "更新後的爬蟲名稱",
            "base_url": "https://example.com/updated",
            "is_active": False,
            "config_file_name": "bnext_crawler_config.json"
        }
        
        result = crawlers_service.update_crawler(crawler_id, update_data)
        assert result['success'] is True
        assert result['crawler'] is not None
        assert result['crawler'].crawler_name == "更新後的爬蟲名稱"
        
        # 測試不存在的ID
        result = crawlers_service.update_crawler(999999, update_data)
        assert result['success'] is False
        assert "不存在" in result['message']
    
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
    
    def test_toggle_crawler_status(self, crawlers_service, sample_crawlers, session):
        """測試切換爬蟲活躍狀態"""
        crawler_id = sample_crawlers[1]["id"]
        
        # 獲取原始狀態
        original_result = crawlers_service.get_crawler_by_id(crawler_id)
        original_is_active = original_result['crawler'].is_active
        
        # 切換狀態
        result = crawlers_service.toggle_crawler_status(crawler_id)
        assert result['success'] is True
        assert result['crawler'].is_active != original_is_active
        
        # 再次切換
        result = crawlers_service.toggle_crawler_status(crawler_id)
        assert result['success'] is True
        assert result['crawler'].is_active == original_is_active
        
        # 測試不存在的爬蟲
        result = crawlers_service.toggle_crawler_status(999999)
        assert result['success'] is False
    
    def test_get_crawlers_by_type(self, crawlers_service, sample_crawlers, session):
        """測試根據爬蟲類型查找爬蟲"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        # 查詢 bnext 類型的爬蟲
        result = crawlers_service.get_crawlers_by_type("bnext")
        assert result['success'] is True
        assert len(result['crawlers']) == 1
        assert all(crawler.crawler_type == "bnext" for crawler in result['crawlers'])
        
        # 測試不存在的類型
        no_result = crawlers_service.get_crawlers_by_type("不存在類型")
        assert no_result['success'] is False
        assert "找不到類型為" in no_result['message']
    
    def test_get_crawlers_by_target(self, crawlers_service, sample_crawlers, session):
        """測試根據爬取目標模糊查詢爬蟲"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        # 查詢 URL 包含 bnext 的爬蟲
        result = crawlers_service.get_crawlers_by_target("bnext")
        assert result['success'] is True
        assert len(result['crawlers']) == 1
        
        # 測試不存在的目標
        no_result = crawlers_service.get_crawlers_by_target("不存在網址")
        assert no_result['success'] is False
        assert "找不到目標包含" in no_result['message']
    
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
        assert len(stats['by_type']) >= 1  # 至少有一種類型
    
    def test_get_crawler_by_exact_name(self, crawlers_service, sample_crawlers, session):
        """測試根據爬蟲名稱精確查詢"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        # 精確查詢存在的爬蟲名稱
        exact_name = sample_crawlers[0]["crawler_name"]
        result = crawlers_service.get_crawler_by_exact_name(exact_name)
        assert result['success'] is True
        assert result['crawler'] is not None
        assert result['crawler'].crawler_name == exact_name
        
        # 測試不存在的名稱
        no_result = crawlers_service.get_crawler_by_exact_name("不存在的名稱")
        assert no_result['success'] is False
        assert "找不到名稱為" in no_result['message']
    
    def test_create_or_update_crawler(self, crawlers_service, sample_crawlers, session):
        """測試創建或更新爬蟲設定"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        # 測試更新現有爬蟲
        existing_id = sample_crawlers[0]["id"]
        
        # 先獲取現有的爬蟲以確保名稱不會與其他爬蟲衝突
        existing_crawler = crawlers_service.get_crawler_by_id(existing_id)
        assert existing_crawler['success'] is True
        
        # 使用一個唯一的名稱來避免衝突
        unique_name = f"更新測試爬蟲_{datetime.now().timestamp()}"
        
        # 注意：更新爬蟲時不能包含 crawler_type，它是不可變欄位
        update_data = {
            "id": existing_id,
            "crawler_name": unique_name,
            "base_url": "https://example.com/updated",
            "is_active": False,
            "config_file_name": "test_config.json"
        }
        
        result = crawlers_service.create_or_update_crawler(update_data)
        assert result['success'] is True
        assert result['crawler'] is not None
        assert result['crawler'].crawler_name == unique_name
        assert "更新成功" in result['message']
        
        # 測試創建新爬蟲
        new_unique_name = f"新建測試爬蟲_{datetime.now().timestamp()}"
        
        new_data = {
            "crawler_name": new_unique_name,
            "base_url": "https://example.com/new",
            "is_active": True,
            "crawler_type": "test_new",  # 創建時必須包含 crawler_type
            "config_file_name": "test_config.json"
        }
        
        result = crawlers_service.create_or_update_crawler(new_data)
        assert result['success'] is True
        assert result['crawler'] is not None
        assert result['crawler'].crawler_name == new_unique_name
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
        assert "批量停用爬蟲設定完成" in result['message']
        
        # 檢查是否全部已停用
        all_crawlers = crawlers_service.get_all_crawlers()
        assert all(not crawler.is_active for crawler in all_crawlers['crawlers'])
        
        # 批量啟用所有爬蟲
        result = crawlers_service.batch_toggle_crawler_status(crawler_ids, True)
        assert result['success'] is True
        assert result['result']['success_count'] == 3
        assert "批量啟用爬蟲設定完成" in result['message']
        
        # 檢查是否全部已啟用
        all_crawlers = crawlers_service.get_all_crawlers()
        assert all(crawler.is_active for crawler in all_crawlers['crawlers'])
        
        # 測試部分不存在的 ID
        invalid_ids = [999999, 888888]
        result = crawlers_service.batch_toggle_crawler_status(invalid_ids, False)
        assert result['success'] is False
        assert result['result']['success_count'] == 0
        assert result['result']['fail_count'] == 2
    
    def test_get_filtered_crawlers(self, crawlers_service, sample_crawlers, session):
        """測試根據過濾條件獲取分頁爬蟲列表"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        # 測試按類型過濾
        filter_data = {"crawler_type": "bnext"}
        result = crawlers_service.get_filtered_crawlers(filter_data)
        assert result['success'] is True
        assert result['data']['total'] == 1
        assert result['data']['page'] == 1
        assert len(result['data']['items']) == 1
        
        # 測試按啟用狀態過濾
        filter_data = {"is_active": True}
        result = crawlers_service.get_filtered_crawlers(filter_data)
        assert result['success'] is True
        assert result['data']['total'] == 2
        assert len(result['data']['items']) == 2
        
        # 測試複合條件過濾
        filter_data = {"is_active": True, "crawler_type": "bnext"}
        result = crawlers_service.get_filtered_crawlers(filter_data)
        assert result['success'] is True
        assert result['data']['total'] == 1
        assert len(result['data']['items']) == 1
        
        # 測試排序和分頁
        filter_data = {}
        result = crawlers_service.get_filtered_crawlers(
            filter_data, page=1, per_page=2, sort_by="crawler_name", sort_desc=True
        )
        assert result['success'] is True
        assert result['data']['total'] == 3
        assert result['data']['page'] == 1
        assert len(result['data']['items']) == 2
        assert result['data']['has_next'] is True
        
        # 測試不匹配的條件
        filter_data = {"crawler_type": "不存在類型"}
        result = crawlers_service.get_filtered_crawlers(filter_data)
        assert result['success'] is False
        assert "找不到符合條件" in result['message']
        assert result['data']['total'] == 0

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
        """測試空更新資料處理"""
        crawler_id = sample_crawlers[0]["id"]
        empty_update = {}
        with pytest.raises(ValidationError) as exc_info:
            crawlers_service.update_crawler(crawler_id, empty_update)
        assert "必填欄位不可為空" in str(exc_info.value) or "缺少必填欄位" in str(exc_info.value)
    
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
        assert "驗證失敗" in result['message']

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
        original_status = crawlers_service.get_crawler_by_id(valid_id)['crawler'].is_active
        
        # 執行批量操作，預期部分失敗
        result = crawlers_service.batch_toggle_crawler_status(mixed_ids, not original_status)
        
        # 驗證結果
        assert result['success'] is True  # 至少有一個成功
        assert result['result']['success_count'] == 1
        assert result['result']['fail_count'] == 2
        assert invalid_ids[0] in result['result']['failed_ids']
        assert invalid_ids[1] in result['result']['failed_ids']
        
        # 檢查有效 ID 的狀態已變更
        updated_status = crawlers_service.get_crawler_by_id(valid_id)['crawler'].is_active
        assert updated_status != original_status