import requests
import pandas as pd
import logging
from typing import List, Dict
import time
import re
import random
from src.crawlers.configs.base_config import DEFAULT_HEADERS
from src.crawlers.article_analyzer import ArticleAnalyzer
from src.crawlers.bnext_utils import BnextUtils
from src.utils.log_utils import LoggerSetup

# 設置日誌記錄器
custom_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logger = LoggerSetup.setup_logger(
    module_name='bnext_scraper',
    log_dir='logs',  # 這會在專案根目錄下創建 logs 目錄
    log_format=custom_format,
    level=logging.DEBUG,
    date_format='%Y-%m-%d %H:%M:%S' # 設置日期格式  
)

class BnextScraper:
    def __init__(self, config=None):
        """
        初始化爬蟲
        
        Parameters:
        config (SiteConfig, optional): 網站配置
        """
        # 檢查配置
        logger.debug("檢查爬蟲配置")
        if config is None:
            logger.error("未提供網站配置，請提供有效的配置")
            raise ValueError("未提供網站配置，請提供有效的配置")
        else:
            # 確保配置有必要的屬性
            if not hasattr(config, 'base_url'):
                logger.error("未提供網站基礎URL，將使用預設值")
                config.base_url = "https://www.bnext.com.tw"

            if not hasattr(config, 'categories'):
                logger.error("未提供預設類別，將使用預設值")
                config.categories = ["ai","tech","iot","smartmedical","smartcity","cloudcomputing","security"]

            if not hasattr(config, 'selectors'):
                logger.error("未提供選擇器，將使用預設值")
                config.selectors = {}

            if not hasattr(config, 'get_category_url'):
                logger.error("未提供類別URL，將使用預設值")
                config.get_category_url = lambda x: f"{config.base_url}/categories/{x}"
            
            self.site_config = config
            #logger.debug(f"使用選擇器: {self.site_config.selectors}")

    def scrape_article_list(self, max_pages=3, ai_only=True) -> pd.DataFrame:
        start_time = time.time()
        all_article_links_list = []
        
        try:
            logger.debug("BnextScraper(scrape_article_list()) - call 開始抓取文章列表")
            logger.debug(f"參數設置: max_pages={max_pages}, ai_only={ai_only}")
            logger.debug(f"使用類別: {self.site_config.categories if self.site_config.categories else '預設類別'}")
                
            # 初始化requests session(網路連線)
            session = requests.Session()

            for current_category_name in self.site_config.categories:
                logger.debug(f"開始處理類別: {current_category_name}")
                # 構造類別URL
                current_category_url = self.site_config.get_category_url(current_category_name)
                page = 1
                logger.debug(f"構造類別URL: {current_category_url}, 頁數: {page}")
                
                # 保存原始類別URL，用於構造分頁URL
                base_category_url = current_category_url
                logger.debug(f"保存原始類別URL: {base_category_url}")

                while page <= max_pages:
                    logger.debug(f"正在處理第 {page}/{max_pages} 頁")
                    logger.debug(f"當前URL: {current_category_url}")
                    
                    try:
                        logger.debug(f"開始執行隨機延遲")
                        delay_time = random.uniform(1.5, 3.5)
                        logger.debug(f"設定延遲時間: {delay_time} 秒")
                        time.sleep(delay_time)
                        logger.debug(f"延遲完成")
                        
                        logger.debug(f"準備使用session.get()")
                        response = session.get(str(current_category_url), headers=self.site_config.headers, timeout=15)
                        logger.debug(f"使用session.get()完成")
                    except Exception as e:
                        logger.error(f"增加隨機延遲時發生錯誤: {str(e)}", exc_info=True)
                        continue  # 跳過當前迭代，繼續下一頁

                    # 檢查響應狀態
                    if response.status_code != 200:
                        logger.warning(f"頁面請求失敗: {response.status_code}")
                        break
                    
                    # 正常處理頁面內容
                    try:
                        soup = BnextUtils.get_soup_from_html(response.text)
                        logger.debug(f"構建 soup 完成")

                        # 根據提供的選擇器爬取內容
                        # 1. 爬取文章連結
                        logger.debug(f"BnextScraper(scrape_article_list()) - call self.extract_article_links() 爬取文章連結")
                        current_page_article_links_list = self.extract_article_links(soup)
                        
                        # 篩選是否為AI相關文章
                        # 先透過標題和分類快速篩選
                        if ai_only:
                            # 只對當前頁面新增的文章進行篩選
                            filtered_article_links_list = []
                            for article in current_page_article_links_list:
                                if ArticleAnalyzer().is_ai_related(article, check_content=False):
                                    filtered_article_links_list.append(article)
                            # 將之前累積的文章和當前頁面篩選後的文章合併
                            all_article_links_list.extend(filtered_article_links_list)
                            logger.debug(f"共爬取 {len(all_article_links_list)} 篇與AI相關文章連結")
                        else:
                            all_article_links_list.extend(current_page_article_links_list)
                            logger.debug(f"共爬取 {len(all_article_links_list)} 篇文章連結")
                        
                        # 檢查是否有下一頁
                        next_page = soup.select_one('.pagination .next, .pagination a[rel="next"]')
                        if next_page and 'href' in next_page.attrs:
                            next_url = next_page['href']
                            current_category_url = BnextUtils.normalize_url(next_url, self.site_config.base_url)
                            page += 1
                        else:
                            # 嘗試直接構造下一頁URL
                            current_category_url = self._build_next_page_url(base_category_url, page + 1)
                            page += 1
                            
                            # 檢查構造的URL是否有效
                            if not self._is_valid_next_page(session, current_category_url):
                                break
                    
                        # 記錄每個步驟的結果
                        logger.debug(f"本頁共找到: {len(current_page_article_links_list)} 篇文章連結")
                    
                    except Exception as e:
                        logger.error(f"處理頁面內容時發生錯誤: {str(e)}", exc_info=True)
                        break
                
                logger.debug(f"完成爬取類別: {current_category_url}")
            
            # 修改儲存邏輯
            if all_article_links_list:
                # 轉換為DataFrame
                return self._process_articles_to_dataframe(all_article_links_list)
            else:
                logger.warning("未爬取到任何文章")
                return pd.DataFrame()
        
        except Exception as e:
            logger.error(f"爬蟲過程中發生未預期的錯誤: {str(e)}", exc_info=True)
            return pd.DataFrame()  # 返回空的 DataFrame
        
        finally:
            end_time = time.time()
            duration = end_time - start_time
            logger.debug(f"爬蟲任務完成，總耗時: {duration:.2f} 秒")
            if self.site_config.categories:
                logger.debug(f"共處理 {len(self.site_config.categories)} 個類別，"
                           f"爬取 {len(all_article_links_list)} 篇文章")
            else:
                logger.debug(f"共爬取 {len(all_article_links_list)} 篇文章")

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
                logger.warning(f"無法訪問下一頁: {url}")
                return False
                
            test_soup = BnextUtils.get_soup_from_html(test_response.text)
            # 檢查頁面是否有內容
            if len(test_soup.select('.grid.grid-cols-6.gap-4.relative.h-full')) == 0 and \
            len(test_soup.select('.grid.grid-cols-4.gap-8.xl\\:gap-6 > div')) == 0:
                logger.warning("下一頁沒有文章內容，停止爬取")
                return False
            return True
        except Exception as e:
            logger.error(f"訪問下一頁時出錯: {str(e)}", exc_info=True)
            return False

    def _process_articles_to_dataframe(self, links_list: List[Dict]) -> pd.DataFrame:
        """處理文章列表並轉換為DataFrame"""
        if not links_list:
            logger.warning("未爬取到任何文章")
            return pd.DataFrame()
            
        df = pd.DataFrame(links_list)
        df = df.drop_duplicates(subset=['article_link'], keep='first')
        
        # 添加統計信息
        stats = {
            'total': len(df)
        }
        
        logger.debug("爬取統計信息:")
        logger.debug(f"總文章數: {stats['total']}")
        
        return df

    def extract_article_links(self, soup):
        """
        提取文章連結，增加容錯和詳細日誌
        """

        
        article_links_list = []

        try:
            selectors = self.site_config.selectors
            get_article_links_selectors = selectors.get('get_article_links') 
            get_grid_contentainer_selector = get_article_links_selectors.get("article_grid_container")

            # 提取文章連結
            articles_container = soup.select(get_article_links_selectors.get("articles_container"))
            
            logger.debug(f"找到 {len(articles_container)} 個文章連結容器")
            # logger.debug(f"文章連結容器: {articles_container}")

            category = articles_container[0].select_one(get_article_links_selectors.get("category"))
            category_text = category.get_text(strip=True) if category else None
            link = articles_container[0].select_one(get_article_links_selectors.get("link"))
            link_text = link.get_attribute_list('href')[0] if link else None
            title = articles_container[0].select_one(get_article_links_selectors.get("title"))
            title_text = title.get_text(strip=True) if title else None
            summary = articles_container[0].select_one(get_article_links_selectors.get("summary"))
            summary_text = summary.get_text(strip=True) if summary else None
            published_age = articles_container[0].select_one(get_article_links_selectors.get("published_age"))
            published_age_text = published_age.get_text(strip=True) if published_age else None
            
                    
            article_links_list.append({
                'source_name': self.site_config.name,
                'source_url': self.site_config.base_url,
                'title': title_text,
                'summary': summary_text,
                'article_link': link_text,
                'category': category_text,
                'published_age': published_age_text,
                'is_scraped': False
            })
            
            logger.debug(f"成功提取文章連結，標題: {title_text}")
            
            # 提取網格文章連結
            logger.debug(f"開始提取網格文章連結")


            article_grid_container = articles_container[0].select_one(get_grid_contentainer_selector.get("container"))
            if not article_grid_container:
                logger.warning("未找到文章網格容器")
                return article_links_list
            # logger.debug(f"Container type: {article_grid_container}")

            for idx, container in enumerate(article_grid_container.find_all('div', recursive=False),1): 
                logger.debug(f"開始處理第 {idx} 個網格文章連結容器")
                logger.debug(f"檢查網格文章連結容器類型: {type(container)}")
                try:
                    g_article_link = container.select_one(get_grid_contentainer_selector.get("link"))  # 修改選擇器，直接查找 a 標籤
                    if g_article_link:
                        g_article_link_text = g_article_link.get('href')
                        print(f"第{idx}篇網格文章連結: {g_article_link_text}")  # 列印文章連結
            
                    g_article_title = container.select_one(get_grid_contentainer_selector.get("title"))  # 修改選擇器，直接查找 h2 標籤
                    if g_article_title:
                        g_article_title_text = g_article_title.get_text(strip=True)
                        print(f"第{idx}篇網格文章標題: {g_article_title_text}")  # 列印文章標題
                    g_article_summary = container.select_one(get_grid_contentainer_selector.get("summary"))
                    if g_article_summary:
                        g_article_summary_text = g_article_summary.get_text(strip=True)
                        print(f"第{idx}篇網格文章摘要: {g_article_summary_text}")  # 列印文章摘要
                    g_articel_published_age = container.select_one(get_grid_contentainer_selector.get("published_age"))
                    if g_articel_published_age:
                        g_articel_published_age_text = g_articel_published_age.get_text(strip=True)
                        print(f"第{idx}篇網格文章發佈時間: {g_articel_published_age_text}")  # 列印文章發佈時間
                        # 添加網格文章連結到列表
                        article_links_list.append({
                            'source_name': self.site_config.name,
                            'source_url': self.site_config.base_url,
                            'title': g_article_title_text,
                            'summary': g_article_summary_text,
                            'article_link': g_article_link_text,
                            'category': category_text,
                            'published_age': g_articel_published_age_text,
                            'is_scraped': False
                        })
                        logger.debug(f"成功添加網格文章連結到列表: {g_article_title_text}")
                except Exception as e:
                    print(f"發生錯誤: {e}")
           
        except Exception as e:
            logger.error(f"提取文章連結時發生錯誤: {str(e)}", exc_info=True)
            logger.error(f"當前選擇器配置: {selectors}")
            return article_links_list
        
        logger.debug(f"成功提取 {len(article_links_list)} 篇焦點文章")
        return article_links_list