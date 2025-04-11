from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List, Tuple, Callable
import pandas as pd
from datetime import datetime, timezone
import logging
import time
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.crawlers.configs.site_config import SiteConfig
from src.services.article_service import ArticleService
from src.utils.model_utils import convert_hashable_dict_to_str_dict

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BaseCrawler(ABC):
    # 任務權重配置，用於動態計算進度百分比
    TASK_WEIGHTS = {
        'fetch_links': 20,         # 抓取文章列表佔 20%
        'fetch_contents': 50,      # 抓取文章內容佔 50%
        'update_dataframe': 10,    # 更新數據佔 10%
        'save_to_csv': 10,         # 保存到 CSV 佔 10%
        'save_to_database': 10     # 保存到數據庫佔 10%
    }
    
    # 默認任務參數
    DEFAULT_TASK_PARAMS = {
        'max_retries': 3,         # 最大重試次數
        'retry_delay': 2.0,       # 重試延遲時間（秒）
        'timeout': 15             # 超時時間（秒）
    }

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
        
        # 初始化默認參數
        self.global_params = self.DEFAULT_TASK_PARAMS.copy()
        
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
                # 將task_id添加到每個文章數據中，如果global_params中存在
                if 'task_id' in self.global_params:
                    for article in articles_data:
                        # 確保task_id不會被覆蓋，只有沒有設置時才添加
                        if 'task_id' not in article or article['task_id'] is None:
                            article['task_id'] = self.global_params['task_id']
                
                # 處理 datetime 和 枚舉類型
                for article in articles_data:
                    # 處理 scrape_status，確保使用字串值而非枚舉對象
                    if 'scrape_status' in article and not isinstance(article['scrape_status'], str):
                        if hasattr(article['scrape_status'], 'value'):
                            article['scrape_status'] = article['scrape_status'].value
                        else:
                            article['scrape_status'] = str(article['scrape_status'])
                            
                str_articles_data = [convert_hashable_dict_to_str_dict(article) for article in articles_data]

                if self.site_config.article_settings.get('from_db_link', False):
                    result = self.article_service.batch_update_articles_by_link(
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

    def _update_articles_with_content(self, articles_df: pd.DataFrame, articles_content: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        使用批量更新方式更新 DataFrame 中的文章內容
        
        Args:
            articles_df: 原始文章 DataFrame
            articles_content: 包含文章內容的列表
            
        Returns:
            更新後的 DataFrame
        """
        if not articles_content:
            return articles_df
        
        try:
            # 創建一個新的 DataFrame 包含文章內容
            content_df = pd.DataFrame(articles_content)
            
            if content_df.empty:
                return articles_df
                
            # 確保兩個 DataFrame 都有 'link' 列
            if 'link' not in articles_df.columns or 'link' not in content_df.columns:
                logger.error("文章資料缺少 'link' 欄位，無法更新")
                return articles_df
            
            # 以 'link' 為鍵合併兩個 DataFrame
            # 使用 left 連接保留原始 DataFrame 中的所有行
            # 更新重複的列使用右側 DataFrame (文章內容) 的值
            merged_df = articles_df.merge(
                content_df, 
                on='link', 
                how='left', 
                suffixes=('', '_new')
            )
            
            # 處理合併後的列
            for col in content_df.columns:
                if col != 'link' and f'{col}_new' in merged_df.columns:
                    # 優先使用新值，如果是 NaN 則保留原值
                    mask = merged_df[f'{col}_new'].notna()
                    
                    # 針對布爾型欄位進行特殊處理
                    if col == 'is_scraped' or col == 'is_ai_related':
                        # 確保是布爾型
                        merged_df.loc[mask, col] = merged_df.loc[mask, f'{col}_new'].astype(bool)
                    else:
                        merged_df.loc[mask, col] = merged_df.loc[mask, f'{col}_new']
                    
                    # 刪除臨時列
                    merged_df = merged_df.drop(f'{col}_new', axis=1)
                    
            # 更新抓取相關標記
            successful_links = [article['link'] for article in articles_content 
                               if article.get('scrape_status') == 'content_scraped']
            failed_links = [article['link'] for article in articles_content 
                           if article.get('scrape_status') == 'failed']
            
            # 更新成功抓取的文章
            if successful_links:
                merged_df.loc[merged_df['link'].isin(successful_links), 'is_scraped'] = True
                merged_df.loc[merged_df['link'].isin(successful_links), 'scrape_status'] = 'content_scraped'
            
            # 更新失敗的文章
            if failed_links:
                merged_df.loc[merged_df['link'].isin(failed_links), 'is_scraped'] = False
                merged_df.loc[merged_df['link'].isin(failed_links), 'scrape_status'] = 'failed'
                # 對於失敗的文章，保留錯誤信息和最後嘗試時間，這些已經在原始內容中設置
            
            return merged_df
            
        except Exception as e:
            logger.error(f"更新文章內容失敗: {str(e)}", exc_info=True)
            return articles_df

    def _validate_and_update_task_params(self, task_id: int, task_args: Dict[str, Any]) -> bool:
        """
        驗證並更新任務參數
        
        Args:
            task_id: 任務ID
            task_args: 任務參數
            
        Returns:
            更新是否成功
        """
        if not task_args:
            return True
            
        try:
            # 保存任務ID到全局參數
            self.global_params['task_id'] = task_id
            
            # 驗證參數
            for key, value in task_args.items():
                # 檢查參數是否存在於配置或全局參數中
                if key in self.site_config.article_settings:
                    setting_container = self.site_config.article_settings
                elif key in self.site_config.extraction_settings:
                    setting_container = self.site_config.extraction_settings
                elif key in self.site_config.storage_settings:
                    setting_container = self.site_config.storage_settings
                elif key in self.global_params:
                    setting_container = self.global_params
                # 特殊處理task_id，直接添加到global_params
                elif key == 'task_id':
                    self.global_params['task_id'] = value
                    continue
                # 處理特殊參數，這些參數不需要存在於設定中
                elif key in ['links_only', 'content_only', 'article_ids', 'article_links']:
                    self.global_params[key] = value
                    continue
                else:
                    logger.error(f"未知的任務參數: {key}")
                    raise ValueError(f"未知的任務參數: {key}")
                
                # 根據參數類型進行驗證
                if key in ['max_pages', 'num_articles', 'min_keywords', 'max_retries', 'timeout']:
                    if not isinstance(value, int) or value < 0:
                        logger.error(f"參數 {key} 必須為非負整數")
                        raise ValueError(f"參數 {key} 必須為非負整數")
                elif key in ['ai_only', 'save_to_csv', 'save_to_database']:
                    if not isinstance(value, bool):
                        logger.error(f"參數 {key} 必須為布爾值")
                        raise ValueError(f"參數 {key} 必須為布爾值")
                elif key == 'retry_delay':
                    if not isinstance(value, (int, float)) or value < 0:
                        logger.error(f"參數 {key} 必須為非負數")
                        raise ValueError(f"參數 {key} 必須為非負數")
                
                # 更新參數
                setting_container[key] = value
            
            # 應用配置更新
            self._update_config()
            return True
            
        except Exception as e:
            logger.error(f"更新任務參數失敗: {str(e)}", exc_info=True)
            self._update_task_status(task_id, 0, f'更新任務參數失敗: {str(e)}', 'failed')
            return False

    def _calculate_progress(self, stage: str, sub_progress: float = 1.0) -> int:
        """
        根據任務階段和子進度計算整體進度百分比
        
        Args:
            stage: 任務階段名稱
            sub_progress: 該階段的完成進度 (0.0-1.0)
            
        Returns:
            整體進度百分比 (0-100)
        """
        # 確保子進度在有效範圍內
        sub_progress = max(0.0, min(1.0, sub_progress))
        
        # 獲取階段權重
        stage_weight = self.TASK_WEIGHTS.get(stage, 0)
        
        # 計算已完成的階段總權重
        completed_weight = 0
        stages = list(self.TASK_WEIGHTS.keys())
        stage_index = stages.index(stage) if stage in stages else -1
        
        if stage_index > 0:
            for i in range(stage_index):
                completed_weight += self.TASK_WEIGHTS.get(stages[i], 0)
        
        # 計算當前階段的權重貢獻
        current_weight = stage_weight * sub_progress
        
        # 計算總進度
        total_progress = int((completed_weight + current_weight) / sum(self.TASK_WEIGHTS.values()) * 100)
        
        # 確保進度在 0-100 範圍內
        return max(0, min(100, total_progress))

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
                - links_only: 是否只抓取連結
                - content_only: 是否只抓取內容
                - article_ids: 要抓取內容的文章ID列表 (content_only=True時有效)
                - article_links: 要抓取內容的文章連結列表 (content_only=True時有效)
                
        Returns:
            Dict[str, Any]: 任務狀態
        """
        if self.site_config is None:
            logger.error("site_config 未初始化")
            raise ValueError("site_config 未初始化")
        
        # 初始化任務狀態
        self.task_status[task_id] = {
            'status': 'running',
            'progress': 0,
            'message': '開始執行任務',
            'start_time': datetime.now(timezone.utc)
        }
        
        # 驗證並更新任務參數
        if not self._validate_and_update_task_params(task_id, task_args):
            return {
                'success': False,
                'message': '任務參數驗證失敗',
                'articles_count': 0,
                'task_status': self.get_task_status(task_id)
            }
        
        try:
            # 獲取重試參數
            max_retries = self.global_params.get('max_retries', 3)
            retry_delay = self.global_params.get('retry_delay', 2.0)
            
            # 檢查是否僅抓取內容
            if task_args.get('content_only', False):
                # 獲取要抓取的文章ID或連結
                article_ids = task_args.get('article_ids', [])
                article_links = task_args.get('article_links', [])
                
                if not article_ids and not article_links:
                    logger.warning("沒有提供要抓取內容的文章ID或連結")
                    self._update_task_status(task_id, 100, '沒有提供要抓取內容的文章ID或連結', 'completed')
                    return {
                        'success': False,
                        'message': '沒有提供要抓取內容的文章ID或連結',
                        'articles_count': 0,
                        'task_status': self.get_task_status(task_id)
                    }
                
                # 根據提供的連結直接抓取內容
                # 這裡假設已經有文章資料，只是要抓取內容
                # 實際可能需要根據ID或連結從資料庫中獲取文章，再抓取內容
                
                # 建立一個包含要抓取文章的DataFrame
                if article_links:
                    # 如果有提供連結，將連結轉為DataFrame
                    import pandas as pd
                    self.articles_df = pd.DataFrame({'link': article_links})
                    # 添加其他必要欄位，根據爬蟲的需要
                    # 這裡只是示例，實際可能需要更多欄位
                    self.articles_df['is_scraped'] = False
                    
                # 步驟1：抓取文章詳細內容
                progress_msg = f'抓取文章詳細內容中 (0/{len(article_links or article_ids)})...'
                progress = self._calculate_progress('fetch_contents', 0)
                self._update_task_status(task_id, progress, progress_msg)
                
                # 使用重試機制抓取文章內容
                fetched_articles = self.retry_operation(
                    lambda: self._fetch_articles(),
                    max_retries=max_retries,
                    retry_delay=retry_delay
                )
                
                # 檢查是否成功獲取文章內容
                if fetched_articles is None or len(fetched_articles) == 0:
                    logger.warning("沒有獲取到任何文章內容")
                    self._update_task_status(task_id, 100, '沒有獲取到任何文章內容', 'completed')
                    return {
                        'success': False,
                        'message': '沒有獲取到任何文章內容',
                        'articles_count': 0,
                        'task_status': self.get_task_status(task_id)
                    }
                
                # 記錄成功獲取的文章內容數量
                content_count = len(fetched_articles)
                logger.info(f"成功獲取 {content_count} 篇文章內容")
                
                # 步驟2：更新文章內容
                progress = self._calculate_progress('update_dataframe', 0)
                self._update_task_status(task_id, progress, '更新文章數據中...')
                
                # 使用優化的批量更新方法
                if hasattr(self, 'articles_df') and not self.articles_df.empty:
                    self.articles_df = self._update_articles_with_content(self.articles_df, fetched_articles)
                
                progress = self._calculate_progress('update_dataframe', 1)
                self._update_task_status(task_id, progress, '更新文章數據完成')
                
                # 步驟3：保存結果
                self._save_results(task_id)
                
                # 任務完成
                self._update_task_status(task_id, 100, '抓取文章內容完成', 'completed')
                
                # 返回成功結果
                return {
                    'success': True,
                    'message': '抓取文章內容完成',
                    'articles_count': content_count,
                    'task_status': self.get_task_status(task_id)
                }
            # 檢查是否僅抓取連結
            elif task_args.get('links_only', False):
                # 步驟1：抓取文章列表
                fetched_articles_df = self._fetch_article_list(task_id, max_retries, retry_delay)
                
                # 檢查是否成功獲取文章列表
                if fetched_articles_df is None or fetched_articles_df.empty:
                    logger.warning("沒有獲取到任何文章連結")
                    self._update_task_status(task_id, 100, '沒有獲取到任何文章連結', 'completed')
                    return {
                        'success': False,
                        'message': '沒有獲取到任何文章連結',
                        'articles_count': 0,
                        'task_status': self.get_task_status(task_id)
                    }
                
                # 記錄找到的文章數量
                articles_count = len(fetched_articles_df)
                logger.info(f"找到 {articles_count} 篇文章連結")
                
                # 將获取的文章列表赋值给 self.articles_df
                self.articles_df = fetched_articles_df
                
                # 步驟2：保存結果
                self._save_results(task_id)
                
                # 任務完成
                self._update_task_status(task_id, 100, '文章連結收集完成', 'completed')
                
                # 返回成功結果
                return {
                    'success': True,
                    'message': '文章連結收集完成',
                    'articles_count': articles_count,
                    'task_status': self.get_task_status(task_id)
                }
            else:
                # 完整流程：抓取連結和內容
                # 步驟1：抓取文章列表
                fetched_articles_df = self._fetch_article_list(task_id, max_retries, retry_delay)
                
                # 檢查是否成功獲取文章列表
                if fetched_articles_df is None or fetched_articles_df.empty:
                    logger.warning("沒有獲取到任何文章連結")
                    self._update_task_status(task_id, 100, '沒有獲取到任何文章連結', 'completed')
                    return {
                        'success': False,
                        'message': '沒有獲取到任何文章連結',
                        'articles_count': 0,
                        'task_status': self.get_task_status(task_id)
                    }
                
                # 記錄找到的文章數量
                articles_count = len(fetched_articles_df)
                logger.info(f"找到 {articles_count} 篇文章連結")
                
                # 將获取的文章列表赋值给 self.articles_df
                self.articles_df = fetched_articles_df
                
                # 步驟2：抓取文章詳細內容
                progress_msg = f'抓取文章詳細內容中 (0/{articles_count})...'
                progress = self._calculate_progress('fetch_contents', 0)
                self._update_task_status(task_id, progress, progress_msg)
                
                # 使用重試機制抓取文章內容
                fetched_articles = self.retry_operation(
                    lambda: self._fetch_articles(),
                    max_retries=max_retries,
                    retry_delay=retry_delay
                )
                
                # 檢查是否成功獲取文章內容
                if fetched_articles is None or len(fetched_articles) == 0:
                    logger.warning("沒有獲取到任何文章內容")
                    
                    # 即使沒有獲取到內容，仍然保存連結
                    self._save_results(task_id)
                    
                    self._update_task_status(task_id, 100, '沒有獲取到任何文章內容，但已保存連結', 'completed')
                    return {
                        'success': True,  # 這裡改為true，因為連結已保存成功
                        'message': '沒有獲取到任何文章內容，但已保存連結',
                        'articles_count': articles_count,
                        'task_status': self.get_task_status(task_id)
                    }
                
                # 記錄成功獲取的文章內容數量
                content_count = len(fetched_articles)
                logger.info(f"成功獲取 {content_count}/{articles_count} 篇文章內容")
                
                # 步驟3：更新 articles_df 添加文章內容
                progress = self._calculate_progress('update_dataframe', 0)
                self._update_task_status(task_id, progress, '更新文章數據中...')
                
                # 使用優化的批量更新方法
                self.articles_df = self._update_articles_with_content(self.articles_df, fetched_articles)
                
                progress = self._calculate_progress('update_dataframe', 1)
                self._update_task_status(task_id, progress, '更新文章數據完成')
                
                # 步驟4：保存結果
                self._save_results(task_id)
                
                # 任務完成
                self._update_task_status(task_id, 100, '任務完成', 'completed')
                
                # 返回成功結果
                return {
                    'success': True,
                    'message': '任務完成',
                    'articles_count': len(self.articles_df) if hasattr(self, 'articles_df') and not self.articles_df.empty else 0,
                    'task_status': self.get_task_status(task_id)
                }
            
        except Exception as e:
            self._update_task_status(task_id, 0, f'任務失敗: {str(e)}', 'failed')
            logger.error(f"執行任務失敗 (ID={task_id}): {str(e)}", exc_info=True)
            # 返回失敗結果
            return {
                'success': False,
                'message': f'任務失敗: {str(e)}',
                'articles_count': 0,
                'task_status': self.get_task_status(task_id)
            }
    
    def _fetch_article_list(self, task_id: int, max_retries: int = 3, retry_delay: float = 2.0) -> Optional[pd.DataFrame]:
        """抓取文章列表"""
        try:
            progress = self._calculate_progress('fetch_links', 0)
            
            if not self.site_config.article_settings.get('from_db_link', False):
                self._update_task_status(task_id, progress, '連接網站抓取文章列表中...')
                logger.info("開始從網站抓取文章列表")
                
                # 使用重試機制
                fetched_articles_df = self.retry_operation(
                    lambda: self._fetch_article_links(),
                    max_retries=max_retries,
                    retry_delay=retry_delay
                )
                
                progress = self._calculate_progress('fetch_links', 1)
                self._update_task_status(task_id, progress, '連接網站抓取文章列表完成')
            else:
                self._update_task_status(task_id, progress, '從資料庫連結獲取文章列表中...')
                logger.info("開始從資料庫連結獲取文章列表")
                
                # 使用重試機制
                fetched_articles_df = self.retry_operation(
                    lambda: self._fetch_article_links_from_db(),
                    max_retries=max_retries,
                    retry_delay=retry_delay
                )
                
                progress = self._calculate_progress('fetch_links', 1)
                self._update_task_status(task_id, progress, '從資料庫連結獲取文章列表完成')
                
            return fetched_articles_df
            
        except Exception as e:
            logger.error(f"抓取文章列表失敗: {str(e)}", exc_info=True)
            raise
    
    def _save_results(self, task_id: int) -> None:
        """儲存爬蟲結果（CSV和資料庫）"""
        try:
            # 確認是否有數據要保存
            if self.articles_df.empty:
                logger.warning("沒有數據可供保存")
                return
                
            # 保存到CSV
            if self.site_config.storage_settings.get('save_to_csv', False):
                progress = self._calculate_progress('save_to_csv', 0)
                self._update_task_status(task_id, progress, '保存數據到CSV文件中...')
                
                csv_file_name = self.site_config.storage_settings.get("csv_file_name", f"articles_{task_id}.csv")
                csv_path = f'./logs/{csv_file_name}'
                
                self._save_to_csv(self.articles_df, csv_path)
                
                progress = self._calculate_progress('save_to_csv', 1)
                self._update_task_status(task_id, progress, '保存數據到CSV文件完成')
            
            # 保存到資料庫
            if self.site_config.storage_settings.get('save_to_database', False):
                progress = self._calculate_progress('save_to_database', 0)
                self._update_task_status(task_id, progress, '保存數據到資料庫中...')
                
                self._save_to_database()
                
                progress = self._calculate_progress('save_to_database', 1)
                self._update_task_status(task_id, progress, '保存數據到資料庫完成')
                
        except Exception as e:
            logger.error(f"保存結果失敗: {str(e)}", exc_info=True)
            raise
    
    def _update_task_status(self, task_id: int, progress: int, message: str, status: Optional[str] = None):
        """更新任務狀態並記錄日誌"""
        if task_id in self.task_status:
            # 更新狀態
            self.task_status[task_id]['progress'] = progress
            self.task_status[task_id]['message'] = message
            if status:
                self.task_status[task_id]['status'] = status
                
            # 記錄日誌
            if status:
                logger.info(f"任務 {task_id} {status}: {progress}%, {message}")
            else:
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
                
    def cancel_task(self, task_id: int) -> bool:
        """取消正在執行的任務
        
        Args:
            task_id: 要取消的任務ID
            
        Returns:
            是否成功取消
        """
        if task_id not in self.task_status:
            logger.warning(f"任務 {task_id} 不存在，無法取消")
            return False
            
        status = self.task_status[task_id]['status']
        if status not in ['running', 'paused']:
            logger.warning(f"任務 {task_id} 當前狀態為 {status}，無法取消")
            return False
            
        # 更新任務狀態
        self._update_task_status(task_id, self.task_status[task_id]['progress'], '任務已取消', 'cancelled')
        logger.info(f"任務 {task_id} 已被取消")
        return True




   
