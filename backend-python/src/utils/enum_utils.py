import enum
import json

class EnumEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, enum.Enum):
            # 如果是枚舉成員，返回它的值
            return obj.value
        # 否則，使用預設的編碼器
        return json.JSONEncoder.default(self, obj)
    
class TaskStatus(enum.Enum):
    """執行狀態枚舉"""

    INIT = "init"  # 初始化
    RUNNING = "running"  # 執行中
    COMPLETED = "completed"  # 完成
    FAILED = "failed"  # 失敗
    CANCELING = "canceling"  # 取消中
    CANCELLED = "cancelled"  # 取消
    UNKNOWN = "unknown"  # 未知


class ScrapePhase(enum.Enum):
    """爬取階段枚舉"""

    INIT = "init"  # 初始化
    LINK_COLLECTION = "link_collection"  # 連結收集階段
    CONTENT_SCRAPING = "content_scraping"  # 內容爬取階段
    FAILED = "failed"  # 失敗
    SAVE_TO_CSV = "save_to_csv"  # 保存到CSV
    SAVE_TO_DATABASE = "save_to_database"  # 保存到資料庫
    COMPLETED = "completed"  # 完成
    CANCELLED = "cancelled"  # 取消
    UNKNOWN = "unknown"  # 未知


class ScrapeMode(enum.Enum):
    """抓取模式枚舉"""

    LINKS_ONLY = "links_only"  # 僅抓取連結
    CONTENT_ONLY = "content_only"  # 僅抓取內容(從已有連結)
    FULL_SCRAPE = "full_scrape"  # 連結與內容一起抓取


class ArticleScrapeStatus(enum.Enum):
    PENDING = "pending"  # 等待爬取
    LINK_SAVED = "link_saved"  # 連結已保存
    PARTIAL_SAVED = "partial_saved"  # 部分保存
    CONTENT_SCRAPED = "content_scraped"  # 內容已爬取
    FAILED = "failed"  # 爬取失敗
