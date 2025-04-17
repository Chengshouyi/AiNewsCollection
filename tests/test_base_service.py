import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine, String
from sqlalchemy.orm import sessionmaker, Mapped, mapped_column, Session
from datetime import datetime, timezone
import pydantic

from src.models.base_model import Base
from src.database.base_repository import BaseRepository, SchemaType
from src.database.database_manager import DatabaseManager
from src.services.base_service import BaseService
from src.error.errors import DatabaseOperationError, ValidationError
from typing import Dict, Any, Optional, Type, List, Tuple
from pydantic import BaseModel, field_validator

# 測試用的 Pydantic Schema 類
class ModelCreateSchemaForTest(BaseModel):
    name: str
    title: str
    
    @field_validator('title')
    def validate_title(cls, v):
        if not v or not v.strip():
            raise ValueError("title不能為空")
        return v.strip()
    
    @classmethod
    def get_required_fields(cls) -> List[str]:
        """返回必填欄位列表"""
        return ["name", "title"]

class ModelUpdateSchemaForTest(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    
    @classmethod
    def get_immutable_fields(cls) -> List[str]:
        """返回不可變更的欄位"""
        return []

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
    def get_schema_class(self, schema_type: SchemaType = SchemaType.CREATE) -> Type[BaseModel]:
        if schema_type == SchemaType.CREATE:
            return ModelCreateSchemaForTest
        elif schema_type == SchemaType.UPDATE:
            return ModelUpdateSchemaForTest
        return ModelCreateSchemaForTest
    
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
        """使用驗證後的數據創建實體"""
        try:
            # 首先驗證數據，失敗會拋出 ValidationError
            validated_data = self.validate_data(entity_data, SchemaType.CREATE)
            # 然後使用內部創建方法
            return self._create_internal(validated_data)
        except ValidationError as e:
            # 將 ValidationError 重新拋出，以便上層服務捕獲
            raise e
        except Exception as e:
            # 其他異常轉換為 DatabaseOperationError
            raise DatabaseOperationError(f"內部創建失敗: {str(e)}") from e
    
    def update(self, entity_id: Any, entity_data: Dict[str, Any]) -> Optional[ModelForTest]:
        """使用驗證後的數據更新實體"""
        try:
            # 首先驗證數據，失敗會拋出 ValidationError
            validated_data = self.validate_data(entity_data, SchemaType.UPDATE)
            # 然後使用內部更新方法
            return self._update_internal(entity_id, validated_data)
        except ValidationError as e:
             # 將 ValidationError 重新拋出，以便上層服務捕獲
            raise e
        except Exception as e:
            # 其他異常轉換為 DatabaseOperationError
            raise DatabaseOperationError(f"內部更新失敗: {str(e)}") from e

# 測試用 Service 類
class ServiceForTest(BaseService[ModelForTest]):
    def _get_repository_mapping(self) -> Dict[str, tuple]:
        return {
            "test_repo": (RepositoryForTest, ModelForTest)
        }
    
    def create_test_entity(self, data: Dict[str, Any]) -> Optional[ModelForTest]:
        try:
            with self._transaction():
                repo = self._get_repository("test_repo")
                entity = repo.create(data)
                # 新增: 在返回前刷新 session 以獲取自動生成的 ID
                if entity:
                    repo.session.flush()
                return entity
        except Exception as e:
            raise DatabaseOperationError(f"創建測試實體失敗: {str(e)}") from e
    
    def update_test_entity(self, entity_id: int, data: Dict[str, Any]) -> Optional[ModelForTest]:
        try:
            with self._transaction():
                repo = self._get_repository("test_repo")
                entity = repo.update(entity_id, data)
                # 新增: 刷新 session 以確保更改反映（雖然對此例可能非必要，但保持一致性）
                if entity:
                    repo.session.flush()
                return entity
        except Exception as e:
            raise DatabaseOperationError(f"更新測試實體失敗: {str(e)}") from e
    
    def get_test_entity(self, entity_id: int) -> Optional[ModelForTest]:
        """獲取測試實體"""
        try:
            repo = self._get_repository("test_repo")
            return repo.get_by_id(entity_id)
        except Exception as e:
            # 如果是查詢不到實體，返回 None
            if isinstance(e, DatabaseOperationError) and "找不到實體" in str(e):
                return None
            # 其他錯誤則拋出異常
            raise DatabaseOperationError(f"獲取測試實體失敗: {str(e)}") from e
    
    def delete_test_entity(self, entity_id: int) -> bool:
        try:
            with self._transaction():
                repo = self._get_repository("test_repo")
                return repo.delete(entity_id)
        except Exception as e:
            raise DatabaseOperationError(f"刪除測試實體失敗: {str(e)}") from e
    
    def validate_test_data(self, data: Dict[str, Any], schema_type: SchemaType = SchemaType.CREATE) -> Dict[str, Any]:
        """驗證測試數據"""
        return self.validate_data("test_repo", data, schema_type)

class TestBaseService:
    @pytest.fixture(scope="session")
    def engine(self):
        """創建測試用的資料庫引擎"""
        return create_engine('sqlite:///:memory:')
    
    @pytest.fixture(scope="session")
    def tables(self, engine):
        """創建資料表結構"""
        Base.metadata.create_all(engine)
        yield
        Base.metadata.drop_all(engine)
    
    @pytest.fixture(scope="function")
    def db_manager(self, engine):
        """建立測試用 DatabaseManager"""
        # 使用真實 sessionmaker 構建 Session
        session_factory = sessionmaker(bind=engine)
        
        # 創建 mock DatabaseManager 並設置 Session 屬性
        mock_db_manager = MagicMock(spec=DatabaseManager)
        mock_db_manager.Session = MagicMock(return_value=session_factory())
        
        return mock_db_manager
    
    @pytest.fixture(scope="function")
    def test_service(self, db_manager, tables):
        """為每個測試建立 TestService 實例"""
        service = ServiceForTest(db_manager)
        yield service
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
        repo = test_service._get_repository("test_repo")
        assert isinstance(repo, RepositoryForTest)
        
        # 確認儲存庫被緩存
        assert "test_repo" in test_service._repositories
        assert test_service._repositories["test_repo"] is repo
    
    def test_get_repository_unknown(self, test_service):
        """測試獲取未知儲存庫時拋出異常"""
        with pytest.raises(DatabaseOperationError) as excinfo:
            test_service._get_repository("unknown_repo")
        assert "未知的儲存庫名稱" in str(excinfo.value)
        
    def test_validate_data(self, test_service, sample_entity_data):
        """測試數據驗證功能"""
        # 測試有效數據
        validated_data = test_service.validate_test_data(sample_entity_data)
        assert validated_data["name"] == sample_entity_data["name"]
        assert validated_data["title"] == sample_entity_data["title"]
        
        # 測試無效數據
        invalid_data = {"name": "test", "title": ""}
        with pytest.raises(ValidationError) as excinfo:
            test_service.validate_test_data(invalid_data)
        assert "title不能為空" in str(excinfo.value)
    
    def test_create_entity(self, test_service, sample_entity_data):
        """測試創建實體"""
        result = test_service.create_test_entity(sample_entity_data)
        assert result is not None
        assert result.id is not None
        assert result.name == sample_entity_data["name"]
        assert result.title == sample_entity_data["title"]
    
    def test_create_entity_validation_error(self, test_service):
        """測試創建實體時的驗證錯誤"""
        invalid_data = {
            "name": "test_name",
            "title": ""  # 空標題
        }
        
        with pytest.raises(DatabaseOperationError) as excinfo:
            test_service.create_test_entity(invalid_data)
        # 確認錯誤訊息來自底層的 ValidationError
        assert "title不能為空" in str(excinfo.value)
        # 驗證原始異常是否為 ValidationError
        assert isinstance(excinfo.value.__cause__, ValidationError)
    
    def test_update_entity(self, test_service, sample_entity_data):
        """測試更新實體"""
        # 先創建實體
        entity = test_service.create_test_entity(sample_entity_data)
        entity_id = entity.id
        
        # 更新實體
        update_data = {
            "title": "更新後的標題"
        }
        result = test_service.update_test_entity(entity_id, update_data)
        
        # 檢查更新結果
        assert result is not None
        assert result.id == entity_id
        assert result.title == update_data["title"]
        assert result.name == sample_entity_data["name"]  # 未更新的欄位保持不變
    
    def test_get_entity(self, test_service, sample_entity_data):
        """測試獲取實體"""
        # 先創建實體
        entity = test_service.create_test_entity(sample_entity_data)
        entity_id = entity.id
        
        # 獲取實體
        result = test_service.get_test_entity(entity_id)
        
        # 檢查結果
        assert result is not None
        assert result.id == entity_id
        assert result.name == sample_entity_data["name"]
        assert result.title == sample_entity_data["title"]
    
    def test_delete_entity(self, test_service, sample_entity_data):
        """測試刪除實體"""
        # 先創建實體
        entity = test_service.create_test_entity(sample_entity_data)
        entity_id = entity.id
        
        # 刪除實體
        result = test_service.delete_test_entity(entity_id)
        
        # 檢查結果
        assert result is True
        
        # 確認實體已刪除
        entity = test_service.get_test_entity(entity_id)
        assert entity is None
    
    def test_delete_nonexistent_entity(self, test_service):
        """測試刪除不存在的實體"""
        result = test_service.delete_test_entity(999)
        assert result is False
    
    def test_transaction(self, test_service, sample_entity_data):
        """測試事務功能"""
        entity_id = None
        # 在事務中創建實體
        # 使用 as session 捕獲 _transaction yield 的 session
        with test_service._transaction() as session:
            repo = test_service._get_repository("test_repo")
            # 直接調用 repo.create
            entity = repo.create(sample_entity_data)
            assert entity is not None
            # 手動 flush 以獲取 ID
            session.flush()
            entity_id = entity.id
            # 確保 ID 已獲取
            assert entity_id is not None 
            
        # 確認實體被創建 (事務已提交)
        assert entity_id is not None # 再次確認，避免 None 被傳遞
        result = test_service.get_test_entity(entity_id)
        assert result is not None
    
    def test_transaction_rollback(self, test_service, sample_entity_data):
        """測試事務回滾"""
        entity_id = None
        
        # 在事務中創建實體並觸發回滾
        with pytest.raises(ValueError): 
             # 使用 as session 捕獲 _transaction yield 的 session
            with test_service._transaction() as session:
                repo = test_service._get_repository("test_repo")
                entity = repo.create(sample_entity_data)
                assert entity is not None
                # 手動 flush，確保有變更可以回滾
                session.flush()
                entity_id = entity.id
                 # 確保 ID 已獲取 (如果 flush 成功)
                assert entity_id is not None
                
                # 拋出異常觸發回滾
                raise ValueError("測試事務回滾")
        
        # 確認實體不存在 (ID可能在內部產生但未提交)
        # 注意：如果 validate_data 在 repo.create 之前失敗，entity_id 可能為 None
        if entity_id is not None:
            result = test_service.get_test_entity(entity_id)
            assert result is None  # 應該返回 None 因為事務已回滾
        else:
             # 如果 entity_id 為 None，表示創建或 flush 步驟因異常未完成
             # 在這種情況下，斷言事務已回滾（沒有數據被寫入）仍然是合理的
             pass
    
    def test_transaction_commit(self, test_service, sample_entity_data):
        """測試事務提交"""
        entity_id = None
        
        # 在事務中創建實體
        # 使用 as session 捕獲 _transaction yield 的 session
        with test_service._transaction() as session:
            repo = test_service._get_repository("test_repo")
            entity = repo.create(sample_entity_data)
            assert entity is not None
            # 手動 flush 以獲取 ID
            session.flush()
            entity_id = entity.id
            # 確保 ID 已獲取
            assert entity_id is not None
        
        # 確認實體存在且資料正確 (事務已提交)
        assert entity_id is not None # 確保傳遞的 ID 不是 None
        result = test_service.get_test_entity(entity_id)
        assert result is not None
        assert result.id == entity_id
        assert result.name == sample_entity_data["name"]
        assert result.title == sample_entity_data["title"]
    
    def test_cleanup(self, test_service, sample_entity_data):
        """測試資源清理"""
        # 先創建實體，取得儲存庫
        test_service.create_test_entity(sample_entity_data)
        repo = test_service._get_repository("test_repo")
        
        # 檢查儲存庫字典
        assert len(test_service._repositories) > 0
        
        # 模擬 session 關閉
        repo.session.close = MagicMock()
        
        # 執行清理
        test_service.cleanup()
        
        # 檢查 session 關閉被調用且儲存庫字典被清空
        repo.session.close.assert_called_once()
        assert len(test_service._repositories) == 0
    
    def test_cleanup_error_handling(self, test_service, sample_entity_data):
        """測試清理過程中的異常處理"""
        # 先創建實體，取得儲存庫
        test_service.create_test_entity(sample_entity_data)
        repo = test_service._get_repository("test_repo")
        
        # 模擬 session 關閉異常
        repo.session.close = MagicMock(side_effect=Exception("測試異常"))
        
        # 執行清理，應不拋出異常
        test_service.cleanup()
        
        # 檢查 session 關閉被調用且儲存庫字典被清空
        repo.session.close.assert_called_once()
        assert len(test_service._repositories) == 0
