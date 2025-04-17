import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine, String
from sqlalchemy.orm import sessionmaker, Mapped, mapped_column, Session
from datetime import datetime, timezone
import pydantic
from typing import Dict, Any, Optional, Type, List, Tuple, Union, Literal, overload
import logging
from pydantic import BaseModel, field_validator
from typing import cast

from src.models.base_model import Base
from src.database.base_repository import BaseRepository, SchemaType
from src.database.database_manager import DatabaseManager
from src.services.base_service import BaseService
from src.error.errors import DatabaseOperationError, ValidationError
from src.models.base_schema import BaseCreateSchema, BaseUpdateSchema

# --- Setup logger for this test file --- 
logger = logging.getLogger(__name__)

# 測試用的 Pydantic Schema 類
class ModelCreateSchemaForTest(BaseCreateSchema):
    name: str
    title: str
    
    @field_validator('title')
    def validate_title(cls, v):
        if not v or not v.strip():
            raise ValueError("title不能為空")
        return v.strip()
    
    @staticmethod
    def get_required_fields() -> List[str]:
        """返回必填欄位列表"""
        return ["name", "title"]

class ModelUpdateSchemaForTest(BaseUpdateSchema):
    name: Optional[str] = None
    title: Optional[str] = None
    
    @classmethod
    def get_immutable_fields(cls) -> List[str]:
        """返回不可變更的欄位"""
        return [] + super().get_immutable_fields()

    @classmethod
    def get_updated_fields(cls) -> List[str]:
        """返回可更新欄位列表"""
        return ['name', 'title'] + super().get_updated_fields()

# 測試用模型類
class ModelForTest(Base):
    """測試用模型"""
    __tablename__ = 'test_service_model'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now(timezone.utc))

# 測試用 Repository 類
class RepositoryForTest(BaseRepository[ModelForTest]):
    
    # --- Implement get_schema_class (Removing overloads for simplicity) --- 
    # @overload
    # def get_schema_class(self) -> Type[ModelCreateSchemaForTest]: ...
    # 
    # @overload
    # def get_schema_class(self, schema_type: Literal[SchemaType.UPDATE]) -> Type[ModelUpdateSchemaForTest]: ...
    # 
    # @overload
    # def get_schema_class(self, schema_type: Literal[SchemaType.CREATE]) -> Type[ModelCreateSchemaForTest]: ...

    def get_schema_class(self, schema_type: SchemaType = SchemaType.CREATE) -> Type[Union[ModelCreateSchemaForTest, ModelUpdateSchemaForTest]]:
        """根據操作類型返回對應的schema類"""
        if schema_type == SchemaType.CREATE:
            return ModelCreateSchemaForTest
        elif schema_type == SchemaType.UPDATE:
            return ModelUpdateSchemaForTest
        raise ValueError(f"未支援的 schema 類型: {schema_type}")
    
    def validate_data(self, entity_data: Dict[str, Any], schema_type: SchemaType) -> Dict[str, Any]:
        """重寫 validate_data 方法，確保正確處理 Pydantic 驗證錯誤"""
        schema_class = self.get_schema_class(schema_type)
        try:
            # 執行 Pydantic 驗證
            instance = schema_class.model_validate(entity_data)
            
            # 根據類型返回不同的字典表示
            if schema_type == SchemaType.UPDATE:
                return instance.model_dump(exclude_unset=True)
            else:
                return instance.model_dump()
        except pydantic.ValidationError as e:
            # 將 Pydantic 驗證錯誤轉換為我們自己的 ValidationError
            error_msg = f"{schema_type.name} 資料驗證失敗: {str(e)}"
            raise ValidationError(error_msg) from e
    
    def create(self, entity_data: Dict[str, Any]) -> Optional[ModelForTest]:
        """創建測試實體，包含驗證和內部調用"""
        try:
            # 1. Pydantic Validation (using base class method)
            validated_data = self.validate_data(entity_data, SchemaType.CREATE)
            if validated_data is None: # Should not happen if validation fails, but check anyway
                raise DatabaseOperationError("創建時驗證返回 None")
                
            # 2. Call internal creation method
            created_entity = self._create_internal(validated_data)
            return created_entity
        except ValidationError as e:
            logger.error(f"創建 ModelForTest 驗證失敗: {e}")
            raise # Re-raise for service layer to handle
        except DatabaseOperationError as e:
            logger.error(f"創建 ModelForTest 時資料庫操作失敗: {e}")
            raise # Re-raise
        except Exception as e:
            logger.error(f"創建 ModelForTest 時發生未預期錯誤: {e}", exc_info=True)
            raise DatabaseOperationError(f"創建 ModelForTest 時發生未預期錯誤: {e}") from e
    
    def update(self, entity_id: Any, entity_data: Dict[str, Any]) -> Optional[ModelForTest]:
        """更新測試實體，包含驗證和內部調用"""
        try:
            # 1. Pydantic Validation (using base class method)
            # validate_data for UPDATE returns only provided fields (exclude_unset=True)
            validated_payload = self.validate_data(entity_data, SchemaType.UPDATE)
            
            if validated_payload is None: # Should not happen
                 raise DatabaseOperationError(f"更新驗證時發生內部錯誤，ID={entity_id}")
                 
            # If validation results in empty dict (no valid fields provided), _update_internal handles it
            if not validated_payload:
                logger.debug(f"更新 ModelForTest (ID={entity_id}) 驗證後的 payload 為空，無需更新資料庫。")
                # _update_internal will return None if no changes are made
            
            # 2. Call internal update method
            updated_entity = self._update_internal(entity_id, validated_payload)
            return updated_entity

        except ValidationError as e:
             logger.error(f"更新 ModelForTest (ID={entity_id}) 驗證失敗: {e}")
             raise # Re-raise for service layer
        except DatabaseOperationError as e:
             logger.error(f"更新 ModelForTest (ID={entity_id}) 時資料庫操作失敗: {e}")
             raise # Re-raise
        except Exception as e:
            logger.error(f"更新 ModelForTest (ID={entity_id}) 時發生未預期錯誤: {e}", exc_info=True)
            raise DatabaseOperationError(f"更新 ModelForTest (ID={entity_id}) 時發生未預期錯誤: {e}") from e

# 測試用 Service 類 - Refactored to follow ArticleService pattern
class ServiceForTest(BaseService[ModelForTest]):
    def _get_repository_mapping(self) -> Dict[str, tuple]:
        return {
            "test_repo": (RepositoryForTest, ModelForTest)
        }
    
    # --- Refactored create_test_entity --- 
    def create_test_entity(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with self._transaction() as session:
                repo = cast(RepositoryForTest, self._get_repository("test_repo", session))
                # Call repository's public create method
                new_entity = repo.create(data)
                
                if new_entity:
                    # *** Explicitly flush the session here ***
                    # This ensures the database generates the ID and SQLAlchemy updates the object
                    session.flush() 
                    
                    # Now the ID should be populated
                    entity_id = new_entity.id 
                    if entity_id is None:
                        # Should not happen after flush if PK is auto-generated
                        logger.error(f"創建實體後 Flush，但 ID 仍然為 None: {new_entity}")
                        return {'success': False, 'message': '創建後無法獲取實體 ID', 'entity_id': None}
                        
                    return {
                        'success': True,
                        'message': '實體創建成功',
                        'entity_id': entity_id # Return ID
                    }
                else:
                     # Should not happen if repo.create raises on error
                    return {'success': False, 'message': '實體創建失敗 (Repo 返回 None)', 'entity_id': None}
        except (ValidationError, DatabaseOperationError) as e:
            error_msg = f"創建測試實體失敗: {str(e)}"
            logger.error(error_msg)
            return {'success': False, 'message': error_msg, 'entity_id': None}
        except Exception as e:
            error_msg = f"創建測試實體時發生未預期錯誤: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'entity_id': None}
    
    # --- Refactored update_test_entity --- 
    def update_test_entity(self, entity_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with self._transaction() as session:
                repo = cast(RepositoryForTest, self._get_repository("test_repo", session))
                
                # Check existence first (optional, repo update might handle it)
                # existing = repo.get_by_id(entity_id)
                # if not existing:
                #     return {'success': False, 'message': f'ID={entity_id} 不存在，無法更新', 'updated_data': None}
                    
                # Call repository's public update method
                updated_entity = repo.update(entity_id, data)
                # Commit is handled by _transaction

                if updated_entity:
                     # Convert to dict before session closes
                    updated_data = {
                        "id": updated_entity.id,
                        "name": updated_entity.name,
                        "title": updated_entity.title
                    }
                    return {
                        'success': True,
                        'message': '實體更新成功',
                        'updated_data': updated_data
                    }
                else:
                    # repo.update returns None if not found or no changes
                    # We need to check if it existed before the call to be sure
                    existing_check = repo.get_by_id(entity_id) # Check again within same transaction
                    if existing_check:
                        return {'success': True, 'message': '實體更新完成 (無變更)', 'updated_data': None} # No change
                    else:
                        # This case should ideally be caught by repo.update raising error
                        return {'success': False, 'message': f'ID={entity_id} 不存在，無法更新', 'updated_data': None}
                        
        except (ValidationError, DatabaseOperationError) as e:
            error_msg = f"更新測試實體 ID={entity_id} 失敗: {str(e)}"
            logger.error(error_msg)
            return {'success': False, 'message': error_msg, 'updated_data': None}
        except Exception as e:
            error_msg = f"更新測試實體 ID={entity_id} 時發生未預期錯誤: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'updated_data': None}

    # --- Refactored get_test_entity --- 
    def get_test_entity(self, entity_id: int) -> Dict[str, Any]:
        try:
            with self._transaction() as session:
                repo = cast(RepositoryForTest, self._get_repository("test_repo", session))
                entity = repo.get_by_id(entity_id)
                if entity:
                    # Convert to dict before session closes
                    entity_data = {
                         "id": entity.id,
                         "name": entity.name,
                         "title": entity.title
                     }
                    return {'success': True, 'message': '獲取實體成功', 'entity_data': entity_data}
                else:
                    return {'success': False, 'message': '實體不存在', 'entity_data': None}
        except DatabaseOperationError as e:
            error_msg = f"獲取測試實體 ID={entity_id} 失敗: {str(e)}"
            logger.error(error_msg)
            return {'success': False, 'message': error_msg, 'entity_data': None}
        except Exception as e:
            error_msg = f"獲取測試實體 ID={entity_id} 時發生未預期錯誤: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'entity_data': None}

    # --- Refactored delete_test_entity --- 
    def delete_test_entity(self, entity_id: int) -> Dict[str, Any]:
        try:
            with self._transaction() as session:
                repo = cast(RepositoryForTest, self._get_repository("test_repo", session))
                
                deleted = repo.delete(entity_id)
                # Commit is handled by _transaction
                if deleted:
                    # Flush might still be needed depending on DB backend/isolation
                    session.flush() 
                    logger.info(f"實體 ID={entity_id} 刪除操作已提交。")
                    return {'success': True, 'message': '實體刪除成功'}
                else:
                    logger.warning(f"嘗試刪除實體 ID={entity_id} 失敗 (可能不存在)。")
                    return {'success': False, 'message': '實體刪除失敗 (可能不存在)'}
                        
        except (ValidationError, DatabaseOperationError) as e: # Catch potential IntegrityValidationError from repo.delete
            error_msg = f"刪除測試實體 ID={entity_id} 時發生錯誤: {str(e)}"
            logger.error(error_msg)
            # If it's an IntegrityValidationError, the message might be specific
            return {'success': False, 'message': error_msg}
        except Exception as e:
            error_msg = f"刪除測試實體 ID={entity_id} 時發生未預期錯誤: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg}

class TestBaseService:
    @pytest.fixture(scope="session")
    def engine(self):
        """創建測試用的資料庫引擎 (使用文件型 SQLite)"""
        # Use a file-based SQLite DB for better transaction persistence testing
        db_file = "./test_db_base_service.sqlite"
        engine = create_engine(f'sqlite:///{db_file}')
        # Ensure the file is cleaned up before tests run (optional, if needed)
        # import os
        # if os.path.exists(db_file): os.remove(db_file)
        yield engine
        # Cleanup after tests run
        # import os
        # if os.path.exists(db_file): os.remove(db_file)
    
    @pytest.fixture(scope="session")
    def tables(self, engine):
        """創建資料表結構"""
        # Clean up existing tables first if reusing file across sessions
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        yield
        # Optionally drop tables again after tests, or keep the file for inspection
        # Base.metadata.drop_all(engine)
    
    # Remove the db_manager fixture as we'll use a real one in test_service
    # @pytest.fixture(scope="function")
    # def db_manager(self, engine):
    #     ...
    
    @pytest.fixture(scope="function")
    def test_service(self, engine, tables): # Removed db_manager fixture dependency
        """為每個測試建立 TestService 實例，使用真實的 DatabaseManager"""
        # 創建一個真實的 DatabaseManager 實例
        # 我們需要確保它使用測試引擎，而不是預設配置
        real_db_manager = DatabaseManager() # Create instance
        # Override its engine and session factory to use the test engine
        real_db_manager.engine = engine
        real_db_manager.Session = sessionmaker(bind=engine)

        # 將配置好的真實 manager 傳遞給服務
        service = ServiceForTest(real_db_manager)
        yield service
        # Service cleanup might interact with the manager, which is fine
        service.cleanup()
    
    @pytest.fixture(scope="function")
    def sample_entity_data(self):
        """建立測試資料"""
        return {
            "name": "test_name",
            "title": "測試標題"
        }
    
    def test_get_repository_mapping(self, test_service):
        """測試儲存庫映射功能"""
        mapping = test_service._get_repository_mapping()
        assert "test_repo" in mapping
        assert mapping["test_repo"][0] == RepositoryForTest
        assert mapping["test_repo"][1] == ModelForTest
    
    def test_get_repository(self, test_service):
        """測試獲取儲存庫"""
        # 獲取一個 session 實例以傳遞給 _get_repository
        with test_service._transaction() as session:
            repo = test_service._get_repository("test_repo", session)
            assert isinstance(repo, RepositoryForTest)
            # 確保傳遞的 session 被使用
            assert repo.session is session
        
        # 移除對儲存庫快取的斷言，因為 BaseService 不再快取儲存庫實例
    
    def test_get_repository_unknown(self, test_service):
        """測試獲取未知儲存庫時拋出異常"""
        with test_service._transaction() as session:
            with pytest.raises(DatabaseOperationError) as excinfo:
                test_service._get_repository("unknown_repo", session)
            assert "未知的儲存庫名稱" in str(excinfo.value)
        
    # --- Updated test_create_entity --- 
    def test_create_entity(self, test_service, sample_entity_data):
        """測試創建實體"""
        result = test_service.create_test_entity(sample_entity_data)
        
        assert result['success'] is True
        assert result['message'] == '實體創建成功'
        entity_id = result['entity_id']
        assert entity_id is not None
        assert isinstance(entity_id, int)
        
        # Verify using the get method
        verify_result = test_service.get_test_entity(entity_id)
        assert verify_result['success'] is True
        created_data = verify_result['entity_data']
        assert created_data is not None
        assert created_data['id'] == entity_id
        assert created_data['name'] == sample_entity_data["name"]
        assert created_data['title'] == sample_entity_data["title"]

    # --- Updated test_create_entity_validation_error --- 
    def test_create_entity_validation_error(self, test_service):
        """測試創建實體時的驗證錯誤"""
        invalid_data = {
            "name": "test_name",
            "title": ""  # Empty title should fail validation
        }
        result = test_service.create_test_entity(invalid_data)
        
        assert result['success'] is False
        assert result['entity_id'] is None
        # Check for specific validation error message if possible
        assert "title不能為空" in result['message'] 
        # Or check based on the wrapped Pydantic error:
        assert "Validation Error" in result['message'] or "驗證失敗" in result['message']

    # --- Updated test_update_entity --- 
    def test_update_entity(self, test_service, sample_entity_data):
        """測試更新實體"""
        # Create first
        create_result = test_service.create_test_entity(sample_entity_data)
        assert create_result['success'] is True
        entity_id = create_result['entity_id']
        assert entity_id is not None
        
        # Update
        update_data = {
            "title": "更新後的標題"
        }
        update_result = test_service.update_test_entity(entity_id, update_data)
        
        assert update_result['success'] is True
        assert update_result['message'] == '實體更新成功'
        updated_data = update_result['updated_data']
        assert updated_data is not None
        assert updated_data['id'] == entity_id
        assert updated_data['title'] == update_data["title"]
        assert updated_data['name'] == sample_entity_data["name"] # Unchanged field

        # Verify with get method
        verify_result = test_service.get_test_entity(entity_id)
        assert verify_result['success'] is True
        current_data = verify_result['entity_data']
        assert current_data['title'] == update_data["title"]

    # --- Updated test_get_entity --- 
    def test_get_entity(self, test_service, sample_entity_data):
        """測試獲取實體"""
        # Create first
        create_result = test_service.create_test_entity(sample_entity_data)
        assert create_result['success'] is True
        entity_id = create_result['entity_id']
        assert entity_id is not None
        
        # Get
        get_result = test_service.get_test_entity(entity_id)
        
        assert get_result['success'] is True
        assert get_result['message'] == '獲取實體成功'
        entity_data = get_result['entity_data']
        assert entity_data is not None
        assert entity_data['id'] == entity_id
        assert entity_data['name'] == sample_entity_data["name"]
        assert entity_data['title'] == sample_entity_data["title"]

    # --- Updated test_delete_entity --- 
    def test_delete_entity(self, test_service, sample_entity_data):
        """測試刪除實體"""
        # Create first
        create_result = test_service.create_test_entity(sample_entity_data)
        assert create_result['success'] is True
        entity_id = create_result['entity_id']
        assert entity_id is not None
        
        # Delete
        delete_result = test_service.delete_test_entity(entity_id)
        
        assert delete_result['success'] is True
        assert delete_result['message'] == '實體刪除成功'
        
        # Verify deletion with get method
        verify_result = test_service.get_test_entity(entity_id)
        assert verify_result['success'] is False # Expect get to fail
        assert verify_result['message'] == '實體不存在'
        assert verify_result['entity_data'] is None # CRUCIAL CHECK

    # --- Updated test_delete_nonexistent_entity --- 
    def test_delete_nonexistent_entity(self, test_service):
        """測試刪除不存在的實體"""
        delete_result = test_service.delete_test_entity(999)
        assert delete_result['success'] is False
        assert '不存在' in delete_result['message'] # Check for non-existence message
    
    # --- Updated test_transaction_commit --- 
    def test_transaction_commit(self, test_service, sample_entity_data):
        """測試事務提交 (通過成功創建和讀取驗證)"""
        create_result = test_service.create_test_entity(sample_entity_data)
        assert create_result['success'] is True
        entity_id = create_result['entity_id']
        assert entity_id is not None
        
        # Verify existence after creation transaction committed
        verify_result = test_service.get_test_entity(entity_id)
        assert verify_result['success'] is True
        assert verify_result['entity_data'] is not None
        assert verify_result['entity_data']['id'] == entity_id

    # --- Updated test_transaction_rollback --- 
    def test_transaction_rollback(self, test_service, sample_entity_data):
        """測試事務回滾"""
        # Explicitly type the dictionary value as Optional[int]
        entity_id_holder: Dict[str, Optional[int]] = {'id': None}
        
        class RollbackError(Exception):
            pass # Custom exception to trigger rollback

        try:
            with test_service._transaction() as session:
                repo = cast(RepositoryForTest, test_service._get_repository("test_repo", session))
                new_entity = repo.create(sample_entity_data) # Use repo create directly to get ID within tx
                if new_entity:
                    session.flush() # Flush to get ID before potential rollback
                    entity_id_holder['id'] = new_entity.id
                    assert entity_id_holder['id'] is not None
                # Raise custom error *after* potential ID generation
                raise RollbackError("Intentional rollback") 
        except RollbackError:
            # Expected rollback path
            pass
        except Exception as e:
            pytest.fail(f"事務回滾測試中發生未預期錯誤: {e}")

        # Verify non-existence after rollback
        entity_id = entity_id_holder['id']
        if entity_id is not None:
            verify_result = test_service.get_test_entity(entity_id)
            assert verify_result['success'] is False
            assert verify_result['entity_data'] is None
        else:
             # If ID wasn't even generated, rollback is implicitly successful
            pass

    # --- Cleanup tests remain similar, just ensuring methods run --- 
    def test_cleanup(self, test_service):
        """測試資源清理 (驗證方法可被調用，但無特定斷言)"""
        # 創建一個 session 和 repo 以模擬使用情境
        with test_service._transaction() as session:
            repo = test_service._get_repository("test_repo", session)
            # 執行一些操作（可選）
            repo.session.execute(ModelForTest.__table__.select().limit(1))

        # 直接調用 cleanup
        # 由於 cleanup 現在只記錄日誌，沒有外部可觀察的狀態更改，
        # 這個測試主要確保方法可以被無錯誤地調用。
        try:
            test_service.cleanup()
        except Exception as e:
            pytest.fail(f"cleanup() 引發了未預期的異常: {e}")
        
        # 無需斷言 session.close 或 _repositories 清空
    
    def test_cleanup_error_handling(self, test_service):
        """測試清理過程中的異常處理 (驗證方法可被調用)"""
        # 創建一個 session 和 repo
        with test_service._transaction() as session:
            repo = test_service._get_repository("test_repo", session)
            # 可以選擇性地模擬 repo 或 session 的行為，但由於 cleanup 無操作，此處省略
            
        # 直接調用 cleanup，預期不拋出異常
        try:
            test_service.cleanup()
        except Exception as e:
            pytest.fail(f"cleanup() 引發了未預期的異常: {e}")
            
        # 無需斷言 session.close 或 _repositories 清空
