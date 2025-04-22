import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Union, Optional, Sequence
from flask import Flask, jsonify
from pydantic import BaseModel, Field

from src.web.routes.article_api import article_bp
from src.models.articles_schema import ArticleReadSchema, PaginatedArticleResponse
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 輔助模型 (用於 Mock Service) ---

# 模擬 ArticleReadSchema
class ArticleReadSchemaMock(BaseModel):
    id: int
    title: str
    url: str
    source: str
    category: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[List[str]] = None
    published_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # 模擬 Pydantic v2 的 model_dump，不使用 self.dict()
    def model_dump(self, mode='python', **kwargs): # 接受額外參數以提高兼容性
        dump = {}
        for key, value in self.__dict__.items(): # 直接訪問屬性
            if mode == 'json' and isinstance(value, datetime):
                # 轉換為 ISO 格式字串，與 API 回應一致
                dump[key] = value.isoformat().replace('+00:00', 'Z')
            else:
                dump[key] = value
        return dump

# 模擬 PaginatedArticleResponse
class PaginatedArticleResponseMock(BaseModel):
    items: Sequence[Union[ArticleReadSchemaMock, Dict[str, Any]]] # 使用 Sequence 替代 List
    page: int
    per_page: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool

    # 模擬 Pydantic v2 的 model_dump，不使用 self.dict()
    def model_dump(self, mode='python', **kwargs): # 接受額外參數
        dump = {}
        items_dumped = []
        # 手動處理 items
        for item in self.items:
            if isinstance(item, ArticleReadSchemaMock):
                # 遞迴調用模擬的 model_dump
                items_dumped.append(item.model_dump(mode=mode))
            else: # 假定是字典 (預覽模式)
                items_dumped.append(item)
        
        # 處理其他欄位
        for key, value in self.__dict__.items():
            if key == 'items':
                dump[key] = items_dumped
            else:
                dump[key] = value
                
        return dump


# --- 輔助函數 ---

def compare_datetimes(dt1_str, dt2_obj, tolerance_seconds=5):
    """比較日期時間字串與物件，允許誤差"""
    try:
        dt1 = datetime.fromisoformat(dt1_str.replace('Z', '+00:00'))
        if dt2_obj.tzinfo is None:
            dt2_obj = dt2_obj.replace(tzinfo=timezone.utc)
        else:
            dt2_obj = dt2_obj.astimezone(timezone.utc)
        return abs(dt1 - dt2_obj) <= timedelta(seconds=tolerance_seconds)
    except (ValueError, TypeError):
        return False

def compare_article_dicts(dict1, dict2, ignore_keys=['created_at', 'updated_at', 'published_at', 'category']):
    """比較文章字典，忽略時間戳和分類"""
    d1_copy = {k: v for k, v in dict1.items() if k not in ignore_keys}
    d2_copy = {k: v for k, v in dict2.items() if k not in ignore_keys}
    # 特殊處理 tags (列表順序可能不同)
    if 'tags' in d1_copy and isinstance(d1_copy['tags'], list):
        d1_copy['tags'] = sorted(d1_copy['tags']) if d1_copy['tags'] else []
    if 'tags' in d2_copy and isinstance(d2_copy['tags'], list):
        d2_copy['tags'] = sorted(d2_copy['tags']) if d2_copy['tags'] else []
    return d1_copy == d2_copy

# --- Flask App 和 Client Fixtures ---
@pytest.fixture
def app(): # <-- 移除對 tables 的依賴
    """創建測試用的 Flask 應用程式"""
    flask_app = Flask(__name__)
    flask_app.config['TESTING'] = True
    flask_app.config['JSON_SORT_KEYS'] = False
    flask_app.register_blueprint(article_bp)

    # 添加通用錯誤處理 (可選，用於模擬特定異常)
    @flask_app.errorhandler(ValueError)
    def handle_value_error(e):
        return jsonify({"success": False, "message": f"請求參數錯誤: {e}"}), 400

    @flask_app.errorhandler(Exception)
    def handle_generic_exception(e):
         logger.error(f"Test Flask App Error Handler Caught: {e}", exc_info=True)
         # 檢查是否為 SQLAlchemy 的 OperationalError
         # 注意：這裡的 isinstance 檢查可能不夠精確，取決於異常鏈
         from sqlalchemy.exc import OperationalError
         if isinstance(e, OperationalError) and 'no such column' in str(e):
              logger.error("Detected 'no such column' error - check database schema setup!")
              # 仍然返回 500，但日誌提供了線索
              
         status_code = getattr(e, 'code', 500)
         if not isinstance(status_code, int) or status_code < 100 or status_code >= 600:
             status_code = 500
         if status_code == 404:
              return jsonify({"success": False, "message": "資源未找到" }), 404
         return jsonify({"success": False, "message": f"伺服器內部錯誤: {str(e)}"}), status_code

    return flask_app

@pytest.fixture
def client(app):
    """創建測試客戶端"""
    return app.test_client()

@pytest.fixture
def sample_articles_data():
    """創建測試用的原始文章數據 (字典列表)"""
    now = datetime.now(timezone.utc)
    return [
        {
            'id': 1, 'title': 'AI Trends 2024', 'url': 'https://example.com/ai2024',
            'source': 'TechNews', 'content': 'Full content about AI...', 'summary': 'AI summary...',
            'tags': ['AI', 'Technology'], 'published_at': now - timedelta(days=1),
            'created_at': now - timedelta(days=1), 'updated_at': now,
            'category': 'Artificial Intelligence'
        },
        {
            'id': 2, 'title': 'Python Web Frameworks', 'url': 'https://example.com/pythonweb',
            'source': 'DevBlog', 'content': 'Comparing Flask, Django...', 'summary': 'Web framework comparison...',
            'tags': ['Python', 'Web Development'], 'published_at': now - timedelta(days=5),
            'created_at': now - timedelta(days=5), 'updated_at': now - timedelta(days=2),
            'category': None
        },
        {
            'id': 3, 'title': 'Data Science Insights', 'url': 'https://example.com/datasci',
            'source': 'DataJournal', 'content': 'Latest data analysis...', 'summary': 'Data science summary...',
            'tags': ['Data Science', 'Analysis'], 'published_at': now - timedelta(days=10),
            'created_at': now - timedelta(days=10), 'updated_at': now - timedelta(days=5)
        }
    ]

@pytest.fixture
def mock_article_service(monkeypatch, sample_articles_data):
    """模擬 ArticleService"""
    class MockArticleService:
        def __init__(self):
            self.articles = {a['id']: ArticleReadSchemaMock(**a) for a in sample_articles_data}

        def find_articles_paginated(self, page=1, per_page=10, filter_criteria=None, sort_by=None, sort_desc=False, is_preview=False, preview_fields=None):
            all_articles = list(self.articles.values())

            # 模擬過濾
            filtered = []
            if filter_criteria:
                for article in all_articles:
                    match = True
                    for field, value in filter_criteria.items():
                        attr_value = getattr(article, field, None)
                        # 簡單模擬: 完全匹配 或 包含在 tags 列表
                        if field == 'tags' and isinstance(attr_value, list):
                            if value not in attr_value:
                                match = False
                                break
                        elif str(attr_value) != str(value): # 轉為字串比較，避免型別問題
                            match = False
                            break
                    if match:
                        filtered.append(article)
            else:
                filtered = all_articles

            # 模擬排序
            if sort_by:
                try:
                    # 使用元組鍵來處理可能的 None 值
                    filtered.sort(key=lambda a: (getattr(a, sort_by, None) is None, getattr(a, sort_by, None)), reverse=sort_desc)
                except Exception: # 忽略排序錯誤
                    pass

            # 模擬分頁
            total = len(filtered)
            start = (page - 1) * per_page
            end = start + per_page
            items_on_page = filtered[start:end]
            total_pages = (total + per_page - 1) // per_page

            # 處理預覽
            result_items = []
            if is_preview:
                 # Pydantic v2 使用 model_fields
                 valid_fields = ArticleReadSchemaMock.model_fields.keys()
                 # 將 valid_fields 轉換為 list
                 fields_to_include = preview_fields if preview_fields else list(valid_fields)
                 # 確保 id 總是被包含
                 if 'id' not in fields_to_include:
                     fields_to_include = ['id'] + fields_to_include

                 for article in items_on_page:
                      preview_dict = {
                          field: getattr(article, field)
                          for field in fields_to_include if hasattr(article, field)
                      }
                      # 模擬日期轉換為字串
                      for key, value in preview_dict.items():
                          if isinstance(value, datetime):
                               preview_dict[key] = value.isoformat().replace('+00:00', 'Z')
                      result_items.append(preview_dict)
            else:
                result_items = items_on_page # 返回 ArticleReadSchemaMock 對象

            # 創建模擬的分頁回應物件
            paginated_response_mock = PaginatedArticleResponseMock(
                items=result_items,
                page=page,
                per_page=per_page,
                total=total,
                total_pages=total_pages,
                has_next=end < total,
                has_prev=start > 0
            )

            return {
                'success': True,
                'message': "獲取文章列表成功",
                'resultMsg': paginated_response_mock # 返回模擬物件
            }

        def get_article_by_id(self, article_id):
            article = self.articles.get(article_id)
            if article:
                return {
                    'success': True,
                    'message': "獲取文章成功",
                    'article': article # 返回模擬 Schema 物件
                }
            else:
                return {
                    'success': False,
                    'message': f"文章不存在，ID={article_id}",
                    'article': None
                }

        def find_articles_by_keywords(self, keywords, limit=None, offset=None, sort_by=None, sort_desc=False, is_preview=False, preview_fields=None):
            keywords_lower = keywords.lower()
            
            # --- 強制排序與過濾 ---
            # 1. 先獲取所有 mock 對象並按 ID 排序
            all_mock_articles = sorted(list(self.articles.values()), key=lambda a: a.id)
            
            # 2. 從已排序的列表中過濾匹配項
            matched = []
            for a in all_mock_articles:
                title_match = keywords_lower in a.title.lower()
                summary_val = a.summary # 獲取 summary 值
                summary_match = summary_val and keywords_lower in summary_val.lower()
                # --- 詳細調試 --- 
                print(f"  Debug Filter: ID={a.id}, Title Match={title_match}, Summary='{summary_val}', Summary Match={summary_match}")
                # --- 結束調試 --- 
                if title_match or summary_match:
                    matched.append(a)

            # --- 結束強制排序與過濾 ---

            # 模擬排序 (現在是在已經預排序的基礎上，如果提供了 sort_by)
            if sort_by:
                try:
                    # 使用元組鍵來處理可能的 None 值
                    matched.sort(key=lambda a: (getattr(a, sort_by, None) is None, getattr(a, sort_by, None)), reverse=sort_desc)
                except Exception:
                    pass
            else:
                # 如果未指定排序，應用預設排序 (例如按 ID 升序)，確保分頁可預測
                matched.sort(key=lambda a: a.id)

            # --- 加入調試打印 --- 
            print(f"\nDebug: Matched IDs before slicing (offset={offset}, limit={limit}): {[a.id for a in matched]}")
            # --- 結束調試打印 --- 

            # 模擬 limit/offset (注意: offset 是索引，limit 是數量)
            start = offset if offset is not None else 0
            end = (start + limit) if limit is not None else None
            items_result = matched[start:end] # Python 切片處理 None 很方便

             # 處理預覽
            result_items = []
            if is_preview:
                 # Pydantic v2 使用 model_fields
                 valid_fields = ArticleReadSchemaMock.model_fields.keys()
                 # 將 valid_fields 轉換為 list
                 fields_to_include = preview_fields if preview_fields else list(valid_fields)
                 if 'id' not in fields_to_include:
                     fields_to_include = ['id'] + fields_to_include

                 for article in items_result:
                      preview_dict = {
                          field: getattr(article, field)
                          for field in fields_to_include if hasattr(article, field)
                      }
                      # 模擬日期轉換為字串
                      for key, value in preview_dict.items():
                           if isinstance(value, datetime):
                               preview_dict[key] = value.isoformat().replace('+00:00', 'Z')
                      result_items.append(preview_dict)
            else:
                 # 當 is_preview=False 時，也要調用 model_dump 返回字典列表
                 result_items = [a.model_dump(mode='json') for a in items_result]

            return {
                'success': True,
                'message': "搜尋文章成功",
                'articles': result_items # 返回列表 (可能是 Schema 或 Dict)
            }


    mock_service_instance = MockArticleService()
    # 使用 monkeypatch 將 get_article_service 指向我們的 mock 實例
    monkeypatch.setattr('src.web.routes.article_api.get_article_service', lambda: mock_service_instance)
    return mock_service_instance

# --- 測試類 ---

class TestArticleApiRoutes:
    """測試文章相關的 API 路由"""

    def test_get_articles_default(self, client, mock_article_service, sample_articles_data):
        """測試取得文章列表 (預設分頁)"""
        response = client.get('/api/articles')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert '獲取文章列表成功' in result['message']
        assert 'data' in result
        paginated_data = result['data']

        assert paginated_data['page'] == 1
        assert paginated_data['per_page'] == 10 # API 預設值
        assert paginated_data['total'] == len(sample_articles_data)
        assert len(paginated_data['items']) <= 10
        assert len(paginated_data['items']) == len(sample_articles_data) # 因為總數少於10

        # 比較第一篇文章內容 (現在 items 裡是字典)
        assert compare_article_dicts(paginated_data['items'][0], sample_articles_data[0])
        # 比較日期
        assert compare_datetimes(paginated_data['items'][0]['published_at'], sample_articles_data[0]['published_at'])
        assert compare_datetimes(paginated_data['items'][0]['created_at'], sample_articles_data[0]['created_at'])
        assert compare_datetimes(paginated_data['items'][0]['updated_at'], sample_articles_data[0]['updated_at'])


    def test_get_articles_pagination(self, client, mock_article_service, sample_articles_data):
        """測試取得文章列表 (指定分頁)"""
        page = 2
        per_page = 1
        response = client.get(f'/api/articles?page={page}&per_page={per_page}')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        paginated_data = result['data']

        assert paginated_data['page'] == page
        assert paginated_data['per_page'] == per_page
        assert paginated_data['total'] == len(sample_articles_data)
        assert len(paginated_data['items']) == per_page
        assert paginated_data['has_next'] is True # 總共3個，第2頁(每頁1個)後面還有
        assert paginated_data['has_prev'] is True # 第2頁前面有

        # 預期第二頁的第一項是 sample_articles_data 的第二項 (索引1)
        expected_article_data = sample_articles_data[1]
        assert compare_article_dicts(paginated_data['items'][0], expected_article_data)

    def test_get_articles_sorting(self, client, mock_article_service, sample_articles_data):
        """測試取得文章列表 (排序)"""
        response = client.get('/api/articles?sort_by=published_at&sort_desc=true') # 按發佈日期降序
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        paginated_data = result['data']
        items = paginated_data['items']

        assert len(items) == len(sample_articles_data)
        # 檢查是否按 published_at 降序 (最新的在前)
        # 轉換回 datetime 物件比較
        datetimes = [datetime.fromisoformat(item['published_at'].replace('Z', '+00:00')) for item in items]
        for i in range(len(datetimes) - 1):
            assert datetimes[i] >= datetimes[i+1]

        # 驗證第一項是原始數據中最新的 (ID=1)
        assert items[0]['id'] == 1

    def test_get_articles_filtering(self, client, mock_article_service, sample_articles_data):
        """測試取得文章列表 (篩選)"""
        filter_source = 'DevBlog'
        response = client.get(f'/api/articles?source={filter_source}')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        paginated_data = result['data']
        items = paginated_data['items']

        expected_articles = [a for a in sample_articles_data if a['source'] == filter_source]
        assert len(items) == len(expected_articles)
        assert paginated_data['total'] == len(expected_articles)
        assert all(item['source'] == filter_source for item in items)
        # 驗證找到的是 ID=2 的文章
        assert items[0]['id'] == 2

    def test_get_articles_preview(self, client, mock_article_service, sample_articles_data):
        """測試取得文章列表 (預覽模式)"""
        preview_fields = "id,title,source"
        response = client.get(f'/api/articles?is_preview=true&preview_fields={preview_fields}')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        paginated_data = result['data']
        items = paginated_data['items']

        assert len(items) == len(sample_articles_data)
        # 檢查第一篇文章是否只包含指定欄位
        first_item = items[0]
        expected_keys = preview_fields.split(',')
        assert set(first_item.keys()) == set(expected_keys)
        assert first_item['id'] == sample_articles_data[0]['id']
        assert first_item['title'] == sample_articles_data[0]['title']
        assert first_item['source'] == sample_articles_data[0]['source']

    def test_get_articles_empty(self, client, mock_article_service):
        """測試取得文章列表為空"""
        mock_article_service.articles = {} # 清空模擬數據
        response = client.get('/api/articles')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        paginated_data = result['data']
        assert paginated_data['items'] == []
        assert paginated_data['total'] == 0

    def test_get_articles_invalid_params(self, client, mock_article_service):
        """測試取得文章列表時參數類型錯誤"""
        response = client.get('/api/articles?page=abc')
        assert response.status_code == 400 # Flask-RESTx 或 Flask 本身會處理類型轉換錯誤
        result = json.loads(response.data)
        assert result['success'] is False
        assert '請求參數錯誤' in result['message'] # 檢查自訂錯誤處理或 Flask 的錯誤訊息

    # === 測試單篇文章 ===
    def test_get_article_success(self, client, mock_article_service, sample_articles_data):
        """測試成功取得單篇文章"""
        target_id = 1
        target_article_data = sample_articles_data[0]
        response = client.get(f'/api/articles/{target_id}')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert '獲取文章成功' in result['message']
        assert 'data' in result
        fetched_article = result['data']

        assert fetched_article['id'] == target_id
        assert compare_article_dicts(fetched_article, target_article_data)
        assert compare_datetimes(fetched_article['published_at'], target_article_data['published_at'])

    def test_get_article_not_found(self, client, mock_article_service):
        """測試取得不存在的文章"""
        non_existent_id = 999
        response = client.get(f'/api/articles/{non_existent_id}')
        assert response.status_code == 404
        result = json.loads(response.data)

        assert result['success'] is False
        assert '不存在' in result['message']
        assert result.get('data') is None # API 設計中，失敗時 data 為 null

    # === 測試文章搜尋 ===
    def test_search_articles_success(self, client, mock_article_service, sample_articles_data):
        """測試成功搜尋文章"""
        keyword = "Python"
        response = client.get(f'/api/articles/search?q={keyword}')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert '搜尋文章成功' in result['message']
        assert 'data' in result
        found_articles = result['data']

        # 預期找到 ID=2 的文章
        expected_articles = [a for a in sample_articles_data if keyword.lower() in a['title'].lower() or (a['summary'] and keyword.lower() in a['summary'].lower())]
        assert len(found_articles) == len(expected_articles)
        assert found_articles[0]['id'] == 2 # 驗證找到的是 Python 相關的文章
        assert compare_article_dicts(found_articles[0], expected_articles[0])

    def test_search_articles_pagination(self, client, mock_article_service):
        """測試搜尋文章 (帶 limit/offset)"""
        keyword = "summary" # 應該能匹配多個
        limit = 1
        offset = 1 # 跳過第一個結果
        response = client.get(f'/api/articles/search?q={keyword}&limit={limit}&offset={offset}')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        found_articles = result['data']
        assert len(found_articles) == limit

        # 搜索 "summary" 匹配 ID 1 和 3。按 ID 排序後是 [1, 3]。
        # offset=1 跳過 ID 1，limit=1 取下一個，應得到 ID 3。
        assert found_articles[0]['id'] == 3

    def test_search_articles_preview(self, client, mock_article_service):
        """測試搜尋文章 (預覽模式)"""
        keyword = "AI"
        preview_fields = "id,title"
        response = client.get(f'/api/articles/search?q={keyword}&is_preview=true&preview_fields={preview_fields}')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        found_articles = result['data']
        assert len(found_articles) == 1 # 只有 ID=1 包含 AI
        first_item = found_articles[0]
        expected_keys = preview_fields.split(',')
        assert set(first_item.keys()) == set(expected_keys)
        assert first_item['id'] == 1

    def test_search_articles_not_found(self, client, mock_article_service):
        """測試搜尋文章找不到結果"""
        keyword = "NonExistentKeyword123"
        response = client.get(f'/api/articles/search?q={keyword}')
        assert response.status_code == 200 # API 仍然返回 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert '搜尋文章成功' in result['message'] # 或者 Service 可能會說找不到，取決於實現
        assert result['data'] == []

    def test_search_articles_missing_query(self, client):
        """測試搜尋文章缺少關鍵字參數 q"""
        response = client.get('/api/articles/search')
        assert response.status_code == 400
        result = json.loads(response.data)
        assert result['success'] is False
        assert "缺少搜尋關鍵字 'q'" in result['message']

    def test_search_articles_invalid_params(self, client, mock_article_service):
        """測試搜尋文章時參數類型錯誤"""
        response = client.get('/api/articles/search?q=test&limit=abc')
        assert response.status_code == 400 
        result = json.loads(response.data)
        assert result['success'] is False
        assert '請求參數錯誤' in result['message']
