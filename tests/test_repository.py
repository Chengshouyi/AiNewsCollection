import pytest
from src.model.base_models import Article, ValidationError as CustomValidationError
from src.model.repository import Repository
from datetime import datetime


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
        result = repo.create(**sample_article_data)
        repo.session.commit()
        
        assert result.id is not None
        assert result.title == "測試文章"
    

    def test_repository_update(self, create_database_session, repo, sample_article_data):
        result = repo.create(**sample_article_data)
        repo.session.commit()
        
        updated_article = repo.update(result, title="更新後的文章")
        repo.session.commit()
        
        assert updated_article.id is not None
        assert updated_article.title == "更新後的文章"
    
    def test_repository_delete(self, create_database_session, repo, sample_article_data):
        """測試刪除實體"""
        result = repo.create(**sample_article_data)
        repo.session.commit()
        
        assert repo.delete(result)
        repo.session.commit()
        
        assert repo.get_by_id(result.id) is None
    
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
        repo.create(**article_data1)
        repo.create(**article_data2)
        repo.session.commit()

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
        repo.session.commit()
        
        # 測試基本查詢
        result = repo.get_all()
        assert result is not None
        assert len(result) == 5
        
        # 測試分頁
        paged_result = repo.get_all(limit=2, offset=1)
        assert paged_result is not None
        assert len(paged_result) == 2
        
        # 測試排序
        sorted_result = repo.get_all(sort_by="title")
        assert sorted_result is not None
        for i in range(len(sorted_result) - 1):
            assert sorted_result[i].title <= sorted_result[i + 1].title
        
        # 測試倒序排序
        desc_sorted_result = repo.get_all(sort_by="title", sort_desc=True)
        assert desc_sorted_result is not None
        for i in range(len(desc_sorted_result) - 1):
            assert desc_sorted_result[i].title >= desc_sorted_result[i + 1].title
    
    def test_repository_exists(self, create_database_session, repo, sample_article_data):
        repo.create(**sample_article_data)
        repo.session.commit()
        
        assert repo.exists(title="測試文章")
        assert not repo.exists(title="不存在的文章")

    def test_repository_update_with_validation(self,  repo, sample_article_data):
        """測試更新時的驗證"""
        result = repo.create(**sample_article_data)
        repo.session.commit()
        
        # 測試更新標題長度驗證
        with pytest.raises(CustomValidationError):
            repo.update(result, title="")
        
        with pytest.raises(CustomValidationError):
            repo.update(result, title="a" * 501)
    
    def test_repository_create_with_optional_fields(self,  repo, sample_article_data):
        """測試創建包含可選欄位的文章"""
        article_data = {
            "title": "帶有可選欄位的文章",
            "link": "https://test.com/optional-article",
            "published_at": datetime.now(),
            "summary": "這是一篇測試文章",
            "content": "測試內容",
            "category": "測試分類",
            "tags": "測試,範例"
        }
        
        result = repo.create(**article_data)
        repo.session.commit()
        
        assert result.summary == "這是一篇測試文章"
        assert result.content == "測試內容"
        assert result.category == "測試分類"
        assert result.tags == "測試,範例"
    
    def test_repository_unique_link_constraint(self,  repo):
        """測試連結唯一性約束"""
        first_article_data = {
            "title": "第一篇文章",
            "link": "https://test.com/unique-link",
            "published_at": datetime.now()
        }
        repo.create(**first_article_data)
        repo.session.commit()

        with pytest.raises(CustomValidationError):
            repo.create(**first_article_data)


    def test_repository_batch_create(self, repo, sample_article_data):
        """測試批量創建"""
        article_data1 = {
            "title": "第一篇文章",
            "link": "https://test.com/article1",
            "published_at": datetime.now()
        }

        article_data2 = {
            "title": "第二篇文章",
            "link": "https://test.com/article2",
            "published_at": datetime.now()
        }

        results = repo.batch_create([article_data1, article_data2])
        assert results is not None  
        assert len(results) == 2
        assert results[0].title == "第一篇文章"
        assert results[1].title == "第二篇文章"

    def test_repository_batch_update(self,  repo):
        """測試批量更新"""  
        article_data1 = {
            "title": "第一篇文章",
            "link": "https://test.com/article1",
            "published_at": datetime.now()
        }   

        article_data2 = {
            "title": "第二篇文章",
            "link": "https://test.com/article2",
            "published_at": datetime.now()
        }           

        results = repo.batch_create([article_data1, article_data2])
        repo.session.commit()

        results = repo.batch_update(results, title="更新後的文章")
        repo.session.commit()

        assert results is not None
        assert len(results) == 2
        assert results[0].title == "更新後的文章"
        assert results[1].title == "更新後的文章"  

    def test_repository_batch_delete(self, repo):
        """測試批量刪除"""
        article_data1 = {
            "title": "第一篇文章",
            "link": "https://test.com/article1",
            "published_at": datetime.now()
        }   

        article_data2 = {
            "title": "第二篇文章",
            "link": "https://test.com/article2",
            "published_at": datetime.now()
        }

        results = repo.batch_create([article_data1, article_data2])
        repo.session.commit()

        results = repo.batch_delete(results)
        repo.session.commit()

        assert results is True

    def test_repository_find_by_filter(self, create_database_session, repo):
        """測試過濾查詢"""
        article_data1 = {
            "title": "第一篇文章",
            "link": "https://test.com/article1",
            "published_at": datetime.now()
        }   

        article_data2 = {
            "title": "第二篇文章",
            "link": "https://test.com/article2",
            "published_at": datetime.now()
        }
        
        repo.batch_create([article_data1, article_data2])
        repo.session.commit()

        found_articles = repo.find_by_filter(title="第一篇文章")
        assert len(found_articles) == 1
        assert found_articles[0].title == "第一篇文章"
        



