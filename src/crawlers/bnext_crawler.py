import pandas as pd
import json
import logging
from src.crawlers.base_crawler import BaseCrawler
from src.crawlers.site_config import SiteConfig
from src.crawlers.bnext_config import BNEXT_CONFIG
from src.crawlers.ai_filter_config import AI_KEYWORDS
from src.crawlers.bnext_scraper import BnextScraper
from src.crawlers.bnext_content_extractor import BnextContentExtractor
from src.database.database_manager import DatabaseManager
from src.services.article_service import ArticleService

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BnextCrawler(BaseCrawler):
    def __init__(self, config: SiteConfig = BNEXT_CONFIG):
        super().__init__(config,"BnextCrawler")


    def fetch_article_list(self, args: dict, **kwargs) -> pd.DataFrame:
        """
        抓取文章列表
        
        Args:
            args (dict): 包含以下參數：
                - max_pages (int): 最大頁數，預設為 3
                - categories (list): 文章類別列表，預設為 None
                - ai_only (bool): 是否只抓取 AI 相關文章，預設為 True
            
        Returns:
            pd.DataFrame: 包含文章列表的資料框
        """
        scraper = BnextScraper()
        max_pages = args.get("max_pages", 3)
        categories = args.get("categories", None)
        ai_only = args.get("ai_only", True)
        return scraper.scrape_article_list(max_pages, categories, ai_only)

    def fetch_article_details(self, args: dict, **kwargs) -> pd.DataFrame:
        extractor = BnextContentExtractor()
        articles_df = args.get("articles_df", None)
        num_articles = args.get("num_articles", 10)
        ai_only = args.get("ai_only", True)
        min_keywords = args.get("min_keywords", 3)
        return extractor.batch_get_articles_content(articles_df, num_articles, ai_only, min_keywords)
      

    def save_data(self, data: pd.DataFrame):
        """
        保存網頁內容，需要重新設計
        """
        db_manager = DatabaseManager()
        article_service = ArticleService(db_manager)
        for _, row in data.iterrows():
            article_service.insert_article(row.to_dict())



