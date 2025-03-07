import os
import schedule
import time
import logging
from src.model.data_access import DataAccess

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
        data_access = DataAccess()
        
        # 創建資料庫表格
        # data_access.create_tables()
        # logging.info("資料庫初始化完成")

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

if __name__ == "__main__":
    logging.info("開始執行")
    try:
        main()
        # 如果需要長期運行，可以取消下面這行的註釋
        # run_scheduled_tasks()
    except Exception as e:
        logging.error(f"程序異常退出: {e}", exc_info=True)