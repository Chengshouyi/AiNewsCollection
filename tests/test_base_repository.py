import pytest
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base_model import Base
from src.database.base_repository import BaseRepository, SchemaType
from src.error.errors import DatabaseOperationError, IntegrityValidationError
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from sqlalchemy import String
from unittest.mock import patch
from typing import Optional, Dict, Any, Type
from pydantic import BaseModel, field_validator


# 測試用的 Pydantic Schema 類
class ModelCreateSchema(BaseModel):
    name: str
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
    __tablename__ = 'test_repository_model'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    link: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    published_at: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now(timezone.utc))
    summary: Mapped[Optional[str]] = mapped_column(String, nullable=True)

# 創建一個具體的 Repository 實現類進行測試
class ModelRepositoryforTest(BaseRepository[ModelForTest]):
    """實現 BaseRepository 抽象類以便測試"""
    
    def get_schema_class(self, schema_type: SchemaType = SchemaType.CREATE) -> Type[BaseModel]:
        """實現獲取schema類的抽象方法"""
        if schema_type == SchemaType.CREATE:
            return ModelCreateSchema
        elif schema_type == SchemaType.UPDATE:
            return ModelUpdateSchema
        elif schema_type == SchemaType.LIST:
            return ModelCreateSchema  # 測試用，實際上可能會有不同的 ListSchema
        elif schema_type == SchemaType.DETAIL:
            return ModelCreateSchema  # 測試用，實際上可能會有不同的 DetailSchema
        return ModelCreateSchema  # 默認返回創建schema
    
    def create(self, entity_data: Dict[str, Any]) -> Optional[ModelForTest]:
        """實現創建實體的抽象方法"""
        # 處理特殊邏輯，例如從entity_data提取schema_class
        schema_type = SchemaType.CREATE
        schema_class = entity_data.pop('schema_class', None)
        
        # 如果傳入特定schema_class，創建一個新的schema並使用它
        if schema_class:
            # 調用時仍使用指定的schema而不是從get_schema_class獲取
            return self._create_internal(entity_data, schema_class)
        
        # 使用枚舉獲取正確的schema類型
        return self._create_internal(entity_data, self.get_schema_class(schema_type))
    
    def update(self, entity_id: Any, entity_data: Dict[str, Any]) -> Optional[ModelForTest]:
        """實現更新實體的抽象方法"""
        # 處理特殊邏輯，例如從entity_data提取schema_class
        schema_type = SchemaType.UPDATE
        schema_class = entity_data.pop('schema_class', None)
        
        # 如果傳入特定schema_class，使用它而不是從get_schema_class獲取
        if schema_class:
            return self._update_internal(entity_id, entity_data, schema_class)
        
        # 使用枚舉獲取正確的schema類型
        return self._update_internal(entity_id, entity_data, self.get_schema_class(schema_type))

class TestBaseRepository:
    
    @pytest.fixture(scope="session")
    def engine(self):
        """創建測試用的資料庫引擎，只需執行一次"""
        return create_engine('sqlite:///:memory:')
    
    @pytest.fixture(scope="session")
    def tables(self, engine):
        """創建資料表結構，只需執行一次"""
        Base.metadata.create_all(engine)
        yield
        Base.metadata.drop_all(engine)
    
    @pytest.fixture(scope="session")
    def session_factory(self, engine):
        """創建會話工廠，只需執行一次"""
        return sessionmaker(bind=engine)
    
    @pytest.fixture(scope="function")
    def session(self, session_factory, tables):
        """為每個測試函數創建獨立的會話"""
        session = session_factory()
        yield session
        session.rollback()  # 確保每個測試後都回滾未提交的更改
        session.close()
    
    @pytest.fixture(scope="function")
    def repo(self, session):
        """為每個測試函數創建獨立的 Repository 實例"""
        return ModelRepositoryforTest(session, ModelForTest)
    
    @pytest.fixture(scope="function")
    def sample_model_data(self):
        """建立測試數據資料，每個測試函數都有獨立的測試數據"""
        return {
            "name": "test_name",
            "title": "測試文章",
            "link": "https://test.com/article",
            "published_at": "2023-07-01",
            "source": "測試來源"
        }

    def test_create_entity(self, repo, sample_model_data, session):
        """測試創建實體的基本功能"""
        # 清除可能的干擾數據
        session.query(ModelForTest).delete()
        session.commit()
        
        result = repo.create(sample_model_data)
        session.commit()
        
        # 刷新獲取最新數據
        entity_id = result.id
        session.expire_all()
        
        # 使用ID重新獲取實體
        result = repo.get_by_id(entity_id)
        
        assert result is not None
        assert result.id is not None
        assert result.title == "測試文章"
        assert result.link == "https://test.com/article"

    def test_create_entity_with_schema(self, repo, sample_model_data, session):
        """測試使用 schema 創建實體"""
        # 清除可能的干擾數據
        session.query(ModelForTest).delete()
        session.commit()
        
        data_with_schema = sample_model_data.copy()
        data_with_schema['schema_class'] = ModelCreateSchema
        
        result = repo.create(data_with_schema)
        session.commit()
        
        # 刷新獲取最新數據
        entity_id = result.id
        session.expire_all()
        
        # 使用ID重新獲取實體
        result = repo.get_by_id(entity_id)
        
        assert result is not None
        assert result.id is not None
        assert result.title == "測試文章"
        assert result.link == "https://test.com/article"

    def test_create_entity_validation_error(self, repo, session):
        """測試創建實體時的驗證錯誤"""
        # 清除可能的干擾數據
        session.query(ModelForTest).delete()
        session.commit()
        
        invalid_data = {
            "name": "test_name",
            "title": "",  # 空標題
            "link": "https://test.com/article",
            "published_at": "2023-07-01",
            "source": "測試來源",
            "schema_class": ModelCreateSchema
        }
        
        with pytest.raises(DatabaseOperationError) as excinfo:
            repo.create(invalid_data)
        
        assert "title: 不能為空" in str(excinfo.value)

    def test_update_entity(self, repo, sample_model_data, session):
        """測試更新實體的基本功能"""
        # 清除可能的干擾數據
        session.query(ModelForTest).delete()
        session.commit()
        
        entity = repo.create(sample_model_data)
        session.commit()
        
        # 儲存ID並刷新會話
        entity_id = entity.id
        session.expire_all()
        
        update_data = {
            "title": "更新後的文章",
            "summary": "這是更新後的摘要"
        }
        result = repo.update(entity_id, update_data)
        session.commit()
        
        # 刷新獲取最新數據
        session.expire_all()
        
        # 使用ID重新獲取實體
        result = repo.get_by_id(entity_id)
        
        assert result is not None
        assert result.id == entity_id
        assert result.title == "更新後的文章"
        assert result.summary == "這是更新後的摘要"
        assert result.link == "https://test.com/article"  # 未更新的欄位保持不變

    def test_update_entity_with_schema(self, repo, sample_model_data, session):
        """測試使用 schema 更新實體"""
        # 清除可能的干擾數據
        session.query(ModelForTest).delete()
        session.commit()
        
        entity = repo.create(sample_model_data)
        session.commit()
        
        # 儲存ID並刷新會話
        entity_id = entity.id
        session.expire_all()
        
        update_data = {
            "title": "使用Schema更新後的文章",
            "summary": "這是使用Schema更新後的摘要",
            "schema_class": ModelUpdateSchema
        }
        result = repo.update(entity_id, update_data)
        session.commit()
        
        # 刷新獲取最新數據
        session.expire_all()
        
        # 使用ID重新獲取實體
        result = repo.get_by_id(entity_id)
        
        assert result is not None
        assert result.id == entity_id
        assert result.title == "使用Schema更新後的文章"
        assert result.summary == "這是使用Schema更新後的摘要"

    def test_update_nonexistent_entity(self, repo, session):
        """測試更新不存在的實體"""
        # 清除可能的干擾數據
        session.query(ModelForTest).delete()
        session.commit()
        
        result = repo.update(999, {"title": "新標題"})
        session.commit()
        
        assert result is None

    def test_delete_entity(self, repo, sample_model_data, session):
        """測試刪除實體的基本功能"""
        # 清除可能的干擾數據
        session.query(ModelForTest).delete()
        session.commit()
        
        entity = repo.create(sample_model_data)
        session.commit()
        
        # 儲存ID並刷新會話
        entity_id = entity.id
        session.expire_all()
        
        result = repo.delete(entity_id)
        session.commit()
        
        assert result is True
        assert repo.get_by_id(entity_id) is None

    def test_delete_nonexistent_entity(self, repo, session):
        """測試刪除不存在的實體"""
        # 清除可能的干擾數據
        session.query(ModelForTest).delete()
        session.commit()
        
        result = repo.delete(999)
        
        assert result is False

    def test_get_by_id(self, repo, sample_model_data, session):
        """測試根據 ID 獲取實體"""
        # 清除可能的干擾數據
        session.query(ModelForTest).delete()
        session.commit()
        
        entity = repo.create(sample_model_data)
        session.commit()
        
        # 儲存ID並刷新會話
        entity_id = entity.id
        session.expire_all()
        
        result = repo.get_by_id(entity_id)
        assert result is not None
        assert result.id == entity_id
        assert result.title == "測試文章"

    def test_get_all_basic(self, repo, sample_model_data, session):
        """測試獲取所有實體的基本功能"""
        # 清除可能的干擾數據
        session.query(ModelForTest).delete()
        session.commit()
        
        for i in range(3):
            data = sample_model_data.copy()
            data["title"] = f"測試文章{i}"
            repo.create(data)
        session.commit()
        
        # 刷新會話獲取最新數據
        session.expire_all()
        
        results = repo.get_all()
        assert results is not None
        assert len(results) == 3

    def test_get_all_with_sorting(self, repo, sample_model_data, session):
        """測試獲取所有實體並排序"""
        # 清除可能的干擾數據
        session.query(ModelForTest).delete()
        session.commit()
        
        for i in range(3):
            data = sample_model_data.copy()
            data["title"] = f"測試文章{i}"
            repo.create(data)
        session.commit()
        
        # 刷新會話獲取最新數據
        session.expire_all()
        
        # 升序排序
        results = repo.get_all(sort_by="title", sort_desc=False)
        assert [item.title for item in results] == ["測試文章0", "測試文章1", "測試文章2"]
        
        # 降序排序
        results = repo.get_all(sort_by="title", sort_desc=True)
        assert [item.title for item in results] == ["測試文章2", "測試文章1", "測試文章0"]

    def test_get_all_with_pagination(self, repo, sample_model_data, session):
        """測試獲取所有實體並分頁"""
        # 清除可能的干擾數據
        session.query(ModelForTest).delete()
        session.commit()
        
        for i in range(5):
            data = sample_model_data.copy()
            data["title"] = f"測試文章{i}"
            repo.create(data)
        session.commit()
        
        # 刷新會話獲取最新數據
        session.expire_all()
        
        # 測試限制和偏移
        results = repo.get_all(limit=2, offset=1)
        assert len(results) == 2
        assert results[0].title == "測試文章3"
        assert results[1].title == "測試文章2"

    def test_get_paginated(self, repo, sample_model_data, session):
        """測試分頁功能"""
        # 清除可能的干擾數據
        session.query(ModelForTest).delete()
        session.commit()
        
        for i in range(11):
            data = sample_model_data.copy()
            data["title"] = f"測試文章{i}"
            repo.create(data)
        session.commit()
        
        # 刷新會話獲取最新數據
        session.expire_all()
        
        # 測試第一頁
        page_data = repo.get_paginated(page=1, per_page=5)
        assert page_data["page"] == 1
        assert page_data["per_page"] == 5
        assert page_data["total"] == 11
        assert page_data["total_pages"] == 3
        assert page_data["has_next"] is True
        assert page_data["has_prev"] is False
        assert len(page_data["items"]) == 5

    def test_integrity_error_handling(self, repo, sample_model_data, session):
        """測試完整性錯誤處理"""
        # 清除可能的干擾數據
        session.query(ModelForTest).delete()
        session.commit()
        
        with patch.object(session, 'flush', 
                         side_effect=IntegrityError("UNIQUE constraint failed", None, Exception())):
            with pytest.raises(IntegrityValidationError) as excinfo:
                repo.create(sample_model_data)
            
            assert "資料重複" in str(excinfo.value)

    def test_get_schema_class(self, repo, session):
        """測試獲取schema類的方法"""
        # 清除可能的干擾數據
        session.query(ModelForTest).delete()
        session.commit()
        
        # 測試默認返回
        schema = repo.get_schema_class()
        assert schema == ModelCreateSchema
        
        # 測試各種類型的schema
        schema = repo.get_schema_class(SchemaType.CREATE)
        assert schema == ModelCreateSchema
        
        schema = repo.get_schema_class(SchemaType.UPDATE)
        assert schema == ModelUpdateSchema

        schema = repo.get_schema_class(SchemaType.LIST)
        assert schema == ModelCreateSchema  # 在測試實現中，LIST類型也返回ModelCreateSchema
        
        schema = repo.get_schema_class(SchemaType.DETAIL)
        assert schema == ModelCreateSchema  # 在測試實現中，DETAIL類型也返回ModelCreateSchema