"""測試 Article API 相關路由的功能。"""
# 標準函式庫
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Union, Optional, Sequence
from unittest.mock import patch, MagicMock
import logging
# 第三方函式庫
import pytest
from flask import Flask, jsonify
from pydantic import BaseModel, Field
from sqlalchemy.exc import OperationalError # 移至此處

# 本地應用程式
from src.web.routes.article_api import article_bp
from src.models.articles_schema import ArticleReadSchema, PaginatedArticleResponse # 雖然被 Mock，但保留以防未來類型提示需要
from src.utils.enum_utils import ArticleScrapeStatus # 導入 Enum
  # 使用統一的 logger

# flake8: noqa: F811
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-lines # 允許測試文件較長

# 設定 Logger
logger = logging.getLogger(__name__)  # 使用統一的 logger

# --- 輔助模型 (用於 Mock Service) ---

# 模擬 ArticleReadSchema
class ArticleReadSchemaMock(BaseModel):
    id: int
    title: str
    link: str
    source: str
    source_url: str
    category: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[List[str]] = None
    author: Optional[str] = None
    article_type: Optional[str] = None
    is_ai_related: bool = False
    is_scraped: bool = False
    scrape_status: Optional[ArticleScrapeStatus] = None
    scrape_error: Optional[str] = None
    last_scrape_attempt: Optional[datetime] = None
    task_id: Optional[int] = None
    published_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # 模擬 Pydantic v2 的 model_dump，不使用 self.dict()
    def model_dump(self, mode='python', **kwargs): # 接受額外參數以提高兼容性
        dump = {}
        # 直接使用 Pydantic v2 的 model_fields
        fields = self.__class__.model_fields
        for key in fields.keys():
            # 跳過內部使用的 url 欄位
            if key == 'url':
                continue

            value = getattr(self, key, None)

            if mode == 'json':
                # 在轉換為 JSON 時處理特殊類型
                if isinstance(value, datetime):
                    # 轉換為 ISO 格式字串，以 'Z' 結尾
                    if value.tzinfo:
                        value = value.astimezone(timezone.utc)
                    else:
                        # 假定 naïve datetime 是 UTC
                        value = value.replace(tzinfo=timezone.utc)
                    dump[key] = value.isoformat(timespec='seconds').replace('+00:00', 'Z')
                elif isinstance(value, ArticleScrapeStatus):
                    # 將 Enum 轉換為其值 (字串)
                    dump[key] = value.value
                elif key == 'tags' and isinstance(value, list):
                    # 將 tags 列表轉換為逗號分隔的字串
                    dump[key] = ','.join(value) if value else None
                else:
                    dump[key] = value
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
            elif isinstance(item, dict): # 處理預覽模式下的字典
                 # 如果是 JSON 模式，檢查並轉換日期
                 if mode == 'json':
                      item_copy = {}
                      for k, v in item.items():
                          if isinstance(v, datetime):
                              if v.tzinfo:
                                  v = v.astimezone(timezone.utc)
                              else:
                                  v = v.replace(tzinfo=timezone.utc)
                              item_copy[k] = v.isoformat(timespec='seconds').replace('+00:00', 'Z')
                          else:
                              item_copy[k] = v
                      items_dumped.append(item_copy)
                 else:
                    items_dumped.append(item)
            else: # 其他未知類型，直接添加
                items_dumped.append(item)

        # 處理其他欄位
        # 直接從類別獲取 fields
        fields = self.__class__.model_fields
        for key in fields.keys():
            if key == 'items':
                dump[key] = items_dumped
            else:
                dump[key] = getattr(self, key, None)

        return dump


# --- 輔助函數 ---

def compare_datetimes(dt1_str, dt2_obj, tolerance_seconds=5):
    """比較日期時間字串與物件，允許誤差。"""
    try:
        # API 返回的是 'Z' 結尾的 ISO 格式
        dt1 = datetime.fromisoformat(dt1_str.replace('Z', '+00:00')).replace(tzinfo=timezone.utc)
        if dt2_obj.tzinfo is None:
            # 假設原始測試數據中的 naïve datetime 是 UTC
            dt2_obj = dt2_obj.replace(tzinfo=timezone.utc)
        else:
            dt2_obj = dt2_obj.astimezone(timezone.utc)
        # 打印比較的時間，方便調試
        # print(f"Comparing API time '{dt1_str}' ({dt1}) vs Mock time ({dt2_obj})")
        return abs(dt1 - dt2_obj) <= timedelta(seconds=tolerance_seconds)
    except (ValueError, TypeError) as e:
        logger.error(f"Error comparing datetimes: '{dt1_str}' and {dt2_obj}. Error: {e}")
        return False

def compare_article_dicts(dict1, dict2, ignore_keys=['created_at', 'updated_at', 'published_at', 'category', 'content']):
    """比較文章字典，忽略部分欄位。"""
    # 添加更多要忽略的欄位
    default_ignore = [
        'created_at', 'updated_at', 'published_at', # 時間戳
        'category', 'content', 'summary', # 內容相關 (summary 有時也會被忽略)
        'author', 'article_type', # 作者和類型
        'is_ai_related', 'is_scraped', 'scrape_status', 'scrape_error', 'last_scrape_attempt', 'task_id' # 爬蟲相關
    ]
    # 合併預設忽略和傳入的忽略列表
    all_ignore_keys = set(default_ignore + ignore_keys)

    # 檢查 url vs link
    if 'url' in dict1 and 'link' in dict2:
         if dict1['url'] != dict2['link']:
               return False
         all_ignore_keys.add('url') # 如果比較了 url，就忽略它
         all_ignore_keys.add('link')
    elif 'link' in dict1 and 'url' in dict2:
         if dict1['link'] != dict2['url']:
               return False
         all_ignore_keys.add('url')
         all_ignore_keys.add('link')

    d1_copy = {k: v for k, v in dict1.items() if k not in all_ignore_keys}
    d2_copy = {k: v for k, v in dict2.items() if k not in all_ignore_keys}

    # 特殊處理 tags (列表順序可能不同)
    # 處理 tags，可能一個是字串，一個是列表
    tags1 = d1_copy.get('tags')
    tags2 = d2_copy.get('tags')

    # 將 tags 都轉換為排序後的列表 (或 None)
    processed_tags1 = None
    if isinstance(tags1, str):
        processed_tags1 = sorted(tags1.split(',')) if tags1 else []
    elif isinstance(tags1, list):
        processed_tags1 = sorted(tags1) if tags1 else []

    processed_tags2 = None
    if isinstance(tags2, str):
        processed_tags2 = sorted(tags2.split(',')) if tags2 else []
    elif isinstance(tags2, list):
        processed_tags2 = sorted(tags2) if tags2 else []

    # 如果處理後都是列表或都是 None，則更新字典用於比較
    if (isinstance(processed_tags1, list) or processed_tags1 is None) and \
       (isinstance(processed_tags2, list) or processed_tags2 is None):
         if 'tags' in d1_copy:
               d1_copy['tags'] = processed_tags1
         if 'tags' in d2_copy:
               d2_copy['tags'] = processed_tags2
    # 如果類型不匹配或無法處理，會在後面的比較中失敗

    return d1_copy == d2_copy

# --- Flask App 和 Client Fixtures ---
@pytest.fixture
def app(): # 移除對 tables 的依賴
    """創建測試用的 Flask 應用程式。""" 
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
         logger.error(f"Test Flask App Error Handler Caught: {type(e).__name__}: {e}", exc_info=True) # Log type
         # 檢查是否為 SQLAlchemy 的 OperationalError
         # from sqlalchemy.exc import OperationalError # 移至檔案頂部
         if isinstance(e, OperationalError) and 'no such column' in str(e):
              logger.error("偵測到 'no such column' 錯誤 - 請檢查資料庫結構設定！") # 更新為中文

         # 嘗試從異常中獲取 code，否則預設 500
         status_code = getattr(e, 'code', 500)
         # 確保 status_code 是有效的 HTTP 狀態碼
         if not isinstance(status_code, int) or status_code < 100 or status_code >= 600:
             status_code = 500

         # 基本的錯誤回應格式
         response_body = {"success": False, "message": f"伺服器內部錯誤: {str(e)}"}

         if status_code == 404:
              response_body["message"] = "資源未找到"
         elif status_code == 400: # Flask-Pydantic-Spec 可能拋出帶有詳細訊息的 400
              # 嘗試提取更詳細的錯誤訊息 (這部分可能需要根據實際錯誤類型調整)
              detail_message = getattr(e, 'description', str(e))
              # 保持與原始錯誤訊息一致的格式
              response_body["message"] = f"請求參數錯誤: {detail_message}"

         return jsonify(response_body), status_code

    return flask_app

@pytest.fixture
def client(app):
    """創建測試客戶端"""
    return app.test_client()

@pytest.fixture
def sample_articles_data():
    """創建測試用的原始文章數據 (字典列表)。""" 
    now = datetime.now(timezone.utc)
    return [
        {
            'id': 1, 'title': 'AI Trends 2024', 'url': 'https://example.com/ai2024',
            'source': 'TechNews', 'source_url': 'https://technews.com/ai2024',
            'content': 'Full content about AI...', 'summary': 'AI summary...',
            'tags': ['AI', 'Technology'], 'published_at': now - timedelta(days=1),
            'created_at': now - timedelta(days=1), 'updated_at': now,
            'category': 'Artificial Intelligence',
            'author': 'Jane Doe', 'article_type': 'News',
            'is_ai_related': True, 'is_scraped': True,
            'scrape_status': ArticleScrapeStatus.CONTENT_SCRAPED, 'scrape_error': None,
            'last_scrape_attempt': now - timedelta(hours=1), 'task_id': 123
        },
        {
            'id': 2, 'title': 'Python Web Frameworks', 'url': 'https://example.com/pythonweb',
            'source': 'DevBlog', 'source_url': 'https://devblog.com/pythonweb',
            'content': 'Comparing Flask, Django...', 'summary': 'Web framework comparison...',
            'tags': ['Python', 'Web Development'], 'published_at': now - timedelta(days=5),
            'created_at': now - timedelta(days=5), 'updated_at': now - timedelta(days=2),
            'category': 'Web Development',
            'author': 'John Smith', 'article_type': 'Tutorial',
            'is_ai_related': False, 'is_scraped': True,
            'scrape_status': ArticleScrapeStatus.FAILED, 'scrape_error': 'Timeout during scrape',
            'last_scrape_attempt': now - timedelta(days=2), 'task_id': 456
        },
        {
            'id': 3, 'title': 'Data Science Insights', 'url': 'https://example.com/datasci',
            'source': 'DataJournal', 'source_url': 'https://datajournal.com/datasci',
            'content': 'Latest data analysis...', 'summary': 'Data science summary...',
            'tags': ['Data Science', 'Analysis'], 'published_at': now - timedelta(days=10),
            'created_at': now - timedelta(days=10), 'updated_at': now - timedelta(days=5),
            'category': 'Data Science',
            'author': None, 'article_type': 'Research',
            'is_ai_related': True, 'is_scraped': False,
            'scrape_status': ArticleScrapeStatus.PENDING, 'scrape_error': None,
            'last_scrape_attempt': None, 'task_id': None
        }
    ]

@pytest.fixture
def mock_article_service(monkeypatch, sample_articles_data):
    """模擬 ArticleService。""" 
    class MockArticleService:
        def __init__(self):
            # sample_articles_data 現在應該直接包含 link
            # 如果 sample_articles_data 仍使用 url, 則需要轉換
            self.articles = {}
            for data in sample_articles_data:
                 mock_data = data.copy()
                 # 確保使用的是 link, 如果舊數據用 url 則轉換
                 if 'url' in mock_data and 'link' not in mock_data:
                      mock_data['link'] = mock_data.pop('url')
                 elif 'url' in mock_data and 'link' in mock_data:
                      # 如果意外地兩者都有，優先使用 link，移除 url
                      del mock_data['url']
                 # 現在 mock_data 應該包含 link
                 self.articles[data['id']] = ArticleReadSchemaMock(**mock_data)

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
                    # 特殊處理 published_at 和 last_scrape_attempt
                    if sort_by in ['published_at', 'last_scrape_attempt']:
                        # 確保 None 值排在最後 (升序) 或最前 (降序)
                        none_val = datetime.min.replace(tzinfo=timezone.utc) if not sort_desc else datetime.max.replace(tzinfo=timezone.utc)
                        filtered.sort(key=lambda a: getattr(a, sort_by, none_val), reverse=sort_desc)
                    else:
                        # 其他欄位排序
                        filtered.sort(key=lambda a: (getattr(a, sort_by, None) is None, getattr(a, sort_by, None)), reverse=sort_desc)
                except Exception as e:
                    logger.warning(f"Sorting failed in mock: {e}", exc_info=True)

            # 模擬分頁
            total = len(filtered)
            start = (page - 1) * per_page
            end = start + per_page
            items_on_page = filtered[start:end]
            total_pages = (total + per_page - 1) // per_page

            # 處理預覽
            result_items = []
            if is_preview:
                 # Pydantic v2 使用 model_fields or v1 __fields__
                 valid_fields = ArticleReadSchemaMock.model_fields.keys()
                 # 將 valid_fields 轉換為 list
                 fields_to_include = preview_fields if preview_fields else list(valid_fields)
                 # 確保 id 總是被包含
                 if 'id' not in fields_to_include:
                      fields_to_include = ['id'] + fields_to_include

                 # 檢查是否請求了 'url' 並替換為 'link'
                 if 'url' in fields_to_include:
                     logger.warning("Preview fields requested 'url', but mock uses 'link'. Ignoring 'url'.")
                     fields_to_include.remove('url')

                 for article in items_on_page:
                      preview_dict = {}
                      for field in fields_to_include:
                           if hasattr(article, field):
                                value = getattr(article, field)
                                # 在預覽模式下，如果需要返回 JSON 相容格式，也要轉換日期
                                if isinstance(value, datetime):
                                    if value.tzinfo:
                                        value = value.astimezone(timezone.utc)
                                    else:
                                        value = value.replace(tzinfo=timezone.utc)
                                    preview_dict[field] = value.isoformat(timespec='seconds').replace('+00:00', 'Z')
                                else:
                                    preview_dict[field] = value
                      result_items.append(preview_dict)
            else:
                result_items = items_on_page # 返回 ArticleReadSchemaMock 對象列表

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
                # 確保 summary 存在再搜尋
                summary_match = a.summary and keywords_lower in a.summary.lower()
                # 確保 content 存在再搜尋 (如果需要搜尋 content)
                # content_match = a.content and keywords_lower in a.content.lower()
                if title_match or summary_match: # or content_match:
                    matched.append(a)

            # --- 結束強制排序與過濾 ---

            # 模擬排序 (現在是在已經預排序的基礎上，如果提供了 sort_by)
            if sort_by:
                try:
                    # 使用元組鍵來處理可能的 None 值
                    # 特殊處理 published_at 和 last_scrape_attempt
                    if sort_by in ['published_at', 'last_scrape_attempt']:
                        # 確保 None 值排在最後 (升序) 或最前 (降序)
                        none_val = datetime.min.replace(tzinfo=timezone.utc) if not sort_desc else datetime.max.replace(tzinfo=timezone.utc)
                        matched.sort(key=lambda a: getattr(a, sort_by, none_val), reverse=sort_desc)
                    else:
                        # 其他欄位排序
                        matched.sort(key=lambda a: (getattr(a, sort_by, None) is None, getattr(a, sort_by, None)), reverse=sort_desc)
                except Exception as e:
                    logger.warning(f"Sorting failed in mock search: {e}", exc_info=True)
            else:
                # 如果未指定排序，應用預設排序 (例如按 ID 升序)，確保分頁可預測
                matched.sort(key=lambda a: a.id)

            # 移除調試打印
            # print(f"\nDebug: Matched IDs before slicing (offset={offset}, limit={limit}): {[a.id for a in matched]}")

            # 模擬 limit/offset (注意: offset 是索引，limit 是數量)
            start = offset if offset is not None else 0
            end = (start + limit) if limit is not None else None
            items_result = matched[start:end] # Python 切片處理 None 很方便

             # 處理預覽
            result_items = []
            if is_preview:
                 # Pydantic v2 使用 model_fields or v1 __fields__
                 valid_fields = ArticleReadSchemaMock.model_fields.keys()
                 # 將 valid_fields 轉換為 list
                 fields_to_include = preview_fields if preview_fields else list(valid_fields)
                 if 'id' not in fields_to_include:
                     fields_to_include = ['id'] + fields_to_include

                 # 檢查是否請求了 'url' 並替換為 'link'
                 if 'url' in fields_to_include:
                     logger.warning("Preview fields requested 'url' in search, but mock uses 'link'. Ignoring 'url'.")
                     fields_to_include.remove('url')

                 for article in items_result:
                     preview_dict = {}
                     for field in fields_to_include:
                          if hasattr(article, field):
                               value = getattr(article, field)
                               # 在預覽模式下，如果需要返回 JSON 相容格式，也要轉換日期
                               if isinstance(value, datetime):
                                   if value.tzinfo:
                                       value = value.astimezone(timezone.utc)
                                   else:
                                       value = value.replace(tzinfo=timezone.utc)
                                   preview_dict[field] = value.isoformat(timespec='seconds').replace('+00:00', 'Z')
                               else:
                                   preview_dict[field] = value
                     result_items.append(preview_dict)
            else:
                 # 當 is_preview=False 時，返回 ArticleReadSchemaMock 物件列表
                 # API route 層會處理 model_dump
                 result_items = items_result

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
        """測試取得文章列表 (預設分頁)。"""
        response = client.get('/api/articles')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert '獲取文章列表成功' in result['message']
        assert 'data' in result
        paginated_data = result['data'] # <--- 數據在 'data' 欄位下

        assert paginated_data['page'] == 1
        assert paginated_data['per_page'] == 10 # API 預設值
        assert paginated_data['total'] == len(sample_articles_data)
        assert len(paginated_data['items']) <= 10
        assert len(paginated_data['items']) == len(sample_articles_data) # 因為總數少於10

        # 比較第一篇文章內容 (現在 items 裡是字典，且日期是字串)
        api_article = paginated_data['items'][0]
        mock_article = sample_articles_data[0]

        # 使用輔助函數比較，忽略時間和分類
        assert compare_article_dicts(api_article, mock_article)

        # 使用輔助函數比較時間 (字串 vs datetime 物件)
        assert compare_datetimes(api_article['published_at'], mock_article['published_at'])
        assert compare_datetimes(api_article['created_at'], mock_article['created_at'])
        assert compare_datetimes(api_article['updated_at'], mock_article['updated_at'])


    def test_get_articles_pagination(self, client, mock_article_service, sample_articles_data):
        """測試取得文章列表 (指定分頁)。"""
        page = 2
        per_page = 1
        response = client.get(f'/api/articles?page={page}&per_page={per_page}')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert 'data' in result
        paginated_data = result['data'] # <--- 數據在 'data' 欄位下

        assert paginated_data['page'] == page
        assert paginated_data['per_page'] == per_page
        assert paginated_data['total'] == len(sample_articles_data)
        assert len(paginated_data['items']) == per_page
        assert paginated_data['has_next'] is True # 總共3個，第2頁(每頁1個)後面還有
        assert paginated_data['has_prev'] is True # 第2頁前面有

        # 預期第二頁的第一項是 sample_articles_data 的第二項 (索引1)
        expected_article_data = sample_articles_data[1]
        api_article = paginated_data['items'][0]
        assert compare_article_dicts(api_article, expected_article_data)
        # 也可以檢查時間
        assert compare_datetimes(api_article['published_at'], expected_article_data['published_at'])

    def test_get_articles_sorting(self, client, mock_article_service, sample_articles_data):
        """測試取得文章列表 (排序)。"""
        response = client.get('/api/articles?sort_by=published_at&sort_desc=true') # 按發佈日期降序
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert 'data' in result
        paginated_data = result['data'] # <--- 數據在 'data' 欄位下
        items = paginated_data['items']

        assert len(items) == len(sample_articles_data)
        # 檢查是否按 published_at 降序 (最新的在前)
        # API 返回的是 ISO 字串，可以直接比較字串
        datetimes_str = [item['published_at'] for item in items]
        for i in range(len(datetimes_str) - 1):
            assert datetimes_str[i] >= datetimes_str[i+1]

        # 驗證第一項是原始數據中最新的 (ID=1)
        assert items[0]['id'] == 1

    def test_get_articles_filtering(self, client, mock_article_service, sample_articles_data):
        """測試取得文章列表 (篩選)。"""
        filter_source = 'DevBlog'
        response = client.get(f'/api/articles?source={filter_source}')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert 'data' in result
        paginated_data = result['data'] # <--- 數據在 'data' 欄位下
        items = paginated_data['items']

        expected_articles = [a for a in sample_articles_data if a['source'] == filter_source]
        assert len(items) == len(expected_articles)
        assert paginated_data['total'] == len(expected_articles)
        assert all(item['source'] == filter_source for item in items)
        # 驗證找到的是 ID=2 的文章
        assert items[0]['id'] == 2

    def test_get_articles_preview(self, client, mock_article_service, sample_articles_data):
        """測試取得文章列表 (預覽模式)。"""
        preview_fields = "id,title,source"
        response = client.get(f'/api/articles?is_preview=true&preview_fields={preview_fields}')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert 'data' in result
        paginated_data = result['data'] # <--- 數據在 'data' 欄位下
        items = paginated_data['items']

        assert len(items) == len(sample_articles_data)
        # 檢查第一篇文章是否只包含指定欄位 (items 內直接是字典)
        first_item = items[0]
        expected_keys = preview_fields.split(',')
        assert set(first_item.keys()) == set(expected_keys)
        assert first_item['id'] == sample_articles_data[0]['id']
        assert first_item['title'] == sample_articles_data[0]['title']
        assert first_item['source'] == sample_articles_data[0]['source']

    def test_get_articles_empty(self, client, mock_article_service):
        """測試取得文章列表為空。"""
        # 清空 mock service 中的數據
        mock_article_service.articles = {}
        # 重新設置 mock service 的 find_articles_paginated 方法以返回空的 PaginatedArticleResponseMock
        original_method = mock_article_service.find_articles_paginated
        def mock_empty(*args, **kwargs):
            kwargs['filter_criteria'] = None # 確保 filter_criteria 被正確處理
            result = original_method(*args, **kwargs)
            # 創建一個空的 PaginatedArticleResponseMock
            empty_paginated_response = PaginatedArticleResponseMock(
                items=[], page=kwargs.get('page', 1), per_page=kwargs.get('per_page', 10),
                total=0, total_pages=0, has_next=False, has_prev=False
            )
            result['resultMsg'] = empty_paginated_response
            result['success'] = True
            result['message'] = "獲取文章列表成功" # 即使是空的也成功
            return result
        mock_article_service.find_articles_paginated = mock_empty


        response = client.get('/api/articles')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert 'data' in result
        paginated_data = result['data'] # <--- 數據在 'data' 欄位下
        assert paginated_data['items'] == []
        assert paginated_data['total'] == 0
        assert paginated_data['page'] == 1
        assert paginated_data['per_page'] == 10

    def test_get_articles_invalid_params(self, client, mock_article_service):
        """測試取得文章列表時參數類型錯誤。"""
        response = client.get('/api/articles?page=abc')
        assert response.status_code == 400 # flask-pydantic-spec 應返回 400
        result = json.loads(response.data)
        assert result['success'] is False
        # 驗證錯誤訊息格式是否符合預期
        assert 'message' in result
        # 訊息內容可能依賴於 spec 的具體驗證器，但應指示參數問題
        assert "invalid literal for int()" in result['message'] or "請求參數錯誤" in result['message']


    # === 測試單篇文章 ===
    def test_get_article_success(self, client, mock_article_service, sample_articles_data):
        """測試成功取得單篇文章。"""
        target_id = 1
        target_article_data = sample_articles_data[0] # 原始字典數據
        response = client.get(f'/api/articles/{target_id}')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert '獲取文章成功' in result['message']
        assert 'data' in result
        fetched_article = result['data'] # <--- 數據在 'data' 欄位下

        assert fetched_article['id'] == target_id
        # 比較字典，忽略時間戳和分類
        assert compare_article_dicts(fetched_article, target_article_data)
        # 比較時間戳 (字串 vs datetime)
        assert compare_datetimes(fetched_article['published_at'], target_article_data['published_at'])
        assert compare_datetimes(fetched_article['created_at'], target_article_data['created_at'])
        assert compare_datetimes(fetched_article['updated_at'], target_article_data['updated_at'])

    def test_get_article_not_found(self, client, mock_article_service):
        """測試取得不存在的文章。"""
        non_existent_id = 999
        response = client.get(f'/api/articles/{non_existent_id}')
        # API 路由現在應明確返回 404
        assert response.status_code == 404
        result = json.loads(response.data)

        assert result['success'] is False
        assert '不存在' in result['message'] or '未找到' in result['message'] # 檢查可能的訊息
        # 在失敗的回應中，'data' 鍵不應存在或為 null
        assert 'data' not in result or result.get('data') is None

    # === 測試文章搜尋 ===
    def test_search_articles_success(self, client, mock_article_service, sample_articles_data):
        """測試成功搜尋文章。"""
        keyword = "Python"
        response = client.get(f'/api/articles/search?q={keyword}') # <--- 使用 'q' 參數
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert '搜尋文章成功' in result['message']
        assert 'data' in result
        found_articles = result['data'] # <--- 數據在 'data' 欄位下

        # 預期找到 ID=2 的文章 (原始數據)
        expected_articles_data = [a for a in sample_articles_data if keyword.lower() in a['title'].lower() or (a.get('summary') and keyword.lower() in a['summary'].lower())]
        assert len(found_articles) == len(expected_articles_data)

        # 比較找到的文章 (API 返回的是字典)
        api_article = found_articles[0]
        expected_article = expected_articles_data[0]
        assert api_article['id'] == 2 # 驗證找到的是 Python 相關的文章
        assert compare_article_dicts(api_article, expected_article)
        # 比較日期
        assert compare_datetimes(api_article['published_at'], expected_article['published_at'])


    def test_search_articles_pagination(self, client, mock_article_service, sample_articles_data):
        """測試搜尋文章 (帶 limit/offset)。"""
        keyword = "summary" # 應該能匹配多個
        limit = 1
        offset = 1 # 跳過第一個結果 (基於預設排序，ID 升序)
        response = client.get(f'/api/articles/search?q={keyword}&limit={limit}&offset={offset}') # <--- 使用 'q', 'limit', 'offset'
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert 'data' in result
        found_articles = result['data'] # <--- 數據在 'data' 欄位下
        assert len(found_articles) == limit

        # 搜索 "summary" 匹配 ID 1 和 3。Mock Service 預設按 ID 升序 [1, 3]。
        # offset=1 跳過 ID 1，limit=1 取下一個，應得到 ID 3。
        assert found_articles[0]['id'] == 3

    def test_search_articles_preview(self, client, mock_article_service, sample_articles_data):
        """測試搜尋文章 (預覽模式)。"""
        keyword = "AI"
        preview_fields = "id,title"
        response = client.get(f'/api/articles/search?q={keyword}&is_preview=true&preview_fields={preview_fields}') # <--- 使用 'q'
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert 'data' in result
        found_articles = result['data'] # <--- 數據在 'data' 欄位下 (預覽模式直接是字典列表)
        assert len(found_articles) == 1 # 只有 ID=1 包含 AI

        first_item = found_articles[0]
        expected_keys = preview_fields.split(',')
        assert set(first_item.keys()) == set(expected_keys)
        assert first_item['id'] == 1

    def test_search_articles_not_found(self, client, mock_article_service):
        """測試搜尋文章找不到結果。"""
        keyword = "NonExistentKeyword123"
        response = client.get(f'/api/articles/search?q={keyword}') # <--- 使用 'q'
        assert response.status_code == 200 # API 仍然返回 200
        result = json.loads(response.data)

        assert result['success'] is True
        # 訊息可能是 "搜尋文章成功" 或類似的，取決於服務層
        # assert '搜尋文章成功' in result['message']
        assert 'data' in result
        assert result['data'] == [] # <--- 數據是空列表

    def test_search_articles_missing_query(self, client):
        """測試搜尋文章缺少關鍵字參數 q。"""
        response = client.get('/api/articles/search') # <--- 不帶 'q' 參數
        assert response.status_code == 400 # API 應返回 400
        result = json.loads(response.data)
        assert result['success'] is False
        assert 'message' in result
        assert "缺少搜尋關鍵字 'q'" in result['message'] # 驗證特定錯誤訊息

    def test_search_articles_invalid_params(self, client, mock_article_service):
        """測試搜尋文章時參數類型錯誤。"""
        response = client.get('/api/articles/search?q=test&limit=abc') # <--- 無效的 limit
        assert response.status_code == 400 # spec 驗證應返回 400
        result = json.loads(response.data)
        assert result['success'] is False
        assert 'message' in result
        # 訊息應指示參數錯誤
        assert "invalid literal for int()" in result['message'] or "請求參數錯誤" in result['message']

# 添加一個測試來驗證分類過濾是否有效
    def test_get_articles_filtering_by_category(self, client, mock_article_service, sample_articles_data):
        """測試根據分類篩選文章列表。"""
        filter_category = 'Data Science'
        # URL 編碼可能需要，但 Flask 通常會處理
        response = client.get(f'/api/articles?category={filter_category}')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert 'data' in result
        paginated_data = result['data']
        items = paginated_data['items']

        expected_articles = [a for a in sample_articles_data if a.get('category') == filter_category]
        assert len(items) == len(expected_articles)
        assert paginated_data['total'] == len(expected_articles)
        assert all(item.get('category') == filter_category for item in items)
        # 驗證找到的是 ID=3 的文章
        assert items[0]['id'] == 3

# 添加一個測試來驗證標籤過濾是否有效
    def test_get_articles_filtering_by_tag(self, client, mock_article_service, sample_articles_data):
        """測試根據標籤篩選文章列表。"""
        filter_tag = 'Web Development'
        response = client.get(f'/api/articles?tags={filter_tag}') # 使用 'tags' 參數
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert 'data' in result
        paginated_data = result['data']
        items = paginated_data['items']

        # 預期找到包含 'Web Development' 標籤的文章 (ID=2)
        expected_articles = [a for a in sample_articles_data if a.get('tags') and filter_tag in a['tags']]
        assert len(items) == len(expected_articles)
        assert paginated_data['total'] == len(expected_articles)
        assert items[0]['id'] == 2
        assert filter_tag in items[0]['tags']
