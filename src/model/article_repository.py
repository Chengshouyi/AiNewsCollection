from .base_rerository import BaseRepository
from .article_models import ArticleLinks, Article
from typing import Optional, List

class ArticleLinksRepository(BaseRepository['ArticleLinks']):
    """ArticleLinks 特定的Repository"""
    
    def find_by_article_link(self, article_link: str) -> Optional['ArticleLinks']:
        """根據文章連結查詢"""
        return self.session.query(self.model_class).filter_by(article_link=article_link).first()
    
    def find_unscraped_links(self, limit: int = 100) -> List['ArticleLinks']:
        """查詢未爬取的連結"""
        return self.session.query(self.model_class).filter_by(is_scraped=False).limit(limit).all()


class ArticleRepository(BaseRepository['Article']):
    """Article 特定的Repository"""
    
    def find_by_link(self, link: str) -> Optional['Article']:
        """根據文章連結查詢"""
        return self.session.query(self.model_class).filter_by(link=link).first()
    
    def find_by_category(self, category: str) -> List['Article']:
        """根據分類查詢文章"""
        return self.session.query(self.model_class).filter_by(category=category).all()

    def search_by_title(self, keyword: str) -> List['Article']:
        """根據標題搜索文章"""
        return self.session.query(self.model_class).filter(
            self.model_class.title.like(f'%{keyword}%')
        ).all()