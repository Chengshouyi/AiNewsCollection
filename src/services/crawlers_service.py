"""此模組提供 CrawlersService 類別，用於處理爬蟲相關的業務邏輯。"""

import os
import re
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple, Type, cast, Union, Sequence

from sqlalchemy.orm.attributes import instance_state

from src.models.base_model import Base
from src.models.crawlers_model import Crawlers
from src.models.crawlers_schema import (
    CrawlersCreateSchema,
    CrawlersUpdateSchema,
    CrawlerReadSchema,
    PaginatedCrawlerResponse,
)
from src.database.crawlers_repository import CrawlersRepository
from src.database.base_repository import BaseRepository, SchemaType
from src.services.base_service import BaseService
from src.error.errors import InvalidOperationError
from src.utils.log_utils import LoggerSetup


logger = LoggerSetup.setup_logger(__name__)


class CrawlersService(BaseService[Crawlers]):
    """爬蟲服務，提供爬蟲相關業務邏輯"""

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    def _get_repository_mapping(
        self,
    ) -> Dict[str, Tuple[Type[BaseRepository], Type[Base]]]:
        """提供儲存庫映射"""
        return {"Crawler": (CrawlersRepository, Crawlers)}

    def validate_crawler_data(
        self, data: Dict[str, Any], is_update: bool = False
    ) -> Dict[str, Any]:
        """驗證爬蟲資料

        Args:
            data: 要驗證的資料
            is_update: 是否為更新操作

        Returns:
            Dict[str, Any]: 驗證後的資料
        """
        schema_type = SchemaType.UPDATE if is_update else SchemaType.CREATE
        return self.validate_data("Crawler", data, schema_type)

    def create_crawler(self, crawler_data: Dict[str, Any]) -> Dict[str, Any]:
        """創建新爬蟲設定

        Args:
            crawler_data: 要創建的爬蟲設定資料

        Returns:
            Dict[str, Any]: 創建結果
                success: 是否成功
                message: 訊息
                crawler: 爬蟲設定
        """
        try:
            with self._transaction() as session:
                # 添加必要的欄位
                now = datetime.now(timezone.utc)
                crawler_data.update({"created_at": now, "updated_at": now})

                # 使用 Pydantic 驗證資料
                try:
                    validated_data = CrawlersCreateSchema.model_validate(
                        crawler_data
                    ).model_dump()
                except Exception as e:
                    return {
                        "success": False,
                        "message": f"爬蟲設定資料驗證失敗: {str(e)}",
                        "crawler": None,
                    }

                crawler_repo = cast(
                    CrawlersRepository, self._get_repository("Crawler", session)
                )
                if not crawler_repo:
                    return {
                        "success": False,
                        "message": "無法取得資料庫存取器",
                        "crawler": None,
                    }
                result = crawler_repo.create(validated_data)

                if result and not instance_state(result).detached:
                    session.flush()
                    session.refresh(result)
                    crawler_schema = CrawlerReadSchema.model_validate(result)
                    return {
                        "success": True,
                        "message": "爬蟲設定創建成功",
                        "crawler": crawler_schema,
                    }
                else:
                    return {
                        "success": False,
                        "message": "創建爬蟲設定失敗",
                        "crawler": None,
                    }

        except Exception as e:
            logger.error("創建爬蟲設定失敗: %s", str(e))
            raise e

    def find_all_crawlers(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_desc: bool = False,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """獲取所有爬蟲設定"""
        try:
            with self._transaction() as session:
                crawler_repo = cast(
                    CrawlersRepository, self._get_repository("Crawler", session)
                )
                if not crawler_repo:
                    return {
                        "success": False,
                        "message": "無法取得資料庫存取器",
                        "crawlers": [],
                    }
                crawlers = crawler_repo.find_all(
                    limit=limit,
                    offset=offset,
                    sort_by=sort_by,
                    sort_desc=sort_desc,
                    is_preview=is_preview,
                    preview_fields=preview_fields,
                )

                # Prepare result based on is_preview
                crawlers_result: Sequence[Union[CrawlerReadSchema, Dict[str, Any]]] = []
                if crawlers:
                    if is_preview:
                        # Repository returns List[Dict[str, Any]] in preview mode
                        crawlers_result = cast(List[Dict[str, Any]], crawlers)
                    else:
                        # Repository returns List[Crawlers] when not in preview mode
                        crawlers_result = [
                            CrawlerReadSchema.model_validate(c)
                            for c in cast(List[Crawlers], crawlers)
                        ]

                return {
                    "success": True,
                    "message": "獲取爬蟲設定列表成功",
                    "crawlers": crawlers_result,
                }
        except Exception as e:
            logger.error("獲取所有爬蟲設定失敗: %s", str(e))
            raise e

    def get_crawler_by_id(self, crawler_id: int) -> Dict[str, Any]:
        """根據ID獲取爬蟲設定"""
        try:
            with self._transaction() as session:
                crawler_repo = cast(
                    CrawlersRepository, self._get_repository("Crawler", session)
                )
                if not crawler_repo:
                    return {
                        "success": False,
                        "message": "無法取得資料庫存取器",
                        "crawler": None,
                    }
                crawler = crawler_repo.get_by_id(crawler_id)

                if not crawler:
                    return {
                        "success": False,
                        "message": f"爬蟲設定不存在，ID={crawler_id}",
                        "crawler": None,
                    }

                crawler_schema = CrawlerReadSchema.model_validate(crawler)
                return {
                    "success": True,
                    "message": "獲取爬蟲設定成功",
                    "crawler": crawler_schema,
                }
        except Exception as e:
            logger.error("獲取爬蟲設定失敗，ID=%s: %s", crawler_id, str(e))
            raise e

    def update_crawler(
        self, crawler_id: int, crawler_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新爬蟲設定"""
        try:
            with self._transaction() as session:
                # 自動更新 updated_at 欄位
                crawler_data["updated_at"] = datetime.now(timezone.utc)

                # 使用 Pydantic 驗證資料
                try:

                    validated_data = self.validate_crawler_data(
                        crawler_data, is_update=True
                    )
                except Exception as e:
                    return {
                        "success": False,
                        "message": f"爬蟲設定更新資料驗證失敗: {str(e)}",
                        "crawler": None,
                    }

                crawler_repo = cast(
                    CrawlersRepository, self._get_repository("Crawler", session)
                )
                if not crawler_repo:
                    return {
                        "success": False,
                        "message": "無法取得資料庫存取器",
                        "crawler": None,
                    }

                # 檢查爬蟲是否存在
                original_crawler = crawler_repo.get_by_id(crawler_id)
                if not original_crawler:
                    return {
                        "success": False,
                        "message": f"爬蟲設定不存在，ID={crawler_id}",
                        "crawler": None,
                    }

                result = crawler_repo.update(crawler_id, validated_data)

                if result and not instance_state(result).detached:
                    session.flush()
                    session.refresh(result)
                    crawler_schema = CrawlerReadSchema.model_validate(result)
                    return {
                        "success": True,
                        "message": "爬蟲設定更新成功",
                        "crawler": crawler_schema,
                    }
                else:
                    logger.warning(
                        "更新爬蟲 ID=%s 時 repo.update 返回 None 或 False，可能無變更或更新失敗。",
                        crawler_id,
                    )
                    session.refresh(original_crawler)
                    crawler_schema = CrawlerReadSchema.model_validate(original_crawler)
                    return {
                        "success": True,
                        "message": f"爬蟲設定更新操作完成 (可能無實際變更), ID={crawler_id}",
                        "crawler": crawler_schema,
                    }

        except Exception as e:
            logger.error("更新爬蟲設定失敗，ID=%s: %s", crawler_id, str(e))
            raise e

    def delete_crawler(self, crawler_id: int) -> Dict[str, Any]:
        """刪除爬蟲設定"""
        try:
            with self._transaction() as session:
                crawler_repo = cast(
                    CrawlersRepository, self._get_repository("Crawler", session)
                )
                if not crawler_repo:
                    return {
                        "success": False,
                        "message": "無法取得資料庫存取器",
                    }
                result = crawler_repo.delete(crawler_id)

                if not result:
                    return {
                        "success": False,
                        "message": f"爬蟲設定不存在，ID={crawler_id}",
                    }

                return {"success": True, "message": "爬蟲設定刪除成功"}

        except Exception as e:
            logger.error("刪除爬蟲設定失敗，ID=%s: %s", crawler_id, str(e))
            raise e

    def find_active_crawlers(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """獲取所有活動中的爬蟲設定

        Args:
            limit: 限制數量
            offset: 偏移量
            is_preview: 是否啟用預覽模式，僅返回指定欄位
            preview_fields: 預覽模式下要返回的欄位列表

        Returns:
            Dict[str, Any]: 活動中的爬蟲設定
                success: 是否成功
                message: 訊息
                crawlers: 活動中的爬蟲設定列表 (完整 Schema 或預覽字典)
        """
        try:
            with self._transaction() as session:
                crawler_repo = cast(
                    CrawlersRepository, self._get_repository("Crawler", session)
                )
                if not crawler_repo:
                    return {
                        "success": False,
                        "message": "無法取得資料庫存取器",
                        "crawlers": [],
                    }

                # Pass is_preview and preview_fields to repository method
                crawlers = crawler_repo.find_active_crawlers(
                    limit=limit,
                    offset=offset,
                    is_preview=is_preview,
                    preview_fields=preview_fields,
                )

                # Prepare result based on is_preview
                crawlers_result: Sequence[Union[CrawlerReadSchema, Dict[str, Any]]] = []
                if crawlers:
                    if is_preview:
                        crawlers_result = cast(List[Dict[str, Any]], crawlers)
                    else:
                        crawlers_result = [
                            CrawlerReadSchema.model_validate(c)
                            for c in cast(List[Crawlers], crawlers)
                        ]

                if not crawlers_result:
                    return {
                        "success": True,  # Finding none is not a failure
                        "message": "找不到任何活動中的爬蟲設定",
                        "crawlers": [],
                    }
                return {
                    "success": True,
                    "message": "獲取活動中的爬蟲設定成功",
                    "crawlers": crawlers_result,
                }
        except Exception as e:
            logger.error("獲取活動中的爬蟲設定失敗: %s", str(e))
            raise e

    def toggle_crawler_status(self, crawler_id: int) -> Dict[str, Any]:
        """切換爬蟲活躍狀態"""
        try:
            with self._transaction() as session:
                crawler_repo = cast(
                    CrawlersRepository, self._get_repository("Crawler", session)
                )
                if not crawler_repo:
                    return {
                        "success": False,
                        "message": "無法取得資料庫存取器",
                        "crawler": None,
                    }

                # Fetch the crawler first
                crawler_to_toggle = crawler_repo.get_by_id(crawler_id)

                if not crawler_to_toggle:
                    return {
                        "success": False,
                        "message": f"爬蟲設定不存在，ID={crawler_id}",
                        "crawler": None,
                    }

                # Toggle status and update time
                new_status = not crawler_to_toggle.is_active
                crawler_to_toggle.is_active = new_status
                crawler_to_toggle.updated_at = datetime.now(timezone.utc)

                # Flush and refresh
                session.flush()
                session.refresh(crawler_to_toggle)

                crawler_schema = CrawlerReadSchema.model_validate(crawler_to_toggle)
                return {
                    "success": True,
                    "message": f"成功切換爬蟲狀態，新狀態={new_status}",
                    "crawler": crawler_schema,
                }

        except Exception as e:
            logger.error("切換爬蟲狀態失敗，ID=%s: %s", crawler_id, str(e))
            raise e

    def find_crawlers_by_name(
        self,
        name: str,
        is_active: Optional[bool] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """根據名稱模糊查詢爬蟲設定

        Args:
            name: 爬蟲名稱 (模糊匹配)
            is_active: 是否過濾活躍狀態 (None:不過濾, True:活躍, False:非活躍)
            limit: 限制數量
            offset: 偏移量
            is_preview: 是否啟用預覽模式，僅返回指定欄位
            preview_fields: 預覽模式下要返回的欄位列表

        Returns:
            Dict[str, Any]: 爬蟲設定列表
                success: 是否成功
                message: 訊息
                crawlers: 符合條件的爬蟲設定列表 (完整 Schema 或預覽字典)
        """
        try:
            with self._transaction() as session:
                crawler_repo = cast(
                    CrawlersRepository, self._get_repository("Crawler", session)
                )
                if not crawler_repo:
                    return {
                        "success": False,
                        "message": "無法取得資料庫存取器",
                        "crawlers": [],
                    }

                # Pass parameters including is_preview and preview_fields
                crawlers = crawler_repo.find_by_crawler_name(
                    name,
                    is_active=is_active,
                    limit=limit,
                    offset=offset,
                    is_preview=is_preview,
                    preview_fields=preview_fields,
                )

                # Prepare result based on is_preview
                crawlers_result: Sequence[Union[CrawlerReadSchema, Dict[str, Any]]] = []
                if crawlers:
                    if is_preview:
                        crawlers_result = cast(List[Dict[str, Any]], crawlers)
                    else:
                        crawlers_result = [
                            CrawlerReadSchema.model_validate(c)
                            for c in cast(List[Crawlers], crawlers)
                        ]

                if not crawlers_result:
                    return {
                        "success": True,  # Finding none is not a failure
                        "message": "找不到任何符合條件的爬蟲設定",
                        "crawlers": [],
                    }
                return {
                    "success": True,
                    "message": "獲取爬蟲設定列表成功",
                    "crawlers": crawlers_result,
                }
        except Exception as e:
            logger.error("獲取爬蟲設定列表失敗: %s", str(e))
            raise e

    def find_crawlers_by_type(
        self,
        crawler_type: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """根據爬蟲類型查找爬蟲

        Args:
            crawler_type: 爬蟲類型
            limit: 限制數量
            offset: 偏移量
            is_preview: 是否啟用預覽模式，僅返回指定欄位
            preview_fields: 預覽模式下要返回的欄位列表

        Returns:
            Dict[str, Any]: 爬蟲設定列表
                success: 是否成功
                message: 訊息
                crawlers: 符合條件的爬蟲設定列表 (完整 Schema 或預覽字典)
        """
        try:
            with self._transaction() as session:
                crawler_repo = cast(
                    CrawlersRepository, self._get_repository("Crawler", session)
                )
                if not crawler_repo:
                    return {
                        "success": False,
                        "message": "無法取得資料庫存取器",
                        "crawlers": [],
                    }

                # Pass parameters including is_preview and preview_fields
                crawlers = crawler_repo.find_by_type(
                    crawler_type,
                    limit=limit,
                    offset=offset,
                    is_preview=is_preview,
                    preview_fields=preview_fields,
                )

                # Prepare result based on is_preview
                crawlers_result: Sequence[Union[CrawlerReadSchema, Dict[str, Any]]] = []
                if crawlers:
                    if is_preview:
                        crawlers_result = cast(List[Dict[str, Any]], crawlers)
                    else:
                        crawlers_result = [
                            CrawlerReadSchema.model_validate(c)
                            for c in cast(List[Crawlers], crawlers)
                        ]

                if not crawlers_result:
                    return {
                        "success": True,  # Finding none is not a failure
                        "message": f"找不到類型為 {crawler_type} 的爬蟲設定",
                        "crawlers": [],
                    }
                return {
                    "success": True,
                    "message": f"獲取類型為 {crawler_type} 的爬蟲設定列表成功",
                    "crawlers": crawlers_result,
                }
        except Exception as e:
            logger.error("獲取類型為 %s 的爬蟲設定列表失敗: %s", crawler_type, str(e))
            raise e

    def find_crawlers_by_target(
        self,
        target_pattern: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """根據爬取目標模糊查詢爬蟲

        Args:
            target_pattern: 目標模式 (模糊匹配 base_url)
            limit: 限制數量
            offset: 偏移量
            is_preview: 是否啟用預覽模式，僅返回指定欄位
            preview_fields: 預覽模式下要返回的欄位列表

        Returns:
            Dict[str, Any]: 爬蟲設定列表
                success: 是否成功
                message: 訊息
                crawlers: 符合條件的爬蟲設定列表 (完整 Schema 或預覽字典)
        """
        try:
            with self._transaction() as session:
                crawler_repo = cast(
                    CrawlersRepository, self._get_repository("Crawler", session)
                )
                if not crawler_repo:
                    return {
                        "success": False,
                        "message": "無法取得資料庫存取器",
                        "crawlers": [],
                    }

                # Pass parameters including is_preview and preview_fields
                crawlers = crawler_repo.find_by_target(
                    target_pattern,
                    limit=limit,
                    offset=offset,
                    is_preview=is_preview,
                    preview_fields=preview_fields,
                )

                # Prepare result based on is_preview
                crawlers_result: Sequence[Union[CrawlerReadSchema, Dict[str, Any]]] = []
                if crawlers:
                    if is_preview:
                        crawlers_result = cast(List[Dict[str, Any]], crawlers)
                    else:
                        crawlers_result = [
                            CrawlerReadSchema.model_validate(c)
                            for c in cast(List[Crawlers], crawlers)
                        ]

                if not crawlers_result:
                    return {
                        "success": True,  # Finding none is not a failure
                        "message": f"找不到目標包含 {target_pattern} 的爬蟲設定",
                        "crawlers": [],
                    }
                return {
                    "success": True,
                    "message": f"獲取目標包含 {target_pattern} 的爬蟲設定列表成功",
                    "crawlers": crawlers_result,
                }
        except Exception as e:
            logger.error(
                "獲取目標包含 %s 的爬蟲設定列表失敗: %s", target_pattern, str(e)
            )
            raise e

    def get_crawler_statistics(self) -> Dict[str, Any]:
        """獲取爬蟲統計信息"""
        try:
            with self._transaction() as session:
                crawler_repo = cast(
                    CrawlersRepository, self._get_repository("Crawler", session)
                )
                if not crawler_repo:
                    return {
                        "success": False,
                        "message": "無法取得資料庫存取器",
                        "statistics": None,
                    }
                statistics = crawler_repo.get_crawler_statistics()
                return {
                    "success": True,
                    "message": "獲取爬蟲統計信息成功",
                    "statistics": statistics,
                }
        except Exception as e:
            logger.error("獲取爬蟲統計信息失敗: %s", str(e))
            raise e

    def get_crawler_by_exact_name(
        self,
        crawler_name: str,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """根據爬蟲名稱精確查詢

        Args:
            crawler_name: 爬蟲名稱 (精確匹配)
            is_preview: 是否啟用預覽模式，僅返回指定欄位
            preview_fields: 預覽模式下要返回的欄位列表

        Returns:
            Dict[str, Any]: 單個爬蟲設定
                success: 是否成功
                message: 訊息
                crawler: 符合條件的爬蟲設定 (完整 Schema 或預覽字典) 或 None
        """
        try:
            with self._transaction() as session:
                crawler_repo = cast(
                    CrawlersRepository, self._get_repository("Crawler", session)
                )
                if not crawler_repo:
                    return {
                        "success": False,
                        "message": "無法取得資料庫存取器",
                        "crawler": None,
                    }

                # Pass parameters including is_preview and preview_fields
                crawler = crawler_repo.find_by_crawler_name_exact(
                    crawler_name, is_preview=is_preview, preview_fields=preview_fields
                )

                # Prepare result based on is_preview
                crawler_result: Optional[Union[CrawlerReadSchema, Dict[str, Any]]] = (
                    None
                )
                if crawler:
                    if is_preview:
                        # Repository returns Dict[str, Any] in preview mode
                        if isinstance(crawler, dict):
                            crawler_result = crawler
                        else:
                            # This case shouldn't happen based on repo logic, but handle defensively
                            logger.warning(
                                "Preview mode expected Dict but got %s for %s",
                                type(crawler),
                                crawler_name,
                            )
                            # Decide fallback: return None or try to convert? Let's return None for now.
                            pass  # crawler_result remains None
                    else:
                        # Repository returns Crawlers when not in preview mode
                        # Ensure crawler is Crawlers before validating
                        if isinstance(crawler, Crawlers):
                            crawler_result = CrawlerReadSchema.model_validate(
                                crawler
                            )  # Convert to Schema
                        else:
                            # This case shouldn't happen, handle defensively
                            logger.warning(
                                "Non-preview mode expected Crawlers but got %s for %s",
                                type(crawler),
                                crawler_name,
                            )
                            pass  # crawler_result remains None

                if not crawler_result:
                    return {
                        "success": False,  # Changed to False as exact match failed
                        "message": f"找不到名稱為 {crawler_name} 的爬蟲設定",
                        "crawler": None,
                    }
                return {
                    "success": True,
                    "message": "獲取爬蟲設定成功",
                    "crawler": crawler_result,
                }
        except Exception as e:
            logger.error("獲取名稱為 %s 的爬蟲設定失敗: %s", crawler_name, str(e))
            raise e

    def create_or_update_crawler(self, crawler_data: Dict[str, Any]) -> Dict[str, Any]:
        """創建或更新爬蟲設定

        如果提供 ID 則更新現有爬蟲，否則創建新爬蟲
        """
        try:
            with self._transaction() as session:
                # 添加時間戳
                now = datetime.now(timezone.utc)
                crawler_copy = crawler_data.copy()  # 複製資料，避免直接修改原始資料

                logger.info("開始處理 create_or_update_crawler: %s", crawler_copy)

                # 確保資料中有建立或更新時間欄位
                if "id" not in crawler_copy or not crawler_copy["id"]:
                    # 創建時添加 created_at
                    crawler_copy["created_at"] = now

                # 更新時間總是添加
                crawler_copy["updated_at"] = now

                # 驗證資料
                try:
                    is_update = "id" in crawler_copy and crawler_copy["id"]
                    logger.info("操作類型: %s", "更新" if is_update else "創建")

                    if is_update:
                        # 驗證 ID 是否存在
                        crawler_repo = cast(
                            CrawlersRepository, self._get_repository("Crawler", session)
                        )
                        if not crawler_repo:
                            logger.error("無法取得資料庫存取器")
                            return {
                                "success": False,
                                "message": "無法取得資料庫存取器",
                                "crawler": None,
                            }

                        logger.info("正在檢查爬蟲 ID: %s", crawler_copy["id"])
                        existing_crawler = crawler_repo.get_by_id(crawler_copy["id"])
                        if not existing_crawler:
                            logger.error("爬蟲設定不存在，ID=%s", crawler_copy["id"])
                            return {
                                "success": False,
                                "message": f"爬蟲設定不存在，ID={crawler_copy['id']}",
                                "crawler": None,
                            }

                        # 更新模式：使用 update 方法直接更新，因為 create_or_update 移除 ID 後可能導致問題
                        crawler_id = crawler_copy.pop("id")
                        logger.info(
                            "準備更新爬蟲，ID=%s，資料: %s", crawler_id, crawler_copy
                        )

                        try:
                            validated_data = CrawlersUpdateSchema.model_validate(
                                crawler_copy
                            ).model_dump()
                            logger.info("已驗證的更新資料: %s", validated_data)
                        except Exception as validation_error:
                            logger.error("更新資料驗證失敗: %s", validation_error)
                            return {
                                "success": False,
                                "message": f"爬蟲設定更新資料驗證失敗: {str(validation_error)}",
                                "crawler": None,
                            }

                        try:
                            result = crawler_repo.update(crawler_id, validated_data)
                            logger.info("更新結果: %s", result)
                            if result and not instance_state(result).detached:
                                session.flush()
                                session.refresh(result)
                        except Exception as update_error:
                            logger.error("更新操作執行失敗: %s", update_error)
                            return {
                                "success": False,
                                "message": f"爬蟲設定更新操作失敗: {str(update_error)}",
                                "crawler": None,
                            }

                        operation = "更新"
                    else:
                        # 創建模式：使用 create 方法
                        logger.info("準備創建爬蟲，資料: %s", crawler_copy)

                        try:
                            validated_data = CrawlersCreateSchema.model_validate(
                                crawler_copy
                            ).model_dump()
                            logger.info("已驗證的創建資料: %s", validated_data)
                        except Exception as validation_error:
                            logger.error("創建資料驗證失敗: %s", validation_error)
                            return {
                                "success": False,
                                "message": f"爬蟲設定創建資料驗證失敗: {str(validation_error)}",
                                "crawler": None,
                            }

                        crawler_repo = cast(
                            CrawlersRepository, self._get_repository("Crawler", session)
                        )
                        if not crawler_repo:
                            logger.error("無法取得資料庫存取器")
                            return {
                                "success": False,
                                "message": "無法取得資料庫存取器",
                                "crawler": None,
                            }

                        try:
                            result = crawler_repo.create(validated_data)
                            logger.info("創建結果: %s", result)
                            if result and not instance_state(result).detached:
                                session.flush()
                                session.refresh(result)
                        except Exception as create_error:
                            logger.error("創建操作執行失敗: %s", create_error)
                            return {
                                "success": False,
                                "message": f"爬蟲設定創建操作失敗: {str(create_error)}",
                                "crawler": None,
                            }

                        operation = "創建"

                except Exception as e:
                    logger.error("處理過程中發生未預期錯誤: %s", e)
                    return {
                        "success": False,
                        "message": f"爬蟲設定資料驗證失敗: {str(e)}",
                        "crawler": None,
                    }

                if not result:
                    logger.error("爬蟲設定%s失敗，未返回結果", operation)
                    return {
                        "success": False,
                        "message": f"爬蟲設定{operation}失敗",
                        "crawler": None,
                    }

                crawler_schema = CrawlerReadSchema.model_validate(result)
                logger.info("爬蟲設定%s成功: %s", operation, crawler_schema)
                return {
                    "success": True,
                    "message": f"爬蟲設定{operation}成功",
                    "crawler": crawler_schema,
                }
        except Exception as e:
            logger.error("創建或更新爬蟲設定失敗: %s", str(e))
            return {
                "success": False,
                "message": f"創建或更新爬蟲設定時發生錯誤: {str(e)}",
                "crawler": None,
            }

    def batch_toggle_crawler_status(
        self, crawler_ids: List[int], active_status: bool
    ) -> Dict[str, Any]:
        """批量設置爬蟲的活躍狀態"""
        try:
            with self._transaction() as session:
                crawler_repo = cast(
                    CrawlersRepository, self._get_repository("Crawler", session)
                )
                if not crawler_repo:
                    return {
                        "success": False,
                        "message": "無法取得資料庫存取器",
                        "result": None,
                    }

                result = crawler_repo.batch_toggle_active(crawler_ids, active_status)

                action = "啟用" if active_status else "停用"
                if result["success_count"] > 0:
                    return {
                        "success": True,
                        "message": f"批量{action}爬蟲設定完成，成功: {result['success_count']}，失敗: {result['fail_count']}",
                        "result": result,
                    }
                else:
                    return {
                        "success": False,
                        "message": f"批量{action}爬蟲設定失敗，所有操作均未成功",
                        "result": result,
                    }
        except Exception as e:
            logger.error("批量切換爬蟲狀態失敗: %s", str(e))
            raise e

    def find_filtered_crawlers(
        self,
        filter_criteria: Dict[str, Any],
        page: int = 1,
        per_page: int = 10,
        sort_by: Optional[str] = None,
        sort_desc: bool = False,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """根據過濾條件獲取分頁爬蟲列表，支援預覽模式"""
        try:
            with self._transaction() as session:
                crawler_repo = cast(
                    CrawlersRepository, self._get_repository("Crawler", session)
                )
                if not crawler_repo:
                    return {
                        "success": False,
                        "message": "無法取得資料庫存取器",
                        "data": None,
                    }

                # 使用 Repository 的 find_paginated 方法
                repo_result = crawler_repo.find_paginated(
                    filter_criteria=filter_criteria,
                    page=page,
                    per_page=per_page,
                    sort_by=sort_by,
                    sort_desc=sort_desc,
                    is_preview=is_preview,
                    preview_fields=preview_fields,
                )

                # repo_result 現在是 (total_count, items) 元組
                total_count, items = repo_result

                # 創建 PaginatedCrawlerResponse 實例
                # 需要手動計算分頁資訊
                total_pages = (
                    (total_count + per_page - 1) // per_page if per_page > 0 else 0
                )
                has_next = page < total_pages
                has_prev = page > 1

                try:
                    paginated_response = PaginatedCrawlerResponse(
                        items=items,  # 直接使用解包後的 items
                        page=page,  # 使用傳入的 page
                        per_page=per_page,  # 使用傳入的 per_page
                        total=total_count,  # 使用解包後的 total_count
                        total_pages=total_pages,
                        has_next=has_next,
                        has_prev=has_prev,
                    )
                except Exception as pydantic_error:
                    logger.error(
                        "創建 PaginatedCrawlerResponse 時出錯: %s",
                        pydantic_error,
                        exc_info=True,
                    )
                    # 返回標準錯誤結構
                    return {
                        "success": False,
                        "message": f"分頁結果格式錯誤: {pydantic_error}",
                        "data": None,
                    }

                # 檢查是否有數據並設置消息
                if not paginated_response.items:
                    message = "找不到符合條件的爬蟲設定"
                    success_status = True  # 按照之前的邏輯，空列表也算成功
                else:
                    message = "獲取爬蟲設定列表成功"
                    success_status = True

                return {
                    "success": success_status,
                    "message": message,
                    "data": paginated_response,  # 返回 Schema 實例
                }
        except InvalidOperationError as e:  # 捕獲 repo 可能拋出的分頁/排序錯誤
            logger.error("獲取過濾後的分頁爬蟲設定列表失敗 (參數錯誤): %s", str(e))
            return {"success": False, "message": str(e), "data": None}
        except Exception as e:
            logger.error("獲取過濾後的分頁爬蟲設定列表失敗: %s", str(e))
            # 直接返回標準錯誤結構，避免拋出未處理的異常
            return {
                "success": False,
                "message": f"處理請求時發生錯誤: {str(e)}",
                "data": None,
            }

    def get_crawler_config(self, crawler_id: int) -> Dict[str, Any]:
        """獲取爬蟲的配置檔案內容，優先從環境變數指定路徑讀取

        Args:
            crawler_id: 爬蟲ID

        Returns:
            Dict[str, Any]: 配置檔案內容
                success: 是否成功
                message: 訊息
                config: 配置檔案內容 (字典) 或 None
        """
        try:
            with self._transaction() as session:
                crawler_repo = cast(
                    CrawlersRepository, self._get_repository("Crawler", session)
                )
                if not crawler_repo:
                    logger.error("無法取得資料庫存取器")
                    return {
                        "success": False,
                        "message": "無法取得資料庫存取器",
                        "config": None,
                    }

                crawler = crawler_repo.get_by_id(crawler_id)
                if not crawler:
                    logger.warning("爬蟲設定不存在，ID=%s", crawler_id)
                    return {
                        "success": False,
                        "message": f"爬蟲設定不存在，ID={crawler_id}",
                        "config": None,
                    }
                
                if not crawler.config_file_name:
                     logger.warning("爬蟲 ID=%s 沒有配置檔案名稱。", crawler_id)
                     return {
                         "success": False,
                         "message": f"爬蟲 ID={crawler_id} 未設定配置檔案名稱。",
                         "config": None
                     }

                config_filename = crawler.config_file_name
                logger.debug("準備獲取爬蟲 ID=%s 的配置檔案: %s", crawler_id, config_filename)

                # 1. 確定主要配置目錄 (優先使用環境變數)
                #    預設值應與 update_crawler_config 和 Docker 設定一致
                default_config_dir = "/app/data/web_site_configs"
                config_dir = os.getenv('WEB_SITE_CONFIG_DIR', default_config_dir)
                primary_config_path = os.path.join(config_dir, config_filename)
                logger.debug("主要配置檔案路徑檢查: %s (來自目錄: %s)", primary_config_path, config_dir)

                # 2. 確定後備配置目錄 (專案內預設)
                #    假設服務運行在 /app 工作目錄下
                fallback_config_dir = "/app/src/crawlers/configs"
                fallback_config_path = os.path.join(fallback_config_dir, config_filename)
                logger.debug("後備配置檔案路徑檢查: %s", fallback_config_path)

                # --- 添加詳細日誌以進行除錯 ---
                env_var_value = os.getenv('WEB_SITE_CONFIG_DIR')
                logger.debug(f"[DEBUG] 環境變數 WEB_SITE_CONFIG_DIR: {env_var_value}")
                logger.debug(f"[DEBUG] 檢查主要路徑: {primary_config_path}")
                primary_exists = os.path.exists(primary_config_path)
                logger.debug(f"[DEBUG] 主要路徑 os.path.exists 結果: {primary_exists}")
                logger.debug(f"[DEBUG] 檢查後備路徑: {fallback_config_path}")
                fallback_exists = os.path.exists(fallback_config_path)
                logger.debug(f"[DEBUG] 後備路徑 os.path.exists 結果: {fallback_exists}")
                # --- 日誌結束 ---

                # 3. 檢查路徑並確定最終使用的路徑
                final_config_path = None
                if primary_exists:
                    final_config_path = primary_config_path
                    logger.info("找到配置檔案於主要路徑: %s", final_config_path)
                elif fallback_exists:
                    final_config_path = fallback_config_path
                    logger.warning(
                        "在主要路徑 %s 未找到配置檔案，使用後備路徑: %s",
                        primary_config_path, final_config_path
                    )
                else:
                    logger.error(
                        "在主要路徑 (%s) 和後備路徑 (%s) 都找不到配置檔案: %s",
                        primary_config_path, fallback_config_path, config_filename
                    )
                    return {
                        "success": False,
                        "message": f"配置檔案不存在：{config_filename} (檢查路徑 {config_dir} 和 {fallback_config_dir})",
                        "config": None,
                    }

                # 4. 讀取並解析找到的配置檔案
                try:
                    with open(final_config_path, "r", encoding="utf-8") as f:
                        config_content = f.read()
                        logger.debug("讀取到的原始配置內容 (來自 %s): %s", final_config_path, config_content[:200] + "...") # 限制日誌輸出長度
                        try:
                            config_data = json.loads(config_content)
                            logger.info("成功解析配置檔案內容: %s", final_config_path)
                            return {
                                "success": True,
                                "message": "獲取配置檔案成功",
                                "config": config_data, # 返回解析後的字典
                            }
                        except json.JSONDecodeError as je:
                            logger.error("配置檔案 JSON 解析錯誤 (%s): %s", final_config_path, str(je))
                            return {
                                "success": False,
                                "message": f"配置檔案格式錯誤 ({config_filename}): {str(je)}",
                                "config": None,
                            }
                except Exception as e:
                    logger.error("讀取配置檔案失敗 (%s): %s", final_config_path, str(e), exc_info=True)
                    return {
                        "success": False,
                        "message": f"讀取配置檔案失敗 ({config_filename}): {str(e)}",
                        "config": None,
                    }

        except Exception as e:
            logger.error("獲取爬蟲配置檔案時發生未預期錯誤，ID=%s: %s", crawler_id, str(e), exc_info=True)
            # 避免向上拋出未處理的異常
            return {
                "success": False,
                "message": f"處理請求時發生內部錯誤: {str(e)}",
                "config": None
            }

    def _clean_filename(self, filename: str) -> str:
        """清理檔案名稱，移除路徑並限制允許的字符。

        Args:
            filename: 原始檔案名稱

        Returns:
            清理後的安全檔案名稱
        """
        if not filename:
            return ""

        # 1. 移除路徑部分，只保留檔名
        base_name = os.path.basename(filename)

        # 2. 移除或替換不安全的字符
        #    允許：字母 (a-z, A-Z), 數字 (0-9), 底線 (_), 連字號 (-), 點 (.)
        #    其他所有字符將被移除
        #    注意：點 (.) 只應出現在副檔名前，這裡簡單允許，
        #    更嚴格的可以只允許最後一個點之前的非點字符。
        safe_name = re.sub(r'[^\w.-]', '', base_name)

        # 3. 避免檔名以點或連字號開頭 (有些系統不允許)
        if safe_name.startswith('.') or safe_name.startswith('-'):
            safe_name = '_' + safe_name[1:]
            
        # 4. 確保檔名不為空，如果清理後變空，提供一個預設名稱
        if not safe_name:
             # 可以根據需要生成更唯一的預設名稱，例如加上時間戳
             safe_name = "default_config.json" 
             
        # 5. (可選) 限制檔名長度
        max_len = 200 # 示例最大長度
        if len(safe_name) > max_len:
            name_part, ext_part = os.path.splitext(safe_name)
            allowed_name_len = max_len - len(ext_part)
            safe_name = name_part[:allowed_name_len] + ext_part


        logger.debug("原始檔名: '%s', 清理後檔名: '%s'", filename, safe_name)
        return safe_name

    def validate_config_file(self, config_data: Dict[str, Any]) -> bool:
        """驗證配置檔案格式

        Args:
            config_data: 配置檔案內容

        Returns:
            bool: 是否驗證通過
        """
        required_fields = [
            "name",
            "base_url",
            "list_url_template",
            "categories",
            "selectors",
        ]
        # 檢查頂層必要欄位
        for field in required_fields:
            if field not in config_data:
                logger.error("配置檔案缺少必要欄位: %s", field)
                return False
        
        # 驗證 name 是否為非空字串
        name_value = config_data.get("name")
        if not isinstance(name_value, str) or not name_value.strip():
            logger.error("配置檔案中的 'name' 必須是有效的非空字串")
            return False

        # 驗證 base_url 是否為非空字串
        base_url_value = config_data.get("base_url")
        if not isinstance(base_url_value, str) or not base_url_value.strip():
             logger.error("配置檔案中的 'base_url' 必須是有效的非空字串")
             return False
             
        # 驗證 list_url_template 是否為非空字串
        list_url_template_value = config_data.get("list_url_template")
        if not isinstance(list_url_template_value, str) or not list_url_template_value.strip():
             logger.error("配置檔案中的 'list_url_template' 必須是有效的非空字串")
             return False

        # --- 修改：驗證 categories 是否為非空列表 ---
        categories_value = config_data.get("categories")
        if not isinstance(categories_value, list) or not categories_value:
             logger.error("配置檔案中的 'categories' 必須是有效的非空列表")
             return False
        # --- 修改結束 ---

        # 驗證 selectors 結構
        selectors = config_data.get("selectors", {})
        if not isinstance(selectors, dict):
            logger.error("selectors 必須是字典類型")
            return False

        required_selectors = ["get_article_links", "get_article_contents"]
        for selector_key in required_selectors:
            if selector_key not in selectors:
                logger.error("selectors 缺少必要選擇器: %s", selector_key)
                return False
            # 檢查每個選擇器配置是否為字典
            if not isinstance(selectors[selector_key], dict):
                 logger.error("選擇器 '%s' 的配置必須是字典類型", selector_key)
                 return False

        # 可以添加更多針對 selectors 內部結構的驗證，例如檢查 type, selector 等欄位
        # ...

        logger.debug("配置檔案基本格式驗證通過")
        return True

    def update_crawler_config(
        self, crawler_id: int, config_file, crawler_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新爬蟲的配置檔案，根據 crawler_name 安全命名並儲存到 WEB_SITE_CONFIG_DIR 指定路徑"""
        try:
            with self._transaction() as session:
                crawler_repo = cast(
                    CrawlersRepository, self._get_repository("Crawler", session)
                )
                if not crawler_repo:
                    return { "success": False, "message": "無法取得資料庫存取器", "crawler": None }

                # 1. 檢查爬蟲是否存在
                crawler = crawler_repo.get_by_id(crawler_id)
                if not crawler:
                    return { "success": False, "message": f"爬蟲設定不存在，ID={crawler_id}", "crawler": None }
                
                # --- 新增：檢查 crawler_name 是否存在 ---
                if not crawler.crawler_name:
                     logger.error("爬蟲 ID=%s 的 crawler_name 為空，無法生成檔名。", crawler_id)
                     return { "success": False, "message": "無法生成配置檔名，爬蟲名稱為空。", "crawler": None }

                # 2. 處理上傳的配置檔案
                if not config_file: # 簡化檢查，主要檢查物件是否存在
                     return { "success": False, "message": "未提供有效的配置檔案", "crawler": None }

                # --- 修改：基於 crawler_name 生成檔名 ---
                # 構建基礎檔名，例如 "數位時代爬蟲.json"
                base_filename = f"{crawler.crawler_name}.json"
                # 清理這個構建出來的檔名
                safe_filename = self._clean_filename(base_filename)

                if not safe_filename:
                    logger.error("根據 crawler_name '%s' 無法生成有效的安全檔名。", crawler.crawler_name)
                    return { "success": False, "message": "無法根據爬蟲名稱生成有效的安全檔名。", "crawler": None }

                # 可以在這裡對生成的檔名進行擴展名檢查（如果需要）
                allowed_extensions = {'.json'}
                _, ext = os.path.splitext(safe_filename)
                if ext.lower() not in allowed_extensions:
                     logger.error("生成的檔名 '%s' 副檔名不合法。", safe_filename)
                     # 這種情況理論上不應該發生，因為我們強制加了 .json
                     return { "success": False, "message": f"生成的檔名副檔名不合法: '{ext}'", "crawler": None }

                # 3. 保存配置檔案
                try:
                    # 讀取並驗證上傳的內容
                    config_content = config_file.read()
                    config_file.seek(0)
                    try:
                        config_data = json.loads(config_content)
                    except json.JSONDecodeError as je:
                        logger.error("上傳的配置檔案 JSON 解析錯誤: %s", je)
                        return { "success": False, "message": f"上傳的配置檔案不是有效的 JSON 格式: {je}", "crawler": None }
                    except Exception as e:
                         logger.error("讀取或解析上傳的配置檔案時發生錯誤: %s", e)
                         return { "success": False, "message": f"處理上傳的配置檔案時出錯: {e}", "crawler": None }

                    # 驗證 JSON 內容格式
                    if not self.validate_config_file(config_data):
                        return { "success": False, "message": "上傳的配置檔案格式或內容不正確。", "crawler": None }

                    # 可選：檢查內容中的 name 是否與 crawler.crawler_name 匹配
                    if config_data.get("name") != crawler.crawler_name:
                        logger.warning(
                            "配置檔案內容中的 name '%s' 與爬蟲名稱 '%s' 不符，但仍將保存。建議保持一致。",
                             config_data.get("name"), crawler.crawler_name
                        )

                    # 獲取目標儲存目錄
                    default_config_dir = "/app/data/web_site_configs"
                    config_dir = os.getenv('WEB_SITE_CONFIG_DIR', default_config_dir)
                    try:
                        os.makedirs(config_dir, exist_ok=True)
                        logger.info("確保配置目錄存在: %s", config_dir)
                    except OSError as e:
                        logger.error("創建配置目錄 %s 失敗: %s", config_dir, e)
                        return { "success": False, "message": f"無法創建配置目錄: {e}", "crawler": None }

                    # 使用新生成的安全檔名保存
                    config_path = os.path.join(config_dir, safe_filename)
                    logger.info("準備將配置檔案寫入: %s", config_path)
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(config_data, f, indent=4, ensure_ascii=False)
                    logger.info("配置檔案已成功儲存到: %s", config_path)

                    # 4. 更新爬蟲資料庫記錄
                    crawler_data_update = crawler_data.copy()
                    crawler_data_update["config_file_name"] = safe_filename # <<< 更新為新的檔名
                    crawler_data_update["updated_at"] = datetime.now(timezone.utc)

                    if 'id' in crawler_data_update: del crawler_data_update['id']

                    try:
                         validated_data = CrawlersUpdateSchema.model_validate(crawler_data_update).model_dump(exclude_unset=True)
                    except Exception as validation_error:
                        logger.error("更新爬蟲資料驗證失敗: %s", validation_error)
                        # 考慮回滾已保存的檔案
                        try:
                            if os.path.exists(config_path): os.remove(config_path)
                            logger.warning("因資料庫更新驗證失敗，已回滾（刪除）剛保存的檔案: %s", config_path)
                        except Exception as rollback_error:
                            logger.error("回滾（刪除）檔案 %s 失敗: %s", config_path, rollback_error)
                        return { "success": False, "message": f"爬蟲設定更新資料驗證失敗: {validation_error}", "crawler": None }

                    logger.debug("準備更新資料庫，ID=%s, 數據=%s", crawler_id, validated_data)
                    result = crawler_repo.update(crawler_id, validated_data)

                    if result and not instance_state(result).detached:
                        session.flush()
                        session.refresh(result)
                        crawler_schema = CrawlerReadSchema.model_validate(result)
                        logger.info("爬蟲設定和配置檔案更新成功，ID=%s，新檔名: %s", crawler_id, safe_filename)
                        return { "success": True, "message": "爬蟲設定和配置檔案更新成功", "crawler": crawler_schema }
                    else:
                        logger.warning("更新爬蟲設定失敗或無變更，ID=%s", crawler_id)
                        # 考慮回滾
                        try:
                            if os.path.exists(config_path): os.remove(config_path)
                            logger.warning("因資料庫更新失敗或無變更，已回滾（刪除）剛保存的檔案: %s", config_path)
                        except Exception as rollback_error:
                            logger.error("回滾（刪除）檔案 %s 失敗: %s", config_path, rollback_error)
                        return { "success": False, "message": "更新爬蟲設定失敗或無變更", "crawler": None }

                except Exception as e:
                    logger.error("處理或保存配置檔案時發生錯誤: %s", str(e), exc_info=True)
                    # 如果在這一步出錯，檔案可能未成功寫入或部分寫入，不需要顯式回滾
                    return { "success": False, "message": f"處理或保存配置檔案時發生錯誤: {str(e)}", "crawler": None }

        except Exception as e:
            logger.error("更新爬蟲配置檔案的整體操作失敗，ID=%s: %s", crawler_id, str(e), exc_info=True)
            return { "success": False, "message": f"更新爬蟲配置時發生未預期錯誤: {str(e)}", "crawler": None }

    def create_crawler_with_config(
        self, crawler_data: Dict[str, Any], config_file
    ) -> Dict[str, Any]:
        """
        創建新爬蟲設定並處理其配置檔案，確保操作的原子性。
        如果配置檔案處理失敗，則整個創建操作將回滾。
        """
        saved_config_path: Optional[str] = None # 用於記錄已保存檔案的路徑，以便失敗時回滾

        try:
            with self._transaction() as session:
                crawler_repo = cast(
                    CrawlersRepository, self._get_repository("Crawler", session)
                )
                if not crawler_repo:
                    return { "success": False, "message": "無法取得資料庫存取器", "crawler": None }

                # --- 1. 驗證爬蟲基本資料 ---
                now = datetime.now(timezone.utc)
                crawler_data.update({"created_at": now, "updated_at": now})
                try:
                    # 初始驗證，檔名可能稍後生成
                    temp_validated_data = CrawlersCreateSchema.model_validate(
                        crawler_data
                    ).model_dump()
                    crawler_name = temp_validated_data.get("crawler_name")
                    if not crawler_name:
                         # Schema 應該會捕捉到，但再次確認
                         raise ValueError("爬蟲名稱 (crawler_name) 不得為空。")
                except Exception as e:
                    logger.error("爬蟲基本資料驗證失敗: %s", e)
                    return { "success": False, "message": f"爬蟲基本資料驗證失敗: {str(e)}", "crawler": None }

                # --- 2. 處理和驗證配置檔案 ---
                if not config_file:
                    return { "success": False, "message": "未提供配置檔案", "crawler": None }

                try:
                    config_content = config_file.read()
                    config_file.seek(0) # 重設指針以備後用 (如果需要)
                    config_data_from_file = json.loads(config_content)
                except json.JSONDecodeError as je:
                    logger.error("上傳的配置檔案 JSON 解析錯誤: %s", je)
                    return { "success": False, "message": f"配置檔案不是有效的 JSON 格式: {je}", "crawler": None }
                except Exception as e:
                     logger.error("讀取或解析配置檔案時發生錯誤: %s", e)
                     return { "success": False, "message": f"讀取配置檔案時出錯: {e}", "crawler": None }

                # 驗證檔案內容格式
                if not self.validate_config_file(config_data_from_file):
                    # validate_config_file 內部會記錄詳細錯誤
                    return { "success": False, "message": "配置檔案格式或內容不正確。", "crawler": None }

                # 可選：檢查檔案內容的 name 是否與爬蟲資料中的 name 一致
                if config_data_from_file.get("name") != crawler_name:
                    logger.warning(
                        "配置檔案內容中的 name '%s' 與爬蟲名稱 '%s' 不符。建議保持一致。",
                         config_data_from_file.get("name"), crawler_name
                    )
                    # 根據需求決定是否要強制中止
                    # return { "success": False, "message": "配置檔案中的 name 與爬蟲名稱不符。", "crawler": None }


                # --- 3. 生成安全檔名 ---
                base_filename = f"{crawler_name}.json"
                safe_filename = self._clean_filename(base_filename)
                if not safe_filename:
                    logger.error("根據爬蟲名稱 '%s' 無法生成有效的安全檔名。", crawler_name)
                    return { "success": False, "message": "無法根據爬蟲名稱生成有效的安全檔名。", "crawler": None }

                # --- 4. 儲存配置檔案 ---
                default_config_dir = "/app/data/web_site_configs"
                config_dir = os.getenv('WEB_SITE_CONFIG_DIR', default_config_dir)
                try:
                    os.makedirs(config_dir, exist_ok=True)
                except OSError as e:
                    logger.error("創建配置目錄 %s 失敗: %s", config_dir, e)
                    return { "success": False, "message": f"無法創建配置目錄: {e}", "crawler": None }

                config_path = os.path.join(config_dir, safe_filename)
                logger.info("準備將配置檔案寫入: %s", config_path)
                try:
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(config_data_from_file, f, indent=4, ensure_ascii=False)
                    saved_config_path = config_path # 記錄已保存的路徑
                    logger.info("配置檔案已成功儲存到: %s", saved_config_path)
                except Exception as e:
                    logger.error("儲存配置檔案失敗 (%s): %s", config_path, e)
                    # 即使這裡失敗，事務也會回滾，無需手動刪除檔案
                    return { "success": False, "message": f"儲存配置檔案失敗: {e}", "crawler": None }


                # --- 5. 儲存爬蟲資料到資料庫 ---
                # 更新 validated_data 中的檔名
                temp_validated_data["config_file_name"] = safe_filename

                # 再次驗證（可選，因為欄位已填寫）
                try:
                    final_validated_data = CrawlersCreateSchema.model_validate(
                        temp_validated_data
                    ).model_dump()
                except Exception as e:
                     # 理論上不應該在這裡失敗，但以防萬一
                     logger.error("最終資料驗證失敗（異常情況）: %s", e)
                     # 觸發事務回滾 + 檔案刪除
                     raise RuntimeError(f"最終資料驗證失敗: {e}") from e


                logger.debug("準備將爬蟲資料寫入資料庫: %s", final_validated_data)
                try:
                    result = crawler_repo.create(final_validated_data)
                    if result and not instance_state(result).detached:
                        session.flush()
                        session.refresh(result)
                        crawler_schema = CrawlerReadSchema.model_validate(result)
                        logger.info("爬蟲設定和配置檔案創建成功，ID=%s", result.id)
                        # 成功完成，返回結果
                        return {
                            "success": True,
                            "message": "爬蟲設定和配置檔案創建成功",
                            "crawler": crawler_schema,
                        }
                    else:
                        # repo.create 返回 None 或 detached，視為失敗
                        logger.error("資料庫創建爬蟲記錄失敗，repo.create 未返回有效實例。")
                        # 觸發事務回滾 + 檔案刪除
                        raise RuntimeError("資料庫創建爬蟲記錄失敗。")

                except Exception as db_error:
                    logger.error("儲存爬蟲資料到資料庫時失敗: %s", db_error)
                    # 觸發事務回滾 + 檔案刪除
                    raise db_error # 重新拋出，確保事務回滾並進入外層 except


        except Exception as e:
            logger.error("創建爬蟲與配置檔案的整體操作失敗: %s", str(e), exc_info=True)
            # --- 嘗試回滾已保存的檔案 ---
            if saved_config_path and os.path.exists(saved_config_path):
                try:
                    os.remove(saved_config_path)
                    logger.warning("因操作失敗，已回滾（刪除）先前保存的配置檔案: %s", saved_config_path)
                except Exception as rollback_error:
                    logger.error("回滾（刪除）檔案 %s 失敗: %s", saved_config_path, rollback_error)
            # 返回失敗訊息
            return {
                "success": False,
                "message": f"創建爬蟲失敗: {str(e)}", # 提供更清晰的錯誤訊息
                "crawler": None
            }
