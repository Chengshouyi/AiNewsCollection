"""Flask 應用程式主入口點。

初始化 Flask 應用、SocketIO、註冊藍圖、設定事件處理程序，
並管理應用程式生命週期，包括初始化服務和排程任務。
"""
# 標準函式庫
import os
import sys
import threading
import time
import logging
import datetime

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

from src.web.routes.article_api import article_bp
from src.web.routes.crawler_api import crawler_bp
from src.web.routes.tasks_api import tasks_bp
from src.web.routes.views import view_bp
from src.web.socket_instance import init_app, socketio
from src.utils.log_utils import LoggerSetup

# 配置日誌系統
LoggerSetup.configure_logging(level=logging.INFO)

# 配置日誌
logger = logging.getLogger(__name__)
logger.info("Logging configured for Flask application.")

load_dotenv()


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "a_default_secret_key_for_dev_if_needed"
)

init_app(app)

# 初始化爬蟲和應用程式
initialize_default_crawler()
init_application()

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
    logger.info("開始初始化默認爬蟲...")
    try:
        crawlers_service = get_crawlers_service()
        logger.info("已獲取 crawlers_service")

        default_crawler = {
            "crawler_name": "BnextCrawler",
            "module_name": "bnext",
            "base_url": "https://www.bnext.com.tw",
            "is_active": True,
            "crawler_type": "web",
            "config_file_name": "bnext_crawler_config.json",
        }

        logger.info("正在檢查默認爬蟲是否存在...")
        existing_crawler_result = crawlers_service.get_crawler_by_exact_name(
            default_crawler["crawler_name"]
        )

        if (
            not existing_crawler_result["success"]
            or existing_crawler_result["crawler"] is None
        ):
            logger.info("默認爬蟲不存在，開始創建...")
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


def init_application():
    """應用程式初始化，適用於所有環境（開發和生產）"""
    logger.info("開始初始化應用程式...")
    try:
        # 清理日誌
        cleanup_logger = logging.getLogger("log_cleanup_task")
        try:
            logger.info("執行日誌清理...")
            LoggerSetup.cleanup_logs(logger=cleanup_logger)
        except Exception as e:
            cleanup_logger.error(f"日誌清理任務失敗: {e}", exc_info=True)

        # 啟動排程器
        try:
            scheduler = get_scheduler_service()
            scheduler_result = scheduler.start_scheduler()
            if scheduler_result.get("success"):
                logger.info("排程器已成功啟動: %s", scheduler_result.get('message'))
            else:
                logger.error("啟動排程器失敗: %s", scheduler_result.get('message'))
        except Exception as e:
            logger.error("啟動排程器時發生未預期錯誤: %s", e, exc_info=True)

        # 啟動背景執行緒來定期重新載入排程
        scheduler_thread = threading.Thread(target=run_scheduled_tasks, daemon=True)
        scheduler_thread.start()
        logger.info("已啟動背景排程重新載入執行緒")

        # 確保 Socket.IO 在所有環境中都正確初始化
        if not socketio.server:
            socketio.init_app(app, async_mode='eventlet')
            logger.info("Socket.IO 已初始化 (async_mode: eventlet)")

        logger.info("應用程式初始化完成")

    except Exception as e:
        logger.error("應用程式初始化失敗: %s", e, exc_info=True)
        cleanup_resources()
        raise


def cleanup_resources():
    """清理應用程式資源"""
    try:
        scheduler = get_scheduler_service()
        scheduler.stop_scheduler()
    except Exception as se:
        logger.error("停止排程器時發生錯誤: %s", se, exc_info=True)
    
    try:
        ServiceContainer.clear_instances()
    except Exception as ce:
        logger.error("清理服務實例時發生錯誤: %s", ce, exc_info=True)

    db_manager = get_db_manager()
    if db_manager:
        try:
            db_manager.cleanup()
            logger.info("資料庫管理器資源已清理")
        except Exception as dbe:
            logger.error("清理資料庫管理器時發生錯誤: %s", dbe, exc_info=True)


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


def main():
    """開發環境下的應用程式入口點"""
    try:
        # 啟動 Flask 開發伺服器 (由 SocketIO 包裝)
        socketio.run(
            app,
            debug=True,
            host="::",
            port=5000,
            use_reloader=False,
            allow_unsafe_werkzeug=True
        )
    except Exception as e:
        logger.critical("主程式執行期間發生無法處理的錯誤: %s", e, exc_info=True)
        cleanup_resources()
        sys.exit(1)


@app.route("/health")
def health_check():
    """健康檢查端點"""
    scheduler_service = get_scheduler_service()
    db_manager = get_db_manager()
    
    # 檢查數據庫連接
    db_healthy = False
    try:
        db_manager.get_session()  # 嘗試獲取數據庫會話
        db_healthy = True
    except Exception as e:
        logger.error(f"數據庫健康檢查失敗: {e}")

    status = {
        "status": "healthy",
        "components": {
            "socketio": {
                "running": bool(socketio.server),
                "connected_clients": len(socketio.server.eio.sockets) if socketio.server else 0
            },
            "scheduler": {
                "running": bool(scheduler_service.is_running()),
                "next_run": scheduler_service.get_next_run_time() if scheduler_service.is_running() else None
            },
            "database": {
                "connected": db_healthy
            }
        },
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    # 如果任何關鍵組件不健康，更新整體狀態
    if not all([
        status["components"]["socketio"]["running"],
        status["components"]["scheduler"]["running"],
        status["components"]["database"]["connected"]
    ]):
        status["status"] = "unhealthy"
        return jsonify(status), 503  # 返回 503 Service Unavailable
    
    return jsonify(status)

if __name__ == "__main__":
    logger.info("開始執行開發伺服器...")
    main()
