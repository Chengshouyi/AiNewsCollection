from os import error
from typing import List, Optional, TypeVar, Generic, Type, Dict, Any, Union, Callable, cast
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from src.models.base_model import Base
from src.error.errors import ValidationError, InvalidOperationError, DatabaseOperationError, IntegrityValidationError
from sqlalchemy import desc, asc, and_, or_, not_
import logging
from src.database.database_manager import check_session
from abc import ABC, abstractmethod
from enum import Enum, auto
from src.models.base_schema import BaseCreateSchema, BaseUpdateSchema
from sqlalchemy.orm.attributes import flag_modified
from src.utils.repository_utils import deep_update_dict_field
import copy
# 導入 Pydantic 的 ValidationError
from pydantic_core import ValidationError as PydanticValidationError
from datetime import datetime, timezone # 確保導入 datetime 和 timezone

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
        default_preserve = [IntegrityError, ValidationError, InvalidOperationError]
        # 明確檢查 preserve_exceptions 是否為 None
        if preserve_exceptions is None:
            preserve_exceptions = default_preserve
        # 現在，如果調用者傳入 []，preserve_exceptions 就會是 []

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
    @classmethod
    @abstractmethod
    def get_schema_class(cls, schema_type: SchemaType = SchemaType.CREATE) -> Type[Union[BaseCreateSchema, BaseUpdateSchema]]:
        """子類必須實現此方法提供用於驗證的 Pydantic schema 類"""
        raise NotImplementedError("子類必須實現此方法提供用於驗證的schema類")
    
        # --- 公開驗證方法 (供 API 層和內部使用) ---
    @classmethod
    def validate_data(cls, entity_data: Dict[str, Any], schema_type: SchemaType) -> Dict[str, Any]:
        """
        公開的類別方法：使用 Pydantic Schema 驗證資料。
        根據 schema_type 返回包含預設值 (CREATE) 或僅包含傳入欄位 (UPDATE) 的字典。

        Args:
            entity_data: 待驗證的原始字典資料。
            schema_type: 決定使用 CreateSchema 還是 UpdateSchema。

        Returns:
            Dict[str, Any]: 驗證並處理過的字典資料。
        Raises:
            ValidationError: 如果資料驗證失敗
            Exception: 其他非預期錯誤
        """
        schema_class_untyped = cls.get_schema_class(schema_type)
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
        except PydanticValidationError as e: # 明確捕獲 Pydantic 的 ValidationError
            # 包裝 Pydantic 錯誤為自定義的 ValidationError
            error_msg = f"{schema_type.name} 資料驗證失敗: {str(e)}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e # 拋出自定義 ValidationError
        except ValidationError as e:
            error_msg = f"{schema_type.name} 資料驗證失敗: {str(e)}"
            logger.error(error_msg)
            raise e
        except Exception as e:
            # 將其他未預期錯誤也包裝為自定義 ValidationError
            error_msg = f"執行 validate_data 時發生非預期錯誤: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ValidationError(error_msg) from e # 拋出自定義 ValidationError
        
    
    # --- 受保護的輔助和內部方法 ---
    def _apply_filters(self, query, filter_criteria: Dict[str, Any]):
        """將過濾條件應用到 SQLAlchemy 查詢對象"""
        if not filter_criteria:
            return query

        conditions = []
        for field, value in filter_criteria.items():
            if not hasattr(self.model_class, field):
                logger.warning(f"過濾條件中的欄位 '{field}' 在模型 {self.model_class.__name__} 中不存在，將忽略此條件。")
                continue

            column = getattr(self.model_class, field)

            if isinstance(value, dict):
                # 處理 MongoDB 風格的操作符
                for operator, operand in value.items():
                    if operator == "$in":
                        if isinstance(operand, list):
                            conditions.append(column.in_(operand))
                        else:
                            logger.warning(f"欄位 '{field}' 的 $in 操作符需要一個列表作為操作數，收到 {type(operand)}，忽略。")
                    elif operator == "$nin":
                        if isinstance(operand, list):
                            conditions.append(not_(column.in_(operand)))
                        else:
                            logger.warning(f"欄位 '{field}' 的 $nin 操作符需要一個列表作為操作數，收到 {type(operand)}，忽略。")
                    elif operator == "$ne":
                        conditions.append(column != operand)
                    elif operator == "$gt":
                        conditions.append(column > operand)
                    elif operator == "$gte":
                        conditions.append(column >= operand)
                    elif operator == "$lt":
                        conditions.append(column < operand)
                    elif operator == "$lte":
                        conditions.append(column <= operand)
                    else:
                        logger.warning(f"欄位 '{field}' 的操作符 '{operator}' 不支援，忽略。")
            else:
                # 默認相等比較
                conditions.append(column == value)

        if conditions:
            return query.filter(and_(*conditions))
        else:
            return query

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
        """內部創建，假設 validated_data 已通過 Pydantic Schema 驗證
        Args:
            validated_data: 已通過 Pydantic Schema 驗證的資料字典。

        Returns:
            創建的實體或 None
        """
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
            logger.debug(f"實體準備創建 (待提交): {entity}")
            # 4. 刷新 Session-->移到service層
            # self.execute_query(
            #     lambda: self.session.flush(),
            #     err_msg=f"創建實體時刷新 session 失敗"
            # )
            return entity
        except IntegrityError as e:
            error_msg = f"Repository._create_internal: 完整性錯誤: {str(e)}"
            logger.error(error_msg)
            self._handle_integrity_error(e, f"創建{self.model_class.__name__}時")
        except ValidationError as e: 
            error_msg = f"Repository._create_internal: 必填欄位值驗證失敗: {str(e)}"
            logger.error(error_msg)
            raise e
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
        """內部更新，假設 update_payload 已通過 Pydantic Update Schema 驗證
        
        Args:
            entity_id: 實體ID
            update_payload: 更新資料
            
        Returns:
            更新的實體或 None
        """
        entity = self.get_by_id(entity_id)
        if not entity:
            error_msg = f"找不到ID為{entity_id}的實體，無法更新"
            logger.warning(error_msg)
            raise DatabaseOperationError(error_msg)
        
        try:
            update_schema_class = cast(Type[BaseUpdateSchema], self.get_schema_class(SchemaType.UPDATE))
            immutable_fields = update_schema_class.get_immutable_fields()
            entity_modified = False

            for key, value in update_payload.items():
                if key in immutable_fields:
                    continue
                if hasattr(entity, key):
                    current_value = getattr(entity, key)

                    if current_value != value:
                        setattr(entity, key, value) 
                        entity_modified = True

            if not entity_modified:
                msg = f"實體 ID={entity_id} 沒有變更，跳過資料庫操作。"
                logger.debug(msg)
                return None # 返回 None 表示沒有更新發生
            
            # --- 手動更新 updated_at ---
            if hasattr(entity, 'updated_at'):
                entity.updated_at = datetime.now(timezone.utc)
                logger.debug(f"手動更新 updated_at 為 {entity.updated_at}")
            # --- 手動更新結束 ---
            
            msg = f"實體準備更新 (待提交): {entity}"
            logger.debug(msg)
            return entity
        except IntegrityError as e:
            error_msg = f"更新{self.model_class.__name__} (ID={entity_id}) 時發生完整性錯誤: {str(e)}"
            logger.error(error_msg)
            self._handle_integrity_error(e, f"更新{self.model_class.__name__} (ID={entity_id}) 時")

        except ValidationError as e: # 捕捉 _validate_and_supplement 的錯誤 (如果使用)
            error_msg = f"Repository._update_internal: 必填欄位值驗證失敗 (ID={entity_id}): {str(e)}"
            logger.error(error_msg)
            raise e
        except Exception as e:
            error_msg = f"Repository._update_internal: 未預期錯誤 (ID={entity_id}): {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise DatabaseOperationError(error_msg)
    
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
            # Mark for deletion
            self.execute_query(
                lambda: self.session.delete(entity),
                err_msg=f"刪除ID為{entity_id}的資料庫物件時發生錯誤"
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
            error_msg = f"Repository.delete: 未預期錯誤: {str(e)}"
            logger.error(error_msg)
            raise DatabaseOperationError(error_msg) from e
        
        return False
        
    
    def find_paginated(self, page: int = 1, per_page: int = 10, 
                       filter_criteria: Optional[Dict[str, Any]] = None, 
                       extra_filters: Optional[List[Any]] = None, 
                       sort_by: Optional[str] = None, 
                       sort_desc: bool = False, 
                       is_preview: bool = False, 
                       preview_fields: Optional[List[str]] = None) -> tuple[int, list]:
        """獲取分頁數據，支援過濾、排序和預覽模式"""
        # 驗證分頁參數
        if not isinstance(per_page, int) or per_page <= 0:
            raise InvalidOperationError("每頁記錄數必須是正整數")
        if not isinstance(page, int) or page <= 0:
             page = 1 # 頁碼無效時預設為 1
        
        # 計算偏移量
        offset = (page - 1) * per_page
        
        # --- 預覽模式處理 (保持不變) ---
        query_entities = [self.model_class] # 默認查詢整個模型
        valid_preview_fields = []
        local_is_preview = is_preview # 創建本地變數以在閉包中使用
        if local_is_preview and preview_fields:
            valid_preview_fields = [field for field in preview_fields if hasattr(self.model_class, field)]
            if valid_preview_fields:
                 query_entities = [getattr(self.model_class, field) for field in valid_preview_fields]
            else:
                logger.warning(f"預覽模式請求的欄位 {preview_fields} 均無效，將返回完整物件。")
                local_is_preview = False # 重置預覽標誌
        # --- 預覽模式處理結束 ---
        
        # 構建查詢
        base_query = self.session.query(*query_entities)
        
        # --- 修改：應用過濾和額外過濾 --- 
        filtered_query = self._apply_filters(base_query, filter_criteria or {})
        if extra_filters:
            for extra_filter in extra_filters:
                filtered_query = filtered_query.filter(extra_filter)
        # --- 修改結束 ---

        # 添加排序
        sorted_query = filtered_query # Start with filtered query
        if sort_by:
            if not hasattr(self.model_class, sort_by):
                raise InvalidOperationError(f"無效的排序欄位: {sort_by}")
            sort_column = getattr(self.model_class, sort_by)
            order_by = desc(sort_column) if sort_desc else asc(sort_column)
            sorted_query = filtered_query.order_by(order_by)
        
        # 獲取總記錄數 (基於過濾後的查詢，但在應用分頁前)
        # 注意: count() 會忽略 with_entities 的設定，因此 count 需要基於完整模型
        count_query = self.session.query(self.model_class) 
        count_query = self._apply_filters(count_query, filter_criteria or {})
        if extra_filters: # Count 也需要應用額外過濾
            for extra_filter in extra_filters:
                count_query = count_query.filter(extra_filter)
        total = self.execute_query(lambda: count_query.count(), err_msg="計算總記錄數時出錯")
        
        # 應用分頁獲取當前頁的記錄
        paginated_query = sorted_query.offset(offset).limit(per_page)
        
        # 執行查詢
        raw_items = self.execute_query(
            lambda: paginated_query.all(),
            err_msg=f"分頁獲取資料時發生錯誤 (Page: {page}, PerPage: {per_page})"
        )
        
        # --- 結果轉換 (如果為預覽模式) ---
        items: list
        if local_is_preview and valid_preview_fields:
            items = [dict(zip(valid_preview_fields, row)) for row in raw_items]
        else:
            items = raw_items
        # --- 結果轉換結束 ---

        return total, items # 返回總數和當前頁項目

    # def find_all(self, *args, **kwargs):
    #     """找出所有實體的別名方法"""
    #     # 避免嵌套使用 execute_query
    #     return self.get_all(*args, **kwargs)

    def find_by_filter(self, filter_criteria: Dict[str, Any], sort_by: Optional[str] = None, sort_desc: bool = False, limit: Optional[int] = None, offset: Optional[int] = None, is_preview: bool = False, preview_fields: Optional[List[str]] = None) -> Union[List[T], List[Dict[str, Any]]]:
        """根據過濾條件查找實體列表，支援排序、分頁和預覽模式

        Args:
            filter_criteria: 過濾條件字典
            sort_by: 排序欄位名稱
            sort_desc: 是否降序排列
            limit: 限制返回結果數量
            offset: 跳過結果數量
            is_preview: 是否為預覽模式，若為 True 且 preview_fields 有效，返回字典列表
            preview_fields: 預覽模式下要選擇的欄位列表

        Returns:
            符合條件的實體列表 (預設) 或 字典列表 (預覽模式)
        """
        def query_builder():
            # --- 預覽模式處理 ---
            query_entities = [self.model_class] # 默認查詢整個模型
            valid_preview_fields = []
            local_is_preview = is_preview # 創建本地變數以在閉包中使用
            if local_is_preview and preview_fields:
                valid_preview_fields = [field for field in preview_fields if hasattr(self.model_class, field)]
                if valid_preview_fields:
                    query_entities = [getattr(self.model_class, field) for field in valid_preview_fields]
                else:
                    logger.warning(f"預覽模式請求的欄位 {preview_fields} 均無效，將返回完整物件。")
                    local_is_preview = False # 在此 query_builder 範圍內重置預覽標誌
            # --- 預覽模式處理結束 ---

            query = self.session.query(*query_entities)

            # 1. 應用過濾
            query = self._apply_filters(query, filter_criteria or {})

            # 2. 處理排序
            if sort_by:
                if not hasattr(self.model_class, sort_by):
                    raise InvalidOperationError(f"無效的排序欄位: {sort_by}")
                order_column = getattr(self.model_class, sort_by)
                if sort_desc:
                    query = query.order_by(desc(order_column))
                else:
                    query = query.order_by(asc(order_column))
            else:
                # 預設排序 (如果需要)
                try:
                    created_at_attr = getattr(self.model_class, 'created_at', None)
                    if created_at_attr is not None:
                        query = query.order_by(desc(created_at_attr))
                    else:
                        id_attr = getattr(self.model_class, 'id', None)
                        if id_attr is not None:
                            query = query.order_by(desc(id_attr))
                except (AttributeError, TypeError):
                    pass

            # 3. 應用偏移 (Offset)
            if offset is not None:
                query = query.offset(offset)

            # 4. 應用限制 (Limit)
            if limit is not None:
                query = query.limit(limit)

            # 執行查詢
            raw_results = query.all()

            # --- 結果轉換 (如果為預覽模式) ---
            if local_is_preview and valid_preview_fields:
                # 如果使用了 with_entities，結果是元組列表
                return [dict(zip(valid_preview_fields, row)) for row in raw_results]
            else:
                # 否則結果是模型實例列表
                return raw_results
            # --- 結果轉換結束 ---

        return self.execute_query(
            query_builder,
            err_msg=f"根據過濾條件 {filter_criteria} 查找資料時發生錯誤",
            exception_class=DatabaseOperationError
        )

    def find_all(self, limit: Optional[int] = None, offset: Optional[int] = None, sort_by: Optional[str] = None, sort_desc: bool = False, is_preview: bool = False, preview_fields: Optional[List[str]] = None) -> Union[List[T], List[Dict[str, Any]]]:
        """獲取所有實體，支援分頁、排序和預覽模式

        Args:
            limit: 限制返回結果數量
            offset: 跳過結果數量
            sort_by: 排序欄位名稱
            sort_desc: 是否降序排列
            is_preview: 是否為預覽模式，若為 True 且 preview_fields 有效，返回字典列表
            preview_fields: 預覽模式下要選擇的欄位列表

        Returns:
            實體列表 (預設) 或 字典列表 (預覽模式)
        """
        # 基本上與 find_by_filter 相同，只是 filter_criteria 為空
        # 為了避免代碼重複，可以直接調用 find_by_filter
        # return self.find_by_filter(
        #     filter_criteria={}, 
        #     limit=limit, 
        #     offset=offset, 
        #     sort_by=sort_by, 
        #     sort_desc=sort_desc, 
        #     is_preview=is_preview, 
        #     preview_fields=preview_fields
        # )
        # 或者，如果想保持獨立實現：
        def query_builder():
            # --- 預覽模式處理 ---
            query_entities = [self.model_class] # 默認查詢整個模型
            valid_preview_fields = []
            local_is_preview = is_preview # 創建本地變數以在閉包中使用
            if local_is_preview and preview_fields:
                valid_preview_fields = [field for field in preview_fields if hasattr(self.model_class, field)]
                if valid_preview_fields:
                    query_entities = [getattr(self.model_class, field) for field in valid_preview_fields]
                else:
                    logger.warning(f"預覽模式請求的欄位 {preview_fields} 均無效，將返回完整物件。")
                    local_is_preview = False # 在此 query_builder 範圍內重置預覽標誌
            # --- 預覽模式處理結束 ---

            query = self.session.query(*query_entities)
            
            # 應用過濾 (find_all 沒有過濾條件)
            # query = self._apply_filters(query, {}) # 這行不需要，因為沒有 filter_criteria
            
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
            
            # 執行查詢
            raw_results = query.all()

            # --- 結果轉換 (如果為預覽模式) ---
            if local_is_preview and valid_preview_fields:
                 # 如果使用了 with_entities，結果是元組列表
                return [dict(zip(valid_preview_fields, row)) for row in raw_results]
            else:
                # 否則結果是模型實例列表
                return raw_results
            # --- 結果轉換結束 ---
            
        return self.execute_query(
            query_builder,
            err_msg="獲取所有資料庫物件時發生錯誤",
            exception_class=DatabaseOperationError
        )
    