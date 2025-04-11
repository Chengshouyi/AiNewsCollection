import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.database.crawler_task_history_repository import CrawlerTaskHistoryRepository
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawlers_model import Crawlers
from src.models.base_model import Base
from debug.model_info import get_model_info
from src.error.errors import DatabaseOperationError, ValidationError

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
        if transaction.is_active:
            transaction.rollback()
        connection.close()

@pytest.fixture
def crawler_task_history_repo(session):
    return CrawlerTaskHistoryRepository(session, CrawlerTaskHistory)

@pytest.fixture
def sample_crawler(session):
    crawler = Crawlers(
        crawler_name="測試爬蟲",
        base_url="https://example.com",
        is_active=True,
        crawler_type="bnext",
        config_file_name="bnext_config.json"
    )
    session.add(crawler)
    session.commit()
    return crawler

@pytest.fixture
def sample_task(session, sample_crawler):
    task = CrawlerTasks(
        task_name="測試任務",
        crawler_id=sample_crawler.id,
        is_auto=True,
        ai_only=True,
        notes="測試任務"
    )
    session.add(task)
    session.commit()
    return task

@pytest.fixture
def sample_histories(session, sample_task):
    now = datetime.now()
    histories = [
        CrawlerTaskHistory(
            task_id=sample_task.id,
            start_time=now - timedelta(days=3),
            end_time=now - timedelta(days=3, hours=1),
            success=True,
            articles_count=10,
            message="成功抓取"
        ),
        CrawlerTaskHistory(
            task_id=sample_task.id,
            start_time=now - timedelta(days=2),
            end_time=now - timedelta(days=2, hours=1),
            success=False,
            articles_count=0,
            message="抓取失敗"
        ),
        CrawlerTaskHistory(
            task_id=sample_task.id,
            start_time=now - timedelta(days=1),
            end_time=now - timedelta(days=1, hours=1),
            success=True,
            articles_count=15,
            message="成功抓取更多文章"
        )
    ]
    session.add_all(histories)
    session.commit()
    return histories

class TestCrawlerTaskHistoryRepository:
    """CrawlerTaskHistoryRepository 測試類"""
    
    def test_find_by_task_id(self, crawler_task_history_repo, sample_task, sample_histories):
        """測試根據任務ID查詢歷史記錄"""
        histories = crawler_task_history_repo.find_by_task_id(sample_task.id)
        assert len(histories) == 3
        assert all(history.task_id == sample_task.id for history in histories)

    def test_find_successful_histories(self, crawler_task_history_repo, sample_histories):
        """測試查詢成功的歷史記錄"""
        successful_histories = crawler_task_history_repo.find_successful_histories()
        assert len(successful_histories) == 2
        assert all(history.success for history in successful_histories)

    def test_find_failed_histories(self, crawler_task_history_repo, sample_histories):
        """測試查詢失敗的歷史記錄"""
        failed_histories = crawler_task_history_repo.find_failed_histories()
        assert len(failed_histories) == 1
        assert all(not history.success for history in failed_histories)

    def test_find_histories_with_articles(self, crawler_task_history_repo, sample_histories):
        """測試查詢有文章的歷史記錄"""
        histories_with_articles = crawler_task_history_repo.find_histories_with_articles(min_articles=10)
        assert len(histories_with_articles) == 2
        assert all(history.articles_count >= 10 for history in histories_with_articles)

    def test_find_histories_by_date_range(self, crawler_task_history_repo, sample_histories):
        """測試根據日期範圍查詢歷史記錄"""
        earliest_date = min(h.start_time for h in sample_histories)
        latest_date = max(h.start_time for h in sample_histories)
        
        middle_date = earliest_date + (latest_date - earliest_date) / 2
        
        # 測試只有開始日期
        start_only_histories = crawler_task_history_repo.find_histories_by_date_range(
            start_date=middle_date
        )
        assert len(start_only_histories) > 0
        
        # 測試只有結束日期
        end_only_histories = crawler_task_history_repo.find_histories_by_date_range(
            end_date=middle_date
        )
        assert len(end_only_histories) > 0
        
        # 測試完整日期範圍
        histories = crawler_task_history_repo.find_histories_by_date_range(
            start_date=middle_date,
            end_date=latest_date
        )
        
        expected_count = sum(1 for h in sample_histories if middle_date <= h.start_time <= latest_date)
        assert len(histories) == expected_count

    def test_get_total_articles_count(self, crawler_task_history_repo, sample_task, sample_histories):
        """測試獲取總文章數量"""
        # 測試特定任務的文章總數
        task_total_count = crawler_task_history_repo.get_total_articles_count(sample_task.id)
        assert task_total_count == 25  # 10 + 0 + 15
        
        # 測試所有任務的文章總數
        total_count = crawler_task_history_repo.get_total_articles_count()
        assert total_count == 25  # 在此測試中只有一個任務

    def test_get_latest_history(self, crawler_task_history_repo, sample_task, sample_histories):
        """測試獲取最新的歷史記錄（根據開始時間）"""
        latest_history = crawler_task_history_repo.get_latest_history(sample_task.id)
        assert latest_history is not None
        assert latest_history.start_time == max(h.start_time for h in sample_histories)
        
        # 測試獲取不存在任務的最新歷史
        nonexistent_latest = crawler_task_history_repo.get_latest_history(999)
        assert nonexistent_latest is None

    def test_get_latest_by_task_id(self, crawler_task_history_repo, sample_task, sample_histories, monkeypatch):
        """測試獲取指定任務的最新一筆歷史記錄（根據創建時間）"""
        latest_history = crawler_task_history_repo.get_latest_by_task_id(sample_task.id)
        assert latest_history is not None
        
        # 測試獲取不存在任務的最新歷史（使用模擬來避免實際的資料庫錯誤）
        def mock_query_error(*args, **kwargs):
            raise Exception("模擬資料庫查詢錯誤")
        
        monkeypatch.setattr(crawler_task_history_repo.session, "query", mock_query_error)
        
        with pytest.raises(DatabaseOperationError) as excinfo:
            crawler_task_history_repo.get_latest_by_task_id(999)
        assert "獲取最新歷史記錄失敗" in str(excinfo.value)

    def test_get_histories_older_than(self, crawler_task_history_repo, sample_histories):
        """測試獲取超過指定天數的歷史記錄"""
        histories_older_than_2_days = crawler_task_history_repo.get_histories_older_than(2)
        assert len(histories_older_than_2_days) > 0
        for history in histories_older_than_2_days:
            assert (datetime.now(timezone.utc) - history.start_time).days >= 2

    def test_update_history_status(self, crawler_task_history_repo, sample_histories):
        """測試更新歷史記錄狀態"""
        history = sample_histories[1]
        
        # 測試更新部分欄位
        partial_update_result = crawler_task_history_repo.update_history_status(
            history_id=history.id,
            success=True
        )
        assert partial_update_result is True
        
        updated_history = crawler_task_history_repo.get_by_id(history.id)
        assert updated_history.success is True
        assert updated_history.end_time is not None
        
        # 測試完整更新
        complete_update_result = crawler_task_history_repo.update_history_status(
            history_id=history.id,
            success=True,
            message="重試成功",
            articles_count=5
        )
        
        assert complete_update_result is True
        
        updated_history = crawler_task_history_repo.get_by_id(history.id)
        assert updated_history.success is True
        assert updated_history.message == "重試成功"
        assert updated_history.articles_count == 5
        assert updated_history.end_time is not None

    # 新增測試：測試預設值設定
    def test_create_with_default_values(self, crawler_task_history_repo, sample_task):
        """測試創建時設定預設值的邏輯"""
        # 只提供最小必填欄位
        min_data = {
            'task_id': sample_task.id
        }
        
        # 創建並檢查預設值是否如預期
        history = crawler_task_history_repo.create(min_data)
        assert history is not None
        assert history.task_id == sample_task.id
        assert history.start_time is not None  # 預期設置為當前時間
        assert history.success is False  # 預期預設為 False
        assert history.articles_count == 0  # 預期預設為 0
        
        # 驗證存入資料庫
        db_history = crawler_task_history_repo.get_by_id(history.id)
        assert db_history is not None
        assert db_history.success is False
        assert db_history.articles_count == 0

    # 新增測試：測試創建時的驗證錯誤
    def test_create_validation_error(self, crawler_task_history_repo):
        """測試創建時的驗證錯誤處理"""
        # 缺少必填欄位 task_id
        invalid_data = {
            'start_time': datetime.now(timezone.utc),  # 使用 UTC 時區
            'success': True
        }
        
        # 應該拋出 ValidationError
        with pytest.raises(ValidationError) as excinfo:
            crawler_task_history_repo.create(invalid_data)
        
        assert "驗證失敗" in str(excinfo.value)
    
    # 新增測試：測試更新不可變欄位
    def test_update_immutable_fields(self, crawler_task_history_repo, sample_histories):
        """測試更新不可變欄位的處理邏輯"""
        history = sample_histories[0]
        
        # 嘗試更新不可變欄位
        update_data = {
            'task_id': 999,  # 不可變欄位
            'start_time': datetime.now(),  # 不可變欄位
            'message': "新訊息"  # 可變欄位
        }
        
        # 更新操作
        updated = crawler_task_history_repo.update(history.id, update_data)
        assert updated is not None
        
        # 驗證不可變欄位沒有被更新，但可變欄位有被更新
        assert updated.task_id == history.task_id  # task_id 應保持不變
        assert updated.start_time == history.start_time  # start_time 應保持不變
        assert updated.message == "新訊息"  # message 應被更新
    
    # 新增測試：測試更新空資料
    def test_update_empty_data(self, crawler_task_history_repo, sample_histories):
        """測試更新空資料的處理邏輯"""
        history = sample_histories[0]
        
        # 更新空資料
        updated = crawler_task_history_repo.update(history.id, {})
        
        # 應該返回原實體，不做任何更改
        assert updated is not None
        assert updated.id == history.id
        assert updated.message == history.message
        assert updated.success == history.success

class TestModelStructure:
    """測試模型結構"""
    
    def test_crawler_task_history_model_structure(self, session):
        """測試CrawlerTaskHistory模型結構"""
        model_info = get_model_info(CrawlerTaskHistory)
        
        # 測試表名
        assert model_info["table"] == "crawler_task_history"
        
        # 測試主鍵
        assert "id" in model_info["primary_key"]
        
        # 測試外鍵
        foreign_keys = model_info.get("foreign_keys", [])
        # 檢查是否有指向 crawler_tasks 表的外鍵
        has_task_fk = False
        for fk in foreign_keys:
            if "task_id" in str(fk):  # 使用更寬鬆的檢查
                has_task_fk = True
                break
        assert has_task_fk, "應該有指向 crawler_tasks 表的外鍵"
        
        # 測試必填欄位
        required_fields = []
        for field, info in model_info["columns"].items():
            if not info["nullable"] and info["default"] is None:
                required_fields.append(field)
        
        assert "task_id" in required_fields
        assert "id" in required_fields

class TestSpecialCases:
    """測試特殊情況"""
    
    def test_empty_database(self, crawler_task_history_repo):
        """測試空數據庫的情況"""
        assert crawler_task_history_repo.get_all() == []
        assert crawler_task_history_repo.find_successful_histories() == []
        assert crawler_task_history_repo.find_failed_histories() == []

    def test_invalid_operations(self, crawler_task_history_repo):
        """測試無效操作"""
        # 測試不存在的歷史記錄ID
        assert crawler_task_history_repo.update_history_status(
            history_id=999, 
            success=True
        ) is False

class TestErrorHandling:
    """測試錯誤處理"""
    
    def test_repository_exception_handling(self, crawler_task_history_repo, session, monkeypatch):
        """測試資料庫操作異常處理"""
        # 模擬查詢時資料庫異常
        def mock_query_error(*args, **kwargs):
            raise Exception("模擬資料庫查詢錯誤")
        
        monkeypatch.setattr(crawler_task_history_repo.session, "query", mock_query_error)
        
        # 測試各方法的異常處理
        with pytest.raises(DatabaseOperationError) as excinfo:
            crawler_task_history_repo.find_by_task_id(1)
        
        # 修改斷言方式
        assert "查詢任務ID為1的歷史記錄時發生錯誤" in str(excinfo.value)
        
        # 測試 get_latest_by_task_id 的異常處理
        with pytest.raises(DatabaseOperationError) as excinfo:
            crawler_task_history_repo.get_latest_by_task_id(1)
        assert "獲取最新歷史記錄失敗" in str(excinfo.value)
    
    # 新增測試：測試創建時的異常處理
    def test_create_exception_handling(self, crawler_task_history_repo, sample_task, monkeypatch):
        """測試創建時的異常處理"""
        # 模擬內部方法拋出異常
        def mock_create_internal_error(*args, **kwargs):
            raise Exception("模擬創建內部錯誤")
        
        monkeypatch.setattr(crawler_task_history_repo, "_create_internal", mock_create_internal_error)
        
        # 嘗試創建
        with pytest.raises(DatabaseOperationError) as excinfo:
            crawler_task_history_repo.create({'task_id': sample_task.id})
        
        assert "創建 CrawlerTaskHistory 時發生未預期錯誤" in str(excinfo.value)
    
    # 新增測試：測試更新時的異常處理
    def test_update_exception_handling(self, crawler_task_history_repo, sample_histories, monkeypatch):
        """測試更新時的異常處理"""
        history = sample_histories[0]
        
        # 模擬內部方法拋出異常
        def mock_update_internal_error(*args, **kwargs):
            raise Exception("模擬更新內部錯誤")
        
        monkeypatch.setattr(crawler_task_history_repo, "_update_internal", mock_update_internal_error)
        
        # 嘗試更新
        with pytest.raises(DatabaseOperationError) as excinfo:
            crawler_task_history_repo.update(history.id, {'message': '測試更新'})
        
        assert f"更新 CrawlerTaskHistory (ID={history.id}) 時發生未預期錯誤" in str(excinfo.value) 