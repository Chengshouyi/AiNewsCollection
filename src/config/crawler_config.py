from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import json
from pathlib import Path

@dataclass
class CrawlerConfig:
    site_name: str
    base_url: str
    list_url_template: str
    categories: Dict[str, str]
    crawler_settings: Dict[str, Any] = field(default_factory=lambda: {
        'max_retries': 3,
        'retry_delay': 5,
        'timeout': 10
    })
    content_extraction: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load_from_json(cls, config_path: str):
        """從 JSON 文件載入配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            return cls(**config_data)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise ValueError(f"配置文件載入失敗: {e}")

    def validate(self) -> bool:
        """驗證配置的有效性"""
        if not self.base_url:
            return False
        if not len(self.categories) > 0:
            return False
        if self.crawler_settings.get('max_retries', 0) < 0:
            return False
        return True

    def get_category_url(self, category: str) -> Optional[str]:
        """獲取特定分類的 URL"""
        if category not in self.categories:
            return None
        return f"{self.base_url}{self.categories[category]}" 