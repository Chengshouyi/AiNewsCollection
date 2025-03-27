import logging
import os
from datetime import datetime
from typing import Optional
import pytz

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
        log_dir: str = 'logs',
        level: int = logging.INFO,
        log_format: Optional[str] = None,
        date_format: Optional[str] = None
    ) -> logging.Logger:
        """
        設置日誌記錄器
        
        Args:
            module_name (str): 模組名稱，用於日誌文件名和日誌記錄
            log_dir (str): 日誌目錄
            level (int): 日誌級別
            log_format (str, optional): 日誌格式，如果為None則使用預設格式
            date_format (str, optional): 日期格式，如果為None則使用預設格式
            
        Returns:
            logging.Logger: 配置好的日誌記錄器
        """
        try:
            # 獲取專案根目錄
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            # 創建日誌目錄
            log_dir_path = os.path.join(project_root, log_dir)
            if not os.path.exists(log_dir_path):
                os.makedirs(log_dir_path)
            
            # 使用台北時區
            taipei_tz = pytz.timezone('Asia/Taipei')
            # 獲取當前 UTC 時間並轉換為台北時間
            current_time = datetime.now(pytz.UTC).astimezone(taipei_tz)
            
            # 生成日誌檔案名
            timestamp = current_time.strftime("%Y%m%d_%H%M%S")
            log_filename = os.path.join(log_dir_path, f'{module_name}_{timestamp}.log')
            
            # 設置預設日誌格式
            if log_format is None:
                log_format = '%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s - %(message)s'
            
            # 設置預設日期格式
            if date_format is None:
                date_format = '%Y-%m-%d %H:%M:%S'
            
            # 獲取日誌記錄器
            logger = logging.getLogger(module_name)
            
            # 清除現有的處理器
            if logger.handlers:
                for handler in logger.handlers[:]:
                    logger.removeHandler(handler)
            
            # 設置日誌級別
            logger.setLevel(level)
            
            # 創建格式化器
            class TaipeiFormatter(logging.Formatter):
                def converter(self, timestamp):
                    dt = datetime.fromtimestamp(timestamp, pytz.UTC)
                    return dt.astimezone(taipei_tz)
                
                def formatTime(self, record, datefmt=None):
                    dt = self.converter(record.created)
                    if datefmt:
                        return dt.strftime(datefmt)
                    return dt.strftime(date_format)
            
            # 使用自定義格式化器
            formatter = TaipeiFormatter(log_format, date_format)
            
            # 配置控制台處理器
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
            
            # 配置文件處理器
            file_handler = logging.FileHandler(
                filename=log_filename,
                encoding='utf-8',
                mode='a'
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
            # 設置不要傳遞到父記錄器
            logger.propagate = False
            
            # 記錄初始化信息
            logger.info(f"日誌系統初始化完成")
            logger.info(f"日誌文件路徑: {log_filename}")
            logger.info(f"當前時間: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            
            return logger
            
        except Exception as e:
            # 基本錯誤處理
            basic_logger = logging.getLogger(module_name)
            basic_logger.setLevel(logging.DEBUG)
            
            if not basic_logger.handlers:
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
                basic_logger.addHandler(console_handler)
            
            basic_logger.error(f"日誌系統初始化失敗: {str(e)}", exc_info=True)
            return basic_logger

    @staticmethod
    def set_debug_mode(logger: logging.Logger, enable: bool = False):
        """
        啟用或禁用調試模式
        
        Args:
            logger (logging.Logger): 要設置的日誌記錄器
            enable (bool): 是否啟用調試模式
        """
        logger.setLevel(logging.DEBUG if enable else logging.INFO) 