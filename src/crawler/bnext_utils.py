# bnext_utils.py
# 共用模組，提供 BnextScraper 和 BnextContentExtractor 共用的功能

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from src.crawler.bnext_config import BNEXT_CONFIG

class BnextUtils:
    """提供 Bnext 爬蟲共用的功能"""
    
    @staticmethod
    def build_selector(selector_dict):
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
    
    @staticmethod
    def find_element(container, selectors, selector_type):
        """
        使用選擇器格式查找元素
        """
        if not isinstance(selectors, list):
            return None
            
        for selector in selectors:
            if isinstance(selector, dict):
                css_selector = BnextUtils.build_selector(selector)
                element = container.select_one(css_selector)
                if element:
                    return element
        return None
    
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
