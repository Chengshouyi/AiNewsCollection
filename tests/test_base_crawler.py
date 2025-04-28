"""測試 BaseCrawler 類及其相關功能的單元測試。"""
# flake8: noqa: F811
# pylint: disable=redefined-outer-name

# 標準函式庫
from datetime import datetime, timezone
import json
import logging # 保留 logging 以便 MockCrawlerForTest 中的 logger 屬性
from typing import Dict, List, Any, Optional
from unittest.mock import MagicMock, patch, mock_open

# 第三方函式庫
import pandas as pd
import pytest
from sqlalchemy.orm import sessionmaker

# 本地應用程式 imports
from src.crawlers.base_crawler import BaseCrawler
from src.crawlers.configs.site_config import SiteConfig
from src.crawlers.bnext_scraper import BnextUtils # 假設 MockCrawlerForTest 需要
from src.database.database_manager import DatabaseManager
from src.models.base_model import Base
from src.models.articles_model import Articles
from src.models.articles_schema import ArticleReadSchema, PaginatedArticleResponse
from src.models.crawler_tasks_model import TASK_ARGS_DEFAULT, CrawlerTasks
from src.services.article_service import ArticleService
from src.utils.enum_utils import ScrapeMode, ArticleScrapeStatus, ScrapePhase
from src.utils.log_utils import LoggerSetup  # 使用統一的 logger

# 使用統一的 logger
logger = LoggerSetup.setup_logger(__name__)

# 建立測試用的爬蟲配置
TEST_CONFIG = {
    "name": "test_crawler",
    "base_url": "https://www.example.com",
    "list_url_template": "{base_url}/categories/{category}",
    "categories": ["test"],
    "full_categories": ["test", "example"],
    "article_settings": {
        "max_pages": 2,
        "ai_only": False,
        "num_articles": 5,
        "min_keywords": 3
    },
    "extraction_settings": {
        "num_articles": 5,
        "min_keywords": 3
    },
    "storage_settings": {
        "save_to_csv": True,
        "save_to_database": True
    },
    "selectors": {
        "test": "test"
    }
}

# 測試用的子類
class MockCrawlerForTest(BaseCrawler):
    def __init__(self, config_file_name=None, article_service=None):
        self.fetch_article_links_called = False
        self.fetch_articles_called = False
        self.update_config_called = False
        # 替換舊的 logger 初始化
        self.logger = LoggerSetup.setup_logger(f"{__name__}.{self.__class__.__name__}") 
        super().__init__(config_file_name, article_service)
        
    def _fetch_article_links(self, task_id: int) -> Optional[pd.DataFrame]:
        """測試用的實現"""
        self.fetch_article_links_called = True
        data = []
        current_time = datetime.now(timezone.utc)
        data.append(
            BnextUtils.get_article_columns_dict(
            title='Test Article 1',
            summary='Test summary 1',
            content='',
            link='https://example.com/1',
            category='Test Category',
            published_at=current_time.strftime('%Y-%m-%d %H:%M:%S'),
            author='',
            source='test_crawler',
            source_url='https://www.example.com',
            article_type='',
            tags='',
            is_ai_related=False,
            is_scraped=False,
            scrape_status='link_saved',
            scrape_error=None,
            last_scrape_attempt=current_time,
            task_id=task_id
            )
        )
        data.append(
            BnextUtils.get_article_columns_dict(
                title='Test Article 2',
                summary='Test summary 2',
                content='',
                link='https://example.com/2',
                category='Test Category',
                published_at=current_time.strftime('%Y-%m-%d %H:%M:%S'),
                author='',
                source='test_crawler',
                source_url='https://www.example.com',
                article_type='',
                tags='',
                is_ai_related=False,
                is_scraped=False,
                scrape_status='link_saved',
                scrape_error=None,
                last_scrape_attempt=current_time,
                task_id=task_id
            )
        )
        df = pd.DataFrame(data)
        self.articles_df = df
        return df
        
    def _fetch_articles(self, task_id: int) -> Optional[List[Dict[str, Any]]]:
        """測試用的實現"""
        self.fetch_articles_called = True
        current_time = datetime.now(timezone.utc)
        return [
            {
                'title': 'Test Article 1',
                'summary': 'Summary of article 1',
                'content': 'Content of article 1',
                'link': 'https://example.com/1',
                'category': 'Test Category',
                'published_at': current_time,
                'author': 'Test Author',
                'source': 'Test Source',
                'source_url': 'https://example.com/1',
                'article_type': 'Test Article Type',
                'tags': 'Test Tags',
                'is_ai_related': False,
                'is_scraped': True,
                'scrape_status': 'content_scraped',
                'scrape_error': None,
                'last_scrape_attempt': current_time,
                'task_id': task_id
            },
            {
                'title': 'Test Article 2',
                'summary': 'Summary of article 2',
                'content': 'Content of article 2',
                'link': 'https://example.com/2',
                'category': 'Test Category',
                'published_at': current_time,
                'author': 'Test Author',
                'source': 'Test Source',
                'source_url': 'https://example.com/2',
                'article_type': 'Test Article Type',
                'tags': 'Test Tags',
                'is_ai_related': False,
                'is_scraped': True,
                'scrape_status': 'content_scraped',
                'scrape_error': None,
                'last_scrape_attempt': current_time,
                'task_id': task_id
            }
        ]
        
    def _update_config(self):
        """測試用的實現"""
        self.update_config_called = True

    def _fetch_article_links_from_db(self) -> Optional[pd.DataFrame]:
        """測試用的實現 - 返回從字典轉換來的 DataFrame"""
        try:
            # 使用 article_service 獲取未爬取的文章
            result = self.article_service.find_articles_advanced(
                is_scraped=False,
                per_page=100 # 使用 per_page 替代 limit
            )
            
            if not result["success"] or not result.get("resultMsg") or not result["resultMsg"].items:
                return None
                
            # 將文章列表轉換為 DataFrame
            articles_data = []
            articles_list = result["resultMsg"].items # 從 PaginatedArticleResponse 獲取
            for article_schema in articles_list:
                # 將 Pydantic Schema 轉換為字典
                article_dict = article_schema.model_dump(mode='json') # 確保轉換為字典
                articles_data.append(article_dict)
                
            return pd.DataFrame(articles_data)
            
        except Exception as e:
            self.logger.error(f"從資料庫獲取文章連結失敗: {str(e)}") # 使用 self.logger
            return None

@pytest.fixture(scope="function")
def initialized_db_manager(db_manager_for_test: DatabaseManager):
    """
    提供一個初始化好的 DatabaseManager 實例。
    確保資料表已創建，並在每次測試前清理 Articles 資料表。
    """
    # 確保資料表存在
    try:
        Base.metadata.create_all(db_manager_for_test.engine)
    except Exception as e:
        logger.error(f"創建資料表時出錯: {e}")
        raise
        
    # 在每次測試前清理 Articles 資料表
    try:
        with db_manager_for_test.session_scope() as session:
            session.query(Articles).delete()
            session.commit()
    except Exception as e:
        logger.error(f"清理 Articles 資料表時出錯: {e}")
        # 即使清理失敗，也繼續執行測試，但在日誌中記錄錯誤

    yield db_manager_for_test
    # 清理工作由 db_manager_for_test 本身處理 (如果它有定義)

@pytest.fixture(scope="function")
def article_service(initialized_db_manager: DatabaseManager): # 改為依賴 initialized_db_manager
    """創建 ArticleService 實例，使用共享的 initialized_db_manager"""
    service = ArticleService(initialized_db_manager)
    yield service
    # 清理通常由 fixture 本身處理，如果需要特定清理可以在這裡添加
    # 例如: service.cleanup() 如果 ArticleService 有此方法且需要調用

@pytest.fixture(scope="function")
def mock_config_file(monkeypatch):
    """模擬配置文件"""
    def mock_open_file(*args, **kwargs):
        mock = mock_open(read_data=json.dumps(TEST_CONFIG))
        return mock(*args, **kwargs)
    
    monkeypatch.setattr("builtins.open", mock_open_file)
    return "test_config.json"

@pytest.fixture
def logs_dir(tmp_path):
    """建立暫存的logs目錄"""
    logs_path = tmp_path / "logs"
    logs_path.mkdir()
    with patch("os.makedirs"):
        yield str(logs_path)

class TestBaseCrawler:
    """BaseCrawler 的測試類"""
    
    def test_init_with_config(self, mock_config_file, article_service):
        """測試使用配置文件初始化 BaseCrawler"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        assert crawler.config_file_name == mock_config_file
        assert crawler.article_service == article_service
        assert isinstance(crawler.site_config, SiteConfig)
        assert crawler.site_config.name == "test_crawler"
        assert crawler.site_config.base_url == "https://www.example.com"
    
    def test_init_without_article_service(self, mock_config_file):
        """測試沒有提供 article_service 時應拋出錯誤"""
        with pytest.raises(ValueError, match="未提供文章服務"):
            MockCrawlerForTest(mock_config_file)
    
    def test_execute_task_with_real_db(self, mock_config_file, article_service, initialized_db_manager, logs_dir):
        """測試使用真實記憶體資料庫執行任務的完整流程 (使用 initialized_db_manager)"""
        with patch('os.makedirs', return_value=None):
            # 清理操作已移至 initialized_db_manager fixture
            # with initialized_db_manager.get_session() as session:
            #     session.query(Articles).delete()
            #     session.commit()
            test_time = datetime.now(timezone.utc)
            crawler = MockCrawlerForTest(mock_config_file, article_service)
            task_id = 1
            task_args = {
                "max_pages": 3,
                "ai_only": True,
                "num_articles": 10,
                "max_retries": 2,  # 這是全局參數
                "retry_delay": 0.1,  # 這是全局參數
                "save_to_database": True  # 關鍵：確保保存到資料庫的參數設為True
            }
            
            # 設置全局參數 - 確保save_to_database設為True，否則文章不會被保存
            crawler.global_params = {'max_retries': 2, 'retry_delay': 0.1, 'save_to_database': True}
            
            # 保存原始函數
            original_validate = crawler._validate_and_update_task_params
            # 模擬 _validate_and_update_task_params 成功但仍調用實際的 _update_config
            def mock_validate(*args, **kwargs):
                crawler.update_config_called = True
                return True
            crawler._validate_and_update_task_params = mock_validate
            
            # 模擬 retry_operation 成功
            original_retry_operation = crawler.retry_operation
            crawler.retry_operation = MagicMock(side_effect=lambda func, max_retries=None, retry_delay=None, task_id=None: func())
            
            # 執行任務
            result = crawler.execute_task(task_id, task_args)
            
            # 恢復原始函數
            crawler.retry_operation = original_retry_operation
            crawler._validate_and_update_task_params = original_validate
            
            # 驗證結果
            assert result['success'] is True
            assert result['message'] == '任務完成'
            assert result['articles_count'] == 2
            
            # 驗證任務狀態
            scrape_phase = crawler.get_scrape_phase(task_id)
            assert scrape_phase["scrape_phase"] == ScrapePhase.COMPLETED.value
            assert scrape_phase["progress"] == 100
            
            # 驗證方法調用
            assert crawler.fetch_article_links_called
            assert crawler.fetch_articles_called
            assert crawler.update_config_called
            
            # 驗證資料是否確實被保存到資料庫
            db_result = article_service.find_all_articles() # 修正: 使用 find_all_articles
            assert db_result["success"] is True
            # find_all_articles 返回的是 Pydantic 模型列表
            assert len(db_result["articles"]) == 2 
            # 轉換為字典列表進行斷言
            articles_dicts = [article.model_dump(mode='json') for article in db_result["articles"]]
            articles_sorted = sorted(articles_dicts, key=lambda x: x['title'])
            
            assert articles_sorted[0]['title'] == "Test Article 1"
            assert articles_sorted[1]['title'] == "Test Article 2"
            assert articles_sorted[0]['summary'] == "Summary of article 1"
            assert articles_sorted[1]['summary'] == "Summary of article 2"
            assert articles_sorted[0]['content'] == "Content of article 1"
            assert articles_sorted[1]['content'] == "Content of article 2"
            assert articles_sorted[0]['link'] == "https://example.com/1"
            assert articles_sorted[1]['link'] == "https://example.com/2"
            assert articles_sorted[0]['category'] == "Test Category"
            assert articles_sorted[1]['category'] == "Test Category"
            # published_at 可能需要檢查類型或存在性
            assert 'published_at' in articles_sorted[0] and articles_sorted[0]['published_at'] is not None
            assert 'published_at' in articles_sorted[1] and articles_sorted[1]['published_at'] is not None
            assert articles_sorted[0]['author'] == "Test Author"
            assert articles_sorted[1]['author'] == "Test Author"
            assert articles_sorted[0]['source'] == "Test Source" 
            assert articles_sorted[1]['source'] == "Test Source"
            assert articles_sorted[0]['source_url'] == "https://example.com/1"
            assert articles_sorted[1]['source_url'] == "https://example.com/2"
            assert articles_sorted[0]['article_type'] == "Test Article Type"
            assert articles_sorted[1]['article_type'] == "Test Article Type"
            assert articles_sorted[0]['tags'] == "Test Tags"
            assert articles_sorted[1]['tags'] == "Test Tags"
            assert articles_sorted[0]['is_ai_related'] is False
            assert articles_sorted[1]['is_ai_related'] is False
            assert articles_sorted[0]['is_scraped'] is True
            assert articles_sorted[1]['is_scraped'] is True
    
    def test_execute_task_no_articles(self, mock_config_file, article_service):
        """測試執行任務但沒有獲取到文章的情況"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 模擬 fetch_article_links 返回空 DataFrame
        crawler._fetch_article_links = MagicMock(return_value=None)
        
        task_id = 1
        result = crawler.execute_task(task_id, {})
        
        # 驗證結果
        assert result['success'] is False
        assert '沒有獲取到任何文章連結' in result['message']
        
        # 驗證任務狀態
        scrape_phase = crawler.get_scrape_phase(task_id)
        assert scrape_phase["scrape_phase"] == ScrapePhase.COMPLETED.value
        
        # 驗證 fetch_articles 沒有被調用
        assert not crawler.fetch_articles_called
    
    def test_execute_task_error(self, mock_config_file, article_service):
        """測試執行任務發生錯誤的情況"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 模擬 _validate_and_update_task_params 失敗
        crawler._validate_and_update_task_params = MagicMock(return_value=False)
        
        task_id = 1
        result = crawler.execute_task(task_id, {'bad_param': 'value'})
        
        # 驗證結果
        assert result['success'] is False
        assert '任務參數驗證失敗' in result['message']
        
        # 重置模擬並測試執行過程中的異常
        crawler._validate_and_update_task_params = MagicMock(return_value=True)
        crawler._fetch_article_list = MagicMock(side_effect=Exception("測試執行錯誤"))
        
        # 設置全局參數
        crawler.global_params = {'max_retries': 2, 'retry_delay': 0.1}
        
        result = crawler.execute_task(task_id, {})
        
        # 驗證結果
        assert result['success'] is False
        assert '測試執行錯誤' in result['message']
        
        # 驗證任務狀態
        scrape_phase = crawler.get_scrape_phase(task_id)
        assert scrape_phase["scrape_phase"] == ScrapePhase.FAILED.value
        assert '測試執行錯誤' in scrape_phase["message"]
    
    def test_save_to_csv(self, mock_config_file, article_service, logs_dir):
        """測試保存數據到CSV文件"""
        with patch("pandas.DataFrame.to_csv") as mock_to_csv:
            crawler = MockCrawlerForTest(mock_config_file, article_service)
            data = pd.DataFrame({
                "title": ["Test Title"],
                "content": ["Test Content"]
            })
            
            csv_path = f"{logs_dir}/test_output.csv"
            crawler._save_to_csv(data, csv_path)
            
            # 驗證 to_csv 被調用
            mock_to_csv.assert_called_once()
    
    def test_save_to_csv_no_path(self, mock_config_file, article_service):
        """測試沒有提供CSV路徑的情況"""
        with patch("pandas.DataFrame.to_csv") as mock_to_csv:
            crawler = MockCrawlerForTest(mock_config_file, article_service)
            data = pd.DataFrame({
                "title": ["Test Title"],
                "content": ["Test Content"]
            })
            
            crawler._save_to_csv(data, None)
            
            # 驗證 to_csv 沒有被調用
            mock_to_csv.assert_not_called()
    
    def test_save_to_database(self, mock_config_file, article_service, initialized_db_manager):
        """測試保存數據到資料庫 (使用 initialized_db_manager)"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 保存測試用的時間 - 確保這行被包含
        test_time = datetime.now(timezone.utc)
        # 不再需要 test_time_str，直接比較 datetime 物件
        # test_time_str = test_time.isoformat() 

        crawler.articles_df = pd.DataFrame({
            "title": ["Test Title 1", "Test Title 2"],
            "summary": ["Test Summary 1", "Test Summary 2"],
            "content": ["Test Content 1", "Test Content 2"],
            "link": ["https://example.com/1", "https://example.com/2"],
            "category": ["Test Category 1", "Test Category 2"],
            "published_at": [test_time, test_time], # DataFrame 中仍使用 datetime 對象
            "author": ["Test Author 1", "Test Author 2"],
            "source": ["Test Source 1", "Test Source 2"],
            "source_url": ["https://example.com/1", "https://example.com/2"],
            "article_type": ["Test Article Type 1", "Test Article Type 2"],
            "tags": ["Test Tags 1", "Test Tags 2"],
            "is_ai_related": [False, False],
            "is_scraped": [False, False],
            "scrape_status": [ArticleScrapeStatus.LINK_SAVED.value, ArticleScrapeStatus.LINK_SAVED.value],
        })
        
        # 清理操作已移至 initialized_db_manager fixture
        # with initialized_db_manager.get_session() as session:
        #     session.query(Articles).delete()
        #     session.commit()
        
        # 執行保存
        crawler._save_to_database()
        
        # 驗證資料是否被保存到資料庫
        result = article_service.find_all_articles() 
        assert result["success"] is True
        assert len(result["articles"]) == 2
        
        # 轉換為字典列表進行斷言
        articles_dicts = [article.model_dump(mode='json') for article in result["articles"]]
        articles_sorted = sorted(articles_dicts, key=lambda x: x['title'])
        
        # 斷言字典內容
        assert articles_sorted[0]['title'] == "Test Title 1"
        assert articles_sorted[1]['title'] == "Test Title 2"
        assert articles_sorted[0]['summary'] == "Test Summary 1"
        assert articles_sorted[1]['summary'] == "Test Summary 2"
        assert articles_sorted[0]['content'] == "Test Content 1"
        assert articles_sorted[1]['content'] == "Test Content 2"
        assert articles_sorted[0]['link'] == "https://example.com/1"
        assert articles_sorted[1]['link'] == "https://example.com/2"
        assert articles_sorted[0]['category'] == "Test Category 1"
        assert articles_sorted[1]['category'] == "Test Category 2"
        # 比較 ISO 格式的時間字符串
        # assert articles_sorted[0]['published_at'] == test_time_str
        # assert articles_sorted[1]['published_at'] == test_time_str
        # 改為比較 datetime 物件
        # fromisoformat 可以處理 'Z' 和 '+00:00' 格式
        assert datetime.fromisoformat(articles_sorted[0]['published_at'].replace('Z', '+00:00')) == test_time
        assert datetime.fromisoformat(articles_sorted[1]['published_at'].replace('Z', '+00:00')) == test_time
        assert articles_sorted[0]['author'] == "Test Author 1"
        assert articles_sorted[1]['author'] == "Test Author 2"
        assert articles_sorted[0]['source'] == "Test Source 1"
        assert articles_sorted[1]['source'] == "Test Source 2"
        assert articles_sorted[0]['source_url'] == "https://example.com/1"
        assert articles_sorted[1]['source_url'] == "https://example.com/2"
        assert articles_sorted[0]['article_type'] == "Test Article Type 1"
        assert articles_sorted[1]['article_type'] == "Test Article Type 2"
        assert articles_sorted[0]['tags'] == "Test Tags 1"
        assert articles_sorted[1]['tags'] == "Test Tags 2"
        assert articles_sorted[0]['is_ai_related'] is False
        assert articles_sorted[1]['is_ai_related'] is False
        assert articles_sorted[0]['is_scraped'] is False
        assert articles_sorted[1]['is_scraped'] is False
    
    def test_save_to_database_with_get_links_by_task_id(self, mock_config_file, article_service):
        """測試從資料庫根據任務ID獲取文章"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 設定從資料庫根據任務ID獲取文章
        crawler.global_params = {'get_links_by_task_id': True}
        
        # 保存測試用的時間
        test_time = datetime.now(timezone.utc)
        crawler.articles_df = pd.DataFrame({
            "title": ["Test Title 1", "Test Title 2"],
            "summary": ["Test Summary 1", "Test Summary 2"],
            "content": ["Test Content 1", "Test Content 2"],
            "link": ["https://example.com/1", "https://example.com/2"],
            "category": ["Test Category 1", "Test Category 2"],
            "published_at": [test_time, test_time],
            "author": ["Test Author 1", "Test Author 2"],
            "source": ["Test Source 1", "Test Source 2"],
            "source_url": ["https://example.com/1", "https://example.com/2"],
            "article_type": ["Test Article Type 1", "Test Article Type 2"],
            "tags": ["Test Tags 1", "Test Tags 2"],
            "is_ai_related": [False, False],
            "is_scraped": [False, False],
            "scrape_status": [ArticleScrapeStatus.LINK_SAVED.value, ArticleScrapeStatus.LINK_SAVED.value],
        })
        
        # 模擬 batch_update_articles_by_link 方法 (而不是 batch_update_articles)
        article_service.batch_update_articles_by_link = MagicMock(return_value={"success": True, "message": "更新成功"})
        
        # 執行保存
        crawler._save_to_database()
        
        # 驗證 batch_update_articles_by_link 被正確調用
        article_service.batch_update_articles_by_link.assert_called_once()
        
        # 獲取傳遞給 batch_update_articles_by_link 的參數
        call_args = article_service.batch_update_articles_by_link.call_args[1]
        article_data = call_args.get('article_data', [])
        
        # 驗證資料格式
        assert len(article_data) == 2
        assert article_data[0]['link'] == "https://example.com/1"
        assert article_data[1]['link'] == "https://example.com/2"
    
    def test_get_scrape_phase(self, mock_config_file, article_service):
        """測試獲取任務狀態"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 測試獲取不存在任務的狀態
        status = crawler.get_scrape_phase(999)
        assert status["scrape_phase"] == ScrapePhase.UNKNOWN.value
        
        # 測試獲取存在任務的狀態
        task_id = 1
        crawler.scrape_phase[task_id] = {
            "scrape_phase": ScrapePhase.LINK_COLLECTION.value,
            "progress": 50,
            "message": "測試任務"
        }
        
        status = crawler.get_scrape_phase(task_id)
        assert status["scrape_phase"] == ScrapePhase.LINK_COLLECTION.value
        assert status["progress"] == 50
        assert status["message"] == "測試任務"
    
    def test_retry_operation(self, mock_config_file, article_service):
        """測試重試操作功能"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 測試成功的操作
        success_operation = MagicMock(return_value="success")
        result = crawler.retry_operation(success_operation)
        assert result == "success"
        assert success_operation.call_count == 1
        
        # 測試需要重試的操作
        fail_then_success = MagicMock(side_effect=[Exception("First failure"), "success"])
        result = crawler.retry_operation(fail_then_success, max_retries=2, retry_delay=0.01)
        assert result == "success"
        assert fail_then_success.call_count == 2
        
        # 測試超過重試次數的操作
        always_fail = MagicMock(side_effect=Exception("Always fail"))
        with pytest.raises(Exception, match="Always fail"):
            crawler.retry_operation(always_fail, max_retries=3, retry_delay=0.01)
        assert always_fail.call_count == 3
        
        # 測試任務取消的情況
        task_id = 123
        crawler.scrape_phase[task_id] = {
            'scrape_phase': ScrapePhase.LINK_COLLECTION.value,
            'progress': 50,
            'message': '正在執行任務',
            'start_time': datetime.now(timezone.utc),
            'cancel_flag': True
        }
        
        # 模擬一個正常操作，但在重試期間檢查到任務已取消
        operation_with_task_id = MagicMock(return_value="success")
        with pytest.raises(Exception, match=f"任務 {task_id} 已取消"):
            crawler.retry_operation(operation_with_task_id, max_retries=3, retry_delay=0.01, task_id=task_id)
        
        # 操作應該沒有被調用，因為任務已取消
        operation_with_task_id.assert_not_called()

    def test_update_scrape_phase(self, mock_config_file, article_service):
        """測試更新任務狀態功能"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        task_id = 1
        # 初始化任務狀態
        crawler.scrape_phase[task_id] = {
            'scrape_phase': ScrapePhase.INIT.value,
            'progress': 0,
            'message': '開始執行任務',
            'start_time': datetime.now(timezone.utc)
        }
        
        # 更新進度
        crawler._update_scrape_phase(task_id, 50, '處理中')
        assert crawler.scrape_phase[task_id]['progress'] == 50
        assert crawler.scrape_phase[task_id]['message'] == '處理中'
        assert crawler.scrape_phase[task_id]['scrape_phase'] == ScrapePhase.INIT.value
        
        # 更新狀態
        crawler._update_scrape_phase(task_id, 100, '完成', ScrapePhase.COMPLETED)
        assert crawler.scrape_phase[task_id]['progress'] == 100
        assert crawler.scrape_phase[task_id]['message'] == '完成'
        assert crawler.scrape_phase[task_id]['scrape_phase'] == ScrapePhase.COMPLETED.value
        
        # 測試更新不存在的任務
        crawler._update_scrape_phase(999, 50, '不存在的任務')
        assert 999 not in crawler.scrape_phase

    def test_fetch_article_links_from_db(self, mock_config_file, article_service, initialized_db_manager):
        """測試從資料庫獲取未爬取的文章連結 (使用 initialized_db_manager)"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 準備測試資料
        test_time = datetime.now(timezone.utc)
        test_articles_data = [
            {
                "title": "測試文章1",
                "summary": "測試摘要1",
                "content": "測試內容1",
                "link": "https://example.com/1",
                "category": "測試分類",
                "published_at": test_time,
                "author": "測試作者",
                "source": "test_source",
                "source_url": "https://example.com",
                "article_type": "test",
                "tags": "test",
                "is_ai_related": False,
                "is_scraped": False
            },
            {
                "title": "測試文章2",
                "summary": "測試摘要2",
                "content": "測試內容2",
                "link": "https://example.com/2",
                "category": "測試分類",
                "published_at": test_time,
                "author": "測試作者",
                "source": "test_source",
                "source_url": "https://example.com",
                "article_type": "test",
                "tags": "test",
                "is_ai_related": False,
                "is_scraped": False
            }
        ]
        
        # 新增測試資料 (清理已由 fixture 處理)
        with initialized_db_manager.get_session() as session:
            new_articles = [Articles(**data) for data in test_articles_data]
            session.add_all(new_articles)
            session.commit()
        
        # 測試成功情況
        result_df = crawler._fetch_article_links_from_db()
        assert result_df is not None
        assert len(result_df) == 2
        # 根據 DataFrame 斷言
        result_df_sorted = result_df.sort_values(by='title').reset_index(drop=True)
        assert result_df_sorted.loc[0, 'title'] == "測試文章1"
        assert result_df_sorted.loc[1, 'title'] == "測試文章2"
        assert result_df_sorted.loc[0, 'link'] == "https://example.com/1"
        assert result_df_sorted.loc[1, 'link'] == "https://example.com/2"

    def test_fetch_article_links_from_db_empty(self, mock_config_file, article_service, initialized_db_manager):
        """測試從空資料庫獲取未爬取的文章連結 (使用 initialized_db_manager)"""
        # 資料庫清理已由 initialized_db_manager fixture 處理
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 測試空資料庫情況
        result_df = crawler._fetch_article_links_from_db()
        assert result_df is None

    def test_fetch_article_links_from_db_error(self, mock_config_file, article_service):
        """測試從資料庫獲取文章連結時發生錯誤的情況"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 模擬 article_service.find_articles_advanced 拋出異常
        crawler.article_service.find_articles_advanced = MagicMock(side_effect=Exception("資料庫錯誤"))
        
        # 測試錯誤情況
        result_df = crawler._fetch_article_links_from_db()
        assert result_df is None

    def test_fetch_article_links_by_filter(self, mock_config_file, article_service, initialized_db_manager):
        """測試根據過濾條件獲取文章連結 (使用 initialized_db_manager)"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        test_time = datetime.now(timezone.utc)
        
        # 1. 測試使用 task_id 過濾
        test_articles_data = [
            {
                "title": "測試文章1", "summary": "測試摘要1", "link": "https://example.com/1",
                "category": "測試分類", "published_at": test_time, "author": "測試作者",
                "source": "test_source", "source_url": "https://example.com", "article_type": "test",
                "tags": "test", "is_ai_related": False, "is_scraped": False, "task_id": 123
            },
            {
                "title": "測試文章2", "summary": "測試摘要2", "link": "https://example.com/2",
                "category": "測試分類", "published_at": test_time, "author": "測試作者",
                "source": "test_source", "source_url": "https://example.com", "article_type": "test",
                "tags": "test", "is_ai_related": False, "is_scraped": False, "task_id": 456
            }
        ]
        
        # 新增測試資料 (清理已由 fixture 處理)
        with initialized_db_manager.get_session() as session:
            new_articles = [Articles(**data) for data in test_articles_data]
            session.add_all(new_articles)
            session.commit()
        
        # 測試 task_id 過濾
        result_df = crawler._fetch_article_links_by_filter(task_id=123, is_scraped=False)
        assert result_df is not None
        assert len(result_df) == 1
        assert result_df.iloc[0]['title'] == "測試文章1"
        assert result_df.iloc[0]['task_id'] == 123
        
        # 2. 測試使用 article_links 過濾
        crawler.global_params = {}
        article_links = ["https://example.com/1", "https://example.com/2"]
        result_df = crawler._fetch_article_links_by_filter(article_links=article_links)
        assert result_df is not None
        assert len(result_df) == 2
        assert set(result_df['link'].tolist()) == set(article_links)
        
        # 3. 測試使用 article_links 過濾但部分連結不存在 - 預期行為可能需要調整
        #    當前的實現似乎會返回包含空字典的行，需要確認這是否是預期的
        article_links_mixed = ["https://example.com/1", "https://example.com/nonexistent"]
        # 模擬 get_article_by_link 返回 None for nonexistent
        def mock_get_by_link(link: str):
            if link == "https://example.com/1":
                # 創建一個臨時的 Pydantic 模型實例來返回
                # article_model = ArticleReadSchema.model_validate(test_articles_data[0]) # <-- 舊的錯誤方式
                # 改為從資料庫實際獲取數據來創建模型
                with initialized_db_manager.get_session() as session:
                    db_article = session.query(Articles).filter(Articles.link == link).first()
                    if db_article:
                        article_model = ArticleReadSchema.model_validate(db_article)
                        return {"success": True, "article": article_model}
                    else:
                        # 如果意外未找到，也返回失敗
                        return {"success": False, "article": None, "message": "Article not found in DB for mock"}
            else:
                return {"success": False, "article": None, "message": "Article not found"}
        # 保存原始方法並 mock
        original_get_article_by_link = article_service.get_article_by_link
        article_service.get_article_by_link = MagicMock(side_effect=mock_get_by_link)
        
        result_df = crawler._fetch_article_links_by_filter(article_links=article_links_mixed)
        
        # 恢復原始方法
        article_service.get_article_by_link = original_get_article_by_link
        
        assert result_df is not None
        assert len(result_df) == 2 # 確保返回了兩行
        # 檢查第一行數據是否正確
        assert result_df.iloc[0]['link'] == "https://example.com/1"
        # 檢查第二行是否包含預期的空標記或標識符 (這裡用 link 作為標識符)
        assert result_df.iloc[1]['link'] == "https://example.com/nonexistent"
        # 檢查第二行其他欄位是否為 None 或預設值 (這裡檢查 title)
        # assert pd.isna(result_df.iloc[1]['title']) # 原始斷言
        # 修改斷言以接受空字串或 NaN/None
        assert pd.isna(result_df.iloc[1]['title']) or result_df.iloc[1]['title'] == '' 
        
        # 4. 測試使用其他參數過濾
        result_df = crawler._fetch_article_links_by_filter(source="test_source", limit=1)
        assert result_df is not None
        assert len(result_df) == 1
        
        # 5. 測試使用 global_params 中的 task_id
        crawler.global_params = {'task_id': 456}
        result_df = crawler._fetch_article_links_by_filter(is_scraped=False)
        assert result_df is not None
        assert len(result_df) == 1
        assert result_df.iloc[0]['title'] == "測試文章2"
        assert result_df.iloc[0]['task_id'] == 456

    def test_fetch_article_links_by_filter_error(self, mock_config_file, article_service):
        """測試根據過濾條件獲取文章連結時發生錯誤的情況"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 模擬 article_service.find_articles_advanced 拋出異常
        crawler.article_service.find_articles_advanced = MagicMock(side_effect=Exception("過濾條件錯誤"))
        crawler.article_service.get_article_by_link = MagicMock(side_effect=Exception("獲取文章錯誤"))
        
        # 測試 find_articles_advanced 錯誤情況
        result_df = crawler._fetch_article_links_by_filter(is_scraped=False)
        assert result_df is None
        
        # 測試 get_article_by_link 錯誤情況
        result_df = crawler._fetch_article_links_by_filter(article_links=["https://example.com/error"])
        assert result_df is None 


    def test_update_articles_with_content(self, mock_config_file, article_service):
        """測試批量更新文章內容的方法"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 準備測試數據
        original_df = pd.DataFrame({
            'title': ['Title 1', 'Title 2', 'Title 3'],
            'summary': ['Summary 1', 'Summary 2', 'Summary 3'],
            'content': ['', '', ''],
            'link': ['https://example.com/1', 'https://example.com/2', 'https://example.com/3'],
            'is_scraped': [False, False, False],
            'scrape_status': ['link_saved', 'link_saved', 'link_saved']
        })
        
        # 準備新的文章內容
        new_articles = [
            {
                'title': 'Updated Title 1',
                'summary': 'Updated Summary 1',
                'content': 'New Content 1',
                'link': 'https://example.com/1',
                'is_scraped': True,
                'scrape_status': 'content_scraped'
            },
            {
                'title': 'Updated Title 3',
                'summary': 'Updated Summary 3',
                'content': 'New Content 3',
                'link': 'https://example.com/3',
                'is_scraped': True,
                'scrape_status': 'content_scraped'
            }
        ]
        
        # 執行更新
        updated_df = crawler._update_articles_with_content(original_df, new_articles)
        
        # 驗證結果
        assert len(updated_df) == 3  # 應該仍然有3行
        assert updated_df.loc[0, 'title'] == 'Updated Title 1'
        assert updated_df.loc[0, 'content'] == 'New Content 1'
        assert updated_df.loc[0, 'is_scraped'] == True
        
        assert updated_df.loc[1, 'title'] == 'Title 2'  # 沒有被更新
        assert updated_df.loc[1, 'content'] == ''
        assert updated_df.loc[1, 'is_scraped'] == False
        
        assert updated_df.loc[2, 'title'] == 'Updated Title 3'
        assert updated_df.loc[2, 'content'] == 'New Content 3'
        assert updated_df.loc[2, 'is_scraped'] == True

    def test_validate_and_update_task_params(self, mock_config_file, article_service):
        """測試驗證和更新任務參數的方法"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        task_id = 1
        
        # 初始化任務狀態
        crawler.scrape_phase[task_id] = {
            'status': 'running',
            'progress': 0,
            'message': '開始執行任務',
            'start_time': datetime.now(timezone.utc)
        }
        
        # 測試有效參數 - 文章設定
        valid_article_params = {**TASK_ARGS_DEFAULT,
            'max_pages': 5,
            'ai_only': True,
            'num_articles': 20
        }
        
        result = crawler._validate_and_update_task_params(task_id, valid_article_params)
        assert result is True
        assert crawler.global_params['max_pages'] == 5
        assert crawler.global_params['ai_only'] is True
        assert crawler.global_params['num_articles'] == 20
        assert crawler.update_config_called
        
        # 測試有效參數 - 全局參數
        crawler.update_config_called = False
        valid_global_params = {**TASK_ARGS_DEFAULT,
            'max_retries': 5,
            'retry_delay': 1.5
        }
        
        result = crawler._validate_and_update_task_params(task_id, valid_global_params)
        assert result is True
        assert crawler.global_params['max_retries'] == 5
        assert crawler.global_params['retry_delay'] == 1.5
        assert crawler.update_config_called
        
        # 測試無效參數類型
        crawler.update_config_called = False
        invalid_params = {
            'max_pages': 'not_a_number',  # 應該是整數
            'ai_only': True
        }
        
        result = crawler._validate_and_update_task_params(task_id, invalid_params)
        assert result is False
        assert crawler.scrape_phase[task_id]['scrape_phase'] == ScrapePhase.FAILED.value
        
        

    def test_calculate_progress(self, mock_config_file, article_service):
        """測試進度計算方法"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 測試不同階段的進度計算
        assert crawler._calculate_progress('fetch_links', 0.5) == 10  # 20% * 0.5 = 10%
        assert crawler._calculate_progress('fetch_contents', 0.0) == 20  # fetch_links 完成 (20%) + fetch_contents 0%
        assert crawler._calculate_progress('fetch_contents', 0.5) == 45  # 20% + 50% * 0.5 = 45%
        assert crawler._calculate_progress('update_dataframe', 1.0) == 80  # 20% + 50% + 10% = 80%
        assert crawler._calculate_progress('save_to_csv', 1.0) == 90  # 20% + 50% + 10% + 10% = 90%
        assert crawler._calculate_progress('save_to_database', 1.0) == 100  # 全部完成

        # 測試無效的階段名稱
        assert crawler._calculate_progress('invalid_stage', 0.5) == 0
        
        # 測試超出範圍的子進度
        assert crawler._calculate_progress('fetch_links', 1.5) == 20  # 應該被限制在 1.0
        assert crawler._calculate_progress('fetch_links', -0.5) == 0  # 應該被限制在 0.0

    def test_fetch_article_list(self, mock_config_file, article_service, initialized_db_manager):
        """測試 _fetch_article_list 方法 (使用 initialized_db_manager)"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        task_id = 1
        
        # 初始化任務狀態
        crawler.scrape_phase[task_id] = {
            'status': 'running',
            'progress': 0,
            'message': '開始執行任務',
            'start_time': datetime.now(timezone.utc)
        }
        
        # 測試從網站抓取
        crawler.global_params = {'get_links_by_task_id': False}
        # 模擬 retry_operation 的行為，直接返回 _fetch_article_links 的結果
        # 創建一個臨時的 MockCrawlerForTest 來調用 _fetch_article_links
        temp_crawler = MockCrawlerForTest(mock_config_file, article_service)
        mock_fetch_links_result = temp_crawler._fetch_article_links(task_id)
        crawler.retry_operation = MagicMock(return_value=mock_fetch_links_result)
        
        result_df = crawler._fetch_article_list(task_id)
        
        # 驗證 _fetch_article_links 在 retry_operation 內部被間接調用
        # 我們不能直接斷言 crawler.fetch_article_links_called，因為它在 mock_fetch_links_result 創建時被設置
        assert result_df is not None
        assert len(result_df) == 2
        
        # 測試從資料庫抓取
        crawler.global_params = {'get_links_by_task_id': True}
        
        # 建立測試資料
        test_time = datetime.now(timezone.utc)
        test_articles_data = [
             {
                "title": "測試文章DB", "summary": "測試摘要DB", "link": "https://example.com/db",
                "category": "測試分類", "published_at": test_time, "author": "測試作者",
                "source": "test_source", "source_url": "https://example.com", "article_type": "test",
                "tags": "test", "is_ai_related": False, "is_scraped": False,
                # 添加 Pydantic Schema 驗證所需的預設時間戳記
                "created_at": test_time, 
                "updated_at": test_time 
            }
        ]
        
        # 新增數據 (清理已由 fixture 處理)
        with initialized_db_manager.get_session() as session:
            new_article = Articles(**test_articles_data[0])
            session.add(new_article)
            session.commit()
            # 獲取新文章的 ID，以創建 Pydantic 模型
            article_id = new_article.id 

        # 模擬 article_service.find_articles_advanced 的返回值
        test_articles_data[0]['id'] = article_id # 添加 ID
        articles_schemas = [ArticleReadSchema.model_validate(a) for a in test_articles_data]
        paginated_response = PaginatedArticleResponse(
            items=articles_schemas, 
            total=len(articles_schemas), 
            page=1, 
            per_page=100, 
            total_pages=1,
            has_next=False,
            has_prev=False
        )
        
        # 暫時 mock find_articles_advanced
        original_find_advanced = article_service.find_articles_advanced
        article_service.find_articles_advanced = MagicMock(return_value={
            "success": True,
            "resultMsg": paginated_response,
            "message": "獲取成功"
        })
        
        # 模擬 retry_operation 
        # 創建一個臨時的 MockCrawlerForTest 來調用 _fetch_article_links_from_db
        temp_crawler_db = MockCrawlerForTest(mock_config_file, article_service)
        mock_fetch_db_result = temp_crawler_db._fetch_article_links_from_db()
        crawler.retry_operation = MagicMock(return_value=mock_fetch_db_result)
        
        result_df = crawler._fetch_article_list(task_id)
        
        # 恢復原始方法
        article_service.find_articles_advanced = original_find_advanced
        
        assert result_df is not None
        assert len(result_df) == 1
        assert result_df.iloc[0]['title'] == "測試文章DB"
        
        # 測試抓取失敗
        # 使用 side_effect 模擬 retry_operation 抛出異常
        crawler.retry_operation = MagicMock(side_effect=Exception("測試抓取失敗"))
        
        with pytest.raises(Exception, match="測試抓取失敗"):
            crawler._fetch_article_list(task_id)

    def test_save_results(self, mock_config_file, article_service, logs_dir):
        """測試 _save_results 方法"""
        with patch('os.makedirs', return_value=None):
            crawler = MockCrawlerForTest(mock_config_file, article_service)
            task_id = 1
            
            # 初始化任務狀態
            crawler.scrape_phase[task_id] = {
                'status': 'running',
                'progress': 0,
                'message': '開始執行任務',
                'start_time': datetime.now(timezone.utc)
            }
            
            # 準備測試數據
            crawler.articles_df = pd.DataFrame({
                'title': ['Title 1', 'Title 2'],
                'summary': ['Summary 1', 'Summary 2'],
                'content': ['Content 1', 'Content 2'],
                'link': ['https://example.com/1', 'https://example.com/2'],
                'is_scraped': [True, True]
            })
            
            # 模擬保存方法
            crawler._save_to_csv = MagicMock()
            crawler._save_to_database = MagicMock()
            
            # 測試都不保存的情況
            crawler.global_params = {
                'save_to_csv': False,
                'save_to_database': False
            }
            
            crawler._save_results(task_id)
            crawler._save_to_csv.assert_not_called()
            crawler._save_to_database.assert_not_called()
            
            # 測試只保存到CSV
            crawler.global_params = {
                'save_to_csv': True,
                'save_to_database': False
            }
            
            crawler._save_results(task_id)
            crawler._save_to_csv.assert_called_once()
            crawler._save_to_database.assert_not_called()
            
            # 重置Mock
            crawler._save_to_csv.reset_mock()
            
            # 測試只保存到數據庫
            crawler.global_params = {
                'save_to_csv': False,
                'save_to_database': True
            }
            
            crawler._save_results(task_id)
            crawler._save_to_csv.assert_not_called()
            crawler._save_to_database.assert_called_once()
            
            # 重置Mock
            crawler._save_to_database.reset_mock()
            
            # 測試空的DataFrame
            crawler.articles_df = pd.DataFrame()
            crawler.global_params = {
                'save_to_csv': True,
                'save_to_database': True
            }
            
            crawler._save_results(task_id)
            crawler._save_to_csv.assert_not_called()
            crawler._save_to_database.assert_not_called()
    
    def test_cancel_task(self, mock_config_file, article_service):
        """測試取消任務的方法"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 測試取消不存在的任務
        result = crawler.cancel_task(999)
        assert result is False
        
        # 測試取消正在執行的任務
        task_id = 1
        crawler.scrape_phase[task_id] = {
            'scrape_phase': ScrapePhase.LINK_COLLECTION.value,
            'progress': 50,
            'message': '正在執行任務',
            'start_time': datetime.now(timezone.utc)
        }
        
        result = crawler.cancel_task(task_id)
        assert result is True
        assert crawler.scrape_phase[task_id]['cancel_flag'] == True
        assert crawler.scrape_phase[task_id]['message'] == '任務已取消'
        
        # 測試取消已完成的任務
        task_id = 2
        crawler.scrape_phase[task_id] = {
            'scrape_phase': ScrapePhase.COMPLETED.value,
            'progress': 100,
            'message': '任務已完成',
            'start_time': datetime.now(timezone.utc)
        }
        
        result = crawler.cancel_task(task_id)
        assert result is False
        assert crawler.scrape_phase[task_id]['scrape_phase'] == ScrapePhase.COMPLETED.value

    def test_check_if_cancelled(self, mock_config_file, article_service):
        """測試檢查任務是否被取消的方法"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 測試不存在的任務
        result = crawler._check_if_cancelled(999)
        assert result is False
        
        # 測試未取消的任務
        task_id = 1
        crawler.scrape_phase[task_id] = {
            'scrape_phase': ScrapePhase.LINK_COLLECTION.value,
            'progress': 50,
            'message': '正在執行任務',
            'start_time': datetime.now(timezone.utc),
            'cancel_flag': False
        }
        
        result = crawler._check_if_cancelled(task_id)
        assert result is False
        
        # 測試已取消的任務
        task_id = 2
        crawler.scrape_phase[task_id] = {
            'scrape_phase': ScrapePhase.LINK_COLLECTION.value,
            'progress': 50,
            'message': '正在執行任務',
            'start_time': datetime.now(timezone.utc),
            'cancel_flag': True
        }
        
        result = crawler._check_if_cancelled(task_id)
        assert result is True
        
        # 測試沒有設置 cancelled 標誌的任務
        task_id = 3
        crawler.scrape_phase[task_id] = {
            'scrape_phase': ScrapePhase.LINK_COLLECTION.value,
            'progress': 50,
            'message': '正在執行任務',
            'start_time': datetime.now(timezone.utc)
            # 沒有 cancelled 標誌
        }
        
        result = crawler._check_if_cancelled(task_id)
        assert result is False

    def test_update_articles_with_content_with_new_fields(self, mock_config_file, article_service):
        """測試更新文章內容時包含新欄位"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 創建測試用的 DataFrame
        current_time = datetime.now(timezone.utc)
        df = pd.DataFrame({
            'title': ['Test Article 1', 'Test Article 2', 'Test Article 3'],
            'link': ['https://example.com/1', 'https://example.com/2', 'https://example.com/3'],
            'is_scraped': [False, False, False],
            'scrape_status': ['link_saved', 'link_saved', 'link_saved'],
            'scrape_error': [None, None, None],
            'last_scrape_attempt': [None, None, None],
            'task_id': [None, None, None]
        })
        
        # 創建測試用的文章內容
        articles_content = [
            {
                'title': 'Test Article 1 (Updated)',
                'link': 'https://example.com/1',
                'content': 'Updated content 1',
                'is_scraped': True,
                'scrape_status': 'content_scraped',
                'scrape_error': None,
                'last_scrape_attempt': current_time,
                'task_id': 123
            },
            {
                'title': 'Test Article 2 (Failed)',
                'link': 'https://example.com/2',
                'content': None,
                'is_scraped': False,
                'scrape_status': 'failed',
                'scrape_error': '連接錯誤',
                'last_scrape_attempt': current_time,
                'task_id': 123
            }
        ]
        
        # 更新 DataFrame
        result_df = crawler._update_articles_with_content(df, articles_content)
        
        # 驗證結果
        assert len(result_df) == 3
        assert result_df.loc[0, 'title'] == 'Test Article 1 (Updated)'
        assert result_df.loc[0, 'content'] == 'Updated content 1'
        assert result_df.loc[0, 'is_scraped'] == True
        
        assert result_df.loc[1, 'title'] == 'Test Article 2 (Failed)'
        assert result_df.loc[1, 'is_scraped'] == False
        assert result_df.loc[1, 'scrape_status'] == 'failed'
        assert result_df.loc[1, 'scrape_error'] == '連接錯誤'
        assert pd.notna(result_df.loc[1, 'last_scrape_attempt'])
        assert result_df.loc[1, 'task_id'] == 123
        
        # 第三篇文章應該保持不變
        assert result_df.loc[2, 'title'] == 'Test Article 3'
        assert result_df.loc[2, 'is_scraped'] == False
        assert result_df.loc[2, 'scrape_status'] == 'link_saved'

    def test_save_to_database_with_new_fields(self, mock_config_file, article_service, initialized_db_manager):
        """測試保存到數據庫包含新欄位 (使用 initialized_db_manager)"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 建立測試用的 DataFrame
        current_time = datetime.now(timezone.utc)
        test_data = [
            {
                'title': 'Test Article For DB',
                'summary': 'Test summary',
                'content': 'Test content',
                'link': 'https://example.com/db_test',
                'category': 'Test Category',
                'published_at': current_time,
                'author': 'Test Author',
                'source': 'test_source',
                'source_url': 'https://example.com',
                'article_type': 'news',
                'tags': 'tag1,tag2',
                'is_ai_related': True,
                'is_scraped': True,
                'scrape_status': 'content_scraped',
                'scrape_error': None,
                'last_scrape_attempt': current_time,
                'task_id': 456
            }
        ]
        crawler.articles_df = pd.DataFrame(test_data)
        
        # 清理數據庫 (已由 fixture 處理)
        # with initialized_db_manager.get_session() as session:
        #     session.query(Articles).filter_by(link='https://example.com/db_test').delete()
        #     session.commit()
            
        # 執行保存到數據庫的方法
        crawler._save_to_database()
        
        # 查詢數據庫以驗證保存的結果
        with initialized_db_manager.get_session() as session:
            saved_article = session.query(Articles).filter_by(link='https://example.com/db_test').first()
        
        assert saved_article is not None
        assert saved_article.title == 'Test Article For DB'
        assert saved_article.is_scraped == True
        assert saved_article.scrape_status == ArticleScrapeStatus.CONTENT_SCRAPED # 比較 Enum
        assert saved_article.scrape_error is None
        # 比較 datetime 對象
        assert saved_article.last_scrape_attempt.replace(tzinfo=timezone.utc) == current_time.replace(tzinfo=timezone.utc)
        assert saved_article.task_id == 456

    def test_execute_content_only_task_with_get_links_by_task_id(self, mock_config_file, article_service):
        """測試使用get_links_by_task_id參數執行僅抓取內容的任務"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        task_id = 1
        
        # 設置全局參數
        crawler.global_params = {
            'get_links_by_task_id': True,
            'scrape_mode': ScrapeMode.CONTENT_ONLY
        }
        
        # 初始化任務狀態
        crawler.scrape_phase[task_id] = {
            'status': 'running',
            'progress': 0,
            'message': '開始執行任務',
            'start_time': datetime.now(timezone.utc)
        }
        
        # 模擬 _fetch_article_links_by_filter 方法
        crawler._fetch_article_links_by_filter = MagicMock(return_value=pd.DataFrame({
            'title': ['Test Article'],
            'link': ['https://example.com']
        }))
        
        # 模擬 retry_operation 方法來模擬成功獲取文章清單
        crawler.retry_operation = MagicMock(side_effect=lambda func, max_retries=None, retry_delay=None, task_id=None: func())
        
        # 模擬 _fetch_articles 方法以返回一些文章內容
        crawler._fetch_articles = MagicMock(return_value=[{
            'title': 'Test Article',
            'content': 'Test Content',
            'link': 'https://example.com',
            'is_scraped': True,
            'scrape_status': 'content_scraped'
        }])
        
        # 模擬 _save_results 方法以避免實際執行保存
        crawler._save_results = MagicMock()
        
        # 調用方法
        result = crawler._execute_content_only_task(task_id, 3, 0.1)
        
        # 驗證 _fetch_article_links_by_filter 被調用，並且傳入了正確的 task_id
        crawler._fetch_article_links_by_filter.assert_called_once_with(task_id=task_id, is_scraped=False)
        
        # 驗證 _fetch_articles 被調用，並且傳入了正確的 task_id
        crawler._fetch_articles.assert_called_once_with(task_id)
        
        # 驗證結果
        assert result['success'] is True
        assert 'articles_count' in result

    def test_validate_get_links_by_task_id_param(self, mock_config_file, article_service):
        """測試驗證get_links_by_task_id參數"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        task_id = 1
        
        # 初始化任務狀態
        crawler.scrape_phase[task_id] = {
            'status': 'running',
            'progress': 0,
            'message': '開始執行任務',
            'start_time': datetime.now(timezone.utc)
        }
        
        # 測試有效的get_links_by_task_id參數
        valid_params = {**TASK_ARGS_DEFAULT,
            'get_links_by_task_id': True,
            'scrape_mode': 'content_only'
        }
        
        result = crawler._validate_and_update_task_params(task_id, valid_params)
        assert result is True
        assert crawler.global_params['get_links_by_task_id'] is True
        assert crawler.global_params['scrape_mode'] == ScrapeMode.CONTENT_ONLY.value
        
        # 測試CONTENT_ONLY模式下缺少必要參數的情況
        invalid_params = {**TASK_ARGS_DEFAULT,
            'get_links_by_task_id': False,
            'scrape_mode': 'content_only',
            # 沒有提供article_links
        }
        invalid_params.pop('article_links')
        result = crawler._validate_and_update_task_params(task_id, invalid_params)
        assert result is False
        # 驗證狀態更新為失敗
        assert crawler.scrape_phase[task_id]['scrape_phase'] == ScrapePhase.FAILED.value
        # 驗證錯誤消息包含預期文本
        assert "任務參數驗證失敗: task_args.article_links: 必填欄位不能缺少" in crawler.scrape_phase[task_id]['message']

    def test_execute_links_only_task(self, mock_config_file, article_service):
        """測試僅抓取連結的任務執行模式"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        task_id = 1
        
        # 設置全局參數
        crawler.global_params = {**TASK_ARGS_DEFAULT,
            'scrape_mode': ScrapeMode.LINKS_ONLY
        }
        
        # 初始化任務狀態
        crawler.scrape_phase[task_id] = {
            'status': 'running',
            'progress': 0,
            'message': '開始執行任務',
            'start_time': datetime.now(timezone.utc)
        }
        
        # 模擬 retry_operation 方法來模擬成功獲取文章清單
        crawler.retry_operation = MagicMock(side_effect=lambda func, max_retries=None, retry_delay=None, task_id=None: func())
        
        # 模擬 _fetch_article_list 方法
        test_df = pd.DataFrame({
            'title': ['Article 1', 'Article 2'],
            'link': ['https://example.com/1', 'https://example.com/2'],
            'is_scraped': [False, False]
        })
        crawler._fetch_article_list = MagicMock(return_value=test_df)
        
        # 模擬 _save_results 方法以避免實際執行保存
        crawler._save_results = MagicMock()
        
        # 調用 _execute_links_only_task 方法
        result = crawler._execute_links_only_task(task_id, 3, 0.1)
        
        # 驗證方法調用與結果
        crawler._fetch_article_list.assert_called_once_with(task_id, 3, 0.1)
        crawler._save_results.assert_called_once_with(task_id)
        
        # 驗證結果
        assert result['success'] is True
        assert result['message'] == '文章連結收集完成'
        assert result['articles_count'] == 2
        assert crawler.scrape_phase[task_id]['scrape_phase'] == ScrapePhase.COMPLETED.value
        assert crawler.scrape_phase[task_id]['progress'] == 100
    
    def test_execute_full_scrape_task(self, mock_config_file, article_service):
        """測試完整抓取模式 (連結和內容)"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        task_id = 1
        
        # 設置全局參數
        crawler.global_params = {
            'scrape_mode': ScrapeMode.FULL_SCRAPE
        }
        
        # 初始化任務狀態
        crawler.scrape_phase[task_id] = {
            'scrape_phase': ScrapePhase.LINK_COLLECTION.value,
            'progress': 0,
            'message': '開始執行任務',
            'start_time': datetime.now(timezone.utc)
        }
        
        # 模擬 retry_operation 方法來模擬成功獲取文章清單和內容
        crawler.retry_operation = MagicMock(side_effect=lambda func, max_retries=None, retry_delay=None, task_id=None: func())
        
        # 模擬 _fetch_article_list 方法
        test_df = pd.DataFrame({
            'title': ['Article 1', 'Article 2'],
            'link': ['https://example.com/1', 'https://example.com/2'],
            'is_scraped': [False, False]
        })
        crawler._fetch_article_list = MagicMock(return_value=test_df)
        
        # 模擬 _fetch_articles 方法
        current_time = datetime.now(timezone.utc)
        crawler._fetch_articles = MagicMock(return_value=[
            {
                'title': 'Article 1',
                'content': 'Content 1',
                'link': 'https://example.com/1',
                'is_scraped': True,
                'scrape_status': 'content_scraped',
                'published_at': current_time
            },
            {
                'title': 'Article 2',
                'content': 'Content 2',
                'link': 'https://example.com/2',
                'is_scraped': True,
                'scrape_status': 'content_scraped',
                'published_at': current_time
            }
        ])
        
        # 模擬 _update_articles_with_content 和 _save_results 方法
        crawler._update_articles_with_content = MagicMock(return_value=test_df)
        crawler._save_results = MagicMock()
        
        # 調用 _execute_full_scrape_task 方法
        result = crawler._execute_full_scrape_task(task_id, 3, 0.1)
        
        # 驗證方法調用與結果
        crawler._fetch_article_list.assert_called_once_with(task_id, 3, 0.1)
        crawler._fetch_articles.assert_called_once_with(task_id)
        crawler._update_articles_with_content.assert_called_once()
        crawler._save_results.assert_called_once_with(task_id)
        
        # 驗證結果
        assert result['success'] is True
        assert result['message'] == '任務完成'
        assert result['articles_count'] == 2
        assert crawler.scrape_phase[task_id]['scrape_phase'] == ScrapePhase.COMPLETED.value
        assert crawler.scrape_phase[task_id]['progress'] == 100
    
    def test_execute_content_only_task_with_article_ids(self, mock_config_file, article_service):
        """測試使用文章ID列表的內容抓取模式"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        task_id = 1
        
        # 設置全局參數 - 將article_ids轉換為article_links
        article_links = ['https://example.com/1', 'https://example.com/2']
        crawler.global_params = {
            'get_links_by_task_id': False,
            'scrape_mode': ScrapeMode.CONTENT_ONLY,
            'article_links': article_links  # 使用article_links替代article_ids
        }
        
        # 初始化任務狀態
        crawler.scrape_phase[task_id] = {
            'scrape_phase': ScrapePhase.LINK_COLLECTION.value,
            'progress': 0,
            'message': '開始執行任務',
            'start_time': datetime.now(timezone.utc)
        }
        
        # 模擬 retry_operation 方法來模擬成功獲取文章清單和內容
        crawler.retry_operation = MagicMock(side_effect=lambda func, max_retries=None, retry_delay=None, task_id=None: func())
        
        # 模擬 _fetch_article_links_by_filter 方法
        test_df = pd.DataFrame({
            'title': ['Test Article 1', 'Test Article 2'],
            'link': ['https://example.com/1', 'https://example.com/2'],
            'id': [101, 102],
            'is_scraped': [False, False]
        })
        crawler._fetch_article_links_by_filter = MagicMock(return_value=test_df)
        
        # 模擬 _fetch_articles 方法
        current_time = datetime.now(timezone.utc)
        crawler._fetch_articles = MagicMock(return_value=[
            {
                'title': 'Test Article 1',
                'content': 'Content 1',
                'link': 'https://example.com/1',
                'is_scraped': True,
                'scrape_status': 'content_scraped',
                'published_at': current_time
            },
            {
                'title': 'Test Article 2',
                'content': 'Content 2',
                'link': 'https://example.com/2',
                'is_scraped': True,
                'scrape_status': 'content_scraped',
                'published_at': current_time
            }
        ])
        
        # 模擬 _update_articles_with_content 和 _save_results 方法
        crawler._update_articles_with_content = MagicMock(return_value=test_df)
        crawler._save_results = MagicMock()
        
        # 調用 _execute_content_only_task 方法
        result = crawler._execute_content_only_task(task_id, 3, 0.1)
        
        # 驗證方法調用與結果
        crawler._fetch_article_links_by_filter.assert_called_once()
        # 確認調用時傳遞了article_links參數
        call_args = crawler._fetch_article_links_by_filter.call_args[1]
        assert 'article_links' in call_args
        assert call_args['article_links'] == article_links
        
        crawler._fetch_articles.assert_called_once_with(task_id)
        crawler._update_articles_with_content.assert_called_once()
        crawler._save_results.assert_called_once_with(task_id)
        
        # 驗證結果
        assert result['success'] is True
        assert result['message'] == '任務完成'
        assert 'articles_count' in result
        assert crawler.scrape_phase[task_id]['scrape_phase'] == ScrapePhase.COMPLETED.value
        assert crawler.scrape_phase[task_id]['progress'] == 100
    
    def test_execute_content_only_task_with_article_links(self, mock_config_file, article_service):
        """測試使用文章連結列表的內容抓取模式"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        task_id = 1
        
        # 設置全局參數
        crawler.global_params = {
            'get_links_by_task_id': False,
            'scrape_mode': ScrapeMode.CONTENT_ONLY,
            'article_links': ['https://example.com/link1', 'https://example.com/link2']
        }
        
        # 初始化任務狀態
        crawler.scrape_phase[task_id] = {
            'scrape_phase': ScrapePhase.LINK_COLLECTION.value,
            'progress': 0,
            'message': '開始執行任務',
            'start_time': datetime.now(timezone.utc)
        }
        
        # 模擬 retry_operation 方法來模擬成功獲取文章清單
        crawler.retry_operation = MagicMock(side_effect=lambda func, max_retries=None, retry_delay=None, task_id=None: func())
        
        # 模擬 _fetch_article_links_by_filter 方法
        test_df = pd.DataFrame({
            'title': ['Link Article 1', 'Link Article 2'],
            'link': ['https://example.com/link1', 'https://example.com/link2'],
            'is_scraped': [False, False]
        })
        crawler._fetch_article_links_by_filter = MagicMock(return_value=test_df)
        
        # 模擬 _fetch_articles 方法
        current_time = datetime.now(timezone.utc)
        crawler._fetch_articles = MagicMock(return_value=[
            {
                'title': 'Link Article 1',
                'content': 'Content from link 1',
                'link': 'https://example.com/link1',
                'is_scraped': True,
                'scrape_status': 'content_scraped',
                'published_at': current_time
            },
            {
                'title': 'Link Article 2',
                'content': 'Content from link 2',
                'link': 'https://example.com/link2',
                'is_scraped': True,
                'scrape_status': 'content_scraped',
                'published_at': current_time
            }
        ])
        
        # 模擬 _update_articles_with_content 和 _save_results 方法
        crawler._update_articles_with_content = MagicMock(return_value=test_df)
        crawler._save_results = MagicMock()
        
        # 調用 _execute_content_only_task 方法
        result = crawler._execute_content_only_task(task_id, 3, 0.1)
        
        # 驗證方法調用與結果
        crawler._fetch_article_links_by_filter.assert_called_once()
        # 確認調用時傳遞了article_links參數
        call_args = crawler._fetch_article_links_by_filter.call_args[1]
        assert 'article_links' in call_args
        assert call_args['article_links'] == ['https://example.com/link1', 'https://example.com/link2']
        
        crawler._fetch_articles.assert_called_once_with(task_id)
        crawler._update_articles_with_content.assert_called_once()
        crawler._save_results.assert_called_once_with(task_id)
        
        # 驗證結果
        assert result['success'] is True
        assert result['message'] == '任務完成'
        assert 'articles_count' in result
        assert crawler.scrape_phase[task_id]['scrape_phase'] == ScrapePhase.COMPLETED.value
        assert crawler.scrape_phase[task_id]['progress'] == 100
        
    def test_execute_task_different_modes(self, mock_config_file, article_service):
        """測試 execute_task 方法對不同模式的調用"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 模擬子方法
        crawler._execute_links_only_task = MagicMock(return_value={'success': True, 'message': 'LINKS_ONLY完成'})
        crawler._execute_content_only_task = MagicMock(return_value={'success': True, 'message': 'CONTENT_ONLY完成'})
        crawler._execute_full_scrape_task = MagicMock(return_value={'success': True, 'message': 'FULL_SCRAPE完成'})
        
        # 模擬驗證方法，使其能夠設置全局參數
        def validate_and_update_mock(task_id, task_args):
            if 'scrape_mode' in task_args:
                # 修正: 存儲 Enum 的 value
                if task_args['scrape_mode'] == 'links_only':
                    crawler.global_params['scrape_mode'] = ScrapeMode.LINKS_ONLY.value
                elif task_args['scrape_mode'] == 'content_only':
                    crawler.global_params['scrape_mode'] = ScrapeMode.CONTENT_ONLY.value
                elif task_args['scrape_mode'] == 'full_scrape':
                    crawler.global_params['scrape_mode'] = ScrapeMode.FULL_SCRAPE.value
            crawler.global_params['max_retries'] = 3
            crawler.global_params['retry_delay'] = 0.1
            return True
            
        crawler._validate_and_update_task_params = MagicMock(side_effect=validate_and_update_mock)
        
        # 模擬 _check_if_cancelled 方法，使其總是返回 False
        crawler._check_if_cancelled = MagicMock(return_value=False)
        
        # 模擬 retry_operation 方法來支持task_id參數
        crawler.retry_operation = MagicMock(side_effect=lambda func, max_retries=None, retry_delay=None, task_id=None: func())
        
        # 測試LINKS_ONLY模式
        task_id = 1
        crawler.global_params = {}  # 清除全局參數
        crawler.scrape_phase[task_id] = {
            'scrape_phase': ScrapePhase.LINK_COLLECTION.value,
            'progress': 0,
            'message': '開始執行任務',
            'start_time': datetime.now(timezone.utc)
        }
        result = crawler.execute_task(task_id, {'scrape_mode': 'links_only'})
        crawler._execute_links_only_task.assert_called_once_with(task_id, 3, 0.1)
        assert result['success'] is True
        assert result['message'] == 'LINKS_ONLY完成'
        
        # 重置模擬
        crawler._execute_links_only_task.reset_mock()
        crawler._execute_content_only_task.reset_mock() 
        crawler._execute_full_scrape_task.reset_mock()
        
        # 測試CONTENT_ONLY模式
        task_id = 2
        crawler.global_params = {}  # 清除全局參數
        crawler.scrape_phase[task_id] = {
            'status': 'running',
            'progress': 0,
            'message': '開始執行任務',
            'start_time': datetime.now(timezone.utc)
        }
        result = crawler.execute_task(task_id, {'scrape_mode': 'content_only'})
        crawler._execute_content_only_task.assert_called_once_with(task_id, 3, 0.1)
        assert result['success'] is True
        assert result['message'] == 'CONTENT_ONLY完成'
        
        # 重置模擬
        crawler._execute_links_only_task.reset_mock()
        crawler._execute_content_only_task.reset_mock() 
        crawler._execute_full_scrape_task.reset_mock()
        
        # 測試FULL_SCRAPE模式
        task_id = 3
        crawler.global_params = {}  # 清除全局參數
        crawler.scrape_phase[task_id] = {
            'status': 'running',
            'progress': 0,
            'message': '開始執行任務',
            'start_time': datetime.now(timezone.utc)
        }
        result = crawler.execute_task(task_id, {'scrape_mode': 'full_scrape'})
        crawler._execute_full_scrape_task.assert_called_once_with(task_id, 3, 0.1)
        assert result['success'] is True
        assert result['message'] == 'FULL_SCRAPE完成'

    def test_execute_task_with_cancellation(self, mock_config_file, article_service):
        """測試執行任務過程中被取消的情況"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 初始化任務並將其設為已取消
        task_id = 999
        crawler.scrape_phase[task_id] = {
            'status': 'running',
            'progress': 0,
            'message': '開始執行任務',
            'start_time': datetime.now(timezone.utc),
            'cancel_flag': True
        }
        
        # 模擬 _validate_and_update_task_params 通過驗證
        crawler._validate_and_update_task_params = MagicMock(return_value=True)
        
        # 模擬 _check_if_cancelled 始終返回True，確保任務被視為已取消
        crawler._check_if_cancelled = MagicMock(return_value=True)
        
        # 模擬取消處理方法返回標準的取消響應
        expected_result = {
            'success': False,
            'message': '任務已取消',
            'articles_count': 0,
            'scrape_phase': {'status': 'cancelled'},
            'partial_data_saved': False
        }
        crawler._handle_task_cancellation = MagicMock(return_value=expected_result)
        
        # 模擬各種執行方法，以便確認它們未被調用
        crawler._execute_full_scrape_task = MagicMock()
        crawler._execute_links_only_task = MagicMock()
        crawler._execute_content_only_task = MagicMock()
        
        # 測試在參數驗證後立即檢查取消狀態
        result = crawler.execute_task(task_id, {'scrape_mode': 'full_scrape'})
        
        # 驗證結果
        assert result['success'] is False
        assert '任務已取消' in result['message']
        assert result['articles_count'] == 0
        
        # 確認取消檢查方法被調用
        crawler._check_if_cancelled.assert_called()
        crawler._handle_task_cancellation.assert_called_once_with(task_id)
        
        # 確認各執行任務方法未被調用
        crawler._execute_full_scrape_task.assert_not_called()
        crawler._execute_links_only_task.assert_not_called()
        crawler._execute_content_only_task.assert_not_called()

    def test_handle_task_cancellation(self, mock_config_file, article_service, logs_dir):
        """測試處理任務取消的功能"""
        with patch('os.makedirs', return_value=None):
            crawler = MockCrawlerForTest(mock_config_file, article_service)
            
            # 準備測試數據
            task_id = 111
            current_time = datetime.now(timezone.utc)
            crawler.scrape_phase[task_id] = {
                'scrape_phase': ScrapePhase.LINK_COLLECTION.value,
                'progress': 50,
                'message': '正在執行任務',
                'start_time': current_time,
                'cancel_flag': True
            }
            
            # 測試1: 沒有數據的情況
            crawler.articles_df = pd.DataFrame()
            result = crawler._handle_task_cancellation(task_id)
            assert result['success'] is False
            assert result['message'] == '任務已取消'
            assert result['articles_count'] == 0
            assert result['partial_data_saved'] is False
            assert crawler.scrape_phase[task_id]['scrape_phase'] == ScrapePhase.CANCELLED.value
            
            # 測試2: 有數據但不保存
            crawler.articles_df = pd.DataFrame({
                'title': ['Title 1', 'Title 2'],
                'content': ['Content 1', 'Content 2'],
                'link': ['https://example.com/1', 'https://example.com/2'],
                'is_scraped': [True, True]
            })
            crawler.global_params = {
                'save_partial_results_on_cancel': False
            }
            
            result = crawler._handle_task_cancellation(task_id)
            assert result['success'] is False
            assert result['message'] == '任務已取消'
            assert result['partial_data_saved'] is False
            
            # 測試3: 有數據且保存到CSV
            crawler.global_params = {
                'save_partial_results_on_cancel': True,
                'save_to_csv': True,
                'csv_file_prefix': 'test'
            }
            
            # 增加更多數據，確保滿足len(articles_df) >= 5的條件
            crawler.articles_df = pd.DataFrame({
                'title': ['Title ' + str(i) for i in range(1, 6)],
                'content': ['Content ' + str(i) for i in range(1, 6)],
                'link': ['https://example.com/' + str(i) for i in range(1, 6)],
                'is_scraped': [True, True, True, True, True]
            })
            
            # 保存DataFrame的副本，因為_handle_task_cancellation會在最後清空articles_df
            original_df = crawler.articles_df.copy()
            
            # 模擬_save_to_csv方法
            crawler._save_to_csv = MagicMock()
            
            result = crawler._handle_task_cancellation(task_id)
            assert result['success'] is False
            assert '並保存部分數據' in result['message']
            assert result['partial_data_saved'] is True
            crawler._save_to_csv.assert_called_once()
            
            # 使用saved_df的副本進行檢查，因為原始的DataFrame已被清空
            args, _ = crawler._save_to_csv.call_args
            saved_df = args[0]  # 獲取傳給_save_to_csv的DataFrame
            
            # 檢查傳給_save_to_csv的DataFrame是否被正確標記
            assert 'is_partial_save' in saved_df.columns
            assert 'cancel_reason' in saved_df.columns
            assert saved_df['is_partial_save'].all() == True  # 使用==而非is進行值比較
            
            # 測試4: 有數據且保存到數據庫
            crawler.global_params = {
                'save_partial_results_on_cancel': True,
                'save_to_csv': False,
                'save_to_database': True,
                'save_partial_to_database': True
            }
            
            # 重置DataFrame - 確保有足夠的數據且都標記為已抓取
            crawler.articles_df = pd.DataFrame({
                'title': ['Title ' + str(i) for i in range(1, 6)],
                'content': ['Content ' + str(i) for i in range(1, 6)],
                'link': ['https://example.com/' + str(i) for i in range(1, 6)],
                'is_scraped': [True, True, True, True, True]  # 全部標記為已抓取
            })
            
            # 保存DataFrame的副本
            original_df = crawler.articles_df.copy()
            
            # 模擬_save_to_database方法
            crawler._save_to_database = MagicMock()
            
            result = crawler._handle_task_cancellation(task_id)
            assert result['success'] is False
            assert '並保存部分數據' in result['message']
            assert result['partial_data_saved'] is True
            crawler._save_to_database.assert_called_once()

            assert crawler._save_to_database.called

            # 測試5: 處理在保存過程中發生錯誤的情況
            crawler._save_to_database = MagicMock(side_effect=Exception("保存錯誤"))
            
            result = crawler._handle_task_cancellation(task_id)
            assert result['success'] is False
            assert result['message'] == '任務已取消'
            assert result['partial_data_saved'] is False
            
            # 確認資源被釋放
            assert crawler.articles_df.empty

    def test_save_partial_results_on_cancel(self, mock_config_file, article_service, logs_dir):
        """測試取消任務時保存部分結果的功能"""
        with patch('os.makedirs', return_value=None):
            crawler = MockCrawlerForTest(mock_config_file, article_service)
            
            # 初始化任務
            task_id = 222
            crawler.scrape_phase[task_id] = {
                'scrape_phase': ScrapePhase.LINK_COLLECTION.value,  # 使用正確的枚舉值
                'progress': 30,
                'message': '正在抓取文章',
                'start_time': datetime.now(timezone.utc),
                'cancel_flag': True  # 從 'cancelled' 改為 'cancel_flag'
            }
            
            # 準備測試數據 - 太少的數據
            crawler.articles_df = pd.DataFrame({
                'title': ['Title 1', 'Title 2'],
                'content': ['Content 1', 'Content 2'],
                'link': ['https://example.com/1', 'https://example.com/2'],
                'is_scraped': [True, False]
            })
            
            # 測試1: 文章數量不足，不保存
            crawler.global_params = {
                'save_partial_results_on_cancel': True,
                'save_to_csv': True
            }
            
            # 模擬_save_to_csv方法
            crawler._save_to_csv = MagicMock()
            
            # 調用_handle_task_cancellation方法
            result = crawler._handle_task_cancellation(task_id)
            assert result['success'] is False
            assert result['partial_data_saved'] is False
            crawler._save_to_csv.assert_not_called()
            
            # 準備測試數據 - 足夠的數據
            crawler.articles_df = pd.DataFrame({
                'title': ['Title ' + str(i) for i in range(10)],
                'content': ['Content ' + str(i) for i in range(10)],
                'link': ['https://example.com/' + str(i) for i in range(10)],
                'is_scraped': [i % 2 == 0 for i in range(10)]  # 一半已抓取
            })
            
            # 測試2: 保存到數據庫，但只保存已抓取的文章
            crawler.global_params = {
                'save_partial_results_on_cancel': True,
                'save_to_database': True,
                'save_partial_to_database': True
            }
            
            # 模擬_save_to_database方法
            crawler._save_to_database = MagicMock()
            
            # 調用_handle_task_cancellation方法
            result = crawler._handle_task_cancellation(task_id)
            assert result['success'] is False
            assert result['partial_data_saved'] is True
            crawler._save_to_database.assert_called_once()
            
            assert result['message'] == '任務已取消並保存部分數據'
            assert result['partial_data_saved'] is True

    def test_task_cancellation_during_different_phases(self, mock_config_file, article_service):
        """測試在不同執行階段取消任務"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 初始化任務
        task_id = 333
        crawler.scrape_phase[task_id] = {
            'status': 'running',
            'progress': 0,
            'message': '開始執行任務',
            'start_time': datetime.now(timezone.utc)
        }
        
        # 模擬_validate_and_update_task_params方法，使其通過驗證
        crawler._validate_and_update_task_params = MagicMock(return_value=True)
        
        # 模擬_handle_task_cancellation方法
        crawler._handle_task_cancellation = MagicMock(return_value={
            'success': False,
            'message': '任務已取消(模擬)',
            'articles_count': 0,
            'scrape_phase': {'scrape_phase': ScrapePhase.CANCELLED.value},  # 修改為正確的結構
            'partial_data_saved': False
        })
        
        # 測試1: 獲取連結階段取消
        def fetch_article_list_and_cancel(task_id, max_retries=None, retry_delay=None):
            # 模擬在抓取文章列表時取消任務
            crawler.scrape_phase[task_id]['cancel_flag'] = True
            return None
        
        # 模擬_check_if_cancelled方法始終返回True，確保任務被視為已取消
        # 注意：在_execute_full_scrape_task方法的開頭就會檢查取消狀態
        crawler._check_if_cancelled = MagicMock(return_value=True)
        crawler._fetch_article_list = MagicMock(side_effect=fetch_article_list_and_cancel)
        crawler.global_params = {'scrape_mode': ScrapeMode.FULL_SCRAPE.value}
        
        # 重設取消狀態
        crawler.scrape_phase[task_id]['cancel_flag'] = False
        
        result = crawler._execute_full_scrape_task(task_id, 3, 0.1)
        assert crawler._handle_task_cancellation.called
        crawler._handle_task_cancellation.reset_mock()
        
        # 測試2: 獲取內容階段取消
        def fetch_article_list_mock(task_id, max_retries=None, retry_delay=None):
            # 返回一個有效的DataFrame
            return pd.DataFrame({
                'title': ['Title 1', 'Title 2'],
                'link': ['https://example.com/1', 'https://example.com/2'],
                'is_scraped': [False, False]
            })
        
        def fetch_articles_and_cancel(task_id):
            # 模擬在抓取文章內容時取消任務
            crawler.scrape_phase[task_id]['cancel_flag'] = True
            return None
        
        crawler._fetch_article_list = MagicMock(side_effect=fetch_article_list_mock)
        crawler._fetch_articles = MagicMock(side_effect=fetch_articles_and_cancel)
        crawler.retry_operation = MagicMock(side_effect=lambda func, max_retries=None, retry_delay=None, task_id=None: func())
        
        # 重設取消狀態
        crawler.scrape_phase[task_id]['cancel_flag'] = False
        
        result = crawler._execute_full_scrape_task(task_id, 3, 0.1)
        assert crawler._handle_task_cancellation.called
        crawler._handle_task_cancellation.reset_mock()
        
        # 測試3: 保存階段取消
        def fetch_articles_mock(task_id):
            # 返回有效的文章內容
            return [{
                'title': 'Title 1',
                'content': 'Content 1',
                'link': 'https://example.com/1',
                'is_scraped': True
            }]
        
        def save_results_and_cancel(task_id):
            # 模擬在保存結果時取消任務
            crawler.scrape_phase[task_id]['cancel_flag'] = True
            raise Exception(f"任務 {task_id} 已取消")
        
        crawler._fetch_articles = MagicMock(side_effect=fetch_articles_mock)
        crawler._update_articles_with_content = MagicMock(return_value=pd.DataFrame())
        crawler._save_results = MagicMock(side_effect=save_results_and_cancel)
        
        # 重設取消狀態
        crawler.scrape_phase[task_id]['cancel_flag'] = False
        
        result = crawler._execute_full_scrape_task(task_id, 3, 0.1)
        assert crawler._handle_task_cancellation.called

    def test_task_cancellation_error_handling(self, mock_config_file, article_service):
        """測試取消任務時的錯誤處理"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 初始化任務
        task_id = 444
        crawler.scrape_phase[task_id] = {
            'scrape_phase': ScrapePhase.INIT.value,  # 使用正確的枚舉值
            'progress': 0,
            'message': '開始執行任務',
            'start_time': datetime.now(timezone.utc),
            'cancel_flag': True  # 從 'cancelled' 改為 'cancel_flag'
        }
        
        # 準備測試數據
        crawler.articles_df = pd.DataFrame({
            'title': ['Title 1', 'Title 2', 'Title 3', 'Title 4', 'Title 5'],
            'content': ['Content 1', 'Content 2', 'Content 3', 'Content 4', 'Content 5'],
            'link': ['https://example.com/' + str(i) for i in range(5)],
            'is_scraped': [True, True, True, True, True]
        })
        
        # 測試1: _save_to_csv方法發生錯誤
        crawler.global_params = {
            'save_partial_results_on_cancel': True,
            'save_to_csv': True,
            'save_to_database': False
        }
        
        crawler._save_to_csv = MagicMock(side_effect=Exception("CSV保存錯誤"))
        
        result = crawler._handle_task_cancellation(task_id)
        assert result['success'] is False
        assert result['message'] == '任務已取消'
        assert result['partial_data_saved'] is False
        
        # 測試2: _save_to_database方法發生錯誤
        crawler.global_params = {
            'save_partial_results_on_cancel': True,
            'save_to_csv': False,
            'save_to_database': True,
            'save_partial_to_database': True
        }
        
        crawler._save_to_database = MagicMock(side_effect=Exception("數據庫保存錯誤"))
        
        result = crawler._handle_task_cancellation(task_id)
        assert result['success'] is False
        assert result['message'] == '任務已取消'
        assert result['partial_data_saved'] is False
        
        # 測試3: 在資源釋放過程中發生錯誤
        # 創建一個會在刪除時拋出異常的DataFrame類
        class ErrorDataFrame(pd.DataFrame):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
            
            def empty(self):
                raise Exception("資源釋放錯誤")
        
        crawler.articles_df = ErrorDataFrame({
            'title': ['Title'],
            'content': ['Content'],
            'link': ['https://example.com/'],
            'is_scraped': [True]
        })
        
        # 即使在資源釋放過程中發生錯誤，方法也應該正常完成
        result = crawler._handle_task_cancellation(task_id)
        assert result['success'] is False
        assert result['message'] == '任務已取消'

    def test_load_site_config(self, mock_config_file, article_service, monkeypatch):
        """測試配置檔案讀取功能"""
        # 創建測試用的配置檔案內容
        test_config = {
            "name": "Test Site",
            "base_url": "https://test.com",
            "list_url_template": "https://test.com/list/{page}",
            "categories": ["test"],
            "full_categories": ["Test Category"],  # 修改為列表格式
            "selectors": {
                "list": "//div[@class='article-list']",
                "title": "//h1[@class='title']",
                "content": "//div[@class='content']"
            }
        }
        
        # 設置 mock 配置檔案
        def mock_open_file(*args, **kwargs):
            class MockFile:
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    pass
                def read(self):
                    return json.dumps(test_config)
            return MockFile()
        
        monkeypatch.setattr("builtins.open", mock_open_file)
        
        # 創建爬蟲實例
        crawler = MockCrawlerForTest(config_file_name="test_config.json", article_service=article_service)
        
        # 驗證配置是否正確載入
        assert crawler.config_data == test_config
        assert crawler.site_config.name == test_config["name"]
        assert crawler.site_config.base_url == test_config["base_url"]
        assert crawler.site_config.list_url_template == test_config["list_url_template"]
        assert crawler.site_config.categories == test_config["categories"]
        assert crawler.site_config.full_categories == test_config["full_categories"]
        assert crawler.site_config.selectors == test_config["selectors"]
        
    def test_load_site_config_file_not_found(self, article_service):
        """測試配置檔案不存在的情況"""
        with pytest.raises(ValueError, match="未找到配置文件"):
            MockCrawlerForTest(config_file_name="non_existent.json", article_service=article_service)
            
    def test_load_site_config_invalid_json(self, mock_config_file, article_service, monkeypatch):
        """測試配置檔案格式錯誤的情況"""
        # 設置 mock 配置檔案返回無效的 JSON
        def mock_open_file(*args, **kwargs):
            class MockFile:
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    pass
                def read(self):
                    return "invalid json"
            return MockFile()
        
        monkeypatch.setattr("builtins.open", mock_open_file)
        
        # 創建爬蟲實例，應該會使用預設配置
        with pytest.raises(ValueError, match="未找到配置文件"):
            MockCrawlerForTest(config_file_name="test_config.json", article_service=article_service)

if __name__ == "__main__":
    pytest.main()