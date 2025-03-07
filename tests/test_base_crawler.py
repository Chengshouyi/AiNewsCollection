# 測試基礎爬蟲

from src.crawler.base_crawler import BaseCrawler

def test_base_crawler():
    crawler = BaseCrawler()
    assert crawler is not None

def test_base_crawler_crawl():
    crawler = BaseCrawler()
    assert crawler.crawl() is not None

