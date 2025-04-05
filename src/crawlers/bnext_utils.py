# bnext_utils.py
# 共用模組，提供 BnextScraper 和 BnextContentExtractor 共用的功能

from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import logging
import random
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BnextUtils:
    """明日科技爬蟲的工具類"""

    @staticmethod
    def get_random_sleep_time(min_time: float = 1.0, max_time: float = 3.0):
        """產生隨機休眠時間"""
        return random.uniform(min_time, max_time)
        
    @staticmethod
    def sleep_random_time(min_time: float = 1.0, max_time: float = 3.0):
        """隨機休眠指定範圍的時間"""
        sleep_time = BnextUtils.get_random_sleep_time(min_time, max_time)
        time.sleep(sleep_time)
        return sleep_time
        
    @staticmethod
    def find_element(container, selectors, tag_type=None):
        """
        在容器中查找元素
        
        Args:
            container: BeautifulSoup或Tag
            selectors: 選擇器列表或字符串
            tag_type: 標籤類型（可選）
            
        Returns:
            找到的元素或None
        """
        if not container:
            return None
            
        # 處理多個選擇器
        if isinstance(selectors, list):
            for selector in selectors:
                element = BnextUtils.find_element(container, selector, tag_type)
                if element:
                    return element
            return None
        
        # 單一選擇器
        if tag_type:
            elements = container.find_all(tag_type, class_=selectors)
            return elements[0] if elements else None
        else:
            return container.select_one(selectors)
            
    @staticmethod
    def normalize_url(url, base_url):
        """標準化URL（處理相對路徑）"""
        if not url:
            return None
        return urljoin(base_url, url)
        
    @staticmethod
    def get_soup_from_html(html):
        """從HTML字符串創建BeautifulSoup對象"""
        return BeautifulSoup(html, 'html.parser')
    
    @staticmethod
    def get_article_columns_dict(
        title: Optional[str] = '', 
        summary: Optional[str] = '', 
        content: Optional[str] = '', 
        link: Optional[str] = '', 
        category: Optional[str] = '', 
        published_at: Optional[datetime] = None, 
        author: Optional[str] = '', 
        source: Optional[str] = '', 
        source_url: Optional[str] = '', 
        article_type: Optional[str] = '', 
        tags: Optional[str] = '', 
        is_ai_related: Optional[bool] = False, 
        is_scraped: Optional[bool] = False) -> Dict:
        """獲取文章欄位字典"""
        return {
            'title': title,
            'summary': summary,
            'content': content,
            'link': link,
            'category': category,
            'published_at': published_at,
            'author': author,
            'source': source,
            'source_url': source_url,
            'article_type': article_type,
            'tags': tags,
            'is_ai_related': is_ai_related,
            'is_scraped': is_scraped
        }
    
    @staticmethod
    def process_articles_to_dataframe(articles_list: List[Dict]) -> pd.DataFrame:
        """處理文章列表並轉換為DataFrame"""
        if not articles_list:
            logger.warning("未爬取到任何文章")
            return pd.DataFrame()
            
        df = pd.DataFrame(articles_list)
        df = df.drop_duplicates(subset=['link'], keep='first')
        
        # 添加統計信息
        stats = {
            'total': len(df)
        }
        
        logger.debug("爬取統計信息:")
        logger.debug(f"總文章數: {stats['total']}")
        
        return df

 
