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

    def validate_unique_article_link(self, article_link: str, exclude_id: Optional[int] = None, raise_error: bool = True) -> bool:
        """驗證文章連結是否唯一"""
        if not article_link:
            return True

        def query_builder():
            query = self.session.query(self.model_class).filter_by(article_link=article_link)
            if exclude_id is not None:
                query = query.filter(self.model_class.id != exclude_id)
            return query.first()
        
        existing = self.execute_query(
            query_builder,
            err_msg="驗證文章連結唯一性時發生錯誤"
        )
        
        if existing:
            if exclude_id is not None and not self.get_by_id(exclude_id):
                if raise_error:
                    raise ValidationError(f"文章連結不存在，ID={exclude_id}")
                return False
            
            if raise_error:
                raise ValidationError(f"已存在具有相同連結的文章: {article_link}")
            return False
        
        return True

    def _validate_required_fields(self, entity_data: Dict[str, Any], existing_entity: Optional[ArticleLinks] = None) -> Dict[str, Any]:
        """
        驗證並補充必填欄位
        
        Args:
            entity_data: 實體資料
            existing_entity: 現有實體 (用於更新時)
            
        Returns:
            處理後的實體資料
        """
        # 深度複製避免修改原始資料
        processed_data = entity_data.copy()
        
        # 檢查必填欄位，必須移除不可更新的欄位
        required_fields = ['source_name', 'source_url', 'title', 'summary', 'category', 'published_age', 'is_scraped']
        
        # 如果是更新操作，從現有實體中補充必填欄位
        if existing_entity:
            for field in required_fields:
                if field not in processed_data and hasattr(existing_entity, field):
                    processed_data[field] = getattr(existing_entity, field)
        
        # 檢查是否仍然缺少必填欄位
        missing_fields = [field for field in required_fields if field not in processed_data or processed_data[field] is None]
        if missing_fields:
            raise ValidationError(f"缺少必填欄位: {', '.join(missing_fields)}")
            
        return processed_data

    def create(self, entity_data: Dict[str, Any]) -> Optional[ArticleLinks]:
        """
        創建文章連結，添加針對 ArticleLinks 的特殊驗證
        
        Args:
            entity_data: 實體資料
            
        Returns:
            創建的文章連結實體
        """
        # 驗證連結唯一性
        if 'article_link' in entity_data and entity_data['article_link']:
            self.validate_unique_article_link(entity_data['article_link'])
        
        # 驗證並補充必填欄位
        validated_data = self._validate_required_fields(entity_data)
        
        # 獲取並使用適當的schema進行驗證和創建
        schema_class = self.get_schema_class(SchemaType.CREATE)
        return self._create_internal(validated_data, schema_class)

    def update(self, entity_id: Any, entity_data: Dict[str, Any]) -> Optional[ArticleLinks]:
        """
        更新文章連結，添加針對 ArticleLinks 的特殊驗證
        
        Args:
            entity_id: 實體ID
            entity_data: 要更新的實體資料
            
        Returns:
            更新後的文章連結實體，如果實體不存在則返回None
        """
        # 檢查實體是否存在
        existing_entity = self.get_by_id(entity_id)
        if not existing_entity:
            logger.warning(f"更新文章連結失敗，ID不存在: {entity_id}")
            return None
        
        # 如果更新資料為空，直接返回已存在的實體
        if not entity_data:
            return existing_entity
        
        # 驗證連結唯一性（如果要更新連結）
        if 'article_link' in entity_data and entity_data['article_link'] != getattr(existing_entity, 'article_link', None):
            self.validate_unique_article_link(entity_data['article_link'], exclude_id=entity_id)
        
        # 驗證並補充必填欄位
        validated_data = self._validate_required_fields(entity_data, existing_entity)
        
        # 獲取並使用適當的schema進行驗證和更新
        schema_class = self.get_schema_class(SchemaType.UPDATE)
        return self._update_internal(entity_id, validated_data, schema_class)

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
    
    def update_scrape_status(self, article_link: str, is_scraped: bool = True) -> bool:
        """更新文章連結的爬取狀態"""
        def update_func():
            link_entity = self.find_by_article_link(article_link)
            if not link_entity:
                return False
            link_entity.is_scraped = is_scraped
            self.session.flush()
            return True
        
        return self.execute_query(
            update_func,
            err_msg=f"更新文章連結爬取狀態時發生錯誤: {article_link}"
        )
    
    def delete_by_article_link(self, article_link: str) -> bool:
        """根據文章連結刪除"""
        def delete_func():
            link_entity = self.find_by_article_link(article_link)
            if not link_entity:
                return False
            self.session.delete(link_entity)
            self.session.flush()
            return True
        
        return self.execute_query(
            delete_func,
            err_msg=f"刪除文章連結時發生錯誤: {article_link}"
        )