from flask import Flask, jsonify
import logging
from src.web.routes.crawler_api import crawler_bp
from src.web.routes.tasks_api import tasks_bp
from src.web.routes.article_api import article_bp
from src.web.routes.views import view_bp  # 導入視圖藍圖
from src.web.socket_instance import socketio, init_app
from flask_socketio import join_room, leave_room
from src.config import get_db_manager
from src.services.service_container import (
    ServiceContainer,
    get_scheduler_service,
    get_task_executor_service,
    get_crawler_task_service,
    get_article_service,
    get_crawlers_service,
)
import os
import time
from dotenv import load_dotenv
from src.utils.log_utils import LoggerSetup  # 使用統一的 logger
import threading  # 導入 threading 模組

logger = LoggerSetup.setup_logger(__name__)  # 使用統一的 logger


load_dotenv()


# 初始化 Flask 應用和 SocketIO
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "a_default_secret_key_for_dev_if_needed"
)

# 初始化 socketio，綁定到 app
init_app(app)

# 註冊藍圖
app.register_blueprint(crawler_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(article_bp)
app.register_blueprint(view_bp)

# 執行應用初始化
# initialize_app(app)


# SocketIO /tasks 命名空間事件處理
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
        logger.info(f"Client joined room: {room}")
        # 可選：發送確認消息或當前狀態
        # socketio.emit('status', {'msg': f'Joined room {room}'}, room=room, namespace='/tasks')
    else:
        logger.warning("Join room request received without room specified.")


@socketio.on("leave_room", namespace="/tasks")
def handle_leave_room(data):
    """處理客戶端離開房間的請求"""
    room = data.get("room")
    if room:
        leave_room(room)
        logger.info(f"Client left room: {room}")
    else:
        logger.warning("Leave room request received without room specified.")


@app.route("/debug/routes")
def list_routes():
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
            # 假設 DatabaseManager 有 cleanup 方法
            db_manager.cleanup()
            logger.info("資料庫管理器資源已清理 (teardown_appcontext)")
        except Exception as e:
            logger.error(
                f"清理資料庫管理器時發生錯誤 (teardown_appcontext): {e}", exc_info=True
            )


def initialize_default_crawler():
    """初始化默認的爬蟲數據，如果不存在則創建"""
    try:
        # 獲取爬蟲服務
        crawlers_service = get_crawlers_service()

        # 定義默認爬蟲數據
        default_crawler = {
            "crawler_name": "BnextCrawler",
            "module_name": "bnext",
            "base_url": "https://www.bnext.com.tw",
            "is_active": True,
            "crawler_type": "web",
            "config_file_name": "bnext_crawler_config.json",
        }

        # 檢查爬蟲是否已存在
        existing_crawler_result = crawlers_service.get_crawler_by_exact_name(
            default_crawler["crawler_name"]
        )

        # 如果不存在，創建新爬蟲
        if (
            not existing_crawler_result["success"]
            or existing_crawler_result["crawler"] is None
        ):
            result = crawlers_service.create_crawler(default_crawler)
            if result["success"]:
                logger.info(f"已成功初始化默認爬蟲: {default_crawler['crawler_name']}")
            else:
                logger.error(f"初始化默認爬蟲失敗: {result['message']}")
        else:
            logger.info(f"默認爬蟲 {default_crawler['crawler_name']} 已存在，無需創建")

    except Exception as e:
        logger.error(f"初始化默認爬蟲時發生錯誤: {e}", exc_info=True)


def main():
    try:
        # 新增：啟動排程器
        try:
            scheduler = get_scheduler_service()
            scheduler_result = scheduler.start_scheduler()
            if scheduler_result.get("success"):
                logger.info(f"排程器已成功啟動: {scheduler_result.get('message')}")
            else:
                logger.error(f"啟動排程器失敗: {scheduler_result.get('message')}")
        except Exception as e:
            logger.error(f"啟動排程器時發生未預期錯誤: {e}", exc_info=True)
            # 根據您的需求，決定是否要在排程器啟動失敗時阻止應用程式啟動
            # raise e # 如果需要，可以取消註解以停止啟動

        # 初始化默認爬蟲數據
        initialize_default_crawler()

        if __debug__:
            # 測試資料庫存取
            pass
            # test_data_access(data_access)

        # 可以在這裡添加其他初始化或定期任務
        logger.info("主程序啟動成功")

    except Exception as e:
        # 在初始化失敗時嘗試清理
        logger.error(f"初始化失敗: {e}", exc_info=True)
        try:
            scheduler.stop_scheduler()
        except Exception as se:
            logger.error(f"初始化失敗後停止排程器時發生錯誤: {se}", exc_info=True)
        try:
            ServiceContainer.clear_instances()
        except Exception as ce:
            logger.error(f"初始化失敗後清理服務實例時發生錯誤: {ce}", exc_info=True)

        db_manager = get_db_manager()
        if db_manager:
            try:
                # 假設 DatabaseManager 有 cleanup 方法
                db_manager.cleanup()
                logger.info("資料庫管理器資源已清理 (teardown_appcontext)")
            except Exception as e:
                logger.error(
                    f"清理資料庫管理器時發生錯誤 (teardown_appcontext): {e}",
                    exc_info=True,
                )
        # 初始化失敗通常意味著無法繼續，所以直接拋出
        raise


def run_scheduled_tasks():
    """長期運行，定期執行排程任務重新載入"""
    # 從環境變數讀取間隔，若無則使用預設值 4 小時
    try:
        interval_sec = int(os.getenv("SCHEDULE_RELOAD_INTERVAL_SEC", "1800"))
        if interval_sec <= 0:
            interval_sec = 1800  # 防止無效值
        logger.info(f"排程任務重新載入間隔設定為: {interval_sec} 秒")
    except ValueError:
        interval_sec = 1800
        logger.warning(
            f"環境變數 SCHEDULE_RELOAD_INTERVAL_SEC 設定無效，使用預設值: {interval_sec} 秒"
        )

    interval_min = interval_sec / 60
    while True:
        try:
            # 執行排程任務重新載入ㄋ
            logger.info("開始重新載入排程任務...")
            get_scheduler_service().reload_scheduler()
            logger.info("排程任務重新載入完成。")
            logger.info(f"下一次重新載入將在 {interval_min} 分鐘後進行。")
            time.sleep(interval_sec)
        except Exception as e:
            # 考慮是否在每次失敗後都停止排程器，或者只是記錄錯誤並繼續嘗試
            get_scheduler_service().stop_scheduler()
            logger.error(f"排程任務重新載入/執行錯誤: {e}", exc_info=True)
            # 在出現錯誤後，短暫休眠避免快速連續失敗
            logger.info("發生錯誤，將在 60 秒後重試...")
            time.sleep(60)


# 主程式入口
if __name__ == "__main__":
    logger.info("開始執行主程序...")
    try:
        main()

        # 創建並啟動一個背景執行緒來運行 run_scheduled_tasks
        scheduler_thread = threading.Thread(target=run_scheduled_tasks, daemon=True)
        scheduler_thread.start()
        logger.info("已啟動背景排程重新載入執行緒")

        # 使用 socketio.run 來啟動伺服器，以便 WebSocket 正常工作
        # 允許來自任何 IP 的連接，方便容器環境
        socketio.run(
            app,
            debug=True,
            host="0.0.0.0",
            port=5000,
            use_reloader=False,  # 通常背景執行緒與 reloader 一起使用會有問題
            allow_unsafe_werkzeug=True,
        )
        # run_scheduled_tasks() 已移至背景執行緒，從此處移除

    except Exception as e:
        logger.error(f"主程式執行錯誤: {e}", exc_info=True)
