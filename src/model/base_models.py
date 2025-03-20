from sqlalchemy.orm import DeclarativeBase

# 自定義應用程式錯誤層級
class DataOperationError(Exception):
    """Base application error"""
    pass

class OptionError(DataOperationError):
    """Option error"""
    pass

class ValidationError(DataOperationError):
    """Validation error"""
    pass

class NotFoundError(DataOperationError):
    """Resource not found error"""
    pass

class Base(DeclarativeBase):
    pass