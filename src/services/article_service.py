import logging
from typing import Optional, Dict, Any, List, TypeVar, Tuple, Hashable, Type, cast, Union
from src.models.articles_model import Base, Articles, ArticleScrapeStatus
from src.models.articles_schema import ArticleReadSchema, PaginatedArticleResponse
from datetime import datetime, timedelta
from src.error.errors import DatabaseOperationError, ValidationError, InvalidOperationError
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
        # 驗證資料，若是更新則移除 link 欄位
        if is_update:
            data.pop('link', None)

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
        """
        批量創建或更新文章。
        如果文章連結已存在，則更新；否則創建新文章。
        """
        success_count = 0
        update_count = 0
        fail_count = 0
        # 將這些列表定義在 try 外部，以便 except 塊可以訪問它們
        inserted_articles_orm: List[Articles] = []
        updated_articles_orm: List[Articles] = []
        failed_articles_details: List[Dict[str, Any]] = []
        inserted_schemas: List[ArticleReadSchema] = [] # 將 Schema 列表也定義在外部
        updated_schemas: List[ArticleReadSchema] = []   # 將 Schema 列表也定義在外部

        # 在事務中執行所有操作
        try:
            valid_inserted_orms = [] # 臨時列表，用於收集 refresh 成功的 ORM
            valid_updated_orms = []   # 臨時列表，用於收集 refresh 成功的 ORM

            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))

                for item_data in articles_data:
                    link = item_data.get('link')
                    existing_article = None
                    item_success = False
                    is_update_path = False

                    try:
                        if not link:
                             raise ValidationError("文章資料缺少 'link' 欄位")

                        # 1. 檢查連結是否存在
                        existing_article = article_repo.find_by_link(link)

                        if existing_article:
                            # --- 更新路徑 ---
                            is_update_path = True
                            logger.debug(f"批量處理：連結 '{link}' 已存在，嘗試更新。")
                            # 驗證會移除link後送驗，所以不須額外處理
                            validated_data = self.validate_article_data(item_data, is_update=True)

                            # 調用 repo.update (它會處理驗證和不可變欄位)
                            updated_article = article_repo.update(existing_article.id, validated_data)

                            # repo.update 成功執行 (可能返回 None 表示無變更)
                            update_count += 1
                            if updated_article:
                                updated_articles_orm.append(updated_article)
                            else:
                                logger.debug(f"批量處理：連結 '{link}' 更新完成，無實際數據變更。")
                            item_success = True

                        else:
                            # --- 創建路徑 ---
                            is_update_path = False
                            logger.debug(f"批量處理：連結 '{link}' 不存在，嘗試創建。")
                            validated_data = self.validate_article_data(item_data, is_update=False)

                            # 調用 repo.create
                            new_article = article_repo.create(validated_data)

                            if new_article:
                                inserted_articles_orm.append(new_article)
                                success_count += 1
                                item_success = True
                            else:
                                raise DatabaseOperationError("Repository create 方法返回 None，創建失敗")

                    except (ValidationError, DatabaseOperationError, InvalidOperationError) as e:
                        logger.error(f"批量處理文章 {'更新' if is_update_path else '創建'} 失敗 (Link: {link}): {e}")
                        fail_count += 1
                        failed_articles_details.append({"data": item_data, "error": str(e)})
                    except Exception as e:
                        logger.error(f"批量處理文章時發生未預期錯誤 (Link: {link}): {e}", exc_info=True)
                        fail_count += 1
                        failed_articles_details.append({"data": item_data, "error": f"未預期錯誤: {str(e)}"})

                # --- 在事務內部，循環結束後 ---
                session.flush()

                # Refresh inserted ORMs and collect valid ones
                for article in inserted_articles_orm:
                    if article and not instance_state(article).detached:
                        try:
                            session.refresh(article)
                            valid_inserted_orms.append(article) # Collect successfully refreshed
                        except Exception as refresh_err:
                             logger.error(f"Refresh 插入的文章 ID={getattr(article, 'id', 'N/A')} 失敗: {refresh_err}", exc_info=True)
                             fail_count += 1
                             success_count -= 1
                             failed_articles_details.append({"data": f"ID={getattr(article, 'id', 'N/A')}", "error": f"Refresh 失敗: {refresh_err}"})

                # Refresh updated ORMs and collect valid ones
                for article in updated_articles_orm:
                     if article and not instance_state(article).detached:
                        try:
                            session.refresh(article)
                            valid_updated_orms.append(article) # Collect successfully refreshed
                        except Exception as refresh_err:
                             logger.error(f"Refresh 更新的文章 ID={getattr(article, 'id', 'N/A')} 失敗: {refresh_err}", exc_info=True)
                             fail_count += 1
                             update_count -= 1
                             failed_articles_details.append({"data": f"ID={getattr(article, 'id', 'N/A')}", "error": f"Refresh 失敗: {refresh_err}"})

                # --- 將 ORM 轉換為 Schema (移到事務內部) ---
                inserted_schemas = [ArticleReadSchema.model_validate(a) for a in valid_inserted_orms]
                updated_schemas = [ArticleReadSchema.model_validate(a) for a in valid_updated_orms]

            # --- 事務在此提交或回滾 ---

            # --- 事務外部：構建成功返回結果 ---
            message = (
                f"批量處理文章完成：新增 {success_count} 筆，"
                f"更新 {update_count} 筆，"
                f"失敗 {fail_count} 筆"
            )
            final_result_msg = {
                'success_count': success_count,
                'update_count': update_count,
                'fail_count': fail_count,
                'inserted_articles': inserted_schemas, # 使用在事務內轉換好的列表
                'updated_articles': updated_schemas,   # 使用在事務內轉換好的列表
                'failed_details': failed_articles_details
            }
            overall_success = fail_count == 0

            return {
                'success': overall_success,
                'message': message,
                'resultMsg': final_result_msg
            }

        except Exception as e:
            # 捕獲事務層面或其他未預期的異常
            error_msg = f"批量創建/更新文章過程中發生未預期錯誤: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # 返回通用錯誤結構
            return {
                'success': False,
                'message': error_msg,
                'resultMsg': { # 提供部分結果（如果有的話）
                    'success_count': success_count,
                    'update_count': update_count,
                    'fail_count': fail_count + (len(articles_data) - success_count - update_count - fail_count), # 將未處理的也計入失敗
                    'inserted_articles': [], # 保持外部錯誤時返回空
                    'updated_articles': [], # 保持外部錯誤時返回空
                    'failed_details': failed_articles_details + [{"data": "General Error", "error": str(e)}]
                }
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
