from .base_crawler import BaseCrawler
from .bnext_crawler import BnextCrawler
from .bnext_scraper import BnextScraper
from .bnext_content_extractor import BnextContentExtractor
from .crawler_factory import CrawlerFactory
from .site_config import SiteConfig
from .bnext_config import BNEXT_CONFIG, create_bnext_config, load_bnext_config
from .base_config import get_default_session, random_sleep, DEFAULT_HEADERS, DEFAULT_REQUEST_CONFIG
from .article_analyzer import ArticleAnalyzer

# 註冊爬蟲類型
CrawlerFactory.register_crawler_type("bnext", BnextCrawler, BNEXT_CONFIG)

__all__ = [
    'BaseCrawler',
    'BnextCrawler',
    'BnextScraper',
    'BnextContentExtractor',
    'CrawlerFactory',
    'SiteConfig',
    'BNEXT_CONFIG',
    'create_bnext_config',
    'load_bnext_config',
    'get_default_session',
    'random_sleep',
    'DEFAULT_HEADERS',
    'DEFAULT_REQUEST_CONFIG',
    'ArticleAnalyzer'
]

