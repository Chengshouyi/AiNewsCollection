import requests
import logging
from typing import Dict, Optional, List, Any
import pandas as pd
import time
from src.crawlers.configs.base_config import DEFAULT_HEADERS
from src.crawlers.article_analyzer import ArticleAnalyzer
from src.crawlers.bnext_utils import BnextUtils
from src.utils.log_utils import LoggerSetup
from src.utils import datetime_utils
from datetime import datetime, timezone
from src.utils.enum_utils import ArticleScrapeStatus

# 設置日誌記錄器(校正用)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BnextContentExtractor:
    def __init__(self, config=None):
        """
        初始化爬蟲設定
        """
        if config is None:
            logger.error("未提供網站配置，請提供有效的配置")
            raise ValueError("未提供網站配置，請提供有效的配置")
        else:
            self.site_config = config
            
    def update_config(self, config=None):
        """
        更新爬蟲設定
        """
        if config is None:
            logger.error("未提供網站配置，請提供有效的配置")
            raise ValueError("未提供網站配置，請提供有效的配置")
        else:
            self.site_config = config

    def batch_get_articles_content(self, articles_df: pd.DataFrame, num_articles: Optional[int] = None, 
                                   ai_only: bool = True, min_keywords: int = 3) -> List[Dict[str, Any]]:
        """批量獲取文章內容
        
        Args:
            articles_df: 文章DataFrame
            num_articles: 最大處理文章數量，None表示處理所有
            ai_only: 是否只處理AI相關文章
            min_keywords: AI關鍵字最小匹配數量
            
        Returns:
            List[Dict[str, Any]]: 文章內容列表
        """
        result = []
        
        # 如果限制數量，只處理指定數量的文章
        if num_articles is not None:
            articles_df = articles_df.head(num_articles)
        
        for _, article in articles_df.iterrows():
            try:
                # 獲取文章內容
                article_content = self._get_article_content(article['link'])
                
                if article_content:
                    # 如果設置了 ai_only，檢查文章是否AI相關
                    if ai_only and not article_content.get('is_ai_related', False):
                        # 如果需要AI相關但文章不符合，標記為非AI相關並跳過
                        article_content.update({
                            'is_scraped': True,
                            'scrape_status': ArticleScrapeStatus.CONTENT_SCRAPED.value,
                            'scrape_error': '文章不符合 AI 相關條件',
                            'last_scrape_attempt': datetime.now(timezone.utc)
                        })
                    else:
                        # 正常處理AI相關文章
                        article_content.update({
                            'is_scraped': True,
                            'scrape_status': ArticleScrapeStatus.CONTENT_SCRAPED.value,
                            'scrape_error': None,
                            'last_scrape_attempt': datetime.now(timezone.utc)
                        })
                    
                    result.append(article_content)
                else:
                    # 如果獲取失敗，添加錯誤信息
                    result.append({
                        'title': article.get('title', ''),
                        'link': article['link'],
                        'is_scraped': False,
                        'scrape_status': ArticleScrapeStatus.FAILED.value,
                        'scrape_error': '無法獲取文章內容',
                        'last_scrape_attempt': datetime.now(timezone.utc)
                    })
            except Exception as e:
                # 處理異常
                result.append({
                    'title': article.get('title', ''),
                    'link': article['link'],
                    'is_scraped': False,
                    'scrape_status': ArticleScrapeStatus.FAILED.value,
                    'scrape_error': str(e),
                    'last_scrape_attempt': datetime.now(timezone.utc)
                })
        
        return result

    def _get_article_content(self, article_url: str, ai_only: bool = True, min_keywords: int = 3) -> Optional[Dict]:
        """獲取文章詳細內容"""
        logger.debug(f"開始獲取文章內容: {article_url}")
        start_time = time.time()
        
        try:
            BnextUtils.sleep_random_time(2.0, 4.0)
            
            response = requests.get(article_url, headers=DEFAULT_HEADERS, timeout=15)
            if response.status_code != 200:
                logger.error(f"請求失敗 ({response.status_code}): {article_url}")
                return None
            
            logger.debug("成功獲取網頁內容")
            
            soup = BnextUtils.get_soup_from_html(response.text)
            if self.site_config is None:
                logger.error("未提供選擇器，請提供有效的配置")
                raise ValueError("未提供選擇器，請提供有效的配置")
            
            selectors = self.site_config.selectors
            get_article_contents_selectors = selectors.get('get_article_contents')
            #logger.debug(f"get_article_contents_selectors: {get_article_contents_selectors}")

            # 提取文章內容
            article_content_container = soup.select(get_article_contents_selectors.get("content_container"))
            if not article_content_container:
                logger.error(f"無法找到文章container: {article_url}")
                return None
            #logger.debug(f"article_content_container: {article_content_container}")
            article_content = self._extract_article_parts(article_content_container, soup, get_article_contents_selectors, article_url, ai_only, min_keywords)
            if article_content is None:
                logger.error(f"文章內容提取失敗: {article_url}")
                return None
            
            # AI 相關性檢查
            if ai_only:
                is_ai_related = ArticleAnalyzer().is_ai_related(article_content, min_keywords=min_keywords)
                logger.debug(f"AI相關性檢查 (最小匹配關鍵字數: {min_keywords}): {'通過' if is_ai_related else '未通過'}")
                if not is_ai_related:
                    # 準備當前時間作為最後抓取嘗試時間
                    current_time = datetime.now(timezone.utc)
                    
                    # 創建帶有特殊標記的記錄，表示文章不相關
                    non_ai_record = article_content.copy()
                    non_ai_record.update({
                        'is_ai_related': False,
                        'is_scraped': True,
                        'scrape_status': ArticleScrapeStatus.CONTENT_SCRAPED.value,
                        'scrape_error': "文章不符合 AI 相關條件",
                        'last_scrape_attempt': current_time
                    })
                    return non_ai_record
            
            end_time = time.time()
            logger.debug(f"文章內容獲取完成，耗時: {end_time - start_time:.2f}秒")
            
            return article_content
            
        except Exception as e:
            logger.error(f"獲取文章內容失敗: {str(e)}", exc_info=True)
            return None

    def _extract_article_parts(self, article_content_container, soup, get_article_contents_selectors, article_url: str, ai_only: bool = True, min_keywords: int = 3):
        """提取文章各個部分"""
        logger.debug("開始提取文章各部分內容")
        
        if not article_content_container:
            logger.error("沒有提供文章container")
            return None
        
        logger.debug(f"找到文章container數量: {len(article_content_container)}")
        
        try:
            # 獲取主要容器以避免重複訪問
            main_container = article_content_container[0]
            
            # 提取各個部分並記錄日誌
            category = main_container.select_one(get_article_contents_selectors.get("category"))
            category_text = category.get_text(strip=True) if category else None
            logger.debug(f"提取文章category: {category_text}")
            
            published_date = main_container.select_one(get_article_contents_selectors.get("published_date"))
            published_date_text = published_date.get_text(strip=True) if published_date else None
            logger.debug(f"提取文章published_date: {published_date_text}")
            try:
                if published_date_text:
                    published_date_text = datetime_utils.convert_str_to_utc_ISO_str(published_date_text)
            except Exception as e:
                logger.error(f"日期格式轉換錯誤: {str(e)}", exc_info=True)
                published_date_text = None
            logger.debug(f"轉換文章published_date: {published_date_text}")
            
            title = main_container.select_one(get_article_contents_selectors.get("title"))
            title_text = title.get_text(strip=True) if title else None
            logger.debug(f"提取文章title: {title_text}")
            
            summary = main_container.select_one(get_article_contents_selectors.get("summary"))
            summary_text = summary.get_text(strip=True) if summary else None
            logger.debug(f"提取文章summary: {summary_text}")

            
            # 提取標籤
            tags = []
            tag_container_selector = get_article_contents_selectors.get("tags").get("container")
            tag_container = main_container.select_one(tag_container_selector)
            if not tag_container:
                logger.debug(f"該文章沒有標籤容器: {article_url}")
            else:
                logger.debug(f"找到標籤容器")
                for container in tag_container.find_all(get_article_contents_selectors.get("tags").get("tag"), recursive=False):
                    tag_text = container.get_text(strip=True)
                    logger.debug(f"找到Tag: {tag_text}")
                    tags.append(tag_text)

            author = main_container.select_one(get_article_contents_selectors.get("author"))
            author_text = author.get_text(strip=True) if author else None
            logger.debug(f'提取author: {author_text}')

            # 提取內容
            full_content = ""
            content_container = main_container.select_one(get_article_contents_selectors.get("content"))
            if content_container:
                all_text = []
                for element in content_container.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol']):
                    text = element.get_text(strip=True)
                    if text:
                        all_text.append(text)
                full_content = "\n".join(all_text)
                logger.debug(f'提取content: {full_content[:100]}...') # 只記錄前100個字符

                if summary_text is None:
                    summary_text = full_content[:100]
                    logger.debug(f"文章摘要為空，使用內容前100字作為摘要")
                if title_text is None:
                    title_text = full_content[:50]
                    logger.debug(f"文章標題為空，使用內容前50字作為標題")
                if category_text is None:
                    category_text = "未分類"
                    logger.debug(f"文章分類為空，使用「未分類」作為分類")
            else:
                logger.error("找不到文章內容容器")
                return None

            # 準備當前時間作為最後抓取嘗試時間
            current_time = datetime.now(timezone.utc)
            
            # 返回提取的所有部分
            return BnextUtils.get_article_columns_dict(
                title=title_text,
                summary=summary_text,
                content=full_content,
                link=article_url,
                category=category_text,
                published_at=published_date_text,
                author=author_text,
                source=self.site_config.name,
                source_url=self.site_config.base_url,
                article_type=None,
                tags=",".join(tags),
                is_ai_related=ai_only,
                is_scraped=True,
                scrape_status=ArticleScrapeStatus.CONTENT_SCRAPED.value,
                scrape_error=None,
                last_scrape_attempt=current_time,
                task_id=None  # 將在 base_crawler 中填充
            )
            
        except Exception as e:
            logger.error(f"提取文章部分時發生錯誤: {str(e)}", exc_info=True)
            # 準備當前時間作為最後抓取嘗試時間
            current_time = datetime.now(timezone.utc)
            
            # 記錄錯誤但返回基本結構
            return BnextUtils.get_article_columns_dict(
                title=None,
                summary=None,
                content=None,
                link=article_url,
                category=None,
                published_at=None,
                author=None,
                source=self.site_config.name,
                source_url=self.site_config.base_url,
                article_type=None,
                tags=None,
                is_ai_related=False,
                is_scraped=False,
                scrape_status=ArticleScrapeStatus.FAILED.value,
                scrape_error=str(e),
                last_scrape_attempt=current_time,
                task_id=None  # 將在 base_crawler 中填充
            )
