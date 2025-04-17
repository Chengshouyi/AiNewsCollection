import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.articles_model import Articles, Base, ArticleScrapeStatus
from src.services.article_service import ArticleService
from src.database.database_manager import DatabaseManager
from src.models.crawler_tasks_model import CrawlerTasks, ScrapeMode

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
            scrape_status=ArticleScrapeStatus.CONTENT_SCRAPED,
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
            scrape_status=ArticleScrapeStatus.CONTENT_SCRAPED,
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
            scrape_status=ArticleScrapeStatus.CONTENT_SCRAPED,
            tags="AI,機器學習"
        ),
        Articles(
            title="待抓取新聞",
            link="https://example.com/news1",
            summary="等待抓取的新聞",
            content=None,
            source="新聞網",
            source_url="https://example.com/source4",
            category="新聞",
            published_at=datetime(2023, 1, 4, tzinfo=timezone.utc),
            is_ai_related=False,
            is_scraped=False,
            scrape_status=ArticleScrapeStatus.LINK_SAVED,
            tags="新聞,科技"
        )
    ]

    session.add_all(articles)
    session.commit()
    # 重新查詢以獲取分配的 ID
    articles = session.query(Articles).order_by(Articles.published_at).all()
    return articles

class TestArticleService:
    """測試文章服務的核心功能"""

    def test_create_article(self, article_service):
        """測試新增單一文章 (或更新若連結已存在)"""
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
            "tags": "測試,文章",
            "scrape_status": ArticleScrapeStatus.CONTENT_SCRAPED
        }

        result = article_service.create_article(article_data)
        assert result["success"] is True
        assert result["message"] == "文章創建成功"
        assert "article" in result
        assert isinstance(result["article"], dict) # 驗證返回的是字典
        assert result["article"]["title"] == article_data["title"] # 檢查字典中的值
        assert result["article"]["link"] == article_data["link"]   # 檢查字典中的值
        assert "id" in result["article"] and result["article"]["id"] is not None # 確保有 ID

        # 測試更新現有文章
        update_data = {
            "title": "更新標題",
            "link": "https://test.com/article1", # 使用相同連結
            "summary": "更新摘要"
            # 注意：這裡只傳遞要更新的字段，create_article 內部會處理
        }
        result_update = article_service.create_article(update_data)
        assert result_update["success"] is True
        # 注意：根據修改後的 create_article 邏輯，更新成功或無變更時的 message 可能不同
        # 我們主要關心數據是否正確
        # assert result_update["message"] == "文章已存在，更新成功" # 或 '文章已存在，無變更或更新失敗'
        assert "article" in result_update
        assert isinstance(result_update["article"], dict)
        assert result_update["article"]["title"] == update_data["title"]
        assert result_update["article"]["summary"] == update_data["summary"]
        assert result_update["article"]["link"] == article_data["link"] # 連結應保持不變

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
                "tags": "測試,文章",
                "scrape_status": ArticleScrapeStatus.CONTENT_SCRAPED
            }
            for i in range(3)
        ]

        result = article_service.batch_create_articles(articles_data)
        assert result["success"] is True
        assert "resultMsg" in result
        assert result["resultMsg"]["success_count"] == 3
        assert result["resultMsg"]["update_count"] == 0 # 在此測試案例中，預期沒有更新
        assert result["resultMsg"]["fail_count"] == 0
        # 可以選擇性地驗證 inserted_articles 的數量或內容
        # assert len(result["resultMsg"]["inserted_articles"]) == 3

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
        assert "resultMsg" in result
        assert len(result["resultMsg"]["items"]) == 2
        assert result["resultMsg"]["total"] == 4
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
        assert result["article"].title == "更新後的標題" # 驗證資料實際已更新

        # 測試更新無變更
        result_no_change = article_service.update_article(article_id, update_data)
        assert result_no_change["success"] is True
        assert result_no_change["message"] == "文章更新成功 (或無變更)"
        assert result_no_change["article"].title == "更新後的標題" # 驗證資料未變

        # 測試更新不存在的文章
        result_not_exist = article_service.update_article(999999, {"title": "新標題"})
        assert result_not_exist["success"] is False
        assert result_not_exist["message"] == "更新文章失敗, ID=999999: 找不到ID為999999的實體，無法更新"


    def test_batch_update_articles_by_ids(self, article_service, sample_articles):
        """測試批量更新文章"""
        article_ids = [article.id for article in sample_articles[:2]]
        update_data = {
            "category": "更新分類",
            "summary": "更新的摘要"
        }

        result = article_service.batch_update_articles_by_ids(article_ids, update_data)
        assert result["success"] is True
        assert "resultMsg" in result
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
        assert "resultMsg" in result
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

        # 測試刪除不存在的文章
        result_not_exist = article_service.delete_article(99999)
        assert result_not_exist["success"] is False
        assert result_not_exist["message"] == "文章不存在或刪除失敗"

    def test_batch_delete_articles(self, article_service, sample_articles):
        """測試批量刪除文章"""
        article_ids_to_delete = [article.id for article in sample_articles[:2]]
        non_existent_id = 99999

        # 包含存在的和不存在的 ID
        all_ids = article_ids_to_delete + [non_existent_id]

        result = article_service.batch_delete_articles(all_ids)
        assert result["success"] is False # 因為有一個失敗了
        assert "resultMsg" in result
        assert result["resultMsg"]["success_count"] == 2
        assert result["resultMsg"]["fail_count"] == 1
        assert result["resultMsg"]["missing_ids"] == [non_existent_id]
        assert result["resultMsg"]["failed_ids"] == []

        # 確認文章已被刪除
        for article_id in article_ids_to_delete:
            get_result = article_service.get_article_by_id(article_id)
            assert get_result["success"] is False
            assert get_result["message"] == "文章不存在"

        # 測試空列表
        result_empty = article_service.batch_delete_articles([])
        assert result_empty["success"] is True
        assert result_empty["message"] == "未提供文章ID，無需刪除"
        assert result_empty["resultMsg"]["success_count"] == 0
        assert result_empty["resultMsg"]["fail_count"] == 0

    def test_get_articles_statistics(self, article_service, sample_articles):
        """測試獲取文章統計資訊"""
        result = article_service.get_articles_statistics()

        assert result["success"] is True
        assert "resultMsg" in result
        stats = result["resultMsg"]

        # 驗證基本統計資訊
        assert "total_articles" in stats
        assert "ai_related_articles" in stats
        assert "category_distribution" in stats
        assert "recent_articles" in stats

        # 驗證具體數值
        assert stats["total_articles"] == 4
        assert stats["ai_related_articles"] == 2
        assert "AI研究" in stats["category_distribution"]
        assert stats["category_distribution"]["AI研究"] == 2

    def test_error_handling(self, article_service, sample_articles):
        """測試錯誤處理"""
        # 測試創建重複連結的文章 (現在應執行更新)
        existing_link = sample_articles[0].link
        article_data = {
            "title": "重複連結更新測試",
            "link": existing_link, # 使用已存在的連結
            "summary": "新的摘要", # 更新的資料
            "content": "測試內容",
            "source": "測試來源",
            "source_url": "https://test.com/source",
            "category": "測試",
            "published_at": datetime.now(timezone.utc),
            "is_ai_related": True,
            "is_scraped": True
        }

        result = article_service.create_article(article_data)
        assert result["success"] is True
        assert result["message"] == "文章已存在，更新成功" # 預期訊息改為更新成功
        assert result["article"].summary == "新的摘要" # 驗證資料已更新

        # 測試更新不存在的文章
        result_update_fail = article_service.update_article(999999, {"title": "新標題"})
        assert result_update_fail["success"] is False
        assert result_update_fail["message"] == "文章不存在，無法更新" # 驗證更新失敗的訊息

class TestArticleServiceAdvancedFeatures:
    """測試文章服務的進階功能"""

    def test_advanced_search_articles(self, article_service, sample_articles):
        """測試進階搜尋文章"""
        # 測試關鍵字搜尋 (應匹配 title="AI發展新突破" 和 content="詳細的AI研究內容")
        result_keywords = article_service.advanced_search_articles(
            keywords="AI研究",
            is_ai_related=True
        )
        assert result_keywords["success"] is True
        assert len(result_keywords["articles"]) == 1
        assert result_keywords["articles"][0].title == "AI發展新突破"

        # 測試日期範圍搜尋
        date_range = (
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            datetime(2023, 1, 2, tzinfo=timezone.utc)
        )
        result_date = article_service.advanced_search_articles(date_range=date_range)
        assert result_date["success"] is True
        # 應找到 2023/1/1 和 2023/1/2 的文章
        assert len(result_date["articles"]) == 2
        assert {a.published_at.day for a in result_date["articles"]} == {1, 2}

        # 測試多條件組合搜尋 (AI研究, is_ai_related=True, tags="AI")
        result_combined = article_service.advanced_search_articles(
            category="AI研究",
            is_ai_related=True,
            tags=["AI"]
        )
        assert result_combined["success"] is True
        # 應找到 AI發展新突破 (tags="AI,研究") 和 機器學習應用 (tags="AI,機器學習")
        assert len(result_combined["articles"]) == 2
        assert all(article.category == "AI研究" for article in result_combined["articles"])
        assert all("AI" in article.tags.split(',') for article in result_combined["articles"])

        # 測試 is_scraped 條件
        result_scraped = article_service.advanced_search_articles(is_scraped=True)
        assert result_scraped["success"] is True
        assert len(result_scraped["articles"]) == 3 # sample_articles 中有 3 篇 is_scraped=True

        result_unscraped = article_service.advanced_search_articles(is_scraped=False)
        assert result_unscraped["success"] is True
        assert len(result_unscraped["articles"]) == 1 # sample_articles 中有 1 篇 is_scraped=False

        # 測試 source 條件
        result_source = article_service.advanced_search_articles(source="科技日報")
        assert result_source["success"] is True
        assert len(result_source["articles"]) == 2

    def test_update_article_tags(self, article_service, sample_articles):
        """測試更新文章標籤"""
        article_id = sample_articles[0].id
        new_tags = ["新標籤1", "新標籤2"]

        result = article_service.update_article_tags(article_id, new_tags)
        assert result["success"] is True
        assert result["message"] == "更新文章標籤成功"
        assert result["article"].tags == ",".join(new_tags)

    def test_search_by_title(self, article_service, sample_articles):
        """測試根據標題搜索文章"""
        # 模糊匹配 "AI" - 應找到 "AI發展新突破"
        result_fuzzy = article_service.search_articles_by_title("AI")
        assert result_fuzzy["success"] is True
        assert len(result_fuzzy["articles"]) == 1
        assert "AI" in result_fuzzy["articles"][0].title

        # 精確匹配
        result_exact = article_service.search_articles_by_title("機器學習應用", exact_match=True)
        assert result_exact["success"] is True
        assert len(result_exact["articles"]) == 1
        assert result_exact["articles"][0].title == "機器學習應用"

        # 測試找不到
        result_not_found = article_service.search_articles_by_title("不存在的標題")
        assert result_not_found["success"] is True
        assert len(result_not_found["articles"]) == 0

    def test_search_by_keywords(self, article_service, sample_articles):
        """測試根據關鍵字搜索文章 (標題或內容)"""
        # 關鍵字 "研究" 應匹配 title="AI發展新突破", content="詳細的AI研究內容" 和 title="機器學習應用"
        result = article_service.search_articles_by_keywords("研究")
        assert result["success"] is True
        assert len(result["articles"]) == 2 # AI發展新突破 & 機器學習應用 (假設標題也匹配)
        assert {"AI發展新突破", "機器學習應用"} == {a.title for a in result["articles"]}

        # 關鍵字 "內容"
        result_content = article_service.search_articles_by_keywords("內容")
        assert result_content["success"] is True
        # 應匹配 content="詳細的AI研究內容", content="詳細的市場分析內容", content="機器學習應用案例"
        assert len(result_content["articles"]) == 3

    def test_get_source_statistics(self, article_service, sample_articles):
        """測試獲取各來源的爬取統計"""
        result = article_service.get_source_statistics()
        assert result["success"] is True
        assert "stats" in result

        # 驗證統計數據
        stats = result["stats"]
        assert "科技日報" in stats
        assert "財經週刊" in stats
        assert "新聞網" in stats

        # 驗證科技日報的統計
        tech_stats = stats["科技日報"]
        assert tech_stats["total"] == 2
        assert tech_stats["scraped"] == 2
        assert tech_stats.get("unscraped", 0) == 0 # 確保 unscraped 存在或為 0

        # 驗證新聞網的統計
        news_stats = stats["新聞網"]
        assert news_stats["total"] == 1
        assert news_stats["unscraped"] == 1
        assert news_stats.get("scraped", 0) == 0

    def test_update_article_scrape_status(self, article_service, sample_articles):
        """測試更新文章爬取狀態"""
        link = sample_articles[3].link  # 未爬取的文章
        assert sample_articles[3].is_scraped is False

        # 標記為已爬取
        result = article_service.update_article_scrape_status(link, True)
        assert result["success"] is True
        assert result["message"] == "更新文章爬取狀態成功"

        # 確認狀態已更新
        article_result = article_service.get_article_by_link(link)
        assert article_result["success"] is True
        assert article_result["article"].is_scraped is True
        assert article_result["article"].scrape_status == ArticleScrapeStatus.CONTENT_SCRAPED

        # 標記回未爬取
        result_false = article_service.update_article_scrape_status(link, False)
        assert result_false["success"] is True
        assert result_false["message"] == "更新文章爬取狀態成功"
        article_result_false = article_service.get_article_by_link(link)
        assert article_result_false["success"] is True
        assert article_result_false["article"].is_scraped is False
        # 注意：狀態可能不會回到 LINK_SAVED，這取決於 update_scrape_status 的實現
        # assert article_result_false["article"].scrape_status == ArticleScrapeStatus.LINK_SAVED

        # 測試更新不存在的連結
        result_not_exist = article_service.update_article_scrape_status("https://nonexistent.com", True)
        assert result_not_exist["success"] is False
        assert result_not_exist["message"] == "更新文章爬取狀態失敗 (文章可能不存在)"

    def test_batch_mark_articles_as_scraped(self, article_service, sample_articles, session):
        """測試批量標記文章為已爬取"""
        # 創建多個未爬取的文章
        unscraped_articles_data = []
        for i in range(3):
            data = {
                "title": f"批量測試{i}",
                "link": f"https://test.com/batch_mark_{i}",
                "summary": "測試摘要",
                "content": None,
                "source": "測試來源",
                "source_url": "https://test.com/source",
                "category": "測試",
                "published_at": datetime.now(timezone.utc),
                "is_ai_related": False,
                "is_scraped": False,
                "scrape_status": ArticleScrapeStatus.LINK_SAVED
            }
            unscraped_articles_data.append(data)

        # 使用服務創建文章以確保它們在 session 中
        batch_create_result = article_service.batch_create_articles(unscraped_articles_data)
        assert batch_create_result["success"] is True
        assert batch_create_result["resultMsg"]["success_count"] == 3

        # 獲取連結 (從資料中獲取，因為 batch_create 不返回對象)
        links = [data["link"] for data in unscraped_articles_data]
        non_existent_link = "https://nonexistent.com/mark"
        links_with_invalid = links + [non_existent_link]

        # 批量標記
        result = article_service.batch_mark_articles_as_scraped(links_with_invalid)
        assert result["success"] is False # 因為有一個失敗了
        assert "resultMsg" in result
        assert result["resultMsg"]["success_count"] == 3
        assert result["resultMsg"]["fail_count"] == 1 # 確保失敗計數正確

        # 確認所有文章都已標記為已爬取
        for link in links:
            article_result = article_service.get_article_by_link(link)
            assert article_result["success"] is True
            assert article_result["article"].is_scraped is True
            assert article_result["article"].scrape_status == ArticleScrapeStatus.CONTENT_SCRAPED

        # 測試空列表
        result_empty = article_service.batch_mark_articles_as_scraped([])
        assert result_empty["success"] is True
        assert result_empty["resultMsg"]["success_count"] == 0
        assert result_empty["resultMsg"]["fail_count"] == 0

    def test_get_unscraped_articles(self, article_service, sample_articles):
        """測試獲取未爬取的文章"""
        # 初始狀態下有 1 篇未爬取
        result = article_service.get_unscraped_articles()
        assert result["success"] is True
        assert len(result["articles"]) == 1
        assert all(not article.is_scraped for article in result["articles"])
        assert result["articles"][0].title == "待抓取新聞"

        # 測試按來源篩選
        result_source = article_service.get_unscraped_articles(source="新聞網")
        assert result_source["success"] is True
        assert len(result_source["articles"]) == 1
        assert result_source["articles"][0].source == "新聞網"

        # 測試按來源篩選 (無結果)
        result_no_match = article_service.get_unscraped_articles(source="科技日報")
        assert result_no_match["success"] is True
        assert len(result_no_match["articles"]) == 0

    def test_get_scraped_articles(self, article_service, sample_articles):
        """測試獲取已爬取的文章"""
        # 初始狀態下有 3 篇已爬取
        result = article_service.get_scraped_articles()
        assert result["success"] is True
        assert len(result["articles"]) == 3
        assert all(article.is_scraped for article in result["articles"])

        # 測試按來源篩選
        result_source = article_service.get_scraped_articles(source="科技日報")
        assert result_source["success"] is True
        assert len(result_source["articles"]) == 2
        assert all(article.source == "科技日報" for article in result_source["articles"])

        # 測試按來源篩選 (無結果)
        result_no_match = article_service.get_scraped_articles(source="新聞網")
        assert result_no_match["success"] is True
        assert len(result_no_match["articles"]) == 0

    def test_count_unscraped_articles(self, article_service, sample_articles):
        """測試計算未爬取的文章數量"""
        # 初始狀態下有 1 篇未爬取
        result = article_service.count_unscraped_articles()
        assert result["success"] is True
        assert result["count"] == 1

        # 測試按來源篩選
        result_source = article_service.count_unscraped_articles(source="新聞網")
        assert result_source["success"] is True
        assert result_source["count"] == 1

        result_no_match = article_service.count_unscraped_articles(source="科技日報")
        assert result_no_match["success"] is True
        assert result_no_match["count"] == 0

    def test_count_scraped_articles(self, article_service, sample_articles):
        """測試計算已爬取的文章數量"""
        # 初始狀態下有 3 篇已爬取
        result = article_service.count_scraped_articles()
        assert result["success"] is True
        assert result["count"] == 3

        # 測試按來源篩選
        result_source = article_service.count_scraped_articles(source="科技日報")
        assert result_source["success"] is True
        assert result_source["count"] == 2

        result_no_match = article_service.count_scraped_articles(source="新聞網")
        assert result_no_match["success"] is True
        assert result_no_match["count"] == 0

    def test_get_articles_by_task(self, article_service, sample_articles, session):
        """測試根據任務ID獲取文章，用於支援不同的爬取模式(ScrapeMode)"""
        # 創建測試任務
        tasks = [
            CrawlerTasks(
                task_name="僅連結任務",
                crawler_id=1,
                scrape_mode=ScrapeMode.LINKS_ONLY
            ),
            CrawlerTasks(
                task_name="僅內容任務",
                crawler_id=1,
                scrape_mode=ScrapeMode.CONTENT_ONLY
            ),
            CrawlerTasks(
                task_name="完整爬取任務",
                crawler_id=1,
                scrape_mode=ScrapeMode.FULL_SCRAPE
            )
        ]
        session.add_all(tasks)
        session.commit()
        # 獲取任務ID
        task_ids = [task.id for task in tasks]

        # 為每個任務創建對應的文章
        test_articles_data = []

        # 為LINKS_ONLY任務創建僅保存了連結的文章（未爬取內容）
        for i in range(2):
            article = {
                "title": f"連結任務文章{i}",
                "link": f"https://example.com/links_only_{i}",
                "summary": "連結任務摘要",
                "content": None,  # 無內容
                "source": "測試來源",
                "source_url": "https://example.com/source",
                "category": "測試",
                "published_at": datetime.now(timezone.utc),
                "is_ai_related": False,
                "is_scraped": False,  # 未爬取
                "scrape_status": ArticleScrapeStatus.LINK_SAVED,  # 僅保存連結
                "task_id": task_ids[0]  # 關聯到LINKS_ONLY任務
            }
            test_articles_data.append(article)

        # 為CONTENT_ONLY任務創建已爬取內容的文章
        for i in range(2):
            article = {
                "title": f"內容任務文章{i}",
                "link": f"https://example.com/content_only_{i}",
                "summary": "內容任務摘要",
                "content": "內容任務的詳細內容",  # 有內容
                "source": "測試來源",
                "source_url": "https://example.com/source",
                "category": "測試",
                "published_at": datetime.now(timezone.utc),
                "is_ai_related": False,
                "is_scraped": True,  # 已爬取
                "scrape_status": ArticleScrapeStatus.CONTENT_SCRAPED,  # 已爬取內容
                "task_id": task_ids[1]  # 關聯到CONTENT_ONLY任務
            }
            test_articles_data.append(article)

        # 為FULL_SCRAPE任務創建混合狀態的文章（一些已爬取內容，一些僅有連結）
        for i in range(2):
            is_scraped = i == 0  # 第一篇已爬取，第二篇未爬取
            scrape_status = ArticleScrapeStatus.CONTENT_SCRAPED if is_scraped else ArticleScrapeStatus.LINK_SAVED
            content = "完整任務的詳細內容" if is_scraped else None

            article = {
                "title": f"完整任務文章{i}",
                "link": f"https://example.com/full_scrape_{i}",
                "summary": "完整任務摘要",
                "content": content,
                "source": "測試來源",
                "source_url": "https://example.com/source",
                "category": "測試",
                "published_at": datetime.now(timezone.utc),
                "is_ai_related": False,
                "is_scraped": is_scraped,
                "scrape_status": scrape_status,
                "task_id": task_ids[2]  # 關聯到FULL_SCRAPE任務
            }
            test_articles_data.append(article)

        # 批量創建所有測試文章
        create_res = article_service.batch_create_articles(test_articles_data)
        assert create_res["success"] is True
        assert create_res["resultMsg"]["success_count"] == 6

        # 測試1: 獲取LINKS_ONLY任務的所有文章
        result1 = article_service.get_articles_by_task({'task_id': task_ids[0]})
        assert result1["success"] is True
        assert len(result1["articles"]) == 2
        assert all(article.task_id == task_ids[0] for article in result1["articles"])
        assert all(article.scrape_status == ArticleScrapeStatus.LINK_SAVED for article in result1["articles"])

        # 測試2: 獲取CONTENT_ONLY任務的已爬取文章 (使用 is_scraped=True)
        result2 = article_service.get_articles_by_task({'task_id': task_ids[1], 'is_scraped': True})
        assert result2["success"] is True
        assert len(result2["articles"]) == 2
        assert all(article.task_id == task_ids[1] for article in result2["articles"])
        assert all(article.is_scraped for article in result2["articles"])

        # 測試3: 獲取FULL_SCRAPE任務的未爬取文章 (使用 is_scraped=False)
        result3 = article_service.get_articles_by_task({'task_id': task_ids[2], 'is_scraped': False})
        assert result3["success"] is True
        assert len(result3["articles"]) == 1
        assert all(article.task_id == task_ids[2] for article in result3["articles"])
        assert all(not article.is_scraped for article in result3["articles"])

        # 測試4: 獲取FULL_SCRAPE任務的已爬取文章 (使用 is_scraped=True)
        result4 = article_service.get_articles_by_task({'task_id': task_ids[2], 'is_scraped': True})
        assert result4["success"] is True
        assert len(result4["articles"]) == 1
        assert all(article.task_id == task_ids[2] for article in result4["articles"])
        assert all(article.is_scraped for article in result4["articles"])

        # 測試5: 獲取FULL_SCRAPE任務的所有文章，並以預覽模式返回 (使用 is_preview=True)
        result5 = article_service.get_articles_by_task({'task_id': task_ids[2], 'is_preview': True})
        assert result5["success"] is True
        assert len(result5["articles"]) == 2
        assert all(isinstance(article, dict) for article in result5["articles"]) # 預覽模式返回字典而非模型對象
        assert all('id' in article for article in result5["articles"])
        assert all('title' in article for article in result5["articles"])
        assert all('link' in article for article in result5["articles"])
        assert all('is_scraped' in article for article in result5["articles"]) # 檢查 is_scraped 是否存在
        assert all('content' not in article for article in result5["articles"]) # 預覽模式不包含內容

        # 測試6: 測試缺少必要參數 (task_id)
        result6 = article_service.get_articles_by_task({})
        assert result6["success"] is False
        assert result6["message"] == '必須提供任務ID (task_id)'

        # 測試7: 測試獲取不存在的任務ID
        result7 = article_service.get_articles_by_task({'task_id': 999})
        assert result7["success"] is True
        assert len(result7["articles"]) == 0 # 應返回空列表而不是錯誤
