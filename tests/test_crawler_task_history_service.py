"""測試 CrawlerTaskHistoryService 的功能。

此模組包含對 CrawlerTaskHistoryService 類的所有測試案例，
涵蓋了 CRUD 操作、查詢功能以及錯誤處理等。
"""

# Standard library imports
import logging
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from contextlib import contextmanager
from typing import Dict, Any, List  # 新增 Dict, Any, List

# Third party imports
import pytest
from sqlalchemy.orm import Session  # 保留 Session 用於類型提示

# Local application imports
from src.models.crawler_task_history_model import (
    CrawlerTaskHistory,
    Base,
)  # Base 可能用於 db_manager
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.crawlers_model import Crawlers
from src.models.crawler_task_history_schema import (
    CrawlerTaskHistoryReadSchema,
)  # 引入 ReadSchema
from src.services.crawler_task_history_service import CrawlerTaskHistoryService

# from src.database.database_manager import DatabaseManager # Service 內部使用，測試中不直接引用


# flake8: noqa: F811
# pylint: disable=redefined-outer-name

logger = logging.getLogger(__name__)  # 使用統一的 logger


# 設置測試資料庫管理器
@pytest.fixture(scope="function")
def initialized_db_manager(db_manager_for_test):
    """Fixture that depends on db_manager_for_test, creates tables, and yields the manager."""
    logger.debug("Creating tables for test function (CrawlerTaskHistory)...")
    try:
        # 使用 CrawlerTaskHistory 的 Base 來創建相關表格
        # 確保 Crawlers 和 CrawlerTasks 的 Base 也被包含，如果它們在不同的 Base.metadata
        # 或者假設 db_manager_for_test 會處理所有模型的 Base
        db_manager_for_test.create_tables(Base)  # 假設 Base 包含所有需要的模型
        yield db_manager_for_test
    finally:
        logger.debug(
            "Test function finished, tables might be dropped by manager cleanup or next test setup."
        )
        # db_manager_for_test fixture 會負責清理
        # db_manager_for_test.drop_tables(Base)


@pytest.fixture(scope="function")
def history_service(initialized_db_manager):
    """創建爬蟲任務歷史記錄服務實例，並注入測試用的 db_manager"""
    # Service 初始化時傳入 db_manager
    service = CrawlerTaskHistoryService(db_manager=initialized_db_manager)

    # 模擬事務管理器，使其返回由 initialized_db_manager 控制的 session
    @contextmanager
    def mock_transaction_scope():
        # 使用 initialized_db_manager 的 session_scope 來獲取 session
        with initialized_db_manager.session_scope() as session:
            try:
                yield session
                # 注意：測試中通常不 commit，讓 initialized_db_manager 控制事務
                # session.commit() # 如果需要測試提交行為，則取消註釋
            except Exception:
                # session.rollback() # session_scope 會自動處理回滾
                raise
            # finally: # session_scope 會自動處理關閉
            #     pass

    # 模擬 service 內部使用的 _transaction 方法（或其等效方法）
    # 假設 service 有一個類似 _transaction 的方法來獲取 session
    # 如果 service 直接使用 db_manager.session_scope()，則可能需要 mock db_manager.session_scope
    # 這裡我們保持原來的 patch 目標 '_transaction'，但讓它返回正確管理的 session
    # 為了確保 patch 生效，我們需要一個 mock 對象，它的 __enter__ 返回模擬的 session
    mock_context = MagicMock()
    mock_context.__enter__.side_effect = (
        mock_transaction_scope  # 使用 side_effect 執行我們的 context manager
    )

    # 改為 patch Service 內部使用的 session_scope，這樣更直接
    # with patch.object(service._db_manager, 'session_scope', new=mock_transaction_scope):
    #     yield service

    # 如果 service 確實有一個 self._transaction 的 context manager helper
    with patch.object(service, "_transaction", new=mock_transaction_scope):
        yield service


@pytest.fixture(scope="function")
def sample_data(initialized_db_manager) -> Dict[str, Any]:
    """創建並提交測試用的基礎數據 (Crawler, Task)，返回包含 ID 的字典"""
    crawler_id = None
    task_id = None
    with initialized_db_manager.session_scope() as session:
        # 清理舊數據（如果需要）
        session.query(CrawlerTaskHistory).delete()
        session.query(CrawlerTasks).delete()
        session.query(Crawlers).delete()
        # session.commit() # 在同一事務中完成

        crawler = Crawlers(
            crawler_name="測試爬蟲",
            module_name="test_module",
            base_url="https://test.com",
            is_active=True,
            crawler_type="RSS",
            config_file_name="test_config.json",
        )
        session.add(crawler)
        session.flush()  # 獲取 crawler.id
        crawler_id = crawler.id

        task = CrawlerTasks(
            task_name="測試任務",
            module_name="test_module",
            crawler_id=crawler_id,
            schedule="0 0 * * *",
            is_active=True,
            config={"max_items": 100},
        )
        session.add(task)
        session.flush()  # 獲取 task.id
        task_id = task.id
        session.commit()  # 提交基礎數據
        logger.debug(
            f"Created sample crawler (ID: {crawler_id}) and task (ID: {task_id})"
        )
    return {"crawler_id": crawler_id, "task_id": task_id}


@pytest.fixture(scope="function")
def sample_histories_data(
    initialized_db_manager, sample_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """創建測試用的爬蟲任務歷史記錄資料，返回包含 ID 的字典列表"""
    task_id = sample_data["task_id"]
    now = datetime.now(timezone.utc)
    histories_input_data = [
        {
            "task_id": task_id,
            "start_time": now - timedelta(days=1),
            "end_time": now - timedelta(days=1) + timedelta(hours=1),  # 修正結束時間
            "success": True,
            "message": "執行成功 1",
            "articles_count": 10,
        },
        {
            "task_id": task_id,
            "start_time": now - timedelta(days=2),
            "end_time": now - timedelta(days=2) + timedelta(hours=1),  # 修正結束時間
            "success": False,
            "message": "執行失敗",
            "articles_count": 0,
        },
        {
            "task_id": task_id,
            "start_time": now - timedelta(days=10),
            "end_time": now - timedelta(days=10) + timedelta(hours=1),  # 修正結束時間
            "success": True,
            "message": "執行成功 2",
            "articles_count": 5,
        },
    ]
    # 確保 start_time 是唯一的，方便後續查找
    histories_input_data.sort(key=lambda x: x["start_time"], reverse=True)

    created_history_data = []
    with initialized_db_manager.session_scope() as session:
        histories_objs = [CrawlerTaskHistory(**data) for data in histories_input_data]
        session.add_all(histories_objs)
        session.flush()  # 分配 ID

        # 提取需要的信息到字典中
        for obj in histories_objs:
            created_history_data.append(
                {
                    "id": obj.id,
                    "task_id": obj.task_id,
                    "start_time": obj.start_time,
                    "end_time": obj.end_time,
                    "success": obj.success,
                    "message": obj.message,
                    "articles_count": obj.articles_count,
                    "created_at": obj.created_at,  # 添加創建時間以便排序
                }
            )
        session.commit()  # 提交歷史記錄數據
        logger.debug(
            f"Created {len(created_history_data)} sample histories for task ID: {task_id}"
        )

    # 返回創建的數據字典列表，按 start_time 降序排列
    return sorted(created_history_data, key=lambda h: h["start_time"], reverse=True)


class TestCrawlerTaskHistoryService:
    """測試爬蟲任務歷史記錄服務的核心功能"""

    # --- Get All / Successful / Failed / With Articles / By Date ---
    # 使用 sample_histories_data (字典列表) 作為預期結果的來源
    def test_find_all_histories(
        self,
        history_service: CrawlerTaskHistoryService,
        sample_histories_data: List[Dict[str, Any]],
    ):
        """測試查找所有歷史記錄 (非預覽)"""
        result = history_service.find_all_histories()
        assert result["success"] is True
        assert result["message"] == "獲取所有歷史記錄成功"
        assert isinstance(result["histories"], list)
        assert len(result["histories"]) == len(sample_histories_data)
        assert all(
            isinstance(h, CrawlerTaskHistoryReadSchema) for h in result["histories"]
        )
        returned_ids = sorted([h.id for h in result["histories"]])
        expected_ids = sorted([h["id"] for h in sample_histories_data])
        assert returned_ids == expected_ids

    def test_find_all_histories_preview(
        self,
        history_service: CrawlerTaskHistoryService,
        sample_histories_data: List[Dict[str, Any]],
    ):
        """測試查找所有歷史記錄 (預覽模式)"""
        preview_fields = ["id", "success"]
        result = history_service.find_all_histories(
            is_preview=True, preview_fields=preview_fields
        )
        assert result["success"] is True
        assert result["message"] == "獲取所有歷史記錄成功"
        assert isinstance(result["histories"], list)
        assert len(result["histories"]) == len(sample_histories_data)
        assert all(isinstance(h, dict) for h in result["histories"])
        assert all(set(h.keys()) == set(preview_fields) for h in result["histories"])
        returned_ids = sorted([h["id"] for h in result["histories"]])
        expected_ids = sorted([h["id"] for h in sample_histories_data])
        assert returned_ids == expected_ids

    def test_find_successful_histories(
        self,
        history_service: CrawlerTaskHistoryService,
        sample_histories_data: List[Dict[str, Any]],
    ):
        """測試查找成功的歷史記錄 (非預覽)"""
        result = history_service.find_successful_histories()
        assert result["success"] is True
        assert isinstance(result["histories"], list)
        successful_histories_data = [h for h in sample_histories_data if h["success"]]
        assert len(result["histories"]) == len(successful_histories_data)
        assert all(
            isinstance(h, CrawlerTaskHistoryReadSchema) for h in result["histories"]
        )
        assert all(h.success for h in result["histories"])

    def test_find_successful_histories_preview(
        self,
        history_service: CrawlerTaskHistoryService,
        sample_histories_data: List[Dict[str, Any]],
    ):
        """測試查找成功的歷史記錄 (預覽)"""
        preview_fields = ["id", "message"]
        result = history_service.find_successful_histories(
            is_preview=True, preview_fields=preview_fields
        )
        assert result["success"] is True
        assert isinstance(result["histories"], list)
        successful_histories_data = [h for h in sample_histories_data if h["success"]]
        assert len(result["histories"]) == len(successful_histories_data)
        assert all(isinstance(h, dict) for h in result["histories"])
        assert all(set(h.keys()) == set(preview_fields) for h in result["histories"])

    def test_find_failed_histories(
        self,
        history_service: CrawlerTaskHistoryService,
        sample_histories_data: List[Dict[str, Any]],
    ):
        """測試查找失敗的歷史記錄 (非預覽)"""
        result = history_service.find_failed_histories()
        assert result["success"] is True
        assert isinstance(result["histories"], list)
        failed_histories_data = [h for h in sample_histories_data if not h["success"]]
        assert len(result["histories"]) == len(failed_histories_data)
        assert all(
            isinstance(h, CrawlerTaskHistoryReadSchema) for h in result["histories"]
        )
        assert not any(h.success for h in result["histories"])

    def test_find_failed_histories_preview(
        self,
        history_service: CrawlerTaskHistoryService,
        sample_histories_data: List[Dict[str, Any]],
    ):
        """測試查找失敗的歷史記錄 (預覽)"""
        preview_fields = ["task_id", "message"]
        result = history_service.find_failed_histories(
            is_preview=True, preview_fields=preview_fields
        )
        assert result["success"] is True
        assert isinstance(result["histories"], list)
        failed_histories_data = [h for h in sample_histories_data if not h["success"]]
        assert len(result["histories"]) == len(failed_histories_data)
        assert all(isinstance(h, dict) for h in result["histories"])
        assert all(set(h.keys()) == set(preview_fields) for h in result["histories"])

    def test_find_histories_with_articles(
        self,
        history_service: CrawlerTaskHistoryService,
        sample_histories_data: List[Dict[str, Any]],
    ):
        """測試查找有文章的歷史記錄 (非預覽)"""
        min_articles = 5
        result = history_service.find_histories_with_articles(min_articles=min_articles)
        assert result["success"] is True
        assert isinstance(result["histories"], list)
        expected_histories_data = [
            h for h in sample_histories_data if h["articles_count"] >= min_articles
        ]
        assert len(result["histories"]) == len(expected_histories_data)
        assert all(
            isinstance(h, CrawlerTaskHistoryReadSchema) for h in result["histories"]
        )
        assert all(h.articles_count >= min_articles for h in result["histories"])

    def test_find_histories_with_articles_preview(
        self,
        history_service: CrawlerTaskHistoryService,
        sample_histories_data: List[Dict[str, Any]],
    ):
        """測試查找有文章的歷史記錄 (預覽)"""
        min_articles = 5
        preview_fields = ["id", "articles_count"]
        result = history_service.find_histories_with_articles(
            min_articles=min_articles, is_preview=True, preview_fields=preview_fields
        )
        assert result["success"] is True
        assert isinstance(result["histories"], list)
        expected_histories_data = [
            h for h in sample_histories_data if h["articles_count"] >= min_articles
        ]
        assert len(result["histories"]) == len(expected_histories_data)
        assert all(isinstance(h, dict) for h in result["histories"])
        assert all(set(h.keys()) == set(preview_fields) for h in result["histories"])
        assert all(h["articles_count"] >= min_articles for h in result["histories"])

    def test_find_histories_by_date_range(
        self,
        history_service: CrawlerTaskHistoryService,
        sample_histories_data: List[Dict[str, Any]],
    ):
        """測試根據日期範圍查找歷史記錄 (非預覽)"""
        start_date = datetime.now(timezone.utc) - timedelta(days=3)
        end_date = datetime.now(timezone.utc)
        result = history_service.find_histories_by_date_range(start_date, end_date)
        assert result["success"] is True
        assert isinstance(result["histories"], list)
        expected_histories_data = [
            h
            for h in sample_histories_data
            if start_date <= h["start_time"] <= end_date
        ]
        assert len(result["histories"]) == len(expected_histories_data)
        assert all(
            isinstance(h, CrawlerTaskHistoryReadSchema) for h in result["histories"]
        )

    def test_find_histories_by_date_range_preview(
        self,
        history_service: CrawlerTaskHistoryService,
        sample_histories_data: List[Dict[str, Any]],
    ):
        """測試根據日期範圍查找歷史記錄 (預覽)"""
        start_date = datetime.now(timezone.utc) - timedelta(days=3)
        end_date = datetime.now(timezone.utc)
        preview_fields = ["id", "start_time"]
        result = history_service.find_histories_by_date_range(
            start_date, end_date, is_preview=True, preview_fields=preview_fields
        )
        assert result["success"] is True
        assert isinstance(result["histories"], list)
        expected_histories_data = [
            h
            for h in sample_histories_data
            if start_date <= h["start_time"] <= end_date
        ]
        assert len(result["histories"]) == len(expected_histories_data)
        assert all(isinstance(h, dict) for h in result["histories"])
        assert all(set(h.keys()) == set(preview_fields) for h in result["histories"])

    # --- Specific Getters ---
    def test_get_total_articles_count(
        self,
        history_service: CrawlerTaskHistoryService,
        sample_histories_data: List[Dict[str, Any]],
    ):
        """測試獲取總文章數量"""
        result = history_service.get_total_articles_count()
        assert result["success"] is True
        expected_total = sum(h["articles_count"] for h in sample_histories_data)
        assert result["count"] == expected_total  # 10 + 0 + 5 = 15

    def test_find_latest_history(
        self,
        history_service: CrawlerTaskHistoryService,
        sample_histories_data: List[Dict[str, Any]],
    ):
        """測試查找最新歷史記錄 (非預覽)"""
        # sample_histories_data is already sorted desc by start_time
        task_id = sample_histories_data[0]["task_id"]
        latest_history_data = sample_histories_data[0]
        result = history_service.find_latest_history(task_id)
        assert result["success"] is True
        assert isinstance(result["history"], CrawlerTaskHistoryReadSchema)
        assert result["history"].id == latest_history_data["id"]
        assert result["history"].start_time == latest_history_data["start_time"]

    def test_find_latest_history_preview(
        self,
        history_service: CrawlerTaskHistoryService,
        sample_histories_data: List[Dict[str, Any]],
    ):
        """測試查找最新歷史記錄 (預覽)"""
        task_id = sample_histories_data[0]["task_id"]
        latest_history_data = sample_histories_data[0]
        preview_fields = ["id", "start_time", "success"]
        result = history_service.find_latest_history(
            task_id, is_preview=True, preview_fields=preview_fields
        )
        assert result["success"] is True
        assert isinstance(result["history"], dict)
        assert set(result["history"].keys()) == set(preview_fields)
        assert result["history"]["id"] == latest_history_data["id"]
        assert result["history"]["success"] == latest_history_data["success"]

    def test_find_histories_older_than(
        self,
        history_service: CrawlerTaskHistoryService,
        sample_histories_data: List[Dict[str, Any]],
    ):
        """測試查找超過指定天數的歷史記錄 (非預覽)"""
        days_threshold = 5
        result = history_service.find_histories_older_than(days_threshold)
        assert result["success"] is True
        assert isinstance(result["histories"], list)
        threshold_date = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        # Ensure comparison with timezone-aware threshold date
        expected_histories_data = [
            h
            for h in sample_histories_data
            if h["start_time"].replace(tzinfo=timezone.utc) < threshold_date
        ]
        assert len(result["histories"]) == len(expected_histories_data)
        assert all(
            isinstance(h, CrawlerTaskHistoryReadSchema) for h in result["histories"]
        )

    def test_find_histories_older_than_preview(
        self,
        history_service: CrawlerTaskHistoryService,
        sample_histories_data: List[Dict[str, Any]],
    ):
        """測試查找超過指定天數的歷史記錄 (預覽)"""
        days_threshold = 5
        preview_fields = ["id", "start_time"]
        result = history_service.find_histories_older_than(
            days_threshold, is_preview=True, preview_fields=preview_fields
        )
        assert result["success"] is True
        assert isinstance(result["histories"], list)
        threshold_date = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        expected_histories_data = [
            h
            for h in sample_histories_data
            if h["start_time"].replace(tzinfo=timezone.utc) < threshold_date
        ]
        assert len(result["histories"]) == len(expected_histories_data)
        assert all(isinstance(h, dict) for h in result["histories"])
        assert all(set(h.keys()) == set(preview_fields) for h in result["histories"])

    # --- CRUD ---
    # Use sample_data (dict) to get task_id
    def test_create_history(
        self, history_service: CrawlerTaskHistoryService, sample_data: Dict[str, Any]
    ):
        """測試創建歷史記錄"""
        task_id = sample_data["task_id"]
        history_data = {
            "task_id": task_id,
            "start_time": datetime.now(timezone.utc),
            "success": True,
            "articles_count": 7,
            # end_time and message can be omitted, service might set defaults
        }
        result = history_service.create_history(history_data)
        logger.debug(f"Create history result: {result}")
        assert result["success"] is True
        assert result["message"] == "歷史記錄創建成功"
        assert isinstance(result["history"], CrawlerTaskHistoryReadSchema)
        assert result["history"].id is not None
        assert result["history"].task_id == task_id
        assert result["history"].articles_count == 7
        assert result["history"].start_time is not None  # Check if start_time was set

    def test_update_history_status(
        self,
        history_service: CrawlerTaskHistoryService,
        sample_histories_data: List[Dict[str, Any]],
    ):
        """測試更新歷史記錄狀態"""
        history_to_update_data = sample_histories_data[
            0
        ]  # Already sorted desc by start_time
        history_id = history_to_update_data["id"]

        result = history_service.update_history_status(
            history_id=history_id,
            success=False,  # Change status
            message="更新測試狀態",
            articles_count=25,
        )
        logger.debug(f"Update history status result: {result}")
        assert result["success"] is True
        assert result["message"] == "更新歷史記錄狀態成功"
        assert isinstance(result["history"], CrawlerTaskHistoryReadSchema)
        assert result["history"].id == history_id
        assert result["history"].success is False
        assert result["history"].articles_count == 25
        assert result["history"].message == "更新測試狀態"
        assert (
            result["history"].end_time is not None
        )  # end_time should be set by update_history_status

    def test_delete_history(
        self,
        history_service: CrawlerTaskHistoryService,
        sample_histories_data: List[Dict[str, Any]],
        initialized_db_manager,
    ):
        """測試刪除歷史記錄"""
        history_to_delete_data = sample_histories_data[0]
        history_id = history_to_delete_data["id"]
        initial_count = len(sample_histories_data)

        result = history_service.delete_history(history_id)
        logger.debug(f"Delete history result: {result}")
        assert result["success"] is True
        assert (
            result["result"] is True
        )  # Assuming delete_history returns True on success
        assert result["message"] == f"成功刪除歷史記錄，ID={history_id}"

        # Use a new session scope to verify deletion from the database
        with initialized_db_manager.session_scope() as session:
            deleted_history = session.get(CrawlerTaskHistory, history_id)
            assert (
                deleted_history is None
            ), f"History with ID {history_id} should be deleted"

            # Verify count in a separate query within the verification scope
            remaining_count = session.query(CrawlerTaskHistory).count()
            assert remaining_count == initial_count - 1

    def test_delete_old_histories(
        self,
        history_service: CrawlerTaskHistoryService,
        sample_histories_data: List[Dict[str, Any]],
    ):
        """測試刪除舊的歷史記錄"""
        days_threshold = 5
        initial_count = len(sample_histories_data)
        threshold_date = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        # Use data from fixture dict list
        expected_deleted_count = len(
            [
                h
                for h in sample_histories_data
                if h["start_time"].replace(tzinfo=timezone.utc) < threshold_date
            ]
        )
        expected_remaining_count = initial_count - expected_deleted_count

        result = history_service.delete_old_histories(days_threshold)
        logger.debug(f"Delete old histories result: {result}")
        assert result["success"] is True
        assert result["resultMsg"]["deleted_count"] == expected_deleted_count
        assert len(result["resultMsg"]["failed_ids"]) == 0

        # 確認記錄已被刪除 (查詢 service)
        all_result = history_service.find_all_histories()
        assert len(all_result["histories"]) == expected_remaining_count

    # --- Paginated ---
    def test_find_histories_paginated(
        self,
        history_service: CrawlerTaskHistoryService,
        sample_histories_data: List[Dict[str, Any]],
    ):
        """測試分頁查找歷史記錄 (非預覽)"""
        page = 1
        per_page = 2
        total_items = len(sample_histories_data)
        result = history_service.find_histories_paginated(
            page=page, per_page=per_page, sort_by="start_time", sort_desc=True
        )

        assert result["success"] is True
        assert result["message"] == "分頁獲取歷史記錄成功"
        assert result["resultMsg"] is not None
        paginated_data = result["resultMsg"]

        assert paginated_data["page"] == page
        assert paginated_data["per_page"] == per_page
        assert paginated_data["total"] == total_items
        assert paginated_data["total_pages"] == (total_items + per_page - 1) // per_page
        assert paginated_data.get("has_next") is (page * per_page < total_items)
        assert paginated_data.get("has_prev") is (page > 1)
        assert isinstance(paginated_data["items"], list)
        assert len(paginated_data["items"]) <= per_page
        assert all(
            isinstance(h, CrawlerTaskHistoryReadSchema) for h in paginated_data["items"]
        )

        # sample_histories_data is already sorted desc by start_time
        expected_ids_page1 = [h["id"] for h in sample_histories_data[:per_page]]
        actual_ids_page1 = [item.id for item in paginated_data["items"]]
        assert actual_ids_page1 == expected_ids_page1

    def test_find_histories_paginated_preview(
        self,
        history_service: CrawlerTaskHistoryService,
        sample_histories_data: List[Dict[str, Any]],
    ):
        """測試分頁查找歷史記錄 (預覽)"""
        page = 1
        per_page = 2
        total_items = len(sample_histories_data)
        preview_fields = ["id", "success"]
        result = history_service.find_histories_paginated(
            page=page,
            per_page=per_page,
            is_preview=True,
            preview_fields=preview_fields,
            sort_by="start_time",
            sort_desc=True,
        )

        assert result["success"] is True
        assert result["resultMsg"] is not None
        paginated_data = result["resultMsg"]

        assert paginated_data["page"] == page
        assert paginated_data["per_page"] == per_page
        assert paginated_data["total"] == total_items
        assert paginated_data["total_pages"] == (total_items + per_page - 1) // per_page
        assert paginated_data.get("has_next") is (page * per_page < total_items)
        assert paginated_data.get("has_prev") is (page > 1)
        assert isinstance(paginated_data["items"], list)
        assert len(paginated_data["items"]) <= per_page
        assert all(isinstance(h, dict) for h in paginated_data["items"])
        assert all(
            set(h.keys()) == set(preview_fields) for h in paginated_data["items"]
        )

        # Verify ID order based on sorted fixture data
        expected_ids_sorted = [h["id"] for h in sample_histories_data]  # Already sorted
        assert [item["id"] for item in paginated_data["items"]] == expected_ids_sorted[
            :per_page
        ]

    # --- Error Handling ---
    def test_error_handling(self, history_service: CrawlerTaskHistoryService):
        """測試錯誤處理"""
        # 測試更新不存在的歷史記錄
        result_update = history_service.update_history_status(
            history_id=999999, success=True
        )
        assert result_update["success"] is False
        assert "不存在" in result_update["message"]

        # 測試刪除不存在的歷史記錄
        result_delete = history_service.delete_history(999999)
        assert result_delete["success"] is False
        # delete_history 內部 repository 返回 False，service 層應包裝消息
        assert (
            "不存在" in result_delete["message"] or "失敗" in result_delete["message"]
        )

        # 測試無效的分頁參數
        result_paginate_neg = history_service.find_histories_paginated(
            page=1, per_page=-1
        )
        assert result_paginate_neg["success"] is False
        assert (
            "分頁獲取歷史記錄失敗: 每頁記錄數必須是正整數"
            in result_paginate_neg["message"]
            or "大於 0" in result_paginate_neg["message"]
        )

        # 測試無效的排序欄位
        result_paginate_sort = history_service.find_histories_paginated(
            page=1, per_page=10, sort_by="invalid_field"
        )
        assert result_paginate_sort["success"] is False
        assert (
            "無效的排序欄位" in result_paginate_sort["message"]
            or "invalid_field" in result_paginate_sort["message"]
        )
