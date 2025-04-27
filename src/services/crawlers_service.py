"""此模組提供 CrawlersService 類別，用於處理爬蟲相關的業務邏輯。"""

import os
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
        """獲取爬蟲的配置檔案內容

        Args:
            crawler_id: 爬蟲ID

        Returns:
            Dict[str, Any]: 配置檔案內容
                success: 是否成功
                message: 訊息
                config: 配置檔案內容
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
                    logger.error("爬蟲設定不存在，ID=%s", crawler_id)
                    return {
                        "success": False,
                        "message": f"爬蟲設定不存在，ID={crawler_id}",
                        "config": None,
                    }

                # 讀取配置檔案
                try:
                    # 獲取專案根目錄
                    current_file = os.path.dirname(__file__)
                    logger.info("當前檔案目錄: %s", current_file)

                    project_root = os.path.abspath(
                        os.path.join(current_file, "..", "..")
                    )
                    logger.info("專案根目錄: %s", project_root)

                    config_path = os.path.join(
                        project_root,
                        "src",
                        "crawlers",
                        "configs",
                        crawler.config_file_name,
                    )
                    logger.info("完整配置檔案路徑: %s", config_path)
                    logger.info("配置檔案名稱: %s", crawler.config_file_name)
                    logger.info(
                        "資料庫中的 config_file_name: %s", crawler.config_file_name
                    )
                    logger.info("檔案是否存在: %s", os.path.exists(config_path))

                    if not os.path.exists(config_path):
                        logger.error("配置檔案不存在: %s", config_path)
                        return {
                            "success": False,
                            "message": f"配置檔案不存在：{crawler.config_file_name}",
                            "config": None,
                        }

                    with open(config_path, "r", encoding="utf-8") as f:
                        config_content = f.read()
                        logger.info("讀取到的原始配置內容: %s", config_content)
                        try:
                            config_data = json.loads(config_content)
                            logger.info("成功解析配置檔案內容: %s", config_data)
                            return {
                                "success": True,
                                "message": "獲取配置檔案成功",
                                "config": config_data,
                            }
                        except json.JSONDecodeError as je:
                            logger.error("配置檔案 JSON 解析錯誤: %s", str(je))
                            return {
                                "success": False,
                                "message": f"配置檔案格式錯誤：{str(je)}",
                                "config": None,
                            }

                except Exception as e:
                    logger.error("讀取配置檔案失敗: %s", str(e))
                    return {
                        "success": False,
                        "message": f"讀取配置檔案失敗：{str(e)}",
                        "config": None,
                    }

        except Exception as e:
            logger.error("獲取爬蟲配置檔案失敗，ID=%s: %s", crawler_id, str(e))
            raise e

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
        for field in required_fields:
            if field not in config_data:
                logger.error("配置檔案缺少必要欄位: %s", field)
                return False

        # 驗證 selectors 結構
        selectors = config_data.get("selectors", {})
        if not isinstance(selectors, dict):
            logger.error("selectors 必須是字典類型")
            return False

        required_selectors = ["get_article_links", "get_article_contents"]
        for selector in required_selectors:
            if selector not in selectors:
                logger.error("selectors 缺少必要選擇器: %s", selector)
                return False

        return True

    def update_crawler_config(
        self, crawler_id: int, config_file, crawler_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新爬蟲的配置檔案

        Args:
            crawler_id: 爬蟲ID
            config_file: 上傳的配置檔案
            crawler_data: 爬蟲資料

        Returns:
            Dict[str, Any]: 更新結果
                success: 是否成功
                message: 訊息
                crawler: 更新後的爬蟲設定
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

                # 檢查爬蟲是否存在
                crawler = crawler_repo.get_by_id(crawler_id)
                if not crawler:
                    return {
                        "success": False,
                        "message": f"爬蟲設定不存在，ID={crawler_id}",
                        "crawler": None,
                    }

                # 保存配置檔案
                try:
                    # 讀取並驗證配置檔案內容
                    config_content = config_file.read()
                    try:
                        config_data = json.loads(config_content)
                    except json.JSONDecodeError:
                        return {
                            "success": False,
                            "message": "配置檔案不是有效的 JSON 格式",
                            "crawler": None,
                        }

                    # 驗證配置檔案格式
                    if not self.validate_config_file(config_data):
                        return {
                            "success": False,
                            "message": "配置檔案格式不正確，請檢查必要欄位",
                            "crawler": None,
                        }

                    # 獲取專案根目錄
                    project_root = os.path.abspath(
                        os.path.join(os.path.dirname(__file__), "..", "..")
                    )
                    config_dir = os.path.join(
                        project_root, "src", "crawlers", "configs"
                    )
                    os.makedirs(config_dir, exist_ok=True)

                    # 使用原始檔名保存
                    config_path = os.path.join(config_dir, config_file.filename)
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(config_data, f, indent=4, ensure_ascii=False)

                    # 更新爬蟲資料
                    crawler_data["config_file_name"] = config_file.filename
                    crawler_data["updated_at"] = datetime.now(timezone.utc)

                    # 驗證並更新爬蟲資料
                    validated_data = self.validate_crawler_data(
                        crawler_data, is_update=True
                    )
                    result = crawler_repo.update(crawler_id, validated_data)

                    if result and not instance_state(result).detached:
                        session.flush()
                        session.refresh(result)
                        crawler_schema = CrawlerReadSchema.model_validate(result)
                        return {
                            "success": True,
                            "message": "爬蟲設定和配置檔案更新成功",
                            "crawler": crawler_schema,
                        }
                    else:
                        return {
                            "success": False,
                            "message": "更新爬蟲設定失敗",
                            "crawler": None,
                        }

                except Exception as e:
                    logger.error("保存配置檔案失敗: %s", str(e))
                    return {
                        "success": False,
                        "message": f"保存配置檔案失敗: {str(e)}",
                        "crawler": None,
                    }

        except Exception as e:
            logger.error("更新爬蟲配置檔案失敗，ID=%s: %s", crawler_id, str(e))
            raise e
