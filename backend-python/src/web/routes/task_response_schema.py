"""定義任務相關 API 端點的回應 schema。"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union

from src.models.crawler_tasks_schema import CrawlerTaskReadSchema, TaskHistorySchema, ArticlePreviewSchema
from src.web.routes.base_response_schema import BaseResponseSchema

# --- Schedule Task Schemas ---

class GetScheduledTasksSuccessResponseSchema(BaseResponseSchema):
    data: List[CrawlerTaskReadSchema]

class CreateScheduledTaskSuccessResponseSchema(BaseResponseSchema):
    data: CrawlerTaskReadSchema

class UpdateScheduledTaskSuccessResponseSchema(BaseResponseSchema):
    data: CrawlerTaskReadSchema

class DeleteScheduledTaskSuccessResponseSchema(BaseResponseSchema):
    pass # Only success/message from Base

# --- Manual Task Schemas ---

class ManualTaskStartDataSchema(BaseModel):
    task_id: int
    task_status: str

class StartManualTaskSuccessResponseSchema(BaseResponseSchema):
    data: ManualTaskStartDataSchema

class TaskStatusDataSchema(BaseModel):
    task_status: str
    scrape_phase: str
    progress: int
    task: Optional[CrawlerTaskReadSchema] # Task can be None

class GetTaskStatusSuccessResponseSchema(BaseResponseSchema):
    data: TaskStatusDataSchema

class CollectLinksManualTaskSuccessResponseSchema(BaseResponseSchema):
    data: ManualTaskStartDataSchema # Same structure as start

class GetUnscrapedLinksSuccessResponseSchema(BaseResponseSchema):
    data: List[ArticlePreviewSchema]

class FetchContentManualTaskSuccessResponseSchema(BaseResponseSchema):
    data: ManualTaskStartDataSchema # Same structure as start

class GetScrapedResultsSuccessResponseSchema(BaseResponseSchema):
    data: List[ArticlePreviewSchema]

class TestCrawlerSuccessResponseSchema(BaseResponseSchema):
    data: Dict[str, Any] = Field(description="The result of the crawler test run.")

# --- General Task Schemas ---

class CancelTaskSuccessResponseSchema(BaseResponseSchema):
    pass # Only success/message from Base

class TaskHistoryDataSchema(BaseModel):
    history: List[TaskHistorySchema]
    total_count: int

class GetTaskHistorySuccessResponseSchema(BaseResponseSchema):
    data: TaskHistoryDataSchema

class RunTaskDataSchema(BaseModel):
    task_id: int
    session_id: Optional[str]
    room: str

class RunTaskSuccessResponseSchema(BaseResponseSchema):
    data: RunTaskDataSchema

class CreateTaskSuccessResponseSchema(BaseResponseSchema):
    data: CrawlerTaskReadSchema

class UpdateTaskSuccessResponseSchema(BaseResponseSchema):
    data: CrawlerTaskReadSchema

class GetAllTasksSuccessResponseSchema(BaseResponseSchema):
    data: List[CrawlerTaskReadSchema]

class DeleteTaskSuccessResponseSchema(BaseResponseSchema):
    pass # Only success/message from Base
