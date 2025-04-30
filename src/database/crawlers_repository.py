"""提供與爬蟲設定 (Crawlers) 相關的資料庫操作 Repository。

包含創建、讀取、更新、刪除 (CRUD) 爬蟲設定，以及特定查詢、
狀態切換、統計等功能。
"""

# Standard library imports
from typing import Any, Dict, List, Literal, Optional, Type, Union, overload
import logging

# Third party imports
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import load_only, noload

# Local application imports
from src.error.errors import DatabaseOperationError, ValidationError
from src.models.crawlers_model import Crawlers
from src.models.crawlers_schema import CrawlersCreateSchema, CrawlersUpdateSchema
  # 使用統一的 logger
from .base_repository import BaseRepository, SchemaType


logger = logging.getLogger(__name__)  # 使用統一的 logger
# logger.setLevel(logging.DEBUG)  # <-- 臨時添加這行


class CrawlersRepository(BaseRepository["Crawlers"]):
    """Crawlers 特定的Repository"""

    @classmethod
    @overload
    def get_schema_class(
        cls, schema_type: Literal[SchemaType.CREATE]
    ) -> Type[CrawlersCreateSchema]: ...

    @classmethod
    @overload
    def get_schema_class(
        cls, schema_type: Literal[SchemaType.UPDATE]
    ) -> Type[CrawlersUpdateSchema]: ...

    @classmethod
    def get_schema_class(
        cls, schema_type: SchemaType = SchemaType.CREATE
    ) -> Type[BaseModel]:
        """根據操作類型返回對應的schema類"""
        if schema_type == SchemaType.CREATE:
            return CrawlersCreateSchema
        elif schema_type == SchemaType.UPDATE:
            return CrawlersUpdateSchema
        raise ValueError(f"未支援的 schema 類型: {schema_type}")

    def create(self, entity_data: Dict[str, Any]) -> Optional[Crawlers]:
        """創建爬蟲設定，包含名稱唯一性檢查。"""
        try:
            crawler_name = entity_data.get("crawler_name")
            if crawler_name:
                existing_check = self.find_by_crawler_name_exact(crawler_name)
                if isinstance(existing_check, self.model_class):
                    raise ValidationError(f"爬蟲名稱 '{crawler_name}' 已存在")
                elif isinstance(existing_check, dict):
                    # PylintW1203:logging-fstring-interpolation fix
                    logger.warning(
                        "創建檢查時 find_by_crawler_name_exact 返回了字典，可能配置錯誤。名稱: %s",
                        crawler_name,
                    )
                    raise ValidationError(f"爬蟲名稱 '{crawler_name}' 已存在")

            if "is_active" not in entity_data:
                entity_data["is_active"] = True
            # created_at is handled by BaseCreateSchema

            validated_data = self.validate_data(entity_data, SchemaType.CREATE)

            if validated_data is None:
                # PylintW1203:logging-fstring-interpolation fix
                logger.error(
                    "創建 Crawler 時 validate_data 返回 None，原始資料: %s", entity_data
                )
                raise ValidationError("創建 Crawler 時驗證數據返回 None")
            else:
                return self._create_internal(validated_data)
        except ValidationError as e:
            # PylintW1203:logging-fstring-interpolation fix
            logger.error("創建 Crawler 驗證失敗: %s", e)
            raise
        except DatabaseOperationError:
            raise
        except Exception as e:
            # PylintW1203:logging-fstring-interpolation fix
            logger.error("創建 Crawler 時發生未預期錯誤: %s", e, exc_info=True)
            raise DatabaseOperationError(f"創建 Crawler 時發生未預期錯誤: {e}") from e

    def update(self, entity_id: Any, entity_data: Dict[str, Any]) -> Optional[Crawlers]:
        """更新爬蟲設定，包含名稱唯一性檢查（如果名稱變更）。"""
        try:
            existing_entity = self.get_by_id(entity_id)
            if not existing_entity:
                # PylintW1203:logging-fstring-interpolation fix
                logger.warning("找不到 ID=%s 的爬蟲設定，無法更新。", entity_id)
                return None

            new_crawler_name = entity_data.get("crawler_name")
            if new_crawler_name and new_crawler_name != existing_entity.crawler_name:
                existing_check = self.find_by_crawler_name_exact(new_crawler_name)
                if isinstance(existing_check, self.model_class):
                    raise ValidationError(f"爬蟲名稱 '{new_crawler_name}' 已存在")
                elif isinstance(existing_check, dict):
                    # PylintW1203:logging-fstring-interpolation fix
                    logger.warning(
                        "更新檢查時 find_by_crawler_name_exact 返回了字典，可能配置錯誤。名稱: %s",
                        new_crawler_name,
                    )
                    raise ValidationError(f"爬蟲名稱 '{new_crawler_name}' 已存在")

            # updated_at is handled by BaseUpdateSchema

            update_payload = self.validate_data(entity_data, SchemaType.UPDATE)

            if update_payload is None:
                # PylintW1203:logging-fstring-interpolation fix
                logger.error(
                    "更新 Crawler (ID=%s) 時 validate_data 返回 None，原始資料: %s",
                    entity_id,
                    entity_data,
                )
                raise ValidationError("更新 Crawler 時驗證數據返回 None")
            else:
                return self._update_internal(entity_id, update_payload)
        except ValidationError as e:
            # PylintW1203:logging-fstring-interpolation fix
            logger.error("更新 Crawler (ID=%s) 驗證失敗: %s", entity_id, e)
            raise
        except DatabaseOperationError:
            raise
        except Exception as e:
            # PylintW1203:logging-fstring-interpolation fix
            logger.error(
                "更新 Crawler (ID=%s) 時發生未預期錯誤: %s", entity_id, e, exc_info=True
            )
            raise DatabaseOperationError(
                f"更新 Crawler (ID={entity_id}) 時發生未預期錯誤: {e}"
            ) from e

    def find_active_crawlers(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List[Crawlers], List[Dict[str, Any]]]:
        """查詢活動中的爬蟲，支援分頁和預覽"""
        return self.find_by_filter(
            filter_criteria={"is_active": True},
            limit=limit,
            offset=offset,
            sort_by="created_at",
            sort_desc=True,
            is_preview=is_preview,
            preview_fields=preview_fields,
        )

    def find_by_crawler_id(
        self,
        crawler_id: int,
        is_active: bool = True,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Optional[Union[Crawlers, Dict[str, Any]]]:
        """根據爬蟲ID查詢，支援預覽"""
        results = self.find_by_filter(
            filter_criteria={"id": crawler_id, "is_active": is_active},
            limit=1,
            is_preview=is_preview,
            preview_fields=preview_fields,
        )
        return results[0] if results else None

    def find_by_crawler_name(
        self,
        crawler_name: str,
        is_active: Optional[bool] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List[Crawlers], List[Dict[str, Any]]]:
        """根據爬蟲名稱模糊查詢，支援活躍狀態過濾、分頁和預覽"""

        def query_builder():
            query_entities = [self.model_class]
            valid_preview_fields = []
            local_is_preview = is_preview
            if local_is_preview and preview_fields:
                valid_preview_fields = [
                    f for f in preview_fields if hasattr(self.model_class, f)
                ]
                if valid_preview_fields:
                    query_entities = [
                        getattr(self.model_class, f) for f in valid_preview_fields
                    ]
                else:
                    # PylintW1203:logging-fstring-interpolation fix
                    logger.warning(
                        "find_by_crawler_name 預覽欄位無效: %s，返回完整物件。",
                        preview_fields,
                    )
                    local_is_preview = False

            query = self.session.query(*query_entities).filter(
                self.model_class.crawler_name.like(f"%{crawler_name}%")
            )

            if is_active is not None:
                query = query.filter(self.model_class.is_active == is_active)

            if hasattr(self.model_class, "created_at"):
                query = query.order_by(self.model_class.created_at.desc())

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
            # PylintW1203:logging-fstring-interpolation fix (using % formatting)
            err_msg=f"模糊查詢爬蟲名稱 '{crawler_name}' 時發生錯誤",
        )

    def toggle_active_status(self, crawler_id: int) -> bool:
        """切換爬蟲活躍狀態"""

        def toggle_status():
            crawler = self.get_by_id(crawler_id)
            if not crawler:
                return False

            update_data = {
                "is_active": not crawler.is_active,
                # updated_at is handled by BaseUpdateSchema now in the update method
                # 'updated_at': datetime.now(timezone.utc)
            }
            updated_crawler = self.update(crawler_id, update_data)
            return updated_crawler is not None

        return self.execute_query(
            toggle_status,
            # PylintW1203:logging-fstring-interpolation fix (using % formatting)
            err_msg=f"切換爬蟲ID={crawler_id}活躍狀態時發生錯誤",
        )

    def find_by_type(
        self,
        crawler_type: str,
        is_active: Optional[bool] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List[Crawlers], List[Dict[str, Any]]]:
        """根據爬蟲類型查找爬蟲，支援活躍狀態過濾、分頁和預覽"""
        filter_criteria: Dict[str, Any] = {"crawler_type": crawler_type}

        if is_active is not None:
            filter_criteria["is_active"] = is_active

        return self.find_by_filter(
            filter_criteria=filter_criteria,
            limit=limit,
            offset=offset,
            sort_by="created_at",
            sort_desc=True,
            is_preview=is_preview,
            preview_fields=preview_fields,
        )

    def find_by_target(
        self,
        target_pattern: str,
        is_active: Optional[bool] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List[Crawlers], List[Dict[str, Any]]]:
        """根據爬取目標(base_url)模糊查詢爬蟲，支援活躍狀態過濾、分頁和預覽"""

        def query_builder():
            from sqlalchemy.orm import noload  # <--- 導入 noload

            # --- 修改開始 ---
            valid_preview_fields = []
            local_is_preview = is_preview
            query_entities_orm = []  # 儲存 ORM 屬性

            if local_is_preview and preview_fields:
                # --- 預覽模式邏輯 ---
                for field_name in preview_fields:
                    if hasattr(self.model_class, field_name):
                        # 確保關聯屬性不被加入 query_entities_orm (load_only 不處理關聯)
                        if (
                            field_name != "crawler_tasks"
                        ):  # 假設關聯名稱是 crawler_tasks
                            valid_preview_fields.append(field_name)
                            query_entities_orm.append(
                                getattr(self.model_class, field_name)
                            )

                if not valid_preview_fields:
                    logger.warning(
                        "find_by_target 預覽欄位無效: %s，返回完整物件。",
                        preview_fields,
                    )
                    local_is_preview = False
                    # 無效預覽，載入所有非關聯欄位
                    query_entities_orm = [
                        getattr(self.model_class, c.name)
                        for c in self.model_class.__table__.columns  # 只獲取基本欄位
                    ]
            else:
                # --- 非預覽模式邏輯 ---
                # 獲取 Crawlers 模型所有基本欄位的 ORM 映射屬性
                query_entities_orm = [
                    getattr(self.model_class, c.name)
                    for c in self.model_class.__table__.columns  # 只獲取基本欄位
                ]

            # --- 查詢構建 ---
            query = (
                self.session.query(self.model_class)
                .options(
                    # --- 關鍵修改：明確禁止載入 'crawler_tasks' 關聯 ---
                    noload(self.model_class.crawler_tasks),
                    # 仍然使用 load_only 限制 Crawlers 自身的欄位
                    load_only(*query_entities_orm),
                )
                .filter(self.model_class.base_url.like(f"%{target_pattern}%"))
            )
            # --- 結束修改 ---

            if is_active is not None:
                query = query.filter(self.model_class.is_active == is_active)

            if hasattr(self.model_class, "created_at"):
                query = query.order_by(
                    self.model_class.created_at.desc(), self.model_class.id.asc()
                )
            elif hasattr(self.model_class, "id"):
                query = query.order_by(self.model_class.id.asc())

            if offset is not None:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)

            # --- SQL 日誌記錄 (保持不變) ---
            try:
                from sqlalchemy.dialects import sqlite

                compiled_query = query.statement.compile(
                    dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}
                )
                logger.debug(
                    "new version: Executing SQL for find_by_target (offset=%s, limit=%s): %s",
                    offset,
                    limit,
                    compiled_query,
                )
            except Exception as log_err:
                logger.error("Error compiling or logging SQL query: %s", log_err)
            # --- 結束添加 ---

            raw_results = query.all()

            # --- 添加調試日誌 ---
            if offset == 2 and limit == 1:
                logger.debug(
                    "Executing query.all() for offset=2, limit=1 returned %d results: %s",
                    len(raw_results),
                    raw_results,
                )
            # --- 結束添加 ---

            if local_is_preview and valid_preview_fields:
                return [
                    {f: getattr(row, f) for f in valid_preview_fields}
                    for row in raw_results
                ]
            else:
                return raw_results

        return self.execute_query(
            query_builder,
            err_msg=f"模糊查詢爬蟲目標 '{target_pattern}' 時發生錯誤",
        )

    def get_crawler_statistics(self) -> Dict[str, Any]:
        """獲取爬蟲統計信息"""

        def get_statistics():
            total = self.session.query(func.count(self.model_class.id)).scalar() or 0
            active = (
                self.session.query(func.count(self.model_class.id))
                .filter(self.model_class.is_active == True)
                .scalar()
                or 0
            )

            type_counts = (
                self.session.query(
                    self.model_class.crawler_type, func.count(self.model_class.id)
                )
                .group_by(self.model_class.crawler_type)
                .all()
            )

            return {
                "total": total,
                "active": active,
                "inactive": total - active,
                "by_type": {crawler_type: count for crawler_type, count in type_counts},
            }

        return self.execute_query(get_statistics, err_msg="獲取爬蟲統計信息時發生錯誤")

    def find_by_crawler_name_exact(
        self,
        crawler_name: str,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Optional[Union[Crawlers, Dict[str, Any]]]:
        """根據爬蟲名稱精確查詢，支援預覽"""
        results = self.find_by_filter(
            filter_criteria={"crawler_name": crawler_name},
            limit=1,
            is_preview=is_preview,
            preview_fields=preview_fields,
        )
        return results[0] if results else None

    def create_or_update(self, entity_data: Dict[str, Any]) -> Optional[Crawlers]:
        """創建或更新爬蟲設定"""
        if "id" in entity_data and entity_data["id"]:
            crawler_id = entity_data.pop("id")
            updated_crawler = self.update(crawler_id, entity_data)
            # 如果更新成功，直接返回；否則繼續嘗試創建
            if updated_crawler:
                return updated_crawler
            else:
                # PylintW1203:logging-fstring-interpolation fix
                logger.warning(
                    "更新爬蟲 ID=%s 失敗，將嘗試創建新記錄。數據: %s",
                    crawler_id,
                    entity_data,
                )
                # 確保在創建前，傳入的數據中沒有 id
                if "id" in entity_data:
                    del entity_data["id"]  # 避免 create 報錯

        # ID不存在或更新失敗，創建新爬蟲
        return self.create(entity_data)

    def batch_toggle_active(
        self, crawler_ids: List[int], active_status: bool
    ) -> Dict[str, Any]:
        """批量設置爬蟲的活躍狀態"""

        def batch_update():
            success_count = 0
            failed_ids = []

            for crawler_id in crawler_ids:
                try:
                    # 這裡直接調用 toggle_active_status 可能更簡潔且能利用其錯誤處理
                    # 但為了演示批量操作的原子性（雖然這裡不是真的原子），保留 update
                    crawler = self.get_by_id(crawler_id)
                    if not crawler:
                        failed_ids.append(crawler_id)
                        continue

                    # 只有當狀態不同時才更新
                    if crawler.is_active != active_status:
                        update_data = {
                            "is_active": active_status,
                            # updated_at is handled by BaseUpdateSchema in update
                        }
                        updated = self.update(crawler_id, update_data)
                        if updated:
                            success_count += 1
                        else:
                            # PylintW1203:logging-fstring-interpolation fix
                            logger.warning(
                                "批量切換狀態時更新爬蟲 ID=%s 失敗。", crawler_id
                            )
                            failed_ids.append(crawler_id)
                    else:
                        # 狀態相同，也視為成功（無操作）
                        success_count += 1

                except Exception as e:
                    # 在循環內部捕獲異常，以便繼續處理其他 ID
                    # PylintW1203:logging-fstring-interpolation fix
                    logger.error(
                        "批量切換爬蟲 ID=%s 狀態時發生錯誤: %s",
                        crawler_id,
                        e,
                        exc_info=True,
                    )
                    # 回滾當前失敗的操作（如果 update 內部沒有處理）
                    # 理想情況下 update 應處理回滾，但這裡添加以防萬一
                    try:
                        self.session.rollback()
                    except Exception as rb_err:
                        # PylintW1203:logging-fstring-interpolation fix
                        logger.error(
                            "批量切換狀態時回滾爬蟲 ID=%s 失敗: %s", crawler_id, rb_err
                        )
                    failed_ids.append(crawler_id)

            # 注意：這個實現不是真正的原子操作。如果一個更新失敗，之前的成功更新仍然會被提交（如果 commit 在外部）。
            # 真正的批量更新通常使用 session.bulk_update_mappings 或 update() 語句。
            # 但這裡為了重用 self.update 的邏輯（包括驗證），採用了逐個更新的方式。
            return {
                "success_count": success_count,
                "fail_count": len(failed_ids),
                "failed_ids": failed_ids,
            }

        status_text = "啟用" if active_status else "停用"
        return self.execute_query(
            batch_update,
            # PylintW1203:logging-fstring-interpolation fix (using % formatting)
            err_msg=f"批量 {status_text} 爬蟲時發生錯誤",
        )
