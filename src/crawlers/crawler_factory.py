from typing import Dict, Type, Optional, Any
from src.crawlers.configs.site_config import SiteConfig
from src.database.database_manager import DatabaseManager
from src.database.crawlers_repository import CrawlersRepository
from src.models.crawlers_model import Crawlers
import logging

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CrawlerFactory:
    _crawler_types: Dict[str, Dict[str, Any]] = {}
    _db_manager: Optional[DatabaseManager] = None
    
    @classmethod
    def initialize(cls, db_manager: DatabaseManager):
        """
        初始化爬蟲工廠，從資料庫讀取爬蟲設定並註冊
        
        Args:
            db_manager: 資料庫管理器實例
        """
        cls._db_manager = db_manager
        try:
            # 取得爬蟲儲存庫
            session = db_manager.Session()
            crawlers_repo = CrawlersRepository(session, Crawlers)
            
            # 取得所有活動中的爬蟲
            active_crawlers = crawlers_repo.find_active_crawlers()
            
            # 註冊每個爬蟲
            for crawler in active_crawlers:
                try:
                    # 動態導入爬蟲類別
                    module_name = f"src.crawlers.{crawler.crawler_type.lower()}_crawler"
                    class_name = crawler.crawler_name
                    
                    # 動態導入模組和類別
                    module = __import__(module_name, fromlist=[class_name])
                    crawler_class = getattr(module, class_name)
                    
                    # 註冊爬蟲
                    cls._crawler_types[crawler.crawler_name] = {
                        'class': crawler_class,
                        'config_file_name': crawler.config_file_name
                    }
                    
                    logger.info(f"成功註冊爬蟲: {crawler.crawler_name}")
                except Exception as e:
                    logger.error(f"註冊爬蟲失敗 {crawler.crawler_name}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"初始化爬蟲工廠失敗: {str(e)}")
            raise
        finally:
            if 'session' in locals():
                session.close()

    @classmethod
    def get_crawler(cls, name: str) -> Any:
        """
        獲取特定爬蟲實例
        
        Args:
            name (str): 爬蟲名稱
            
        Returns:
            爬蟲實例
        """
        if not cls._db_manager:
            raise RuntimeError("爬蟲工廠尚未初始化，請先調用 initialize 方法")
            
        crawler_info = cls._crawler_types.get(name)
        if not crawler_info:
            available = ", ".join(cls._crawler_types.keys())
            raise ValueError(f"未找到 {name} 爬蟲。可用爬蟲: {available}")
        
        try:
            # 取得爬蟲類別
            crawler_class = crawler_info['class']
            config_file_name = crawler_info['config_file_name']
            
            # 創建爬蟲實例，傳入 db_manager
            return crawler_class(db_manager=cls._db_manager, config_file_name=config_file_name)
            
        except Exception as e:
            logger.error(f"創建爬蟲實例失敗: {str(e)}")
            raise
    
    @classmethod
    def list_available_crawlers(cls):
        """列出所有可用的爬蟲類型"""
        return list(cls._crawler_types.keys()) 