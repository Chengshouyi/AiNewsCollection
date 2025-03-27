from typing import Dict, Type, Optional, Any
from .site_config import SiteConfig
import logging

logger = logging.getLogger(__name__)

class CrawlerFactory:
    _crawler_types: Dict[str, Dict[str, Any]] = {}
    
    @classmethod
    def register_crawler_type(
        cls, 
        name: str, 
        crawler_class: Type, 
        default_config: Optional[SiteConfig] = None
    ):
        """
        動態註冊爬蟲類型
        
        Args:
            name (str): 爬蟲名稱
            crawler_class (Type): 爬蟲類
            default_config (Optional[SiteConfig]): 預設配置
        """
        if name in cls._crawler_types:
            logger.warning(f"覆蓋已存在的爬蟲類型: {name}")
            
        cls._crawler_types[name] = {
            'class': crawler_class,
            'config': default_config
        }
        logger.info(f"註冊爬蟲類型: {name}")

    @classmethod
    def get_crawler(
        cls, 
        name: str, 
        config: Optional[SiteConfig] = None,
        **kwargs
    ):
        """
        獲取特定爬蟲實例
        
        Args:
            name (str): 爬蟲名稱
            config (Optional[SiteConfig]): 自定義配置
            **kwargs: 其他參數傳遞給爬蟲初始化
        
        Returns:
            爬蟲實例
        """
        crawler_info = cls._crawler_types.get(name)
        if not crawler_info:
            available = ", ".join(cls._crawler_types.keys())
            raise ValueError(f"未找到 {name} 爬蟲。可用爬蟲: {available}")
        
        crawler_class = crawler_info['class']
        default_config = crawler_info.get('config')
        
        # 優先使用傳入配置，其次使用預設配置
        final_config = config or default_config
        
        # 檢查配置有效性
        if final_config and hasattr(final_config, 'validate'):
            if not final_config.validate():
                logger.warning(f"爬蟲配置驗證失敗: {name}")
        
        # 創建爬蟲實例
        try:
            if final_config:
                return crawler_class(config=final_config, **kwargs)
            else:
                return crawler_class(**kwargs)
        except Exception as e:
            logger.error(f"創建爬蟲實例失敗: {str(e)}")
            raise
    
    @classmethod
    def list_available_crawlers(cls):
        """列出所有可用的爬蟲類型"""
        return list(cls._crawler_types.keys()) 