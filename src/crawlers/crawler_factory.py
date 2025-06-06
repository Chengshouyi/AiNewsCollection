"""提供爬蟲工廠，用於初始化和管理不同類型的爬蟲實例。"""

from typing import Dict, Optional, Any
import logging
from src.services.article_service import ArticleService
from src.services.crawlers_service import CrawlersService

# from src.database.database_manager import DatabaseManager # 移除未使用的 import
  # 使用統一的 logger

logger = logging.getLogger(__name__)  # 使用統一的 logger  # 使用統一的 logger


class CrawlerFactory:
    _crawler_names: Dict[str, Dict[str, Any]] = {}
    # _db_manager: Optional[DatabaseManager] = None # 移除未使用的屬性
    _crawlers_service: Optional[CrawlersService] = None
    _article_service: Optional[ArticleService] = None

    @classmethod
    def initialize(
        cls, crawlers_service: CrawlersService, article_service: ArticleService
    ):
        """
        初始化爬蟲工廠，從資料庫讀取爬蟲設定並註冊

        Args:
            crawlers_service: 爬蟲服務實例
            article_service: 文章服務實例
        """
        cls._crawlers_service = crawlers_service
        cls._article_service = article_service
        if cls._article_service is None or cls._crawlers_service is None:
            raise ValueError("未提供文章服務或爬蟲服務")
        try:
            # 取得所有活動中的爬蟲
            active_crawlers = cls._crawlers_service.find_active_crawlers()
            if active_crawlers["success"]:
                # 註冊每個爬蟲
                for crawler in active_crawlers["crawlers"]:
                    try:
                        # 動態導入爬蟲類別
                        # 假設 module_name 在 crawler 物件中定義
                        module_name = (
                            f"src.crawlers.{crawler.module_name.lower()}_crawler"
                        )
                        class_name = crawler.crawler_name

                        # 動態導入模組和類別
                        module = __import__(module_name, fromlist=[class_name])
                        crawler_class = getattr(module, class_name)

                        # 註冊爬蟲
                        cls._crawler_names[crawler.crawler_name] = {
                            "class": crawler_class,
                            "config_file_name": crawler.config_file_name,
                        }

                        logger.debug("成功註冊爬蟲: %s", crawler.crawler_name)
                    except Exception as e:
                        logger.error("註冊爬蟲失敗 %s: %s", crawler.crawler_name, e)
                        continue
            else:
                error_message = active_crawlers["message"]
                logger.error("獲取活動中的爬蟲設定失敗: %s", error_message)
                raise RuntimeError(f"獲取活動中的爬蟲設定失敗: {error_message}")

        except Exception as e:
            logger.error("初始化爬蟲工廠失敗: %s", e)
            raise

    @classmethod
    def get_crawler(cls, name: str) -> Any:
        """
        獲取特定爬蟲實例

        Args:
            name (str): 爬蟲名稱

        Returns:
            爬蟲實例
        """
        if not cls._crawlers_service:
            raise RuntimeError("爬蟲工廠尚未初始化，請先調用 initialize 方法")

        crawler_info = cls._crawler_names.get(name)
        if not crawler_info:
            available = ", ".join(cls._crawler_names.keys())
            raise ValueError(f"未找到 {name} 爬蟲。可用爬蟲: {available}")

        try:
            # 取得爬蟲類別
            crawler_class = crawler_info["class"]
            config_file_name = crawler_info["config_file_name"]

            # 創建爬蟲實例，傳入 article_service
            return crawler_class(
                config_file_name=config_file_name, article_service=cls._article_service
            )

        except Exception as e:
            logger.error("創建爬蟲實例失敗: %s", e)
            raise

    @classmethod
    def list_available_crawler_types(cls):
        """列出所有可用的爬蟲類型"""
        return list(cls._crawler_names.keys())
