import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Type, TypeVar, Generic
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.decl_api import DeclarativeBase

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

T = TypeVar('T', bound=DeclarativeBase)


class Repository(Generic[T]):
    """通用Repository模式實現，用於基本CRUD操作"""
    
    def __init__(self, session: Session, model_class: Type[T]):
        self.session = session
        self.model_class = model_class
        
    def get_by_id(self, id: int) -> Optional[T]:
        """根據ID獲取實體"""
        return self.session.query(self.model_class).filter_by(id=id).first()
    
    def get_all(self) -> List[T]:
        """獲取所有實體"""
        return self.session.query(self.model_class).all()
    
    def find_by(self, **kwargs) -> List[T]:
        """根據條件查詢實體"""
        return self.session.query(self.model_class).filter_by(**kwargs).all()
    
    def find_one_by(self, **kwargs) -> Optional[T]:
        """根據條件查詢單個實體"""
        return self.session.query(self.model_class).filter_by(**kwargs).first()
    
    def create(self, **kwargs) -> T:
        """創建新實體"""
        entity = self.model_class(**kwargs)
        self.session.add(entity)
        return entity
    
    def update(self, entity: T, **kwargs) -> T:
        """更新實體"""
        for key, value in kwargs.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        return entity
    
    def delete(self, entity: T) -> None:
        """刪除實體"""
        self.session.delete(entity)
    
    def exists(self, **kwargs) -> bool:
        """檢查是否存在滿足條件的實體"""
        return self.session.query(self.model_class).filter_by(**kwargs).first() is not None


class DatabaseManager:
    """數據庫連接和會話管理"""
    
    def __init__(self, db_path: Optional[str] = None):
        try:
            self.db_url = self._get_db_url(db_path)
            self.engine = create_engine(self.db_url)
            self.Session = sessionmaker(bind=self.engine)
            self._verify_connection()
        except Exception as e:
            error_msg = f"數據庫初始化錯誤: {e}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e
    
    def _get_db_url(self, db_path: Optional[str] = None) -> str:
        """獲取數據庫URL"""
        if db_path is None:
            db_path = os.getenv('DATABASE_PATH', '/workspace/data/news.db')
            
        if db_path.startswith('sqlite:///:memory:'):
            return db_path
        
        if not db_path.startswith('sqlite:///'):
            db_path = f"sqlite:///{db_path}"
            
        file_path = db_path.replace('sqlite:///', '')
        db_dir = os.path.dirname(file_path)
        
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
            
        return db_path
    
    def _verify_connection(self) -> None:
        """驗證數據庫連接"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except SQLAlchemyError as e:
            error_msg = f"數據庫連接驗證失敗: {e}"
            logger.error(error_msg, exc_info=True)
            raise SQLAlchemyError(error_msg) from e
    
    @contextmanager
    def session_scope(self):
        """提供事務範圍的會話上下文管理器"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            error_msg = f"數據庫操作失敗: {e}"
            logger.error(error_msg, exc_info=True)
            raise
        finally:
            session.close()
    
    def create_tables(self, base: Type[DeclarativeBase]) -> None:
        """創建所有表格"""
        try:
            base.metadata.create_all(self.engine)
        except SQLAlchemyError as e:
            error_msg = f"創建表格失敗: {e}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e


class ArticleService:
    """文章服務，提供文章相關業務邏輯"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        
    def get_all_articles(self) -> List[Dict[str, Any]]:
        """獲取所有文章"""
        from model.models import Article
        
        with self.db_manager.session_scope() as session:
            repo = Repository(session, Article)
            articles = repo.get_all()
            return [self._article_to_dict(article) for article in articles]
    
    def get_article_by_id(self, article_id: int) -> Optional[Dict[str, Any]]:
        """根據ID獲取文章"""
        from model.models import Article
        
        with self.db_manager.session_scope() as session:
            repo = Repository(session, Article)
            article = repo.get_by_id(article_id)
            if article:
                return self._article_to_dict(article)
            return None
    
    def create_article(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """創建新文章"""
        from model.models import Article
        
        with self.db_manager.session_scope() as session:
            repo = Repository(session, Article)
            
            # 檢查文章是否已存在
            if not article_data.get('link'):
                raise ValueError("文章連結不能為空")
                
            if repo.exists(link=article_data['link']):
                raise ValueError(f"文章已存在: {article_data['link']}")
                
            article = repo.create(**article_data)
            session.commit()
            return self._article_to_dict(article)
    
    def update_article(self, article_id: int, article_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新文章"""
        from model.models import Article
        
        with self.db_manager.session_scope() as session:
            repo = Repository(session, Article)
            article = repo.get_by_id(article_id)
            
            if not article:
                return None
                
            article = repo.update(article, **article_data)
            session.commit()
            return self._article_to_dict(article)
    
    def delete_article(self, article_id: int) -> bool:
        """刪除文章"""
        from model.models import Article
        
        with self.db_manager.session_scope() as session:
            repo = Repository(session, Article)
            article = repo.get_by_id(article_id)
            
            if not article:
                return False
                
            repo.delete(article)
            session.commit()
            return True
    
    def _article_to_dict(self, article) -> Dict[str, Any]:
        """將Article對象轉換為字典"""
        try:
            return {
                "id": article.id,
                "title": article.title,
                "summary": article.summary,
                "link": article.link,
                "content": article.content,
                "published_at": article.published_at.strftime('%Y-%m-%d %H:%M:%S') if article.published_at else None,
                "source": article.source
            }
        except Exception as e:
            error_msg = f"轉換文章為字典失敗: {e}, 文章ID: {article.id if hasattr(article, 'id') else 'N/A'}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e


# 使用示例
def create_app():
    """創建應用實例，初始化數據庫和服務"""
    from model.models import Base
    
    db_manager = DatabaseManager()
    db_manager.create_tables(Base)
    
    article_service = ArticleService(db_manager)
    
    return {
        'db_manager': db_manager,
        'article_service': article_service
    }


# 簡單的使用示例
if __name__ == "__main__":
    app = create_app()
    article_service = app['article_service']
    
    # 創建文章
    article = article_service.create_article({
        'title': '測試文章',
        'summary': '這是一個測試摘要',
        'link': 'https://example.com/test',
        'content': '這是測試內容',
        'published_at': datetime.now(),
        'source': '測試來源'
    })
    
    print(f"創建的文章: {article}")
    
    # 獲取所有文章
    articles = article_service.get_all_articles()
    print(f"所有文章: {articles}")
