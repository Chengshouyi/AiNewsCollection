import pandas as pd
import logging
import time
import os
import json
from src.crawlers.base_crawler import BaseCrawler
from src.crawlers.configs.site_config import SiteConfig
from src.crawlers.bnext_scraper import BnextScraper
from src.crawlers.bnext_content_extractor import BnextContentExtractor
from src.database.database_manager import DatabaseManager
from src.crawlers.bnext_utils import BnextUtils
from typing import Optional

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BnextCrawler(BaseCrawler):
    def __init__(self, db_manager: DatabaseManager, config_file_name: Optional[str] = None, scraper=None, extractor=None):
        """
        初始化明日科技爬蟲
        
        Args:
            db_manager (DatabaseManager): 資料庫管理器
            scraper (BnextScraper, optional): 文章列表爬蟲
            extractor (BnextContentExtractor, optional): 文章內容擷取器
        """
        super().__init__(db_manager, config_file_name)
        
        self._create_site_config()
        
        # 創建爬蟲實例，傳入配置
        #TODO:傳入資料庫ArticleRepository,ArticleLinkRepository
        self.scraper = scraper or BnextScraper(
            config=self.site_config
        )
        self.extractor = extractor or BnextContentExtractor(
            config=self.site_config
        )
        
        # 設置資料庫
        self._set_repository()
        self.articles_df = pd.DataFrame()



    def _load_site_config(self):
        """載入爬蟲設定"""
        if self.config_file_name:
            try:
                with open(f'src/crawlers/configs/{self.config_file_name}', 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    # 使用文件配置更新默認配置
                    self.config_data.update(file_config)
                    
                    # 特別處理選擇器配置，確保其結構正確
                    if 'selectors' in file_config:
                        logger.info(f"從配置文件中載入選擇器配置，找到 {len(file_config['selectors'])} 個選擇器組")
                        if 'selectors' not in self.config_data:
                            self.config_data['selectors'] = {}
                        
                        # 確保選擇器下的項目都正確加載
                        selectors = file_config['selectors']
                        self.config_data['selectors'].update(selectors)
                        
                        # 記錄載入的選擇器配置
                        logger.debug(f"載入的選擇器配置: {list(self.config_data['selectors'].keys())}")
                    
                logger.info(f"已載入 BNext 配置: {self.config_file_name}")
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logger.warning(f"載入配置文件失敗: {str(e)}，使用預設配置")
        else:
            logger.error(f"未找到配置文件")
            raise ValueError("未找到配置文件")  
        

    def _create_site_config(self):
        """創建站點配置"""
        if not self.config_data:
            self._load_site_config()
        
        # 創建 site_config
        self.site_config = SiteConfig(
            name=self.config_data.get("name", "BNext"),
            base_url=self.config_data.get("base_url", "https://www.bnext.com.tw"),
            list_url_template=self.config_data.get("list_url_template", "{base_url}/categories/{category}"),
            categories=self.config_data.get("categories", {}),
            crawler_settings=self.config_data.get("crawler_settings", {}),
            content_extraction=self.config_data.get("content_extraction", {}),
            default_categories=self.config_data.get("default_categories", []),
            selectors=self.config_data.get("selectors", {})
        )
        BnextUtils.set_bnext_config(self.site_config)

    def _set_repository(self):
        """設置數據庫管理器"""
        if self.db_manager:
            self.scraper.article_repository = self.article_repository
            self.extractor.article_repository = self.article_repository
    
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
        categories = self.site_config.categories.get("categories", None)
        ai_only = self.site_config.crawler_settings.get("ai_only", True)
        logger.info(f"抓取文章列表參數設定：最大頁數: {max_pages}, 文章類別: {categories}, AI 相關文章: {ai_only}")
        logger.info(f"BnextCrawler(fetch_article_list()) - call BnextScraper.scrape_article_list： 抓取文章列表中...")
        self.articles_df = self.retry_operation(
            lambda: self.scraper.scrape_article_list(max_pages, categories, ai_only)
        )
        return self.articles_df

    def fetch_article_details(self) -> Optional[pd.DataFrame]:
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
        if not self.site_config:
            self._create_site_config()

        articles_df = self.articles_df
        num_articles = self.site_config.content_extraction.get("num_articles", 10)
        ai_only = self.site_config.content_extraction.get("ai_only", True)
        min_keywords = self.site_config.content_extraction.get("min_keywords", 3)
        
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



