import pytest
from sqlalchemy import create_engine
from src.model.data_access import DataAccess

@pytest.fixture
def data_access():
    # 使用記憶體中的 SQLite 資料庫
    data_access = DataAccess(db_path="sqlite:///:memory:")
    # 確認資料庫表格已經建立
    data_access.create_tables()
    return data_access

def test_insert_article(data_access):
    # 測試插入文章
    article_data = {
        "title":"測試文章",
        "simmary":"這是測試文章的摘要",
        "link":"https://test.com/article",
        "content":"測試文章內容",
        "published_at":"2025-03-05 10:00:00",
        "soure":"資料來源"
    }

    # 插入文章
    data_access.insert_article(article_data)

    # 驗證文章是否插入成功
    articles = data_access.get_all_articles()
    assert len(articles) == 1
    assert articles[0]["title"] == "測試文章"
    assert articles[0]["link"] == "https://test.com/article"

def test_insert_duplicate_article(data_access):
    # 測試插入重複的文章
    article_data = {
        "title":"測試文章",
        "summary":"這是測試文章的摘要",
        "link":"https://test.com/article",
        "content":"測試文章內容",
        "published_at":"2025-03-05 10:00:00",
        "source":"資料來源"
    }

    # 插入第一篇文章
    data_access.insert_article(article_data)

    # 插入第二篇相同的文章
    data_access.insert_article(article_data)

    # 驗證只有一篇文章被插入
    articles = data_access.get_all_articles()
    assert len(articles) == 1


def test_get_article_by_id(data_access):
    # 測試根據ID抓取文章
    article_data = {
        "title":"測試文章",
        "summary":"這是測試文章的摘要",
        "link":"https://test.com/article",
        "content":"測試文章內容",
        "published_at":"2025-03-05 10:00:00",
        "source":"資料來源"
    }

    article_data1 = {
        "title":"測試文章1",
        "summary":"這是測試文章的摘要",
        "link":"https://test.com/article1",
        "content":"測試文章內容",
        "published_at":"2025-03-05 10:00:00",
        "source":"資料來源"
    }
    # 插入文章
    data_access.insert_article(article_data)
    data_access.insert_article(article_data1)

    # 抓取文章
    articles = data_access.get_all_articles()
    article_id = articles[0]["id"]
    retrieved_article = data_access.get_article_by_id(article_id)
    assert retrieved_article is not None
    assert retrieved_article["title"] == "測試文章"
    assert retrieved_article["link"] == "https://test.com/article"

def test_get_all_articles(data_access):
    # 測試抓取所有文章
    article_data1 = {
        "title":"測試文章1",
        "summary":"這是測試文章的摘要1",
        "link":"https://test.com/article1",
        "content":"測試文章內容1",
        "published_at":"2025-03-05 10:00:00",
        "source":"資料來源1"
    }

    article_data2 = {
        "title":"測試文章2",
        "summary":"這是測試文章的摘要2",
        "link":"https://test.com/article2",
        "content":"測試文章內容2",
        "published_at":"2025-03-05 10:00:00",
        "source":"資料來源2"
    }
    

    # 插入兩篇文章
    data_access.insert_article(article_data1)   
    data_access.insert_article(article_data2)

    # 抓取所有文章
    articles = data_access.get_all_articles()
    assert len(articles) == 2
    assert articles[0]["title"] == "測試文章1"
    assert articles[1]["title"] == "測試文章2"

    
    
    
    




