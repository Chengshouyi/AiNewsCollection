import pytest
from datetime import datetime
from src.model.data_access import DataAccess, Article

@pytest.fixture
def data_access():
    # 使用記憶體中的 SQLite 資料庫
    data_access = DataAccess(db_path="sqlite:///:memory:")
    # 確認資料庫表格已經建立
    data_access.create_tables()
    return data_access

def get_test_article_data(title, link):
    return {
        "title": title,
        "summary": "這是測試文章的摘要",
        "link": link,
        "content": "測試文章內容",
        "published_at": datetime(2025, 3, 5, 10, 0, 0),
        "source": "資料來源"
    }

def test_insert_article(data_access):
    # 測試插入文章
    article_data = get_test_article_data("測試文章", "https://test.com/article")
    # 插入文章
    data_access.insert_article(article_data)
    # 驗證文章是否插入成功
    articles = data_access.get_all_articles()
    assert len(articles) == 1
    assert articles[0]["title"] == "測試文章"
    assert articles[0]["link"] == "https://test.com/article"

# 測試插入重複的文章
def test_insert_duplicate_article(data_access):
    article_data = get_test_article_data("測試文章", "https://test.com/article")
    # 插入第一篇文章
    data_access.insert_article(article_data)
    # 插入第二篇相同的文章
    data_access.insert_article(article_data)
    # 驗證只有一篇文章被插入
    articles = data_access.get_all_articles()
    assert len(articles) == 1

# 測試根據ID抓取文章
def test_get_article_by_id(data_access):
    article_data1 = get_test_article_data("測試文章", "https://test.com/article")
    article_data2 = get_test_article_data("測試文章1", "https://test.com/article1")
    # 插入文章
    data_access.insert_article(article_data1)
    data_access.insert_article(article_data2)
    # 抓取文章
    articles = data_access.get_all_articles()
    article_id = articles[0]["id"]
    retrieved_article = data_access.get_article_by_id(article_id)
    assert retrieved_article is not None
    assert retrieved_article["title"] == "測試文章"
    assert retrieved_article["link"] == "https://test.com/article"

# 測試抓取所有文章
def test_get_all_articles(data_access):
    # 測試抓取所有文章
    article_data1 = get_test_article_data("測試文章1", "https://test.com/article1")
    article_data2 = get_test_article_data("測試文章2", "https://test.com/article2")
    # 插入兩篇文章
    data_access.insert_article(article_data1)
    data_access.insert_article(article_data2)
    # 抓取所有文章
    articles = data_access.get_all_articles()
    assert len(articles) == 2
    assert articles[0]["title"] == "測試文章1"
    assert articles[1]["title"] == "測試文章2"

# 增加邊界測試範例
def test_insert_empty_article(data_access):
    article_data = {
        "title": "",
        "summary": "",
        "link": "https://test.com/empty",
        "content": "",
        "published_at": datetime(2025, 3, 5, 10, 0, 0),
        "source": ""
    }
    data_access.insert_article(article_data)
    articles = data_access.get_all_articles()
    assert len(articles) == 1
    assert articles[0]["title"] == ""

# 增加異常測試範例
def test_insert_article_with_empty_link(data_access):
    empty_link = ''
    article_data = get_test_article_data('這是測試空白link的資料', empty_link)
    # 插入文章，預期空白link會拋出異常
    with pytest.raises(Exception): 
        data_access.insert_article(article_data)