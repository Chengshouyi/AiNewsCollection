"""定義爬蟲基類，提供爬取流程的基礎架構和通用方法。"""
# Standard library imports
from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
import os
import time
from typing import Dict, Optional, Any, List, Tuple, Callable
import logging
# Third-party library imports
import pandas as pd

# Local application imports
from src.crawlers.bnext_utils import BnextUtils
from src.crawlers.configs.site_config import SiteConfig
from src.error.errors import ValidationError
from src.interface.progress_reporter import ProgressListener, ProgressReporter
from src.services.article_service import ArticleService
from src.utils.enum_utils import ArticleScrapeStatus, ScrapeMode, ScrapePhase

from src.utils.model_utils import validate_task_args
from src.utils.transform_utils import convert_hashable_dict_to_str_dict


logger = logging.getLogger(__name__)  # 使用統一的 logger  # 使用統一的 logger

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
        self.scrape_phase = {}
        self.config_file_name = config_file_name
        self.articles_df = pd.DataFrame()
        if article_service is None:
            logger.error("未提供文章服務，請提供有效的文章服務")
            raise ValueError("未提供文章服務，請提供有效的文章服務")
        else:
            self.article_service = article_service

        self._create_site_config()

        # 確保任務狀態不包含取消標記
        for task_id in self.scrape_phase:
            if ScrapePhase.CANCELLED.value in self.scrape_phase[task_id]:
                self.scrape_phase[task_id][ScrapePhase.CANCELLED.value] = False

        # 添加進度報告器
        self.progress_reporter = ProgressReporter()

    @abstractmethod # 抓取文章列表
    def _fetch_article_links(self, task_id: int) -> Optional[pd.DataFrame]:
        """
        抓取文章列表

        Returns:
            pd.DataFrame: 包含文章列表的資料框
        """
        raise NotImplementedError("子類別需要實作 _fetch_article_links 方法")
    
    @abstractmethod
    def _fetch_articles(self, task_id: int) -> Optional[List[Dict[str, Any]]]:
        """
        爬取文章詳細內容，子類別需要實作

        Args:
            task_id: 任務ID，用於檢查是否取消

        Returns:
            List[Dict[str, Any]]: 包含文章詳細內容的列表，如果爬取失敗則返回None
        """
        
        raise NotImplementedError("子類別需要實作 _fetch_articles 方法")

    
    @abstractmethod
    def _update_config(self):
        """
        更新爬蟲設定，子類別需要實作
        """
        raise NotImplementedError("子類別需要實作 _update_config 方法")
    
    def _load_site_config(self):
        """載入爬蟲設定，優先從環境變數 WEB_SITE_CONFIG_DIR 讀取目錄"""
        if self.config_file_name:
            try:
                # 從環境變數讀取設定檔目錄，若未設定則使用預設路徑
                config_dir = os.getenv('WEB_SITE_CONFIG_DIR', os.path.join(os.path.dirname(__file__), 'configs'))
                logger.debug("config_dir: %s", config_dir)
                # 確保 config_dir 是絕對路徑或相對於專案根目錄（假設 base_crawler.py 在 src/crawlers 下）
                if not os.path.isabs(config_dir):
                     # 假設腳本在 /app/src/crawlers/base_crawler.py
                    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
                    config_dir = os.path.join(project_root, config_dir)
                
                config_path = os.path.join(config_dir, self.config_file_name)
                
                logger.debug("嘗試讀取配置檔案路徑: %s (來自目錄: %s)", config_path, config_dir)
                
                # 檢查檔案是否存在
                if not os.path.exists(config_path):
                    logger.error("找不到設定檔: %s", config_path)
                    # 可以選擇是使用預設路徑下的檔案，還是直接拋出錯誤
                    # 這裡選擇拋出錯誤，因為如果指定了環境變數但檔案不存在，通常是配置錯誤
                    default_config_path = os.path.join(os.path.dirname(__file__), 'configs', self.config_file_name)
                    if os.path.exists(default_config_path):
                         logger.warning("在指定目錄 %s 中找不到設定檔，將嘗試使用預設路徑 %s", config_dir, default_config_path)
                         config_path = default_config_path
                    else:
                         logger.error("在指定目錄和預設目錄中都找不到設定檔: %s", self.config_file_name)
                         raise FileNotFoundError(f"找不到設定檔: {config_path} 或 {default_config_path}")

                with open(config_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    # 使用文件配置更新默認配置
                    self.config_data.update(file_config)
                
                logger.debug("已載入爬蟲配置: %s (從 %s)", self.config_file_name, config_path)
                logger.debug("已載入爬蟲配置內容: %s", self.config_data)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logger.warning("載入配置文件 %s 失敗: %s，請檢查路徑和檔案內容。", self.config_file_name, e)
                # 根據需求決定是否拋出錯誤或使用預設值
                raise ValueError(f"載入配置文件 {self.config_file_name} 失敗")
            except Exception as e:
                logger.error("載入配置文件 %s 時發生未預期錯誤: %s", self.config_file_name, e, exc_info=True)
                raise ValueError(f"載入配置文件 {self.config_file_name} 時發生未預期錯誤")
        else:
            logger.error("未指定配置文件名稱 (config_file_name)")
            raise ValueError("未指定配置文件名稱")  
        

    def _create_site_config(self):
        """創建站點配置"""
        # 確保先載入配置
        if not self.config_data:
             logger.debug("base_crawler - call_load_site_config()： 載入站點配置")
             # _load_site_config 會在需要時被調用，這裡確保它在創建 SiteConfig 前執行
             try:
                 self._load_site_config()
             except ValueError as e:
                 logger.error("創建 SiteConfig 失敗，因為無法載入配置: %s", e)
                 raise  # 重新拋出錯誤，阻止後續操作

        if not self.config_data: # 再次檢查，如果載入失敗 config_data 仍為空
             logger.error("SiteConfig 創建失敗：配置數據為空。")
             raise ValueError("無法創建 SiteConfig，配置數據為空。")
             
        logger.debug("base_crawler - call_create_site_config()： 創建 site_config")
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
                logger.error("未提供 %s 值，請設定有效值", key)
                raise ValueError(f"未提供 {key} 值，請設定有效值")

    def _fetch_article_links_by_filter(self, **filters) -> Optional[pd.DataFrame]:
        """根據過濾條件從資料庫獲取文章列表

        Args:
            **filters: 可選的過濾條件，直接傳遞給find_articles_advanced方法
                - task_id: 任務ID
                - is_scraped: 是否已抓取內容
                - article_links: 文章連結列表 (特殊處理)
                - keywords: 搜尋關鍵字
                - category: 文章分類
                - is_ai_related: 是否AI相關
                - source: 來源
                - limit: 限制數量 (對應 find_articles_advanced 的 per_page)
                - offset: 偏移量 (對應 find_articles_advanced 的 page 計算)
                - page: 頁碼 (優先於 offset)
        
        Returns:
            pd.DataFrame: 包含文章列表的資料框，如果沒有找到則返回None
        """
        try:
            # 從global_params獲取task_id（如果沒有在filters中指定）
            if 'task_id' not in filters and 'task_id' in self.global_params:
                filters['task_id'] = self.global_params.get('task_id')

            # 處理article_links（需要特殊處理）
            article_links = filters.pop('article_links', self.global_params.get('article_links', []))
            if article_links and len(article_links) > 0:
                # 如果有article_links，則直接建立DataFrame
                articles_data = []
                for link in article_links:
                    # 嘗試從資料庫獲取已存在的文章
                    article_response = self.article_service.get_article_by_link(link)
                    if article_response["success"] and article_response["article"]:
                        # 如果文章已存在，使用資料庫中的資料 (轉換為字典)
                        article_schema = article_response["article"]
                        # 使用 model_dump() 將 Pydantic 模型轉換為字典
                        article_dict = article_schema.model_dump() if hasattr(article_schema, 'model_dump') else vars(article_schema)

                        # 添加必要的轉換，例如將枚舉轉換為其值
                        if 'scrape_status' in article_dict and hasattr(article_dict['scrape_status'], 'value'):
                            article_dict['scrape_status'] = article_dict['scrape_status'].value

                        # 確保所有需要的鍵都存在
                        required_keys = BnextUtils.get_article_columns_dict().keys()
                        for key in required_keys:
                            if key not in article_dict:
                                article_dict[key] = None # 或提供默認值

                        articles_data.append(article_dict)
                    else:
                        # 如果文章不存在，創建一個簡單記錄
                        articles_data.append({
                            'link': link,
                            'title': '',
                            'is_scraped': False,
                            'scrape_status': 'pending'
                        })
                return pd.DataFrame(articles_data)

            # 映射 BaseCrawler 的過濾條件到 ArticleService 的 find_articles_advanced 參數
            advanced_filters = {}
            # 處理分頁: page 優先於 offset
            if 'page' in filters:
                advanced_filters['page'] = filters.pop('page')
                advanced_filters['per_page'] = filters.pop('limit', self.global_params.get('num_articles', 10)) # 使用 limit 作為 per_page
                filters.pop('offset', None) # 移除 offset
            elif 'offset' in filters:
                limit = filters.pop('limit', self.global_params.get('num_articles', 10))
                offset = filters.pop('offset')
                advanced_filters['page'] = (offset // limit) + 1
                advanced_filters['per_page'] = limit
            else:
                 advanced_filters['page'] = 1 # 預設為第1頁
                 advanced_filters['per_page'] = filters.pop('limit', self.global_params.get('num_articles', 10)) # 使用 limit 作為 per_page

            # 處理其他過濾器
            if 'keywords' in filters: advanced_filters['keywords'] = filters.pop('keywords')
            if 'category' in filters: advanced_filters['category'] = filters.pop('category')
            if 'is_ai_related' in filters: advanced_filters['is_ai_related'] = filters.pop('is_ai_related')
            if 'is_scraped' in filters: advanced_filters['is_scraped'] = filters.pop('is_scraped')
            if 'scrape_status' in filters: advanced_filters['scrape_status'] = filters.pop('scrape_status')
            if 'tags' in filters: advanced_filters['tags'] = filters.pop('tags') # 注意: find_articles_advanced 目前只支援單一標籤
            if 'source' in filters: advanced_filters['source'] = filters.pop('source')
            if 'task_id' in filters: advanced_filters['task_id'] = filters.pop('task_id')

            # 處理排序
            if 'sort_by' in filters: advanced_filters['sort_by'] = filters.pop('sort_by')
            if 'sort_desc' in filters: advanced_filters['sort_desc'] = filters.pop('sort_desc')

            # 如果還有未處理的過濾器，記錄警告
            if filters:
                logger.warning("發現未處理的過濾條件: %s，這些條件將被忽略。", filters.keys())

            articles_response = self.article_service.find_articles_advanced(**advanced_filters)

            if articles_response["success"] and articles_response.get("resultMsg") and articles_response["resultMsg"].items:
                # 將文章列表轉換為DataFrame
                articles_data = []
                # 從 PaginatedArticleResponse 中獲取文章列表
                articles_list = articles_response["resultMsg"].items
                for article_schema in articles_list:
                    # 將 Pydantic Schema 轉換為字典
                    article_dict = article_schema.model_dump() if hasattr(article_schema, 'model_dump') else vars(article_schema)

                    # 添加必要的轉換，例如將枚舉轉換為其值
                    if 'scrape_status' in article_dict and hasattr(article_dict['scrape_status'], 'value'):
                        article_dict['scrape_status'] = article_dict['scrape_status'].value

                    articles_data.append(article_dict)

                logger.debug("根據過濾條件獲取文章列表成功: %d篇", len(articles_data))
                return pd.DataFrame(articles_data)
            else:
                message = articles_response.get('message', '未知錯誤')
                # 檢查是否是因為找不到數據而導致的 "失敗"
                if articles_response.get("resultMsg") and not articles_response["resultMsg"].items:
                    logger.info("根據過濾條件未找到任何文章。")
                    return pd.DataFrame() # 返回空的 DataFrame
                else:
                    logger.warning("根據過濾條件獲取文章列表失敗: %s", message)
                    return None
        except Exception as e:
            logger.error("根據過濾條件獲取文章列表失敗: %s", e, exc_info=True)
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

                if self.global_params.get('get_links_by_task_id', False) or self.global_params.get('scrape_mode') == ScrapeMode.CONTENT_ONLY.value:
                    logger.info("調用 article_service.batch_update_articles_by_link...") # 新增日誌
                    result = self.article_service.batch_update_articles_by_link(
                        article_data = str_articles_data
                    )
                else:
                    logger.info("調用 article_service.batch_create_articles...") # 新增日誌
                    result = self.article_service.batch_create_articles(
                        articles_data = str_articles_data
                    )
                
                if not result["success"]:
                    logger.error("批量保存文章到資料庫失敗: %s", result['message'])
                    return
                
                # 設定get_links_by_task_id為True，這個任務下次就不會再去網站抓取文章列表
                self.global_params['get_links_by_task_id'] = True
                logger.info("批量保存文章到資料庫成功: %s", result['message'])
                
        except Exception as e:
            logger.error("保存到資料庫失敗: %s", e)
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
            logger.debug("文章數據已保存到 CSV 文件: %s", csv_path)
        except Exception as e:
            logger.error("保存文章到 CSV 文件失敗: %s", e, exc_info=True)

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
                               if article.get('scrape_status') == ArticleScrapeStatus.CONTENT_SCRAPED.value]
            failed_links = [article['link'] for article in articles_content 
                           if article.get('scrape_status') == ArticleScrapeStatus.FAILED.value]
            
            # 更新成功抓取的文章
            if successful_links:
                merged_df.loc[merged_df['link'].isin(successful_links), 'is_scraped'] = True
                merged_df.loc[merged_df['link'].isin(successful_links), 'scrape_status'] = ArticleScrapeStatus.CONTENT_SCRAPED.value
            
            # 更新失敗的文章
            if failed_links:
                merged_df.loc[merged_df['link'].isin(failed_links), 'is_scraped'] = False
                merged_df.loc[merged_df['link'].isin(failed_links), 'scrape_status'] = ArticleScrapeStatus.FAILED.value
                # 對於失敗的文章，保留錯誤信息和最後嘗試時間，這些已經在原始內容中設置
            
            return merged_df
            
        except Exception as e:
            logger.error("更新文章內容失敗: %s", e, exc_info=True)
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
            try:
                # 修改調用方式，指定 is_update=False 表示這是完整模式而非更新模式
                validated_task_args = validate_task_args('task_args')(task_args, is_update=False)
            except ValidationError as e:
                logger.error("任務參數驗證失敗: %s", e)
                self._update_scrape_phase(task_id, 0, f'任務參數驗證失敗: {str(e)}', ScrapePhase.FAILED)
                return False
            
            # 參數驗證成功，更新全局參數
            if validated_task_args:
                for key, value in validated_task_args.items():
                    self.global_params[key] = value
            
            # 更新配置以確保與新參數兼容
            self._update_config()
            return True
            
        except Exception as e:
            logger.error("更新任務參數失敗: %s", e, exc_info=True)
            self._update_scrape_phase(task_id, 0, f'更新任務參數失敗: {str(e)}', ScrapePhase.FAILED)
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
            task_args: 任務參數 (與crawler_tasks_model.py的task_args對應)
                - max_pages: 最大頁數
                - ai_only: 是否只抓取AI相關文章
                - is_limit_num_articles: 是否限制抓取文章數量
                - num_articles: 抓取的文章數量
                - min_keywords: 最小關鍵字數量
                - max_retries: 最大重試次數
                - retry_delay: 重試延遲時間
                - timeout: 超時時間 
                - is_test: 是否為測試模式
                - save_to_csv: 是否保存到CSV文件
                - csv_file_prefix: CSV檔案名稱前綴，最終文件名格式為 {前綴}_{任務ID}_{時間戳}.csv
                - save_to_database: 是否保存到資料庫
                - scrape_mode: 抓取模式 (LINKS_ONLY, CONTENT_ONLY, FULL_SCRAPE)
                - get_links_by_task_id: 是否從資料庫根據任務ID獲取要抓取內容的文章(scrape_mode=CONTENT_ONLY時有效)
                - article_links: 要抓取內容的文章連結列表 (scrape_mode=CONTENT_ONLY且get_links_by_task_id=False時有效)
                - save_partial_results_on_cancel: 是否在取消時保存部分結果
                - save_partial_to_database: 是否在取消時將部分結果保存到資料庫
                - max_cancel_wait: 最大取消等待時間
                - cancel_interrupt_interval: 取消等待間隔
                - cancel_timeout: 取消超時時間
                
        Returns:
            Dict[str, Any]: 包含任務執行結果
                success: 是否成功
                message: 任務執行結果訊息
                articles_count: 文章數量
                scrape_phase: 任務狀態
                get_links_by_task_id: 是否從資料庫根據任務ID獲取要抓取內容的文章，這個參數會在任務完成後，文章有儲存成功設定為True
        """
        if self.site_config is None:
            logger.error("site_config 未初始化")
            raise ValueError("site_config 未初始化")
        
        # 初始化任務狀態
        self.scrape_phase[task_id] = {
            'scrape_phase': ScrapePhase.INIT.value,
            'progress': 0,
            'message': '開始執行任務',
            'start_time': datetime.now(timezone.utc)
        }
        self.scrape_phase[task_id][ScrapePhase.CANCELLED.value] = False
        # 驗證並更新任務參數
        if not self._validate_and_update_task_params(task_id, task_args):
            return {
                'success': False,
                'message': '任務參數驗證失敗',
                'articles_count': 0,
                'scrape_phase': self.get_scrape_phase(task_id).get('scrape_phase')
            }
        if self._check_if_cancelled(task_id):
            return self._handle_task_cancellation(task_id)
        try:
            # 獲取重試參數
            max_retries = self.global_params.get('max_retries', 3)
            retry_delay = self.global_params.get('retry_delay', 2.0)
            
            # 獲取當前的抓取模式
            scrape_mode = self.global_params.get('scrape_mode', ScrapeMode.FULL_SCRAPE.value)
            if self._check_if_cancelled(task_id):
                return self._handle_task_cancellation(task_id)
            # 根據抓取模式執行不同的流程
            execute_result = {}
            if scrape_mode == ScrapeMode.CONTENT_ONLY.value:
                execute_result = self._execute_content_only_task(task_id, max_retries, retry_delay)
            elif scrape_mode == ScrapeMode.LINKS_ONLY.value:
                execute_result = self._execute_links_only_task(task_id, max_retries, retry_delay)
            else:  # ScrapeMode.FULL_SCRAPE
                execute_result = self._execute_full_scrape_task(task_id, max_retries, retry_delay)
            # 設定get_links_by_task_id為True，這個任務下次就不會再去網站抓取文章列表
            if execute_result.get('success', False):
                execute_result['get_links_by_task_id'] = True

            return execute_result
        except Exception as e:
            # 檢查是否是因為任務取消而引發的異常
            if task_id and "任務 {} 已取消".format(task_id) in str(e):
                return self._handle_task_cancellation(task_id)
            
            self._update_scrape_phase(task_id, 0, f'任務失敗: {str(e)}', ScrapePhase.FAILED)
            logger.error("執行任務失敗 (ID=%s): %s", task_id, e, exc_info=True)
            return {
                'success': False,
                'message': f'任務失敗: {str(e)}',
                'articles_count': 0,
                'scrape_phase': self.get_scrape_phase(task_id).get('scrape_phase'),
                'get_links_by_task_id': self.global_params.get('get_links_by_task_id', False)
            }

    def _execute_content_only_task(self, task_id: int, max_retries: int, retry_delay: float):
        """執行僅抓取內容的任務
        Args:
            task_id: 任務ID
            max_retries: 最大重試次數
            retry_delay: 重試延遲時間
        Returns:
            Dict[str, Any]: 包含任務執行結果
                success: 是否成功
                message: 任務執行結果訊息
                articles_count: 文章數量
                scrape_phase: 任務狀態
        """
        if self._check_if_cancelled(task_id):
            return self._handle_task_cancellation(task_id)
        # 獲取是否從資料庫根據任務ID獲取文章
        get_links_by_task_id = self.global_params.get('get_links_by_task_id', False)
        
        if get_links_by_task_id:
            # 從資料庫獲取文章連結
            logger.info("從資料庫獲取要抓取內容的文章連結")
            # 使用重試機制獲取文章列表
            self.articles_df = self.retry_operation(
                lambda: self._fetch_article_links_by_filter(task_id=task_id, is_scraped=False),
                max_retries=max_retries,
                retry_delay=retry_delay,
                task_id=task_id  # 傳入任務ID以支持取消
            )
            
            # 檢查是否成功獲取文章連結
            if self.articles_df is None or self.articles_df.empty:
                logger.warning("從資料庫未獲取到任何文章連結")
                self._update_scrape_phase(task_id, 100, '從資料庫未獲取到任何文章連結', ScrapePhase.COMPLETED)
                return {
                    'success': False,
                    'message': '從資料庫未獲取到任何文章連結',
                    'articles_count': 0,
                    'scrape_phase': self.get_scrape_phase(task_id).get('scrape_phase')
                }
        else:
            # 獲取要抓取的文章連結
            article_links = self.global_params.get('article_links', [])
            
            if not article_links or len(article_links) == 0:
                logger.warning("沒有提供要抓取內容的文章連結")
                self._update_scrape_phase(task_id, 100, '沒有提供要抓取內容的文章連結', ScrapePhase.COMPLETED)
                return {
                    'success': False,
                    'message': '沒有提供要抓取內容的文章連結',
                    'articles_count': 0,
                    'scrape_phase': self.get_scrape_phase(task_id).get('scrape_phase')
                }
            if self._check_if_cancelled(task_id):
                return self._handle_task_cancellation(task_id)
            # 使用過濾功能獲取文章資訊
            self.articles_df = self.retry_operation(
                lambda: self._fetch_article_links_by_filter(
                    article_links=article_links
                ),
                max_retries=max_retries,
                retry_delay=retry_delay,
                task_id=task_id  # 傳入任務ID以支持取消
            )
        
        # 確認是否有文章要抓取
        if not hasattr(self, 'articles_df') or self.articles_df is None or self.articles_df.empty:
            logger.warning("沒有獲取到要抓取內容的文章資訊")
            self._update_scrape_phase(task_id, 100, '沒有獲取到要抓取內容的文章資訊', ScrapePhase.COMPLETED)
            return {
                'success': False,
                'message': '沒有獲取到要抓取內容的文章資訊',
                'articles_count': 0,
                'scrape_phase': self.get_scrape_phase(task_id).get('scrape_phase')
            }
        
        # 步驟1：抓取文章詳細內容
        articles_count = len(self.articles_df)
        progress_msg = f'抓取文章詳細內容中 (0/{articles_count})...'
        progress = self._calculate_progress('fetch_contents', 0)
        self._update_scrape_phase(task_id, progress, progress_msg)

        # 使用重試機制抓取文章內容
        fetched_articles = self.retry_operation(
            lambda: self._fetch_articles(task_id),
            max_retries=max_retries,
            retry_delay=retry_delay,
            task_id=task_id
        )
        
        # 檢查是否成功獲取文章內容
        if fetched_articles is None or len(fetched_articles) == 0:
            logger.warning("沒有獲取到任何文章內容")
            
            # 即使沒有獲取到內容，仍然保存連結
            self._save_results(task_id)
            
            self._update_scrape_phase(task_id, 100, '沒有獲取到任何文章內容，但已保存連結', ScrapePhase.COMPLETED)
            return {
                'success': True,
                'message': '沒有獲取到任何文章內容，但已保存連結',
                'articles_count': articles_count,
                'scrape_phase': self.get_scrape_phase(task_id).get('scrape_phase')
            }
        
        # 記錄成功獲取的文章內容數量
        content_count = len(fetched_articles)
        logger.info(f"成功獲取 {content_count}/{articles_count} 篇文章內容")

        # 步驟2：更新 articles_df 添加文章內容
        progress = self._calculate_progress('update_dataframe', 0)
        self._update_scrape_phase(task_id, progress, '更新文章數據中...')
        
        # 使用優化的批量更新方法
        self.articles_df = self._update_articles_with_content(self.articles_df, fetched_articles)
        
        progress = self._calculate_progress('update_dataframe', 1)
        self._update_scrape_phase(task_id, progress, '更新文章數據完成')
        
        # 步驟3：保存結果
        self._save_results(task_id)
        
        # 任務完成
        self._update_scrape_phase(task_id, 100, '任務完成', ScrapePhase.COMPLETED)
        
        # 返回成功結果
        return {
            'success': True,
            'message': '任務完成',
            'articles_count': len(self.articles_df) if hasattr(self, 'articles_df') and not self.articles_df.empty else 0,
            'scrape_phase': self.get_scrape_phase(task_id).get('scrape_phase')
        }

    def _execute_links_only_task(self, task_id: int, max_retries: int, retry_delay: float):
        """執行僅抓取連結的任務
        Args:
            task_id: 任務ID
            max_retries: 最大重試次數
            retry_delay: 重試延遲時間
        Returns:
            Dict[str, Any]: 包含任務執行結果
                success: 是否成功
                message: 任務執行結果訊息
                articles_count: 文章數量
                scrape_phase: 任務狀態
        """
        if self._check_if_cancelled(task_id):
            return self._handle_task_cancellation(task_id)
        # 步驟1：抓取文章列表
        fetched_articles_df = self._fetch_article_list(task_id, max_retries, retry_delay)
        
        # 檢查是否成功獲取文章列表
        if fetched_articles_df is None or fetched_articles_df.empty:
            logger.warning("沒有獲取到任何文章連結")
            self._update_scrape_phase(task_id, 100, '沒有獲取到任何文章連結', ScrapePhase.COMPLETED)
            return {
                'success': False,
                'message': '沒有獲取到任何文章連結',
                'articles_count': 0,
                'scrape_phase': self.get_scrape_phase(task_id).get('scrape_phase')
            }
        
        # 記錄找到的文章數量
        articles_count = len(fetched_articles_df)
        logger.info(f"找到 {articles_count} 篇文章連結")
        
        # 將获取的文章列表赋值给 self.articles_df
        self.articles_df = fetched_articles_df
        
        # 步驟2：保存結果
        self._save_results(task_id)
        
        # 任務完成
        self._update_scrape_phase(task_id, 100, '文章連結收集完成', ScrapePhase.COMPLETED)
        
        # 返回成功結果
        return {
            'success': True,
            'message': '文章連結收集完成',
            'articles_count': articles_count,
            'scrape_phase': self.get_scrape_phase(task_id).get('scrape_phase')
        }

    def _execute_full_scrape_task(self, task_id: int, max_retries: int, retry_delay: float):
        """執行完整爬取任務(連結和內容)
        Args:
            task_id: 任務ID
            max_retries: 最大重試次數
            retry_delay: 重試延遲時間
        Returns:
            Dict[str, Any]: 包含任務執行結果
                success: 是否成功
                message: 任務執行結果訊息
                articles_count: 文章數量
                scrape_phase: 任務狀態
        """
        if self._check_if_cancelled(task_id):
            return self._handle_task_cancellation(task_id)
        # 步驟1：抓取文章列表
        fetched_articles_df = self._fetch_article_list(task_id, max_retries, retry_delay)
        
        # 檢查是否成功獲取文章列表
        if fetched_articles_df is None or fetched_articles_df.empty:
            logger.warning("沒有獲取到任何文章連結")
            self._update_scrape_phase(task_id, 100, '沒有獲取到任何文章連結', ScrapePhase.COMPLETED)
            return {
                'success': False,
                'message': '沒有獲取到任何文章連結',
                'articles_count': 0,
                'scrape_phase': self.get_scrape_phase(task_id).get('scrape_phase')
            }
        
        # 記錄找到的文章數量
        articles_count = len(fetched_articles_df)
        logger.info(f"找到 {articles_count} 篇文章連結")
        
        # 將获取的文章列表赋值给 self.articles_df
        self.articles_df = fetched_articles_df
        
        # 步驟2：抓取文章詳細內容
        progress_msg = f'抓取文章詳細內容中 (0/{articles_count})...'
        progress = self._calculate_progress('fetch_contents', 0)
        self._update_scrape_phase(task_id, progress, progress_msg)
        
        # 使用重試機制抓取文章內容
        fetched_articles = self.retry_operation(
            lambda: self._fetch_articles(task_id),
            max_retries=max_retries,
            retry_delay=retry_delay,
            task_id=task_id
        )
        
        # 檢查是否成功獲取文章內容
        if fetched_articles is None or len(fetched_articles) == 0:
            logger.warning("沒有獲取到任何文章內容")
            
            # 即使沒有獲取到內容，仍然保存連結
            self._save_results(task_id)
            
            self._update_scrape_phase(task_id, 100, '沒有獲取到任何文章內容，但已保存連結', ScrapePhase.COMPLETED)
            return {
                'success': True,
                'message': '沒有獲取到任何文章內容，但已保存連結',
                'articles_count': articles_count,
                'scrape_phase': self.get_scrape_phase(task_id).get('scrape_phase')
            }
        
        # 記錄成功獲取的文章內容數量
        content_count = len(fetched_articles)
        logger.info(f"成功獲取 {content_count}/{articles_count} 篇文章內容")
        
        # 步驟3：更新 articles_df 添加文章內容
        progress = self._calculate_progress('update_dataframe', 0)
        self._update_scrape_phase(task_id, progress, '更新文章數據中...')
        
        # 使用優化的批量更新方法
        self.articles_df = self._update_articles_with_content(self.articles_df, fetched_articles)
        
        progress = self._calculate_progress('update_dataframe', 1)
        self._update_scrape_phase(task_id, progress, '更新文章數據完成')
        
        # 步驟4：保存結果
        self._save_results(task_id)
        
        # 任務完成
        self._update_scrape_phase(task_id, 100, '任務完成', ScrapePhase.COMPLETED)
        
        # 返回成功結果
        return {
            'success': True,
            'message': '任務完成',
            'articles_count': len(self.articles_df) if hasattr(self, 'articles_df') and not self.articles_df.empty else 0,
            'scrape_phase': self.get_scrape_phase(task_id).get('scrape_phase')
        }

    def _fetch_article_list(self, task_id: int, max_retries: int = 3, retry_delay: float = 2.0) -> Optional[pd.DataFrame]:
        """抓取文章列表"""
        try:
            progress = self._calculate_progress('fetch_links', 0)
            
            if not self.global_params.get('get_links_by_task_id', False):
                self._update_scrape_phase(task_id, progress, '連接網站抓取文章列表中...')
                logger.info("開始從網站抓取文章列表")
                
                # 使用重試機制
                fetched_articles_df = self.retry_operation(
                    lambda: self._fetch_article_links(task_id),
                    max_retries=max_retries,
                    retry_delay=retry_delay,
                    task_id=task_id  # 傳入任務ID以支持取消
                )
                
                progress = self._calculate_progress('fetch_links', 1)
                self._update_scrape_phase(task_id, progress, '連接網站抓取文章列表完成', ScrapePhase.LINK_COLLECTION)
            else:
                self._update_scrape_phase(task_id, progress, '從資料庫連結獲取文章列表中...', ScrapePhase.LINK_COLLECTION)
                logger.info("開始從資料庫連結獲取文章列表")
                
                # 使用重試機制
                fetched_articles_df = self.retry_operation(
                    lambda: self._fetch_article_links_by_filter(task_id=task_id, is_scraped=False),
                    max_retries=max_retries,
                    retry_delay=retry_delay,
                    task_id=task_id  # 傳入任務ID以支持取消
                )
                
                progress = self._calculate_progress('fetch_links', 1)
                self._update_scrape_phase(task_id, progress, '從資料庫連結獲取文章列表完成', ScrapePhase.LINK_COLLECTION)
            
            return fetched_articles_df
            
        except Exception as e:
            # 檢查是否是因為任務取消而引發的異常
            if task_id and "任務 {} 已取消".format(task_id) in str(e):
                logger.info("抓取文章列表時檢測到任務 %s 已取消", task_id)
                return None
                
            logger.error("抓取文章列表失敗: %s", e, exc_info=True)
            raise
    
    def _save_results(self, task_id: int) -> None:
        """儲存爬蟲結果（CSV和資料庫）"""
        try:
            # 檢查任務是否已取消
            if self._check_if_cancelled(task_id):
                # 如果已取消但仍需要保存部分數據，會在_handle_task_cancellation中處理
                return
                
            # 確認是否有數據要保存
            if self.articles_df is None or self.articles_df.empty:
                logger.warning("沒有數據可供保存")
                return
                
            # 保存到CSV
            if self.global_params.get('save_to_csv', False):
                progress = self._calculate_progress('save_to_csv', 0)
                self._update_scrape_phase(task_id, progress, '保存數據到CSV文件中...', ScrapePhase.SAVE_TO_CSV)
                
                csv_file_prefix = self.global_params.get("csv_file_prefix", "articles")
                # 使用前綴+任務ID+時間戳作為文件名
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                csv_file_name = f"{csv_file_prefix}_{task_id}_{timestamp}.csv"
                csv_path = f'./logs/{csv_file_name}'
                
                self._save_to_csv(self.articles_df, csv_path)
                
                progress = self._calculate_progress('save_to_csv', 1)
                self._update_scrape_phase(task_id, progress, '保存數據到CSV文件完成', ScrapePhase.SAVE_TO_CSV)
            
            # 保存到資料庫
            if self.global_params.get('save_to_database', False):
                progress = self._calculate_progress('save_to_database', 0)
                self._update_scrape_phase(task_id, progress, '保存數據到資料庫中...', ScrapePhase.SAVE_TO_DATABASE)
                
                self._save_to_database()
                
                progress = self._calculate_progress('save_to_database', 1)
                self._update_scrape_phase(task_id, progress, '保存數據到資料庫完成', ScrapePhase.SAVE_TO_DATABASE)
                
        except Exception as e:
            logger.error("保存結果失敗: %s", e, exc_info=True)
            raise
    
    def _update_scrape_phase(self, task_id: int, progress: int, message: str, scrape_phase: Optional[ScrapePhase] = None):
        """更新任務狀態並記錄日誌"""
        if task_id in self.scrape_phase:
            # 更新狀態
            self.scrape_phase[task_id]['progress'] = progress
            self.scrape_phase[task_id]['message'] = message
            if scrape_phase:
                self.scrape_phase[task_id]['scrape_phase'] = scrape_phase.value
                
            # 記錄日誌
            if scrape_phase:
                logger.info("任務 %s %s: %d%%, %s", task_id, scrape_phase.value, progress, message)
            else:
                logger.debug("任務進度更新 (ID=%s): %d%%, %s", task_id, progress, message)
            
            # 通知監聽者
            progress_data = self.get_scrape_phase(task_id)
            self.progress_reporter.notify_progress(task_id, progress_data)
    
    def get_scrape_phase(self, task_id: int):
        """獲取任務狀態"""
        return self.scrape_phase.get(task_id, {
            'scrape_phase': ScrapePhase.UNKNOWN.value,
            'progress': 0,
            'message': '任務不存在'
        })
        
    def retry_operation(self, operation, max_retries=3, retry_delay=2.0, task_id=None):
        """重試操作的通用方法，支持取消檢查
        
        Args:
            operation: 要執行的操作
            max_retries: 最大重試次數
            retry_delay: 重試延遲時間
            task_id: 任務ID，用於檢查是否取消
            
        Returns:
            操作結果
        """
        retries = 0
        while retries < max_retries:
            # 檢查任務是否已取消
            if task_id and self._check_if_cancelled(task_id):
                raise Exception(f"任務 {task_id} 已取消")
            
            try:
                return operation()
            except Exception as e:
                retries += 1
                if retries >= max_retries:
                    logger.error("操作失敗，已重試 %d 次: %s", retries, e)
                    raise e
                
                logger.warning("操作失敗，正在重試 (%d/%d): %s", retries, max_retries, e)
                time.sleep(retry_delay)
                
    def cancel_task(self, task_id: int) -> bool:
        """取消正在執行的任務
        
        Args:
            task_id: 要取消的任務ID
            
        Returns:
            是否成功取消
        """
        if task_id not in self.scrape_phase:
            logger.warning("任務 %s 不存在，無法取消", task_id)
            return False
            
        # 檢查任務狀態，只有運行中的任務才能取消
        if self.scrape_phase[task_id].get('scrape_phase') in [ScrapePhase.CANCELLED.value,  ScrapePhase.FAILED.value, ScrapePhase.COMPLETED.value]:
            logger.warning("任務 %s 當前狀態為 %s，無法取消", task_id, self.scrape_phase[task_id].get('scrape_phase'))
            return False
            
        self.scrape_phase[task_id]['cancel_flag'] = True
        self._update_scrape_phase(task_id, self.scrape_phase[task_id]['progress'], '任務已取消', ScrapePhase.CANCELLED)
        return True

    def _check_if_cancelled(self, task_id: int) -> bool:
        """檢查任務是否已被取消，如已取消則記錄日誌
        
        Args:
            task_id: 任務ID
            
        Returns:
            bool: 是否已取消
        """
        if task_id in self.scrape_phase and self.scrape_phase[task_id].get('cancel_flag', False):
            logger.info("任務 %s 已被取消，停止執行", task_id)
            return True
        return False

    def _handle_task_cancellation(self, task_id: int) -> Dict[str, Any]:
        """處理任務取消時的資源清理和數據處理
        
        當檢測到任務已被取消時，執行必要的清理工作：
        1. 關閉可能的網絡連接
        2. 釋放臨時資源
        3. 保存已獲取的部分數據（如果有價值）
        4. 更新任務狀態
        
        Args:
            task_id: 要處理的任務ID
            
        Returns:
            Dict[str, Any]: 標準化的任務取消響應
        """
        logger.info("正在處理任務 %s 的取消清理工作...", task_id)
        
        # 更新任務狀態為取消
        self._update_scrape_phase(task_id, self.scrape_phase[task_id].get('progress', 0), '任務已取消並清理完成', ScrapePhase.CANCELLED)
        
        # 如果有未保存的有價值數據，可以選擇保存
        partial_data_saved = False
        if hasattr(self, 'articles_df') and self.articles_df is not None and not self.articles_df.empty:
            # 只有當數據達到一定數量且值得保存時才保存
            if len(self.articles_df) >= 5 and self.global_params.get('save_partial_results_on_cancel', False):
                try:
                    # 標記這些數據是由於任務取消而部分保存的
                    self.articles_df['is_partial_save'] = True
                    self.articles_df['cancel_reason'] = '使用者取消任務'
                    
                    # 保存到CSV（如果配置了）
                    if self.global_params.get('save_to_csv', False):
                        # 使用特殊前綴標記是取消的部分保存
                        csv_file_prefix = self.global_params.get("csv_file_prefix", "articles")
                        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
                        csv_file_name = f"{csv_file_prefix}_cancelled_{task_id}_{timestamp}.csv"
                        csv_path = f'./logs/{csv_file_name}'
                        
                        self._save_to_csv(self.articles_df, csv_path)
                        logger.info("已將取消任務的部分數據保存到 %s", csv_path)
                    
                    # 保存到資料庫（如果配置了且獲取了有意義的數據）
                    if self.global_params.get('save_to_database', False) and self.global_params.get('save_partial_to_database', False):
                        # 為防止保存太多無用數據，可以限制只保存已經完成抓取的文章
                        complete_articles = self.articles_df[self.articles_df['is_scraped'] == True].copy()
                        if not complete_articles.empty:
                            # 標記為部分保存
                            complete_articles['scrape_status'] = ArticleScrapeStatus.PARTIAL_SAVED.value
                            
                            # 臨時替換 articles_df 進行保存
                            original_df = self.articles_df
                            self.articles_df = complete_articles
                            self._save_to_database()
                            self.articles_df = original_df
                            
                            logger.info("已將取消任務的 %d 篇完整文章保存到資料庫", len(complete_articles))
                    
                    partial_data_saved = True
                except Exception as e:
                    logger.error("保存取消任務的部分數據時發生錯誤: %s", e)
        
        # 釋放資源：清空DataFrame以釋放記憶體
        if hasattr(self, 'articles_df'):
            self.articles_df = pd.DataFrame()
        
        # 執行其他可能需要的清理工作
        # ... (如關閉網絡連接等)
        
        # 返回標準化的取消響應
        return {
            'success': False,
            'message': '任務已取消' + ('並保存部分數據' if partial_data_saved else ''),
            'articles_count': 0,
            'scrape_phase': self.get_scrape_phase(task_id).get('scrape_phase'),
            'partial_data_saved': partial_data_saved
        }

    # 添加監聽者管理方法
    def add_progress_listener(self, task_id: int, listener: ProgressListener) -> None:
        """添加進度監聽者"""
        self.progress_reporter.add_listener(task_id, listener)
        
    def remove_progress_listener(self, task_id: int, listener: ProgressListener) -> None:
        """移除進度監聽者"""
        self.progress_reporter.remove_listener(task_id, listener)
        
    def clear_progress_listeners(self, task_id: int) -> None:
        """清除指定任務的所有監聽者"""
        self.progress_reporter.clear_listeners(task_id)






   
