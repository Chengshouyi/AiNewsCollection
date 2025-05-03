"""數位時代 (Bnext) 爬蟲共用工具模組。

提供 BnextScraper 和 BnextContentExtractor 共用的功能，例如：
- 隨機休眠
- HTML 元素查找
- URL 標準化
- HTML 解析
- 資料結構轉換 (字典, DataFrame)
"""

import random
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urljoin
import logging

import pandas as pd
from bs4 import BeautifulSoup



logger = logging.getLogger(__name__)  # 使用統一的 logger

class BnextUtils:
    """數位時代爬蟲的工具類"""

    @staticmethod
    def get_random_sleep_time(min_time: float = 1.0, max_time: float = 3.0) -> float:
        """產生隨機休眠時間"""
        return random.uniform(min_time, max_time)

    @staticmethod
    def sleep_random_time(min_time: float = 1.0, max_time: float = 3.0) -> float:
        """隨機休眠指定範圍的時間，並返回實際休眠秒數"""
        sleep_time = BnextUtils.get_random_sleep_time(min_time, max_time)
        time.sleep(sleep_time)
        return sleep_time

    @staticmethod
    def find_element(container, selectors, tag_type=None):
        """
        在指定的 BeautifulSoup 容器中查找 HTML 元素。

        Args:
            container: BeautifulSoup 物件或 Tag 物件。
            selectors: CSS 選擇器字串或選擇器列表。
            tag_type: 標籤類型字串 (例如 'span', 'div')，當 selectors 為 class 名稱時使用。

        Returns:
            找到的第一個元素 (Tag 物件) 或 None。
        """
        if not container:
            return None

        # 處理選擇器列表，返回第一個成功找到的元素
        if isinstance(selectors, list):
            for selector in selectors:
                element = BnextUtils.find_element(container, selector, tag_type)
                if element:
                    return element
            return None

        # 處理單一選擇器
        if tag_type:
            # 按標籤類型和 class 查找
            elements = container.find_all(tag_type, class_=selectors)
            return elements[0] if elements else None
        else:
            # 按 CSS 選擇器查找
            return container.select_one(selectors)

    @staticmethod
    def normalize_url(url: Optional[str], base_url: str) -> Optional[str]:
        """將可能為相對路徑的 URL 標準化為絕對 URL"""
        if not url:
            return None
        return urljoin(base_url, url)

    @staticmethod
    def get_soup_from_html(html: str) -> Optional[BeautifulSoup]:
        """從 HTML 原始碼字串創建 BeautifulSoup 物件"""
        if not html:
            return None
        return BeautifulSoup(html, 'html.parser')

    @staticmethod
    def get_article_columns_dict(
        title: Optional[str] = '',
        summary: Optional[str] = '',
        content: Optional[str] = '',
        link: Optional[str] = '',
        category: Optional[str] = '',
        published_at: Optional[str] = None,
        author: Optional[str] = '',
        source: Optional[str] = '',
        source_url: Optional[str] = '',
        article_type: Optional[str] = '',
        tags: Optional[str] = '',
        is_ai_related: Optional[bool] = False,
        is_scraped: Optional[bool] = False,
        scrape_status: Optional[str] = 'pending',
        scrape_error: Optional[str] = None,
        last_scrape_attempt: Optional[datetime] = None,
        task_id: Optional[int] = None) -> Dict:
        """建立包含單一文章所有欄位的字典 (常用於資料庫操作)

        Returns:
            Dict: 包含文章各欄位鍵值對的字典。
        """
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
            'is_scraped': is_scraped,
            'scrape_status': scrape_status,
            'scrape_error': scrape_error,
            'last_scrape_attempt': last_scrape_attempt,
            'task_id': task_id
        }

    @staticmethod
    def get_article_columns_dict_for_df(
        title: Optional[str] = '',
        summary: Optional[str] = '',
        content: Optional[str] = '',
        link: Optional[str] = '',
        category: Optional[str] = '',
        published_at: Optional[str] = None,
        author: Optional[str] = '',
        source: Optional[str] = '',
        source_url: Optional[str] = '',
        article_type: Optional[str] = '',
        tags: Optional[str] = '',
        is_ai_related: Optional[bool] = False,
        is_scraped: Optional[bool] = False,
        scrape_status: Optional[str] = 'pending',
        scrape_error: Optional[str] = None,
        last_scrape_attempt: Optional[datetime] = None,
        task_id: Optional[int] = None) -> Dict:
        """建立適合直接轉換為 Pandas DataFrame 的文章欄位字典。
           與 get_article_columns_dict 不同，此方法的值為列表。

        Returns:
            Dict: 包含列表形式值的字典，適合單行 DataFrame 創建。
        """
        return {
            'title': [title],
            'summary': [summary],
            'content': [content],
            'link': [link],
            'category': [category],
            'published_at': [published_at],
            'author': [author],
            'source': [source],
            'source_url': [source_url],
            'article_type': [article_type],
            'tags': [tags],
            'is_ai_related': [is_ai_related],
            'is_scraped': [is_scraped],
            'scrape_status': [scrape_status],
            'scrape_error': [scrape_error],
            'last_scrape_attempt': [last_scrape_attempt],
            'task_id': [task_id]
        }

    @staticmethod
    def process_articles_to_dataframe(articles_list: List[Dict]) -> pd.DataFrame:
        """將包含多個文章字典的列表轉換為 Pandas DataFrame，並去除重複連結。

        Args:
            articles_list: 包含多個文章字典的列表。

        Returns:
            pd.DataFrame: 包含文章資料的 DataFrame，若列表為空則返回空的 DataFrame。
        """
        if not articles_list:
            logger.warning("輸入的文章列表為空，無法轉換為 DataFrame。")
            return pd.DataFrame()

        # 將每個文章字典轉換為單行 DataFrame，確保所有欄位都存在
        df_articles = []
        for article in articles_list:
            # 使用 .get() 提供預設值，避免 KeyError
            article_data = {
                'title': article.get('title', ''),
                'summary': article.get('summary', ''),
                'content': article.get('content', ''),
                'link': article.get('link', ''),
                'category': article.get('category', ''),
                'published_at': article.get('published_at', None),
                'author': article.get('author', ''),
                'source': article.get('source', ''),
                'source_url': article.get('source_url', ''),
                'article_type': article.get('article_type', ''),
                'tags': article.get('tags', ''),
                'is_ai_related': article.get('is_ai_related', False),
                'is_scraped': article.get('is_scraped', False),
                'scrape_status': article.get('scrape_status', 'pending'),
                'scrape_error': article.get('scrape_error', None),
                'last_scrape_attempt': article.get('last_scrape_attempt', None),
                'task_id': article.get('task_id', None)
            }
            # 將單個字典包裝在列表中以創建單行 DataFrame
            df_articles.append(pd.DataFrame([article_data]))

        # 合併所有單行 DataFrame
        if df_articles:
            df = pd.concat(df_articles, ignore_index=True)
            # 根據 'link' 欄位去除重複的文章，保留第一個出現的
            df = df.drop_duplicates(subset=['link'], keep='first')
            logger.info("已將 %d 篇文章處理並轉換為 DataFrame (已去除重複)。", len(df))
        else:
            # 如果轉換過程中沒有有效的 DataFrame 生成
            df = pd.DataFrame()
            logger.warning("處理後未生成有效的 DataFrame。")

        # 日誌記錄處理後的統計信息
        stats = {
            'total': len(df)
        }
        logger.debug("DataFrame 處理統計信息:")
        logger.debug("最終 DataFrame 文章數: %s", stats['total']) # 修正 Pylint W1203

        return df

 
