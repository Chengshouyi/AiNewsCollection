"""定義爬蟲的基礎通用配置，如請求頭、超時、重試和延遲設定。"""

# 標準函式庫導入
import time
import random
import logging # 移除舊的 logger 設定
from typing import Dict, Final

# 第三方函式庫導入
import requests

# 本地應用程式導入
from src.utils.log_utils import LoggerSetup

# 設定統一的 logger
logger = LoggerSetup.setup_logger(__name__)

# 移除舊的 logging.basicConfig
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)


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

# 預設請求配置字典 (注意: 這裡的 retry_delay 是 int，與 DEFAULT_RETRY_DELAY 不同)
DEFAULT_REQUEST_CONFIG: Dict[str, int] = {
    'timeout': 10,
    'max_retries': 3,
    'retry_delay': 2 # 這裡使用整數 2
}

def get_default_session() -> requests.Session:
    """創建預設的 requests 會話，並應用預設請求頭。"""
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    return session

def random_sleep(min_seconds: float = DEFAULT_MIN_DELAY, max_seconds: float = DEFAULT_MAX_DELAY) -> None:
    """隨機暫停，避免請求過於頻繁

    使用模組級別的 DEFAULT_MIN_DELAY 和 DEFAULT_MAX_DELAY 作為預設值。

    Args:
        min_seconds (float): 最小暫停時間（秒）。
        max_seconds (float): 最大暫停時間（秒）。

    Raises:
        ValueError: 當 min_seconds 大於 max_seconds 時。
        ValueError: 當 min_seconds 或 max_seconds 小於 0 時。
    """
    if min_seconds < 0 or max_seconds < 0:
        raise ValueError("暫停時間不能小於 0 秒")
    if min_seconds > max_seconds:
        raise ValueError("最小暫停時間不能大於最大暫停時間")

    sleep_time = random.uniform(min_seconds, max_seconds)
    # 使用標準格式化避免 PylintW1203
    logger.debug("等待 %.2f 秒...", sleep_time)
    time.sleep(sleep_time)