"""此模組定義 ArticlesRepository 類別，用於處理與文章相關的資料庫操作。"""

from datetime import datetime, timezone, timedelta
import logging
from typing import (
    Optional,
    List,
    Dict,
    Any,
    Type,
    Union,
    overload,
    Literal,
    Tuple,
    cast,
)

from sqlalchemy import func, or_, case, desc, asc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query

from src.database.base_repository import BaseRepository, SchemaType
from src.error.errors import (
    ValidationError,
    DatabaseOperationError,
    InvalidOperationError,
)
from src.models.articles_model import Articles, ArticleScrapeStatus
from src.models.articles_schema import ArticleCreateSchema, ArticleUpdateSchema
  # 使用統一的 logger

# 使用統一的 logger
logger = logging.getLogger(__name__)  # 使用統一的 logger


class ArticlesRepository(BaseRepository[Articles]):
    """Article 的Repository"""

    @classmethod
    @overload
    def get_schema_class(
        cls, schema_type: Literal[SchemaType.UPDATE]
    ) -> Type[ArticleUpdateSchema]: ...

    @classmethod
    @overload
    def get_schema_class(
        cls, schema_type: Literal[SchemaType.CREATE]
    ) -> Type[ArticleCreateSchema]: ...

    @classmethod
    def get_schema_class(
        cls, schema_type: SchemaType = SchemaType.CREATE
    ) -> Type[Union[ArticleCreateSchema, ArticleUpdateSchema]]:
        """根據操作類型返回對應的schema類"""
        if schema_type == SchemaType.CREATE:
            return ArticleCreateSchema
        elif schema_type == SchemaType.UPDATE:
            return ArticleUpdateSchema
        raise ValueError(f"未支援的 schema 類型: {schema_type}")

    def find_by_link(self, link: str) -> Optional[Articles]:
        """根據文章連結查詢"""
        return self.execute_query(
            lambda: self.session.query(self.model_class).filter_by(link=link).first()
        )

    def find_by_category(
        self,
        category: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List[Articles], List[Dict[str, Any]]]:
        """根據分類查詢文章，支援分頁和預覽"""
        page = 1
        per_page = limit if limit is not None and limit > 0 else 10
        if offset is not None and offset >= 0 and per_page > 0:
            page = (offset // per_page) + 1
        elif offset is not None:
            logger.warning(
                "Offset (%s) provided but limit/per_page (%s) is invalid, defaulting to page 1.",
                offset,
                limit,
            )
            page = 1

        total, items = self.find_paginated(
            filter_criteria={"category": category},
            page=page,
            per_page=per_page,
            is_preview=is_preview,
            preview_fields=preview_fields,
        )
        return items

    def search_by_title(
        self,
        keyword: str,
        exact_match: bool = False,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List[Articles], List[Dict[str, Any]]]:
        """根據標題搜索文章，支援分頁和預覽

        Args:
            keyword: 搜索關鍵字
            exact_match: 是否進行精確匹配（預設為模糊匹配）
            limit: 限制數量
            offset: 偏移量
            is_preview: 是否預覽模式
            preview_fields: 預覽欄位

        Returns:
            符合條件的文章列表 (模型實例或字典)
        """
        if exact_match:
            return self.find_by_filter(
                filter_criteria={"title": keyword},
                limit=limit,
                offset=offset,
                is_preview=is_preview,
                preview_fields=preview_fields,
            )
        else:

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
                        logger.warning(
                            "search_by_title (fuzzy) 預覽欄位無效: %s，返回完整物件。",
                            preview_fields,
                        )
                        local_is_preview = False

                query = self.session.query(*query_entities).filter(
                    self.model_class.title.like(f"%{keyword}%")
                )

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
                query_builder, err_msg=f"模糊搜索標題 '{keyword}' 時出錯"
            )

    def search_by_keywords(
        self,
        keywords: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List[Articles], List[Dict[str, Any]]]:
        """根據關鍵字搜索文章（標題、內容和摘要），支援分頁和預覽

        Args:
            keywords: 搜索關鍵字
            limit: 限制數量
            offset: 偏移量
            is_preview: 是否預覽模式
            preview_fields: 預覽欄位

        Returns:
            符合條件的文章列表 (模型實例或字典)
        """
        if not keywords or not isinstance(keywords, str):
            logger.warning("search_by_keywords 需要一個非空字串關鍵字。")
            return []

        # 假設 BaseRepository._apply_filters 會處理 'search_text'
        filter_criteria = {"search_text": keywords}

        return self.find_by_filter(
            filter_criteria=filter_criteria,
            limit=limit,
            offset=offset,
            is_preview=is_preview,
            preview_fields=preview_fields,
        )

    def get_statistics(self) -> Dict[str, Any]:
        """獲取文章統計信息"""

        def stats_func():
            total_count = self.count()
            ai_related_count = self.count({"is_ai_related": True})
            category_distribution = self.get_category_distribution()
            source_distribution = self.get_source_distribution()
            scrape_status_distribution = self.get_scrape_status_distribution()
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            recent_count = self.count({"published_at": {"$gte": week_ago}})

            return {
                "total_count": total_count,
                "ai_related_count": ai_related_count,
                "category_distribution": category_distribution,
                "recent_count": recent_count,
                "source_distribution": source_distribution,
                "scrape_status_distribution": scrape_status_distribution,
            }

        return self.execute_query(stats_func, err_msg="獲取文章統計信息時發生錯誤")

    def get_scrape_status_distribution(self) -> Dict[str, int]:
        """獲取各爬取狀態的統計 (返回字典)"""

        def stats_func():
            result = (
                self.session.query(
                    self.model_class.scrape_status, func.count(self.model_class.id)  # type: ignore
                )
                .group_by(self.model_class.scrape_status)
                .all()
            )
            return {
                (
                    status.value
                    if isinstance(status, ArticleScrapeStatus)
                    else str(status)
                ): count
                for status, count in result
            }

        return self.execute_query(stats_func, err_msg="獲取爬取狀態統計時發生錯誤")

    def get_source_distribution(self) -> Dict[str, int]:
        """獲取各來源的統計 (返回字典)"""

        def stats_func():
            result = (
                self.session.query(
                    self.model_class.source, func.count(self.model_class.id)
                )
                .group_by(self.model_class.source)
                .all()
            )
            return {
                str(source) if source else "未知來源": count for source, count in result
            }

        return self.execute_query(stats_func, err_msg="獲取來源統計時發生錯誤")

    def get_source_statistics(self) -> Dict[str, Dict[str, int]]:
        """獲取各來源的爬取統計"""

        def stats_func():
            total_stats = (
                self.session.query(
                    self.model_class.source,
                    func.count(self.model_class.id).label("total"),
                    func.sum(
                        case((self.model_class.is_scraped == False, 1), else_=0)
                    ).label("unscraped"),
                    func.sum(
                        case((self.model_class.is_scraped == True, 1), else_=0)
                    ).label("scraped"),
                )
                .group_by(self.model_class.source)
                .all()
            )

            return {
                source: {
                    "total": total,
                    "unscraped": unscraped or 0,
                    "scraped": scraped or 0,
                }
                for source, total, unscraped, scraped in total_stats
            }

        return self.execute_query(stats_func, err_msg="獲取來源統計時發生錯誤")

    def count(self, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        """計算符合條件的文章數量"""

        def query_builder():
            query = self.session.query(func.count(self.model_class.id))
            query = self._apply_filters(query, filter_dict or {})
            result = query.scalar()
            return result if result is not None else 0

        return self.execute_query(
            query_builder, err_msg="計算符合條件的文章數量時發生錯誤"
        )

    def get_category_distribution(self) -> Dict[str, int]:
        """獲取各分類的文章數量分布"""

        def query_builder():
            return (
                self.session.query(
                    self.model_class.category, func.count(self.model_class.id)
                )
                .group_by(self.model_class.category)
                .all()
            )

        result = self.execute_query(
            query_builder, err_msg="獲取各分類的文章數量分布時發生錯誤"
        )
        return {
            str(category) if category else "未分類": count for category, count in result
        }

    def find_by_tags(
        self,
        tags: List[str],
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List[Articles], List[Dict[str, Any]]]:
        """根據標籤列表查詢文章 (OR 邏輯)，支援分頁和預覽"""
        if not tags or not isinstance(tags, list):
            logger.warning("find_by_tags 需要一個非空的標籤列表。")
            return []

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
                    logger.warning(
                        "find_by_tags 預覽欄位無效: %s，返回完整物件。", preview_fields
                    )
                    local_is_preview = False

            query = self.session.query(*query_entities)

            conditions = []
            for tag in tags:
                if isinstance(tag, str) and tag.strip():
                    conditions.append(self.model_class.tags.like(f"%{tag.strip()}%"))
                else:
                    logger.warning("find_by_tags 收到無效標籤: %s, 已忽略。", tag)

            if conditions:
                query = query.filter(or_(*conditions))
            else:
                logger.info("find_by_tags: 沒有提供有效的標籤條件。")
                return []

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
            query_builder, err_msg="根據標籤列表查詢文章時發生錯誤"
        )

    def validate_unique_link(
        self, link: str, exclude_id: Optional[int] = None, raise_error: bool = True
    ) -> bool:
        """驗證文章連結是否唯一，不允許空連結。"""
        if not link or not link.strip():
            raise ValidationError("連結不可為空")

        def query_builder():
            query = self.session.query(self.model_class).filter_by(link=link)
            if exclude_id is not None:
                query = query.filter(self.model_class.id != exclude_id)
            return query.first()

        existing = self.execute_query(
            query_builder, err_msg="驗證文章連結唯一性時發生錯誤"
        )

        if existing:
            if raise_error:
                raise ValidationError(f"已存在具有相同連結的文章: {link}")
            return False

        return True

    def create(self, entity_data: Dict[str, Any]) -> Optional[Articles]:
        """
        創建文章。如果連結已存在，則觸發更新邏輯。
        先進行 Pydantic 驗證，然後調用內部創建。

        Args:
            entity_data: 實體資料字典。

        Returns:
            創建或更新後的 Articles 實例，如果發生錯誤則返回 None 或拋出異常。

        Raises:
            ValidationError: 如果輸入資料驗證失敗。
            DatabaseOperationError: 如果資料庫操作失敗。
            Exception: 其他未預期錯誤。
        """
        link = entity_data.get("link")
        if link:
            existing_article = self.find_by_link(link)
            if existing_article:
                error_msg = f"文章連結 '{link}' 已存在，驗證失敗。"
                logger.info(error_msg)
                raise ValidationError(error_msg)
                # 相同連結更新這種業務邏輯應該在 Service 層處理

        try:
            # 設定預設值 (更好的做法是在 Schema 或 Service 層處理)
            if "scrape_status" not in entity_data:
                entity_data["scrape_status"] = ArticleScrapeStatus.LINK_SAVED
            if "is_scraped" not in entity_data:
                entity_data["is_scraped"] = False

            # 使用基類方法進行 Pydantic 驗證
            validated_data = self.validate_data(entity_data, SchemaType.CREATE)

            if validated_data is None:
                error_msg = "創建 Article 時驗證步驟失敗"
                logger.error(error_msg)
                raise ValidationError(error_msg)

            # 調用內部創建方法
            created_article = self._create_internal(validated_data)
            return created_article

        except ValidationError as e:
            logger.error("創建 Article 驗證失敗: %s", e)
            raise
        except DatabaseOperationError as e:
            logger.error("創建 Article 時資料庫操作失敗: %s", e)
            raise
        except Exception as e:
            logger.error("創建 Article 時發生未預期錯誤: %s", e, exc_info=True)
            raise DatabaseOperationError(f"創建 Article 時發生未預期錯誤: {e}") from e

    def update(self, entity_id: Any, entity_data: Dict[str, Any]) -> Optional[Articles]:
        """
        更新文章。
        先進行 Pydantic 驗證，然後調用內部更新。

        Args:
            entity_id: 要更新的實體 ID。
            entity_data: 包含更新欄位的字典。

        Returns:
            更新後的 Articles 實例，如果未找到實體或未做任何更改則返回 None，
            如果發生錯誤則拋出異常。

        Raises:
            ValidationError: 如果輸入資料驗證失敗或包含不可變欄位。
            DatabaseOperationError: 如果資料庫操作失敗。
            Exception: 其他未預期錯誤。
        """
        try:
            # 獲取不可變欄位
            update_schema_class = self.get_schema_class(SchemaType.UPDATE)
            immutable_fields = update_schema_class.get_immutable_fields()

            payload_for_validation = entity_data.copy()

            # 檢查是否有嘗試更新不可變欄位
            invalid_immutable_updates = []
            for field in immutable_fields:
                if field in payload_for_validation:
                    invalid_immutable_updates.append(field)
                    payload_for_validation.pop(field, None)

            if invalid_immutable_updates:
                raise ValidationError(
                    f"不能更新不可變欄位: {', '.join(invalid_immutable_updates)}"
                )

            if not payload_for_validation:
                logger.debug(
                    "更新 Article (ID=%s) 的 payload 為空 (移除非法欄位後)，跳過驗證和更新。",
                    entity_id,
                )
                return None

            # 執行 Pydantic 驗證
            validated_payload = self.validate_data(
                payload_for_validation, SchemaType.UPDATE
            )

            if validated_payload is None:
                error_msg = f"更新 Article (ID={entity_id}) 時驗證步驟失敗"
                logger.error(error_msg)
                raise ValidationError(error_msg)

            if not validated_payload:
                logger.debug(
                    "更新 Article (ID=%s) 驗證後的 payload 為空，無需更新資料庫。",
                    entity_id,
                )
                return None

            # 調用內部更新方法
            updated_article = self._update_internal(entity_id, validated_payload)
            return updated_article

        except ValidationError as e:
            logger.error("更新 Article (ID=%s) 驗證失敗: %s", entity_id, e)
            raise
        except DatabaseOperationError as e:
            logger.error("更新 Article (ID=%s) 時資料庫操作失敗: %s", entity_id, e)
            raise
        except Exception as e:
            logger.error(
                "更新 Article (ID=%s) 時發生未預期錯誤: %s", entity_id, e, exc_info=True
            )
            raise DatabaseOperationError(
                f"更新 Article (ID={entity_id}) 時發生未預期錯誤: {e}"
            ) from e

    def update_scrape_status(
        self,
        link: str,
        is_scraped: bool = True,
        status: Optional[ArticleScrapeStatus] = None,
    ) -> bool:
        """更新文章連結的爬取狀態和狀態標籤"""

        def update_func():
            link_entity = self.find_by_link(link)
            if not link_entity:
                logger.warning("嘗試更新爬取狀態，但找不到連結: %s", link)
                return False

            entity_changed = False
            is_scraped_bool = bool(is_scraped)

            if link_entity.is_scraped != is_scraped_bool:
                link_entity.is_scraped = is_scraped_bool
                entity_changed = True

            # 根據 is_scraped 和傳入的 status 更新狀態標籤
            target_status = status
            if target_status is None:
                if is_scraped_bool:
                    target_status = ArticleScrapeStatus.CONTENT_SCRAPED
                elif link_entity.scrape_status not in [
                    ArticleScrapeStatus.FAILED,
                    ArticleScrapeStatus.PENDING,
                ]:
                    # 只有當 is_scraped 為 False 且當前狀態不是 FAILED 或 PENDING 時，
                    # 才將其設為 FAILED (避免覆蓋 PENDING 狀態)
                    target_status = ArticleScrapeStatus.FAILED

            if (
                target_status is not None
                and isinstance(target_status, ArticleScrapeStatus)
                and link_entity.scrape_status != target_status
            ):
                link_entity.scrape_status = target_status
                entity_changed = True
            elif target_status is not None and not isinstance(
                target_status, ArticleScrapeStatus
            ):
                logger.warning(
                    "更新連結 '%s' 的 scrape_status 時提供了無效的類型: %s, 已忽略。",
                    link,
                    type(target_status),
                )

            if entity_changed:
                logger.debug(
                    "更新連結 '%s' 爬取狀態為 is_scraped=%s, status=%s",
                    link,
                    is_scraped_bool,
                    link_entity.scrape_status.name,
                )
                return True
            else:
                logger.debug("連結 '%s' 爬取狀態未變更，跳過更新。", link)
                return True  # 操作完成 (即使無變化)

        try:
            return self.execute_query(
                update_func, err_msg=f"更新文章連結爬取狀態時發生錯誤: {link}"
            )
        except Exception as e:
            logger.error(
                "更新連結 %s 爬取狀態時發生未預期錯誤: %s", link, e, exc_info=True
            )
            raise

    def batch_update_by_link(
        self, entities_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """批量更新文章
        Args:
            entities_data: 實體資料列表, 每個字典必須包含 'link' 和其他要更新的欄位。

        Returns:
            包含成功和失敗資訊的字典
        """
        success_count = 0
        fail_count = 0
        updated_articles: List[Articles] = []
        missing_links: List[str] = []
        error_details: List[Dict[str, Any]] = []

        for entity_data in entities_data:
            link = entity_data.get("link")
            if not link or not isinstance(link, str):
                logger.warning("批量更新缺少有效的 'link' 鍵: %s", entity_data)
                fail_count += 1
                error_details.append({"link": link, "error": "缺少有效的 'link' 鍵"})
                continue

            try:
                update_payload = entity_data.copy()
                update_payload.pop("link", None)

                if not update_payload:
                    logger.debug("連結 '%s' 的更新 payload 為空，跳過。", link)
                    continue

                entity = self.find_by_link(link)
                if not entity:
                    missing_links.append(link)
                    fail_count += 1
                    continue

                # 使用 update 方法進行驗證和更新
                updated_entity = self.update(entity.id, update_payload)

                success_count += 1
                if updated_entity:
                    updated_articles.append(updated_entity)
                else:
                    logger.debug("連結 '%s' 的更新未導致實際變更。", link)

            except (ValidationError, DatabaseOperationError) as e:
                logger.error("更新實體 link=%s 時發生錯誤: %s", link, str(e))
                fail_count += 1
                error_details.append({"link": link, "error": str(e)})
            except Exception as e:
                logger.error(
                    "更新實體 link=%s 時發生未預期錯誤: %s", link, str(e), exc_info=True
                )
                fail_count += 1
                error_details.append({"link": link, "error": f"未預期錯誤: {str(e)}"})
                continue

        return {
            "success_count": success_count,
            "fail_count": fail_count,
            "updated_articles": updated_articles,
            "missing_links": missing_links,
            "error_details": error_details,
        }

    def batch_update_by_ids(
        self, entity_ids: List[Any], entity_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        批量使用相同的資料更新多個文章 ID。

        Args:
            entity_ids: 要更新的文章ID列表。
            entity_data: 要應用於每個文章的更新資料字典。

        Returns:
            Dict: 包含成功和失敗資訊的字典
        """
        updated_articles: List[Articles] = []
        missing_ids: List[Any] = []
        error_details: List[Dict[str, Any]] = []
        success_count = 0

        if not entity_data:
            logger.warning("batch_update_by_ids 收到空的 entity_data，不執行任何更新。")
            return {
                "success_count": 0,
                "fail_count": 0,
                "updated_articles": [],
                "missing_ids": [],
                "error_details": [],
            }

        # 預先檢查不可變欄位
        try:
            update_schema_class = self.get_schema_class(SchemaType.UPDATE)
            immutable_fields = update_schema_class.get_immutable_fields()
            invalid_immutable_updates = [
                f for f in immutable_fields if f in entity_data
            ]
            if invalid_immutable_updates:
                raise ValidationError(
                    f"批量更新嘗試修改不可變欄位: {', '.join(invalid_immutable_updates)}"
                )
        except ValidationError as e:
            logger.error("批量更新因包含不可變欄位而中止: %s", e)
            return {
                "success_count": 0,
                "fail_count": len(entity_ids),
                "updated_articles": [],
                "missing_ids": [],
                "error_details": [{"id": "*", "error": str(e)}],
            }

        for entity_id in entity_ids:
            try:
                updated_entity = self.update(entity_id, entity_data.copy())

                success_count += 1
                if updated_entity:
                    updated_articles.append(updated_entity)
                else:
                    logger.debug("ID=%s 的更新完成，但無數據變更。", entity_id)

            except DatabaseOperationError as e:
                if f"找不到ID為{entity_id}的實體" in str(e):
                    missing_ids.append(entity_id)
                else:
                    logger.error(
                        "更新實體 ID=%s 時發生資料庫錯誤: %s", entity_id, str(e)
                    )
                    error_details.append({"id": entity_id, "error": str(e)})
            except ValidationError as e:
                logger.error("更新實體 ID=%s 時發生驗證錯誤: %s", entity_id, str(e))
                error_details.append({"id": entity_id, "error": str(e)})
            except Exception as e:
                logger.error(
                    "更新實體 ID=%s 時發生未預期錯誤: %s",
                    entity_id,
                    str(e),
                    exc_info=True,
                )
                error_details.append(
                    {"id": entity_id, "error": f"未預期錯誤: {str(e)}"}
                )
                continue

        fail_count = len(missing_ids) + len(error_details)

        return {
            "success_count": success_count,
            "fail_count": fail_count,
            "updated_articles": updated_articles,
            "missing_ids": missing_ids,
            "error_details": error_details,
        }

    def batch_mark_as_scraped(self, links: List[str]) -> Dict[str, Any]:
        """批量將文章連結標記為已爬取 (is_scraped=True, status=CONTENT_SCRAPED)"""
        success_count = 0
        fail_count = 0
        failed_links: List[str] = []
        processed_links = 0

        for link in links:
            processed_links += 1
            try:
                result = self.update_scrape_status(
                    link, is_scraped=True, status=ArticleScrapeStatus.CONTENT_SCRAPED
                )
                if result:
                    success_count += 1
                else:
                    # update_scrape_status 返回 False 表示連結未找到
                    logger.warning("嘗試標記為已爬取，但找不到連結: %s", link)
                    failed_links.append(link)
                    fail_count += 1
            except Exception as e:
                logger.error(
                    "批量標記連結 %s 時 update_scrape_status 拋出異常: %s", link, e
                )
                failed_links.append(link)
                fail_count += 1

        return {
            "success_count": success_count,
            "fail_count": fail_count,
            "failed_links": failed_links,
        }

    def get_paginated_by_filter(
        self,
        filter_dict: Dict[str, Any],
        page: int,
        per_page: int,
        sort_by: Optional[str] = None,
        sort_desc: bool = False,
    ) -> tuple[int, list]:
        """根據過濾條件獲取分頁資料 (使用 BaseRepository.find_paginated)"""
        if sort_by is None:
            sort_by = "published_at"
            sort_desc = True

        return self.find_paginated(
            filter_criteria=filter_dict,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_desc=sort_desc,
        )

    def delete_by_link(self, link: str) -> bool:
        """根據文章連結刪除"""
        if not link:
            raise ValueError("必須提供文章連結才能刪除")

        try:
            article = self.find_by_link(link)
            if not article:
                logger.warning("嘗試刪除但找不到文章，連結: %s", link)
                raise ValidationError(f"連結 '{link}' 不存在，無法刪除")
            # 調用基類的 delete 方法
            return self.delete(article.id)
        except IntegrityError as e:
            # 基類 delete 內部已處理
            logger.error("刪除連結 %s 時發生完整性約束錯誤: %s", link, e)
            raise
        except DatabaseOperationError as e:
            logger.error("刪除連結 %s 時發生資料庫操作錯誤: %s", link, e, exc_info=True)
            raise

    def count_unscraped_links(self, source: Optional[str] = None) -> int:
        """計算未爬取的連結數量 (is_scraped=False)"""

        def query_func():
            query = self.session.query(func.count(self.model_class.id)).filter(
                self.model_class.is_scraped
                == False  # pylint: disable=singleton-comparison
            )
            if source:
                if hasattr(self.model_class, "source"):
                    query = query.filter_by(source=source)
                else:
                    logger.warning(
                        "嘗試按 source 過濾，但模型 %s 沒有 'source' 欄位。",
                        self.model_class.__name__,
                    )
            result = query.scalar()
            return result if result is not None else 0

        return self.execute_query(query_func, err_msg="計算未爬取的連結數量時發生錯誤")

    def count_scraped_links(self, source: Optional[str] = None) -> int:
        """計算已爬取的連結數量 (is_scraped=True)"""
        return self.count_scraped_articles(source)

    def find_scraped_links(
        self,
        limit: Optional[int] = 100,
        source: Optional[str] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List[Articles], List[Dict[str, Any]]]:
        """查詢已爬取的連結 (is_scraped=True)，支援預覽"""
        filter_criteria: Dict[str, Any] = {"is_scraped": True}
        if source:
            if hasattr(self.model_class, "source"):
                filter_criteria["source"] = source
            else:
                logger.warning(
                    "嘗試按 source 過濾，但模型 %s 沒有 'source' 欄位。",
                    self.model_class.__name__,
                )

        sort_column = "updated_at" if hasattr(self.model_class, "updated_at") else "id"

        return self.find_by_filter(
            filter_criteria=filter_criteria,
            limit=limit,
            sort_by=sort_column,
            sort_desc=True,
            is_preview=is_preview,
            preview_fields=preview_fields,
        )

    def find_unscraped_links(
        self,
        limit: Optional[int] = 100,
        source: Optional[str] = None,
        order_by_status: bool = True,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List[Articles], List[Dict[str, Any]]]:
        """查詢未爬取的連結 (is_scraped=False)，可選按爬取狀態排序，支援預覽"""

        def query_func():
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
                    logger.warning(
                        "find_unscraped_links 預覽欄位無效: %s，返回完整物件。",
                        preview_fields,
                    )
                    local_is_preview = False

            query = self.session.query(*query_entities).filter(
                self.model_class.is_scraped
                == False  # pylint: disable=singleton-comparison
            )
            if source:
                if hasattr(self.model_class, "source"):
                    query = query.filter_by(source=source)
                else:
                    logger.warning(
                        "嘗試按 source 過濾，但模型 %s 沒有 'source' 欄位。",
                        self.model_class.__name__,
                    )

            if (
                order_by_status
                and hasattr(self.model_class, "scrape_status")
                and hasattr(self.model_class, "updated_at")
            ):
                query = query.order_by(
                    case(
                        (
                            self.model_class.scrape_status
                            == ArticleScrapeStatus.PENDING,
                            0,
                        ),
                        (
                            self.model_class.scrape_status
                            == ArticleScrapeStatus.LINK_SAVED,
                            1,
                        ),
                        (
                            self.model_class.scrape_status
                            == ArticleScrapeStatus.FAILED,
                            2,
                        ),
                        else_=3,
                    ).asc(),
                    self.model_class.updated_at.asc(),
                )
            elif hasattr(self.model_class, "updated_at"):
                query = query.order_by(self.model_class.updated_at.asc())

            if limit is not None and limit > 0:
                query = query.limit(limit)
            elif limit is not None and limit <= 0:
                logger.warning(
                    "查詢未爬取連結時提供了無效的 limit=%s，將忽略限制。", limit
                )

            raw_results = query.all()

            if local_is_preview and valid_preview_fields:
                return [dict(zip(valid_preview_fields, row)) for row in raw_results]
            else:
                return raw_results

        return self.execute_query(query_func, err_msg="查詢未爬取的連結時發生錯誤")

    def count_scraped_articles(self, source: Optional[str] = None) -> int:
        """計算已爬取的文章數量 (is_scraped=True)"""

        def query_func():
            query = self.session.query(func.count(self.model_class.id)).filter(
                self.model_class.is_scraped == True
            )
            if source:
                if hasattr(self.model_class, "source"):
                    query = query.filter_by(source=source)
                else:
                    logger.warning(
                        "嘗試按 source 過濾，但模型 %s 沒有 'source' 欄位。",
                        self.model_class.__name__,
                    )
            result = query.scalar()
            return result if result is not None else 0

        return self.execute_query(query_func, err_msg="計算已爬取的文章數量時發生錯誤")

    def find_articles_by_task_id(
        self,
        task_id: Optional[int],
        is_scraped: Optional[bool] = None,
        limit: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Union[List[Articles], List[Dict[str, Any]]]:
        """根據任務ID查詢相關的文章，支援預覽"""
        if task_id is not None and (not isinstance(task_id, int) or task_id <= 0):
            raise ValueError("task_id 必須是正整數或 None")

        def query_func():
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
                    logger.warning(
                        "find_articles_by_task_id 預覽欄位無效: %s，返回完整物件。",
                        preview_fields,
                    )
                    local_is_preview = False

            if not hasattr(self.model_class, "task_id"):
                raise AttributeError(
                    f"模型 {self.model_class.__name__} 沒有 'task_id' 欄位"
                )

            query = self.session.query(*query_entities).filter(
                self.model_class.task_id == task_id
            )

            if is_scraped is not None:
                is_scraped_bool = bool(is_scraped)
                if not hasattr(self.model_class, "is_scraped"):
                    logger.warning(
                        "嘗試按 is_scraped 過濾，但模型 %s 沒有 'is_scraped' 欄位。",
                        self.model_class.__name__,
                    )
                else:
                    query = query.filter(self.model_class.is_scraped == is_scraped_bool)

            if hasattr(self.model_class, "scrape_status") and hasattr(
                self.model_class, "updated_at"
            ):
                query = query.order_by(
                    case(
                        (
                            self.model_class.scrape_status
                            == ArticleScrapeStatus.PENDING,
                            0,
                        ),
                        (
                            self.model_class.scrape_status
                            == ArticleScrapeStatus.LINK_SAVED,
                            1,
                        ),
                        (
                            self.model_class.scrape_status
                            == ArticleScrapeStatus.FAILED,
                            2,
                        ),
                        (
                            self.model_class.scrape_status
                            == ArticleScrapeStatus.CONTENT_SCRAPED,
                            3,
                        ),
                        else_=4,
                    ).asc(),
                    self.model_class.updated_at.desc(),
                )
            elif hasattr(self.model_class, "updated_at"):
                query = query.order_by(self.model_class.updated_at.desc())

            if limit is not None:
                if isinstance(limit, int) and limit > 0:
                    query = query.limit(limit)
                else:
                    logger.warning(
                        "find_articles_by_task_id 提供了無效的 limit=%s，將忽略限制。",
                        limit,
                    )

            raw_results = query.all()

            if local_is_preview and valid_preview_fields:
                return [dict(zip(valid_preview_fields, row)) for row in raw_results]
            else:
                return raw_results

        return self.execute_query(
            query_func, err_msg=f"根據任務ID={task_id}查詢文章時發生錯誤"
        )

    def count_articles_by_task_id(
        self, task_id: int, is_scraped: Optional[bool] = None
    ) -> int:
        """計算特定任務的文章數量

        Args:
            task_id: 任務ID
            is_scraped: 可選過濾條件，是否已爬取內容

        Returns:
            符合條件的文章數量
        """
        if not isinstance(task_id, int) or task_id <= 0:
            raise ValueError("task_id 必須是正整數")

        def query_func():
            if not hasattr(self.model_class, "task_id"):
                raise AttributeError(
                    f"模型 {self.model_class.__name__} 沒有 'task_id' 欄位"
                )

            query = self.session.query(func.count(self.model_class.id)).filter(
                self.model_class.task_id == task_id
            )

            if is_scraped is not None:
                is_scraped_bool = bool(is_scraped)
                if not hasattr(self.model_class, "is_scraped"):
                    logger.warning(
                        "嘗試按 is_scraped 過濾，但模型 %s 沒有 'is_scraped' 欄位。",
                        self.model_class.__name__,
                    )
                else:
                    query = query.filter(self.model_class.is_scraped == is_scraped_bool)

            result = query.scalar()
            return result if result is not None else 0

        return self.execute_query(
            query_func, err_msg=f"計算任務ID={task_id}的文章數量時發生錯誤"
        )

    def _apply_filters(self, query, filter_criteria: Dict[str, Any]):
        """
        覆寫基類的過濾方法，以處理 ArticlesRepository 特有的過濾條件。
        """
        remaining_criteria = filter_criteria.copy()
        processed_query = query

        search_text = remaining_criteria.pop("search_text", None)
        tags_like = remaining_criteria.pop("tags", None)
        category_filter = remaining_criteria.pop("category", None)

        special_filter_value = remaining_criteria.pop("filter", None)
        if special_filter_value is not None:
            if special_filter_value == "ai":
                if hasattr(self.model_class, "is_ai_related"):
                    processed_query = processed_query.filter(
                        self.model_class.is_ai_related == True
                    )
                else:
                    logger.warning(
                        "嘗試按 'filter=ai' 過濾，但模型沒有 'is_ai_related' 欄位。"
                    )
            elif special_filter_value == "not-ai":
                if hasattr(self.model_class, "is_ai_related"):
                    processed_query = processed_query.filter(
                        self.model_class.is_ai_related == False
                    )
                else:
                    logger.warning(
                        "嘗試按 'filter=not-ai' 過濾，但模型沒有 'is_ai_related' 欄位。"
                    )
            elif special_filter_value == "today":
                if hasattr(self.model_class, "created_at"):
                    today_start = datetime.now().replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                    processed_query = processed_query.filter(
                        self.model_class.created_at >= today_start
                    )
                else:
                    logger.warning(
                        "嘗試按 'filter=today' 過濾，但模型沒有 'created_at' 欄位。"
                    )
            elif special_filter_value == "week":
                if hasattr(self.model_class, "created_at"):
                    today = datetime.now().date()
                    start_of_week = today - timedelta(days=today.weekday())
                    start_of_week_dt = datetime.combine(
                        start_of_week, datetime.min.time()
                    )
                    processed_query = processed_query.filter(
                        self.model_class.created_at >= start_of_week_dt
                    )
                else:
                    logger.warning(
                        "嘗試按 'filter=week' 過濾，但模型沒有 'created_at' 欄位。"
                    )
            elif special_filter_value == "month":
                if hasattr(self.model_class, "created_at"):
                    today = datetime.now().date()
                    start_of_month = today.replace(day=1)
                    start_of_month_dt = datetime.combine(
                        start_of_month, datetime.min.time()
                    )
                    processed_query = processed_query.filter(
                        self.model_class.created_at >= start_of_month_dt
                    )
                else:
                    logger.warning(
                        "嘗試按 'filter=month' 過濾，但模型沒有 'created_at' 欄位。"
                    )
            else:
                logger.warning(
                    "過濾條件 'filter' 的值 '%s' 無效，已忽略。接受的值為 'ai', 'not-ai', 'today', 'week', 'month'。",
                    special_filter_value,
                )

        if search_text and isinstance(search_text, str):
            search_term = f"%{search_text}%"
            processed_query = processed_query.filter(
                or_(
                    self.model_class.title.like(search_term),
                    self.model_class.content.like(search_term),
                    self.model_class.summary.like(search_term),
                )
            )

        if tags_like and isinstance(tags_like, str):
            processed_query = processed_query.filter(
                self.model_class.tags.like(f"%{tags_like}%")
            )

        if category_filter is not None:
            if hasattr(self.model_class, "category"):
                processed_query = processed_query.filter(
                    self.model_class.category == category_filter
                )
            else:
                logger.warning(
                    "嘗試按 category 過濾，但模型 %s 沒有 'category' 欄位。",
                    self.model_class.__name__,
                )

        # 調用基類的 _apply_filters 處理剩餘的標準條件
        return super()._apply_filters(processed_query, remaining_criteria)
