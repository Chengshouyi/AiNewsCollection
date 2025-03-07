"""
模型模組初始化
"""

from model.models import Article
from model.data_access import DataAccess
from model.system_settings import SystemSettings

__all__ = ["Article", "DataAccess", "SystemSettings"]
