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

    def test_get_all_basic(self, repo, sample_model_data, session):
        """測試獲取所有實體的基本功能"""
        # 不需要清理，tables fixture 會處理
        # session.query(ModelForTest).delete()
        # session.commit()

        for i in range(3):
            data = sample_model_data.copy()
            data["title"] = f"測試文章{i}"
            data["link"] = f"https://test.com/article/{i}" # <-- 確保 link 唯一
            repo.create(data)
        session.commit() # 提交所有創建操作

        # 清除快取 (或者重新查詢也可以)
        session.expire_all()

        results = repo.get_all()
        assert results is not None
        assert len(results) == 3

    def test_get_all_with_sorting(self, repo, sample_model_data, session):
        """測試獲取所有實體並排序"""
        # 不需要清理，tables fixture 會處理
        # session.query(ModelForTest).delete()
        # session.commit()

        titles = ["測試文章C", "測試文章A", "測試文章B"]
        for title in titles:
            data = sample_model_data.copy()
            data["title"] = title
            data["link"] = f"https://test.com/article/{title.replace('測試文章', '')}" # <-- 確保 link 唯一
            repo.create(data)
        session.commit() # 提交所有創建

        session.expire_all()

        # 升序排序 (預期 A, B, C)
        results_asc = repo.get_all(sort_by="title", sort_desc=False)
        assert [item.title for item in results_asc] == ["測試文章A", "測試文章B", "測試文章C"]

        # 降序排序 (預期 C, B, A)
        results_desc = repo.get_all(sort_by="title", sort_desc=True)
        assert [item.title for item in results_desc] == ["測試文章C", "測試文章B", "測試文章A"]

    def test_get_all_with_pagination(self, repo, sample_model_data, session):
        """測試獲取所有實體並分頁"""
        # 不需要清理，tables fixture 會處理
        # session.query(ModelForTest).delete()
        # session.commit()

        count = 5
        for i in range(count):
            data = sample_model_data.copy()
            data["title"] = f"測試文章{i}" # 0, 1, 2, 3, 4
            data["link"] = f"https://test.com/article/pagination/{i}" # <-- 確保 link 唯一
            repo.create(data)
        session.commit()

        session.expire_all()

        # 獲取第 2 頁，每頁 2 個 (預設按創建時間/ID 升序)
        # 假設 ID 升序為 1, 2, 3, 4, 5 (對應 title 0, 1, 2, 3, 4)
        # 預設升序是 1, 2, 3, 4, 5 (title 0, 1, 2, 3, 4)
        # limit=2, offset=2 應該跳過 title 0, 1，獲取 title 2, 3
        results = repo.get_all(limit=2, offset=2) # offset=2 表示跳過前 2 個
        assert len(results) == 2
        # 由於 get_all 預設排序是降序，這裡需要重新思考預期結果
        # 如果 get_all 默認降序 (ID: 5,4,3,2,1 / Title: 4,3,2,1,0)
        # offset=2 跳過 ID 5, 4 (Title 4, 3)
        # limit=2 應該獲取 ID 3, 2 (Title 2, 1)
        # 讓我們確認 get_all 的默認排序
        # base_repository.py L415: 預設按 created_at 或 id 降序
        assert results[0].title == "測試文章2" # 降序排列的第 3 個 (ID=3)
        assert results[1].title == "測試文章1" # 降序排列的第 4 個 (ID=2)

    def test_get_paginated(self, repo, sample_model_data, session):
        """測試 get_paginated 分頁功能 (預期默認升序)"""
        # 不需要清理，tables fixture 會處理
        # session.query(ModelForTest).delete()
        # session.commit()

        total_items = 11
        for i in range(total_items): # 創建 title 0 到 10
            data = sample_model_data.copy()
            data["title"] = f"測試文章{i}"
            data["link"] = f"https://test.com/article/paginated/{i}" # <-- 確保 link 唯一
            repo.create(data)
        session.commit()

        session.expire_all() # 清除快取以確保從 DB 讀取

        # 測試第一頁 (預期 title 0, 1, 2, 3, 4)
        per_page = 5
        page_data = repo.get_paginated(page=1, per_page=per_page)
        assert page_data["page"] == 1
        assert page_data["per_page"] == per_page
        assert page_data["total"] == total_items
        assert page_data["total_pages"] == 3 # ceil(11 / 5) = 3
        assert page_data["has_next"] is True
        assert page_data["has_prev"] is False
        assert len(page_data["items"]) == per_page
        # 驗證內容 (預期升序)
        assert page_data["items"][0].title == "測試文章0" # <-- 修正斷言
        assert page_data["items"][-1].title == "測試文章4" # <-- 修正斷言

        # 測試第二頁 (預期 title 5, 6, 7, 8, 9)
        page_data_2 = repo.get_paginated(page=2, per_page=per_page)
        assert page_data_2["page"] == 2
        assert len(page_data_2["items"]) == per_page
        assert page_data_2["has_next"] is True
        assert page_data_2["has_prev"] is True
        # 驗證內容 (預期升序)
        assert page_data_2["items"][0].title == "測試文章5" # <-- 修正斷言
        assert page_data_2["items"][-1].title == "測試文章9" # <-- 修正斷言

        # 測試最後一頁 (預期 title 10)
        page_data_3 = repo.get_paginated(page=3, per_page=per_page)
        assert page_data_3["page"] == 3
        assert len(page_data_3["items"]) == 1 # 剩餘 1 個
        assert page_data_3["has_next"] is False
        assert page_data_3["has_prev"] is True
        # 驗證內容 (預期升序)
        assert page_data_3["items"][0].title == "測試文章10" # <-- 修正斷言

    def test_get_paginated_invalid_per_page(self, repo, session):
        """測試 get_paginated 無效 per_page 時拋出 InvalidOperationError"""
        with pytest.raises(InvalidOperationError) as excinfo:
            repo.get_paginated(page=1, per_page=0)
        assert "每頁記錄數必須大於0" in str(excinfo.value)

        with pytest.raises(InvalidOperationError) as excinfo:
            repo.get_paginated(page=1, per_page=-1)
        assert "每頁記錄數必須大於0" in str(excinfo.value)

    def test_integrity_error_handling_on_commit(self, repo, sample_model_data, session):
        """測試在 session.commit() 時直接捕獲 sqlalchemy.exc.IntegrityError (Unique Constraint)"""
        # 不需要清理數據，因為 tables fixture 會處理
        # session.query(ModelForTest).delete()
        # session.commit()

        # 1. 創建第一個實體並提交
        repo.create(sample_model_data)
        session.commit()

        # 2. 嘗試將重複數據添加到 session (link 會重複)
        repo.create(sample_model_data)

        # 3. 在提交時，期望直接捕獲 SQLAlchemy 的 IntegrityError
        with pytest.raises(IntegrityError) as excinfo:
            session.commit() # 觸發唯一性約束錯誤 (現在 link 是 unique)

        # 檢查 SQLAlchemy 的錯誤訊息
        assert "UNIQUE constraint failed" in str(excinfo.value)
        assert "test_repository_model.link" in str(excinfo.value) # 更具體的檢查

        # 確保 session 在錯誤後可以回滾
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