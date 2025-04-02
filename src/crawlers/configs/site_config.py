from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import logging
from src.crawlers.configs.base_config import DEFAULT_HEADERS

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class SiteConfig:
    """網站配置類別"""
    name: str
    base_url: str = "https://www.bnext.com.tw"  # 設定預設值
    list_url_template: str = ""
    categories: List[str] = field(default_factory=lambda: ["ai", "tech", "iot", "smartmedical", "smartcity", "cloudcomputing", "security"])
    full_categories: List[str] = field(default_factory=list)
    crawler_settings: Dict[str, Any] = field(default_factory=lambda: {
        'max_retries': 3,
        'retry_delay': 5,
        'timeout': 10
    })
    content_extraction: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=lambda: DEFAULT_HEADERS)
    selectors: Dict[str, Any] = field(default_factory=dict)
    valid_domains: List[str] = field(default_factory=list)
    url_patterns: List[str] = field(default_factory=list)
    url_file_extensions: List[str] = field(default_factory=lambda: ['.html', '.htm'])
    date_format: str = '%Y/%m/%d %H:%M'
    
    def validate_url(self, url: str) -> bool:
        if not url or not any(url.startswith(domain) for domain in self.valid_domains):
            return False
        if not any(pattern in url for pattern in self.url_patterns):
            return False
        if self.url_file_extensions and not any(url.endswith(ext) for ext in self.url_file_extensions):
            return False
        return True

    def __post_init__(self):
        # 驗證並設定預設值
        if not self.base_url:
            logger.error("未提供網站基礎URL，將使用預設值")
            self.base_url = "https://www.bnext.com.tw"
            
        if not self.categories:
            logger.error("未提供預設類別，將使用預設值")
            self.categories = ["ai", "tech", "iot", "smartmedical", "smartcity", "cloudcomputing", "security"]
            
        if not self.selectors:
            logger.error("未提供選擇器，將使用預設值")
            self.selectors = {}
            
        # 如果未提供 list_url_template，創建一個基於 base_url 的預設模板
        if not self.list_url_template:
            logger.error("未提供列表URL模板，將使用預設值")
            self.list_url_template = "{base_url}/categories/{category}"
            
        # 若 valid_domains 為空，則使用 base_url
        if not self.valid_domains:
            self.valid_domains = [self.base_url]
            
        # 確保 name 不為空
        if not self.name:
            logger.error("未提供網站名稱，請設定有效名稱")
            raise ValueError("網站名稱不能為空")

    def get_category_url(self, category_name: str) -> Optional[str]:
        """獲取特定分類的 URL"""
        if category_name not in self.categories:
            return None
        return self.list_url_template.format(base_url=self.base_url, category=category_name)

    def validate(self) -> bool:
        """驗證站點配置"""
        return bool(self.name and self.base_url)