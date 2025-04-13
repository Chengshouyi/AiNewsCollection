from src.models.crawler_tasks_model import CrawlerTasks, TASK_ARGS_DEFAULT
from src.utils.model_utils import TaskPhase, ScrapeMode
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.base_model import Base

# 改用記憶體資料庫
TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="session")
def engine():
    """創建測試用記憶體資料庫引擎"""
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)

@pytest.fixture
def session(engine):
    """創建測試資料庫會話"""
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()

class TestCrawlerTasksModel:
    """CrawlerTasks 模型的測試類"""
    
    def test_crawler_tasks_creation_with_required_fields(self, session):
        """測試使用必填欄位創建 CrawlerTasks"""
        task = CrawlerTasks(
            task_name="測試任務",
            crawler_id=1,
            is_auto=True,
            task_args=TASK_ARGS_DEFAULT,
            notes="測試任務"
        )
        session.add(task)
        session.commit()
        
        # 測試必填欄位
        assert task.task_name == "測試任務"
        assert task.crawler_id == 1
        assert task.is_auto is True
        assert task.task_args == TASK_ARGS_DEFAULT
        assert task.notes == "測試任務"
        
        # 測試自動生成的欄位
        assert task.created_at is not None
        assert task.updated_at is None
        
        # 測試可選欄位預設值
        assert task.last_run_at is None
        assert task.last_run_success is None
        assert task.last_run_message is None
        assert task.cron_expression is None
        
        # 測試新增欄位的預設值
        assert task.current_phase == TaskPhase.INIT
        assert task.retry_count == 0
    
    def test_default_values(self, session):
        """測試默認值設置"""
        task = CrawlerTasks(
            crawler_id=1,
            task_name="測試預設值任務"
        )
        session.add(task)
        session.commit()
        
        # 測試布林欄位預設值
        assert task.is_auto is True
        assert task.is_active is True
        
        # 測試默認的 task_args
        assert task.task_args['max_pages'] == 10
        assert task.task_args['ai_only'] is False
        assert task.task_args['num_articles'] == 10
        assert task.task_args['min_keywords'] == 10
        assert task.task_args['max_retries'] == 3
        assert task.task_args['retry_delay'] == 2.0
        assert task.task_args['timeout'] == 10
        assert task.task_args['is_test'] is False
        assert task.task_args['save_to_csv'] is False
        assert task.task_args['csv_file_prefix'] == ''
        assert task.task_args['save_to_database'] is True
        assert task.task_args['scrape_mode'] == ScrapeMode.FULL_SCRAPE.value
        assert task.task_args['get_links_by_task_id'] is True
        assert isinstance(task.task_args['article_links'], list)
        assert len(task.task_args['article_links']) == 0
        
        # 測試可選欄位預設值
        assert task.notes is None
        assert task.cron_expression is None
        assert task.last_run_at is None
        assert task.last_run_success is None
        assert task.last_run_message is None
        
        # 測試新增欄位的預設值
        assert task.current_phase == TaskPhase.INIT
        assert task.retry_count == 0
    
    def test_crawler_tasks_repr(self):
        """測試 CrawlerTasks 的 __repr__ 方法"""
        task = CrawlerTasks(
            id=1,
            task_name="測試任務",
            crawler_id=1
        )
        
        expected_repr = "<CrawlerTask(id=1, task_name=測試任務, crawler_id=1)>"
        assert repr(task) == expected_repr
    
    def test_field_updates(self):
        """測試欄位更新"""
        task = CrawlerTasks(crawler_id=1)
        
        # 測試布林欄位更新
        task.is_auto = False
        assert task.is_auto is False
        
        task.is_active = False
        assert task.is_active is False
        
        # 測試 task_args 更新
        task.task_args = {
            "max_pages": 5,
            "num_articles": 20
        }
        assert task.task_args["max_pages"] == 5
        assert task.task_args["num_articles"] == 20
        
        # 測試文字欄位更新
        task.task_name = "更新後的任務名稱"
        task.notes = "更新的備註"
        task.cron_expression = "hourly"
        task.last_run_message = "執行成功"
        assert task.task_name == "更新後的任務名稱"
        assert task.notes == "更新的備註"
        assert task.last_run_message == "執行成功"
        
        # 測試新增欄位更新
        task.current_phase = TaskPhase.CONTENT_SCRAPING
        assert task.current_phase == TaskPhase.CONTENT_SCRAPING
        
        task.max_retries = 5
        assert task.max_retries == 5
        
        task.retry_count = 2
        assert task.retry_count == 2
        
        task.cron_expression = "*/5 * * * *"
        assert task.cron_expression == "*/5 * * * *"

    def test_to_dict(self):
        """測試 to_dict 方法"""
        task = CrawlerTasks(
            id=1,
            task_name="測試任務",
            crawler_id=1,
            notes="測試任務",
            task_args={
                "max_pages": 5,
                "num_articles": 20,
                "scrape_mode": ScrapeMode.LINKS_ONLY.value
            }
        )
        
        task_dict = task.to_dict()
        
        # 驗證所有欄位都在字典中
        expected_keys = {
            'id', 'task_name', 'crawler_id', 'is_auto', 'is_active',  'task_args', 
            'notes', 'created_at', 'updated_at', 'last_run_at', 
            'last_run_success', 'last_run_message', 'cron_expression',
            'current_phase', 'retry_count'
        }
        
        assert set(task_dict.keys()) == expected_keys
        
        # 測試預設值的序列化
        assert task_dict['is_active'] is True
        
        # 測試枚舉值的序列化
        assert task_dict['current_phase'] == TaskPhase.INIT.value
        assert task_dict['task_args']['scrape_mode'] == ScrapeMode.LINKS_ONLY.value
    
    def test_task_phase_transitions(self):
        """測試任務階段轉換"""
        task = CrawlerTasks(crawler_id=1)
        
        # 測試初始階段
        assert task.current_phase == TaskPhase.INIT
        
        # 測試階段轉換
        task.current_phase = TaskPhase.LINK_COLLECTION
        assert task.current_phase == TaskPhase.LINK_COLLECTION
        
        task.current_phase = TaskPhase.CONTENT_SCRAPING
        assert task.current_phase == TaskPhase.CONTENT_SCRAPING
        
        task.current_phase = TaskPhase.COMPLETED
        assert task.current_phase == TaskPhase.COMPLETED
    
    def test_retry_mechanism(self):
        """測試重試機制相關欄位"""
        task = CrawlerTasks(crawler_id=1, max_retries=5)
        
        # 測試初始值
        assert task.max_retries == 5
        assert task.retry_count == 0
        
        # 測試重試計數更新
        task.retry_count += 1
        assert task.retry_count == 1
        
        # 測試重置重試計數
        task.retry_count = 0
        assert task.retry_count == 0

    def test_crawler_tasks_utc_datetime_conversion(self):
        """測試 CrawlerTasks 的 last_run_at 欄位 UTC 時間轉換"""
        from datetime import timedelta
        
        # 測試 1: 傳入無時區資訊的 datetime (naive datetime)
        naive_time = datetime(2025, 3, 28, 12, 0, 0)  # 無時區資訊
        task = CrawlerTasks(
            crawler_id=1,
            last_run_at=naive_time
        )
        if task.last_run_at is not None:
            assert task.last_run_at.tzinfo == timezone.utc  # 確認有 UTC 時區
        assert task.last_run_at == naive_time.replace(tzinfo=timezone.utc)  # 確認值正確

        # 測試 2: 傳入帶非 UTC 時區的 datetime (aware datetime, UTC+8)
        utc_plus_8_time = datetime(2025, 3, 28, 14, 0, 0, tzinfo=timezone(timedelta(hours=8)))
        task.last_run_at = utc_plus_8_time
        expected_utc_time = datetime(2025, 3, 28, 6, 0, 0, tzinfo=timezone.utc)  # UTC+8 轉 UTC
        assert task.last_run_at.tzinfo == timezone.utc  # 確認轉換為 UTC 時區
        assert task.last_run_at == expected_utc_time  # 確認時間正確轉換

        # 測試 3: 傳入已是 UTC 的 datetime，確保不變
        utc_time = datetime(2025, 3, 28, 12, 0, 0, tzinfo=timezone.utc)
        task.last_run_at = utc_time
        assert task.last_run_at == utc_time  # 確認值未被改變

        # 測試 4: 確認非監聽欄位（如 notes）不觸發轉換邏輯
        task.notes = "新備註"
        assert task.last_run_at == utc_time  # last_run_at 不受影響

    def test_scrape_mode_enum(self):
        """測試 ScrapeMode 枚舉值及相關功能"""
        # 測試所有可能的枚舉值
        assert ScrapeMode.LINKS_ONLY.value == "links_only"
        assert ScrapeMode.CONTENT_ONLY.value == "content_only"
        assert ScrapeMode.FULL_SCRAPE.value == "full_scrape"
        
        # 測試在 CrawlerTasks 中設置和獲取 scrape_mode
        task = CrawlerTasks(crawler_id=1)
        assert task.task_args['scrape_mode'] == ScrapeMode.FULL_SCRAPE.value  # 預設值
        
        # 測試更改 scrape_mode
        task.task_args['scrape_mode'] = ScrapeMode.LINKS_ONLY.value
        assert task.task_args['scrape_mode'] == ScrapeMode.LINKS_ONLY.value
        
        task.task_args['scrape_mode'] = ScrapeMode.CONTENT_ONLY.value
        assert task.task_args['scrape_mode'] == ScrapeMode.CONTENT_ONLY.value
        
        # 測試在初始化時指定 scrape_mode
        task2 = CrawlerTasks(
            crawler_id=1, 
            task_args={
                "scrape_mode": ScrapeMode.LINKS_ONLY.value
            }
        )
        assert task2.task_args['scrape_mode'] == ScrapeMode.LINKS_ONLY.value
    
    def test_relationship_fields(self, session):
        """測試關聯關係欄位是否存在"""
        task = CrawlerTasks(
            task_name="測試關係",
            crawler_id=1
        )
        
        # 驗證關聯欄位的存在性
        assert hasattr(task, 'articles')
        assert hasattr(task, 'crawler')
        assert hasattr(task, 'history')
        
        # 驗證關聯欄位的初始值
        assert task.articles == []
        assert task.crawler is None
        assert task.history == []
    
    def test_field_updates_with_scrape_mode(self):
        """測試欄位更新，包括 scrape_mode"""
        task = CrawlerTasks(crawler_id=1)
        
        # 測試 scrape_mode 更新
        task.scrape_mode = ScrapeMode.LINKS_ONLY
        assert task.scrape_mode == ScrapeMode.LINKS_ONLY
        
        task.scrape_mode = ScrapeMode.CONTENT_ONLY
        assert task.scrape_mode == ScrapeMode.CONTENT_ONLY
        
        task.scrape_mode = ScrapeMode.FULL_SCRAPE
        assert task.scrape_mode == ScrapeMode.FULL_SCRAPE

    def test_task_args_default(self):
        """測試 task_args 的預設值"""
        from src.models.crawler_tasks_model import TASK_ARGS_DEFAULT
        
        task = CrawlerTasks(crawler_id=1)
        
        # 測試 task_args 預設值
        assert task.task_args['max_pages'] == TASK_ARGS_DEFAULT['max_pages']
        assert task.task_args['ai_only'] == TASK_ARGS_DEFAULT['ai_only']
        assert task.task_args['num_articles'] == TASK_ARGS_DEFAULT['num_articles']
        assert task.task_args['min_keywords'] == TASK_ARGS_DEFAULT['min_keywords']
        assert task.task_args['max_retries'] == TASK_ARGS_DEFAULT['max_retries']
        assert task.task_args['retry_delay'] == TASK_ARGS_DEFAULT['retry_delay']
        assert task.task_args['timeout'] == TASK_ARGS_DEFAULT['timeout']
        assert task.task_args['is_test'] == TASK_ARGS_DEFAULT['is_test']
        assert task.task_args['save_to_csv'] == TASK_ARGS_DEFAULT['save_to_csv']
        assert task.task_args['csv_file_prefix'] == TASK_ARGS_DEFAULT['csv_file_prefix']
        assert task.task_args['save_to_database'] == TASK_ARGS_DEFAULT['save_to_database']
        assert task.task_args['scrape_mode'] == TASK_ARGS_DEFAULT['scrape_mode']
        assert task.task_args['get_links_by_task_id'] == TASK_ARGS_DEFAULT['get_links_by_task_id']
        assert isinstance(task.task_args['article_links'], list)
        assert len(task.task_args['article_links']) == 0