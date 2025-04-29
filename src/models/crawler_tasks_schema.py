"""Crawler tasks schema module for data validation and serialization.

This module defines the Pydantic models for crawler task creation, update, and reading,
providing data validation, serialization, and schema definitions for the crawler task system.
"""

# Standard library imports
from datetime import datetime
from typing import Annotated, Optional, Any, List, Dict, Union

# Third party imports
from pydantic import BeforeValidator, model_validator, BaseModel, ConfigDict

# Local application imports
from src.error.errors import ValidationError
from src.models.base_schema import BaseCreateSchema, BaseUpdateSchema
from src.models.crawler_tasks_model import TASK_ARGS_DEFAULT
from src.utils.enum_utils import ScrapePhase, TaskStatus
from src.utils.model_utils import (
    validate_str,
    validate_boolean,
    validate_positive_int,
    validate_cron_expression,
    validate_scrape_phase,
    validate_task_args,
    validate_task_status,
)
from src.utils.schema_utils import (
    validate_required_fields_schema,
    validate_update_schema,
)
from src.utils.log_utils import LoggerSetup

logger = LoggerSetup.setup_logger(__name__)

# 通用字段定義
TaskName = Annotated[
    str, BeforeValidator(validate_str("task_name", max_length=255, required=True))
]
CrawlerId = Annotated[
    int,
    BeforeValidator(
        validate_positive_int("crawler_id", is_zero_allowed=False, required=True)
    ),
]
TaskArgs = Annotated[
    dict, BeforeValidator(validate_task_args("task_args", required=True))
]
IsAuto = Annotated[bool, BeforeValidator(validate_boolean("is_auto", required=True))]
IsActive = Annotated[
    bool, BeforeValidator(validate_boolean("is_active", required=True))
]
IsScheduled = Annotated[
    bool, BeforeValidator(validate_boolean("is_scheduled", required=True))
]
RetryCount = Annotated[
    int,
    BeforeValidator(
        validate_positive_int("retry_count", is_zero_allowed=True, required=False)
    ),
]
Notes = Annotated[
    Optional[str],
    BeforeValidator(validate_str("notes", max_length=65536, required=False)),
]
CronExpression = Annotated[
    Optional[str],
    BeforeValidator(
        validate_cron_expression(
            "cron_expression", max_length=255, min_length=5, required=False
        )
    ),
]
LastRunMessage = Annotated[
    Optional[str],
    BeforeValidator(validate_str("last_run_message", max_length=65536, required=False)),
]
CurrentPhase = Annotated[
    Optional[ScrapePhase],
    BeforeValidator(validate_scrape_phase("scrape_phase", required=True)),
]
TaskStatusValidator = Annotated[
    TaskStatus, BeforeValidator(validate_task_status("task_status", required=True))
]


class CrawlerTasksCreateSchema(BaseCreateSchema):
    """爬蟲任務創建模型"""

    task_name: TaskName
    crawler_id: CrawlerId
    is_auto: IsAuto = True
    is_active: IsActive = True
    is_scheduled: IsScheduled = False
    task_args: TaskArgs = TASK_ARGS_DEFAULT
    notes: Notes = None
    last_run_at: Optional[datetime] = None
    last_run_success: Optional[bool] = None
    last_run_message: LastRunMessage = None
    cron_expression: CronExpression = None
    scrape_phase: CurrentPhase = ScrapePhase.INIT
    task_status: TaskStatusValidator = TaskStatus.INIT
    retry_count: RetryCount = 0

    # 添加 model_config 來處理序列化
    model_config = ConfigDict(
        use_enum_values=True,  # 告訴 Pydantic 在序列化時使用 enum 的值
        # 如果 task_args 是嵌套模型，可能需要 populate_by_name=True 等其他配置
    )

    @model_validator(mode="before")
    @classmethod
    def validate_required_fields(cls, data):
        """驗證必填欄位"""
        if isinstance(data, dict):
            required_fields = CrawlerTasksCreateSchema.get_required_fields()
            return validate_required_fields_schema(required_fields, data)
        else:
            raise ValidationError("無效的資料格式，需要字典")

    @classmethod
    def get_required_fields(cls):
        return ["task_name", "crawler_id", "task_args", "scrape_phase"]


class CrawlerTasksUpdateSchema(BaseUpdateSchema):
    """爬蟲任務更新模型"""

    task_name: Optional[TaskName] = None
    is_auto: Optional[IsAuto] = None
    is_active: Optional[IsActive] = None
    is_scheduled: Optional[IsScheduled] = None
    task_args: Optional[TaskArgs] = None
    notes: Optional[Notes] = None
    last_run_at: Optional[datetime] = None
    last_run_success: Optional[bool] = None
    last_run_message: Optional[LastRunMessage] = None
    cron_expression: Optional[CronExpression] = None
    scrape_phase: Optional[CurrentPhase] = None
    retry_count: Optional[RetryCount] = None
    task_status: Optional[TaskStatusValidator] = None

    # 添加 model_config 來處理序列化
    model_config = ConfigDict(
        use_enum_values=True,  # 告訴 Pydantic 在序列化時使用 enum 的值
    )

    @classmethod
    def get_immutable_fields(cls):
        return ["crawler_id"] + BaseUpdateSchema.get_immutable_fields()

    @classmethod
    def get_updated_fields(cls):
        return [
            "task_name",
            "is_auto",
            "is_active",
            "is_scheduled",
            "task_args",
            "notes",
            "last_run_at",
            "last_run_success",
            "last_run_message",
            "cron_expression",
            "scrape_phase",
            "retry_count",
            "task_status",
        ] + BaseUpdateSchema.get_updated_fields()

    @model_validator(mode="before")
    @classmethod
    def validate_update(cls, data):
        """驗證更新操作"""
        if isinstance(data, dict):
            return validate_update_schema(
                cls.get_immutable_fields(), cls.get_updated_fields(), data
            )
        else:
            raise ValidationError("無效的資料格式，需要字典")


# --- 新增用於讀取/響應的 Schema ---


class CrawlerTaskReadSchema(BaseModel):
    """用於 API 響應的爬蟲任務數據模型"""

    id: int
    task_name: str
    crawler_id: int
    is_auto: bool
    is_active: bool
    is_scheduled: bool
    task_args: dict
    notes: Optional[str] = None
    last_run_at: Optional[datetime] = None
    last_run_success: Optional[bool] = None
    last_run_message: Optional[str] = None
    cron_expression: Optional[str] = None
    scrape_phase: Optional[ScrapePhase] = None
    task_status: TaskStatus
    retry_count: int
    created_at: datetime
    updated_at: datetime

    # Pydantic V2 配置: 允許從 ORM 屬性創建模型
    model_config = ConfigDict(from_attributes=True)


class PaginatedCrawlerTaskResponse(BaseModel):
    """用於分頁響應的結構化數據模型"""

    items: Union[List[CrawlerTaskReadSchema], List[Dict[str, Any]]]
    page: int
    per_page: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool

    # Pydantic V2 配置: 如果輸入數據是對象而非字典，這也可能有用
    model_config = ConfigDict(from_attributes=True)
