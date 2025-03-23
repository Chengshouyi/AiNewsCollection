import logging
from typing import Optional, Dict, Any, List, TypeVar, Tuple, cast
from src.models.articles_model import Base, Articles
from datetime import datetime, timedelta
from src.models.articles_schema import ArticleCreateSchema, ArticleUpdateSchema
from src.error.errors import DatabaseOperationError, ValidationError
from src.database.database_manager import DatabaseManager
from src.database.articles_repository import ArticlesRepository
from sqlalchemy import func, or_

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 通用類型變數，用於泛型方法
T = TypeVar('T', bound=Base)

class ArticleService:
    """文章服務，提供文章相關業務邏輯"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def _get_repository(self):
        """取得儲存庫的上下文管理器"""
        session = self.db_manager.Session()
        try:
            return ArticlesRepository(session, Articles), session
        except Exception as e:
            error_msg = f"取得儲存庫失敗: {e}"
            logger.error(error_msg)
            session.close()
            raise DatabaseOperationError(error_msg) from e
    
    def insert_article(self, article_data: Dict[str, Any]) -> Optional[Articles]:
        """
        創建新文章
        
        Args:
            article_data: 文章資料字典
            
        Returns:
            創建成功的文章或 None
        """
        try:
            # 添加必要的欄位
            now = datetime.now()
            article_data.update({
                'created_at': now,
            })
            
            # 使用 Pydantic 驗證資料
            try:
                validated_data = ArticleCreateSchema.model_validate(article_data).model_dump()
            except Exception as e:
                error_msg = f"文章資料驗證失敗: {e}"
                logger.error(error_msg)
                raise e

            repo, session = self._get_repository()
            # Repository 層會檢查文章是否已存在
            try:
                result = repo.create(validated_data)
                session.commit()
                return self._ensure_fresh_instance(result)
            except Exception as e:
                session.rollback()
                raise e
        except Exception as e:
            error_msg = f"創建文章失敗: {e}"
            logger.error(error_msg)
            raise e

    def batch_insert_articles(self, articles_data: List[Dict[str, Any]]) -> Dict[str, Any]:
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

        # 驗證所有文章
        try:
            validated_articles = []
            for article_data in articles_data:
                validated_data = ArticleCreateSchema.model_validate(article_data).model_dump()
                validated_articles.append(validated_data)
        except Exception as e:
            error_msg = f"批次插入文章時，文章資料驗證失敗: {e}"
            logger.error(error_msg)
            raise e
        
        # 批量插入有效文章
        if validated_articles: 
            try:
                repo, session = self._get_repository()
                # 創建所有文章實體
                article_entities = []
                for article_data in validated_articles:
                    article = Articles(**article_data)
                    article_entities.append(article)
                
                # 批量添加
                session.add_all(article_entities)
                session.flush()  # 獲取所有ID
                
                session.commit()
                
                success_count = len(article_entities)
                log_info = f"批量插入文章完成: 成功 {success_count}"
                logger.info(log_info)
                
                return {
                    "success_count": success_count,
                    "fail_count": 0,
                    "inserted_articles": article_entities
                }
            except Exception as e:
                error_msg = f"批量插入失敗: {e}"
                logger.error(error_msg)
                raise e
        
        return {
            "success_count": 0,
            "fail_count": len(articles_data),
            "inserted_articles": []
        }

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
        try:
            repo, session = self._get_repository()
            # 獲取所有文章
            articles = repo.get_all(
                limit=limit,
                offset=offset,
                sort_by=sort_by,
                sort_desc=sort_desc
            )
            if not articles:
                return []
            return articles
        except Exception as e:
            error_msg = f"獲取所有文章失敗: {e}"
            logger.error(error_msg)
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
        try:
            repo, session = self._get_repository()
            # 建立查詢
            query = session.query(Articles)
            
            # 應用搜尋條件
            if "title" in search_terms and search_terms["title"]:
                query = query.filter(Articles.title.like(f"%{search_terms['title']}%"))
                
            if "content" in search_terms and search_terms["content"]:
                query = query.filter(Articles.content.like(f"%{search_terms['content']}%"))
                
            if "published_at_start" in search_terms and search_terms["published_at_start"]:
                query = query.filter(Articles.published_at >= search_terms["published_at_start"])
                
            if "published_at_end" in search_terms and search_terms["published_at_end"]:
                query = query.filter(Articles.published_at <= search_terms["published_at_end"])
            
            # 分頁
            if offset is not None:
                query = query.offset(offset)
                
            if limit is not None:
                query = query.limit(limit)
            
            articles = query.all()
            return articles
        except Exception as e:
            error_msg = f"搜尋文章失敗: {e}"
            logger.error(error_msg)
            raise e
    
    def get_article_by_id(self, article_id: int) -> Optional[Articles]:
        """
        根據ID獲取文章
        
        Args:
            article_id: 文章ID
            
        Returns:
            文章或 None
        """  
        try:
            repo, session = self._get_repository()
            article = repo.get_by_id(article_id)
            return article
        except Exception as e:
            error_msg = f"獲取文章失敗，ID={article_id}: {e}"
            logger.error(error_msg)
            raise e

    def get_article_by_link(self, link: str) -> Optional[Articles]:
        """
        根據連結獲取文章
        
        Args:
            link: 文章連結
            
        Returns:
            文章或 None
        """
        try:
            repo, session = self._get_repository()
            article = repo.find_by_link(link)
            return article
        except Exception as e:
            error_msg = f"根據連結獲取文章失敗，link={link}: {e}"
            logger.error(error_msg)
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
        try:
            repo, session = self._get_repository()
            return repo.get_paginated(page, per_page, sort_by, sort_desc)
        except Exception as e:
            error_msg = f"分頁獲取文章失敗: {e}"
            logger.error(error_msg)
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
        try:
            repo, session = self._get_repository()
            articles = repo.get_by_filter(
                filter_dict={"is_ai_related": True},
                limit=limit,
                offset=offset
            )
            return articles
        except Exception as e:
            error_msg = f"獲取AI相關文章失敗: {e}"
            logger.error(error_msg)
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
        try:
            repo, session = self._get_repository()
            articles = repo.get_by_filter(
                filter_dict={"category": category},
                limit=limit,
                offset=offset
            )
            return articles
        except Exception as e:
            error_msg = f"獲取分類文章失敗: {e}"
            logger.error(error_msg)
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
        try:
            repo, session = self._get_repository()
            articles = repo.find_by_tags(tags)
            
            # 處理分頁
            if offset is not None and limit is not None:
                start = offset
                end = offset + limit
                return articles[start:end]
            elif limit is not None:
                return articles[:limit]
            else:
                return articles
        except Exception as e:
            error_msg = f"根據標籤獲取文章失敗: {e}"
            logger.error(error_msg)
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
        repo, session = None, None
        try:
            # 自動更新 updated_at 欄位
            article_data['updated_at'] = datetime.now()
            
            # 使用 Pydantic 驗證資料
            try:
                validated_data = ArticleUpdateSchema.model_validate(article_data).model_dump()
            except Exception as e:
                error_msg = f"文章更新資料驗證失敗: {str(e)}"
                logger.error(error_msg)
                raise ValidationError(error_msg)
            
            repo, session = self._get_repository()
            # 嘗試執行更新，這可能會引發 ValidationError
            try:
                result = repo.update(article_id, validated_data)
                
                if not result:
                    error_msg = f"文章更新失敗，ID不存在: {article_id}"
                    logger.error(error_msg)
                    return None
                    
                session.commit()
                return self._ensure_fresh_instance(result)
            except ValidationError as e:
                # 重要：回滾會話並重新引發例外
                session.rollback()
                raise e
        except ValidationError as e:
            # 重新引發驗證錯誤
            if session:
                session.rollback()
            raise e
        except Exception as e:
            error_msg = f"更新文章失敗，ID={article_id}: {e}"
            logger.error(error_msg)
            if session:
                session.rollback()
            # 將其他例外轉換為 ValidationError，保持一致性
            raise ValidationError(f"更新文章失敗: {str(e)}")
    
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
        """
        if not article_ids:
            return {
                "success_count": 0,
                "fail_count": 0,
                "updated_articles": [],
                "missing_ids": [],
                "error_ids": []
            }
            
        try:
            # 自動更新 updated_at 欄位
            article_data['updated_at'] = datetime.now()
            
            # 先驗證更新資料
            try:
                validated_data = ArticleUpdateSchema.model_validate(article_data).model_dump(exclude_unset=True)
            except Exception as e:
                error_msg = f"文章更新資料驗證失敗: {e}"
                logger.error(error_msg)
                raise e
                
            repo, session = self._get_repository()
            
            # 使用Repository的批量更新方法
            result = repo.batch_update(article_ids, validated_data)
            
            # 提交更新
            session.commit()
            
            success_count = result["success_count"]
            fail_count = result["fail_count"]
            log_info = f"批量更新文章完成: 成功 {success_count}, 失敗 {fail_count}"
            logger.info(log_info)
            
            return {
                "success_count": success_count,
                "fail_count": fail_count,
                "updated_articles": result["updated_entities"],
                "missing_ids": result["missing_ids"],
                "error_ids": result.get("error_ids", [])
            }
        except Exception as e:
            error_msg = f"批量更新文章失敗: {e}"
            logger.error(error_msg)
            raise e
        
    def delete_article(self, article_id: int) -> bool:
        """
        刪除文章
        
        Args:
            article_id: 文章ID
            
        Returns:
            是否成功刪除
        """              
        try:
            repo, session = self._get_repository()
            result = repo.delete(article_id)
            
            if not result:
                error_msg = f"欲刪除的文章不存在，ID={article_id}"
                logger.error(error_msg)
                return False
                
            session.commit()
            log_info = f"成功刪除文章，ID={article_id}"
            logger.info(log_info)
            return True
        except Exception as e:
            error_msg = f"刪除文章失敗，ID={article_id}: {str(e)}"
            logger.error(error_msg)
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
        
        try:
            repo, session = self._get_repository()
            deleted_ids = []
            missing_ids = []
            
            # 逐個刪除文章
            for article_id in article_ids:
                result = repo.delete(article_id)
                if result:
                    deleted_ids.append(article_id)
                else:
                    missing_ids.append(article_id)
            
            session.commit()
            
            success_count = len(deleted_ids)
            fail_count = len(missing_ids)
            
            log_info = f"批量刪除文章完成: 成功 {success_count}, 失敗 {fail_count}"
            logger.info(log_info)
            
            return {
                "success_count": success_count,
                "fail_count": fail_count,
                "missing_ids": missing_ids
            }
        except Exception as e:
            error_msg = f"批量刪除文章失敗: {e}"
            logger.error(error_msg)
            session.rollback()  
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
            error_msg = f"更新文章標籤失敗: {e}"
            logger.error(error_msg)
            raise e

    def get_articles_statistics(self) -> Dict[str, Any]:
        """
        獲取文章統計資訊
        
        Returns:
            包含各種統計數據的字典
        """
        try:
            repo, session = self._get_repository()
            total_count = repo.count()
            ai_related_count = repo.count(filter_dict={"is_ai_related": True})
            
            # 獲取各分類的文章數量
            category_distribution = repo.get_category_distribution()
            
            # 獲取最近一週的文章數量
            week_ago = datetime.now() - timedelta(days=7)
            recent_count = repo.count(
                filter_dict={"published_at": {"$gte": week_ago}}
            )
            
            return {
                "total_articles": total_count,
                "ai_related_articles": ai_related_count,
                "category_distribution": category_distribution,
                "recent_articles": recent_count
            }
        except Exception as e:
            error_msg = f"獲取文章統計資訊失敗: {e}"
            logger.error(error_msg)
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
        try:
            repo, session = self._get_repository()
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
            error_msg = f"進階搜尋文章失敗: {e}"
            logger.error(error_msg)
            raise e

    def _ensure_fresh_instance(self, entity: Optional[T]) -> Optional[T]:
        """
        確保實體不是分離的實例
        
        如果實體已分離，則重新查詢；如果實體不存在，則返回 None
        """
        if entity is None:
            return None
        
        try:
            # 使用 getattr 安全訪問 id 屬性
            entity_id = getattr(entity, 'id', None)
            if entity_id is not None:
                return entity
            return None
        except Exception:
            # 如果實體已分離，則重新查詢
            if isinstance(entity, Articles):
                entity_id = getattr(entity, 'id', None)
                if entity_id is not None:
                    refreshed = self.get_article_by_id(entity_id)
                    return cast(T, refreshed)  # 使用 cast 進行類型轉換
            return None
