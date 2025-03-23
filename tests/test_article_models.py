import pytest
from datetime import datetime, timezone
from src.model.article_models import Article, ArticleLinks
from src.model.base_models import ValidationError

class TestArticleModel:
    """Article 模型的測試類"""
    
    def test_article_creation_with_required_fields_only(self):
        """測試只使用必填欄位創建 Article"""
        article = Article(
            title="測試文章",
            link="https://test.com/article"
        )
        
        assert article.title == "測試文章"
        assert article.link == "https://test.com/article"
        assert article.published_at is None
        assert article.summary is None
        assert article.content is None
        assert article.source is None
        assert article.created_at is not None

    def test_article_creation_with_all_fields(self):
        """測試使用所有欄位創建 Article"""
        article = Article(
            title="完整測試文章",
            link="https://test.com/full-article",
            summary="這是一篇測試文章的摘要",
            content="這是一篇測試文章的完整內容，包含了多個段落...",
            category="科技",
            published_at="2023-04-01",
            author="測試作者",
            source="測試來源",
            article_type="新聞",
            tags="AI,科技,測試"
        )
        
        assert article.title == "完整測試文章"
        assert article.link == "https://test.com/full-article"
        assert article.summary == "這是一篇測試文章的摘要"
        assert article.content == "這是一篇測試文章的完整內容，包含了多個段落..."
        assert article.category == "科技"
        assert article.published_at == "2023-04-01"
        assert article.author == "測試作者"
        assert article.source == "測試來源"
        assert article.article_type == "新聞"
        assert article.tags == "AI,科技,測試"
        assert article.created_at is not None
        assert article.updated_at is None

    def test_article_immutable_fields(self):
        """測試 Article 的不可變欄位"""
        article = Article(
            title="測試文章",
            link="https://test.com/article"
        )
        
        # 測試不可修改 id
        with pytest.raises(ValidationError, match="id cannot be updated"):
            article.id = 100
            
        # 測試不可修改 link
        with pytest.raises(ValidationError, match="link cannot be updated"):
            article.link = "https://test.com/new-link"
            
        # 測試不可修改 created_at
        with pytest.raises(ValidationError, match="created_at cannot be updated"):
            article.created_at = datetime.now(timezone.utc)

    def test_article_update_mutable_fields(self):
        """測試 Article 的可變欄位更新"""
        article = Article(
            title="原始標題",
            link="https://test.com/article",
            summary="原始摘要"
        )
        
        # 更新可變欄位
        article.title = "更新後的標題"
        article.summary = "更新後的摘要"
        article.content = "新增的內容"
        
        assert article.title == "更新後的標題"
        assert article.summary == "更新後的摘要"
        assert article.content == "新增的內容"

    def test_article_repr(self):
        """測試 Article 的 __repr__ 方法"""
        article = Article(
            id=1,
            title="測試文章",
            link="https://test.com/article"
        )
        
        assert repr(article) == "<Article(id=1, title='測試文章', link='https://test.com/article')>"


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

    def test_article_links_immutable_fields(self):
        """測試 ArticleLinks 的不可變欄位"""
        article_link = ArticleLinks(
            source_name="測試來源",
            source_url="https://test.com",
            article_link="https://test.com/article"
        )
        
        # 測試不可修改 id
        with pytest.raises(ValidationError, match="id cannot be updated"):
            article_link.id = 100
            
        # 測試不可修改 article_link
        with pytest.raises(ValidationError, match="article_link cannot be updated"):
            article_link.article_link = "https://test.com/new-article"
            
        # 測試不可修改 created_at
        with pytest.raises(ValidationError, match="created_at cannot be updated"):
            article_link.created_at = datetime.now()

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
            id=1,
            source_name="測試來源",
            source_url="https://test.com",
            article_link="https://test.com/article",
            is_scraped=False
        )
        
        assert repr(article_link) == "<ArticleLink(id=1, source_name='測試來源', source_url='https://test.com', article_link='https://test.com/article', is_scraped=False)>"

    def test_article_relationship(self):
        """測試 ArticleLinks 和 Article 之間的關係"""
        # 創建 Article
        article = Article(
            title="測試文章",
            link="https://test.com/article"
        )
        
        # 創建 ArticleLinks 並設置關聯
        article_link = ArticleLinks(
            source_name="測試來源",
            source_url="https://test.com",
            article_link="https://test.com/article"
        )
        
        # 基本檢查連結是否相同
        assert article_link.article_link == article.link
        
        # 模擬資料庫操作後的關聯
        article_link.article = article
        
        # 檢查關聯是否正確設置
        assert article_link.article is not None
        assert article_link.article.title == "測試文章"
        
        # 註：在測試環境中，反向關聯 article.article_links 需要實際資料庫支援
        # 因此，這裡不測試反向關聯

    def test_article_relationship_with_db(self):
        """測試 ArticleLinks 和 Article 之間的關係 (使用內存資料庫)"""
        from src.database.database_manager import DatabaseManager
        from src.model.base_models import Base
        
        # 創建內存資料庫管理器
        db_manager = DatabaseManager('sqlite:///:memory:')
        
        # 創建資料表
        db_manager.create_tables(Base)
        
        # 在資料庫中創建和測試關聯
        with db_manager.session_scope() as session:
            # 創建 Article
            article = Article(
                title="測試文章",
                link="https://test.com/article"
            )
            
            # 創建 ArticleLinks
            article_link = ArticleLinks(
                source_name="測試來源",
                source_url="https://test.com",
                article_link="https://test.com/article"
            )
            
            # 保存到資料庫
            session.add(article)
            session.add(article_link)
            session.flush()  # 確保資料被寫入資料庫
            session.expire_all()  # 強制刷新所有物件
            
            # 重新從資料庫讀取
            db_article = session.query(Article).filter_by(link="https://test.com/article").first()
            db_article_link = session.query(ArticleLinks).filter_by(article_link="https://test.com/article").first()
            
            # 檢查是否獲取到資料
            assert db_article is not None, "資料庫查詢未找到 Article"
            assert db_article_link is not None, "資料庫查詢未找到 ArticleLinks"
            
            # 檢查基本屬性
            assert db_article_link.article_link == db_article.link
            assert db_article_link.source_name == "測試來源"
            assert db_article.title == "測試文章"
            
            # 檢查 ArticleLinks -> Article 關聯
            assert db_article_link.article is not None, "ArticleLinks 未建立關聯到 Article"
            assert db_article_link.article.title == "測試文章"
            
            # 測試反向關聯
            assert db_article.article_links is not None
            assert db_article.article_links.source_name == "測試來源"