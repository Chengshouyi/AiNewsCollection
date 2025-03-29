from abc import ABC, abstractmethod
from typing import Dict, Optional
import pandas as pd
from src.crawlers.site_config import SiteConfig
from datetime import datetime, timezone
import logging
import time

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BaseCrawler(ABC):
    def __init__(self, site_config, crawler_type: str):
        self.site_config = site_config
        self.task_status = {}
        self.crawler_type = crawler_type

    @abstractmethod
    def fetch_article_list(self, args: dict, **kwargs) -> pd.DataFrame:
        """
        爬取新聞列表，子類別需要實作
        """
        pass

    @abstractmethod
    def fetch_article_details(self, args: dict, **kwargs) -> pd.DataFrame:
        """
        爬取文章詳細內容，子類別需要實作
        """
        pass

    @abstractmethod
    def save_data(self, data: pd.DataFrame, save_to_csv: bool = False, csv_path: Optional[str] = None):
        """
        保存數據，支持保存到數據庫和CSV文件
        """
        pass

    def execute_task(self, task_id: int, task_args: dict, db_manager=None):
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
            articles_df = self.fetch_article_list(task_args)
            
            # 步驟2：抓取文章詳細內容
            self._update_task_status(task_id, 50, '抓取文章詳細內容中...')
            if task_args.get('fetch_details', False):
                args = {
                    'articles_df': articles_df,
                    'num_articles': task_args.get('num_articles', 10),
                    'ai_only': task_args.get('ai_only', True),
                    'min_keywords': task_args.get('min_keywords', 3)
                }
                detailed_df = self.fetch_article_details(args)
            else:
                detailed_df = articles_df
                
            # 步驟3：保存數據
            self._update_task_status(task_id, 80, '保存數據中...')
            save_to_csv = task_args.get('save_to_csv', False)
            csv_path = task_args.get('csv_path', f'articles_{task_id}.csv')
            
            self.save_data(detailed_df, save_to_csv, csv_path)
                
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

   
