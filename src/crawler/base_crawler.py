from abc import ABC, abstractmethod
import requests
from typing import Optional, Dict

class BaseCrawler(ABC):
    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

    def _fetch_page(self, url: str) -> Optional[str]:
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    @abstractmethod
    def _save_data(self, data: Dict):
        """
        保存數據，子類別需要實作
        """
        pass

    @abstractmethod
    def run(self) -> Optional[Dict]:
        """
        執行爬取流程，子類別需要實作
        """
        pass

   
