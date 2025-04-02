import logging
from typing import Optional, Dict, Any, List, Tuple, Hashable
from datetime import datetime
from src.models.articles_model import Articles
from src.models.article_links_model import ArticleLinks
from src.models.articles_schema import ArticleCreateSchema
from src.models.article_links_schema import ArticleLinksCreateSchema
from src.error.errors import DatabaseOperationError, ValidationError
from src.database.database_manager import DatabaseManager
from src.database.articles_repository import ArticlesRepository
from src.database.article_links_repository import ArticleLinksRepository

# 設定 logger
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LinksWithArticlesService:
    """文章與連結關聯服務，提供文章和連結的關聯操作"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def _get_repository(self):
        """取得儲存庫的上下文管理器"""
        session = self.db_manager.Session()
        try:
            return ArticlesRepository(session, Articles), ArticleLinksRepository(session, ArticleLinks), session
        except Exception as e:
            error_msg = f"取得儲存庫失敗: {e}"
            logger.error(error_msg)
            session.close()
            raise DatabaseOperationError(error_msg) from e

    def batch_insert_links_with_articles(self, article_links_data: List[Dict[Hashable, Any]], articles_data: Optional[List[Dict[Hashable, Any]]] = None) -> Dict[str, Any]:
        """
        批量創建文章連結，並可選擇性地同時創建對應的文章
        
        Args:
            article_links_data: 文章連結資料字典列表
            articles_data: 可選的文章資料字典列表，如果提供則同時創建文章
            
        Returns:
            包含成功和失敗資訊的字典
                success_count: 成功插入數量
                fail_count: 失敗數量
                inserted_links: 成功插入的連結列表
                inserted_articles: 成功插入的文章列表（如果有提供文章資料）
                failed_pairs: 插入失敗的連結和文章對
        """
        if not article_links_data:
            return {
                "success_count": 0,
                "fail_count": 0,
                "inserted_links": [],
                "inserted_articles": [],
                "failed_pairs": []
            }

        # 用於儲存成功和失敗的結果
        successful_links = []
        successful_articles = []
        failed_pairs = []
        
        # 檢查是否同時新增文章，並驗證資料數量
        is_with_articles = articles_data is not None and len(articles_data or []) > 0
        
        if is_with_articles and len(articles_data or []) != len(article_links_data):
            error_msg = "文章資料和連結資料數量不匹配"
            logger.error(error_msg)
            raise ValidationError(error_msg)

        # 逐筆處理連結和文章
        for i, link_data in enumerate(article_links_data):
            article_repo, article_link_repo, session = None, None, None
            try:
                # 驗證連結資料
                validated_link = ArticleLinksCreateSchema.model_validate(link_data).model_dump()
                
                # 如果有文章資料，則驗證文章資料
                article = None
                if is_with_articles and articles_data is not None:
                    validated_article = ArticleCreateSchema.model_validate(articles_data[i]).model_dump()
                
                # 取得新的 session
                article_repo, article_link_repo, session = self._get_repository()
                
                # 如果有文章資料，先創建文章
                if is_with_articles and articles_data is not None:
                    article = Articles(**validated_article)
                    session.add(article)
                    session.flush()  # 獲取文章 ID
                
                # 設置連結的 is_scraped 狀態
                validated_link['is_scraped'] = True if is_with_articles else False
                link = ArticleLinks(**validated_link)
                session.add(link)
                
                # 提交交易
                session.commit()
                
                # 記錄成功的實體
                successful_links.append(link)
                if article:
                    successful_articles.append(article)
                
                log_info = f"成功插入連結: link={link.article_link}"
                if article:
                    log_info += f", article_id={article.id}"
                logger.debug(log_info)
                
            except Exception as e:
                # 記錄失敗的資料
                failed_pair = {
                    "link_data": link_data,
                    "error": str(e)
                }
                if is_with_articles and articles_data is not None:
                    failed_pair["article_data"] = articles_data[i]
                failed_pairs.append(failed_pair)
                
                error_msg = f"插入失敗: {str(e)}"
                logger.error(error_msg)
                
                # 回滾交易
                if session:
                    session.rollback()
                
            finally:
                # 關閉 session
                if session:
                    session.close()

        success_count = len(successful_links)
        fail_count = len(failed_pairs)
        
        log_info = f"批量插入完成: 成功 {success_count}, 失敗 {fail_count}"
        logger.info(log_info)
        
        return {
            "success_count": success_count,
            "fail_count": fail_count,
            "inserted_links": successful_links,
            "inserted_articles": successful_articles,
            "failed_pairs": failed_pairs
        }

    def get_article_with_links(self, article_id: int) -> Optional[Dict[str, Any]]:
        """
        獲取文章及其相關連結資訊
        
        Args:
            article_id: 文章ID
            
        Returns:
            包含文章和連結資訊的字典或 None
        """
        try:
            article_repo, article_link_repo, session = self._get_repository()
            article = article_repo.get_by_id(article_id)
            if not article:
                return None
                
            links = article_link_repo.find_by_article_link(article.article_links)
            
            return {
                "article": article,
                "links": links
            }
        except Exception as e:
            error_msg = f"獲取文章及連結失敗，ID={article_id}: {e}"
            logger.error(error_msg)
            raise DatabaseOperationError(error_msg)

    def update_article_link_status(self, article_link: str, is_scraped: bool = True) -> bool:
        """
        更新文章連結的爬取狀態
        
        Args:
            article_link: 文章連結
            is_scraped: 是否已爬取
            
        Returns:
            是否更新成功
        """
        try:
            article_repo, article_link_repo, session = self._get_repository()
            result = article_link_repo.update_scrape_status(article_link, is_scraped)
            if result:
                session.commit()
                return True
            return False
        except Exception as e:
            error_msg = f"更新文章連結狀態失敗，link={article_link}: {e}"
            logger.error(error_msg)
            if session:
                session.rollback()
            raise DatabaseOperationError(error_msg)

    def get_unscraped_links(self, limit: Optional[int] = None) -> List[ArticleLinks]:
        """
        獲取未爬取的文章連結
        
        Args:
            limit: 限制返回數量
            
        Returns:
            未爬取的文章連結列表
        """
        try:
            article_repo, article_link_repo, session = self._get_repository()
            return article_link_repo.find_unscraped_links(limit)
        except Exception as e:
            error_msg = f"獲取未爬取連結失敗: {e}"
            logger.error(error_msg)
            raise DatabaseOperationError(error_msg)

    def get_articles_by_source(self, source: str, with_links: bool = False) -> List[Dict[str, Any]]:
        """
        根據來源獲取文章及其連結
        
        Args:
            source: 文章來源
            with_links: 是否包含連結資訊
            
        Returns:
            文章列表，每個元素包含文章和連結資訊
        """
        try:
            article_repo, article_link_repo, session = self._get_repository()
            articles = article_repo.get_by_filter({"source": source})
            result = []
            if not with_links and articles is not None:
                result.append({
                    "article": articles,
                    "links": None
                })
            elif with_links and articles is not None:
                for article in articles:
                    links = article_link_repo.find_by_article_link(article.article_links)
                result.append({
                    "article": article,
                    "links": links
                })
            return result
        except Exception as e:
            error_msg = f"獲取來源文章失敗，source={source}: {e}"
            logger.error(error_msg)
            raise DatabaseOperationError(error_msg)

    def delete_article_with_links(self, article_link: str) -> bool:
        """
        刪除文章及其相關連結
        
        Args:
            article_link: 文章連結
            
        Returns:
            是否刪除成功
        """
        article_repo, article_link_repo, session = None, None, None
        try:
            article_repo, article_link_repo, session = self._get_repository()
            
            # 先刪除連結
            article_link_repo.delete_by_article_link(article_link)
            
            # 再刪除文章
            result = article_repo.delete(article_link)
            
            if result:
                session.commit()
                return True
            return False
        except Exception as e:
            error_msg = f"刪除文章及連結失敗，link={article_link}: {e}"
            logger.error(error_msg)
            if session:
                session.rollback()
            raise DatabaseOperationError(error_msg)
