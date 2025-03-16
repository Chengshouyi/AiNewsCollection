from abc import ABC, abstractmethod
from typing import Dict
import pandas as pd
from src.crawler.site_config import SiteConfig

class BaseCrawler(ABC):
    def __init__(self, config: SiteConfig):
        self.site_config = config

    @abstractmethod
    def fetch_article_list(self, args: dict, **kwargs) -> pd.DataFrame:
        """
        爬取新聞列表，子類別需要實作
        """
        pass

    @abstractmethod
    def fetch_article_details(self, args: dict, **kwargs) -> pd.DataFrame:
        """
        爬取文章詳細內容，子類別需要實作
        """
        pass


    @abstractmethod
    def save_data(self, data: pd.DataFrame):
        """
        保存數據，子類別需要實作
        """
        pass

   
