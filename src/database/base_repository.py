from typing import List, Optional, TypeVar, Generic, Type, Dict, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from src.models.base_model import Base
from src.error.errors import ValidationError, InvalidOperationError, DatabaseOperationError
from sqlalchemy import desc, asc
import logging
from sqlalchemy.exc import SQLAlchemyError
from src.database.database_manager import check_session

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 將T綁定到Base，這樣可以訪問SQLAlchemy的屬性
T = TypeVar('T', bound=Base)

class BaseRepository(Generic[T]):
    """
    基礎Repository類別，提供通用CRUD操作
    """
    def __init__(self, session: Session, model_class: Type[T]):
        self.session = session
        self.model_class = model_class
    
    # CRUD 操作
    def create(self, entity_data: Dict[str, Any], schema_class=None) -> T:
        """創建實體"""
        try:
            # 使用 Pydantic schema 進行驗證
            if schema_class:
                validated_data = schema_class(**entity_data).model_dump()
                entity = self.model_class(**validated_data)
            else:
                entity = self.model_class(**entity_data)
                
            self.session.add(entity)
            self.session.flush()
            return entity
        except IntegrityError as e:
            self.session.rollback()
            # 提取更具體的錯誤訊息
            error_msg = self._extract_integrity_error_message(e, entity_data)
            logger.error(f"Repository.create: {error_msg}")
            raise ValidationError(error_msg)
        except Exception as e:
            self.session.rollback()
            error_msg = f"Repository.create: unexpected error: {str(e)}"
            logger.error(error_msg)
            raise e

    def _extract_integrity_error_message(self, error: IntegrityError, data: Dict[str, Any]) -> str:
        """從完整性錯誤中提取更具體的錯誤訊息"""
        error_str = str(error).lower()
        
        # 處理唯一性約束錯誤
        if 'unique' in error_str or 'duplicate' in error_str:
            # 嘗試識別涉及哪個欄位
            if hasattr(self.model_class, '__table_args__'):
                for arg in self.model_class.__table_args__:
                    if hasattr(arg, 'name') and 'uq_' in getattr(arg, 'name', '').lower():
                        # 從約束名稱中提取欄位名稱
                        constraint_name = getattr(arg, 'name')
                        field_name = constraint_name.replace('uq_', '').replace(self.model_class.__tablename__, '').strip('_')
                        
                        if field_name in data:
                            return f"已存在具有相同{field_name}的記錄: {data.get(field_name)}"
            
            # 從錯誤訊息中試著提取欄位名
            for key in data.keys():
                if key.lower() in error_str:
                    return f"已存在具有相同{key}的記錄: {data.get(key)}"
            
            return f"資料唯一性錯誤，可能已存在相同記錄"
        
        # NOT NULL constraint 錯誤
        if 'not null constraint' in error_str:
            for key in self.model_class.__table__.columns.keys():
                if key.lower() in error_str:
                    return f"欄位'{key}'不能為空"
            return f"必填欄位不可為空: {str(error)}"
        
        # 其他完整性錯誤
        return f"資料完整性錯誤: {str(error)}"
    
    def get_by_id(self, entity_id: Any) -> Optional[T]:
        """根據ID獲取實體"""
        return self.session.get(self.model_class, entity_id)
    
    def update(self, entity_id: Any, entity_data: Dict[str, Any], schema_class=None) -> Optional[T]:
        """更新實體"""
        entity = self.get_by_id(entity_id)
        if not entity:
            return None
        
        try:
            # 使用 Pydantic schema 進行驗證
            if schema_class:
                # 對於更新操作，通常會有專用的 UpdateSchema
                validated_data = schema_class(**entity_data).model_dump(exclude_unset=True)
                
                # 更新實體
                for key, value in validated_data.items():
                    if key != 'id':  # ID不更新
                        setattr(entity, key, value)
            else:
                # 無 schema 的情況下直接更新
                for key, value in entity_data.items():
                    if key != 'id':  # ID不更新
                        setattr(entity, key, value)
            
            self.session.flush()
            return entity
        except IntegrityError as e:
            self.session.rollback()
            # 提取更具體的錯誤訊息
            error_msg = self._extract_integrity_error_message(e, entity_data)
            logger.error(f"Repository.update: {error_msg}")
            raise ValidationError(error_msg)
        except Exception as e:
            self.session.rollback()
            error_msg = f"Repository.update: unknown error: {str(e)}"
            logger.error(error_msg)
            raise e
    
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
        
    def get_all(self, limit: Optional[int] = None, offset: Optional[int] = None, sort_by: Optional[str] = None, sort_desc: bool = False) -> List[T]:
        """獲取所有實體，支援分頁和排序

        Args:
            limit: 限制返回結果數量
            offset: 跳過結果數量
            sort_by: 排序欄位名稱
            sort_desc: 是否降序排列

        Returns:
            實體列表
        """
        try:
            query = self.session.query(self.model_class)
            
            # 處理排序
            if sort_by:
                if not hasattr(self.model_class, sort_by):
                    raise InvalidOperationError(f"無效的排序欄位: {sort_by}")
                order_column = getattr(self.model_class, sort_by)
                if sort_desc:
                    query = query.order_by(desc(order_column))
                else:
                    query = query.order_by(asc(order_column))
            else:
                # 預設按創建時間或ID降序排列
                try:
                    # 嘗試使用 created_at
                    created_at_attr = getattr(self.model_class, 'created_at', None)
                    if created_at_attr is not None:
                        query = query.order_by(desc(created_at_attr))
                    else:
                        # 否則使用 id
                        id_attr = getattr(self.model_class, 'id', None)
                        if id_attr is not None:
                            query = query.order_by(desc(id_attr))
                except (AttributeError, TypeError):
                    # 如果無法訪問這些屬性，則不排序
                    pass
            
            # 處理分頁
            if offset is not None:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)
            
            return query.all()
        except SQLAlchemyError as e:
            error_msg = f"查詢資料時發生錯誤: {e}"
            logger.error(error_msg)
            raise DatabaseOperationError(error_msg) from e
    
    def get_paginated(self, page: int, per_page: int, sort_by: Optional[str] = None, sort_desc: bool = False) -> Dict[str, Any]:
        """獲取分頁資料

        Args:
            page: 當前頁碼，從1開始
            per_page: 每頁數量
            sort_by: 排序欄位
            sort_desc: 是否降序排列

        Returns:
            包含分頁資訊和結果的字典
        """
        # 計算總記錄數
        total = self.session.query(self.model_class).count()
        
        # 計算總頁數
        total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0
        
        # 確保頁碼有效
        current_page = max(1, min(page, total_pages)) if total_pages > 0 else 1
        
        # 計算偏移量
        offset = (current_page - 1) * per_page
        
        # 獲取當前頁數據
        items = self.get_all(
            limit=per_page, 
            offset=offset,
            sort_by=sort_by,
            sort_desc=sort_desc
        )
        
        # 構建分頁結果
        return {
            "items": items,
            "page": current_page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": current_page < total_pages,
            "has_prev": current_page > 1
        }

    @check_session
    def execute_query(self, query_func):
        """執行查詢的通用包裝器"""
        try:
            return query_func()
        except SQLAlchemyError as e:
            error_msg = f"資料庫操作錯誤: {e}"
            logger.error(error_msg)
            raise DatabaseOperationError(error_msg) from e

    @check_session
    def find_all(self, *args, **kwargs):
        return self.execute_query(lambda: self.get_all(*args, **kwargs))
