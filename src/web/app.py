from flask import Flask
from src.web.routes.crawler import crawler_bp

def create_app():
    """創建並配置 Flask 應用程式"""
    app = Flask(__name__)
    
    # 註冊藍圖
    app.register_blueprint(crawler_bp)
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)