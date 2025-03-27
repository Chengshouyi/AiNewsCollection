"""BNext 網站爬蟲的配置模組"""

from .site_config import SiteConfig
import json
import os
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# 預設配置
DEFAULT_BNEXT_CONFIG = {
    "name": "BNext",
        "base_url": "https://www.bnext.com.tw",
    "categories": {
        "ai": "/categories/ai",
        "tech": "/categories/tech",
        "startup": "/categories/startup"
    },
    "crawler_settings": {
        "max_retries": 3,
        "retry_delay": 5,
        "timeout": 10,
        "max_pages": 5
    },
    "content_extraction": {
        "min_keywords": 3,
        "ai_only": True
    }
}

# 定義預設分類
BNEXT_DEFAULT_CATEGORIES: List[str] = ["ai", "tech", "startup"]

def load_bnext_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    載入 BNext 爬蟲配置
    
    Args:
        config_path (str, optional): 配置文件路徑
        
    Returns:
        Dict[str, Any]: 配置字典
    """
    if not config_path:
        # 嘗試在預設位置尋找配置文件
        potential_paths = [
            "src/config/bnext_crawler_config.json",
            "../config/bnext_crawler_config.json",
            "config/bnext_crawler_config.json",
            "/workspace/src/config/bnext_crawler_config.json",  # 添加絕對路徑
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "bnext_crawler_config.json"),  # 使用相對於當前文件的路徑
            "bnext_crawler_config.json"
        ]
        
        for path in potential_paths:
            if os.path.exists(path):
                config_path = path
                logger.info(f"找到配置文件: {path}")
                break
    
    config_data = DEFAULT_BNEXT_CONFIG.copy()
    
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                # 使用文件配置更新默認配置
                config_data.update(file_config)
                
                # 特別處理選擇器配置，確保其結構正確
                if 'selectors' in file_config:
                    logger.info(f"從配置文件中載入選擇器配置，找到 {len(file_config['selectors'])} 個選擇器組")
                    if 'selectors' not in config_data:
                        config_data['selectors'] = {}
                    
                    # 確保選擇器下的項目都正確加載
                    selectors = file_config['selectors']
                    config_data['selectors'].update(selectors)
                    
                    # 記錄載入的選擇器配置
                    logger.debug(f"載入的選擇器配置: {list(config_data['selectors'].keys())}")
                
            logger.info(f"已載入 BNext 配置: {config_path}")
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.warning(f"載入配置文件失敗: {str(e)}，使用預設配置")
    else:
        logger.warning(f"未找到配置文件，使用預設配置。搜尋路徑: {', '.join(potential_paths)}")
    
    return config_data

def create_bnext_config(config_data: Optional[Dict[str, Any]] = None) -> SiteConfig:
    """
    創建 BNext 站點配置
    
    Args:
        config_data (Dict[str, Any], optional): 配置數據
        
    Returns:
        SiteConfig: 站點配置對象
    """
    if config_data is None:
        config_data = load_bnext_config()
    
    return SiteConfig(
        name=config_data.get("name", "BNext"),
        base_url=config_data.get("base_url", "https://www.bnext.com.tw"),
        list_url_template=config_data.get("list_url_template", "{base_url}/categories/{category}"),
        categories=config_data.get("categories", {}),
        crawler_settings=config_data.get("crawler_settings", {}),
        content_extraction=config_data.get("content_extraction", {}),
        default_categories=config_data.get("default_categories", [])
    )

# 在模組導入時建立一個全局的 BNext 配置對象
BNEXT_CONFIG = create_bnext_config()

