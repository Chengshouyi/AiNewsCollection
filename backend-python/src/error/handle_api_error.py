"""定義一個通用的 API 錯誤處理函數，將異常映射到標準的 JSON 響應和 HTTP 狀態碼。"""

# 標準函式庫導入
import logging # 移除舊的 logger 設定

# 第三方函式庫導入
from flask import jsonify, Response
import requests
from werkzeug.exceptions import HTTPException

# 本地應用程式導入
from src.error.errors import (
    ValidationError, NotFoundError, DatabaseError,
    DataOperationError, InvalidOperationError
)
from src.error.service_errors import (
    ServiceError, ServiceExecutionError, ServiceInitializationError,
    ServiceCleanupError, ServiceShutdownError
)


# 設定統一的 logger
logger = logging.getLogger(__name__)  # 使用統一的 logger


def handle_api_error(error: Exception) -> tuple[Response, int]:
    """
    集中處理 API 路由中發生的各種異常。

    根據異常類型返回標準化的 JSON 錯誤響應和對應的 HTTP 狀態碼。
    同時記錄詳細的錯誤資訊。

    Args:
        error: 捕獲到的異常物件。

    Returns:
        一個包含 Flask Response 物件和整數狀態碼的元組。
    """
    # 記錄錯誤詳情，使用標準格式化
    logger.error("API 錯誤: %s", str(error), exc_info=True)

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

    # --- Service Errors ---  
    elif isinstance(error, ServiceExecutionError):
        return jsonify({"success": False, "message": str(error), "errors": "Service Execution Error"}), 500

    elif isinstance(error, ServiceInitializationError):
        return jsonify({"success": False, "message": str(error), "errors": "Service Initialization Error"}), 500
        
    elif isinstance(error, ServiceCleanupError):
        return jsonify({"success": False, "message": str(error), "errors": "Service Cleanup Error"}), 500

    elif isinstance(error, ServiceShutdownError):
        return jsonify({"success": False, "message": str(error), "errors": "Service Shutdown Error"}), 500

    elif isinstance(error, ServiceError): # 捕獲其他未明確指定的 ServiceError 子類
        return jsonify({"success": False, "message": str(error), "errors": "Service Error"}), 500

    # --- HTTP 請求相關錯誤處理 ---
    elif isinstance(error, requests.Timeout):
        # 請求超時
        return jsonify({"success": False, "message": str(error), "errors": "Request Timeout Error"}), 504

    elif isinstance(error, requests.ConnectionError):
        # 連接錯誤 (requests 庫的)
        return jsonify({"success": False, "message": str(error), "errors": "Connection Error"}), 503

    elif isinstance(error, requests.URLRequired):
        # URL 錯誤
        return jsonify({"success": False, "message": str(error), "errors": "Invalid URL Error"}), 400

    elif isinstance(error, requests.TooManyRedirects):
        # 重定向次數過多
        return jsonify({"success": False, "message": str(error), "errors": "Too Many Redirects Error"}), 400

    elif isinstance(error, requests.exceptions.RequestException):
         # requests 庫的其他通用請求錯誤（應放在更具體的 requests 錯誤之後）
        return jsonify({"success": False, "message": str(error), "errors": "External Service Error"}), 502 # 502 Bad Gateway 通常表示上游服務問題

    # --- Flask/Werkzeug HTTP 異常處理 ---
    elif isinstance(error, HTTPException):
        # Flask/Werkzeug 定義的標準 HTTP 異常
        # HTTPException 預設有 code 屬性
        status_code = error.code if hasattr(error, 'code') and error.code is not None else 500
        return jsonify({"success": False, "message": str(error), "errors": "HTTP Error"}), status_code

    # --- Python 內建異常處理 (部分示例) ---
    elif isinstance(error, ValueError):
        # 值錯誤 (常與驗證相關)
        return jsonify({"success": False, "message": str(error), "errors": "Validation Error"}), 400

    elif isinstance(error, KeyError):
        # 鍵錯誤 (常因請求缺少必要參數)
        return jsonify({"success": False, "message": f"請求缺少必要鍵: {str(error)}", "errors": "Invalid Request Error"}), 400

    elif isinstance(error, FileNotFoundError):
        # 文件未找到
        return jsonify({"success": False, "message": str(error), "errors": "Not Found Error"}), 404

    elif isinstance(error, PermissionError):
        # 權限錯誤
        return jsonify({"success": False, "message": str(error), "errors": "Permission Denied Error"}), 403

    elif isinstance(error, TimeoutError):
        # 內建超時錯誤 (非 requests 庫的)
        return jsonify({"success": False, "message": str(error), "errors": "Timeout Error"}), 504

    elif isinstance(error, ConnectionError):
        # 內建連接錯誤 (非 requests 庫的)
        return jsonify({"success": False, "message": str(error), "errors": "Connection Error"}), 503

    # --- 其他未明確處理的錯誤 --- 
    # 捕獲所有未被特別處理的 Exception 子類
    else:
        # 使用通用訊息避免暴露過多內部細節
        generic_message = "伺服器內部發生未預期的錯誤。"
        return jsonify({"success": False, "message": generic_message, "errors": "Internal Server Error"}), 500
