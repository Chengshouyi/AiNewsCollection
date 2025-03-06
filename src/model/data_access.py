import os
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime, UniqueConstraint, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()

class Article(Base):
    __tablename__ = 'articles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    summary = Column(String)
    link = Column(String, unique=True)
    content = Column(String)
    published_at = Column(DateTime)
    source = Column(String)

class DataAccess:
    def __init__(self, db_path=None):
        try:
            # 確定資料庫路徑和 URL
            if db_path is None:
                # 使用環境變數或預設路徑
                db_path = os.getenv('DATABASE_PATH', '/workspace/data/news.db')
                db_url = f"sqlite:///{db_path}"
            else:
                # 使用提供的路徑
                if db_path.startswith('sqlite:///:memory:'):
                    # 記憶體資料庫
                    db_url = db_path
                else:
                    # 檔案資料庫
                    if db_path.startswith('sqlite:///'):
                        file_path = db_path
                    else:
                        file_path = f"sqlite:///{db_path}"
                        db_path = file_path.replace('sqlite:///', '')
                    db_url = file_path
            
            # 僅對檔案資料庫，確保目錄存在
            if not db_url.startswith('sqlite:///:memory:'):
                file_path = db_url.replace('sqlite:///', '')
                db_dir = os.path.dirname(file_path)
                if db_dir:  # 確保目錄名稱非空
                    os.makedirs(db_dir, exist_ok=True)
            
            # 建立引擎
            self.engine = create_engine(db_url)
            # 驗證連接 - 早期失敗
            self.verify_connection()
            # 建立 session
            self.Session = sessionmaker(bind=self.engine)

        except SQLAlchemyError as e:
            error_msg = f"資料庫連接或初始化錯誤: {e}"
            print(error_msg)
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = f"一般初始化錯誤: {e}"
            print(error_msg)
            raise RuntimeError(error_msg) from e
        
    def verify_connection(self):
        """驗證資料庫連接，如果失敗則拋出異常"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except SQLAlchemyError as e:
            raise SQLAlchemyError(f"資料庫連接驗證失敗: {e}") from e
            
    def check_connection(self):
        """檢查資料庫連接狀態，返回布林值
        
        可在連接創建後的任何時間調用此方法以檢查連接狀態
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def create_tables(self):
        Base.metadata.create_all(self.engine)


    def insert_article(self, article_data):
        session = self.Session()
        try:
            # 如果傳入的是字典，轉換為 Article 實例
            if isinstance(article_data, dict):
                article = Article(**article_data)
            else:
                # 如果已經是 Article 實例，直接使用
                article = article_data

            # 檢查是否已存在相同連結的文章
            existing_article = session.query(Article).filter_by(link=article.link).first()
            
            if not existing_article:
                # 如果不存在，直接添加文章實例
                session.add(article)
                session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()



    def get_all_articles(self):
        session = self.Session()
        try:
            articles = session.query(Article).all()
            # 將 SQLAlchemy 模型實例轉換為字典
            return [
                {
                    "id": article.id, 
                    "title": article.title, 
                    "summary": article.summary,
                    "link": article.link,
                    "content": article.content,
                    "published_at": str(article.published_at),
                    "source": article.source
                } for article in articles
            ]
        finally:
            session.close()

    def get_article_by_id(self, article_id):
        session = self.Session()
        try:
            article = session.query(Article).filter_by(id=article_id).first()
            if article:
                return {
                    "id": article.id, 
                    "title": article.title, 
                    "summary": article.summary,
                    "link": article.link,
                    "content": article.content,
                    "published_at": str(article.published_at),
                    "source": article.source
                }
            return None
        finally:
            session.close()

    
    