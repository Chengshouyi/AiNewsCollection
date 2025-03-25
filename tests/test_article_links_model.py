from src.models.article_links_model import ArticleLinks
from src.models.articles_model import Articles
from src.error.errors import ValidationError
from datetime import datetime, timezone
import pytest


class TestArticleLinksModel:
    """ArticleLinks 模型的測試類"""
    
    def test_article_links_creation_with_required_fields(self):
        """測試使用必填欄位創建 ArticleLinks"""
        article_link = ArticleLinks(
            source_name="測試來源",
            source_url="https://test.com",
            article_link="https://test.com/article"
        )
        
        assert article_link.source_name == "測試來源"
        assert article_link.source_url == "https://test.com"
        assert article_link.article_link == "https://test.com/article"
        assert article_link.is_scraped is False
        assert article_link.created_at is not None


    def test_article_links_update_mutable_fields(self):
        """測試 ArticleLinks 的可變欄位更新"""
        article_link = ArticleLinks(
            source_name="原始來源",
            source_url="https://test.com",
            article_link="https://test.com/article"
        )
        
        # 更新可變欄位
        article_link.source_name = "更新後的來源"
        article_link.is_scraped = True
        
        assert article_link.source_name == "更新後的來源"
        assert article_link.is_scraped is True

    def test_article_links_repr(self):
        """測試 ArticleLinks 的 __repr__ 方法"""
        article_link = ArticleLinks(
            source_name="測試來源",
            source_url="https://test.com",
            article_link="https://test.com/article"
        )
        
        expected_repr = "<ArticleLink(id=None, source_name='測試來源', article_link='https://test.com/article')>"
        assert repr(article_link) == expected_repr

    def test_article_links_to_dict(self):
        """測試 ArticleLinks 的 to_dict 方法"""
        article_link = ArticleLinks(
            source_name="測試來源",
            source_url="https://test.com",
            article_link="https://test.com/article"
        )
        
        article_dict = article_link.to_dict()
        assert article_dict['source_name'] == "測試來源"
        assert article_dict['source_url'] == "https://test.com"
        assert article_dict['article_link'] == "https://test.com/article"
        assert article_dict['is_scraped'] is False
        assert 'created_at' in article_dict

    def test_article_relationship(self):
        """測試 ArticleLinks 和 Article 之間的基本關係"""
        article = Articles(
            title="測試文章",
            link="https://test.com/article"
        )
        
        article_link = ArticleLinks(
            source_name="測試來源",
            source_url="https://test.com",
            article_link="https://test.com/article",
            articles=article
        )
        
        assert article_link.articles is not None
        assert article_link.articles.title == "測試文章"
        assert article_link.article_link == article.link

    def test_article_relationship_with_db(self):
        """測試 ArticleLinks 和 Article 之間的關係 (使用內存資料庫)"""
        from src.database.database_manager import DatabaseManager
        from src.models.base_model import Base
        
        # 創建內存資料庫管理器
        db_manager = DatabaseManager('sqlite:///:memory:')
        
        # 創建資料表
        db_manager.create_tables(Base)
        
        # 在資料庫中創建和測試關聯
        with db_manager.session_scope() as session:
            # 創建 Article
            article = Articles(
                title="測試文章",
                link="https://test.com/article"
            )
            
            # 創建 ArticleLinks
            article_link = ArticleLinks(
                source_name="測試來源",
                source_url="https://test.com",
                article_link="https://test.com/article",
                articles=article  # 直接設定關聯
            )
            
            # 保存到資料庫
            session.add(article)
            session.add(article_link)
            session.flush()  # 確保資料被寫入資料庫
            session.expire_all()  # 強制刷新所有物件
            
            # 重新從資料庫讀取
            db_article = session.query(Articles).filter_by(link="https://test.com/article").first()
            db_article_link = session.query(ArticleLinks).filter_by(article_link="https://test.com/article").first()
            
            # 檢查是否獲取到資料
            assert db_article is not None, "資料庫查詢未找到 Article"
            assert db_article_link is not None, "資料庫查詢未找到 ArticleLinks"
            
            # 檢查基本屬性
            assert db_article_link.article_link == db_article.link
            assert db_article_link.source_name == "測試來源"
            assert db_article.title == "測試文章"
            
            # 檢查 ArticleLinks -> Article 關聯
            assert db_article_link.articles is not None, "ArticleLinks 未建立關聯到 Article"
            assert db_article_link.articles.title == "測試文章"
            
            # 測試反向關聯
            assert db_article.article_links is not None
            assert len(db_article.article_links) > 0, "Article 沒有關聯的 ArticleLinks"
            assert db_article.article_links[0].source_name == "測試來源"  # 檢查第一個關聯的 ArticleLink