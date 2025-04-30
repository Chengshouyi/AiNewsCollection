"""提供通用的資料庫 CRUD 操作基礎 Repository 類別。"""

# 標準函式庫
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum, auto
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    cast,
)
import copy

# 第三方函式庫
from pydantic import BaseModel
from pydantic_core import ValidationError as PydanticValidationError
from sqlalchemy import and_, asc, desc, not_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

# 本地應用程式
from src.database.database_manager import check_session
from src.error.errors import (
    DatabaseOperationError,
    IntegrityValidationError,
    InvalidOperationError,
    ValidationError,
)
from src.models.base_model import Base
from src.models.base_schema import BaseCreateSchema, BaseUpdateSchema
  # 使用統一的 logger


# --- Setup ---
logger = logging.getLogger(__name__)  # 使用統一的 logger  # 使用統一的 logger
T = TypeVar("T", bound=Base)


class SchemaType(Enum):
    CREATE = auto()
    UPDATE = auto()
    LIST = auto()
    DETAIL = auto()


class BaseRepository(Generic[T], ABC):
    """基礎 Repository 類別，提供通用 CRUD 操作。"""

    def __init__(self, session: Session, model_class: Type[T]):
        self.session = session
        self.model_class = model_class

    @check_session
    def execute_query(
        self,
        query_func: Callable,
        exception_class=DatabaseOperationError,
        err_msg=None,
        preserve_exceptions=None,
    ):
        """執行查詢的通用包裝器。"""
        default_preserve = [IntegrityError, ValidationError, InvalidOperationError]
        if preserve_exceptions is None:
            preserve_exceptions = default_preserve

        try:
            return query_func()
        except Exception as e:
            error_message = f"{err_msg if err_msg else '資料庫操作錯誤'}: {e}"
            logger.error("執行查詢時發生錯誤: %s", error_message)

            if any(isinstance(e, exc) for exc in preserve_exceptions):
                raise

            raise exception_class(error_message) from e

    def _handle_integrity_error(self, e: IntegrityError, context: str) -> None:
        """處理完整性錯誤並記錄日誌。"""
        error_msg = None
        error_type = None

        error_str = str(e)
        if "UNIQUE constraint" in error_str:
            error_type = "唯一性約束錯誤"
            error_msg = f"{context}: 資料重複"
        elif "NOT NULL constraint" in error_str:
            error_type = "非空約束錯誤"
            error_msg = f"{context}: 必填欄位不可為空"
        elif "FOREIGN KEY constraint" in error_str:
            error_type = "外鍵約束錯誤"
            error_msg = f"{context}: 關聯資料不存在或無法刪除"
        else:
            error_type = "其他完整性錯誤"
            error_msg = f"{context}: {error_str}"

        logger.error(
            "完整性錯誤 - 類型: %s, 上下文: %s, 詳細訊息: %s, 模型: %s",
            error_type,
            context,
            error_str,
            self.model_class.__name__,
        )
        raise IntegrityValidationError(error_msg)

    # --- 抽象方法 ---
    @classmethod
    @abstractmethod
    def get_schema_class(
        cls, schema_type: SchemaType = SchemaType.CREATE
    ) -> Type[Union[BaseCreateSchema, BaseUpdateSchema]]:
        """子類必須實現此方法提供用於驗證的 Pydantic schema 類。"""
        raise NotImplementedError("子類必須實現此方法提供用於驗證的schema類")

    # --- 公開驗證方法 ---
    @classmethod
    def validate_data(
        cls, entity_data: Dict[str, Any], schema_type: SchemaType
    ) -> Dict[str, Any]:
        """
        公開的類別方法：使用 Pydantic Schema 驗證資料。
        """
        schema_class_untyped = cls.get_schema_class(schema_type)
        schema_class = cast(Type[BaseModel], schema_class_untyped)
        logger.debug(
            "使用 Schema '%s' 驗證資料 (%s)", schema_class.__name__, schema_type.name
        )
        try:
            instance = schema_class.model_validate(entity_data)

            if schema_type == SchemaType.UPDATE:
                validated_dict = instance.model_dump(exclude_unset=True)
                logger.debug("更新資料驗證成功 (Payload): %s", validated_dict)
            else:
                validated_dict = instance.model_dump()
                logger.debug("創建資料驗證成功 (含預設值): %s", validated_dict)

            return validated_dict
        except PydanticValidationError as e:
            error_msg = f"{schema_type.name} 資料驗證失敗: {str(e)}"
            logger.error("%s", error_msg)
            raise ValidationError(error_msg) from e
        except ValidationError as e:
            error_msg = f"{schema_type.name} 資料驗證失敗: {str(e)}"
            logger.error("%s", error_msg)
            raise e
        except Exception as e:
            error_msg = f"執行 validate_data 時發生非預期錯誤: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ValidationError(error_msg) from e

    # --- 受保護的輔助和內部方法 ---
    def _apply_filters(self, query, filter_criteria: Dict[str, Any]):
        """將過濾條件應用到 SQLAlchemy 查詢對象。"""
        if not filter_criteria:
            return query

        conditions = []
        for field, value in filter_criteria.items():
            if not hasattr(self.model_class, field):
                logger.warning(
                    "過濾條件中的欄位 '%s' 在模型 %s 中不存在，將忽略此條件。",
                    field,
                    self.model_class.__name__,
                )
                continue

            column = getattr(self.model_class, field)

            if isinstance(value, dict):
                for operator, operand in value.items():
                    if operator == "$in":
                        if isinstance(operand, list):
                            conditions.append(column.in_(operand))
                        else:
                            logger.warning(
                                "欄位 '%s' 的 $in 操作符需要一個列表作為操作數，收到 %s，忽略。",
                                field,
                                type(operand),
                            )
                    elif operator == "$nin":
                        if isinstance(operand, list):
                            conditions.append(not_(column.in_(operand)))
                        else:
                            logger.warning(
                                "欄位 '%s' 的 $nin 操作符需要一個列表作為操作數，收到 %s，忽略。",
                                field,
                                type(operand),
                            )
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
                        logger.warning(
                            "欄位 '%s' 的操作符 '%s' 不支援，忽略。", field, operator
                        )
            else:
                conditions.append(column == value)

        if conditions:
            return query.filter(and_(*conditions))
        else:
            return query

    def _validate_and_supplement_required_fields(
        self,
        pydantic_validated_data: Dict[str, Any],
        existing_entity: Optional[T] = None,
    ) -> Dict[str, Any]:
        """
        輔助方法：在 Pydantic 驗證後，檢查必填欄位的值是否有效，並在更新時補充。
        """
        copied_data = pydantic_validated_data.copy()

        create_schema_class = cast(
            Type[BaseCreateSchema], self.get_schema_class(SchemaType.CREATE)
        )
        required_fields = create_schema_class.get_required_fields()

        fields_to_check = required_fields.copy()

        if existing_entity:
            update_schema_class = cast(
                Type[BaseUpdateSchema], self.get_schema_class(SchemaType.UPDATE)
            )
            immutable_fields = update_schema_class.get_immutable_fields()
            fields_to_check_for_update = [
                f for f in required_fields if f not in immutable_fields
            ]

            for field in fields_to_check_for_update:
                if field not in copied_data or copied_data.get(field) is None:
                    if hasattr(existing_entity, field):
                        current_value = getattr(existing_entity, field)
                        if current_value is not None:
                            copied_data[field] = current_value
                            logger.debug("更新時從現有實體補充欄位 '%s'", field)

            fields_to_check = fields_to_check_for_update

        missing_or_empty_fields = []
        for field in fields_to_check:
            field_value = copied_data.get(field)
            if field_value is None or (
                isinstance(field_value, str) and not field_value.strip()
            ):
                missing_or_empty_fields.append(field)

        if missing_or_empty_fields:
            raise ValidationError(
                f"以下必填欄位值無效 (None 或空字串): {', '.join(missing_or_empty_fields)}"
            )

        logger.debug("必填欄位值驗證通過: %s", self.model_class.__name__)
        return copied_data

    def _create_internal(self, validated_data: Dict[str, Any]) -> Optional[T]:
        """內部創建方法。"""
        try:
            final_data = self._validate_and_supplement_required_fields(validated_data)
            entity = self.model_class(**final_data)

            self.execute_query(
                lambda: self.session.add(entity),
                err_msg="添加資料庫物件到session時發生錯誤",
            )
            logger.debug("實體準備創建 (待提交): %s", entity)
            return entity
        except IntegrityError as e:
            error_msg = f"Repository._create_internal: 完整性錯誤: {str(e)}"
            logger.error("%s", error_msg)
            self._handle_integrity_error(e, f"創建{self.model_class.__name__}時")
        except ValidationError as e:
            error_msg = f"Repository._create_internal: 必填欄位值驗證失敗: {str(e)}"
            logger.error("%s", error_msg)
            raise e
        except Exception as e:
            error_msg = f"Repository._create_internal: 未預期錯誤: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise DatabaseOperationError(error_msg) from e

    @abstractmethod
    def create(self, entity_data: Dict[str, Any]) -> Optional[T]:
        """創建實體（強制子類實現）。"""
        raise NotImplementedError("子類必須實現此方法提供用於驗證的schema類")

    def _update_internal(
        self, entity_id: Any, update_payload: Dict[str, Any]
    ) -> Optional[T]:
        """內部更新方法。"""
        entity = self.get_by_id(entity_id)
        if not entity:
            error_msg = f"找不到ID為{entity_id}的實體，無法更新"
            logger.warning("%s", error_msg)
            raise DatabaseOperationError(error_msg)

        try:
            update_schema_class = cast(
                Type[BaseUpdateSchema], self.get_schema_class(SchemaType.UPDATE)
            )
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
                logger.debug("%s", msg)
                return None

            if hasattr(entity, "updated_at"):
                new_time = datetime.now(timezone.utc)
                entity.updated_at = new_time
                # flag_modified(entity, "updated_at")
                logger.debug("手動更新 updated_at 為 %s", entity.updated_at)

            msg = f"實體準備更新 (待提交): {entity}"
            logger.debug("%s", msg)
            return entity
        except IntegrityError as e:
            error_msg = f"更新{self.model_class.__name__} (ID={entity_id}) 時發生完整性錯誤: {str(e)}"
            logger.error("%s", error_msg)
            self._handle_integrity_error(
                e, f"更新{self.model_class.__name__} (ID={entity_id}) 時"
            )
        except ValidationError as e:
            error_msg = f"Repository._update_internal: 必填欄位值驗證失敗 (ID={entity_id}): {str(e)}"
            logger.error("%s", error_msg)
            raise e
        except Exception as e:
            error_msg = (
                f"Repository._update_internal: 未預期錯誤 (ID={entity_id}): {str(e)}"
            )
            logger.error(error_msg, exc_info=True)
            raise DatabaseOperationError(error_msg) from e

    @abstractmethod
    def update(self, entity_id: Any, entity_data: Dict[str, Any]) -> Optional[T]:
        """更新實體（強制子類實現）。"""
        raise NotImplementedError("子類必須實現此方法提供用於驗證的schema類")

    def get_by_id(self, entity_id: Any) -> Optional[T]:
        """根據 ID 獲取實體。"""
        return self.execute_query(
            lambda: self.session.get(self.model_class, entity_id),
            err_msg=f"獲取ID為{entity_id}的資料庫物件時發生錯誤",
        )

    def delete(self, entity_id: Any) -> bool:
        """刪除實體。"""
        entity = self.get_by_id(entity_id)
        if not entity:
            return False

        try:
            self.execute_query(
                lambda: self.session.delete(entity),
                err_msg=f"刪除ID為{entity_id}的資料庫物件時發生錯誤",
            )
            return True
        except IntegrityError as e:
            self._handle_integrity_error(e, f"刪除{self.model_class.__name__}時")
        except Exception as e:
            error_msg = f"Repository.delete: 未預期錯誤: {str(e)}"
            logger.error("%s", error_msg)
            raise DatabaseOperationError(error_msg) from e

        return False

    def find_paginated(
        self,
        page: int = 1,
        per_page: int = 10,
        filter_criteria: Optional[Dict[str, Any]] = None,
        extra_filters: Optional[List[Any]] = None,
        sort_by: Optional[str] = None,
        sort_desc: bool = False,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> tuple[int, list]:
        """獲取分頁數據，支援過濾、排序和預覽模式。"""
        if not isinstance(per_page, int) or per_page <= 0:
            raise InvalidOperationError("每頁記錄數必須是正整數")
        if not isinstance(page, int) or page <= 0:
            page = 1

        offset = (page - 1) * per_page

        query_entities = [self.model_class]
        valid_preview_fields = []
        local_is_preview = is_preview
        if local_is_preview and preview_fields:
            valid_preview_fields = [
                field for field in preview_fields if hasattr(self.model_class, field)
            ]
            if valid_preview_fields:
                query_entities = [
                    getattr(self.model_class, field) for field in valid_preview_fields
                ]
            else:
                logger.warning(
                    "預覽模式請求的欄位 %s 均無效，將返回完整物件。", preview_fields
                )
                local_is_preview = False

        base_query = self.session.query(*query_entities)
        filtered_query = self._apply_filters(base_query, filter_criteria or {})
        if extra_filters:
            for extra_filter in extra_filters:
                filtered_query = filtered_query.filter(extra_filter)

        sorted_query = filtered_query
        if sort_by:
            if not hasattr(self.model_class, sort_by):
                raise InvalidOperationError(f"無效的排序欄位: {sort_by}")
            sort_column = getattr(self.model_class, sort_by)
            order_by = desc(sort_column) if sort_desc else asc(sort_column)
            sorted_query = filtered_query.order_by(order_by)

        count_query = self.session.query(self.model_class)
        count_query = self._apply_filters(count_query, filter_criteria or {})
        if extra_filters:
            for extra_filter in extra_filters:
                count_query = count_query.filter(extra_filter)
        total = self.execute_query(
            lambda: count_query.count(),
            err_msg="計算總記錄數時出錯",  # pylint: disable=unnecessary-lambda
        )

        paginated_query = sorted_query.offset(offset).limit(per_page)
        raw_items = self.execute_query(
            lambda: paginated_query.all(),  # pylint: disable=unnecessary-lambda
            err_msg=f"分頁獲取資料時發生錯誤 (Page: {page}, PerPage: {per_page})",
        )

        items: list
        if local_is_preview and valid_preview_fields:
            items = [dict(zip(valid_preview_fields, row)) for row in raw_items]
        else:
            items = raw_items

        return total, items

    def find_by_filter(
        self,
        filter_criteria: Dict[str, Any],
        sort_by: Optional[str] = None,
        sort_desc: bool = False,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List[T], List[Dict[str, Any]]]:
        """根據過濾條件查找實體列表。"""

        def query_builder():
            query_entities = [self.model_class]
            valid_preview_fields = []
            local_is_preview = is_preview
            if local_is_preview and preview_fields:
                valid_preview_fields = [
                    field
                    for field in preview_fields
                    if hasattr(self.model_class, field)
                ]
                if valid_preview_fields:
                    query_entities = [
                        getattr(self.model_class, field)
                        for field in valid_preview_fields
                    ]
                else:
                    logger.warning(
                        "預覽模式請求的欄位 %s 均無效，將返回完整物件。", preview_fields
                    )
                    local_is_preview = False

            query = self.session.query(*query_entities)
            query = self._apply_filters(query, filter_criteria or {})

            if sort_by:
                if not hasattr(self.model_class, sort_by):
                    raise InvalidOperationError(f"無效的排序欄位: {sort_by}")
                order_column = getattr(self.model_class, sort_by)
                if sort_desc:
                    query = query.order_by(desc(order_column))
                else:
                    query = query.order_by(asc(order_column))
            else:
                try:
                    created_at_attr = getattr(self.model_class, "created_at", None)
                    if created_at_attr is not None:
                        query = query.order_by(desc(created_at_attr))
                    else:
                        id_attr = getattr(self.model_class, "id", None)
                        if id_attr is not None:
                            query = query.order_by(desc(id_attr))
                except (AttributeError, TypeError):
                    pass

            if offset is not None:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)

            raw_results = query.all()

            if local_is_preview and valid_preview_fields:
                return [dict(zip(valid_preview_fields, row)) for row in raw_results]
            else:
                return raw_results

        return self.execute_query(
            query_builder,
            err_msg=f"根據過濾條件 {filter_criteria} 查找資料時發生錯誤",
            exception_class=DatabaseOperationError,
        )

    def find_all(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_desc: bool = False,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List[T], List[Dict[str, Any]]]:
        """獲取所有實體。"""

        def query_builder():
            query_entities = [self.model_class]
            valid_preview_fields = []
            local_is_preview = is_preview
            if local_is_preview and preview_fields:
                valid_preview_fields = [
                    field
                    for field in preview_fields
                    if hasattr(self.model_class, field)
                ]
                if valid_preview_fields:
                    query_entities = [
                        getattr(self.model_class, field)
                        for field in valid_preview_fields
                    ]
                else:
                    logger.warning(
                        "預覽模式請求的欄位 %s 均無效，將返回完整物件。", preview_fields
                    )
                    local_is_preview = False

            query = self.session.query(*query_entities)

            if sort_by:
                if not hasattr(self.model_class, sort_by):
                    raise InvalidOperationError(f"無效的排序欄位: {sort_by}")
                order_column = getattr(self.model_class, sort_by)
                if sort_desc:
                    query = query.order_by(desc(order_column))
                else:
                    query = query.order_by(asc(order_column))
            else:
                try:
                    created_at_attr = getattr(self.model_class, "created_at", None)
                    if created_at_attr is not None:
                        query = query.order_by(desc(created_at_attr))
                    else:
                        id_attr = getattr(self.model_class, "id", None)
                        if id_attr is not None:
                            query = query.order_by(desc(id_attr))
                except (AttributeError, TypeError):
                    pass

            if offset is not None:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)

            raw_results = query.all()

            if local_is_preview and valid_preview_fields:
                return [dict(zip(valid_preview_fields, row)) for row in raw_results]
            else:
                return raw_results

        return self.execute_query(
            query_builder,
            err_msg="獲取所有資料庫物件時發生錯誤",
            exception_class=DatabaseOperationError,
        )
