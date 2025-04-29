"""測試 src.crawlers.configs.site_config 中的 SiteConfig 類別功能。"""

# 標準函式庫導入
from unittest.mock import patch # patch 雖然未使用，但保留以備將來擴展

# 第三方函式庫導入
import pytest

# 本地應用程式導入
from src.crawlers.configs.base_config import DEFAULT_HEADERS # 雖然未直接測試，但 SiteConfig 會使用
from src.crawlers.configs.site_config import SiteConfig
from src.error.errors import ValidationError
from src.utils.log_utils import LoggerSetup

# 設定統一的 logger
logger = LoggerSetup.setup_logger(__name__)


class TestSiteConfig:
    """測試 SiteConfig 類別的功能"""

    def test_default_initialization(self):
        """測試使用默認值創建 SiteConfig 實例"""
        config = SiteConfig(
            name="test_site",
            base_url="https://www.bnext.com.tw",
            categories=["ai", "tech", "iot", "smartmedical", "smartcity", "cloudcomputing", "security"],
            full_categories=["ai", "tech", "iot", "smartmedical", "smartcity", "cloudcomputing", "security"],
            selectors={'max_retries': 3, 'retry_delay': 5, 'timeout': 10},
            list_url_template="{base_url}/categories/{category}"
        )

        assert config.name == "test_site"
        assert config.base_url == "https://www.bnext.com.tw"
        assert config.categories == ["ai", "tech", "iot", "smartmedical", "smartcity", "cloudcomputing", "security"]
        assert config.full_categories == ["ai", "tech", "iot", "smartmedical", "smartcity", "cloudcomputing", "security"]
        assert config.selectors == {'max_retries': 3, 'retry_delay': 5, 'timeout': 10}
        assert config.headers == DEFAULT_HEADERS # 驗證是否使用了 base_config 的預設值
        assert config.list_url_template == "{base_url}/categories/{category}"
        assert config.url_file_extensions == ['.html', '.htm']
        assert config.date_format == '%Y/%m/%d %H:%M'

    def test_custom_initialization(self):
        """測試使用自定義值創建 SiteConfig 實例"""
        custom_config = SiteConfig(
            name="custom_site",
            base_url="https://example.com",
            list_url_template="https://example.com/{category}/list",
            categories=["news", "blog"],
            full_categories=["news", "blog"],
            selectors={'max_retries': 5, 'timeout': 15},
            headers={"User-Agent": "CustomAgent"},
            valid_domains=["https://example.com", "https://blog.example.com"],
            url_patterns=["/article/", "/post/"],
            url_file_extensions=[".php", ".asp"]
        )

        assert custom_config.name == "custom_site"
        assert custom_config.base_url == "https://example.com"
        assert custom_config.list_url_template == "https://example.com/{category}/list"
        assert custom_config.categories == ["news", "blog"]
        assert custom_config.full_categories == ["news", "blog"]
        assert custom_config.selectors == {'max_retries': 5, 'timeout': 15}
        assert custom_config.headers == {"User-Agent": "CustomAgent"}
        assert custom_config.valid_domains == ["https://example.com", "https://blog.example.com"]
        assert custom_config.url_patterns == ["/article/", "/post/"]
        assert custom_config.url_file_extensions == [".php", ".asp"]

    def test_empty_name_raises_error(self):
        """測試空名稱應該拋出錯誤"""
        with pytest.raises(ValidationError, match="name: 不能為空"):
            SiteConfig(
                name="",
                base_url="https://www.bnext.com.tw",
                list_url_template="{base_url}/categories/{category}",
                categories=["ai", "tech"],
                full_categories=["ai", "tech"],
                selectors={'max_retries': 3, 'retry_delay': 5, 'timeout': 10}
            )

    def test_empty_base_url_raises_error(self):
        """測試空基礎URL應該拋出錯誤"""
        with pytest.raises(ValidationError, match="base_url: URL不能為空"):
            SiteConfig(
                name="test_site",
                base_url="",
                list_url_template="{base_url}/categories/{category}",
                categories=["ai", "tech"],
                full_categories=["ai", "tech"],
                selectors={'max_retries': 3, 'retry_delay': 5, 'timeout': 10}
            )

    def test_empty_list_url_template_raises_error(self):
        """測試空列表URL模板應該拋出錯誤"""
        with pytest.raises(ValidationError, match="list_url_template: 不能為空"):
            SiteConfig(
                name="test_site",
                base_url="https://www.bnext.com.tw",
                list_url_template="",
                categories=["ai", "tech"],
                full_categories=["ai", "tech"],
                selectors={'max_retries': 3, 'retry_delay': 5, 'timeout': 10}
            )

    def test_empty_categories_raises_error(self):
        """測試空分類列表應該拋出錯誤"""
        with pytest.raises(ValidationError, match="categories: 列表長度不能小於 1"):
            SiteConfig(
                name="test_site",
                base_url="https://www.bnext.com.tw",
                list_url_template="{base_url}/categories/{category}",
                categories=[],
                full_categories=["ai", "tech"],
                selectors={'max_retries': 3, 'retry_delay': 5, 'timeout': 10}
            )

    def test_empty_full_categories_raises_error(self):
        """測試空完整分類列表應該拋出錯誤"""
        with pytest.raises(ValidationError, match="full_categories: 列表長度不能小於 1"):
            SiteConfig(
                name="test_site",
                base_url="https://www.bnext.com.tw",
                list_url_template="{base_url}/categories/{category}",
                categories=["ai", "tech"],
                full_categories=[],
                selectors={'max_retries': 3, 'retry_delay': 5, 'timeout': 10}
            )

    def test_get_category_url(self):
        """測試 get_category_url 方法"""
        config = SiteConfig(
            name="test_site",
            base_url="https://test.com",
            list_url_template="{base_url}/cat/{category}",
            categories=["ai", "tech"],
            full_categories=["ai", "tech"],
            selectors={'max_retries': 3, 'retry_delay': 5, 'timeout': 10}
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
            base_url="https://example.com",
            list_url_template="{base_url}/cat/{category}",
            categories=["ai", "tech"],
            full_categories=["ai", "tech"],
            selectors={'max_retries': 3, 'retry_delay': 5, 'timeout': 10},
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
        valid_config = SiteConfig(
            name="test_site",
            base_url="https://example.com",
            list_url_template="{base_url}/cat/{category}",
            categories=["ai", "tech"],
            full_categories=["ai", "tech"],
            selectors={'max_retries': 3, 'retry_delay': 5, 'timeout': 10}
        )
        assert valid_config.validate() is True