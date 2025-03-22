from typing import List, Optional, TypeVar, Generic, Type, Dict, Any, Union, Set
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .base_models import Base, ValidationError, NotFoundError
import logging
import re
# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

T = TypeVar('T', bound=Base)

class BaseRepository(Generic[T]):
    """
    基礎Repository類別，提供通用CRUD操作與資料驗證
    """
    def __init__(self, session: Session, model_class: Type[T]):
        self.session = session
        self.model_class = model_class
        
    # 資料驗證方法 - 入口點
    def validate_entity(self, entity: Union[T, Dict[str, Any]], is_update: bool = False, 
                        schema_class=None, skip_validators: Optional[Set[str]] = None) -> Any:
        """
        驗證實體資料，確保符合模型限制，並返回有效的實體對象
        
        Args:
            entity: 要驗證的實體或包含實體資料的字典
            is_update: 是否為更新操作
            schema_class: 可選的Pydantic schema類別用於額外的驗證
            skip_validators: 可選，要跳過的驗證步驟集合
        
        Returns:
            驗證後的實體對象
            
        Raises:
            ValidationError: 驗證失敗時拋出
            NotFoundError: 更新操作時找不到實體時拋出
        """
        skip_validators = skip_validators or set()
        
        if is_update:
            return self._validate_update(entity, schema_class, skip_validators)
        else:
            return self._validate_create(entity, schema_class, skip_validators)
    
    def _validate_create(self, entity: Any, schema_class=None, 
                         skip_validators: Optional[Set[str]] = None) -> Any:
        """驗證新增操作的資料並返回驗證後的實體"""
        errors = []
        entity_data = entity if isinstance(entity, dict) else None
        skip_validators = skip_validators or set()
        
        # 1. 使用Schema驗證
        if 'schema' not in skip_validators:
            self._validate_with_schema(entity, schema_class, errors)
        
        # 2. 轉換為模型實例
        if 'convert' not in skip_validators:
            entity = self._convert_to_model_instance(entity, is_update=False, errors=errors)
            if errors:
                self._raise_validation_errors(errors)
        
        # 3. 驗證必填欄位 (創建時所有必填欄位都必須有值)
        if 'required' not in skip_validators:
            self._validate_required_fields(entity, entity_data, is_update=False, errors=errors)
        
        # 4. 如果schema驗證已通過，且其包含全面的驗證，可以跳過其餘的約束檢查
        if schema_class and 'schema' not in skip_validators and 'skip_after_schema' in skip_validators:
            self._raise_validation_errors(errors)
            return entity
        
        # 5. 驗證欄位長度及其他約束
        if 'field_constraints' not in skip_validators:
            self._validate_field_constraints(entity, errors)
        
        # 6. 驗證模型約束
        if 'model_constraints' not in skip_validators:
            self._validate_model_constraints(entity, errors)
        
        # 7. 拋出錯誤 (如果有)
        self._raise_validation_errors(errors)
        
        return entity
    
    def _validate_update(self, entity: Any, schema_class=None, 
                         skip_validators: Optional[Set[str]] = None) -> Any:
        """驗證更新操作的資料並返回驗證後的實體"""
        errors = []
        entity_data = entity if isinstance(entity, dict) else None
        skip_validators = skip_validators or set()
        
        # 1. 使用Schema驗證
        if 'schema' not in skip_validators:
            self._validate_with_schema(entity, schema_class, errors)
        
        # 2. 轉換為模型實例並檢查不可修改欄位
        # 這個步驟不能跳過，因為需要檢查現有實體
        entity = self._convert_to_model_instance(entity, is_update=True, errors=errors)
        if errors:
            self._raise_validation_errors(errors)
        
        # 3. 驗證必填欄位 (更新時只驗證包含在更新資料中的欄位)
        if 'required' not in skip_validators:
            self._validate_required_fields(entity, entity_data, is_update=True, errors=errors)
        
        # 4. 如果schema驗證已通過，且其包含全面的驗證，可以跳過其餘的約束檢查
        if schema_class and 'schema' not in skip_validators and 'skip_after_schema' in skip_validators:
            self._raise_validation_errors(errors)
            return entity
        
        # 5. 驗證欄位長度及其他約束
        if 'field_constraints' not in skip_validators:
            self._validate_field_constraints(entity, errors)
        
        # 6. 驗證模型約束
        if 'model_constraints' not in skip_validators:
            self._validate_model_constraints(entity, errors)
        
        # 7. 拋出錯誤 (如果有)
        self._raise_validation_errors(errors)
        
        return entity
    
    def _validate_with_schema(self, entity, schema_class, errors):
        """使用Pydantic schema進行驗證"""
        if schema_class and isinstance(entity, dict):
            try:
                schema_class(**entity)
            except Exception as e:
                error_msg = f"Schema validation failed: {str(e)}"
                errors.append(error_msg)
    
    def _convert_to_model_instance(self, entity: Any, is_update: bool, errors: List[str]) -> Any:
        """將字典轉換為模型實例，並檢查不可修改欄位"""
        # 如果已經是模型實例，直接返回
        if not isinstance(entity, dict):
            return entity
        
        entity_id = entity.get('id')
        if is_update and entity_id:
            # 更新操作：載入現有實體
            existing = self.get_by_id(entity_id)
            if not existing:
                error_msg = f"{self.model_class.__name__} with id {entity_id} not found"
                logger.error(error_msg)
                raise NotFoundError(error_msg)
            
            # 先檢查不可修改欄位
            immutable_fields = self._get_immutable_fields(existing)
            for field in immutable_fields:
                if field in entity and getattr(existing, field) != entity[field]:
                    errors.append(f"Field '{field}' cannot be updated")
            
            # 創建臨時實體用於驗證
            temp_entity = self.model_class()
            for key, value in entity.items():
                if key not in immutable_fields or getattr(existing, key) == value:
                    try:
                        setattr(temp_entity, key, value)
                    except (TypeError, AttributeError) as e:
                        errors.append(f"Invalid field '{key}': {str(e)}")
            return temp_entity
        else:
            # 創建操作：直接使用字典創建實體
            try:
                return self.model_class(**entity)
            except (TypeError, AttributeError) as e:
                errors.append(f"Invalid field: {str(e)}")
                return None
    
    def _get_immutable_fields(self, entity):
        """獲取實體的不可修改欄位"""
        immutable_fields = {'id'}  # ID 始終不可修改
        
        # 基於模型類型的精確匹配
        class_name = entity.__class__.__name__
        if class_name == 'Article':
            immutable_fields.update(['link', 'created_at'])
        elif class_name == 'ArticleLinks':
            immutable_fields.update(['article_link', 'created_at'])
        elif class_name == 'CrawlerSettings':
            immutable_fields.update(['created_at'])
        else:
            # 對於未知模型，則嘗試分析 __setattr__ 方法
            if hasattr(entity.__class__, '__setattr__'):
                # 此處可以添加源碼分析的邏輯，但通常不需要
                pass
        
        return immutable_fields
    
    def _validate_required_fields(self, entity, entity_data, is_update, errors):
        """驗證必填欄位"""
        if entity is None:
            return
            
        for column in self.model_class.__table__.columns:
            if not column.nullable and not column.default and not column.server_default:
                # 更新操作時，只檢查要更新的欄位
                if is_update and entity_data and column.name not in entity_data:
                    continue
                
                value = getattr(entity, column.name, None)
                if value is None and column.name != 'id':
                    errors.append(f"Field '{column.name}' is required")
    
    def _validate_field_constraints(self, entity, errors):
        """驗證欄位長度及其他約束"""
        if entity is None:
            return
            
        from sqlalchemy.sql.sqltypes import String, Text, Unicode, UnicodeText
        
        for column in self.model_class.__table__.columns:
            value = getattr(entity, column.name, None)
            if value is not None:
                # 字段長度檢查
                if isinstance(column.type, (String, Text, Unicode, UnicodeText)) and hasattr(column.type, "length"):
                    if isinstance(value, str) and column.type.length and len(value) > column.type.length:
                        errors.append(f"Field '{column.name}' exceeds maximum length ({column.type.length})")
    
    def _validate_model_constraints(self, entity, errors):
        """驗證模型上的表級約束"""
        if entity is None or not hasattr(self.model_class, '__table_args__'):
            return
        
        from sqlalchemy import CheckConstraint
        
        for arg in self.model_class.__table_args__:
            if isinstance(arg, CheckConstraint) and hasattr(arg, 'name'):
                constraint_name = getattr(arg, 'name', '')
                
                # 處理長度約束
                if '_length' in constraint_name:
                    self._validate_length_constraint(entity, arg, constraint_name, errors)
                
                # 處理類型約束
                elif '_type' in constraint_name:
                    self._validate_type_constraint(entity, arg, constraint_name, errors)
    
    def _validate_length_constraint(self, entity, constraint, constraint_name, errors):
        """驗證長度約束"""
        # 解析欄位名稱
        field_name = self._extract_field_name_from_constraint(constraint_name, 'length')
        
        # 檢查欄位是否存在於實體中
        if hasattr(entity, field_name):
            field_value = getattr(entity, field_name)
            if field_value is not None and isinstance(field_value, str):
                # 從約束條件中提取長度限制
                constraint_text = str(constraint.sqltext)
                
                # 提取最小長度
                min_length = 1  # 預設最小長度
                min_length_match = re.search(r'length\([^)]+\)\s*>=\s*(\d+)', constraint_text)
                if min_length_match:
                    min_length = int(min_length_match.group(1))
                
                # 提取最大長度
                max_length = None
                max_length_match = re.search(r'length\([^)]+\)\s*<=\s*(\d+)', constraint_text)
                if max_length_match:
                    max_length = int(max_length_match.group(1))
                
                # 進行長度驗證
                if max_length and len(field_value) > max_length:
                    errors.append(f"Field '{field_name}' exceeds maximum length ({max_length})")
                if min_length and len(field_value) < min_length:
                    errors.append(f"Field '{field_name}' is too short (minimum length: {min_length})")
    
    def _validate_type_constraint(self, entity, constraint, constraint_name, errors):
        """驗證類型約束"""
        # 解析欄位名稱
        field_name = self._extract_field_name_from_constraint(constraint_name, 'type')
        
        # 檢查欄位是否存在於實體中
        if hasattr(entity, field_name):
            field_value = getattr(entity, field_name)
            if field_value is not None:
                # 檢查Boolean類型約束
                constraint_text = str(constraint.sqltext)
                if 'IN (0, 1)' in constraint_text and not isinstance(field_value, bool):
                    errors.append(f"Field '{field_name}' must be a boolean value")
    
    def _extract_field_name_from_constraint(self, constraint_name, suffix):
        """從約束名稱中提取欄位名稱"""
        parts = constraint_name.split('_')
        field_parts = []
        found_chk = False
        for part in parts:
            if part == 'chk':
                found_chk = True
                continue
            if part == suffix:
                break
            if found_chk:
                field_parts.append(part)
        
        return '_'.join(field_parts)
    
    def _raise_validation_errors(self, errors):
        """如有錯誤則拋出ValidationError"""
        if errors:
            error_msg = f"Repository.validate_entity: Validation failed: {', '.join(errors)}"
            logger.error(error_msg)
            raise ValidationError(error_msg)
    
    # CRUD 操作
    def create(self, entity_data: Dict[str, Any]) -> T:
        """創建實體"""
        # 資料驗證並獲取驗證後的實體
        validated_entity = self.validate_entity(entity_data)
        
        try:
            # 直接使用已驗證的實體資料
            entity = self.model_class(**entity_data)
            self.session.add(entity)
            self.session.flush()
            return entity
        except IntegrityError as e:
            self.session.rollback()
            error_msg = f"Repository.create: data unique error: {str(e)}"
            logger.error(error_msg)
            raise ValidationError(error_msg)
    
    def get_by_id(self, entity_id: Any) -> Optional[T]:
        """根據ID獲取實體"""
        return self.session.query(self.model_class).get(entity_id)
    
    def get_all(self) -> List[T]:
        """獲取所有實體"""
        return self.session.query(self.model_class).all()
    
    def update(self, entity_id: Any, entity_data: Dict[str, Any]) -> Optional[T]:
        """更新實體"""
        entity = self.get_by_id(entity_id)
        if not entity:
            return None
        
        # 確保ID不可修改
        entity_data['id'] = entity_id
        
        # 資料驗證 - 這裡會檢查不可修改欄位
        validated_entity = self.validate_entity(entity_data, is_update=True)
        
        try:
            # 更新實體 - 無需再檢查欄位是否可修改，因為驗證已確保所有欄位都可以安全設置
            # 驗證已檢查了不可修改的欄位，所以這裡可以放心設置所有欄位
            for key, value in entity_data.items():
                if key != 'id':  # ID仍然不更新，以防萬一
                    setattr(entity, key, value)
            
            self.session.flush()
            return entity
        except IntegrityError as e:
            self.session.rollback()
            error_msg = f"Repository.update: data unique error: {str(e)}"
            logger.error(error_msg)
            raise ValidationError(error_msg)
    
    def delete(self, entity_id: Any) -> bool:
        """刪除實體"""
        entity = self.get_by_id(entity_id)
        if not entity:
            return False
        
        try:
            self.session.delete(entity)
            self.session.flush()
            return True
        except IntegrityError as e:
            self.session.rollback()
            error_msg = f"Repository.delete: cannot delete {self.model_class.__name__}: {str(e)}"
            logger.error(error_msg)
            raise ValidationError(error_msg)