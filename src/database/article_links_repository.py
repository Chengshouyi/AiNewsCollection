from .base_repository import BaseRepository
from src.models.article_links_model import ArticleLinks
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
        try:
            return self.session.query(self.model_class).filter_by(article_link=article_link).first()
        except Exception as e:
            error_msg = f"查詢文章連結時發生錯誤: {e}"
            logger.error(error_msg)
            raise e

    def find_unscraped_links(self, limit: Optional[int] = 100, source_name: Optional[str] = None) -> List['ArticleLinks']:
        """查詢未爬取的連結
        
        Args:
            limit: 限制返回數量
            source_name: 可選的來源名稱過濾
            
        Returns:
            List[ArticleLinks]: 未爬取的文章連結列表
        """
        try:
            query = self.session.query(self.model_class).filter_by(is_scraped=False)
            
            if source_name:
                query = query.filter_by(source_name=source_name)
                
            if limit:
                query = query.limit(limit)
                
            return query.all()
        except (OperationalError, ResourceClosedError, StatementError, UnboundExecutionError) as e:
            error_msg = f"資料庫連接錯誤: {e}"
            logger.error(error_msg)
            raise DatabaseConnectionError(error_msg) from e
        except SQLAlchemyError as e:
            error_msg = f"資料庫操作錯誤: {e}"
            logger.error(error_msg)
            raise DatabaseOperationError(error_msg) from e
        except Exception as e:
            error_msg = f"查詢未爬取的連結時發生錯誤: {e}"
            logger.error(error_msg)
            raise DatabaseOperationError(error_msg) from e

    def count_unscraped_links(self, source_name: Optional[str] = None) -> int:
        """計算未爬取的連結數量
        
        Args:
            source_name: 可選的來源名稱過濾
            
        Returns:
            int: 未爬取的連結數量
        """
        try:
            query = self.session.query(func.count(self.model_class.id)).filter_by(is_scraped=False)
            
            if source_name:
                query = query.filter_by(source_name=source_name)
                
            return query.scalar()
        except Exception as e:
            error_msg = f"計算未爬取的連結數量時發生錯誤: {e}"
            logger.error(error_msg)
            raise e

    def mark_as_scraped(self, article_link: str) -> bool:
        """將文章連結標記為已爬取
        
        Args:
            article_link: 文章連結
            
        Returns:
            bool: 是否成功標記
        """
        try:
            link_entity = self.find_by_article_link(article_link)
            if not link_entity:
                return False
                
            link_entity.is_scraped = True
            self.session.flush()
            return True
        except Exception as e:
            error_msg = f"標記文章為已爬取時發生錯誤: {e}"
            logger.error(error_msg)
            raise e

    def get_source_statistics(self) -> Dict[str, Dict[str, int]]:
        """獲取各來源的爬取統計
        
        Returns:
            Dict[str, Dict[str, int]]: 各來源的爬取和未爬取數量
        """
        try:
            # 查詢各來源的總數和未爬取數量
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
        except Exception as e:
            error_msg = f"獲取來源統計時發生錯誤: {e}"
            logger.error(error_msg)
            raise e

    def create(self, entity_data: Dict[str, Any], schema_class=None) -> ArticleLinks:
        """重寫基類的 create 方法，添加針對 ArticleLinks 的特殊驗證
        
        Args:
            entity_data: 實體資料
            schema_class: 可選的 schema 類別
            
        Returns:
            ArticleLinks: 創建的實體
        """
        try:
            # 驗證必填欄位
            required_fields = ['source_name', 'source_url', 'article_link']
            missing_fields = [field for field in required_fields if field not in entity_data]
            
            if missing_fields:
                raise ValidationError(f"缺少必填欄位: {', '.join(missing_fields)}")
            
            # 檢查連結是否已存在
            existing = self.find_by_article_link(entity_data['article_link'])
            if existing:
                raise ValidationError(f"文章連結已存在: {entity_data['article_link']}")
            
            return super().create(entity_data, schema_class)
        except Exception as e:
            error_msg = f"創建文章連結時發生錯誤: {e}"
            logger.error(error_msg)
            raise e

    def batch_mark_as_scraped(self, article_links: List[str]) -> Dict[str, Any]:
        """批量將文章連結標記為已爬取
        
        Args:
            article_links: 文章連結列表
            
        Returns:
            Dict[str, Any]: 處理結果統計
        """
        success_count = 0
        failed_links = []
        
        try:
            for link in article_links:
                try:
                    if self.mark_as_scraped(link):
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
        except Exception as e:
            error_msg = f"批量標記文章為已爬取時發生錯誤: {e}"
            logger.error(error_msg)
            raise e