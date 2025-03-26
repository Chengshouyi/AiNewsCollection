from .base_repository import BaseRepository, SchemaType
from src.models.article_links_model import ArticleLinks
from src.models.article_links_schema import ArticleLinksCreateSchema, ArticleLinksUpdateSchema
from typing import Optional, List, Dict, Any, Type
from sqlalchemy import func, case
from src.error.errors import ValidationError
import logging
from pydantic import BaseModel

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ArticleLinksRepository(BaseRepository[ArticleLinks]):
    """ArticleLinks 特定的Repository"""
    
    def get_schema_class(self, schema_type: SchemaType = SchemaType.CREATE) -> Type[BaseModel]:
        """根據操作類型返回對應的schema類"""
        if schema_type == SchemaType.CREATE:
            return ArticleLinksCreateSchema
        elif schema_type == SchemaType.UPDATE:
            return ArticleLinksUpdateSchema
        raise ValueError(f"未支援的 schema 類型: {schema_type}")
    
    def find_by_article_link(self, article_link: str) -> Optional[ArticleLinks]:
        """根據文章連結查詢"""
        return self.execute_query(
            lambda: self.session.query(self.model_class)
                              .filter_by(article_link=article_link)
                              .first(),
            err_msg=f"查詢文章連結時發生錯誤: {article_link}"
        )

    def find_unscraped_links(self, limit: Optional[int] = 100, source_name: Optional[str] = None) -> List[ArticleLinks]:
        """查詢未爬取的連結"""
        def query_func():
            query = self.session.query(self.model_class).filter_by(is_scraped=False)
            if source_name:
                query = query.filter_by(source_name=source_name)
            if limit:
                query = query.limit(limit)
            return query.all()
            
        return self.execute_query(
            query_func,
            err_msg="查詢未爬取的連結時發生錯誤"
        )

    def count_unscraped_links(self, source_name: Optional[str] = None) -> int:
        """計算未爬取的連結數量"""
        def query_func():
            query = self.session.query(func.count(self.model_class.id)).filter_by(is_scraped=False)
            if source_name:
                query = query.filter_by(source_name=source_name)
            return query.scalar()
            
        return self.execute_query(
            query_func,
            err_msg="計算未爬取的連結數量時發生錯誤"
        )

    def mark_as_scraped(self, article_link: str) -> bool:
        """將文章連結標記為已爬取"""
        def update_func():
            link_entity = self.find_by_article_link(article_link)
            if not link_entity:
                return False
            link_entity.is_scraped = True
            self.session.flush()
            return True
            
        return self.execute_query(
            update_func,
            err_msg=f"標記文章為已爬取時發生錯誤: {article_link}"
        )

    def get_source_statistics(self) -> Dict[str, Dict[str, int]]:
        """獲取各來源的爬取統計"""
        def stats_func():
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
            
        return self.execute_query(
            stats_func,
            err_msg="獲取來源統計時發生錯誤"
        )

    def create(self, entity_data: Dict[str, Any]) -> Optional[ArticleLinks]:
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
        
        # 使用適當的schema進行驗證和創建
        schema_class = self.get_schema_class(SchemaType.CREATE)
        return self._create_internal(entity_data, schema_class)

    def update(self, entity_id: Any, entity_data: Dict[str, Any]) -> Optional[ArticleLinks]:
        """更新文章連結，使用模式驗證
        
        Args:
            entity_id: 連結ID
            entity_data: 更新的資料
            
        Returns:
            Optional[ArticleLinks]: 更新後的實體
        """
        # 使用適當的schema進行驗證和更新
        schema_class = self.get_schema_class(SchemaType.UPDATE)
        return self._update_internal(entity_id, entity_data, schema_class)

    def batch_mark_as_scraped(self, article_links: List[str]) -> Dict[str, Any]:
        """批量將文章連結標記為已爬取"""
        def batch_update_func():
            success_count = 0
            failed_links = []
            
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
            
        return self.execute_query(
            batch_update_func,
            err_msg="批量標記文章為已爬取時發生錯誤"
        )