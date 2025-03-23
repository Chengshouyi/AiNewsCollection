from .base_rerository import BaseRepository
from src.models.crawler_tasks_model import CrawlerTasks
from typing import List
from datetime import datetime

class CrawlerTasksRepository(BaseRepository['CrawlerTasks']):
    """CrawlerTasks 特定的Repository"""
    
    def find_by_crawler_id(self, crawler_id: int) -> List['CrawlerTasks']:
        """根據爬蟲ID查詢相關的任務"""
        return self.session.query(self.model_class).filter_by(
            crawler_id=crawler_id
        ).all()
    
    def find_auto_tasks(self) -> List['CrawlerTasks']:
        """查詢所有自動執行的任務"""
        return self.session.query(self.model_class).filter_by(
            is_auto=True
        ).all()
    
    def find_ai_only_tasks(self) -> List['CrawlerTasks']:
        """查詢所有僅收集AI相關的任務"""
        return self.session.query(self.model_class).filter_by(
            ai_only=True
        ).all()
    
    def find_tasks_by_crawler_and_auto(self, crawler_id: int, is_auto: bool) -> List['CrawlerTasks']:
        """根據爬蟲ID和自動執行狀態查詢任務"""
        return self.session.query(self.model_class).filter_by(
            crawler_id=crawler_id,
            is_auto=is_auto
        ).all()
    
    def toggle_auto_status(self, task_id: int) -> bool:
        """切換任務的自動執行狀態"""
        task = self.get_by_id(task_id)
        if not task:
            return False
            
        task.is_auto = not task.is_auto
        task.updated_at = datetime.now()
        self.session.commit()
        return True
    
    def toggle_ai_only_status(self, task_id: int) -> bool:
        """切換任務的AI收集狀態"""
        task = self.get_by_id(task_id)
        if not task:
            return False
            
        task.ai_only = not task.ai_only
        task.updated_at = datetime.now()
        self.session.commit()
        return True
    
    def update_notes(self, task_id: int, new_notes: str) -> bool:
        """更新任務備註"""
        task = self.get_by_id(task_id)
        if not task:
            return False
            
        task.notes = new_notes
        task.updated_at = datetime.now()
        self.session.commit()
        return True
    
    def find_tasks_with_notes(self) -> List['CrawlerTasks']:
        """查詢所有有備註的任務"""
        return self.session.query(self.model_class).filter(
            self.model_class.notes.isnot(None)
        ).all()
    
    def find_tasks_by_multiple_crawlers(self, crawler_ids: List[int]) -> List['CrawlerTasks']:
        """根據多個爬蟲ID查詢任務"""
        return self.session.query(self.model_class).filter(
            self.model_class.crawler_id.in_(crawler_ids)
        ).all()
    
    def get_tasks_count_by_crawler(self, crawler_id: int) -> int:
        """獲取特定爬蟲的任務數量"""
        return self.session.query(self.model_class).filter_by(
            crawler_id=crawler_id
        ).count() 