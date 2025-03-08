import logging
from typing import Optional, Dict, Any, List, TypeVar, Type
from .database_manager import DatabaseManager
from .repository import Repository
from .models import Article, Base
from datetime import datetime
from contextlib import contextmanager

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 通用類型變數，用於泛型方法
T = TypeVar('T', bound=Base)

class ArticleService:
    """文章服務，提供文章相關業務邏輯"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    # 增加裝飾器來包裝通用的 session 與 repo 操作
    @contextmanager
    def _get_repository(self, model_class: Type[T]):
        """取得儲存庫的上下文管理器"""
        with self.db_manager.session_scope() as session:
            repo = Repository(session, model_class)
            try:
                yield repo, session
            except Exception as e:
                error_msg = f"儲存庫操作錯誤: {e}"
                logger.error(error_msg, exc_info=True)
                session.rollback()
                raise
    
    def insert_article(self, article_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """創建新文章"""
        try:
            # 添加必要的欄位
            now = datetime.now()
            article_data.update({
                'created_at': now,
            })
            
            # 檢查文章連結是否為空
            if not Article.verify_insert_data(article_data):
                logger.error(f"文章資料驗證失敗: {article_data}")
                return None
            
            with self._get_repository(Article) as (repo, session):
                # 檢查文章是否已存在
                if not repo.exists(link=article_data['link']):
                    article = repo.create(**article_data)
                    session.commit()
                    return self._article_to_dict(article)
                else:
                    error_msg = f"文章已存在: {article_data['link']}"
                    logger.warning(error_msg)  # 改用 warning 級別，因為這不是嚴重錯誤
                    return None
        except Exception as e:
            error_msg = f"創建文章失敗: {e}"
            logger.error(error_msg, exc_info=True)
            return None

    def get_all_articles(self) -> List[Dict[str, Any]]:
        """獲取所有文章"""
        try:
            with self._get_repository(Article) as (repo, _):
                articles = repo.get_all()
                # 使用列表推導式簡化轉換過程，並確保返回類型為 List[Dict[str, Any]]
                return [article_dict for article in articles 
                        if (article_dict := self._article_to_dict(article)) is not None]
        except Exception as e:
            error_msg = f"獲取所有文章失敗: {e}"
            logger.error(error_msg, exc_info=True)
            return []
    
    def get_article_by_id(self, article_id: int) -> Optional[Dict[str, Any]]:
        """根據ID獲取文章"""
        if not isinstance(article_id, int) or article_id <= 0:
            logger.error(f"無效的文章ID: {article_id}")
            return None
            
        try:
            with self._get_repository(Article) as (repo, _):
                article = repo.get_by_id(article_id)
                return self._article_to_dict(article) if article else None
        except Exception as e:
            error_msg = f"獲取文章失敗，ID={article_id}: {e}"
            logger.error(error_msg, exc_info=True)
            return None
                
    def update_article(self, article_id: int, article_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新文章"""
        # 驗證輸入
        if not isinstance(article_id, int) or article_id <= 0:
            logger.error(f"無效的文章ID: {article_id}")
            return None
            
        if not article_data:
            logger.error("更新資料為空")
            return None
            
        try:
            # 自動更新 updated_at 欄位
            article_data['updated_at'] = datetime.now()
            
            with self._get_repository(Article) as (repo, session):
                article = repo.get_by_id(article_id)
                
                if not article or not Article.verify_update_data(article_data):
                    return None
                    
                article = repo.update(article, **article_data)
                session.commit()
                return self._article_to_dict(article)
        except Exception as e:
            error_msg = f"更新文章失敗，ID={article_id}: {e}"
            logger.error(error_msg, exc_info=True)
            return None
    
    def delete_article(self, article_id: int) -> bool:
        """刪除文章"""        
        if not isinstance(article_id, int) or article_id <= 0:
            logger.error(f"無效的文章ID: {article_id}")
            return False
            
        try:
            with self._get_repository(Article) as (repo, session):
                article = repo.get_by_id(article_id)
                
                if not article:
                    logger.warning(f"欲刪除的文章不存在，ID={article_id}")
                    return False
                    
                repo.delete(article)
                session.commit()
                logger.info(f"成功刪除文章，ID={article_id}")
                return True
        except Exception as e:
            error_msg = f"刪除文章失敗，ID={article_id}: {e}"
            logger.error(error_msg, exc_info=True)
            return False
    
    def _article_to_dict(self, article) -> Optional[Dict[str, Any]]:
        """將Article對象轉換為字典"""
        if not article:
            return None
            
        try:
            return {
                "id": article.id,
                "title": article.title,
                "summary": article.summary,
                "link": article.link,
                "content": article.content,
                "published_at": article.published_at,
                "source": article.source,
                "created_at": article.created_at,
                "updated_at": article.updated_at,
            }
        except Exception as e:
            article_id = getattr(article, 'id', 'N/A')
            error_msg = f"轉換文章為字典失敗: {e}, 文章ID: {article_id}"
            logger.error(error_msg, exc_info=True)
            return None