# scraper.py
# 用於爬取網站文章列表的模組

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import re
from urllib.parse import urljoin

from src.crawler.base_config import DEFAULT_HEADERS
from src.crawler.bnext_config import BNEXT_CONFIG, BNEXT_DEFAULT_CATEGORIES
from src.crawler.article_analyzer import ArticleAnalyzer
from src.crawler.bnext_utils import BnextUtils

class BnextScraper:
    def __init__(self, db_manager=None):
        """
        初始化爬蟲
        
        Parameters:
        db_manager (DatabaseManager, optional): 資料庫管理器，用於存儲文章
        """
        self.db_manager = db_manager
        if db_manager:
            from src.model.article_service import ArticleService
            self.article_service = ArticleService(db_manager)
        else:
            self.article_service = None

    def scrape_article_list(self, max_pages=3, categories=None, ai_only=True) -> pd.DataFrame:
        """
        爬取 bnext.com.tw 的文章
    
        Parameters:
        max_pages (int): 爬取的最大頁數
        categories (list): 要爬取的特定類別URL列表，如果為None則使用預設類別
        ai_only (bool): 是否僅返回AI相關文章
        
        Returns:
        pandas.DataFrame: 包含文章標題、連結、分類等信息的 DataFrame
        """
        # 如果沒有指定類別，則使用預設類別
        if not categories:
            categories = []
            url_temp_str = BNEXT_CONFIG.list_url_template
            for category in BNEXT_DEFAULT_CATEGORIES:
                category_url = url_temp_str.format(base_url=BNEXT_CONFIG.base_url, category=category)
                categories.append(category_url)
        
        session = requests.Session()
        all_articles = []
        
        for category_url in categories:
            current_url = category_url
            page = 1
            
            # 保存原始類別URL，用於構造分頁URL
            base_category_url = category_url

            while page <= max_pages:
                try:
                    print(f"正在爬取: {current_url} (第 {page} 頁)")
                    
                    # 增加隨機延遲，避免被封鎖
                    time.sleep(random.uniform(1.5, 3.5))
                    
                    response = session.get(str(current_url), headers=DEFAULT_HEADERS, timeout=15)
                    
                    if response.status_code != 200:
                        print(f"頁面請求失敗: {response.status_code}")
                        break
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
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
                        if isinstance(next_url, str) and not next_url.startswith('http'):
                            next_url = urljoin(BNEXT_CONFIG.base_url, next_url)
                        current_url = next_url
                        page += 1
                    else:
                        # 如果沒有明確的下一頁按鈕，嘗試直接構造下一頁URL
                        if '?' in base_category_url:
                            if 'page=' in base_category_url:
                                current_url = re.sub(r'page=\d+', f'page={page+1}', base_category_url)
                            else:
                                current_url = f"{base_category_url}&page={page+1}"
                        else:
                            current_url = f"{base_category_url}?page={page+1}"
                        
                        page += 1
                        
                        # 檢查構造的URL是否有效
                        try:
                            test_response = session.get(current_url, headers=DEFAULT_HEADERS, timeout=10)
                            # 檢查是否成功獲取下一頁及其內容
                            if test_response.status_code != 200:
                                print(f"無法訪問下一頁: {current_url}")
                                break
                                
                            test_soup = BeautifulSoup(test_response.text, 'html.parser')
                            # 檢查頁面是否有內容
                            if len(test_soup.select('.grid.grid-cols-6.gap-4.relative.h-full')) == 0 and \
                            len(test_soup.select('.grid.grid-cols-4.gap-8.xl\\:gap-6 > div')) == 0:
                                print("下一頁沒有文章內容，停止爬取")
                                break
                        except Exception as e:
                            print(f"訪問下一頁時出錯: {e}")
                            break
                except Exception as e:
                    print(f"爬取過程中發生錯誤: {e}")
                    break
            
            print(f"完成爬取類別: {category_url}")
        
        # 在獲取DataFrame後，存儲到資料庫
        if all_articles and self.article_service:
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
                
                # 存儲到資料庫
                result = self.article_service.insert_article(db_article)
                if result:
                    success_count += 1
                else:
                    fail_count += 1
            
            print(f"文章存儲結果: 成功 {success_count} 篇，失敗 {fail_count} 篇")
            
            # 顯示爬取結果
            print(f"\n總共爬取到 {len(df)} 篇文章")
            
            # 保存爬取結果
            output_file = 'bnext_ai_articles.csv' if ai_only else 'bnext_tech_articles.csv'
            df.to_csv(output_file, index=False, encoding='utf-8-sig')
            print(f"已將爬取結果保存至 {output_file}")
            
            return df
        else:
            print("未爬取到任何文章")
            return pd.DataFrame()

    def extract_focus_articles(self, soup):
        """
        提取焦點文章，使用選擇器格式
        """
        articles = []
        selectors = BNEXT_CONFIG.selectors
        
        # 使用容器選擇器
        container_selector = BnextUtils.build_selector(selectors['focus_articles'][0])
        focus_article_containers = soup.select(container_selector)
        
        for container in focus_article_containers:
            # 提取標題
            title_elem = BnextUtils.find_element(container, selectors['focus_articles'][1:2], 'title')
            if not title_elem:
                continue
            
            title = title_elem.get_text(strip=True)
            
            # 提取摘要
            summary_elem = BnextUtils.find_element(container, selectors['focus_articles'][2:3], 'summary')
            summary = summary_elem.get_text(strip=True) if summary_elem else ""
            
            # 尋找連結
            link = BnextUtils.extract_article_link(container, title_elem)
            if not link:
                continue
            
            # 提取分類
            category_elem = BnextUtils.find_element(container, selectors['focus_articles'][3:4], 'category')
            category = category_elem.get_text(strip=True) if category_elem else None
            
            # 提取發布時間
            time_elem = BnextUtils.find_element(container, selectors['focus_articles'][4:], 'time')
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
        
        return articles

    def extract_regular_articles(self, soup):
        """
        提取一般文章，使用選擇器格式
        """
        articles = []
        selectors = BNEXT_CONFIG.selectors
        
        # 使用容器選擇器
        container_selector = BnextUtils.build_selector(selectors['regular_articles'][0])
        article_containers = soup.select(container_selector)
        
        for container in article_containers:
            # 提取標題
            title_elem = BnextUtils.find_element(container, selectors['regular_articles'][1:2], 'title')
            if not title_elem:
                continue
            
            title = title_elem.get_text(strip=True)
            
            # 提取摘要
            summary_elem = BnextUtils.find_element(container, selectors['regular_articles'][2:3], 'summary')
            summary = summary_elem.get_text(strip=True) if summary_elem else ""
            
            # 尋找連結
            link = BnextUtils.extract_article_link(container, title_elem)
            if not link:
                continue
            
            # 提取分類
            category_elem = BnextUtils.find_element(container, selectors['regular_articles'][3:4], 'category')
            category = category_elem.get_text(strip=True) if category_elem else None
            
            # 提取發布時間
            time_elem = BnextUtils.find_element(container, selectors['regular_articles'][4:], 'time')
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
        
        return articles

    def extract_backup_articles(self, soup, current_url):
        """
        備用方法，使用選擇器格式
        """
        articles = []
        found_links = set()
        selectors = BNEXT_CONFIG.selectors
        
        # 使用備用選擇器
        for container_selector in selectors['backup_articles']:
            css_selector = BnextUtils.build_selector(container_selector)
            article_cards = soup.select(css_selector)
            
            if not article_cards:
                continue
                
            for card in article_cards:
                # 提取連結
                link = BnextUtils.extract_article_link(card)
                if not link or link in found_links:
                    continue
                    
                found_links.add(link)
                
                # 提取標題
                title_elem = BnextUtils.find_element(card, selectors['backup_articles'][1:2], 'title')
                title = title_elem.get_text(strip=True) if title_elem else card.get_text(strip=True)
                
                # 提取摘要
                summary_elem = BnextUtils.find_element(card, selectors['backup_articles'][2:3], 'summary')
                summary = summary_elem.get_text(strip=True) if summary_elem else ""
                
                # 提取分類
                category_elem = BnextUtils.find_element(card, selectors['backup_articles'][3:4], 'category')
                category = category_elem.get_text(strip=True) if category_elem else None
                
                # 如果沒有找到分類，從URL推斷
                if not category:
                    category_match = re.search(r'/categories/([^/]+)', current_url)
                    if category_match:
                        category = category_match.group(1)
                
                # 提取發布時間
                time_elem = BnextUtils.find_element(card, selectors['backup_articles'][4:], 'time')
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
                
        return articles