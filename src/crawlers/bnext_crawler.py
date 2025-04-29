"""定義 BnextCrawler 類別，用於爬取 Bnext 網站的文章。"""

# 標準函式庫
from typing import Optional, List, Dict, Any

# 第三方函式庫
import pandas as pd

# 本地應用程式 imports
from src.crawlers.base_crawler import BaseCrawler
from src.crawlers.bnext_content_extractor import BnextContentExtractor
from src.crawlers.bnext_scraper import BnextScraper
from src.models.articles_model import ArticleScrapeStatus # 確保導入 ArticleScrapeStatus
from src.utils.log_utils import LoggerSetup

# 使用統一的 logger
logger = LoggerSetup.setup_logger(__name__)

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
        
        # 創建爬蟲和擷取器實例，傳入配置
        logger.debug("BnextCrawler - call_create_scraper(): 建立爬蟲實例")
        self.scraper = scraper or BnextScraper(
            config=self.site_config
        )
        logger.debug("BnextCrawler - call_create_extractor(): 建立文章內容擷取器")
        self.extractor = extractor or BnextContentExtractor(
            config=self.site_config
        )
        
        # 初始化 DataFrame
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
            pd.DataFrame: 包含文章列表的資料框，若無文章或發生錯誤則返回 None
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
        
        # 處理測試單一類別的情況
        is_test = self.global_params.get("is_test", False)
        if is_test and categories and len(categories) > 0:
            # 只使用第一個類別進行測試
            categories = categories[:1]
            # 更新site_config中的類別
            self.site_config.categories = categories
            logger.info("測試模式：只使用第一個類別 %s 進行測試", categories[0])
        
        logger.debug("抓取文章列表參數設定：最大頁數: %s, 文章類別: %s, AI 相關文章: %s", max_pages, categories, ai_only)
        logger.debug("抓取文章列表中...")
        article_links_df = self.retry_operation(
            lambda: self.scraper.scrape_article_list(max_pages, ai_only, min_keywords)
        )
        if article_links_df is None or article_links_df.empty:
            logger.warning("沒有文章列表可供處理")
            return None
        else:
            logger.debug("成功抓取文章列表")
            return article_links_df



    def _fetch_articles(self, task_id: int) -> Optional[List[Dict[str, Any]]]:
        """爬取文章詳細內容"""
        if self.articles_df is None or self.articles_df.empty:
            return None
        
        try:
            # 從 global_params 獲取參數
            num_articles = self.global_params.get("num_articles", 10)
            ai_only = self.global_params.get("ai_only", True)
            min_keywords = self.global_params.get("min_keywords", 3)
            is_limit_num_articles = self.global_params.get("is_limit_num_articles", False)
            
            # 使用重試機制批量獲取文章內容
            articles_content = self.retry_operation(
                lambda: self.extractor.batch_get_articles_content(
                    self.articles_df,
                    num_articles=num_articles,
                    ai_only=ai_only,
                    min_keywords=min_keywords,
                    is_limit_num_articles=is_limit_num_articles
                ),
                task_id=task_id
            )
            
            if not articles_content:
                return None
            
            # 更新 DataFrame 中的文章狀態
            for index, article in enumerate(articles_content):
                if index < len(self.articles_df):
                    # 使用 bool() 確保布林值類型正確
                    is_scraped = bool(article.get('is_scraped', False))
                    
                    # 更新狀態
                    self.articles_df.loc[index, 'is_scraped'] = is_scraped
                    self.articles_df.loc[index, 'scrape_status'] = ArticleScrapeStatus.CONTENT_SCRAPED.value if is_scraped else ArticleScrapeStatus.FAILED.value
                    self.articles_df.loc[index, 'scrape_error'] = article.get('scrape_error')
                    self.articles_df.loc[index, 'last_scrape_attempt'] = article.get('last_scrape_attempt')
                    self.articles_df.loc[index, 'task_id'] = task_id
            
            # 確保布林值欄位的類型 (迴圈外執行一次)
            self.articles_df['is_scraped'] = self.articles_df['is_scraped'].astype(bool)
            
            return articles_content
            
        except Exception as e:
            logger.error("抓取文章內容時發生錯誤: %s", e)
            return None



