from flask import Flask, jsonify
import logging
from src.web.routes.crawler_api import crawler_bp
from src.web.routes.tasks_api import tasks_bp
from src.web.routes.article_api import article_bp
from src.web.routes.views import view_bp # 導入視圖藍圖
from src.web.socket_instance import socketio, init_app
from flask_socketio import join_room, leave_room
from src.models.base_model import Base
from src.config import get_db_manager
from src.services.service_container import get_scheduler_service, get_crawlers_service
import os

from src.utils.log_utils import LoggerSetup # 使用統一的 logger
logger = LoggerSetup.setup_logger(__name__) # 使用統一的 logger



# 初始化資料庫和默認數據
# def initialize_app(app):
#     with app.app_context():
        # 初始化資料庫表格
        # db_manager = get_db_manager()
        # db_manager.create_tables(Base)
        # logger.info("資料庫初始化完成")
        
        # 初始化默認爬蟲數據，移到 run.py 中
        # initialize_default_crawler()
        # logger.info("默認數據初始化完成")

# 初始化 Flask 應用和 SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_default_secret_key_for_dev_if_needed')

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
@socketio.on('connect', namespace='/tasks')
def handle_tasks_connect():
    logger.info('Client connected to /tasks namespace')

@socketio.on('disconnect', namespace='/tasks')
def handle_tasks_disconnect():
    logger.info('Client disconnected from /tasks namespace')

@socketio.on('join_room', namespace='/tasks')
def handle_join_room(data):
    """處理客戶端加入房間的請求"""
    room = data.get('room')
    if room:
        join_room(room)
        logger.info(f'Client joined room: {room}')
        # 可選：發送確認消息或當前狀態
        # socketio.emit('status', {'msg': f'Joined room {room}'}, room=room, namespace='/tasks')
    else:
        logger.warning("Join room request received without room specified.")

@socketio.on('leave_room', namespace='/tasks')
def handle_leave_room(data):
    """處理客戶端離開房間的請求"""
    room = data.get('room')
    if room:
        leave_room(room)
        logger.info(f'Client left room: {room}')
    else:
        logger.warning("Leave room request received without room specified.")

@app.route('/debug/routes')
def list_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods or set()),
            'route': str(rule)
        })
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
            logger.error(f"清理資料庫管理器時發生錯誤 (teardown_appcontext): {e}", exc_info=True)

# 主程式入口
if __name__ == '__main__':
    logger.info("Starting Flask-SocketIO server...")
    # 新增：啟動排程器
    try:
        scheduler = get_scheduler_service()
        scheduler_result = scheduler.start_scheduler()
        if scheduler_result.get('success'):
            logger.info(f"排程器已成功啟動: {scheduler_result.get('message')}")
        else:
            logger.error(f"啟動排程器失敗: {scheduler_result.get('message')}")
    except Exception as e:
        logger.error(f"啟動排程器時發生未預期錯誤: {e}", exc_info=True)
        # 根據您的需求，決定是否要在排程器啟動失敗時阻止應用程式啟動
        # raise e # 如果需要，可以取消註解以停止啟動
    # 新增結束

    # 使用 socketio.run 來啟動伺服器，以便 WebSocket 正常工作
    # 允許來自任何 IP 的連接，方便容器環境
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, use_reloader=False, allow_unsafe_werkzeug=True) # 添加參數