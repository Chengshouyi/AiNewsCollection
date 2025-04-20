from src.database.base_repository import BaseRepository, SchemaType
from src.models.articles_model import Articles
from src.models.articles_schema import ArticleCreateSchema, ArticleUpdateSchema
from typing import Optional, List, Dict, Any, Type, Union, overload, Literal, Tuple, cast
from sqlalchemy import func, or_, case, desc, asc
from sqlalchemy.orm import Query
from src.error.errors import ValidationError, DatabaseOperationError, InvalidOperationError
from sqlalchemy.exc import IntegrityError
import logging
from src.models.articles_model import ArticleScrapeStatus
from datetime import datetime, timezone, timedelta
# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



class ArticlesRepository(BaseRepository[Articles]):
    """Article 的Repository"""

    @classmethod
    @overload
    def get_schema_class(cls, schema_type: Literal[SchemaType.UPDATE]) -> Type[ArticleUpdateSchema]: ...

    @classmethod
    @overload
    def get_schema_class(cls, schema_type: Literal[SchemaType.CREATE]) -> Type[ArticleCreateSchema]: ...
    
    @classmethod
    def get_schema_class(cls, schema_type: SchemaType = SchemaType.CREATE) -> Type[Union[ArticleCreateSchema, ArticleUpdateSchema]]:
        """根據操作類型返回對應的schema類"""
        if schema_type == SchemaType.CREATE:
            return ArticleCreateSchema
        elif schema_type == SchemaType.UPDATE:
            return ArticleUpdateSchema
        raise ValueError(f"未支援的 schema 類型: {schema_type}")


        
    def find_by_link(self, link: str) -> Optional[Articles]:
        """根據文章連結查詢"""
        return self.execute_query(lambda: self.session.query(self.model_class).filter_by(link=link).first())

    
    def find_by_category(self, category: str, 
                         limit: Optional[int] = None, 
                         offset: Optional[int] = None,
                         is_preview: bool = False, 
                         preview_fields: Optional[List[str]] = None
                         ) -> Union[List[Articles], List[Dict[str, Any]]]:
        """根據分類查詢文章，支援分頁和預覽"""
        # Use base class find_by_filter and pass parameters
        return self.find_by_filter(
            filter_criteria={"category": category},
            limit=limit,
            offset=offset,
            is_preview=is_preview,
            preview_fields=preview_fields
        )

    def search_by_title(self, keyword: str, exact_match: bool = False, 
                        limit: Optional[int] = None, 
                        offset: Optional[int] = None,
                        is_preview: bool = False,
                        preview_fields: Optional[List[str]] = None
                        ) -> Union[List[Articles], List[Dict[str, Any]]]:
        """根據標題搜索文章，支援分頁和預覽
        
        Args:
            keyword: 搜索關鍵字
            exact_match: 是否進行精確匹配（預設為模糊匹配）
            limit: 限制數量
            offset: 偏移量
            is_preview: 是否預覽模式
            preview_fields: 預覽欄位
        
        Returns:
            符合條件的文章列表 (模型實例或字典)
        """
        if exact_match:
            # 精確匹配: 使用基類的 find_by_filter
            return self.find_by_filter(
                filter_criteria={"title": keyword},
                limit=limit,
                offset=offset,
                is_preview=is_preview,
                preview_fields=preview_fields
            )
        else:
            # 模糊匹配: 保留原有實現，但添加預覽和 limit/offset
            def query_builder():
                # --- Preview Logic ---
                query_entities = [self.model_class]
                valid_preview_fields = []
                local_is_preview = is_preview
                if local_is_preview and preview_fields:
                    valid_preview_fields = [f for f in preview_fields if hasattr(self.model_class, f)]
                    if valid_preview_fields:
                        query_entities = [getattr(self.model_class, f) for f in valid_preview_fields]
                    else:
                        logger.warning(f"search_by_title (fuzzy) 預覽欄位無效: {preview_fields}，返回完整物件。")
                        local_is_preview = False
                # --- End Preview Logic ---

                query = self.session.query(*query_entities).filter(
                    self.model_class.title.like(f'%{keyword}%')
                )
                
                # Apply offset and limit
                if offset is not None:
                    query = query.offset(offset)
                if limit is not None:
                    query = query.limit(limit)
                    
                raw_results = query.all()

                # --- Result Transformation ---
                if local_is_preview and valid_preview_fields:
                    return [dict(zip(valid_preview_fields, row)) for row in raw_results]
                else:
                    return raw_results
                # --- End Result Transformation ---

            return self.execute_query(query_builder, err_msg=f"模糊搜索標題 '{keyword}' 時出錯")

    def search_by_keywords(self, keywords: str, 
                           limit: Optional[int] = None, 
                           offset: Optional[int] = None,
                           is_preview: bool = False,
                           preview_fields: Optional[List[str]] = None
                           ) -> Union[List[Articles], List[Dict[str, Any]]]:
        """根據關鍵字搜索文章（標題、內容和摘要），支援分頁和預覽
        
        Args:
            keywords: 搜索關鍵字
            limit: 限制數量
            offset: 偏移量
            is_preview: 是否預覽模式
            preview_fields: 預覽欄位
            
        Returns:
            符合條件的文章列表 (模型實例或字典)
        """
        if not keywords or not isinstance(keywords, str):
             logger.warning("search_by_keywords 需要一個非空字串關鍵字。")
             return []
             
        # Use base class find_by_filter and pass parameters
        # _apply_filters in base class handles "search_text" if needed, 
        # otherwise we might need _build_filter_query logic here if base class doesn't support it.
        # Assuming BaseRepository._apply_filters now handles 'search_text' or similar custom logic.
        # If not, this needs to revert to using _build_filter_query.
        # For now, assume find_by_filter is sufficient.
        filter_criteria = {"search_text": keywords} # Use a key recognized by _apply_filters if possible

        # If BaseRepository._apply_filters cannot handle 'search_text', 
        # we must use the custom query logic with preview handling like in search_by_title (fuzzy)
        # Let's assume for now BaseRepository handles it:
        return self.find_by_filter(
            filter_criteria=filter_criteria, 
            limit=limit, 
            offset=offset,
            is_preview=is_preview,
            preview_fields=preview_fields
        )

    def get_statistics(self) -> Dict[str, Any]:
        """獲取文章統計信息"""
        def stats_func():
            total_count = self.count()
            ai_related_count = self.count({"is_ai_related": True})
            category_distribution = self.get_category_distribution()
            source_distribution = self.get_source_distribution()
            scrape_status_distribution = self.get_scrape_status_distribution()
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            recent_count = self.count({"published_at": {"$gte": week_ago}})
            
            return {
                'total_count': total_count,
                'ai_related_count': ai_related_count,
                'category_distribution': category_distribution, 
                'recent_count': recent_count,
                'source_distribution': source_distribution,
                'scrape_status_distribution': scrape_status_distribution
            }
        
        return self.execute_query(
            stats_func,
            err_msg="獲取文章統計信息時發生錯誤"
        )
    def get_scrape_status_distribution(self) -> Dict[str, int]:
        """獲取各爬取狀態的統計 (返回字典)"""
        def stats_func():
            # 查詢返回 (status_enum, count) 的元組列表
            result = self.session.query(
                self.model_class.scrape_status,
                func.count(self.model_class.id)
            ).group_by(self.model_class.scrape_status).all()
            # 將結果轉換為字典 {status_name: count}
            return {
                # 使用 status.name 將 Enum 成員轉為字串鍵
                status.value if isinstance(status, ArticleScrapeStatus) else str(status): count 
                for status, count in result
            }
        
        return self.execute_query(
            stats_func,
            err_msg="獲取爬取狀態統計時發生錯誤"
        )
    
    def get_source_distribution(self) -> Dict[str, int]:
        """獲取各來源的統計 (返回字典)"""
        def stats_func():
             # 查詢返回 (source_string, count) 的元組列表
            result = self.session.query(
                self.model_class.source,
                func.count(self.model_class.id)
            ).group_by(self.model_class.source).all()
            # 將結果轉換為字典 {source_name: count}
            return {
                # 確保來源是字串，處理 None 的情況
                str(source) if source else "未知來源": count 
                for source, count in result
            }
        
        return self.execute_query(
            stats_func,
            err_msg="獲取來源統計時發生錯誤"
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
            query = self._apply_filters(query, filter_dict or {})
            result = query.scalar()
            return result if result is not None else 0
        
        return self.execute_query(
            query_builder,
            err_msg="計算符合條件的文章數量時發生錯誤"
        )

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

    def find_by_tags(self, tags: List[str], 
                     limit: Optional[int] = None, 
                     offset: Optional[int] = None,
                     is_preview: bool = False,
                     preview_fields: Optional[List[str]] = None
                     ) -> Union[List[Articles], List[Dict[str, Any]]]:
        """根據標籤列表查詢文章 (OR 邏輯)，支援分頁和預覽"""
        if not tags or not isinstance(tags, list):
            logger.warning("find_by_tags 需要一個非空的標籤列表。")
            return [] 
            
        def query_builder():
            # --- Preview Logic ---
            query_entities = [self.model_class]
            valid_preview_fields = []
            local_is_preview = is_preview
            if local_is_preview and preview_fields:
                valid_preview_fields = [f for f in preview_fields if hasattr(self.model_class, f)]
                if valid_preview_fields:
                    query_entities = [getattr(self.model_class, f) for f in valid_preview_fields]
                else:
                    logger.warning(f"find_by_tags 預覽欄位無效: {preview_fields}，返回完整物件。")
                    local_is_preview = False
            # --- End Preview Logic ---

            query = self.session.query(*query_entities)

            # 創建用於存放 LIKE 條件的列表
            conditions = []
            for tag in tags:
                if isinstance(tag, str) and tag.strip(): 
                    conditions.append(self.model_class.tags.like(f'%{tag.strip()}%'))
                else:
                    logger.warning(f"find_by_tags 收到無效標籤: {tag}, 已忽略。")
            
            # 如果有有效的條件，使用 or_ 連接它們
            if conditions:
                query = query.filter(or_(*conditions))
            else:
                logger.info("find_by_tags: 沒有提供有效的標籤條件。")
                return [] 
                
            # Apply offset and limit
            if offset is not None:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)

            raw_results = query.all()

            # --- Result Transformation ---
            if local_is_preview and valid_preview_fields:
                return [dict(zip(valid_preview_fields, row)) for row in raw_results]
            else:
                return raw_results
            # --- End Result Transformation ---

        return self.execute_query(
            query_builder,
            err_msg="根據標籤列表查詢文章時發生錯誤"
        )
    
    def validate_unique_link(self, link: str, exclude_id: Optional[int] = None, raise_error: bool = True) -> bool:
        """驗證文章連結是否唯一，不允許空連結。"""
        # 檢查連結是否為空或僅包含空白
        if not link or not link.strip():
             # 根據測試預期，拋出 ValueError
             raise ValidationError("連結不可為空")

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
            # 檢查提供的 exclude_id 是否有效
            # if exclude_id is not None and not self.get_by_id(exclude_id):
            #     if raise_error:
            #         raise ValidationError(f"文章不存在，ID={exclude_id}")
            #     return False
            
            if raise_error:
                raise ValidationError(f"已存在具有相同連結的文章: {link}")
            return False
        
        return True
    
    def create(self, entity_data: Dict[str, Any]) -> Optional[Articles]:
        """
        創建文章。如果連結已存在，則觸發更新邏輯。
        先進行 Pydantic 驗證，然後調用內部創建。
        
        Args:
            entity_data: 實體資料字典。

        Returns:
            創建或更新後的 Articles 實例，如果發生錯誤則返回 None 或拋出異常。
        
        Raises:
            ValidationError: 如果輸入資料驗證失敗。
            DatabaseOperationError: 如果資料庫操作失敗。
            Exception: 其他未預期錯誤。
        """
        link = entity_data.get('link')
        if link:
            existing_article = self.find_by_link(link)
            if existing_article:
                error_msg = f"文章連結 '{link}' 已存在，驗證失敗。"
                logger.info(error_msg)
                raise ValidationError(error_msg)
                # 相同連結更新這種業務邏輯應該在 Service 層處理
                # return self.update(existing_article.id, entity_data)

        try:
            # 1. 設定特定預設值 (如果 Pydantic Schema 沒處理)
            #    這些值應該由 Schema 的 default 或 default_factory 處理，
            #    或者在 Service 層處理是更好的實踐。
            #    這裡保留以防萬一，但建議移至 Schema 或 Service。
            if 'scrape_status' not in entity_data:
                 entity_data['scrape_status'] = ArticleScrapeStatus.LINK_SAVED
            if 'is_scraped' not in entity_data:
                entity_data['is_scraped'] = False
            # created_at/updated_at 由 BaseEntity/Schema 處理

            # 2. 執行 Pydantic 驗證 (使用基類方法)
            #    validate_data 失敗會直接拋出 ValidationError
            validated_data = self.validate_data(entity_data, SchemaType.CREATE)
            
            # 檢查 validate_data 的返回值，它返回 Optional[Dict[str, Any]]
            if validated_data is None:
                # Pydantic 驗證失敗應該拋出 ValidationError
                error_msg = "創建 Article 時驗證步驟失敗"
                logger.error(error_msg)
                raise ValidationError(error_msg)
            
            # 3. 將已驗證的資料傳給內部方法 (_create_internal 失敗會拋出異常)
            #    _create_internal 返回 Optional[Articles]
            created_article = self._create_internal(validated_data)
            return created_article

        except ValidationError as e:
            logger.error(f"創建 Article 驗證失敗: {e}")
            raise # 重新拋出讓上層處理
        except DatabaseOperationError as e: # 捕捉來自 _create_internal 或 validate_data 的錯誤
            logger.error(f"創建 Article 時資料庫操作失敗: {e}")
            raise # 重新拋出
        except Exception as e: # 捕捉其他意外錯誤
            logger.error(f"創建 Article 時發生未預期錯誤: {e}", exc_info=True)
            # 重新包裝成 DatabaseOperationError 或更具體的錯誤類型
            raise DatabaseOperationError(f"創建 Article 時發生未預期錯誤: {e}") from e
    
    def batch_create(self, entities_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        批量創建實體，如果存在相同 link 則更新
        
        Args:
            entities_data: 實體資料列表
            
        Returns:
            包含成功和失敗資訊的字典
                success_count: 成功創建數量
                update_count: 成功更新數量
                fail_count: 失敗數量
                inserted_articles: 成功創建的實體列表 (Articles objects)
                updated_articles: 成功更新的實體列表 (Articles objects)
                failed_articles: 創建失敗的實體資料及錯誤信息
        """
        success_count = 0
        update_count = 0
        fail_count = 0
        inserted_articles: List[Articles] = []
        updated_articles: List[Articles] = []
        failed_articles: List[Dict[str, Any]] = []
        
        for entity_data in entities_data:
            link = entity_data.get('link')
            is_update = False
            try:
                # 先檢查是否為更新操作
                if link:
                    existing_article = self.find_by_link(link)
                    if existing_article:
                        is_update = True
                
                # 使用 create 方法，它會自動處理創建或更新邏輯
                # create 現在返回 Optional[Articles]
                result_article = self.create(entity_data) 
                
                if result_article:
                    if is_update:
                        updated_articles.append(result_article)
                        update_count += 1
                    else:
                        inserted_articles.append(result_article)
                        success_count += 1
                # else:
                    # 如果 create 返回 None，這通常表示在 create 方法內部發生了
                    # 被捕獲但未重新拋出的異常，或者邏輯允許返回 None (目前不會)。
                    # 應該檢查 create 方法的實現。
                    # logger.warning(f"創建/更新 Link: {link or 'N/A'} 返回 None")
                    # fail_count += 1
                    # failed_articles.append({
                    #     "data": entity_data,
                    #     "error": "創建或更新實體返回空值"
                    # })

            except (ValidationError, DatabaseOperationError) as e:
                logger.error(f"批量操作實體失敗 (Link: {link or 'N/A'}): {str(e)}")
                fail_count += 1
                failed_articles.append({
                    "data": entity_data,
                    "error": str(e)
                })
                # 考慮是否需要在事務中進行 rollback
                # self.session.rollback()
            except Exception as e:
                logger.error(f"批量操作實體時發生未預期錯誤 (Link: {link or 'N/A'}): {str(e)}", exc_info=True)
                fail_count += 1
                failed_articles.append({
                    "data": entity_data,
                    "error": f"未預期錯誤: {str(e)}"
                })
                # 考慮是否需要在事務中進行 rollback
                # self.session.rollback() # 考慮事務回滾
                continue # 確保繼續處理下一個
        
        # 批量操作通常應在一個事務中完成，這裡未顯式處理事務
        # 如果需要原子性，應在調用此方法的外層管理事務
        # try:
        #     self.session.commit() 
        # except Exception:
        #     self.session.rollback()
        #     raise
            
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
        
        Args:
            entity_id: 要更新的實體 ID。
            entity_data: 包含更新欄位的字典。

        Returns:
            更新後的 Articles 實例，如果未找到實體或未做任何更改則返回 None，
            如果發生錯誤則拋出異常。

        Raises:
            ValidationError: 如果輸入資料驗證失敗或包含不可變欄位。
            DatabaseOperationError: 如果資料庫操作失敗。
            Exception: 其他未預期錯誤。
        """
        try:
            # 1. 獲取更新 Schema 以檢查不可變欄位
            update_schema_class = self.get_schema_class(SchemaType.UPDATE)
            immutable_fields = update_schema_class.get_immutable_fields()
            
            # 創建 payload 副本以進行驗證，排除不可變欄位
            payload_for_validation = entity_data.copy()
            
            # 檢查是否有嘗試更新不可變欄位
            invalid_immutable_updates = []
            for field in immutable_fields:
                 if field in payload_for_validation:
                     invalid_immutable_updates.append(field)
                     # 從驗證的 payload 中移除，防止傳遞給 validate_data
                     # 注意：'link' 通常是不可變的，這裡確保它被移除
                     payload_for_validation.pop(field, None) 
                     
            # 預設為協助移除不可更新欄位，
            if invalid_immutable_updates:
                 raise ValidationError(f"不能更新不可變欄位: {', '.join(invalid_immutable_updates)}")

            # 如果移除了不可變欄位後，沒有其他欄位需要更新，則提前返回
            if not payload_for_validation:
                 logger.debug(f"更新 Article (ID={entity_id}) 的 payload 為空 (移除非法欄位後)，跳過驗證和更新。")
                 # 可以選擇返回 None 或獲取當前實體返回
                 # return self.get_by_id(entity_id) # 返回未更改的實體
                 return None # 表示無操作

            # 2. 執行 Pydantic 驗證 (使用基類方法)
            #    validate_data 使用 Update Schema 時，只包含明確傳入的欄位 (exclude_unset=True)
            #    如果驗證失敗，會拋出 ValidationError
            validated_payload = self.validate_data(payload_for_validation, SchemaType.UPDATE)

            # validated_payload 現在是 Optional[Dict[str, Any]]
            if validated_payload is None:
                 # 這種情況不應發生，因為 validate_data 在失敗時會拋出 ValidationError
                 error_msg = f"更新 Article (ID={entity_id}) 時驗證步驟失敗"
                 logger.error(error_msg)
                 raise ValidationError(error_msg)
                 
            # 如果 Pydantic 驗證後的 payload 為空 (例如，所有欄位都是 None 且被 exclude_unset 排除)
            # _update_internal 應該能處理空字典，並返回 None (無變更)
            if not validated_payload:
                logger.debug(f"更新 Article (ID={entity_id}) 驗證後的 payload 為空，無需更新資料庫。")
                return None # 表示無變更

            # 3. 將已驗證的 payload 傳給內部方法 (_update_internal 失敗會拋出異常)
            #    _update_internal 返回 Optional[Articles]
            updated_article = self._update_internal(entity_id, validated_payload)
            return updated_article

        except ValidationError as e:
             logger.error(f"更新 Article (ID={entity_id}) 驗證失敗: {e}")
             raise # 重新拋出
        except DatabaseOperationError as e: # 捕捉來自 _update_internal 或 validate_data 的內部錯誤
             logger.error(f"更新 Article (ID={entity_id}) 時資料庫操作失敗: {e}")
             raise # 重新拋出
        except Exception as e: # 捕捉其他意外錯誤
            logger.error(f"更新 Article (ID={entity_id}) 時發生未預期錯誤: {e}", exc_info=True)
            raise DatabaseOperationError(f"更新 Article (ID={entity_id}) 時發生未預期錯誤: {e}") from e

    def update_scrape_status(self, link: str, is_scraped: bool = True, status: Optional[ArticleScrapeStatus] = None) -> bool:
        """更新文章連結的爬取狀態和狀態標籤"""
        def update_func():
            link_entity = self.find_by_link(link)
            if not link_entity:
                logger.warning(f"嘗試更新爬取狀態，但找不到連結: {link}")
                return False
            
            entity_changed = False
            # 確保 is_scraped 是布爾值
            is_scraped_bool = bool(is_scraped)
            
            if link_entity.is_scraped != is_scraped_bool:
                link_entity.is_scraped = is_scraped_bool
                entity_changed = True
                
            # 根據 is_scraped 和傳入的 status 更新狀態標籤
            target_status = status
            if target_status is None: # 如果未明確傳入 status
                if is_scraped_bool:
                    target_status = ArticleScrapeStatus.CONTENT_SCRAPED
                elif link_entity.scrape_status not in [ArticleScrapeStatus.FAILED, ArticleScrapeStatus.PENDING]:
                    # 只有當 is_scraped 為 False 且當前狀態不是 FAILED 或 PENDING 時，
                    # 才將其設為 FAILED (避免覆蓋 PENDING 狀態)
                    target_status = ArticleScrapeStatus.FAILED
            
            if target_status is not None and isinstance(target_status, ArticleScrapeStatus) and link_entity.scrape_status != target_status:
                link_entity.scrape_status = target_status
                entity_changed = True
            elif target_status is not None and not isinstance(target_status, ArticleScrapeStatus):
                 logger.warning(f"更新連結 '{link}' 的 scrape_status 時提供了無效的類型: {type(target_status)}, 已忽略。")

            if entity_changed:
                logger.debug(f"更新連結 '{link}' 爬取狀態為 is_scraped={is_scraped_bool}, status={link_entity.scrape_status.name}")
                return True
            else:
                logger.debug(f"連結 '{link}' 爬取狀態未變更，跳過更新。")
                # 即使未變更，操作本身也可以視為成功，返回 True 可能更合適
                # 取決於調用者期望的語義
                return True # 改為返回 True 表示操作完成 (即使無變化)
        
        try:
            # find_by_link 和 flush 可能引發異常，由 execute_query 處理
            return self.execute_query(
                update_func,
                err_msg=f"更新文章連結爬取狀態時發生錯誤: {link}"
            )
        except Exception as e:
             # 捕獲 execute_query 可能未處理的異常 (雖然不太可能)
             logger.error(f"更新連結 {link} 爬取狀態時發生未預期錯誤: {e}", exc_info=True)
             raise # 重新拋出以通知上層

    def batch_update_by_link(self, entities_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量更新文章
        Args:
            entities_data: 實體資料列表, 每個字典必須包含 'link' 和其他要更新的欄位。

        Returns:
            包含成功和失敗資訊的字典
                success_count: 成功更新數量 (包括無變化的更新)
                fail_count: 失敗數量
                updated_articles: 成功更新的文章列表 (Articles objects)
                missing_links: 未找到的文章連結列表
                error_details: 更新過程中出錯的連結及錯誤信息列表
        """
        success_count = 0
        fail_count = 0
        updated_articles: List[Articles] = []
        missing_links: List[str] = []
        error_details: List[Dict[str, Any]] = []

        for entity_data in entities_data:
            link = entity_data.get('link')
            if not link or not isinstance(link, str):
                logger.warning(f"批量更新缺少有效的 'link' 鍵: {entity_data}")
                fail_count += 1
                error_details.append({"link": link, "error": "缺少有效的 'link' 鍵"})
                continue

            try:
                # 創建要更新的數據副本，移除 link 本身
                update_payload = entity_data.copy()
                update_payload.pop('link', None)
                
                if not update_payload: # 如果沒有提供任何要更新的欄位
                    logger.debug(f"連結 '{link}' 的更新 payload 為空，跳過。")
                    continue

                entity = self.find_by_link(link)
                if not entity:
                    missing_links.append(link)
                    fail_count += 1 # 未找到也計入失敗
                    continue

                # 使用 update 方法，它包含驗證邏輯
                # update 返回 Optional[Articles] 或拋出異常
                updated_entity = self.update(entity.id, update_payload)
                
                # update 成功執行（未拋異常），無論是否實際修改數據，都計為成功
                success_count += 1
                if updated_entity:
                    updated_articles.append(updated_entity)
                else:
                    # 如果返回 None，表示沒有實際更新，但操作成功
                    # 可以選擇將未更改的實體添加到 updated_articles
                    # updated_articles.append(entity)
                    logger.debug(f"連結 '{link}' 的更新未導致實際變更。")

            except (ValidationError, DatabaseOperationError) as e:
                logger.error(f"更新實體 link={link} 時發生錯誤: {str(e)}")
                fail_count += 1
                error_details.append({"link": link, "error": str(e)})
                # self.session.rollback() # 考慮事務回滾
            except Exception as e:
                logger.error(f"更新實體 link={link} 時發生未預期錯誤: {str(e)}", exc_info=True)
                fail_count += 1
                error_details.append({"link": link, "error": f"未預期錯誤: {str(e)}"})
                # self.session.rollback() # 考慮事務回滾
                continue

        # 事務管理應在外層處理

        return {
            "success_count": success_count,
            "fail_count": fail_count,
            "updated_articles": updated_articles,
            "missing_links": missing_links,
            "error_details": error_details
        }

    def batch_update_by_ids(self, entity_ids: List[Any], entity_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        批量使用相同的資料更新多個文章 ID。
        
        Args:
            entity_ids: 要更新的文章ID列表。
            entity_data: 要應用於每個文章的更新資料字典。
        
        Returns:
            Dict: 包含成功和失敗資訊的字典
                success_count: 成功更新數量 (包括無變化的更新)
                fail_count: 失敗數量 (ID不存在或更新時出錯)
                updated_articles: 成功更新的文章列表 (Articles objects)
                missing_ids: 未找到的文章ID列表
                error_details: 更新過程中出錯的ID及錯誤信息列表
        """
        updated_articles: List[Articles] = []
        missing_ids: List[Any] = []
        error_details: List[Dict[str, Any]] = []      
        success_count = 0 # 初始化成功計數
        
        # 如果更新資料為空，直接返回結果
        if not entity_data:
             logger.warning("batch_update_by_ids 收到空的 entity_data，不執行任何更新。")
             return {
                "success_count": 0,
                "fail_count": 0,
                "updated_articles": [],
                "missing_ids": [],
                "error_details": []
             }

        # 預先檢查不可變欄位，如果 entity_data 包含不可變欄位，則直接失敗
        try:
             update_schema_class = self.get_schema_class(SchemaType.UPDATE)
             immutable_fields = update_schema_class.get_immutable_fields()
             invalid_immutable_updates = [f for f in immutable_fields if f in entity_data]
             if invalid_immutable_updates:
                 raise ValidationError(f"批量更新嘗試修改不可變欄位: {', '.join(invalid_immutable_updates)}")
        except ValidationError as e:
             logger.error(f"批量更新因包含不可變欄位而中止: {e}")
             return {
                "success_count": 0,
                "fail_count": len(entity_ids), # 所有 ID 都算失敗
                "updated_articles": [],
                "missing_ids": [],
                "error_details": [{"id": "*", "error": str(e)}] # 指示是全局錯誤
             }

        # 逐一更新實體
        for entity_id in entity_ids:
            try:
                # 使用 self.update 方法更新實體
                # update 返回 Optional[Articles] 或拋出異常
                updated_entity = self.update(entity_id, entity_data.copy()) # 傳遞副本以防萬一
                
                # update 成功執行（未拋異常），計為成功
                success_count += 1
                if updated_entity:
                    updated_articles.append(updated_entity)
                else:
                    # 返回 None 表示無變化，但操作成功
                    logger.debug(f"ID={entity_id} 的更新完成，但無數據變更。")
                    # 可以選擇加入未更改的實體
                    # current_entity = self.get_by_id(entity_id)
                    # if current_entity: updated_articles.append(current_entity)

            except DatabaseOperationError as e:
                 # 檢查是否是 "找不到 ID" 的錯誤 (依賴基類的錯誤訊息)
                 if f"找不到ID為{entity_id}的實體" in str(e):
                      missing_ids.append(entity_id)
                 else:
                      logger.error(f"更新實體 ID={entity_id} 時發生資料庫錯誤: {str(e)}")
                      error_details.append({"id": entity_id, "error": str(e)})
                 # self.session.rollback() # 考慮事務
            except ValidationError as e:
                 logger.error(f"更新實體 ID={entity_id} 時發生驗證錯誤: {str(e)}")
                 error_details.append({"id": entity_id, "error": str(e)})
                 # self.session.rollback() # 考慮事務
            except Exception as e:
                logger.error(f"更新實體 ID={entity_id} 時發生未預期錯誤: {str(e)}", exc_info=True)
                error_details.append({"id": entity_id, "error": f"未預期錯誤: {str(e)}"})
                # self.session.rollback() # 考慮事務
                continue
        
        # 失敗計數是未找到的 ID 和更新出錯的 ID 總和
        fail_count = len(missing_ids) + len(error_details)

        # 事務管理應在外層處理

        return {
            "success_count": success_count,
            "fail_count": fail_count,
            "updated_articles": updated_articles,
            "missing_ids": missing_ids,
            "error_details": error_details
        }
    

    def batch_mark_as_scraped(self, links: List[str]) -> Dict[str, Any]:
        """批量將文章連結標記為已爬取 (is_scraped=True, status=CONTENT_SCRAPED)"""
        success_count = 0
        fail_count = 0
        failed_links: List[str] = []
        processed_links = 0 # 跟蹤處理了多少個連結
        
        for link in links:
            processed_links += 1
            try:
                # 調用已更新的 update_scrape_status
                # 它現在在無變化時也返回 True
                result = self.update_scrape_status(link, is_scraped=True, status=ArticleScrapeStatus.CONTENT_SCRAPED)
                if result:
                    success_count += 1
                else:
                    # 如果 update_scrape_status 返回 False，表示連結未找到
                    # （因為無變化的情況現在返回 True）
                    logger.warning(f"嘗試標記為已爬取，但找不到連結: {link}")
                    failed_links.append(link)
                    fail_count += 1
            except Exception as e:
                # update_scrape_status 內部已記錄錯誤，這裡記錄失敗的連結
                logger.error(f"批量標記連結 {link} 時 update_scrape_status 拋出異常: {e}")
                failed_links.append(link)
                fail_count += 1
                # self.session.rollback() # 考慮事務
        
        # 事務管理應在外層處理
        
        return {
            "success_count": success_count,
            "fail_count": fail_count,
            "failed_links": failed_links
        }

    def get_paginated_by_filter(self, filter_dict: Dict[str, Any], page: int, per_page: int, 
                               sort_by: Optional[str] = None, sort_desc: bool = False) -> Dict[str, Any]:
        """根據過濾條件獲取分頁資料 (現在使用 BaseRepository.find_paginated)"""
        # 如果未指定排序欄位，預設按 published_at 降序排序
        if sort_by is None:
            sort_by = 'published_at'
            sort_desc = True
            
        # 直接調用基類的方法，它會使用我們覆寫的 _apply_filters
        return self.find_paginated(
            filter_criteria=filter_dict,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_desc=sort_desc,
            # 預設 is_preview=False，除非需要在這裡覆寫
        )
    
    def delete_by_link(self, link: str) -> bool:
        """根據文章連結刪除"""
        if not link:
             raise ValueError("必須提供文章連結才能刪除")
             
        try:
            article = self.find_by_link(link)
            if not article:
                 logger.warning(f"嘗試刪除但找不到文章，連結: {link}")
                 raise ValidationError(f"連結 '{link}' 不存在，無法刪除")
            # 調用基類的 delete 方法
            # BaseRepository.delete 會處理找不到 ID 的情況（雖然這裡我們保證 article.id 存在）
            # 並處理 IntegrityError
            return self.delete(article.id) 
        except IntegrityError as e:
            # 基類 delete 內部已處理了 rollback 和 _handle_integrity_error
            # _handle_integrity_error 會拋出 IntegrityValidationError
            logger.error(f"刪除連結 {link} 時發生完整性約束錯誤: {e}")
            raise # 重新拋出 IntegrityValidationError (或讓 BaseRepository 處理)
        except DatabaseOperationError as e:
            # 基類 delete 可能拋出 DatabaseOperationError
            logger.error(f"刪除連結 {link} 時發生資料庫操作錯誤: {e}", exc_info=True)
            raise

    def count_unscraped_links(self, source: Optional[str] = None) -> int:
        """計算未爬取的連結數量 (is_scraped=False)"""
        def query_func():
            query = self.session.query(func.count(self.model_class.id)).filter(self.model_class.is_scraped == False)
            if source:
                # 確保 source 欄位存在
                if hasattr(self.model_class, 'source'):
                    query = query.filter_by(source=source)
                else:
                    logger.warning(f"嘗試按 source 過濾，但模型 {self.model_class.__name__} 沒有 'source' 欄位。")
            result = query.scalar()
            return result if result is not None else 0 # 確保返回 int
            
        return self.execute_query(
            query_func,
            err_msg="計算未爬取的連結數量時發生錯誤"
        )

    def count_scraped_links(self, source: Optional[str] = None) -> int:
        """計算已爬取的連結數量 (is_scraped=True)"""
        # 直接調用 count_scraped_articles，因為它們邏輯相同
        return self.count_scraped_articles(source)
    
    def find_scraped_links(self, limit: Optional[int] = 100, 
                           source: Optional[str] = None,
                           is_preview: bool = False,
                           preview_fields: Optional[List[str]] = None
                           ) -> Union[List[Articles], List[Dict[str, Any]]]:
        """查詢已爬取的連結 (is_scraped=True)，支援預覽"""
        # 使用基類的 find_by_filter
        filter_criteria: Dict[str, Any] = {"is_scraped": True}
        if source:
            if hasattr(self.model_class, 'source'):
                filter_criteria["source"] = source
            else:
                logger.warning(f"嘗試按 source 過濾，但模型 {self.model_class.__name__} 沒有 'source' 欄位。")

        # 決定排序欄位
        sort_column = 'updated_at' if hasattr(self.model_class, 'updated_at') else 'id'
        
        return self.find_by_filter(
            filter_criteria=filter_criteria,
            limit=limit,
            sort_by=sort_column,
            sort_desc=True, # 假設按最新更新排序
            is_preview=is_preview,
            preview_fields=preview_fields
        )
        
    def find_unscraped_links(self, limit: Optional[int] = 100, 
                             source: Optional[str] = None, 
                             order_by_status: bool = True,
                             is_preview: bool = False,
                             preview_fields: Optional[List[str]] = None
                             ) -> Union[List[Articles], List[Dict[str, Any]]]:
        """查詢未爬取的連結 (is_scraped=False)，可選按爬取狀態排序，支援預覽"""
        def query_func():
            # --- Preview Logic ---
            query_entities = [self.model_class]
            valid_preview_fields = []
            local_is_preview = is_preview
            if local_is_preview and preview_fields:
                valid_preview_fields = [f for f in preview_fields if hasattr(self.model_class, f)]
                if valid_preview_fields:
                    query_entities = [getattr(self.model_class, f) for f in valid_preview_fields]
                else:
                    logger.warning(f"find_unscraped_links 預覽欄位無效: {preview_fields}，返回完整物件。")
                    local_is_preview = False
            # --- End Preview Logic ---
            
            query = self.session.query(*query_entities).filter(self.model_class.is_scraped == False)
            if source:
                 if hasattr(self.model_class, 'source'):
                     query = query.filter_by(source=source)
                 else:
                     logger.warning(f"嘗試按 source 過濾，但模型 {self.model_class.__name__} 沒有 'source' 欄位。")
            
            # 添加排序
            if order_by_status and hasattr(self.model_class, 'scrape_status') and hasattr(self.model_class, 'updated_at'):
                query = query.order_by(
                    case(
                        (self.model_class.scrape_status == ArticleScrapeStatus.PENDING, 0),
                        (self.model_class.scrape_status == ArticleScrapeStatus.LINK_SAVED, 1),
                        (self.model_class.scrape_status == ArticleScrapeStatus.FAILED, 2), 
                        else_=3 
                    ).asc(),
                    self.model_class.updated_at.asc() 
                )
            elif hasattr(self.model_class, 'updated_at'):
                 query = query.order_by(self.model_class.updated_at.asc())
                 
            # Apply limit
            if limit is not None and limit > 0:
                query = query.limit(limit)
            elif limit is not None and limit <= 0:
                logger.warning(f"查詢未爬取連結時提供了無效的 limit={limit}，將忽略限制。")

            raw_results = query.all()

            # --- Result Transformation ---
            if local_is_preview and valid_preview_fields:
                return [dict(zip(valid_preview_fields, row)) for row in raw_results]
            else:
                return raw_results
            # --- End Result Transformation ---

        return self.execute_query(
            query_func,
            err_msg="查詢未爬取的連結時發生錯誤"
        )

    def count_scraped_articles(self, source: Optional[str] = None) -> int:
        """計算已爬取的文章數量 (is_scraped=True)"""
        def query_func():
            query = self.session.query(func.count(self.model_class.id)).filter(self.model_class.is_scraped == True)
            if source:
                 if hasattr(self.model_class, 'source'):
                     query = query.filter_by(source=source)
                 else:
                     logger.warning(f"嘗試按 source 過濾，但模型 {self.model_class.__name__} 沒有 'source' 欄位。")
            result = query.scalar()
            return result if result is not None else 0 # 確保返回 int
            
        return self.execute_query(
            query_func,
            err_msg="計算已爬取的文章數量時發生錯誤"
        )
        
    def find_articles_by_task_id(self, task_id: Optional[int], 
                                 is_scraped: Optional[bool] = None, 
                                 limit: Optional[int] = None,
                                 is_preview: bool = False,
                                 preview_fields: Optional[List[str]] = None
                                 ) -> Union[List[Articles], List[Dict[str, Any]]]:
        """根據任務ID查詢相關的文章，支援預覽"""
        if task_id is not None and (not isinstance(task_id, int) or task_id <= 0):
             raise ValueError("task_id 必須是正整數或 None")
            
        def query_func():
            # --- Preview Logic ---
            query_entities = [self.model_class]
            valid_preview_fields = []
            local_is_preview = is_preview
            if local_is_preview and preview_fields:
                valid_preview_fields = [f for f in preview_fields if hasattr(self.model_class, f)]
                if valid_preview_fields:
                    query_entities = [getattr(self.model_class, f) for f in valid_preview_fields]
                else:
                    logger.warning(f"find_articles_by_task_id 預覽欄位無效: {preview_fields}，返回完整物件。")
                    local_is_preview = False
            # --- End Preview Logic ---

            if not hasattr(self.model_class, 'task_id'):
                 raise AttributeError(f"模型 {self.model_class.__name__} 沒有 'task_id' 欄位")
                 
            query = self.session.query(*query_entities).filter(self.model_class.task_id == task_id)
            
            if is_scraped is not None:
                 is_scraped_bool = bool(is_scraped)
                 if not hasattr(self.model_class, 'is_scraped'):
                     logger.warning(f"嘗試按 is_scraped 過濾，但模型 {self.model_class.__name__} 沒有 'is_scraped' 欄位。")
                 else:
                     query = query.filter(self.model_class.is_scraped == is_scraped_bool)
                
            # 排序邏輯不變
            if hasattr(self.model_class, 'scrape_status') and hasattr(self.model_class, 'updated_at'):
                query = query.order_by(
                    case(
                        (self.model_class.scrape_status == ArticleScrapeStatus.PENDING, 0),
                        (self.model_class.scrape_status == ArticleScrapeStatus.LINK_SAVED, 1),
                        (self.model_class.scrape_status == ArticleScrapeStatus.FAILED, 2),
                        (self.model_class.scrape_status == ArticleScrapeStatus.CONTENT_SCRAPED, 3),
                        else_=4
                    ).asc(),
                    self.model_class.updated_at.desc() 
                )
            elif hasattr(self.model_class, 'updated_at'):
                 query = query.order_by(self.model_class.updated_at.desc()) 
            
            # Apply limit
            if limit is not None:
                 if isinstance(limit, int) and limit > 0:
                     query = query.limit(limit)
                 else:
                      logger.warning(f"find_articles_by_task_id 提供了無效的 limit={limit}，將忽略限制。")

            raw_results = query.all()

            # --- Result Transformation ---
            if local_is_preview and valid_preview_fields:
                return [dict(zip(valid_preview_fields, row)) for row in raw_results]
            else:
                return raw_results
            # --- End Result Transformation ---

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
        if not isinstance(task_id, int) or task_id <= 0:
             raise ValueError("task_id 必須是正整數")
             
        def query_func():
            # 確保 task_id 欄位存在
            if not hasattr(self.model_class, 'task_id'):
                 raise AttributeError(f"模型 {self.model_class.__name__} 沒有 'task_id' 欄位")
                 
            query = self.session.query(func.count(self.model_class.id)).filter(self.model_class.task_id == task_id)
            
            # 如果指定了是否已爬取內容
            if is_scraped is not None:
                 # 確保 is_scraped 是布爾值
                 is_scraped_bool = bool(is_scraped)
                 if not hasattr(self.model_class, 'is_scraped'):
                     logger.warning(f"嘗試按 is_scraped 過濾，但模型 {self.model_class.__name__} 沒有 'is_scraped' 欄位。")
                 else:
                     query = query.filter(self.model_class.is_scraped == is_scraped_bool)
                
            result = query.scalar()
            return result if result is not None else 0 # 確保返回 int
            
        return self.execute_query(
            query_func,
            err_msg=f"計算任務ID={task_id}的文章數量時發生錯誤"
        )

    def _apply_filters(self, query, filter_criteria: Dict[str, Any]):
        """
        覆寫基類的過濾方法，以處理 ArticlesRepository 特有的過濾條件。
        """
        # 創建副本以安全地修改
        remaining_criteria = filter_criteria.copy()
        processed_query = query 

        # 1. 處理 ArticlesRepository 特有的過濾鍵
        search_text = remaining_criteria.pop("search_text", None)
        tags_like = remaining_criteria.pop("tags", None) # 假設 'tags' 意指 LIKE 搜索
        # is_ai_related 和 published_at Range 也可以在這裡處理，
        # 或者如果基類 _apply_filters 已能處理 bool 和 $gte/$lte，則讓基類處理
        
        if search_text and isinstance(search_text, str):
            search_term = f"%{search_text}%"
            processed_query = processed_query.filter(or_(
                self.model_class.title.like(search_term),
                # 假設 content 和 summary 欄位存在於 Articles 模型
                self.model_class.content.like(search_term), 
                self.model_class.summary.like(search_term) 
            ))
            
        if tags_like and isinstance(tags_like, str):
            processed_query = processed_query.filter(self.model_class.tags.like(f'%{tags_like}%'))
            
        # ... 可以繼續處理其他 Articles 特有的鍵 ...

        # 2. 調用基類的 _apply_filters 處理剩餘的標準條件
        #    將已經部分過濾的查詢物件和剩餘的條件傳遞過去
        return super()._apply_filters(processed_query, remaining_criteria)