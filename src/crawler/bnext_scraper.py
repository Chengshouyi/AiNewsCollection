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

class BnextScraper:
    def __init__(self):
        pass

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
        
        # 將爬取的文章資訊轉換為DataFrame
        if all_articles:
            df = pd.DataFrame(all_articles)

            # 刪除重複項
            df = df.drop_duplicates(subset=['link'], keep='first')
            
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
        提取焦點文章，使用指定的選擇器
        """
        articles = []
        
        # 使用提供的焦點文章選擇器
        focus_article_containers = soup.select('.grid.grid-cols-6.gap-4.relative.h-full')
        
        for container in focus_article_containers:
            # 提取標題
            title_elem = container.select_one('div.col-span-3.flex.flex-col.flex-grow.gap-y-3.m-4 > h2')
            if not title_elem:
                continue
            
            title = title_elem.get_text(strip=True)
            
            # 提取摘要
            summary_elem = container.select_one('div.col-span-3.flex.flex-col.flex-grow.gap-y-3.m-4 > div.flex-grow.pt-4.text-lg.text-gray-500')
            summary = summary_elem.get_text(strip=True) if summary_elem else ""
            
            # 尋找連結
            link_elem = None
            
            # 嘗試從標題元素找連結
            if title_elem:
                parent_a = title_elem.find_parent('a')
                if parent_a and 'href' in parent_a.attrs:
                    link_elem = parent_a
            
            # 如果找不到，嘗試從容器中找連結
            if not link_elem:
                link_elem = container.find('a', href=lambda href: href and '/article/' in href)
            
            # 如果還是找不到，嘗試找任何可能的文章連結
            if not link_elem:
                all_links = container.find_all('a', href=True)
                for a in all_links:
                    if '/article/' in a['href']:
                        link_elem = a
                        break
            
            # 如果還是找不到連結，則跳過這篇文章
            if not link_elem:
                continue
                
            link = link_elem.get('href', '')
            
            # 確保連結是完整的
            if link and not link.startswith('http'):
                link = urljoin(BNEXT_CONFIG.base_url, link)
            
            # 提取分類 - 使用提供的選擇器
            category_elem = container.select_one('div.col-span-3.flex.flex-col.flex-grow.gap-y-3.m-4 > div.flex.relative.items-center.gap-2.text-gray-500.text-sm > a')
            category = category_elem.get_text(strip=True) if category_elem else None
            
            # 提取日期
            date_elem = container.select_one('time, .date, .time')
            publish_date = date_elem.get_text(strip=True) if date_elem else None
            
            # 提取作者
            author_elem = container.select_one('.author, .writer')
            author = author_elem.get_text(strip=True) if author_elem else None
            
            # 提取閱讀數
            read_count_elem = container.select_one('.read-count, .view-count')
            read_count = read_count_elem.get_text(strip=True) if read_count_elem else None
            
            # 添加到文章列表
            article_info = {
                'title': title,
                'summary': summary,
                'link': link,
                'category': category,
                'publish_date': publish_date,
                'author': author,
                'read_count': read_count,
                'article_type': 'focus'
            }
            
            articles.append(article_info)
        
        return articles


    def extract_regular_articles(self, soup):
        """
        提取一般文章，使用指定的選擇器
        """
        articles = []
        
        # 使用提供的一般文章選擇器
        article_containers = soup.select('.grid.grid-cols-4.gap-8.xl\\:gap-6 > div')
        
        for container in article_containers:
            # 提取標題
            title_elem = container.select_one('div > h2')
            if not title_elem:
                continue
                
            title = title_elem.get_text(strip=True)
            
            # 提取摘要
            summary_elem = container.select_one('div > div.text-sm.text-justify.font-normal.text-gray-500.three-line-text.tracking-wide')
            summary = summary_elem.get_text(strip=True) if summary_elem else ""
            
            # 尋找連結
            link_elem = None
            
            # 嘗試從標題元素找連結
            if title_elem:
                parent_a = title_elem.find_parent('a')
                if parent_a and 'href' in parent_a.attrs:
                    link_elem = parent_a
            
            # 如果找不到，嘗試從容器中找連結
            if not link_elem:
                link_elem = container.find('a', href=lambda href: href and '/article/' in href)
            
            # 如果還是找不到，嘗試找任何可能的文章連結
            if not link_elem:
                all_links = container.find_all('a', href=True)
                for a in all_links:
                    if '/article/' in a['href']:
                        link_elem = a
                        break
            
            # 如果還是找不到連結，則跳過這篇文章
            if not link_elem:
                continue
                
            link = link_elem.get('href', '')
            
            # 確保連結是完整的
            if link and not link.startswith('http'):
                link = urljoin(BNEXT_CONFIG.base_url, link)
            
            # 提取分類 - 尋找類似的選擇器模式
            category_elem = container.select_one('div.flex.relative.items-center.gap-2.text-gray-500.text-sm > a')
            if not category_elem:
                # 嘗試其他可能的類別選擇器
                category_elem = container.select_one('.category, .tag, a[href*="/categories/"]')
            
            category = category_elem.get_text(strip=True) if category_elem else None
            
            # 提取日期
            date_elem = container.select_one('time, .date, .time')
            publish_date = date_elem.get_text(strip=True) if date_elem else None
            
            # 提取作者
            author_elem = container.select_one('.author, .writer')
            author = author_elem.get_text(strip=True) if author_elem else None
            
            # 提取閱讀數
            read_count_elem = container.select_one('.read-count, .view-count')
            read_count = read_count_elem.get_text(strip=True) if read_count_elem else None
            
            # 添加到文章列表
            article_info = {
                'title': title,
                'summary': summary,
                'link': link,
                'category': category,
                'publish_date': publish_date,
                'author': author,
                'read_count': read_count,
                'article_type': 'regular'
            }
            
            articles.append(article_info)
        
        return articles

    
    def extract_backup_articles(self, soup, current_url):
        """
        備用方法，當特定選擇器失效時使用
        """
        articles = []
        found_links = set()
        
        # 嘗試使用更通用的選擇器
        article_cards = soup.select('.article-card, .article-item, .article-list-item')
        
        # 如果找不到特定卡片，就查找所有可能的文章連結
        if not article_cards:
            article_cards = soup.select('a[href*="/article/"]')
        
        # 處理文章卡片元素
        for card in article_cards:
            # 如果卡片本身是連結
            if card.name == 'a':
                link = card.get('href', '')
                title_elem = card.select_one('.title, h2, h3, .article-title')
                title = title_elem.get_text(strip=True) if title_elem else card.get_text(strip=True)
                
                # 尋找摘要
                summary_elem = None
                if title_elem:
                    # 嘗試查找與標題相鄰的摘要元素
                    parent = title_elem.parent
                    if parent:
                        summary_elem = parent.select_one('div.text-gray-500, .summary, .excerpt, .description')
                
                summary = summary_elem.get_text(strip=True) if summary_elem else ""
                
            else:
                # 如果卡片包含連結
                link_elem = card.select_one('a[href*="/article/"]')
                if not link_elem:
                    continue
                
                link = link_elem.get('href', '')
                title_elem = card.select_one('.title, h2, h3, .article-title')
                title = title_elem.get_text(strip=True) if title_elem else link_elem.get_text(strip=True)
                
                # 尋找摘要
                summary_elem = card.select_one('div.text-gray-500, .summary, .excerpt, .description')
                summary = summary_elem.get_text(strip=True) if summary_elem else ""
            
            # 確保連結是完整的
            if link and not link.startswith('http'):
                link = urljoin(BNEXT_CONFIG.base_url, link)
            
            if not link or link in found_links:
                continue
            
            found_links.add(link)
            
            # 提取文章分類
            category_elem = card.select_one('.category, .tag')
            category = category_elem.get_text(strip=True) if category_elem else None
            
            # 如果沒有在卡片上找到分類，則使用當前頁面URL推斷分類
            if not category:
                category_match = re.search(r'/categories/([^/]+)', current_url)
                if category_match:
                    category = category_match.group(1)
            
            # 提取發布日期
            date_elem = card.select_one('time, .date, .time')
            publish_date = date_elem.get_text(strip=True) if date_elem else None
            
            # 提取作者
            author_elem = card.select_one('.author, .writer')
            author = author_elem.get_text(strip=True) if author_elem else None
            
            # 提取閱讀數或點讀數
            read_count_elem = card.select_one('.read-count, .view-count')
            read_count = read_count_elem.get_text(strip=True) if read_count_elem else None
            
            article_info = {
                'title': title,
                'summary': summary,
                'link': link,
                'category': category,
                'publish_date': publish_date,
                'author': author,
                'read_count': read_count,
                'article_type': 'backup',
                'source_page': current_url
            }
            
            articles.append(article_info)
        
        return articles