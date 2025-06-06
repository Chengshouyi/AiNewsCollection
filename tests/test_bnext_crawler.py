"""測試 BnextCrawler 類及其相關功能的單元測試。"""

# 標準函式庫
import json
import logging
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, mock_open
import os

# 第三方函式庫
import pandas as pd
import pytest

# 本地應用程式 imports
from src.crawlers.bnext_content_extractor import BnextContentExtractor
from src.crawlers.bnext_crawler import BnextCrawler
from src.crawlers.bnext_scraper import BnextScraper
from src.database.database_manager import DatabaseManager
from src.models.articles_model import Articles, ArticleScrapeStatus
from src.models.base_model import Base
from src.services.article_service import ArticleService
  # 使用統一的 logger

# flake8: noqa: F811
# pylint: disable=redefined-outer-name

# 使用統一的 logger
logger = logging.getLogger(__name__)  # 使用統一的 logger

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
    """模擬配置文件及其存在性"""
    # --- Mock open ---
    config_content = json.dumps(TEST_CONFIG)
    # 使用 mock_open 替代 io.StringIO，更符合文件操作的模擬
    mock_file = mock_open(read_data=config_content)
    monkeypatch.setattr("builtins.open", mock_file)

    # --- Mock os.path.exists ---
    original_exists = os.path.exists
    def mock_exists(path):
        """模擬 os.path.exists，對測試配置文件返回 True"""
        # 判斷是否是期望的測試配置文件路徑
        # 這裡假設 _load_site_config 會檢查以 "test_bnext_config.json" 結尾的路徑
        if isinstance(path, str) and path.endswith("test_bnext_config.json"):
            # logger.debug(f"Mocking os.path.exists for: {path} -> True") # 可選的調試日誌
            return True
        # 對其他路徑，使用原始的 os.path.exists 函數
        # logger.debug(f"Mocking os.path.exists for: {path} -> delegating to original") # 可選的調試日誌
        return original_exists(path)

    monkeypatch.setattr("os.path.exists", mock_exists)

    # 返回檔名供測試使用
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

@pytest.fixture(scope="function")
def mock_article_service():
    """模擬 ArticleService"""
    service = MagicMock(spec=ArticleService)
    # 預設返回成功但沒有數據，或失敗，避免影響不需要模擬的測試
    service.find_articles_advanced = MagicMock()
    service.get_article_by_link = MagicMock()
    service.find_articles_advanced.return_value = {
        "success": True,
        "resultMsg": SimpleNamespace(items=[]), # 使用 SimpleNamespace 模擬物件屬性
        "message": "未找到文章"
    }
    service.get_article_by_link.return_value = {
        "success": False,
        "article": None,
        "message": "未找到文章"
    }
    return service

@pytest.fixture(scope="function")
def initialized_db_manager(db_manager_for_test: DatabaseManager):
    """
    提供一個初始化好的 DatabaseManager 實例。
    確保資料表已創建，並在每次測試前清理 Articles 資料表。
    依賴 conftest.py 中的 db_manager_for_test。
    """
    # 確保資料表存在 (假設 db_manager_for_test 會處理引擎)
    try:
        Base.metadata.create_all(db_manager_for_test.engine)
    except Exception as e:
        # 可以添加日誌記錄
        print(f"創建資料表時出錯: {e}") # 暫時用 print 替代 logger
        raise

    # 在每次測試前清理 Articles 資料表
    try:
        with db_manager_for_test.session_scope() as session:
            session.query(Articles).delete()
            session.commit()
    except Exception as e:
        print(f"清理 Articles 資料表時出錯: {e}") # 暫時用 print 替代 logger
        # 即使清理失敗，也繼續執行測試

    yield db_manager_for_test
    # 清理工作應由 db_manager_for_test 或其相關的 session fixture 處理

@pytest.fixture(scope="function")
def article_service(initialized_db_manager: DatabaseManager):
    """創建ArticleService實例"""
    # 直接使用傳入的 initialized_db_manager
    service = ArticleService(initialized_db_manager)
    yield service
    # 通常不需要在此處清理，由 initialized_db_manager 處理

class TestBnextCrawler:
    """BnextCrawler 的測試類"""
    
    def test_init(self, mock_config_file, mock_article_service, mock_scraper, mock_extractor):
        """測試初始化"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=mock_article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        assert crawler.config_file_name == mock_config_file
        assert crawler.article_service == mock_article_service
        assert crawler.scraper == mock_scraper
        assert crawler.extractor == mock_extractor
        assert isinstance(crawler.articles_df, pd.DataFrame)
        assert crawler.articles_df.empty
        
    def test_fetch_article_links(self, mock_config_file, mock_article_service, mock_scraper, mock_extractor):
        """測試抓取文章列表"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=mock_article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        articles_df = crawler._fetch_article_links(task_id=123)
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
        
    def test_fetch_articles(self, mock_config_file, mock_article_service, mock_scraper, mock_extractor):
        """測試抓取文章內容"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=mock_article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        # 設置 batch_get_articles_content 的返回值，提供兩篇文章
        current_time = datetime.now(timezone.utc)
        mock_extractor.batch_get_articles_content.return_value = [
            {
                'title': '測試文章1',
                'link': 'https://example.com/1',
                'is_scraped': True,
                'scrape_status': 'content_scraped',
                'scrape_error': None,
                'last_scrape_attempt': current_time,
                'task_id': 123,
                'is_ai_related': True  # 添加測試中需要驗證的欄位
            },
            {
                'title': '測試文章2',
                'link': 'https://example.com/2',
                'is_scraped': True,
                'scrape_status': 'content_scraped',
                'scrape_error': None,
                'last_scrape_attempt': current_time,
                'task_id': 123,
                'is_ai_related': True
            }
        ]
        
        # 設置文章列表資料
        crawler.articles_df = mock_scraper.scrape_article_list()
        
        # 測試抓取文章內容
        articles_content = crawler._fetch_articles(task_id=123)
        
        # 驗證結果
        assert articles_content is not None
        assert len(articles_content) == 2  # 現在應該能通過這個測試
        assert articles_content[0]['title'] == "測試文章1"
        assert articles_content[0]['is_ai_related'] == True
        assert articles_content[0]['is_scraped'] == True
        assert articles_content[0]['scrape_status'] == "content_scraped"
        assert articles_content[0]['scrape_error'] is None
        assert articles_content[0]['last_scrape_attempt'] is not None
        assert articles_content[0]['task_id'] == 123
        
        # 驗證第二篇文章
        assert articles_content[1]['title'] == "測試文章2"
        
        # 驗證 batch_get_articles_content 被調用
        mock_extractor.batch_get_articles_content.assert_called_once()
        
        # 檢查 DataFrame 更新
        assert crawler.articles_df.loc[0, 'scrape_status'] == "content_scraped"
        assert crawler.articles_df.loc[0, 'is_scraped'] == True
        assert crawler.articles_df.loc[1, 'scrape_status'] == "content_scraped"
        assert crawler.articles_df.loc[1, 'is_scraped'] == True

    def test_fetch_article_links_by_filter(self, mock_config_file, mock_article_service, mock_scraper, mock_extractor):
        """測試根據過濾條件從資料庫獲取文章連結"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=mock_article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        # --- 修改模擬方式 ---
        # 創建一個類似 Pydantic 模型行為的物件 (或直接用字典)
        mock_db_article_data = {
            "id": 1, # 假設有 ID
            "title": "DB文章標題",
            "link": "https://www.bnext.com.tw/article/db1",
            "summary": "DB摘要",
            "content": "DB內容",
            "published_at": datetime.now(timezone.utc),
            "category": "AI",
            "author": "DB作者",
            "source": "bnext",
            "source_url": "https://www.bnext.com.tw",
            "article_type": "新聞",
            "tags": "DB,AI",
            "is_ai_related": True,
            "is_scraped": False,
            "scrape_status": ArticleScrapeStatus.LINK_SAVED.value, # 直接使用字串值
            "scrape_error": None,
            "last_scrape_attempt": datetime.now(timezone.utc),
            "task_id": 456
        }
        # 讓 mock 物件能透過 . 訪問屬性，並能被 vars() 轉換
        mock_db_article_obj = SimpleNamespace(**mock_db_article_data)

        # 設置 find_articles_advanced 的返回值
        mock_article_service.find_articles_advanced.return_value = {
            "success": True,
            "resultMsg": SimpleNamespace( # 使用 SimpleNamespace
                items=[mock_db_article_obj] # 包含模擬物件
            ),
            "message": "成功獲取文章"
        }
        # --- 結束修改 ---

        # 使用新的方法名稱並傳入過濾條件
        articles_df = crawler._fetch_article_links_by_filter(
            is_scraped=False,
            task_id=456
        )
        
        # 驗證結果
        assert articles_df is not None
        assert not articles_df.empty
        assert len(articles_df) == 1
        assert articles_df.iloc[0]['title'] == mock_db_article_data['title']
        assert articles_df.iloc[0]['link'] == mock_db_article_data['link']
        assert articles_df.iloc[0]['is_scraped'] == mock_db_article_data['is_scraped']
        assert articles_df.iloc[0]['scrape_status'] == mock_db_article_data['scrape_status']
        assert articles_df.iloc[0]['scrape_error'] is mock_db_article_data['scrape_error']
        assert pd.notna(articles_df.iloc[0]['last_scrape_attempt'])
        assert articles_df.iloc[0]['task_id'] == mock_db_article_data['task_id']
        
        # 驗證 find_articles_advanced 是否被正確調用
        mock_article_service.find_articles_advanced.assert_called_once_with(
            is_scraped=False,
            task_id=456,
            page=1,
            per_page=10
        )

    def test_fetch_article_links_by_filter_with_links(self, mock_config_file, mock_article_service, mock_scraper, mock_extractor):
        """測試使用文章連結從資料庫獲取文章"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=mock_article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        link = "https://www.bnext.com.tw/article/link1"
        
        # --- 修改模擬方式 ---
        mock_link_article_data = {
            "id": 2,
            "title": "根據連結獲取的文章",
            "link": link,
            "summary": "連結摘要",
            "content": "連結內容",
            "published_at": datetime.now(timezone.utc),
            "category": "Technology",
            "author": "連結作者",
            "source": "bnext",
            "source_url": "https://www.bnext.com.tw",
            "article_type": "分析",
            "tags": "Tech",
            "is_ai_related": False,
            "is_scraped": True,
            "scrape_status": ArticleScrapeStatus.CONTENT_SCRAPED.value,
            "scrape_error": None,
            "last_scrape_attempt": datetime.now(timezone.utc),
            "task_id": 789
        }
        mock_link_article_obj = SimpleNamespace(**mock_link_article_data)

        # 設置 get_article_by_link 的返回值
        mock_article_service.get_article_by_link.return_value = {
            "success": True,
            "article": mock_link_article_obj,
            "message": "成功獲取文章"
        }
        # --- 結束修改 ---

        # 使用新的方法名稱並傳入文章連結
        articles_df = crawler._fetch_article_links_by_filter(
            article_links=[link],
            task_id=123
        )
        
        # 驗證結果
        assert articles_df is not None
        assert not articles_df.empty
        assert len(articles_df) == 1
        assert articles_df.iloc[0]['title'] == mock_link_article_data['title']
        assert articles_df.iloc[0]['link'] == mock_link_article_data['link']
        assert articles_df.iloc[0]['is_scraped'] == mock_link_article_data['is_scraped']
        assert articles_df.iloc[0]['scrape_status'] == mock_link_article_data['scrape_status']
        
        # 驗證 get_article_by_link 是否被正確調用
        mock_article_service.get_article_by_link.assert_called_once_with(link)

    def test_fetch_article_links_by_filter_not_found_link(self, mock_config_file, mock_article_service, mock_scraper, mock_extractor):
        """測試處理資料庫中不存在的文章連結"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=mock_article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        link = "https://www.bnext.com.tw/article/notfound"
    

        # 使用新的方法名稱並傳入不存在的文章連結
        articles_df = crawler._fetch_article_links_by_filter(
            article_links=[link],
            task_id=123
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
        mock_article_service.get_article_by_link.assert_called_once_with(link)

    def test_fetch_article_links_by_filter_error(self, mock_config_file, mock_article_service, mock_scraper, mock_extractor):
        """測試獲取文章連結時發生錯誤"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=mock_article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        # --- 修改模擬方式 ---
        # 直接在測試中設置 side_effect，確保是正確的 mock 物件
        mock_article_service.find_articles_advanced.side_effect = Exception("資料庫查詢錯誤")
        # --- 結束修改 ---

        # 使用新的方法名稱並檢查錯誤處理
        articles_df = crawler._fetch_article_links_by_filter(
            is_scraped=False,
            task_id=123
        )
        
        # --- 驗證結果 ---
        # 根據 base_crawler 的 except 區塊，發生異常應返回 None
        assert articles_df is None
        # --- 結束驗證 ---

        # 驗證 find_articles_advanced 是否被調用
        mock_article_service.find_articles_advanced.assert_called_once()

    def test_fetch_article_links_no_config(self, mock_article_service, mock_scraper, mock_extractor):
        """測試沒有配置時抓取文章列表"""
        with pytest.raises(ValueError, match="未指定配置文件名稱"):
            crawler = BnextCrawler(
                config_file_name=None,
                article_service=mock_article_service,
                scraper=mock_scraper,
                extractor=mock_extractor
            )

    def test_fetch_articles_no_links(self, mock_config_file, mock_article_service, mock_scraper, mock_extractor):
        """測試沒有文章列表時抓取文章內容"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=mock_article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        articles = crawler._fetch_articles(task_id=123)
        assert articles is None

    def test_update_config(self, mock_config_file, mock_article_service, mock_scraper, mock_extractor):
        """測試更新爬蟲設定"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=mock_article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        # 驗證 update_config 方法調用了 scraper 和 extractor 的 update_config 方法
        crawler._update_config()
        
        mock_scraper.update_config.assert_called_once_with(crawler.site_config)
        mock_extractor.update_config.assert_called_once_with(crawler.site_config)

    def test_fetch_article_links_with_params(self, mock_config_file, mock_article_service, mock_scraper, mock_extractor):
        """測試帶參數抓取文章列表"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=mock_article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        # 設置不同的全局參數
        custom_params = {
            "max_pages": 5,
            "ai_only": False,
            "min_keywords": 2
        }
        crawler.global_params.update(custom_params)
        
        # 執行抓取
        crawler._fetch_article_links(task_id=123)
        
        # 驗證使用了正確的參數呼叫 scraper.scrape_article_list
        mock_scraper.scrape_article_list.assert_called_once_with(
            custom_params["max_pages"], 
            custom_params["ai_only"],
            custom_params["min_keywords"]
        )

    def test_fetch_articles_with_params(self, mock_config_file, mock_article_service, mock_scraper, mock_extractor):
        """測試帶參數抓取文章內容"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=mock_article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        # 設置返回值
        mock_extractor.batch_get_articles_content.return_value = [
            {
                'title': '測試文章1',
                'link': 'https://example.com/1',
                'is_scraped': True,
                'scrape_status': 'content_scraped',
                'scrape_error': None,
                'last_scrape_attempt': datetime.now(timezone.utc),
                'task_id': 123
            }
        ]
        
        # 設置文章列表資料
        crawler.articles_df = mock_scraper.scrape_article_list()
        
        # 設置不同的全局參數
        custom_params = {
            "num_articles": 7,
            "ai_only": False,
            "min_keywords": 1
        }
        crawler.global_params.update(custom_params)
        
        # 執行抓取
        crawler._fetch_articles(task_id=123)
        
        # 驗證調用參數
        mock_extractor.batch_get_articles_content.assert_called_once_with(
            crawler.articles_df,
            num_articles=custom_params["num_articles"],
            ai_only=custom_params["ai_only"],
            min_keywords=custom_params["min_keywords"],
            is_limit_num_articles=False
        )

    def test_fetch_article_links_empty_result(self, mock_config_file, mock_article_service, mock_scraper, mock_extractor):
        """測試抓取文章列表返回空結果"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=mock_article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        # 設置 scrape_article_list 返回空 DataFrame
        mock_scraper.scrape_article_list.return_value = pd.DataFrame()
        
        # 執行抓取
        result = crawler._fetch_article_links(task_id=123)
        
        # 驗證結果為 None
        assert result is None
        mock_scraper.scrape_article_list.assert_called_once()

    def test_fetch_articles_with_error_handling(self, mock_config_file, mock_article_service, mock_scraper, mock_extractor):
        """測試抓取文章內容時處理錯誤信息"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=mock_article_service,
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
                "is_scraped": True,  # 使用 Python 布林值
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
        articles = crawler._fetch_articles(task_id=123)
        
        # 驗證文章狀態正確更新到 DataFrame
        assert crawler.articles_df.loc[0, 'scrape_status'] == ArticleScrapeStatus.CONTENT_SCRAPED.value
        assert crawler.articles_df.loc[0, 'is_scraped'] == True
        assert crawler.articles_df.loc[0, 'scrape_error'] is None
        
        assert crawler.articles_df.loc[1, 'scrape_status'] == ArticleScrapeStatus.FAILED.value
        assert crawler.articles_df.loc[1, 'is_scraped'] == False
        assert crawler.articles_df.loc[1, 'scrape_error'] == "無法抓取內容"
        
        assert articles is not None
        assert len(articles) == 2

    def test_retry_operation_in_fetch_article_links(self, mock_config_file, mock_article_service, mock_scraper, mock_extractor):
        """測試在抓取文章列表時重試操作"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=mock_article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        # 模擬 retry_operation 方法
        with patch.object(crawler, 'retry_operation', wraps=crawler.retry_operation) as mock_retry:
            crawler._fetch_article_links(task_id=123)
            
        # 驗證 retry_operation 被調用
        mock_retry.assert_called()

    def test_retry_operation_in_fetch_articles(self, mock_config_file, mock_article_service, mock_scraper, mock_extractor):
        """測試在抓取文章內容時重試操作"""
        crawler = BnextCrawler(
            config_file_name=mock_config_file,
            article_service=mock_article_service,
            scraper=mock_scraper,
            extractor=mock_extractor
        )
        
        # 設置 mock_extractor 在第一次調用時拋出異常，第二次成功
        mock_extractor.batch_get_articles_content.side_effect = [
            Exception("測試異常"),
            [{'title': '測試文章1', 'is_scraped': True}]
        ]
        
        # 設置文章列表資料
        crawler.articles_df = mock_scraper.scrape_article_list()
        
        # 執行抓取
        articles = crawler._fetch_articles(task_id=123)
        
        # 驗證 retry_operation 被調用
        assert mock_extractor.batch_get_articles_content.call_count == 2
        assert articles is not None
        assert len(articles) == 1
        assert articles[0]['title'] == '測試文章1'
        assert articles[0]['is_scraped'] == True
