import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from contextlib import contextmanager
from typing import Optional, Dict, Any, List
from model.models import Article, Base
# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DataAccess:
    def __init__(self, db_path: Optional[str] = None) -> None:
        try:
            # 確定及設定資料庫路徑和 URL
            db_url = self._get_db_url(db_path)
            # 建立引擎
            self.engine = create_engine(db_url)
            Base.metadata.create_all(self.engine)
            # 驗證連接 - 早期失敗
            self._verify_connection()  # 修正為正確的方法名稱
        except SQLAlchemyError as e:
            error_msg = f"資料庫連接或初始化錯誤: {e}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = f"一般初始化錯誤: {e}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e

    @contextmanager
    def _session_scope(self):
        session = Session(self.engine)
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            error_msg = f"資料庫操作失敗: {e}"
            logger.error(error_msg, exc_info=True)
            session.rollback()
            raise RuntimeError(error_msg) from e
        finally:
            session.close()

    def _get_db_url(self, db_path: Optional[str] = None) -> str:
        try:
            # 確定資料庫路徑
            if db_path is None:
                db_path = os.getenv('DATABASE_PATH', '/workspace/data/news.db')
            if db_path.startswith('sqlite:///:memory:'):
                db_url = db_path
            else:
                # 確定資料庫路徑格式
                if not db_path.startswith('sqlite:///'):
                    db_path = f"sqlite:///{db_path}"
                file_path = db_path.replace('sqlite:///', '')
                db_dir = os.path.dirname(file_path)
                # 確定資料庫路徑是否存在
                if db_dir:
                    os.makedirs(db_dir, exist_ok=True)
                db_url = db_path
            return db_url
        except (FileNotFoundError, OSError) as e:
            error_msg = f"資料庫路徑錯誤: {e}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = f"一般初始化錯誤: {e}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e

    def _verify_connection(self) -> None:
        try:
            # 驗證連接
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except SQLAlchemyError as e:
            error_msg = f"資料庫連接驗證失敗: {e}"
            logger.error(error_msg, exc_info=True)
            raise SQLAlchemyError(error_msg) from e

    def _check_connection(self) -> bool:
        try:
            # 檢查連接
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError as e:
            logger.error(f"資料庫連接檢查失敗: {e}", exc_info=True)
            return False
    def _db_base_to_dict(self, base: Base) -> Dict[str, Any]:
        try:
            return {
                "id": getattr(base, "id", None),
                "created_at": getattr(base, "created_at", None).strftime('%Y-%m-%d %H:%M:%S') if hasattr(base, "created_at") and getattr(base, "created_at") else None,
                "updated_at": getattr(base, "updated_at", None).strftime('%Y-%m-%d %H:%M:%S') if hasattr(base, "updated_at") and getattr(base, "updated_at") else None
            }
        except AttributeError as e:
            error_msg = f"轉換資料庫物件為字典失敗: {e}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e

            
    def _article_to_dict(self, article: Article) -> Dict[str, Any]:
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
        except AttributeError as e:  # 捕獲更具體的異常
            error_msg = f"轉換文章為字典失敗 (AttributeError): {e}, 文章ID: {article.id if hasattr(article, 'id') else 'N/A'}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e
        except TypeError as e:
            error_msg = f"轉換文章為字典失敗 (TypeError): {e}, 文章ID: {article.id if hasattr(article, 'id') else 'N/A'}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = f"轉換文章為字典失敗 (Exception): {e}, 文章ID: {article.id if hasattr(article, 'id') else 'N/A'}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e
        
    def create_tables(self) -> None:
        try:
            # 建立資料表
            Base.metadata.create_all(self.engine)
        except SQLAlchemyError as e:
            error_msg = f"資料表建立失敗: {e}"
            logger.error(error_msg, exc_info=True)
            raise SQLAlchemyError(error_msg) from e


    def insert_article(self, article_data: Dict[str, Any]) -> None:
        with self._session_scope() as session:
            try:
                # 確認文章資料格式
                if isinstance(article_data, dict):
                    article = Article(**article_data)
                else:
                    article = article_data

                if article.link is None or article.link.strip() == '':
                    raise ValueError("文章連結不能為空")

                # 確認文章是否已存在
                existing_article = session.query(Article).filter_by(link=article.link).first()
                if not existing_article:
                    session.add(article)
                    session.commit()
            except Exception as e:
                # 回復資料庫狀態
                session.rollback()
                error_msg = f"插入文章失敗: {e}"
                logger.error(error_msg, exc_info=True)
                raise RuntimeError(error_msg) from e

    def get_all_articles(self) -> List[Dict[str, Any]]:
        try:
            with self._session_scope() as session:
                # 取得所有文章
                articles = session.query(Article).all()
                # 轉換為字典
                return [self._article_to_dict(article) for article in articles]
        except Exception as e:
            error_msg = f"取得所有文章失敗: {e}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e

    def get_article_by_id(self, article_id: int) -> Optional[Dict[str, Any]]:
        try:
            with self._session_scope() as session:
                # 取得指定文章
                article = session.query(Article).filter_by(id=article_id).first()
                # 確認文章是否存在
                if article:
                    # 轉換為字典
                    return self._article_to_dict(article)
                return None
        except Exception as e:
            error_msg = f"取得指定文章失敗: {e}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e


