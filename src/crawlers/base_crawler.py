from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
import pandas as pd
from datetime import datetime, timezone
import logging
import time
import json
import os
from src.crawlers.configs.site_config import SiteConfig
from src.database.database_manager import DatabaseManager
from src.database.articles_repository import ArticlesRepository
from src.database.article_links_repository import ArticleLinksRepository
from src.models.articles_model import Articles
from src.models.article_links_model import ArticleLinks
# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BaseCrawler(ABC):



    def __init__(self, config_file_name: Optional[str] = None):
        self.config_data: Dict[str, Any] = {}
        self.site_config: SiteConfig
        self.task_status = {}
        self.config_file_name = config_file_name
        

        
    @abstractmethod
    def _load_site_config(self):
        """
        從配置檔案讀取爬蟲設定，子類別需要實作
        """

    @abstractmethod
    def _create_site_config(self):
        """
        創建站點配置，子類別需要實作
        """
        pass

    @abstractmethod
    def fetch_article_list(self) -> pd.DataFrame:
        """
        爬取新聞列表，子類別需要實作
        """
        pass

    @abstractmethod
    def fetch_article_details(self) -> pd.DataFrame:
        """
        爬取文章詳細內容，子類別需要實作
        """
        pass

    def _save_to_database(self, data: pd.DataFrame, target: str):
        """保存爬取到的文章數據"""
        if data is None or len(data) == 0:
            logger.warning("沒有數據可供保存")
            return

        if target == "article_links":
            pass
        elif target == "articles":
            pass
        else:
            raise ValueError(f"不支持的保存目標: {target}")

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


    def execute_task(self, task_id: int, task_args: dict):
        """執行爬蟲任務的完整流程，並更新任務狀態"""
        self.task_status[task_id] = {
            'status': 'running',
            'progress': 0,
            'message': '開始執行任務',
            'start_time': datetime.now(timezone.utc)
        }
        
        try:
            # 步驟1：抓取文章列表
            self._update_task_status(task_id, 10, '抓取文章列表中...')
            logger.info(f"BaseCrawler(execute_task()) - call BnextCrawler.fetch_article_list： 抓取文章列表中...")
            articles_df = self.fetch_article_list()
            
            # 步驟2：抓取文章詳細內容
            self._update_task_status(task_id, 50, '抓取文章詳細內容中...')
            if task_args.get('fetch_details', False):
                args = {
                    'articles_df': articles_df,
                    'num_articles': task_args.get('num_articles', 10),
                    'ai_only': task_args.get('ai_only', True),
                    'min_keywords': task_args.get('min_keywords', 3)
                }
                detailed_df = self.fetch_article_details()
            else:
                detailed_df = articles_df
                
            # 步驟3：保存數據
            self._update_task_status(task_id, 80, '保存數據中...')
            save_to_csv = task_args.get('save_to_csv', False)
            csv_path = task_args.get('csv_path', f'articles_{task_id}.csv')
            
            self._save_to_database(detailed_df, "articles")
                
            self._update_task_status(task_id, 100, '任務完成', 'completed')
            return detailed_df
            
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
                
            logger.info(f"任務進度更新 (ID={task_id}): {progress}%, {message}")
    
    def get_task_status(self, task_id: int):
        """獲取任務狀態"""
        return self.task_status.get(task_id, {
            'status': 'unknown',
            'progress': 0,
            'message': '任務不存在'
        })
        
    def retry_operation(self, operation, max_retries=3, retry_delay=2):
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

   
