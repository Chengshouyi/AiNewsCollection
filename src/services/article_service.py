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

# 輔助函數，將 ORM 對象轉為字典 (可以根據需要選擇字段)
def article_to_dict(article: Articles) -> Dict[str, Any]:
    if not article:
        return {}
    return {
        "id": article.id,
        "title": article.title,
        "link": article.link,
        "summary": article.summary,
        "content": article.content, # 根據需要決定是否包含 content
        "source": article.source,
        "source_url": article.source_url,
        "category": article.category,
        "published_at": article.published_at,
        "is_ai_related": article.is_ai_related,
        "is_scraped": article.is_scraped,
        "scrape_status": article.scrape_status,
        "tags": article.tags,
        "task_id": article.task_id,
        # 可以添加 created_at, updated_at 等
    }

class ArticleService(BaseService[Articles]):
    """文章服務，提供文章相關業務邏輯"""
    
    def __init__(self, db_manager=None):
        super().__init__(db_manager)

    def _get_repository_mapping(self) -> Dict[str, Tuple[Type[BaseRepository], Type[Base]]]:
        """提供儲存庫映射"""
        return {
            'Article': (ArticlesRepository, Articles)
        }
    
    def create_article(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """創建新文章，若連結已存在則更新，返回文章數據字典"""
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
                        
                    # 在 repo 上執行驗證
                    validated_data = article_repo.validate_data(article_data_for_validation, SchemaType.UPDATE)
                    
                    updated_article = article_repo.update(existing_article.id, validated_data)
                    # commit 由 _transaction 處理
                    if updated_article:
                        return {
                            'success': True,
                            'message': '文章已存在，更新成功',
                            'article': article_to_dict(updated_article) # 返回字典
                        }
                    else:
                        # 無變更或更新失敗，返回現有文章的字典
                        session.refresh(existing_article) # 確保 existing_article 是最新狀態
                        return {
                            'success': True, # 標記為 True 因為文章已存在，只是未更新或無變更
                            'message': '文章已存在，無變更或更新失敗',
                            'article': article_to_dict(existing_article) # 返回字典
                        }
                else:
                    validated_data = article_repo.validate_data(article_data, SchemaType.CREATE)
                    new_article = article_repo.create(validated_data)
                    
                    if new_article:
                        # 確保新創建的文章數據完整 (尤其是自動生成的 ID)
                        session.flush() # 將新對象寫入數據庫以獲取 ID
                        session.refresh(new_article) # 從數據庫刷新對象狀態
                        return {
                            'success': True,
                            'message': '文章創建成功',
                            'article': article_to_dict(new_article) # 返回字典
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
        """批量創建新文章 (儲存庫應處理創建或更新邏輯)"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                
                # batch_create 內部應包含驗證邏輯
                result = article_repo.batch_create(articles_data)
                # commit 由 _transaction 處理
                
                message = (
                    f"批量處理文章完成：新增 {result.get('success_count', 0)} 筆，"
                    f"更新 {result.get('update_count', 0)} 筆，"
                    f"失敗 {result.get('fail_count', 0)} 筆"
                )
                
                success = result.get('fail_count', 0) == 0
                return {
                    'success': success,
                    'message': message,
                    'resultMsg': result
                }
        except ValidationError as e: # 假設 batch_create 可能拋出驗證錯誤
            error_msg = f"批量創建文章時資料驗證失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {'success': False, 'message': error_msg, 'resultMsg': None}
        except DatabaseOperationError as e:
            error_msg = f"批量創建文章時資料庫操作失敗: {str(e)}"
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
            # 讀取操作通常不需要事務，但為保持一致性，仍使用 _transaction
            # 如果效能是考量，可以考慮移除 transaction
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                
                articles = article_repo.get_all(limit=limit, offset=offset)
                return {
                    'success': True,
                    'message': '獲取所有文章成功',
                    'articles': articles
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
        """根據ID獲取文章"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                
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
        """更新文章"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                
                # 先檢查文章是否存在
                existing_article = article_repo.get_by_id(article_id)
                if not existing_article:
                    return {
                        'success': False,
                        'message': '文章不存在，無法更新',
                        'article': None
                    }

                # 在 repo 上執行驗證
                validated_data = article_repo.validate_data(article_data, SchemaType.UPDATE)

                updated_article = article_repo.update(article_id, validated_data)
                # commit 由 _transaction 處理
                
                # update 成功會返回更新後的物件，若無變更可能返回 None 或原物件 (依 repo 實現)
                # 這裡假設成功更新一定返回物件，若返回 None 則認為更新失敗或無變更
                if updated_article:
                    return {
                        'success': True,
                        'message': '文章更新成功',
                        'article': updated_article
                    }
                else:
                    # 如果 update 返回 None，但文章確實存在，則認為無變更或更新邏輯問題
                    logger.warning(f"更新文章 ID={article_id} 時 repo.update 返回 None，可能無變更或更新失敗。")
                    return {
                        'success': True, # 操作本身可能沒錯，只是無實際變更
                        'message': '文章更新操作完成 (可能無實際變更)',
                        'article': existing_article # 返回更新前的狀態
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
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
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
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
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
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
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
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
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
        if not tags:
            return {'success': False, 'message': '未提供標籤', 'articles': []}
        try:
            with self._transaction() as session: 
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session)) 
                
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
                    'message': f'獲取標籤 {tags} 的文章成功',
                    'articles': articles_to_return
                }
        except AttributeError:
             error_msg = "ArticleRepository 未實現 find_by_tags 方法"
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
        """批量更新文章 (依連結)"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
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
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'resultMsg': None
                    }
                validated_data = article_repo.validate_data(article_data, SchemaType.UPDATE)
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
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
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
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
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

    def advanced_search_articles(
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
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_desc: bool = False
    ) -> Dict[str, Any]:
        """進階搜尋文章"""
        criteria = {}
        if task_id is not None: criteria['task_id'] = task_id
        if keywords is not None: criteria['keywords'] = keywords
        if category is not None: criteria['category'] = category
        if date_range is not None: criteria['date_range'] = date_range
        if is_ai_related is not None: criteria['is_ai_related'] = is_ai_related
        if scrape_status is not None:
            criteria['scrape_status'] = scrape_status
        elif is_scraped is not None:
             criteria['is_scraped'] = is_scraped
        if tags is not None: criteria['tags'] = tags
        if source is not None: criteria['source'] = source

        try:
            with self._transaction() as session: 
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                
                articles, total_count = article_repo.get_all(
                    filter_criteria=criteria, 
                    limit=limit, 
                    offset=offset, 
                    sort_by=sort_by, 
                    sort_desc=sort_desc
                )
                
                return {
                    'success': True,
                    'message': '進階搜尋文章成功',
                    'articles': articles,
                    'total_count': total_count
                }
        except AttributeError:
             error_msg = "ArticleRepository 未實現 advanced_search 方法"
             logger.error(error_msg)
             return {'success': False, 'message': error_msg, 'articles': [], 'total_count': 0}
        except DatabaseOperationError as e:
             error_msg = f"進階搜尋文章時資料庫操作失敗: {str(e)}"
             logger.error(error_msg, exc_info=True)
             return {'success': False, 'message': error_msg, 'articles': [], 'total_count': 0}
        except Exception as e:
            error_msg = f"進階搜尋文章失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'articles': [],
                'total_count': 0
            }

    def search_articles_by_title(self, keyword: str, exact_match: bool = False, limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        """根據標題搜尋文章"""
        try:
            # Pass session to _get_repository
            with self._transaction() as session: 
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                
                articles = article_repo.search_by_title(
                    keyword=keyword, 
                    exact_match=exact_match, 
                    limit=limit, 
                    offset=offset
                )
                return {
                    'success': True,
                    'message': '根據標題搜尋文章成功',
                    'articles': articles
                }
        except AttributeError:
             error_msg = "ArticleRepository 未實現 search_by_title 方法"
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

    def search_articles_by_keywords(self, keywords: str, limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        """根據關鍵字搜尋文章(標題和內容)"""
        try:
            # Pass session to _get_repository
            with self._transaction() as session: 
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                
                articles = article_repo.search_by_keywords(
                    keywords=keywords, 
                    limit=limit, 
                    offset=offset
                )
                return {
                    'success': True,
                    'message': '根據關鍵字搜尋文章成功',
                    'articles': articles
                }
        except AttributeError:
             error_msg = "ArticleRepository 未實現 search_by_keywords 方法"
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
            # Pass session to _get_repository
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

    def update_article_scrape_status(self, link: str, is_scraped: bool, scrape_status: ArticleScrapeStatus) -> Dict[str, Any]:
        """更新文章爬取狀態 (依連結)"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }

                success = article_repo.update_scrape_status(link, is_scraped, scrape_status)
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


    def get_unscraped_articles(self, limit: Optional[int] = 100, source: Optional[str] = None) -> Dict[str, Any]:
        """獲取未爬取的文章"""
        try:
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
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
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
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
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
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
            with self._transaction() as session:
                article_repo = cast(ArticlesRepository, self._get_repository('Article', session))
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
