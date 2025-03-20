from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from contextlib import contextmanager
import logging
from .models import Base
from .database_manager import DatabaseManager
from .models import ValidationError as CustomValidationError

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

T = TypeVar('T', bound=Base)
    

class Repository(Generic[T]):
    """通用Repository模式實現，用於基本CRUD操作"""
    
    def __init__(self, session: Session, model_class: Type[T]):
        self.session = session
        self.model_class = model_class

    def get_by_id(self, id: int) -> Optional[T]:
        """根據 ID 獲取實體"""
        if not isinstance(id, int) or id <= 0:
            error_msg = f"無效的ID: {id}"
            logger.error(error_msg)
            raise CustomValidationError(error_msg)
        return self.session.query(self.model_class).get({"id":id})
    
    def get_all(
        self, 
        limit: Optional[int] = None, 
        offset: Optional[int] = None, 
        sort_by: Optional[str] = None, 
        sort_desc: bool = False
    ) -> List[T]:
        """根據條件查詢實體"""
        query = self.session.query(self.model_class)
    
        if sort_by:
            sort_column = getattr(self.model_class, sort_by)
            query = query.order_by(sort_column.desc() if sort_desc else sort_column)
    
        if offset is not None:
            query = query.offset(offset)
    
        if limit is not None:
            query = query.limit(limit)
    
        return query.all()
    
    def get_paginated(self, page: int, per_page: int, sort_by: Optional[str] = None, sort_desc: bool = False) -> Dict[str, Any]:
        """
        分頁獲取實體
        
        Args:
            page: 頁碼
            per_page: 每頁數量
            sort_by: 排序欄位，默認None
            sort_desc: 是否降序排序，默認False
        Returns:
            items: 分頁後的實體列表
            total: 總實體數量
            page: 當前頁碼
            per_page: 每頁實體數量
            total_pages: 總頁數
        """
        # 計算總文章數量
        items = self.get_all()
        if not items:
            return {
                "items": [],
                "total": 0,
                "page": page,
                "per_page": per_page,
                "total_pages": 0
            }
        total_items = len(items)
        
        # 計算總頁數
        total_pages = (total_items + per_page - 1) // per_page 
        
        # 計算起始偏移
        offset = (page - 1) * per_page
        
        # 獲取分頁後的文章
        items = self.get_all(limit=per_page, offset=offset, sort_by=sort_by, sort_desc=sort_desc)

        return {
            "items": items,
            "total": total_items,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages
        }


    def find_by(self, **kwargs) -> List[T]:
        """根據條件查詢實體"""
        return self.session.query(self.model_class).filter_by(**kwargs).all()
    
    def find_one_by(self, **kwargs) -> Optional[T]:
        """根據條件查詢單個實體"""
        return self.session.query(self.model_class).filter_by(**kwargs).first()
    
    
    def create(self, **kwargs) -> T:
        """創建新實體，處理唯一性約束"""
        try:
            entity = self.model_class(**kwargs)
            self.session.add(entity)
            self.session.flush()  # 立即獲取 ID
            return entity  
        except IntegrityError as e:
            self.session.rollback()
            if "uq_article_link" in str(e):
                link_value = kwargs.get('link', '未知連結')
                raise CustomValidationError(f"已存在具有相同連結的文章: {link_value}")
            logger.error(f"資料庫唯一性約束違反: {str(e)}")
            raise CustomValidationError(f"資料唯一性衝突: {str(e)}")
        except Exception as e:
            self.session.rollback()
            error_msg = f"創建實體失敗: {str(e)}"
            logger.error(error_msg)
            raise e
    
    def update(self, entity: T, **kwargs) -> T:
        """更新實體"""
        try:      
            # 更新屬性
            for key, value in kwargs.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            self.session.flush()
            return entity
        except Exception as e:
            self.session.rollback()
            error_msg = f"更新實體失敗: {str(e)}"
            logger.error(error_msg)
            raise e

    def delete(self, entity: T) -> bool:
        """刪除實體
        Args:
            entity: 要刪除的實體
        Returns:
            bool: 刪除成功與否
        """
        try:
            self.session.delete(entity)
            self.session.flush()
            return True
        except Exception as e:
            self.session.rollback()
            error_msg = f"刪除實體失敗: {str(e)}"
            logger.error(error_msg)
            return False

    def batch_create(self, items_data: List[Dict[str, Any]]) -> List[T]:
        """批量創建實體"""
        try:
            # 預先建立所有實體物件
            entities = []
            for item_data in items_data:
                # 創建實體並加入列表
                entity = self.model_class(**item_data)
                entities.append(entity)
            
            # 批量添加所有實體
            if entities:
                self.session.add_all(entities)
                self.session.flush()
                
            return entities
        except Exception as e:
            self.session.rollback()
            error_msg = f"批量創建失敗: {str(e)}"
            logger.error(error_msg)
            raise e
    
    def batch_update(self, entities: List[T], **kwargs) -> List[T]:
        """批量更新實體"""
        try:
            for entity in entities:
                for key, value in kwargs.items():
                    if hasattr(entity, key):    
                        setattr(entity, key, value)
            self.session.flush()
            return entities
        except Exception as e:
            self.session.rollback()
            error_msg = f"批量更新失敗: {str(e)}"
            logger.error(error_msg)
            raise e

    def batch_delete(self, entities: List[T]) -> bool:
        """批量刪除實體"""
        try:
            for entity in entities:
                self.session.delete(entity)
            self.session.flush()
            return True
        except Exception as e:
            self.session.rollback()
            error_msg = f"批量刪除失敗: {str(e)}"
            logger.error(error_msg)
            return False

    def find_by_filter(self, **kwargs) -> List[T]:
        """根據過濾條件查詢實體"""
        query = self.session.query(self.model_class)
        for key, value in kwargs.items():
            if hasattr(self.model_class, key):
                query = query.filter(getattr(self.model_class, key) == value)
        return query.all()
    
    def find_one_by_filter(self, **kwargs) -> Optional[T]:
        """根據過濾條件查詢單個實體"""
        query = self.session.query(self.model_class)
        for key, value in kwargs.items():
            if hasattr(self.model_class, key):
                query = query.filter(getattr(self.model_class, key) == value)
        return query.first()
    
    def exists(self, **kwargs) -> bool:
        """檢查是否存在符合條件的實體"""
        query = self.session.query(self.model_class)
        for key, value in kwargs.items():
            if hasattr(self.model_class, key):
                query = query.filter(getattr(self.model_class, key) == value)
        return self.session.query(query.exists()).scalar()

# 使用上下文管理器處理 Repository 的創建和事務管理
@contextmanager
def repository_context(db_manager: DatabaseManager, model_class: Type[T]):
    """使用上下文管理器處理 Repository 的創建和事務管理"""
    with db_manager.session_scope() as session:
        repo = Repository(session, model_class)
        try:
            yield repo, session
        except Exception as e:
            error_msg = f"儲存庫操作錯誤: {e}"
            logger.error(error_msg, exc_info=True)
            session.rollback()
            raise
        