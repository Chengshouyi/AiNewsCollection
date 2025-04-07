from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List
import pandas as pd
from datetime import datetime, timezone
import logging
import time
import json
import os
from src.crawlers.configs.site_config import SiteConfig
from src.services.article_service import ArticleService
from src.utils.model_utils import convert_hashable_dict_to_str_dict

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BaseCrawler(ABC):



    def __init__(self, config_file_name: Optional[str] = None, article_service: Optional[ArticleService] = None):
        self.config_data: Dict[str, Any] = {}
        self.site_config: SiteConfig
        self.task_status = {}
        self.config_file_name = config_file_name
        self.articles_df = pd.DataFrame()
        if article_service is None:
            logger.error("未提供文章服務，請提供有效的文章服務")
            raise ValueError("未提供文章服務，請提供有效的文章服務")
        else:
            self.article_service = article_service

        self._create_site_config()

    def _load_site_config(self):
        """載入爬蟲設定"""
        if self.config_file_name:
            try:
                with open(f'src/crawlers/configs/{self.config_file_name}', 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    # 使用文件配置更新默認配置
                    self.config_data.update(file_config)
                    
                logger.debug(f"已載入 BNext 配置: {self.config_file_name}")
                logger.debug(f"已載入 BNext 配置: {self.config_data}")
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logger.warning(f"載入配置文件失敗: {str(e)}，使用預設配置")
        else:
            logger.error(f"未找到配置文件")
            raise ValueError("未找到配置文件")  
        

    def _create_site_config(self):
        """創建站點配置"""
        if not self.config_data:
            logger.debug(f"BnextCrawler - call_load_site_config()： 載入站點配置")
            self._load_site_config()
        
        # 創建 site_config
        logger.debug(f"BnextCrawler - call_create_site_config()： 創建 site_config")
        self.site_config = SiteConfig(
            name=self.config_data.get("name", None),
            base_url=self.config_data.get("base_url", None),
            list_url_template=self.config_data.get("list_url_template", None),
            categories=self.config_data.get("categories", None),
            full_categories=self.config_data.get("full_categories", None),
            article_settings=self.config_data.get("article_settings", None),
            extraction_settings=self.config_data.get("extraction_settings", None),
            storage_settings=self.config_data.get("storage_settings", None),
            selectors=self.config_data.get("selectors", None)
        )
        
        # 檢查必要的配置值
        for key, value in self.site_config.__dict__.items():
            if value is None:
                logger.error(f"未提供 {key} 值，請設定有效值")
                raise ValueError(f"未提供 {key} 值，請設定有效值")
            
            if key == "article_settings":
                required_settings = ["max_pages", "ai_only", "num_articles", "min_keywords"]
                for setting in required_settings:
                    if setting not in value:  # 直接檢查字典鍵
                        logger.error(f"未提供 {setting} 值，請設定有效值")
                        raise ValueError(f"未提供 {setting} 值，請設定有效值")
                    
            elif key == "extraction_settings":
                required_settings = ["num_articles", "min_keywords"]
                for setting in required_settings:
                    if setting not in value:
                        logger.error(f"未提供 {setting} 值，請設定有效值")
                        raise ValueError(f"未提供 {setting} 值，請設定有效值")
                    
            elif key == "storage_settings":
                required_settings = ["save_to_csv", "save_to_database"]
                for setting in required_settings:
                    if setting not in value:
                        logger.error(f"未提供 {setting} 值，請設定有效值")
                        raise ValueError(f"未提供 {setting} 值，請設定有效值")

    @abstractmethod
    def _fetch_article_links(self) -> Optional[pd.DataFrame]:
        """
        爬取新聞列表，子類別需要實作
        """
        raise NotImplementedError("子類別需要實作 _fetch_article_links 方法")

    @abstractmethod
    def _fetch_articles(self) -> Optional[List[Dict[str, Any]]]:
        """
        爬取文章詳細內容，子類別需要實作
        """
        raise NotImplementedError("子類別需要實作 _fetch_articles 方法")

    @abstractmethod
    def _fetch_article_links_from_db(self) -> Optional[pd.DataFrame]:
        """
        從資料庫連結獲取文章列表，子類別需要實作
        """
        raise NotImplementedError("子類別需要實作 _fetch_article_links_from_db 方法")
    
    @abstractmethod
    def _update_config(self):
        """
        更新爬蟲設定，子類別需要實作
        """
        raise NotImplementedError("子類別需要實作 _update_config 方法")

    def _save_to_database(self):
        """保存爬取到的文章數據"""
        if self.article_service is None:
            logger.error("article_service 未初始化")
            return
        try:
            # 新增文章
            articles_data = self.articles_df.to_dict('records')
            if articles_data:
                str_articles_data = [convert_hashable_dict_to_str_dict(article) for article in articles_data]

                if self.site_config.article_settings.get('from_db_link', False):
                    article_ids = self.articles_df['id'].tolist()
                    #取代 entity_id 為 id
                    for article in str_articles_data:
                        article['entity_id'] = article['id']
                        del article['id']
                    result = self.article_service.batch_update_articles(
                        article_data = str_articles_data
                    )
                else:
                    result = self.article_service.batch_create_articles(
                        articles_data = str_articles_data
                    )
                
                if not result["success"]:
                    logger.error(f"批量創建文章失敗: {result['message']}")
                    return
                
                logger.info(f"批量創建文章成功: {result['message']}")
                
        except Exception as e:
            logger.error(f"保存到資料庫失敗: {str(e)}")
            raise e

    def _save_to_csv(self, data: pd.DataFrame, csv_path: Optional[str] = None):
        """保存數據到CSV文件"""
        if not csv_path:
            logger.error("未提供CSV文件路徑")
            return
            
        try:
            # 確保目錄存在
            os.makedirs(os.path.dirname(csv_path) or '.', exist_ok=True)
            data.to_csv(csv_path, index=False, encoding='utf-8-sig')
            logger.debug(f"文章數據已保存到 CSV 文件: {csv_path}")
        except Exception as e:
            logger.error(f"保存文章到 CSV 文件失敗: {str(e)}", exc_info=True)




    def execute_task(self, task_id: int, task_args: dict):
        """執行爬蟲任務的完整流程，並更新任務狀態
        
        Args:
            task_id: 任務ID
            task_args: 任務參數 
                - max_pages: 最大頁數
                - ai_only: 是否只抓取AI相關文章
                - num_articles: 抓取的文章數量
                - min_keywords: 最小關鍵字數量
                - max_retries: 最大重試次數
                - retry_delay: 重試延遲時間
                - timeout: 超時時間
                - save_to_csv: 是否保存到CSV文件
                - save_to_database: 是否保存到資料庫
                
        Returns:
            Dict[str, Any]: 任務狀態
        """
        if self.site_config is None:
            logger.error("site_config 未初始化")
            raise ValueError("site_config 未初始化")
        
        self.task_status[task_id] = {
            'status': 'running',
            'progress': 0,
            'message': '開始執行任務',
            'start_time': datetime.now(timezone.utc)
        }
        
        if task_args:
            # 更新任務參數
            for key, value in task_args.items():
                if key in self.site_config.article_settings:
                    self.site_config.article_settings[key] = value
                elif key in self.site_config.extraction_settings:
                    self.site_config.extraction_settings[key] = value
                elif key in self.site_config.storage_settings:
                    self.site_config.storage_settings[key] = value
                else:
                    logger.error(f"未知的任務參數: {key}")
                    raise ValueError(f"未知的任務參數: {key}")
                
            self._update_config()
        
        try:
            # 步驟1：抓取文章列表
            if not self.site_config.article_settings.get('from_db_link', False):
                self._update_task_status(task_id, 10, '連接網站抓取文章列表中...')
                logger.debug(f"BaseCrawler(execute_task()) - call BnextCrawler.fetch_article_list： 連接網站抓取文章列表中...")

                fetched_articles_df = self._fetch_article_links()
            
                logger.debug(f"BaseCrawler(execute_task()) - call BnextCrawler.fetch_article_list： 連接網站抓取文章列表完成")
                self._update_task_status(task_id, 20, '連接網站抓取文章列表完成')
            else:
                self._update_task_status(task_id, 10, '從資料庫連結獲取文章列表中...')
                logger.debug(f"BaseCrawler(execute_task()) - call BnextCrawler._fetch_article_links_from_db： 從資料庫連結獲取文章列表中...")

                fetched_articles_df = self._fetch_article_links_from_db()

                self._update_task_status(task_id, 20, '從資料庫連結獲取文章列表完成')
                logger.debug(f"BaseCrawler(execute_task()) - call BnextCrawler._fetch_article_links_from_db： 從資料庫連結獲取文章列表完成")

            if fetched_articles_df is None or fetched_articles_df.empty:
                logger.warning("沒有獲取到任何文章連結")
                self._update_task_status(task_id, 100, '沒有獲取到任何文章連結', 'completed')
                return
            
            # 將获取的文章列表赋值给 self.articles_df(TODO:將來要改成用參數傳入)
            self.articles_df = fetched_articles_df
            
            # 步驟2：抓取文章詳細內容
            self._update_task_status(task_id, 30, '抓取文章詳細內容中...')
            logger.debug(f"BaseCrawler(execute_task()) - call BnextCrawler.fetch_article_content： 抓取文章詳細內容中...")

            fetched_articles = self._fetch_articles()

            logger.debug(f"BaseCrawler(execute_task()) - call BnextCrawler.fetch_article_content： 抓取文章詳細內容完成")
            self._update_task_status(task_id, 40, '抓取文章詳細內容完成')
            if fetched_articles is None or len(fetched_articles) == 0:
                logger.warning("沒有獲取到任何文章")
                self._update_task_status(task_id, 100, '沒有獲取到任何文章', 'completed')
                return
            
            # 步驟3：以Link為key，更新articles_df
            self._update_task_status(task_id, 60, '更新articles_df中...')
            logger.debug(f"BaseCrawler(execute_task()) - call BnextCrawler.fetch_article_content： 更新articles_df")

            for article in fetched_articles:
                if article:
                    # 使用 link 作為 key 來更新整篇文章的所有欄位
                    article_link = article['link']
                    article_index = self.articles_df.index[self.articles_df['link'] == article_link].tolist()
                    if article_index:
                        # 更新該筆資料的所有欄位
                        self.articles_df.loc[article_index[0]] = pd.Series(article)

            logger.debug(f"BaseCrawler(execute_task()) - call BnextCrawler.fetch_article_content： 更新articles_df完成")
            self._update_task_status(task_id, 70, '更新articles_df完成')

            # 步驟4：保存數據到CSV文件
            self._update_task_status(task_id, 80, '保存數據中...')
            if self.site_config.storage_settings.get('save_to_csv', False):
                logger.debug(f"BaseCrawler(execute_task()) - call _save_to_csv： 保存數據到CSV文件中...")
                self._update_task_status(task_id, 85, '保存數據到CSV文件中...')

                self._save_to_csv(self.articles_df, f'./logs/{self.site_config.storage_settings.get("csv_file_name", "articles_{task_id}.csv")}')

                logger.debug(f"BaseCrawler(execute_task()) - call _save_to_csv： 保存數據到CSV文件完成")
                self._update_task_status(task_id, 90, '保存數據到CSV文件完成')

            # 步驟4：保存數據到資料庫
            if self.site_config.storage_settings.get('save_to_database', False):
                logger.debug(f"BaseCrawler(execute_task()) - call _save_to_database： 保存數據到資料庫中...")
                self._update_task_status(task_id, 95, '保存數據到資料庫中...')

                self._save_to_database()

                logger.debug(f"BaseCrawler(execute_task()) - call _save_to_database： 保存數據到資料庫完成")
                self._update_task_status(task_id, 100, '保存數據到資料庫完成')
            self._update_task_status(task_id, 100, '任務完成', 'completed')
            
        except Exception as e:
            self._update_task_status(task_id, 0, f'任務失敗: {str(e)}', 'failed')
            logger.error(f"執行任務失敗 (ID={task_id}): {str(e)}", exc_info=True)
            raise e
    
    def _update_task_status(self, task_id: int, progress: int, message: str, status: Optional[str] = None):
        """更新任務狀態"""
        if task_id in self.task_status:
            self.task_status[task_id]['progress'] = progress
            self.task_status[task_id]['message'] = message
            if status:
                self.task_status[task_id]['status'] = status
                
            logger.debug(f"任務進度更新 (ID={task_id}): {progress}%, {message}")
    
    def get_task_status(self, task_id: int):
        """獲取任務狀態"""
        return self.task_status.get(task_id, {
            'status': 'unknown',
            'progress': 0,
            'message': '任務不存在'
        })
        
    def retry_operation(self, operation, max_retries=3, retry_delay=2.0):
        """重試操作的通用方法"""
        retries = 0
        while retries < max_retries:
            try:
                return operation()
            except Exception as e:
                retries += 1
                if retries >= max_retries:
                    logger.error(f"操作失敗，已重試 {retries} 次: {str(e)}")
                    raise e
                
                logger.warning(f"操作失敗，正在重試 ({retries}/{max_retries}): {str(e)}")
                time.sleep(retry_delay)

   
