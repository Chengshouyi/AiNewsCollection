"""Flask 應用程式主入口點。

初始化 Flask 應用、SocketIO、註冊藍圖、設定事件處理程序，
並管理應用程式生命週期，包括初始化服務和排程任務。
"""
# 標準函式庫
import os
import sys
import threading
import time

# 第三方函式庫
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_socketio import join_room, leave_room

# 本地應用程式 imports
from src.config import get_db_manager
from src.services.service_container import (
    ServiceContainer,
    get_crawlers_service,
    get_scheduler_service,
)
from src.utils.log_utils import LoggerSetup
from src.web.routes.article_api import article_bp
from src.web.routes.crawler_api import crawler_bp
from src.web.routes.tasks_api import tasks_bp
from src.web.routes.views import view_bp
from src.web.socket_instance import init_app, socketio

logger = LoggerSetup.setup_logger(__name__)


load_dotenv()


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "a_default_secret_key_for_dev_if_needed"
)

init_app(app)

app.register_blueprint(crawler_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(article_bp)
app.register_blueprint(view_bp)


@socketio.on("connect", namespace="/tasks")
def handle_tasks_connect():
    logger.info("Client connected to /tasks namespace")


@socketio.on("disconnect", namespace="/tasks")
def handle_tasks_disconnect():
    logger.info("Client disconnected from /tasks namespace")


@socketio.on("join_room", namespace="/tasks")
def handle_join_room(data):
    """處理客戶端加入房間的請求"""
    room = data.get("room")
    if room:
        join_room(room)
        logger.info("Client joined room: %s", room)
    else:
        logger.warning("Join room request received without room specified.")


@socketio.on("leave_room", namespace="/tasks")
def handle_leave_room(data):
    """處理客戶端離開房間的請求"""
    room = data.get("room")
    if room:
        leave_room(room)
        logger.info("Client left room: %s", room)
    else:
        logger.warning("Leave room request received without room specified.")


@app.route("/debug/routes")
def list_routes():
    """列出所有已註冊的 Flask 路由，用於調試"""
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append(
            {
                "endpoint": rule.endpoint,
                "methods": list(rule.methods or set()),
                "route": str(rule),
            }
        )
    return jsonify(routes)


@app.teardown_appcontext
def shutdown_session(exception=None):
    """在應用程式上下文銷毀時清理資料庫資源"""
    db_manager = get_db_manager()
    if db_manager:
        try:
            db_manager.cleanup()
            logger.info("資料庫管理器資源已清理 (teardown_appcontext)")
        except Exception as e:
            logger.error(
                "清理資料庫管理器時發生錯誤 (teardown_appcontext): %s", e, exc_info=True
            )


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
            # 如果需要在排程器啟動失敗時阻止應用程式啟動，可以取消註解下一行
            # raise e

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
        raise


def run_scheduled_tasks():
    """定期重新載入排程任務的背景執行緒"""
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
            logger.error("排程任務重新載入/執行錯誤: %s", e, exc_info=True)
            # 考慮是否在每次失敗後都停止排程器，目前選擇記錄錯誤並在短暫延遲後重試
            logger.info("發生錯誤，將在 60 秒後重試...")
            time.sleep(60)


if __name__ == "__main__":
    logger.info("開始執行主程序...")
    try:
        main()

        # 啟動背景執行緒來定期重新載入排程
        scheduler_thread = threading.Thread(target=run_scheduled_tasks, daemon=True)
        scheduler_thread.start()
        logger.info("已啟動背景排程重新載入執行緒")

        # 啟動 Flask 開發伺服器 (由 SocketIO 包裝)
        socketio.run(
            app,
            debug=True,
            host="0.0.0.0", # 允許外部連接
            port=5000,
            use_reloader=False, # 避免與背景執行緒衝突
            allow_unsafe_werkzeug=True, # 在某些情況下 debug 模式需要
        )

    except Exception as e:
        logger.critical("主程式執行期間發生無法處理的錯誤: %s", e, exc_info=True)
        # 在嚴重錯誤時，可以考慮執行更徹底的清理或退出
        sys.exit(1)
