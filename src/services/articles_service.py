import logging
from typing import Optional, Dict, Any, List, TypeVar, Type
from ..model.articles_models import Article, Base
from datetime import datetime
from ..model.articles_schema import ArticleCreateSchema, ArticleUpdateSchema
from src.error.errors import ValidationError, DatabaseOperationError
from ..database.database_manager import DatabaseManager
from ..database.articles_repository import ArticleRepository

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
            return ArticleRepository(session, Article), session
        except Exception as e:
            error_msg = f"取得儲存庫失敗: {e}"
            logger.error(error_msg)
            session.close()
            raise DatabaseOperationError(error_msg) from e
    
    def insert_article(self, article_data: Dict[str, Any]) -> Optional[Article]:
        """
        創建新文章
        
        Args:
            article_data: 文章資料字典
            
        Returns:
            創建成功的文章或 None
        """
        try:
            # 檢查文章是否已存在
            if 'link' in article_data and article_data['link']:
               existing = self.get_article_by_link(article_data['link'])
               if existing:
                   raise CustomValidationError(f"已存在具有相同連結的文章: {article_data['link']}")
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
            # 檢查文章是否已存在
            if repo.find_by_link(validated_data['link']):
                error_msg = f"文章已存在: {validated_data['link']}"
                logger.error(error_msg)
                raise CustomValidationError(error_msg)
            try:
                result = repo.create(**validated_data)
            except Exception as e:
                error_msg = f"文章創建失敗: {e}"
                logger.error(error_msg)
                raise e
            session.commit()
            return result
        except Exception as e:
            error_msg = f"創建文章失敗: {e}"
            logger.error(error_msg)
            raise e

    def batch_insert_articles(self, articles_data: List[Dict[str, Any]]) -> Optional[List[Article]]:
        """
        批量創建新文章
        
        Args:
            articles_data: 文章資料字典列表
            
        Returns:
            創建成功的文章列表或 None
        """
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
                    article = Article(**article_data)
                    article_entities.append(article)
                
                # 批量添加
                session.add_all(article_entities)
                session.flush()  # 獲取所有ID
                
                session.commit()
                return article_entities
            except Exception as e:
                error_msg = f"批量插入失敗: {e}"
                logger.error(error_msg)
                raise e
        return None

    def get_all_articles(self, limit: Optional[int] = None, offset: Optional[int] = None, sort_by: Optional[str] = None, sort_desc: bool = False) -> List[Article]:
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
            repo, session = self._get_repository()
            # 獲取所有文章
            articles = repo.get_all_articles(
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
    
    def search_articles(self, search_terms: Dict[str, Any], limit: Optional[int] = None, offset: Optional[int] = None) -> List[Article]:
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
            repo, session = self._get_repository()
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
            return articles
        except Exception as e:
            error_msg = f"搜尋文章失敗: {e}"
            logger.error(error_msg)
            raise e
    
    def get_article_by_id(self, article_id: int) -> Optional[Article]:
        """
        根據ID獲取文章
        
        Args:
            article_id: 文章ID
            
        Returns:
            文章字典或 None
        """  
        try:
            repo, session = self._get_repository()
            article = repo.get_by_id(article_id)

            return article
        except Exception as e:
            error_msg = f"獲取文章失敗，ID={article_id}: {e}"
            logger.error(error_msg)
            raise e

    def get_article_by_link(self, link: str) -> Optional[Dict[str, Any]]:
        """
        根據連結獲取文章
        
        Args:
            link: 文章連結
            
        Returns:
            文章字典或 None
        """
        try:
            repo, session = self._get_repository()
            article = repo.find_by_link(link)
            return self._article_to_dict(article) if article else None
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
        repo, session = self._get_repository()
        return repo.get_paginated(page, per_page, sort_by, sort_desc)



    def update_article(self, article_id: int, article_data: Dict[str, Any]) -> Optional[Article]:
        """
        更新文章
        
        Args:
            article_id: 文章ID
            article_data: 要更新的文章資料
            
        Returns:
            更新成功的文章或 None
        """
            
        try:
            # 自動更新 updated_at 欄位
            article_data['updated_at'] = datetime.now()
            
            repo, session = self._get_repository()
            article = repo.get_by_id(article_id)
            
            if not article:
                error_msg = f"ID不存在，文章更新失敗"
                logger.error(error_msg)
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
            except Exception as e:
                error_msg = f"文章更新資料驗證失敗: {str(e)}"
                logger.error(error_msg)
                raise CustomValidationError(error_msg, e)
            
            result = repo.update(article, **validated_data)
            if not result:
                error_msg = f"文章更新失敗"
                logger.error(error_msg)
                return None
                
            session.commit()
            return result
        except Exception as e:
            error_msg = f"更新文章失敗，ID={article_id}: {e}"
            logger.error(error_msg)
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
        """
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
            # 批量查詢所有文章
            articles_to_update = session.query(Article).filter(Article.id.in_(article_ids)).all()
            
            # 追蹤找到的文章ID
            found_article_ids = [article.id for article in articles_to_update]
            
            # 計算未找到的文章ID
            missing_ids = [id for id in article_ids if id not in found_article_ids]
            
            updated_articles = []
            # 更新找到的文章
            for article in articles_to_update:
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
                current_article_data.update(validated_data)
                
                # 更新文章
                for key, value in current_article_data.items():
                    if hasattr(article, key):
                        setattr(article, key, value)
                updated_articles.append(article)
            
            # 提交更新
            session.commit()
            
            success_count = len(updated_articles)
            fail_count = len(missing_ids)
            log_info = f"批量更新文章完成: 成功 {success_count}, 失敗 {fail_count}"
            logger.info(log_info)
            return {
                "updated_articles": updated_articles,
                "success_count": success_count,
                "fail_count": fail_count,
                "missing_ids": missing_ids
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
            # 直接執行刪除操作並返回受影響的行數
            result = session.query(Article).filter(Article.id == article_id).delete()
            
            if result == 0:
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
            # 先查詢所有需要刪除的文章
            articles_to_delete = session.query(Article).filter(Article.id.in_(article_ids)).all()
            
            # 追蹤找到的文章ID
            found_ids = [article.id for article in articles_to_delete]
            
            # 計算未找到的文章ID
            missing_ids = list(set(article_ids) - set(found_ids))
            
            # 批量刪除找到的文章
            if articles_to_delete:
                # 使用bulk_delete操作而非逐個刪除
                for article in articles_to_delete:
                    session.delete(article)
                
                session.commit() 
            
            success_count = len(found_ids)
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
            raise  

        
    # 考慮刪除，使用dump_to_dict
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
        # 如果已經是字典，直接返回
        if isinstance(article, dict):
            return article

        return {
            "id": article.id,
            "title": article.title,
            "summary": article.summary,
            "content": article.content,
            "link": article.link,
            "category": article.category,
            "published_at": article.published_at,
            "author": article.author,
            "source": article.source,
            "article_type": article.article_type,
            "tags": article.tags,
            "content_length": article.content_length,
            "is_ai_related": article.is_ai_related,
            "created_at": article.created_at,
            "updated_at": article.updated_at,
        }

    # 考慮刪除
    def merge_article_data(self, article_id: int, new_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        合併文章資料，用於將列表頁和詳細頁的資料合併
        
        Args:
            article_id: 文章ID
            new_data: 新的文章資料
            
        Returns:
            合併後的文章字典或 None
        """
        try:
            repo, session = self._get_repository()
            article = repo.get_by_id(article_id)
            
            if not article:
                error_msg = f"欲合併的文章不存在，ID={article_id}"
                logger.error(error_msg)
                return None
                
            # 只更新非空值
            update_data = {}
            for key, value in new_data.items():
                if value is not None and value != '':
                    # 特殊處理某些欄位
                    if key == 'tags' and getattr(article, 'tags') and value:
                        # 合併標籤
                        existing_tags = set(getattr(article, 'tags').split(','))
                        new_tags = set(value.split(','))
                        update_data[key] = ','.join(existing_tags.union(new_tags))
                    else:
                        update_data[key] = value
                
                # 更新時間
                update_data['updated_at'] = datetime.now()
                
                # 更新文章Mㄋ
                updated_article = repo.update(article, **update_data)
                session.commit()
                return self._article_to_dict(updated_article)
                
        except Exception as e:
            error_msg = f"合併文章資料失敗，ID={article_id}: {e}"
            logger.error(error_msg)
            raise e

   