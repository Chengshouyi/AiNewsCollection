import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.articles_model import Articles, Base
from src.services.article_service import ArticleService
from src.database.database_manager import DatabaseManager

# 設置測試資料庫
@pytest.fixture(scope="session")
def engine():
    """創建測試用的資料庫引擎"""
    return create_engine('sqlite:///:memory:')

@pytest.fixture(scope="session")
def tables(engine):
    """創建資料表"""
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="session")
def session_factory(engine):
    """創建會話工廠"""
    return sessionmaker(bind=engine)

@pytest.fixture(scope="function")
def session(session_factory, tables):
    """為每個測試函數創建新的會話"""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture(scope="function")
def article_service(session):
    """創建文章服務實例"""
    # 使用記憶體資料庫
    db_manager = DatabaseManager('sqlite:///:memory:')
    # 設置測試用的 session
    db_manager.Session = sessionmaker(bind=session.get_bind())
    return ArticleService(db_manager)

@pytest.fixture(scope="function")
def sample_articles(session):
    """創建測試用的文章資料"""
    # 清除現有資料
    session.query(Articles).delete()
    session.commit()
    
    articles = [
        Articles(
            title="AI發展新突破",
            link="https://example.com/ai1",
            summary="AI領域的重大突破",
            content="詳細的AI研究內容",
            source="科技日報",
            source_url="https://example.com/source1",
            category="AI研究",
            published_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            is_ai_related=True,
            is_scraped=True,
            tags="AI,研究"
        ),
        Articles(
            title="市場分析報告",
            link="https://example.com/market1",
            summary="市場趨勢分析",
            content="詳細的市場分析內容",
            source="財經週刊",
            source_url="https://example.com/source2",
            category="財經",
            published_at=datetime(2023, 1, 2, tzinfo=timezone.utc),
            is_ai_related=False,
            is_scraped=True,
            tags="財經,市場"
        ),
        Articles(
            title="機器學習應用",
            link="https://example.com/ml1",
            summary="機器學習在產業的應用",
            content="機器學習應用案例",
            source="科技日報",
            source_url="https://example.com/source3",
            category="AI研究",
            published_at=datetime(2023, 1, 3, tzinfo=timezone.utc),
            is_ai_related=True,
            is_scraped=True,
            tags="AI,機器學習"
        )
    ]
    
    session.add_all(articles)
    session.commit()
    return articles

class TestArticleService:
    """測試文章服務的核心功能"""

    def test_insert_article(self, article_service):
        """測試新增單一文章"""
        article_data = {
            "title": "測試文章",
            "link": "https://test.com/article1",
            "summary": "測試摘要",
            "content": "測試內容",
            "source": "測試來源",
            "source_url": "https://test.com/source",
            "category": "測試",
            "published_at": datetime.now(timezone.utc),
            "is_ai_related": True,
            "is_scraped": True,
            "tags": "測試,文章"
        }
        
        result = article_service.insert_article(article_data)
        assert result["success"] is True
        assert "article" in result
        assert result["article"].title == article_data["title"]
        assert result["article"].link == article_data["link"]

    def test_batch_create_articles(self, article_service):
        """測試批量新增文章"""
        articles_data = [
            {
                "title": f"batch_測試文章{i}",
                "link": f"https://test.com/batch_article{i}",
                "summary": f"batch_測試摘要{i}",
                "content": f"batch_測試內容{i}",
                "source": "測試來源",
                "source_url": f"https://test.com/batch_source{i}",
                "category": "測試",
                "published_at": datetime.now(timezone.utc),
                "is_ai_related": True,
                "is_scraped": True,
                "tags": "測試,文章"
            }
            for i in range(3)
        ]
        
        result = article_service.batch_create_articles(articles_data)
        assert result["success"] is True
        assert result["resultMsg"]["success_count"] == 3
        assert result["resultMsg"]["fail_count"] == 0
        assert len(result["resultMsg"]["inserted_articles"]) == 3

    def test_get_article_by_id(self, article_service, sample_articles):
        """測試根據ID獲取文章"""
        article_id = sample_articles[0].id
        result = article_service.get_article_by_id(article_id)
        
        assert result["success"] is True
        assert result["article"].id == article_id
        assert result["article"].title == sample_articles[0].title

    def test_get_article_by_link(self, article_service, sample_articles):
        """測試根據連結獲取文章"""
        link = sample_articles[0].link
        result = article_service.get_article_by_link(link)
        
        assert result["success"] is True
        assert result["article"].link == link

    def test_get_articles_paginated(self, article_service, sample_articles):
        """測試分頁獲取文章"""
        result = article_service.get_articles_paginated(page=1, per_page=2)
        
        assert result["success"] is True
        assert len(result["resultMsg"]["items"]) == 2
        assert result["resultMsg"]["total"] == 3
        assert result["resultMsg"]["page"] == 1
        assert result["resultMsg"]["per_page"] == 2
        assert result["resultMsg"]["total_pages"] == 2

    def test_get_ai_related_articles(self, article_service, sample_articles):
        """測試獲取AI相關文章"""
        result = article_service.get_ai_related_articles()
        assert result["success"] is True
        assert len(result["articles"]) == 2
        assert all(article.is_ai_related for article in result["articles"])

    def test_get_articles_by_category(self, article_service, sample_articles):
        """測試根據分類獲取文章"""
        result = article_service.get_articles_by_category("AI研究")
        assert result["success"] is True
        assert len(result["articles"]) == 2
        assert all(article.category == "AI研究" for article in result["articles"])

    def test_update_article(self, article_service, sample_articles):
        """測試更新文章"""
        article_id = sample_articles[0].id
        update_data = {
            "title": "更新後的標題",
            "content": "更新後的內容"
        }
        
        result = article_service.update_article(article_id, update_data)
        assert result["success"] is True
        assert result["message"] == "文章更新成功"

    def test_batch_update_articles_by_ids(self, article_service, sample_articles):
        """測試批量更新文章"""
        article_ids = [article.id for article in sample_articles[:2]]
        update_data = {
            "category": "更新分類",
            "summary": "更新的摘要"
        }
        
        result = article_service.batch_update_articles_by_ids(article_ids, update_data)
        assert result["success"] is True
        assert result["resultMsg"]["success_count"] == 2
        assert result["resultMsg"]["fail_count"] == 0
        assert len(result["resultMsg"]["updated_articles"]) == 2

    def test_batch_update_articles_by_link(self, article_service, sample_articles):
        """測試根據連結批量更新文章"""
        # 準備包含連結和更新資料的列表
        article_data = [
            {
                "link": sample_articles[0].link,
                "category": "更新分類1",
                "summary": "更新的摘要1"
            },
            {
                "link": sample_articles[1].link,
                "category": "更新分類2",
                "summary": "更新的摘要2"
            }
        ]
        
        result = article_service.batch_update_articles_by_link(article_data)
        
        assert result["success"] is True
        assert result["resultMsg"]["success_count"] == 2
        assert result["resultMsg"]["fail_count"] == 0
        assert len(result["resultMsg"]["updated_articles"]) == 2

    def test_delete_article(self, article_service, sample_articles):
        """測試刪除文章"""
        article_id = sample_articles[0].id
        result = article_service.delete_article(article_id)
        assert result["success"] is True
        assert result["message"] == "文章刪除成功"
        
        # 確認文章已被刪除
        result = article_service.get_article_by_id(article_id)
        assert result["success"] is False
        assert result["message"] == "文章不存在"

    def test_get_articles_statistics(self, article_service, sample_articles):
        """測試獲取文章統計資訊"""
        result = article_service.get_articles_statistics()
        
        assert result["resultMsg"]["total_articles"] == 3
        assert result["resultMsg"]["ai_related_articles"] == 2
        assert "category_distribution" in result["resultMsg"]
        assert result["resultMsg"]["category_distribution"]["AI研究"] == 2
        assert result["resultMsg"]["category_distribution"]["財經"] == 1

    def test_error_handling(self, article_service):
        """測試錯誤處理"""
        # 測試創建重複連結的文章
        article_data = {
            "title": "重複連結測試",
            "link": "https://example.com/ai1",  # 使用已存在的連結
            "summary": "測試摘要",
            "content": "測試內容",
            "source": "測試來源",
            "source_url": "https://test.com/source",
            "category": "測試",
            "published_at": datetime.now(timezone.utc),
            "is_ai_related": True,
            "is_scraped": True
        }
        
        result = article_service.insert_article(article_data)
        assert result["success"] is True #自動轉為更新
        assert "文章創建成功" in result["message"]

        # 測試更新不存在的文章
        result = article_service.update_article(999999, {"title": "新標題"})
        assert result["success"] is False
        assert result["message"] == "文章不存在"

class TestArticleServiceAdvancedFeatures:
    """測試文章服務的進階功能"""

    def test_advanced_search_articles(self, article_service, sample_articles):
        """測試進階搜尋文章"""
        # 測試關鍵字搜尋
        result = article_service.advanced_search_articles(
            keywords="AI",
            is_ai_related=True
        )
        assert result["success"] is True
        assert len(result["articles"]) > 0
        assert all("AI" in article.title for article in result["articles"])
        
        # 測試日期範圍搜尋
        date_range = (
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            datetime(2023, 1, 2, tzinfo=timezone.utc)
        )
        result = article_service.advanced_search_articles(date_range=date_range)
        assert result["success"] is True
        assert len(result["articles"]) == 2
        
        # 測試多條件組合搜尋
        result = article_service.advanced_search_articles(
            category="AI研究",
            is_ai_related=True,
            tags=["AI"]
        )
        assert result["success"] is True
        assert len(result["articles"]) == 2
        assert all(article.category == "AI研究" for article in result["articles"])


    def test_update_article_tags(self, article_service, sample_articles):
        """測試更新文章標籤"""
        article_id = sample_articles[0].id
        new_tags = ["新標籤1", "新標籤2"]
        
        result = article_service.update_article_tags(article_id, new_tags)
        assert result["success"] is True
        assert result["message"] == "更新文章標籤成功"
        assert result["article"].tags == ",".join(new_tags)
