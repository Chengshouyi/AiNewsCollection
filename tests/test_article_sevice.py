from pydantic import ValidationError
import pytest
from datetime import datetime, timedelta
from src.model.models import Base, Article
from src.model.database_manager import DatabaseManager
from src.model.article_service import ArticleService
from src.model.repository import Repository
from src.model.article_schema import ArticleCreateSchema, ArticleUpdateSchema

@pytest.fixture
def create_app():
    """創建應用實例，初始化數據庫和服務"""
    db_manager = DatabaseManager(db_path="sqlite:///:memory:")
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
):
    return {
        "title": title,
        "summary": summary,
        "link": link,
        "content": content,
        "published_at": published_at,
        "source": source,
        "created_at": datetime.now(),
    }

# 插入文章的基本測試
def test_insert_article(create_app):
    """測試插入文章"""
    article_service = create_app['article_service']
    article_data = get_test_article_data()
    
    # 插入文章
    inserted_article = article_service.insert_article(article_data)
    assert inserted_article is not None
    
    # 驗證文章是否插入成功
    articles = article_service.get_all_articles()
    assert len(articles) == 1
    assert articles[0]["title"] == "測試文章"
    assert articles[0]["link"] == "https://test.com/article"

# 測試插入重複的文章
def test_insert_duplicate_article(create_app):
    article_service = create_app['article_service']
    article_data = get_test_article_data()
    
    # 插入第一篇文章
    article_service.insert_article(article_data)
    # 插入第二篇相同的文章，預期失敗
    assert article_service.insert_article(article_data) is None


# 參數化測試無效數據
@pytest.mark.parametrize("invalid_data, field", [
    ({"title": ""}, "title"),
    ({"link": ""}, "link"),
    ({"published_at": None}, "published_at"),
    ({"title": "a" * 256}, "title"),  # 過長的標題
    ({"link": "invalid-url"}, "link"),  # 無效的URL格式
])
def test_insert_invalid_article_data(create_app, invalid_data, field):
    """參數化測試各種無效資料情況"""
    article_service = create_app['article_service']
    article_data = get_test_article_data(**invalid_data)
    
    # 插入文章，預期無效資料會返回 None
    assert article_service.insert_article(article_data) is None


# 資料驗證詳細測試
def test_article_data_validation():
    """測試文章資料驗證方法"""
    # 測試 verify_insert_data
    valid_data = get_test_article_data()
    assert ArticleCreateSchema.model_validate(valid_data) is not None
    assert ArticleUpdateSchema.model_validate(valid_data) is not None

    # 無標題
    invalid_data = valid_data.copy()
    invalid_data["title"] = ""
    with pytest.raises(ValidationError):
        ArticleCreateSchema.model_validate(invalid_data)
    with pytest.raises(ValidationError):
        ArticleUpdateSchema.model_validate(invalid_data)


    # 無連結
    invalid_data = valid_data.copy()
    invalid_data["link"] = ""
    with pytest.raises(ValidationError):
        ArticleCreateSchema.model_validate(invalid_data)
    with pytest.raises(ValidationError):
        ArticleUpdateSchema.model_validate(invalid_data)


    # 無效的連結
    invalid_data = valid_data.copy()
    invalid_data["link"] = "invalid-url"
    with pytest.raises(ValidationError):
        ArticleCreateSchema.model_validate(invalid_data)
    with pytest.raises(ValidationError):
        ArticleUpdateSchema.model_validate(invalid_data)


    # 無發布日期
    invalid_data = valid_data.copy()
    invalid_data["published_at"] = None
    with pytest.raises(ValidationError):
        ArticleCreateSchema.model_validate(invalid_data)
    with pytest.raises(ValidationError):
        ArticleUpdateSchema.model_validate(invalid_data)


    # 未來日期
    future_date = datetime.now() + timedelta(days=30)
    invalid_data = valid_data.copy()
    invalid_data["published_at"] = future_date
    with pytest.raises(ValidationError):
        ArticleCreateSchema.model_validate(invalid_data)
    with pytest.raises(ValidationError):
        ArticleUpdateSchema.model_validate(invalid_data)


# 測試搜尋功能
def test_article_search_functionality(create_app):
    """測試文章搜尋功能"""
    article_service = create_app['article_service']
    
    # 建立測試資料
    article_service.insert_article(get_test_article_data(
        title="Python教學",
        link="https://test.com/python",
        content="這是關於Python的教學文章",
        published_at=datetime(2025, 3, 1)
    ))
    
    article_service.insert_article(get_test_article_data(
        title="JavaScript基礎",
        link="https://test.com/javascript",
        content="這是關於JavaScript的基礎教學",
        published_at=datetime(2025, 3, 5)
    ))
    
    article_service.insert_article(get_test_article_data(
        title="資料分析與Python",
        link="https://test.com/data-analysis",
        content="使用Python進行資料分析",
        published_at=datetime(2025, 3, 10)
    ))
    
    # 測試依標題搜尋
    results = article_service.search_articles({"title":"Python"})
    assert len(results) == 2
    assert any(a["title"] == "Python教學" for a in results)
    assert any(a["title"] == "資料分析與Python" for a in results)
    
    # 測試依內容搜尋
    results = article_service.search_articles({"content":"JavaScript"})
    assert len(results) == 1
    assert results[0]["title"] == "JavaScript基礎"
    
    # 測試依日期範圍搜尋
    results = article_service.search_articles(
        {"published_at_start":datetime(2025, 3, 4),
        "published_at_end":datetime(2025, 3, 8)}
    )
    assert len(results) == 1
    assert results[0]["title"] == "JavaScript基礎"
    
    # 測試複合條件搜尋
    results = article_service.search_articles(
        {"content":"教學",
        "published_at_start":datetime(2025, 3, 1),
        "published_at_end":datetime(2025, 3, 5)}
    )
    assert len(results) == 2
    
    # 測試無結果搜尋
    results = article_service.search_articles({"title":"不存在的標題"})
    assert len(results) == 0


# 測試分頁和排序功能
def test_article_pagination_and_sorting(create_app):
    """測試文章分頁和排序功能"""
    article_service = create_app['article_service']
    
    # 插入多篇文章
    for i in range(10):
        article_service.insert_article(get_test_article_data(
            title=f"文章{i+1}",
            link=f"https://test.com/article{i+1}",
            published_at=datetime(2025, 3, i+1)
        ))
    
    # 測試分頁
    page1 = article_service.get_articles_paginated(page=1, per_page=3)
    assert len(page1["items"]) == 3
    assert page1["total"] == 10
    assert page1["page"] == 1
    assert page1["total_pages"] == 4
    
    page2 = article_service.get_articles_paginated(page=2, per_page=3)
    assert len(page2["items"]) == 3
    assert page2["page"] == 2
    
    # 測試最後一頁
    page4 = article_service.get_articles_paginated(page=4, per_page=3)
    assert len(page4["items"]) == 1
    
    # 測試超出範圍的頁碼
    page5 = article_service.get_articles_paginated(page=5, per_page=3)
    assert len(page5["items"]) == 0
    
    # 測試排序功能 - 依發布日期降序
    sorted_desc = article_service.get_articles_paginated(
        page=1, 
        per_page=5, 
        sort_by="published_at", 
        sort_desc=True
    )
    assert sorted_desc["items"][0]["title"] == "文章10"
    assert sorted_desc["items"][4]["title"] == "文章6"
    
    # 測試排序功能 - 依發布日期升序
    sorted_asc = article_service.get_articles_paginated(
        page=1, 
        per_page=5, 
        sort_by="published_at", 
        sort_desc=False
    )
    assert sorted_asc["items"][0]["title"] == "文章1"
    assert sorted_asc["items"][4]["title"] == "文章5"


# 測試獲取文章功能 (保留原有測試)
def test_get_article_by_id(create_app):
    article_service = create_app['article_service']
    article_data1 = get_test_article_data(title="測試文章1", link="https://test.com/article1")
    article_data2 = get_test_article_data(title="測試文章2", link="https://test.com/article2")
    
    # 插入兩篇文章
    article_service.insert_article(article_data1)
    article_service.insert_article(article_data2)
    
    # 抓取文章
    articles = article_service.get_all_articles()
    article_id = articles[0]["id"]
    retrieved_article = article_service.get_article_by_id(article_id)
    assert retrieved_article is not None
    assert retrieved_article["title"] == "測試文章1"
    assert retrieved_article["link"] == "https://test.com/article1"


# 測試更新文章 (保留原有測試並增強)
def test_update_article(create_app):
    article_service = create_app['article_service']
    article_data = get_test_article_data()
    
    # 插入文章
    inserted_article = article_service.insert_article(article_data)
    inserted_article_id = inserted_article["id"]
    assert inserted_article_id is not None

    # 更新文章
    updated_data = {
        "title": "更新後的測試文章",
        "summary": "更新後的摘要",
        "link": "https://test.com/updated",
        "content": "更新後的內容",
        "published_at": datetime(2025, 3, 5, 10, 0, 0),
        "source": "更新後的資料來源",
        "updated_at": datetime.now()
    }
    
    updated_article = article_service.update_article(
        inserted_article_id, 
        updated_data
    )
    
    # 驗證更新文章是否成功
    assert updated_article is not None
    assert updated_article["title"] == "更新後的測試文章"
    assert updated_article["summary"] == "更新後的摘要"
    assert updated_article["link"] == "https://test.com/updated"
    assert updated_article["content"] == "更新後的內容"
    assert updated_article["source"] == "更新後的資料來源"
    assert updated_article["updated_at"] is not None


# 測試資料庫異常處理
def test_database_exception_handling(create_app, monkeypatch):
    """測試資料庫異常處理"""
    article_service = create_app['article_service']

    # 模擬資料庫異常
    def mock_session_scope(*args, **kwargs):
        raise Exception("Database connection error")

    monkeypatch.setattr(article_service.db_manager, "session_scope", mock_session_scope)

    # 測試各種操作的異常處理
    assert article_service.get_all_articles() == []
    assert article_service.get_article_by_id(1) is None
    assert article_service.insert_article(get_test_article_data()) is None
    assert article_service.update_article(1, {"title": "新標題"}) is None
    assert article_service.delete_article(1) is False


# 測試 _article_to_dict 方法的異常處理
def test_article_to_dict_exception_handling(create_app, monkeypatch):
    """測試文章轉換字典異常處理"""
    article_service = create_app['article_service']

    # 建立測試文章
    article_data = get_test_article_data()
    inserted_article = article_service.insert_article(article_data)
    
    # 模擬異常
    def mock_getattr(*args, **kwargs):
        raise AttributeError("測試異常")

    # 獲取文章對象然後修改其行為來模擬異常
    with create_app['db_manager'].session_scope() as session:
        repo = Repository(session, Article)
        article = repo.get_by_id(inserted_article["id"])
        
        with monkeypatch.context() as m:
            m.setattr(article.__class__, "__getattribute__", mock_getattr)
            result = article_service._article_to_dict(article)
            assert result is None


# 保留原有測試：刪除文章
def test_delete_article(create_app):
    article_service = create_app['article_service']
    article_data = get_test_article_data()
    
    # 插入文章
    inserted_article = article_service.insert_article(article_data)
    
    # 刪除文章
    assert article_service.delete_article(inserted_article["id"]) is True
    
    # 驗證文章是否刪除成功
    articles = article_service.get_all_articles()
    assert len(articles) == 0


# 保留原有測試：刪除不存在文章
def test_delete_nonexistent_article(create_app):
    article_service = create_app['article_service']
    
    # 嘗試刪除不存在文章
    assert article_service.delete_article(999999) is False


# 批量操作測試
def test_batch_operations(create_app):
    """測試批量操作功能"""
    article_service = create_app['article_service']
    
    # 準備多篇文章數據
    articles = [
        get_test_article_data(
            title=f"批量文章{i}", 
            link=f"https://test.com/batch/{i}",
            published_at=datetime(2025, 3, 8)
        )
        for i in range(1, 6)
    ]
    
    # 測試批量插入
    inserted_articles = article_service.batch_insert_articles(articles)
    assert inserted_articles[0] == 5
    assert inserted_articles[1] == 0
    # 驗證插入結果
    all_articles = article_service.get_all_articles()
    assert len(all_articles) == 5
    
    # 測試批量更新
    ids_to_update = [all_articles[0]["id"], all_articles[1]["id"]]
    update_data = {"source": "新來源"}
    
    updated_count, fail_count = article_service.batch_update_articles(ids_to_update, update_data)
    assert updated_count == 2
    assert fail_count == 0
    
    # 驗證更新結果
    for article_id in ids_to_update:
        article = article_service.get_article_by_id(article_id)
        assert article["source"] == "新來源"
    
    # 測試批量刪除
    ids_to_delete = [all_articles[2]["id"], all_articles[3]["id"]]
    deleted_count, fail_count = article_service.batch_delete_articles(ids_to_delete)
    assert deleted_count == 2
    assert fail_count == 0
    
    # 驗證刪除結果
    remaining_articles = article_service.get_all_articles()
    assert len(remaining_articles) == 3
    for article in remaining_articles:
        assert article["id"] not in ids_to_delete


# 測試 article_service 的無效輸入
def test_article_service_invalid_inputs(create_app):
    article_service = create_app['article_service']
    
    # 測試無效的文章ID
    assert article_service.get_article_by_id(-1) is None
    assert article_service.get_article_by_id(0) is None
    
    # 測試無效的更新輸入
    assert article_service.update_article(-1, {}) is None
    assert article_service.update_article(0, {"title": "測試"}) is None


def test_article_service_edge_cases(create_app):
    article_service = create_app['article_service']
    
    # 測試搜尋極端情況
    edge_cases = [
        # 空搜尋條件
        {},
        # 極端日期範圍
        {"published_at_start": datetime.min, "published_at_end": datetime.max},
        # 不存在的搜尋條件
        {"non_existent_field": "value"}
    ]
    
    for case in edge_cases:
        results = article_service.search_articles(case)
        assert isinstance(results, list)

def test_article_service_pagination_edge_cases(create_app):
    article_service = create_app['article_service']
    
    # 測試極端分頁情況
    edge_cases = [
        # 非常大的頁碼
        {"page": 9999, "per_page": 10},
        # 非常小的每頁數量
        {"page": 1, "per_page": 0},
        # 負數頁碼
        {"page": -1, "per_page": 10}
    ]
    
    for case in edge_cases:
        result = article_service.get_articles_paginated(**case)
        assert result["items"] == []
        assert result["total"] == 0

def test_article_service_batch_operations_error_handling(create_app):
    article_service = create_app['article_service']
    
    # 測試批量操作的錯誤處理
    # 空列表
    assert article_service.batch_insert_articles([]) == (0, 0)
    assert article_service.batch_update_articles([], {}) == (0, 0)
    assert article_service.batch_delete_articles([]) == (0, 0)
    
    # 無效的 ID 列表
    invalid_ids = [-1, 0, 999999]
    assert article_service.batch_update_articles(invalid_ids, {}) == (0, len(invalid_ids))
    assert article_service.batch_delete_articles(invalid_ids) == (0, len(invalid_ids))
