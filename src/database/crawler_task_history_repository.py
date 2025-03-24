from .base_repository import BaseRepository
from src.models.crawler_task_history_model import CrawlerTaskHistory
from typing import List, Optional
from datetime import datetime, timedelta

class CrawlerTaskHistoryRepository(BaseRepository['CrawlerTaskHistory']):
    """CrawlerTaskHistory 特定的Repository"""
    
    def find_by_task_id(self, task_id: int) -> List['CrawlerTaskHistory']:
        """根據任務ID查詢相關的歷史記錄"""
        return self.session.query(self.model_class).filter_by(
            task_id=task_id
        ).all()
    
    def find_successful_histories(self) -> List['CrawlerTaskHistory']:
        """查詢所有成功的任務歷史記錄"""
        return self.session.query(self.model_class).filter_by(
            success=True
        ).all()
    
    def find_failed_histories(self) -> List['CrawlerTaskHistory']:
        """查詢所有失敗的任務歷史記錄"""
        return self.session.query(self.model_class).filter_by(
            success=False
        ).all()
    
    def find_histories_with_articles(self, min_articles: int = 1) -> List['CrawlerTaskHistory']:
        """查詢文章數量大於指定值的歷史記錄"""
        return self.session.query(self.model_class).filter(
            self.model_class.articles_count >= min_articles
        ).all()
    
    def find_histories_by_date_range(
        self, 
        start_date: Optional[datetime] = None, 
        end_date: Optional[datetime] = None
    ) -> List['CrawlerTaskHistory']:
        """根據日期範圍查詢歷史記錄"""
        query = self.session.query(self.model_class)
        
        if start_date:
            query = query.filter(self.model_class.start_time >= start_date)
        
        if end_date:
            query = query.filter(self.model_class.start_time <= end_date)
        
        return query.all()
    
    def get_total_articles_count(self, task_id: Optional[int] = None) -> int:
        """
        獲取總文章數量
        
        :param task_id: 可選的任務ID，如果提供則只計算該任務的文章數
        :return: 文章總數
        """
        query = self.session.query(self.model_class)
        
        if task_id is not None:
            query = query.filter_by(task_id=task_id)
        
        return sum(history.articles_count for history in query.all())
    
    def get_latest_history(self, task_id: int) -> Optional['CrawlerTaskHistory']:
        """
        獲取指定任務的最新歷史記錄
        
        :param task_id: 任務ID
        :return: 最新的歷史記錄，如果不存在則返回 None
        """
        return (
            self.session.query(self.model_class)
            .filter_by(task_id=task_id)
            .order_by(self.model_class.start_time.desc())
            .first()
        )
    
    def get_histories_older_than(self, days: int) -> List['CrawlerTaskHistory']:
        """
        獲取超過指定天數的歷史記錄
        
        :param days: 天數
        :return: 超過指定天數的歷史記錄列表
        """
        threshold_date = datetime.now() - timedelta(days=days)
        return (
            self.session.query(self.model_class)
            .filter(self.model_class.start_time < threshold_date)
            .all()
        )
    
    def update_history_status(
        self, 
        history_id: int, 
        success: bool, 
        message: Optional[str] = None, 
        articles_count: Optional[int] = None
    ) -> bool:
        """
        更新歷史記錄的狀態
        
        :param history_id: 歷史記錄ID
        :param success: 是否成功
        :param message: 可選的訊息
        :param articles_count: 可選的文章數量
        :return: 是否更新成功
        """
        history = self.get_by_id(history_id)
        if not history:
            return False
        
        history.success = success
        history.end_time = datetime.now()
        
        if message is not None:
            history.message = message
        
        if articles_count is not None:
            history.articles_count = articles_count
        
        self.session.commit()
        return True 