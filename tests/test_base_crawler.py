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
from src.models.articles_model import Articles
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
        data.append(
            BnextUtils.get_article_columns_dict(
            title='Test Article 1',
            summary='Test summary 1',
            content='',
            link='https://example.com/1',
            category='Test Category',
            published_at=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
            author='',
            source='test_crawler',
            source_url='https://www.example.com',
            article_type='',
            tags='',
            is_ai_related=False,
            is_scraped=False
            )
        )
        data.append(
            BnextUtils.get_article_columns_dict(
                title='Test Article 2',
                summary='Test summary 2',
                content='',
                link='https://example.com/2',
                category='Test Category',
                published_at=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                author='',
                source='test_crawler',
                source_url='https://www.example.com',
                article_type='',
                tags='',
                is_ai_related=False,
                is_scraped=False
            )
        )
        df = pd.DataFrame(data)
        self.articles_df = df
        return df
        
    def _fetch_articles(self) -> Optional[List[Dict[str, Any]]]:
        """測試用的實現"""
        self.fetch_articles_called = True
        return [
            {
                'title': 'Test Article 1',
                'summary': 'Summary of article 1',
                'content': 'Content of article 1',
                'link': 'https://example.com/1',
                'category': 'Test Category',
                'published_at': datetime.now(timezone.utc),
                'author': 'Test Author',
                'source': 'Test Source',
                'source_url': 'https://example.com/1',
                'article_type': 'Test Article Type',
                'tags': 'Test Tags',
                'is_ai_related': False,
                'is_scraped': False
            },
            {
                'title': 'Test Article 2',
                'summary': 'Summary of article 2',
                'content': 'Content of article 2',
                'link': 'https://example.com/2',
                'category': 'Test Category',
                'published_at': datetime.now(timezone.utc),
                'author': 'Test Author',
                'source': 'Test Source',
                'source_url': 'https://example.com/2',
                'article_type': 'Test Article Type',
                'tags': 'Test Tags',
                'is_ai_related': False,
                'is_scraped': False
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
                    "is_scraped": article.is_scraped
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
                "num_articles": 10
            }
            
            # 執行任務
            crawler.execute_task(task_id, task_args)
            
            # 驗證任務狀態
            task_status = crawler.get_task_status(task_id)
            assert task_status["status"] == "completed"
            assert task_status["progress"] == 100
            
            # 驗證方法調用
            assert crawler.fetch_article_links_called
            assert crawler.fetch_articles_called
            assert crawler.update_config_called
            
            # 驗證資料是否確實被保存到資料庫
            result = article_service.get_all_articles()
            assert result["success"] is True
            assert len(result["articles"]) == 2
            assert result["articles"][0].title == "Test Article 1"
            assert result["articles"][1].title == "Test Article 2"
    
    def test_execute_task_no_articles(self, mock_config_file, article_service):
        """測試執行任務但沒有獲取到文章的情況"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 模擬 fetch_article_links 返回空 DataFrame
        crawler._fetch_article_links = MagicMock(return_value=None)
        
        task_id = 1
        crawler.execute_task(task_id, {})
        
        # 驗證任務狀態
        task_status = crawler.get_task_status(task_id)
        assert task_status["status"] == "completed"  # 任務狀態不會變為 completed
        
        # 驗證 fetch_articles 沒有被調用
        assert not crawler.fetch_articles_called
    
    def test_execute_task_error(self, mock_config_file, article_service):
        """測試執行任務發生錯誤的情況"""
        crawler = MockCrawlerForTest(mock_config_file, article_service)
        
        # 模擬 fetch_article_links 拋出異常
        crawler._fetch_article_links = MagicMock(side_effect=Exception("Test error"))
        
        task_id = 1
        with pytest.raises(Exception, match="Test error"):
            crawler.execute_task(task_id, {})
        
        # 驗證任務狀態
        task_status = crawler.get_task_status(task_id)
        assert task_status["status"] == "failed"
        assert "Test error" in task_status["message"]
    
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
        """測試從資料庫連結獲取的文章保存到資料庫時，將id轉為entity_id的情況"""
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

if __name__ == "__main__":
    pytest.main()