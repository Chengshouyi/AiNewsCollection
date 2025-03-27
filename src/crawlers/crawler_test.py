#!/usr/bin/env python
import argparse
import logging
import sys
import os

# 確保可以正確導入模組
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.crawlers.crawler_factory import CrawlerFactory
from src.crawlers.bnext_config import create_bnext_config, load_bnext_config

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

def parse_args():
    parser = argparse.ArgumentParser(description='測試 BNext 爬蟲')
    parser.add_argument('--max-pages', type=int, default=2, help='最大爬取頁數')
    parser.add_argument('--num-articles', type=int, default=5, help='要獲取詳情的文章數量')
    parser.add_argument('--ai-only', action='store_true', help='僅獲取 AI 相關文章')
    parser.add_argument('--fetch-details', action='store_true', help='是否獲取文章詳情')
    parser.add_argument('--min-keywords', type=int, default=3, help='判定為 AI 相關的最小關鍵詞數量')
    parser.add_argument('--config', type=str, help='配置文件路徑')
    parser.add_argument('--output', type=str, default='bnext_articles.csv', help='CSV 文件保存路徑')
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
    
    try:
        # 載入配置
        config = create_bnext_config()
        if args.config:
            logger.info(f"使用自定義配置文件: {args.config}")
            config_data = load_bnext_config(args.config)
            config = create_bnext_config(config_data)
        
        # 更新配置參數
        config.crawler_settings['max_pages'] = args.max_pages
        config.content_extraction['min_keywords'] = args.min_keywords
        config.content_extraction['ai_only'] = args.ai_only
        
        logger.info(f"爬蟲配置: {config.__dict__}")
        
        # 獲取爬蟲實例
        crawler = CrawlerFactory.get_crawler("bnext", config=config)
        
        # 執行爬蟲
        logger.info(f"開始爬取 BNext，最大頁數: {args.max_pages}")
        
        # 獲取文章列表
        articles_df = crawler.fetch_article_list(
            {
                "max_pages": args.max_pages,
                "ai_only": args.ai_only
            }
        )
        
        logger.info(f"獲取文章列表，共 {len(articles_df)} 篇")
        
        # 獲取文章詳情
        if args.fetch_details and not articles_df.empty:
            logger.info(f"開始獲取文章詳情，數量: {args.num_articles}")
            articles_df = crawler.fetch_article_details(
                articles_df, 
                num_articles=args.num_articles,
                ai_only=args.ai_only,
                min_keywords=args.min_keywords
            )
        
        # 保存數據
        if not articles_df.empty:
            crawler.save_data(articles_df, save_to_csv=True, csv_path=args.output)
            logger.info(f"已保存 {len(articles_df)} 篇文章到 {args.output}")
        else:
            logger.warning("沒有獲取到任何文章")
            
    except Exception as e:
        logger.error(f"爬蟲執行錯誤: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 


# 預設 INFO 級別
# python -m src.crawlers.crawler_test

# 設置 DEBUG 級別，獲取更詳細日誌
# python -m src.crawlers.crawler_test --log-level DEBUG

# 使用自定義配置文件
# python -m src.crawlers.crawler_test --config /path/to/config.json

# 只爬取 AI 相關文章
# python -m src.crawlers.crawler_test --ai-only --output ./logs/bnext_articles_ai.csv --log-level DEBUG