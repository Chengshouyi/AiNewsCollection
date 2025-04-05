import logging
from typing import Optional, Dict, Any, List, TypeVar, Tuple, Hashable
from src.models.articles_model import Base, Articles
from datetime import datetime, timedelta
from src.error.errors import DatabaseOperationError
from src.database.articles_repository import ArticlesRepository
from sqlalchemy import or_
from sqlalchemy.orm import Session

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 通用類型變數，用於泛型方法
T = TypeVar('T', bound=Base)

class ArticleService:
    """文章服務，提供文章相關業務邏輯"""
    
    def __init__(self, session: Session):
        self.session = session

    def _get_repository(self):
        """取得儲存庫的上下文管理器"""
        try:
            return ArticlesRepository(self.session, Articles), self.session
        except Exception as e:
            error_msg = f"取得儲存庫失敗: {e}"
            logger.error(error_msg)
            raise DatabaseOperationError(error_msg) from e
    
    def insert_article(self, article_data: Dict[str, Any]) -> Optional[Articles]:
        """
        創建新文章
        
        Args:
            article_data: 文章資料字典
            
        Returns:
            創建成功的文章或 None
        """
        article_repo, session = self._get_repository()
        try:
            # Repository 層已包含驗證邏輯
            result = article_repo.create(article_data)
            session.commit()
            return result
        except Exception as e:
            session.rollback()
            logger.error(f"創建文章失敗: {e}")
            raise e

    def batch_create_articles(self, articles_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        批量創建新文章
        
        Args:
            articles_data: 文章資料字典列表
            
        Returns:
            包含成功和失敗資訊的字典
                success_count: 成功插入數量
                fail_count: 失敗數量
                inserted_articles: 成功插入的文章列表
        """
        if not articles_data:
            return {
                "success_count": 0,
                "fail_count": 0,
                "inserted_articles": []
            }

        article_repo, session = self._get_repository()
        try:
            # 直接使用 Repository 的批量創建功能

            # 將 articles_data 轉換為 Dict[str, Any]
            result = article_repo.batch_create(articles_data)
            session.commit()
            return {
                "success_count": result["success_count"],
                "fail_count": result["fail_count"],
                "inserted_articles": result["inserted_articles"]
            }
        except Exception as e:
            session.rollback()
            error_msg = f"批量插入文章失敗: {e}"
            logger.error(error_msg)
            raise DatabaseOperationError(error_msg) from e
    
    def get_all_articles(self, limit: Optional[int] = None, offset: Optional[int] = None, sort_by: Optional[str] = None, sort_desc: bool = False) -> List[Articles]:
        """
        獲取所有文章，支持分頁和排序
        
        Args:
            limit: 限制返回數量，預設為 None（返回全部）
            offset: 起始偏移，預設為 None
            sort_by: 排序欄位，預設為 None
            sort_desc: 是否降序排序，預設為 False
            
        Returns:
            文章列表
        """
        article_repo, session = self._get_repository()
        try:
            return article_repo.get_by_filter({}, limit=limit, offset=offset)
        except Exception as e:
            logger.error(f"獲取所有文章失敗: {e}")
            raise e
    
    def search_articles(self, search_terms: Dict[str, Any], limit: Optional[int] = None, offset: Optional[int] = None) -> List[Articles]:
        """
        搜尋文章
        
        Args:
            search_terms: 搜尋條件，如 {"title": "關鍵字", "published_at_start": datetime, "published_at_end": datetime}
            limit: 限制返回數量
            offset: 起始偏移
            
        Returns:
            符合條件的文章列表
        """
        article_repo, session = self._get_repository()
        try:
            return article_repo.get_by_filter(search_terms, limit=limit, offset=offset)
        except Exception as e:
            logger.error(f"搜尋文章失敗: {e}")
            raise e
    
    def get_article_by_id(self, article_id: int) -> Optional[Articles]:
        """
        根據ID獲取文章
        
        Args:
            article_id: 文章ID
            
        Returns:
            文章或 None
        """  
        article_repo, session = self._get_repository()
        try:
            return article_repo.get_by_id(article_id)
        except Exception as e:
            logger.error(f"獲取文章失敗，ID={article_id}: {e}")
            raise e

    def get_article_by_link(self, link: str) -> Optional[Articles]:
        """
        根據連結獲取文章
        
        Args:
            link: 文章連結
            
        Returns:
            文章或 None
        """
        article_repo, session = self._get_repository()
        try:
            return article_repo.find_by_link(link)
        except Exception as e:
            logger.error(f"根據連結獲取文章失敗，link={link}: {e}")
            raise e

    def get_articles_paginated(self, page: int, per_page: int, sort_by: Optional[str] = None, sort_desc: bool = False) -> Dict[str, Any]:
        """
        分頁獲取文章
        
        Args:
            page: 頁碼  
            per_page: 每頁文章數量
            sort_by: 排序欄位，默認None
            sort_desc: 是否降序排序，默認False
        Returns:
            items: 分頁後的文章列表
            total: 總文章數量
            page: 當前頁碼
            per_page: 每頁文章數量
            total_pages: 總頁數
        """
        article_repo, session = self._get_repository()
        try:
            return article_repo.get_paginated_by_filter({}, page, per_page, sort_by, sort_desc)
        except Exception as e:
            logger.error(f"分頁獲取文章失敗: {e}")
            raise e

    def get_ai_related_articles(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Articles]:
        """
        獲取所有AI相關的文章
        
        Args:
            limit: 限制返回數量
            offset: 起始偏移
            
        Returns:
            AI相關文章列表
        """
        article_repo, session = self._get_repository()
        try:
            return article_repo.get_by_filter({"is_ai_related": True}, limit=limit, offset=offset)
        except Exception as e:
            logger.error(f"獲取AI相關文章失敗: {e}")
            raise e

    def get_articles_by_category(self, category: str, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Articles]:
        """
        根據分類獲取文章
        
        Args:
            category: 文章分類
            limit: 限制返回數量
            offset: 起始偏移
            
        Returns:
            指定分類的文章列表
        """
        article_repo, session = self._get_repository()
        try:
            return article_repo.find_by_category(category)
        except Exception as e:
            logger.error(f"獲取分類文章失敗: {e}")
            raise e

    def get_articles_by_tags(self, tags: List[str], limit: Optional[int] = None, offset: Optional[int] = None) -> List[Articles]:
        """
        根據標籤獲取文章
        
        Args:
            tags: 標籤列表
            limit: 限制返回數量
            offset: 起始偏移
            
        Returns:
            包含指定標籤的文章列表
        """
        article_repo, session = self._get_repository()
        try:
            articles = article_repo.find_by_tags(tags)
            if offset is not None and limit is not None:
                return articles[offset:offset + limit]
            elif limit is not None:
                return articles[:limit]
            return articles
        except Exception as e:
            logger.error(f"根據標籤獲取文章失敗: {e}")
            raise e

    def update_article(self, article_id: int, article_data: Dict[str, Any]) -> Optional[Articles]:
        """
        更新文章
        
        Args:
            article_id: 文章ID
            article_data: 要更新的文章資料
            
        Returns:
            更新成功的文章或 None
        
        Raises:
            ValidationError: 當嘗試更新不可變欄位或資料驗證失敗時
        """
        article_repo, session = self._get_repository()
        try:
            result = article_repo.update(article_id, article_data)
            session.commit()
            return result
        except Exception as e:
            session.rollback()
            logger.error(f"更新文章失敗: {e}")
            raise e
    
    def batch_update_articles(self, article_ids: List[int], article_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        批量更新文章
        
        Args:
            article_ids: 文章ID列表 
            article_data: 要更新的文章資料
            
        Returns:
            成功更新數量和失敗數量的字典
                success_count: 成功更新數量
                fail_count: 失敗數量
                updated_articles: 成功更新的文章列表
                missing_ids: 未找到的文章ID列表
                error_ids: 更新過程中出錯的ID列表
                invalid_fields: 不合規的欄位列表
        """
        article_repo, session = self._get_repository()
        try:
            result = article_repo.batch_update(article_ids, article_data)
            session.commit()
            return {
                "success_count": result["success_count"],
                "fail_count": result["fail_count"],
                "updated_articles": result["updated_articles"],
                "missing_ids": result["missing_ids"],
                "error_ids": result["error_ids"],
                "invalid_fields": result["invalid_fields"]
            }
        except Exception as e:
            session.rollback()
            logger.error(f"批量更新文章失敗: {e}")
            raise e
        
    def delete_article(self, article_id: int) -> bool:
        """
        刪除文章
        
        Args:
            article_id: 文章ID
            
        Returns:
            是否成功刪除
        """              
        article_repo, session = self._get_repository()
        try:
            result = article_repo.delete(article_id)
            session.commit()
            return result
        except Exception as e:
            session.rollback()
            logger.error(f"刪除文章失敗: {e}")
            raise e
        
    def delete_article_by_link(self, link: str) -> bool:
        """
        根據連結刪除文章
        
        Args:
            link: 文章連結  
        Returns:
            是否成功刪除
        """
        article_repo, session = self._get_repository()
        try:
            result = article_repo.delete_by_link(link)
            session.commit()
            return result
        except Exception as e:
            session.rollback()
            logger.error(f"根據連結刪除文章失敗: {e}")
            raise e
    

    def batch_delete_articles(self, article_ids: List[int]) -> Dict[str, Any]:
        """
        批量刪除文章
        
        Args:
            article_ids: 文章ID列表
            
        Returns:
            成功刪除數量和失敗數量的字典
                success_count: 成功刪除數量
                fail_count: 失敗數量
                missing_ids: 未找到的文章ID列表
        """
        if not article_ids:
            return {
                "success_count": 0,
                "fail_count": 0,
                "missing_ids": []
            }
        
        article_repo, session = self._get_repository()
        try:
            deleted_count = 0
            missing_ids = []
            
            for article_id in article_ids:
                if article_repo.delete(article_id):
                    deleted_count += 1
                else:
                    missing_ids.append(article_id)
            
            session.commit()
            return {
                "success_count": deleted_count,
                "fail_count": len(missing_ids),
                "missing_ids": missing_ids
            }
        except Exception as e:
            session.rollback()
            logger.error(f"批量刪除文章失敗: {e}")
            raise e

    def update_article_tags(self, article_id: int, tags: List[str]) -> Optional[Articles]:
        """
        更新文章標籤
        
        Args:
            article_id: 文章ID
            tags: 新的標籤列表
            
        Returns:
            更新後的文章
        """
        try:
            tags_str = ','.join(tags)
            return self.update_article(article_id, {"tags": tags_str})
        except Exception as e:
            logger.error(f"更新文章標籤失敗: {e}")
            raise e

    def get_articles_statistics(self) -> Dict[str, Any]:
        """
        獲取文章統計資訊
        
        Returns:
            包含各種統計數據的字典
        """
        article_repo, session = self._get_repository()
        try:
            total_count = article_repo.count()
            ai_related_count = article_repo.count({"is_ai_related": True})
            category_distribution = article_repo.get_category_distribution()
            week_ago = datetime.now() - timedelta(days=7)
            recent_count = article_repo.count({"published_at": {"$gte": week_ago}})
            
            return {
                "total_articles": total_count,
                "ai_related_articles": ai_related_count,
                "category_distribution": category_distribution,
                "recent_articles": recent_count
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
        tags: Optional[List[str]] = None,
        source: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Articles]:
        """
        進階搜尋文章
        
        Args:
            keywords: 關鍵字（搜尋標題和內容）
            category: 文章分類
            date_range: 發布日期範圍
            is_ai_related: 是否為AI相關文章
            tags: 標籤列表
            source: 來源網站
            limit: 限制返回數量
            offset: 起始偏移
            
        Returns:
            符合條件的文章列表
        """
        article_repo, session = self._get_repository()
        try:
            query = session.query(Articles)
            
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
                
            if tags:
                for tag in tags:
                    query = query.filter(Articles.tags.like(f"%{tag}%"))
                    
            if source:
                query = query.filter(Articles.source == source)
                
            if offset:
                query = query.offset(offset)
                
            if limit:
                query = query.limit(limit)
                
            return query.all()
        except Exception as e:
            logger.error(f"進階搜尋文章失敗: {e}")
            raise e
