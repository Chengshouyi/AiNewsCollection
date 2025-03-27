from .base_repository import BaseRepository, SchemaType
from src.models.crawlers_model import Crawlers
from typing import List, Optional, Dict, Any, Type
from datetime import datetime, timezone
from sqlalchemy import func, desc, asc
from pydantic import BaseModel
from src.models.crawlers_schema import CrawlersCreateSchema, CrawlersUpdateSchema
from src.error.errors import ValidationError

class CrawlersRepository(BaseRepository['Crawlers']):
    """Crawlers 特定的Repository"""
    
    def get_schema_class(self, schema_type: SchemaType = SchemaType.CREATE) -> Type[BaseModel]:
        """根據操作類型返回對應的schema類"""
        if schema_type == SchemaType.CREATE:
            return CrawlersCreateSchema
        elif schema_type == SchemaType.UPDATE:
            return CrawlersUpdateSchema
        raise ValueError(f"未支援的 schema 類型: {schema_type}")
        
    def _validate_required_fields(self, entity_data: Dict[str, Any], existing_entity: Optional[Crawlers] = None) -> Dict[str, Any]:
        """
        驗證並補充必填欄位
        
        Args:
            entity_data: 爬蟲設定數據
            existing_entity: 現有爬蟲實體 (用於更新時)
            
        Returns:
            處理後的爬蟲設定數據
        """
        # 深度複製避免修改原始資料
        processed_data = entity_data.copy()
        
        # 檢查必填欄位
        required_fields = ['crawler_name', 'base_url']
        
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
    
    def create(self, entity_data: Dict[str, Any]) -> Optional[Crawlers]:
        """創建爬蟲設定
        
        Args:
            entity_data: 爬蟲設定數據
            
        Returns:
            創建的爬蟲設定或 None
        """
        # 設置默認值
        if 'created_at' not in entity_data:
            entity_data['created_at'] = datetime.now(timezone.utc)
        if 'is_active' not in entity_data:
            entity_data['is_active'] = True
            
        # 驗證爬蟲名稱是否重複
        if 'crawler_name' in entity_data and entity_data['crawler_name']:
            existing = self.find_by_crawler_name_exact(entity_data['crawler_name'])
            if existing:
                raise ValidationError(f"爬蟲名稱 '{entity_data['crawler_name']}' 已存在")
        
        # 驗證並補充必填欄位
        validated_data = self._validate_required_fields(entity_data)
        
        # 獲取並使用適當的schema進行驗證和創建
        schema_class = self.get_schema_class(SchemaType.CREATE)
        return self._create_internal(validated_data, schema_class)
    
    def update(self, entity_id: Any, entity_data: Dict[str, Any]) -> Optional[Crawlers]:
        """更新爬蟲設定
        
        Args:
            entity_id: 爬蟲ID
            entity_data: 要更新的數據
            
        Returns:
            更新後的爬蟲設定或 None
        """
        # 檢查爬蟲是否存在
        existing_entity = self.get_by_id(entity_id)
        if not existing_entity:
            return None
        
        # 如果更新資料為空，直接返回已存在的實體
        if not entity_data:
            return existing_entity
        
        # 驗證不可更新的欄位
        immutable_fields = ['created_at', 'id', 'crawler_type']
        for field in immutable_fields:
            if field in entity_data:
                raise ValidationError(f"不允許更新欄位: {field}")
            
        # 檢查爬蟲名稱是否重複
        if 'crawler_name' in entity_data and entity_data['crawler_name'] != existing_entity.crawler_name:
            existing = self.find_by_crawler_name_exact(entity_data['crawler_name'])
            if existing:
                raise ValidationError(f"爬蟲名稱 '{entity_data['crawler_name']}' 已存在")
        
        # 設置更新時間
        if 'updated_at' not in entity_data:
            entity_data['updated_at'] = datetime.now(timezone.utc)
        
        # 驗證並補充必填欄位
        validated_data = self._validate_required_fields(entity_data, existing_entity)
        
        # 獲取並使用適當的schema進行驗證和更新
        schema_class = self.get_schema_class(SchemaType.UPDATE)
        return self._update_internal(entity_id, validated_data, schema_class)
    
    def find_active_crawlers(self) -> List['Crawlers']:
        """查詢活動中的爬蟲"""
        return self.execute_query(
            lambda: self.session.query(self.model_class)
                .filter_by(is_active=True)
                .all()
        )
    
    def find_by_crawler_name(self, crawler_name: str) -> List['Crawlers']:
        """根據爬蟲名稱模糊查詢，回傳匹配的列表"""
        return self.execute_query(
            lambda: self.session.query(self.model_class)
                .filter(self.model_class.crawler_name.like(f"%{crawler_name}%"))
                .all()
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


    def find_by_type(self, crawler_type: str) -> List[Crawlers]:
        """根據爬蟲類型查找爬蟲"""
        return self.execute_query(
            lambda: self.session.query(self.model_class)
                .filter(self.model_class.crawler_type == crawler_type)
                .all(),
            err_msg=f"查詢類型為{crawler_type}的爬蟲時發生錯誤"
        )
    
    def find_by_target(self, target_pattern: str) -> List[Crawlers]:
        """根據爬取目標模糊查詢爬蟲"""
        return self.execute_query(
            lambda: self.session.query(self.model_class)
                .filter(self.model_class.base_url.like(f"%{target_pattern}%"))
                .all(),
            err_msg=f"查詢目標包含{target_pattern}的爬蟲時發生錯誤"
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

    def find_by_crawler_name_exact(self, crawler_name: str) -> Optional[Crawlers]:
        """根據爬蟲名稱精確查詢，回傳匹配的爬蟲或None"""
        return self.execute_query(
            lambda: self.session.query(self.model_class)
                .filter(self.model_class.crawler_name == crawler_name)
                .first(),
            err_msg=f"精確查詢爬蟲名稱 '{crawler_name}' 時發生錯誤"
        )
    
    def create_or_update(self, entity_data: Dict[str, Any]) -> Crawlers:
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