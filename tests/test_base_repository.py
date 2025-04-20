import pytest
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base_model import Base
from src.database.base_repository import BaseRepository, SchemaType
from src.error.errors import DatabaseOperationError, IntegrityValidationError, ValidationError, InvalidOperationError
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
    summary: Optional[str] = None  # 明確標記為選填並提供預設值
    
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
    
    @classmethod
    def get_required_fields(cls) -> list:
        """返回所有必填欄位名稱"""
        return ["name", "title", "link", "source", "published_at"]  # 明確列出必填欄位

class ModelUpdateSchema(BaseModel):
    title: Optional[str] = None
    link: Optional[str] = None
    source: Optional[str] = None
    published_at: Optional[str] = None
    summary: Optional[str] = None
    
    @classmethod
    def get_required_fields(cls) -> list:
        """返回所有必填欄位名稱"""
        return []
    
    @classmethod
    def get_immutable_fields(cls) -> list:
        """返回不可變更的欄位"""
        return []


class ModelForTest(Base):
    """測試用模型"""
    __tablename__ = 'test_repository_model'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    link: Mapped[str] = mapped_column(String, unique=True)
    source: Mapped[str] = mapped_column(String)
    published_at: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now(timezone.utc))
    summary: Mapped[Optional[str]] = mapped_column(String, nullable=True)

# 創建一個具體的 Repository 實現類進行測試
class ModelRepositoryforTest(BaseRepository[ModelForTest]):
    """實現 BaseRepository 抽象類以便測試"""
    
    @classmethod
    def get_schema_class(cls, schema_type: SchemaType = SchemaType.CREATE) -> Type[BaseModel]:
        """實現獲取schema類的抽象方法"""
        if schema_type == SchemaType.CREATE:
            return ModelCreateSchema
        elif schema_type == SchemaType.UPDATE:
            return ModelUpdateSchema
        elif schema_type == SchemaType.LIST:
            return ModelCreateSchema
        elif schema_type == SchemaType.DETAIL:
            return ModelCreateSchema
        return ModelCreateSchema
    
    def create(self, entity_data: Dict[str, Any]) -> Optional[ModelForTest]:
        """實現創建實體的抽象方法"""
        try:
            validated_data = self.validate_data(entity_data, SchemaType.CREATE)
            if validated_data:
                return self._create_internal(validated_data)
            return None
        except (ValidationError, DatabaseOperationError, IntegrityValidationError) as e:
            raise e
        except Exception as e:
            raise DatabaseOperationError(f"創建時發生未預期錯誤: {e}") from e
    
    def update(self, entity_id: Any, entity_data: Dict[str, Any]) -> Optional[ModelForTest]:
        """實現更新實體的抽象方法"""
        try:
            update_payload = self.validate_data(entity_data, SchemaType.UPDATE)
            if update_payload:
                return self._update_internal(entity_id, update_payload)
            return None
        except (ValidationError, DatabaseOperationError, IntegrityValidationError) as e:
            raise e
        except Exception as e:
            raise DatabaseOperationError(f"更新時發生未預期錯誤: {e}") from e

class TestBaseRepository:
    
    @pytest.fixture(scope="session")
    def engine(self):
        """創建測試用的資料庫引擎，只需執行一次"""
        return create_engine('sqlite:///:memory:')
    
    @pytest.fixture(scope="function")
    def tables(self, engine):
        """創建資料表結構 (每次測試函數執行前)"""
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

    @pytest.fixture(scope="function")
    def sample_model_data_list(self, sample_model_data):
        """建立多個測試數據資料"""
        data_list = []
        for i in range(5):
            data = sample_model_data.copy()
            data["name"] = f"name_{i}"
            data["title"] = f"測試文章{i}"
            data["link"] = f"https://test.com/article/{i}" # 確保 link 唯一
            data["source"] = f"來源 {chr(ord('A') + i)}" # A, B, C, D, E
            data["published_at"] = f"2023-01-{(i+1):02d}"
            data_list.append(data)
        return data_list

    def test_create_entity(self, repo, sample_model_data, session):
        """測試創建實體的基本功能"""
        session.query(ModelForTest).delete()
        session.commit()
        
        created_entity = repo.create(sample_model_data)
        session.commit()
        
        assert created_entity is not None
        assert created_entity.id is not None
        entity_id = created_entity.id
        
        session.expire(created_entity)
        
        result = repo.get_by_id(entity_id)
        
        assert result is not None
        assert result.id == entity_id
        assert result.title == "測試文章"
        assert result.link == "https://test.com/article"

    def test_create_entity_with_schema_internal_logic(self, repo, sample_model_data, session):
        """測試 validate_data 和 _create_internal 的協同工作"""
        session.query(ModelForTest).delete()
        session.commit()
        
        data_with_schema = sample_model_data.copy()
        
        validated_data = repo.validate_data(data_with_schema, SchemaType.CREATE)
        assert validated_data is not None
        assert "title" in validated_data
        assert validated_data["title"] == "測試文章"
        assert all(key in validated_data for key in ModelCreateSchema.get_required_fields())
        
        created_entity = repo._create_internal(validated_data)
        session.commit()
        
        assert created_entity is not None
        assert created_entity.id is not None
        entity_id = created_entity.id
        
        session.expire(created_entity)
        
        result = repo.get_by_id(entity_id)
        assert result is not None
        assert result.id == entity_id
        assert result.title == "測試文章"
        assert result.link == "https://test.com/article"

    def test_create_entity_validation_error(self, repo, session):
        """測試創建實體時捕獲自定義的 ValidationError"""
        session.query(ModelForTest).delete()
        session.commit()
        
        invalid_data = {
            "name": "test_name",
            "title": "",  # 空標題 -> 觸發 Pydantic 驗證器
            "link": "https://test.com/article",
            "published_at": "2023-07-01",
            "source": "測試來源"
        }
        
        with pytest.raises(ValidationError) as excinfo:
            repo.create(invalid_data)
            # 注意：不需要 session.commit()，因為錯誤在 validate_data 階段就會發生
        
        # 檢查錯誤訊息是否包含 Pydantic 的原始錯誤提示
        assert "不能為空" in str(excinfo.value)

    def test_update_entity(self, repo, sample_model_data, session):
        """測試更新實體的基本功能"""
        session.query(ModelForTest).delete()
        session.commit()
        
        created_entity = repo.create(sample_model_data)
        session.commit()
        assert created_entity is not None and created_entity.id is not None
        entity_id = created_entity.id
        session.expire(created_entity)
        
        update_data = {
            "title": "更新後的文章",
            "summary": "這是更新後的摘要"
        }
        updated_entity = repo.update(entity_id, update_data)
        session.commit()
        
        assert updated_entity is not None
        
        session.expire(updated_entity)
        
        result = repo.get_by_id(entity_id)
        assert result is not None
        assert result.id == entity_id
        assert result.title == "更新後的文章"
        assert result.summary == "這是更新後的摘要"
        assert result.link == "https://test.com/article"

    def test_update_entity_with_schema_internal_logic(self, repo, sample_model_data, session):
        """測試 validate_data 和 _update_internal 的協同工作"""
        session.query(ModelForTest).delete()
        session.commit()
        
        created_entity = repo.create(sample_model_data)
        session.commit()
        assert created_entity is not None and created_entity.id is not None
        entity_id = created_entity.id
        session.expire(created_entity)
        
        update_data = {
            "title": "使用Schema更新後的文章",
            "summary": "這是使用Schema更新後的摘要"
        }
        
        validated_payload = repo.validate_data(update_data, SchemaType.UPDATE)
        assert validated_payload is not None
        assert "title" in validated_payload
        assert validated_payload["title"] == "使用Schema更新後的文章"
        assert "summary" in validated_payload
        assert "link" not in validated_payload
        
        updated_entity = repo._update_internal(entity_id, validated_payload)
        session.commit()
        
        assert updated_entity is not None
        
        session.expire(updated_entity)
        
        result = repo.get_by_id(entity_id)
        assert result is not None
        assert result.id == entity_id
        assert result.title == "使用Schema更新後的文章"
        assert result.summary == "這是使用Schema更新後的摘要"

    def test_update_nonexistent_entity(self, repo, session):
        """測試更新不存在的實體時拋出 DatabaseOperationError"""
        session.query(ModelForTest).delete()
        session.commit()
        
        non_existent_id = 999
        with pytest.raises(DatabaseOperationError) as excinfo:
            repo.update(non_existent_id, {"title": "新標題"})
            # 不需要 commit，因為錯誤在查詢階段發生
        
        assert f"找不到ID為{non_existent_id}的實體" in str(excinfo.value)

    def test_delete_entity(self, repo, sample_model_data, session):
        """測試刪除實體的基本功能"""
        session.query(ModelForTest).delete()
        session.commit()
        
        created_entity = repo.create(sample_model_data)
        session.commit()
        assert created_entity is not None and created_entity.id is not None
        entity_id = created_entity.id
        
        result = repo.delete(entity_id)
        session.commit()
        
        assert result is True
        assert repo.get_by_id(entity_id) is None

    def test_delete_nonexistent_entity(self, repo, session):
        """測試刪除不存在的實體返回 False"""
        session.query(ModelForTest).delete()
        session.commit()
        
        non_existent_id = 999
        result = repo.delete(non_existent_id)
        session.commit()
        
        assert result is False

    def test_get_by_id(self, repo, sample_model_data, session):
        """測試根據 ID 獲取實體"""
        session.query(ModelForTest).delete()
        session.commit()
        
        created_entity = repo.create(sample_model_data)
        session.commit()
        assert created_entity is not None and created_entity.id is not None
        entity_id = created_entity.id
        session.expire(created_entity)
        
        result = repo.get_by_id(entity_id)
        assert result is not None
        assert result.id == entity_id
        assert result.title == "測試文章"

    def test_find_all_basic(self, repo, sample_model_data_list, session):
        """測試 find_all 獲取所有實體 (非預覽模式)"""
        for data in sample_model_data_list:
            repo.create(data)
        session.commit()
        session.expire_all()

        results = repo.find_all()
        assert results is not None
        assert len(results) == len(sample_model_data_list)
        assert all(isinstance(item, ModelForTest) for item in results)

    def test_find_all_with_sorting(self, repo, sample_model_data_list, session):
        """測試 find_all 獲取所有實體並排序 (非預覽模式)"""
        for data in sample_model_data_list:
            repo.create(data)
        session.commit()
        session.expire_all()

        results_asc = repo.find_all(sort_by="title", sort_desc=False)
        assert [item.title for item in results_asc] == [f"測試文章{i}" for i in range(5)]
        assert all(isinstance(item, ModelForTest) for item in results_asc)

        results_desc = repo.find_all(sort_by="title", sort_desc=True)
        assert [item.title for item in results_desc] == [f"測試文章{i}" for i in range(4, -1, -1)]
        assert all(isinstance(item, ModelForTest) for item in results_desc)

    def test_find_all_with_pagination(self, repo, sample_model_data_list, session):
        """測試 find_all 獲取所有實體並分頁 (非預覽模式)"""
        for data in sample_model_data_list:
            repo.create(data)
        session.commit()
        session.expire_all()

        results = repo.find_all(limit=2, offset=2)
        assert len(results) == 2
        assert results[0].title == "測試文章2"
        assert results[1].title == "測試文章1"
        assert all(isinstance(item, ModelForTest) for item in results)

    def test_find_all_preview(self, repo, sample_model_data_list, session):
        """測試 find_all 預覽模式"""
        for data in sample_model_data_list:
            repo.create(data)
        session.commit()
        session.expire_all()

        preview_fields = ["title", "link"]
        results = repo.find_all(is_preview=True, preview_fields=preview_fields)

        assert results is not None
        assert len(results) == len(sample_model_data_list)
        assert all(isinstance(item, dict) for item in results)
        for item in results:
            assert set(item.keys()) == set(preview_fields)
            assert item["title"].startswith("測試文章")

    def test_find_all_preview_with_sort_limit(self, repo, sample_model_data_list, session):
        """測試 find_all 預覽模式帶排序和分頁"""
        for data in sample_model_data_list:
            repo.create(data)
        session.commit()
        session.expire_all()

        preview_fields = ["name", "source"]
        results = repo.find_all(
            sort_by="source",
            sort_desc=False,
            limit=2,
            offset=1,
            is_preview=True,
            preview_fields=preview_fields
        )

        assert len(results) == 2
        assert all(isinstance(item, dict) for item in results)
        assert results[0]["source"] == "來源 B"
        assert results[0]["name"] == "name_1"
        assert results[1]["source"] == "來源 C"
        assert results[1]["name"] == "name_2"
        assert set(results[0].keys()) == set(preview_fields)

    def test_find_all_preview_invalid_fields(self, repo, sample_model_data_list, session):
        """測試 find_all 預覽模式但欄位無效，應返回完整物件"""
        for data in sample_model_data_list:
            repo.create(data)
        session.commit()
        session.expire_all()

        results = repo.find_all(is_preview=True, preview_fields=["invalid_field", "non_existent"])
        assert len(results) == len(sample_model_data_list)
        assert all(isinstance(item, ModelForTest) for item in results)

    def test_find_all_invalid_sort_key(self, repo, session):
        """測試 find_all 使用無效排序欄位"""
        with pytest.raises(InvalidOperationError) as excinfo:
            repo.find_all(sort_by="invalid_column")
        assert "無效的排序欄位: invalid_column" in str(excinfo.value)

    def test_integrity_error_handling_on_commit(self, repo, sample_model_data, session):
        """測試在 session.commit() 時直接捕獲 sqlalchemy.exc.IntegrityError (Unique Constraint)"""
        repo.create(sample_model_data)
        session.commit()

        repo.create(sample_model_data)

        with pytest.raises(IntegrityError) as excinfo:
            session.commit()

        assert "UNIQUE constraint failed" in str(excinfo.value)
        assert "test_repository_model.link" in str(excinfo.value)

        session.rollback()

    def test_get_schema_class(self, repo):
        """測試獲取schema類的方法"""
        assert repo.get_schema_class(SchemaType.CREATE) == ModelCreateSchema
        assert repo.get_schema_class(SchemaType.UPDATE) == ModelUpdateSchema
        assert repo.get_schema_class(SchemaType.LIST) == ModelCreateSchema
        assert repo.get_schema_class(SchemaType.DETAIL) == ModelCreateSchema
        assert repo.get_schema_class() == ModelCreateSchema

    def test_validate_data(self, repo, sample_model_data):
        """測試 validate_data 方法"""
        validated_create = repo.validate_data(sample_model_data, SchemaType.CREATE)
        assert validated_create is not None
        assert validated_create["title"] == "測試文章"
        assert validated_create["link"] == "https://test.com/article"
        assert all(key in validated_create for key in ModelCreateSchema.get_required_fields())
        
        update_data = {"title": "更新的標題", "summary": "新摘要"}
        validated_update = repo.validate_data(update_data, SchemaType.UPDATE)
        assert validated_update is not None
        assert validated_update["title"] == "更新的標題"
        assert validated_update["summary"] == "新摘要"
        assert "link" not in validated_update
        
        invalid_data = sample_model_data.copy()
        invalid_data["title"] = ""
        
        with pytest.raises(ValidationError) as excinfo:
            repo.validate_data(invalid_data, SchemaType.CREATE)
        
        assert "不能為空" in str(excinfo.value)
        assert "CREATE 資料驗證失敗" in str(excinfo.value)

    def test_validate_and_supplement_create_success(self, repo, sample_model_data):
        validated_data = repo.validate_data(sample_model_data, SchemaType.CREATE)
        final_data = repo._validate_and_supplement_required_fields(validated_data)
        assert final_data is not None

    def test_validate_and_supplement_create_error(self, repo, sample_model_data):
        validated_data = repo.validate_data(sample_model_data, SchemaType.CREATE)
        validated_data["title"] = ""
        with pytest.raises(ValidationError) as excinfo:
            repo._validate_and_supplement_required_fields(validated_data)
        assert "必填欄位值無效" in str(excinfo.value)
        assert "title" in str(excinfo.value)

    def test_validate_and_supplement_update_supplement(self, repo, sample_model_data, session):
        created_entity = repo.create(sample_model_data)
        session.commit()
        entity_id = created_entity.id
        session.expire(created_entity)

        update_payload = {"summary": "New Summary"}
        validated_payload = repo.validate_data(update_payload, SchemaType.UPDATE)

        existing_entity = repo.get_by_id(entity_id)

        final_data = repo._validate_and_supplement_required_fields(validated_payload, existing_entity)

        assert "title" in final_data
        assert final_data["title"] == sample_model_data["title"]
        assert final_data["summary"] == "New Summary"

    def test_validate_and_supplement_update_error(self, repo, sample_model_data, session):
        invalid_initial_data = {
            "name": sample_model_data["name"],
            "title": "",
            "link": "https://test.com/invalid_update",
            "source": sample_model_data["source"],
            "published_at": sample_model_data["published_at"],
        }
        initial_entity = ModelForTest(**invalid_initial_data)
        session.add(initial_entity)
        try:
            session.commit()
            entity_id = initial_entity.id
            assert entity_id is not None
            print(f"DEBUG: 已直接創建 ID={entity_id} 的無效標題實體用於測試")
        except Exception as e:
            session.rollback()
            pytest.fail(f"直接創建無效實體失敗: {e}")

        session.expire(initial_entity)

        update_payload = {}
        validated_payload = repo.validate_data(update_payload, SchemaType.UPDATE)

        existing_entity = repo.get_by_id(entity_id)
        assert existing_entity is not None
        assert existing_entity.title == ""

        with pytest.raises(ValidationError) as excinfo:
            repo._validate_and_supplement_required_fields(validated_payload, existing_entity)

        assert "必填欄位值無效" in str(excinfo.value)
        assert "title" in str(excinfo.value)

    def test_create_internal_validation_error(self, repo, sample_model_data):
        with patch.object(repo, '_validate_and_supplement_required_fields', side_effect=ValidationError("模擬必填欄位錯誤")):
            validated_data = repo.validate_data(sample_model_data, SchemaType.CREATE)
            with pytest.raises(ValidationError) as excinfo:
                repo._create_internal(validated_data)
            assert "模擬必填欄位錯誤" in str(excinfo.value)

    def test_update_internal_immutable_field(self, repo, sample_model_data, session):
        created = repo.create(sample_model_data)
        session.commit()
        entity_id = created.id
        original_name = created.name

        with patch.object(ModelUpdateSchema, 'get_immutable_fields', return_value=['name']):
            update_payload = {"name": "New Name", "title": "New Title"}
            validated_payload = repo.validate_data(update_payload, SchemaType.UPDATE)

            updated_entity = repo._update_internal(entity_id, validated_payload)
            session.commit()

            result = repo.get_by_id(entity_id)
            assert result.title == "New Title"
            assert result.name == original_name

    def test_execute_query_wraps_exception(self, repo, session):
        def faulty_query():
            raise ValueError("Something went wrong")

        with pytest.raises(DatabaseOperationError) as excinfo:
            repo.execute_query(faulty_query, err_msg="Test Error")
        assert "Test Error: Something went wrong" in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, ValueError)

    def test_execute_query_preserves_exception(self, repo, session):
        def integrity_error_query():
            raise IntegrityError("Mock IntegrityError", params=None, orig=ValueError("orig"))

        with pytest.raises(IntegrityError):
             repo.execute_query(integrity_error_query)

        with pytest.raises(DatabaseOperationError):
            repo.execute_query(integrity_error_query, preserve_exceptions=[])

    def test_validate_data_as_classmethod(self, sample_model_data):
        """測試可以直接通過類調用 validate_data"""
        validated_create = ModelRepositoryforTest.validate_data(sample_model_data, SchemaType.CREATE)
        assert validated_create is not None
        assert validated_create["title"] == "測試文章"

        invalid_data = sample_model_data.copy()
        invalid_data["title"] = ""
        with pytest.raises(ValidationError):
            ModelRepositoryforTest.validate_data(invalid_data, SchemaType.CREATE)