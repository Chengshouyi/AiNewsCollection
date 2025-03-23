import pandas as pd
import json
import logging
from src.crawler.base_crawler import BaseCrawler
from src.crawler.site_config import SiteConfig
from src.crawler.bnext_config import BNEXT_CONFIG
from src.crawler.ai_filter_config import AI_KEYWORDS
from src.crawler.bnext_scraper import BnextScraper
from src.crawler.bnext_content_extractor import BnextContentExtractor
from src.config import get_db_manager
from src.services.articles_service import ArticleService

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BnextCrawler(BaseCrawler):
    def __init__(self, config: SiteConfig = BNEXT_CONFIG):
        super().__init__(config)


    def fetch_article_list(self, args: dict, **kwargs) -> pd.DataFrame:
        scraper = BnextScraper()
        max_pages = args.get("max_pages", 3)
        categories = args.get("categories", None)
        ai_only = args.get("ai_only", True)
        return scraper.scrape_article_list(max_pages, categories, ai_only)

    def fectch_artcle_details(self, args: dict, **kwargs) -> pd.DataFrame:
        extractor = BnextContentExtractor()
        articles_df = args.get("articles_df", None)
        num_articles = args.get("num_articles", 10)
        ai_only = args.get("ai_only", True)
        min_keywords = args.get("min_keywords", 3)
        return extractor.batch_get_articles_content(articles_df, num_articles, ai_only, min_keywords)
      

    def save_data(self, data: pd.DataFrame):
        """
        保存網頁內容
        """
        db_manager = get_db_manager()
        article_service = ArticleService(db_manager)
        for _, row in data.iterrows():
            article_service.insert_article(row.to_dict())



