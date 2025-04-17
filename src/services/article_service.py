import logging
from typing import Optional, Dict, Any, List, TypeVar, Tuple, Hashable, Type, cast
from src.models.articles_model import Base, Articles, ArticleScrapeStatus
from datetime import datetime, timedelta
from src.error.errors import DatabaseOperationError, ValidationError
from src.database.articles_repository import ArticlesRepository
from sqlalchemy import or_
from sqlalchemy.orm import Session
from src.services.base_service import BaseService
from src.database.base_repository import BaseRepository, SchemaType

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 通用類型變數，用於泛型方法
T = TypeVar('T', bound=Base)

class ArticleService(BaseService[Articles]):
    """文章服務，提供文章相關業務邏輯"""
    
    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    def _get_repository_mapping(self) -> Dict[str, Tuple[Type[BaseRepository], Type[Base]]]:
        """提供儲存庫映射"""
        return {
            'Article': (ArticlesRepository, Articles)
        }
    
    def _get_repositories(self) -> ArticlesRepository:
        """獲取文章資料庫訪問對象"""
        repo = cast(ArticlesRepository, super()._get_repository('Article'))
        return repo
    
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
        """創建新文章，若連結已存在則更新"""
        try:
            with self._transaction() as session:
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'article': None
                    }
                
                link = article_data.get('link')
                existing_article = None
                if link:
                    existing_article = article_repo.find_by_link(link)

                if existing_article:
                    logger.info(f"文章連結 '{link}' 已存在，將執行更新操作。")
                    # 業務邏輯：重複爬取的文章，預設更新，移除 link 欄位，避免驗證時出現錯誤
                    article_data.pop('link')
                    validated_data = self.validate_article_data(article_data, is_update=True)
                    updated_article = article_repo.update(existing_article.id, validated_data)
                    if updated_article:
                        session.flush()
                        return {
                            'success': True,
                            'message': '文章已存在，更新成功',
                            'article': updated_article
                        }
                    else:
                        return {
                            'success': False,
                            'message': '文章已存在，但更新失敗或無變更',
                            'article': existing_article
                        }
                else:
                    validated_data = self.validate_article_data(article_data, is_update=False)
                    new_article = article_repo.create(validated_data)
                    if new_article:
                        session.flush()
                        return {
                            'success': True,
                            'message': '文章創建成功',
                            'article': new_article
                        }
                    else:
                        return {
                            'success': False,
                            'message': '文章創建失敗',
                            'article': None
                        }

        except ValidationError as e:
            error_msg = f"創建或更新文章時資料驗證失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'article': None}
        except Exception as e:
            error_msg = f"創建或更新文章失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'article': None
            }

    def batch_create_articles(self, articles_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量創建新文章 (儲存庫應處理創建或更新邏輯)"""
        try:
            with self._transaction() as session:
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'resultMsg': None
                    }
                
                result = article_repo.batch_create(articles_data)
                message = (
                    f"批量處理文章完成：新增 {result['success_count']} 筆，"
                    f"更新 {result['update_count']} 筆，"
                    f"失敗 {result['fail_count']} 筆"
                )
                if result['success_count'] > 0:
                    session.flush()
                return {
                    'success': True,
                    'message': message,
                    'resultMsg': result
                }
        except ValidationError as e:
            error_msg = f"批量創建文章時資料驗證失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'resultMsg': None}
        except Exception as e:
            error_msg = f"批量創建文章失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'resultMsg': None
            }

    def get_all_articles(self, limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        """獲取所有文章"""
        try:
            with self._transaction():
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }
                
                articles = article_repo.get_all(limit=limit, offset=offset)
                return {
                    'success': True,
                    'message': '獲取所有文章成功',
                    'articles': articles
                }
        except Exception as e:
            error_msg = f"獲取所有文章失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'articles': []
            }

    def get_article_by_id(self, article_id: int) -> Dict[str, Any]:
        """根據ID獲取文章"""
        try:
            with self._transaction():
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'article': None
                    }
                
                article = article_repo.get_by_id(article_id)
                if article:
                    return {
                        'success': True,
                        'message': '獲取文章成功',
                        'article': article
                    }
                return {
                    'success': False,
                    'message': '文章不存在',
                    'article': None
                }
        except Exception as e:
            error_msg = f"獲取文章失敗, ID={article_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'article': None
            }

    def update_article(self, article_id: int, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新文章"""
        try:
            with self._transaction() as session:
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'article': None
                    }
                
                validated_data = self.validate_article_data(article_data, is_update=True)

                article = article_repo.update(article_id, validated_data)
                if not article:
                    existing_check = article_repo.get_by_id(article_id)
                    if not existing_check:
                        return {
                            'success': False,
                            'message': '文章不存在，無法更新',
                            'article': None
                        }
                    else:
                        session.flush()
                        return {
                            'success': True,
                            'message': '文章更新成功 (或無變更)',
                            'article': existing_check
                        }

                else:
                    return {
                        'success': True,
                        'message': '文章更新成功',
                        'article': article
                    }
        except ValidationError as e:
            error_msg = f"更新文章時資料驗證失敗, ID={article_id}: {str(e)}"
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
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                    }
                
                success = article_repo.delete(article_id)
                if success:
                    session.flush()
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
        """根據連結獲取文章"""
        try:
            with self._transaction():
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'article': None
                    }
                article = article_repo.find_by_link(link)
                if article:
                    return {
                        'success': True,
                        'message': '獲取文章成功',
                        'article': article
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

    def get_articles_paginated(self, page: int, per_page: int, sort_by: Optional[str] = None, sort_desc: bool = False) -> Dict[str, Any]:
        """分頁獲取文章"""
        try:
            with self._transaction():
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'resultMsg': None
                    }
                
                result = article_repo.get_paginated({}, page, per_page, sort_by, sort_desc)
                if not result:
                    return {
                        'success': False,
                        'message': '分頁獲取文章失敗 (內部錯誤)',
                        'resultMsg': None
                    }
                return {
                    'success': True,
                    'message': '分頁獲取文章成功',
                    'resultMsg': result
                }
        except Exception as e:
            error_msg = f"分頁獲取文章失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'resultMsg': None
            }

    def get_ai_related_articles(self, limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        """獲取所有AI相關的文章"""
        try:
            with self._transaction():
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }
                articles = article_repo.get_all({"is_ai_related": True}, limit=limit, offset=offset)
                return {
                    'success': True,
                    'message': '獲取AI相關文章成功',
                    'articles': articles
                }
        except Exception as e:
            error_msg = f"獲取AI相關文章失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                 'success': False,
                 'message': error_msg,
                 'articles': []
             }

    def get_articles_by_category(self, category: str, limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        """根據分類獲取文章"""
        try:
            with self._transaction():
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }
                articles = article_repo.get_all({'category': category}, limit=limit, offset=offset)
                return {
                    'success': True,
                    'message': '獲取分類文章成功',
                    'articles': articles
                }
        except Exception as e:
            error_msg = f"獲取分類文章失敗, category={category}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'articles': []
            }

    def get_articles_by_tags(self, tags: List[str], limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        """根據標籤獲取文章"""
        try:
            with self._transaction():
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }
                all_articles_with_tags = article_repo.find_by_tags(tags)

                if not all_articles_with_tags:
                    articles_to_return = []
                elif offset is not None and limit is not None:
                    articles_to_return = all_articles_with_tags[offset:offset + limit]
                elif limit is not None:
                    articles_to_return = all_articles_with_tags[:limit]
                elif offset is not None:
                    articles_to_return = all_articles_with_tags[offset:]
                else:
                    articles_to_return = all_articles_with_tags

                return {
                    'success': True,
                    'message': '獲取標籤文章成功',
                    'articles': articles_to_return
                }
        except Exception as e:
            error_msg = f"根據標籤獲取文章失敗, tags={tags}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'articles': []
            }

    def batch_update_articles_by_link(self, article_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量更新文章 (依連結)"""
        try:
            with self._transaction() as session:
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'resultMsg': None
                    }
                result = article_repo.batch_update_by_link(article_data)
                if not result:
                    return {
                        'success': False,
                        'message': '批量更新文章失敗 (內部錯誤)',
                        'resultMsg': None
                    }
                if result['success_count'] > 0:
                    session.flush()
                return {
                    'success': True,
                    'message': f"批量更新文章成功: {result.get('success_count', 0)} 筆成功, {result.get('fail_count', 0)} 筆失敗",
                    'resultMsg': result
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
        """批量更新文章 (依ID列表，使用相同資料)"""
        try:
            with self._transaction() as session:
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'resultMsg': None
                    }
                validated_data = self.validate_article_data(article_data, is_update=True)
                result = article_repo.batch_update_by_ids(article_ids, validated_data)
                if not result:
                    return {
                        'success': False,
                        'message': '批量更新文章失敗 (內部錯誤)',
                        'resultMsg': None
                    }
                if result['success_count'] > 0:
                    session.flush()
                return {
                    'success': True,
                    'message': f"批量更新文章成功: {result.get('success_count', 0)} 筆成功, {result.get('fail_count', 0)} 筆失敗",
                    'resultMsg': result
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
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                    }
                success = article_repo.delete_by_link(link)
                if success:
                    session.flush()
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
                'resultMsg': {'success_count': 0, 'fail_count': 0, 'missing_ids': []}
            }
        
        try:
            with self._transaction() as session:
                article_repo = self._get_repositories()
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
                if success:
                    session.flush()
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
        """更新文章標籤"""
        try:
            with self._transaction() as session:
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'article': None
                    }
                tags_str = ','.join(tags)
                update_data = {"tags": tags_str}

                updated_article = article_repo.update(article_id, update_data)

                if not updated_article:
                    existing_check = article_repo.get_by_id(article_id)
                    if not existing_check:
                        return {
                            'success': False,
                            'message': '文章不存在，無法更新標籤',
                            'article': None
                        }
                    else:
                        return {
                            'success': True,
                            'message': '文章標籤更新成功 (或無變更)',
                            'article': existing_check
                        }
                if updated_article:
                    session.flush()
                return {
                    'success': True,
                    'message': '更新文章標籤成功',
                    'article': updated_article
                }
        except Exception as e:
            error_msg = f"更新文章標籤失敗, ID={article_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'article': None
            }

    def get_articles_statistics(self) -> Dict[str, Any]:
        """獲取文章統計資訊"""
        try:
            with self._transaction():
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'resultMsg': None
                    }
                total_count = article_repo.count()
                ai_related_count = article_repo.count({"is_ai_related": True})
                category_distribution = article_repo.get_category_distribution()
                week_ago = datetime.now() - timedelta(days=7)
                recent_count = article_repo.count({"published_at": {"$gte": week_ago}})
                
                return {
                    'success': True,
                    'message': '獲取文章統計資訊成功',
                    'resultMsg': {
                        'total_articles': total_count,
                        'ai_related_articles': ai_related_count,
                        'category_distribution': category_distribution,
                        'recent_articles': recent_count
                    }
                }
        except Exception as e:
            error_msg = f"獲取文章統計資訊失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'resultMsg': None
            }

    def advanced_search_articles(
        self,
        task_id: Optional[str] = None,
        keywords: Optional[str] = None,
        category: Optional[str] = None,
        date_range: Optional[Tuple[datetime, datetime]] = None,
        is_ai_related: Optional[bool] = None,
        is_scraped: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        source: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_desc: bool = False
    ) -> Dict[str, Any]:
        """進階搜尋文章"""
        try:
            with self._transaction():
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }
                query = article_repo.session.query(Articles)
                
                if keywords:
                    query = query.filter(or_(
                        Articles.title.like(f"%{keywords}%"),
                        Articles.content.like(f"%{keywords}%")
                    ))
                    
                if task_id:
                    query = query.filter(Articles.task_id == task_id)
                    
                if category:
                    query = query.filter(Articles.category == category)
                    
                if date_range:
                    start_date, end_date = date_range
                    query = query.filter(Articles.published_at.between(start_date, end_date))
                    
                if is_ai_related is not None:
                    query = query.filter(Articles.is_ai_related == is_ai_related)
                    
                if is_scraped is not None:
                    query = query.filter(Articles.is_scraped == is_scraped)
                    
                if tags:
                    for tag in tags:
                        query = query.filter(Articles.tags.like(f"%{tag}%"))
                        
                if source:
                    query = query.filter(Articles.source == source)
                    
                if offset:
                    query = query.offset(offset)
                    
                if limit:
                    query = query.limit(limit)
                    
                result = query.all()
                if not result:
                    return {
                        'success': False,
                        'message': '進階搜尋文章失敗',
                        'articles': []
                    }
                return {
                    'success': True,
                    'message': '進階搜尋文章成功',
                    'articles': result
                }
        except Exception as e:
            error_msg = f"進階搜尋文章失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise e

    def get_articles_by_task(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """根據任務ID獲取文章
        
        Args:
            filters: 過濾條件，包含：
                - task_id: 任務ID
                - is_scraped: 是否已抓取內容
                - is_preview: 是否只返回預覽資料
                
        Returns:
            Dict[str, Any]: 包含文章列表的字典
        """
        try:
            with self._transaction():
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }

                task_id = filters.get('task_id')
                if not task_id:
                    return {
                        'success': False,
                        'message': '必須提供任務ID (task_id)',
                        'articles': []
                    }

                query_filters = {'task_id': task_id}
                if 'is_scraped' in filters:
                    is_scraped_filter = filters['is_scraped']
                    if isinstance(is_scraped_filter, str):
                        is_scraped_filter = is_scraped_filter.lower() in ['true', '1', 'yes']
                    query_filters['is_scraped'] = bool(is_scraped_filter)

                articles = article_repo.get_all(filter_criteria=query_filters)
                logger.debug(f"查詢條件: {query_filters}, 找到 {len(articles)} 筆文章")

                if filters.get('is_preview'):
                    preview_articles = []
                    for article in articles:
                        preview_articles.append({
                            'id': getattr(article, 'id', None),
                            'title': getattr(article, 'title', None),
                            'link': getattr(article, 'link', None),
                            'source': getattr(article, 'source', None),
                            'published_at': getattr(article, 'published_at', None),
                            'is_scraped': getattr(article, 'is_scraped', None)
                        })
                    articles_to_return = preview_articles
                    message = '獲取文章預覽成功'
                else:
                    articles_to_return = articles
                    message = '獲取完整文章成功'

                return {
                    'success': True,
                    'message': message,
                    'articles': articles_to_return
                }
        except Exception as e:
            error_msg = f"獲取任務相關文章失敗, task_id={filters.get('task_id')}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'articles': []
            }

    def search_articles_by_title(self, keyword: str, exact_match: bool = False, limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        """根據標題搜索文章"""
        try:
            with self._transaction():
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }

                articles = article_repo.search_by_title(keyword, exact_match)

                if articles:
                    if offset is not None:
                        articles = articles[offset:]
                    if limit is not None:
                        articles = articles[:limit]

                return {
                    'success': True,
                    'message': '搜索文章成功',
                    'articles': articles
                }
        except Exception as e:
            error_msg = f"根據標題搜索文章失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'articles': []
            }

    def search_articles_by_keywords(self, keywords: str, limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        """根據關鍵字搜索文章 (標題或內容)"""
        try:
            with self._transaction():
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }

                articles = article_repo.search_by_keywords(keywords)

                if articles:
                    if offset is not None:
                        articles = articles[offset:]
                    if limit is not None:
                        articles = articles[:limit]

                return {
                    'success': True,
                    'message': '搜索文章成功',
                    'articles': articles
                }
        except Exception as e:
            error_msg = f"根據關鍵字搜索文章失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'articles': []
            }

    def get_source_statistics(self) -> Dict[str, Any]:
        """獲取各來源的爬取統計"""
        try:
            with self._transaction():
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'stats': {}
                    }

                stats = article_repo.get_source_statistics()
                return {
                    'success': True,
                    'message': '獲取來源統計成功',
                    'stats': stats
                }
        except Exception as e:
            error_msg = f"獲取來源統計失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'stats': {}
            }

    def update_article_scrape_status(self, link: str, is_scraped: bool = True) -> Dict[str, Any]:
        """更新文章爬取狀態 (依連結)"""
        try:
            with self._transaction() as session:
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }

                success = article_repo.update_scrape_status(link, is_scraped)
                if success:
                    session.flush()
                    return {
                        'success': True,
                        'message': '更新文章爬取狀態成功'
                    }
                return {
                    'success': False,
                    'message': '更新文章爬取狀態失敗 (文章可能不存在)'
                }
        except Exception as e:
            error_msg = f"更新文章爬取狀態失敗, link={link}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }

    def batch_mark_articles_as_scraped(self, links: List[str]) -> Dict[str, Any]:
        """批量將文章標記為已爬取 (依連結列表)"""
        if not links:
            return {
                'success': True,
                'message': '未提供連結，無需標記',
                'resultMsg': {'success_count': 0, 'fail_count': 0}
            }
        try:
            with self._transaction() as session:
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'resultMsg': None
                    }

                result = article_repo.batch_mark_as_scraped(links)
                success_count = result.get('success_count', 0)
                fail_count = result.get('fail_count', 0)
                if success_count > 0:
                    session.flush()
                return {
                    'success': fail_count == 0,
                    'message': f"批量標記文章為已爬取完成: {success_count} 成功, {fail_count} 失敗",
                    'resultMsg': result
                }
        except Exception as e:
            error_msg = f"批量標記文章為已爬取失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'resultMsg': None
            }

    def get_unscraped_articles(self, limit: Optional[int] = 100, source: Optional[str] = None) -> Dict[str, Any]:
        """獲取未爬取的文章"""
        try:
            with self._transaction():
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }

                filter_criteria: Dict[str, Any] = {'is_scraped': False}
                if source:
                    filter_criteria['source'] = source

                articles = article_repo.get_all(
                    filter_criteria=filter_criteria,
                    limit=limit,
                    sort_by='published_at',
                    sort_desc=False
                )

                return {
                    'success': True,
                    'message': '獲取未爬取文章成功',
                    'articles': articles
                }
        except Exception as e:
            error_msg = f"獲取未爬取文章失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'articles': []
            }

    def get_scraped_articles(self, limit: Optional[int] = 100, source: Optional[str] = None) -> Dict[str, Any]:
        """獲取已爬取的文章"""
        try:
            with self._transaction():
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }

                filter_criteria: Dict[str, Any] = {'is_scraped': True}
                if source:
                    filter_criteria['source'] = source

                articles = article_repo.get_all(
                    filter_criteria=filter_criteria,
                    limit=limit,
                    sort_by='updated_at',
                    sort_desc=True
                )

                return {
                    'success': True,
                    'message': '獲取已爬取文章成功',
                    'articles': articles
                }
        except Exception as e:
            error_msg = f"獲取已爬取文章失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'articles': []
            }

    def count_unscraped_articles(self, source: Optional[str] = None) -> Dict[str, Any]:
        """計算未爬取的文章數量"""
        try:
            with self._transaction():
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'count': 0
                    }

                filter_criteria: Dict[str, Any] = {'is_scraped': False}
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

    def count_scraped_articles(self, source: Optional[str] = None) -> Dict[str, Any]:
        """計算已爬取的文章數量"""
        try:
            with self._transaction():
                article_repo = self._get_repositories()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'count': 0
                    }

                filter_criteria: Dict[str, Any] = {'is_scraped': True}
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
