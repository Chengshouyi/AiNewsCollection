from .base_repository import BaseRepository
from src.models.article_links_model import ArticleLinks
from typing import Optional, List


class ArticleLinksRepository(BaseRepository['ArticleLinks']):
    """ArticleLinks 特定的Repository"""
    
    def find_by_article_link(self, article_link: str) -> Optional['ArticleLinks']:
        """根據文章連結查詢"""
        return self.session.query(self.model_class).filter_by(article_link=article_link).first()
    
    def find_unscraped_links(self, limit: int = 100) -> List['ArticleLinks']:
        """查詢未爬取的連結"""
        return self.session.query(self.model_class).filter_by(is_scraped=False).limit(limit).all()