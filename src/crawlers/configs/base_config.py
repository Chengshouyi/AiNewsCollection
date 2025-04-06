from typing import Dict, Final
import requests
import time
import random
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

"""基礎配置模組，包含爬蟲的通用配置項"""

# HTTP請求頭
DEFAULT_HEADERS: Dict[str, str] = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7'
}

# 請求超時設定（秒）
DEFAULT_TIMEOUT: Final[int] = 15

# 重試設定
DEFAULT_MAX_RETRIES: Final[int] = 3
DEFAULT_RETRY_DELAY: Final[float] = 2.0

# 隨機延遲設定（避免被封鎖）
DEFAULT_MIN_DELAY: Final[float] = 1.5
DEFAULT_MAX_DELAY: Final[float] = 3.5

DEFAULT_REQUEST_CONFIG = {
    'timeout': 10,
    'max_retries': 3,
    'retry_delay': 2
}

def get_default_session() -> requests.Session:
    """創建預設的 requests 會話"""
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    return session

def random_sleep(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
    """隨機暫停，避免請求過於頻繁
    
    Args:
        min_seconds (float): 最小暫停時間（秒），預設為 1.0 秒
        max_seconds (float): 最大暫停時間（秒），預設為 3.0 秒
        
    Raises:
        ValueError: 當 min_seconds 大於 max_seconds 時
        ValueError: 當 min_seconds 或 max_seconds 小於 0 時
    """
    if min_seconds < 0 or max_seconds < 0:
        raise ValueError("暫停時間不能小於 0 秒")
    if min_seconds > max_seconds:
        raise ValueError("最小暫停時間不能大於最大暫停時間")
        
    sleep_time = random.uniform(min_seconds, max_seconds)
    logger.debug(f"等待 {sleep_time:.2f} 秒...")
    time.sleep(sleep_time)