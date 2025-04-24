from src.web.routes.article_api import article_bp
from src.web.routes.tasks_api import tasks_bp
from src.web.routes.crawler_api import crawler_bp
from src.web.routes.views import view_bp

__all__ = ['article_bp', 'tasks_bp', 'crawler_bp', 'view_bp']