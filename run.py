import os
import time
import logging
from src.services.article_service import ArticleService
from src.services.scheduler_service import SchedulerService
from src.models.base_model import Base
from src.config import get_db_manager
from src.services.service_container import ServiceContainer, get_scheduler_service, get_task_executor_service, get_crawler_task_service, get_article_service, get_crawlers_service
from datetime import datetime, timezone

# 配置日誌
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

def initialize_default_crawler():
    """初始化默認的爬蟲數據，如果不存在則創建"""
    try:
        # 獲取爬蟲服務
        crawlers_service = get_crawlers_service()
        
        # 定義默認爬蟲數據
        default_crawler = {
            'crawler_name': 'BnextCrawler',
            'base_url': 'https://www.bnext.com.tw',
            'is_active': True,
            'crawler_type': 'web',
            'config_file_name': 'bnext_crawler_config.json',
        }
        
        # 檢查爬蟲是否已存在
        existing_crawler_result = crawlers_service.get_crawler_by_exact_name(default_crawler['crawler_name'])
        
        # 如果不存在，創建新爬蟲
        if not existing_crawler_result['success'] or existing_crawler_result['crawler'] is None:
            result = crawlers_service.create_crawler(default_crawler)
            if result['success']:
                logging.info(f"已成功初始化默認爬蟲: {default_crawler['crawler_name']}")
            else:
                logging.error(f"初始化默認爬蟲失敗: {result['message']}")
        else:
            logging.info(f"默認爬蟲 {default_crawler['crawler_name']} 已存在，無需創建")
    
    except Exception as e:
        logging.error(f"初始化默認爬蟲時發生錯誤: {e}", exc_info=True)

def main():
    try:
        # 初始化資料庫存取
        db_manager = get_db_manager()

        # 初始化排程服務（使用單體模式）
        scheduler_service = get_scheduler_service()
        
        # 初始化任務執行服務（使用單體模式）
        task_executor_service = get_task_executor_service()

        # 初始化爬蟲任務服務（使用單體模式）
        crawler_task_service = get_crawler_task_service()

        # 初始化文章服務（使用單體模式）
        article_service = get_article_service()
        
        # 啟動排程服務
        scheduler_service.start_scheduler()
        
        # 創建資料庫表格
        db_manager.create_tables(Base)
        logging.info("資料庫初始化完成")
        
        # 初始化默認爬蟲數據
        initialize_default_crawler()
        
        if __debug__:
            # 測試資料庫存取
            pass
            # test_data_access(data_access)
        
        # 可以在這裡添加其他初始化或定期任務
        logging.info("主程序啟動成功")
        
        
    except Exception as e:
        # 在初始化失敗時嘗試清理
        logging.error(f"初始化失敗: {e}", exc_info=True)
        try:
            scheduler_service.stop_scheduler()
        except Exception as se:
            logging.error(f"初始化失敗後停止排程器時發生錯誤: {se}", exc_info=True)
        try:
            ServiceContainer.clear_instances()
        except Exception as ce:
            logging.error(f"初始化失敗後清理服務實例時發生錯誤: {ce}", exc_info=True)
        try:
            db_manager.cleanup()
        except Exception as de:
            logging.error(f"初始化失敗後清理資料庫管理器時發生錯誤: {de}", exc_info=True)
        # 初始化失敗通常意味著無法繼續，所以直接拋出
        raise e

def run_scheduled_tasks():
    """長期運行，定期執行排程任務重新載入"""
    # 從環境變數讀取間隔，若無則使用預設值 4 小時
    try:
        interval_hr = int(os.getenv('SCHEDULE_RELOAD_INTERVAL_HR', '4'))
        if interval_hr <= 0:
            interval_hr = 4 # 防止無效值
        logging.info(f"排程任務重新載入間隔設定為: {interval_hr} 小時")
    except ValueError:
        interval_hr = 4
        logging.warning(f"環境變數 SCHEDULE_RELOAD_INTERVAL_HR 設定無效，使用預設值: {interval_hr} 小時")

    interval_sec = interval_hr * 3600

    while True:
        try:
            # 執行排程任務重新載入
            logging.info("開始重新載入排程任務...")
            get_scheduler_service().reload_scheduler()
            logging.info("排程任務重新載入完成。")
            logging.info(f"下一次重新載入將在 {interval_hr} 小時後進行。")
            time.sleep(interval_sec)
        except Exception as e:
            # 考慮是否在每次失敗後都停止排程器，或者只是記錄錯誤並繼續嘗試
            # get_scheduler_service().stop_scheduler() # 暫時註解，取決於錯誤處理策略
            logging.error(f"排程任務重新載入/執行錯誤: {e}", exc_info=True)
            # 在出現錯誤後，短暫休眠避免快速連續失敗
            logging.info("發生錯誤，將在 60 秒後重試...")
            time.sleep(60)



if __name__ == "__main__":
    logging.info("開始執行主程序...")
    try:
        main()
        # 不再傳遞 interval_hr，函數內部會自行讀取
        run_scheduled_tasks()
    except Exception as e:
        logging.error(f"程序異常退出: {e}", exc_info=True)
        # 確保在任何頂層異常時都嘗試清理資源
        try:
            get_scheduler_service().stop_scheduler()
        except Exception as se:
            logging.error(f"停止排程器時發生錯誤: {se}", exc_info=True)
        try:
            ServiceContainer.clear_instances()
        except Exception as ce:
            logging.error(f"清理服務實例時發生錯誤: {ce}", exc_info=True)
        try:
            get_db_manager().cleanup()
        except Exception as de:
            logging.error(f"清理資料庫管理器時發生錯誤: {de}", exc_info=True)
        # 重新引發原始異常，以便外部監控（如 systemd/supervisor）知道程序失敗
        raise e