from flask import Flask
from flask_socketio import SocketIO, join_room, leave_room
import logging
from src.web.routes.crawler_api import crawler_bp
from src.web.routes.tasks_api import tasks_bp
from src.web.routes.article_api import article_bp
from src.web.routes.views import view_bp # 導入視圖藍圖

# 設定 Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 初始化 Flask 應用和 SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # 記得更換為安全的密鑰
# 初始化 SocketIO，允許所有來源 (開發方便，生產環境應限制)
# 使用 threading 模式，因為 TaskExecutorService 使用 ThreadPoolExecutor
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*") 

# 註冊藍圖
app.register_blueprint(crawler_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(article_bp)
app.register_blueprint(view_bp)

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

# 主程式入口
if __name__ == '__main__':
    logger.info("Starting Flask-SocketIO server...")
    # 使用 socketio.run 來啟動伺服器，以便 WebSocket 正常工作
    # 允許來自任何 IP 的連接，方便容器環境
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, use_reloader=False) # use_reloader=False 避免多線程問題