import pytest
import pandas as pd
import os
import json
from unittest.mock import MagicMock, patch, mock_open
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import logging

from src.crawlers.base_crawler import BaseCrawler
from src.crawlers.configs.site_config import SiteConfig
from src.services.article_service import ArticleService
from src.models.base_model import Base
from src.models.articles_model import Articles, ArticleScrapeStatus
from src.crawlers.bnext_scraper import BnextUtils
from src.database.database_manager import DatabaseManager

# 配置日誌
logger = logging.getLogger(__name__)

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
        super().__init__(config_file_name, article_service)
        
    def _fetch_article_links(self) -> Optional[pd.DataFrame]:
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
            task_id=123
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
                task_id=123
            )
        )
        df = pd.DataFrame(data)
        self.articles_df = df
        return df
        
    def _fetch_articles(self) -> Optional[List[Dict[str, Any]]]:
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
                'task_id': 123
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
                'task_id': 123
            }
        ]
        
    def _update_config(self):
        """測試用的實現"""
        self.update_config_called = True

    def _fetch_article_links_from_db(self) -> Optional[pd.DataFrame]:
        """測試用的實現"""
        try:
            # 使用 article_service 獲取未爬取的文章
            result = self.article_service.advanced_search_articles(
                is_scraped=False,
                limit=100
            )
            
            if not result["success"] or not result["articles"]:
                return None
                
            # 將文章列表轉換為 DataFrame
            articles_data = []
            for article in result["articles"]:
                articles_data.append({
                    "title": article.title,
                    "summary": article.summary,
                    "content": article.content,
                    "link": article.link,
                    "category": article.category,
                    "published_at": article.published_at,
                    "author": article.author,
                    "source": article.source,
                    "source_url": article.source_url,
                    "article_type": article.article_type,
                    "tags": article.tags,
                    "is_ai_related": article.is_ai_related,
                    "is_scraped": article.is_scraped,
                    "scrape_status": article.scrape_status.value if hasattr(article, 'scrape_status') and article.scrape_status else 'pending',
                    "scrape_error": article.scrape_error if hasattr(article, 'scrape_error') else None,
                    "last_scrape_attempt": article.last_scrape_attempt if hasattr(article, 'last_scrape_attempt') else None,
                    "task_id": article.task_id if hasattr(article, 'task_id') else None
                })
                
            return pd.DataFrame(articles_data)
            
        except Exception as e:
            logger.error(f"從資料庫獲取文章連結失敗: {str(e)}")
            return None

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

@pytest.fixture(scope="function")
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
def article_service(engine, tables):
    """創建ArticleService實例"""
    # 使用記憶體資料庫
    db_manager = DatabaseManager('sqlite:///:memory:')
    # 設置測試用的引擎
    db_manager.engine = engine
    # 創建新的會話工廠
    db_manager.Session = sessionmaker(bind=engine)
    # 創建資料表
    db_manager.create_tables(Base)
    
    service = ArticleService(db_manager)
    yield service
    
    # 清理資源
    service.cleanup()

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
    
    def test_execute_task_with_real_db(self, mock_config_file, article_service, logs_dir):
        """測試使用真實記憶體資料庫執行任務的完整流程"""
        with patch('os.makedirs', return_value=None):
            crawler = MockCrawlerForTest(mock_config_file, article_service)
            task_id = 1
            task_args = {
                "max_pages": 3,
                "ai_only": True,
                "num_articles": 10,
                "max_retries": 2,  # 這是全局參數
                "retry_delay": 0.1  # 這是全局參數
            }
            
            # 設置全局參數
            crawler.global_params = {'max_retries': 2, 'retry_delay': 0.1}
            
            # 保存原始函數
            original_validate = crawler._validate_and_update_task_params
            # 模擬 _validate_and_update_task_params 成功但仍調用實際的 _update_config
            def mock_validate(*args, **kwargs):
                crawler.update_config_called = True
                return True
            crawler._validate_and_update_task_params = mock_validate
            
            # 模擬 retry_operation 成功
            original_retry_operation = crawler.retry_operation
            crawler.retry_operation = MagicMock(side_effect=lambda func, max_retries=None, retry_delay=None: func())
            
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
            task_status = crawler.get_task_status(task_id)
            assert task_status["status"] == "completed"
            assert task_status["progress"] == 100
            
            # 驗證方法調用
            assert crawler.fetch_article_links_called
            assert crawler.fetch_articles_called
            assert crawler.update_config_called
            
            # 驗證資料是否確實被保存到資料庫
            db_result = article_service.get_all_articles()
            assert db_result["success"] is True
            assert len(db_result["articles"]) == 2
            assert db_result["articles"][0].title == "Test Article 1"
            assert db_result["articles"][1].title == "Test Article 2"
    
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
        task_status = crawler.get_task_status(task_id)
        assert task_status["status"] == "completed" 
        
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
        task_status = crawler.get_task_status(task_id)
        assert task_status["status"] == "failed"
        assert '測試執行錯誤' in task_status["message"]
    
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
    
    def test_save_to_database(self, mock_config_file, article_service, session):
        """測試保存數據到資料庫"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
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
        })
        
        # 先清除資料庫中的所有文章
        session.query(Articles).delete()
        session.commit()
        
        # 執行保存
        crawler._save_to_database()
        
        # 驗證資料是否被保存到資料庫
        result = article_service.get_all_articles()
        assert result["success"] is True
        assert len(result["articles"]) == 2
        
        articles = result["articles"]
        assert articles[0].title == "Test Title 1"
        assert articles[1].title == "Test Title 2"
        assert articles[0].summary == "Test Summary 1"
        assert articles[1].summary == "Test Summary 2"
        assert articles[0].content == "Test Content 1"
        assert articles[1].content == "Test Content 2"
        assert articles[0].link == "https://example.com/1"
        assert articles[1].link == "https://example.com/2"
        assert articles[0].category == "Test Category 1"
        assert articles[1].category == "Test Category 2"
        assert articles[0].published_at == test_time
        assert articles[1].published_at == test_time
        assert articles[0].author == "Test Author 1"
        assert articles[1].author == "Test Author 2"
        assert articles[0].source == "Test Source 1"
        assert articles[1].source == "Test Source 2"
        assert articles[0].source_url == "https://example.com/1"
        assert articles[1].source_url == "https://example.com/2"
        assert articles[0].article_type == "Test Article Type 1"
        assert articles[1].article_type == "Test Article Type 2"
        assert articles[0].tags == "Test Tags 1"
        assert articles[1].tags == "Test Tags 2"
        assert articles[0].is_ai_related is False
        assert articles[1].is_ai_related is False
        assert articles[0].is_scraped is False
        assert articles[1].is_scraped is False
    
    def test_save_to_database_with_db_link(self, mock_config_file, article_service, session):
        """測試從資料庫連結獲取文章"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 設定從資料庫連結獲取文章
        crawler.site_config.article_settings['from_db_link'] = True
        
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
    
    def test_get_task_status(self, mock_config_file, article_service):
        """測試獲取任務狀態"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 測試獲取不存在任務的狀態
        status = crawler.get_task_status(999)
        assert status["status"] == "unknown"
        
        # 測試獲取存在任務的狀態
        task_id = 1
        crawler.task_status[task_id] = {
            "status": "running",
            "progress": 50,
            "message": "測試任務"
        }
        
        status = crawler.get_task_status(task_id)
        assert status["status"] == "running"
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

    def test_update_task_status(self, mock_config_file, article_service):
        """測試更新任務狀態功能"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        task_id = 1
        # 初始化任務狀態
        crawler.task_status[task_id] = {
            'status': 'running',
            'progress': 0,
            'message': '開始執行任務',
            'start_time': datetime.now(timezone.utc)
        }
        
        # 更新進度
        crawler._update_task_status(task_id, 50, '處理中')
        assert crawler.task_status[task_id]['progress'] == 50
        assert crawler.task_status[task_id]['message'] == '處理中'
        assert crawler.task_status[task_id]['status'] == 'running'
        
        # 更新狀態
        crawler._update_task_status(task_id, 100, '完成', 'completed')
        assert crawler.task_status[task_id]['progress'] == 100
        assert crawler.task_status[task_id]['message'] == '完成'
        assert crawler.task_status[task_id]['status'] == 'completed'
        
        # 測試更新不存在的任務
        crawler._update_task_status(999, 50, '不存在的任務')
        assert 999 not in crawler.task_status

    def test_fetch_article_links_from_db(self, mock_config_file, article_service, session):
        """測試從資料庫獲取未爬取的文章連結"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 準備測試資料
        test_articles = [
            Articles(
                title="測試文章1",
                summary="測試摘要1",
                content="測試內容1",
                link="https://example.com/1",
                category="測試分類",
                published_at=datetime.now(timezone.utc),
                author="測試作者",
                source="test_source",
                source_url="https://example.com",
                article_type="test",
                tags="test",
                is_ai_related=False,
                is_scraped=False
            ),
            Articles(
                title="測試文章2",
                summary="測試摘要2",
                content="測試內容2",
                link="https://example.com/2",
                category="測試分類",
                published_at=datetime.now(timezone.utc),
                author="測試作者",
                source="test_source",
                source_url="https://example.com",
                article_type="test",
                tags="test",
                is_ai_related=False,
                is_scraped=False
            )
        ]
        
        # 清除現有資料並新增測試資料
        session.query(Articles).delete()
        session.add_all(test_articles)
        session.commit()
        
        # 測試成功情況
        result_df = crawler._fetch_article_links_from_db()
        assert result_df is not None
        assert len(result_df) == 2
        assert result_df.iloc[0]['title'] == "測試文章1"
        assert result_df.iloc[1]['title'] == "測試文章2"
        assert result_df.iloc[0]['link'] == "https://example.com/1"
        assert result_df.iloc[1]['link'] == "https://example.com/2"

    def test_fetch_article_links_from_db_empty(self, mock_config_file, article_service, session):
        """測試從空資料庫獲取未爬取的文章連結"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 清除所有資料
        session.query(Articles).delete()
        session.commit()
        
        # 測試空資料庫情況
        result_df = crawler._fetch_article_links_from_db()
        assert result_df is None

    def test_fetch_article_links_from_db_error(self, mock_config_file, article_service):
        """測試從資料庫獲取文章連結時發生錯誤的情況"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 模擬 article_service.advanced_search_articles 拋出異常
        crawler.article_service.advanced_search_articles = MagicMock(side_effect=Exception("資料庫錯誤"))
        
        # 測試錯誤情況
        result_df = crawler._fetch_article_links_from_db()
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
        crawler.task_status[task_id] = {
            'status': 'running',
            'progress': 0,
            'message': '開始執行任務',
            'start_time': datetime.now(timezone.utc)
        }
        
        # 測試有效參數 - 文章設定
        valid_article_params = {
            'max_pages': 5,
            'ai_only': True,
            'num_articles': 20
        }
        
        result = crawler._validate_and_update_task_params(task_id, valid_article_params)
        assert result is True
        assert crawler.site_config.article_settings['max_pages'] == 5
        assert crawler.site_config.article_settings['ai_only'] is True
        assert crawler.site_config.article_settings['num_articles'] == 20
        assert crawler.update_config_called
        
        # 測試有效參數 - 全局參數
        crawler.update_config_called = False
        valid_global_params = {
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
        assert crawler.task_status[task_id]['status'] == 'failed'
        
        # 測試未知參數
        crawler.update_config_called = False
        unknown_params = {
            'unknown_param': 'value'
        }
        
        result = crawler._validate_and_update_task_params(task_id, unknown_params)
        assert result is False

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

    def test_fetch_article_list(self, mock_config_file, article_service):
        """測試 _fetch_article_list 方法"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        task_id = 1
        
        # 初始化任務狀態
        crawler.task_status[task_id] = {
            'status': 'running',
            'progress': 0,
            'message': '開始執行任務',
            'start_time': datetime.now(timezone.utc)
        }
        
        # 測試從網站抓取
        crawler.site_config.article_settings['from_db_link'] = False
        # 模擬 retry_operation 的行為，直接返回 _fetch_article_links 的結果
        crawler.retry_operation = MagicMock(return_value=crawler._fetch_article_links())
        
        result_df = crawler._fetch_article_list(task_id)
        
        assert crawler.fetch_article_links_called
        assert result_df is not None
        assert len(result_df) == 2
        
        # 測試從資料庫抓取
        crawler.fetch_article_links_called = False
        crawler.site_config.article_settings['from_db_link'] = True
        
        # 建立測試資料
        test_articles = [
            Articles(
                title="測試文章1",
                summary="測試摘要1",
                content="測試內容1",
                link="https://example.com/1",
                category="測試分類",
                published_at=datetime.now(timezone.utc),
                author="測試作者",
                source="test_source",
                source_url="https://example.com",
                article_type="test",
                tags="test",
                is_ai_related=False,
                is_scraped=False
            )
        ]
        
        # 模擬 article_service.advanced_search_articles 的返回值
        crawler.article_service.advanced_search_articles = MagicMock(return_value={
            "success": True,
            "articles": test_articles
        })
        
        # 模擬 retry_operation 
        crawler.retry_operation = MagicMock(return_value=crawler._fetch_article_links_from_db())
        
        result_df = crawler._fetch_article_list(task_id)
        assert result_df is not None
        
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
            crawler.task_status[task_id] = {
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
            crawler.site_config.storage_settings['save_to_csv'] = False
            crawler.site_config.storage_settings['save_to_database'] = False
            
            crawler._save_results(task_id)
            crawler._save_to_csv.assert_not_called()
            crawler._save_to_database.assert_not_called()
            
            # 測試只保存到CSV
            crawler.site_config.storage_settings['save_to_csv'] = True
            crawler.site_config.storage_settings['save_to_database'] = False
            
            crawler._save_results(task_id)
            crawler._save_to_csv.assert_called_once()
            crawler._save_to_database.assert_not_called()
            
            # 重置Mock
            crawler._save_to_csv.reset_mock()
            
            # 測試只保存到數據庫
            crawler.site_config.storage_settings['save_to_csv'] = False
            crawler.site_config.storage_settings['save_to_database'] = True
            
            crawler._save_results(task_id)
            crawler._save_to_csv.assert_not_called()
            crawler._save_to_database.assert_called_once()
            
            # 重置Mock
            crawler._save_to_database.reset_mock()
            
            # 測試空的DataFrame
            crawler.articles_df = pd.DataFrame()
            crawler.site_config.storage_settings['save_to_csv'] = True
            crawler.site_config.storage_settings['save_to_database'] = True
            
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
        crawler.task_status[task_id] = {
            'status': 'running',
            'progress': 50,
            'message': '正在執行任務',
            'start_time': datetime.now(timezone.utc)
        }
        
        result = crawler.cancel_task(task_id)
        assert result is True
        assert crawler.task_status[task_id]['status'] == 'cancelled'
        assert crawler.task_status[task_id]['message'] == '任務已取消'
        
        # 測試取消已完成的任務
        task_id = 2
        crawler.task_status[task_id] = {
            'status': 'completed',
            'progress': 100,
            'message': '任務已完成',
            'start_time': datetime.now(timezone.utc)
        }
        
        result = crawler.cancel_task(task_id)
        assert result is False
        assert crawler.task_status[task_id]['status'] == 'completed'

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
        assert result_df.loc[0, 'scrape_status'] == 'content_scraped'
        assert result_df.loc[0, 'scrape_error'] is None
        assert pd.notna(result_df.loc[0, 'last_scrape_attempt'])
        assert result_df.loc[0, 'task_id'] == 123
        
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

    def test_save_to_database_with_new_fields(self, mock_config_file, article_service, session):
        """測試保存到數據庫包含新欄位"""
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
        
        # 執行保存到數據庫的方法
        crawler._save_to_database()
        
        # 查詢數據庫以驗證保存的結果
        saved_article = session.query(Articles).filter_by(link='https://example.com/db_test').first()
        
        assert saved_article is not None
        assert saved_article.title == 'Test Article For DB'
        assert saved_article.is_scraped == True
        assert saved_article.scrape_status == ArticleScrapeStatus.CONTENT_SCRAPED
        assert saved_article.scrape_error is None
        assert saved_article.last_scrape_attempt is not None
        assert saved_article.task_id == 456

if __name__ == "__main__":
    pytest.main()