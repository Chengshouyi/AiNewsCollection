import pytest
from bs4 import BeautifulSoup
from src.crawlers.bnext_utils import BnextUtils
from unittest.mock import patch
import time

class TestBnextUtils:
    def test_get_random_sleep_time_in_range(self):
        """測試 get_random_sleep_time 返回值在指定範圍內"""
        min_time = 0.5
        max_time = 1.5
        sleep_time = BnextUtils.get_random_sleep_time(min_time, max_time)
        assert min_time <= sleep_time <= max_time

    @patch('time.sleep')
    def test_sleep_random_time_calls_sleep(self, mock_sleep):
        """測試 sleep_random_time 調用了 time.sleep"""
        min_time = 0.1
        max_time = 0.2
        returned_sleep_time = BnextUtils.sleep_random_time(min_time, max_time)
        mock_sleep.assert_called_once()
        args, _ = mock_sleep.call_args
        assert min_time <= args[0] <= max_time
        assert returned_sleep_time == args[0]

    def test_find_element_by_selector(self):
        """測試 find_element 通過 CSS 選擇器找到單個元素"""
        html = '<div class="container"><h1 class="title">Hello</h1></div>'
        soup = BeautifulSoup(html, 'html.parser')
        element = BnextUtils.find_element(soup, '.title')
        assert element is not None
        assert element.text == 'Hello'

    def test_find_element_by_selector_not_found(self):
        """測試 find_element 在找不到元素時返回 None"""
        html = '<div class="container"></div>'
        soup = BeautifulSoup(html, 'html.parser')
        element = BnextUtils.find_element(soup, '.title')
        assert element is None

    def test_find_element_by_tag_and_class(self):
        """測試 find_element 通過標籤類型和 class 找到元素"""
        html = '<div class="container"><span class="item highlight">World</span></div>'
        soup = BeautifulSoup(html, 'html.parser')
        element = BnextUtils.find_element(soup, 'highlight', tag_type='span')
        assert element is not None
        assert element.text == 'World'

    def test_find_element_by_tag_and_class_not_found(self):
        """測試 find_element 在通過標籤類型和 class 找不到元素時返回 None"""
        html = '<div class="container"><span>Text</span></div>'
        soup = BeautifulSoup(html, 'html.parser')
        element = BnextUtils.find_element(soup, 'highlight', tag_type='span')
        assert element is None

    def test_find_element_with_multiple_selectors_first_found(self):
        """測試 find_element 使用多個選擇器時返回第一個找到的元素"""
        html = '<div class="container"><h1 class="title">Hello</h1><p class="content">World</p></div>'
        soup = BeautifulSoup(html, 'html.parser')
        selectors = ['.content', '.title']
        element = BnextUtils.find_element(soup, selectors)
        assert element is not None
        assert element.name == 'p'
        assert element.text == 'World'

    def test_find_element_with_multiple_selectors_none_found(self):
        """測試 find_element 使用多個選擇器時如果都找不到則返回 None"""
        html = '<div class="container"></div>'
        soup = BeautifulSoup(html, 'html.parser')
        selectors = ['.content', '.title']
        element = BnextUtils.find_element(soup, selectors)
        assert element is None

    def test_find_element_with_empty_container(self):
        """測試 find_element 在容器為 None 時返回 None"""
        element = BnextUtils.find_element(None, '.title')
        assert element is None

    def test_normalize_url_absolute(self):
        """測試 normalize_url 處理絕對 URL"""
        base_url = 'https://www.example.com'
        url = 'https://www.another.com/page'
        normalized = BnextUtils.normalize_url(url, base_url)
        assert normalized == url

    def test_normalize_url_relative_path(self):
        """測試 normalize_url 處理相對路徑 URL"""
        base_url = 'https://www.example.com'
        url = '/page'
        normalized = BnextUtils.normalize_url(url, base_url)
        assert normalized == 'https://www.example.com/page'

    def test_normalize_url_relative_to_current(self):
        """測試 normalize_url 處理相對於當前路徑的 URL"""
        base_url = 'https://www.example.com/section/'
        url = 'item'
        normalized = BnextUtils.normalize_url(url, base_url)
        assert normalized == 'https://www.example.com/section/item'

    def test_normalize_url_empty(self):
        """測試 normalize_url 處理空 URL"""
        base_url = 'https://www.example.com'
        url = ''
        normalized = BnextUtils.normalize_url(url, base_url)
        assert normalized is None

    def test_get_soup_from_html(self):
        """測試 get_soup_from_html 返回 BeautifulSoup 對象"""
        html = '<html><head><title>Test</title></head><body><h1>Hello</h1></body></html>'
        soup = BnextUtils.get_soup_from_html(html)
        if soup is None:
            assert False, "soup 為 None"
        else:
            assert isinstance(soup, BeautifulSoup)
            if soup.title:
                assert soup.title.string == 'Test'
            if soup.h1:
                assert soup.h1.text == 'Hello'