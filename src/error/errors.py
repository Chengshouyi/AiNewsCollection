# 自定義應用程式錯誤層級
class DataOperationError(Exception):
    """基礎應用程式錯誤"""
    pass
class DatabaseError(Exception):
    """資料庫操作基礎異常類"""
    pass


class OptionError(DataOperationError):
    """選項錯誤"""
    pass

class ValidationError(DataOperationError):
    """驗證錯誤"""
    pass

class NotFoundError(DataOperationError):
    """沒有找到資料"""
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


class InvalidOperationError(DatabaseError):
    """無效的操作異常"""
    pass


class InvalidQueryError(DatabaseError):
    """無效的查詢異常"""
    pass

class IntegrityValidationError(ValidationError):
    """完整性約束驗證錯誤"""
    pass

class ForeignKeyValidationError(ValidationError):
    """外鍵約束驗證錯誤"""
    pass

class NotNullValidationError(ValidationError):
    """非空約束驗證錯誤"""
    pass


class UniqueValidationError(ValidationError):
    """唯一性約束驗證錯誤"""
    pass







