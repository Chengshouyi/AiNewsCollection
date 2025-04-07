import pandas as pd
import logging
from src.crawlers.base_crawler import BaseCrawler
from src.crawlers.bnext_scraper import BnextScraper
from src.crawlers.bnext_content_extractor import BnextContentExtractor
from typing import Optional, List, Dict, Any

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BnextCrawler(BaseCrawler):
    def __init__(self, config_file_name: Optional[str] = None, article_service=None, scraper=None, extractor=None):
        """
        初始化明日科技爬蟲
        
        Args:
            db_manager (DatabaseManager): 資料庫管理器
            scraper (BnextScraper, optional): 文章列表爬蟲
            extractor (BnextContentExtractor, optional): 文章內容擷取器
        """
        super().__init__(config_file_name, article_service)
        
        # 創建爬蟲實例，傳入配置
        logger.debug(f"BnextCrawler - call_create_scraper()： 建立爬蟲實例")
        self.scraper = scraper or BnextScraper(
            config=self.site_config
        )
        logger.debug(f"BnextCrawler - call_create_extractor()： 建立文章內容擷取器")
        self.extractor = extractor or BnextContentExtractor(
            config=self.site_config
        )
        
        # 設置資料庫
        self.articles_df = pd.DataFrame()

    def _update_config(self):
        """
        更新爬蟲設定
        """
        self.scraper.update_config(self.site_config)
        self.extractor.update_config(self.site_config)
        

    def fetch_article_links(self) -> Optional[pd.DataFrame]:
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
        if not self.site_config:
            raise ValueError("網站設定(site_config)未初始化")

        max_pages = self.site_config.article_settings.get("max_pages", 3)
        categories = self.site_config.categories
        ai_only = self.site_config.article_settings.get("ai_only", True)
        min_keywords = self.site_config.article_settings.get("min_keywords", 3)
        logger.debug(f"抓取文章列表參數設定：最大頁數: {max_pages}, 文章類別: {categories}, AI 相關文章: {ai_only}")
        logger.debug(f"抓取文章列表中...")
        self.articles_df = self.retry_operation(
            lambda: self.scraper.scrape_article_list(max_pages, ai_only, min_keywords)
        )
        if self.articles_df is None or self.articles_df.empty:
            logger.warning("沒有文章列表可供處理")
            return None
        else:
            logger.debug(f"成功抓取文章列表")
            return self.articles_df

    def fetch_articles(self) -> Optional[List[Dict[str, Any]]]:
        """
        抓取文章詳細內容
        
        Args:
            args (dict): 包含以下參數：
                - articles_df (pd.DataFrame): 文章列表資料框
                - num_articles (int): 要抓取的文章數量
                - ai_only (bool): 是否只抓取 AI 相關文章
                - min_keywords (int): 最小關鍵字數量
                
        Returns:
            List[Dict[str, Any]]: 包含文章詳細內容的列表
        """
        if self.articles_df is None or self.articles_df.empty:
            logger.warning("沒有文章列表可供處理")
            return None

        if not self.site_config:
            self._create_site_config()

        num_articles = self.site_config.article_settings.get("num_articles", 10)
        ai_only = self.site_config.article_settings.get("ai_only", True)
        min_keywords = self.site_config.article_settings.get("min_keywords", 3)
            
        article_contents = self.retry_operation(
            lambda: self.extractor.batch_get_articles_content(self.articles_df, num_articles, ai_only, min_keywords)
        )

        if article_contents is None or len(article_contents) == 0:
            logger.warning("沒有文章內容可供處理")
            return None
        
        # 以Link為key，更新articles_df
        for article_content in article_contents:
            if article_content:
                self.articles_df.loc[self.articles_df['link'] == article_content['link'], 'is_scraped'] = True
        
        return article_contents



