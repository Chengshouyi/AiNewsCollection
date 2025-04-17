from src.database.base_repository import BaseRepository, SchemaType
from src.models.articles_model import Articles
from src.models.articles_schema import ArticleCreateSchema, ArticleUpdateSchema
from typing import Optional, List, Dict, Any, Type, Union, overload, Literal
from sqlalchemy import func, or_, case
from sqlalchemy.orm import Query
from src.error.errors import ValidationError, DatabaseOperationError, InvalidOperationError
from sqlalchemy.exc import IntegrityError
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
                # 確保值是布爾類型
                if isinstance(value, bool):
                     query = query.filter(self.model_class.is_ai_related == value)
                else:
                     logger.warning(f"過濾 is_ai_related 時收到非布爾值: {value}, 已忽略此條件。")
            elif key == "tags":
                if isinstance(value, str):
                    query = query.filter(self.model_class.tags.like(f'%{value}%'))
                else:
                     logger.warning(f"過濾 tags 時收到非字串值: {value}, 已忽略此條件。")
            elif key == "published_at" and isinstance(value, dict):
                if "$gte" in value:
                    query = query.filter(self.model_class.published_at >= value["$gte"])
                if "$lte" in value:
                    query = query.filter(self.model_class.published_at <= value["$lte"])
            elif key == "search_text" and isinstance(value, str) and value:
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
            result = query.scalar()
            return result if result is not None else 0
        
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
        """根據標籤列表查詢文章 (OR 邏輯)"""
        if not tags or not isinstance(tags, list):
            logger.warning("find_by_tags 需要一個非空的標籤列表。")
            return [] # 或者根據需求拋出錯誤
            
        def query_builder():
            # 創建用於存放 LIKE 條件的列表
            conditions = []
            for tag in tags:
                if isinstance(tag, str) and tag.strip(): # 確保是有效字串
                    # 為每個標籤創建 LIKE 條件，注意處理 SQL 注入風險（此處簡單演示）
                    # 實際應用中可能需要更安全的參數化方法，但 SQLAlchemy 通常會處理
                    conditions.append(self.model_class.tags.like(f'%{tag.strip()}%'))
                else:
                    logger.warning(f"find_by_tags 收到無效標籤: {tag}, 已忽略。")
            
            query = self.session.query(self.model_class)
            # 如果有有效的條件，使用 or_ 連接它們
            if conditions:
                query = query.filter(or_(*conditions))
            else:
                # 如果沒有有效的標籤條件，則不返回任何結果
                # 或者根據需求調整行為，例如返回所有文章
                logger.info("find_by_tags: 沒有提供有效的標籤條件。")
                return [] 
                
            return query.all()
        
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
                # 這種情況理論上不應發生，除非基類 validate_data 內部邏輯有誤
                # 或者 get_schema_class 返回了意外的類型
                # Pydantic 驗證失敗應該拋出 ValidationError
                logger.error(f"創建 Article 時 validate_data 返回 None，原始資料: {entity_data}")
                raise DatabaseOperationError("創建文章時驗證步驟返回意外的 None 值")
            
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
                # self.session.rollback()
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
                 logger.error(f"更新 Article (ID={entity_id}) 時 validate_data 返回 None，驗證前 Payload={payload_for_validation}")
                 raise DatabaseOperationError(f"更新驗證時發生內部錯誤，ID={entity_id}")
                 
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
                self.session.flush()
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
        """根據過濾條件獲取分頁資料
        
        Args:
            filter_dict: 過濾條件字典
            page: 當前頁碼，從1開始
            per_page: 每頁數量
            sort_by: 排序欄位
            sort_desc: 是否降序排列
            
        Returns:
            包含分頁資訊和結果的字典
        
        Raises:
            InvalidOperationError: 如果分頁參數無效。
            DatabaseOperationError: 如果查詢過程中發生錯誤。
        """
        # 驗證分頁參數 (移到這裡更合適)
        if not isinstance(page, int) or page <= 0:
             # 允許 page=1 作為有效值，但 0 或負數無效
             # raise InvalidOperationError("頁碼必須是正整數")
             logger.warning(f"無效的頁碼 '{page}'，將使用預設值 1。")
             page = 1
        if not isinstance(per_page, int) or per_page <= 0:
             raise InvalidOperationError("每頁數量必須是正整數")

        def paginated_query():
            # --- 內部實現與 BaseRepository.get_paginated 類似 ---
            # --- 可以考慮重用 BaseRepository 的邏輯，如果過濾部分能整合 ---
            
            # 構建計數查詢
            count_query = self.session.query(func.count(self.model_class.id))
            count_query = self._build_filter_query(count_query, filter_dict)
            total = count_query.scalar() or 0 # 確保 count 結果是 int

            # 計算總頁數
            total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0
            
            # 調整頁碼 (如果請求的頁碼超出範圍)
            current_page = max(1, min(page, total_pages)) if total_pages > 0 else 1
            
            # 計算偏移量
            offset = (current_page - 1) * per_page
            
            # 構建獲取數據的查詢
            data_query = self.session.query(self.model_class)
            data_query = self._build_filter_query(data_query, filter_dict)
            
            # 添加排序
            if sort_by:
                 if hasattr(self.model_class, sort_by):
                     order_column = getattr(self.model_class, sort_by)
                     data_query = data_query.order_by(order_column.desc() if sort_desc else order_column.asc())
                 else:
                      logger.warning(f"請求的排序欄位 '{sort_by}' 不存在於模型 {self.model_class.__name__}，將使用預設排序。")
                      # 應用預設排序 (例如，按 published_at)
                      if hasattr(self.model_class, 'published_at'):
                           data_query = data_query.order_by(self.model_class.published_at.desc())
            else:
                # 預設排序 (例如，按 published_at)
                if hasattr(self.model_class, 'published_at'):
                     data_query = data_query.order_by(self.model_class.published_at.desc())
                elif hasattr(self.model_class, 'id'): # 備用排序
                     data_query = data_query.order_by(self.model_class.id.desc())
            
            # 應用分頁
            items = data_query.offset(offset).limit(per_page).all()
            
            return {
                "items": items,
                "page": current_page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_next": current_page < total_pages,
                "has_prev": current_page > 1
            }
        
        # 使用 execute_query 包裹以處理異常
        return self.execute_query(
            paginated_query,
            err_msg="根據過濾條件獲取分頁資料時發生錯誤",
            exception_class=DatabaseOperationError # 指定錯誤類型
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
    
    def find_scraped_links(self, limit: Optional[int] = 100, source: Optional[str] = None) -> List[Articles]:
        """查詢已爬取的連結 (is_scraped=True)"""
        # 可以使用 get_by_filter 或直接構建查詢
        def query_func():
            query = self.session.query(self.model_class).filter(self.model_class.is_scraped == True)
            if source:
                 if hasattr(self.model_class, 'source'):
                     query = query.filter_by(source=source)
                 else:
                     logger.warning(f"嘗試按 source 過濾，但模型 {self.model_class.__name__} 沒有 'source' 欄位。")

            # 添加排序，例如按更新時間
            if hasattr(self.model_class, 'updated_at'):
                 query = query.order_by(self.model_class.updated_at.desc())

            if limit is not None and limit > 0:
                query = query.limit(limit)
            elif limit is not None and limit <= 0:
                 logger.warning(f"查詢已爬取連結時提供了無效的 limit={limit}，將忽略限制。")

            return query.all()
            
        return self.execute_query(
            query_func,
            err_msg="查詢已爬取的連結時發生錯誤"
        )
    
    def find_unscraped_links(self, limit: Optional[int] = 100, source: Optional[str] = None, 
                             order_by_status: bool = True) -> List[Articles]:
        """查詢未爬取的連結 (is_scraped=False)，可選按爬取狀態排序"""
        def query_func():
            query = self.session.query(self.model_class).filter(self.model_class.is_scraped == False)
            if source:
                 if hasattr(self.model_class, 'source'):
                     query = query.filter_by(source=source)
                 else:
                     logger.warning(f"嘗試按 source 過濾，但模型 {self.model_class.__name__} 沒有 'source' 欄位。")
            
            # 添加排序
            if order_by_status and hasattr(self.model_class, 'scrape_status') and hasattr(self.model_class, 'updated_at'):
                # 優先處理 PENDING，然後是 LINK_SAVED，然後按更新時間
                query = query.order_by(
                    case(
                        (self.model_class.scrape_status == ArticleScrapeStatus.PENDING, 0),
                        (self.model_class.scrape_status == ArticleScrapeStatus.LINK_SAVED, 1),
                        (self.model_class.scrape_status == ArticleScrapeStatus.FAILED, 2), # FAILED 也算未爬取
                        else_=3 # 其他狀態（理論上不應出現）
                    ).asc(),
                    self.model_class.updated_at.asc() # 或 desc() 取決於優先級
                )
            elif hasattr(self.model_class, 'updated_at'):
                 # 默認按更新時間排序 (升序較早的先處理，或降序較新的先處理)
                 query = query.order_by(self.model_class.updated_at.asc())
                 
            if limit is not None and limit > 0:
                query = query.limit(limit)
            elif limit is not None and limit <= 0:
                logger.warning(f"查詢未爬取連結時提供了無效的 limit={limit}，將忽略限制。")

            return query.all()
            
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
        
    def find_articles_by_task_id(self, task_id: Optional[int], is_scraped: Optional[bool] = None, limit: Optional[int] = None) -> List[Articles]:
        """根據任務ID查詢相關的文章
        
        Args:
            task_id: 任務ID (可以是 None)
            is_scraped: 可選過濾條件，是否已爬取內容
            limit: 可選限制返回數量
            
        Returns:
            符合條件的文章列表 
        """
        if task_id is not None and (not isinstance(task_id, int) or task_id <= 0):
             raise ValueError("task_id 必須是正整數或 None")
            
        def query_func():
            # 確保 task_id 欄位存在
            if not hasattr(self.model_class, 'task_id'):
                 raise AttributeError(f"模型 {self.model_class.__name__} 沒有 'task_id' 欄位")
                 
            query = self.session.query(self.model_class).filter(self.model_class.task_id == task_id)
            
            # 如果指定了是否已爬取內容
            if is_scraped is not None:
                 # 確保 is_scraped 是布爾值
                 is_scraped_bool = bool(is_scraped)
                 if not hasattr(self.model_class, 'is_scraped'):
                     logger.warning(f"嘗試按 is_scraped 過濾，但模型 {self.model_class.__name__} 沒有 'is_scraped' 欄位。")
                 else:
                     query = query.filter(self.model_class.is_scraped == is_scraped_bool)
                
            # 根據抓取狀態和更新時間排序
            if hasattr(self.model_class, 'scrape_status') and hasattr(self.model_class, 'updated_at'):
                query = query.order_by(
                    case(
                        (self.model_class.scrape_status == ArticleScrapeStatus.PENDING, 0),
                        (self.model_class.scrape_status == ArticleScrapeStatus.LINK_SAVED, 1),
                        (self.model_class.scrape_status == ArticleScrapeStatus.FAILED, 2),
                        (self.model_class.scrape_status == ArticleScrapeStatus.CONTENT_SCRAPED, 3),
                        else_=4
                    ).asc(),
                    self.model_class.updated_at.desc() # 相同狀態下，最新的優先
                )
            elif hasattr(self.model_class, 'updated_at'):
                 query = query.order_by(self.model_class.updated_at.desc()) # 降序排列，返回最新更新的記錄
            
            # 如果指定了限制數量
            if limit is not None:
                 if isinstance(limit, int) and limit > 0:
                     query = query.limit(limit)
                 else:
                      logger.warning(f"find_articles_by_task_id 提供了無效的 limit={limit}，將忽略限制。")

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