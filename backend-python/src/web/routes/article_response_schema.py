from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from src.models.articles_schema import ArticleReadSchema, PaginatedArticleResponse
from src.web.routes.base_response_schema import BaseResponseSchema


# get_article 的成功回應模型
class GetArticleSuccessResponseSchema(BaseResponseSchema):
    data: ArticleReadSchema # 使用您已有的 ArticleReadSchema

# search_articles 的成功回應模型
class SearchArticlesSuccessResponseSchema(BaseResponseSchema):
    data: Union[List[ArticleReadSchema], List[Dict[str, Any]]]

# get_articles 的成功回應模型
class GetArticlesSuccessResponseSchema(BaseResponseSchema):
    data: PaginatedArticleResponse