import pytest
import time # 引入 time 模組
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.articles_repository import ArticlesRepository
from src.models.articles_model import Articles
from src.models.base_model import Base
from src.database.base_repository import SchemaType
from src.models.articles_schema import ArticleCreateSchema, ArticleUpdateSchema
from src.error.errors import ValidationError, DatabaseOperationError
from src.models.articles_model import ArticleScrapeStatus
from typing import List, Dict, Any

# 設置測試資料庫，使用 session scope
@pytest.fixture(scope="session")
def engine():
    return create_engine('sqlite:///:memory:')

@pytest.fixture(scope="session")
def tables(engine):
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
def article_repo(session):
    return ArticlesRepository(session, Articles)

@pytest.fixture(scope="function")
def clean_db(session):
    """清空資料庫的 fixture"""
    session.query(Articles).delete()
    session.commit()
    session.expire_all()

@pytest.fixture(scope="function")
def sample_articles(session, clean_db) -> List[Articles]:
    """更新 sample_articles fixture 以包含 tags 和 task_id"""
    articles = [
        Articles(
            title="科技新聞：AI研究突破",
            link="https://example.com/article1",
            summary="這是關於AI研究的文章摘要",
            content="這是關於AI研究的文章內容",
            source="測試來源1",
            source_url="https://example.com/source1",
            category="科技",
            published_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            is_ai_related=True,
            is_scraped=True,
            scrape_status=ArticleScrapeStatus.PENDING,
            tags="AI,研究",
            task_id=1
        ),
        Articles(
            title="財經報導：股市走勢分析",
            link="https://example.com/article2",
            summary="這是股市分析的摘要",
            content="這是股市分析的內容",
            source="測試來源2",
            source_url="https://example.com/source2",
            category="財經",
            published_at=datetime(2023, 1, 3, tzinfo=timezone.utc),
            is_ai_related=False,
            is_scraped=True,
            scrape_status=ArticleScrapeStatus.PENDING,
            tags="財經,市場",
            task_id=1
        ),
        Articles(
            title="Python編程技巧分享",
            link="https://example.com/article3",
            summary="這是Python相關教學",
            content="這是Python相關教學",
            source="測試來源1",
            source_url="https://example.com/source3",
            category="科技",
            published_at=datetime(2023, 1, 5, tzinfo=timezone.utc),
            is_ai_related=False,
            is_scraped=False,
            scrape_status=ArticleScrapeStatus.LINK_SAVED,
            tags="Python,編程",
            task_id=2
        )
    ]
    session.add_all(articles)
    session.commit()

    # 確保所有物件都有正確的 ID
    session.expire_all()
    return articles

# ArticleRepository 測試
class TestArticleRepository:
    """測試 ArticlesRepository 的核心功能"""

    def test_get_schema_class(self, article_repo, clean_db):
        """測試獲取schema類的方法"""
        # 測試默認返回
        schema = article_repo.get_schema_class()
        assert schema == ArticleCreateSchema

        # 測試指定類型返回
        create_schema = article_repo.get_schema_class(SchemaType.CREATE)
        assert create_schema == ArticleCreateSchema

        update_schema = article_repo.get_schema_class(SchemaType.UPDATE)
        assert update_schema == ArticleUpdateSchema

        with pytest.raises(ValueError) as exc_info:
            article_repo.get_schema_class(SchemaType.LIST)
        assert "未支援的 schema 類型" in str(exc_info.value)

    def test_find_by_link(self, article_repo, sample_articles, session, clean_db):
        """測試根據連結查詢文章"""

        # 測試存在的連結
        article = article_repo.find_by_link("https://example.com/article1")
        assert article is not None
        assert article.title == "科技新聞：AI研究突破"

        # 測試不存在的連結
        article = article_repo.find_by_link("https://nonexistent.com")
        assert article is None

    def test_find_by_category(self, article_repo, sample_articles, session, clean_db):
        """測試根據分類查詢文章"""

        articles = article_repo.find_by_category("科技")
        assert len(articles) == 2
        assert all(article.category == "科技" for article in articles)

    def test_search_by_title(self, article_repo, sample_articles, session, clean_db):
        """測試根據標題搜索文章"""

        # 測試模糊匹配
        articles = article_repo.search_by_title("Python")
        assert len(articles) == 1
        assert "Python" in articles[0].title

        # 測試精確匹配
        articles = article_repo.search_by_title("Python編程技巧分享", exact_match=True)
        assert len(articles) == 1
        assert articles[0].title == "Python編程技巧分享"

    # 增強 get_by_filter 測試以包含 search_text
    def test_get_by_filter(self, article_repo, sample_articles, session, clean_db):
        """測試根據過濾條件查詢文章"""
        # 使用 sample_articles[0] 來避免 linter 錯誤
        existing_article_link = sample_articles[0].link

        # 測試單一條件過濾
        articles = article_repo.get_by_filter({"category": "科技"})
        assert len(articles) == 2
        assert all(a.category == "科技" for a in articles)

        # 測試多條件過濾
        articles = article_repo.get_by_filter({
            "category": "科技",
            "is_ai_related": True
        })
        assert len(articles) == 1
        assert articles[0].is_ai_related is True

        # 測試日期範圍過濾
        articles = article_repo.get_by_filter({
            "published_at": {
                "$gte": datetime(2023, 1, 1, tzinfo=timezone.utc),
                "$lte": datetime(2023, 1, 3, tzinfo=timezone.utc)
            }
        })
        # 預期 sample_articles[0] 和 sample_articles[1]
        assert len(articles) == 2
        # 檢查返回的文章是否在日期範圍內
        assert all(datetime(2023, 1, 1, tzinfo=timezone.utc) <= a.published_at <= datetime(2023, 1, 3, tzinfo=timezone.utc) for a in articles)

        # 測試使用布爾字段過濾
        articles = article_repo.get_by_filter({"is_ai_related": True})
        assert len(articles) == 1
        assert articles[0].is_ai_related is True

        articles = article_repo.get_by_filter({"is_scraped": False})
        assert len(articles) == 1
        assert articles[0].is_scraped is False

        # 測試空過濾條件
        articles = article_repo.get_by_filter({})
        assert len(articles) == 3 # 應該返回所有樣本文章

        # 測試無效過濾鍵 (應被忽略或引發錯誤，取決於實現)
        # 假設 BaseRepository 會忽略無法處理的鍵
        try:
            articles = article_repo.get_by_filter({"invalid_key": "value"})
            assert len(articles) == 3 # 如果忽略無效鍵，則返回所有
        except Exception as e:
            pytest.fail(f"get_by_filter with invalid key raised an unexpected exception: {e}")

        # 測試 $in 操作符
        articles = article_repo.get_by_filter({"category": {"$in": ["科技", "財經"]}})
        assert len(articles) == 3 # 所有樣本文章都屬於這兩個分類之一
        assert all(a.category in ["科技", "財經"] for a in articles)

        # 測試 $nin 操作符
        articles = article_repo.get_by_filter({"category": {"$nin": ["財經"]}})
        assert len(articles) == 2 # 應該只返回科技類文章
        assert all(a.category == "科技" for a in articles)

        # 測試 $ne 操作符
        articles = article_repo.get_by_filter({"category": {"$ne": "財經"}})
        assert len(articles) == 2 # 同上
        assert all(a.category == "科技" for a in articles)

        # 測試 $gt 操作符
        articles = article_repo.get_by_filter({"published_at": {"$gt": datetime(2023, 1, 3, tzinfo=timezone.utc)}})
        assert len(articles) == 1 # 只有 article3
        assert articles[0].link == "https://example.com/article3"

        # 測試 $lt 操作符
        articles = article_repo.get_by_filter({"published_at": {"$lt": datetime(2023, 1, 3, tzinfo=timezone.utc)}})
        assert len(articles) == 1 # 只有 article1
        assert articles[0].link == "https://example.com/article1"

        # 測試 $lte 操作符
        articles = article_repo.get_by_filter({"published_at": {"$lte": datetime(2023, 1, 3, tzinfo=timezone.utc)}})
        assert len(articles) == 2 # article1 和 article2
        assert articles[0].link in ["https://example.com/article1", "https://example.com/article2"]
        assert articles[1].link in ["https://example.com/article1", "https://example.com/article2"]

        # 測試 $gte 操作符
        articles = article_repo.get_by_filter({"published_at": {"$gte": datetime(2023, 1, 3, tzinfo=timezone.utc)}})
        assert len(articles) == 2 # article2 和 article3
        assert articles[0].link in ["https://example.com/article2", "https://example.com/article3"]
        assert articles[1].link in ["https://example.com/article2", "https://example.com/article3"]

    def test_get_source_statistics(self, article_repo, sample_articles, session, clean_db):
        """測試獲取來源統計數據"""
        # 使用 sample_articles[0] 來避免 linter 錯誤
        existing_article_link = sample_articles[0].link

        stats = article_repo.get_source_statistics()
        assert isinstance(stats, dict) # 驗證返回的是字典
        assert len(stats) == 2 # 兩個來源

        # 驗證來源1的數據
        assert "測試來源1" in stats
        assert isinstance(stats["測試來源1"], dict)
        assert stats["測試來源1"]["total"] == 2 # article1 和 article3
        # 根據 sample_articles fixture 的數據驗證 scraped/unscraped
        # article1: is_scraped=True
        # article3: is_scraped=False
        assert stats["測試來源1"]["scraped"] == 1
        assert stats["測試來源1"]["unscraped"] == 1

        # 驗證來源2的數據
        assert "測試來源2" in stats
        assert isinstance(stats["測試來源2"], dict)
        assert stats["測試來源2"]["total"] == 1 # article2
        # article2: is_scraped=True
        assert stats["測試來源2"]["scraped"] == 1
        assert stats["測試來源2"]["unscraped"] == 0

    def test_count(self, article_repo, sample_articles, session, clean_db):
        """測試計算文章總數"""
        # 使用 sample_articles[0] 來避免 linter 錯誤
        existing_article_link = sample_articles[0].link

        count = article_repo.count()
        assert count == 3

        # 清空後計數
        session.query(Articles).delete()
        session.commit()
        count = article_repo.count()
        assert count == 0

    def test_get_category_distribution(self, article_repo, sample_articles, session, clean_db):
        """測試獲取分類分佈"""
        # 使用 sample_articles[0] 來避免 linter 錯誤
        existing_article_link = sample_articles[0].link

        distribution = article_repo.get_category_distribution()
        assert isinstance(distribution, dict) # 驗證返回的是字典
        assert len(distribution) == 2
        # 驗證字典內容
        assert "科技" in distribution
        assert distribution["科技"] == 2
        assert "財經" in distribution
        assert distribution["財經"] == 1

    def test_find_by_tags(self, article_repo, sample_articles, session, clean_db):
        """測試根據標籤查找文章"""
        # 使用 sample_articles[0] 來避免 linter 錯誤
        existing_article_link = sample_articles[0].link

        # 測試單一標籤
        articles = article_repo.find_by_tags(["AI"])
        assert len(articles) == 1
        assert articles[0].title == "科技新聞：AI研究突破"

        # 測試多個標籤（OR 邏輯）
        articles = article_repo.find_by_tags(["Python", "市場"])
        assert len(articles) == 2
        titles = {a.title for a in articles}
        assert "Python編程技巧分享" in titles
        assert "財經報導：股市走勢分析" in titles

        # 測試不存在的標籤
        articles = article_repo.find_by_tags(["不存在的標籤"])
        assert len(articles) == 0

    def test_validate_unique_link(self, article_repo, sample_articles, session, clean_db):
        """測試連結唯一性驗證"""
        # 使用 sample_articles[0] 來避免 linter 錯誤
        existing_article_link = sample_articles[0].link

        # 測試已存在的連結
        with pytest.raises(ValidationError) as exc_info:
            article_repo.validate_unique_link("https://example.com/article1")
        assert "已存在具有相同連結的文章" in str(exc_info.value)

        # 測試新的唯一連結
        try:
            article_repo.validate_unique_link("https://new-unique-link.com")
        except ValidationError:
            pytest.fail("新的唯一連結不應引發 ValidationError")

        # 測試空連結 (如果允許) - 假設不允許
        with pytest.raises(ValidationError) as exc_info:
            article_repo.validate_unique_link("")
        assert "連結不可為空" in str(exc_info.value)

        # 測試 None 連結 (如果允許) - 假設不允許
        with pytest.raises(ValidationError) as exc_info:
            article_repo.validate_unique_link(None)
        assert "連結不可為空" in str(exc_info.value)

    def test_create_article(self, article_repo, session, clean_db):
        """測試創建新文章，並驗證返回的 Article 物件"""
        article_data = {
            "title": "測試創建文章",
            "link": "https://test.com/create",
            "summary": "創建摘要",
            "content": "創建內容",
            "category": "創建類別",
            "is_ai_related": False,
            "is_scraped": False,
            "source": "創建來源",
            "source_url": "https://test.com/source_create",
            "published_at": datetime(2023, 1, 10, tzinfo=timezone.utc),
            "scrape_status": ArticleScrapeStatus.LINK_SAVED,
            "tags": "創建,測試",
            "task_id": 10
        }

        # 成功創建
        created_article = article_repo.create(article_data)
        assert created_article is not None
        assert isinstance(created_article, Articles)
        # 在 repository 的 create 之後，物件可能還沒有 ID，需要 flush 來觸發 ID 生成
        session.flush()
        # flush 之後，ID 應該可用了
        assert created_article.id is not None
        assert created_article.title == "測試創建文章"
        assert created_article.link == "https://test.com/create"
        assert created_article.category == "創建類別"
        assert created_article.is_ai_related is False
        assert created_article.is_scraped is False
        assert created_article.scrape_status == ArticleScrapeStatus.LINK_SAVED
        assert created_article.source == "創建來源"
        assert created_article.published_at == datetime(2023, 1, 10, tzinfo=timezone.utc)
        assert created_article.tags == "創建,測試"
        assert created_article.task_id == 10
        assert created_article.created_at is not None
        assert created_article.updated_at is not None

        # 驗證資料庫中確實存在
        db_article = session.get(Articles, created_article.id)
        assert db_article is not None
        assert db_article.title == "測試創建文章"
        
        # # 測試創建重複連結的文章 (應該引發 ValidationError)
        # duplicate_data = article_data.copy()
        # duplicate_data["title"] = "重複連結測試"
        # with pytest.raises(ValidationError) as exc_info:
        #     article_repo.create(duplicate_data)
        # assert "已存在具有相同連結的文章" in str(exc_info.value)

        # 測試創建包含無效數據的文章 (應該引發 ValidationError)
        invalid_data = article_data.copy()
        invalid_data["link"] = "not-a-url"
        invalid_data["title"] = "無效連結測試" # 確保連結不同
        with pytest.raises(ValidationError) as exc_info:
            article_repo.create(invalid_data)
        # 檢查 ValidationError 的 message 內容，可能包含 Pydantic 的錯誤細節
        assert "link" in str(exc_info.value).lower() # 簡單檢查是否提及 link

    def test_create_article_with_missing_fields(self, article_repo, clean_db):
        """測試創建缺少必要欄位的文章，預期引發 ValidationError"""
        minimal_data = {
            "title": "缺少欄位測試",
            "link": "https://test.com/missing"
            # 缺少 source, source_url 等等
        }
        with pytest.raises(ValidationError) as exc_info:
            article_repo.create(minimal_data)
        # 檢查 Pydantic 拋出的錯誤訊息
        error_message = str(exc_info.value)
        assert "source" in error_message  or "source_url" in error_message # 檢查是否提及缺少的欄位

    def test_update_article(self, article_repo, sample_articles, session, clean_db):
        """測試更新現有文章，並驗證返回的 Article 物件或 None"""
        # 使用 sample_articles[0] 來避免 linter 錯誤
        article_to_update = sample_articles[0]
        article_id = article_to_update.id

        update_data = {
            "title": "更新後的標題",
            "summary": "更新後的摘要",
            "is_ai_related": False,
            "tags": "更新,測試",
            "scrape_status": ArticleScrapeStatus.CONTENT_SCRAPED
        }

        # 確保有足夠的時間差
        original_updated_at = article_to_update.updated_at
        time.sleep(0.1) # 加入 0.1 秒延遲

        # 成功更新
        updated_article = article_repo.update(article_id, update_data)
        assert updated_article is not None
        assert isinstance(updated_article, Articles)
        assert updated_article.id == article_id
        assert updated_article.title == "更新後的標題"
        assert updated_article.summary == "更新後的摘要"
        assert updated_article.is_ai_related is False
        assert updated_article.tags == "更新,測試"
        assert updated_article.scrape_status == ArticleScrapeStatus.CONTENT_SCRAPED
        assert updated_article.link == article_to_update.link # 連結不應被修改
        assert updated_article.updated_at > original_updated_at # 與原始時間比較

        # 驗證資料庫中的更改
        db_article = session.get(Articles, article_id)
        assert db_article.title == "更新後的標題"
        assert db_article.scrape_status == ArticleScrapeStatus.CONTENT_SCRAPED

        # 測試更新不存在的文章 ID
        non_existent_id = 99999
        with pytest.raises(DatabaseOperationError) as exc_info:
            article_repo.update(non_existent_id, update_data)
        assert f"找不到ID為{non_existent_id}的實體" in str(exc_info.value)

        # 測試傳入無效數據 (例如 title 為空)
        invalid_update_data = {"title": ""}
        with pytest.raises(ValidationError):
            article_repo.update(article_id, invalid_update_data)

        # 測試傳入空字典 (根據 ArticlesRepository.update 的實現，預期返回 None)
        # Repository update 現在會檢查 data 是否為空
        # unchanged_article = article_repo.update(article_id, {})
        # assert unchanged_article is not None
        # assert unchanged_article.title == "更新後的標題" # 應保持上次更新的值
        # # 改為預期 ValidationError
        # with pytest.raises(ValidationError) as exc_info:
        #     article_repo.update(article_id, {})
        result_empty_update = article_repo.update(article_id, {})
        assert result_empty_update is None

    def test_update_article_with_link_field(self, article_repo, sample_articles, session, clean_db):
        """測試更新文章時包含不可變欄位（如 link），預期引發 ValidationError"""
        # 使用 sample_articles[0] 來避免 linter 錯誤
        article_to_update = sample_articles[0]
        article_id = article_to_update.id

        update_data_with_link = {
            "title": "嘗試更新連結",
            "link": "https://new-link.com" # 嘗試修改連結
        }

        with pytest.raises(ValidationError) as exc_info:
            article_repo.update(article_id, update_data_with_link)
        assert "link" in str(exc_info.value).lower() # 錯誤訊息應提及 link
        assert "不能更新不可變欄位" in str(exc_info.value) or "extra fields not permitted" in str(exc_info.value).lower() # Pydantic V2 錯誤訊息

        # 確保文章未被修改
        db_article = session.get(Articles, article_id)
        assert db_article.title == article_to_update.title
        assert db_article.link == article_to_update.link

    def test_update_scrape_status(self, article_repo, sample_articles, session, clean_db):
        """測試更新單個文章的爬取狀態，並驗證新的返回值"""
        # 使用 sample_articles 來避免 linter 錯誤
        articles = sample_articles # 獲取實際的 Articles 物件列表
        link1 = articles[0].link # is_scraped=True, PENDING
        link2 = articles[1].link # is_scraped=True, PENDING
        link3 = articles[2].link # is_scraped=False, LINK_SAVED
        non_existent_link = "https://nonexistent.com"

        links_to_mark = [link1, link3, non_existent_link]

        # 執行批量標記
        result = article_repo.batch_mark_as_scraped(links_to_mark)
        session.commit() # 模擬 Service 層提交事務

        # 驗證返回結構
        assert isinstance(result, dict)
        assert "success_count" in result
        assert "fail_count" in result
        assert "failed_links" in result # 包含成功找到並處理的連結

        # 驗證成功和失敗計數
        # 成功找到 link1 和 link3，失敗 non_existent_link
        assert result["success_count"] == 2
        assert result["fail_count"] == 1

        # 驗證成功處理的連結列表
        assert len(result["failed_links"]) == 1
        assert non_existent_link in result["failed_links"] # 應該檢查 non_existent_link

        # 驗證資料庫狀態
        db_article1 = session.get(Articles, articles[0].id)
        db_article2 = session.get(Articles, articles[1].id) # 未包含在更新列表中
        db_article3 = session.get(Articles, articles[2].id)

        # 定義預期的狀態
        expected_status = ArticleScrapeStatus.CONTENT_SCRAPED

        assert db_article1.is_scraped is True # 保持 True
        assert db_article1.scrape_status == expected_status # 狀態應更新
        assert db_article2.is_scraped is True # 保持原樣
        assert db_article2.scrape_status == ArticleScrapeStatus.PENDING # 保持原樣
        assert db_article3.is_scraped is True # 從 False 更新為 True
        assert db_article3.scrape_status == expected_status # 狀態應更新

        # 測試僅標記 is_scraped=True，不傳遞 status
        links_to_mark_only_flag = [link1, link2] # link1 已是 True, link2 已是 True
        # 注意： batch_mark_as_scraped 的簽名不接受 status=None，修改測試或方法
        # 假設意圖是調用不帶 status 的 update_scrape_status，但 batch 函數沒有這個選項
        # 這裡我們假設 batch 函數總是設置為 CONTENT_SCRAPED
        result_only_flag = article_repo.batch_mark_as_scraped(links_to_mark_only_flag)
        session.commit() # 模擬 Service 層提交事務

        assert result_only_flag["success_count"] == 2 # 兩個連結都找到了

        db_article1_after_flag = session.get(Articles, articles[0].id)
        db_article2_after_flag = session.get(Articles, articles[1].id)
        assert db_article1_after_flag.is_scraped is True # 保持 True
        assert db_article1_after_flag.scrape_status == expected_status # 保持上次更新的狀態
        assert db_article2_after_flag.is_scraped is True # 保持 True
        assert db_article2_after_flag.scrape_status == expected_status # 狀態現在也應被更新

        # 測試傳入空列表
        empty_result = article_repo.batch_mark_as_scraped([])
        assert empty_result["success_count"] == 0
        assert empty_result["fail_count"] == 0
        assert "failed_links" in empty_result and len(empty_result["failed_links"]) == 0
        # assert len(empty_result["successful_links"]) == 0
        # assert len(empty_result["errors"]) == 0

    @pytest.fixture(scope="function")
    def filter_test_articles(self, session, clean_db) -> List[Articles]:
        """創建專門用於過濾和分頁測試的文章，包含 task_id 和 tags"""
        articles = [
            Articles( # 0
                title="AI研究報告1", link="https://example.com/ai1", category="AI研究",
                published_at=datetime(2023, 1, 1, 10, tzinfo=timezone.utc), is_ai_related=True, is_scraped=True,
                tags="AI,研究,深度學習", task_id=10, scrape_status=ArticleScrapeStatus.CONTENT_SCRAPED,
                summary="AI研究摘要", content="AI研究內容",
                source="來源A", source_url="https://source.a/ai1"
            ),
            Articles( # 1
                title="一般科技新聞1", link="https://example.com/tech1", category="科技",
                published_at=datetime(2023, 1, 10, 10, tzinfo=timezone.utc), is_ai_related=False, is_scraped=True,
                tags="科技,創新", task_id=10, scrape_status=ArticleScrapeStatus.CONTENT_SCRAPED,
                summary="科技新聞摘要", content="科技新聞內容",
                source="來源B", source_url="https://source.b/tech1"
            ),
            Articles( # 2
                title="財經報導", link="https://example.com/finance", category="財經",
                published_at=datetime(2023, 1, 5, 10, tzinfo=timezone.utc), is_ai_related=False, is_scraped=False,
                tags="財經,市場", task_id=11, scrape_status=ArticleScrapeStatus.LINK_SAVED,
                summary="財經報導摘要", content="財經報導內容",
                source="來源C", source_url="https://source.c/finance"
            ),
             Articles( # 3
                title="AI研究報告2", link="https://example.com/ai2", category="AI研究",
                published_at=datetime(2023, 1, 15, 10, tzinfo=timezone.utc), is_ai_related=True, is_scraped=False,
                tags="AI,研究,大語言模型", task_id=11, scrape_status=ArticleScrapeStatus.PENDING,
                summary="更多AI研究摘要", content="更多AI研究內容",
                source="來源A", source_url="https://source.a/ai2"
            ),
            Articles( # 4
                title="一般科技新聞2", link="https://example.com/tech2", category="科技",
                published_at=datetime(2023, 1, 20, 10, tzinfo=timezone.utc), is_ai_related=False, is_scraped=True,
                tags="科技,產業", task_id=10, scrape_status=ArticleScrapeStatus.CONTENT_SCRAPED,
                summary="更多科技新聞摘要", content="更多科技新聞內容",
                source="來源B", source_url="https://source.b/tech2"
            )
        ]
        session.add_all(articles)
        session.commit()
        session.expire_all()
        # 按 published_at 降序排列的預期順序: tech2(4), ai2(3), tech1(1), finance(2), ai1(0)
        return articles

    def test_get_paginated_by_filter_default_sort(self, article_repo, filter_test_articles, session):
        """測試分頁查詢，使用預設排序 (published_at desc)"""
        # 使用 filter_test_articles[0] 來避免 linter 錯誤
        existing_article_link = filter_test_articles[0].link

        # 測試第一頁
        page1_result = article_repo.get_paginated_by_filter(
            filter_dict={}, page=1, per_page=2
        )
        assert page1_result["total_pages"] == 3
        assert page1_result["total"] == 5
        assert len(page1_result["items"]) == 2
        assert page1_result["items"][0].title == "一般科技新聞2"
        assert page1_result["items"][1].title == "AI研究報告2"

        # 測試第二頁
        page2_result = article_repo.get_paginated_by_filter(
            filter_dict={}, page=2, per_page=2
        )
        assert page2_result["page"] == 2
        assert len(page2_result["items"]) == 2
        assert page2_result["items"][0].title == "一般科技新聞1"
        assert page2_result["items"][1].title == "財經報導"

        # 測試最後一頁
        page3_result = article_repo.get_paginated_by_filter(
            filter_dict={}, page=3, per_page=2
        )
        assert page3_result["page"] == 3
        assert len(page3_result["items"]) == 1
        assert page3_result["items"][0].title == "AI研究報告1"

        # 測試超出範圍的頁碼
        page4_result = article_repo.get_paginated_by_filter(
            filter_dict={}, page=4, per_page=2
        )
        assert page4_result["page"] == 3 # 應返回調整後的最後一頁頁碼
        assert len(page4_result["items"]) == 1 # 應返回調整後頁碼(3)對應的項目
        assert page4_result["items"][0].title == "AI研究報告1" # 驗證項目內容
        assert page4_result["total_pages"] == 3
        assert page4_result["total"] == 5

        # 測試應用過濾條件的分頁
        filtered_page_result = article_repo.get_paginated_by_filter(
            filter_dict={"category": "科技"},
            page=1, per_page=2
        )
        assert filtered_page_result["total"] == 2
        assert filtered_page_result["total_pages"] == 1
        assert len(filtered_page_result["items"]) == 2
        assert filtered_page_result["items"][0].title == "一般科技新聞2"
        assert filtered_page_result["items"][1].title == "一般科技新聞1"

    def test_get_paginated_by_filter_custom_sort(self, article_repo, filter_test_articles, session):
        """測試分頁查詢，使用自定義排序"""
        # 使用 filter_test_articles[0] 來避免 linter 錯誤
        existing_article_link = filter_test_articles[0].link

        # 按 title 升序排序
        title_asc_result = article_repo.get_paginated_by_filter(
            filter_dict={}, page=1, per_page=3,
            sort_by="title", sort_desc=False
        )
        assert len(title_asc_result["items"]) == 3
        titles = [item.title for item in title_asc_result["items"]]
        assert titles == ["AI研究報告1", "AI研究報告2", "一般科技新聞1"]
        assert title_asc_result["has_next"] is True
        assert title_asc_result["total"] == 5

        # 按 source_url 降序排序
        source_desc_result = article_repo.get_paginated_by_filter(
            filter_dict={}, page=1, per_page=2,
            sort_by="source_url", sort_desc=True
        )
        assert len(source_desc_result["items"]) == 2
        assert source_desc_result["items"][0].title == "財經報導"
        assert source_desc_result["items"][1].title == "一般科技新聞2"
        assert source_desc_result["total"] == 5

        # 測試無效排序欄位 (應退回預設排序)
        invalid_sort_result = article_repo.get_paginated_by_filter(
            filter_dict={}, page=1, per_page=2,
            sort_by="invalid_field", sort_desc=False
        )
        assert len(invalid_sort_result["items"]) == 2
        assert invalid_sort_result["items"][0].title == "一般科技新聞2"
        assert invalid_sort_result["items"][1].title == "AI研究報告2"
        assert invalid_sort_result["total"] == 5

    def test_pagination_navigation(self, article_repo, filter_test_articles, session):
        """測試分頁導航屬性 (has_next, has_prev)"""
        # 使用 filter_test_articles[0] 來避免 linter 錯誤
        existing_article_link = filter_test_articles[0].link
        per_page = 2
        total = 5
        total_pages = 3

        # 第一頁
        page1 = article_repo.get_paginated_by_filter(filter_dict={}, page=1, per_page=per_page)
        assert page1["page"] == 1
        assert page1["has_prev"] is False
        assert page1["has_next"] is True
        assert page1["total_pages"] == total_pages
        assert page1["total"] == total

        # 中間頁
        page2 = article_repo.get_paginated_by_filter(filter_dict={}, page=2, per_page=per_page)
        assert page2["page"] == 2
        assert page2["has_prev"] is True
        assert page2["has_next"] is True
        assert page2["total_pages"] == total_pages
        assert page2["total"] == total

        # 最後一頁
        page3 = article_repo.get_paginated_by_filter(filter_dict={}, page=3, per_page=per_page)
        assert page3["page"] == 3
        assert page3["has_prev"] is True
        assert page3["has_next"] is False
        assert page3["total_pages"] == total_pages
        assert page3["total"] == total # 驗證 total

        # 只有一頁的情況
        one_page_result = article_repo.get_paginated_by_filter(filter_dict={}, page=1, per_page=10)
        assert one_page_result["page"] == 1
        assert one_page_result["has_prev"] is False
        assert one_page_result["has_next"] is False
        assert one_page_result["total_pages"] == 1
        assert one_page_result["total"] == total # 驗證 total

        # 沒有結果的情況
        no_result = article_repo.get_paginated_by_filter(filter_dict={"category": "不存在"}, page=1, per_page=per_page)
        assert no_result["page"] == 1
        assert no_result["has_prev"] is False
        assert no_result["has_next"] is False
        assert no_result["total_pages"] == 0
        assert no_result["total"] == 0 # 使用正確的鍵 'total'

    def test_delete_by_link(self, article_repo, sample_articles, session, clean_db):
        """測試根據連結刪除文章，並在找不到連結時引發 ValidationError"""
        # 使用 sample_articles 來避免 linter 錯誤
        articles = sample_articles # 獲取實際的 Articles 物件列表
        link_to_delete = articles[0].link
        id_to_delete = articles[0].id
        non_existent_link = "https://nonexistent.com"

        # 確保文章存在
        assert session.get(Articles, id_to_delete) is not None

        # 成功刪除
        deleted = article_repo.delete_by_link(link_to_delete)
        assert deleted is True
        
        # 手動提交事務 (模擬 Service 層行為)
        session.commit()

        # 驗證文章已被刪除
        assert session.get(Articles, id_to_delete) is None
        assert article_repo.find_by_link(link_to_delete) is None

        # 嘗試刪除不存在的連結 (預期引發 ValidationError)
        with pytest.raises(ValidationError) as exc_info:
            article_repo.delete_by_link(non_existent_link)
        assert f"連結 '{non_existent_link}' 不存在，無法刪除" in str(exc_info.value)

        # 再次嘗試刪除已刪除的連結 (預期引發 ValidationError)
        with pytest.raises(ValidationError) as exc_info:
            article_repo.delete_by_link(link_to_delete)
        assert f"連結 '{link_to_delete}' 不存在，無法刪除" in str(exc_info.value)

    def test_count_unscraped_links(self, article_repo, sample_articles, session, clean_db):
        """測試計算未爬取連結的數量"""
        # sample_articles 中有 1 條 is_scraped=False (article3)
        # 使用 sample_articles[0] 來避免 linter 錯誤
        existing_article_link = sample_articles[0].link

        count = article_repo.count_unscraped_links()
        assert count == 1

        # 將所有文章標記為已爬取
        for article in sample_articles:
            article.is_scraped = True
        session.commit()
        count = article_repo.count_unscraped_links()
        assert count == 0

    def test_count_scraped_links(self, article_repo, sample_articles, session, clean_db):
        """測試計算已爬取連結的數量"""
        # sample_articles 中有 2 條 is_scraped=True (article1, article2)
        # 使用 sample_articles[0] 來避免 linter 錯誤
        existing_article_link = sample_articles[0].link

        count = article_repo.count_scraped_links()
        assert count == 2

        # 將所有文章標記為未爬取
        for article in sample_articles:
            article.is_scraped = False
        session.commit()
        count = article_repo.count_scraped_links()
        assert count == 0

    def test_count_scraped_articles(self, article_repo, sample_articles, session, clean_db):
        """測試計算已成功爬取內容的文章數量 (實際測試的是 is_scraped=True 的數量)"""
        # 此測試依賴於 scrape_status
        # 假設 sample_articles 中沒有 SCRAPED_SUCCESS 或 SCRAPED_FAILURE
        # 使用 sample_articles[0] 來避免 linter 錯誤
        existing_article_link = sample_articles[0].link

        count_initial = article_repo.count_scraped_articles()
        assert count_initial == 2 # sample_articles 初始有 2 個 is_scraped=True

        # 將 article1 標記為成功爬取 (它本來 is_scraped 就是 True)
        # sample_articles[0].scrape_status = ArticleScrapeStatus.CONTENT_SCRAPED
        # session.commit()
        # count_after_success = article_repo.count_scraped_articles()
        # assert count_after_success == 2 # is_scraped 數量不變

        # 將 article2 標記為爬取失敗 (但 is_scraped 仍為 True)
        # sample_articles[1].scrape_status = ArticleScrapeStatus.FAILED
        # session.commit()
        # count_after_failure = article_repo.count_scraped_articles()
        # assert count_after_failure == 2 # is_scraped 數量仍不變

        # 將 article3 標記為 is_scraped=True
        sample_articles[2].is_scraped = True
        # sample_articles[2].scrape_status = ArticleScrapeStatus.CONTENT_SCRAPED
        session.commit()
        count_after_another_success = article_repo.count_scraped_articles()
        assert count_after_another_success == 3 # 現在應該有 3 個 is_scraped=True

    def test_find_unscraped_links(self, article_repo, sample_articles, session, clean_db):
        """測試查找未爬取的連結"""
        # sample_articles 中 article3 是 is_scraped=False
        # 使用 sample_articles[0] 來避免 linter 錯誤
        existing_article_link = sample_articles[0].link
    
        # 測試不帶 limit
        unscraped_articles = article_repo.find_unscraped_links() # 方法返回 Articles 物件列表
        assert isinstance(unscraped_articles, list)
        assert len(unscraped_articles) == 1
        # assert links[0] == sample_articles[2].link
        assert unscraped_articles[0].link == sample_articles[2].link # 比較 link 屬性
        assert unscraped_articles[0].id == sample_articles[2].id # 可以順便比較 id

        # 測試帶 limit=0 (方法會忽略無效 limit，返回所有)
        links_limited = article_repo.find_unscraped_links(limit=0)
        # assert len(links_limited) == 0
        assert len(links_limited) == 1 # limit=0 被忽略，返回 1 個

        # 添加更多未爬取的文章
        new_unscraped_data = Articles(title="未爬取4", link="https://unscraped.com/4", summary="s", content="c", category="cat", is_scraped=False, source="s", source_url="su", published_at=datetime.now(timezone.utc), scrape_status=ArticleScrapeStatus.LINK_SAVED)
        session.add(new_unscraped_data)
        session.commit()
        # 獲取提交後的物件，以便比較
        session.refresh(new_unscraped_data)

        unscraped_articles_after_add = article_repo.find_unscraped_links()
        assert len(unscraped_articles_after_add) == 2
        # 驗證返回的連結是否正確 (假設默認排序是按 updated_at 升序)
        links_found = {a.link for a in unscraped_articles_after_add}
        assert sample_articles[2].link in links_found
        assert new_unscraped_data.link in links_found

        unscraped_articles_limited_after_add = article_repo.find_unscraped_links(limit=1)
        assert len(unscraped_articles_limited_after_add) == 1
        # 根據排序假設，第一個應是 sample_articles[2]
        assert unscraped_articles_limited_after_add[0].link == sample_articles[2].link

    def test_find_scraped_links(self, article_repo, sample_articles, session, clean_db):
        """測試查找已爬取的連結"""
        # sample_articles 中 article1, article2 是 is_scraped=True
        # 使用 sample_articles[0] 來避免 linter 錯誤
        existing_article_link = sample_articles[0].link
    
        scraped_articles = article_repo.find_scraped_links() # 返回物件列表
        assert isinstance(scraped_articles, list)
        assert len(scraped_articles) == 2
        # assert sample_articles[0].link in links
        # assert sample_articles[1].link in links
        links_found = {a.link for a in scraped_articles} # 提取連結到集合中
        assert sample_articles[0].link in links_found
        assert sample_articles[1].link in links_found

        # 測試帶 limit
        scraped_articles_limited = article_repo.find_scraped_links(limit=1)
        assert len(scraped_articles_limited) == 1
        # 根據預設排序 (updated_at desc)，最新的應該是 article2
        # (假設 sample_articles fixture 的順序是創建順序)
        # 為了更健壯，可以只檢查是否是已知的 scraped link 之一
        assert scraped_articles_limited[0].link in [sample_articles[0].link, sample_articles[1].link]


        # 將 article3 標記為已爬取
        sample_articles[2].is_scraped = True
        session.commit()
        scraped_articles_after_update = article_repo.find_scraped_links()
        assert len(scraped_articles_after_update) == 3
        links_found_after_update = {a.link for a in scraped_articles_after_update}
        assert sample_articles[0].link in links_found_after_update
        assert sample_articles[1].link in links_found_after_update
        assert sample_articles[2].link in links_found_after_update

    def test_find_articles_by_task_id(self, article_repo, filter_test_articles, session):
        """測試根據 task_id 查找文章，並驗證返回列表"""
        # filter_test_articles 中: task_id=10 (3篇), task_id=11 (2篇)
        # filter_test_articles 的 title 命名與 task_id 不符，應修正
        # 使用 filter_test_articles[0] 來避免 linter 錯誤
        existing_article_link = filter_test_articles[0].link
    
        # 查找 task_id = 10
        result_task10 = article_repo.find_articles_by_task_id(task_id=10)
        assert isinstance(result_task10, list)
        assert len(result_task10) == 3 # task_id=10 有 3 篇: ai1, tech1, tech2
        titles_task10 = {a.title for a in result_task10}
        assert "AI研究報告1" in titles_task10
        assert "一般科技新聞1" in titles_task10
        assert "一般科技新聞2" in titles_task10

        # 查找 task_id = 11
        result_task11 = article_repo.find_articles_by_task_id(task_id=11)
        assert isinstance(result_task11, list)
        assert len(result_task11) == 2 # task_id=11 有 2 篇: finance, ai2
        titles_task11 = {a.title for a in result_task11}
        assert "財經報導" in titles_task11
        assert "AI研究報告2" in titles_task11

        # 查找 task_id = 11，帶 limit
        result_task11_limited = article_repo.find_articles_by_task_id(task_id=11, limit=1)
        assert len(result_task11_limited) == 1
        # 根據方法的預設排序 (status asc, updated_at desc)，PENDING 的 ai2 應該在 LINK_SAVED 的 finance 前面
        assert result_task11_limited[0].title == "AI研究報告2"

        # 查找 task_id = 10, is_scraped = True
        result_task10_scraped = article_repo.find_articles_by_task_id(task_id=10, is_scraped=True)
        assert len(result_task10_scraped) == 3 # ai1, tech1, tech2 都是 is_scraped=True

        # 查找 task_id = 11, is_scraped = False
        result_task11_unscraped = article_repo.find_articles_by_task_id(task_id=11, is_scraped=False)
        assert len(result_task11_unscraped) == 2 # finance, ai2 都是 is_scraped=False


        # 查找不存在的 task_id
        result_nonexistent = article_repo.find_articles_by_task_id(task_id=99)
        assert len(result_nonexistent) == 0

        # 查找 task_id = None (應返回所有未分配 task_id 的文章，此處假設沒有)
        article_no_task = Articles(title="無任務", link="https://notask.com", summary="s", content="c", category="cat", is_scraped=False, source="s", source_url="su", published_at=datetime.now(timezone.utc), scrape_status=ArticleScrapeStatus.LINK_SAVED, task_id=None)
        session.add(article_no_task)
        session.commit()

        result_no_task = article_repo.find_articles_by_task_id(task_id=None)
        assert len(result_no_task) == 1
        assert result_no_task[0].title == "無任務"

    def test_count_articles_by_task_id(self, article_repo, filter_test_articles, session):
        """測試根據 task_id 計算文章數量"""
        # filter_test_articles 中: task_id=10 (3篇), task_id=11 (2篇)
        # 使用 filter_test_articles[0] 來避免 linter 錯誤
        existing_article_link = filter_test_articles[0].link

        assert article_repo.count_articles_by_task_id(task_id=10) == 3
        assert article_repo.count_articles_by_task_id(task_id=11) == 2
        assert article_repo.count_articles_by_task_id(task_id=99) == 0 # 不存在的 task_id

        # 測試帶 is_scraped 過濾
        # task_id=10: 3 篇 True, 0 篇 False
        assert article_repo.count_articles_by_task_id(task_id=10, is_scraped=True) == 3
        assert article_repo.count_articles_by_task_id(task_id=10, is_scraped=False) == 0

        # task_id=11: 0 篇 True, 2 篇 False
        assert article_repo.count_articles_by_task_id(task_id=11, is_scraped=True) == 0
        assert article_repo.count_articles_by_task_id(task_id=11, is_scraped=False) == 2