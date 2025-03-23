from .base_rerository import BaseRepository
from ..model.article_models import ArticleLinks, Article
from typing import Optional, List, Dict, Any


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

    def search_by_title(self, keyword: str, exact_match: bool = False) -> List['Article']:
        """根據標題搜索文章
        
        Args:
            keyword: 搜索關鍵字
            exact_match: 是否進行精確匹配（預設為模糊匹配）
        
        Returns:
            符合條件的文章列表
        """
        if exact_match:
            # 精確匹配（區分大小寫）
            return self.session.query(self.model_class).filter(
                self.model_class.title == keyword
            ).all()
        else:
            # 模糊匹配
            return self.session.query(self.model_class).filter(
                self.model_class.title.like(f'%{keyword}%')
            ).all()
    
