from flask_socketio import SocketIO
import uuid

# 初始化 SocketIO 實例，但不綁定到 app
# 使用 threading 模式，因為 TaskExecutorService 使用 ThreadPoolExecutor
socketio = SocketIO(async_mode='threading', cors_allowed_origins="*", ping_timeout=10, ping_interval=5)

# 這個函數會在 app.py 中被調用
def init_app(app):
    """將 socketio 實例綁定到 Flask 應用"""
    socketio.init_app(app)
    return socketio

def generate_session_id():
    """生成唯一的會話ID，用於識別WebSocket連接
    
    Returns:
        str: 唯一的UUID字符串
    """
    return f"session_{uuid.uuid4().hex}" 