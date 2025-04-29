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
            log_dir (str): 日誌目錄
            level (int): 日誌級別 (可被環境變數 LOG_LEVEL 覆蓋)
            log_format (str, optional): 日誌格式，如果為None則使用預設格式
            date_format (str, optional): 日期格式，如果為None則使用預設格式

        Returns:
            logging.Logger: 配置好的日誌記錄器

        環境變數:
            LOG_LEVEL: 設置日誌級別 (e.g., DEBUG, INFO, WARNING, ERROR, CRITICAL)
            LOG_OUTPUT_MODE: 控制日誌輸出目的地 ('console', 'file', 'both'). 預設為 'both'.
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
            log_level_str_env = os.getenv("LOG_LEVEL")
            effective_level = level  # 預設使用傳入的整數級別

            if log_level_str_env:
                level_name_upper = log_level_str_env.strip().upper()
                level_map = logging._nameToLevel # 使用內部映射替代 getLevelNamesMapping()
                if level_name_upper in level_map:
                    effective_level = level_map[level_name_upper] # 使用映射查找整數級別
                else:
                    # 如果環境變數值無效，發出警告並使用預設值
                    # 注意：此時 logger 的 handler 可能還未完全配置好，使用 print 可能更可靠
                    print(f"警告: 環境變數 LOG_LEVEL 值 '{log_level_str_env}' 無效，將使用預設級別 {logging.getLevelName(level)}")
                    # 或者如果 logger 已經有基本 handler:
                    # logger.warning(f"環境變數 LOG_LEVEL 值 '{log_level_str_env}' 無效，將使用預設級別 {logging.getLevelName(level)}")

            logger.setLevel(effective_level)

            # 從環境變數讀取輸出模式
            log_output_mode = os.getenv("LOG_OUTPUT_MODE", "both").lower()

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

            output_destinations = []

            # 根據模式添加控制台處理器
            if log_output_mode in ["console", "both"]:
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(formatter)
                logger.addHandler(console_handler)
                output_destinations.append("控制台")

            # 根據模式添加文件處理器
            if log_output_mode in ["file", "both"]:
                # 啟用文件處理器
                file_handler = logging.FileHandler(
                    filename=log_filename,
                    encoding='utf-8',
                    mode='a'
                )
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
                output_destinations.append("文件")

            logger.propagate = False

            init_message = f"日誌系統初始化完成 ({' + '.join(output_destinations)})"
            if not output_destinations:
                init_message = "警告：未配置任何日誌輸出目的地 (LOG_OUTPUT_MODE 可能設置為無效值)"
                logger.warning(init_message) # 如果沒有 handler，這條可能無法輸出
            else:
                logger.debug(init_message)
                if "文件" in output_destinations:
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
        # 優先使用環境變數 LOG_LEVEL，如果存在則不應手動切換
        log_level_env = os.getenv("LOG_LEVEL")
        if log_level_env:
             current_level = logger.getEffectiveLevel()
             new_level = logging.DEBUG if enable else logging.getLevelName(log_level_env.upper())
             if new_level != current_level:
                 logger.warning("LOG_LEVEL 環境變數已設置 (%s)，set_debug_mode 可能不會按預期工作。", log_level_env)
             # 即使有環境變數，仍然允許臨時切換，但給出警告
             logger.setLevel(new_level)

        else:
            # 如果沒有環境變數，則根據 enable 切換 INFO 和 DEBUG
            current_level_name = logging.getLevelName(logger.level)
            default_level = logging.INFO # 假設預設非調試級別是 INFO
            new_level = logging.DEBUG if enable else default_level
            if new_level != logger.level:
                logger.info(f"日誌級別從 {current_level_name} 切換到 {logging.getLevelName(new_level)}")
                logger.setLevel(new_level)

    @staticmethod
    def cleanup_logs(
        log_dir: Optional[str] = None,
        module_name: Optional[str] = None,
        keep_days: Optional[int] = None,
        dry_run: bool = False,
        logger: Optional[logging.Logger] = None
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
            # 如果沒有提供 logger，創建一個簡單的
            logger = logging.getLogger("LogCleanup")
            if not logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                logger.addHandler(handler)
                logger.setLevel(logging.INFO)

        # 讀取環境變數，函數參數優先
        final_log_dir = log_dir if log_dir is not None else os.getenv("LOG_CLEANUP_LOG_DIR", "logs")
        final_module_name = module_name if module_name is not None else os.getenv("LOG_CLEANUP_MODULE_NAME", "")
        # 如果環境變數是空字串，視為 None (清理所有模組)
        if final_module_name == "":
            final_module_name = None

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

        # Dry run: 函數參數優先，否則讀取環境變數
        final_dry_run = dry_run
        if not final_dry_run: # 只有當函數參數沒設為 True 時，才檢查環境變數
            dry_run_env = os.getenv("LOG_CLEANUP_DRY_RUN", "false").lower()
            final_dry_run = dry_run_env in ["true", "1", "yes"]

        project_root = "/app"
        log_dir_path = os.path.join(project_root, final_log_dir)

        if not os.path.isdir(log_dir_path):
            logger.error(f"日誌目錄不存在: {log_dir_path}")
            raise FileNotFoundError(f"日誌目錄不存在: {log_dir_path}")

        logger.info(f"{'Dry run: ' if final_dry_run else ''}開始清理日誌目錄: {log_dir_path}")
        if final_module_name:
            logger.info(f"目標模組: {final_module_name}")
        if final_keep_days is not None:
            logger.info(f"保留天數: {final_keep_days}")
        else:
             logger.info("未設置保留天數，將刪除所有符合條件的日誌。")

        # --- 以下邏輯與之前類似，使用 final_xxx 變數 ---
        timestamp_pattern = re.compile(r"_(\d{8}_\d{6})\.log$")
        files_to_delete = []
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(days=final_keep_days) if final_keep_days is not None else None

        try:
            for filename in os.listdir(log_dir_path):
                file_path = os.path.join(log_dir_path, filename)

                if not os.path.isfile(file_path) or not filename.endswith(".log"):
                    continue

                if final_module_name and not filename.startswith(final_module_name + "_"):
                    continue

                match = timestamp_pattern.search(filename)
                if not match:
                    # logger.debug(f"Skipping file with non-matching format: {filename}") # 減少囉嗦程度
                    continue

                timestamp_str = match.group(1)
                try:
                    naive_dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    taipei_tz = pytz.timezone("Asia/Taipei") # 保持與 setup_logger 一致
                    local_dt = taipei_tz.localize(naive_dt)
                    file_time_utc = local_dt.astimezone(timezone.utc)

                    if cutoff_time and file_time_utc >= cutoff_time:
                        # logger.debug(f"Keeping newer file: {filename} (Time: {file_time_utc})")
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
