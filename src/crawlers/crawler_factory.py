from typing import Dict, Any, Optional

from src.crawlers.base_crawler import BaseCrawler
from src.crawlers.bnext_crawler import BnextCrawler
from src.crawlers.site_config import SiteConfig
from src.crawlers.bnext_config import BNEXT_CONFIG

class CrawlerFactory:
    """爬蟲工廠類，負責創建各種爬蟲實例"""
    
    def __init__(self):
        # 註冊所有支持的爬蟲類型
        self.crawler_types = {
            'bnext': BnextCrawler,
            # 可以添加其他爬蟲類型
        }
        
        # 默認配置
        self.default_configs = {
            'bnext': BNEXT_CONFIG,
            # 可以添加其他爬蟲的默認配置
        }
        
    def get_crawler(self, crawler_type: str, config: Optional[Dict[str, Any]] = None) -> BaseCrawler:
        """
        根據類型和配置創建爬蟲實例
        
        Args:
            crawler_type: 爬蟲類型，如 'bnext'
            config: 爬蟲配置，如果為None則使用默認配置
            
        Returns:
            對應類型的爬蟲實例
        
        Raises:
            ValueError: 如果爬蟲類型不支持
        """
        if crawler_type not in self.crawler_types:
            raise ValueError(f"不支持的爬蟲類型: {crawler_type}")
            
        crawler_class = self.crawler_types[crawler_type]
        
        # 使用提供的配置或默認配置
        site_config = SiteConfig(**config) if config else self.default_configs[crawler_type]
        
        return crawler_class(site_config)
        
    def get_supported_crawler_types(self):
        """獲取所有支持的爬蟲類型列表"""
        return list(self.crawler_types.keys())
        
    def register_crawler_type(self, type_name: str, crawler_class, default_config: Optional[SiteConfig] = None):
        """註冊新的爬蟲類型"""
        self.crawler_types[type_name] = crawler_class
        if default_config is not None:
            self.default_configs[type_name] = default_config 