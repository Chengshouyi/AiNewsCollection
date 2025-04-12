import pytest
import pandas as pd
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, mock_open
from src.crawlers.bnext_crawler import BnextCrawler
from src.crawlers.bnext_scraper import BnextScraper
from src.crawlers.bnext_content_extractor import BnextContentExtractor
from src.services.article_service import ArticleService
from src.models.articles_model import Articles, ArticleScrapeStatus
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
        "is_scraped": [False, False],
        "scrape_status": ["link_saved", "link_saved"],
        "scrape_error": [None, None],
        "last_scrape_attempt": [datetime.now(timezone.utc), datetime.now(timezone.utc)],
        "task_id": [None, None]
    })
    
    scraper.scrape_article_list.return_value = test_articles_df
    return scraper

@pytest.fixture
def mock_extractor():
    """模擬 BnextContentExtractor"""
    extractor = MagicMock(spec=BnextContentExtractor)
    
    current_time = datetime.now(timezone.utc)
    
    # 模擬文章內容資料
    test_articles = [
        {
            "title": "測試文章1",
            "summary": "摘要1",
            "content": "文章內容1",
            "link": "https://www.bnext.com.tw/article/1",
            "category": "AI",
            "published_at": current_time,
            "author": "作者1",
            "source": "bnext",
            "source_url": "https://www.bnext.com.tw",
            "article_type": "新聞",
            "tags": "AI",
            "is_ai_related": True,
            "is_scraped": True,
            "scrape_status": "content_scraped",
            "scrape_error": None,
            "last_scrape_attempt": current_time,
            "task_id": 123
        },
        {
            "title": "測試文章2",
            "summary": "摘要2",
            "content": "文章內容2",
            "link": "https://www.bnext.com.tw/article/2",
            "category": "technology",
            "published_at": current_time,
            "author": "作者2",
            "source": "bnext",
            "source_url": "https://www.bnext.com.tw",
            "article_type": "新聞",
            "tags": "科技",
            "is_ai_related": False,
            "is_scraped": True,
            "scrape_status": "content_scraped",
            "scrape_error": None,
            "last_scrape_attempt": current_time,
            "task_id": 123
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
        
        articles_df = crawler._fetch_article_links()
        assert articles_df is not None
        assert not articles_df.empty
        assert len(articles_df) == 2
        assert list(articles_df['title']) == ["測試文章1", "測試文章2"]
        assert list(articles_df['is_ai_related']) == [True, False]
        assert list(articles_df['scrape_status']) == ["link_saved", "link_saved"]
        assert all(pd.isna(articles_df['scrape_error']))
        assert all(pd.notna(articles_df['last_scrape_attempt']))
        assert all(pd.isna(articles_df['task_id']))
        mock_scraper.scrape_article_list.assert_called_once()
        
    def test_fetch_articles(self, mock_config_file, article_service, mock_scraper, mock_extractor):
        """測試抓取文章內容"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        # 設置文章列表資料
        crawler.articles_df = mock_scraper.scrape_article_list()
        
        # 測試抓取文章內容
        articles_content = crawler._fetch_articles()
        
        assert articles_content is not None
        assert len(articles_content) == 2
        assert articles_content[0]['title'] == "測試文章1"
        assert articles_content[0]['is_ai_related'] == True
        assert articles_content[0]['is_scraped'] == True
        assert articles_content[0]['scrape_status'] == "content_scraped"
        assert articles_content[0]['scrape_error'] is None
        assert articles_content[0]['last_scrape_attempt'] is not None
        assert articles_content[0]['task_id'] == 123
        
        mock_extractor.batch_get_articles_content.assert_called_once()
        
        # 檢查 articles_df 是否更新了爬取狀態
        assert crawler.articles_df.loc[0, 'scrape_status'] == "content_scraped"
        assert crawler.articles_df.loc[0, 'is_scraped'] == True

    def test_fetch_article_links_by_filter(self, mock_config_file, article_service, mock_scraper, mock_extractor):
        """測試根據過濾條件從資料庫獲取文章連結"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        # 模擬 article_service.advanced_search_articles 返回包含欄位的文章
        mock_article = MagicMock()
        mock_article.title = "DB文章標題"
        mock_article.link = "https://www.bnext.com.tw/article/db1"
        mock_article.is_scraped = False
        mock_article.scrape_status = ArticleScrapeStatus.LINK_SAVED
        mock_article.scrape_error = None
        mock_article.last_scrape_attempt = datetime.now(timezone.utc)
        mock_article.task_id = 456
        
        article_service.advanced_search_articles = MagicMock(return_value={
            "success": True,
            "articles": [mock_article],
            "message": "成功獲取文章"
        })
        
        # 使用新的方法名稱並傳入過濾條件
        articles_df = crawler._fetch_article_links_by_filter(
            is_scraped=False,
            task_id=456
        )
        
        # 驗證結果
        assert articles_df is not None
        assert not articles_df.empty
        assert len(articles_df) == 1
        assert articles_df.iloc[0]['title'] == "DB文章標題"
        assert articles_df.iloc[0]['link'] == "https://www.bnext.com.tw/article/db1"
        assert articles_df.iloc[0]['is_scraped'] == False
        assert articles_df.iloc[0]['scrape_status'] == "link_saved"
        assert articles_df.iloc[0]['scrape_error'] is None
        assert articles_df.iloc[0]['last_scrape_attempt'] is not None
        assert articles_df.iloc[0]['task_id'] == 456
        
        # 驗證 advanced_search_articles 是否被正確調用
        article_service.advanced_search_articles.assert_called_once_with(
            is_scraped=False,
            task_id=456
        )

    def test_fetch_article_links_by_filter_with_article_ids(self, mock_config_file, article_service, mock_scraper, mock_extractor):
        """測試使用文章ID從資料庫獲取文章連結"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        # 模擬 article_service.get_article_by_id 返回文章
        mock_article = MagicMock()
        mock_article.id = 123
        mock_article.title = "根據ID獲取的文章"
        mock_article.link = "https://www.bnext.com.tw/article/123"
        mock_article.is_scraped = False
        mock_article.scrape_status = ArticleScrapeStatus.LINK_SAVED
        mock_article.scrape_error = None
        mock_article.last_scrape_attempt = datetime.now(timezone.utc)
        mock_article.task_id = 456
        
        article_service.get_article_by_id = MagicMock(return_value={
            "success": True,
            "article": mock_article,
            "message": "成功獲取文章"
        })
        
        # 使用新的方法名稱並傳入文章ID
        articles_df = crawler._fetch_article_links_by_filter(
            article_ids=[123]
        )
        
        # 驗證結果
        assert articles_df is not None
        assert not articles_df.empty
        assert len(articles_df) == 1
        assert articles_df.iloc[0]['title'] == "根據ID獲取的文章"
        assert articles_df.iloc[0]['link'] == "https://www.bnext.com.tw/article/123"
        assert articles_df.iloc[0]['is_scraped'] == False
        assert articles_df.iloc[0]['scrape_status'] == "link_saved"
        
        # 驗證 get_article_by_id 是否被正確調用
        article_service.get_article_by_id.assert_called_once_with(123)

    def test_fetch_article_links_by_filter_with_links(self, mock_config_file, article_service, mock_scraper, mock_extractor):
        """測試使用文章連結從資料庫獲取文章"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        link = "https://www.bnext.com.tw/article/link1"
        
        # 模擬 article_service.get_article_by_link 返回文章
        mock_article = MagicMock()
        mock_article.title = "根據連結獲取的文章"
        mock_article.link = link
        mock_article.is_scraped = True
        mock_article.scrape_status = ArticleScrapeStatus.CONTENT_SCRAPED
        mock_article.scrape_error = None
        mock_article.last_scrape_attempt = datetime.now(timezone.utc)
        mock_article.task_id = 789
        
        article_service.get_article_by_link = MagicMock(return_value={
            "success": True,
            "article": mock_article,
            "message": "成功獲取文章"
        })
        
        # 使用新的方法名稱並傳入文章連結
        articles_df = crawler._fetch_article_links_by_filter(
            article_links=[link]
        )
        
        # 驗證結果
        assert articles_df is not None
        assert not articles_df.empty
        assert len(articles_df) == 1
        assert articles_df.iloc[0]['title'] == "根據連結獲取的文章"
        assert articles_df.iloc[0]['link'] == link
        assert articles_df.iloc[0]['is_scraped'] == True
        assert articles_df.iloc[0]['scrape_status'] == "content_scraped"
        
        # 驗證 get_article_by_link 是否被正確調用
        article_service.get_article_by_link.assert_called_once_with(link)

    def test_fetch_article_links_by_filter_not_found_link(self, mock_config_file, article_service, mock_scraper, mock_extractor):
        """測試處理資料庫中不存在的文章連結"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        link = "https://www.bnext.com.tw/article/notfound"
        
        # 模擬 article_service.get_article_by_link 返回未找到文章
        article_service.get_article_by_link = MagicMock(return_value={
            "success": False,
            "article": None,
            "message": "未找到文章"
        })
        
        # 使用新的方法名稱並傳入不存在的文章連結
        articles_df = crawler._fetch_article_links_by_filter(
            article_links=[link]
        )
        
        # 驗證結果 - 應該創建一個簡單的記錄
        assert articles_df is not None
        assert not articles_df.empty
        assert len(articles_df) == 1
        assert articles_df.iloc[0]['link'] == link
        assert articles_df.iloc[0]['title'] == ''
        assert articles_df.iloc[0]['is_scraped'] == False
        assert articles_df.iloc[0]['scrape_status'] == 'pending'
        
        # 驗證 get_article_by_link 是否被正確調用
        article_service.get_article_by_link.assert_called_once_with(link)

    def test_fetch_article_links_by_filter_error(self, mock_config_file, article_service, mock_scraper, mock_extractor):
        """測試獲取文章連結時發生錯誤"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        # 模擬 article_service.advanced_search_articles 拋出異常
        article_service.advanced_search_articles = MagicMock(side_effect=Exception("資料庫查詢錯誤"))
        
        # 使用新的方法名稱並檢查錯誤處理
        articles_df = crawler._fetch_article_links_by_filter(
            is_scraped=False
        )
        
        # 驗證結果 - 應該返回None
        assert articles_df is None
        
        # 驗證 advanced_search_articles 是否被調用
        article_service.advanced_search_articles.assert_called_once()

    def test_fetch_article_links_no_config(self, mock_config_file, article_service, mock_scraper, mock_extractor):
        """測試沒有配置時抓取文章列表"""
        with pytest.raises(ValueError, match="未找到配置文件"):
            crawler = BnextCrawler(
                config_file_name=None,
                article_service=article_service,
                scraper=mock_scraper,
                extractor=mock_extractor
            )
            crawler._fetch_article_links()
            
    def test_fetch_articles_no_links(self, mock_config_file, article_service, mock_scraper, mock_extractor):
        """測試沒有文章列表時抓取文章內容"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        articles = crawler._fetch_articles()
        assert articles is None

    def test_update_config(self, mock_config_file, article_service, mock_scraper, mock_extractor):
        """測試更新爬蟲設定"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        # 驗證 update_config 方法調用了 scraper 和 extractor 的 update_config 方法
        crawler._update_config()
        
        mock_scraper.update_config.assert_called_once_with(crawler.site_config)
        mock_extractor.update_config.assert_called_once_with(crawler.site_config)

    def test_fetch_article_links_with_params(self, mock_config_file, article_service, mock_scraper, mock_extractor):
        """測試帶參數抓取文章列表"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        # 設置不同的全局參數
        custom_params = {
            "max_pages": 5,
            "ai_only": False,
            "min_keywords": 2
        }
        crawler.global_params = custom_params
        
        # 執行抓取
        crawler._fetch_article_links()
        
        # 驗證使用了正確的參數呼叫 scraper.scrape_article_list
        mock_scraper.scrape_article_list.assert_called_once_with(
            custom_params["max_pages"], 
            custom_params["ai_only"],
            custom_params["min_keywords"]
        )

    def test_fetch_articles_with_params(self, mock_config_file, article_service, mock_scraper, mock_extractor):
        """測試帶參數抓取文章內容"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        # 設置文章列表資料
        crawler.articles_df = mock_scraper.scrape_article_list()
        
        # 設置不同的全局參數
        custom_params = {
            "num_articles": 7,
            "ai_only": False,
            "min_keywords": 1
        }
        crawler.global_params = custom_params
        
        # 執行抓取
        crawler._fetch_articles()
        
        # 驗證使用了正確的參數呼叫 extractor.batch_get_articles_content
        mock_extractor.batch_get_articles_content.assert_called_once_with(
            crawler.articles_df,
            custom_params["num_articles"], 
            custom_params["ai_only"],
            custom_params["min_keywords"]
        )

    def test_fetch_article_links_empty_result(self, mock_config_file, article_service, mock_scraper, mock_extractor):
        """測試抓取文章列表返回空結果"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        # 設置 scrape_article_list 返回空 DataFrame
        mock_scraper.scrape_article_list.return_value = pd.DataFrame()
        
        # 執行抓取
        result = crawler._fetch_article_links()
        
        # 驗證結果為 None
        assert result is None
        mock_scraper.scrape_article_list.assert_called_once()

    def test_fetch_articles_with_error_handling(self, mock_config_file, article_service, mock_scraper, mock_extractor):
        """測試抓取文章內容時處理錯誤信息"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        # 設置文章列表資料
        crawler.articles_df = mock_scraper.scrape_article_list()
        
        # 設置 batch_get_articles_content 返回帶錯誤信息的文章
        current_time = datetime.now(timezone.utc)
        mock_extractor.batch_get_articles_content.return_value = [
            {
                "title": "測試文章1",
                "link": "https://www.bnext.com.tw/article/1",
                "is_scraped": True,
                "scrape_status": "content_scraped",
                "scrape_error": None,
                "last_scrape_attempt": current_time,
                "task_id": 123
            },
            {
                "title": "測試文章2",
                "link": "https://www.bnext.com.tw/article/2",
                "is_scraped": False,
                "scrape_status": "scrape_failed",
                "scrape_error": "無法抓取內容",
                "last_scrape_attempt": current_time,
                "task_id": 123
            }
        ]
        
        # 執行抓取
        articles = crawler._fetch_articles()
        
        # 驗證文章狀態正確更新到 DataFrame
        assert crawler.articles_df.loc[0, 'scrape_status'] == "content_scraped"
        assert crawler.articles_df.loc[0, 'is_scraped'] == True
        assert crawler.articles_df.loc[0, 'scrape_error'] is None
        
        assert crawler.articles_df.loc[1, 'scrape_status'] == "scrape_failed"
        assert crawler.articles_df.loc[1, 'is_scraped'] == False
        assert crawler.articles_df.loc[1, 'scrape_error'] == "無法抓取內容"
        
        assert articles is not None
        assert len(articles) == 2

    def test_retry_operation_in_fetch_article_links(self, mock_config_file, article_service, mock_scraper, mock_extractor):
        """測試在抓取文章列表時重試操作"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        # 模擬 retry_operation 方法
        mock_retry = MagicMock()
        crawler.retry_operation = mock_retry
        
        # 執行抓取
        crawler._fetch_article_links()
        
        # 驗證 retry_operation 被調用
        mock_retry.assert_called_once()

    def test_retry_operation_in_fetch_articles(self, mock_config_file, article_service, mock_scraper, mock_extractor):
        """測試在抓取文章內容時重試操作"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        # 設置文章列表資料
        crawler.articles_df = mock_scraper.scrape_article_list()
        
        # 模擬 retry_operation 方法
        mock_retry = MagicMock()
        crawler.retry_operation = mock_retry
        
        # 執行抓取
        crawler._fetch_articles()
        
        # 驗證 retry_operation 被調用
        mock_retry.assert_called_once()
