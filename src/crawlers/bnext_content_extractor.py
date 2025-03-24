# content_extractor.py
# 用於爬取文章內容的模組

import requests
from bs4 import BeautifulSoup
import time
import random
from urllib.parse import urljoin
from typing import Dict, Optional
import pandas as pd
from src.crawlers.base_config import DEFAULT_HEADERS
from src.crawlers.bnext_config import BNEXT_CONFIG
from src.crawlers.article_analyzer import ArticleAnalyzer
from src.crawlers.bnext_utils import BnextUtils

class BnextContentExtractor:
    def __init__(self):
        pass

    def _build_selector(self, selector_dict):
        """
        根據選擇器格式構建CSS選擇器
        """
        selector = f"{selector_dict['tag']}"
        if 'attrs' in selector_dict:
            for attr, value in selector_dict['attrs'].items():
                if attr == 'class':
                    classes = value.split()
                    for cls in classes:
                        selector += f".{cls}"
                else:
                    selector += f"[{attr}='{value}']"
        
        if 'parent' in selector_dict:
            parent_selector = ""
            for attr, value in selector_dict['parent'].items():
                if attr == 'class':
                    classes = value.split()
                    for cls in classes:
                        parent_selector += f".{cls}"
                elif attr == 'id':
                    parent_selector += f"#{value}"
                else:
                    parent_selector += f"[{attr}='{value}']"
            selector = f"{parent_selector} > {selector}"
            
        if 'nth_child' in selector_dict:
            selector += f":nth-child({selector_dict['nth_child']})"
            
        return selector
        
    def _find_element(self, container, selectors, selector_type):
        """
        使用選擇器格式查找元素
        """
        if not isinstance(selectors, list):
            return None
            
        for selector in selectors:
            if isinstance(selector, dict):
                css_selector = self._build_selector(selector)
                element = container.select_one(css_selector)
                if element:
                    return element
        return None
        
    def _find_elements_by_purpose(self, soup, selectors, purpose):
        """
        根據purpose屬性查找元素
        """
        matching_selectors = [s for s in selectors if s.get('purpose') == purpose]
        if not matching_selectors:
            return None
            
        for selector in matching_selectors:
            css_selector = self._build_selector(selector)
            elements = soup.select(css_selector)
            if elements:
                return elements
                
        return None
        
    def _find_element_by_purpose(self, soup, selectors, purpose):
        """
        根據purpose屬性查找單個元素
        """
        elements = self._find_elements_by_purpose(soup, selectors, purpose)
        return elements[0] if elements else None

    def _get_article_content(self, article_url: str, ai_filter: bool = True, min_keywords: int = 3) -> Optional[Dict]:
        """
        獲取文章詳細內容
    
        Parameters:
        article_url (str): 文章URL
        ai_filter (bool): 是否過濾非AI相關文章
        min_keywords (int): 判斷為AI相關文章的最少關鍵字數量
        
        Returns:
        dict or None: 包含文章詳細內容的字典，如果不符合AI過濾條件則返回None
        """
        try:
            # 增加隨機延遲，避免被封鎖
            time.sleep(random.uniform(2.0, 4.0))
            
            response = requests.get(article_url, headers=DEFAULT_HEADERS, timeout=15)
            if response.status_code != 200:
                print(f"文章頁面請求失敗: {response.status_code}")
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            selectors = BNEXT_CONFIG.selectors['article_detail']
            
            # 找到文章頭部容器
            header_selector = next((s for s in selectors if s.get('purpose') == 'header'), selectors[0])
            header = soup.select_one(BnextUtils.build_selector(header_selector))
            
            if not header:
                print(f"無法找到文章頭部: {article_url}")
                return None
            
            # 提取標題
            title_elem = BnextUtils.find_element_by_purpose(header, selectors, 'title')
            title = title_elem.get_text(strip=True) if title_elem else None
            
            # 提取摘要
            summary_elem = BnextUtils.find_element_by_purpose(header, selectors, 'summary')
            summary = summary_elem.get_text(strip=True) if summary_elem else None
            
            # 提取類別
            category_elem = BnextUtils.find_element_by_purpose(header, selectors, 'category')
            category = category_elem.get_text(strip=True) if category_elem else None
            
            # 提取發布日期
            publish_at_elem = BnextUtils.find_element_by_purpose(header, selectors, 'publish_at')
            publish_at = publish_at_elem.get_text(strip=True) if publish_at_elem else None
            
            # 提取作者
            author_elem = BnextUtils.find_element_by_purpose(header, selectors, 'author')
            author = author_elem.get_text(strip=True) if author_elem else None
            
            # 提取標籤
            tags = []
            tags_container = BnextUtils.find_element_by_purpose(header, selectors, 'tags_container')
            if tags_container:
                tag_elems = tags_container.select('a')
                tags = [tag.get_text(strip=True) for tag in tag_elems if tag.get_text(strip=True)]
            
            # 提取文章內容
            content_elem = BnextUtils.find_element_by_purpose(soup, selectors, 'content')
            content_text = ""
            if content_elem:
                # 移除不需要的元素
                for unwanted in content_elem.select('script, style, .ad, .advertisement, .social-share'):
                    unwanted.extract()
                content_text = content_elem.get_text(separator='\n', strip=True)
            
            # 提取相關文章
            related_links = []
            related_link_elems = BnextUtils.find_elements_by_purpose(soup, selectors, 'related_links')
            if related_link_elems:
                for link in related_link_elems:
                    link_url = link.get('href', '')
                    link_title = link.get_text(strip=True)
                    
                    # 確保連結是完整的
                    if link_url and not link_url.startswith('http'):
                        link_url = urljoin(BNEXT_CONFIG.base_url, link_url)
                    
                    if link_url and link_title:
                        related_links.append({
                            'title': link_title,
                            'link': link_url
                        })
            
            # 創建文章內容字典
            article_content = {
                'title': title,
                'summary': summary,
                'category': category,
                'publish_at': publish_at,
                'author': author,
                'content': content_text,
                'content_length': len(content_text) if content_text else 0,
                'tags': tags,
                'related_articles': related_links,
                'source': article_url
            }
            
            # 檢查是否符合AI相關條件
            if ai_filter:
                if not ArticleAnalyzer().is_ai_related(article_content, min_keywords=min_keywords):
                    return None
            
            return article_content
        
        except Exception as e:
            print(f"獲取文章內容時發生錯誤 ({article_url}): {e}")
            return None

    def batch_get_articles_content(self, articles_df, num_articles=10, ai_only=True, min_keywords=3, db_manager=None):
        """
        批量獲取文章內容
        
        Parameters:
        articles_df (pandas.DataFrame): 包含文章基本信息的DataFrame
        num_articles (int): 要處理的文章數量
        ai_only (bool): 是否只處理AI相關文章
        min_keywords (int): 判斷為AI相關文章的最少關鍵字數量
        db_manager (DatabaseManager, optional): 資料庫管理器，用於存儲文章
        
        Returns:
        pandas.DataFrame: 包含文章詳細內容的DataFrame
        """
        
        # 爬取指定數量的文章內容
        print(f"\n正在爬取前 {num_articles} 篇文章的內容...")
        articles_contents = []
        successful_count = 0
        
        # 如果提供了資料庫管理器，創建文章服務
        article_service = None
        if db_manager:
            from src.services.article_service import ArticleService
            article_service = ArticleService(db_manager)
        
        for i, (_, article) in enumerate(articles_df.head(num_articles).iterrows(), 1):
            print(f"正在爬取 {i}/{num_articles}: {article['title']}")
            content_data = self._get_article_content(article['link'], ai_filter=ai_only, min_keywords=min_keywords)
            
            # 如果不是AI相關文章且啟用了AI過濾，則跳過
            if content_data is None:
                print(f"  跳過: 非AI相關文章或內容獲取失敗")
                continue
            
            # 合併文章基本資訊和內容
            content_data.update({
                'title': article.get('title', content_data.get('title')),
                'link': article['link'],
                'category': article.get('category', content_data.get('category')),
                'source_page': article.get('source_page', 'bnext_content')
            })
            
            # 如果有資料庫服務，存儲文章
            if article_service:
                # 轉換為資料庫模型格式
                db_article = {
                    'title': content_data['title'],
                    'summary': content_data.get('summary', ''),
                    'content': content_data.get('content', ''),
                    'link': content_data['link'],
                    'category': content_data.get('category', ''),
                    'published_at': content_data.get('publish_at', ''),
                    'author': content_data.get('author', ''),
                    'source': 'bnext_detail',
                    'tags': ', '.join(content_data.get('tags', [])) if isinstance(content_data.get('tags'), list) else ''
                }
                
                # 存儲到資料庫
                result = article_service.insert_article(db_article)
                if result:
                    print(f"  成功存儲文章到資料庫: {content_data['title']}")
                else:
                    print(f"  文章已存在或存儲失敗: {content_data['title']}")
            
            articles_contents.append(content_data)
            successful_count += 1
            
            # 顯示爬取進度
            if successful_count % 5 == 0 or i == num_articles:
                print(f"已成功爬取 {successful_count} 篇AI相關文章")
        
        # 如果沒有找到任何AI相關文章
        if not articles_contents:
            print("未找到符合條件的AI相關文章！")
            return pd.DataFrame()
        
        # 將文章內容保存到CSV
        contents_df = pd.DataFrame(articles_contents)
        
        # 處理相關文章列表（轉換為字符串）
        if 'related_articles' in contents_df.columns:
            contents_df['related_articles'] = contents_df['related_articles'].apply(
                lambda x: '; '.join([f"{a['title']} ({a['link']})" for a in x]) if isinstance(x, list) else ''
            )
        
        # 處理標籤列表
        if 'tags' in contents_df.columns:
            contents_df['tags'] = contents_df['tags'].apply(
                lambda x: ', '.join(x) if isinstance(x, list) else ''
            )
        
        # 將文章內容保存到CSV
        output_file = 'bnext_article_contents.csv'
        contents_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"已將文章內容保存至 {output_file}")
        
        return contents_df
