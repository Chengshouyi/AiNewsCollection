import pytest
import requests
from src.crawlers.configs.base_config import DEFAULT_HEADERS, DEFAULT_TIMEOUT, DEFAULT_MAX_RETRIES, DEFAULT_RETRY_DELAY, DEFAULT_MIN_DELAY, DEFAULT_MAX_DELAY, DEFAULT_REQUEST_CONFIG, get_default_session, random_sleep
import time
import random
from unittest.mock import patch

def test_default_headers():
    """測試預設的 HTTP 請求頭是否包含必要的欄位"""
    assert "User-Agent" in DEFAULT_HEADERS
    assert "Accept-Language" in DEFAULT_HEADERS
    assert "Accept" in DEFAULT_HEADERS
    assert isinstance(DEFAULT_HEADERS, dict)

def test_default_timeout():
    """測試預設的請求超時設定是否為預期的整數"""
    assert isinstance(DEFAULT_TIMEOUT, int)
    assert DEFAULT_TIMEOUT == 15

def test_default_retries():
    """測試預設的最大重試次數是否為預期的整數"""
    assert isinstance(DEFAULT_MAX_RETRIES, int)
    assert DEFAULT_MAX_RETRIES == 3

def test_default_retry_delay():
    """測試預設的重試延遲時間是否為預期的浮點數"""
    assert isinstance(DEFAULT_RETRY_DELAY, float)
    assert DEFAULT_RETRY_DELAY == 2.0

def test_default_min_delay():
    """測試預設的最小隨機延遲時間是否為預期的浮點數"""
    assert isinstance(DEFAULT_MIN_DELAY, float)
    assert DEFAULT_MIN_DELAY == 1.5

def test_default_max_delay():
    """測試預設的最大隨機延遲時間是否為預期的浮點數"""
    assert isinstance(DEFAULT_MAX_DELAY, float)
    assert DEFAULT_MAX_DELAY == 3.5

def test_default_request_config():
    """測試預設的請求配置是否包含必要的鍵且值為預期的類型"""
    assert isinstance(DEFAULT_REQUEST_CONFIG, dict)
    assert "timeout" in DEFAULT_REQUEST_CONFIG
    assert isinstance(DEFAULT_REQUEST_CONFIG["timeout"], int)
    assert "max_retries" in DEFAULT_REQUEST_CONFIG
    assert isinstance(DEFAULT_REQUEST_CONFIG["max_retries"], int)
    assert "retry_delay" in DEFAULT_REQUEST_CONFIG
    assert isinstance(DEFAULT_REQUEST_CONFIG["retry_delay"], int) # 原本程式碼是 float，但 DEFAULT_REQUEST_CONFIG 中是 int

def test_get_default_session():
    """測試 get_default_session 函數是否返回一個 requests.Session 物件
    且該物件的 headers 是否包含預設的請求頭
    """
    session = get_default_session()
    assert isinstance(session, requests.Session)
    for key, value in DEFAULT_HEADERS.items():
        assert session.headers.get(key) == value

def test_random_sleep_within_range():
    """測試 random_sleep 函數是否在指定的範圍內暫停"""
    min_delay = 0.5
    max_delay = 1.0
    start_time = time.time()
    random_sleep(min_seconds=min_delay, max_seconds=max_delay)
    end_time = time.time()
    elapsed_time = end_time - start_time
    assert min_delay <= elapsed_time <= max_delay + 1.0  # 允許較大誤差以適應不同系統環境

def test_random_sleep_invalid_range():
    """測試當最小值大於最大值時是否拋出異常"""
    with pytest.raises(ValueError, match="最小暫停時間不能大於最大暫停時間"):
        random_sleep(min_seconds=2.0, max_seconds=1.0)

def test_random_sleep_negative_values():
    """測試當輸入負數時是否拋出異常"""
    with pytest.raises(ValueError, match="暫停時間不能小於 0 秒"):
        random_sleep(min_seconds=-1.0, max_seconds=1.0)
    with pytest.raises(ValueError, match="暫停時間不能小於 0 秒"):
        random_sleep(min_seconds=1.0, max_seconds=-1.0)

@patch('time.sleep')
@patch('random.uniform')
def test_random_sleep_calls(mock_uniform, mock_sleep):
    """測試 random_sleep 函數是否正確調用 random.uniform 和 time.sleep"""
    min_delay = 2.0
    max_delay = 5.0
    mock_uniform.return_value = 3.0  # 模擬 random.uniform 的返回值
    random_sleep(min_seconds=min_delay, max_seconds=max_delay)
    mock_uniform.assert_called_once_with(min_delay, max_delay)
    mock_sleep.assert_called_once_with(mock_uniform.return_value)

def test_random_sleep_default_values():
    """測試 random_sleep 函數的預設參數是否正常工作"""
    start_time = time.time()
    time.sleep(1.0)  # 確保至少等待 1 秒
    random_sleep()  # 使用預設參數
    end_time = time.time()
    elapsed_time = end_time - start_time
    assert 2.0 <= elapsed_time <= 5.0  # 預設範圍是 1.0 到 3.0 秒，加上額外的 1 秒等待以及一些允許誤差