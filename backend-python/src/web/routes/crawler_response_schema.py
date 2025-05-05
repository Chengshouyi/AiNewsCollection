from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from src.models.crawlers_schema import (
    CrawlerReadSchema,
    PaginatedCrawlerResponse
)
from src.web.routes.base_response_schema import BaseResponseSchema


# --- 通用爬蟲操作成功回應 ---
class CrawlerActionSuccessResponseSchema(BaseResponseSchema):
    """單一爬蟲資料的成功回應。"""
    data: CrawlerReadSchema

# --- 獲取爬蟲列表成功回應 ---
class GetCrawlersSuccessResponseSchema(BaseResponseSchema):
    """爬蟲列表的成功回應。"""
    data: List[CrawlerReadSchema]

# --- 刪除爬蟲成功回應 ---
class DeleteCrawlerSuccessResponseSchema(BaseResponseSchema):
    """刪除操作成功的基礎回應。"""
    pass

# --- 獲取爬蟲類型成功回應 ---
class GetCrawlerTypesSuccessResponseSchema(BaseResponseSchema):
    """可用爬蟲類型列表的成功回應。"""
    data: List[Dict[str, str]]

# --- 獲取爬蟲統計成功回應 ---
class GetCrawlerStatsSuccessResponseSchema(BaseResponseSchema):
    """爬蟲統計資料的成功回應。"""
    data: Dict[str, Any] # 或者更精確的類型

# --- 批量切換狀態內部結果 ---
class BatchToggleStatusResultSchema(BaseModel):
    """批量切換狀態的操作結果詳情。"""
    success_count: int = Field(..., description="成功操作的數量")
    failure_count: int = Field(..., description="失敗操作的數量")
    failed_ids: List[int] = Field(..., description="操作失敗的爬蟲 ID 列表")

# --- 批量切換狀態成功回應 ---
class BatchToggleStatusSuccessResponseSchema(BaseResponseSchema):
    """批量切換狀態操作的成功回應 (即使有部分失敗)。"""
    # 注意：API 目前回傳的是 result 鍵，但為了與 BaseResponseSchema 一致，
    # 我們定義 data，並在 API 端進行調整。
    # 如果堅持要 result 鍵，可以不繼承 BaseResponseSchema:
    # class BatchToggleStatusSuccessResponseSchema(BaseModel):
    #     success: bool = Field(default=True)
    #     message: str
    #     result: BatchToggleStatusResultSchema
    data: BatchToggleStatusResultSchema


# --- 獲取過濾/分頁爬蟲成功回應 ---
class GetFilteredCrawlersSuccessResponseSchema(BaseResponseSchema):
    """過濾/分頁爬蟲列表的成功回應。"""
    data: PaginatedCrawlerResponse

# --- 獲取爬蟲配置成功回應 ---
class GetCrawlerConfigSuccessResponseSchema(BaseResponseSchema):
    """獲取爬蟲配置內容的成功回應。"""
    data: Dict[str, Any] # JSON 配置內容通常是字典
