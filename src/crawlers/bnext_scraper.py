"""定義 BnextScraper 類別，用於爬取 Bnext 網站的文章列表。"""
import logging
import time
import re
import random
from datetime import datetime, timezone

import requests
import pandas as pd

from src.crawlers.configs.base_config import DEFAULT_HEADERS
from src.crawlers.article_analyzer import ArticleAnalyzer
from src.crawlers.bnext_utils import BnextUtils
from src.utils.log_utils import LoggerSetup
from src.utils.enum_utils import ArticleScrapeStatus
# from src.utils.enum_utils import ScrapePhase # ScrapePhase seems unused

# 使用統一的 logger
logger = LoggerSetup.setup_logger(__name__)


class BnextScraper:
    def __init__(self, config=None):
        """
        初始化爬蟲
        
        Parameters:
        config: 網站配置
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

    def scrape_article_list(self, max_pages=3, ai_only=True, min_keywords=3) -> pd.DataFrame:
        start_time = time.time()
        all_article_links_list = []
        
        try:
            logger.debug("開始抓取文章列表")
            logger.debug("參數設置: max_pages=%s, ai_only=%s", max_pages, ai_only)
            categories_log = self.site_config.categories if self.site_config.categories else '預設類別'
            logger.debug("使用類別: %s", categories_log)
                
            session = requests.Session()

            for current_category_name in self.site_config.categories:
                
                logger.debug("開始處理類別: %s", current_category_name)
                current_category_url = self.site_config.get_category_url(current_category_name)
                page = 1
                logger.debug("構造類別URL: %s, 頁數: %s", current_category_url, page)
                
                base_category_url = current_category_url
                logger.debug("保存原始類別URL: %s", base_category_url)

                while page <= max_pages:
                    logger.debug("正在處理第 %s/%s 頁", page, max_pages)
                    logger.debug("當前URL: %s", current_category_url)
                    
                    try:
                        logger.debug("開始執行隨機延遲")
                        delay_time = random.uniform(1.5, 3.5)
                        logger.debug("設定延遲時間: %s 秒", delay_time)
                        time.sleep(delay_time)
                        logger.debug("延遲完成")
                        
                        logger.debug("準備使用session.get()")
                        response = session.get(str(current_category_url), headers=self.site_config.headers, timeout=15)
                        logger.debug("使用session.get()完成")
                    except Exception as e:
                        logger.error("增加隨機延遲時發生錯誤: %s", str(e), exc_info=True)
                        continue

                    if response.status_code != 200:
                        logger.warning("頁面請求失敗: %s", response.status_code)
                        break
                    
                    try:
                        soup = BnextUtils.get_soup_from_html(response.text)
                        logger.debug("構建 soup 完成")

                        logger.debug("BnextScraper(scrape_article_list()) - call self.extract_article_links() 爬取文章連結")
                        current_page_article_links_list = self.extract_article_links(soup, ai_only=ai_only, min_keywords=min_keywords)
                        
                        all_article_links_list.extend(current_page_article_links_list)
                        logger.debug("共爬取 %s 篇文章連結", len(all_article_links_list))
                                        
                        next_page = soup.select_one('.pagination .next, .pagination a[rel="next"]')
                        if next_page and 'href' in next_page.attrs:
                            next_url = next_page['href']
                            current_category_url = BnextUtils.normalize_url(next_url, self.site_config.base_url)
                            page += 1
                        else:
                            current_category_url = self._build_next_page_url(base_category_url, page + 1)
                            page += 1
                            
                            if not self._is_valid_next_page(session, current_category_url):
                                break
                    
                        logger.debug("本頁共找到: %s 篇文章連結", len(current_page_article_links_list))
                    
                    except Exception as e:
                        logger.error("處理頁面內容時發生錯誤: %s", str(e), exc_info=True)
                        break
                
                logger.debug("完成爬取類別: %s", current_category_url)
            
            if all_article_links_list:
                return BnextUtils.process_articles_to_dataframe(all_article_links_list)
            else:
                logger.warning("未爬取到任何文章")
                return pd.DataFrame()
        
        except Exception as e:
            logger.error("爬蟲過程中發生未預期的錯誤: %s", str(e), exc_info=True)
            return pd.DataFrame()
        
        finally:
            end_time = time.time()
            duration = end_time - start_time
            logger.debug("爬蟲任務完成，總耗時: %.2f 秒", duration)
            if self.site_config.categories:
                logger.debug("共處理 %s 個類別，爬取 %s 篇文章", len(self.site_config.categories), len(all_article_links_list))
            else:
                logger.debug("共爬取 %s 篇文章", len(all_article_links_list))

    def _build_next_page_url(self, base_url: str, page_num: int) -> str:
        """構建下一頁URL"""
        if '?' in base_url:
            if 'page=' in base_url:
                return re.sub(r'page=\d+', f'page={page_num}', base_url)
            else:
                return f"{base_url}&page={page_num}"
        else:
            return f"{base_url}?page={page_num}"
            
    def _is_valid_next_page(self, session, url: str) -> bool:
        """檢查下一頁URL是否有效"""
        try:
            test_response = session.get(url, headers=DEFAULT_HEADERS, timeout=10)
            if test_response.status_code != 200:
                logger.warning("無法訪問下一頁: %s", url)
                return False
                
            test_soup = BnextUtils.get_soup_from_html(test_response.text)
            if len(test_soup.select('.grid.grid-cols-6.gap-4.relative.h-full')) == 0 and \
            len(test_soup.select('.grid.grid-cols-4.gap-8.xl\\:gap-6 > div')) == 0:
                logger.warning("下一頁沒有文章內容，停止爬取")
                return False
            return True
        except Exception as e:
            logger.error("訪問下一頁時出錯: %s", str(e), exc_info=True)
            return False

    def extract_article_links(self, soup, ai_only: bool = True, min_keywords: int = 3):
        """
        提取文章連結，增加容錯和詳細日誌
        
        Parameters:
        soup: BeautifulSoup對象，包含要爬取的頁面內容
        ai_only: 是否只返回AI相關文章，默認為True
        min_keywords: 判斷文章是否與AI相關所需的最小關鍵詞數量，默認為3
        
        Returns:
        List[Dict]: 文章連結列表
        """
        
        article_links_list = []

        try:
            selectors = self.site_config.selectors
            get_article_links_selectors = selectors.get('get_article_links') 
            get_grid_contentainer_selector = get_article_links_selectors.get("article_grid_container")

            articles_container = soup.select(get_article_links_selectors.get("articles_container"))
            
            logger.debug("找到 %s 個文章連結容器", len(articles_container))

            category = articles_container[0].select_one(get_article_links_selectors.get("category"))
            category_text = category.get_text(strip=True) if category else None
            link = articles_container[0].select_one(get_article_links_selectors.get("link"))
            link_text = link.get_attribute_list('href')[0] if link else None
            title = articles_container[0].select_one(get_article_links_selectors.get("title"))
            title_text = title.get_text(strip=True) if title else None
            summary = articles_container[0].select_one(get_article_links_selectors.get("summary"))
            summary_text = summary.get_text(strip=True) if summary else None
            
            article_link_dict = BnextUtils.get_article_columns_dict(
                title=title_text,
                summary=summary_text,
                content='',
                link=link_text,
                category=category_text,
                published_at=None,
                author='',
                source=self.site_config.name,
                source_url=self.site_config.base_url,
                article_type='',
                tags='',
                is_ai_related=ai_only,
                is_scraped=False,
                scrape_status=ArticleScrapeStatus.LINK_SAVED.value,
                scrape_error=None,
                last_scrape_attempt=datetime.now(timezone.utc),
                task_id=None
            )

            if ai_only:
                is_ai_related = ArticleAnalyzer().is_ai_related(article_link_dict, min_keywords=min_keywords)
                logger.debug("AI相關性檢查: %s", '通過' if is_ai_related else '未通過')
                if not is_ai_related:
                    article_link_dict = None

            if article_link_dict:
                article_links_list.append(article_link_dict)
                logger.debug("成功提取文章連結，標題: %s", title_text)
            
            logger.debug("開始提取網格文章連結")


            article_grid_container = articles_container[0].select_one(get_grid_contentainer_selector.get("container"))
            if not article_grid_container:
                logger.warning("未找到文章網格容器")
                return article_links_list

            for idx, container in enumerate(article_grid_container.find_all('div', recursive=False),1): 
                logger.debug("開始處理第 %s 個網格文章連結容器", idx)
                logger.debug("檢查網格文章連結容器類型: %s", type(container))
                try:
                    g_article_link_text = None
                    g_article_title_text = None
                    g_article_summary_text = None
                    
                    g_article_link = container.select_one(get_grid_contentainer_selector.get("link"))
                    if g_article_link:
                        g_article_link_text = g_article_link.get('href')
                        logger.debug("第%s篇網格文章連結: %s", idx, g_article_link_text)
            
                    g_article_title = container.select_one(get_grid_contentainer_selector.get("title"))
                    if g_article_title:
                        g_article_title_text = g_article_title.get_text(strip=True)
                        logger.debug("第%s篇網格文章標題: %s", idx, g_article_title_text)
                    g_article_summary = container.select_one(get_grid_contentainer_selector.get("summary"))
                    if g_article_summary:
                        g_article_summary_text = g_article_summary.get_text(strip=True)
                        logger.debug("第%s篇網格文章摘要: %s", idx, g_article_summary_text)

                    if g_article_link_text and g_article_title_text:
                        article_link_dict=BnextUtils.get_article_columns_dict(
                            title=g_article_title_text,
                            summary=g_article_summary_text if g_article_summary_text else "",
                            content='',
                            link=g_article_link_text,
                            category=category_text,
                            published_at=None,
                            author='',
                            source=self.site_config.name,
                            source_url=self.site_config.base_url,
                            article_type='',
                            tags='',
                            is_ai_related=ai_only,
                            is_scraped=False,
                            scrape_status=ArticleScrapeStatus.LINK_SAVED.value,
                            scrape_error=None,
                            last_scrape_attempt=datetime.now(timezone.utc),
                            task_id=None
                        )

                        if ai_only:
                            is_ai_related = ArticleAnalyzer().is_ai_related(article_link_dict, min_keywords=min_keywords)
                            logger.debug("AI相關性檢查: %s", '通過' if is_ai_related else '未通過')
                            if not is_ai_related:
                                article_link_dict = None

                        if article_link_dict:
                            article_links_list.append(article_link_dict)
                            logger.debug("成功添加網格文章連結到列表: %s", g_article_title_text)
                    
                except Exception as e:
                    logger.error("處理第%s個網格容器時發生錯誤: %s", idx, e, exc_info=True)
           
        except Exception as e:
            logger.error("提取文章連結時發生錯誤: %s", str(e), exc_info=True)
            logger.error("提取文章連結失敗")
            return article_links_list
        
        logger.debug("成功提取 %s 篇焦點文章", len(article_links_list))
        return article_links_list