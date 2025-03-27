# bnext_utils.py
# 共用模組，提供 BnextScraper 和 BnextContentExtractor 共用的功能

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from src.crawlers.bnext_config import BNEXT_CONFIG
import re
import time
import logging
import random

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
    def build_url(base_url, path=None, params=None):
        """建構完整URL"""
        url = base_url
        if path:
            url = urljoin(url, path)
            
        if params:
            query_params = '&'.join([f"{k}={v}" for k, v in params.items()])
            url = f"{url}?{query_params}"
            
        return url
    
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
    def clean_text(text):
        """清理文本中的多餘空白"""
        if not text:
            return ""
        # 替換多個空白為單一空白
        text = re.sub(r'\s+', ' ', text)
        # 移除前後空白
        return text.strip()
        
    @staticmethod
    def extract_date(date_string):
        """從日期字符串提取標準日期格式"""
        try:
            # 這裡可以實現對各種日期格式的處理
            # 例如：「2023-08-15」、「2023/08/15」、「2小時前」等
            return date_string
        except:
            return date_string
            
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
    def build_selector(selector):
        """構建並修復選擇器"""
        if not selector:
            return ""
        return BnextUtils.fix_tailwind_selector(selector)
    
    @staticmethod
    def find_elements_by_purpose(soup, selectors, purpose):
        """
        根據purpose屬性查找元素
        """
        matching_selectors = [s for s in selectors if s.get('purpose') == purpose]
        if not matching_selectors:
            return None
            
        for selector in matching_selectors:
            css_selector = BnextUtils.build_selector(selector)
            elements = soup.select(css_selector)
            if elements:
                return elements
                
        return None
    
    @staticmethod
    def find_element_by_purpose(soup, selectors, purpose):
        """
        根據purpose屬性查找單個元素
        """
        elements = BnextUtils.find_elements_by_purpose(soup, selectors, purpose)
        return elements[0] if elements else None
    
    @staticmethod
    def extract_article_link(container, title_elem=None):
        """
        提取文章連結的通用方法
        """
        link = None
        
        # 從標題元素尋找
        if title_elem:
            parent_a = title_elem.find_parent('a')
            if parent_a and 'href' in parent_a.attrs:
                link = parent_a['href']
        
        # 從容器中尋找
        if not link:
            link_elem = BnextUtils.find_element(container, BNEXT_CONFIG.selectors['common_elements'][3:], 'link')
            if link_elem:
                link = link_elem['href']
        
        # 確保連結是完整的
        if link and not link.startswith('http'):
            link = urljoin(BNEXT_CONFIG.base_url, link)
            
        return link

    @staticmethod
    def fix_css_selector(selector: str) -> str:
        """
        修復 CSS 選擇器中的 Tailwind 類名問題
        
        Args:
            selector (str): 原始選擇器
            
        Returns:
            str: 修復後的選擇器
        """
        # 修復常見的 Tailwind 偽類問題，例如 :block, :flex 等
        problematic_patterns = [':block', ':flex', ':grid', ':hidden']
        
        fixed_selector = selector
        for pattern in problematic_patterns:
            # 將 class:block 轉換為 class[class*=block]
            fixed_selector = fixed_selector.replace(pattern, '')
        
        return fixed_selector

    @staticmethod
    def fix_tailwind_selector(selector: str) -> str:
        """
        修復 Tailwind CSS 選擇器中的偽類問題
        
        Args:
            selector (str): 原始選擇器
            
        Returns:
            str: 修復後的選擇器
        """
        if not selector:
            return ""
        
        # 常見的 Tailwind 偽類問題
        tailwind_classes = [':block', ':flex', ':grid', ':hidden']
        
        fixed_selector = selector
        for cls in tailwind_classes:
            # 移除冒號，因為這些實際上是類名而非偽類
            fixed_selector = fixed_selector.replace(cls, '')
        
        return fixed_selector

    @staticmethod
    def extract_focus_articles(soup):
        try:
            # 修復原來的選擇器 ".pc.hidden.lg:block > div.grid.grid-cols-6.gap-4.relative.h-full"
            container_selector = BnextUtils.fix_css_selector(".pc.hidden.lg > div.grid.grid-cols-6.gap-4.relative.h-full")
            focus_article_containers = soup.select(container_selector)
            
            if not focus_article_containers:
                # 嘗試更寬鬆的選擇器
                focus_article_containers = soup.select("div.grid.grid-cols-6")
        except Exception as e:
            logger.warning(f"選擇器解析失敗：{e}")
            # 備用選擇器
            focus_article_containers = soup.select('div.grid > div')
        
        return focus_article_containers
