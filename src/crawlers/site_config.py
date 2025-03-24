from dataclasses import dataclass, field
from typing import List, Dict
from src.crawlers.base_config import DEFAULT_HEADERS
@dataclass
class SiteConfig:
    """網站配置類別"""
    name: str
    base_url: str
    list_url_template: str
    headers: Dict[str, str] = field(default_factory=lambda: DEFAULT_HEADERS)
    selectors: Dict[str, List[Dict]] = field(default_factory=dict)
    valid_domains: List[str] = field(default_factory=list)
    url_patterns: List[str] = field(default_factory=list)
    url_file_extensions: List[str] = field(default_factory=lambda: ['.html', '.htm'])
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

