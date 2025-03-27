import requests
import pandas as pd
import logging
from typing import List, Dict
import time
import re

from src.crawlers.base_config import DEFAULT_HEADERS
from src.crawlers.bnext_config import BNEXT_CONFIG, BNEXT_DEFAULT_CATEGORIES
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
    def __init__(self, db_manager=None):
        """
        初始化爬蟲
        
        Parameters:
        db_manager (DatabaseManager, optional): 資料庫管理器，用於存儲文章
        """
        self.db_manager = db_manager
        self.article_repository = None
        
        # 檢查配置
        logger.info("檢查爬蟲配置")
        logger.info(f"使用配置: {BNEXT_CONFIG.__dict__}")
        
        if db_manager:
            self.article_repository = db_manager.get_repository('Article')
            logger.info("資料庫連接已建立")
        else:
            logger.warning("未提供資料庫管理器，將不會保存到資料庫")

    def scrape_article_list(self, max_pages=3, categories=None, ai_only=True) -> pd.DataFrame:
        start_time = time.time()
        logger.info("開始爬蟲任務")
        
        try:
            logger.info("開始爬取文章列表")
            logger.info(f"參數設置: max_pages={max_pages}, ai_only={ai_only}")
            logger.info(f"使用類別: {categories if categories else '預設類別'}")
            
            # 如果沒有指定類別，則使用預設類別
            if not categories:
                categories = []
                if BNEXT_CONFIG.default_categories:
                    categories.extend(BNEXT_CONFIG.default_categories)
                else:
                    logger.warning("未設置預設類別，將使用預設類別")
                    for category in BNEXT_DEFAULT_CATEGORIES:
                        category_url = BNEXT_CONFIG.get_category_url(category)
                        if category_url:
                            categories.append(category_url)
                
            session = requests.Session()
            all_articles = []
            
            for category_url in categories:
                logger.info(f"開始處理類別: {category_url}")
                current_url = category_url
                page = 1
                
                # 保存原始類別URL，用於構造分頁URL
                base_category_url = category_url

                while page <= max_pages:
                    logger.info(f"正在處理第 {page}/{max_pages} 頁")
                    logger.debug(f"當前URL: {current_url}")
                    
                    try:
                        logger.info(f"正在爬取: {current_url} (第 {page} 頁)")
                        
                        # 增加隨機延遲，避免被封鎖
                        BnextUtils.sleep_random_time(1.5, 3.5)
                        
                        response = session.get(str(current_url), headers=DEFAULT_HEADERS, timeout=15)
                        
                        if response.status_code != 200:
                            logger.warning(f"頁面請求失敗: {response.status_code}")
                            break
                        
                        soup = BnextUtils.get_soup_from_html(response.text)
                        
                        # 根據提供的選擇器爬取內容
                        # 1. 爬取焦點文章
                        focus_articles = self.extract_focus_articles(soup)
                        all_articles.extend(focus_articles)
                        
                        # 2. 爬取一般文章
                        regular_articles = self.extract_regular_articles(soup)
                        all_articles.extend(regular_articles)
                        
                        # 3. 如果上述兩種方法沒有找到任何文章或文章太少，則使用備用方法
                        backup_articles = []
                        if len(focus_articles) + len(regular_articles) < 5:  # 假設每頁至少應有5篇文章
                            backup_articles = self.extract_backup_articles(soup, current_url)
                            all_articles.extend(backup_articles)
                        
                            
                        # 篩選是否為AI相關文章
                        # 先透過標題和分類快速篩選
                        if ai_only:
                            # 只對當前頁面新增的文章進行篩選
                            current_page_articles = focus_articles + regular_articles + backup_articles
                            filtered_articles = []
                            for article in current_page_articles:
                                if ArticleAnalyzer().is_ai_related(article, check_content=False):
                                    filtered_articles.append(article)
                            # 將之前累積的文章和當前頁面篩選後的文章合併
                            all_articles = all_articles[:-len(current_page_articles)] + filtered_articles
                        
                        # 檢查是否有下一頁
                        next_page = soup.select_one('.pagination .next, .pagination a[rel="next"]')
                        if next_page and 'href' in next_page.attrs:
                            next_url = next_page['href']
                            current_url = BnextUtils.normalize_url(next_url, BNEXT_CONFIG.base_url)
                            page += 1
                        else:
                            # 嘗試直接構造下一頁URL
                            current_url = self._build_next_page_url(base_category_url, page + 1)
                            page += 1
                            
                            # 檢查構造的URL是否有效
                            if not self._is_valid_next_page(session, current_url):
                                break
                    
                        # 記錄每個步驟的結果
                        logger.info(f"本頁找到: 焦點文章 {len(focus_articles)} 篇, "
                                   f"一般文章 {len(regular_articles)} 篇, "
                                   f"備用文章 {len(backup_articles)} 篇")
                    
                    except Exception as e:
                        logger.error(f"爬取過程中發生錯誤: {str(e)}", exc_info=True)
                        break
                
                logger.info(f"完成爬取類別: {category_url}")
            
            # 修改儲存邏輯
            if all_articles and self.article_repository:
                df = pd.DataFrame(all_articles)
                df = df.drop_duplicates(subset=['link'], keep='first')
                
                # 轉換資料格式以符合資料庫結構
                success_count = 0
                fail_count = 0
                
                for _, article in df.iterrows():
                    # 轉換為資料庫模型格式
                    db_article = {
                        'title': article['title'],
                        'summary': article.get('summary', ''),
                        'link': article['link'],
                        'category': article.get('category', ''),
                        'published_at': article.get('publish_time', ''),
                        'source': 'bnext_list',
                        'article_type': article.get('article_type', 'regular')
                    }
                    
                    # 使用 repository 直接存儲
                    try:
                        self.article_repository.create(db_article)
                        success_count += 1
                    except Exception as e:
                        logger.error(f"儲存文章失敗: {str(e)}")
                        fail_count += 1
                
                logger.info(f"文章存儲結果: 成功 {success_count} 篇，失敗 {fail_count} 篇")
            
            # 轉換為DataFrame
            return self._process_articles_to_dataframe(all_articles)
        
        finally:
            end_time = time.time()
            duration = end_time - start_time
            logger.info(f"爬蟲任務完成，總耗時: {duration:.2f} 秒")
            if categories:
                logger.info(f"共處理 {len(categories)} 個類別，"
                           f"爬取 {len(all_articles)} 篇文章")
            else:
                logger.info(f"共爬取 {len(all_articles)} 篇文章")

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

    def _process_articles_to_dataframe(self, articles: List[Dict]) -> pd.DataFrame:
        """處理文章列表並轉換為DataFrame"""
        if not articles:
            logger.warning("未爬取到任何文章")
            return pd.DataFrame()
            
        df = pd.DataFrame(articles)
        df = df.drop_duplicates(subset=['link'], keep='first')
        
        # 添加統計信息
        stats = {
            'total': len(df),
            'focus': len(df[df['article_type'] == 'focus']),
            'regular': len(df[df['article_type'] == 'regular']),
            'backup': len(df[df['article_type'] == 'backup'])
        }
        
        logger.info("爬取統計信息:")
        logger.info(f"總文章數: {stats['total']}")
        logger.info(f"焦點文章: {stats['focus']}")
        logger.info(f"一般文章: {stats['regular']}")
        logger.info(f"備用文章: {stats['backup']}")
        
        return df

    def extract_focus_articles(self, soup):
        """
        提取焦點文章，增加容錯和詳細日誌
        """
        articles = []
        selectors = BNEXT_CONFIG.selectors if hasattr(BNEXT_CONFIG, 'selectors') else {}
        
        logger.info(f"焦點文章選擇器配置: {selectors}")
        
        # 預設備用選擇器 - 根據實際使用經驗設置更準確的選擇器
        default_selectors = {
            'container': 'div.grid.grid-cols-6.gap-4.relative.h-full',
            'title': 'div.col-span-3.flex.flex-col.flex-grow.gap-y-3.m-4 > h2',
            'summary': 'div.col-span-3.flex.flex-col.flex-grow.gap-y-3.m-4 > div.flex-grow.pt-4.text-lg.text-gray-500',
            'category': 'div.col-span-3.flex.flex-col.flex-grow.gap-y-3.m-4 > div.flex.relative.items-center.gap-2.text-gray-500.text-sm > a',
            'time': 'div.flex.relative.items-center.gap-2.text-gray-500.text-sm span:nth-child(1)'
        }
        
        try:
            # 嘗試使用配置中的選擇器，若無則使用預設選擇器
            container_selector = (
                selectors.get('focus_articles', [default_selectors['container']])[0] 
                if selectors.get('focus_articles') 
                else default_selectors['container']
            )
            
            logger.debug(f"使用容器選擇器: {container_selector}")
            
            # 選擇文章容器
            focus_article_containers = soup.select(container_selector)
            
            logger.info(f"找到 {len(focus_article_containers)} 個焦點文章容器")
            
            for idx, container in enumerate(focus_article_containers, 1):
                try:
                    # 使用預設或配置選擇器提取標題
                    title_selector = (
                        selectors.get('focus_articles', [None, default_selectors['title']])[1] 
                        if selectors.get('focus_articles') 
                        else default_selectors['title']
                    )
                    title_elem = container.select_one(title_selector)
                    
                    # 如果找不到標題，嘗試使用h2、h3標籤直接搜索
                    if not title_elem:
                        for selector in ['h2', 'h3', '.title', 'div.font-bold']: 
                            title_elem = container.select_one(selector)
                            if title_elem:
                                break
                    
                    if not title_elem:
                        logger.warning(f"第 {idx} 個容器未找到標題，使用標題選擇器: {title_selector}")
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    
                    # 提取摘要
                    summary_selector = (
                        selectors.get('focus_articles', [None, None, default_selectors['summary']])[2] 
                        if selectors.get('focus_articles') 
                        else default_selectors['summary']
                    )
                    summary_elem = container.select_one(summary_selector)
                    
                    # 如果找不到摘要，嘗試使用通用選擇器
                    if not summary_elem:
                        for selector in ['div.text-gray-500', '.summary', '.excerpt', 'div.text-sm']:
                            summary_elem = container.select_one(selector)
                            if summary_elem:
                                break
                    
                    summary = summary_elem.get_text(strip=True) if summary_elem else ""
                    
                    # 提取連結 - 改進鏈接提取邏輯
                    link = BnextUtils.extract_article_link(container, title_elem)
                    
                    # 如果找不到鏈接，嘗試從標題元素或其父元素中提取
                    if not link and title_elem:
                        # 嘗試標題的父級a標籤
                        parent_a = title_elem.find_parent('a')
                        if parent_a and 'href' in parent_a.attrs:
                            link = parent_a['href']
                        else:
                            # 嘗試找出所有帶有/article/路徑的連結
                            article_links = container.find_all('a', href=lambda x: x and '/article/' in x)
                            if article_links:
                                link = article_links[0]['href']
                    
                    # 確保連結是完整的
                    if link and not link.startswith('http'):
                        link = BnextUtils.normalize_url(link, BNEXT_CONFIG.base_url)
                    
                    # 如果還是找不到連結，則跳過這篇文章
                    if not link:
                        logger.warning(f"第 {idx} 個焦點文章未找到有效連結")
                        continue
                    
                    # 提取分類
                    category_selector = (
                        selectors.get('focus_articles', [None, None, None, default_selectors['category']])[3] 
                        if selectors.get('focus_articles') 
                        else default_selectors['category']
                    )
                    category_elem = container.select_one(category_selector)
                    
                    # 如果找不到分類，嘗試使用其他選擇器
                    if not category_elem:
                        for selector in ['.category', '.tag', 'a[href*="/categories/"]']:
                            category_elem = container.select_one(selector)
                            if category_elem:
                                break
                    
                    category = category_elem.get_text(strip=True) if category_elem else None
                    
                    # 如果從DOM中無法提取類別，嘗試從URL中提取
                    if not category and link:
                        category_match = re.search(r'/categories/([^/]+)', link)
                        if category_match:
                            category = category_match.group(1)
                    
                    # 提取發布時間
                    time_selector = (
                        selectors.get('focus_articles', [None, None, None, None, default_selectors['time']])[4] 
                        if selectors.get('focus_articles') 
                        else default_selectors['time']
                    )
                    time_elem = container.select_one(time_selector)
                    
                    # 如果找不到發布時間，嘗試使用其他選擇器
                    if not time_elem:
                        for selector in ['time', '.date', '.time', '.published-date']:
                            time_elem = container.select_one(selector)
                            if time_elem:
                                break
                    
                    publish_time = time_elem.get_text(strip=True) if time_elem else None
                    
                    article_info = {
                        'title': title,
                        'summary': summary,
                        'link': link,
                        'category': category,
                        'publish_time': publish_time,
                        'article_type': 'focus'
                    }
                    
                    articles.append(article_info)
                    logger.debug(f"成功提取焦點文章: {title}")
                
                except Exception as article_error:
                    logger.error(f"提取第 {idx} 個焦點文章時出錯: {str(article_error)}", exc_info=True)
        
        except Exception as e:
            logger.error("提取焦點文章時發生錯誤", exc_info=True)
            logger.error(f"錯誤詳情: {str(e)}")
            logger.error(f"當前選擇器配置: {selectors}")
            return []
        
        logger.info(f"成功提取 {len(articles)} 篇焦點文章")
        return articles

    def extract_regular_articles(self, soup):
        """
        提取一般文章，增加容錯和詳細日誌
        """
        articles = []
        selectors = BNEXT_CONFIG.selectors if hasattr(BNEXT_CONFIG, 'selectors') else {}
        
        logger.info(f"一般文章選擇器配置: {selectors}")
        
        # 預設備用選擇器 - 根據實際使用經驗設置更準確的選擇器
        default_selectors = {
            'container': 'div.grid.grid-cols-4.gap-8.xl\\:gap-6 > div',
            'title': 'div > h2',
            'summary': 'div > div.text-sm.text-justify.font-normal.text-gray-500.three-line-text.tracking-wide',
            'category': 'div.flex.relative.items-center.gap-2.text-gray-500.text-sm > a',
            'time': 'div.flex.relative.items-center.gap-2.text-gray-500.text-sm span:nth-child(1)'
        }
        
        try:
            # 嘗試使用配置中的選擇器，若無則使用預設選擇器
            container_selector = (
                selectors.get('regular_articles', [default_selectors['container']])[0] 
                if selectors.get('regular_articles') 
                else default_selectors['container']
            )
            
            logger.debug(f"使用容器選擇器: {container_selector}")
            
            # 選擇文章容器
            article_containers = soup.select(container_selector)
            
            logger.info(f"找到 {len(article_containers)} 個一般文章容器")
            
            # 如果找不到文章，嘗試使用備用選擇器
            if len(article_containers) == 0:
                backup_selectors = [
                    "div.grid.grid-cols-4",
                    "div.grid div[class*='grid-cols']",
                    "div.grid div.flex.flex-col"
                ]
                
                for backup_selector in backup_selectors:
                    article_containers = soup.select(backup_selector)
                    if len(article_containers) > 0:
                        logger.warning(f"使用備用選擇器: {backup_selector}，找到 {len(article_containers)} 個容器")
                        break
            
            for idx, container in enumerate(article_containers, 1):
                try:
                    # 使用預設或配置選擇器提取標題
                    title_selector = (
                        selectors.get('regular_articles', [None, default_selectors['title']])[1] 
                        if selectors.get('regular_articles') 
                        else default_selectors['title']
                    )
                    title_elem = container.select_one(title_selector)
                    
                    # 如果找不到標題，嘗試使用更通用的選擇器
                    if not title_elem:
                        for selector in ['h2', 'h3', '.title', '.article-title', 'div.font-bold', '.font-medium']:
                            title_elem = container.select_one(selector)
                            if title_elem:
                                break
                    
                    if not title_elem:
                        logger.warning(f"第 {idx} 個容器未找到標題，使用標題選擇器: {title_selector}")
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    
                    # 提取摘要
                    summary_selector = (
                        selectors.get('regular_articles', [None, None, default_selectors['summary']])[2] 
                        if selectors.get('regular_articles') 
                        else default_selectors['summary']
                    )
                    summary_elem = container.select_one(summary_selector)
                    
                    # 如果找不到摘要，嘗試使用通用選擇器
                    if not summary_elem:
                        for selector in ['div.text-gray-500', '.summary', '.excerpt', '.description', 'div.text-sm']:
                            summary_elem = container.select_one(selector)
                            if summary_elem:
                                break
                    
                    summary = summary_elem.get_text(strip=True) if summary_elem else ""
                    
                    # 提取連結 - 改進鏈接提取邏輯
                    link = BnextUtils.extract_article_link(container, title_elem)
                    
                    # 如果找不到鏈接，嘗試從標題元素或其父元素中提取
                    if not link and title_elem:
                        # 嘗試標題的父級a標籤
                        parent_a = title_elem.find_parent('a')
                        if parent_a and 'href' in parent_a.attrs:
                            link = parent_a['href']
                        else:
                            # 嘗試找出所有帶有/article/路徑的連結
                            article_links = container.find_all('a', href=lambda x: x and '/article/' in x)
                            if article_links:
                                link = article_links[0]['href']
                    
                    # 確保連結是完整的
                    if link and not link.startswith('http'):
                        link = BnextUtils.normalize_url(link, BNEXT_CONFIG.base_url)
                    
                    if not link:
                        logger.warning(f"第 {idx} 個一般文章未找到連結")
                        continue
                    
                    # 提取分類
                    category_selector = (
                        selectors.get('regular_articles', [None, None, None, default_selectors['category']])[3] 
                        if selectors.get('regular_articles') 
                        else default_selectors['category']
                    )
                    category_elem = container.select_one(category_selector)
                    
                    # 如果找不到分類，嘗試使用其他選擇器
                    if not category_elem:
                        for selector in ['.category', '.tag', 'a[href*="/categories/"]']:
                            category_elem = container.select_one(selector)
                            if category_elem:
                                break
                    
                    category = category_elem.get_text(strip=True) if category_elem else None
                    
                    # 如果從DOM中無法提取類別，嘗試從URL中提取
                    if not category and link:
                        category_match = re.search(r'/categories/([^/]+)', link)
                        if category_match:
                            category = category_match.group(1)
                    
                    # 提取發布時間
                    time_selector = (
                        selectors.get('regular_articles', [None, None, None, None, default_selectors['time']])[4] 
                        if selectors.get('regular_articles') 
                        else default_selectors['time']
                    )
                    time_elem = container.select_one(time_selector)
                    
                    # 如果找不到發布時間，嘗試使用其他選擇器
                    if not time_elem:
                        for selector in ['time', '.date', '.time', '.published-date']:
                            time_elem = container.select_one(selector)
                            if time_elem:
                                break
                    
                    publish_time = time_elem.get_text(strip=True) if time_elem else None
                    
                    article_info = {
                        'title': title,
                        'summary': summary,
                        'link': link,
                        'category': category,
                        'publish_time': publish_time,
                        'article_type': 'regular'
                    }
                    
                    articles.append(article_info)
                    logger.debug(f"成功提取一般文章: {title}")
                
                except Exception as article_error:
                    logger.error(f"提取第 {idx} 個一般文章時出錯: {str(article_error)}", exc_info=True)
        
        except Exception as e:
            logger.error("提取一般文章時發生錯誤", exc_info=True)
            logger.error(f"錯誤詳情: {str(e)}")
            logger.error(f"當前選擇器配置: {selectors}")
            return []
        
        logger.info(f"成功提取 {len(articles)} 篇一般文章")
        return articles

    def extract_backup_articles(self, soup, current_url):
        """
        備用文章提取方法，增加容錯和詳細日誌
        """
        articles = []
        found_links = set()
        selectors = BNEXT_CONFIG.selectors if hasattr(BNEXT_CONFIG, 'selectors') else {}
        
        logger.info(f"備用文章選擇器配置: {selectors}")
        
        # 預設備用選擇器 - 更完整的備用選擇器集合
        default_selectors = {
            'container': [
                'div.article-card', '.article-item', 'a.text-black', 'div.flex.flex-col',
                'a[href*="/articles/"]', 'a[href*="/article/"]'
            ],
            'title': ['h2', 'h3', '.article-title', '.font-bold', '.title'],
            'summary': ['.article-summary', '.text-gray-500', 'div.text-sm', '.excerpt', '.description'],
            'category': ['.article-category', 'a.category', '.text-xs', 'a[href*="/categories/"]', '.tag'],
            'time': ['.article-time', '.text-gray-500.text-sm', 'span', 'time', '.date', '.published-date']
        }
        
        try:
            # 嘗試多種可能的備用選擇器
            backup_selectors = selectors.get('backup_articles', [])
            
            # 使用預設選擇器和配置選擇器合併
            all_container_selectors = default_selectors['container']
            for selector_obj in backup_selectors:
                # 如果是簡單的字符串選擇器
                if isinstance(selector_obj, str):
                    all_container_selectors.append(selector_obj)
                # 如果是複雜選擇器對象
                elif isinstance(selector_obj, dict) and 'tag' in selector_obj:
                    # 構建css選擇器
                    tag = selector_obj.get('tag', '')
                    attrs = selector_obj.get('attrs', {})
                    if 'class' in attrs and isinstance(attrs['class'], list):
                        for class_name in attrs['class']:
                            all_container_selectors.append(f"{tag}.{class_name}")
                    elif 'href' in attrs:
                        all_container_selectors.append(f"{tag}[href*=\"{attrs['href']}\"]")
            
            # 記錄所有已找到的連結，避免重複
            for container_selector in all_container_selectors:
                logger.debug(f"嘗試備用選擇器: {container_selector}")
                
                article_cards = soup.select(container_selector)
                logger.info(f"使用選擇器 '{container_selector}' 找到 {len(article_cards)} 個可能的文章")
                
                for idx, card in enumerate(article_cards, 1):
                    try:
                        # 提取連結 - 更靈活的鏈接提取
                        link = None
                        
                        # 如果卡片本身是連結
                        if card.name == 'a' and 'href' in card.attrs:
                            link = card['href']
                        else:
                            # 尋找內部的文章連結
                            link_candidates = card.find_all('a', href=lambda href: href and ('/article/' in href or '/articles/' in href))
                            if link_candidates:
                                link = link_candidates[0]['href']
                        
                        # 確保連結是完整的
                        if link and not link.startswith('http'):
                            link = BnextUtils.normalize_url(link, BNEXT_CONFIG.base_url)
                            
                        if not link or link in found_links or 'javascript:' in link:
                            continue
                            
                        found_links.add(link)
                        
                        # 提取標題
                        title_elem = None
                        for title_selector in default_selectors['title']:
                            title_elem = card.select_one(title_selector)
                            if title_elem:
                                break
                        
                        title = title_elem.get_text(strip=True) if title_elem else card.get_text(strip=True)
                        
                        # 清理標題，移除過長的內容
                        if len(title) > 100:
                            title = title[:100] + "..."
                        
                        # 提取摘要
                        summary_elem = None
                        for summary_selector in default_selectors['summary']:
                            summary_elem = card.select_one(summary_selector)
                            if summary_elem:
                                break
                                
                        summary = summary_elem.get_text(strip=True) if summary_elem else ""
                        
                        # 提取分類
                        category_elem = None
                        for category_selector in default_selectors['category']:
                            category_elem = card.select_one(category_selector)
                            if category_elem:
                                break
                                
                        category = category_elem.get_text(strip=True) if category_elem else None
                        
                        # 如果沒有找到分類，從URL推斷
                        if not category:
                            category_match = re.search(r'/categories/([^/]+)', current_url)
                            if category_match:
                                category = category_match.group(1)
                            elif link:
                                category_match = re.search(r'/categories/([^/]+)', link)
                                if category_match:
                                    category = category_match.group(1)
                        
                        # 提取發布時間
                        time_elem = None
                        for time_selector in default_selectors['time']:
                            time_elem = card.select_one(time_selector)
                            if time_elem:
                                break
                                
                        publish_time = time_elem.get_text(strip=True) if time_elem else None
                        
                        article_info = {
                            'title': title,
                            'summary': summary,
                            'link': link,
                            'category': category,
                            'publish_time': publish_time,
                            'article_type': 'backup'
                        }
                        
                        articles.append(article_info)
                        logger.debug(f"成功提取備用文章: {title}")
                    
                    except Exception as article_error:
                        logger.error(f"提取第 {idx} 個備用文章時出錯: {str(article_error)}", exc_info=True)
        
        except Exception as e:
            logger.error(f"提取備用文章時出現嚴重錯誤: {str(e)}", exc_info=True)
        
        logger.info(f"成功提取 {len(articles)} 篇備用文章")
        return articles