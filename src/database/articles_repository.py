from src.database.base_repository import BaseRepository, SchemaType
from src.models.articles_model import Articles
from src.models.articles_schema import ArticleCreateSchema, ArticleUpdateSchema
from typing import Optional, List, Dict, Any, Type, Union, overload, Literal
from sqlalchemy import func, or_, case
from sqlalchemy.orm import Query
from src.error.errors import ValidationError, DatabaseOperationError
import logging
from src.models.articles_model import ArticleScrapeStatus

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



class ArticlesRepository(BaseRepository[Articles]):
    """Article 的Repository"""
    
    @overload
    def get_schema_class(self, schema_type: Literal[SchemaType.UPDATE]) -> Type[ArticleUpdateSchema]: ...
    
    @overload
    def get_schema_class(self, schema_type: Literal[SchemaType.CREATE]) -> Type[ArticleCreateSchema]: ...
    
    def get_schema_class(self, schema_type: SchemaType = SchemaType.CREATE) -> Type[Union[ArticleCreateSchema, ArticleUpdateSchema]]:
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
    
    def create(self, entity_data: Dict[str, Any]) -> Optional[Articles]:
        """
        創建文章。如果連結已存在，則觸發更新邏輯。
        先進行 Pydantic 驗證，然後調用內部創建。
        """
        link = entity_data.get('link')
        if link:
            existing_article = self.find_by_link(link)
            if existing_article:
                logger.info(f"文章連結 '{link}' 已存在，將執行更新操作。")
                # 更新操作也會先調用 validate_data
                return self.update(existing_article.id, entity_data)

        try:
            # 1. 設定特定預設值 (如果 Pydantic Schema 沒處理)
            if 'scrape_status' not in entity_data:
                 entity_data['scrape_status'] = ArticleScrapeStatus.LINK_SAVED
            if 'is_scraped' not in entity_data:
                entity_data['is_scraped'] = False
            # created_at/updated_at 由 BaseEntity/Schema 處理

            # 2. 執行 Pydantic 驗證 (使用基類方法)
            validated_data = self.validate_data(entity_data, SchemaType.CREATE)

            # 3. 將已驗證的資料傳給內部方法
            return self._create_internal(validated_data)
        except ValidationError as e:
            logger.error(f"創建 Article 驗證失敗: {e}")
            raise # 重新拋出讓 Service 層處理
        except DatabaseOperationError: # 捕捉來自 _create_internal 的錯誤
             raise # 重新拋出
        except Exception as e: # 捕捉其他意外錯誤
            logger.error(f"創建 Article 時發生未預期錯誤: {e}", exc_info=True)
            raise DatabaseOperationError(f"創建 Article 時發生未預期錯誤: {e}") from e
    
    def batch_create(self, entities_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        批量創建實體，如果存在相同 link 則更新
        
        Args:
            entities_data: 實體資料列表
            
        Returns:
            包含成功和失敗資訊的字典
                success_count: 成功創建數量
                fail_count: 失敗數量
                inserted_articles: 成功創建的實體列表
                failed_articles: 創建失敗的實體資料及錯誤信息
        """
        success_count = 0
        update_count = 0
        fail_count = 0
        inserted_articles = []
        updated_articles = []
        failed_articles = []
        
        for entity_data in entities_data:
            try:
                # 先檢查是否為更新操作
                is_update = False
                if 'link' in entity_data and entity_data['link']:
                    existing_article = self.find_by_link(entity_data['link'])
                    if existing_article:
                        is_update = True
                # 使用 create 方法，它會自動處理更新邏輯
                result = self.create(entity_data)
                if result:
                    # 檢查是否為更新操作
                    if is_update:
                        updated_articles.append(result)
                        update_count += 1
                    else:
                        inserted_articles.append(result)
                        success_count += 1
                else:
                    fail_count += 1
                    failed_articles.append({
                        "data": entity_data,
                        "error": "創建實體返回空值"
                    })
            except Exception as e:
                logger.error(f"批量創建實體失敗: {str(e)} - 資料: {entity_data.get('link', 'N/A')}")
                fail_count += 1
                failed_articles.append({
                    "data": entity_data,
                    "error": str(e)
                })
                continue
        
        return {
            "success_count": success_count,
            "update_count": update_count,
            "fail_count": fail_count,
            "inserted_articles": inserted_articles,
            "updated_articles": updated_articles,
            "failed_articles": failed_articles
        }

    def update(self, entity_id: Any, entity_data: Dict[str, Any]) -> Optional[Articles]:
        """
        更新文章。
        先進行 Pydantic 驗證，然後調用內部更新。
        """
        try:
             # 1. 執行 Pydantic 驗證 (獲取 update payload)
             # 因為ArticleCreateSchema的link是unique，所以不可以更新
             original_link = None
             if 'link' in entity_data:
                original_link = entity_data['link']
                entity_data.pop('link', None)
             update_payload = self.validate_data(entity_data, SchemaType.UPDATE)
             # 恢復原始連結
             if original_link:
                update_payload['link'] = original_link

             # 2. 將已驗證的 payload 傳給內部方法
             return self._update_internal(entity_id, update_payload)
        except ValidationError as e:
             logger.error(f"更新 Article (ID={entity_id}) 驗證失敗: {e}")
             raise # 重新拋出
        except DatabaseOperationError: # 捕捉來自 _update_internal 的錯誤
             raise # 重新拋出
        except Exception as e: # 捕捉其他意外錯誤
            logger.error(f"更新 Article (ID={entity_id}) 時發生未預期錯誤: {e}", exc_info=True)
            raise DatabaseOperationError(f"更新 Article (ID={entity_id}) 時發生未預期錯誤: {e}") from e

    def update_scrape_status(self, link: str, is_scraped: bool = True) -> bool:
        """更新文章連結的爬取狀態"""
        def update_func():
            link_entity = self.find_by_link(link)
            if not link_entity:
                return False
            link_entity.is_scraped = is_scraped
            link_entity.scrape_status = ArticleScrapeStatus.CONTENT_SCRAPED if is_scraped else ArticleScrapeStatus.FAILED
            self.session.flush()
            return True
        
        return self.execute_query(
            update_func,
            err_msg=f"更新文章連結爬取狀態時發生錯誤: {link}"
        )

    def batch_update_by_link(self, entities_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量更新文章
        Args:
            entities_data: 實體資料列表
                link: 文章連結<必要>
                other_data: 其他要更新的資料<必要>

        Returns:
            包含成功和失敗資訊的字典
                success_count: 成功更新數量
                fail_count: 失敗數量
                updated_articles: 成功更新的文章列表
                missing_links: 未找到的文章連結列表
                error_links: 更新過程中出錯的連結列表
        """
        success_count = 0
        fail_count = 0
        updated_articles = []
        missing_links = []
        error_links = []

        for entity_data in entities_data:
            try:
                entity = self.find_by_link(entity_data['link'])
                if not entity:
                    missing_links.append(entity_data['link'])
                    continue

                updated_entity = self.update(entity.id, entity_data)
                if updated_entity:
                    updated_articles.append(updated_entity)
                    success_count += 1
                else:
                    fail_count += 1
                    error_links.append(entity_data['link'])
            except Exception as e:
                logger.error(f"更新實體 link={entity_data.get('link')} 時發生錯誤: {str(e)}")
                error_links.append(entity_data.get('link'))
                fail_count += 1
                continue

        return {
            "success_count": success_count,
            "fail_count": fail_count,
            "updated_articles": updated_articles,
            "missing_links": missing_links,
            "error_links": error_links
        }

    def batch_update_by_ids(self, entity_ids: List[Any], entity_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        批量更新文章的同一組資料，使用單一更新方法確保一致性
        
        Args:
            entity_ids: 要更新的文章ID列表
            entity_data: 要更新的實體資料
        
        Returns:
            Dict: 包含成功和失敗資訊的字典
                success_count: 成功更新數量
                fail_count: 失敗數量
                updated_articles: 成功更新的文章列表
                missing_ids: 未找到的文章ID列表
                error_ids: 更新過程中出錯的ID列表
                invalid_fields: 不合規的欄位列表
        """
        updated_articles = []
        missing_ids = []
        error_ids = []        
        # 如果更新資料為空，直接返回結果
        if not entity_data:
            return {
                "success_count": 0,
                "fail_count": 0,
                "updated_articles": [],
                "missing_ids": [],
                "error_ids": []
            }
        
        
        # 逐一更新實體
        for entity_id in entity_ids:
            try:
                # 使用 self.update 方法更新實體
                updated_entity = self.update(entity_id, entity_data)
                
                if updated_entity is None:
                    # 如果返回 None，表示實體不存在
                    missing_ids.append(entity_id)
                    continue
                    
                updated_articles.append(updated_entity)
                
            except Exception as e:
                logger.error(f"更新實體 ID={entity_id} 時發生錯誤: {str(e)}")
                error_ids.append(entity_id)
                continue
        
        return {
            "success_count": len(updated_articles),
            "fail_count": len(missing_ids) + len(error_ids),
            "updated_articles": updated_articles,
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

    def count_scraped_articles(self, source: Optional[str] = None) -> Dict[str, Any]:
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
        
    def find_articles_by_task_id(self, task_id: int, is_scraped: Optional[bool] = None, limit: Optional[int] = None) -> List[Articles]:
        """根據任務ID查詢相關的文章
        
        Args:
            task_id: 任務ID
            is_scraped: 可選過濾條件，是否已爬取內容
            limit: 可選限制返回數量
            
        Returns:
            符合條件的文章列表
        """
        def query_func():
            query = self.session.query(self.model_class).filter(self.model_class.task_id == task_id)
            
            # 如果指定了是否已爬取內容
            if is_scraped is not None:
                query = query.filter(self.model_class.is_scraped == is_scraped)
                
            # 根據抓取狀態排序，優先返回PENDING狀態的文章
            query = query.order_by(
                case(
                    (self.model_class.scrape_status == ArticleScrapeStatus.PENDING, 0),
                    (self.model_class.scrape_status == ArticleScrapeStatus.LINK_SAVED, 1),
                    (self.model_class.scrape_status == ArticleScrapeStatus.FAILED, 2),
                    (self.model_class.scrape_status == ArticleScrapeStatus.CONTENT_SCRAPED, 3),
                    else_=4
                ).asc()
            )
            
            # 如果指定了限制數量
            if limit is not None:
                query = query.limit(limit)
                
            return query.all()
            
        return self.execute_query(
            query_func,
            err_msg=f"根據任務ID={task_id}查詢文章時發生錯誤"
        )
    
    def count_articles_by_task_id(self, task_id: int, is_scraped: Optional[bool] = None) -> int:
        """計算特定任務的文章數量
        
        Args:
            task_id: 任務ID
            is_scraped: 可選過濾條件，是否已爬取內容
            
        Returns:
            符合條件的文章數量
        """
        def query_func():
            query = self.session.query(func.count(self.model_class.id)).filter(self.model_class.task_id == task_id)
            
            # 如果指定了是否已爬取內容
            if is_scraped is not None:
                query = query.filter(self.model_class.is_scraped == is_scraped)
                
            return query.scalar()
            
        return self.execute_query(
            query_func,
            err_msg=f"計算任務ID={task_id}的文章數量時發生錯誤"
        )