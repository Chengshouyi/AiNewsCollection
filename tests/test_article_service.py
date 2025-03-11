from pydantic import ValidationError
import pytest
from datetime import datetime, timedelta
from src.model.models import Base, Article
from src.model.database_manager import DatabaseManager
from src.model.article_service import ArticleService
from src.model.repository import Repository
from src.model.article_schema import ArticleCreateSchema, ArticleUpdateSchema
from tests import create_in_memory_db, create_database_session


@pytest.fixture
def app_instance(create_in_memory_db):
    """創建應用實例，初始化數據庫和服務"""
    db_manager = create_in_memory_db
    db_manager.create_tables(Base)
    article_service = ArticleService(db_manager)
    return {
        'db_manager': db_manager,
        'article_service': article_service
    }


def get_test_article_data(
    title="測試文章",
    link="https://test.com/article",
    published_at=datetime(2025, 3, 5, 10, 0, 0),
    summary="這是測試文章的摘要",
    content="測試文章內容",
    source="資料來源",
    created_at=datetime.now()
):
    """生成測試用的文章數據"""
    return {
        "title": title,
        "summary": summary,
        "link": link,
        "content": content,
        "published_at": published_at,
        "source": source,
        "created_at": created_at,
    }


class TestArticleService:
    """測試 ArticleService 的測試類"""

    @pytest.fixture(autouse=True)
    def setup(self, app_instance):
        """每個測試前執行的設置"""
        self.article_service = app_instance['article_service']
        self.db_manager = app_instance['db_manager']

    # 插入相關測試
    def test_insert_basic(self):
        """測試基本文章插入"""
        article_data = get_test_article_data()
        inserted_article = self.article_service.insert_article(article_data)
        assert inserted_article is not None
        
        articles = self.article_service.get_all_articles()
        assert len(articles) == 1
        assert articles[0]["title"] == "測試文章"
        assert articles[0]["link"] == "https://test.com/article"

    def test_insert_duplicate(self):
        """測試插入重複文章"""
        article_data = get_test_article_data()
        self.article_service.insert_article(article_data)
        assert self.article_service.insert_article(article_data) is None

    @pytest.mark.parametrize("invalid_data, field", [
        ({"title": ""}, "title"),
        ({"link": ""}, "link"),
        ({"published_at": None}, "published_at"),
        ({"title": "a" * 256}, "title"),
        ({"link": "invalid-url"}, "link"),
    ])
    def test_insert_invalid_data(self, invalid_data, field):
        """測試插入無效數據"""
        article_data = get_test_article_data(**invalid_data)
        assert self.article_service.insert_article(article_data) is None

    def test_insert_data_validation(self):
        """測試文章數據驗證"""
        valid_data = get_test_article_data()
        valid_data.pop('created_at', None)
        assert ArticleCreateSchema.model_validate(valid_data) is not None
        assert ArticleUpdateSchema.model_validate(valid_data) is not None

        invalid_cases = [
            ("title", ""),
            ("link", ""),
            ("link", "invalid-url"),
            ("published_at", None),
            ("published_at", datetime.now() + timedelta(days=30))
        ]
        for field, value in invalid_cases:
            invalid_data = valid_data.copy()
            invalid_data[field] = value
            with pytest.raises(ValidationError):
                ArticleCreateSchema.model_validate(invalid_data)
            with pytest.raises(ValidationError):
                ArticleUpdateSchema.model_validate(invalid_data)

    # 搜尋相關測試
    def test_search_functionality(self):
        """測試文章搜尋功能"""
        self._insert_search_test_data()
        
        # 依標題搜尋
        results = self.article_service.search_articles({"title": "Python"})
        assert len(results) == 2
        assert any(a["title"] == "Python教學" for a in results)
        assert any(a["title"] == "資料分析與Python" for a in results)
        
        # 依內容搜尋
        results = self.article_service.search_articles({"content": "JavaScript"})
        assert len(results) == 1
        assert results[0]["title"] == "JavaScript基礎"
        
        # 依日期範圍搜尋
        results = self.article_service.search_articles({
            "published_at_start": datetime(2025, 3, 4),
            "published_at_end": datetime(2025, 3, 8)
        })
        assert len(results) == 1
        assert results[0]["title"] == "JavaScript基礎"
        
        # 複合條件搜尋
        results = self.article_service.search_articles({
            "content": "教學",
            "published_at_start": datetime(2025, 3, 1),
            "published_at_end": datetime(2025, 3, 5)
        })
        assert len(results) == 2
        
        # 無結果搜尋
        results = self.article_service.search_articles({"title": "不存在的標題"})
        assert len(results) == 0

    # 分頁和排序相關測試
    def test_pagination_and_sorting(self):
        """測試分頁和排序功能"""
        self._insert_pagination_test_data()
        
        # 分頁測試
        page1 = self.article_service.get_articles_paginated(page=1, per_page=3)
        assert len(page1["items"]) == 3
        assert page1["total"] == 10
        assert page1["page"] == 1
        assert page1["total_pages"] == 4
        
        page2 = self.article_service.get_articles_paginated(page=2, per_page=3)
        assert len(page2["items"]) == 3
        assert page2["page"] == 2
        
        page4 = self.article_service.get_articles_paginated(page=4, per_page=3)
        assert len(page4["items"]) == 1
        
        page5 = self.article_service.get_articles_paginated(page=5, per_page=3)
        assert len(page5["items"]) == 0
        
        # 排序測試 - 降序
        sorted_desc = self.article_service.get_articles_paginated(
            page=1, per_page=5, sort_by="published_at", sort_desc=True
        )
        assert sorted_desc["items"][0]["title"] == "文章10"
        assert sorted_desc["items"][4]["title"] == "文章6"
        
        # 排序測試 - 升序
        sorted_asc = self.article_service.get_articles_paginated(
            page=1, per_page=5, sort_by="published_at", sort_desc=False
        )
        assert sorted_asc["items"][0]["title"] == "文章1"
        assert sorted_asc["items"][4]["title"] == "文章5"

    # 獲取相關測試
    def test_get_by_id(self):
        """測試根據ID獲取文章"""
        article_data1 = get_test_article_data(title="測試文章1", link="https://test.com/article1")
        article_data2 = get_test_article_data(title="測試文章2", link="https://test.com/article2")
        self.article_service.insert_article(article_data1)
        self.article_service.insert_article(article_data2)
        
        articles = self.article_service.get_all_articles()
        article_id = articles[0]["id"]
        retrieved_article = self.article_service.get_article_by_id(article_id)
        assert retrieved_article is not None
        assert retrieved_article["title"] == "測試文章1"
        assert retrieved_article["link"] == "https://test.com/article1"

    # 更新相關測試
    def test_update_basic(self):
        """測試更新文章"""
        article_data = get_test_article_data()
        article_data.pop('created_at', None)
        inserted_article = self.article_service.insert_article(article_data)
        article_id = inserted_article["id"]
        
        updated_data = {
            "title": "更新後的測試文章",
            "summary": "更新後的摘要",
            "link": "https://test.com/updated",
            "content": "更新後的內容",
            "published_at": datetime(2025, 3, 5, 10, 0, 0),
            "source": "更新後的資料來源",
            "updated_at": datetime.now()
        }
        updated_article = self.article_service.update_article(article_id, updated_data)
        assert updated_article is not None
        assert updated_article["title"] == "更新後的測試文章"
        assert updated_article["summary"] == "更新後的摘要"
        assert updated_article["link"] == "https://test.com/updated"
        assert updated_article["content"] == "更新後的內容"
        assert updated_article["source"] == "更新後的資料來源"
        assert updated_article["updated_at"] is not None

    # 異常處理相關測試
    def test_database_exception(self, monkeypatch):
        """測試資料庫異常處理"""
        def mock_session_scope(*args, **kwargs):
            raise Exception("Database connection error")
        
        monkeypatch.setattr(self.article_service.db_manager, "session_scope", mock_session_scope)
        assert self.article_service.get_all_articles() == []
        assert self.article_service.get_article_by_id(1) is None
        assert self.article_service.insert_article(get_test_article_data()) is None
        assert self.article_service.update_article(1, {"title": "新標題"}) is None
        assert self.article_service.delete_article(1) is False

    def test_article_to_dict_exception(self, monkeypatch):
        """測試文章轉換字典異常處理"""
        article_data = get_test_article_data()
        inserted_article = self.article_service.insert_article(article_data)
        
        def mock_getattr(*args, **kwargs):
            raise AttributeError("測試異常")
        
        with self.db_manager.session_scope() as session:
            repo = Repository(session, Article)
            article = repo.get_by_id(inserted_article["id"])
            with monkeypatch.context() as m:
                m.setattr(article.__class__, "__getattribute__", mock_getattr)
                result = self.article_service._article_to_dict(article)
                assert result is None

    # 刪除相關測試
    def test_delete_basic(self):
        """測試刪除文章"""
        article_data = get_test_article_data()
        inserted_article = self.article_service.insert_article(article_data)
        assert self.article_service.delete_article(inserted_article["id"]) is True
        assert len(self.article_service.get_all_articles()) == 0

    def test_delete_nonexistent(self):
        """測試刪除不存在的文章"""
        assert self.article_service.delete_article(999999) is False

    # 批量操作相關測試
    def test_batch_operations(self):
        """測試批量操作"""
        articles = [
            get_test_article_data(
                title=f"批量文章{i}",
                link=f"https://test.com/batch/{i}",
                published_at=datetime(2025, 3, 8)
            ) for i in range(1, 6)
        ]
        
        # 批量插入
        success, fail = self.article_service.batch_insert_articles(articles)
        assert success == 5
        assert fail == 0
        assert len(self.article_service.get_all_articles()) == 5
        
        # 批量更新
        all_articles = self.article_service.get_all_articles()
        ids_to_update = [all_articles[0]["id"], all_articles[1]["id"]]
        updated_count, fail_count = self.article_service.batch_update_articles(
            ids_to_update, {"source": "新來源"}
        )
        assert updated_count == 2
        assert fail_count == 0
        for article_id in ids_to_update:
            article = self.article_service.get_article_by_id(article_id)
            assert article["source"] == "新來源"
        
        # 批量刪除
        ids_to_delete = [all_articles[2]["id"], all_articles[3]["id"]]
        deleted_count, fail_count = self.article_service.batch_delete_articles(ids_to_delete)
        assert deleted_count == 2
        assert fail_count == 0
        remaining_articles = self.article_service.get_all_articles()
        assert len(remaining_articles) == 3
        for article in remaining_articles:
            assert article["id"] not in ids_to_delete

    # 無效輸入相關測試
    def test_invalid_inputs(self):
        """測試無效輸入"""
        assert self.article_service.get_article_by_id(-1) is None
        assert self.article_service.get_article_by_id(0) is None
        assert self.article_service.update_article(-1, {}) is None
        assert self.article_service.update_article(0, {"title": "測試"}) is None

    # 邊界情況相關測試
    def test_search_edge_cases(self):
        """測試搜尋邊界情況"""
        edge_cases = [
            {},
            {"published_at_start": datetime.min, "published_at_end": datetime.max},
            {"non_existent_field": "value"}
        ]
        for case in edge_cases:
            results = self.article_service.search_articles(case)
            assert isinstance(results, list)

    def test_pagination_edge_cases(self):
        """測試分頁邊界情況"""
        edge_cases = [
            {"page": 9999, "per_page": 10},
            {"page": 1, "per_page": 0},
            {"page": -1, "per_page": 10}
        ]
        for case in edge_cases:
            result = self.article_service.get_articles_paginated(**case)
            assert result["items"] == []
            assert result["total"] == 0

    def test_batch_operations_error_handling(self):
        """測試批量操作錯誤處理"""
        assert self.article_service.batch_insert_articles([]) == (0, 0)
        assert self.article_service.batch_update_articles([], {}) == (0, 0)
        assert self.article_service.batch_delete_articles([]) == (0, 0)
        
        invalid_ids = [-1, 0, 999999]
        assert self.article_service.batch_update_articles(invalid_ids, {}) == (0, len(invalid_ids))
        assert self.article_service.batch_delete_articles(invalid_ids) == (0, len(invalid_ids))

    # 輔助方法
    def _insert_search_test_data(self):
        """插入搜尋測試數據"""
        self.article_service.insert_article(get_test_article_data(
            title="Python教學",
            link="https://test.com/python",
            content="這是關於Python的教學文章",
            published_at=datetime(2025, 3, 1)
        ))
        self.article_service.insert_article(get_test_article_data(
            title="JavaScript基礎",
            link="https://test.com/javascript",
            content="這是關於JavaScript的基礎教學",
            published_at=datetime(2025, 3, 5)
        ))
        self.article_service.insert_article(get_test_article_data(
            title="資料分析與Python",
            link="https://test.com/data-analysis",
            content="使用Python進行資料分析",
            published_at=datetime(2025, 3, 10)
        ))

    def _insert_pagination_test_data(self):
        """插入分頁測試數據"""
        for i in range(10):
            self.article_service.insert_article(get_test_article_data(
                title=f"文章{i+1}",
                link=f"https://test.com/article{i+1}",
                published_at=datetime(2025, 3, i+1)
            ))