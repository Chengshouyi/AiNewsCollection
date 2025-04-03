import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.articles_model import Articles, Base
from src.services.article_service import ArticleService

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
    return ArticleService(session)  # 直接使用 session，不需要 DatabaseManager

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
        assert result is not None
        assert result.title == article_data["title"]
        assert result.link == article_data["link"]

    def test_batch_insert_articles(self, article_service, session):
        """測試批量新增文章"""
        session.expire_all()  # 確保從數據庫重新讀取
        
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
        
        result = article_service.batch_insert_articles(articles_data)
        session.expire_all()
        assert result["success_count"] == 3
        assert result["fail_count"] == 0
        assert len(result["inserted_articles"]) == 3

    def test_get_article_by_id(self, article_service, sample_articles, session):
        """測試根據ID獲取文章"""
        article_id = sample_articles[0].id
        article = article_service.get_article_by_id(article_id)
        
        assert article is not None
        assert article.id == article_id
        assert article.title == sample_articles[0].title

    def test_get_article_by_link(self, article_service, sample_articles):
        """測試根據連結獲取文章"""
        link = sample_articles[0].link
        article = article_service.get_article_by_link(link)
        
        assert article is not None
        assert article.link == link

    def test_get_articles_paginated(self, article_service, sample_articles):
        """測試分頁獲取文章"""
        result = article_service.get_articles_paginated(page=1, per_page=2)
        
        assert len(result["items"]) == 2
        assert result["total"] == 3
        assert result["page"] == 1
        assert result["per_page"] == 2
        assert result["total_pages"] == 2

    def test_get_ai_related_articles(self, article_service, sample_articles):
        """測試獲取AI相關文章"""
        articles = article_service.get_ai_related_articles()
        assert len(articles) == 2
        assert all(article.is_ai_related for article in articles)

    def test_get_articles_by_category(self, article_service, sample_articles):
        """測試根據分類獲取文章"""
        articles = article_service.get_articles_by_category("AI研究")
        assert len(articles) == 2
        assert all(article.category == "AI研究" for article in articles)

    def test_update_article(self, article_service, sample_articles):
        """測試更新文章"""
        article_id = sample_articles[0].id
        update_data = {
            "title": "更新後的標題",
            "content": "更新後的內容"
        }
        
        updated = article_service.update_article(article_id, update_data)
        assert updated is not None
        assert updated.title == update_data["title"]
        assert updated.content == update_data["content"]

    def test_batch_update_articles(self, article_service, sample_articles):
        """測試批量更新文章"""
        # 準備測試資料
        article_ids = [article.id for article in sample_articles[:2]]  # 取前兩篇文章
        non_existent_id = 99999  # 不存在的ID
        article_ids.append(non_existent_id)  # 加入不存在的ID以測試 missing_ids
        
        update_data = {
            "category": "更新分類",
            "summary": "更新的摘要",
            "content": "更新的內容",
            "link": "https://new-link.com"  # 加入不允許更新的欄位
        }
        
        # 執行批量更新
        result = article_service.batch_update_articles(article_ids, update_data)
        
        # 驗證返回值包含所有必要的欄位
        assert "success_count" in result
        assert "fail_count" in result
        assert "updated_articles" in result
        assert "missing_ids" in result
        assert "error_ids" in result
        assert "invalid_fields" in result  # 驗證新增的欄位
        
        # 驗證更新結果
        assert result["success_count"] == 2  # 應該成功更新兩篇文章
        assert result["fail_count"] == 1  # 一個不存在的ID應該失敗
        assert len(result["updated_articles"]) == 2  # 應該有兩篇更新成功的文章
        assert len(result["missing_ids"]) == 1  # 應該有一個找不到的ID
        assert non_existent_id in result["missing_ids"]  # 確認是我們加入的不存在ID
        assert isinstance(result["error_ids"], list)  # error_ids 應該是列表
        assert "link" in result["invalid_fields"]  # 確認 link 被標記為不合規欄位
        
        # 驗證更新後的文章內容
        for updated_article in result["updated_articles"]:
            assert updated_article.category == "更新分類"
            assert updated_article.summary == "更新的摘要"
            assert updated_article.content == "更新的內容"
            assert updated_article.link != "https://new-link.com"  # 確認 link 沒有被更新
            assert updated_article.id in article_ids[:2]  # 只檢查前兩個ID

    def test_batch_update_articles_with_invalid_data(self, article_service, sample_articles):
        """測試批量更新文章時的錯誤處理"""
        article_ids = [article.id for article in sample_articles]
        
        # 測試無效的更新資料
        invalid_update_data = {
            "link": "https://new-link.com",  # 不允許更新的欄位
            "non_existent_field": "invalid value",  # 不存在的欄位
            "category": "有效分類"  # 有效欄位
        }
        
        result = article_service.batch_update_articles(article_ids, invalid_update_data)
        
        # 驗證返回值
        assert "invalid_fields" in result
        assert "link" in result["invalid_fields"]
        assert result["success_count"] == len(article_ids)  # 應該成功更新所有文章的有效欄位
        assert len(result["updated_articles"]) == len(article_ids)
        assert not result["error_ids"]  # 不應該有錯誤ID
        assert not result["missing_ids"]  # 所有ID都存在
        
        # 驗證更新結果
        for updated_article in result["updated_articles"]:
            assert updated_article.category == "有效分類"  # 有效欄位應該被更新
            assert updated_article.link != "https://new-link.com"  # 無效欄位不應該被更新

    def test_batch_update_articles_with_duplicate_links(self, article_service, sample_articles):
        """測試批量更新文章時處理重複連結的情況"""
        article_ids = [article.id for article in sample_articles[:2]]
        
        # 使用已存在的連結
        existing_link = sample_articles[2].link
        update_data = {
            "link": existing_link
        }
        
        result = article_service.batch_update_articles(article_ids, update_data)
        
        # 驗證返回值
        assert "success_count" in result
        assert "fail_count" in result
        assert "updated_articles" in result
        assert "missing_ids" in result
        assert "error_ids" in result
        
        # 由於連結重複，應該沒有成功更新的文章
        assert result["success_count"] == 0
        assert len(result["updated_articles"]) == 0
        assert len(result["error_ids"]) == 0

    def test_delete_article(self, article_service, sample_articles):
        """測試刪除文章"""
        article_id = sample_articles[0].id
        result = article_service.delete_article(article_id)
        assert result is True
        
        # 確認文章已被刪除
        article = article_service.get_article_by_id(article_id)
        assert article is None

    def test_get_articles_statistics(self, article_service, sample_articles):
        """測試獲取文章統計資訊"""
        stats = article_service.get_articles_statistics()
        
        assert stats["total_articles"] == 3
        assert stats["ai_related_articles"] == 2
        assert "category_distribution" in stats
        assert stats["category_distribution"]["AI研究"] == 2
        assert stats["category_distribution"]["財經"] == 1

    def test_batch_update_articles_empty_data(self, article_service, sample_articles):
        """測試使用空資料進行批量更新"""
        article_ids = [article.id for article in sample_articles[:2]]
        empty_update_data = {}
        
        result = article_service.batch_update_articles(article_ids, empty_update_data)
        
        # 驗證返回值
        assert "invalid_fields" in result
        assert result["success_count"] == 0
        assert result["fail_count"] == 0
        assert len(result["updated_articles"]) == 0
        assert not result["missing_ids"]
        assert not result["error_ids"]
        assert not result["invalid_fields"]  # 空資料不應該有無效欄位

    def test_batch_update_articles_all_invalid_fields(self, article_service, sample_articles):
        """測試所有欄位都是無效的情況"""
        article_ids = [article.id for article in sample_articles[:2]]
        invalid_update_data = {
            "link": "https://new-link.com",
            "id": 999,  # 不允許更新的欄位
            "created_at": datetime.now(timezone.utc)  # 不允許更新的欄位
        }
        
        result = article_service.batch_update_articles(article_ids, invalid_update_data)
        
        # 驗證返回值
        assert "invalid_fields" in result
        assert len(result["invalid_fields"]) == len(invalid_update_data)
        assert result["success_count"] == 0
        assert len(result["updated_articles"]) == 0
        assert not result["missing_ids"]
        assert not result["error_ids"]

class TestArticleServiceAdvancedFeatures:
    """測試文章服務的進階功能"""

    def test_advanced_search_articles(self, article_service, sample_articles):
        """測試進階搜尋文章"""
        # 測試關鍵字搜尋
        articles = article_service.advanced_search_articles(
            keywords="AI",
            is_ai_related=True
        )
        assert len(articles) > 0
        assert all("AI" in article.title for article in articles)
        
        # 測試日期範圍搜尋
        date_range = (
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            datetime(2023, 1, 2, tzinfo=timezone.utc)
        )
        articles = article_service.advanced_search_articles(date_range=date_range)
        assert len(articles) == 2
        
        # 測試多條件組合搜尋
        articles = article_service.advanced_search_articles(
            category="AI研究",
            is_ai_related=True,
            tags=["AI"]
        )
        assert len(articles) == 2
        assert all(article.category == "AI研究" for article in articles)

    def test_search_articles(self, article_service, sample_articles):
        """測試搜尋文章功能"""
        search_terms = {
            "category": "AI研究",
            "is_ai_related": True
        }
        articles = article_service.search_articles(search_terms)
        assert len(articles) == 2
        assert all(
            article.category == "AI研究" and article.is_ai_related 
            for article in articles
        )

    def test_update_article_tags(self, article_service, sample_articles):
        """測試更新文章標籤"""
        article_id = sample_articles[0].id
        new_tags = ["新標籤1", "新標籤2"]
        
        updated = article_service.update_article_tags(article_id, new_tags)
        assert updated is not None
        assert updated.tags == ",".join(new_tags)

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
        
        with pytest.raises(Exception):
            article_service.insert_article(article_data)

        # 測試更新不存在的文章
        assert article_service.update_article(999999, {"title": "新標題"}) is None
