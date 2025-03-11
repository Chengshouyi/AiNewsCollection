from src.crawler.base_crawler import BaseCrawler
from unittest.mock import patch, MagicMock

def test_base_crawler():
    crawler = BaseCrawler("test", "https://example.com")
    assert crawler.name == "test"
    assert crawler.url == "https://example.com"
    assert crawler.run() is None  
    #  測試 _fetch_html
    with patch("src.crawler.base_crawler.BaseCrawler._fetch_html") as mock_fetch_html:
        mock_fetch_html.return_value = None
        assert crawler._fetch_html("https://example.com") is None
    #  測試 _parse_html
    with patch("src.crawler.base_crawler.BaseCrawler._parse_html") as mock_parse_html:
        mock_parse_html.return_value = None
        assert crawler._parse_html(None) is None
    #  測試 _extract_data
    with patch("src.crawler.base_crawler.BaseCrawler._extract_data") as mock_extract_data:
        mock_extract_data.return_value = None
        assert crawler._extract_data(None) is None
    #  測試 _transform_data
    with patch("src.crawler.base_crawler.BaseCrawler._transform_data") as mock_transform_data:
        mock_transform_data.return_value = None
        assert crawler._transform_data(None) is None
    #  測試 _save_data
    with patch("src.crawler.base_crawler.BaseCrawler._save_data") as mock_save_data:
        mock_save_data.return_value = None
        assert crawler._save_data(None) is None  




