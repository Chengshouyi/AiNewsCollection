"""定義特定網站爬蟲的配置，使用 dataclass 進行結構化。"""

# 標準函式庫導入
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import logging # 移除舊的 logger 設定

# 本地應用程式導入
from src.crawlers.configs.base_config import DEFAULT_HEADERS
from src.error.errors import ValidationError
from src.utils.model_utils import validate_str, validate_url, validate_list


# 設定統一的 logger
logger = logging.getLogger(__name__)  # 使用統一的 logger



@dataclass
class SiteConfig:
    """儲存單一網站爬蟲配置的資料類別。"""
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

    def validate_url(self, url: str) -> bool:
        """根據配置驗證提供的 URL 是否有效。"""
        if not url:
            return False
        # 檢查域名是否有效
        if self.valid_domains and not any(url.startswith(domain) for domain in self.valid_domains):
             # logger.debug(f"URL '{url}' 不在有效域名 {self.valid_domains} 中")
            return False
        # 檢查 URL 是否包含必要模式
        if self.url_patterns and not any(pattern in url for pattern in self.url_patterns):
             # logger.debug(f"URL '{url}' 不包含必要模式 {self.url_patterns}")
            return False
        # 檢查文件擴展名是否有效
        if self.url_file_extensions and not any(url.endswith(ext) for ext in self.url_file_extensions):
            # logger.debug(f"URL '{url}' 不具有有效擴展名 {self.url_file_extensions}")
            return False
        return True

    def __post_init__(self):
        """在初始化後執行驗證。"""
        # 驗證必要欄位
        if not validate_str("name", required=True)(self.name):
            raise ValidationError(f"name: 欄位值 '{self.name}' 驗證失敗 (不能為空)")
        if not validate_url("base_url", required=True)(self.base_url):
            raise ValidationError(f"base_url: 欄位值 '{self.base_url}' 驗證失敗 (URL不能為空或格式錯誤)")
        if not validate_str("list_url_template", required=True)(self.list_url_template):
            raise ValidationError(f"list_url_template: 欄位值 '{self.list_url_template}' 驗證失敗 (不能為空)")
        if not validate_list("categories", type=str, min_length=1, required=True)(self.categories):
            raise ValidationError(f"categories: 欄位值 '{self.categories}' 驗證失敗 (列表長度不能小於 1)")
        if not validate_list("full_categories", type=str, min_length=1, required=True)(self.full_categories):
            raise ValidationError(f"full_categories: 欄位值 '{self.full_categories}' 驗證失敗 (列表長度不能小於 1)")
        # 可以在此處添加更多驗證，例如 selectors 的結構等

    def get_category_url(self, category_name: str) -> Optional[str]:
        """根據分類名稱格式化並返回列表頁面的 URL。"""
        if category_name not in self.categories:
            logger.warning("請求的分類 '%s' 不在配置的分類列表 %s 中", category_name, self.categories)
            return None
        try:
            return self.list_url_template.format(base_url=self.base_url, category=category_name)
        except KeyError as e:
            logger.error("格式化 URL 模板 '%s' 時缺少鍵: %s", self.list_url_template, e)
            return None

    def validate(self) -> bool:
        """執行基本的配置健全性檢查。實際驗證在 __post_init__ 中完成。"""
        # 這裡可以保留一個簡單的檢查，或者依賴 __post_init__ 的驗證
        # 目前 __post_init__ 已經涵蓋了 name 和 base_url 的非空驗證
        return True # 因為 __post_init__ 會在失敗時拋出異常