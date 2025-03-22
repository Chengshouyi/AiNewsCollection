from .base_rerository import BaseRepository
from .article_models import ArticleLinks, Article
from typing import Optional, List, Dict, Any
from sqlalchemy import desc, asc


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
    
    def get_all_articles(self, limit: Optional[int] = None, offset: Optional[int] = None, sort_by: Optional[str] = None, sort_desc: bool = False) -> List['Article']:
        """獲取所有文章，支援分頁和排序

        Args:
            limit: 限制返回結果數量
            offset: 跳過結果數量
            sort_by: 排序欄位名稱
            sort_desc: 是否降序排列

        Returns:
            文章列表
        """
        query = self.session.query(self.model_class)
        
        # 處理排序
        if sort_by and hasattr(self.model_class, sort_by):
            order_column = getattr(self.model_class, sort_by)
            if sort_desc:
                query = query.order_by(desc(order_column))
            else:
                query = query.order_by(asc(order_column))
        else:
            # 預設按創建時間降序排列
            query = query.order_by(desc(self.model_class.created_at))
        
        # 處理分頁
        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
            
        return query.all()
    
    def get_paginated(self, page: int, per_page: int, sort_by: Optional[str] = None, sort_desc: bool = False) -> Dict[str, Any]:
        """獲取分頁文章資料

        Args:
            page: 當前頁碼，從1開始
            per_page: 每頁數量
            sort_by: 排序欄位
            sort_desc: 是否降序排列

        Returns:
            包含分頁資訊和結果的字典
        """
        # 計算總記錄數
        total = self.session.query(self.model_class).count()
        
        # 計算總頁數
        total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0
        
        # 確保頁碼有效
        current_page = max(1, min(page, total_pages)) if total_pages > 0 else 1
        
        # 計算偏移量
        offset = (current_page - 1) * per_page
        
        # 獲取當前頁數據
        items = self.get_all_articles(
            limit=per_page, 
            offset=offset,
            sort_by=sort_by,
            sort_desc=sort_desc
        )
        
        # 構建分頁結果
        return {
            "items": items,
            "page": current_page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": current_page < total_pages,
            "has_prev": current_page > 1
        }
