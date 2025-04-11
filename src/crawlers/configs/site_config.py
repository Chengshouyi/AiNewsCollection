from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import logging
from src.crawlers.configs.base_config import DEFAULT_HEADERS
from src.utils.model_utils import validate_str, validate_url, validate_list

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class SiteConfig:
    """網站配置類別"""
    name: str
    base_url: str
    list_url_template: str
    categories: List[str]
    full_categories: List[str]
    selectors: Dict[str, Any]
    headers: Dict[str, str] = field(default_factory=lambda: DEFAULT_HEADERS)
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
        name_validator = validate_str("name", max_length=100, required=True)
        if not name_validator(self.name):
            raise ValueError("網站名稱不能為空")
        base_url_validator = validate_url("base_url", max_length=1000, required=True)
        if not base_url_validator(self.base_url):
            raise ValueError("網站基礎URL不能為空")
        list_url_template_validator = validate_str("list_url_template", max_length=1000, required=True)
        if not list_url_template_validator(self.list_url_template):
            raise ValueError("列表URL模板不能為空")
        categories_validator = validate_list("categories", type=str, min_length=1, required=True)
        if not categories_validator(self.categories):
            raise ValueError("分類不能為空，或分類列表中的元素必須是字串")
        full_categories_validator = validate_list("full_categories", type=str, min_length=1, required=True)
        if not full_categories_validator(self.full_categories):
            raise ValueError("完整分類不能為空，或完整分類列表中的元素必須是字串")
        


    def get_category_url(self, category_name: str) -> Optional[str]:
        """獲取特定分類的 URL"""
        if category_name not in self.categories:
            return None
        return self.list_url_template.format(base_url=self.base_url, category=category_name)

    def validate(self) -> bool:
        """驗證站點配置"""
        return bool(self.name and self.base_url)