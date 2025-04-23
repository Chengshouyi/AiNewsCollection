import pytest
from datetime import datetime, timezone
import os
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.crawlers_model import Crawlers
from src.models.base_model import Base
from src.services.crawlers_service import CrawlersService
from src.error.errors import ValidationError, DatabaseOperationError
from src.database.database_manager import DatabaseManager
from src.database.crawlers_repository import CrawlersRepository
from src.models.crawlers_schema import CrawlerReadSchema
import json

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

@pytest.fixture
def valid_config_file():
    """提供有效的配置檔案內容"""
    return {
        "name": "test_crawler",
        "base_url": "https://example.com",
        "list_url_template": "{base_url}/categories/{category}",
        "categories": ["test"],
        "full_categories": ["test"],
        "selectors": {
            "get_article_links": {
                "articles_container": "div.articles",
                "category": "span.category",
                "link": "a.link",
                "title": "h2.title",
                "summary": "div.summary"
            },
            "get_article_contents": {
                "content_container": "div.content",
                "published_date": "span.date",
                "category": "span.category",
                "title": "h1.title",
                "summary": "div.summary",
                "content": "div.article-content"
            }
        }
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
        assert isinstance(created_crawler.updated_at, datetime)
    
    def test_find_all_crawlers(self, crawlers_service, sample_crawlers, session):
        """測試獲取所有爬蟲設定，包括分頁、排序和預覽"""
        # 基本測試
        result = crawlers_service.find_all_crawlers()
        assert result['success'] is True
        assert len(result['crawlers']) == 3
        assert all(isinstance(c, CrawlerReadSchema) for c in result['crawlers'])
        
        # 測試分頁
        result_limit = crawlers_service.find_all_crawlers(limit=2)
        assert result_limit['success'] is True
        assert len(result_limit['crawlers']) == 2
        
        result_offset = crawlers_service.find_all_crawlers(offset=1, limit=1)
        assert result_offset['success'] is True
        assert len(result_offset['crawlers']) == 1
        
        # 測試排序
        result_sort = crawlers_service.find_all_crawlers(sort_by="crawler_name", sort_desc=True)
        assert result_sort['success'] is True
        names = [crawler.crawler_name for crawler in result_sort['crawlers']]
        expected_names = sorted([c['crawler_name'] for c in sample_crawlers], reverse=True)
        assert names == expected_names

        # --- 測試預覽模式 --- 
        preview_fields = ['id', 'crawler_name', 'is_active']
        result_preview = crawlers_service.find_all_crawlers(is_preview=True, preview_fields=preview_fields)
        assert result_preview['success'] is True
        assert len(result_preview['crawlers']) == 3
        # 驗證返回的是字典列表，且只包含指定欄位
        for item in result_preview['crawlers']:
            assert isinstance(item, dict)
            assert set(item.keys()) == set(preview_fields)
            # 驗證字典中的值是否正確 (與 sample_crawlers 對比)
            original = next((c for c in sample_crawlers if c['id'] == item['id']), None)
            assert original is not None
            assert item['crawler_name'] == original['crawler_name']
            assert item['is_active'] == original['is_active']

        # 測試預覽模式 + 分頁 + 排序
        result_preview_paged = crawlers_service.find_all_crawlers(
            is_preview=True, 
            preview_fields=preview_fields,
            limit=1,
            offset=1,
            sort_by='crawler_name',
            sort_desc=False
        )
        assert result_preview_paged['success'] is True
        assert len(result_preview_paged['crawlers']) == 1
        assert isinstance(result_preview_paged['crawlers'][0], dict)
        assert set(result_preview_paged['crawlers'][0].keys()) == set(preview_fields)
        # 驗證是排序後的第二個元素
        expected_sorted_names = sorted([c['crawler_name'] for c in sample_crawlers])
        assert result_preview_paged['crawlers'][0]['crawler_name'] == expected_sorted_names[1]

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
        """測試獲取活動中的爬蟲設定，包括分頁和預覽"""
        # 基本測試
        result = crawlers_service.find_active_crawlers()
        assert result['success'] is True
        assert len(result['crawlers']) == 2 # 預期有 2 個活動的
        assert all(isinstance(c, CrawlerReadSchema) for c in result['crawlers'])
        assert all(crawler.is_active for crawler in result['crawlers'])

        # --- 測試分頁 --- 
        result_limit = crawlers_service.find_active_crawlers(limit=1)
        assert result_limit['success'] is True
        assert len(result_limit['crawlers']) == 1

        result_offset = crawlers_service.find_active_crawlers(offset=1, limit=1)
        assert result_offset['success'] is True
        assert len(result_offset['crawlers']) == 1
        # 驗證偏移後取到的還是活動的
        assert result_offset['crawlers'][0].is_active is True 

        # --- 測試預覽模式 --- 
        preview_fields = ['id', 'base_url']
        result_preview = crawlers_service.find_active_crawlers(is_preview=True, preview_fields=preview_fields)
        assert result_preview['success'] is True
        assert len(result_preview['crawlers']) == 2
        for item in result_preview['crawlers']:
            assert isinstance(item, dict)
            assert set(item.keys()) == set(preview_fields)
            # 驗證 base_url 存在且與 sample_crawlers 一致
            original = next((c for c in sample_crawlers if c['id'] == item['id']), None)
            assert original is not None
            assert item['base_url'] == original['base_url']

    def test_find_crawlers_by_name(self, crawlers_service, sample_crawlers, session):
        """測試根據名稱模糊查詢爬蟲設定，包括分頁、狀態過濾和預覽"""
        # 確保會話中的資料是最新的
        session.expire_all()
    
        # --- 測試 is_active=None (預設，查找所有) --- 
        result_all = crawlers_service.find_crawlers_by_name("爬蟲")
        assert result_all['success'] is True
        assert len(result_all['crawlers']) == 3
        assert all(isinstance(c, CrawlerReadSchema) for c in result_all['crawlers'])
        
        # --- 測試 is_active=True (僅查找活動的) --- 
        result_active = crawlers_service.find_crawlers_by_name("爬蟲", is_active=True)
        assert result_active['success'] is True
        assert len(result_active['crawlers']) == 2
        assert all(crawler.is_active for crawler in result_active['crawlers'])
        
        # --- 測試 is_active=False (僅查找非活動的) --- 
        result_inactive = crawlers_service.find_crawlers_by_name("爬蟲", is_active=False)
        assert result_inactive['success'] is True
        assert len(result_inactive['crawlers']) == 1
        assert not result_inactive['crawlers'][0].is_active

        # --- 測試分頁 --- 
        result_limit = crawlers_service.find_crawlers_by_name("爬蟲", limit=2)
        assert result_limit['success'] is True
        assert len(result_limit['crawlers']) == 2

        result_offset = crawlers_service.find_crawlers_by_name("爬蟲", offset=2, limit=1)
        assert result_offset['success'] is True
        assert len(result_offset['crawlers']) == 1

        # --- 測試預覽模式 --- 
        preview_fields = ['crawler_name', 'crawler_type']
        result_preview = crawlers_service.find_crawlers_by_name("爬蟲", is_preview=True, preview_fields=preview_fields)
        assert result_preview['success'] is True
        assert len(result_preview['crawlers']) == 3
        for item in result_preview['crawlers']:
            assert isinstance(item, dict)
            assert set(item.keys()) == set(preview_fields)
            assert "爬蟲" in item['crawler_name'] # 驗證內容

        # --- 測試不存在的名稱 --- 
        no_crawlers_result = crawlers_service.find_crawlers_by_name("不存在")
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
            "config_file_name": "bnext_crawler_config_updated.json", # 更新配置檔名
            "crawler_type": "bnext"  # 添加 crawler_type
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
        
        # 第二次切換 (Active -> Inactive)
        result = crawlers_service.toggle_crawler_status(crawler_id)
        assert result['success'] is True
        assert result['crawler'] is not None
        assert isinstance(result['crawler'], CrawlerReadSchema) # 檢查類型
        assert result['crawler'].id == crawler_id
        assert result['crawler'].is_active is False # 狀態應恢復為 Inactive
        
        # 測試不存在的爬蟲
        result = crawlers_service.toggle_crawler_status(999999)
        assert result['success'] is False
        assert "不存在" in result['message']
        assert result['crawler'] is None
    
    def test_find_crawlers_by_type(self, crawlers_service, sample_crawlers, session):
        """測試根據爬蟲類型查找爬蟲，包括分頁和預覽"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        # --- 基本測試 --- 
        result = crawlers_service.find_crawlers_by_type("bnext")
        assert result['success'] is True
        assert len(result['crawlers']) == 1
        assert isinstance(result['crawlers'][0], CrawlerReadSchema)
        assert all(crawler.crawler_type == "bnext" for crawler in result['crawlers'])

        # --- 測試分頁 (雖然只有一個結果，但也測試參數傳遞) --- 
        result_limit = crawlers_service.find_crawlers_by_type("bnext", limit=1)
        assert result_limit['success'] is True
        assert len(result_limit['crawlers']) == 1

        result_offset = crawlers_service.find_crawlers_by_type("bnext", offset=1, limit=1)
        assert result_offset['success'] is True
        assert len(result_offset['crawlers']) == 0 # 因為偏移量為 1

        # --- 測試預覽模式 --- 
        preview_fields = ['id', 'config_file_name']
        result_preview = crawlers_service.find_crawlers_by_type("bnext", is_preview=True, preview_fields=preview_fields)
        assert result_preview['success'] is True
        assert len(result_preview['crawlers']) == 1
        assert isinstance(result_preview['crawlers'][0], dict)
        assert set(result_preview['crawlers'][0].keys()) == set(preview_fields)
        assert "bnext" in result_preview['crawlers'][0]['config_file_name']
        
        # --- 測試不存在的類型 --- 
        no_result = crawlers_service.find_crawlers_by_type("不存在類型")
        assert no_result['success'] is True 
        assert f"找不到類型為 不存在類型 的爬蟲設定" in no_result['message']
        assert len(no_result['crawlers']) == 0

    def test_find_crawlers_by_target(self, crawlers_service, sample_crawlers, session):
        """測試根據爬取目標模糊查詢爬蟲，包括分頁和預覽"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        # --- 基本測試 --- 
        result = crawlers_service.find_crawlers_by_target("bnext")
        assert result['success'] is True
        assert len(result['crawlers']) == 1
        assert isinstance(result['crawlers'][0], CrawlerReadSchema)
        assert "bnext" in result['crawlers'][0].base_url
    
        # --- 測試分頁 --- 
        result_limit = crawlers_service.find_crawlers_by_target(".com", limit=2) # 查找包含 .com 的
        assert result_limit['success'] is True
        assert len(result_limit['crawlers']) == 2
    
        result_offset = crawlers_service.find_crawlers_by_target(".com", offset=2, limit=1)
        assert result_offset['success'] is True
        assert len(result_offset['crawlers']) == 0 # 修正斷言：offset=2 應該返回 0 個
    
        # --- 測試預覽模式 --- 
        preview_fields = ['id', 'base_url']
        result_preview = crawlers_service.find_crawlers_by_target("bnext", is_preview=True, preview_fields=preview_fields)
        assert result_preview['success'] is True
        assert len(result_preview['crawlers']) == 1
        assert isinstance(result_preview['crawlers'][0], dict)
        assert set(result_preview['crawlers'][0].keys()) == set(preview_fields)
        assert "bnext" in result_preview['crawlers'][0]['base_url']
        
        # --- 測試不存在的目標 --- 
        no_result = crawlers_service.find_crawlers_by_target("不存在網址")
        assert no_result['success'] is True 
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
            "config_file_name": "test_config_updated.json",
            "crawler_type": "bnext"  # 添加 crawler_type
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
        all_crawlers_result = crawlers_service.find_all_crawlers()
        assert all(not crawler.is_active for crawler in all_crawlers_result['crawlers'])
        
        # 批量啟用所有爬蟲
        result = crawlers_service.batch_toggle_crawler_status(crawler_ids, True)
        assert result['success'] is True
        assert result['result']['success_count'] == 3
        assert result['result']['fail_count'] == 0 # 應為 0
        assert "批量啟用爬蟲設定完成" in result['message']
        
        # 檢查是否全部已啟用
        all_crawlers_result = crawlers_service.find_all_crawlers()
        assert all(crawler.is_active for crawler in all_crawlers_result['crawlers'])
        
        # 測試部分不存在的 ID (預期部分失敗)
        invalid_ids = [999999, 888888]
        result = crawlers_service.batch_toggle_crawler_status(invalid_ids, False)
        assert result['success'] is False # 因為 success_count 為 0
        assert result['result']['success_count'] == 0
        assert result['result']['fail_count'] == 2
        assert 999999 in result['result']['failed_ids'] # 檢查失敗 ID
        assert 888888 in result['result']['failed_ids']
    
    def test_get_filtered_crawlers(self, crawlers_service, sample_crawlers, session):
        """測試根據過濾條件獲取分頁爬蟲列表，包括預覽"""
        # 確保會話中的資料是最新的
        session.expire_all()
        
        # --- 測試按類型過濾 --- 
        filter_data = {"crawler_type": "bnext"}
        result = crawlers_service.find_filtered_crawlers(filter_data)
        assert result['success'] is True
        assert result['data'] is not None
        paginated_data = result['data'] # 應為 PaginatedCrawlerResponse
        assert paginated_data.total == 1
        assert paginated_data.page == 1
        assert len(paginated_data.items) == 1
        assert isinstance(paginated_data.items[0], CrawlerReadSchema)
        assert paginated_data.items[0].crawler_type == "bnext"
        
        # --- 測試按啟用狀態過濾 --- 
        filter_data = {"is_active": True}
        result = crawlers_service.find_filtered_crawlers(filter_data)
        assert result['success'] is True
        paginated_data = result['data']
        assert paginated_data.total == 2
        assert len(paginated_data.items) == 2
        assert all(isinstance(item, CrawlerReadSchema) for item in paginated_data.items) # 檢查類型
        assert all(item.is_active for item in paginated_data.items)
        
        # --- 測試複合條件過濾 --- 
        filter_data = {"is_active": True, "crawler_type": "bnext"}
        result = crawlers_service.find_filtered_crawlers(filter_data)
        assert result['success'] is True
        paginated_data = result['data']
        assert paginated_data.total == 1
        assert len(paginated_data.items) == 1
        assert paginated_data.items[0].crawler_type == "bnext"
        assert paginated_data.items[0].is_active is True
        
        # --- 測試排序和分頁 --- 
        filter_data = {}
        result_sort = crawlers_service.find_filtered_crawlers(
            filter_data, page=1, per_page=2, sort_by="crawler_name", sort_desc=True
        )
        assert result_sort['success'] is True
        paginated_data_sort = result_sort['data']
        assert paginated_data_sort.total == 3
        assert paginated_data_sort.page == 1
        assert len(paginated_data_sort.items) == 2
        assert paginated_data_sort.has_next is True
        assert paginated_data_sort.has_prev is False
        expected_first_page_names = sorted([c['crawler_name'] for c in sample_crawlers], reverse=True)[:2]
        actual_names = [item.crawler_name for item in paginated_data_sort.items]
        assert actual_names == expected_first_page_names

        # --- 測試預覽模式 --- 
        preview_fields = ['id', 'is_active']
        result_preview = crawlers_service.find_filtered_crawlers(
            filter_criteria={"crawler_type": "technews"}, 
            is_preview=True, 
            preview_fields=preview_fields
        )
        assert result_preview['success'] is True
        assert result_preview['data'] is not None
        paginated_preview = result_preview['data']
        assert paginated_preview.total == 1
        assert len(paginated_preview.items) == 1
        item = paginated_preview.items[0]
        assert isinstance(item, dict)
        assert set(item.keys()) == set(preview_fields)
        assert item['is_active'] is False # technews is inactive

        # --- 測試不匹配的條件 --- 
        filter_data = {"crawler_type": "不存在類型"}
        result_nomatch = crawlers_service.find_filtered_crawlers(filter_data)
        # 服務層對於找不到結果返回 success: False
        assert result_nomatch['success'] is False # 修正斷言：應為 False
        assert "找不到符合條件" in result_nomatch['message']
        assert result_nomatch['data'] is not None # 即使失敗，也應返回分頁結構
        assert result_nomatch['data'].total == 0
        assert len(result_nomatch['data'].items) == 0

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

class TestCrawlersServiceConfigFile:
    """測試爬蟲配置檔案相關功能"""
    
    def test_validate_config_file(self, crawlers_service, valid_config_file):
        """測試配置檔案格式驗證"""
        # 測試有效配置
        assert crawlers_service.validate_config_file(valid_config_file) is True
        
        # 測試缺少必要欄位
        invalid_config = valid_config_file.copy()
        del invalid_config['name']
        assert crawlers_service.validate_config_file(invalid_config) is False
        
        # 測試缺少 selectors
        invalid_config = valid_config_file.copy()
        del invalid_config['selectors']
        assert crawlers_service.validate_config_file(invalid_config) is False
        
        # 測試缺少必要選擇器
        invalid_config = valid_config_file.copy()
        del invalid_config['selectors']['get_article_links']
        assert crawlers_service.validate_config_file(invalid_config) is False
    
    def test_update_crawler_config(self, crawlers_service, sample_crawlers, valid_config_file, tmp_path):
        """測試更新爬蟲配置檔案"""
        # 創建臨時配置檔案
        config_file = tmp_path / "test_config.json"
        config_file.write_text(json.dumps(valid_config_file))
        
        # 獲取一個現有的爬蟲 ID
        crawler_id = sample_crawlers[0]["id"]
        
        # 創建模擬的檔案對象
        mock_file = MagicMock()
        mock_file.filename = "test_config.json"
        mock_file.read.return_value = json.dumps(valid_config_file).encode()
        
        # 準備爬蟲資料
        crawler_data = {
            "crawler_name": "測試爬蟲",
            "base_url": "https://example.com",
            "is_active": True,
            "crawler_type": "test",
            "config_file_name": "test_config.json"
        }
        
        # 測試更新配置
        result = crawlers_service.update_crawler_config(crawler_id, mock_file, crawler_data)
        assert result['success'] is True
        assert result['crawler'] is not None
        assert result['crawler'].config_file_name == "test_config.json"
        
        # 驗證配置檔案是否已保存
        config_path = os.path.join(
            os.path.dirname(__file__), 
            '..', 
            'src', 
            'crawlers', 
            'configs', 
            'test_config.json'
        )
        assert os.path.exists(config_path)
        
        # 驗證配置檔案內容
        with open(config_path, 'r', encoding='utf-8') as f:
            saved_config = json.load(f)
        assert saved_config == valid_config_file
        
        # 清理測試檔案
        os.remove(config_path)
    
    def test_update_crawler_config_invalid_json(self, crawlers_service, sample_crawlers, tmp_path):
        """測試更新無效的 JSON 配置檔案"""
        # 創建無效的 JSON 檔案
        config_file = tmp_path / "invalid_config.json"
        config_file.write_text("invalid json content")
        
        # 獲取一個現有的爬蟲 ID
        crawler_id = sample_crawlers[0]["id"]
        
        # 創建模擬的檔案對象
        mock_file = MagicMock()
        mock_file.filename = "invalid_config.json"
        mock_file.read.return_value = b"invalid json content"
        
        # 準備爬蟲資料
        crawler_data = {
            "crawler_name": "測試爬蟲",
            "base_url": "https://example.com",
            "is_active": True,
            "crawler_type": "test",
            "config_file_name": "invalid_config.json"
        }
        
        # 測試更新無效配置
        result = crawlers_service.update_crawler_config(crawler_id, mock_file, crawler_data)
        assert result['success'] is False
        assert "配置檔案不是有效的 JSON 格式" in result['message']
    
    def test_update_crawler_config_invalid_format(self, crawlers_service, sample_crawlers, tmp_path):
        """測試更新格式不正確的配置檔案"""
        # 創建格式不正確的配置檔案
        invalid_config = {
            "name": "test_crawler",
            "base_url": "https://example.com"
            # 缺少必要欄位
        }
        
        config_file = tmp_path / "invalid_format_config.json"
        config_file.write_text(json.dumps(invalid_config))
        
        # 獲取一個現有的爬蟲 ID
        crawler_id = sample_crawlers[0]["id"]
        
        # 創建模擬的檔案對象
        mock_file = MagicMock()
        mock_file.filename = "invalid_format_config.json"
        mock_file.read.return_value = json.dumps(invalid_config).encode()
        
        # 準備爬蟲資料
        crawler_data = {
            "crawler_name": "測試爬蟲",
            "base_url": "https://example.com",
            "is_active": True,
            "crawler_type": "test",
            "config_file_name": "invalid_format_config.json"
        }
        
        # 測試更新格式不正確的配置
        result = crawlers_service.update_crawler_config(crawler_id, mock_file, crawler_data)
        assert result['success'] is False
        assert "配置檔案格式不正確" in result['message']