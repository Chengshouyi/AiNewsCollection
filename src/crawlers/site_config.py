from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from src.crawlers.base_config import DEFAULT_HEADERS

@dataclass
class SiteConfig:
    """網站配置類別"""
    name: str
    base_url: str
    list_url_template: str
    categories: Dict[str, str] = field(default_factory=dict)
    crawler_settings: Dict[str, Any] = field(default_factory=lambda: {
        'max_retries': 3,
        'retry_delay': 5,
        'timeout': 10
    })
    content_extraction: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=lambda: DEFAULT_HEADERS)
    selectors: Dict[str, List[Dict]] = field(default_factory=dict)
    valid_domains: List[str] = field(default_factory=list)
    url_patterns: List[str] = field(default_factory=list)
    url_file_extensions: List[str] = field(default_factory=lambda: ['.html', '.htm'])
    default_categories: List[str] = field(default_factory=list)
    date_format: str = '%Y/%m/%d %H:%M'
    
    # 選擇器配置
    selectors: Dict[str, List[Dict]] = field(default_factory=dict)
    
    def validate_url(self, url: str) -> bool:
        if not url or not any(url.startswith(domain) for domain in self.valid_domains):
            return False
        if not any(pattern in url for pattern in self.url_patterns):
            return False
        if self.url_file_extensions and not any(url.endswith(ext) for ext in self.url_file_extensions):
            return False
        return True

    def __post_init__(self):
        default_selectors = {'list': [], 'content': [], 'date': [], 'title': [], 'pagination': []}
        self.selectors = {**default_selectors, **self.selectors}
        if not self.valid_domains: self.valid_domains = [self.base_url]

    def get_category_url(self, category: str) -> Optional[str]:
        """獲取特定分類的 URL"""
        if category not in self.categories:
            return None
        return f"{self.base_url}{self.categories[category]}"

    def validate(self) -> bool:
        """驗證站點配置"""
        return bool(self.name and self.base_url)

    @classmethod
    def from_crawler_config(cls, crawler_config):
        """從 CrawlerConfig 對象創建 SiteConfig"""
        return cls(
            name=crawler_config.site_name,
            base_url=crawler_config.base_url,
            list_url_template=crawler_config.list_url_template,
            categories=crawler_config.categories,
            crawler_settings=crawler_config.crawler_settings,
            content_extraction=crawler_config.content_extraction,
            default_categories=crawler_config.default_categories
        )

