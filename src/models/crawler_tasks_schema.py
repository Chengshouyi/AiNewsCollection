from typing import Annotated, Optional, Any
from pydantic import BaseModel, BeforeValidator, model_validator
from datetime import datetime
from src.error.errors import ValidationError
from src.utils.model_utils import validate_str, validate_boolean, validate_positive_int

def validate_crawler_id(value: Any) -> int:
    """爬蟲ID驗證"""
    if not value:
        raise ValidationError("crawler_id: 不能為空")
    try:
        value = int(value)
        if value <= 0:
            raise ValidationError("crawler_id: 必須大於0")
        return value
    except ValueError:
        raise ValidationError("crawler_id: 必須是整數")

def validate_schedule(value: Optional[str]) -> Optional[str]:
    """排程驗證"""
    if value is None:
        return None
    value = value.strip()
    if value not in ['hourly', 'daily', 'weekly']:
        raise ValidationError("schedule: 必須是 'hourly', 'daily', 'weekly' 或 None")
    return value

# 通用字段定義
CrawlerId = Annotated[int, BeforeValidator(validate_crawler_id)]
MaxPages = Annotated[int, BeforeValidator(validate_positive_int("max_pages"))]
NumArticles = Annotated[int, BeforeValidator(validate_positive_int("num_articles"))]
MinKeywords = Annotated[int, BeforeValidator(validate_positive_int("min_keywords"))]
IsAuto = Annotated[bool, BeforeValidator(validate_boolean("is_auto"))]
AiOnly = Annotated[bool, BeforeValidator(validate_boolean("ai_only"))]
FetchDetails = Annotated[bool, BeforeValidator(validate_boolean("fetch_details"))]
Notes = Annotated[Optional[str], BeforeValidator(validate_str("notes", max_length=65536))]
Schedule = Annotated[Optional[str], BeforeValidator(validate_schedule)]
LastRunMessage = Annotated[Optional[str], BeforeValidator(validate_str("last_run_message", max_length=65536))]

class CrawlerTasksCreateSchema(BaseModel):
    """爬蟲任務創建模型"""
    crawler_id: CrawlerId
    is_auto: IsAuto = True
    ai_only: AiOnly = False
    notes: Notes = None
    max_pages: MaxPages = 3
    num_articles: NumArticles = 10
    min_keywords: MinKeywords = 3
    fetch_details: FetchDetails = False
    last_run_at: Optional[datetime] = None
    last_run_success: Optional[bool] = None
    last_run_message: LastRunMessage = None
    schedule: Schedule = None

    @model_validator(mode='before')
    @classmethod
    def validate_required_fields(cls, data):
        """驗證必填欄位"""
        if isinstance(data, dict):
            required_fields = ['crawler_id']
            for field in required_fields:
                if field not in data:
                    raise ValidationError(f"{field}: 不能為空")
        return data

class CrawlerTasksUpdateSchema(BaseModel):
    """爬蟲任務更新模型"""
    is_auto: Optional[IsAuto] = None
    ai_only: Optional[AiOnly] = None
    notes: Optional[Notes] = None
    max_pages: Optional[MaxPages] = None
    num_articles: Optional[NumArticles] = None
    min_keywords: Optional[MinKeywords] = None
    fetch_details: Optional[FetchDetails] = None
    last_run_at: Optional[datetime] = None
    last_run_success: Optional[bool] = None
    last_run_message: Optional[LastRunMessage] = None
    schedule: Optional[Schedule] = None

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        """驗證更新操作"""
        if isinstance(data, dict):
            immutable_fields = ['created_at', 'crawler_id']
            for field in immutable_fields:
                if field in data:
                    raise ValidationError(f"不允許更新 {field} 欄位")
            
            update_fields = [
                field for field in data.keys()
                if field not in ['updated_at'] + immutable_fields
            ]
            if not update_fields:
                raise ValidationError("必須提供至少一個要更新的欄位")
        return data
    