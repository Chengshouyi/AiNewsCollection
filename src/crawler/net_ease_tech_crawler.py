from typing import Optional, Dict, List
import requests
from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString
import time
import random
import json
import logging
from fake_useragent import UserAgent
from .base_crawler import BaseCrawler
from .site_config import SiteConfig, TECH163_CONFIG

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NetEaseTechCrawler(BaseCrawler):
    def __init__(self, name: str, url: str):
        super().__init__(name, url)
        # 初始化 User-Agent
        self.ua = UserAgent()
        # AI 相關關鍵詞
        self.ai_keywords = ["人工智能", "AI", "机器学习", "深度学习", "智能"]

    def _get_headers(self):
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    def _fetch_news_list(self, config: SiteConfig) -> List[Dict[str, str]]:
        """
        爬取新聞列表
        """
        url = config.list_url_template.format(base_url=config.base_url)
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            articles: List[Dict[str, str]] = []
            for selector in config.selectors['list']:
                items = soup.find_all(selector['tag'], **selector['attrs'])
                for item in items:
                    # type: ignore 用於忽略型別檢查
                    link_tag = item.find('a')  # type: ignore
                    if link_tag is not None:
                        # type: ignore 用於忽略型別檢查
                        title: str = link_tag.get_text(strip=True)  # type: ignore
                        # type: ignore 用於忽略型別檢查
                        href: str = str(link_tag.get('href', ''))  # type: ignore
                        full_url: str = href if href.startswith('http') else str(config.base_url) + href.lstrip('/')
                        if config.validate_url(full_url) and any(kw in title for kw in self.ai_keywords):
                            articles.append({"title": title, "link": full_url})
            return articles
        except requests.RequestException as e:
            logger.error(f"爬取新聞列表時發生錯誤: {e}")
            return []
        except Exception as e:
            logger.error(f"爬取新聞列表時發生錯誤: {e}")
            return []

    def _fectch_artcle_details(self, config: SiteConfig, url: str):
        """
        爬取新聞詳細內容
        """
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            content = "無內容"
            for selector in config.selectors['content']:
                if elem := soup.find(selector['tag'], **selector['attrs']):
                    content = elem.get_text(strip=True)
                    break

            date = "未知時間"
            for selector in config.selectors['date']:
                if elem := soup.find(selector['tag'], **selector['attrs']):
                    date = elem.get_text(strip=True)
                    break

            title = "未知標題"
            for selector in config.selectors['title']:
                if elem := soup.find(selector['tag'], **selector['attrs']):
                    title = elem.get_text(strip=True)
                    break

            return {"title": title, "content": content, "publish_time": date}
        except requests.RequestException as e:
            logger.error(f"爬取新聞詳細內容時發生錯誤: {e}")
            return {"title": "錯誤", "content": "錯誤", "publish_time": "未知"}
        except Exception as e:
            logger.error(f"爬取新聞詳細內容時發生錯誤: {e}")
            return {"title": "錯誤", "content": "錯誤", "publish_time": "未知"}

    def _fetch_page(self, url: str) -> Optional[str]:
        """
        爬取網頁內容
        """
        config = TECH163_CONFIG
        news_list = self._fetch_news_list(config)
    
        results = []
        for news in news_list:
            print(f"正在處理: {news['title']}")
            details = self._fectch_artcle_details(config, news['link'])
            results.append({
                "title": news['title'],
                "link": news['link'],
                "content": details['content'],
                "publish_time": details['publish_time']
            })
            time.sleep(random.uniform(1, 3))  # 隨機延遲避免被封
        
        with open("tech163_ai_news.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print("爬取完成，已保存至 tech163_ai_news.json")
        

    def _save_data(self, data: Dict):
        """
        保存網頁內容
        """
        pass

    def run(self):
        """
        執行爬取流程
        """
        self._fetch_page(self.url)


if __name__ == "__main__":
    crawler = NetEaseTechCrawler("NetEaseTech", "https://tech.163.com/")
    crawler.run()

