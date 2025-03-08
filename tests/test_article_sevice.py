import pytest
from datetime import datetime
from src.model.models import Base
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

def get_test_article_data(title, link):
    return {
        "title": title,
        "summary": "這是測試文章的摘要",
        "link": link,
        "content": "測試文章內容",
        "published_at": datetime(2025, 3, 5, 10, 0, 0),
        "source": "資料來源"
    }

def test_insert_article(create_app):
    """測試插入文章"""
    article_service = create_app['article_service']
    article_data = get_test_article_data("測試文章", "https://test.com/article")
    # 插入文章
    article_service.create_article(article_data)
    # 驗證文章是否插入成功
    articles = article_service.get_all_articles()
    assert len(articles) == 1
    assert articles[0]["title"] == "測試文章"
    assert articles[0]["link"] == "https://test.com/article"

# 測試插入重複的文章
def test_insert_duplicate_article(create_app):
    article_service = create_app['article_service']
    article_data = get_test_article_data("測試文章", "https://test.com/article")
    # 插入第一篇文章
    article_service.create_article(article_data)
    # 插入第二篇相同的文章
    article_service.create_article(article_data)
    # 驗證插入重複文章會返回 None
    assert article_service.create_article(article_data) is None

# 測試根據ID抓取文章
def test_get_article_by_id(create_app):
    article_service = create_app['article_service']
    article_data1 = get_test_article_data("測試文章", "https://test.com/article")
    article_data2 = get_test_article_data("測試文章1", "https://test.com/article1")
    # 插入文章
    article_service.create_article(article_data1)
    article_service.create_article(article_data2)
    # 抓取文章
    articles = article_service.get_all_articles()
    article_id = articles[0]["id"]
    retrieved_article = article_service.get_article_by_id(article_id)
    assert retrieved_article is not None
    assert retrieved_article["title"] == "測試文章"
    assert retrieved_article["link"] == "https://test.com/article"

# 測試抓取所有文章
def test_get_all_articles(create_app):
    article_service = create_app['article_service']
    article_data1 = get_test_article_data("測試文章1", "https://test.com/article1")
    article_data2 = get_test_article_data("測試文章2", "https://test.com/article2")
    # 插入兩篇文章
    article_service.create_article(article_data1)
    article_service.create_article(article_data2)
    # 抓取所有文章
    articles = article_service.get_all_articles()
    assert len(articles) == 2
    assert articles[0]["title"] == "測試文章1"
    assert articles[1]["title"] == "測試文章2"

# 增加邊界測試範例
def test_insert_empty_article(create_app):
    article_service = create_app['article_service']
    article_data = {
        "title": "",
        "summary": "",
        "link": "https://test.com/empty",
        "content": "",
        "published_at": datetime(2025, 3, 5, 10, 0, 0),
        "source": ""
    }
    article_service.create_article(article_data)
    articles = article_service.get_all_articles()
    assert len(articles) == 1
    assert articles[0]["title"] == ""

# 增加異常測試範例
def test_insert_article_with_empty_link(create_app):
    article_service = create_app['article_service']
    empty_link = ''
    article_data = get_test_article_data('這是測試空白link的資料', empty_link)
    # 插入文章，預期空白link會返回 None
    assert article_service.create_article(article_data) is None

def test_update_article(create_app):
    article_service = create_app['article_service']
    article_data = get_test_article_data("測試文章", "https://test.com/article")
    # 插入文章
    created_article = article_service.create_article(article_data)
    # 更新文章
    updated_data = {
        "title": "更新後的測試文章",
        "summary": "更新後的摘要",
        "link": "https://test.com/updated",
        "content": "更新後的內容",
        "published_at": datetime(2025, 3, 5, 10, 0, 0),
        "source": "更新後的資料來源"
    }
    updated_article = article_service.update_article(created_article ["id"], updated_data)
    assert updated_article is not None
    assert updated_article["title"] == "更新後的測試文章"
    assert updated_article["link"] == "https://test.com/updated"    

def test_delete_article(create_app):
    article_service = create_app['article_service']
    article_data = get_test_article_data("測試文章", "https://test.com/article")
    # 插入文章
    created_article = article_service.create_article(article_data)
    # 刪除文章
    article_service.delete_article(created_article["id"])
    # 驗證文章是否刪除成功
    articles = article_service.get_all_articles()
    assert len(articles) == 0   

def test_delete_nonexistent_article(create_app):
    article_service = create_app['article_service']
    # 嘗試刪除不存在文章
    assert not article_service.delete_article(999999)   

def test_get_article_by_nonexistent_id(create_app):
    article_service = create_app['article_service']
    # 嘗試抓取不存在文章
    assert article_service.get_article_by_id(999999) is None

def test_get_all_articles_empty(create_app):
    article_service = create_app['article_service']
    # 驗證空資料庫返回空列表
    assert article_service.get_all_articles() == []     
    
def test_create_article_with_empty_link(create_app):
    article_service = create_app['article_service']
    article_data = get_test_article_data("測試文章", "")
    # 插入文章，預期空白link會返回 None
    assert article_service.create_article(article_data) is None
    
def test_update_article_with_empty_link(create_app):
    article_service = create_app['article_service']
    article_data = get_test_article_data("測試文章", "https://test.com/article")
    # 插入文章
    created_article = article_service.create_article(article_data)
    # 更新文章，預期空白link會返回 None
    assert article_service.update_article(created_article["id"], {"link": ""}) is None     
    
def test_update_article_with_nonexistent_id(create_app):
    article_service = create_app['article_service']
    article_data = get_test_article_data("測試文章", "https://test.com/article")
    # 插入文章
    article_service.create_article(article_data)
    # 更新文章，預期不存在id會返回 None
    assert article_service.update_article(999999, {"link": "https://test.com/updated"}) is None
    
def test_delete_article_with_nonexistent_id(create_app):
    article_service = create_app['article_service']
    # 嘗試刪除不存在文章
    assert not article_service.delete_article(999999)
    

# if __name__ == "__main__":
#     # 先調用create_app()函數獲取返回的字典
#     app_context = create_app()
#     # 然後將這個字典傳給測試函數
#     test_update_article_with_nonexistent_id(app_context)



