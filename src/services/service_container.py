
class ServiceContainer:
    """服務容器，管理服務依賴"""

    _instances = {}

    @classmethod
    def get_instance(cls, service_class, *args, **kwargs):
        """獲取服務實例，如果不存在則創建"""
        service_name = service_class.__name__
        if service_name not in cls._instances:
            cls._instances[service_name] = service_class(*args, **kwargs)
        return cls._instances[service_name]

    @classmethod
    def clear_instances(cls):
        """清除所有實例"""
        cls._instances.clear()

def get_crawler_task_service():
    """獲取任務服務實例"""
    from src.services.crawler_task_service import CrawlerTaskService
    return ServiceContainer.get_instance(CrawlerTaskService)

def get_task_executor_service():
    """獲取任務執行器實例"""
    from src.services.task_executor_service import TaskExecutorService
    return ServiceContainer.get_instance(TaskExecutorService)

def get_scheduler_service():
    """獲取排程服務實例"""
    from src.services.scheduler_service import SchedulerService
    return ServiceContainer.get_instance(SchedulerService)

def get_article_service():
    """獲取文章服務實例"""
    from src.services.article_service import ArticleService
    return ServiceContainer.get_instance(ArticleService)

def get_crawlers_service():
    """獲取爬蟲服務實例"""
    from src.services.crawlers_service import CrawlersService
    return ServiceContainer.get_instance(CrawlersService)
