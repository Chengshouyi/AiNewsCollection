import logging
from typing import Optional, Dict, Any, List, TypeVar, Type, Tuple
from .database_manager import DatabaseManager
from .repository import Repository
from .models import Article, Base
from datetime import datetime
from contextlib import contextmanager
from .article_schema import ArticleCreateSchema, ArticleUpdateSchema
from pydantic import ValidationError

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
    
    # 增加裝飾器來包裝通用的 session 與 repo 操作
    @contextmanager
    def _get_repository(self, model_class: Type[T]):
        """取得儲存庫的上下文管理器"""
        with self.db_manager.session_scope() as session:
            repo = Repository(session, model_class)
            try:
                yield repo, session
            except Exception as e:
                error_msg = f"儲存庫操作錯誤: {e}"
                logger.error(error_msg, exc_info=True)
                session.rollback()
                raise
    
    def insert_article(self, article_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        創建新文章
        
        Args:
            article_data: 文章資料字典
            
        Returns:
            成功時返回文章字典，失敗時返回 None
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
            except ValidationError as e:
                logger.error(f"文章資料驗證失敗: {e}")
                return None

            with self._get_repository(Article) as (repo, session):
                # 檢查文章是否已存在
                if not repo.exists(link=validated_data['link']):
                    article = repo.create(**validated_data)
                    session.commit()
                    return {
                        "id": article.id,
                        "title": article.title,
                        "summary": article.summary,
                        "link": article.link,
                        "content": article.content,
                        "published_at": article.published_at,
                        "source": article.source,
                        "created_at": article.created_at,
                        "updated_at": article.updated_at,
                    }
                else:
                    error_msg = f"文章已存在: {validated_data['link']}"
                    logger.warning(error_msg)
                    return None
        except Exception as e:
            error_msg = f"創建文章失敗: {e}"
            logger.error(error_msg, exc_info=True)
            return None

    def batch_insert_articles(self, articles_data: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        批量創建新文章
        
        Args:
            articles_data: 文章資料字典列表
            
        Returns:
            成功插入數量和失敗數量的元組
        """
        success_count = 0
        fail_count = 0
        
        for article_data in articles_data:
            result = self.insert_article(article_data)
            if result:
                success_count += 1
            else:
                fail_count += 1
                
        logger.info(f"批量創建文章完成: 成功 {success_count}, 失敗 {fail_count}")
        return (success_count, fail_count)

    def get_all_articles(self, limit: Optional[int] = None, offset: Optional[int] = None, sort_by: Optional[str] = None, sort_desc: bool = False) -> List[Dict[str, Any]]:
        """
        獲取所有文章，支持分頁和排序
        
        Args:
            limit: 限制返回數量，預設為 None（返回全部）
            offset: 起始偏移，預設為 None
            sort_by: 排序欄位，預設為 None
            sort_desc: 是否降序排序，預設為 False
            
        Returns:
            文章字典列表
        """
        try:
            with self._get_repository(Article) as (repo, _):
                # 獲取所有文章
                articles = repo.get_all(
                    limit=limit,
                    offset=offset,
                    sort_by=sort_by,
                    sort_desc=sort_desc
                )
                # 使用列表推導式簡化轉換過程，並確保返回類型為 List[Dict[str, Any]]
                return [article_dict for article in articles 
                        if (article_dict := self._article_to_dict(article)) is not None]
        except Exception as e:
            error_msg = f"獲取所有文章失敗: {e}"
            logger.error(error_msg, exc_info=True)
            return []
    
    def search_articles(self, search_terms: Dict[str, Any], limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        搜尋文章
        
        Args:
            search_terms: 搜尋條件，如 {"title": "關鍵字", "published_at_start": datetime, "published_at_end": datetime}
            limit: 限制返回數量
            offset: 起始偏移
            
        Returns:
            符合條件的文章字典列表
        """
        try:
            with self._get_repository(Article) as (repo, session):
                # 建立查詢
                query = session.query(Article)
                
                # 應用搜尋條件
                if "title" in search_terms and search_terms["title"]:
                    query = query.filter(Article.title.like(f"%{search_terms['title']}%"))
                    
                if "content" in search_terms and search_terms["content"]:
                    query = query.filter(Article.content.like(f"%{search_terms['content']}%"))
                    
                if "published_at_start" in search_terms and search_terms["published_at_start"]:
                    query = query.filter(Article.published_at >= search_terms["published_at_start"])
                    
                if "published_at_end" in search_terms and search_terms["published_at_end"]:
                    query = query.filter(Article.published_at <= search_terms["published_at_end"])
                
                # 分頁
                if offset is not None:
                    query = query.offset(offset)
                    
                if limit is not None:
                    query = query.limit(limit)
                
                articles = query.all()
                return [article_dict for article in articles 
                        if (article_dict := self._article_to_dict(article)) is not None]
        except Exception as e:
            error_msg = f"搜尋文章失敗: {e}"
            logger.error(error_msg, exc_info=True)
            return []
    
    def get_article_by_id(self, article_id: int) -> Optional[Dict[str, Any]]:
        """
        根據ID獲取文章
        
        Args:
            article_id: 文章ID
            
        Returns:
            文章字典或 None
        """
        if not isinstance(article_id, int) or article_id <= 0:
            logger.error(f"無效的文章ID: {article_id}")
            return None
            
        try:
            with self._get_repository(Article) as (repo, _):
                article = repo.get_by_id(article_id)
                return self._article_to_dict(article) if article else None
        except Exception as e:
            error_msg = f"獲取文章失敗，ID={article_id}: {e}"
            logger.error(error_msg, exc_info=True)
            return None
                
    def get_articles_paginated(self, page: int, per_page: int, sort_by: Optional[str] = None, sort_desc: bool = False) -> Dict[str, Any]:
        """
        分頁獲取文章
        
        Args:
            page: 頁碼  
            per_page: 每頁文章數量
            sort_by: 排序欄位，默認None
            sort_desc: 是否降序排序，默認False
        Returns:
            分頁後的文章字典列表
        """
        try:
            with self._get_repository(Article) as (repo, _):
                # 計算總文章數量
                total_articles = len(repo.get_all())
                
                # 計算總頁數
                total_pages = (total_articles + per_page - 1) // per_page 
                
                # 計算起始偏移
                offset = (page - 1) * per_page
                
                # 獲取分頁後的文章
                articles = repo.get_all(limit=per_page, offset=offset, sort_by=sort_by, sort_desc=sort_desc)

                return {
                    "items": [self._article_to_dict(article) for article in articles],
                    "total": total_articles,
                    "page": page,
                    "per_page": per_page,
                    "total_pages": total_pages
                }
        except Exception as e:
            error_msg = f"分頁獲取文章失敗: {e}"
            logger.error(error_msg, exc_info=True)
            return {
                "items": [],
                "total": 0,
                "page": page,   
                "per_page": per_page,
                "total_pages": 0
            }   


    def update_article(self, article_id: int, article_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        更新文章
        
        Args:
            article_id: 文章ID
            article_data: 要更新的文章資料
            
        Returns:
            更新後的文章字典或 None
        """
        # 移除可能意外傳入的 created_at
        article_data.pop('created_at', None)
        
        # 驗證輸入
        if not isinstance(article_id, int) or article_id <= 0:
            logger.error(f"無效的文章ID: {article_id}")
            return None
            
        if not article_data:
            logger.error("更新資料為空")
            return None
            
        try:
            # 自動更新 updated_at 欄位
            article_data['updated_at'] = datetime.now()
            
            with self._get_repository(Article) as (repo, session):
                article = repo.get_by_id(article_id)
                
                if not article:
                    logger.warning(f"欲更新的文章不存在，ID={article_id}")
                    return None

                # 獲取當前文章資料
                current_article_data = {
                    'title': article.title,
                    'link': article.link,
                    'published_at': article.published_at,
                    'summary': article.summary or '',
                    'content': article.content or '',
                    'source': article.source or ''
                }

                # 更新資料
                current_article_data.update(article_data)
                
                try: 
                    # 驗證更新資料    
                    validated_data = ArticleUpdateSchema.model_validate(current_article_data).model_dump()
                except ValidationError as e:
                    logger.error(f"文章更新資料驗證失敗: {e}")
                    return None
                
                article = repo.update(article, **validated_data)
                session.commit()
                return self._article_to_dict(article)
        except Exception as e:
            error_msg = f"更新文章失敗，ID={article_id}: {e}"
            logger.error(error_msg, exc_info=True)
            return None
    
    def batch_update_articles(self, article_ids: List[int], article_data: Dict[str, Any]) -> Tuple[int, int]:
        """
        批量更新文章
        
        Args:
            article_ids: 文章ID列表 
            article_data: 要更新的文章資料
            
        Returns:
            成功更新數量和失敗數量的元組
        """
        success_count = 0
        fail_count = 0
        
        for article_id in article_ids:
            result = self.update_article(article_id, article_data)
            if result:
                success_count += 1
            else:
                fail_count += 1
                
        logger.info(f"批量更新文章完成: 成功 {success_count}, 失敗 {fail_count}")
        return (success_count, fail_count)

    def delete_article(self, article_id: int) -> bool:
        """
        刪除文章
        
        Args:
            article_id: 文章ID
            
        Returns:
            是否成功刪除
        """        
        if not isinstance(article_id, int) or article_id <= 0:
            logger.error(f"無效的文章ID: {article_id}")
            return False
            
        try:
            with self._get_repository(Article) as (repo, session):
                article = repo.get_by_id(article_id)
                
                if not article:
                    logger.warning(f"欲刪除的文章不存在，ID={article_id}")
                    return False
                    
                repo.delete(article)
                session.commit()
                logger.info(f"成功刪除文章，ID={article_id}")
                return True
        except Exception as e:
            error_msg = f"刪除文章失敗，ID={article_id}: {e}"
            logger.error(error_msg, exc_info=True)
            return False
            
    def batch_delete_articles(self, article_ids: List[int]) -> Tuple[int, int]:
        """
        批量刪除文章
        
        Args:
            article_ids: 文章ID列表
            
        Returns:
            成功刪除數量和失敗數量的元組
        """
        success_count = 0
        fail_count = 0
        
        for article_id in article_ids:
            result = self.delete_article(article_id)
            if result:
                success_count += 1
            else:
                fail_count += 1
                
        logger.info(f"批量刪除文章完成: 成功 {success_count}, 失敗 {fail_count}")
        return (success_count, fail_count)
    
    def _article_to_dict(self, article) -> Optional[Dict[str, Any]]:
        """
        將Article對象轉換為字典
        
        Args:
            article: Article對象
            
        Returns:
            文章字典或 None
        """
        if not article:
            return None
            
        try:
            # 如果已經是字典，直接返回
            if isinstance(article, dict):
                return article

            return {
                "id": article.id,
                "title": article.title,
                "summary": article.summary,
                "link": article.link,
                "content": article.content,
                "published_at": article.published_at,
                "source": article.source,
                "created_at": article.created_at,
                "updated_at": article.updated_at,
            }
        except Exception as e:
            try:
                article_id = getattr(article, 'id', 'N/A')
                error_msg = f"轉換文章為字典失敗: {e}, 文章ID: {article_id}"
            except:
                error_msg = f"轉換文章為字典失敗: {e}, 無法獲取文章ID"
            logger.error(error_msg, exc_info=True)
            return None
