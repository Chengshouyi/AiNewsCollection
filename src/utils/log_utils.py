"""提供統一的日誌記錄設置工具。"""

import logging
import os
from datetime import datetime
from typing import Optional
import pytz
from dotenv import load_dotenv

load_dotenv()


class LoggerSetup:
    """日誌設置工具類
    # 基本使用
    logger = LoggerSetup.setup_logger('my_module')

    # 使用自定義日誌級別
    logger = LoggerSetup.setup_logger('my_module', level=logging.DEBUG)

    # 使用自定義日誌格式
    custom_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logger = LoggerSetup.setup_logger('my_module', log_format=custom_format)

    # 動態切換調試模式
    LoggerSetup.set_debug_mode(logger, True)  # 啟用調試模式
    LoggerSetup.set_debug_mode(logger, False)  # 禁用調試模式


    """

    @staticmethod
    def setup_logger(
        module_name: str,
        log_dir: str = "logs",
        level: int = logging.INFO,
        log_format: Optional[str] = None,
        date_format: Optional[str] = None,
    ) -> logging.Logger:
        """
        設置日誌記錄器

        Args:
            module_name (str): 模組名稱，用於日誌記錄
            log_dir (str): 日誌目錄 (目前未使用，僅輸出到控制台)
            level (int): 日誌級別
            log_format (str, optional): 日誌格式，如果為None則使用預設格式
            date_format (str, optional): 日期格式，如果為None則使用預設格式

        Returns:
            logging.Logger: 配置好的日誌記錄器
        """
        try:
            # 專案根目錄 (假設在容器內的 /app)
            project_root = "/app"
            log_dir_path = os.path.join(project_root, log_dir)
            # 確保日誌目錄存在
            if not os.path.exists(log_dir_path):
                os.makedirs(log_dir_path)

            taipei_tz = pytz.timezone("Asia/Taipei")
            current_time = datetime.now(pytz.UTC).astimezone(taipei_tz)
            timestamp = current_time.strftime("%Y%m%d_%H%M%S")
            log_filename = os.path.join(log_dir_path, f'{module_name}_{timestamp}.log')

            if log_format is None:
                log_format = (
                    "%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s - %(message)s"
                )

            if date_format is None:
                date_format = "%Y-%m-%d %H:%M:%S"

            logger = logging.getLogger(module_name)

            if logger.handlers:
                for handler in logger.handlers[:]:
                    logger.removeHandler(handler)

            # 從環境變數讀取日誌級別，若未設置則使用傳入的 level
            log_level_str = os.getenv("LOG_LEVEL", logging.getLevelName(level))
            try:
                effective_level = logging.getLevelName(log_level_str.upper())
            except ValueError:
                effective_level = level # 若環境變數值無效，使用預設
            logger.setLevel(effective_level)

            class TaipeiFormatter(logging.Formatter):
                def converter(self, timestamp):
                    dt = datetime.fromtimestamp(timestamp, pytz.UTC)
                    return dt.astimezone(taipei_tz)

                def formatTime(self, record, datefmt=None):
                    dt = self.converter(record.created)
                    fmt = datefmt or self._style._fmt.split('.')[0] # 從主格式獲取日期格式
                    if self._style._fmt.endswith('.%(msecs)03d'):
                        s = dt.strftime(fmt)
                        return f"{s}.{record.msecs:03d}"
                    else:
                         return dt.strftime(fmt)

            formatter = TaipeiFormatter(log_format, date_format)

            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

            # 啟用文件處理器
            file_handler = logging.FileHandler(
                filename=log_filename,
                encoding='utf-8',
                mode='a'
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            logger.propagate = False

            logger.debug("日誌系統初始化完成 (控制台 + 文件)")
            logger.debug("日誌文件路徑: %s", log_filename)
            logger.debug("當前時間 (台北): %s", current_time.strftime('%Y-%m-%d %H:%M:%S %Z'))

            return logger

        except Exception as e:
            # 使用基本配置處理初始化錯誤
            basic_logger = logging.getLogger(f"{module_name}_setup_error")
            if not basic_logger.handlers:
                basic_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(basic_formatter)
                basic_logger.addHandler(console_handler)
                basic_logger.setLevel(logging.ERROR) # 確保錯誤能被看到

            basic_logger.error("日誌系統初始化失敗: %s", str(e), exc_info=True)
            return basic_logger # 返回基本 logger 以便至少能記錄錯誤

    @staticmethod
    def set_debug_mode(logger: logging.Logger, enable: bool = False):
        """
        啟用或禁用調試模式

        Args:
            logger (logging.Logger): 要設置的日誌記錄器
            enable (bool): 是否啟用調試模式
        """
        logger.setLevel(logging.DEBUG if enable else logging.INFO)
