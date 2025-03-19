from typing import TypeVar, Generic, Type, Optional, List, Dict, Any, Callable
from sqlalchemy.orm import Session
from contextlib import contextmanager
import logging
from .models import Base

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

T = TypeVar('T', bound=Base)
    

class Repository(Generic[T]):
    """通用Repository模式實現，用於基本CRUD操作"""
    
    def __init__(self, session: Session, model_class: Type[T], validator: Optional[Callable] = None):
        self.session = session
        self.model_class = model_class

    def get_by_id(self, id: int) -> Optional[T]:
        """根據 ID 獲取實體"""
        return self.session.query(self.model_class).get(id)
    
    def get_all(
        self, 
        limit: Optional[int] = None, 
        offset: Optional[int] = None, 
        sort_by: Optional[str] = None, 
        sort_desc: bool = False
    ) -> List[T]:
        query = self.session.query(self.model_class)
    
        if sort_by:
            sort_column = getattr(self.model_class, sort_by)
            query = query.order_by(sort_column.desc() if sort_desc else sort_column)
    
        if offset is not None:
            query = query.offset(offset)
    
        if limit is not None:
            query = query.limit(limit)
    
        return query.all()
    
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
        except Exception as e:
            self.session.rollback()
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
            raise e

    def delete(self, entity: T) -> None:
        """刪除實體
        Args:
            entity: 要刪除的實體
        Returns:
            None
        """
        try:
            self.session.delete(entity)
            self.session.flush()
        except Exception as e:
            self.session.rollback()
            raise e

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
            logger.error(f"批量創建失敗: {str(e)}")
            raise e
    
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


@contextmanager
def repository_context(session: Session, model_class: Type[T], validator=None):
    """使用上下文管理器處理 Repository 的創建和事務管理"""
    repo = Repository(session, model_class, validator)
    try:
        yield repo
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
        