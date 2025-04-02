# bnext_utils.py
# 共用模組，提供 BnextScraper 和 BnextContentExtractor 共用的功能

from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import time
import logging
import random
from typing import Optional, Dict, Any
from src.crawlers.configs.site_config import SiteConfig
import json


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
    

 
