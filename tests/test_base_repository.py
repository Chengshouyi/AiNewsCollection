import pytest
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from src.model.base_models import Base, ValidationError
from src.model.base_rerository import BaseRepository
from src.model.article_models import Article
from datetime import datetime, timezone

class TestBaseRepository:
    
    @pytest.fixture
    def engine(self):
        """創建測試用的資料庫引擎"""
        return create_engine('sqlite:///:memory:')
    
    @pytest.fixture
    def session(self, engine):
        """創建測試用的資料庫會話"""
        Base.metadata.create_all(engine)
        session = Session(engine)
        yield session
        session.close()
        Base.metadata.drop_all(engine)
    
    @pytest.fixture
    def repo(self, session):
        """創建 Article 的 Repository 實例"""
        return BaseRepository(session, Article)
    
    @pytest.fixture
    def sample_article_data(self):
        """建立測試文章資料"""
        return {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": "2023-07-01",
            "source": "測試來源",
            "created_at": datetime.now(timezone.utc)
        }
    
    def test_create(self, repo, sample_article_data):
        """測試創建實體"""
        result = repo.create(sample_article_data)
        repo.session.commit()
        
        assert result.id is not None
        assert result.title == "測試文章"
        assert result.link == "https://test.com/article"
    
    def test_get_by_id(self, repo, sample_article_data):
        """測試根據ID獲取實體"""
        article = repo.create(sample_article_data)
        repo.session.commit()
        
        result = repo.get_by_id(article.id)
        assert result is not None
        assert result.id == article.id
        assert result.title == "測試文章"
    
    def test_get_all(self, repo, sample_article_data):
        """測試獲取所有實體"""
        # 創建多篇文章
        for i in range(3):
            article_data = sample_article_data.copy()
            article_data["title"] = f"測試文章{i}"
            article_data["link"] = f"https://test.com/article{i}"
            repo.create(article_data)
        repo.session.commit()
        
        results = repo.get_all()
        assert results is not None
        assert len(results) == 3
    
    def test_update(self, repo, sample_article_data):
        """測試更新實體"""
        article = repo.create(sample_article_data)
        repo.session.commit()
        
        updated_data = {
            "id": article.id,
            "title": "更新後的文章",
            "summary": "這是更新後的摘要"
        }
        
        result = repo.update(article.id, updated_data)
        repo.session.commit()
        
        assert result is not None
        assert result.id == article.id
        assert result.title == "更新後的文章"
        assert result.summary == "這是更新後的摘要"
        assert result.link == "https://test.com/article"  # 未更新的欄位應保持不變
    
    def test_delete(self, repo, sample_article_data):
        """測試刪除實體"""
        article = repo.create(sample_article_data)
        repo.session.commit()
        
        result = repo.delete(article.id)
        repo.session.commit()
        
        assert result is True
        assert repo.get_by_id(article.id) is None
    
    def test_validate_entity_required_fields(self, repo):
        """測試必填欄位驗證"""
        invalid_data = {
            "title": "測試文章"
            # 缺少必填欄位 link, source
        }
        
        with pytest.raises(ValidationError):
            repo.validate_entity(invalid_data)
    
    def test_validate_entity_field_length(self, repo):
        """測試欄位長度驗證"""
        invalid_data = {
            "title": "a" * 501,  # 超過最大長度 500
            "link": "https://test.com/article",
            "source": "測試來源"
        }
        
        with pytest.raises(ValidationError):
            repo.validate_entity(invalid_data)
    
    def test_validate_entity_with_schema(self, repo):
        """測試使用 schema 進行驗證"""
        from src.model.article_schema import ArticleCreateSchema
        
        # 有效數據
        valid_data = {
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": "2023-07-01",
            "source": "測試來源",
            "summary": "這是一篇測試文章的摘要"
        }
        
        # 不應拋出異常
        repo.validate_entity(valid_data, schema_class=ArticleCreateSchema)
        
        # 無效數據
        invalid_data = {
            "title": "",  # 空標題，違反schema驗證規則
            "link": "https://test.com/article",
            "published_at": "2023-07-01",
            "source": "測試來源"
        }
        
        with pytest.raises(ValidationError):
            repo.validate_entity(invalid_data, schema_class=ArticleCreateSchema)
    
    def test_update_immutable_field(self, repo, sample_article_data):
        """測試更新不可變欄位"""
        article = repo.create(sample_article_data)
        repo.session.commit()
        
        # 嘗試更新不可變欄位 link
        with pytest.raises(ValidationError):
            repo.update(article.id, {"link": "https://test.com/updated"})
    
    def test_create_with_integrity_error(self, repo, sample_article_data):
        """測試創建時的完整性錯誤"""
        repo.create(sample_article_data)
        repo.session.commit()
        
        # 嘗試創建具有相同 link 的文章
        duplicate_data = sample_article_data.copy()
        duplicate_data["title"] = "另一篇文章"
        
        with pytest.raises(ValidationError):
            repo.create(duplicate_data)
            repo.session.commit()
    
    def test_update_with_integrity_error(self, repo, sample_article_data):
        """測試更新時的完整性錯誤"""
        article1 = repo.create(sample_article_data)
        
        article2_data = sample_article_data.copy()
        article2_data["link"] = "https://test.com/article2"
        article2_data["title"] = "第二篇文章"
        article2 = repo.create(article2_data)
        
        repo.session.commit()
        
        # 嘗試將第二篇文章的 link 更新為與第一篇相同
        with pytest.raises(ValidationError):
            repo.update(article2.id, {"title": "更新的第二篇文章", "link": article1.link})
            repo.session.commit()



