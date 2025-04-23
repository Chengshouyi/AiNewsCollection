from flask_socketio import SocketIO

# 初始化 SocketIO 實例，但不綁定到 app
# 使用 threading 模式，因為 TaskExecutorService 使用 ThreadPoolExecutor
socketio = SocketIO(async_mode='threading', cors_allowed_origins="*")

# 這個函數會在 app.py 中被調用
def init_app(app):
    """將 socketio 實例綁定到 Flask 應用"""
    socketio.init_app(app)
    return socketio 