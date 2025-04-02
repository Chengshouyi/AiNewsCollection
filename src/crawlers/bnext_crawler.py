import pandas as pd
import logging
import json
from src.crawlers.base_crawler import BaseCrawler
from src.crawlers.configs.site_config import SiteConfig
from src.crawlers.bnext_scraper import BnextScraper
from src.crawlers.bnext_content_extractor import BnextContentExtractor
from typing import Optional

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BnextCrawler(BaseCrawler):
    def __init__(self, config_file_name: Optional[str] = None, scraper=None, extractor=None):
        """
        初始化明日科技爬蟲
        
        Args:
            db_manager (DatabaseManager): 資料庫管理器
            scraper (BnextScraper, optional): 文章列表爬蟲
            extractor (BnextContentExtractor, optional): 文章內容擷取器
        """
        super().__init__(config_file_name)
        
        logger.info(f"BnextCrawler - call_create_site_config()： 建立站點配置")
        self._create_site_config()
        
        # 創建爬蟲實例，傳入配置
        logger.info(f"BnextCrawler - call_create_scraper()： 建立爬蟲實例")
        self.scraper = scraper or BnextScraper(
            config=self.site_config
        )
        logger.info(f"BnextCrawler - call_create_extractor()： 建立文章內容擷取器")
        self.extractor = extractor or BnextContentExtractor(
            config=self.site_config
        )
        
        # 設置資料庫
        self.articles_df = pd.DataFrame()



    def _load_site_config(self):
        """載入爬蟲設定"""
        if self.config_file_name:
            try:
                with open(f'src/crawlers/configs/{self.config_file_name}', 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    # 使用文件配置更新默認配置
                    self.config_data.update(file_config)
                    
                logger.info(f"已載入 BNext 配置: {self.config_file_name}")
                logger.info(f"已載入 BNext 配置: {self.config_data}")
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logger.warning(f"載入配置文件失敗: {str(e)}，使用預設配置")
        else:
            logger.error(f"未找到配置文件")
            raise ValueError("未找到配置文件")  
        

    def _create_site_config(self):
        """創建站點配置"""
        if not self.config_data:
            logger.info(f"BnextCrawler - call_load_site_config()： 載入站點配置")
            self._load_site_config()
        
        # 創建 site_config
        logger.info(f"BnextCrawler - call_create_site_config()： 創建 site_config")
        self.site_config = SiteConfig(
            name=self.config_data.get("name", "BNext"),
            base_url=self.config_data.get("base_url", "https://www.bnext.com.tw"),
            list_url_template=self.config_data.get("list_url_template", "{base_url}/categories/{category}"),
            categories=self.config_data.get("categories", []),
            crawler_settings=self.config_data.get("crawler_settings", {}),
            content_extraction=self.config_data.get("content_extraction", {}),
            selectors=self.config_data.get("selectors", {})
        )
    
    def fetch_article_list(self) -> Optional[pd.DataFrame]:
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
            self._create_site_config()

        max_pages = self.site_config.crawler_settings.get("max_pages", 3)
        categories = self.site_config.categories
        ai_only = self.site_config.crawler_settings.get("ai_only", True)
        logger.info(f"抓取文章列表參數設定：最大頁數: {max_pages}, 文章類別: {categories}, AI 相關文章: {ai_only}")
        logger.info(f"BnextCrawler(fetch_article_list()) - call BnextScraper.scrape_article_list： 抓取文章列表中...")
        self.articles_df = self.retry_operation(
            lambda: self.scraper.scrape_article_list(max_pages, ai_only)
        )
        return self.articles_df

    def fetch_article_details(self, article_links_df: Optional[pd.DataFrame] = None) -> Optional[pd.DataFrame]:
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
        if article_links_df is None:
            articles_df = self.articles_df
        else:
            articles_df = article_links_df

        if not self.site_config:
            self._create_site_config()

        num_articles = self.site_config.content_extraction.get("num_articles", 10)
        ai_only = self.site_config.content_extraction.get("ai_only", True)
        min_keywords = self.site_config.content_extraction.get("min_keywords", 3)
        
        if articles_df is None or len(articles_df) == 0:
            logger.warning("沒有文章列表可供處理")
            return pd.DataFrame()
            
        return self.retry_operation(
            lambda: self.extractor.batch_get_articles_content(
                articles_df, num_articles, ai_only, min_keywords)
        )



