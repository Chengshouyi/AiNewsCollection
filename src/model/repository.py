from typing import TypeVar, Generic, Type, Optional, List, Dict, Any, Callable
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from .models import Base, AppError, ValidationError, NotFoundError
from contextlib import contextmanager
import logging
# 設定 logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

T = TypeVar('T', bound=Base)

class Result:
    """表示操作結果的類別，包含成功/失敗狀態和詳細錯誤信息"""
    def __init__(self, success: bool, data=None, error=None, error_message=None):
        self.success = success
        self.data = data
        self.error = error
        self.error_message = error_message

    @classmethod
    def succeed(cls, data=None):
        return cls(True, data=data)

    @classmethod
    def failure(cls, error_message, error=None):
        return cls(False, error=error, error_message=error_message)
    

class Repository(Generic[T]):
    """通用Repository模式實現，用於基本CRUD操作"""
    
    def __init__(self, session: Session, model_class: Type[T], validator: Optional[Callable] = None):
        self.session = session
        self.model_class = model_class
        self.validator = validator  # 可選的驗證器

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
    
    def create(self, **kwargs) -> Result:
        """創建新實體，處理唯一性約束"""
        try:
            # 如果有驗證器，先進行驗證
            if self.validator:
                try:
                    kwargs = self.validator(kwargs)
                except Exception as e:
                    return Result.failure(f"驗證失敗: {str(e)}", e)
                
            entity = self.model_class(**kwargs)
            self.session.add(entity)
            self.session.flush()  # 立即獲取 ID
            return Result.succeed(entity)
        except IntegrityError as e:
            self.session.rollback()
            if "unique constraint" in str(e).lower():
                return Result.failure("資料已存在，違反唯一性約束", e)
            return Result.failure(f"資料庫約束違反: {str(e)}", e)
        except SQLAlchemyError as e:
            self.session.rollback()
            return Result.failure(f"資料庫錯誤: {str(e)}", e)
        except Exception as e:
            self.session.rollback()
            return Result.failure(f"創建實體時發生錯誤: {str(e)}", e)
    
    def update(self, entity: T, **kwargs) -> Result:
        """更新實體"""
        try:
            if not entity:
                return Result.failure(f"找不到要更新的實體")
            
            # 如果有驗證器，先進行驗證
            if self.validator:
                try:
                    kwargs = self.validator(kwargs, is_update=True)
                except Exception as e:
                    return Result.failure(f"驗證失敗: {str(e)}", e)
            
            # 更新屬性
            for key, value in kwargs.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            
            self.session.flush()
            return Result.succeed(entity)
        except IntegrityError as e:
            self.session.rollback()
            if "unique constraint" in str(e).lower():
                return Result.failure("資料已存在，違反唯一性約束", e)
            return Result.failure(f"資料庫約束違反: {str(e)}", e)
        except SQLAlchemyError as e:
            self.session.rollback()
            return Result.failure(f"資料庫錯誤: {str(e)}", e)
        except Exception as e:
            self.session.rollback()
            return Result.failure(f"更新實體時發生錯誤: {str(e)}", e)

    def delete(self, entity: T) -> Result:
        """刪除實體"""
        try:
            if not entity:
                return Result.failure(f"找不到要刪除的實體")
            
            self.session.delete(entity)
            self.session.flush()
            return Result.succeed(True)
        except SQLAlchemyError as e:
            self.session.rollback()
            return Result.failure(f"資料庫錯誤: {str(e)}", e)
        except Exception as e:
            self.session.rollback()
            return Result.failure(f"刪除實體時發生錯誤: {str(e)}", e)

    def batch_create(self, items_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量創建實體"""
        results = {
            "success_count": 0,
            "fail_count": 0,
            "failed_items": []
        }
        
        for item_data in items_data:
            result = self.create(**item_data)
            if result.success:
                results["success_count"] += 1
            else:
                results["fail_count"] += 1
                results["failed_items"].append({
                    "data": item_data,
                    "error": result.error_message
                })
        
        return results
    
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
        