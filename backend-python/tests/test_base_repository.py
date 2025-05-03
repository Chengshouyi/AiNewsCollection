"""Tests for the BaseRepository functionality."""

# Standard library imports
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Type
from unittest.mock import patch
import logging

# Third party imports
import pytest
from pydantic import BaseModel, field_validator
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, Session
from sqlalchemy.exc import IntegrityError

# Local application imports
from src.database.base_repository import BaseRepository, SchemaType
from src.error.errors import (
    DatabaseOperationError,
    IntegrityValidationError,
    ValidationError,
    InvalidOperationError,
)
from src.models.base_model import Base
  # 使用統一的 logger

# flake8: noqa: F811
# pylint: disable=redefined-outer-name

# 使用統一的 logger
logger = logging.getLogger(__name__)  # 使用統一的 logger


# --- Test Schemas ---
class ModelCreateSchema(BaseModel):
    name: str
    title: str
    link: str
    source: str
    published_at: str
    summary: Optional[str] = None

    @field_validator("title")
    def validate_title(cls, v):  # pylint: disable=no-self-argument
        if not v or not v.strip():
            raise ValueError("title: 不能為空")
        if len(v) > 500:
            raise ValueError("title: 長度不能超過 500 字元")
        return v.strip()

    @field_validator("link")
    def validate_link(cls, v):  # pylint: disable=no-self-argument
        if not v or not v.strip():
            raise ValueError("link: 不能為空")
        if len(v) > 1000:
            raise ValueError("link: 長度不能超過 1000 字元")
        return v.strip()

    @classmethod
    def get_required_fields(cls) -> list:  # pylint: disable=no-self-argument
        """返回所有必填欄位名稱"""
        return ["name", "title", "link", "source", "published_at"]


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


# --- Test Model ---
class ModelForTest(Base):
    """測試用模型"""

    __tablename__ = "test_repository_model"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    link: Mapped[str] = mapped_column(String, unique=True)
    source: Mapped[str] = mapped_column(String)
    published_at: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now(timezone.utc))
    summary: Mapped[Optional[str]] = mapped_column(String, nullable=True)


# --- Test Repository ---
class ModelRepositoryforTest(BaseRepository[ModelForTest]):
    """實現 BaseRepository 抽象類以便測試"""

    @classmethod
    def get_schema_class(
        cls, schema_type: SchemaType = SchemaType.CREATE
    ) -> Type[BaseModel]:
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
        except (
            ValidationError,
            DatabaseOperationError,
            IntegrityValidationError,
        ) as e:
            raise e
        except Exception as e:
            raise DatabaseOperationError(f"創建時發生未預期錯誤: {e}") from e

    def update(
        self, entity_id: Any, entity_data: Dict[str, Any]
    ) -> Optional[ModelForTest]:
        """實現更新實體的抽象方法"""
        try:
            update_payload = self.validate_data(entity_data, SchemaType.UPDATE)
            if update_payload:
                return self._update_internal(entity_id, update_payload)
            return None
        except (
            ValidationError,
            DatabaseOperationError,
            IntegrityValidationError,
        ) as e:
            raise e
        except Exception as e:
            raise DatabaseOperationError(f"更新時發生未預期錯誤: {e}") from e


# --- Fixtures ---
@pytest.fixture(scope="function")
def initialized_db_manager(db_manager_for_test):
    """
    Fixture that depends on db_manager_for_test, creates tables, and yields the manager.
    Ensures tables are created before each test function.
    """
    logger.debug("Creating tables for test function...")
    # 嘗試訪問公共的 engine 屬性
    engine = db_manager_for_test.engine
    if engine is None:
        pytest.fail(
            "DatabaseManager did not provide a valid engine."
        )  # 添加檢查確保引擎有效

    try:
        # Ensure the specific model's table is created
        ModelForTest.metadata.create_all(bind=engine)  # 使用 MetaData 創建
        yield db_manager_for_test
    finally:
        logger.debug("Dropping tables after test function...")
        # Ensure the specific model's table is dropped using MetaData
        ModelForTest.metadata.drop_all(bind=engine)  # 使用 MetaData 刪除


@pytest.fixture(scope="function")
def repo_factory(initialized_db_manager):
    """提供一個工廠函數來創建綁定特定 session 的 repo 實例"""

    def _create_repo(session: Session):
        return ModelRepositoryforTest(session, ModelForTest)

    return _create_repo


@pytest.fixture(scope="function")
def sample_model_data():
    """建立測試數據資料，每個測試函數都有獨立的測試數據"""
    return {
        "name": "test_name",
        "title": "測試文章",
        "link": "https://test.com/article",
        "published_at": "2023-07-01",
        "source": "測試來源",
    }


@pytest.fixture(scope="function")
def sample_model_data_list(sample_model_data):
    """建立多個測試數據資料"""
    data_list = []
    for i in range(5):
        data = sample_model_data.copy()
        data["name"] = f"name_{i}"
        data["title"] = f"測試文章{i}"
        data["link"] = f"https://test.com/article/{i}"  # 確保 link 唯一
        data["source"] = f"來源 {chr(ord('A') + i)}"  # A, B, C, D, E
        data["published_at"] = f"2023-01-{(i+1):02d}"
        data_list.append(data)
    return data_list


# --- Test Class ---
class TestBaseRepository:
    def test_create_entity(
        self, repo_factory, initialized_db_manager, sample_model_data
    ):
        """測試創建實體的基本功能"""
        entity_id = None  # 初始化 entity_id
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            created_entity = repo.create(sample_model_data)
            session.flush()
            assert created_entity is not None
            assert created_entity.id is not None  # 現在 ID 應該已填充
            entity_id = created_entity.id
        # Commit happens automatically by session_scope

        # 在新的 session 中驗證
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            # Use repo method to get data
            result = repo.get_by_id(entity_id)  # 使用之前獲取的 entity_id

            assert result is not None
            assert result.id == entity_id
            assert result.title == "測試文章"
            assert result.link == "https://test.com/article"

    def test_create_entity_with_schema_internal_logic(
        self, repo_factory, initialized_db_manager, sample_model_data
    ):
        """測試 validate_data 和 _create_internal 的協同工作"""
        entity_id = None  # 初始化 entity_id
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            data_with_schema = sample_model_data.copy()

            validated_data = repo.validate_data(data_with_schema, SchemaType.CREATE)
            assert validated_data is not None
            assert "title" in validated_data
            assert validated_data["title"] == "測試文章"
            assert all(
                key in validated_data for key in ModelCreateSchema.get_required_fields()
            )

            # Note: _create_internal is protected, ideally test through public `create`
            # Here we call it directly assuming it's okay for this test setup
            created_entity = repo._create_internal(validated_data)
            assert created_entity is not None
            session.flush()  # <--- 在斷言 ID 之前 flush
            assert created_entity.id is not None  # 現在 ID 應該已填充
            entity_id = created_entity.id
            # Commit happens via session_scope

        # 在新的 session 中驗證
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            result = repo.get_by_id(entity_id)  # 使用之前獲取的 entity_id
            assert result is not None
            assert result.id == entity_id
            assert result.title == "測試文章"
            assert result.link == "https://test.com/article"

    def test_create_entity_validation_error(self, repo_factory, initialized_db_manager):
        """測試創建實體時捕獲自定義的 ValidationError"""
        invalid_data = {
            "name": "test_name",
            "title": "",  # 空標題 -> 觸發 Pydantic 驗證器
            "link": "https://test.com/article",
            "published_at": "2023-07-01",
            "source": "測試來源",
        }

        with initialized_db_manager.session_scope():  # No commit needed as error happens before
            with pytest.raises(ValidationError) as excinfo:
                # Need repo instance even if commit fails
                repo = repo_factory(
                    initialized_db_manager.get_session()
                )  # Use factory, get session directly
                repo.create(invalid_data)

        assert "不能為空" in str(excinfo.value)

    def test_update_entity(
        self, repo_factory, initialized_db_manager, sample_model_data
    ):
        """測試更新實體的基本功能"""
        entity_id = None
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            created_entity = repo.create(sample_model_data)
            session.flush()  # <--- 在斷言 ID 之前 flush
            assert created_entity is not None and created_entity.id is not None
            entity_id = created_entity.id
            # Commit via scope

        update_data = {"title": "更新後的文章", "summary": "這是更新後的摘要"}
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            updated_entity = repo.update(entity_id, update_data)
            assert updated_entity is not None
            # Commit via scope

        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            result = repo.get_by_id(entity_id)
            assert result is not None
            assert result.id == entity_id
            assert result.title == "更新後的文章"
            assert result.summary == "這是更新後的摘要"
            assert result.link == "https://test.com/article"

    def test_update_entity_with_schema_internal_logic(
        self, repo_factory, initialized_db_manager, sample_model_data
    ):
        """測試 validate_data 和 _update_internal 的協同工作"""
        entity_id = None
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            created_entity = repo.create(sample_model_data)
            assert created_entity is not None  # 先確認物件已創建
            session.flush()  # <--- 在斷言 ID 之前 flush
            assert created_entity.id is not None  # 現在 ID 應該已填充
            entity_id = created_entity.id
            # Commit via scope

        update_data = {
            "title": "使用Schema更新後的文章",
            "summary": "這是使用Schema更新後的摘要",
        }
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            validated_payload = repo.validate_data(update_data, SchemaType.UPDATE)
            assert validated_payload is not None
            assert "title" in validated_payload
            assert validated_payload["title"] == "使用Schema更新後的文章"
            assert "summary" in validated_payload
            assert "link" not in validated_payload

            # Test internal directly (assuming ok for test)
            updated_entity = repo._update_internal(entity_id, validated_payload)
            assert updated_entity is not None
            # Commit via scope

        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            result = repo.get_by_id(entity_id)
            assert result is not None
            assert result.id == entity_id
            assert result.title == "使用Schema更新後的文章"
            assert result.summary == "這是使用Schema更新後的摘要"

    def test_update_nonexistent_entity(self, repo_factory, initialized_db_manager):
        """測試更新不存在的實體時拋出 DatabaseOperationError"""
        non_existent_id = 999
        with initialized_db_manager.session_scope() as session:  # No commit needed
            repo = repo_factory(session)  # Use factory
            with pytest.raises(DatabaseOperationError) as excinfo:
                repo.update(non_existent_id, {"title": "新標題"})

        assert f"找不到ID為{non_existent_id}的實體" in str(excinfo.value)

    def test_delete_entity(
        self, repo_factory, initialized_db_manager, sample_model_data
    ):
        """測試刪除實體的基本功能"""
        entity_id = None
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            created_entity = repo.create(sample_model_data)
            session.flush()  # <--- 在斷言 ID 之前 flush
            assert created_entity is not None and created_entity.id is not None
            entity_id = created_entity.id
            # Commit via scope

        delete_result = False
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            delete_result = repo.delete(entity_id)
            # Commit via scope

        assert delete_result is True
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            assert repo.get_by_id(entity_id) is None

    def test_delete_nonexistent_entity(self, repo_factory, initialized_db_manager):
        """測試刪除不存在的實體返回 False"""
        non_existent_id = 999
        delete_result = False
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            delete_result = repo.delete(non_existent_id)
            # Commit via scope

        assert delete_result is False

    def test_get_by_id(self, repo_factory, initialized_db_manager, sample_model_data):
        """測試根據 ID 獲取實體"""
        entity_id = None
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            created_entity = repo.create(sample_model_data)
            session.flush()
            assert created_entity is not None and created_entity.id is not None
            entity_id = created_entity.id
        # Commit via scope

        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            result = repo.get_by_id(entity_id)
            assert result is not None
            assert result.id == entity_id
            assert result.title == "測試文章"

    def test_find_all_basic(
        self, repo_factory, initialized_db_manager, sample_model_data_list
    ):
        """測試 find_all 獲取所有實體 (非預覽模式)"""
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            for data in sample_model_data_list:
                repo.create(data)
            # Commit via scope

        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            results = repo.find_all()
            assert results is not None
            assert len(results) == len(sample_model_data_list)
            assert all(isinstance(item, ModelForTest) for item in results)

    def test_find_all_with_sorting(
        self, repo_factory, initialized_db_manager, sample_model_data_list
    ):
        """測試 find_all 獲取所有實體並排序 (非預覽模式)"""
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            for data in sample_model_data_list:
                repo.create(data)
            # Commit via scope

        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            results_asc = repo.find_all(sort_by="title", sort_desc=False)
            assert [item.title for item in results_asc] == [
                f"測試文章{i}" for i in range(5)
            ]
            assert all(isinstance(item, ModelForTest) for item in results_asc)

        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            results_desc = repo.find_all(sort_by="title", sort_desc=True)
            assert [item.title for item in results_desc] == [
                f"測試文章{i}" for i in range(4, -1, -1)
            ]
            assert all(isinstance(item, ModelForTest) for item in results_desc)

    def test_find_all_with_pagination(
        self, repo_factory, initialized_db_manager, sample_model_data_list
    ):
        """測試 find_all 獲取所有實體並分頁 (非預覽模式)"""
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            for data in sample_model_data_list:
                repo.create(data)
            # Commit via scope

        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            # Note: Default sorting might affect which items are returned
            # Add explicit sort for predictable pagination results
            results = repo.find_all(sort_by="name", sort_desc=False, limit=2, offset=2)
            assert len(results) == 2
            assert results[0].title == "測試文章2"  # Expecting item 2 (index 2)
            assert results[1].title == "測試文章3"  # Expecting item 3 (index 3)
            assert all(isinstance(item, ModelForTest) for item in results)

    def test_find_all_preview(
        self, repo_factory, initialized_db_manager, sample_model_data_list
    ):
        """測試 find_all 預覽模式"""
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            for data in sample_model_data_list:
                repo.create(data)
            # Commit via scope

        preview_fields = ["title", "link"]
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            results = repo.find_all(is_preview=True, preview_fields=preview_fields)

            assert results is not None
            assert len(results) == len(sample_model_data_list)
            assert all(isinstance(item, dict) for item in results)
            for item in results:
                assert set(item.keys()) == set(preview_fields)
                assert item["title"].startswith("測試文章")

    def test_find_all_preview_with_sort_limit(
        self, repo_factory, initialized_db_manager, sample_model_data_list
    ):
        """測試 find_all 預覽模式帶排序和分頁"""
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            for data in sample_model_data_list:
                repo.create(data)
            # Commit via scope

        preview_fields = ["name", "source"]
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            results = repo.find_all(
                sort_by="source",
                sort_desc=False,
                limit=2,
                offset=1,
                is_preview=True,
                preview_fields=preview_fields,
            )

            assert len(results) == 2
            assert all(isinstance(item, dict) for item in results)
            assert results[0]["source"] == "來源 B"
            assert results[0]["name"] == "name_1"
            assert results[1]["source"] == "來源 C"
            assert results[1]["name"] == "name_2"
            assert set(results[0].keys()) == set(preview_fields)

    def test_find_all_preview_invalid_fields(
        self, repo_factory, initialized_db_manager, sample_model_data_list
    ):
        """測試 find_all 預覽模式但欄位無效，應返回完整物件"""
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            for data in sample_model_data_list:
                repo.create(data)
            # Commit via scope

        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            results = repo.find_all(
                is_preview=True, preview_fields=["invalid_field", "non_existent"]
            )
            assert len(results) == len(sample_model_data_list)
            # It should return full model instances if preview fields are invalid
            assert all(isinstance(item, ModelForTest) for item in results)

    def test_find_all_invalid_sort_key(self, repo_factory, initialized_db_manager):
        """測試 find_all 使用無效排序欄位"""
        with initialized_db_manager.session_scope() as session:  # No db action needed, just repo call
            repo = repo_factory(session)  # Use factory
            with pytest.raises(InvalidOperationError) as excinfo:
                repo.find_all(sort_by="invalid_column")
        assert "無效的排序欄位: invalid_column" in str(excinfo.value)

    def test_integrity_error_handling_on_commit(
        self, repo_factory, initialized_db_manager, sample_model_data
    ):
        """測試在 session_scope 結束時捕獲 sqlalchemy.exc.IntegrityError (Unique Constraint)"""
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            repo.create(sample_model_data)
            # Commit via scope

        # Try to create again, violating unique constraint
        with pytest.raises(DatabaseOperationError) as excinfo:
            with initialized_db_manager.session_scope() as session:
                repo = repo_factory(session)  # Use factory
                repo.create(sample_model_data)
                # Error occurs on commit at scope exit

        assert "UNIQUE constraint failed" in str(excinfo.value)
        assert "test_repository_model.link" in str(excinfo.value)

        # Verify rollback happened (no second entry)
        with initialized_db_manager.session_scope() as session:
            # No need for repo factory here, just querying count
            count = session.query(ModelForTest).count()
            assert count == 1

    def test_get_schema_class(self, repo_factory, initialized_db_manager):
        """測試獲取schema類的方法"""
        # Need an instance to call the method, but doesn't need db interaction
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            assert repo.get_schema_class(SchemaType.CREATE) == ModelCreateSchema
            assert repo.get_schema_class(SchemaType.UPDATE) == ModelUpdateSchema
            assert repo.get_schema_class(SchemaType.LIST) == ModelCreateSchema
            assert repo.get_schema_class(SchemaType.DETAIL) == ModelCreateSchema
            assert repo.get_schema_class() == ModelCreateSchema

    def test_validate_data(
        self, repo_factory, initialized_db_manager, sample_model_data
    ):
        """測試 validate_data 方法"""
        # Need an instance to call the method
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            validated_create = repo.validate_data(sample_model_data, SchemaType.CREATE)
            assert validated_create is not None
            assert validated_create["title"] == "測試文章"
            assert validated_create["link"] == "https://test.com/article"
            assert all(
                key in validated_create
                for key in ModelCreateSchema.get_required_fields()
            )

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

    def test_validate_and_supplement_create_success(
        self, repo_factory, initialized_db_manager, sample_model_data
    ):
        """測試 _validate_and_supplement_required_fields 創建成功"""
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            validated_data = repo.validate_data(sample_model_data, SchemaType.CREATE)
            # Simulate calling internal method (assuming ok for test)
            final_data = repo._validate_and_supplement_required_fields(validated_data)
            assert final_data is not None

    def test_validate_and_supplement_create_error(
        self, repo_factory, initialized_db_manager, sample_model_data
    ):
        """測試 _validate_and_supplement_required_fields 創建失敗"""
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            validated_data = repo.validate_data(sample_model_data, SchemaType.CREATE)
            validated_data["title"] = ""  # Make it invalid *after* initial validation
            with pytest.raises(ValidationError) as excinfo:
                # Simulate calling internal method
                repo._validate_and_supplement_required_fields(validated_data)
            assert "必填欄位值無效" in str(excinfo.value)
            assert "title" in str(excinfo.value)

    def test_validate_and_supplement_update_supplement(
        self, repo_factory, initialized_db_manager, sample_model_data
    ):
        """測試 _validate_and_supplement_required_fields 更新補充"""
        entity_id = None
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            created_entity = repo.create(sample_model_data)
            assert created_entity is not None
            session.flush()  # <--- 加入 flush 確保 ID 生成
            assert created_entity.id is not None
            entity_id = created_entity.id
            # Commit via scope

        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            update_payload = {"summary": "New Summary"}
            validated_payload = repo.validate_data(update_payload, SchemaType.UPDATE)

            existing_entity = repo.get_by_id(entity_id)
            assert existing_entity is not None  # <--- 增加斷言，確認實體已找到

            # Simulate internal call
            final_data = repo._validate_and_supplement_required_fields(
                validated_payload, existing_entity
            )

            assert "title" in final_data
            assert final_data["title"] == sample_model_data["title"]
            assert final_data["summary"] == "New Summary"

    def test_validate_and_supplement_update_error(
        self, repo_factory, initialized_db_manager, sample_model_data
    ):
        """測試 _validate_and_supplement_required_fields 更新檢查到無效的現有值"""
        entity_id = None
        # Create an entity with an initially invalid field (bypassing repo.create validation)
        with initialized_db_manager.session_scope() as session:
            # repo = repo_factory(session) # No repo needed here, directly use model
            invalid_initial_data = sample_model_data.copy()
            invalid_initial_data["title"] = ""
            invalid_initial_data["link"] = "https://test.com/invalid_update"
            initial_entity = ModelForTest(**invalid_initial_data)
            session.add(initial_entity)
            # Commit via scope

        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            # Fetch the invalid entity
            existing_entity = (
                session.query(ModelForTest)
                .filter_by(link="https://test.com/invalid_update")
                .first()
            )
            assert existing_entity is not None
            assert existing_entity.title == ""
            entity_id = existing_entity.id

            update_payload = (
                {}
            )  # Empty update, should trigger check on existing required fields
            validated_payload = repo.validate_data(update_payload, SchemaType.UPDATE)

            with pytest.raises(ValidationError) as excinfo:
                # Simulate internal call
                repo._validate_and_supplement_required_fields(
                    validated_payload, existing_entity
                )

        assert "必填欄位值無效" in str(excinfo.value)
        assert "title" in str(excinfo.value)

    def test_create_internal_validation_error(
        self, repo_factory, initialized_db_manager, sample_model_data
    ):
        """測試 _create_internal 捕捉 _validate_and_supplement 的錯誤"""
        with initialized_db_manager.session_scope() as session:  # No commit needed
            repo = repo_factory(session)  # Use factory
            # Mock the internal validation to raise an error
            with patch.object(
                repo,
                "_validate_and_supplement_required_fields",
                side_effect=ValidationError("模擬必填欄位錯誤"),
            ):
                validated_data = repo.validate_data(
                    sample_model_data, SchemaType.CREATE
                )
                with pytest.raises(ValidationError) as excinfo:
                    # Simulate internal call
                    repo._create_internal(validated_data)
            assert "模擬必填欄位錯誤" in str(excinfo.value)

    def test_update_internal_immutable_field(
        self, repo_factory, initialized_db_manager, sample_model_data
    ):
        """測試 _update_internal 忽略不可變欄位"""
        entity_id = None
        original_name = sample_model_data["name"]
        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            created = repo.create(sample_model_data)
            assert created is not None  # 確認物件已創建
            session.flush()  # <--- 加入 flush 確保 ID 生成
            assert created.id is not None  # 確保 ID 確實已生成
            entity_id = created.id
            # Commit via scope

        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            # Mock get_immutable_fields for the update schema
            with patch.object(
                ModelUpdateSchema, "get_immutable_fields", return_value=["name"]
            ):
                update_payload = {"name": "New Name", "title": "New Title"}
                # Note: validate_data with UPDATE schema doesn't include 'name' by default if not provided
                # We are testing _update_internal directly, so we pass the validated payload
                # Assume validation happened correctly before
                validated_payload = repo.validate_data(
                    {"title": "New Title"}, SchemaType.UPDATE
                )
                # Manually add 'name' to simulate it being in the payload passed to _update_internal
                # This is slightly artificial but tests the desired logic within _update_internal
                validated_payload_for_internal = validated_payload.copy()
                validated_payload_for_internal["name"] = "New Name"

                updated_entity = repo._update_internal(
                    entity_id,
                    validated_payload_for_internal,  # 現在 entity_id 應該有值了
                )
                # Commit via scope

        with initialized_db_manager.session_scope() as session:
            repo = repo_factory(session)  # Use factory
            result = repo.get_by_id(entity_id)
            assert result.title == "New Title"  # Title should be updated
            assert result.name == original_name  # Name should remain unchanged

    def test_execute_query_wraps_exception(self, repo_factory, initialized_db_manager):
        """測試 execute_query 正常包裝非預期異常"""

        def faulty_query():
            raise ValueError("Something went wrong")

        with initialized_db_manager.session_scope() as session:  # No db action needed
            repo = repo_factory(session)  # Use factory
            with pytest.raises(DatabaseOperationError) as excinfo:
                repo.execute_query(faulty_query, err_msg="Test Error")
        assert "Test Error: Something went wrong" in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, ValueError)

    def test_execute_query_preserves_exception(
        self, repo_factory, initialized_db_manager
    ):
        """測試 execute_query 保留指定的異常類型"""

        def integrity_error_query():
            # Simulate an IntegrityError
            raise IntegrityError(
                "Mock IntegrityError", params=None, orig=ValueError("orig")
            )

        with initialized_db_manager.session_scope() as session:  # No db action needed
            repo = repo_factory(session)  # Use factory
            # By default, IntegrityError should be preserved
            with pytest.raises(IntegrityError):
                repo.execute_query(integrity_error_query)

            # If we explicitly say not to preserve it, it should be wrapped
            with pytest.raises(DatabaseOperationError):
                repo.execute_query(integrity_error_query, preserve_exceptions=[])

    def test_validate_data_as_classmethod(self, sample_model_data):
        """測試可以直接通過類調用 validate_data"""
        # No DB needed for this test
        validated_create = ModelRepositoryforTest.validate_data(
            sample_model_data, SchemaType.CREATE
        )
        assert validated_create is not None
        assert validated_create["title"] == "測試文章"
