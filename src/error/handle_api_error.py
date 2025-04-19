import logging
from flask import jsonify, Response
import requests
from werkzeug.exceptions import HTTPException
from src.error.errors import (
    ValidationError, NotFoundError, DatabaseError, 
    DataOperationError, InvalidOperationError
)

# 設置日誌記錄器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def handle_api_error(error: Exception) -> tuple[Response, int]:
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
        return jsonify({"success": False, "message": str(error), "errors": "Validation Error"}), 400
    
    elif isinstance(error, NotFoundError):
        # 資源不存在
        return jsonify({"success": False, "message": str(error), "errors": "Not Found Error"}), 404
    
    elif isinstance(error, InvalidOperationError):
        # 無效操作
        return jsonify({"success": False, "message": str(error), "errors": "Invalid Operation Error"}), 400
    
    elif isinstance(error, DatabaseError):
        # 資料庫錯誤
        return jsonify({"success": False, "message": str(error), "errors": "Database Error"}), 500
    
    elif isinstance(error, DataOperationError):
        # 資料操作錯誤
        return jsonify({"success": False, "message": str(error), "errors": "Data Operation Error"}), 400
    
    # HTTP 請求相關錯誤處理
    elif isinstance(error, requests.Timeout):
        # 請求超時
        return jsonify({"success": False, "message": str(error), "errors": "Request Timeout Error"}), 504
    
    elif isinstance(error, requests.ConnectionError):
        # 連接錯誤
        return jsonify({"success": False, "message": str(error), "errors": "Connection Error"}), 503
    
    elif isinstance(error, requests.URLRequired):
        # URL 錯誤
        return jsonify({"success": False, "message": str(error), "errors": "Invalid URL Error"}), 400
    
    elif isinstance(error, requests.TooManyRedirects):
        # 重定向次數過多
        return jsonify({"success": False, "message": str(error), "errors": "Too Many Redirects Error"}), 400
    
    elif isinstance(error, requests.RequestException):
        # 一般的請求錯誤
        return jsonify({"success": False, "message": str(error), "errors": "Request Error"}), 500
    
    elif isinstance(error, HTTPException):
        # Flask/Werkzeug HTTP 異常
        return jsonify({"success": False, "message": str(error), "errors": "HTTP Error"}), error.code if error.code is not None else 500
    
    elif isinstance(error, ValueError):
        return jsonify({"success": False, "message": str(error), "errors": "Validation Error"}), 400
    
    elif isinstance(error, KeyError):
        return jsonify({"success": False, "message": str(error), "errors": "Invalid Request Error"}), 400
    
    elif isinstance(error, FileNotFoundError):
        return jsonify({"success": False, "message": str(error), "errors": "Not Found Error"}), 404
    
    elif isinstance(error, PermissionError):
        return jsonify({"success": False, "message": str(error), "errors": "Permission Denied Error"}), 403
    
    elif isinstance(error, TimeoutError):
        return jsonify({"success": False, "message": str(error), "errors": "Timeout Error"}), 504
    
    elif isinstance(error, ConnectionError):
        return jsonify({"success": False, "message": str(error), "errors": "Connection Error"}), 503
    
    elif isinstance(error, requests.exceptions.RequestException):
        return jsonify({"success": False, "message": str(error), "errors": "External Service Error"}), 502
    
    # 其他未處理的錯誤
    return jsonify({"success": False, "message": str(error), "errors": "Internal Server Error"}), 500
