"""測試 src.error.handle_api_error 中的 API 錯誤處理函數。"""

# 第三方函式庫導入
import logging
import pytest
from flask import Flask
import requests
from werkzeug.exceptions import NotFound, Forbidden

# 本地應用程式導入
from src.error.handle_api_error import handle_api_error
from src.error.errors import (
    ValidationError, NotFoundError, DatabaseError,
    DataOperationError, InvalidOperationError # InvalidOperationError 未使用，但保留
)


# 設定統一的 logger
logger = logging.getLogger(__name__)  # 使用統一的 logger


@pytest.fixture
def app():
    """設置 Flask 測試應用程式上下文。"""
    app = Flask(__name__)
    app.config['TESTING'] = True

    with app.app_context():
        yield app

def test_validation_error(app):
    """測試處理 ValidationError (預期 400 Bad Request)。"""
    with app.test_request_context():
        error = ValidationError("欄位驗證錯誤")
        response, status_code = handle_api_error(error)

        data = response.get_json()
        assert status_code == 400
        assert data["success"] is False
        assert data["message"] == "欄位驗證錯誤"
        assert data["errors"] == "Validation Error"

def test_not_found_error(app):
    """測試處理 NotFoundError (預期 404 Not Found)。"""
    with app.test_request_context():
        error = NotFoundError("找不到資源")
        response, status_code = handle_api_error(error)

        data = response.get_json()
        assert status_code == 404
        assert data["success"] is False
        assert data["message"] == "找不到資源"
        assert data["errors"] == "Not Found Error"

def test_database_error(app):
    """測試處理 DatabaseError (預期 500 Internal Server Error)。"""
    with app.test_request_context():
        error = DatabaseError("資料庫連接失敗")
        response, status_code = handle_api_error(error)

        data = response.get_json()
        assert status_code == 500
        assert data["success"] is False
        assert data["message"] == "資料庫連接失敗"
        assert data["errors"] == "Database Error"

def test_data_operation_error(app):
    """測試處理 DataOperationError (預期 400 Bad Request)。"""
    with app.test_request_context():
        error = DataOperationError("資料操作失敗")
        response, status_code = handle_api_error(error)

        data = response.get_json()
        assert status_code == 400
        assert data["success"] is False
        assert data["message"] == "資料操作失敗"
        assert data["errors"] == "Data Operation Error"

def test_http_request_timeout_error(app):
    """測試處理 requests.Timeout (預期 504 Gateway Timeout)。"""
    with app.test_request_context():
        error = requests.Timeout("請求超時")
        response, status_code = handle_api_error(error)

        data = response.get_json()
        assert status_code == 504
        assert data["success"] is False
        assert data["message"] == "請求超時"
        assert data["errors"] == "Request Timeout Error"

def test_http_connection_error(app):
    """測試處理 requests.ConnectionError (預期 503 Service Unavailable)。"""
    with app.test_request_context():
        error = requests.ConnectionError("連接失敗")
        response, status_code = handle_api_error(error)

        data = response.get_json()
        assert status_code == 503
        assert data["success"] is False
        assert data["message"] == "連接失敗"
        assert data["errors"] == "Connection Error"

def test_http_url_error(app):
    """測試處理 requests.URLRequired (預期 400 Bad Request)。"""
    with app.test_request_context():
        error = requests.URLRequired("需要 URL")
        response, status_code = handle_api_error(error)

        data = response.get_json()
        assert status_code == 400
        assert data["success"] is False
        assert data["message"] == "需要 URL"
        assert data["errors"] == "Invalid URL Error"

def test_http_too_many_redirects_error(app):
    """測試處理 requests.TooManyRedirects (預期 400 Bad Request)。"""
    with app.test_request_context():
        error = requests.TooManyRedirects("重定向過多")
        response, status_code = handle_api_error(error)

        data = response.get_json()
        assert status_code == 400
        assert data["success"] is False
        assert data["message"] == "重定向過多"
        assert data["errors"] == "Too Many Redirects Error"

def test_flask_http_exception(app):
    """測試處理 Flask HTTP 異常 (如 NotFound, Forbidden)。"""
    with app.test_request_context():
        # 測試 404 Not Found
        error_404 = NotFound("找不到頁面")
        response_404, status_code_404 = handle_api_error(error_404)

        data_404 = response_404.get_json()
        assert status_code_404 == 404
        assert data_404["success"] is False
        # Flask 的 HTTPException 描述包含在 str(error) 中
        assert "找不到頁面" in data_404["message"]
        assert data_404["errors"] == "HTTP Error"

        # 測試 403 Forbidden
        error_403 = Forbidden("禁止訪問")
        response_403, status_code_403 = handle_api_error(error_403)

        data_403 = response_403.get_json()
        assert status_code_403 == 403
        assert data_403["success"] is False
        assert "禁止訪問" in data_403["message"]
        assert data_403["errors"] == "HTTP Error"

def test_generic_exception(app):
    """測試處理未被特別處理的一般 Exception (預期 500 Internal Server Error)。"""
    with app.test_request_context():
        error = Exception("未知錯誤")
        response, status_code = handle_api_error(error)

        data = response.get_json()
        assert status_code == 500
        assert data["success"] is False
        assert data["message"] == "伺服器內部發生未預期的錯誤。"
        assert data["errors"] == "Internal Server Error" 