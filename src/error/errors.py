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


class DatabaseError(Exception):
    """資料庫操作基礎異常類"""
    pass


class DatabaseConnectionError(DatabaseError):
    """資料庫連接異常"""
    pass


class DatabaseConfigError(DatabaseError):
    """資料庫設定異常"""
    pass


class DatabaseOperationError(DatabaseError):
    """資料庫操作異常"""
    pass