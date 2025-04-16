import pytest
from unittest.mock import MagicMock

# 導入被測試的模組
from src.services.crawlers_service import CrawlersService
from src.models.crawlers_model import Crawlers
from src.crawlers.crawler_factory import CrawlerFactory

class TestCrawlerFactory:
    @pytest.fixture
    def mock_article_service(self):
        """建立模擬的 ArticleService"""
        return MagicMock()
    
    @pytest.fixture
    def mock_crawlers_service(self):
        """建立模擬的 CrawlersService"""
        mock_service = MagicMock(spec=CrawlersService)
        return mock_service
    
    @pytest.fixture
    def sample_crawlers(self):
        """建立測試用的爬蟲模型列表"""
        crawler1 = MagicMock(spec=Crawlers)
        crawler1.crawler_name = "TestCrawler"
        crawler1.crawler_type = "test"
        crawler1.config_file_name = "test_config.json"
        crawler1.is_active = True
        
        crawler2 = MagicMock(spec=Crawlers)
        crawler2.crawler_name = "NewsCrawler"
        crawler2.crawler_type = "news"
        crawler2.config_file_name = "news_config.json"
        crawler2.is_active = True
        
        return [crawler1, crawler2]
    
    @pytest.fixture
    def setup_crawler_factory(self, mock_crawlers_service, sample_crawlers):
        """設置 CrawlerFactory 的測試環境"""
        # 重置爬蟲工廠狀態
        CrawlerFactory._crawler_names = {}
        
        # 模擬 get_active_crawlers 方法返回樣本數據
        mock_crawlers_service.get_active_crawlers.return_value = {
            'success': True,
            'crawlers': sample_crawlers
        }
        
        yield mock_crawlers_service
        
        # 測試後清理
        CrawlerFactory._crawler_names = {}
    
    def test_initialize(self, setup_crawler_factory, sample_crawlers, monkeypatch, mock_article_service):
        """測試 CrawlerFactory 的初始化功能"""
        mock_service = setup_crawler_factory
        
        # 模擬動態導入模組
        mock_module = MagicMock()
        mock_test_crawler = MagicMock()
        mock_news_crawler = MagicMock()
        
        # 設置 mock 模組的屬性
        setattr(mock_module, "TestCrawler", mock_test_crawler)
        setattr(mock_module, "NewsCrawler", mock_news_crawler)
        
        # 修改 mock_import 函數以接受任意參數
        def mock_import(*args, **kwargs):
            return mock_module
        
        # 使用 monkeypatch 替換 __import__ 函數
        monkeypatch.setattr("builtins.__import__", mock_import)
        
        # 執行初始化
        CrawlerFactory.initialize(mock_service, article_service=mock_article_service)
        
        # 驗證是否調用了 get_active_crawlers
        mock_service.get_active_crawlers.assert_called_once()
        
        # 驗證爬蟲是否被正確註冊
        assert "TestCrawler" in CrawlerFactory._crawler_names
        assert "NewsCrawler" in CrawlerFactory._crawler_names
        assert CrawlerFactory._crawler_names["TestCrawler"]["class"] == mock_test_crawler
        assert CrawlerFactory._crawler_names["NewsCrawler"]["class"] == mock_news_crawler
    
    def test_initialize_exception(self, setup_crawler_factory, mock_article_service):
        """測試初始化過程中的異常處理"""
        mock_service = setup_crawler_factory
        
        # 模擬 get_active_crawlers 拋出異常
        mock_service.get_active_crawlers.side_effect = Exception("測試異常")
        
        # 驗證異常是否被正確傳播
        with pytest.raises(Exception) as excinfo:
            CrawlerFactory.initialize(mock_service, article_service=mock_article_service)
            
        # 檢查異常訊息是否包含預期的文字
        assert "測試異常" in str(excinfo.value)
    
    def test_get_crawler(self, setup_crawler_factory, monkeypatch, mock_article_service):
        """測試獲取爬蟲實例功能"""
        mock_service = setup_crawler_factory
        
        # 模擬動態導入
        mock_module = MagicMock()
        mock_crawler_class = MagicMock()
        mock_crawler_instance = MagicMock()
        
        # 設置 mock_crawler_class 的返回值
        mock_crawler_class.return_value = mock_crawler_instance
        
        # 設置 mock 模組的屬性
        setattr(mock_module, "TestCrawler", mock_crawler_class)
        
        # 修改這裡的 mock_import
        def mock_import(*args, **kwargs):
            return mock_module
        
        monkeypatch.setattr("builtins.__import__", mock_import)
        
        # 初始化工廠
        CrawlerFactory.initialize(mock_service, article_service=mock_article_service)
        
        # 獲取爬蟲實例
        crawler = CrawlerFactory.get_crawler("TestCrawler")
        
        # 驗證爬蟲類別是否被正確實例化
        mock_crawler_class.assert_called_once_with(
            config_file_name="test_config.json",
            article_service=mock_article_service
        )
        assert crawler == mock_crawler_instance
    
    def test_get_crawler_not_initialized(self):
        """測試在未初始化的情況下獲取爬蟲實例"""
        # 重置爬蟲工廠狀態
        CrawlerFactory._crawler_names = {}
        
        # 驗證是否拋出正確的異常
        with pytest.raises(ValueError, match="未找到 TestCrawler 爬蟲"):
            CrawlerFactory.get_crawler("TestCrawler")
    
    def test_get_crawler_not_found(self, setup_crawler_factory, monkeypatch, mock_article_service):
        """測試獲取不存在的爬蟲實例"""
        mock_service = setup_crawler_factory
        
        # 模擬動態導入
        mock_module = MagicMock()
        monkeypatch.setattr("builtins.__import__", lambda name, fromlist: mock_module)
        
        # 初始化工廠
        CrawlerFactory.initialize(mock_service, article_service=mock_article_service)
        
        # 驗證是否拋出正確的異常
        with pytest.raises(ValueError, match="未找到 NonExistCrawler 爬蟲"):
            CrawlerFactory.get_crawler("NonExistCrawler")
    
    def test_list_available_crawlers(self, setup_crawler_factory, monkeypatch, mock_article_service):
        """測試列出可用爬蟲功能"""
        mock_service = setup_crawler_factory
        
        # 模擬動態導入
        mock_module = MagicMock()
        setattr(mock_module, "TestCrawler", MagicMock())
        setattr(mock_module, "NewsCrawler", MagicMock())
        
        # 修改這裡的 lambda 函數
        monkeypatch.setattr("builtins.__import__", lambda *args, **kwargs: mock_module)
        
        # 初始化工廠
        CrawlerFactory.initialize(mock_service, article_service=mock_article_service)
        
        # 獲取可用爬蟲列表
        available_crawlers = CrawlerFactory.list_available_crawler_types()
        
        # 驗證列表是否包含預期的爬蟲
        assert sorted(available_crawlers) == sorted(["TestCrawler", "NewsCrawler"])