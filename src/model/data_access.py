import os
import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Table, MetaData, UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

class DataAccess:
    def __init__(self, db_path=None):
        try:
            # 如果沒有設定資料庫路徑，則使用預設路徑
            if db_path is None:
                db_path = os.getenv(
                    'DATABASE_PATH',
                    '/workspace/data/news.db'
                )
                os.makedirs(os.path.dirname(db_path), exist_ok=True)
                db_url = f"sqlite:///{db_path}"
                self.engine = create_engine(db_url)
            else:
                if not db_path.startswith('sqlite:///:memory:'):
                    db_dir = os.path.dirname(db_path.replace('sqlite:///', ''))
                    os.makedirs(db_dir, exist_ok=True)
        except Exception as e:
             # 如果沒有設定資料庫路徑，則拋出錯誤
            print(f"資料庫連接錯誤: {e}")
            raise e

        # 如果資料庫路徑不是記憶體資料庫，則建立資料庫目錄
        

        # 建立引擎  
        self.engine = create_engine(db_path)
        # 反射資料庫
        self.metadata = MetaData()

        # 定義文章表
        self.articles = Table('articles', self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('title', String, nullable=False),
            Column('summary', String),
            Column('link', String, nullable=False),
            Column('content', String),
            Column('publication_date', DateTime),
            Column('source', String),
            UniqueConstraint('link', name='uq_article_link')
        )

        # self.metadata.create_all(self.engine)  
        self.create_tables()
        # 建立 session
        self.session = sessionmaker(bind=self.engine)
        
        
        
    def create_tables(self):
        self.metadata.create_all(self.engine)


    def insert_article(self, article_data):
        pass

    def get_article_by_id(self, article_id):
        pass

    def get_all_articles(self):
        pass
    
    