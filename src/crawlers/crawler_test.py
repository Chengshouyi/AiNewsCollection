#!/usr/bin/env python
import argparse
import logging
import sys
import os
from datetime import datetime, timezone
import pandas as pd
# 確保可以正確導入模組
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.crawlers.crawler_factory import CrawlerFactory
from src.database.database_manager import DatabaseManager
from src.models.crawlers_model import Crawlers
from src.models.base_model import Base

# 設置更詳細的日誌
def setup_logging(log_level=logging.INFO):
    """
    設置日誌配置，支持輸出到控制台和文件
    
    Args:
        log_level (int): 日誌級別，默認為 INFO
    """
    # 創建根日誌記錄器
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            # 輸出到控制台
            logging.StreamHandler(sys.stdout),
            # 可選：輸出到文件
            logging.FileHandler('crawler_test.log', encoding='utf-8', mode='w')
        ]
    )

    # 設置第三方庫的日誌級別
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('selenium').setLevel(logging.WARNING)

def init_test_database(db_manager: DatabaseManager):
    """
    初始化測試資料庫，創建必要的表格和測試資料
    
    Args:
        db_manager: 資料庫管理器實例
    """
    # 創建所有表格
    Base.metadata.create_all(db_manager.engine)
    
    # 創建測試用的爬蟲資料
    test_crawlers = [
        {
            'crawler_name': 'BnextCrawler',
            'base_url': 'https://www.bnext.com.tw',
            'is_active': True,
            'crawler_type': 'bnext',
            'config_file_name': 'bnext_crawler_config.json',
            'created_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc)
        }
    ]
    
    # 使用 session 添加測試資料
    session = db_manager.Session()
    try:
        for crawler_data in test_crawlers:
            crawler = Crawlers(**crawler_data)
            session.add(crawler)
        session.commit()
        logging.info("成功初始化測試資料庫")
    except Exception as e:
        session.rollback()
        logging.error(f"初始化測試資料庫失敗: {str(e)}")
        raise
    finally:
        session.close()

def parse_args():
    parser = argparse.ArgumentParser(description='測試爬蟲')
    parser.add_argument('--crawler', type=str, default='BnextCrawler', help='要測試的爬蟲名稱')
    parser.add_argument('--max-pages', type=int, default=2, help='最大爬取頁數')
    parser.add_argument('--num-articles', type=int, default=5, help='要獲取詳情的文章數量')
    parser.add_argument('--ai-only', action='store_true', help='僅獲取 AI 相關文章')
    parser.add_argument('--fetch-details', action='store_true', help='是否獲取文章詳情')
    parser.add_argument('--min-keywords', type=int, default=3, help='判定為 AI 相關的最小關鍵詞數量')
    parser.add_argument('--output', type=str, default='articles.csv', help='CSV 文件保存路徑')
    parser.add_argument('--log-level', type=str, default='INFO', 
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], 
                        help='設置日誌級別')
    
    return parser.parse_args()

def main():
    # 解析命令行參數
    args = parse_args()
    
    # 根據參數設置日誌級別
    log_level = getattr(logging, args.log_level.upper())
    setup_logging(log_level)
    
    # 創建日誌記錄器
    logger = logging.getLogger(__name__)
    
    db_manager = None
    try:
        # 初始化記憶體資料庫
        db_manager = DatabaseManager('sqlite:///:memory:')
        
        # 初始化測試資料
        init_test_database(db_manager)
        
        # 初始化爬蟲工廠
        CrawlerFactory.initialize(db_manager)
        
        # 獲取爬蟲實例
        crawler = CrawlerFactory.get_crawler(args.crawler)
        crawler.execute_task(1, {})
        
        # logger.debug(f"CrawlerTest - call CrawlerFactory.get_crawler(args.crawler)： 獲取爬蟲實例完成")
        # # 執行爬蟲
        # logger.debug(f"CrawlerTest - call main： 開始爬取 {args.crawler}，最大頁數: {args.max_pages}")
        
        # # 獲取文章連結
        # logger.debug(f"CrawlerTest - call crawler.fetch_article_list()： 獲取文章連結中...")
        # article_links_df = crawler.fetch_article_list()
        
        # logger.debug(f"CrawlerTest - call crawler.fetch_article_list()： 獲取文章連結完成")
        # logger.debug(f"獲取文章連結，共 {len(article_links_df)} 篇")
        # # 保存數據
        # if not article_links_df.empty:
        #     logger.debug(f"CrawlerTest - call crawler.save_data()： 開始保存文章連結到 {'./logs/article_links_ai.csv'}")
        #     crawler._save_to_csv(article_links_df, csv_path='./logs/article_links_ai.csv')
        #     logger.debug(f"CrawlerTest - call crawler.save_data()： 已保存 {len(article_links_df)} 篇文章到 {args.output}")
        # else:
        #     logger.warning("沒有獲取到任何文章")
        
        # # 從 CSV 讀取數據並轉換為 DataFrame(測試用)
        # try:
        #     # 假設 CSV 文件路徑儲存在變數中或作為參數傳入
        #     csv_file_path = './logs/article_links_ai.csv'  # 或者直接指定路徑，例如 'data/articles.csv'
            
        #     # 檢查文件是否存在
        #     if not os.path.exists(csv_file_path):
        #         logger.error(f"CSV 文件不存在: {csv_file_path}")
        #         articles_df = pd.DataFrame()  # 創建空的 DataFrame
        #     else:
        #         logger.debug(f"開始從 CSV 文件讀取數據: {csv_file_path}")
        #         # 讀取 CSV 文件
        #         articles_df = pd.read_csv(csv_file_path, encoding='utf-8')
        #         logger.debug(f"成功讀取 CSV 文件，共 {len(articles_df)} 條記錄")
                
        #         # 顯示 DataFrame 的基本信息
        #         logger.debug(f"DataFrame 信息:\n{articles_df.info()}")
        #         logger.debug(f"DataFrame 前 5 行:\n{articles_df.head()}")
                
        # except Exception as e:
        #     logger.error(f"讀取 CSV 文件時發生錯誤: {str(e)}")
        #     articles_df = pd.DataFrame()  # 創建空的 DataFrame 作為後備
            
        # 獲取文章內容
        # if args.fetch_details and not article_links_df.empty:
        #     logger.debug(f"CrawlerTest - call crawler.fetch_article_details()： 開始獲取文章內容，數量: {args.num_articles}")
        #     articles_df = crawler.fetch_article_details(article_links_df)
        #     logger.debug(f"CrawlerTest - call crawler.fetch_article_details()： 獲取文章內容完成")

        # # 保存文章內容
        # if not articles_df.empty:
        #     logger.debug(f"CrawlerTest - call crawler.save_data()： 開始保存文章內容到 {'./logs/articles_ai.csv'}")
        #     crawler._save_to_csv(articles_df, csv_path='./logs/articles_ai.csv')
        #     logger.debug(f"CrawlerTest - call crawler.save_data()： 已保存 {len(articles_df)} 篇文章到 {args.output}")
        # else:
        #     logger.warning("沒有獲取到任何文章")
            
    except Exception as e:
        logger.error(f"爬蟲執行錯誤: {str(e)}", exc_info=True)
    finally:
        if db_manager:
            db_manager.engine.dispose()

if __name__ == "__main__":
    main() 

# 使用範例：
# 預設 INFO 級別
# python -m src.crawlers.crawler_test

# 設置 DEBUG 級別，獲取更詳細日誌
# python -m src.crawlers.crawler_test --log-level DEBUG

# 指定爬蟲
# python -m src.crawlers.crawler_test --crawler BnextCrawler

# 只爬取AI 相關文章連結
# python -m src.crawlers.crawler_test --crawler BnextCrawler --ai-only --output ./logs/articles_ai.csv --log-level DEBUG


# 爬取文章連結和文章內容
# python -m src.crawlers.crawler_test --crawler BnextCrawler  --ai-only  --fetch-details --output ./logs/articles_ai.csv --log-level DEBUG


