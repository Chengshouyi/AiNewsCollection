from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List, Tuple, Callable
import pandas as pd
from datetime import datetime, timezone
import logging
import time
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.crawlers.bnext_utils import BnextUtils
from src.crawlers.configs.site_config import SiteConfig
from src.services.article_service import ArticleService
from src.utils.model_utils import convert_hashable_dict_to_str_dict, validate_positive_int, validate_boolean, validate_str
import enum
from src.models.crawler_tasks_model import ScrapeMode

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

    @abstractmethod # 抓取文章列表
    def _fetch_article_links(self) -> Optional[pd.DataFrame]:
        """
        抓取文章列表
        
        Returns:
            pd.DataFrame: 包含文章列表的資料框
        """
        raise NotImplementedError("子類別需要實作 _fetch_article_links 方法")
    
    @abstractmethod
    def _fetch_articles(self) -> Optional[List[Dict[str, Any]]]:
        """
        爬取文章詳細內容，子類別需要實作
        """
        raise NotImplementedError("子類別需要實作 _fetch_articles 方法")

    
    @abstractmethod
    def _update_config(self):
        """
        更新爬蟲設定，子類別需要實作
        """
        raise NotImplementedError("子類別需要實作 _update_config 方法")
    
    def _load_site_config(self):
        """載入爬蟲設定"""
        if self.config_file_name:
            try:
                with open(f'src/crawlers/configs/{self.config_file_name}', 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    # 使用文件配置更新默認配置
                    self.config_data.update(file_config)
                    
                logger.debug(f"已載入爬蟲配置: {self.config_file_name}")
                logger.debug(f"已載入爬蟲配置: {self.config_data}")
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logger.warning(f"載入配置文件失敗: {str(e)}，使用預設配置")
        else:
            logger.error(f"未找到配置文件")
            raise ValueError("未找到配置文件")  
        

    def _create_site_config(self):
        """創建站點配置"""
        if not self.config_data:
            logger.debug(f"base_crawler - call_load_site_config()： 載入站點配置")
            self._load_site_config()
        
        # 創建 site_config
        logger.debug(f"base_crawler - call_create_site_config()： 創建 site_config")
        self.site_config = SiteConfig(
            name=self.config_data.get("name", None),
            base_url=self.config_data.get("base_url", None),
            list_url_template=self.config_data.get("list_url_template", None),
            categories=self.config_data.get("categories", None),
            full_categories=self.config_data.get("full_categories", None),
            selectors=self.config_data.get("selectors", None)
        )
        
        # 初始化默認參數
        self.global_params = self.DEFAULT_TASK_PARAMS.copy()
        
        # 檢查必要的配置值
        required_site_config_keys = ["name", "base_url", "list_url_template", "categories", "selectors"]
        for key in required_site_config_keys:
            value = getattr(self.site_config, key, None)
            if value is None:
                logger.error(f"未提供 {key} 值，請設定有效值")
                raise ValueError(f"未提供 {key} 值，請設定有效值")

    def _fetch_article_links_by_filter(self, **filters) -> Optional[pd.DataFrame]:
        """根據過濾條件從資料庫獲取文章列表
        
        Args:
            **filters: 可選的過濾條件，直接傳遞給advanced_search_articles方法
                - task_id: 任務ID
                - is_scraped: 是否已抓取內容
                - article_ids: 文章ID列表 (特殊處理)
                - article_links: 文章連結列表 (特殊處理)
                - keywords: 搜尋關鍵字
                - category: 文章分類
                - is_ai_related: 是否AI相關
                - source: 來源
                - limit: 限制數量
                - offset: 偏移量
        
        Returns:
            pd.DataFrame: 包含文章列表的資料框，如果沒有找到則返回None
        """
        try:
            # 從global_params獲取task_id（如果沒有在filters中指定）
            if 'task_id' not in filters and 'task_id' in self.global_params:
                filters['task_id'] = self.global_params.get('task_id')
            
            # 處理article_ids（需要特殊處理，因為advanced_search_articles不直接支援）
            article_ids = filters.pop('article_ids', self.global_params.get('article_ids', []))
            if article_ids:
                # 如果有article_ids，則直接從資料庫獲取這些文章
                articles_data = []
                for article_id in article_ids:
                    article_response = self.article_service.get_article_by_id(article_id)
                    if article_response["success"] and article_response["article"]:
                        article = article_response["article"]
                        articles_data.append(BnextUtils.get_article_columns_dict(
                            title=article.title,
                            summary=article.summary,
                            content=article.content,
                            link=article.link,
                            category=article.category,
                            published_at=article.published_at,
                            author=article.author,
                            source=article.source,
                            source_url=article.source_url,
                            article_type=article.article_type,
                            tags=article.tags,
                            is_ai_related=article.is_ai_related,
                            is_scraped=article.is_scraped,
                            scrape_status=article.scrape_status.value if hasattr(article, 'scrape_status') and article.scrape_status else 'pending',
                            scrape_error=article.scrape_error if hasattr(article, 'scrape_error') else None,
                            last_scrape_attempt=article.last_scrape_attempt if hasattr(article, 'last_scrape_attempt') else None,
                            task_id=article.task_id if hasattr(article, 'task_id') else None
                        ))
                if articles_data:
                    return pd.DataFrame(articles_data)
                return None
            
            # 處理article_links（需要特殊處理）
            article_links = filters.pop('article_links', self.global_params.get('article_links', []))
            if article_links:
                # 如果有article_links，則直接建立DataFrame
                articles_data = []
                for link in article_links:
                    # 嘗試從資料庫獲取已存在的文章
                    article_response = self.article_service.get_article_by_link(link)
                    if article_response["success"] and article_response["article"]:
                        # 如果文章已存在，使用資料庫中的資料
                        article = article_response["article"]
                        articles_data.append(BnextUtils.get_article_columns_dict(
                            title=article.title,
                            summary=article.summary,
                            content=article.content,
                            link=article.link,
                            category=article.category,
                            published_at=article.published_at,
                            author=article.author,
                            source=article.source,
                            source_url=article.source_url,
                            article_type=article.article_type,
                            tags=article.tags,
                            is_ai_related=article.is_ai_related,
                            is_scraped=article.is_scraped,
                            scrape_status=article.scrape_status.value if hasattr(article, 'scrape_status') and article.scrape_status else 'pending',
                            scrape_error=article.scrape_error if hasattr(article, 'scrape_error') else None,
                            last_scrape_attempt=article.last_scrape_attempt if hasattr(article, 'last_scrape_attempt') else None,
                            task_id=article.task_id if hasattr(article, 'task_id') else None
                        ))
                    else:
                        # 如果文章不存在，創建一個簡單記錄
                        articles_data.append({
                            'link': link,
                            'title': '',
                            'is_scraped': False,
                            'scrape_status': 'pending'
                        })
                return pd.DataFrame(articles_data)
            
            # 設定默認的is_scraped值（如果未提供）
            if 'is_scraped' not in filters:
                filters['is_scraped'] = False
            
            # 設定默認的limit值（如果需要）
            if 'limit' not in filters and 'num_articles' in self.global_params:
                filters['limit'] = self.global_params.get('num_articles')
            
            # 使用advanced_search_articles獲取文章列表
            articles_response = self.article_service.advanced_search_articles(**filters)
            
            if articles_response["success"] and articles_response["articles"]:
                # 將文章列表轉換為DataFrame
                articles_data = []
                for article in articles_response["articles"]:
                    articles_data.append(BnextUtils.get_article_columns_dict(
                        title=article.title,
                        summary=article.summary,
                        content=article.content,
                        link=article.link,
                        category=article.category,
                        published_at=article.published_at,
                        author=article.author,
                        source=article.source,
                        source_url=article.source_url,
                        article_type=article.article_type,
                        tags=article.tags,
                        is_ai_related=article.is_ai_related,
                        is_scraped=article.is_scraped,
                        scrape_status=article.scrape_status.value if hasattr(article, 'scrape_status') and article.scrape_status else 'pending',
                        scrape_error=article.scrape_error if hasattr(article, 'scrape_error') else None,
                        last_scrape_attempt=article.last_scrape_attempt if hasattr(article, 'last_scrape_attempt') else None,
                        task_id=article.task_id if hasattr(article, 'task_id') else None
                    ))
                
                logger.debug(f"根據過濾條件獲取文章列表成功: {len(articles_data)}篇")
                return pd.DataFrame(articles_data)
            else:
                logger.warning(f"根據過濾條件獲取文章列表失敗: {articles_response['message']}")
                return None
        except Exception as e:
            logger.error(f"根據過濾條件獲取文章列表失敗: {str(e)}", exc_info=True)
            return None

    def _save_to_database(self):
        """保存爬取到的文章數據"""
        if self.article_service is None:
            logger.error("article_service 未初始化")
            return
        try:
            # 新增文章
            if self.articles_df is None or self.articles_df.empty:
                logger.warning("沒有數據可供保存")
                return
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

                if self.global_params.get('get_links_by_task_id', False):
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
            
            # 先處理基本參數驗證
            for key, value in task_args.items():
                # 特殊處理task_id，直接添加到global_params
                if key == 'task_id':
                    self.global_params['task_id'] = value
                    continue
                
                # 特殊處理scrape_mode
                if key == 'scrape_mode':
                    # 檢查是否為有效的ScrapeMode枚舉值
                    if isinstance(value, str):
                        try:
                            # 嘗試將字符串轉換為枚舉值
                            self.global_params['scrape_mode'] = ScrapeMode(value)
                        except ValueError:
                            logger.error(f"無效的抓取模式: {value}")
                            raise ValueError(f"無效的抓取模式: {value}")
                    elif isinstance(value, ScrapeMode):
                        self.global_params['scrape_mode'] = value
                    else:
                        logger.error(f"抓取模式必須為ScrapeMode枚舉值或對應的字符串")
                        raise ValueError(f"抓取模式必須為ScrapeMode枚舉值或對應的字符串")
                    continue
                
                # 處理其他一般參數
                if key in ['max_pages', 'num_articles', 'min_keywords', 'max_retries', 'timeout']:
                    validated_value = validate_positive_int(key, is_zero_allowed=False)(value)
                    self.global_params[key] = validated_value
                elif key in ['ai_only', 'save_to_csv', 'save_to_database', 'get_links_by_task_id']:
                    validated_value = validate_boolean(key)(value)
                    self.global_params[key] = validated_value
                elif key == 'retry_delay':
                    if not isinstance(value, (int, float)) or value < 0:
                        logger.error(f"參數 {key} 必須為非負數")
                        raise ValueError(f"參數 {key} 必須為非負數")
                    self.global_params[key] = value
                elif key == 'csv_file_prefix':
                    validated_value = validate_str(key, max_length=255)(value)
                    self.global_params[key] = validated_value
                elif key in ['article_ids', 'article_links']:
                    if not isinstance(value, list):
                        logger.error(f"參數 {key} 必須為列表類型")
                        raise ValueError(f"參數 {key} 必須為列表類型")
                    self.global_params[key] = value
                elif key in ['links_only', 'content_only']:
                    # 完全拒絕接受舊版參數
                    logger.error(f"參數 {key} 已不再支援，請改用 scrape_mode 參數")
                    raise ValueError(f"參數 {key} 已不再支援，請改用 scrape_mode 參數")
                else:
                    # 其他未知參數，直接添加到全局參數中
                    logger.info(f"添加未驗證的參數到全局參數: {key}")
                    self.global_params[key] = value
            
            # 確保存在scrape_mode，如果沒有則設置為預設值
            if 'scrape_mode' not in self.global_params:
                self.global_params['scrape_mode'] = ScrapeMode.FULL_SCRAPE
            
            # 根據scrape_mode進行後續驗證
            if self.global_params['scrape_mode'] == ScrapeMode.CONTENT_ONLY:
                get_links_by_task_id = self.global_params.get('get_links_by_task_id', False)
                
                # 當get_links_by_task_id為False時，必須提供article_ids或article_links
                if not get_links_by_task_id:
                    article_ids = self.global_params.get('article_ids', [])
                    article_links = self.global_params.get('article_links', [])
                    
                    if not article_ids and not article_links:
                        logger.error("當抓取模式為CONTENT_ONLY且get_links_by_task_id=False時，必須提供article_ids或article_links")
                        raise ValueError("當抓取模式為CONTENT_ONLY且get_links_by_task_id=False時，必須提供article_ids或article_links")
            
            # 當抓取模式為LINKS_ONLY時，清除無關參數
            if self.global_params['scrape_mode'] == ScrapeMode.LINKS_ONLY:
                if self.global_params.get('article_ids', []) or self.global_params.get('article_links', []):
                    logger.warning("抓取模式為LINKS_ONLY時，article_ids和article_links參數將被忽略")
                
                # 清除無效參數，避免混淆
                if 'article_ids' in self.global_params:
                    del self.global_params['article_ids']
                if 'article_links' in self.global_params:
                    del self.global_params['article_links']
            
            # 更新配置以確保與新參數兼容
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
                - csv_file_prefix: CSV檔案名稱前綴，最終文件名格式為 {前綴}_{任務ID}_{時間戳}.csv
                - save_to_database: 是否保存到資料庫
                - scrape_mode: 抓取模式 (LINKS_ONLY, CONTENT_ONLY, FULL_SCRAPE)
                - get_links_by_task_id: 是否從資料庫根據任務ID獲取要抓取內容的文章(scrape_mode=CONTENT_ONLY時有效)
                - article_ids: 要抓取內容的文章ID列表 (scrape_mode=CONTENT_ONLY且get_links_by_task_id=False時有效)
                - article_links: 要抓取內容的文章連結列表 (scrape_mode=CONTENT_ONLY且get_links_by_task_id=False時有效)
                
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
            
            # 獲取當前的抓取模式
            scrape_mode = self.global_params.get('scrape_mode', ScrapeMode.FULL_SCRAPE)
            
            # 根據抓取模式執行不同的流程
            if scrape_mode == ScrapeMode.CONTENT_ONLY:
                return self._execute_content_only_task(task_id, max_retries, retry_delay)
            elif scrape_mode == ScrapeMode.LINKS_ONLY:
                return self._execute_links_only_task(task_id, max_retries, retry_delay)
            else:  # ScrapeMode.FULL_SCRAPE
                return self._execute_full_scrape_task(task_id, max_retries, retry_delay)
            
        except Exception as e:
            self._update_task_status(task_id, 0, f'任務失敗: {str(e)}', 'failed')
            logger.error(f"執行任務失敗 (ID={task_id}): {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f'任務失敗: {str(e)}',
                'articles_count': 0,
                'task_status': self.get_task_status(task_id)
            }

    def _execute_content_only_task(self, task_id: int, max_retries: int, retry_delay: float):
        """執行僅抓取內容的任務"""
        # 獲取是否從資料庫根據任務ID獲取文章
        get_links_by_task_id = self.global_params.get('get_links_by_task_id', False)
        
        if get_links_by_task_id:
            # 從資料庫獲取文章連結
            logger.info("從資料庫獲取要抓取內容的文章連結")
            # 使用重試機制獲取文章列表
            self.articles_df = self.retry_operation(
                lambda: self._fetch_article_links_by_filter(task_id=task_id, is_scraped=False),
                max_retries=max_retries,
                retry_delay=retry_delay
            )
            
            # 檢查是否成功獲取文章連結
            if self.articles_df is None or self.articles_df.empty:
                logger.warning("從資料庫未獲取到任何文章連結")
                self._update_task_status(task_id, 100, '從資料庫未獲取到任何文章連結', 'completed')
                return {
                    'success': False,
                    'message': '從資料庫未獲取到任何文章連結',
                    'articles_count': 0,
                    'task_status': self.get_task_status(task_id)
                }
        else:
            # 獲取要抓取的文章ID或連結
            article_ids = self.global_params.get('article_ids', [])
            article_links = self.global_params.get('article_links', [])
            
            if not article_ids and not article_links:
                logger.warning("沒有提供要抓取內容的文章ID或連結")
                self._update_task_status(task_id, 100, '沒有提供要抓取內容的文章ID或連結', 'completed')
                return {
                    'success': False,
                    'message': '沒有提供要抓取內容的文章ID或連結',
                    'articles_count': 0,
                    'task_status': self.get_task_status(task_id)
                }
            
            # 使用過濾功能獲取文章資訊
            self.articles_df = self.retry_operation(
                lambda: self._fetch_article_links_by_filter(
                    article_ids=article_ids,
                    article_links=article_links
                ),
                max_retries=max_retries,
                retry_delay=retry_delay
            )
        
        # 確認是否有文章要抓取
        if not hasattr(self, 'articles_df') or self.articles_df is None or self.articles_df.empty:
            logger.warning("沒有獲取到要抓取內容的文章資訊")
            self._update_task_status(task_id, 100, '沒有獲取到要抓取內容的文章資訊', 'completed')
            return {
                'success': False,
                'message': '沒有獲取到要抓取內容的文章資訊',
                'articles_count': 0,
                'task_status': self.get_task_status(task_id)
            }
        
        # 步驟1：抓取文章詳細內容
        articles_count = len(self.articles_df)
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
                'success': True,
                'message': '沒有獲取到任何文章內容，但已保存連結',
                'articles_count': articles_count,
                'task_status': self.get_task_status(task_id)
            }
        
        # 記錄成功獲取的文章內容數量
        content_count = len(fetched_articles)
        logger.info(f"成功獲取 {content_count}/{articles_count} 篇文章內容")
        
        # 步驟2：更新 articles_df 添加文章內容
        progress = self._calculate_progress('update_dataframe', 0)
        self._update_task_status(task_id, progress, '更新文章數據中...')
        
        # 使用優化的批量更新方法
        self.articles_df = self._update_articles_with_content(self.articles_df, fetched_articles)
        
        progress = self._calculate_progress('update_dataframe', 1)
        self._update_task_status(task_id, progress, '更新文章數據完成')
        
        # 步驟3：保存結果
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

    def _execute_links_only_task(self, task_id: int, max_retries: int, retry_delay: float):
        """執行僅抓取連結的任務"""
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

    def _execute_full_scrape_task(self, task_id: int, max_retries: int, retry_delay: float):
        """執行完整爬取任務(連結和內容)"""
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
                'success': True,
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

    def _fetch_article_list(self, task_id: int, max_retries: int = 3, retry_delay: float = 2.0) -> Optional[pd.DataFrame]:
        """抓取文章列表"""
        try:
            progress = self._calculate_progress('fetch_links', 0)
            
            if not self.global_params.get('get_links_by_task_id', False):
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
                    lambda: self._fetch_article_links_by_filter(),
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
            if self.articles_df is None or self.articles_df.empty:
                logger.warning("沒有數據可供保存")
                return
                
            # 保存到CSV
            if self.global_params.get('save_to_csv', False):
                progress = self._calculate_progress('save_to_csv', 0)
                self._update_task_status(task_id, progress, '保存數據到CSV文件中...')
                
                csv_file_prefix = self.global_params.get("csv_file_prefix", "articles")
                # 使用前綴+任務ID+時間戳作為文件名
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                csv_file_name = f"{csv_file_prefix}_{task_id}_{timestamp}.csv"
                csv_path = f'./logs/{csv_file_name}'
                
                self._save_to_csv(self.articles_df, csv_path)
                
                progress = self._calculate_progress('save_to_csv', 1)
                self._update_task_status(task_id, progress, '保存數據到CSV文件完成')
            
            # 保存到資料庫
            if self.global_params.get('save_to_database', False):
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




   
