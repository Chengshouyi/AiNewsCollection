import logging
from typing import Optional, Dict, Any, List, TypeVar, Tuple, Hashable, Type, cast
from src.models.articles_model import Base, Articles
from datetime import datetime, timedelta
from src.error.errors import DatabaseOperationError
from src.database.articles_repository import ArticlesRepository
from sqlalchemy import or_
from sqlalchemy.orm import Session
from src.services.base_service import BaseService
from src.database.base_repository import BaseRepository

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
    
    def _get_repository(self) -> ArticlesRepository:
        """獲取文章資料庫訪問對象"""
        return cast(ArticlesRepository, super()._get_repository('Article'))
    
    def insert_article(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """創建新文章"""
        try:
            with self._transaction():
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'article': None
                    }
                
                result = article_repo.create(article_data)
                return {
                    'success': True,
                    'message': '文章創建成功',
                    'article': result
                }
        except Exception as e:
            error_msg = f"創建文章失敗: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'article': None
            }

    def batch_create_articles(self, articles_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量創建新文章"""
        try:
            with self._transaction():
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'resultMsg': None
                    }
                
                result = article_repo.batch_create(articles_data)
                return {
                    'success': True,
                    'message': '批量創建文章成功',
                    'resultMsg': result
                }
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
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }
                
                articles = article_repo.get_by_filter({}, limit=limit, offset=offset)
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
                article_repo = self._get_repository()
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
            with self._transaction():
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'article': None
                    }
                
                article = article_repo.update(article_id, article_data)
                if not article:
                    return {
                        'success': False,
                        'message': '文章不存在',
                        'article': None
                    }
                else:
                    return {
                        'success': True,
                        'message': '文章更新成功',
                        'article': article
                    }
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
            with self._transaction():
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                    }
                
                success = article_repo.delete(article_id)
                return {
                    'success': success,
                    'message': '文章刪除成功' if success else '文章不存在',
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
                article_repo = self._get_repository()
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
            logger.error(f"根據連結獲取文章失敗，link={link}: {e}")
            raise e

    def get_articles_paginated(self, page: int, per_page: int, sort_by: Optional[str] = None, sort_desc: bool = False) -> Dict[str, Any]:
        """分頁獲取文章"""
        try:
            with self._transaction():
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'resultMsg': None
                    }
                
                result = article_repo.get_paginated_by_filter({}, page, per_page, sort_by, sort_desc)
                if not result:
                    return {
                        'success': False,
                        'message': '分頁獲取文章失敗',
                        'resultMsg': None
                    }
                return {
                    'success': True,
                    'message': '分頁獲取文章成功',
                    'resultMsg': result
                }
        except Exception as e:
            logger.error(f"分頁獲取文章失敗: {e}")
            raise e

    def get_ai_related_articles(self, limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        """獲取所有AI相關的文章"""
        try:
            with self._transaction():
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }
                result = article_repo.get_by_filter({"is_ai_related": True}, limit=limit, offset=offset)
                if not result:
                    return {
                        'success': False,
                        'message': '獲取AI相關文章失敗',
                        'articles': []
                    }
                return {
                    'success': True,
                    'message': '獲取AI相關文章成功',
                    'articles': result
                }
        except Exception as e:
            logger.error(f"獲取AI相關文章失敗: {e}")
            raise e

    def get_articles_by_category(self, category: str, limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        """根據分類獲取文章"""
        try:
            with self._transaction():
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }
                result = article_repo.find_by_category(category)
                if not result:
                    return {
                        'success': False,
                        'message': '獲取分類文章失敗',
                        'articles': []
                    }
                return {
                    'success': True,
                    'message': '獲取分類文章成功',
                    'articles': result
                }
        except Exception as e:
            logger.error(f"獲取分類文章失敗: {e}")
            raise e

    def get_articles_by_tags(self, tags: List[str], limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        """根據標籤獲取文章"""
        try:
            with self._transaction():
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }
                articles = article_repo.find_by_tags(tags)
                if not articles:
                    return {
                        'success': False,
                        'message': '獲取標籤文章失敗',
                        'articles': []
                    }
                if offset is not None and limit is not None:
                    return {
                        'success': True,
                        'message': '獲取標籤文章成功',
                        'articles': articles[offset:offset + limit]
                    }
                elif limit is not None:
                    return {
                        'success': True,
                        'message': '獲取標籤文章成功',
                        'articles': articles[:limit]
                    }
                return {
                    'success': True,
                    'message': '獲取標籤文章成功',
                    'articles': articles
                }
        except Exception as e:
            logger.error(f"根據標籤獲取文章失敗: {e}")
            raise e

    def batch_update_articles(self, article_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量更新文章
        Args:
            article_data: 文章資料(使用同一筆資料更新多筆文章)

        Returns:
            Dict[str, Any]: 包含成功和失敗資訊的字典
        """
        try:
            with self._transaction():
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'resultMsg': None
                    }
                result = article_repo.batch_update(article_data)
                if not result:
                    return {
                        'success': False,
                        'message': '批量更新文章失敗',
                        'resultMsg': None
                    }   
                return {
                    'success': True,
                    'message': '批量更新文章成功',
                    'resultMsg': result
                }
        except Exception as e:
            logger.error(f"批量更新文章失敗: {e}")
            raise e
        

    def batch_update_articles_by_ids(self, article_ids: List[int], article_data: Dict[str, Any]) -> Dict[str, Any]:
        """批量更新文章
        Args:
            article_ids: 文章ID列表
            article_data: 文章資料(使用同一筆資料更新多筆文章)

        Returns:
            Dict[str, Any]: 包含成功和失敗資訊的字典
        """
        try:
            with self._transaction():
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'resultMsg': None
                    }
                result = article_repo.batch_update_by_ids(article_ids, article_data)
                if not result:
                    return {
                        'success': False,
                        'message': '批量更新文章失敗',
                        'resultMsg': None
                    }
                return {
                    'success': True,
                    'message': '批量更新文章成功',
                    'resultMsg': result
                }
        except Exception as e:
            logger.error(f"批量更新文章失敗: {e}")
            raise e

    def delete_article_by_link(self, link: str) -> Dict[str, Any]:
        """根據連結刪除文章"""
        try:
            with self._transaction():
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                    }
                result = article_repo.delete_by_link(link)
                if not result:
                    return {
                        'success': False,
                        'message': '刪除文章失敗'
                    }
                return {
                    'success': True,
                    'message': '刪除文章成功'
                }
        except Exception as e:
            logger.error(f"根據連結刪除文章失敗: {e}")
            raise e

    def batch_delete_articles(self, article_ids: List[int]) -> Dict[str, Any]:
        """批量刪除文章"""
        if not article_ids:
            return {
                'success': False,
                'message': '無法取得資料庫存取器',
                'resultMsg': None
            }
        
        try:
            with self._transaction():
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'resultMsg': None
                    }
                deleted_count = 0
                missing_ids = []
                
                for article_id in article_ids:
                    if article_repo.delete(article_id):
                        deleted_count += 1
                    else:
                        missing_ids.append(article_id)
                
                return {
                    'success': True,
                    'message': '批量刪除文章成功',
                    'resultMsg': {
                        'success_count': deleted_count,
                        'fail_count': len(missing_ids),
                        'missing_ids': missing_ids
                    }
                }
        except Exception as e:
            logger.error(f"批量刪除文章失敗: {e}")
            raise e

    def update_article_tags(self, article_id: int, tags: List[str]) -> Dict[str, Any]:
        """更新文章標籤"""
        try:
            with self._transaction():
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'article': None
                    }
                tags_str = ','.join(tags)
                result = article_repo.update(article_id, {"tags": tags_str})
                if not result:
                    return {
                        'success': False,
                        'message': '更新文章標籤失敗',
                        'article': None
                    }
                return {
                    'success': True,
                    'message': '更新文章標籤成功',
                    'article': result
                }
        except Exception as e:
            logger.error(f"更新文章標籤失敗: {e}")
            raise e

    def get_articles_statistics(self) -> Dict[str, Any]:
        """獲取文章統計資訊"""
        try:
            with self._transaction():
                article_repo = self._get_repository()
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
            logger.error(f"獲取文章統計資訊失敗: {e}")
            raise e

    def advanced_search_articles(
        self,
        keywords: Optional[str] = None,
        category: Optional[str] = None,
        date_range: Optional[Tuple[datetime, datetime]] = None,
        is_ai_related: Optional[bool] = None,
        is_scraped: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        source: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> Dict[str, Any]:
        """進階搜尋文章"""
        try:
            with self._transaction():
                article_repo = self._get_repository()
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
            logger.error(f"進階搜尋文章失敗: {e}")
            raise e
