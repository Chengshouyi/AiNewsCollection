"""提供統一的日誌記錄設置工具。"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import pytz
from dotenv import load_dotenv
import re

load_dotenv()


class LoggerSetup:
    """日誌設置工具類
    # 基本使用 (在應用程式入口調用一次)
    # LoggerSetup.configure_logging()

    # 其他模塊直接使用 standard logging:
    # import logging
    # logger = logging.getLogger(__name__)
    # logger.info("Some message")

    # 使用自定義日誌級別
    logger = LoggerSetup.setup_logger('my_module', level=logging.DEBUG)

    # 使用自定義日誌格式
    custom_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logger = LoggerSetup.setup_logger('my_module', log_format=custom_format)

    # 動態切換調試模式
    LoggerSetup.set_debug_mode(logger, True)  # 啟用調試模式
    LoggerSetup.set_debug_mode(logger, False)  # 禁用調試模式


    """

    _configured = False # 類變量，防止重複配置

    @staticmethod
    def configure_logging(
        log_dir: str = "logs",
        level: int = logging.INFO,
        log_format: Optional[str] = None,
        date_format: Optional[str] = None,
    ):
        """
        配置根日誌記錄器。此方法應在應用程式啟動時調用一次。

        Args:
            log_dir (str): 日誌目錄 (相對於專案根目錄 /app)
            level (int): 預設日誌級別 (可被環境變數 LOG_LEVEL 覆蓋)
            log_format (str, optional): 日誌格式，如果為None則使用預設格式
            date_format (str, optional): 日期格式，如果為None則使用預設格式

        環境變數:
            LOG_LEVEL: 設置日誌級別 (e.g., DEBUG, INFO, WARNING, ERROR, CRITICAL)
            LOG_OUTPUT_MODE: 控制日誌輸出目的地 ('console', 'file', 'both'). 預設為 'both'.
        """
        # 防止重複配置
        if LoggerSetup._configured:
            # 可以選擇性地打印一個 debug 消息或直接返回
            # print("Logging already configured.")
            return

        root_logger = logging.getLogger() # 獲取根記錄器

        # --- 設置級別 ---
        log_level_str_env = os.getenv("LOG_LEVEL")
        effective_level = level

        if log_level_str_env:
            level_name_upper = log_level_str_env.strip().upper()
            level_map = logging._nameToLevel
            if level_name_upper in level_map:
                effective_level = level_map[level_name_upper]
            else:
                # 使用 print 因為此時 logger 可能還未完全設置
                print(f"警告: 環境變數 LOG_LEVEL 值 '{log_level_str_env}' 無效，將使用預設級別 {logging.getLevelName(level)}")

        root_logger.setLevel(effective_level)

        # --- 格式化器 ---
        if log_format is None:
            log_format = (
                "%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s - %(message)s"
            )
        if date_format is None:
            date_format = "%Y-%m-%d %H:%M:%S"

        taipei_tz = pytz.timezone("Asia/Taipei")
        class TaipeiFormatter(logging.Formatter):
            def converter(self, timestamp):
                dt = datetime.fromtimestamp(timestamp, pytz.UTC)
                return dt.astimezone(taipei_tz)

            def formatTime(self, record, datefmt=None):
                dt = self.converter(record.created)
                fmt = datefmt or self._style._fmt.split('.')[0]
                if self._style._fmt.endswith('.%(msecs)03d'):
                    s = dt.strftime(fmt)
                    return f"{s}.{record.msecs:03d}"
                else:
                    return dt.strftime(fmt)

        formatter = TaipeiFormatter(log_format, date_format)

        # --- 清理現有 Handlers (以防萬一，通常根記錄器默認沒有) ---
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # --- 添加 Handlers ---
        log_output_mode = os.getenv("LOG_OUTPUT_MODE", "both").lower()
        output_destinations = []

        # 控制台 Handler
        if log_output_mode in ["console", "both"]:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
            output_destinations.append("控制台")

        # 文件 Handler
        if log_output_mode in ["file", "both"]:
            try:
                project_root = "/app"
                log_dir_path = os.path.join(project_root, log_dir)
                if not os.path.exists(log_dir_path):
                    os.makedirs(log_dir_path)

                current_time = datetime.now(pytz.UTC).astimezone(taipei_tz)
                timestamp = current_time.strftime("%Y%m%d_%HM") # 簡化文件名，避免過多文件
                log_filename = os.path.join(log_dir_path, f'app_{timestamp}.log') # 通用文件名

                file_handler = logging.FileHandler(
                    filename=log_filename,
                    encoding='utf-8',
                    mode='a'
                )
                file_handler.setFormatter(formatter)
                root_logger.addHandler(file_handler)
                output_destinations.append("文件")
            except Exception as e:
                 print(f"錯誤：無法設置文件日誌處理器: {e}")


        init_message = f"根日誌系統初始化完成 ({' + '.join(output_destinations)})"
        if not output_destinations:
            init_message = "警告：未配置任何日誌輸出目的地 (LOG_OUTPUT_MODE 可能設置為無效值)"
            print(init_message)
        else:
            root_logger.info(init_message) # 使用 INFO 級別報告初始化完成
            if "文件" in output_destinations:
                 root_logger.info("日誌文件可能位於: %s", log_dir_path) # 不再打印精確文件名以防歧義

        # 標記為已配置
        LoggerSetup._configured = True

    @staticmethod
    def set_debug_mode(logger: logging.Logger, enable: bool = False):
        # 這個方法現在操作的是傳入的 logger，可能不再需要，
        # 或者應該調整為直接設置根 logger 的級別，但要小心副作用。
        # 暫時保留原樣，但調用時需謹慎。
        # 更好的方法是透過環境變數 LOG_LEVEL 控制。
        # ... (原有的 set_debug_mode 邏輯) ...
        pass # 暫時禁用，因為直接修改根記錄器級別影響全局

    @staticmethod
    def cleanup_logs(
        log_dir: Optional[str] = None,
        module_name: Optional[str] = None, # 參數保留，但可能不再精確匹配文件名
        keep_days: Optional[int] = None,
        dry_run: bool = False,
        logger: Optional[logging.Logger] = None # 保持允許傳入 logger
    ) -> List[str]:
        """
        清理指定目錄下的日誌文件。

        配置優先級: 函數參數 > 環境變數 > 預設值

        Args:
            log_dir (str, optional): 日誌文件所在的目錄 (相對於專案根目錄 /app)。
                                     如果為 None，則嘗試讀取環境變數 LOG_CLEANUP_LOG_DIR，預設為 "logs"。
            module_name (str, optional): 只清理特定模組的日誌。
                                     如果為 None，則嘗試讀取環境變數 LOG_CLEANUP_MODULE_NAME，預設為清理所有模組。
                                     若環境變數設為空字串 ""，也表示清理所有模組。
            keep_days (int, optional): 保留最近幾天的日誌。
                                     如果為 None，則嘗試讀取環境變數 LOG_CLEANUP_KEEP_DAYS。
                                     若環境變數也未設置或無效，則不按天數限制刪除 (刪除所有匹配的)。
                                     例如，設置為 7 將保留今天及過去 7 天內的日誌。
            dry_run (bool): 如果為 True，則僅打印將要刪除的文件列表，而不實際刪除。
                                     可由環境變數 LOG_CLEANUP_DRY_RUN 控制 (設為 "true" 或 "1")。函數參數優先。
            logger (logging.Logger, optional): 用於記錄清理操作的日誌記錄器。如果未提供，
                                               將使用一個基本的控制台記錄器。

        Returns:
            List[str]: 被刪除 (或在 dry_run 模式下將被刪除) 的文件完整路徑列表。

        Raises:
            FileNotFoundError: 如果最終確定的 log_dir 不存在。
            PermissionError: 如果沒有權限讀取目錄或刪除文件。
            ValueError: 如果 keep_days 或對應的環境變數設為負數或無法解析的非數字。

        環境變數:
            LOG_CLEANUP_LOG_DIR: 指定日誌目錄 (預設: "logs")
            LOG_CLEANUP_MODULE_NAME: 指定要清理的模組名稱 (預設: ""，表示所有模組)
            LOG_CLEANUP_KEEP_DAYS: 指定保留天數 (預設: ""，表示不限制天數，刪除所有匹配項)
            LOG_CLEANUP_DRY_RUN: 設為 "true" 或 "1" 以啟用 Dry Run 模式 (預設: "false")
        """
        if logger is None:
            # 如果沒有提供 logger，創建一個簡單的或獲取根 logger
            logger = logging.getLogger("LogCleanup")
            if not logger.handlers: # 確保 cleanup logger 有 handler
                 if logging.getLogger().hasHandlers(): # 嘗試繼承根 logger 的 handler
                      pass # 繼承即可
                 else: # 如果根 logger 也沒配置好，加一個 console handler
                    handler = logging.StreamHandler()
                    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                    handler.setFormatter(formatter)
                    logger.addHandler(handler)
                    logger.setLevel(logging.INFO)


        # --- 其餘邏輯基本保持不變，但文件名匹配模式可能需要調整 ---
        # 讀取環境變數，函數參數優先
        final_log_dir = log_dir if log_dir is not None else os.getenv("LOG_CLEANUP_LOG_DIR", "logs")
        # final_module_name = module_name if module_name is not None else os.getenv("LOG_CLEANUP_MODULE_NAME", "")
        # 注意：由於文件名現在是 app_timestamp.log，module_name 不再直接適用於過濾文件名
        # 如果仍想按模塊清理，需要改變日誌記錄方式或文件名格式。
        # 暫時忽略 module_name 過濾條件。
        if module_name:
             logger.warning("Log cleanup by module_name is currently not supported with the new root logger file naming scheme.")

        final_keep_days = keep_days # 函數參數優先

        if final_keep_days is None:
            keep_days_str = os.getenv("LOG_CLEANUP_KEEP_DAYS", "")
            if keep_days_str.isdigit():
                try:
                    final_keep_days = int(keep_days_str)
                    if final_keep_days < 0:
                         logger.warning(f"環境變數 LOG_CLEANUP_KEEP_DAYS 值無效 (負數: {keep_days_str})，將不按天數限制刪除。")
                         final_keep_days = None # 無效值，重置為 None
                except ValueError:
                    logger.warning(f"環境變數 LOG_CLEANUP_KEEP_DAYS 值無法解析為整數: '{keep_days_str}'，將不按天數限制刪除。")
                    final_keep_days = None # 無法解析，重置為 None
            elif keep_days_str != "":
                 logger.warning(f"環境變數 LOG_CLEANUP_KEEP_DAYS 值非數字: '{keep_days_str}'，將不按天數限制刪除。")
                 # final_keep_days 保持 None

        # 檢查 final_keep_days 是否最終為負數 (可能來自函數參數)
        if final_keep_days is not None and final_keep_days < 0:
            raise ValueError("keep_days 不能是負數")

        # Dry run: ... (邏輯保持不變) ...
        final_dry_run = dry_run
        if not final_dry_run:
            dry_run_env = os.getenv("LOG_CLEANUP_DRY_RUN", "false").lower()
            final_dry_run = dry_run_env in ["true", "1", "yes"]

        project_root = "/app"
        log_dir_path = os.path.join(project_root, final_log_dir)

        if not os.path.isdir(log_dir_path):
            logger.error(f"日誌目錄不存在: {log_dir_path}")
            raise FileNotFoundError(f"日誌目錄不存在: {log_dir_path}")

        logger.info(f"{'Dry run: ' if final_dry_run else ''}開始清理日誌目錄: {log_dir_path}")
        # if final_module_name: # 移除模塊過濾日誌
        #     logger.info(f"目標模塊: {final_module_name}")
        if final_keep_days is not None:
            logger.info(f"保留天數: {final_keep_days}")
        else:
             logger.info("未設置保留天數，將刪除所有符合條件的日誌。")

        # 調整文件名模式以匹配 app_*.log
        timestamp_pattern = re.compile(r"app_(\d{8}_\d{4})\.log$") # 匹配 YYYYMMDD_HHMM
        files_to_delete = []
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(days=final_keep_days) if final_keep_days is not None else None

        try:
            for filename in os.listdir(log_dir_path):
                file_path = os.path.join(log_dir_path, filename)

                if not os.path.isfile(file_path) or not filename.startswith("app_") or not filename.endswith(".log"):
                    continue

                # if final_module_name and not filename.startswith(final_module_name + "_"): # 移除模塊名檢查
                #     continue

                match = timestamp_pattern.search(filename)
                if not match:
                    continue

                timestamp_str = match.group(1)
                try:
                    # 根據新的格式解析
                    naive_dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M")
                    # 假設文件名中的時間是台北時間 (因為是這樣生成的)
                    taipei_tz = pytz.timezone("Asia/Taipei")
                    local_dt = taipei_tz.localize(naive_dt)
                    file_time_utc = local_dt.astimezone(timezone.utc)

                    if cutoff_time and file_time_utc >= cutoff_time:
                        continue
                except ValueError:
                    logger.warning(f"無法解析文件名的時間戳: {filename}")
                    continue

                files_to_delete.append(file_path)

            deleted_files = []
            if not files_to_delete:
                logger.info("沒有找到符合條件需要刪除的日誌文件。")
                return []

            logger.info(f"找到 {len(files_to_delete)} 個符合條件的日誌文件準備{'打印' if final_dry_run else '刪除'}:")
            for file_path in files_to_delete:
                try:
                    if final_dry_run:
                        logger.info(f"[Dry Run] 會刪除: {file_path}")
                        deleted_files.append(file_path)
                    else:
                        os.remove(file_path)
                        logger.info(f"已刪除: {file_path}")
                        deleted_files.append(file_path)
                except OSError as e:
                    logger.error(f"刪除文件失敗: {file_path} - {e}")

            logger.info(f"{'Dry run: ' if final_dry_run else ''}清理完成。{'計劃' if final_dry_run else '實際'}刪除 {len(deleted_files)} 個文件。")
            return deleted_files

        except PermissionError:
            logger.error(f"讀取目錄或刪除文件權限不足: {log_dir_path}")
            raise
        except Exception as e:
            logger.error(f"清理日誌時發生未知錯誤: {e}", exc_info=True)
            raise
