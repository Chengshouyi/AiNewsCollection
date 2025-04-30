"""本模組測試 BaseCreateSchema 與 BaseUpdateSchema 的功能與資料庫互動。"""

# flake8: noqa: F811
# pylint: disable=redefined-outer-name

from datetime import datetime, timezone, timedelta
from typing import Optional
import logging

import pytest
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.error.errors import ValidationError
from src.models.base_model import Base
from src.models.base_schema import BaseCreateSchema, BaseUpdateSchema


logger = logging.getLogger(__name__)  # 使用統一的 logger


class ModelForTest(Base):
    __tablename__ = "test_schema_model"
    name: Mapped[str] = mapped_column(String(50))


class CreateSchemaForTest(BaseCreateSchema):
    name: str


class UpdateSchemaForTest(BaseUpdateSchema):
    name: Optional[str] = None


@pytest.fixture(scope="function")
def initialized_db_manager(db_manager_for_test):
    """初始化測試資料庫管理器並創建表"""
    try:
        db_manager_for_test.create_tables(Base)
        yield db_manager_for_test
    finally:
        pass


def test_base_create_schema_default_values():
    """測試BaseCreateSchema的默認值設置"""
    before_create = datetime.now(timezone.utc)
    schema = CreateSchemaForTest(name="test")
    after_create = datetime.now(timezone.utc)

    assert schema.name == "test"
    assert schema.id is None
    assert schema.created_at is not None
    assert before_create <= schema.created_at <= after_create


def test_base_create_schema_custom_values():
    """測試BaseCreateSchema使用自定義值"""
    custom_time = datetime.now(timezone.utc) - timedelta(days=1)
    schema = CreateSchemaForTest(id=1, name="test", created_at=custom_time)

    assert schema.id == 1
    assert schema.name == "test"
    assert schema.created_at == custom_time


def test_base_update_schema_default_values():
    """測試BaseUpdateSchema的默認值設置"""
    before_update = datetime.now(timezone.utc)
    schema = UpdateSchemaForTest()
    after_update = datetime.now(timezone.utc)

    assert schema.updated_at is not None
    assert before_update <= schema.updated_at <= after_update


def test_base_update_schema_custom_values():
    """測試BaseUpdateSchema使用自定義值"""
    custom_time = datetime.now(timezone.utc) - timedelta(days=1)
    schema = UpdateSchemaForTest(name="updated", updated_at=custom_time)

    assert schema.name == "updated"
    assert schema.updated_at == custom_time


def test_immutable_fields():
    """測試不可變字段"""
    immutable_fields = UpdateSchemaForTest.get_immutable_fields()
    assert "id" in immutable_fields
    assert "created_at" in immutable_fields


def test_updated_fields():
    """測試自動更新字段"""
    updated_fields = UpdateSchemaForTest.get_updated_fields()
    assert "updated_at" in updated_fields


def test_create_model_in_db(initialized_db_manager):
    """測試在資料庫中創建模型實例"""
    with initialized_db_manager.session_scope() as session:
        create_data = CreateSchemaForTest(name="Test Model")
        db_model = ModelForTest(**create_data.model_dump())
        session.add(db_model)
        session.flush()
        model_id = db_model.id

    with initialized_db_manager.session_scope() as session:
        saved_model = session.get(ModelForTest, model_id)
        assert saved_model is not None
        assert saved_model.id is not None
        assert saved_model.name == "Test Model"
        assert saved_model.created_at is not None
        assert (
            datetime.now(timezone.utc) - saved_model.created_at
        ).total_seconds() < 10


def test_update_model_in_db(initialized_db_manager):
    """測試在資料庫中更新模型實例"""
    with initialized_db_manager.session_scope() as session:
        create_data = CreateSchemaForTest(name="Original Name")
        db_model = ModelForTest(**create_data.model_dump())
        session.add(db_model)
        session.flush()
        model_id = db_model.id

    with initialized_db_manager.session_scope() as session:
        model_to_update = session.get(ModelForTest, model_id)
        update_data = UpdateSchemaForTest(name="Updated Name")

        exclude_fields = set(UpdateSchemaForTest.get_immutable_fields())
        model_data = update_data.model_dump(exclude=exclude_fields)
        for key, value in model_data.items():
            if value is not None:
                setattr(model_to_update, key, value)
        session.flush()

    with initialized_db_manager.session_scope() as session:
        updated_model = session.get(ModelForTest, model_id)
        assert updated_model.name == "Updated Name"
        assert updated_model.updated_at is not None
        assert (
            datetime.now(timezone.utc) - updated_model.updated_at
        ).total_seconds() < 10
        assert updated_model.created_at is not None


def test_validate_positive_int():
    """測試正整數驗證"""
    valid_schema = CreateSchemaForTest(id=10, name="test")
    assert valid_schema.id == 10

    with pytest.raises(ValidationError):
        CreateSchemaForTest(id=-1, name="test")

    with pytest.raises(ValidationError):
        CreateSchemaForTest(id=0, name="test")


def test_validate_datetime():
    """測試datetime驗證"""
    valid_time = datetime.now(timezone.utc)
    valid_schema = CreateSchemaForTest(created_at=valid_time, name="test")
    assert valid_schema.created_at == valid_time

    iso_time_string = "2023-01-01T12:00:00Z"
    parsed_datetime = datetime.fromisoformat(iso_time_string.replace("Z", "+00:00"))
    str_schema = CreateSchemaForTest(created_at=parsed_datetime, name="test")
    created_at_value = str_schema.created_at
    assert isinstance(created_at_value, datetime)
    assert created_at_value.year == 2023
    assert created_at_value.month == 1
    assert created_at_value.day == 1


def test_concurrent_model_operations(initialized_db_manager):
    """測試並發模型操作，確保資料隔離"""
    model_ids = []

    with initialized_db_manager.session_scope() as session:
        for i in range(5):
            create_data = CreateSchemaForTest(name=f"Model {i}")
            db_model = ModelForTest(**create_data.model_dump())
            session.add(db_model)
            session.flush()
            model_ids.append(db_model.id)

    with initialized_db_manager.session_scope() as session:
        for i, model_id in enumerate(model_ids):
            model = session.get(ModelForTest, model_id)
            update_data = UpdateSchemaForTest(name=f"Updated Model {i}")

            exclude_fields = set(UpdateSchemaForTest.get_immutable_fields())
            model_data = update_data.model_dump(exclude=exclude_fields)
            for key, value in model_data.items():
                if value is not None:
                    setattr(model, key, value)
        session.flush()

    with initialized_db_manager.session_scope() as session:
        for i, model_id in enumerate(model_ids):
            updated_model = session.get(ModelForTest, model_id)
            assert updated_model.name == f"Updated Model {i}"
            assert updated_model.updated_at is not None


def test_empty_database(initialized_db_manager):
    """測試空資料庫操作"""
    with initialized_db_manager.session_scope() as session:
        count = session.query(ModelForTest).count()
        assert count == 0

        non_existent = session.get(ModelForTest, 9999)
        assert non_existent is None


def test_model_dump_with_exclude_include():
    """測試Pydantic v2的model_dump方法中exclude和include參數"""
    schema = CreateSchemaForTest(id=100, name="Test Exclude Include")

    dump_exclude = schema.model_dump(exclude={"id"})
    assert "name" in dump_exclude
    assert "created_at" in dump_exclude
    assert "id" not in dump_exclude

    dump_include = schema.model_dump(include={"name"})
    assert "name" in dump_include
    assert "created_at" not in dump_include
    assert "id" not in dump_include


def test_model_json_serialization():
    """測試Pydantic v2的model_json_schema方法"""
    schema_dict = CreateSchemaForTest.model_json_schema()

    assert "properties" in schema_dict
    assert "name" in schema_dict["properties"]
    assert "id" in schema_dict["properties"]
    assert "created_at" in schema_dict["properties"]

    assert "required" in schema_dict
    assert "name" in schema_dict["required"]
