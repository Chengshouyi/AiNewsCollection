from flask import Flask
from flask_socketio import SocketIO
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
socketio = SocketIO(app, async_mode='threading') # 使用 threading 模式

# 註冊藍圖
app.register_blueprint(crawler_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(article_bp)
app.register_blueprint(view_bp)

# SocketIO 事件處理 (範例)
@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')

# 主程式入口
if __name__ == '__main__':
    logger.info("Starting Flask-SocketIO server...")
    # 使用 socketio.run 來啟動伺服器，以便 WebSocket 正常工作
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)