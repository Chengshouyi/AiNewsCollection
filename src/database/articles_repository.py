from src.database.base_repository import BaseRepository, SchemaType
from src.models.articles_model import Articles
from src.models.articles_schema import ArticleCreateSchema, ArticleUpdateSchema
from typing import Optional, List, Dict, Any, Type
from sqlalchemy import func, or_, case
from sqlalchemy.orm import Query
from src.error.errors import ValidationError
import logging
from pydantic import BaseModel

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



class ArticlesRepository(BaseRepository[Articles]):
    """Article 特定的Repository"""
    
    def get_schema_class(self, schema_type: SchemaType = SchemaType.CREATE) -> Type[BaseModel]:
        """根據操作類型返回對應的schema類"""
        if schema_type == SchemaType.CREATE:
            return ArticleCreateSchema
        elif schema_type == SchemaType.UPDATE:
            return ArticleUpdateSchema
        raise ValueError(f"未支援的 schema 類型: {schema_type}")


        
    def find_by_link(self, link: str) -> Optional[Articles]:
        """根據文章連結查詢"""
        return self.execute_query(lambda: self.session.query(self.model_class).filter_by(link=link).first())

    
    def find_by_category(self, category: str) -> List[Articles]:
        """根據分類查詢文章"""
        return self.execute_query(lambda: self.session.query(self.model_class).filter_by(category=category).all())

    def search_by_title(self, keyword: str, exact_match: bool = False) -> List[Articles]:
        """根據標題搜索文章
        
        Args:
            keyword: 搜索關鍵字
            exact_match: 是否進行精確匹配（預設為模糊匹配）
        
        Returns:
            符合條件的文章列表
        """
        if exact_match:
            # 精確匹配（區分大小寫）
            return self.execute_query(lambda: self.session.query(self.model_class).filter(
                self.model_class.title == keyword
            ).all())
        else:
            # 模糊匹配
            return self.execute_query(lambda: self.session.query(self.model_class).filter(
                self.model_class.title.like(f'%{keyword}%')
            ).all())

    
    def _build_filter_query(self, query: Query, filter_dict: Dict[str, Any]) -> Query:
        """構建過濾查詢"""
        if not filter_dict:
            return query
        
        for key, value in filter_dict.items():
            if key == "is_ai_related":
                query = query.filter(self.model_class.is_ai_related == value)
            elif key == "tags":
                query = query.filter(self.model_class.tags.like(value))
            elif key == "published_at" and isinstance(value, dict):
                if "$gte" in value:
                    query = query.filter(self.model_class.published_at >= value["$gte"])
                if "$lte" in value:
                    query = query.filter(self.model_class.published_at <= value["$lte"])
            elif key == "search_text" and value:
                search_term = f"%{value}%"
                query = query.filter(or_(
                    self.model_class.title.like(search_term),
                    self.model_class.content.like(search_term),
                    self.model_class.summary.like(search_term)
                ))
            else:
                if hasattr(self.model_class, key):
                    query = query.filter(getattr(self.model_class, key) == value)
        
        return query
    
    def get_by_filter(self, filter_dict: Dict[str, Any], limit: Optional[int] = None, offset: Optional[int] = None) -> List[Articles]:
        """根據過濾條件查詢文章"""
        def query_builder():
            query = self.session.query(self.model_class)
            query = self._build_filter_query(query, filter_dict)
                
            if offset is not None:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)
                
            return query.all()
        
        return self.execute_query(
            query_builder,
            err_msg="根據過濾條件查詢文章時發生錯誤"
        )

    def get_source_statistics(self) -> Dict[str, Dict[str, int]]:
        """獲取各來源的爬取統計"""
        def stats_func():
            total_stats = self.session.query(
                self.model_class.source,
                func.count(self.model_class.id).label('total'),
                func.sum(case((self.model_class.is_scraped == False, 1), else_=0)).label('unscraped'),
                func.sum(case((self.model_class.is_scraped == True, 1), else_=0)).label('scraped')
            ).group_by(self.model_class.source).all()
            
            return {
                source: {
                    'total': total,
                    'unscraped': unscraped or 0,
                    'scraped': scraped or 0
                }
                for source, total, unscraped, scraped in total_stats
            }
            
        return self.execute_query(
            stats_func,
            err_msg="獲取來源統計時發生錯誤"
        )
    
    def count(self, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        """計算符合條件的文章數量"""
        def query_builder():
            query = self.session.query(func.count(self.model_class.id))
            query = self._build_filter_query(query, filter_dict or {})
            return query.scalar()
        
        return self.execute_query(
            query_builder,
            err_msg="計算符合條件的文章數量時發生錯誤"
        )

    def search_by_keywords(self, keywords: str) -> List[Articles]:
        """根據關鍵字搜索文章（標題和內容）
        
        Args:
            keywords: 搜索關鍵字
            
        Returns:
            符合條件的文章列表
        """
        return self.get_by_filter({"search_text": keywords})

    def get_category_distribution(self) -> Dict[str, int]:
        """獲取各分類的文章數量分布"""
        def query_builder():
            return self.session.query(
                self.model_class.category,
                func.count(self.model_class.id)
            ).group_by(self.model_class.category).all()
        
        result = self.execute_query(
            query_builder,
            err_msg="獲取各分類的文章數量分布時發生錯誤"
        )
        return {str(category) if category else "未分類": count for category, count in result}

    def find_by_tags(self, tags: List[str]) -> List[Articles]:
        """根據標籤列表查詢文章"""
        def query_builder():
            query = self.session.query(self.model_class)
            for tag in tags:
                query = query.filter(self.model_class.tags.like(f'%{tag}%'))
            return query.all()
        
        return self.execute_query(
            query_builder,
            err_msg="根據標籤列表查詢文章時發生錯誤"
        )
    
    def validate_unique_link(self, link: str, exclude_id: Optional[int] = None, raise_error: bool = True) -> bool:
        """驗證文章連結是否唯一"""
        if not link:
            return True

        def query_builder():
            query = self.session.query(self.model_class).filter_by(link=link)
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
                    raise ValidationError(f"文章不存在，ID={exclude_id}")
                return False
            
            if raise_error:
                raise ValidationError(f"已存在具有相同連結的文章: {link}")
            return False
        
        return True

    def _validate_required_fields(self, entity_data: Dict[str, Any], existing_entity: Optional[Articles] = None) -> Dict[str, Any]:
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
        
        # 檢查必填欄位，排除不可修改欄位link
        required_fields = ['summary', 'source', 'source_url','category', 'is_ai_related', 'title', 'published_at','is_scraped']
        
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
    
    def create(self, entity_data: Dict[str, Any]) -> Optional[Articles]:
        """
        創建文章，添加針對 Articles 的特殊驗證
        
        Args:
            entity_data: 實體資料
            
        Returns:
            創建的文章實體
        """
        # 驗證連結唯一性
        if 'link' in entity_data and entity_data['link']:
            self.validate_unique_link(entity_data['link'])
        
        # 驗證並補充必填欄位
        validated_data = self._validate_required_fields(entity_data)
        
        # 獲取並使用適當的schema進行驗證和創建
        schema_class = self.get_schema_class(SchemaType.CREATE)
        return self._create_internal(validated_data, schema_class)
    
    def batch_create(self, entities_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        批量創建實體
        
        Args:
            entities_data: 實體資料列表
            
        Returns:
            包含成功和失敗資訊的字典
                success_count: 成功創建數量
                fail_count: 失敗數量
                inserted_articles: 成功創建的實體列表
        """
        success_count = 0
        fail_count = 0
        inserted_articles = []
        
        for entity_data in entities_data:
            try:
                # 驗證連結唯一性
                self.validate_unique_link(entity_data['link'])
                
                # 創建實體
                entity = self.model_class(**entity_data)
                self.session.add(entity)
                self.session.flush()
                
                inserted_articles.append(entity)
                success_count += 1
            except Exception as e:
                logger.error(f"批量創建實體失敗: {e}")
                fail_count += 1
                continue
        
        return {
            "success_count": success_count,
            "fail_count": fail_count,
            "inserted_articles": inserted_articles
        }

    def update(self, entity_id: Any, entity_data: Dict[str, Any]) -> Optional[Articles]:
        """
        更新文章，添加針對 Articles 的特殊驗證
        
        Args:
            entity_id: 實體ID
            entity_data: 要更新的實體資料
            
        Returns:
            更新後的文章實體，如果實體不存在則返回None
        """
        # 檢查實體是否存在
        existing_entity = self.get_by_id(entity_id)
        if not existing_entity:
            logger.warning(f"更新文章失敗，ID不存在: {entity_id}")
            return None
        
        # 如果更新資料為空，直接返回已存在的實體
        if not entity_data:
            return existing_entity
            
        # 驗證連結唯一性（如果要更新連結）
        if 'link' in entity_data and entity_data['link'] != getattr(existing_entity, 'link', None):
            self.validate_unique_link(entity_data['link'], exclude_id=entity_id)
            
        # 驗證並補充必填欄位
        validated_data = self._validate_required_fields(entity_data, existing_entity)
        
        # 獲取並使用適當的schema進行驗證和更新
        schema_class = self.get_schema_class(SchemaType.UPDATE)
        return self._update_internal(entity_id, validated_data, schema_class)

    def update_scrape_status(self, link: str, is_scraped: bool = True) -> bool:
        """更新文章連結的爬取狀態"""
        def update_func():
            link_entity = self.find_by_link(link)
            if not link_entity:
                return False
            link_entity.is_scraped = is_scraped
            self.session.flush()
            return True
        
        return self.execute_query(
            update_func,
            err_msg=f"更新文章連結爬取狀態時發生錯誤: {link}"
        )

    def batch_update(self, entity_ids: List[Any], entity_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        批量更新文章，優化處理連結重複的問題
        
        Args:
            entity_ids: 要更新的實體ID列表
            entity_data: 要更新的實體資料
        
        Returns:
            Dict: 包含成功和失敗資訊的字典
        """
        updated_entities = []
        missing_ids = []
        error_ids = []
        
        # 第一步：檢查所有ID是否存在
        existing_entities = {}
        for entity_id in entity_ids:
            entity = self.get_by_id(entity_id)
            if entity:
                existing_entities[entity_id] = entity
            else:
                missing_ids.append(entity_id)
        
        # 第二步：如果要更新link欄位，預先檢查連結是否已存在且屬於非更新範圍內的實體
        if 'link' in entity_data and entity_data['link']:
            # 檢查連結是否存在於其他非更新實體中
            link = entity_data['link']
            def check_link_query():
                query = self.session.query(self.model_class).filter_by(link=link)
                if entity_ids:
                    query = query.filter(~self.model_class.id.in_(entity_ids))
                return query.first()
            
            existing_with_link = self.execute_query(
                check_link_query,
                err_msg="批量更新文章時檢查連結是否存在時發生錯誤"
            )
            
            if existing_with_link:
                # 發現連結衝突，但仍然繼續處理其他實體
                logger.warning(f"無法更新連結，已存在相同連結的文章: {link}")
        
        # 獲取更新用的schema
        schema_class = self.get_schema_class(SchemaType.UPDATE)
        
        # 第三步：逐一更新實體
        for entity_id, entity in existing_entities.items():
            try:
                # 複製一份資料，防止修改原始資料
                entity_data_copy = entity_data.copy()
                
                # 處理連結欄位的特殊情況：如果需要更新連結但與其他實體重複，則跳過該欄位的更新
                if 'link' in entity_data_copy:
                    # 如果當前實體已經具有此連結，則可以更新
                    if entity.link == entity_data_copy['link']:
                        pass  # 允許更新自己的連結
                    else:
                        # 檢查除自身外是否有其他實體具有此連結
                        def check_duplicate_query():
                            query = self.session.query(self.model_class).filter_by(link=entity_data_copy['link'])
                            query = query.filter(self.model_class.id != entity_id)
                            return query.first()
                        
                        duplicate = self.execute_query(
                            check_duplicate_query,
                            err_msg=f"檢查實體 ID={entity_id} 的連結重複性時發生錯誤"
                        )
                        
                        if duplicate:
                            # 如果發現重複，則從更新資料中移除連結欄位
                            logger.warning(f"實體 ID={entity_id} 的連結更新已跳過，因為連結 '{entity_data_copy['link']}' 已存在")
                            entity_data_copy.pop('link', None)
                
                # 如果沒有任何要更新的欄位，則跳過
                if not entity_data_copy:
                    continue
                
                # 驗證並補充必填欄位
                validated_data = self._validate_required_fields(entity_data_copy, entity)
                
                # 更新實體
                result = self._update_internal(entity_id, validated_data, schema_class)
                if result:
                    updated_entities.append(result)
                
            except Exception as e:
                logger.error(f"更新實體 ID={entity_id} 時出錯: {str(e)}")
                error_ids.append(entity_id)
        
        # 返回結果
        return {
            "success_count": len(updated_entities),
            "fail_count": len(missing_ids) + len(error_ids),
            "updated_entities": updated_entities,
            "missing_ids": missing_ids,
            "error_ids": error_ids
        }
    

    def batch_mark_as_scraped(self, links: List[str]) -> Dict[str, Any]:
        """批量將文章連結標記為已爬取"""
        def batch_update_func():
            success_count = 0
            failed_links = []
            
            for link in links:
                try:
                    if self.update_scrape_status(link):
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

    def get_paginated_by_filter(self, filter_dict: Dict[str, Any], page: int, per_page: int, 
                               sort_by: Optional[str] = None, sort_desc: bool = False) -> Dict[str, Any]:
        """根據過濾條件獲取分頁資料
        
        Args:
            filter_dict: 過濾條件字典
            page: 當前頁碼，從1開始
            per_page: 每頁數量
            sort_by: 排序欄位
            sort_desc: 是否降序排列
            
        Returns:
            包含分頁資訊和結果的字典
        """
        def paginated_query():
            # 計算總記錄數
            total = self.count(filter_dict)
            
            # 計算總頁數
            total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0
            
            # 確保頁碼有效
            current_page = max(1, min(page, total_pages)) if total_pages > 0 else 1
            
            # 計算偏移量
            offset = (current_page - 1) * per_page
            
            # 構建基本查詢
            query = self.session.query(self.model_class)
            query = self._build_filter_query(query, filter_dict)
            
            # 添加排序 - 使用兼容 SQLite 的方式
            if sort_by and hasattr(self.model_class, sort_by):
                order_column = getattr(self.model_class, sort_by)
                # SQLite 兼容的排序方式
                query = query.order_by(order_column.desc() if sort_desc else order_column.asc())
            else:
                # 默認按發布時間降序排列
                query = query.order_by(self.model_class.published_at.desc())
            
            # 應用分頁
            query = query.offset(offset).limit(per_page)
            
            # 執行查詢
            items = query.all()
            
            return {
                "items": items,
                "page": current_page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_next": current_page < total_pages,
                "has_prev": current_page > 1
            }
        
        return self.execute_query(
            paginated_query,
            err_msg="根據過濾條件獲取分頁資料時發生錯誤"
        )
    

    def delete_by_link(self, link: str) -> bool:
        """根據文章連結刪除"""
        try:
            article = self.find_by_link(link)
            if not article:
                raise ValidationError(f"文章不存在，連結: {link}")
            return  self.delete(article.id)
        except Exception as e:
            self.session.rollback()
            raise e

    def count_unscraped_links(self, source: Optional[str] = None) -> int:
        """計算未爬取的連結數量"""
        def query_func():
            query = self.session.query(func.count(self.model_class.id)).filter(self.model_class.is_scraped == False)
            if source:
                query = query.filter_by(source=source)
            return query.scalar()
            
        return self.execute_query(
            query_func,
            err_msg="計算未爬取的連結數量時發生錯誤"
        )

    def count_scraped_links(self, source: Optional[str] = None) -> int:
        """計算已爬取的連結數量"""
        def query_func():
            query = self.session.query(func.count(self.model_class.id)).filter(self.model_class.is_scraped == True)
            if source:
                query = query.filter_by(source=source)
            return query.scalar()
            
        return self.execute_query(
            query_func,
            err_msg="計算已爬取的連結數量時發生錯誤"
        )
    
    def find_scraped_links(self, limit: Optional[int] = 100, source: Optional[str] = None) -> List[Articles]:
        """查詢已爬取的連結"""
        def query_func():
            query = self.session.query(self.model_class).filter(self.model_class.is_scraped == True)
            if source:
                query = query.filter_by(source=source)
            if limit:
                query = query.limit(limit)
            return query.all()
            
        return self.execute_query(
            query_func,
            err_msg="查詢已爬取的連結時發生錯誤"
        )
    
    def find_unscraped_links(self, limit: Optional[int] = 100, source: Optional[str] = None) -> List[Articles]:
        """查詢未爬取的連結"""
        def query_func():
            query = self.session.query(self.model_class).filter(self.model_class.is_scraped == False)
            if source:
                query = query.filter_by(source=source)
            if limit:
                query = query.limit(limit)
            return query.all()
            
        return self.execute_query(
            query_func,
            err_msg="查詢未爬取的連結時發生錯誤"
        )