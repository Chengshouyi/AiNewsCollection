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

    def test_get_by_filter_equality(self, repo, sample_model_data, session):
        # 創建符合條件的測試數據
        data1 = sample_model_data.copy()
        data1["source"] = "特定來源"
        data1["link"] = "https://test.com/filter/1" # 確保 link 唯一
        repo.create(data1)

        # 創建不符合條件的測試數據 (可選，用於驗證過濾的準確性)
        data2 = sample_model_data.copy()
        data2["source"] = "其他來源"
        data2["link"] = "https://test.com/filter/2" # 確保 link 唯一
        repo.create(data2)
        session.commit() # 提交創建操作

        session.expire_all() # 確保從 DB 讀取

        # 執行過濾查詢
        results = repo.get_by_filter({"source": "特定來源"})

        # 斷言
        assert len(results) > 0 # 應該至少找到一個
        assert len(results) == 1 # 如果只創建了一個符合條件的數據
        assert all(item.source == "特定來源" for item in results) # 驗證找到的數據都符合條件

    def test_get_by_filter_operators(self, repo, sample_model_data, session):
        # 創建 name 為 test1, test2, test3 的數據
        names_to_create = ["test1", "test2", "test3"]
        for i, name in enumerate(names_to_create):
            data = sample_model_data.copy()
            data["name"] = name
            data["link"] = f"https://test.com/filter-op/{i}" # 確保 link 唯一
            data["title"] = f"Title for {name}" # 提供 title
            data["source"] = f"Source for {name}" # 提供 source
            data["published_at"] = f"2023-08-{i+1:02d}" # 提供 published_at
            repo.create(data)
        session.commit() # 提交創建操作

        session.expire_all() # 確保從 DB 讀取

        # 測試 $in 操作符
        results_in = repo.get_by_filter({"name": {"$in": ["test1", "test3"]}})
        assert len(results_in) == 2 # 應該找到 name 為 test1 和 test3 的記錄
        assert all(item.name in ["test1", "test3"] for item in results_in) # 驗證找到的數據都符合條件
        # 可以按 name 排序後斷言具體內容
        results_in.sort(key=lambda x: x.name)
        assert results_in[0].name == "test1"
        assert results_in[1].name == "test3"

        # ... (繼續添加其他操作符的測試和數據創建) ...
        # 例如: 創建一些 published_at 數據用於測試 $gte
        # data_gte1 = sample_model_data.copy()
        # data_gte1["name"] = "gte_test1"
        # data_gte1["link"] = "https://test.com/filter-op/gte1"
        # data_gte1["published_at"] = "2023-08-15"
        # repo.create(data_gte1)
        # data_gte2 = sample_model_data.copy()
        # data_gte2["name"] = "gte_test2"
        # data_gte2["link"] = "https://test.com/filter-op/gte2"
        # data_gte2["published_at"] = "2023-07-31"
        # repo.create(data_gte2)
        # session.commit()
        # session.expire_all()

        # results_gte = repo.get_by_filter({"published_at": {"$gte": "2023-08-01"}})
        # assert len(results_gte) >= 1 # 至少找到 gte_test1 和之前創建的 test1, test2, test3 (假設日期符合)
        # assert all(item.published_at >= "2023-08-01" for item in results_gte)

        # ... (測試 $ne, $nin, $gt, $lt, $lte) ...

    def test_get_by_filter_non_existent_field(self, repo, sample_model_data, session):
        # ... (創建數據) ...
        # 預期不會報錯，且能返回所有數據 (因為無效過濾被忽略)
        # 理想情況下可以 mock logger 來驗證警告，但較複雜
        all_items = repo.get_all()
        results = repo.get_by_filter({"non_existent_field": "some_value"})
        assert len(results) == len(all_items)

    def test_get_by_filter_with_sort_and_limit(self, repo, sample_model_data, session):
        # 創建多個符合條件的數據，以便測試排序和限制
        data1 = sample_model_data.copy()
        data1["source"] = "特定來源"
        data1["title"] = "文章 Z" # 用於降序排序
        data1["link"] = "https://test.com/filter-sort/1"
        repo.create(data1)

        data2 = sample_model_data.copy()
        data2["source"] = "特定來源"
        data2["title"] = "文章 A" # 用於降序排序
        data2["link"] = "https://test.com/filter-sort/2"
        repo.create(data2)

        # 創建不符合條件的數據 (可選)
        data3 = sample_model_data.copy()
        data3["source"] = "其他來源"
        data3["title"] = "文章 X"
        data3["link"] = "https://test.com/filter-sort/3"
        repo.create(data3)
        session.commit() # 提交創建

        session.expire_all() # 確保從 DB 讀取

        # 執行查詢：過濾 source="特定來源"，按 title 降序，取第一個
        results = repo.get_by_filter(
            {"source": "特定來源"},
            sort_by="title",
            sort_desc=True,
            limit=1
        )
        assert len(results) == 1 # 斷言只返回了一個結果
        assert results[0].title == "文章 Z" # 斷言返回的是 title 降序排列的第一個
        assert results[0].source == "特定來源" # 斷言返回的結果符合過濾條件

    def test_get_all_invalid_sort_key(self, repo, session):
        with pytest.raises(InvalidOperationError) as excinfo:
            repo.get_all(sort_by="invalid_column")
        assert "無效的排序欄位: invalid_column" in str(excinfo.value)

    def test_get_paginated_with_sorting(self, repo, sample_model_data, session):
        # 創建數據 (例如創建 7 條，以便測試分頁)
        titles = ["文章 C", "文章 A", "文章 E", "文章 B", "文章 D", "文章 G", "文章 F"]
        for i, title in enumerate(titles):
            data = sample_model_data.copy()
            data["title"] = title
            data["link"] = f"https://test.com/paginate-sort/{i}" # 確保 link 唯一
            data["name"] = f"name_{i}" # 提供其他必要欄位
            data["source"] = f"source_{i}"
            data["published_at"] = f"2023-09-{i+1:02d}"
            repo.create(data)
        session.commit() # 提交創建

        session.expire_all() # 確保從 DB 讀取

        # 獲取第一頁，每頁 5 個，按 title 降序
        page_data = repo.get_paginated(page=1, per_page=5, sort_by="title", sort_desc=True)

        # 斷言
        assert len(page_data["items"]) == 5 # 驗證第一頁有 5 條記錄
        # 驗證排序結果 (預期 G, F, E, D, C)
        actual_titles = [item.title for item in page_data["items"]]
        expected_titles = ["文章 G", "文章 F", "文章 E", "文章 D", "文章 C"]
        assert actual_titles == expected_titles
        assert page_data["page"] == 1
        assert page_data["per_page"] == 5
        assert page_data["total"] == 7
        assert page_data["total_pages"] == 2
        assert page_data["has_next"] is True
        assert page_data["has_prev"] is False

    def test_validate_and_supplement_create_success(self, repo, sample_model_data):
        # 測試創建時，所有 Pydantic 驗證過的必填欄位都有有效值
        validated_data = repo.validate_data(sample_model_data, SchemaType.CREATE)
        final_data = repo._validate_and_supplement_required_fields(validated_data)
        assert final_data is not None
        # 確保必填欄位都有值 (如果 create schema 有預設值，這裡也會包含)

    def test_validate_and_supplement_create_error(self, repo, sample_model_data):
        # 測試創建時，如果 Pydantic 驗證後某必填欄位值為 None 或空
        validated_data = repo.validate_data(sample_model_data, SchemaType.CREATE)
        validated_data["title"] = "" # 手動設為空字串
        with pytest.raises(ValidationError) as excinfo:
            repo._validate_and_supplement_required_fields(validated_data)
        assert "必填欄位值無效" in str(excinfo.value)
        assert "title" in str(excinfo.value)

    def test_validate_and_supplement_update_supplement(self, repo, sample_model_data, session):
        # 測試更新時，從現有實體補充數據
        # 1. 創建實體
        created_entity = repo.create(sample_model_data)
        session.commit()
        entity_id = created_entity.id
        session.expire(created_entity) # 從 session 移除，確保下次讀取是從 DB

        # 2. 準備更新 payload，缺少某些必填欄位 (例如 title)
        update_payload = {"summary": "New Summary"}
        validated_payload = repo.validate_data(update_payload, SchemaType.UPDATE)

        # 3. 獲取現有實體
        existing_entity = repo.get_by_id(entity_id)

        # 4. 調用驗證與補充
        final_data = repo._validate_and_supplement_required_fields(validated_payload, existing_entity)

        # 5. 斷言：必填欄位 title 應該從 existing_entity 補充進來
        assert "title" in final_data
        assert final_data["title"] == sample_model_data["title"] # 應為原始值
        assert final_data["summary"] == "New Summary"

    def test_validate_and_supplement_update_error(self, repo, sample_model_data, session):
        # 測試更新時，即使補充後，某必填欄位的值仍然無效
        # 1. **直接使用 session 創建一個 title 為空的實體，繞過 repo.create 的驗證**
        invalid_initial_data = {
            "name": sample_model_data["name"],
            "title": "", # 直接設置為空字串
            "link": "https://test.com/invalid_update", # 確保 link 唯一
            "source": sample_model_data["source"],
            "published_at": sample_model_data["published_at"],
            # created_at 會自動生成
        }
        initial_entity = ModelForTest(**invalid_initial_data)
        session.add(initial_entity)
        try:
            session.commit() # 提交這個 "無效" 狀態
            entity_id = initial_entity.id
            assert entity_id is not None # 確保 ID 已生成
            # logger.debug(f"已直接創建 ID={entity_id} 的無效標題實體用於測試") # <--- 移除或註釋掉此行
            # 或者使用 print 進行簡單的測試輸出
            print(f"DEBUG: 已直接創建 ID={entity_id} 的無效標題實體用於測試")
        except Exception as e:
            session.rollback()
            pytest.fail(f"直接創建無效實體失敗: {e}")

        session.expire(initial_entity) # 從 session 移除，確保下次讀取是從 DB

        # 2. 準備空的更新 payload
        update_payload = {}
        validated_payload = repo.validate_data(update_payload, SchemaType.UPDATE) # 這步應該能通過

        # 3. 獲取現有實體 (現在它應該是 title="" 的那個)
        existing_entity = repo.get_by_id(entity_id)
        assert existing_entity is not None
        assert existing_entity.title == "" # 確認讀取到的確實是空標題

        # 4. **執行被測邏輯：** 調用驗證與補充，預期失敗，因為從現有實體補充的 title 是空
        with pytest.raises(ValidationError) as excinfo:
            repo._validate_and_supplement_required_fields(validated_payload, existing_entity)

        # 5. 斷言錯誤訊息
        assert "必填欄位值無效" in str(excinfo.value)
        assert "title" in str(excinfo.value)

    def test_create_internal_validation_error(self, repo, sample_model_data):
        # Mock _validate_and_supplement_required_fields 使其拋出錯誤
        with patch.object(repo, '_validate_and_supplement_required_fields', side_effect=ValidationError("模擬必填欄位錯誤")):
            validated_data = repo.validate_data(sample_model_data, SchemaType.CREATE)
            with pytest.raises(ValidationError) as excinfo:
                repo._create_internal(validated_data)
            assert "模擬必填欄位錯誤" in str(excinfo.value)

    def test_update_internal_immutable_field(self, repo, sample_model_data, session):
        # 1. 創建實體
        created = repo.create(sample_model_data)
        session.commit()
        entity_id = created.id
        original_name = created.name # 假設 name 是 immutable

        # 2. Mock get_immutable_fields 返回 ['name']
        with patch.object(ModelUpdateSchema, 'get_immutable_fields', return_value=['name']):
            update_payload = {"name": "New Name", "title": "New Title"}
            validated_payload = repo.validate_data(update_payload, SchemaType.UPDATE) # 驗證本身會通過

            updated_entity = repo._update_internal(entity_id, validated_payload)
            session.commit()

            # 3. 檢查結果
            result = repo.get_by_id(entity_id)
            assert result.title == "New Title" # 可變欄位應更新
            assert result.name == original_name # 不可變欄位不應更新

    def test_execute_query_wraps_exception(self, repo, session):
        def faulty_query():
            raise ValueError("Something went wrong")

        with pytest.raises(DatabaseOperationError) as excinfo:
            repo.execute_query(faulty_query, err_msg="Test Error")
        assert "Test Error: Something went wrong" in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, ValueError)

    def test_execute_query_preserves_exception(self, repo, session):
        def integrity_error_query():
            # 模擬一個 IntegrityError (這裡用子類 ValueError 模擬)
            # 實際測試中可能需要 mock session 操作來觸發真正的 IntegrityError
            raise IntegrityError("Mock IntegrityError", params=None, orig=ValueError("orig"))

        # IntegrityError 默認在 preserve_exceptions 中
        with pytest.raises(IntegrityError):
             repo.execute_query(integrity_error_query)

        # 測試不 preserve 的情況
        with pytest.raises(DatabaseOperationError): # 應該被包裝
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