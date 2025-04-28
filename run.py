"""應用程式主執行腳本 (非 Web 伺服器模式)。

此腳本負責初始化應用程式所需的服務、資料庫連線、
預設資料（如爬蟲），並啟動背景排程任務。
主要用於命令行執行或非 Web 環境下的應用啟動。
"""
# 標準函式庫
import os
import sys
import time

# 第三方函式庫
from dotenv import load_dotenv

# 本地應用程式 imports
from src.config import get_db_manager
from src.services.service_container import (
    ServiceContainer,
    get_crawlers_service,
    get_scheduler_service,
)
from src.utils.log_utils import LoggerSetup

logger = LoggerSetup.setup_logger(__name__)

load_dotenv()


def initialize_default_crawler():
    """初始化默認的爬蟲數據，如果不存在則創建"""
    try:
        crawlers_service = get_crawlers_service()

        default_crawler = {
            "crawler_name": "BnextCrawler",
            "module_name": "bnext",
            "base_url": "https://www.bnext.com.tw",
            "is_active": True,
            "crawler_type": "web",
            "config_file_name": "bnext_crawler_config.json",
        }

        existing_crawler_result = crawlers_service.get_crawler_by_exact_name(
            default_crawler["crawler_name"]
        )

        if (
            not existing_crawler_result["success"]
            or existing_crawler_result["crawler"] is None
        ):
            result = crawlers_service.create_crawler(default_crawler)
            if result["success"]:
                logger.info(
                    "已成功初始化默認爬蟲: %s", default_crawler['crawler_name']
                )
            else:
                logger.error("初始化默認爬蟲失敗: %s", result['message'])
        else:
            logger.info(
                "默認爬蟲 %s 已存在，無需創建", default_crawler['crawler_name']
            )

    except Exception as e:
        logger.error("初始化默認爬蟲時發生錯誤: %s", e, exc_info=True)


def main():
    """執行應用程式的主要初始化邏輯"""
    try:
        # 啟動排程器
        try:
            scheduler = get_scheduler_service()
            scheduler_result = scheduler.start_scheduler()
            if scheduler_result.get("success"):
                logger.info(
                    "排程器已成功啟動: %s", scheduler_result.get('message')
                )
            else:
                logger.error(
                    "啟動排程器失敗: %s", scheduler_result.get('message')
                )
        except Exception as e:
            logger.error("啟動排程器時發生未預期錯誤: %s", e, exc_info=True)
            # 根據需求，決定是否在排程器啟動失敗時阻止應用程式啟動
            # raise e # 取消註解以停止啟動

        # 初始化默認爬蟲數據
        initialize_default_crawler()

        logger.info("主程序初始化完成")

    except Exception as e:
        logger.error("初始化失敗: %s", e, exc_info=True)
        # 在初始化失敗時嘗試清理資源
        try:
            scheduler = get_scheduler_service()
            scheduler.stop_scheduler()
        except Exception as se:
            logger.error(
                "初始化失敗後停止排程器時發生錯誤: %s", se, exc_info=True
            )
        try:
            ServiceContainer.clear_instances()
        except Exception as ce:
            logger.error(
                "初始化失敗後清理服務實例時發生錯誤: %s", ce, exc_info=True
            )

        db_manager = get_db_manager()
        if db_manager:
            try:
                db_manager.cleanup()
                logger.info("資料庫管理器資源已清理 (初始化失敗清理)")
            except Exception as dbe:
                logger.error(
                    "初始化失敗後清理資料庫管理器時發生錯誤: %s",
                    dbe,
                    exc_info=True,
                )
        # 初始化失敗通常意味著無法繼續，所以重新拋出異常
        raise Exception("初始化失敗") from e


def run_scheduled_tasks():
    """長期運行，定期執行排程任務重新載入"""
    try:
        raw_interval = os.getenv("SCHEDULE_RELOAD_INTERVAL_SEC", "1800")
        interval_sec = int(raw_interval)
        if interval_sec <= 0:
            interval_sec = 1800
            logger.warning(
                "SCHEDULE_RELOAD_INTERVAL_SEC 必須為正整數，使用預設值: %s 秒",
                interval_sec,
            )
        logger.info("排程任務重新載入間隔設定為: %s 秒", interval_sec)
    except ValueError:
        interval_sec = 1800
        logger.warning(
            "環境變數 SCHEDULE_RELOAD_INTERVAL_SEC 值 '%s' 無效，使用預設值: %s 秒",
            raw_interval,
            interval_sec,
        )

    interval_min = interval_sec / 60
    while True:
        try:
            logger.info("開始重新載入排程任務...")
            get_scheduler_service().reload_scheduler()
            logger.info("排程任務重新載入完成。")
            logger.info("下一次重新載入將在 %.1f 分鐘後進行。", interval_min)
            time.sleep(interval_sec)
        except Exception as e:
            # 目前選擇記錄錯誤並在短暫延遲後重試
            logger.error("排程任務重新載入/執行錯誤: %s", e, exc_info=True)
            logger.info("發生錯誤，將在 60 秒後重試...")
            time.sleep(60)


if __name__ == "__main__":
    logger.info("開始執行主程序 (run.py)...")
    try:
        main()
        # 主初始化完成後，持續運行排程任務重新載入
        run_scheduled_tasks()
    except Exception as e:
        # 捕捉 main() 或 run_scheduled_tasks() 初始化階段的錯誤
        logger.critical("程序因未處理的異常而終止: %s", e, exc_info=True)
        # 確保在任何頂層異常時都嘗試清理資源 (儘管可能部分已在 main 的 except 塊處理)
        try:
            scheduler = get_scheduler_service()
            if scheduler.is_running(): # 檢查排程器是否正在運行
                scheduler.stop_scheduler()
        except Exception as se:
            logger.error("頂層異常處理中停止排程器時發生錯誤: %s", se, exc_info=True)
        try:
            ServiceContainer.clear_instances()
        except Exception as ce:
             logger.error("頂層異常處理中清理服務實例時發生錯誤: %s", ce, exc_info=True)
        db_manager = get_db_manager()
        if db_manager:
            try:
                db_manager.cleanup()
            except Exception as dbe:
                 logger.error("頂層異常處理中清理資料庫管理器時發生錯誤: %s", dbe, exc_info=True)
        sys.exit(1) # 以錯誤碼退出
