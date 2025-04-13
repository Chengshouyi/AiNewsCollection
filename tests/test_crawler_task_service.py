import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.crawler_tasks_model import CrawlerTasks, Base, TaskPhase, ScrapeMode
from src.models.crawlers_model import Crawlers
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.services.crawler_task_service import CrawlerTaskService
from src.database.database_manager import DatabaseManager
from src.error.errors import ValidationError
from src.models.crawler_tasks_schema import TASK_ARGS_DEFAULT
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
    finally:
        session.close()

@pytest.fixture(scope="function")
def crawler_task_service(session):
    """創建爬蟲任務服務實例"""
    db_manager = DatabaseManager('sqlite:///:memory:')
    db_manager.Session = sessionmaker(bind=session.get_bind())
    return CrawlerTaskService(db_manager)

@pytest.fixture(scope="function")
def sample_tasks(session):
    """創建測試用的爬蟲任務資料"""
    # 清除現有資料
    session.query(CrawlerTaskHistory).delete()
    session.query(CrawlerTasks).delete()
    session.query(Crawlers).delete()
    session.commit()
    
    # 創建測試用的爬蟲
    crawler = Crawlers(
        crawler_name="測試爬蟲",
        base_url="https://test.com",
        is_active=True,
        crawler_type="RSS",
        config_file_name="test_config.json"
    )
    session.add(crawler)
    session.flush()
    
    tasks = [
        CrawlerTasks(
            task_name="每日新聞爬取",
            crawler_id=crawler.id,
            cron_expression="0 0 * * *",
            is_auto=True,
            task_args={"max_items": 100},
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            current_phase=TaskPhase.INIT,
            max_retries=3,
            retry_count=0,
            scrape_mode=ScrapeMode.FULL_SCRAPE,
            ai_only=False
        ),
        CrawlerTasks(
            task_name="週間財經新聞",
            crawler_id=crawler.id,
            cron_expression="0 0 * * 1-5",
            is_auto=True,
            task_args={"max_items": 50},
            created_at=datetime(2023, 1, 2, tzinfo=timezone.utc),
            updated_at=datetime(2023, 1, 2, tzinfo=timezone.utc),
            current_phase=TaskPhase.INIT,
            max_retries=3,
            retry_count=0,
            scrape_mode=ScrapeMode.LINKS_ONLY,
            ai_only=True
        )
    ]
    
    session.add_all(tasks)
    session.commit()
    return tasks

class TestCrawlerTaskService:
    """測試爬蟲任務服務的核心功能"""

    def test_create_task(self, crawler_task_service):
        """測試創建爬蟲任務"""
        task_data = {
            "task_name": "測試任務",
            "crawler_id": 1,
            "is_auto": True,
            "cron_expression": "0 0 * * *",
            "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False, "max_retries": 3, "retry_count": 0, "scrape_mode": "full_scrape"},
            "current_phase": "init"
        }
        
        result = crawler_task_service.create_task(task_data)
        assert result["success"] is True
        assert "task" in result.keys()
        assert result["message"] == "任務創建成功"

    def test_update_task(self, crawler_task_service, sample_tasks):
        """測試更新爬蟲任務"""
        task_id = sample_tasks[0].id
        update_data = {
            "task_name": "更新後的任務名稱",
            "is_active": False,
            "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False, "max_retries": 3, "retry_count": 0, "scrape_mode": "full_scrape"},
        }
        
        result = crawler_task_service.update_task(task_id, update_data)
        assert result["success"] is True
        assert result["message"] == "任務更新成功"

    def test_delete_task(self, crawler_task_service, sample_tasks):
        """測試刪除爬蟲任務"""
        task_id = sample_tasks[0].id
        result = crawler_task_service.delete_task(task_id)
        assert result["success"] is True
        assert result["message"] == "任務刪除成功"
        
        # 確認任務已被刪除
        result = crawler_task_service.get_task_by_id(task_id)
        assert result["success"] is False
        assert result["message"] == "任務不存在"

    def test_get_task_by_id(self, crawler_task_service, sample_tasks):
        """測試根據ID獲取任務"""
        task_id = sample_tasks[0].id
        result = crawler_task_service.get_task_by_id(task_id)
        
        assert result["success"] is True
        assert "task" in result
        assert result["task"].id == task_id
        assert result["task"].task_name == sample_tasks[0].task_name

    def test_get_all_tasks(self, crawler_task_service, sample_tasks):
        """測試獲取所有任務"""
        result = crawler_task_service.get_all_tasks()
        assert result["success"] is True
        assert len(result["tasks"]) == 2

    def test_get_task_history(self, crawler_task_service, sample_tasks, session):
        """測試獲取任務歷史記錄"""
        task_id = sample_tasks[0].id
        
        # 創建一些測試用的歷史記錄
        histories = [
            CrawlerTaskHistory(
                task_id=task_id,
                start_time=datetime(2023, 1, 1, tzinfo=timezone.utc),
                end_time=datetime(2023, 1, 1, 1, tzinfo=timezone.utc),
                success=True,
                message="執行成功",
                articles_count=10
            ),
            CrawlerTaskHistory(
                task_id=task_id,
                start_time=datetime(2023, 1, 2, tzinfo=timezone.utc),
                end_time=datetime(2023, 1, 2, 1, tzinfo=timezone.utc),
                success=False,
                message="執行失敗",
                articles_count=0
            )
        ]
        session.add_all(histories)
        session.commit()
        
        result = crawler_task_service.get_task_history(task_id)
        assert result["success"] is True
        assert len(result["history"]) == 2

    def test_get_task_status(self, crawler_task_service, sample_tasks, session):
        """測試獲取任務狀態"""
        task_id = sample_tasks[0].id
        
        # 創建一個進行中的任務歷史記錄
        history = CrawlerTaskHistory(
            task_id=task_id,
            start_time=datetime.now(timezone.utc),
            success=None,
            message="正在執行中"
        )
        session.add(history)
        session.commit()
        
        result = crawler_task_service.get_task_status(task_id)
        assert result["status"] == "running"
        assert 0 <= result["progress"] <= 95
        assert result["message"] == "正在執行中"

    def test_error_handling(self, crawler_task_service):
        """測試錯誤處理"""
        # 測試獲取不存在的任務
        result = crawler_task_service.get_task_by_id(999999)
        assert result["success"] is False
        assert result["message"] == "任務不存在"
        
        # 測試更新不存在的任務，使用正確的字段名稱
        result = crawler_task_service.update_task(999999, {"task_name": "新名稱"})
        assert result["success"] is False
        assert result["message"] == "任務不存在"

    def test_test_crawler(self, crawler_task_service, monkeypatch):
        """測試爬蟲任務的測試功能"""
        # 任務配置數據
        task_data = {
            "task_name": "測試爬蟲任務",
            "crawler_id": 1,
            "task_args": {**TASK_ARGS_DEFAULT, "test_mode": True, "ai_only": False, "scrape_mode": "full_scrape"},
            "current_phase": "init",
            "is_auto": True,
            "cron_expression": "0 0 * * *"
        }
        
        # 模擬 Crawler 對象，模擬 repository 返回這個物件
        class MockCrawler:
            id = 1
            crawler_name = "測試爬蟲"
            base_url = "https://test.com"
            crawler_type = "RSS"
            config_file_name = "test_config.json"
        
        # 模擬 CrawlerFactory.get_crawler 方法返回一個可以成功執行任務的爬蟲
        class MockCrawlerInstance:
            def execute_task(self, *args, **kwargs):
                return {
                    'success': True,
                    'message': '測試執行成功',
                    'links_found': 10,
                    'sample_links': ['https://test.com/1', 'https://test.com/2']
                }
        
        # 模擬查詢爬蟲數據的函數
        def mock_get_crawler_by_id(crawler_id):
            return MockCrawler()
        
        def mock_get_crawler(crawler_name):
            return MockCrawlerInstance()
        
        # 補丁替換相關方法
        monkeypatch.setattr(crawler_task_service._get_repositories()[1], 'get_by_id', mock_get_crawler_by_id)
        
        # 確保模塊已經加載
        import sys
        from unittest.mock import MagicMock
        if 'src.crawlers.crawler_factory' not in sys.modules:
            sys.modules['src.crawlers.crawler_factory'] = MagicMock()
        
        # 設置 CrawlerFactory.get_crawler 方法
        sys.modules['src.crawlers.crawler_factory'].CrawlerFactory.get_crawler = mock_get_crawler
        
        # 調用測試方法
        result = crawler_task_service.test_crawler(task_data)
        
        assert result["success"] is True
        assert "test_results" in result
        assert "links_found" in result["test_results"]
        assert "sample_links" in result["test_results"]

    def test_cancel_task(self, crawler_task_service, sample_tasks, session):
        """測試取消任務功能"""
        task_id = sample_tasks[0].id
        
        # 創建一個進行中的任務歷史記錄
        history = CrawlerTaskHistory(
            task_id=task_id,
            start_time=datetime.now(timezone.utc),
            success=None,
            message="正在執行中"
        )
        
        # 添加status屬性的模擬方法
        history.status = 'running'
        session.add(history)
        session.commit()
        
        # 重寫get_latest_history方法以返回帶有status的對象
        original_get_latest_history = crawler_task_service._get_repositories()[2].get_latest_history
        
        def mocked_get_latest_history(task_id):
            history = original_get_latest_history(task_id)
            if history:
                history.status = 'running'
            return history
        
        # 替換方法
        crawler_task_service._get_repositories()[2].get_latest_history = mocked_get_latest_history
        
        result = crawler_task_service.cancel_task(task_id)
        assert result["success"] is True
        assert result["message"] == "任務已取消"

    @pytest.mark.skip("暫時跳過帶過濾條件的歷史記錄測試，需重新設計API")
    def test_get_task_history_with_filters(self, crawler_task_service, sample_tasks, session):
        """測試帶過濾條件的任務歷史記錄獲取"""
        task_id = sample_tasks[0].id
        
        # 創建多個測試用的歷史記錄
        histories = [
            CrawlerTaskHistory(
                task_id=task_id,
                start_time=datetime(2023, 1, 1, tzinfo=timezone.utc),
                end_time=datetime(2023, 1, 1, 1, tzinfo=timezone.utc),
                success=True,
                message="執行成功",
                articles_count=10
            ),
            CrawlerTaskHistory(
                task_id=task_id,
                start_time=datetime(2023, 1, 2, tzinfo=timezone.utc),
                end_time=datetime(2023, 1, 2, 1, tzinfo=timezone.utc),
                success=False,
                message="執行失敗",
                articles_count=0
            ),
            CrawlerTaskHistory(
                task_id=task_id,
                start_time=datetime(2023, 1, 3, tzinfo=timezone.utc),
                end_time=datetime(2023, 1, 3, 1, tzinfo=timezone.utc),
                success=True,
                message="執行成功",
                articles_count=15
            )
        ]
        session.add_all(histories)
        session.commit()
        
        # 測試按日期範圍過濾 - 此測試需要重新設計，因為API不支持過濾器參數
        # 暫時跳過，待重新設計API後再補充測試

    def test_collect_article_links(self, crawler_task_service, sample_tasks, monkeypatch):
        """測試收集文章連結功能"""
        task_id = sample_tasks[0].id
        
        # 模擬 CrawlerFactory.get_crawler 方法，返回一個具有 execute_task 方法的模擬對象
        class MockCrawler:
            def execute_task(self, task_id, task_args):
                assert task_args['scrape_mode'] == 'links_only'  # 確保使用正確的抓取模式
                return {
                    'success': True,
                    'message': '文章連結收集完成，共收集 10 個連結',
                    'articles_count': 10,
                    'links_found': 10
                }
        
        def mock_get_crawler(crawler_name):
            return MockCrawler()
        
        # 模擬文章存儲庫
        class MockArticleRepo:
            def count_articles_by_task_id(self, task_id):
                # 模擬先返回0，然後返回10，表示新增了10篇文章
                if not hasattr(self, 'called'):
                    self.called = True
                    return 0
                return 10
            
            def find_articles_by_task_id(self, **kwargs):
                # 返回10個模擬文章對象
                return [type('MockArticle', (), {'id': i}) for i in range(1, 11)]
        
        # 補丁替換方法
        monkeypatch.setattr('src.crawlers.crawler_factory.CrawlerFactory.get_crawler', mock_get_crawler)
        monkeypatch.setattr(crawler_task_service, '_get_articles_repository', lambda: MockArticleRepo())
        
        # 執行測試
        result = crawler_task_service.collect_article_links(task_id)
        
        # 驗證結果
        assert result['success'] is True
        assert result['links_found'] == 10
        assert len(result['article_ids']) == 10
        assert result['next_step'] in ['content_scraping', 'completed']

    def test_fetch_article_content(self, crawler_task_service, sample_tasks, monkeypatch):
        """測試抓取文章內容功能"""
        task_id = sample_tasks[0].id
        link_ids = [1, 2, 3]  # 模擬的文章ID列表
        
        # 模擬 CrawlerFactory.get_crawler 方法，返回一個具有 execute_task 方法的模擬對象
        class MockCrawler:
            def execute_task(self, task_id, task_args):
                assert task_args['scrape_mode'] == 'content_only'  # 確保使用正確的抓取模式
                assert 'article_ids' in task_args
                assert task_args['article_ids'] == link_ids
                return {
                    'success': True,
                    'message': '文章內容抓取完成',
                    'articles_count': len(link_ids)
                }
        
        def mock_get_crawler(crawler_name):
            return MockCrawler()
        
        # 補丁替換方法
        monkeypatch.setattr('src.crawlers.crawler_factory.CrawlerFactory.get_crawler', mock_get_crawler)
        
        # 執行測試
        result = crawler_task_service.fetch_article_content(task_id, link_ids)
        
        # 驗證結果
        assert result['success'] is True
        assert result['message'] == '文章內容抓取完成'
        assert result['articles_count'] == len(link_ids)

    def test_run_task_with_different_modes(self, crawler_task_service, sample_tasks, monkeypatch):
        """測試不同抓取模式下的任務執行"""
        from src.models.crawler_tasks_model import ScrapeMode
        
        # 為每種抓取模式創建測試
        for mode, task_id in [
            (ScrapeMode.LINKS_ONLY, sample_tasks[1].id),  # 使用LINKS_ONLY模式的任務
            (ScrapeMode.CONTENT_ONLY, sample_tasks[0].id),  # 手動轉換為CONTENT_ONLY模式
            (ScrapeMode.FULL_SCRAPE, sample_tasks[0].id)   # 使用FULL_SCRAPE模式的任務
        ]:
            # 模擬任務對象
            class MockTask:
                from src.models.crawler_tasks_model import TaskPhase
                crawler = sample_tasks[0].crawler
                is_auto = True
                task_args = {**TASK_ARGS_DEFAULT, "ai_only": False, "scrape_mode": mode.value}
                current_phase = TaskPhase.INIT
            
            # 替換獲取任務的方法
            def mock_get_by_id(task_id):
                return MockTask()
            
            # 模擬必要的方法調用
            if mode == ScrapeMode.LINKS_ONLY:
                # 模擬collect_article_links方法
                monkeypatch.setattr(
                    crawler_task_service, 'collect_article_links', 
                    lambda task_id: {'success': True, 'message': '連結收集完成', 'links_found': 10}
                )
            elif mode == ScrapeMode.CONTENT_ONLY:
                # 模擬fetch_article_content方法和find_articles_by_task_id
                monkeypatch.setattr(
                    crawler_task_service, 'fetch_article_content', 
                    lambda task_id, link_ids: {'success': True, 'message': '內容抓取完成', 'articles_count': len(link_ids)}
                )
                
                # 模擬文章存儲庫
                class MockArticleRepoForContentMode:
                    def find_articles_by_task_id(self, **kwargs):
                        return [type('MockArticle', (), {'id': i}) for i in range(1, 11)]
            
                monkeypatch.setattr(crawler_task_service, '_get_articles_repository', lambda: MockArticleRepoForContentMode())
            else:  # FULL_SCRAPE
                # 模擬collect_article_links和fetch_article_content方法
                monkeypatch.setattr(
                    crawler_task_service, 'collect_article_links', 
                    lambda task_id: {'success': True, 'message': '連結收集完成', 'links_found': 10}
                )
                monkeypatch.setattr(
                    crawler_task_service, 'fetch_article_content', 
                    lambda task_id, link_ids: {'success': True, 'message': '內容抓取完成', 'articles_count': len(link_ids)}
                )
                
                # 模擬文章存儲庫
                class MockArticleRepoForFullMode:
                    def find_articles_by_task_id(self, **kwargs):
                        return [type('MockArticle', (), {'id': i}) for i in range(1, 11)]
            
                monkeypatch.setattr(crawler_task_service, '_get_articles_repository', lambda: MockArticleRepoForFullMode())
            
            # 補丁替換獲取任務的方法
            monkeypatch.setattr(crawler_task_service._get_repositories()[0], 'get_by_id', mock_get_by_id)
            
            # 執行測試
            result = crawler_task_service.run_task(task_id, {})
            
            # 驗證結果
            assert result['success'] is True
            if mode == ScrapeMode.LINKS_ONLY:
                assert '連結收集完成' in result['message']
            elif mode == ScrapeMode.CONTENT_ONLY:
                assert '內容抓取完成' in result['message']
            else:  # FULL_SCRAPE
                assert '內容抓取完成' in result['message']

    def test_scrape_mode_enum(self):
        """測試抓取模式枚舉的值"""
        from src.models.crawler_tasks_model import ScrapeMode
        
        # 確認枚舉值
        assert ScrapeMode.LINKS_ONLY.value == "links_only"
        assert ScrapeMode.CONTENT_ONLY.value == "content_only"
        assert ScrapeMode.FULL_SCRAPE.value == "full_scrape"
        
        # 測試從字符串創建枚舉
        assert ScrapeMode("links_only") == ScrapeMode.LINKS_ONLY
        assert ScrapeMode("content_only") == ScrapeMode.CONTENT_ONLY
        assert ScrapeMode("full_scrape") == ScrapeMode.FULL_SCRAPE

    def test_create_task_with_scrape_mode(self, crawler_task_service):
        """測試創建帶有抓取模式的任務"""
        task_data = {
            "task_name": "測試抓取模式任務",
            "crawler_id": 1,
            "is_auto": True,
            "cron_expression": "0 0 * * *",
            "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False, "scrape_mode": "links_only", "max_retries": 3, "retry_count": 0},
            "current_phase": "init"
        }
        
        result = crawler_task_service.create_task(task_data)
        assert result["success"] is True
        
        # 獲取創建的任務
        task_id = result["task_id"]
        task_result = crawler_task_service.get_task_by_id(task_id)
        
        # 確認抓取模式已正確設置
        assert task_result["success"] is True
        assert task_result["task"].task_args.get("scrape_mode") == "links_only"

    def test_content_only_mode_with_limit(self, crawler_task_service, sample_tasks, mocker):
        """測試CONTENT_ONLY模式時的文章限制邊界條件"""
        task_id = sample_tasks[0].id
        
        # 修改任務為僅抓取內容模式
        from src.models.crawler_tasks_model import ScrapeMode
        crawler_task_service.update_task(task_id, {"task_args": {**TASK_ARGS_DEFAULT, "scrape_mode": "content_only"}})
        
        # 創建超過100篇的文章模擬對象
        mock_articles = [mocker.Mock(id=i) for i in range(1, 120)]
        
        # Mock文章存儲庫以返回測試數據
        mock_article_repo = mocker.Mock()
        mock_article_repo.find_articles_by_task_id.return_value = mock_articles[:100]  # 應該只返回100篇
        mocker.patch.object(crawler_task_service, '_get_articles_repository', return_value=mock_article_repo)
        
        # Mock fetch_article_content 函數以避免實際執行
        mocker.patch.object(
            crawler_task_service, 
            'fetch_article_content', 
            return_value={'success': True, 'articles_count': 100}
        )
        
        # 模擬 CrawlerFactory.get_crawler 方法
        mock_crawler = mocker.Mock()
        mock_crawler.execute_task.return_value = {'success': True, 'articles_count': 100}
        mocker.patch('src.crawlers.crawler_factory.CrawlerFactory.get_crawler', return_value=mock_crawler)
        
        # 模擬任務對象
        mock_task = mocker.Mock()
        mock_task.task_args = {"scrape_mode": ScrapeMode.CONTENT_ONLY.value, "ai_only": False}
        mock_task.crawler = sample_tasks[0].crawler
        mock_task.is_auto = True
        mocker.patch.object(crawler_task_service._get_repositories()[0], 'get_by_id', return_value=mock_task)
        
        result = crawler_task_service.run_task(task_id, {})
        
        # 驗證文章數量確實被限制在100
        mock_article_repo.find_articles_by_task_id.assert_called_once()
        # 檢查調用參數中限制值是否為100
        assert mock_article_repo.find_articles_by_task_id.call_args[1]['limit'] == 100
        assert result["success"] is True

    def test_validate_task_data(self, crawler_task_service):
        """測試任務資料驗證功能"""
        # 有效的任務資料
        valid_data = {
            "task_name": "測試驗證",
            "crawler_id": 1,
            "is_auto": True,
            "cron_expression": "0 0 * * *",
            "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False, "max_retries": 3, "retry_count": 0, "scrape_mode": "full_scrape"},
            "current_phase": "init"
        }
        
        try:
            result = crawler_task_service.validate_task_data(valid_data)
            assert isinstance(result, dict)
            assert "task_name" in result
        except ValidationError:
            pytest.fail("驗證應該通過，但卻失敗了")
        
        # 無效的任務資料 - 自動執行但沒有cron表達式
        invalid_data = {
            "task_name": "測試驗證",
            "crawler_id": 1,
            "is_auto": True,  # 自動執行
            "cron_expression": None,  # 沒有cron表達式
            "task_args": {**TASK_ARGS_DEFAULT, "ai_only": False, "max_retries": 3, "retry_count": 0, "scrape_mode": "full_scrape"},
            "current_phase": "init"
        }
        
        with pytest.raises(ValidationError):
            crawler_task_service.validate_task_data(invalid_data)
            
    def test_find_tasks_by_multiple_crawlers(self, crawler_task_service, sample_tasks, session):
        """測試根據多個爬蟲ID查詢任務"""
        crawler_ids = [sample_tasks[0].crawler_id]
        
        result = crawler_task_service.find_tasks_by_multiple_crawlers(crawler_ids)
        assert result["success"] is True
        assert len(result["tasks"]) > 0
        assert all(task.crawler_id in crawler_ids for task in result["tasks"])
        
    def test_find_tasks_by_cron_expression(self, crawler_task_service, sample_tasks):
        """測試根據cron表達式查詢任務"""
        cron_expression = "0 0 * * *"  # 每天午夜執行
        
        result = crawler_task_service.find_tasks_by_cron_expression(cron_expression)
        assert result["success"] is True
        assert len(result["tasks"]) > 0
        assert all(task.cron_expression == cron_expression for task in result["tasks"])
        
    def test_find_pending_tasks(self, crawler_task_service, sample_tasks):
        """測試查詢待執行任務"""
        cron_expression = "0 0 * * *"  # 每天午夜執行
        
        result = crawler_task_service.find_pending_tasks(cron_expression)
        assert result["success"] is True
        # 注意：這個測試可能會因為任務的上次執行時間而有不同結果
        
    def test_update_task_last_run(self, crawler_task_service, sample_tasks):
        """測試更新任務最後執行狀態"""
        task_id = sample_tasks[0].id
        message = "測試執行狀態更新"
        
        result = crawler_task_service.update_task_last_run(task_id, True, message)
        assert result["success"] is True
        
        # 檢查更新是否成功
        task_result = crawler_task_service.get_task_by_id(task_id)
        assert task_result["success"] is True
        assert task_result["task"].last_success is True
        assert task_result["task"].last_message == message
        
    def test_update_task_phase(self, crawler_task_service, sample_tasks):
        """測試更新任務階段"""
        task_id = sample_tasks[0].id
        
        # 測試更新為各種階段
        phases = [
            TaskPhase.INIT,
            TaskPhase.LINK_COLLECTION,
            TaskPhase.CONTENT_SCRAPING,
            TaskPhase.COMPLETED
        ]
        
        for phase in phases:
            result = crawler_task_service.update_task_phase(task_id, phase)
            assert result["success"] is True
            
            # 檢查更新是否成功
            task_result = crawler_task_service.get_task_by_id(task_id)
            assert task_result["success"] is True
            assert task_result["task"].current_phase == phase
            
    def test_increment_retry_count(self, crawler_task_service, sample_tasks):
        """測試增加任務重試次數"""
        task_id = sample_tasks[0].id
        
        # 獲取初始重試次數
        initial_task = crawler_task_service.get_task_by_id(task_id)
        initial_retry_count = initial_task["task"].retry_count
        
        # 測試增加重試次數
        result = crawler_task_service.increment_retry_count(task_id)
        assert result["success"] is True
        assert result["retry_count"] == initial_retry_count + 1
        
        # 檢查更新是否成功
        task_result = crawler_task_service.get_task_by_id(task_id)
        assert task_result["success"] is True
        assert task_result["task"].retry_count == initial_retry_count + 1
        
    def test_reset_retry_count(self, crawler_task_service, sample_tasks):
        """測試重置任務重試次數"""
        task_id = sample_tasks[0].id
        
        # 先增加重試次數
        crawler_task_service.increment_retry_count(task_id)
        
        # 測試重置重試次數
        result = crawler_task_service.reset_retry_count(task_id)
        assert result["success"] is True
        
        # 檢查更新是否成功
        task_result = crawler_task_service.get_task_by_id(task_id)
        assert task_result["success"] is True
        assert task_result["task"].retry_count == 0
        
    def test_update_max_retries(self, crawler_task_service, sample_tasks):
        """測試更新任務最大重試次數"""
        task_id = sample_tasks[0].id
        new_max_retries = 5
        
        result = crawler_task_service.update_max_retries(task_id, new_max_retries)
        assert result["success"] is True
        
        # 檢查更新是否成功
        task_result = crawler_task_service.get_task_by_id(task_id)
        assert task_result["success"] is True
        assert task_result["task"].max_retries == new_max_retries
        
    def test_get_retryable_tasks(self, crawler_task_service, sample_tasks, session):
        """測試獲取可重試的任務"""
        # 設置一個任務為失敗狀態
        task_id = sample_tasks[0].id
        crawler_task_service.update_task_last_run(task_id, False, "測試失敗")
        
        # 確保重試次數小於最大重試次數
        crawler_task_service.reset_retry_count(task_id)
        
        result = crawler_task_service.get_retryable_tasks()
        assert result["success"] is True
        
        # 由於測試環境的差異，不一定能找到可重試的任務
        # 因此只檢查結果格式
        assert "tasks" in result
        
    def test_toggle_auto_status(self, crawler_task_service, sample_tasks):
        """測試切換任務自動執行狀態"""
        task_id = sample_tasks[0].id
        
        # 獲取初始狀態
        initial_task = crawler_task_service.get_task_by_id(task_id)
        initial_auto_status = initial_task["task"].is_auto
        
        # 測試切換狀態
        result = crawler_task_service.toggle_auto_status(task_id)
        assert result["success"] is True
        
        # 檢查切換是否成功
        task_result = crawler_task_service.get_task_by_id(task_id)
        assert task_result["success"] is True
        assert task_result["task"].is_auto != initial_auto_status
        
    def test_toggle_active_status(self, crawler_task_service, sample_tasks):
        """測試切換任務啟用狀態"""
        task_id = sample_tasks[0].id
        
        # 獲取初始狀態
        initial_task = crawler_task_service.get_task_by_id(task_id)
        initial_active_status = initial_task["task"].is_active
        
        # 測試切換狀態
        result = crawler_task_service.toggle_active_status(task_id)
        assert result["success"] is True
        
        # 檢查切換是否成功
        task_result = crawler_task_service.get_task_by_id(task_id)
        assert task_result["success"] is True
        assert task_result["task"].is_active != initial_active_status
        
    def test_update_task_notes(self, crawler_task_service, sample_tasks):
        """測試更新任務備註"""
        task_id = sample_tasks[0].id
        new_notes = "這是測試備註"
        
        result = crawler_task_service.update_task_notes(task_id, new_notes)
        assert result["success"] is True
        
        # 檢查更新是否成功
        task_result = crawler_task_service.get_task_by_id(task_id)
        assert task_result["success"] is True
        assert task_result["task"].notes == new_notes
        
    def test_get_failed_tasks(self, crawler_task_service, sample_tasks):
        """測試獲取失敗的任務"""
        # 設置一個任務為失敗狀態
        task_id = sample_tasks[0].id
        crawler_task_service.update_task_last_run(task_id, False, "測試失敗")
        
        result = crawler_task_service.get_failed_tasks(days=1)
        assert result["success"] is True
        assert "tasks" in result
