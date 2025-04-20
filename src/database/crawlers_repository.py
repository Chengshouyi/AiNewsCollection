from .base_repository import BaseRepository, SchemaType
from src.models.crawlers_model import Crawlers
from typing import List, Optional, Dict, Any, Type, Literal, overload, TypeVar, Union
from datetime import datetime, timezone
from sqlalchemy import func
from pydantic import BaseModel
from src.models.crawlers_schema import CrawlersCreateSchema, CrawlersUpdateSchema
from src.error.errors import ValidationError, DatabaseOperationError
import logging
from sqlalchemy.orm.attributes import instance_state
from sqlalchemy.orm import Query

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CrawlersRepository(BaseRepository['Crawlers']):
    """Crawlers 特定的Repository"""

    @classmethod
    @overload
    def get_schema_class(cls, schema_type: Literal[SchemaType.CREATE]) -> Type[CrawlersCreateSchema]: ...


    @classmethod
    @overload
    def get_schema_class(cls, schema_type: Literal[SchemaType.UPDATE]) -> Type[CrawlersUpdateSchema]: ...
    

    @classmethod
    def get_schema_class(cls, schema_type: SchemaType = SchemaType.CREATE) -> Type[BaseModel]:
        """根據操作類型返回對應的schema類"""
        if schema_type == SchemaType.CREATE:
            return CrawlersCreateSchema
        elif schema_type == SchemaType.UPDATE:
            return CrawlersUpdateSchema
        raise ValueError(f"未支援的 schema 類型: {schema_type}")
        
    
    def create(self, entity_data: Dict[str, Any]) -> Optional[Crawlers]:
        """創建爬蟲設定，包含名稱唯一性檢查。"""
        try:
            # 1. 特定前置檢查：名稱唯一性
            crawler_name = entity_data.get('crawler_name')
            if crawler_name:
                existing_check = self.find_by_crawler_name_exact(crawler_name)
                if isinstance(existing_check, self.model_class):
                    raise ValidationError(f"爬蟲名稱 '{crawler_name}' 已存在")
                elif isinstance(existing_check, dict):
                    logger.warning(f"創建檢查時 find_by_crawler_name_exact 返回了字典，可能配置錯誤。")
                    raise ValidationError(f"爬蟲名稱 '{crawler_name}' 已存在")

            # 2. 設定特定預設值 (如果 Schema 沒處理)
            if 'is_active' not in entity_data:
                entity_data['is_active'] = True
            if 'created_at' not in entity_data: # BaseSchema 會處理，但這裡保留以防萬一
                entity_data['created_at'] = datetime.now(timezone.utc)

            # 3. 執行 Pydantic 驗證
            validated_data = self.validate_data(entity_data, SchemaType.CREATE)

            # 4. 將已驗證的資料傳給內部方法
            if validated_data is None:
                error_msg = f"創建 Crawler 時 validate_data 返回 None，原始資料: {entity_data}"
                logger.error(error_msg)
                raise ValidationError(error_msg)
            else:
                return self._create_internal(validated_data)
        except ValidationError as e:
             logger.error(f"創建 Crawler 驗證失敗: {e}")
             raise
        except DatabaseOperationError:
             raise
        except Exception as e:
             logger.error(f"創建 Crawler 時發生未預期錯誤: {e}", exc_info=True)
             raise DatabaseOperationError(f"創建 Crawler 時發生未預期錯誤: {e}") from e
    
    def update(self, entity_id: Any, entity_data: Dict[str, Any]) -> Optional[Crawlers]:
        """更新爬蟲設定，包含名稱唯一性檢查（如果名稱變更）。"""
        try:
            # 1. 獲取現有實體以供比較 (或者讓 _update_internal 處理)
            existing_entity = self.get_by_id(entity_id)
            if not existing_entity:
                 logger.warning(f"找不到 ID={entity_id} 的爬蟲設定，無法更新。")
                 # 可以直接返回 None，或讓 validate_data/ _update_internal 處理
                 return None


            # 2. 特定前置檢查：如果 crawler_name 被更新，檢查唯一性
            new_crawler_name = entity_data.get('crawler_name')
            if new_crawler_name and new_crawler_name != existing_entity.crawler_name:
                existing_check = self.find_by_crawler_name_exact(new_crawler_name)
                if isinstance(existing_check, self.model_class):
                    raise ValidationError(f"爬蟲名稱 '{new_crawler_name}' 已存在")
                elif isinstance(existing_check, dict):
                    logger.warning(f"更新檢查時 find_by_crawler_name_exact 返回了字典，可能配置錯誤。")
                    raise ValidationError(f"爬蟲名稱 '{new_crawler_name}' 已存在")

            # 3. updated_at 由 Schema 處理
            if 'updated_at' not in entity_data: # BaseUpdateSchema 會處理
                 entity_data['updated_at'] = datetime.now(timezone.utc)

            # 4. 執行 Pydantic 驗證 (獲取 update payload)
            update_payload = self.validate_data(entity_data, SchemaType.UPDATE)

            # 5. 將已驗證的 payload 傳給內部方法
            if update_payload is None:
                error_msg = f"更新 Crawler (ID={entity_id}) 時 validate_data 返回 None，原始資料: {entity_data}"
                logger.error(error_msg)
                raise ValidationError(error_msg)
            else:
                return self._update_internal(entity_id, update_payload)
        except ValidationError as e:
             logger.error(f"更新 Crawler (ID={entity_id}) 驗證失敗: {e}")
             raise
        except DatabaseOperationError:
             raise
        except Exception as e:
             logger.error(f"更新 Crawler (ID={entity_id}) 時發生未預期錯誤: {e}", exc_info=True)
             raise DatabaseOperationError(f"更新 Crawler (ID={entity_id}) 時發生未預期錯誤: {e}") from e
    
    def find_active_crawlers(self, 
                             limit: Optional[int] = None, 
                             offset: Optional[int] = None,
                             is_preview: bool = False, 
                             preview_fields: Optional[List[str]] = None
                             ) -> Union[List[Crawlers], List[Dict[str, Any]]]:
        """查詢活動中的爬蟲，支援分頁和預覽"""
        return self.find_by_filter(
            filter_criteria={"is_active": True},
            limit=limit,
            offset=offset,
            sort_by='created_at', # 或其他預設排序欄位
            sort_desc=True,
            is_preview=is_preview,
            preview_fields=preview_fields
        )
    
    def find_by_crawler_id(self, crawler_id: int, 
                           is_active: bool = True,
                           is_preview: bool = False,
                           preview_fields: Optional[List[str]] = None
                           ) -> Optional[Union[Crawlers, Dict[str, Any]]]:
        """根據爬蟲ID查詢，支援預覽"""
        # 使用 find_by_filter 並限制結果為 1
        results = self.find_by_filter(
            filter_criteria={"id": crawler_id, "is_active": is_active},
            limit=1,
            is_preview=is_preview,
            preview_fields=preview_fields
        )
        # find_by_filter 返回列表，取第一個元素（如果存在）
        return results[0] if results else None
    
    def find_by_crawler_name(self, crawler_name: str, 
                             is_active: Optional[bool] = None,
                             limit: Optional[int] = None,
                             offset: Optional[int] = None,
                             is_preview: bool = False,
                             preview_fields: Optional[List[str]] = None
                             ) -> Union[List[Crawlers], List[Dict[str, Any]]]:
        """根據爬蟲名稱模糊查詢，支援活躍狀態過濾、分頁和預覽
        
        Args:
            crawler_name: 爬蟲名稱 (模糊匹配)
            is_active: 是否過濾活躍狀態 (None:不過濾, True:活躍, False:非活躍)
            limit: 限制數量
            offset: 偏移量
            is_preview: 是否預覽模式
            preview_fields: 預覽欄位
            
        Returns:
            符合條件的爬蟲列表 (模型實例或字典)
        """
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
                    logger.warning(f"find_by_crawler_name 預覽欄位無效: {preview_fields}，返回完整物件。")
                    local_is_preview = False
            # --- End Preview Logic ---
            
            query = self.session.query(*query_entities).filter(
                self.model_class.crawler_name.like(f"%{crawler_name}%")
            )

            # 如果 is_active 不是 None，則添加 is_active 過濾條件
            if is_active is not None:
                query = query.filter(self.model_class.is_active == is_active)
            
            # 添加預設排序 (例如按創建時間)
            if hasattr(self.model_class, 'created_at'):
                 query = query.order_by(self.model_class.created_at.desc())
                 
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
            err_msg=f"模糊查詢爬蟲名稱 '{crawler_name}' 時發生錯誤"
        )

    def toggle_active_status(self, crawler_id: int) -> bool:
        """切換爬蟲活躍狀態"""
        def toggle_status():
            crawler = self.get_by_id(crawler_id)
            if not crawler:
                return False

            update_data = {
                'is_active': not crawler.is_active,
                'updated_at': datetime.now(timezone.utc)
            }
            updated_crawler = self.update(crawler_id, update_data)
            return updated_crawler is not None
            
        return self.execute_query(
            toggle_status,
            err_msg=f"切換爬蟲ID={crawler_id}活躍狀態時發生錯誤"
        )


    def find_by_type(self, crawler_type: str, 
                     is_active: Optional[bool] = None,
                     limit: Optional[int] = None,
                     offset: Optional[int] = None,
                     is_preview: bool = False,
                     preview_fields: Optional[List[str]] = None
                     ) -> Union[List[Crawlers], List[Dict[str, Any]]]:
        """根據爬蟲類型查找爬蟲，支援活躍狀態過濾、分頁和預覽"""
        # 建立基礎過濾條件
        filter_criteria: Dict[str, Any] = {"crawler_type": crawler_type}
        
        # 只有當 is_active 不是 None 時，才添加 is_active 過濾條件
        if is_active is not None:
            filter_criteria["is_active"] = is_active
            
        return self.find_by_filter(
            filter_criteria=filter_criteria, # 使用動態建立的 filter_criteria
            limit=limit,
            offset=offset,
            sort_by='created_at', # 或其他預設排序欄位
            sort_desc=True,
            is_preview=is_preview,
            preview_fields=preview_fields
        )
    
    def find_by_target(self, target_pattern: str, 
                       is_active: Optional[bool] = None,
                       limit: Optional[int] = None,
                       offset: Optional[int] = None,
                       is_preview: bool = False,
                       preview_fields: Optional[List[str]] = None
                       ) -> Union[List[Crawlers], List[Dict[str, Any]]]:
        """根據爬取目標模糊查詢爬蟲，支援活躍狀態過濾、分頁和預覽"""
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
                    logger.warning(f"find_by_target 預覽欄位無效: {preview_fields}，返回完整物件。")
                    local_is_preview = False
            # --- End Preview Logic ---
            
            # 先只過濾 target_pattern
            query = self.session.query(*query_entities).filter(
                 # 假設目標是 base_url
                self.model_class.base_url.like(f"%{target_pattern}%")
            )
            
            # 只有當 is_active 不是 None 時，才添加 is_active 過濾條件
            if is_active is not None:
                 query = query.filter(self.model_class.is_active == is_active)
            
            # 添加預設排序
            if hasattr(self.model_class, 'created_at'):
                 query = query.order_by(self.model_class.created_at.desc())

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
            err_msg=f"模糊查詢爬蟲目標 '{target_pattern}' 時發生錯誤"
        )
    
    def get_crawler_statistics(self) -> Dict[str, Any]:
        """獲取爬蟲統計信息"""
        def get_statistics():
            total = self.session.query(func.count(self.model_class.id)).scalar()
            active = self.session.query(func.count(self.model_class.id))\
                .filter(self.model_class.is_active == True).scalar()
            
            type_counts = self.session.query(
                self.model_class.crawler_type,
                func.count(self.model_class.id)
            ).group_by(self.model_class.crawler_type).all()
            
            return {
                "total": total,
                "active": active,
                "inactive": total - active,
                "by_type": {crawler_type: count for crawler_type, count in type_counts}
            }
            
        return self.execute_query(
            get_statistics,
            err_msg="獲取爬蟲統計信息時發生錯誤"
        )

    def find_by_crawler_name_exact(self, crawler_name: str,
                                   is_preview: bool = False,
                                   preview_fields: Optional[List[str]] = None
                                   ) -> Optional[Union[Crawlers, Dict[str, Any]]]:
        """根據爬蟲名稱精確查詢，支援預覽"""
        results = self.find_by_filter(
            filter_criteria={"crawler_name": crawler_name},
            limit=1,
            is_preview=is_preview,
            preview_fields=preview_fields
        )
        return results[0] if results else None
    

    def create_or_update(self, entity_data: Dict[str, Any]) -> Optional[Crawlers]:
        """創建或更新爬蟲設定
        
        如果有提供 ID 則更新現有爬蟲，否則創建新爬蟲
        
        Args:
            entity_data: 爬蟲設定數據
            
        Returns:
            創建或更新的爬蟲設定
        """
        if 'id' in entity_data and entity_data['id']:
            crawler_id = entity_data.pop('id')
            updated_crawler = self.update(crawler_id, entity_data)
            if updated_crawler:
                return updated_crawler
                
        # ID不存在或更新失敗，創建新爬蟲
        return self.create(entity_data)
            
    def batch_toggle_active(self, crawler_ids: List[int], active_status: bool) -> Dict[str, Any]:
        """批量設置爬蟲的活躍狀態
        
        Args:
            crawler_ids: 爬蟲ID列表
            active_status: 要設置的活躍狀態
            
        Returns:
            包含成功和失敗信息的字典
        """
        def batch_update():
            success_count = 0
            failed_ids = []
            
            for crawler_id in crawler_ids:
                try:
                    update_data = {
                        'is_active': active_status,
                        'updated_at': datetime.now(timezone.utc)
                    }
                    
                    updated = self.update(crawler_id, update_data)
                    if updated:
                        success_count += 1
                    else:
                        failed_ids.append(crawler_id)
                except Exception as e:
                    self.session.rollback()
                    failed_ids.append(crawler_id)
            
            return {
                "success_count": success_count,
                "fail_count": len(failed_ids),
                "failed_ids": failed_ids
            }
            
        return self.execute_query(
            batch_update,
            err_msg=f"批量{'啟用' if active_status else '停用'}爬蟲時發生錯誤"
        )