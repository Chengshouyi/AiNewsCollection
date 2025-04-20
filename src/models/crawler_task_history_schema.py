from typing import Annotated, Optional, Any, List, Union, Dict
from pydantic import BaseModel, BeforeValidator, model_validator, ConfigDict
from datetime import datetime
from src.utils.model_utils import validate_str, validate_datetime, validate_boolean, validate_positive_int,validate_task_status
from src.utils.schema_utils import validate_required_fields_schema, validate_update_schema
from src.models.base_schema import BaseCreateSchema, BaseUpdateSchema
from src.utils.enum_utils import TaskStatus

# 通用字段定義
TaskId = Annotated[int, BeforeValidator(validate_positive_int("task_id", is_zero_allowed=False, required=True))]
ArticlesCount = Annotated[Optional[int], BeforeValidator(validate_positive_int("articles_count", is_zero_allowed=True, required=False))]
Message = Annotated[Optional[str], BeforeValidator(validate_str("message", max_length=65536, required=False))]
TaskStatusValidator = Annotated[TaskStatus, BeforeValidator(validate_task_status("task_status", required=True))]
StartTime = Annotated[Optional[datetime], BeforeValidator(validate_datetime("start_time", required=True))]
EndTime = Annotated[Optional[datetime], BeforeValidator(validate_datetime("end_time", required=False))]
Success = Annotated[Optional[bool], BeforeValidator(validate_boolean("success"))]

class CrawlerTaskHistoryCreateSchema(BaseCreateSchema):
    """爬蟲任務歷史創建模型"""
    task_id: TaskId
    start_time: StartTime = None
    end_time: EndTime = None
    success: Success = None
    message: Message = None
    articles_count: ArticlesCount = None
    task_status: TaskStatusValidator = TaskStatus.INIT
    @model_validator(mode='before')
    @classmethod
    def validate_required_fields(cls, data):
        """驗證必填欄位"""
        if isinstance(data, dict):
            required_fields = CrawlerTaskHistoryCreateSchema.get_required_fields()
            return validate_required_fields_schema(required_fields, data)
        
    @classmethod
    def get_required_fields(cls):
        return ['task_id']


class CrawlerTaskHistoryUpdateSchema(BaseUpdateSchema):
    """爬蟲任務歷史更新模型"""
    end_time: Optional[EndTime] = None
    start_time: Optional[StartTime] = None
    success: Optional[Success] = None
    message: Optional[Message] = None
    articles_count: Optional[ArticlesCount] = None
    task_status: Optional[TaskStatusValidator] = None

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        """驗證更新操作"""
        if isinstance(data, dict):
             return validate_update_schema(cls.get_immutable_fields(), cls.get_updated_fields(), data)
        
    @classmethod
    def get_immutable_fields(cls):
        return ['task_id'] + BaseUpdateSchema.get_immutable_fields()
    
    @classmethod
    def get_updated_fields(cls):
        return ['end_time', 'start_time', 'success', 'message', 'articles_count', 'task_status'] + BaseUpdateSchema.get_updated_fields()
    
# --- 新增用於讀取/響應的 Schema ---

class CrawlerTaskHistoryReadSchema(BaseModel):
    """用於 API 響應的爬蟲任務歷史數據模型"""
    id: int
    task_id: int
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    success: Optional[bool] = None
    message: Optional[str] = None
    articles_count: Optional[int] = None
    task_status: TaskStatus
    created_at: datetime
    updated_at: datetime

    # Pydantic V2 配置: 允許從 ORM 屬性創建模型
    model_config = ConfigDict(from_attributes=True)

class PaginatedCrawlerTaskHistoryResponse(BaseModel):
    """用於分頁響應的結構化數據模型，支援預覽模式"""
    items: Union[List[CrawlerTaskHistoryReadSchema], List[Dict[str, Any]]]
    page: int
    per_page: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool

    # Pydantic V2 配置: 如果輸入數據是對象而非字典，這也可能有用
    model_config = ConfigDict(from_attributes=True)
            