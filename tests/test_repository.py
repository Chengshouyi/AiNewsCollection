import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.model.models import Article, Base
from src.model.repository import Repository
from datetime import datetime
from tests import create_database_session

class TestRepository:
    
    @pytest.fixture
    def repo(self, create_database_session):
        return Repository(create_database_session, Article)
    
    @pytest.fixture
    def sample_article_data(self):
        return {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": datetime.now(),
            "created_at": datetime.now()
        }
    
    def test_repository_create(self, create_database_session, repo, sample_article_data):
        article = repo.create(**sample_article_data)
        create_database_session.commit()
        
        assert article.id is not None
        assert article.title == "測試文章"
    
    def test_repository_update(self, create_database_session, repo, sample_article_data):
        article = repo.create(**sample_article_data)
        create_database_session.commit()
        
        updated_article = repo.update(article, title="更新後的文章")
        create_database_session.commit()
        
        assert updated_article.title == "更新後的文章"
    
    def test_repository_delete(self, create_database_session, repo, sample_article_data):
        article = repo.create(**sample_article_data)
        create_database_session.commit()
        
        repo.delete(article)
        create_database_session.commit()
        
        assert repo.get_by_id(article.id) is None
    
    def test_repository_find_methods(self, create_database_session, repo):
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
        create_database_session.commit()
        
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
    
    def test_repository_get_all(self, create_database_session, repo):
        # 創建多篇文章用於測試排序和分頁
        for i in range(5):
            repo.create(
                title=f"文章{i}",
                link=f"https://test.com/article{i}",
                published_at=datetime.now(),
                created_at=datetime.now()
            )
        create_database_session.commit()
        
        # 測試基本查詢
        all_articles = repo.get_all()
        assert len(all_articles) == 5
        
        # 測試分頁
        paged_articles = repo.get_all(limit=2, offset=1)
        assert len(paged_articles) == 2
        
        # 測試排序
        sorted_articles = repo.get_all(sort_by="title")
        for i in range(len(sorted_articles) - 1):
            assert sorted_articles[i].title <= sorted_articles[i + 1].title
        
        # 測試倒序排序
        desc_sorted_articles = repo.get_all(sort_by="title", sort_desc=True)
        for i in range(len(desc_sorted_articles) - 1):
            assert desc_sorted_articles[i].title >= desc_sorted_articles[i + 1].title
    
    def test_repository_exists(self, create_database_session, repo, sample_article_data):
        article = repo.create(**sample_article_data)
        create_database_session.commit()
        
        assert repo.exists(title="測試文章") is True
        assert repo.exists(title="不存在的文章") is False