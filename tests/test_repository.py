import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.model.models import Article, Base
from src.model.repository import Repository
from datetime import datetime

@pytest.fixture
def session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_repository_create(session):
    repo = Repository(session, Article)
    article_data = {
        "title": "測試文章",
        "link": "https://test.com/article",
        "published_at": datetime.now(),
        "created_at": datetime.now()
    }
    
    article = repo.create(**article_data)
    session.commit()
    
    assert article.id is not None
    assert article.title == "測試文章"

def test_repository_update(session):
    repo = Repository(session, Article)
    article_data = {
        "title": "測試文章",
        "link": "https://test.com/article",
        "published_at": datetime.now(),
        "created_at": datetime.now()
    }
    
    article = repo.create(**article_data)
    session.commit()
    
    updated_article = repo.update(article, title="更新後的文章")
    session.commit()
    
    assert updated_article.title == "更新後的文章"

def test_repository_delete(session):
    repo = Repository(session, Article)
    article_data = {
        "title": "測試文章",
        "link": "https://test.com/article",
        "published_at": datetime.now(),
        "created_at": datetime.now()
    }
    
    article = repo.create(**article_data)
    session.commit()
    
    repo.delete(article)
    session.commit()
    
    assert repo.get_by_id(article.id) is None

def test_repository_find_methods(session):
    repo = Repository(session, Article)
    
    # 準備測試資料
    article_data1 = {
        "title": "測試文章1",
        "link": "https://test.com/article1",
        "published_at": datetime.now(),
        "created_at": datetime.now()
    }
    
    article_data2 = {
        "title": "測試文章2",
        "link": "https://test.com/article2",
        "published_at": datetime.now(),
        "created_at": datetime.now()
    }
    
    # 創建文章
    article1 = repo.create(**article_data1)
    article2 = repo.create(**article_data2)
    session.commit()
    
    # 測試 find_by 方法
    found_articles = repo.find_by(title="測試文章1")
    assert len(found_articles) == 1
    assert found_articles[0].title == "測試文章1"
    
    # 測試 find_one_by 方法
    found_article = repo.find_one_by(link="https://test.com/article2")
    assert found_article is not None
    assert found_article.title == "測試文章2"
    
    # 測試不存在的查詢
    not_found = repo.find_by(title="不存在的文章")
    assert len(not_found) == 0
