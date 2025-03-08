import pytest
from datetime import datetime
from src.model.models import Base, Article
from src.model.database_manager import DatabaseManager
from src.model.article_service import ArticleService

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
    title,
    link,
    published_at,
):
    return {
        "title": title,
        "summary": "這是測試文章的摘要",
        "link": link,
        "content": "測試文章內容",
        "published_at": published_at,
        "source": "資料來源",
        "created_at": datetime.now(),
    }


# 測試插入文章
def test_insert_article(create_app):
    """測試插入文章"""
    article_service = create_app['article_service']
    article_data = get_test_article_data(
        "測試文章", 
        "https://test.com/article", 
        datetime(2025, 3, 5, 10, 0, 0), 
        )
    # 插入文章
    article_service.insert_article(article_data)
    # 驗證文章是否插入成功
    articles = article_service.get_all_articles()
    assert len(articles) == 1
    assert articles[0]["title"] == "測試文章"
    assert articles[0]["link"] == "https://test.com/article"

# 測試插入重複的文章
def test_insert_duplicate_article(create_app):
    article_service = create_app['article_service']
    article_data = get_test_article_data(
        "測試文章", 
        "https://test.com/article", 
        datetime(2025, 3, 5, 10, 0, 0), 
        )
    # 插入第一篇文章
    article_service.insert_article(article_data)
    # 插入第二篇相同的文章
    article_service.insert_article(article_data)
    # 驗證插入重複文章會返回 None
    assert article_service.insert_article(article_data) is None


# 測試插入空白link的文章
def test_insert_article_with_empty_link(create_app):
    article_service = create_app['article_service']
    empty_link = ''
    article_data = get_test_article_data(
        '這是測試空白link的資料', 
        empty_link, 
        datetime(2025, 3, 5, 10, 0, 0), 
        )
    # 插入文章，預期空白link會返回 None
    assert article_service.insert_article(article_data) is None

# 測試插入空白title的文章
def test_insert_article_with_empty_title(create_app):
    article_service = create_app['article_service']
    empty_title = ''
    article_data = get_test_article_data(
        empty_title, 
        'https://test.com/article', 
        datetime(2025, 3, 5, 10, 0, 0), 
        )
    # 插入文章，預期空白title會返回 None
    assert article_service.insert_article(article_data) is None

# 測試插入空白published_at的文章
def test_insert_article_with_empty_published_at(create_app):
    article_service = create_app['article_service']
    empty_published_at = None
    article_data = get_test_article_data(
        "測試文章", 
        "https://test.com/article", 
        empty_published_at, 
        )
    # 插入文章，預期空白published_at會返回 None
    assert article_service.insert_article(article_data) is None

# 測試根據ID抓取文章
def test_get_article_by_id(create_app):
    article_service = create_app['article_service']
    article_data1 = get_test_article_data(
        "測試文章1", 
        "https://test.com/article1", 
        datetime(2025, 3, 5, 10, 0, 0), 
        )
    article_data2 = get_test_article_data(
        "測試文章2", 
        "https://test.com/article2", 
        datetime(2025, 3, 5, 10, 0, 0), 
        )
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

# 測試抓取所有文章
def test_get_all_articles(create_app):
    article_service = create_app['article_service']
    article_data1 = get_test_article_data(
        "測試文章1", 
        "https://test.com/article1", 
        datetime(2025, 3, 5, 10, 0, 0), 
        )
    article_data2 = get_test_article_data(
        "測試文章2", 
        "https://test.com/article2", 
        datetime(2025, 3, 5, 10, 0, 0), 
        )
    # 插入兩篇文章
    article_service.insert_article(article_data1)
    article_service.insert_article(article_data2)
    # 抓取所有文章
    articles = article_service.get_all_articles()
    assert len(articles) == 2
    assert articles[0]["title"] == "測試文章1"
    assert articles[1]["title"] == "測試文章2"

# 測試抓取不存在文章
def test_get_article_by_nonexistent_id(create_app):
    article_service = create_app['article_service']
    article_data = get_test_article_data(
        "測試文章", 
        "https://test.com/article1", 
        datetime(2025, 3, 5, 10, 0, 0), 
        )
    # 插入文章
    article_service.insert_article(article_data)
    # 嘗試抓取不存在文章
    assert article_service.get_article_by_id(999999) is None

# 測試從空資料庫抓取文章
def test_get_all_articles_from_empty_database(create_app):
    article_service = create_app['article_service']
    # 驗證空資料庫返回空列表
    assert article_service.get_all_articles() == []   

# 測試更新文章
def test_update_article(create_app):
    article_service = create_app['article_service']
    article_data = get_test_article_data(
        "測試文章", 
        "https://test.com/article", 
        datetime(2025, 3, 5, 10, 0, 0), 
        )
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
        "updated_at": datetime.now(),
        "deleted_at": None
    }
    assert Article.verify_update_data(updated_data) is True

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
    
    # 使用更靈活的日期比較方式
    assert isinstance(updated_article["published_at"], datetime)
    assert updated_article["published_at"].year == 2025
    assert updated_article["published_at"].month == 3
    assert updated_article["published_at"].day == 5
    assert updated_article["published_at"].hour == 10
    assert updated_article["published_at"].minute == 0
    
    assert updated_article["source"] == "更新後的資料來源"
    assert updated_article["updated_at"] is not None


# 測試更新文章，預期空白link會返回 None
def test_update_article_with_empty_link(create_app):
    article_service = create_app['article_service']
    article_data = get_test_article_data(
        '這是測試空白link的資料', 
        "https://test.com/updated", 
        datetime(2025, 3, 5, 10, 0, 0), 
        )
    
    # 插入文章
    inserted_article = article_service.insert_article(article_data)
    # 更新文章，預期空白link會返回 None
    assert article_service.update_article(
        inserted_article["id"], {"link": ""}) is None     

# 測試更新文章，預期不存在id會返回 None
def test_update_article_with_nonexistent_id(create_app):
    article_service = create_app['article_service']
    article_data = get_test_article_data(
        "測試文章", 
        "https://test.com/article", 
        datetime(2025, 3, 5, 10, 0, 0), 
        )
    # 插入文章
    article_service.insert_article(article_data)
    # 更新文章，預期不存在id會返回 None
    assert article_service.update_article(999999, {"link": "https://test.com/updated"}) is None

# 測試刪除文章
def test_delete_article(create_app):
    article_service = create_app['article_service']
    article_data = get_test_article_data(
        "測試文章", 
        "https://test.com/article", 
        datetime(2025, 3, 5, 10, 0, 0), 
        )
    # 插入文章
    inserted_article = article_service.insert_article(article_data)
    # 刪除文章
    article_service.delete_article(inserted_article["id"])
    # 驗證文章是否刪除成功
    articles = article_service.get_all_articles()
    assert len(articles) == 0   

# 測試刪除不存在文章
def test_delete_nonexistent_article(create_app):
    article_service = create_app['article_service']
    article_data = get_test_article_data(
        "測試文章", 
        "https://test.com/article", 
        datetime(2025, 3, 5, 10, 0, 0), 
        )
    # 插入文章
    article_service.insert_article(article_data)
    # 嘗試刪除不存在文章
    assert not article_service.delete_article(999999)   

# 測試刪除不存在文章，預期不存在id會返回 False
def test_delete_article_with_nonexistent_id(create_app):
    article_service = create_app['article_service']
    # 嘗試刪除不存在文章
    assert not article_service.delete_article(999999)



