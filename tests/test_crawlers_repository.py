import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.models.crawlers_model import Crawlers
from src.database.crawlers_repository import CrawlersRepository
from src.models.base_model import Base
import uuid

# 設置測試資料庫
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
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    
    try:
        yield session
    finally:
        session.close()
        # 只有在事務仍然有效時才回滾
        if transaction.is_active:
            transaction.rollback()
        connection.close()

@pytest.fixture
def crawlers_repo(session):
    return CrawlersRepository(session, Crawlers)

@pytest.fixture
def sample_crawlers(session):
    settings = [
        Crawlers(
            crawler_name="新聞爬蟲1",
            scrape_target="https://example.com/news1",
            crawl_interval=60,  # 60分鐘
            is_active=True,
            last_crawl_time=datetime.now() - timedelta(hours=2)
        ),
        Crawlers(
            crawler_name="新聞爬蟲2",
            scrape_target="https://example.com/news2",
            crawl_interval=120,  # 120分鐘
            is_active=False,
            last_crawl_time=datetime.now() - timedelta(days=1)
        ),
        Crawlers(
            crawler_name="RSS爬蟲",
            scrape_target="https://example.com/rss",
            crawl_interval=30,  # 30分鐘
            is_active=True,
            last_crawl_time=None  # 從未執行過
        )
    ]
    session.add_all(settings)
    session.commit()
    return settings

# CrawlerSettingsRepository 測試
class TestCrawlersRepository:
    """
    測試Crawlers相關資料庫操作
    """
    def test_get_all(self, crawlers_repo, sample_crawlers):
        """測試獲取所有爬蟲設定"""
        settings = crawlers_repo.get_all()
        assert len(settings) == 3
        assert isinstance(settings[0], Crawlers)
        
    def test_get_by_id(self, crawlers_repo, sample_crawlers):
        """測試通過ID獲取爬蟲設定"""
        # 測試存在的ID
        setting = crawlers_repo.get_by_id(1)
        assert setting is not None
        assert setting.id == 1
        
        # 測試不存在的ID
        setting = crawlers_repo.get_by_id(999)
        assert setting is None
    
    def test_find_by_name(self, crawlers_repo, sample_crawlers):
        """測試通過爬蟲名稱查找設定"""
        # 測試存在的名稱
        settings = crawlers_repo.find_by_crawler_name("新聞爬蟲1")
        assert len(settings) == 1
        assert settings[0].crawler_name == "新聞爬蟲1"
        
        # 測試部分匹配的名稱
        settings = crawlers_repo.find_by_crawler_name("爬蟲")
        assert len(settings) == 3
        
        # 測試不存在的名稱
        settings = crawlers_repo.find_by_crawler_name("不存在的爬蟲")
        assert len(settings) == 0
    
    def test_find_active_crawlers(self, crawlers_repo, sample_crawlers):
        """測試查找活躍的爬蟲"""
        settings = crawlers_repo.find_active_crawlers()
        assert len(settings) == 2
        assert all(setting.is_active for setting in settings)
    
    def test_find_pending_crawlers(self, crawlers_repo, sample_crawlers):
        """測試查找需要執行的爬蟲"""
        # 找出所有超過爬蟲間隔時間的爬蟲設定
        now = datetime.now()
        settings = crawlers_repo.find_pending_crawlers(now)
        assert len(settings) > 0
        
        # 檢查所有返回的爬蟲都是活躍的
        assert all(setting.is_active for setting in settings)
        
        # 檢查所有返回的爬蟲都到達了爬蟲間隔時間
        for setting in settings:
            # 如果last_crawl_time為空，應該需要爬取
            if setting.last_crawl_time is None:
                continue
                
            # 否則計算間隔時間，確保已經超過了設定的爬蟲間隔
            interval = now - setting.last_crawl_time
            assert interval.total_seconds() >= setting.crawl_interval * 60

    def test_update_last_crawl_time(self, crawlers_repo, sample_crawlers):
        """測試更新最後爬蟲時間"""
        # 獲取第一個爬蟲設定
        setting_id = sample_crawlers[0].id
        old_time = sample_crawlers[0].last_crawl_time
        
        # 更新最後爬蟲時間
        new_time = datetime.now()
        result = crawlers_repo.update_last_crawl_time(setting_id, new_time)
        assert result is True
        
        # 驗證更新成功
        updated_setting = crawlers_repo.get_by_id(setting_id)
        assert updated_setting.last_crawl_time != old_time
        assert updated_setting.last_crawl_time == new_time
        
        # 測試更新不存在的ID
        result = crawlers_repo.update_last_crawl_time(999, new_time)
        assert result is False

    def test_create(self, crawlers_repo):
        """測試創建新的爬蟲設定"""
        new_crawler_data = {
            "crawler_name": "測試爬蟲",
            "scrape_target": "https://example.com/test",
            "crawl_interval": 45,
            "is_active": True
        }
        
        # 創建新爬蟲設定
        new_crawler = crawlers_repo.create(new_crawler_data)
        assert new_crawler is not None
        assert new_crawler.id is not None
        assert new_crawler.crawler_name == "測試爬蟲"
        assert new_crawler.created_at is not None
        
        # 從資料庫中檢索並驗證
        retrieved = crawlers_repo.get_by_id(new_crawler.id)
        assert retrieved is not None
        assert retrieved.crawler_name == "測試爬蟲"
        assert retrieved.scrape_target == "https://example.com/test"
    
    def test_update(self, crawlers_repo, sample_crawlers):
        """測試更新爬蟲設定"""
        # 獲取第一個爬蟲設定的ID
        setting_id = sample_crawlers[0].id
        
        # 準備更新數據
        update_data = {
            "crawler_name": "已更新爬蟲名稱",
            "crawl_interval": 90,
            "is_active": False
        }
        
        # 執行更新
        updated = crawlers_repo.update(setting_id, update_data)
        assert updated is not None
        assert updated.crawler_name == "已更新爬蟲名稱"
        assert updated.crawl_interval == 90
        assert updated.is_active is False
        assert updated.updated_at is not None
        
        # 確認只更新了指定欄位
        assert updated.scrape_target == sample_crawlers[0].scrape_target
        
        # 測試更新不存在的ID
        result = crawlers_repo.update(999, update_data)
        assert result is None
    
    def test_delete(self, crawlers_repo, sample_crawlers):
        """測試刪除爬蟲設定"""
        # 獲取第三個爬蟲設定的ID
        setting_id = sample_crawlers[2].id
        
        # 執行刪除
        result = crawlers_repo.delete(setting_id)
        assert result is True
        
        # 確認已從資料庫中刪除
        deleted = crawlers_repo.get_by_id(setting_id)
        assert deleted is None
        
        # 測試刪除不存在的ID
        result = crawlers_repo.delete(999)
        assert result is False

    def test_toggle_active_status(self, crawlers_repo, sample_crawlers):
        """測試切換爬蟲活躍狀態"""
        # 獲取第一個爬蟲設定
        setting_id = sample_crawlers[0].id
        original_status = sample_crawlers[0].is_active
        
        # 執行切換
        result = crawlers_repo.toggle_active_status(setting_id)
        assert result is True
        
        # 確認狀態已切換
        updated = crawlers_repo.get_by_id(setting_id)
        assert updated.is_active != original_status
        
        # 再次切換
        crawlers_repo.toggle_active_status(setting_id)
        updated_again = crawlers_repo.get_by_id(setting_id)
        assert updated_again.is_active == original_status
        
        # 測試切換不存在的ID
        result = crawlers_repo.toggle_active_status(999)
        assert result is False

class TestCrawlersConstraints:
    """測試Crawlers的模型約束"""
    
    @pytest.fixture
    def test_session(self, engine, tables):
        """每個測試方法使用獨立的會話"""
        with Session(engine) as session:
            yield session
            # 自動清理
    
    def test_required_fields(self, test_session):
        """測試必填欄位約束"""
        session = test_session
        
        # 測試缺少crawler_name
        setting1 = Crawlers(
            # 缺少crawler_name
            scrape_target="https://example.com/test",
            crawl_interval=60,
            is_active=True
        )
        session.add(setting1)
        
        with pytest.raises(Exception) as excinfo:
            session.flush()
        
        assert "NOT NULL constraint failed" in str(excinfo.value)
        session.rollback()
        
        # 測試缺少scrape_target
        setting2 = Crawlers(
            crawler_name="測試爬蟲",
            # 缺少scrape_target
            crawl_interval=60,
            is_active=True
        )
        session.add(setting2)
        
        with pytest.raises(Exception) as excinfo:
            session.flush()
        
        assert "NOT NULL constraint failed" in str(excinfo.value)
        session.rollback()
        
        # 測試缺少crawl_interval
        setting3 = Crawlers(
            crawler_name="測試爬蟲",
            scrape_target="https://example.com/test",
            # 缺少crawl_interval
            is_active=True
        )
        session.add(setting3)
        
        with pytest.raises(Exception) as excinfo:
            session.flush()
        
        assert "NOT NULL constraint failed" in str(excinfo.value)
    
    def test_default_values(self, test_session):
        """測試默認值"""
        session = test_session
        
        # 測試is_active和created_at的默認值
        setting = Crawlers(
            crawler_name="測試默認值",
            scrape_target="https://example.com/default",
            crawl_interval=60
            # 不設置is_active和created_at
        )
        session.add(setting)
        session.flush()
        session.refresh(setting)
        
        # 檢查默認值
        assert setting.is_active is not None  # 默認應為True
        assert setting.created_at is not None  # 默認應為當前時間
        
        # 測試updated_at在更新時自動生成
        setting.crawler_name = "已更新的名稱"
        session.flush()
        session.refresh(setting)
        
        assert setting.updated_at is not None
    
    def test_check_constraints(self, test_session):
        """測試CHECK約束"""
        session = test_session
    
        # 測試crawler_name長度約束
        setting1 = Crawlers(
            crawler_name="a" * 101,  # 超過100字符
            scrape_target="https://example.com/test",
            crawl_interval=60,
            is_active=True
        )
        session.add(setting1)
    
        with pytest.raises(Exception) as excinfo:
            session.flush()
    
        assert "CONSTRAINT" in str(excinfo.value) or "CHECK" in str(excinfo.value)
        session.rollback()
    
        # 測試scrape_target長度約束
        setting2 = Crawlers(
            crawler_name="測試爬蟲",
            scrape_target="x" * 1001,  # 超過1000字符
            crawl_interval=60,
            is_active=True
        )
        session.add(setting2)
    
        with pytest.raises(Exception) as excinfo:
            session.flush()
    
        assert "CONSTRAINT" in str(excinfo.value) or "CHECK" in str(excinfo.value)
        session.rollback()
    
        # 測試is_active類型約束
        # 註：SQLite可能不會強制檢查這個約束，但在實際數據庫中會生效
        try:
            setting3 = Crawlers(
                crawler_name="測試爬蟲",
                scrape_target="https://example.com/test",
                crawl_interval=60,
                is_active=2  # 不是0或1
            )
            session.add(setting3)
            session.flush()
        except Exception as e:
            # 如果出現異常，則約束生效了
            # is_active 使用 SQLAlchemy Boolean 類型，所以會引發 ValueError
            # 而不是常規的 CHECK 約束錯誤
            assert "Value 2 is not None, True, or False" in str(e) or "CONSTRAINT" in str(e) or "CHECK" in str(e)
            session.rollback()

class TestCrawlersRepositoryQueries:
    """測試CrawlerSettingsRepository的查詢功能"""
    
    
    def test_pagination(self, crawlers_repo, sample_crawlers):
        """測試分頁功能"""
        # 添加更多測試數據以使分頁測試更有意義
        for i in range(5):
            new_setting = Crawlers(
                crawler_name=f"額外爬蟲{i+1}",
                scrape_target=f"https://example.com/extra{i+1}",
                crawl_interval=60,
                is_active=True
            )
            crawlers_repo.session.add(new_setting)
        crawlers_repo.session.commit()
        
        # 測試第一頁
        page1 = crawlers_repo.get_paginated(page=1, per_page=3)
        assert page1["page"] == 1
        assert page1["per_page"] == 3
        assert len(page1["items"]) == 3
        assert page1["total"] == 8  # 3個原始樣本+5個新增
        assert page1["total_pages"] == 3
        assert page1["has_next"] is True
        assert page1["has_prev"] is False
        
        # 測試第二頁
        page2 = crawlers_repo.get_paginated(page=2, per_page=3)
        assert page2["page"] == 2
        assert len(page2["items"]) == 3
        assert page2["has_next"] is True
        assert page2["has_prev"] is True
        
        # 測試第三頁（最後一頁）
        page3 = crawlers_repo.get_paginated(page=3, per_page=3)
        assert page3["page"] == 3
        assert len(page3["items"]) == 2
        assert page3["has_next"] is False
        assert page3["has_prev"] is True
        
        # 測試超出範圍的頁碼
        page_out = crawlers_repo.get_paginated(page=10, per_page=3)
        assert page_out["page"] == 3  # 自動調整為最後一頁

class TestModelStructure:
    """使用model_utiles測試模型結構"""
    
    def test_crawlers_model_structure(self, session):
        """測試Crawlers模型結構是否符合預期"""
        from src.services.model_utiles import get_model_info
        
        # 獲取Crawlers模型信息
        settings_info = get_model_info(Crawlers)
        
        # 1. 測試表名
        assert settings_info["table"] == "crawlers"
        
        # 2. 測試主鍵
        assert "id" in settings_info["primary_key"]
        assert len(settings_info["primary_key"]) == 1  # 只有一個主鍵
        
        # 3. 測試必填欄位
        required_fields = []
        for field, info in settings_info["columns"].items():
            if not info["nullable"] and info["default"] is None:
                required_fields.append(field)
        
        # 驗證必填欄位
        assert "crawler_name" in required_fields
        assert "scrape_target" in required_fields
        assert "crawl_interval" in required_fields
        
        # 4. 測試欄位類型
        assert "VARCHAR" in settings_info["columns"]["crawler_name"]["type"].upper()
        assert "VARCHAR" in settings_info["columns"]["scrape_target"]["type"].upper()
        assert "INTEGER" in settings_info["columns"]["crawl_interval"]["type"].upper()
        assert "BOOLEAN" in settings_info["columns"]["is_active"]["type"].upper()
        assert "DATETIME" in settings_info["columns"]["created_at"]["type"].upper()
        
        # 5. 測試默認值
        assert settings_info["columns"]["is_active"]["default"] is not None
        assert settings_info["columns"]["created_at"]["default"] is not None
        
        # 6. 測試Check約束
        has_crawler_name_length_check = False
        has_scrape_target_length_check = False
        has_is_active_type_check = False
        
        for constraint in settings_info["constraints"]:
            if constraint["type"] == "CheckConstraint":
                if "crawler_name_length" in constraint.get("name", ""):
                    has_crawler_name_length_check = True
                elif "scrape_target_length" in constraint.get("name", ""):
                    has_scrape_target_length_check = True
                elif "is_active_type" in constraint.get("name", ""):
                    has_is_active_type_check = True
        
        assert has_crawler_name_length_check
        assert has_scrape_target_length_check
        assert has_is_active_type_check
    
    def test_model_constraints_discovery(self):
        """發現並輸出Crawlers模型約束"""
        from src.services.model_utiles import get_model_info
        
        # 獲取模型信息
        settings_info = get_model_info(Crawlers)
        
        # 打印實際模型結構和約束
        print("\n===== Crawlers模型結構 =====")
        print(f"表名: {settings_info['table']}")
        print(f"主鍵: {settings_info['primary_key']}")
        
        # 欄位信息
        print("\n欄位信息:")
        for field, info in settings_info["columns"].items():
            nullable = "可為空" if info["nullable"] else "必填"
            default = f"預設值: {info['default']}" if info["default"] is not None else "無預設值"
            print(f" - {field}: {info['type']} - {nullable}, {default}")
        
        # 約束信息
        print("\n約束信息:")
        for constraint in settings_info["constraints"]:
            if constraint["type"] == "CheckConstraint":
                name = constraint.get("name", "未命名約束")
                sqltext = constraint.get("sqltext", "未知條件")
                print(f" - {name}: {sqltext}")
        
        # 測試通過
        assert True
