import pytest
from unittest.mock import patch
from src.crawlers.configs.base_config import DEFAULT_HEADERS
from src.crawlers.configs.site_config import SiteConfig

class TestSiteConfig:
    """測試 SiteConfig 類別的功能"""

    def test_default_initialization(self):
        """測試使用默認值創建 SiteConfig 實例"""
        config = SiteConfig(name="test_site")
        
        assert config.name == "test_site"
        assert config.base_url == "https://www.bnext.com.tw"
        assert config.categories == ["ai", "tech", "iot", "smartmedical", "smartcity", "cloudcomputing", "security"]
        assert config.crawler_settings == {'max_retries': 3, 'retry_delay': 5, 'timeout': 10}
        assert config.headers == DEFAULT_HEADERS
        assert config.list_url_template == "{base_url}/categories/{category}"
        assert config.valid_domains == ["https://www.bnext.com.tw"]
        assert config.url_file_extensions == ['.html', '.htm']
        assert config.date_format == '%Y/%m/%d %H:%M'

    def test_custom_initialization(self):
        """測試使用自定義值創建 SiteConfig 實例"""
        custom_config = SiteConfig(
            name="custom_site",
            base_url="https://example.com",
            list_url_template="https://example.com/{category}/list",
            categories=["news", "blog"],
            crawler_settings={'max_retries': 5, 'timeout': 15},
            headers={"User-Agent": "CustomAgent"},
            valid_domains=["https://example.com", "https://blog.example.com"],
            url_patterns=["/article/", "/post/"],
            url_file_extensions=[".php", ".asp"]
        )
        
        assert custom_config.name == "custom_site"
        assert custom_config.base_url == "https://example.com"
        assert custom_config.list_url_template == "https://example.com/{category}/list"
        assert custom_config.categories == ["news", "blog"]
        assert custom_config.crawler_settings == {'max_retries': 5, 'timeout': 15}
        assert custom_config.headers == {"User-Agent": "CustomAgent"}
        assert custom_config.valid_domains == ["https://example.com", "https://blog.example.com"]
        assert custom_config.url_patterns == ["/article/", "/post/"]
        assert custom_config.url_file_extensions == [".php", ".asp"]

    def test_empty_name_raises_error(self):
        """測試空名稱應該拋出錯誤"""
        with pytest.raises(ValueError, match="網站名稱不能為空"):
            SiteConfig(name="")

    def test_get_category_url(self):
        """測試 get_category_url 方法"""
        config = SiteConfig(
            name="test_site",
            base_url="https://test.com",
            list_url_template="{base_url}/cat/{category}"
        )
        
        # 測試有效分類
        url = config.get_category_url("ai")
        assert url == "https://test.com/cat/ai"
        
        # 測試無效分類
        url = config.get_category_url("invalid_category")
        assert url is None

    def test_validate_url(self):
        """測試 validate_url 方法"""
        config = SiteConfig(
            name="test_site",
            valid_domains=["https://example.com"],
            url_patterns=["/article/", "/blog/"],
            url_file_extensions=[".html"]
        )
        
        # 測試有效 URL
        assert config.validate_url("https://example.com/article/123.html") is True
        assert config.validate_url("https://example.com/blog/post.html") is True
        
        # 測試無效 URL - 錯誤域名
        assert config.validate_url("https://wrong-domain.com/article/123.html") is False
        
        # 測試無效 URL - 錯誤模式
        assert config.validate_url("https://example.com/news/123.html") is False
        
        # 測試無效 URL - 錯誤擴展名
        assert config.validate_url("https://example.com/article/123.php") is False
        
        # 測試無效 URL - 空 URL
        assert config.validate_url("") is False

    def test_validate_method(self):
        """測試 validate 方法"""
        # 有效配置
        valid_config = SiteConfig(name="test_site", base_url="https://example.com")
        assert valid_config.validate() is True
        
        # 無效配置測試已在 test_empty_name_raises_error 中涵蓋

    @patch('logging.Logger.error')
    def test_post_init_log_warnings(self, mock_logger):
        """測試 __post_init__ 方法的日誌警告"""
        # 測試沒有提供 base_url
        config = SiteConfig(name="test_site", base_url="")
        mock_logger.assert_any_call("未提供網站基礎URL，將使用預設值")
        assert config.base_url == "https://www.bnext.com.tw"
        
        # 重置模擬
        mock_logger.reset_mock()
        
        # 測試沒有提供 categories
        config = SiteConfig(name="test_site", categories=[])
        mock_logger.assert_any_call("未提供預設類別，將使用預設值")
        assert config.categories == ["ai", "tech", "iot", "smartmedical", "smartcity", "cloudcomputing", "security"]
        
        # 重置模擬
        mock_logger.reset_mock()
        
        # 測試沒有提供 selectors
        config = SiteConfig(name="test_site", selectors={})
        mock_logger.assert_any_call("未提供選擇器，將使用預設值")
        
        # 重置模擬
        mock_logger.reset_mock()
        
        # 測試沒有提供 list_url_template
        config = SiteConfig(name="test_site", list_url_template="")
        mock_logger.assert_any_call("未提供列表URL模板，將使用預設值")
        assert config.list_url_template == "{base_url}/categories/{category}"

if __name__ == "__main__":
    pytest.main()