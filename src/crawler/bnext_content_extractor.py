# content_extractor.py
# 用於爬取文章內容的模組

import requests
from bs4 import BeautifulSoup
import time
import random
from urllib.parse import urljoin
from typing import Dict, Optional
import pandas as pd
from src.crawler.base_config import DEFAULT_HEADERS
from src.crawler.bnext_config import BNEXT_CONFIG
from src.crawler.article_analyzer import ArticleAnalyzer

class BnextContentExtractor:
    def __init__(self):
        pass

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
            
            # 提取文章內容
            content_selectors = [
                f"{selector['tag']}[class='{selector['attrs'].get('class', '')}']" 
                for selector in BNEXT_CONFIG.selectors['content']
            ]
            
            content_element = None
            for selector in content_selectors:
                content_element = soup.select_one(selector)
                if content_element:
                    break
            
            if not content_element:
                print(f"無法找到文章內容: {article_url}")
                return None
            
            # 提取內容中的文字，排除不需要的標籤
            for unwanted in content_element.select('script, style, .ad, .advertisement, .social-share'):
                unwanted.extract()
            
            # 提取文章內容文本
            content_text = content_element.get_text(separator='\n', strip=True)
            
            # 提取發布日期
            date_element = soup.select_one('time, .date, .published-date, .article-date')
            publish_date = date_element.get_text(strip=True) if date_element else None
            
            # 提取作者
            author_element = soup.select_one('.author, .writer, .article-author')
            author = author_element.get_text(strip=True) if author_element else None
            
            # 提取標籤
            tags = []
            tags_elements = soup.select('.tags a, .tag a, .article-tags a')
            for tag_element in tags_elements:
                tag_text = tag_element.get_text(strip=True)
                if tag_text:
                    tags.append(tag_text)
            
            # 提取相關文章
            related_articles = []
            related_elements = soup.select('.related-article a, .related-post a, .more-article a')
            for related_element in related_elements:
                related_link = related_element.get('href', '')
                related_title = related_element.get_text(strip=True)
                
                # 確保連結是完整的
                if related_link and isinstance(related_link, str) and not related_link.startswith('http'):
                    related_link = urljoin(BNEXT_CONFIG.base_url, related_link)
                
                if related_link and related_title:
                    related_articles.append({
                        'title': related_title,
                        'link': related_link
                    })
            
            # 創建文章內容字典
            article_content = {
                'publish_date': publish_date,
                'author': author,
                'content': content_text,
                'content_length': len(content_text),
                'tags': tags,
                'related_articles': related_articles
            }
            
            # 檢查是否符合AI相關條件
            if ai_filter:
                if not ArticleAnalyzer().is_ai_related(article_content, min_keywords=min_keywords):
                    return None
            
            return article_content
        
        except Exception as e:
            print(f"獲取文章內容時發生錯誤 ({article_url}): {e}")
            return None

    def batch_get_articles_content(self, articles_df, num_articles=10, ai_only=True, min_keywords=3):
        """
        批量獲取文章內容
        
        Parameters:
        articles_df (pandas.DataFrame): 包含文章基本信息的DataFrame
        num_articles (int): 要處理的文章數量
        ai_only (bool): 是否只處理AI相關文章
        min_keywords (int): 判斷為AI相關文章的最少關鍵字數量
        
        Returns:
        pandas.DataFrame: 包含文章詳細內容的DataFrame
        """
        
        # 爬取指定數量的文章內容
        print(f"\n正在爬取前 {num_articles} 篇文章的內容...")
        articles_contents = []
        successful_count = 0
        
        for i, (_, article) in enumerate(articles_df.head(num_articles).iterrows(), 1):
            print(f"正在爬取 {i}/{num_articles}: {article['title']}")
            content_data = self._get_article_content(article['link'], ai_filter=ai_only, min_keywords=min_keywords)
            
            # 如果不是AI相關文章且啟用了AI過濾，則跳過
            if content_data is None:
                print(f"  跳過: 非AI相關文章或內容獲取失敗")
                continue
            
            # 合併文章基本資訊和內容
            content_data.update({
                'title': article['title'],
                'link': article['link'],
                'category': article.get('category'),
                'source_page': article.get('source_page')
            })
            
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
        
        return contents_df
