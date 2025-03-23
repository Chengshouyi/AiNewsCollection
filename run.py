from datetime import datetime
import os
import schedule
import time
import logging
from src.services.articles_service import ArticleService
from src.model.base_models import Base
from src.config import get_db_manager

# 配置日誌
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

def main():
    try:
        # 初始化資料庫存取
        db_manager = get_db_manager()
        data_access = ArticleService(db_manager)  
        
        # 創建資料庫表格
        db_manager.create_tables(Base)
        logging.info("資料庫初始化完成")
        
        if __debug__:
            # 測試資料庫存取
            test_data_access(data_access)

        # 可以在這裡添加其他初始化或定期任務
        logging.info("主程序啟動成功")

    except Exception as e:
        logging.error(f"初始化失敗: {e}", exc_info=True)

def run_scheduled_tasks():
    """定義並運行定期任務"""
    # 範例：每天執行的任務
    schedule.every().day.at("00:00").do(main)

    while True:
        schedule.run_pending()
        time.sleep(1)

def test_data_access(data_access):
    # 測試插入文章
    article_data = {
        "title": "測試文章",
        "link": "https://test.com/article",
        "content": "這是一篇測試文章",
        "published_at": datetime.now(),
        "source": "測試來源"
    }
    data_access.insert_article(article_data)
    logging.info("文章插入完成")

    # 測試抓取所有文章
    

if __name__ == "__main__":
    logging.info("開始執行")
    try:
        main()
        # 如果需要長期運行，可以取消下面這行的註釋
        # run_scheduled_tasks()
    except Exception as e:
        logging.error(f"程序異常退出: {e}", exc_info=True)