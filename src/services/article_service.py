import logging
from typing import Optional, Dict, Any, List, TypeVar, Tuple, Hashable, Type, cast
from src.models.articles_model import Base, Articles, ArticleScrapeStatus
from datetime import datetime, timedelta
from src.error.errors import DatabaseOperationError
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
    
    def _get_repository(self) -> ArticlesRepository:
        """獲取文章資料庫訪問對象"""
        return cast(ArticlesRepository, super()._get_repository('Article'))
    
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
                message = (
                    f"批量處理文章完成：新增 {result['success_count']} 筆，"
                    f"更新 {result['update_count']} 筆，"
                    f"失敗 {result['fail_count']} 筆"
                )
                return {
                    'success': True,
                    'message': message,
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

    def batch_update_articles_by_link(self, article_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量更新文章
        Args:
            article_data: 文章資料

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
                result = article_repo.batch_update_by_link(article_data)
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
        task_id: Optional[str] = None,
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
            logger.error(f"進階搜尋文章失敗: {e}")
            raise e

    def get_articles_by_task(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """根據任務ID獲取文章
        
        Args:
            filters: 過濾條件，包含：
                - task_id: 任務ID
                - is_scraped: 是否已抓取內容
                - preview: 是否只返回預覽資料
                
        Returns:
            Dict[str, Any]: 包含文章列表的字典
        """
        try:
            with self._transaction():
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }
                
                # 檢查必要參數
                task_id = filters.get('task_id')
                if not task_id:
                    return {
                        'success': False,
                        'message': '必須提供任務ID',
                        'articles': []
                    }
                
                # 構建查詢條件
                query_filters = {'task_id': task_id}
                if 'is_scraped' in filters:
                    query_filters['is_scraped'] = filters['is_scraped']
                # elif 'scraped' in filters:  # 增加對 'scraped' 參數的支持
                #     query_filters['is_scraped'] = filters['scraped']
                
                # 打印查詢條件和返回結果，用於調試
                logger.debug(f"查詢條件: {query_filters}")
                articles = article_repo.get_by_filter(query_filters)
                logger.debug(f"查詢結果: {[a.id for a in articles]}, is_scraped狀態: {[a.is_scraped for a in articles]}")
                
                # 如果需要預覽，只返回部分欄位
                if filters.get('preview'):
                    preview_articles = []
                    for article in articles:
                        preview_articles.append({
                            'id': article.id,
                            'title': article.title,
                            'link': article.link,
                            'source': article.source,
                            'published_at': article.published_at,
                            'is_scraped': article.is_scraped
                        })
                    articles = preview_articles
                
                return {
                    'success': True,
                    'message': '獲取文章成功',
                    'articles': articles
                }
        except Exception as e:
            error_msg = f"獲取任務相關文章失敗, task_id={filters.get('task_id')}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg,
                'articles': []
            }

    def search_articles_by_title(self, keyword: str, exact_match: bool = False) -> Dict[str, Any]:
        """根據標題搜索文章"""
        try:
            with self._transaction():
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }
                
                articles = article_repo.search_by_title(keyword, exact_match)
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
            
    def search_articles_by_keywords(self, keywords: str) -> Dict[str, Any]:
        """根據關鍵字搜索文章"""
        try:
            with self._transaction():
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }
                
                articles = article_repo.search_by_keywords(keywords)
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
                article_repo = self._get_repository()
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
        """更新文章爬取狀態"""
        try:
            with self._transaction():
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器'
                    }
                
                result = article_repo.update_scrape_status(link, is_scraped)
                if result:
                    return {
                        'success': True,
                        'message': '更新文章爬取狀態成功'
                    }
                return {
                    'success': False,
                    'message': '更新文章爬取狀態失敗，文章可能不存在'
                }
        except Exception as e:
            error_msg = f"更新文章爬取狀態失敗, link={link}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'message': error_msg
            }
            
    def batch_mark_articles_as_scraped(self, links: List[str]) -> Dict[str, Any]:
        """批量將文章標記為已爬取"""
        try:
            with self._transaction():
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'resultMsg': None
                    }
                
                result = article_repo.batch_mark_as_scraped(links)
                return {
                    'success': True,
                    'message': f"批量標記文章為已爬取成功: {result['success_count']} 筆成功，{result['fail_count']} 筆失敗",
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
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }
                
                articles = article_repo.find_unscraped_links(limit, source)
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
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'articles': []
                    }
                
                articles = article_repo.find_scraped_links(limit, source)
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
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'count': 0
                    }
                
                count = article_repo.count_unscraped_links(source)
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
                article_repo = self._get_repository()
                if not article_repo:
                    return {
                        'success': False,
                        'message': '無法取得資料庫存取器',
                        'count': 0
                    }
                
                count = article_repo.count_scraped_links(source)
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
