from .base_repository import BaseRepository
from src.models.article_links_model import ArticleLinks
from src.models.article_links_schema import ArticleLinksCreateSchema, ArticleLinksUpdateSchema
from typing import Optional, List, Dict, Any
from sqlalchemy import func, or_, case
from src.error.errors import ValidationError, DatabaseConnectionError, DatabaseOperationError
import logging
from sqlalchemy.exc import OperationalError, SQLAlchemyError, UnboundExecutionError
from sqlalchemy.exc import ResourceClosedError, StatementError

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ArticleLinksRepository(BaseRepository['ArticleLinks']):
    """ArticleLinks 特定的Repository"""
    
    def find_by_article_link(self, article_link: str) -> Optional['ArticleLinks']:
        """根據文章連結查詢
        
        Args:
            article_link: 文章連結
            
        Returns:
            Optional[ArticleLinks]: 找到的文章連結實體
        """
        return self.execute_query(
            lambda: self.session.query(self.model_class)
                              .filter_by(article_link=article_link)
                              .first()
        )

    def find_unscraped_links(self, limit: Optional[int] = 100, source_name: Optional[str] = None) -> List['ArticleLinks']:
        """查詢未爬取的連結
        
        Args:
            limit: 限制返回數量
            source_name: 可選的來源名稱過濾
            
        Returns:
            List[ArticleLinks]: 未爬取的文章連結列表
        """
        return self.execute_query(lambda: self._get_unscraped_links(limit, source_name))
    
    def _get_unscraped_links(self, limit: Optional[int], source_name: Optional[str]) -> List['ArticleLinks']:
        """內部方法：獲取未爬取的連結"""
        query = self.session.query(self.model_class).filter_by(is_scraped=False)
        
        if source_name:
            query = query.filter_by(source_name=source_name)
            
        if limit:
            query = query.limit(limit)
            
        return query.all()

    def count_unscraped_links(self, source_name: Optional[str] = None) -> int:
        """計算未爬取的連結數量
        
        Args:
            source_name: 可選的來源名稱過濾
            
        Returns:
            int: 未爬取的連結數量
        """
        return self.execute_query(lambda: self._count_unscraped_links(source_name))
    
    def _count_unscraped_links(self, source_name: Optional[str]) -> int:
        """內部方法：計算未爬取的連結數量"""
        query = self.session.query(func.count(self.model_class.id)).filter_by(is_scraped=False)
        
        if source_name:
            query = query.filter_by(source_name=source_name)
            
        return query.scalar()

    def mark_as_scraped(self, article_link: str) -> bool:
        """將文章連結標記為已爬取
        
        Args:
            article_link: 文章連結
            
        Returns:
            bool: 是否成功標記
        """
        return self.execute_query(lambda: self._mark_as_scraped(article_link))
    
    def _mark_as_scraped(self, article_link: str) -> bool:
        """內部方法：標記文章為已爬取"""
        link_entity = self.find_by_article_link(article_link)
        if not link_entity:
            return False
            
        link_entity.is_scraped = True
        self.session.flush()
        return True

    def get_source_statistics(self) -> Dict[str, Dict[str, int]]:
        """獲取各來源的爬取統計
        
        Returns:
            Dict[str, Dict[str, int]]: 各來源的爬取和未爬取數量
        """
        return self.execute_query(lambda: self._get_source_statistics())
    
    def _get_source_statistics(self) -> Dict[str, Dict[str, int]]:
        """內部方法：獲取來源統計"""
        total_stats = self.session.query(
            self.model_class.source_name,
            func.count(self.model_class.id).label('total'),
            func.sum(case((self.model_class.is_scraped == False, 1), else_=0)).label('unscraped')
        ).group_by(self.model_class.source_name).all()
        
        return {
            source_name: {
                'total': total,
                'unscraped': unscraped or 0,
                'scraped': total - (unscraped or 0)
            }
            for source_name, total, unscraped in total_stats
        }

    def create_article_link(self, entity_data: Dict[str, Any]) -> ArticleLinks:
        """創建文章連結，使用模式驗證
        
        Args:
            entity_data: 實體資料
            
        Returns:
            ArticleLinks: 創建的實體
            
        Raises:
            ValidationError: 當驗證失敗時
        """
        # 檢查連結是否已存在
        if "article_link" in entity_data:
            existing = self.find_by_article_link(entity_data["article_link"])
            if existing:
                raise ValidationError(f"文章連結已存在: {entity_data['article_link']}")
        
        # 使用schema進行其餘驗證並創建
        return self.create(entity_data, schema_class=ArticleLinksCreateSchema)

    def update_article_link(self, link_id: int, entity_data: Dict[str, Any]) -> Optional[ArticleLinks]:
        """更新文章連結，使用模式驗證
        
        Args:
            link_id: 連結ID
            entity_data: 更新的資料
            
        Returns:
            Optional[ArticleLinks]: 更新後的實體
        """
        return self.update(link_id, entity_data, schema_class=ArticleLinksUpdateSchema)

    def batch_mark_as_scraped(self, article_links: List[str]) -> Dict[str, Any]:
        """批量將文章連結標記為已爬取
        
        Args:
            article_links: 文章連結列表
            
        Returns:
            Dict[str, Any]: 處理結果統計
        """
        return self.execute_query(lambda: self._batch_mark_as_scraped(article_links))
    
    def _batch_mark_as_scraped(self, article_links: List[str]) -> Dict[str, Any]:
        """內部方法：批量標記為已爬取"""
        success_count = 0
        failed_links = []
        
        for link in article_links:
            try:
                if self._mark_as_scraped(link):
                    success_count += 1
                else:
                    failed_links.append(link)
            except Exception as e:
                logger.error(f"標記連結 {link} 時發生錯誤: {e}")
                failed_links.append(link)
        
        return {
            "success_count": success_count,
            "fail_count": len(failed_links),
            "failed_links": failed_links
        }