from typing import Dict, Optional
from src.crawler.base_crawler import BaseCrawler
from unittest.mock import patch, MagicMock
import pytest
from src.crawler.bnext_crawler import BnextCrawler
class TestBnextCrawler:
    @pytest.fixture
    def crawler(self):
        return BnextCrawler("test", "https://example.com")

    def test_base_crawler_initialization(self, crawler):
        assert crawler.name == "test"
        assert crawler.url == "https://example.com"

    def test_base_crawler_crawl(self, crawler):
        assert crawler.crawl() is not None

    def test_fetch_page(self, crawler):
        with patch("src.crawler.base_crawler.BaseCrawler._fetch_page") as mock_fetch_page:
            mock_fetch_page.return_value = None
            assert crawler._fetch_page("https://example.com") is not None

    def test_save_data(self, crawler):
        with patch("src.crawler.base_crawler.BaseCrawler.save_data") as mock_save_data:
            mock_save_data.return_value = None
            assert crawler.save_data({"test": "test"}) is None




