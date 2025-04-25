import logging
from typing import Optional, Dict, Any, List, TypeVar, Tuple, Hashable, Type, cast, Union
from src.models.articles_model import Base, Articles, ArticleScrapeStatus
from src.models.articles_schema import ArticleReadSchema, PaginatedArticleResponse
from datetime import datetime, timedelta
from src.error.errors import DatabaseOperationError, ValidationError
from src.database.articles_repository import ArticlesRepository
from sqlalchemy import or_
from sqlalchemy.orm import Session
from src.services.base_service import BaseService
from src.database.base_repository import BaseRepository, SchemaType
from sqlalchemy.orm.attributes import instance_state

# 設定 logger
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 通用類型變數，用於泛型方法
T = TypeVar('T', bound=Base)
# 定義返回結果的類型別名
ArticleResultType = Union[List[ArticleReadSchema], List[Dict[str, Any]]]

class ArticleService(BaseService[Articles]):
    """文章服務，提供文章相關業務邏輯"""

    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    def _get_repository_mapping(self) -> Dict[str, Tuple[Type[BaseRepository], Type[Base]]]:
        """提供儲存庫映射"""
        return {
            'Article': (ArticlesRepository, Articles)
        }

    def validate_article_data(self, data: Dict[str, Any], is_update: bool = False) -> Dict[str, Any]:
        """驗證文章資料

        Args:
            data: 要驗證的資料
            is_update: 是否為更新操作

        Returns:
            Dict[str, Any]: 驗證後的資料
        """
        schema_type = SchemaType.UPDATE if is_update else SchemaType.CREATE
        return self.validate_data('Article', data, schema_type)

    def create_article(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """創建新文章，若連結已存在則更新，返回包含 ArticleReadSchema 的字典"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))

                link = article_data.get('link')
                existing_article = None
                if link:
                    existing_article = article_repo.find_by_link(link)

                if existing_article:
                    logger.info(f"文章連結 '{link}' 已存在，將執行更新操作。")
                    # 業務邏輯：重複爬取的文章，預設更新，移除 link 欄位，避免驗證時出現錯誤
                    if 'link' in article_data:
                        article_data_for_validation = article_data.copy()
                        article_data_for_validation.pop('link', None)
                    else:
                        article_data_for_validation = article_data

                    validated_data = self.validate_article_data(article_data_for_validation, is_update=True)

                    updated_article = article_repo.update(existing_article.id, validated_data)
                    # commit 由 _transaction 處理
                    if updated_article:
                        session.flush() # 確保 ID 等自動生成欄位可用
                        session.refresh(updated_article) # 從 DB 獲取最新狀態
                        article_schema = ArticleReadSchema.model_validate(updated_article) # 轉換為 Schema
                        return {
                            'success': True,
                            'message': '文章已存在，更新成功',
                            'article': article_schema # 返回 Schema
                        }
                    else:
                        session.refresh(existing_article) # 確保是最新狀態
                        article_schema = ArticleReadSchema.model_validate(existing_article) # 轉換為 Schema
                        return {
                            'success': True,
                            'message': '文章已存在，無變更或更新失敗',
                            'article': article_schema # 返回 Schema
                        }
                else:
                    validated_data = self.validate_article_data(article_data, is_update=False)
                    new_article = article_repo.create(validated_data)

                    if new_article:
                        session.flush()
                        session.refresh(new_article)
                        article_schema = ArticleReadSchema.model_validate(new_article) # 轉換為 Schema
                        return {
                            'success': True,
                            'message': '文章創建成功',
                            'article': article_schema # 返回 Schema
                        }
                    else:
                        # 這裡可能表示 repo.create 內部邏輯返回了 None，需要檢查 repo 實現
                        logger.warning("create_article: repo.create 返回 None")
                        return {
                            'success': False,
                            'message': '文章創建失敗 (內部原因)',
                            'article': None
                        }

        except ValidationError as e:
            error_msg = f"創建或更新文章時資料驗證失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'article': None}
        except DatabaseOperationError as e:
            error_msg = f"創建或更新文章時資料庫操作失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'article': None}
        except Exception as e:
            error_msg = f"創建或更新文章時發生未預期錯誤: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'article': None
            }

    def batch_create_articles(self, articles_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量創建新文章，返回包含 ArticleReadSchema 列表的結果"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))

                repo_result = article_repo.batch_create(articles_data)

                # --- 新增: Flush 和 Refresh 以獲取 ID ---
                session.flush() # 將所有待處理的變更寫入 DB (獲取 ID)
                inserted_articles_orm = repo_result.get('inserted_articles', [])
                updated_articles_orm = repo_result.get('updated_articles', [])

                # Refresh 每個對象以確保數據同步
                for article in inserted_articles_orm:
                    if article and not instance_state(article).detached: # 確保對象在 session 中
                         session.refresh(article)
                for article in updated_articles_orm:
                     if article and not instance_state(article).detached:
                         session.refresh(article)
                # --- 結束新增 ---

                # 轉換結果中的 ORM 列表為 Schema 列表
                inserted_schemas = [ArticleReadSchema.model_validate(a) for a in inserted_articles_orm]
                updated_schemas = [ArticleReadSchema.model_validate(a) for a in updated_articles_orm]

                # 構建最終返回的結果字典
                final_result_msg = repo_result.copy()
                final_result_msg['inserted_articles'] = inserted_schemas
                final_result_msg['updated_articles'] = updated_schemas

                message = (
                    f"批量處理文章完成：新增 {final_result_msg.get('success_count', 0)} 筆，"
                    f"更新 {final_result_msg.get('update_count', 0)} 筆，"
                    f"失敗 {final_result_msg.get('fail_count', 0)} 筆"
                )

                success = final_result_msg.get('fail_count', 0) == 0
                return {
                    'success': success,
                    'message': message,
                    'resultMsg': final_result_msg
                }
        except ValidationError as e:
            # Pydantic 驗證錯誤現在也可能在這裡觸發，但應該是轉換時的問題
            error_msg = f"批量創建文章時資料轉換或驗證失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'resultMsg': None}
        except DatabaseOperationError as e:
            error_msg = f"批量創建文章時資料庫操作失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'resultMsg': None}
        except Exception as e:
            # 捕獲更廣泛的異常，包括可能的 refresh 錯誤
            error_msg = f"批量創建文章失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'resultMsg': None
            }

    def find_all_articles(self,
                          limit: Optional[int] = None,
                          offset: Optional[int] = None,
                          sort_by: Optional[str] = None,
                          sort_desc: bool = False,
                          is_preview: bool = False,
                          preview_fields: Optional[List[str]] = None
                          ) -> Dict[str, Any]:
        """獲取所有文章，支援分頁、排序和預覽"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))

                articles_result = article_repo.find_all(
                    limit=limit,
                    offset=offset,
                    sort_by=sort_by,
                    sort_desc=sort_desc,
                    is_preview=is_preview,
                    preview_fields=preview_fields
                )

                # 如果不是預覽模式，且結果是 ORM 列表，則轉換為 Schema
                if not is_preview and articles_result and isinstance(articles_result[0], Articles):
                    articles_schema = [ArticleReadSchema.model_validate(article) for article in articles_result]
                else:
                    articles_schema = articles_result # 保持字典列表或空列表

                return {
                    'success': True,
                    'message': '獲取所有文章成功',
                    'articles': articles_schema
                }
        except DatabaseOperationError as e:
            error_msg = f"獲取所有文章時資料庫操作失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'articles': []}
        except Exception as e:
            error_msg = f"獲取所有文章失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'articles': []
            }

    def get_article_by_id(self, article_id: int) -> Dict[str, Any]:
        """根據ID獲取文章，返回包含 ArticleReadSchema 的字典"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))

                article_orm = article_repo.get_by_id(article_id)
                if article_orm:
                    article_schema = ArticleReadSchema.model_validate(article_orm) # 轉換為 Schema
                    return {
                        'success': True,
                        'message': '獲取文章成功',
                        'article': article_schema # 返回 Schema
                    }
                return {
                    'success': False,
                    'message': '文章不存在',
                    'article': None
                }
        except DatabaseOperationError as e:
            error_msg = f"獲取文章 ID={article_id} 時資料庫操作失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'article': None}
        except Exception as e:
            error_msg = f"獲取文章失敗, ID={article_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'article': None
            }

    def update_article(self, article_id: int, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新文章，返回包含 ArticleReadSchema 的字典"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))

                existing_article = article_repo.get_by_id(article_id)
                if not existing_article:
                    return {
                        'success': False,
                        'message': '文章不存在，無法更新',
                        'article': None
                    }

                validated_data = self.validate_article_data(article_data, is_update=True)
                updated_article = article_repo.update(article_id, validated_data)

                if updated_article:
                    session.flush()
                    session.refresh(updated_article)
                    article_schema = ArticleReadSchema.model_validate(updated_article) # 轉換為 Schema
                    return {
                        'success': True,
                        'message': '文章更新成功',
                        'article': article_schema # 返回 Schema
                    }
                else:
                    logger.warning(f"更新文章 ID={article_id} 時 repo.update 返回 None 或 False，可能無變更或更新失敗。")
                    session.refresh(existing_article) # 確保返回的是最新狀態
                    article_schema = ArticleReadSchema.model_validate(existing_article) # 轉換為 Schema
                    return {
                        'success': True,
                        'message': '文章更新操作完成 (可能無實際變更)',
                        'article': article_schema # 返回 Schema (更新前的狀態)
                    }

        except ValidationError as e:
            error_msg = f"更新文章 ID={article_id} 時資料驗證失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'article': None}
        except DatabaseOperationError as e:
            error_msg = f"更新文章 ID={article_id} 時資料庫操作失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'article': None}
        except Exception as e:
            error_msg = f"更新文章失敗, ID={article_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'article': None
            }

    def delete_article(self, article_id: int) -> Dict[str, Any]:
        """刪除文章"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                    }

                success = article_repo.delete(article_id)
                # Delete 不返回對象，無需 flush 或 refresh
                return {
                    'success': success,
                    'message': '文章刪除成功' if success else '文章不存在或刪除失敗',
                }
        except Exception as e:
            error_msg = f"刪除文章失敗, ID={article_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
            }

    def get_article_by_link(self, link: str) -> Dict[str, Any]:
        """根據連結獲取文章，返回包含 ArticleReadSchema 的字典"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'article': None
                    }
                article_orm = article_repo.find_by_link(link)
                if article_orm:
                    article_schema = ArticleReadSchema.model_validate(article_orm) # 轉換為 Schema
                    return {
                        'success': True,
                        'message': '獲取文章成功',
                        'article': article_schema # 返回 Schema
                    }
                return {
                    'success': False,
                    'message': '文章不存在',
                    'article': None
                }
        except Exception as e:
            error_msg = f"根據連結獲取文章失敗, link={link}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'article': None
            }

    def find_articles_paginated(self,
                                page: int,
                                per_page: int,
                                filter_criteria: Optional[Dict[str, Any]] = None,
                                sort_by: Optional[str] = None,
                                sort_desc: bool = False,
                                is_preview: bool = False,
                                preview_fields: Optional[List[str]] = None,
                                validated_params: Optional[Dict[str, Any]] = None
                               ) -> Dict[str, Any]:
        """查找文章並分頁返回，支援過濾、排序和預覽"""
        try:
            # 確保 filter_criteria 是字典
            if filter_criteria is None:
                filter_criteria = {}

            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))

                total_count, articles_orm_or_dict = article_repo.find_paginated(
                    page=page,
                    per_page=per_page,
                    filter_criteria=filter_criteria,
                    extra_filters=None,
                    sort_by=sort_by,
                    sort_desc=sort_desc,
                    is_preview=is_preview,
                    preview_fields=preview_fields
                )

                # 計算總頁數
                total_pages = (total_count + per_page - 1) // per_page if per_page > 0 else 0

                # 轉換結果
                items: ArticleResultType
                if not is_preview and articles_orm_or_dict and isinstance(articles_orm_or_dict[0], Articles):
                    items = [ArticleReadSchema.model_validate(article) for article in articles_orm_or_dict]
                else:
                    items = articles_orm_or_dict # 保持字典列表或空列表

                # 構建分頁響應對象
                paginated_response = PaginatedArticleResponse(
                    items=items,
                    page=page,
                    per_page=per_page,
                    total=total_count,
                    total_pages=total_pages,
                    has_next=page < total_pages,
                    has_prev=page > 1
                )

                return {
                    'success': True,
                    'message': '獲取分頁文章成功',
                    'resultMsg': paginated_response # 返回包含 Schema 列表的 PaginatedResponse
                }
        except DatabaseOperationError as e:
            error_msg = f"獲取分頁文章時資料庫操作失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'resultMsg': None}
        except Exception as e:
            error_msg = f"獲取分頁文章失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'resultMsg': None
            }

    def find_ai_related_articles(self,
                                 limit: Optional[int] = None,
                                 offset: Optional[int] = None,
                                 sort_by: Optional[str] = None,
                                 sort_desc: bool = False,
                                 is_preview: bool = False,
                                 preview_fields: Optional[List[str]] = None
                                 ) -> Dict[str, Any]:
        """獲取所有AI相關的文章，支援分頁、排序和預覽"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }

                articles_result = article_repo.find_by_filter(
                    filter_criteria={"is_ai_related": True},
                    limit=limit,
                    offset=offset,
                    sort_by=sort_by,
                    sort_desc=sort_desc,
                    is_preview=is_preview,
                    preview_fields=preview_fields
                )

                if not is_preview and articles_result and isinstance(articles_result[0], Articles):
                    articles_schema = [ArticleReadSchema.model_validate(article) for article in articles_result]
                else:
                    articles_schema = articles_result

                return {
                    'success': True,
                    'message': '獲取AI相關文章成功',
                    'articles': articles_schema
                }
        except Exception as e:
            error_msg = f"獲取AI相關文章失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                 'success': False,
                 'message': error_msg,
                 'articles': []
             }

    def find_articles_by_category(self,
                                  category: str,
                                  limit: Optional[int] = None,
                                  offset: Optional[int] = None,
                                  sort_by: Optional[str] = None,
                                  sort_desc: bool = False,
                                  is_preview: bool = False,
                                  preview_fields: Optional[List[str]] = None
                                  ) -> Dict[str, Any]:
        """根據分類獲取文章，支援分頁、排序和預覽"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }
                articles_result = article_repo.find_by_category(
                    category=category,
                    limit=limit,
                    offset=offset,
                    is_preview=is_preview,
                    preview_fields=preview_fields
                )

                if not is_preview and articles_result and isinstance(articles_result[0], Articles):
                    articles_schema = [ArticleReadSchema.model_validate(article) for article in articles_result]
                else:
                    articles_schema = articles_result

                return {
                    'success': True,
                    'message': '獲取分類文章成功',
                    'articles': articles_schema
                }
        except Exception as e:
            error_msg = f"獲取分類文章失敗, category={category}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'articles': []
            }

    def find_articles_by_tags(self,
                              tags: List[str],
                              limit: Optional[int] = None,
                              offset: Optional[int] = None,
                              sort_by: Optional[str] = None,
                              sort_desc: bool = False,
                              is_preview: bool = False,
                              preview_fields: Optional[List[str]] = None
                              ) -> Dict[str, Any]:
        """根據標籤獲取文章 (OR 邏輯)，支援分頁、排序和預覽"""
        if not tags:
            return {'success': False, 'message': '未提供標籤', 'articles': []}
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))

                articles_result = article_repo.find_by_tags(
                    tags=tags,
                    limit=limit,
                    offset=offset,
                    is_preview=is_preview,
                    preview_fields=preview_fields
                )

                if not is_preview and articles_result and isinstance(articles_result[0], Articles):
                    articles_schema = [ArticleReadSchema.model_validate(article) for article in articles_result]
                else:
                    articles_schema = articles_result

                return {
                    'success': True,
                    'message': f'獲取標籤 {tags} 的文章成功',
                    'articles': articles_schema
                }
        except AttributeError:
             error_msg = "ArticleRepository 未實現 find_by_tags 方法或參數不符"
             logger.error(error_msg)
             return {'success': False, 'message': error_msg, 'articles': []}
        except DatabaseOperationError as e:
             error_msg = f"依標籤 {tags} 獲取文章時資料庫操作失敗: {str(e)}"
             logger.error(error_msg, exc_info=True)
             return {'success': False, 'message': error_msg, 'articles': []}
        except Exception as e:
            error_msg = f"依標籤獲取文章失敗, Tags={tags}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'articles': []
            }

    def batch_update_articles_by_link(self, article_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量更新文章 (依連結)，返回包含 ArticleReadSchema 列表的結果"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'resultMsg': None
                    }

                repo_result = article_repo.batch_update_by_link(article_data)

                if not repo_result:
                    return {
                        'success': False,
                        'message': '批量更新文章失敗 (內部錯誤)',
                        'resultMsg': None
                    }

                updated_schemas = [ArticleReadSchema.model_validate(a) for a in repo_result.get('updated_articles', [])]

                final_result_msg = repo_result.copy()
                final_result_msg['updated_articles'] = updated_schemas

                return {
                    'success': True,
                    'message': f"批量更新文章完成: {final_result_msg.get('success_count', 0)} 筆成功, {final_result_msg.get('fail_count', 0)} 筆失敗",
                    'resultMsg': final_result_msg
                }
        except ValidationError as e:
            error_msg = f"批量更新文章時資料驗證失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'resultMsg': None}
        except Exception as e:
            error_msg = f"批量更新文章失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'resultMsg': None
            }

    def batch_update_articles_by_ids(self, article_ids: List[int], article_data: Dict[str, Any]) -> Dict[str, Any]:
        """批量更新文章 (依ID列表)，返回包含 ArticleReadSchema 列表的結果"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'resultMsg': None
                    }

                validated_data = self.validate_article_data(article_data, is_update=True)
                repo_result = article_repo.batch_update_by_ids(article_ids, validated_data)

                if not repo_result:
                    return {
                        'success': False,
                        'message': '批量更新文章失敗 (內部錯誤)',
                        'resultMsg': None
                    }

                updated_schemas = [ArticleReadSchema.model_validate(a) for a in repo_result.get('updated_articles', [])]

                final_result_msg = repo_result.copy()
                final_result_msg['updated_articles'] = updated_schemas

                return {
                    'success': True,
                    'message': f"批量更新文章完成: {final_result_msg.get('success_count', 0)} 筆成功, {final_result_msg.get('fail_count', 0)} 筆失敗",
                    'resultMsg': final_result_msg
                }
        except ValidationError as e:
            error_msg = f"批量更新文章時資料驗證失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'resultMsg': None}
        except Exception as e:
            error_msg = f"批量更新文章失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'resultMsg': None
            }

    def delete_article_by_link(self, link: str) -> Dict[str, Any]:
        """根據連結刪除文章"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                    }
                success = article_repo.delete_by_link(link)
                # Delete 不返回對象
                return {
                    'success': success,
                    'message': '刪除文章成功' if success else '刪除文章失敗 (可能不存在)'
                }
        except Exception as e:
            error_msg = f"根據連結刪除文章失敗, link={link}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    def batch_delete_articles(self, article_ids: List[int]) -> Dict[str, Any]:
        """批量刪除文章 (依ID列表)"""
        if not article_ids:
            return {
                'success': True,
                'message': '未提供文章ID，無需刪除',
                'resultMsg': {'success_count': 0, 'fail_count': 0, 'missing_ids': [], 'failed_ids': []}
            }

        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'resultMsg': None
                    }
                deleted_count = 0
                missing_ids = []
                failed_ids = []

                for article_id in article_ids:
                    try:
                        if article_repo.delete(article_id):
                            deleted_count += 1
                        else:
                            missing_ids.append(article_id)
                    except Exception as inner_e:
                        logger.error(f"批量刪除中刪除 ID {article_id} 失敗: {inner_e}")
                        failed_ids.append(article_id)

                fail_count = len(missing_ids) + len(failed_ids)
                success = fail_count == 0
                # Delete 不返回對象
                return {
                    'success': success,
                    'message': f'批量刪除文章完成: {deleted_count} 成功, {fail_count} 失敗 (不存在: {len(missing_ids)}, 錯誤: {len(failed_ids)})',
                    'resultMsg': {
                        'success_count': deleted_count,
                        'fail_count': fail_count,
                        'missing_ids': missing_ids,
                        'failed_ids': failed_ids
                    }
                }
        except Exception as e:
            error_msg = f"批量刪除文章過程中發生錯誤: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'resultMsg': None
            }

    def update_article_tags(self, article_id: int, tags: List[str]) -> Dict[str, Any]:
        """更新文章標籤，返回包含 ArticleReadSchema 的字典"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'article': None
                    }

                tags_str = ','.join(tags) if tags else None
                update_data = {"tags": tags_str}

                validated_data = self.validate_article_data(update_data, is_update=True)

                updated_article_orm = article_repo.update(article_id, validated_data)
                article_to_return_orm = None
                message = ''
                success = False

                if updated_article_orm:
                    session.flush()
                    session.refresh(updated_article_orm)
                    article_to_return_orm = updated_article_orm
                    message = '更新文章標籤成功'
                    success = True
                else:
                    existing_check_orm = article_repo.get_by_id(article_id)
                    if not existing_check_orm:
                        message = '文章不存在，無法更新標籤'
                        success = False
                    else:
                        session.refresh(existing_check_orm)
                        article_to_return_orm = existing_check_orm
                        message = '文章標籤更新成功 (或無變更)'
                        success = True

                article_schema = None
                if article_to_return_orm:
                    article_schema = ArticleReadSchema.model_validate(article_to_return_orm)

                return {
                    'success': success,
                    'message': message,
                    'article': article_schema
                }
        except ValidationError as e:
            error_msg = f"更新文章標籤 ID={article_id} 時資料驗證失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'article': None}
        except Exception as e:
            error_msg = f"更新文章標籤失敗, ID={article_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'article': None
            }

    def get_articles_statistics(self) -> Dict[str, Any]:
        """獲取文章統計信息"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))

                stats = article_repo.get_statistics()
                return {
                    'success': True,
                    'message': '獲取文章統計信息成功',
                    'statistics': stats
                }
        except AttributeError:
             error_msg = "ArticleRepository 未實現 get_statistics 方法"
             logger.error(error_msg)
             return {'success': False, 'message': error_msg, 'statistics': None}
        except DatabaseOperationError as e:
             error_msg = f"獲取文章統計信息時資料庫操作失敗: {str(e)}"
             logger.error(error_msg, exc_info=True)
             return {'success': False, 'message': error_msg, 'statistics': None}
        except Exception as e:
            error_msg = f"獲取文章統計信息失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'statistics': None
            }

    def find_articles_advanced(
        self,
        task_id: Optional[str] = None,
        keywords: Optional[str] = None,
        category: Optional[str] = None,
        date_range: Optional[Tuple[datetime, datetime]] = None,
        is_ai_related: Optional[bool] = None,
        is_scraped: Optional[bool] = None,
        scrape_status: Optional[ArticleScrapeStatus] = None,
        tags: Optional[List[str]] = None,
        source: Optional[str] = None,
        page: int = 1,
        per_page: int = 10,
        sort_by: Optional[str] = None,
        sort_desc: bool = False,
        is_preview: bool = False,
        preview_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """進階搜尋文章 (分頁, 支援預覽)"""
        criteria = {}
        if task_id is not None: criteria['task_id'] = task_id
        if keywords is not None: criteria['search_text'] = keywords
        if category is not None: criteria['category'] = category
        if date_range is not None:
            criteria['published_at'] = {"$gte": date_range[0], "$lte": date_range[1]}
        if is_ai_related is not None: criteria['is_ai_related'] = is_ai_related
        if scrape_status is not None:
            criteria['scrape_status'] = scrape_status
        elif is_scraped is not None:
             criteria['is_scraped'] = is_scraped
        if tags is not None:
            if len(tags) == 1:
                criteria['tags'] = tags[0]
            elif len(tags) > 1:
                 logger.warning("進階搜尋暫不支援多個標籤 (OR 邏輯)，只會使用第一個標籤 (若有)。")
                 criteria['tags'] = tags[0]
        if source is not None: criteria['source'] = source

        try:
            return self.find_articles_paginated(
                page=page,
                per_page=per_page,
                filter_criteria=criteria,
                sort_by=sort_by,
                sort_desc=sort_desc,
                is_preview=is_preview,
                preview_fields=preview_fields
            )
        except Exception as e:
            error_msg = f"進階搜尋文章失敗: {str(e)}"
            return {
                'success': False,
                'message': error_msg,
                'resultMsg': None
            }

    def find_articles_by_title(self,
                               keyword: str,
                               exact_match: bool = False,
                               limit: Optional[int] = None,
                               offset: Optional[int] = None,
                               is_preview: bool = False,
                               preview_fields: Optional[List[str]] = None
                               ) -> Dict[str, Any]:
        """根據標題搜尋文章，支援分頁和預覽"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))

                articles_result = article_repo.search_by_title(
                    keyword=keyword,
                    exact_match=exact_match,
                    limit=limit,
                    offset=offset,
                    is_preview=is_preview,
                    preview_fields=preview_fields
                )
                if not is_preview and articles_result and isinstance(articles_result[0], Articles):
                    articles_schema = [ArticleReadSchema.model_validate(article) for article in articles_result]
                else:
                    articles_schema = articles_result

                return {
                    'success': True,
                    'message': '根據標題搜尋文章成功',
                    'articles': articles_schema
                }
        except AttributeError:
             error_msg = "ArticleRepository 未實現 search_by_title 方法或參數不符"
             logger.error(error_msg)
             return {'success': False, 'message': error_msg, 'articles': []}
        except DatabaseOperationError as e:
             error_msg = f"根據標題搜尋文章時資料庫操作失敗: {str(e)}"
             logger.error(error_msg, exc_info=True)
             return {'success': False, 'message': error_msg, 'articles': []}
        except Exception as e:
            error_msg = f"根據標題搜尋文章失敗, Keyword='{keyword}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'articles': []
            }

    def find_articles_by_keywords(self,
                                  keywords: str,
                                  limit: Optional[int] = None,
                                  offset: Optional[int] = None,
                                  sort_by: Optional[str] = None,
                                  sort_desc: bool = False,
                                  is_preview: bool = False,
                                  preview_fields: Optional[List[str]] = None
                                  ) -> Dict[str, Any]:
        """根據關鍵字搜尋文章(標題/內容/摘要)，支援分頁、排序和預覽"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))

                articles_result = article_repo.search_by_keywords(
                    keywords=keywords,
                    limit=limit,
                    offset=offset,
                    is_preview=is_preview,
                    preview_fields=preview_fields
                )
                if not is_preview and articles_result and isinstance(articles_result[0], Articles):
                    articles_schema = [ArticleReadSchema.model_validate(article) for article in articles_result]
                else:
                    articles_schema = articles_result

                return {
                    'success': True,
                    'message': '根據關鍵字搜尋文章成功',
                    'articles': articles_schema
                }
        except AttributeError:
             error_msg = "ArticleRepository 未實現 search_by_keywords 方法或參數不符"
             logger.error(error_msg)
             return {'success': False, 'message': error_msg, 'articles': []}
        except DatabaseOperationError as e:
             error_msg = f"根據關鍵字搜尋文章時資料庫操作失敗: {str(e)}"
             logger.error(error_msg, exc_info=True)
             return {'success': False, 'message': error_msg, 'articles': []}
        except Exception as e:
            error_msg = f"根據關鍵字搜尋文章失敗, Keywords='{keywords}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'articles': []
            }

    def get_source_statistics(self) -> Dict[str, Any]:
        """獲取來源統計信息"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))

                stats = article_repo.get_source_statistics()
                return {
                    'success': True,
                    'message': '獲取來源統計信息成功',
                    'statistics': stats
                }
        except AttributeError:
             error_msg = "ArticleRepository 未實現 get_source_statistics 方法"
             logger.error(error_msg)
             return {'success': False, 'message': error_msg, 'statistics': None}
        except DatabaseOperationError as e:
             error_msg = f"獲取來源統計信息時資料庫操作失敗: {str(e)}"
             logger.error(error_msg, exc_info=True)
             return {'success': False, 'message': error_msg, 'statistics': None}
        except Exception as e:
            error_msg = f"獲取來源統計信息失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'statistics': None
            }

    def update_article_scrape_status(self, link: str, is_scraped: bool, scrape_status: Optional[ArticleScrapeStatus] = None) -> Dict[str, Any]:
        """更新文章爬取狀態 (依連結)，可選指定狀態"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                success = article_repo.update_scrape_status(link, is_scraped, scrape_status)
                return {
                    'success': success,
                    'message': '更新文章爬取狀態成功' if success else '更新文章爬取狀態失敗 (文章可能不存在或無變更)'
                }
        except Exception as e:
            error_msg = f"更新文章爬取狀態失敗, link={link}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    def find_unscraped_articles(self,
                                task_id: Optional[int] = None,
                                limit: Optional[int] = 100,
                                source: Optional[str] = None,
                                is_preview: bool = False,
                                preview_fields: Optional[List[str]] = None
                                ) -> Dict[str, Any]:
        """獲取未爬取的文章，支援預覽和排序"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }

                articles_result = article_repo.find_unscraped_links(
                    limit=limit,
                    source=source,
                    order_by_status=True,
                    is_preview=is_preview,
                    preview_fields=preview_fields
                )

                if not is_preview and articles_result and isinstance(articles_result[0], Articles):
                    articles_schema = [ArticleReadSchema.model_validate(article) for article in articles_result]
                else:
                    articles_schema = articles_result

                return {
                    'success': True,
                    'message': '獲取未爬取文章成功',
                    'articles': articles_schema
                }
        except Exception as e:
            error_msg = f"獲取未爬取文章失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'articles': []
            }

    def find_scraped_articles(self,
                              task_id: Optional[int] = None,
                              limit: Optional[int] = 100,
                              source: Optional[str] = None,
                              is_preview: bool = False,
                              preview_fields: Optional[List[str]] = None
                              ) -> Dict[str, Any]:
        """獲取已爬取的文章，支援預覽和排序"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }

                articles_result = article_repo.find_scraped_links(
                    limit=limit,
                    source=source,
                    is_preview=is_preview,
                    preview_fields=preview_fields
                )

                if not is_preview and articles_result and isinstance(articles_result[0], Articles):
                    articles_schema = [ArticleReadSchema.model_validate(article) for article in articles_result]
                else:
                    articles_schema = articles_result

                return {
                    'success': True,
                    'message': '獲取已爬取文章成功',
                    'articles': articles_schema
                }
        except Exception as e:
            error_msg = f"獲取已爬取文章失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'articles': []
            }

    def count_unscraped_articles(self, task_id: Optional[int] = None, source: Optional[str] = None) -> Dict[str, Any]:
        """計算未爬取的文章數量"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'count': 0
                    }

                filter_criteria: Dict[str, Any] = {'is_scraped': False}
                if task_id is not None:
                    filter_criteria['task_id'] = task_id
                if source:
                    filter_criteria['source'] = source

                count = article_repo.count(filter_dict=filter_criteria)
                return {
                    'success': True,
                    'message': '計算未爬取文章數量成功',
                    'count': count
                }
        except Exception as e:
            error_msg = f"計算未爬取文章數量失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'count': 0
            }

    def count_scraped_articles(self, task_id: Optional[int] = None, source: Optional[str] = None) -> Dict[str, Any]:
        """計算已爬取的文章數量"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'count': 0
                    }

                filter_criteria: Dict[str, Any] = {'is_scraped': True}
                if task_id is not None:
                    filter_criteria['task_id'] = task_id
                if source:
                    filter_criteria['source'] = source

                count = article_repo.count(filter_dict=filter_criteria)
                return {
                    'success': True,
                    'message': '計算已爬取文章數量成功',
                    'count': count
                }
        except Exception as e:
            error_msg = f"計算已爬取文章數量失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'count': 0
            }

    def find_articles_by_task_id(self,
                                 task_id: int,
                                 is_scraped: Optional[bool] = None,
                                 limit: Optional[int] = None,
                                 offset: Optional[int] = None,
                                 sort_by: Optional[str] = None,
                                 sort_desc: bool = False,
                                 is_preview: bool = False,
                                 preview_fields: Optional[List[str]] = None
                                 ) -> Dict[str, Any]:
        """根據任務ID查詢相關的文章，支援分頁、排序和預覽"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))

                filter_criteria: Dict[str, Any] = {'task_id': task_id}
                if is_scraped is not None:
                    filter_criteria['is_scraped'] = is_scraped

                articles_result = article_repo.find_by_filter(
                    filter_criteria=filter_criteria,
                    limit=limit,
                    offset=offset,
                    sort_by=sort_by,
                    sort_desc=sort_desc,
                    is_preview=is_preview,
                    preview_fields=preview_fields
                )

                if not is_preview and articles_result and isinstance(articles_result[0], Articles):
                    articles_schema = [ArticleReadSchema.model_validate(article) for article in articles_result]
                else:
                    articles_schema = articles_result

                return {
                    'success': True,
                    'message': f'獲取任務 ID={task_id} 的文章成功',
                    'articles': articles_schema
                }
        except ValueError as ve:
            error_msg = f"獲取任務文章失敗: {str(ve)}"
            logger.error(error_msg)
            return {'success': False, 'message': error_msg, 'articles': []}
        except AttributeError:
             error_msg = f"ArticleRepository 未實現所需方法或參數不符 (task_id={task_id})"
             logger.error(error_msg)
             return {'success': False, 'message': error_msg, 'articles': []}
        except DatabaseOperationError as e:
             error_msg = f"根據任務 ID={task_id} 查詢文章時資料庫操作失敗: {str(e)}"
             logger.error(error_msg, exc_info=True)
             return {'success': False, 'message': error_msg, 'articles': []}
        except Exception as e:
            error_msg = f"根據任務 ID={task_id} 查詢文章失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'articles': []
            }

    def count_articles_by_task_id(self, task_id: int, is_scraped: Optional[bool] = None) -> Dict[str, Any]:
        """計算特定任務的文章數量"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))

                count = article_repo.count_articles_by_task_id(task_id=task_id, is_scraped=is_scraped)
                return {
                    'success': True,
                    'message': f'計算任務 ID={task_id} 的文章數量成功',
                    'count': count
                }
        except ValueError as ve:
            error_msg = f"計算任務文章數量失敗: {str(ve)}"
            logger.error(error_msg)
            return {'success': False, 'message': error_msg, 'count': 0}
        except AttributeError:
             error_msg = f"ArticleRepository 未實現 count_articles_by_task_id (task_id={task_id})"
             logger.error(error_msg)
             return {'success': False, 'message': error_msg, 'count': 0}
        except DatabaseOperationError as e:
             error_msg = f"計算任務 ID={task_id} 文章數量時資料庫操作失敗: {str(e)}"
             logger.error(error_msg, exc_info=True)
             return {'success': False, 'message': error_msg, 'count': 0}
        except Exception as e:
            error_msg = f"計算任務 ID={task_id} 文章數量失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'count': 0
            }
