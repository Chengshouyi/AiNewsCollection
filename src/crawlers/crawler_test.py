#!/usr/bin/env python
import argparse
import logging
import sys
import os
from datetime import datetime, timezone
import pandas as pd
import sqlalchemy
# 確保可以正確導入模組
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.crawlers.crawler_factory import CrawlerFactory
from src.database.database_manager import DatabaseManager
from src.models.crawlers_model import Crawlers
from src.models.crawler_tasks_model import CrawlerTasks
from src.models.base_model import Base
from src.services.crawlers_service import CrawlersService
from src.database.crawlers_repository import CrawlersRepository
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.services.article_service import ArticleService
from src.utils.log_utils import LoggerSetup

logger = logging.getLogger(__name__)

# 設置更詳細的日誌
def setup_logging(log_level=logging.INFO):
    """
    設置日誌配置，支持輸出到控制台和文件
    
    Args:
        log_level (int): 日誌級別，默認為 INFO
    """
    custom_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    return LoggerSetup.setup_logger(
        module_name='crawler_test',
        log_dir='logs',  # 這會在專案根目錄下創建 logs 目錄
        log_format=custom_format,
        level=log_level,
        date_format='%Y-%m-%d %H:%M:%S' # 設置日期格式  
    )
    # 創建根日誌記錄器
    # logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    # return logger

def init_test_database(db_manager: DatabaseManager):
    """
    初始化測試資料庫，創建必要的表格和測試資料
    
    Args:
        db_manager: 資料庫管理器實例
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            Base.metadata.drop_all(db_manager.engine)
            Base.metadata.create_all(db_manager.engine)  # 確保表格被重新創建
            break
        except sqlalchemy.exc.DatabaseError as e:
            if attempt == max_retries - 1:
                raise
            logger.warning(f"第 {attempt + 1} 次嘗試重建資料庫")
            if os.path.exists(db_manager.database_path):
                os.remove(db_manager.database_path)
            db_manager.engine = db_manager.create_engine()
    
    # 創建測試用的爬蟲資料
    test_crawler = {
        'crawler_name': 'BnextCrawler',
        'base_url': 'https://www.bnext.com.tw',
        'is_active': True,
        'crawler_type': 'bnext',
        'config_file_name': 'bnext_crawler_config.json',
        'created_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc)
    }
    
    # 使用 session_scope 管理 session
    with db_manager.session_scope() as session:
        try:
            crawlers_repo = CrawlersRepository(session, Crawlers)
            crawler = crawlers_repo.create(test_crawler)
            if crawler:
                logger.info(f"成功創建測試爬蟲: {crawler.crawler_name}")
                
                # 創建測試任務
                test_task = {
                    'task_name': '測試任務',
                    'crawler_id': crawler.id,
                    'is_auto': False,
                    'ai_only': True,
                    'max_pages': 2,
                    'num_articles': 5,
                    'min_keywords': 3,
                    'fetch_details': True,
                    'created_at': datetime.now(timezone.utc),
                    'updated_at': datetime.now(timezone.utc)
                }
                
                tasks_repo = CrawlerTasksRepository(session, CrawlerTasks)
                task = tasks_repo.create(test_task)
                if task:
                    logger.info(f"成功創建測試任務: {task.task_name}")
                else:
                    logger.error("創建測試任務失敗")
            else:
                logger.error("創建測試爬蟲失敗")
            
            # 確保資料被提交到資料庫
            session.commit()
            logger.info("資料已成功提交到資料庫")
            
        except Exception as e:
            session.rollback()
            logger.error(f"初始化測試資料庫失敗: {str(e)}")
            raise

def parse_args():
    parser = argparse.ArgumentParser(description='測試爬蟲')
    parser.add_argument('--crawler', type=str, default='BnextCrawler', help='要測試的爬蟲名稱')
    parser.add_argument('--max-pages', type=int, default=2, help='最大爬取頁數')
    parser.add_argument('--num-articles', type=int, default=5, help='要獲取詳情的文章數量')
    parser.add_argument('--ai-only', action='store_true', help='僅獲取 AI 相關文章')
    parser.add_argument('--from-db-link', action='store_true', help='從資料庫連結獲取文章')
    parser.add_argument('--min-keywords', type=int, default=3, help='判定為 AI 相關的最小關鍵詞數量')
    parser.add_argument('--csv-output', type=str, default='articles_test.csv', help='CSV 文件保存路徑')
    parser.add_argument('--save-to-database', action='store_true', help='是否保存到資料庫')
    parser.add_argument('--log-level', type=str, default='INFO', 
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], 
                        help='設置日誌級別')
    
    return parser.parse_args()

def main():
    args = parse_args()
    log_level = getattr(logging, args.log_level.upper())
    setup_logging(log_level)  # 只需要設置一次
    
    db_manager = None
    try:
        # 初始化資料庫
        db_manager = DatabaseManager('sqlite:///test.db')
        
        # 初始化測試資料
        init_test_database(db_manager)
        
        # 驗證資料是否正確寫入
        session = db_manager.Session()
        try:
            crawlers_repo = CrawlersRepository(session, Crawlers)
            active_crawlers = crawlers_repo.get_all()
            logger.info(f"資料庫中的爬蟲數量: {len(active_crawlers)}")
            for crawler in active_crawlers:
                logger.info(f"爬蟲資訊: {crawler.crawler_name}, 是否啟用: {crawler.is_active}")
        finally:
            session.close()
        
        # 初始化爬蟲工廠
        crawlers_service = CrawlersService(db_manager)
        article_service = ArticleService(db_manager)
        CrawlerFactory.initialize(crawlers_service, article_service)
        
        # 獲取爬蟲實例
        crawler = CrawlerFactory.get_crawler(args.crawler)
        
        # 執行爬蟲任務
        task_params = {
            'max_pages': args.max_pages,
            'ai_only': args.ai_only,
            'from_db_link': False,
            'num_articles': args.num_articles,
            'min_keywords': args.min_keywords,
            'save_to_database': args.save_to_database,
            'save_to_csv': True if args.csv_output else False,
            'csv_file_name': args.csv_output
        }
        
        crawler.execute_task(1, task_params)

                # 執行爬蟲任務
        task_params = {
            'max_pages': args.max_pages,
            'ai_only': args.ai_only,
            'from_db_link': True,
            'num_articles': 0,
            'min_keywords': args.min_keywords,
            'save_to_database': args.save_to_database,
            'save_to_csv': False,
            'csv_file_name': None
        }

        crawler.execute_task(1, task_params)
        
    except Exception as e:
        logger.error(f"爬蟲執行錯誤: {str(e)}", exc_info=True)
    finally:
        if db_manager:
            db_manager.engine.dispose()

if __name__ == "__main__":
    main() 

# 使用範例：
# 基本測試
# python -m src.crawlers.crawler_test

# # 詳細日誌
# python -m src.crawlers.crawler_test --log-level DEBUG

# # 只爬取 AI 相關文章
# python -m src.crawlers.crawler_test --ai-only


## 詳細設定
# python -m src.crawlers.crawler_test --crawler BnextCrawler --max-pages 3 --num-articles 10 --ai-only --min-keywords 5 --csv-output articles_ai.csv --save-to-database --log-level DEBUG


