from typing import Annotated, Optional, List, Union, Dict, Any
from pydantic import BeforeValidator, model_validator, BaseModel, ConfigDict
from datetime import datetime
from src.utils.model_utils import validate_str, validate_url, validate_datetime, validate_boolean, validate_int,validate_article_scrape_status
from src.models.base_schema import BaseCreateSchema, BaseUpdateSchema
from src.utils.schema_utils import validate_update_schema, validate_required_fields_schema
from src.utils.enum_utils import ArticleScrapeStatus

# 通用字段定義
Title = Annotated[str, BeforeValidator(validate_str("title", max_length=500, required=True))]
Link = Annotated[str, BeforeValidator(validate_url("link", max_length=1000, required=True))]
Source = Annotated[str, BeforeValidator(validate_str("source", max_length=50, required=True))]
SourceUrl = Annotated[str, BeforeValidator(validate_url("source_url", max_length=1000, required=True))]
PublishedAt = Annotated[Optional[datetime], BeforeValidator(validate_datetime("published_at", required=False))]
Summary = Annotated[Optional[str], BeforeValidator(validate_str("summary", 10000, required=False))]
Content = Annotated[Optional[str], BeforeValidator(validate_str("content", 65536, required=False))]
Category = Annotated[Optional[str], BeforeValidator(validate_str("category", 100, required=False))]
Author = Annotated[Optional[str], BeforeValidator(validate_str("author", 100, required=False))]
ArticleType = Annotated[Optional[str], BeforeValidator(validate_str("article_type", 20, required=False))]
Tags = Annotated[Optional[str], BeforeValidator(validate_str("tags", 500, required=False))]
IsAiRelated = Annotated[bool, BeforeValidator(validate_boolean("is_ai_related", required=True))]
IsScraped = Annotated[bool, BeforeValidator(validate_boolean("is_scraped", required=True))]
ScrapeStatus = Annotated[Optional[ArticleScrapeStatus], BeforeValidator(validate_article_scrape_status("scrape_status", required=True))]
ScrapeError = Annotated[Optional[str], BeforeValidator(validate_str("scrape_error", 1000, required=False))]
LastScrapeAttempt = Annotated[Optional[datetime], BeforeValidator(validate_datetime("last_scrape_attempt", required=False))]
TaskId = Annotated[Optional[int], BeforeValidator(validate_int("task_id", required=False))]


class ArticleCreateSchema(BaseCreateSchema):
    """文章創建模型"""
    title: Title
    link: Link
    summary: Summary = None
    content: Content = None
    source: Source
    source_url: SourceUrl
    published_at: PublishedAt = None
    category: Category = None
    author: Author = None
    article_type: ArticleType = None
    tags: Tags = None
    is_ai_related: IsAiRelated
    is_scraped: IsScraped
    scrape_status: ScrapeStatus = ArticleScrapeStatus.PENDING
    scrape_error: ScrapeError = None
    last_scrape_attempt: LastScrapeAttempt = None
    task_id: TaskId = None

    @model_validator(mode='before')
    @classmethod
    def validate_required_fields(cls, data):
        """驗證必填欄位"""
        if isinstance(data, dict):
            required_fields = ArticleCreateSchema.get_required_fields()
            return validate_required_fields_schema(required_fields, data)
        
    @staticmethod
    def get_required_fields():
        return ['title', 'link', 'source', 'source_url', 'is_ai_related', 'is_scraped', 'scrape_status']

class ArticleUpdateSchema(BaseUpdateSchema):
    """文章更新模型"""
    title: Optional[Title] = None
    summary: Optional[Summary] = None
    content: Optional[Content] = None
    source: Optional[Source] = None
    source_url: Optional[SourceUrl] = None
    published_at: Optional[PublishedAt] = None
    category: Optional[Category] = None
    author: Optional[Author] = None
    article_type: Optional[ArticleType] = None
    tags: Optional[Tags] = None
    is_ai_related: Optional[IsAiRelated] = None
    is_scraped: Optional[IsScraped] = None
    scrape_status: Optional[ScrapeStatus] = None
    scrape_error: Optional[ScrapeError] = None
    last_scrape_attempt: Optional[LastScrapeAttempt] = None
    task_id: Optional[TaskId] = None

    @model_validator(mode='before')
    @classmethod
    def validate_update(cls, data):
        """驗證更新操作"""
        if isinstance(data, dict):
            return validate_update_schema(cls.get_immutable_fields(), cls.get_updated_fields(), data)

    @classmethod
    def get_immutable_fields(cls):
        return ['link'] + BaseUpdateSchema.get_immutable_fields()
    
    @classmethod
    def get_updated_fields(cls):
        return ['title', 'summary', 'content', 'source', 'source_url', 'published_at', 'category', 'author', 'article_type', 'tags', 'is_ai_related', 'is_scraped', 'scrape_status', 'scrape_error', 'last_scrape_attempt', 'task_id'] + BaseUpdateSchema.get_updated_fields()
    

# --- 新增用於讀取/響應的 Schema ---

class ArticleReadSchema(BaseModel):
    """用於 API 響應的文章數據模型"""
    id: int
    title: str
    link: str
    summary: Optional[str] = None
    content: Optional[str] = None
    source: str
    source_url: str
    published_at: Optional[datetime] = None
    category: Optional[str] = None
    author: Optional[str] = None
    article_type: Optional[str] = None
    tags: Optional[str] = None # 或者考慮解析成 List[str]
    is_ai_related: bool
    is_scraped: bool
    scrape_status: Optional[ArticleScrapeStatus] = None
    scrape_error: Optional[str] = None
    last_scrape_attempt: Optional[datetime] = None
    task_id: Optional[int] = None # 根據需要決定是否返回 task_id
    created_at: datetime 
    updated_at: datetime 

    # Pydantic V2 配置: 允許從 ORM 屬性創建模型
    model_config = ConfigDict(from_attributes=True)

class PaginatedArticleResponse(BaseModel):
    """用於分頁響應的結構化數據模型"""
    items: Union[List[ArticleReadSchema], List[Dict[str, Any]]] # 支援 ORM Schema 或預覽字典
    page: int
    per_page: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool

    # Pydantic V2 配置: 如果輸入數據是對象而非字典，這也可能有用
    model_config = ConfigDict(from_attributes=True)


