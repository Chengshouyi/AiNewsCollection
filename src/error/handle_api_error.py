import logging
from flask import jsonify
import requests
from werkzeug.exceptions import HTTPException
from src.error.errors import (
    ValidationError, NotFoundError, DatabaseError, 
    DataOperationError, InvalidOperationError
)

# 設置日誌記錄器
logger = logging.getLogger(__name__)

def handle_api_error(error):
    """
    處理 API 錯誤，並返回相應的 HTTP 狀態碼和錯誤訊息
    
    參數:
        error: 異常物件
        
    返回:
        JSON 響應和相應的 HTTP 狀態碼
    """
    # 記錄錯誤詳情
    logger.error(f"API錯誤: {str(error)}", exc_info=True)
    
    # 映射錯誤類型到 HTTP 狀態碼和錯誤訊息
    if isinstance(error, ValidationError):
        # 驗證錯誤
        return jsonify({"error": str(error), "type": "validation_error"}), 400
    
    elif isinstance(error, NotFoundError):
        # 資源不存在
        return jsonify({"error": str(error), "type": "not_found"}), 404
    
    elif isinstance(error, InvalidOperationError):
        # 無效操作
        return jsonify({"error": str(error), "type": "invalid_operation"}), 400
    
    elif isinstance(error, DatabaseError):
        # 資料庫錯誤
        return jsonify({"error": "資料庫操作錯誤", "type": "database_error"}), 500
    
    elif isinstance(error, DataOperationError):
        # 資料操作錯誤
        return jsonify({"error": str(error), "type": "data_operation_error"}), 400
    
    # HTTP 請求相關錯誤處理
    elif isinstance(error, requests.Timeout):
        # 請求超時
        return jsonify({"error": "請求超時", "type": "request_timeout"}), 504
    
    elif isinstance(error, requests.ConnectionError):
        # 連接錯誤
        return jsonify({"error": "無法連接到目標服務器", "type": "connection_error"}), 503
    
    elif isinstance(error, requests.URLRequired):
        # URL 錯誤
        return jsonify({"error": "無效的 URL", "type": "invalid_url"}), 400
    
    elif isinstance(error, requests.TooManyRedirects):
        # 重定向次數過多
        return jsonify({"error": "重定向次數過多", "type": "too_many_redirects"}), 400
    
    elif isinstance(error, requests.RequestException):
        # 一般的請求錯誤
        return jsonify({"error": f"請求錯誤: {str(error)}", "type": "request_error"}), 500
    
    elif isinstance(error, HTTPException):
        # Flask/Werkzeug HTTP 異常
        return jsonify({"error": error.description, "type": "http_error"}), error.code
    
    # 其他未處理的錯誤
    return jsonify({"error": "內部服務器錯誤", "type": "internal_error"}), 500
