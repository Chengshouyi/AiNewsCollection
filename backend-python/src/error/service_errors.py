class ServiceError(Exception):
    """服務初始化錯誤"""
    pass

class ServiceExecutionError(ServiceError):
    """服務執行錯誤"""
    pass

class ServiceInitializationError(ServiceError):
    """服務初始化錯誤"""
    pass

class ServiceCleanupError(ServiceError):
    """服務清理錯誤"""
    pass

class ServiceShutdownError(ServiceError):
    """服務關閉錯誤"""
    pass
