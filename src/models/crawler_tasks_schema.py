from typing import Annotated, Optional, Any
from pydantic import BaseModel, BeforeValidator, model_validator
from datetime import datetime
from src.error.errors import ValidationError
from src.utils.model_utils import validate_str, validate_boolean, validate_positive_int, validate_cron_expression
from src.utils.schema_utils import validate_required_fields_schema, validate_update_schema
from src.models.base_schema import BaseCreateSchema, BaseUpdateSchema


# 通用字段定義
CrawlerId = Annotated[int, BeforeValidator(validate_positive_int("crawler_id", required=True))]
MaxPages = Annotated[int, BeforeValidator(validate_positive_int("max_pages", required=True))]
NumArticles = Annotated[int, BeforeValidator(validate_positive_int("num_articles", required=True))]
MinKeywords = Annotated[int, BeforeValidator(validate_positive_int("min_keywords", required=True))]
IsAuto = Annotated[bool, BeforeValidator(validate_boolean("is_auto", required=True))]
AiOnly = Annotated[bool, BeforeValidator(validate_boolean("ai_only", required=True))]
FetchDetails = Annotated[bool, BeforeValidator(validate_boolean("fetch_details", required=True))]
Notes = Annotated[Optional[str], BeforeValidator(validate_str("notes", max_length=65536, required=False))]
CronExpression = Annotated[Optional[str], BeforeValidator(validate_cron_expression("cron_expression", max_length=255, min_length=5, required=False))]
LastRunMessage = Annotated[Optional[str], BeforeValidator(validate_str("last_run_message", max_length=65536, required=False))]

class CrawlerTasksCreateSchema(BaseCreateSchema):
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
    cron_expression: CronExpression = None

    @model_validator(mode='before')
    @classmethod
    def validate_required_fields(cls, data):
        """驗證必填欄位"""
        if isinstance(data, dict):
            required_fields = ['crawler_id']
            if data.get('is_auto') is True:
                if data.get('cron_expression') is None:
                    raise ValidationError("cron_expression: 當設定為自動執行時,此欄位不能為空")
            return validate_required_fields_schema(required_fields, data)

class CrawlerTasksUpdateSchema(BaseUpdateSchema):
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
    cron_expression: Optional[CronExpression] = None

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        """驗證更新操作"""
        if isinstance(data, dict):
            immutable_fields = ['crawler_id'] + cls._get_immutable_fields()
            updated_fields = ['is_auto', 'ai_only', 'notes', 'max_pages', 'num_articles', 'min_keywords', 'fetch_details', 'last_run_at', 'last_run_success', 'last_run_message', 'cron_expression'] + cls._get_updated_fields()
            if data.get('is_auto') is True:
                if data.get('cron_expression') is None:
                    raise ValidationError("cron_expression: 當設定為自動執行時,此欄位不能為空")
            return validate_update_schema(immutable_fields, updated_fields, data)
    