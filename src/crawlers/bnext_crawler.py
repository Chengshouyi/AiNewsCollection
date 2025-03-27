import pandas as pd
import logging
import time
import os
from src.crawlers.base_crawler import BaseCrawler
from src.crawlers.site_config import SiteConfig
from src.crawlers.bnext_config import BNEXT_CONFIG
from src.crawlers.bnext_scraper import BnextScraper
from src.crawlers.bnext_content_extractor import BnextContentExtractor
from typing import Optional

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BnextCrawler(BaseCrawler):
    def __init__(self, config: SiteConfig = BNEXT_CONFIG, scraper=None, extractor=None):
        """
        初始化明日科技爬蟲
        
        Args:
            config (SiteConfig): 網站配置
            scraper (BnextScraper, optional): 文章列表爬蟲
            extractor (BnextContentExtractor, optional): 文章內容擷取器
        """
        super().__init__(config, "BnextCrawler")
        self.scraper = scraper or BnextScraper()
        self.extractor = extractor or BnextContentExtractor()
        self.db_manager = None
        self.article_repository = None
        
    def set_db_manager(self, db_manager):
        """設置數據庫管理器"""
        self.db_manager = db_manager
        if db_manager:
            self.article_repository = db_manager.get_repository('Article')
            self.scraper.db_manager = db_manager
            self.scraper.article_repository = self.article_repository
            self.extractor.article_repository = self.article_repository

    def fetch_article_list(self, args: dict, **kwargs) -> Optional[pd.DataFrame]:
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
        max_pages = args.get("max_pages", 3)
        categories = args.get("categories", None)
        ai_only = args.get("ai_only", True)
        
        return self.retry_operation(
            lambda: self.scraper.scrape_article_list(max_pages, categories, ai_only)
        )

    def fetch_article_details(self, args: dict, **kwargs) -> Optional[pd.DataFrame]:
        """
        抓取文章詳細內容
        
        Args:
            args (dict): 包含以下參數：
                - articles_df (pd.DataFrame): 文章列表資料框
                - num_articles (int): 要抓取的文章數量
                - ai_only (bool): 是否只抓取 AI 相關文章
                - min_keywords (int): 最小關鍵字數量
                
        Returns:
            pd.DataFrame: 包含文章詳細內容的資料框
        """
        articles_df = args.get("articles_df", None)
        num_articles = args.get("num_articles", 10)
        ai_only = args.get("ai_only", True)
        min_keywords = args.get("min_keywords", 3)
        
        if articles_df is None or len(articles_df) == 0:
            logger.warning("沒有文章列表可供處理")
            return pd.DataFrame()
            
        return self.retry_operation(
            lambda: self.extractor.batch_get_articles_content(
                articles_df, num_articles, ai_only, min_keywords, self.db_manager
            )
        )
      
    def save_data(self, data: pd.DataFrame, save_to_csv: bool = False, csv_path: Optional[str] = None):
        """保存爬取到的文章數據"""
        if data is None or len(data) == 0:
            logger.warning("沒有數據可供保存")
            return
            
        # 保存到數據庫
        if self.db_manager and self.article_repository:
            for _, row in data.iterrows():
                try:
                    article_data = {
                        'title': row['title'],
                        'summary': row.get('summary', ''),
                        'content': row.get('content', ''),
                        'link': row['link'],
                        'category': row.get('category', ''),
                        'published_at': row.get('publish_time', '') or row.get('publish_at', ''),
                        'author': row.get('author', ''),
                        'source': 'bnext_crawler',
                        'tags': row.get('tags', '')
                    }
                    self.article_repository.create(article_data)
                except Exception as e:
                    logger.error(f"保存文章到數據庫失敗: {str(e)}", exc_info=True)
        
        # 如果需要，保存到 CSV 文件
        if save_to_csv:
            self._save_to_csv(data, csv_path)
        
    def _save_to_csv(self, data: pd.DataFrame, csv_path: Optional[str] = None):
        """保存數據到CSV文件"""
        if not csv_path:
            csv_path = f'articles_{int(time.time())}.csv'
            
        try:
            # 確保目錄存在
            os.makedirs(os.path.dirname(csv_path) or '.', exist_ok=True)
            data.to_csv(csv_path, index=False, encoding='utf-8-sig')
            logger.info(f"文章數據已保存到 CSV 文件: {csv_path}")
        except Exception as e:
            logger.error(f"保存文章到 CSV 文件失敗: {str(e)}", exc_info=True)



