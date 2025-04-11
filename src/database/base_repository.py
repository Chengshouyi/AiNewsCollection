from typing import List, Optional, TypeVar, Generic, Type, Dict, Any, Union, Callable, cast
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
from src.models.base_schema import BaseCreateSchema, BaseUpdateSchema
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
        preserve_exceptions = preserve_exceptions or [IntegrityError, ValidationError]
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
    
    
    # --- 抽象方法 (子類必須實現) ---
    @abstractmethod
    def get_schema_class(self, schema_type: SchemaType = SchemaType.CREATE) -> Type[Union[BaseCreateSchema, BaseUpdateSchema]]:
        """子類必須實現此方法提供用於驗證的 Pydantic schema 類"""
        raise NotImplementedError("子類必須實現此方法提供用於驗證的schema類")
    
        # --- 公開驗證方法 (供 API 層和內部使用) ---
    def validate_data(self, entity_data: Dict[str, Any], schema_type: SchemaType) -> Dict[str, Any]:
        """
        公開方法：使用 Pydantic Schema 驗證資料。
        根據 schema_type 返回包含預設值 (CREATE) 或僅包含傳入欄位 (UPDATE) 的字典。

        Args:
            entity_data: 待驗證的原始字典資料。
            schema_type: 決定使用 CreateSchema 還是 UpdateSchema。

        Returns:
            驗證並處理過的字典資料。

        Raises:
            ValidationError: 如果 Pydantic 驗證失敗。
        """
        schema_class_untyped = self.get_schema_class(schema_type)
        # 使用 cast 解決型別檢查問題
        schema_class = cast(Type[BaseModel], schema_class_untyped)
        logger.debug(f"使用 Schema '{schema_class.__name__}' 驗證資料 ({schema_type.name})")
        try:
            # 執行核心 Pydantic 驗證
            instance = schema_class.model_validate(entity_data)

            # 根據類型返回不同的字典表示
            if schema_type == SchemaType.UPDATE:
                # 更新時，只包含明確傳入且非 None 的欄位
                validated_dict = instance.model_dump(exclude_unset=True)
                logger.debug(f"更新資料驗證成功 (Payload): {validated_dict}")
            else: # CREATE 或其他
                # 創建時，包含 Schema 定義的預設值
                validated_dict = instance.model_dump()
                logger.debug(f"創建資料驗證成功 (含預設值): {validated_dict}")

            return validated_dict
        except ValidationError as e:
            # 包裝 Pydantic 錯誤
            error_msg = f"{schema_type.name} 資料驗證失敗: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e
        except Exception as e:
             error_msg = f"執行 validate_data 時發生非預期錯誤: {str(e)}"
             logger.error(error_msg, exc_info=True)
             raise DatabaseOperationError(error_msg) from e
        
    
    # --- 受保護的輔助和內部方法 ---
    def _validate_and_supplement_required_fields(
        self,
        pydantic_validated_data: Dict[str, Any], # 接收已通過 Pydantic 的資料
        existing_entity: Optional[T] = None
    ) -> Dict[str, Any]:
        """
        輔助方法：在 Pydantic 驗證後，檢查必填欄位的值是否有效 (非 None 或空字串)，
        並在更新時從現有實體補充。

        Args:
            pydantic_validated_data: 已通過 Pydantic 驗證的資料字典。
            existing_entity: 現有實體 (用於更新時)。

        Returns:
            處理後的資料字典。

        Raises:
            ValidationError: 如果必填欄位值無效 (None 或空字串)。
        """
        copied_data = pydantic_validated_data.copy()

        # 獲取創建 Schema 以確定哪些是 '真正' 的必填欄位
        create_schema_class = cast(Type[BaseCreateSchema], self.get_schema_class(SchemaType.CREATE))
        required_fields = create_schema_class.get_required_fields()

        fields_to_check = required_fields.copy()

        # 如果是更新操作，從現有實體補充數據 (主要針對非 Schema 管理的欄位，或允許更新時為 None 的情況)
        if existing_entity:
            update_schema_class = cast(Type[BaseUpdateSchema], self.get_schema_class(SchemaType.UPDATE))
            immutable_fields = update_schema_class.get_immutable_fields()
            fields_to_check_for_update = [f for f in required_fields if f not in immutable_fields]

            for field in fields_to_check_for_update:
                # 如果 Pydantic 驗證後的資料中沒有此欄位 (可能因為 exclude_unset=True)，
                # 或者值為 None，則嘗試從現有實體補充
                if field not in copied_data or copied_data.get(field) is None:
                     if hasattr(existing_entity, field):
                          current_value = getattr(existing_entity, field)
                          if current_value is not None: # 只有在現有值非 None 時才補充
                              copied_data[field] = current_value
                              logger.debug(f"更新時從現有實體補充欄位 '{field}'")

            fields_to_check = fields_to_check_for_update # 更新時只檢查這些欄位的值

        # 最終檢查所有 '需要檢查' 的欄位，確保它們的值不是 None 或空字串
        missing_or_empty_fields = []
        for field in fields_to_check:
            field_value = copied_data.get(field)
            if field_value is None or (isinstance(field_value, str) and not field_value.strip()):
                missing_or_empty_fields.append(field)

        if missing_or_empty_fields:
            raise ValidationError(f"以下必填欄位值無效 (None 或空字串): {', '.join(missing_or_empty_fields)}")

        logger.debug(f"必填欄位值驗證通過: {self.model_class.__name__}")
        return copied_data
        
    def _create_internal(self, validated_data: Dict[str, Any]) -> Optional[T]:
        """內部創建，假設 validated_data 已通過 Pydantic Schema 驗證"""
        try:
            # 1. 執行必填欄位值檢查和補充
            final_data = self._validate_and_supplement_required_fields(validated_data)

            # 2. 直接創建模型實例
            entity = self.model_class(**final_data)

            # 3. Session 操作 (add, flush)
            self.execute_query(
                lambda: self.session.add(entity),
                err_msg="添加資料庫物件到session時發生錯誤"
            )
            self.execute_query(
                lambda: self.session.flush(),
                err_msg="刷新session以創建實體時發生錯誤"
            )
            logger.debug(f"實體準備創建 (待提交): {entity}")
            return entity
        except IntegrityError as e:
            self._handle_integrity_error(e, f"創建{self.model_class.__name__}時")
            # 注意：Rollback 應該由 Service 層的 _transaction 處理
            return None
        except ValidationError as e: # 捕捉 _validate_and_supplement 的錯誤
            logger.error(f"Repository._create_internal: 必填欄位值驗證失敗: {str(e)}")
            raise # 重新拋出
        except Exception as e:
            error_msg = f"Repository._create_internal: 未預期錯誤: {str(e)}"
            logger.error(error_msg, exc_info=True)
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
    
    
    def _update_internal(self, entity_id: Any, update_payload: Dict[str, Any]) -> Optional[T]:
        """內部更新，假設 update_payload 已通過 Pydantic Update Schema 驗證"""
        entity = self.get_by_id(entity_id)
        if not entity:
            logger.warning(f"找不到 ID={entity_id} 的實體，無法更新。")
            return None
        try:
            # 1. 獲取不可變欄位
            update_schema_class = cast(Type[BaseUpdateSchema], self.get_schema_class(SchemaType.UPDATE))
            immutable_fields = update_schema_class.get_immutable_fields()

            # 2. (可選，如果需要) 執行必填欄位值檢查 (通常更新時不需要，除非有特殊規則)
            # final_payload = self._validate_and_supplement_required_fields(update_payload, existing_entity=entity)
            # 這裡使用原始 payload，因為 Pydantic 已確保類型正確
            final_payload = update_payload

            # 3. 更新屬性
            has_changes = False
            for key, value in final_payload.items():
                if key in immutable_fields:
                    # 雖然 validate_data 時可能已排除，這裡再檢查一次以防萬一
                    logger.warning(f"內部更新: 嘗試更新不可變欄位 '{key}'，將被忽略。")
                    continue
                if hasattr(entity, key):
                    current_value = getattr(entity, key)
                    if current_value != value:
                        setattr(entity, key, value)
                        has_changes = True
                        logger.debug(f"更新實體 ID={entity_id} 欄位 '{key}' 從 '{current_value}' 到 '{value}'")

            if not has_changes:
                logger.debug(f"實體 ID={entity_id} 沒有變更，跳過資料庫操作。")
                return entity # 返回未修改的實體

            # 4. Session 操作 (flush)
            self.execute_query(
                lambda: self.session.flush(),
                err_msg=f"更新ID為{entity_id}的資料庫物件時刷新session時發生錯誤"
            )
            logger.debug(f"實體準備更新 (待提交): {entity}")
            return entity
        except IntegrityError as e:
            self._handle_integrity_error(e, f"更新{self.model_class.__name__} (ID={entity_id}) 時")
            # 注意：Rollback 應該由 Service 層的 _transaction 處理
            return None
        except ValidationError as e: # 捕捉 _validate_and_supplement 的錯誤 (如果使用)
            logger.error(f"Repository._update_internal: 必填欄位值驗證失敗 (ID={entity_id}): {str(e)}")
            raise # 重新拋出
        except Exception as e:
            error_msg = f"Repository._update_internal: 未預期錯誤 (ID={entity_id}): {str(e)}"
            logger.error(error_msg, exc_info=True)
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

