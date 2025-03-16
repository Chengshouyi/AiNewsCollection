import logging
from typing import Optional, List, Type, TypeVar, Generic
from sqlalchemy.orm import Session
from sqlalchemy.orm.decl_api import DeclarativeBase

# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

T = TypeVar('T', bound=DeclarativeBase)


class Repository(Generic[T]):
    """通用Repository模式實現，用於基本CRUD操作"""
    
    def __init__(self, session: Session, model_class: Type[T]):
        self.session = session
        self.model_class = model_class
        
    def get_by_id(self, id: int) -> Optional[T]:
        """根據ID獲取實體"""
        return self.session.query(self.model_class).filter_by(id=id).first()
    
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
        """創建新實體"""
        entity = self.model_class(**kwargs)
        self.session.add(entity)
        return entity
    
    def update(self, entity: T, **kwargs) -> T:
        """更新實體"""
        for key, value in kwargs.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        return entity
    
    def delete(self, entity: T) -> None:
        """刪除實體"""
        self.session.delete(entity)
    
    def exists(self, **kwargs) -> bool:
        """檢查是否存在滿足條件的實體"""
        return self.session.query(self.model_class).filter_by(**kwargs).first() is not None
