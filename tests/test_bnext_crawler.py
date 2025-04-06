import pytest
import pandas as pd
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, mock_open
from src.crawlers.bnext_crawler import BnextCrawler
from src.crawlers.bnext_scraper import BnextScraper
from src.crawlers.bnext_content_extractor import BnextContentExtractor
from src.services.article_service import ArticleService
from src.models.articles_model import Articles
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.base_model import Base
import json
from src.database.database_manager import DatabaseManager

# 測試用的配置
TEST_CONFIG = {
    "name": "bnext",
    "base_url": "https://www.bnext.com.tw",
    "list_url_template": "{base_url}/articles",
    "categories": ["AI", "technology"],
    "full_categories": ["AI", "technology"],
    "article_settings": {
        "max_pages": 2,
        "ai_only": True,
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
        "article_list": ".article-list",
        "article_title": ".article-title"
    }
}

@pytest.fixture
def mock_config_file(monkeypatch):
    """模擬配置文件"""
    import io
    
    # 將配置轉換為 JSON 字串
    config_str = json.dumps(TEST_CONFIG)
    
    # 創建一個模擬的文件對象
    mock_file = io.StringIO(config_str)
    
    # 創建一個模擬的 open 函數
    def mock_open(*args, **kwargs):
        return mock_file
        
    monkeypatch.setattr('builtins.open', mock_open)
    return "test_bnext_config.json"

@pytest.fixture
def mock_scraper():
    """模擬 BnextScraper"""
    scraper = MagicMock(spec=BnextScraper)
    
    # 模擬文章列表資料
    test_articles_df = pd.DataFrame({
        "title": ["測試文章1", "測試文章2"],
        "summary": ["摘要1", "摘要2"],
        "content": ["", ""],
        "link": ["https://www.bnext.com.tw/article/1", "https://www.bnext.com.tw/article/2"],
        "category": ["AI", "technology"],
        "published_at": [datetime.now(timezone.utc), datetime.now(timezone.utc)],
        "author": ["", ""],
        "source": ["bnext", "bnext"],
        "source_url": ["https://www.bnext.com.tw", "https://www.bnext.com.tw"],
        "article_type": ["", ""],
        "tags": ["", ""],
        "is_ai_related": [True, False],
        "is_scraped": [False, False]
    })
    
    scraper.scrape_article_list.return_value = test_articles_df
    return scraper

@pytest.fixture
def mock_extractor():
    """模擬 BnextContentExtractor"""
    extractor = MagicMock(spec=BnextContentExtractor)
    
    # 模擬文章內容資料
    test_articles = [
        {
            "title": "測試文章1",
            "summary": "摘要1",
            "content": "文章內容1",
            "link": "https://www.bnext.com.tw/article/1",
            "category": "AI",
            "published_at": datetime.now(timezone.utc),
            "author": "作者1",
            "source": "bnext",
            "source_url": "https://www.bnext.com.tw",
            "article_type": "新聞",
            "tags": "AI",
            "is_ai_related": True,
            "is_scraped": True
        },
        {
            "title": "測試文章2",
            "summary": "摘要2",
            "content": "文章內容2",
            "link": "https://www.bnext.com.tw/article/2",
            "category": "technology",
            "published_at": datetime.now(timezone.utc),
            "author": "作者2",
            "source": "bnext",
            "source_url": "https://www.bnext.com.tw",
            "article_type": "新聞",
            "tags": "科技",
            "is_ai_related": False,
            "is_scraped": True
        }
    ]
    
    # 直接設置回傳值，不需要在測試中重新設置
    extractor.batch_get_articles_content.return_value = test_articles
    return extractor

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

class TestBnextCrawler:
    """BnextCrawler 的測試類"""
    
    def test_init(self, mock_config_file, article_service, mock_scraper, mock_extractor):
        """測試初始化"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        assert crawler.config_file_name == mock_config_file
        assert crawler.article_service == article_service
        assert crawler.scraper == mock_scraper
        assert crawler.extractor == mock_extractor
        assert isinstance(crawler.articles_df, pd.DataFrame)
        assert crawler.articles_df.empty
        
    def test_fetch_article_links(self, mock_config_file, article_service, mock_scraper, mock_extractor):
        """測試抓取文章列表"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        articles_df = crawler.fetch_article_links()
        assert articles_df is not None
        assert not articles_df.empty
        assert len(articles_df) == 2
        assert list(articles_df['title']) == ["測試文章1", "測試文章2"]
        assert list(articles_df['is_ai_related']) == [True, False]
        mock_scraper.scrape_article_list.assert_called_once()
        
    def test_fetch_articles(self, mock_config_file, article_service, mock_scraper, mock_extractor):
        """測試抓取文章內容"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        # 先抓取文章列表
        articles_df = crawler.fetch_article_links()
        assert articles_df is not None
        assert not articles_df.empty
        
        # 模擬文章內容資料
        test_articles = [
            {
                "title": "測試文章1",
                "summary": "摘要1",
                "content": "文章內容1",
                "link": "https://www.bnext.com.tw/article/1",
                "category": "AI",
                "published_at": datetime.now(timezone.utc),
                "author": "作者1",
                "source": "bnext",
                "source_url": "https://www.bnext.com.tw",
                "article_type": "新聞",
                "tags": "AI",
                "is_ai_related": True,
                "is_scraped": True
            },
            {
                "title": "測試文章2",
                "summary": "摘要2",
                "content": "文章內容2",
                "link": "https://www.bnext.com.tw/article/2",
                "category": "technology",
                "published_at": datetime.now(timezone.utc),
                "author": "作者2",
                "source": "bnext",
                "source_url": "https://www.bnext.com.tw",
                "article_type": "新聞",
                "tags": "科技",
                "is_ai_related": False,
                "is_scraped": True
            }
        ]
        
        # 設置 mock_extractor 的回傳值和預期參數
        mock_extractor.batch_get_articles_content.return_value = test_articles
        
        # 測試抓取文章內容
        articles = crawler.fetch_articles()
        
        # 驗證 mock_extractor 被正確調用
        mock_extractor.batch_get_articles_content.assert_called_once_with(
            articles_df,  # 確保傳入的 DataFrame 正確
            crawler.site_config.article_settings["num_articles"],  # 從配置中獲取
            crawler.site_config.article_settings["ai_only"],  # 從配置中獲取
            crawler.site_config.article_settings["min_keywords"]  # 從配置中獲取
        )
        
        # 驗證結果
        assert articles is not None
        assert len(articles) == 2
        assert articles[0]['title'] == "測試文章1"
        assert articles[0]['content'] == "文章內容1"
        assert articles[1]['title'] == "測試文章2"
        assert articles[1]['content'] == "文章內容2"
        
    @patch('builtins.open', new_callable=mock_open)
    def test_execute_task(self, mock_file, mock_config_file, article_service, mock_scraper, mock_extractor):
        """測試完整的爬蟲任務執行"""
        # 設置 mock_file 的返回值
        mock_file.return_value.__enter__.return_value.read.return_value = json.dumps(TEST_CONFIG)
        
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        task_id = 1
        task_args = {
            "max_pages": 2,
            "ai_only": True,
            "num_articles": 5
        }
        
        # 執行任務
        crawler.execute_task(task_id, task_args)
        
        # 驗證任務狀態
        task_status = crawler.get_task_status(task_id)
        assert task_status["status"] == "completed"
        assert task_status["progress"] == 100
        
        # 驗證資料庫中的文章
        result = article_service.get_all_articles()
        assert result["success"] is True
        assert len(result["articles"]) == 2
        
        articles = result["articles"]
        assert articles[0].title == "測試文章1"
        assert articles[0].content == "文章內容1"
        assert articles[0].is_ai_related is True
        assert articles[1].title == "測試文章2"
        assert articles[1].content == "文章內容2"
        assert articles[1].is_ai_related is False
        
    def test_fetch_article_links_no_config(self, mock_config_file, article_service, mock_scraper, mock_extractor):
        """測試沒有配置時抓取文章列表"""
        with pytest.raises(ValueError, match="未找到配置文件"):
            crawler = BnextCrawler(
                config_file_name=None,
                article_service=article_service,
                scraper=mock_scraper,
                extractor=mock_extractor
            )
            crawler.fetch_article_links()
            
    def test_fetch_articles_no_links(self, mock_config_file, article_service, mock_scraper, mock_extractor):
        """測試沒有文章列表時抓取文章內容"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        articles = crawler.fetch_articles()
        assert articles is None
