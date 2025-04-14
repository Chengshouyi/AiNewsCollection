import pandas as pd
import logging
from src.crawlers.base_crawler import BaseCrawler
from src.crawlers.bnext_scraper import BnextScraper
from src.crawlers.bnext_content_extractor import BnextContentExtractor
from typing import Optional, List, Dict, Any
from src.models.crawler_tasks_model import ScrapeMode
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
        

    def _fetch_article_links(self, task_id: int) -> Optional[pd.DataFrame]:
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
        # 檢查任務是否已取消
        if task_id and self._check_if_cancelled(task_id):
            return None

        if not self.site_config:
            raise ValueError("網站設定(site_config)未初始化")

        # 從 global_params 獲取參數，如果沒有則使用預設值
        max_pages = self.global_params.get("max_pages", 3)
        categories = self.site_config.categories  # 類別仍然從 site_config 獲取，因為這是網站結構相關
        ai_only = self.global_params.get("ai_only", True)
        min_keywords = self.global_params.get("min_keywords", 3)
        
        logger.debug(f"抓取文章列表參數設定：最大頁數: {max_pages}, 文章類別: {categories}, AI 相關文章: {ai_only}")
        logger.debug(f"抓取文章列表中...")
        article_links_df = self.retry_operation(
            lambda: self.scraper.scrape_article_list(max_pages, ai_only, min_keywords)
        )
        if article_links_df is None or article_links_df.empty:
            logger.warning("沒有文章列表可供處理")
            return None
        else:
            logger.debug(f"成功抓取文章列表")
            return article_links_df



    def _fetch_articles(self, task_id: int) -> Optional[List[Dict[str, Any]]]:
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
        # 檢查任務是否已取消
        if task_id and self._check_if_cancelled(task_id):
            return None

        if self.articles_df is None or self.articles_df.empty:
            logger.warning("沒有文章列表可供處理")
            return None

        if not self.site_config:
            self._create_site_config()

        # 從 global_params 獲取參數，如果沒有則使用預設值
        num_articles = self.global_params.get("num_articles", 10)
        ai_only = self.global_params.get("ai_only", True)
        min_keywords = self.global_params.get("min_keywords", 3)
            
        article_contents = self.retry_operation(
            lambda: self.extractor.batch_get_articles_content(self.articles_df, num_articles, ai_only, min_keywords)
        )

        if article_contents is None or len(article_contents) == 0:
            logger.warning("沒有文章內容可供處理")
            return None
        
        # 以Link為key，根據 scrape_status 更新 articles_df
        for article_content in article_contents:
            if article_content:
                link = article_content.get('link')
                scrape_status = article_content.get('scrape_status')
                is_scraped = article_content.get('is_scraped', False)
                
                if link and link in self.articles_df['link'].values:
                    # 更新爬取狀態
                    self.articles_df.loc[self.articles_df['link'] == link, 'scrape_status'] = scrape_status
                    self.articles_df.loc[self.articles_df['link'] == link, 'is_scraped'] = is_scraped
                    
                    # 如果有錯誤信息，也更新
                    if 'scrape_error' in article_content and article_content['scrape_error'] is not None:
                        self.articles_df.loc[self.articles_df['link'] == link, 'scrape_error'] = article_content['scrape_error']
                    
                    # 更新最後抓取嘗試時間
                    if 'last_scrape_attempt' in article_content and article_content['last_scrape_attempt'] is not None:
                        self.articles_df.loc[self.articles_df['link'] == link, 'last_scrape_attempt'] = article_content['last_scrape_attempt']
        
        return article_contents



