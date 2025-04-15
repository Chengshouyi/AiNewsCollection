from datetime import datetime
import os
import schedule
import time
import logging
from src.services.article_service import ArticleService
from src.services.scheduler_service import SchedulerService
from src.services.task_executor_service import TaskExecutorService
from src.models.base_model import Base
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

        # 初始化排程服務（使用單體模式）
        scheduler_service = SchedulerService.get_instance(db_manager=db_manager)
        
        # 初始化任務執行服務（使用單體模式）
        task_executor_service = TaskExecutorService.get_instance(db_manager=db_manager, max_workers=15)
        
        # 啟動排程服務
        scheduler_service.start_scheduler()
        
        # 創建資料庫表格
        db_manager.create_tables(Base)
        logging.info("資料庫初始化完成")
        
        if __debug__:
            # 測試資料庫存取
            pass
            # test_data_access(data_access)
        
        # 可以在這裡添加其他初始化或定期任務
        logging.info("主程序啟動成功")
        
        scheduler_service.stop_scheduler()
    except Exception as e:
        logging.error(f"初始化失敗: {e}", exc_info=True)

def run_scheduled_tasks(interval_hr: int = 24):
    """長期運行，定期執行排程任務"""
    while True:
        try:
            # 執行排程任務          
            SchedulerService.get_instance().reload_scheduler()
            time.sleep(interval_hr * 3600)
        except Exception as e:
            logging.error(f"排程任務執行錯誤: {e}", exc_info=True)
            time.sleep(10)



if __name__ == "__main__":
    logging.info("開始執行")
    try:
        main()
        run_scheduled_tasks(4) # 每4小時執行一次排程任務重新載入
    except Exception as e:
        logging.error(f"程序異常退出: {e}", exc_info=True)