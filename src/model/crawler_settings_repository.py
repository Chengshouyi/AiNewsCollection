from .base_rerository import BaseRepository
from .crawler_settings_models import CrawlerSettings
from typing import Optional, List

class CrawlerSettingsRepository(BaseRepository['CrawlerSettings']):
    """CrawlerSettings 特定的Repository"""
    
    def find_active_crawlers(self) -> List['CrawlerSettings']:
        """查詢活動中的爬蟲"""
        return self.session.query(self.model_class).filter_by(is_active=True).all()
    
    def find_by_crawler_name(self, crawler_name: str) -> Optional['CrawlerSettings']:
        """根據爬蟲名稱查詢"""
        return self.session.query(self.model_class).filter_by(crawler_name=crawler_name).first()