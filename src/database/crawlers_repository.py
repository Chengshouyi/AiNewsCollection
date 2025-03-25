from .base_repository import BaseRepository
from src.models.crawlers_model import Crawlers
from src.models.crawlers_schema import CrawlersCreateSchema, CrawlersUpdateSchema
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import  func, desc, asc
from src.error.errors import DatabaseOperationError

class CrawlersRepository(BaseRepository['Crawlers']):
    """Crawlers 特定的Repository"""
    
    def find_active_crawlers(self) -> List['Crawlers']:
        """查詢活動中的爬蟲"""
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter_by(is_active=True).all()
        )
    
    def find_by_crawler_name(self, crawler_name: str) -> List['Crawlers']:
        """根據爬蟲名稱模糊查詢，回傳匹配的列表"""
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter(
                self.model_class.crawler_name.like(f"%{crawler_name}%")
            ).all()
        )
    
    def find_pending_crawlers(self, current_time: Optional[datetime] = None) -> List['Crawlers']:
        """查找需要執行的爬蟲（已激活且超過上次爬蟲時間+間隔的爬蟲）
        
        Args:
            current_time: 當前時間，默認為UTC現在時間
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        return self.execute_query(lambda: self._get_pending_crawlers(current_time))
    
    def _get_pending_crawlers(self, current_time: datetime) -> List['Crawlers']:
        """內部方法：獲取需要執行的爬蟲"""
        # 確保 current_time 是 UTC aware
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        
        # 獲取所有啟用的爬蟲
        active_crawlers = self.session.query(self.model_class).filter(
            self.model_class.is_active == True
        ).all()
        
        # 篩選出需要執行的爬蟲
        pending_crawlers = []
        for crawler in active_crawlers:
            # 從未執行過的爬蟲
            if crawler.last_crawl_time is None:
                pending_crawlers.append(crawler)
                continue
                
            # 確保 last_crawl_time 是 UTC aware
            last_crawl_time = crawler.last_crawl_time
            if last_crawl_time.tzinfo is None:
                last_crawl_time = last_crawl_time.replace(tzinfo=timezone.utc)
            
            # 檢查是否超過了設定的爬蟲間隔時間（間隔單位是分鐘）
            interval_seconds = crawler.crawl_interval * 60
            time_diff = (current_time - last_crawl_time).total_seconds()
            
            if time_diff >= interval_seconds:
                pending_crawlers.append(crawler)
                
        return pending_crawlers
    
    def update_last_crawl_time(self, crawler_id: int, new_time: Optional[datetime] = None) -> bool:
        """更新爬蟲最後執行時間
        
        Args:
            crawler_id: 爬蟲ID
            new_time: 新的爬取時間，默認為None，將使用當前UTC時間
        """
        if new_time is None:
            new_time = datetime.now(timezone.utc)
        return self.execute_query(lambda: self._update_last_crawl_time(crawler_id, new_time))
    
    def _update_last_crawl_time(self, crawler_id: int, new_time: datetime) -> bool:
        """內部方法：更新爬蟲最後執行時間"""
        crawler = self.get_by_id(crawler_id)
        if not crawler:
            return False
            
        try:
            crawler.last_crawl_time = new_time
            crawler.updated_at = datetime.now(timezone.utc)
            self.session.flush()
            return True
        except Exception as e:
            self.session.rollback()
            raise DatabaseOperationError(f"更新爬蟲執行時間失敗: {str(e)}")
        
    def toggle_active_status(self, crawler_id: int) -> bool:
        """切換爬蟲活躍狀態"""
        return self.execute_query(lambda: self._toggle_active_status(crawler_id))
    
    def _toggle_active_status(self, crawler_id: int) -> bool:
        """內部方法：切換爬蟲活躍狀態"""
        crawler = self.get_by_id(crawler_id)
        if not crawler:
            return False
            
        try:
            # 切換狀態
            crawler.is_active = not crawler.is_active
            crawler.updated_at = datetime.now(timezone.utc)
            self.session.flush()
            return True
        except Exception as e:
            self.session.rollback()
            raise DatabaseOperationError(f"切換爬蟲狀態失敗: {str(e)}")
    
    def get_sorted_by_interval(self, descending: bool = False) -> List['Crawlers']:
        """按爬取間隔排序的爬蟲設定
        
        Args:
            descending: 是否降序排列，默認為升序
        """
        return self.execute_query(
            lambda: self.session.query(self.model_class).order_by(
                desc(self.model_class.crawl_interval) if descending else asc(self.model_class.crawl_interval)
            ).all()
        )
    
    def create_crawler(self, crawler_data: Dict[str, Any]) -> Crawlers:
        """使用模式驗證創建爬蟲"""
        return self.create(crawler_data, schema_class=CrawlersCreateSchema)
        
    def update_crawler(self, crawler_id: int, crawler_data: Dict[str, Any]) -> Optional[Crawlers]:
        """使用模式驗證更新爬蟲"""
        return self.update(crawler_id, crawler_data, schema_class=CrawlersUpdateSchema)
    
    def find_by_type(self, crawler_type: str) -> List[Crawlers]:
        """根據爬蟲類型查找爬蟲"""
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter(
                self.model_class.crawler_type == crawler_type
            ).all()
        )
    
    def find_by_target(self, target_pattern: str) -> List[Crawlers]:
        """根據爬取目標模糊查詢爬蟲"""
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter(
                self.model_class.scrape_target.like(f"%{target_pattern}%")
            ).all()
        )
    
    def get_crawler_statistics(self) -> Dict[str, Any]:
        """獲取爬蟲統計信息"""
        return self.execute_query(lambda: {
            "total": self.session.query(func.count(self.model_class.id)).scalar(),
            "active": self.session.query(func.count(self.model_class.id)).filter(
                self.model_class.is_active == True
            ).scalar(),
            "inactive": self.session.query(func.count(self.model_class.id)).filter(
                self.model_class.is_active == False
            ).scalar(),
            "by_type": self._get_type_statistics()
        })
    
    def _get_type_statistics(self) -> Dict[str, int]:
        """獲取各類型爬蟲數量統計"""
        result = {}
        type_counts = self.session.query(
            self.model_class.crawler_type,
            func.count(self.model_class.id)
        ).group_by(self.model_class.crawler_type).all()
        
        for crawler_type, count in type_counts:
            result[crawler_type] = count
            
        return result