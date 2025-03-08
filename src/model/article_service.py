import logging
from typing import Optional, Dict, Any, List
from .database_manager import DatabaseManager
from .repository import Repository
from .models import Article
# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ArticleService:
    """文章服務，提供文章相關業務邏輯"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        
    def get_all_articles(self) -> List[Dict[str, Any]]:
        """獲取所有文章"""
        with self.db_manager.session_scope() as session:
            repo = Repository(session, Article)
            articles = repo.get_all()
            # 過濾掉 None 值並轉換為字典列表
            article_dicts = []
            for article in articles:
                if article:
                    article_dicts.append(self._article_to_dict(article))
            return article_dicts
    
    def get_article_by_id(self, article_id: int) -> Optional[Dict[str, Any]]:
        """根據ID獲取文章"""
        with self.db_manager.session_scope() as session:
            repo = Repository(session, Article)
            article = repo.get_by_id(article_id)
            if article:
                return self._article_to_dict(article)
            return None
    
    def create_article(
        self, 
        article_data: Dict[str, Any]
        ) -> Optional[Dict[str, Any]]:
        """創建新文章"""
        with self.db_manager.session_scope() as session:
            repo = Repository(session, Article)
            
            # 檢查文章連結是否為空
            if not article_data.get('link'):
                error_msg = f"文章連結不能為空"
                logger.error(error_msg, exc_info=True)
                return None
            
            # 檢查文章是否已存在
            if not repo.exists(link=article_data['link']):
                article = repo.create(**article_data)
                session.commit()
                return self._article_to_dict(article)
            else:
                error_msg = f"文章已存在: {article_data['link']}"
                logger.error(error_msg, exc_info=True)
                return None
    
                
    def update_article(
        self, 
        article_id: int, 
        article_data: Dict[str, Any]
        ) -> Optional[Dict[str, Any]]:
        """更新文章"""
        with self.db_manager.session_scope() as session:
            repo = Repository(session, Article)
            article = repo.get_by_id(article_id)
            
            if (not article 
                or not article_data 
                or not article_data.get('link')
                or not article_data.get('title')):
                return None
                
            article = repo.update(article, **article_data)
            session.commit()
            return self._article_to_dict(article)
    
    def delete_article(self, article_id: int) -> bool:
        """刪除文章"""        
        with self.db_manager.session_scope() as session:
            repo = Repository(session, Article)
            article = repo.get_by_id(article_id)
            
            if not article:
                return False
                
            repo.delete(article)
            session.commit()
            return True
    
    def _article_to_dict(self, article) -> Optional[Dict[str, Any]]:
        """將Article對象轉換為字典"""
        try:
            return {
                "id": article.id,
                "title": article.title,
                "summary": article.summary,
                "link": article.link,
                "content": article.content,
                "published_at": article.published_at
                                .strftime('%Y-%m-%d %H:%M:%S') 
                                if article.published_at else None,
                "source": article.source
            }
        except Exception as e:
            error_msg = f"轉換文章為字典失敗: {e}, \
                    文章ID: {article.id if hasattr(article, 'id') else 'N/A'}"
            logger.error(error_msg, exc_info=True)
            return None
