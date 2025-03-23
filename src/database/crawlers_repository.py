from .base_repository import BaseRepository
from src.models.crawlers_model import Crawlers
from typing import List
from datetime import datetime

class CrawlersRepository(BaseRepository['Crawlers']):
    """Crawlers 特定的Repository"""
    
    def find_active_crawlers(self) -> List['Crawlers']:
        """查詢活動中的爬蟲"""
        return self.session.query(self.model_class).filter_by(is_active=True).all()
    
    def find_by_crawler_name(self, crawler_name: str) -> List['Crawlers']:
        """根據爬蟲名稱模糊查詢，回傳匹配的列表"""
        return self.session.query(self.model_class).filter(
            self.model_class.crawler_name.like(f"%{crawler_name}%")
        ).all()
    
    def find_pending_crawlers(self, current_time: datetime) -> List['Crawlers']:
        """查找需要執行的爬蟲（已激活且超過上次爬蟲時間+間隔的爬蟲）"""
        query = self.session.query(self.model_class).filter(
            self.model_class.is_active == True
        )
        
        # 篩選出從未執行過（last_crawl_time為None）或超過間隔時間的爬蟲
        pending_crawlers = []
        for crawler in query.all():
            # 如果從未執行過，則需要爬取
            if crawler.last_crawl_time is None:
                pending_crawlers.append(crawler)
                continue
                
            # 檢查是否超過了設定的爬蟲間隔時間
            # 間隔單位是分鐘，轉換為秒
            interval_seconds = crawler.crawl_interval * 60
            time_diff = (current_time - crawler.last_crawl_time).total_seconds()
            
            if time_diff >= interval_seconds:
                pending_crawlers.append(crawler)
                
        return pending_crawlers
    
    def update_last_crawl_time(self, crawler_id: int, new_time: datetime) -> bool:
        """更新爬蟲最後執行時間"""
        crawler = self.get_by_id(crawler_id)
        if not crawler:
            return False
            
        crawler.last_crawl_time = new_time
        crawler.updated_at = datetime.now()
        self.session.commit()
        return True
        
    def toggle_active_status(self, crawler_id: int) -> bool:
        """切換爬蟲活躍狀態"""
        crawler = self.get_by_id(crawler_id)
        if not crawler:
            return False
            
        # 切換狀態
        crawler.is_active = not crawler.is_active
        crawler.updated_at = datetime.now()
        self.session.commit()
        return True
    
    def get_sorted_by_interval(self) -> List['Crawlers']:
        """按爬取間隔排序的爬蟲設定"""
        return self.session.query(self.model_class).order_by(
            self.model_class.crawl_interval
        ).all()