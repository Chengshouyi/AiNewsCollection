import pytest
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base_model import Base
from src.database.base_repository import BaseRepository
from src.error.errors import ValidationError, DatabaseOperationError, InvalidOperationError, DatabaseConnectionError
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from sqlalchemy import String
from unittest.mock import patch
from typing import Optional
from pydantic import BaseModel, field_validator


# 測試用的 Pydantic Schema 類，符合 ArticleCreateSchema 和 ArticleUpdateSchema 的設計
class ModelCreateSchema(BaseModel):
    name: str  # 添加必要的 name 欄位
    title: str
    link: str
    source: str
    published_at: str
    summary: Optional[str] = None
    
    @field_validator('title')
    def validate_title(cls, v):
        if not v or not v.strip():
            raise ValueError("title: 不能為空")
        if len(v) > 500:
            raise ValueError("title: 長度不能超過 500 字元")
        return v.strip()
    
    @field_validator('link')
    def validate_link(cls, v):
        if not v or not v.strip():
            raise ValueError("link: 不能為空")
        if len(v) > 1000:
            raise ValueError("link: 長度不能超過 1000 字元")
        return v.strip()

class ModelUpdateSchema(BaseModel):
    title: Optional[str] = None
    link: Optional[str] = None
    source: Optional[str] = None
    published_at: Optional[str] = None
    summary: Optional[str] = None


class ModelForTest(Base):
    """測試用模型"""
    __tablename__ = 'test_model'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    link: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    published_at: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now(timezone.utc))
    summary: Mapped[Optional[str]] = mapped_column(String, nullable=True)

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
        """創建 TestModel 的 Repository 實例"""
        return BaseRepository(session, ModelForTest)
    
    @pytest.fixture
    def sample_model_data(self):
        """建立測試數據資料"""
        return {
            "name": "test_name",
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": "2023-07-01",
            "source": "測試來源",
            "created_at": datetime.now(timezone.utc)
        }
    
    def test_create(self, repo, sample_model_data):
        """測試創建實體"""
        result = repo.create(sample_model_data)
        repo.session.commit()
        
        assert result.id is not None
        assert result.title == "測試文章"
        assert result.link == "https://test.com/article"
    
    def test_create_with_schema(self, repo, sample_model_data):
        """測試使用schema創建實體"""
        # 確保包含了 name 欄位
        schema_data = {k: v for k, v in sample_model_data.items() 
                      if k in ['name', 'title', 'link', 'published_at', 'source', 'summary']}
        result = repo.create(schema_data, schema_class=ModelCreateSchema)
        repo.session.commit()
        
        assert result.id is not None
        assert result.title == "測試文章"
        assert result.link == "https://test.com/article"
    
    def test_get_by_id(self, repo, sample_model_data):
        """測試根據ID獲取實體"""
        article = repo.create(sample_model_data)
        repo.session.commit()
        
        result = repo.get_by_id(article.id)
        assert result is not None
        assert result.id == article.id
        assert result.title == "測試文章"
    
    def test_get_all(self, repo, sample_model_data):
        """測試獲取所有實體"""
        # 創建多筆數據
        for i in range(3):
            data = sample_model_data.copy()
            data["title"] = f"測試文章{i}"
            data["link"] = f"https://test.com/article{i}"
            repo.create(data)
        repo.session.commit()
        
        results = repo.get_all()
        assert results is not None
        assert len(results) == 3
    
    def test_update(self, repo, sample_model_data):
        """測試更新實體"""
        entity = repo.create(sample_model_data)
        repo.session.commit()
        
        updated_data = {
            "title": "更新後的文章",
            "summary": "這是更新後的摘要"
        }
        
        result = repo.update(entity.id, updated_data)
        repo.session.commit()
        
        assert result is not None
        assert result.id == entity.id
        assert result.title == "更新後的文章"
        assert result.summary == "這是更新後的摘要"
        assert result.link == "https://test.com/article"  # 未更新的欄位應保持不變
    
    def test_update_with_schema(self, repo, sample_model_data):
        """測試使用schema更新實體"""
        entity = repo.create(sample_model_data)
        repo.session.commit()
        
        updated_data = {
            "title": "使用Schema更新後的文章",
            "summary": "這是使用Schema更新後的摘要"
        }
        
        result = repo.update(entity.id, updated_data, schema_class=ModelUpdateSchema)
        repo.session.commit()
        
        assert result is not None
        assert result.id == entity.id
        assert result.title == "使用Schema更新後的文章"
        assert result.summary == "這是使用Schema更新後的摘要"
        assert result.link == "https://test.com/article"  # 未更新的欄位應保持不變
    
    def test_delete(self, repo, sample_model_data):
        """測試刪除實體"""
        entity = repo.create(sample_model_data)
        repo.session.commit()
        
        result = repo.delete(entity.id)
        repo.session.commit()
        
        assert result is True
        assert repo.get_by_id(entity.id) is None
    
    def test_schema_validation_error(self, repo):
        """測試模型驗證失敗"""
        invalid_data = {
            "title": "",  # 空標題，違反schema驗證規則
            "link": "https://test.com/article",
            "published_at": "2023-07-01",
            "source": "測試來源"
        }
        
        with pytest.raises(ValueError):
            repo.create(invalid_data, schema_class=ModelCreateSchema)
    
    def test_create_integrity_error(self, repo, sample_model_data):
        """測試創建具有相同鍵值的實體（完整性錯誤）"""
        # 使用 mock 直接模擬 IntegrityError
        with patch.object(repo.session, 'flush', 
                         side_effect=IntegrityError("unique constraint failed", None, Exception("Original error"))):
            # 嘗試創建記錄，應該立即拋出 ValidationError
            with pytest.raises(ValidationError) as excinfo:
                repo.create(sample_model_data)
            # 驗證錯誤訊息
            assert "唯一性錯誤" in str(excinfo.value) or "已存在" in str(excinfo.value)
    
    def test_update_with_integrity_error(self, repo, sample_model_data):
        """測試更新時的完整性錯誤"""
        entity = repo.create(sample_model_data)
        repo.session.commit()
        
        # 使用 no_autoflush 避免自動 flush 觸發 mock
        with repo.session.no_autoflush:
            with patch.object(repo.session, 'flush', 
                             side_effect=IntegrityError("Mock Integrity Error", None, Exception("Original error"))):
                with pytest.raises(ValidationError):
                    repo.update(entity.id, {"title": "更新的文章"})
    
    def test_execute_query_with_closed_session(self, repo):
        """測試已關閉會話的查詢"""
        repo.session.close()
        repo.session.bind = None  # 確保會話被標記為關閉
        
        with pytest.raises(DatabaseConnectionError):
            repo.execute_query(lambda: repo.session.query(ModelForTest).all())
    
    def test_execute_query_with_operation_error(self, repo):
        """測試查詢操作錯誤"""
        with pytest.raises(DatabaseOperationError) as excinfo:
            repo.execute_query(lambda: repo.session.execute("SELECT * FROM nonexistent_table"))
        assert "資料庫操作錯誤" in str(excinfo.value)
    
    def test_create_with_integrity_error(self, repo):
        """測試創建實體時的完整性錯誤"""
        with pytest.raises(ValidationError) as excinfo:
            with patch.object(repo.session, 'flush', side_effect=IntegrityError("Mock Integrity Error", None, Exception("Original error"))):
                repo.create({"name": "test", "title": "test", "link": "test", "source": "test", "published_at": "2023-07-01"})
        assert "資料完整性錯誤" in str(excinfo.value)
    
    def test_update_nonexistent_entity(self, repo):
        """測試更新不存在的實體"""
        result = repo.update(999, {"title": "新標題"})
        assert result is None  # BaseRepository.update 方法返回 None，而不是拋出異常
    
    def test_delete_with_integrity_error(self, repo, sample_model_data):
        """測試刪除時的完整性錯誤"""
        entity = repo.create(sample_model_data)
        repo.session.commit()
        
        # 使用 no_autoflush 避免自動 flush 觸發 mock
        with repo.session.no_autoflush:
            with patch.object(repo.session, 'flush', 
                          side_effect=IntegrityError("Mock Integrity Error", None, Exception("Original error"))):
                with pytest.raises(ValidationError) as excinfo:
                    repo.delete(entity.id)
            assert "cannot delete" in str(excinfo.value)
    
    def test_get_all_with_invalid_sort_field(self, repo):
        """測試使用無效的排序欄位"""
        with pytest.raises(InvalidOperationError) as excinfo:
            repo.get_all(sort_by="nonexistent_field")
        assert "無效的排序欄位" in str(excinfo.value)
    
    def test_get_paginated_with_invalid_page(self, repo):
        """測試分頁參數驗證"""
        result = repo.get_paginated(page=-1, per_page=10)
        assert result["page"] == 1  # 應該自動修正為有效的頁碼
    
    def test_find_all_wrapper(self, repo, sample_model_data):
        """測試 find_all 包裝方法"""
        for i in range(3):
            data = sample_model_data.copy()
            data["title"] = f"測試文章{i}"
            repo.create(data)
        repo.session.commit()
        
        results = repo.find_all(limit=2)
        assert len(results) == 2



