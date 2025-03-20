from typing import List, Optional, TypeVar, Generic, Type, Dict, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .base_models import Base, ValidationError, NotFoundError
import logging
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
        
    # 資料驗證方法
    def validate_entity(self, entity: Union[T, Dict[str, Any]], is_update: bool = False) -> None:
        """
        驗證實體資料，確保符合模型限制
        
        Args:
            entity: 要驗證的實體或包含實體資料的字典
            is_update: 是否為更新操作
        
        Raises:
            ValidationError: 驗證失敗時拋出
        """
        errors = []
        
        # 將字典轉換為模型物件（若為更新操作則載入現有物件）
        if isinstance(entity, dict):
            entity_id = entity.get('id')
            if is_update and entity_id:
                # 更新操作：載入現有實體
                existing = self.get_by_id(entity_id)
                if not existing:
                    error_msg = f"Repository.validate_entity: {self.model_class.__name__} with id {entity_id} not found"
                    logger.error(error_msg)
                    raise NotFoundError(error_msg)
                
                # 創建臨時實體用於驗證
                temp_entity = self.model_class()
                for key, value in entity.items():
                    try:
                        setattr(temp_entity, key, value)
                    except AttributeError as e:
                        errors.append(str(e))
                entity = temp_entity
            else:
                # 創建操作：直接使用字典創建實體
                try:
                    entity = self.model_class(**entity)
                except (TypeError, AttributeError) as e:
                    error_msg = f"Repository.validate_entity: Invalid field: {str(e)}"
                    logger.error(error_msg)
                    raise ValidationError(error_msg)
        
        # 檢查必填欄位
        for column in self.model_class.__table__.columns:
            if not column.nullable and not column.default and not column.server_default:
                value = getattr(entity, column.name, None)
                if value is None:
                    error_msg = f"Repository.validate_entity: Field '{column.name}' is required"
                    logger.error(error_msg)
                    raise ValidationError(error_msg)
        
        # 如果有檢測到錯誤，拋出ValidationError
        if errors:
            error_msg = f"Repository.validate_entity: Validation failed: {', '.join(errors)}"
            logger.error(error_msg)
            raise ValidationError(error_msg)
    
    # CRUD 操作
    def create(self, entity_data: Dict[str, Any]) -> T:
        """創建實體"""
        # 資料驗證
        self.validate_entity(entity_data)
        
        try:
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
        
        # 資料驗證
        self.validate_entity(entity_data, is_update=True)
        
        try:
            for key, value in entity_data.items():
                if key != 'id':  # 不更新ID
                    try:
                        setattr(entity, key, value)
                    except AttributeError:
                        # 針對不可修改的欄位，若值相同則忽略錯誤，否則重新拋出
                        if getattr(entity, key) != value:
                            error_msg = f"Repository.update: cannot update {self.model_class.__name__}: {str(e)}"
                            logger.error(error_msg)
                            raise ValidationError(error_msg)
            
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