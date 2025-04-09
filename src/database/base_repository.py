from typing import List, Optional, TypeVar, Generic, Type, Dict, Any, Union, Callable
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from src.models.base_model import Base
from src.error.errors import ValidationError, InvalidOperationError, DatabaseOperationError, IntegrityValidationError
from sqlalchemy import desc, asc
import logging
from src.database.database_manager import check_session
from abc import ABC, abstractmethod
from enum import Enum, auto

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 將T綁定到Base，這樣可以訪問SQLAlchemy的屬性
T = TypeVar('T', bound=Base)

class SchemaType(Enum):
    CREATE = auto()
    UPDATE = auto()
    LIST = auto()
    DETAIL = auto()

class BaseRepository(Generic[T], ABC):
    """
    基礎Repository類別，提供通用CRUD操作
    """
    def __init__(self, session: Session, model_class: Type[T]):
        self.session = session
        self.model_class = model_class
    
    @check_session
    def execute_query(self, query_func: Callable, exception_class=DatabaseOperationError, err_msg=None, preserve_exceptions=None):
        """執行查詢的通用包裝器
        
        Args:
            query_func: 要執行的查詢函式
            exception_class: 發生異常時要拋出的異常類型
            err_msg: 自定義錯誤訊息
            preserve_exceptions: 需要保留原始異常的異常類型列表
        """
        preserve_exceptions = preserve_exceptions or [IntegrityError]
        try:
            return query_func()
        except Exception as e:
            error_msg = f"{err_msg if err_msg else '資料庫操作錯誤'}: {e}"
            logger.error(error_msg)
            
            # 如果是需要保留的異常類型，直接重新拋出
            if any(isinstance(e, exc) for exc in preserve_exceptions):
                raise
            
            raise exception_class(error_msg) from e
        
    def _handle_integrity_error(self, e: IntegrityError, context: str) -> None:
        """處理完整性錯誤並記錄日誌
        
        Args:
            e: 完整性錯誤異常
            context: 錯誤發生的上下文描述
        """
        error_msg = None
        error_type = None
        
        if "UNIQUE constraint" in str(e):
            error_type = "唯一性約束錯誤"
            error_msg = f"{context}: 資料重複"
        elif "NOT NULL constraint" in str(e):
            error_type = "非空約束錯誤"
            error_msg = f"{context}: 必填欄位不可為空"
        elif "FOREIGN KEY constraint" in str(e):
            error_type = "外鍵約束錯誤"
            error_msg = f"{context}: 關聯資料不存在或無法刪除"
        else:
            error_type = "其他完整性錯誤"
            error_msg = f"{context}: {str(e)}"
        
        # 記錄詳細的錯誤日誌
        logger.error(
            f"完整性錯誤 - 類型: {error_type}, "
            f"上下文: {context}, "
            f"詳細訊息: {str(e)}, "
            f"模型: {self.model_class.__name__}"
        )
        
        # 拋出異常
        raise IntegrityValidationError(error_msg)
    
    @abstractmethod
    def get_schema_class(self, schema_type: SchemaType = SchemaType.CREATE) -> Type[BaseModel]:
        """子類必須實現此方法提供用於驗證的schema類"""
        raise NotImplementedError("子類必須實現此方法提供用於驗證的schema類")
        
    def _create_internal(self, entity_data: Dict[str, Any], schema_class: Type[BaseModel]) -> Optional[T]:
        """內部方法：創建實體（需要提供schema）"""
        try:
            # 使用 Pydantic schema 進行驗證
            validated_data = self.validate_entity_data(entity_data)
            entity = self.model_class(**validated_data)
            
            self.execute_query(
                lambda: self.session.add(entity),
                err_msg="添加資料庫物件到session時發生錯誤"
            )
            self.execute_query(
                lambda: self.session.flush(),
                err_msg="刷新session時發生錯誤"
            )
            return entity
        except IntegrityError as e:
            self.execute_query(
                lambda: self.session.rollback(),
                err_msg="回滾session時發生錯誤",
                preserve_exceptions=[]
            )
            self._handle_integrity_error(e, f"創建{self.model_class.__name__}時")
        except ValidationError as e:
            self.execute_query(
                lambda: self.session.rollback(),
                err_msg="驗證錯誤時回滾session時發生錯誤"
            )
            logger.error(f"Repository.create: 驗證錯誤: {str(e)}")
            raise
        except Exception as e:
            self.execute_query(
                lambda: self.session.rollback(),
                err_msg="未預期錯誤時回滾session時發生錯誤"
            )
            error_msg = f"Repository.create: 未預期錯誤: {str(e)}"
            logger.error(error_msg)
            raise DatabaseOperationError(error_msg) from e
    
    @abstractmethod
    def create(self, entity_data: Dict[str, Any]) -> Optional[T]:
        """創建實體（強制子類實現）必須提供schema及調用_create_internal
        
        Args:
            entity_data: 實體數據
            
        Returns:
            創建的實體或 None
        """
        raise NotImplementedError("子類必須實現此方法提供用於驗證的schema類")
    
    def validate_entity_data(self, entity_data: Dict[str, Any], existing_entity: Optional[T] = None) -> Dict[str, Any]:
        """驗證實體數據"""
        if existing_entity:
            schema_class = self.get_schema_class(SchemaType.UPDATE)
            validated_data = schema_class(**entity_data).model_dump(exclude_unset=True)
        else:
            schema_class = self.get_schema_class(SchemaType.CREATE)
            validated_data = schema_class(**entity_data).model_dump()

        return validated_data
    
    def _update_internal(self, entity_id: Any, entity_data: Dict[str, Any], schema_class: Type[BaseModel]) -> Optional[T]:
        """內部方法：更新實體（需要提供schema）"""
        entity = self.get_by_id(entity_id)
        if not entity:
            return None
        
        try:
            # 使用 Pydantic schema 進行驗證
            validated_data = self.validate_entity_data(entity_data, entity)
            
            # 更新實體
            for key, value in validated_data.items():
                if key != 'id':  # ID不更新
                    setattr(entity, key, value)
            
            self.execute_query(
                lambda: self.session.flush(),
                err_msg=f"更新ID為{entity_id}的資料庫物件時刷新session時發生錯誤"
            )
            return entity
        except IntegrityError as e:
            self.execute_query(
                lambda: self.session.rollback(),
                err_msg=f"更新ID為{entity_id}的資料庫物件時回滾session時發生錯誤",
                preserve_exceptions=[]
            )
            self._handle_integrity_error(e, f"更新{self.model_class.__name__}時")
        except ValidationError as e:
            self.execute_query(
                lambda: self.session.rollback(),
                err_msg="當更新ID為{entity_id}的資料庫物件時驗證錯誤時回滾session時發生錯誤"
            )
            logger.error(f"Repository.update: 驗證錯誤: {str(e)}")
            raise
        except Exception as e:
            self.execute_query(
                lambda: self.session.rollback(),
                err_msg="當更新ID為{entity_id}的資料庫物件時未預期錯誤時回滾session時發生錯誤"
            )
            error_msg = f"Repository.update: 未預期錯誤: {str(e)}"
            logger.error(error_msg)
            raise DatabaseOperationError(error_msg) from e
    
    @abstractmethod
    def update(self, entity_id: Any, entity_data: Dict[str, Any]) -> Optional[T]:
        """更新實體（強制子類實現）必須提供schema及調用_update_internal
        
        Args:
            entity_id: 實體ID
            entity_data: 實體數據
            
        Returns:
            更新的實體或 None
        """
        raise NotImplementedError("子類必須實現此方法提供用於驗證的schema類")
    
    def get_by_id(self, entity_id: Any) -> Optional[T]:
        """根據ID獲取實體"""
        return self.execute_query(
            lambda: self.session.get(self.model_class, entity_id),
            err_msg=f"獲取ID為{entity_id}的資料庫物件時發生錯誤"
        )
    
    def delete(self, entity_id: Any) -> bool:
        """刪除實體"""
        entity = self.get_by_id(entity_id)
        if not entity:
            return False
        
        try:
            self.execute_query(
                lambda: self.session.delete(entity),
                err_msg=f"刪除ID為{entity_id}的資料庫物件時發生錯誤"
            )
            self.execute_query(
                lambda: self.session.flush(),
                err_msg=f"刪除ID為{entity_id}的資料庫物件時刷新session時發生錯誤"
            )
            return True
        except IntegrityError as e:
            self.execute_query(
                lambda: self.session.rollback(),
                err_msg=f"刪除ID為{entity_id}的資料庫物件時回滾session時發生錯誤",
                preserve_exceptions=[]
            )
            # 使用新的處理方法
            self._handle_integrity_error(e, f"刪除{self.model_class.__name__}時")
        except Exception as e:
            self.execute_query(
                lambda: self.session.rollback(),
                err_msg="刪除ID為{entity_id}的資料庫物件時未預期錯誤時回滾session時發生錯誤"
            )
            error_msg = f"Repository.delete: 未預期錯誤: {str(e)}"
            logger.error(error_msg)
            raise DatabaseOperationError(error_msg) from e
        
        return False
        
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
        def query_builder():
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
            
        return self.execute_query(
            query_builder,
            err_msg="獲取所有資料庫物件時發生錯誤",
            exception_class=DatabaseOperationError
        )
    
    def get_paginated(self, page: int = 1, per_page: int = 10, sort_by: Optional[str] = None, sort_desc: bool = False) -> Dict[str, Any]:
        """獲取分頁數據"""
        # 驗證分頁參數
        if per_page <= 0:
            raise ValueError("每頁記錄數必須大於0")
        if page <= 0:
            page = 1
        
        # 計算偏移量
        offset = (page - 1) * per_page
        
        # 構建查詢
        query = self.session.query(self.model_class)
        
        # 添加排序
        if sort_by:
            if not hasattr(self.model_class, sort_by):
                raise DatabaseOperationError(f"無效的排序欄位: {sort_by}")
            order_by = desc(getattr(self.model_class, sort_by)) if sort_desc else asc(getattr(self.model_class, sort_by))
            query = query.order_by(order_by)
        
        # 獲取總記錄數
        total = query.count()
        
        # 計算總頁數
        total_pages = (total + per_page - 1) // per_page
        
        # 調整頁碼
        if page > total_pages and total > 0:
            page = total_pages
            offset = (page - 1) * per_page
        
        # 獲取當前頁的記錄
        items = query.offset(offset).limit(per_page).all()
        
        return {
            "items": items,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }

    def find_all(self, *args, **kwargs):
        """找出所有實體的別名方法"""
        # 避免嵌套使用 execute_query
        return self.get_all(*args, **kwargs)

