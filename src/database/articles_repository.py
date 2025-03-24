from .base_repository import BaseRepository
from src.models.articles_model import Articles
from typing import Optional, List, Dict, Any
from sqlalchemy import func, or_
from src.error.errors import ValidationError
import logging

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



class ArticlesRepository(BaseRepository['Articles']):
    """Article 特定的Repository"""
    
    def find_by_link(self, link: str) -> Optional['Articles']:
        """根據文章連結查詢"""
        try:
            return self.session.query(self.model_class).filter_by(link=link).first()
        except Exception as e:
            error_msg = f"查詢文章連結時發生錯誤: {e}"
            logger.error(error_msg)
            raise e
    
    def find_by_category(self, category: str) -> List['Articles']:
        """根據分類查詢文章"""
        try:
            return self.session.query(self.model_class).filter_by(category=category).all()
        except Exception as e:
            error_msg = f"查詢文章分類時發生錯誤: {e}"
            logger.error(error_msg)
            raise e

    def search_by_title(self, keyword: str, exact_match: bool = False) -> List['Articles']:
        """根據標題搜索文章
        
        Args:
            keyword: 搜索關鍵字
            exact_match: 是否進行精確匹配（預設為模糊匹配）
        
        Returns:
            符合條件的文章列表
        """
        if exact_match:
            # 精確匹配（區分大小寫）
            try:
                return self.session.query(self.model_class).filter(
                    self.model_class.title == keyword
                ).all()
            except Exception as e:
                error_msg = f"查詢文章標題時發生錯誤: {e}"
                logger.error(error_msg)
                raise e
        else:
            # 模糊匹配
            try:
                return self.session.query(self.model_class).filter(
                    self.model_class.title.like(f'%{keyword}%')
                ).all()
            except Exception as e:
                error_msg = f"查詢文章標題時發生錯誤: {e}"
                logger.error(error_msg)
                raise e
    
    def get_by_filter(self, filter_dict: Dict[str, Any], limit: Optional[int] = None, offset: Optional[int] = None) -> List['Articles']:
        """根據過濾條件查詢文章
        
        Args:
            filter_dict: 過濾條件字典
            limit: 限制返回數量
            offset: 起始偏移
            
        Returns:
            符合條件的文章列表
        """
        try:
            query = self.session.query(self.model_class)
            
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
                else:
                    query = query.filter(getattr(self.model_class, key) == value)
                    
            if offset is not None:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)
                    
            return query.all()
        except Exception as e:
            error_msg = f"根據過濾條件查詢文章時發生錯誤: {e}"
            logger.error(error_msg)
            raise e

    def count(self, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        """計算符合條件的文章數量
        
        Args:
            filter_dict: 過濾條件字典
            
        Returns:
            文章數量
        """
        try:
            query = self.session.query(func.count(self.model_class.id))
            
            if filter_dict:
                for key, value in filter_dict.items():
                    if key == "is_ai_related":
                        query = query.filter(self.model_class.is_ai_related == value)
                    elif key == "published_at" and isinstance(value, dict):
                        if "$gte" in value:
                            query = query.filter(self.model_class.published_at >= value["$gte"])
                        if "$lte" in value:
                            query = query.filter(self.model_class.published_at <= value["$lte"])
                    else:
                        query = query.filter(getattr(self.model_class, key) == value)
                        
            return query.scalar()
        except Exception as e:
            error_msg = f"計算符合條件的文章數量時發生錯誤: {e}"
            logger.error(error_msg)
            raise e

    def search_by_keywords(self, keywords: str) -> List['Articles']:
        """根據關鍵字搜索文章（標題和內容）
        
        Args:
            keywords: 搜索關鍵字
            
        Returns:
            符合條件的文章列表
        """
        try:
            return self.session.query(self.model_class).filter(
                or_(
                    self.model_class.title.like(f'%{keywords}%'),
                    self.model_class.content.like(f'%{keywords}%')
                )
            ).all()
        except Exception as e:
            error_msg = f"根據關鍵字搜索文章時發生錯誤: {e}"
            logger.error(error_msg)
            raise e

    def get_category_distribution(self) -> Dict[str, int]:
        """獲取各分類的文章數量分布
        
        Returns:
            分類及其對應的文章數量字典
        """
        try:
            result = self.session.query(
                self.model_class.category,
                func.count(self.model_class.id)
            ).group_by(self.model_class.category).all()
            return {str(category) if category else "未分類": count for category, count in result}
        except Exception as e:
            error_msg = f"獲取各分類的文章數量分布時發生錯誤: {e}"
            logger.error(error_msg)
            raise e

    def find_by_tags(self, tags: List[str]) -> List['Articles']:
        """根據標籤列表查詢文章
        
        Args:
            tags: 標籤列表
            
        Returns:
            包含指定標籤的文章列表
        """
        try:
            query = self.session.query(self.model_class)
            for tag in tags:
                query = query.filter(self.model_class.tags.like(f'%{tag}%'))
            return query.all()
        except Exception as e:
            error_msg = f"根據標籤列表查詢文章時發生錯誤: {e}"
            logger.error(error_msg)
            raise e
    
    def validate_unique_link(self, link: str, exclude_id: Optional[int] = None, raise_error: bool = True) -> bool:
        """
        驗證文章連結是否唯一
        
        Args:
            link: 要檢查的連結
            exclude_id: 要排除的文章ID (用於更新時)
            raise_error: 是否在發現重複時引發錯誤
        
        Returns:
            True 如果連結唯一，否則根據 raise_error 參數處理
        """

        if not link:
            return True  # 空連結不需檢查唯一性
        try:
            query = self.session.query(self.model_class).filter_by(link=link)
            
            if exclude_id is not None:
                query = query.filter(self.model_class.id != exclude_id)
            
            existing = query.first()
            if existing:
                # 檢查是否為更新時的不存在ID問題
                if exclude_id is not None and not self.get_by_id(exclude_id):
                    if raise_error:
                        raise ValidationError(f"文章不存在，ID={exclude_id}")
                    return False
                
                if raise_error:
                    raise ValidationError(f"已存在具有相同連結的文章: {link}")
                return False
            
            return True
        except Exception as e:
            error_msg = f"驗證文章連結唯一性時發生錯誤: {e}"
            logger.error(error_msg)
            raise e

    def create(self, entity_data: Dict[str, Any]) -> Articles:
        """
        重寫基類的 create 方法，添加針對 Articles 的特殊驗證
        """
        try:
            # 驗證連結唯一性
            if 'link' in entity_data and entity_data['link']:
                self.validate_unique_link(entity_data['link'])
        
            # 確保所有必填欄位都有值
            required_fields = ['is_ai_related', 'title', 'link', 'source', 'published_at']
            missing_fields = [field for field in required_fields if field not in entity_data or entity_data[field] is None]
            
            if missing_fields:
                raise ValidationError(f"缺少必填欄位: {', '.join(missing_fields)}")
        
            # 呼叫基類方法
            return super().create(entity_data)
        except Exception as e:
            error_msg = f"創建文章時發生錯誤: {e}"
            logger.error(error_msg)
            raise e

    def update(self, entity_id: Any, entity_data: Dict[str, Any]) -> Optional[Articles]:
        """
        重寫基類的 update 方法，添加針對 Articles 的特殊驗證
        """
        try:
            # 先檢查實體是否存在
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
            
            # 處理可能缺少的必填欄位（從現有實體中補充）
            required_fields = ['is_ai_related', 'title', 'link', 'source', 'published_at']
            for field in required_fields:
                if field not in entity_data and hasattr(existing_entity, field):
                    entity_data[field] = getattr(existing_entity, field)
        
            # 呼叫基類方法
            return super().update(entity_id, entity_data)
        except Exception as e:
            error_msg = f"更新文章時發生錯誤: {e}"
            logger.error(error_msg)
            raise e

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
        try:
            existing_entities = {}
            for entity_id in entity_ids:
                entity = self.get_by_id(entity_id)
                if entity:
                    existing_entities[entity_id] = entity
                else:
                    missing_ids.append(entity_id)
        except Exception as e:
            error_msg = f"批量更新文章時檢查ID是否存在時發生錯誤: {e}"
            logger.error(error_msg)
            raise e
        
        # 第二步：如果要更新link欄位，預先檢查連結是否已存在且屬於非更新範圍內的實體
        try:
            if 'link' in entity_data and entity_data['link']:
                # 檢查連結是否存在於其他非更新實體中
                link = entity_data['link']
                query = self.session.query(self.model_class).filter_by(link=link)
                if entity_ids:
                    query = query.filter(~self.model_class.id.in_(entity_ids))
                existing_with_link = query.first()
                
                if existing_with_link:
                    # 發現連結衝突，但仍然繼續處理其他實體
                    logger.warning(f"無法更新連結，已存在相同連結的文章: {link}")
        except Exception as e:
            error_msg = f"批量更新文章時檢查連結是否存在時發生錯誤: {e}"
            logger.error(error_msg)
            raise e
        
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
                        duplicate_query = self.session.query(self.model_class).filter_by(link=entity_data_copy['link'])
                        duplicate_query = duplicate_query.filter(self.model_class.id != entity_id)
                        duplicate = duplicate_query.first()
                        
                        if duplicate:
                            # 如果發現重複，則從更新資料中移除連結欄位
                            logger.warning(f"實體 ID={entity_id} 的連結更新已跳過，因為連結 '{entity_data_copy['link']}' 已存在")
                            entity_data_copy.pop('link', None)
                
                # 如果沒有任何要更新的欄位，則跳過
                if not entity_data_copy:
                    continue
                    
                # 處理可能缺少的必填欄位（從現有實體中補充）
                required_fields = ['is_ai_related', 'title', 'link', 'source', 'published_at']
                for field in required_fields:
                    if field not in entity_data_copy and hasattr(entity, field):
                        entity_data_copy[field] = getattr(entity, field)
                
                # 更新實體
                result = super().update(entity_id, entity_data_copy)
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
    
