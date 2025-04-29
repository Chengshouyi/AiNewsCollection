"""測試爬蟲 API 路由 (/api/crawlers) 的功能。"""
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from unittest.mock import patch, MagicMock

import pytest
from flask import Flask, jsonify

from src.error.errors import ValidationError
from src.models.crawlers_schema import PaginatedCrawlerResponse, CrawlerReadSchema
from src.utils.log_utils import LoggerSetup  # 使用統一的 logger
from src.web.routes.crawler_api import crawler_bp

# flake8: noqa: F811
# pylint: disable=redefined-outer-name

logger = LoggerSetup.setup_logger(__name__)  # 使用統一的 logger

# 輔助函數：比較字典（忽略時間精度問題）
def compare_crawler_dicts(dict1, dict2, ignore_keys=['created_at', 'updated_at']):
    d1_copy = {k: v for k, v in dict1.items() if k not in ignore_keys}
    d2_copy = {k: v for k, v in dict2.items() if k not in ignore_keys}
    return d1_copy == d2_copy

# 輔助函數：比較日期時間（允許微小誤差）
def compare_datetimes(dt1_str, dt2_obj, tolerance_seconds=5):
    try:
        # Flask jsonify 可能會將 datetime 轉為 ISO 格式字串
        dt1 = datetime.fromisoformat(dt1_str.replace('Z', '+00:00'))
        # 確保 dt2 是 timezone-aware
        if dt2_obj.tzinfo is None:
            dt2_obj = dt2_obj.replace(tzinfo=timezone.utc)
        else:
            dt2_obj = dt2_obj.astimezone(timezone.utc) # 轉換為 UTC
        return abs(dt1 - dt2_obj) <= timedelta(seconds=tolerance_seconds)
    except (ValueError, TypeError):
        return False # 解析失敗則視為不相等

@pytest.fixture
def app():
    """創建測試用的 Flask 應用程式"""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['JSON_SORT_KEYS'] = False
    
    # 註冊路由藍圖
    app.register_blueprint(crawler_bp)
    
    # 添加通用錯誤處理
    @app.errorhandler(ValidationError)
    def handle_validation_error(e):
        # 模擬 Service 層驗證失敗時 API 的回應
        return jsonify({
            "success": False,
            "message": f"爬蟲設定資料驗證失敗: {str(e)}",
            "crawler": None # 或其他相關結構
            }), 400

    @app.errorhandler(Exception)
    def handle_generic_exception(e):
         # 模擬處理未預期的錯誤
         logger.error(f"Test Flask App Error Handler Caught: {e}", exc_info=True)
         status_code = getattr(e, 'code', 500) # 處理 HTTPException
         # 確保 status_code 在有效範圍內
         if not isinstance(status_code, int) or status_code < 100 or status_code >= 600:
             status_code = 500

         # 對於 404，模仿 Service 的回應格式
         if status_code == 404:
              return jsonify({
                  "success": False,
                  "message": "資源未找到或操作無法完成" # 通用 404 訊息
              }), 404

         # 其他錯誤
         return jsonify({"success": False, "message": f"伺服器內部錯誤: {str(e)}"}), status_code

    return app

@pytest.fixture
def client(app):
    """創建測試客戶端"""
    return app.test_client()

class CrawlerMock:
    """模擬 Crawlers Schema (例如 CrawlerReadSchema) 的行為，用於 Mock Service"""
    def __init__(self, data):
        self.id = data.get('id')
        self.crawler_name = data.get('crawler_name')
        self.module_name = data.get('module_name')
        self.base_url = data.get('base_url')
        self.crawler_type = data.get('crawler_type')
        self.config_file_name = data.get('config_file_name')
        self.is_active = data.get('is_active', True)
        # 確保時間是 timezone-aware UTC
        self.created_at = data.get('created_at', datetime.now(timezone.utc))
        if self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)
        self.updated_at = data.get('updated_at', datetime.now(timezone.utc))
        if self.updated_at.tzinfo is None:
            self.updated_at = self.updated_at.replace(tzinfo=timezone.utc)

    def model_dump(self):
        """模擬 Pydantic 的 model_dump 方法，將 datetime 轉為 ISO 字串"""
        return {
            'id': self.id,
            'crawler_name': self.crawler_name,
            'module_name': self.module_name,
            'base_url': self.base_url,
            'crawler_type': self.crawler_type,
            'config_file_name': self.config_file_name,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat().replace('+00:00', 'Z') if self.created_at else None,
            'updated_at': self.updated_at.isoformat().replace('+00:00', 'Z') if self.updated_at else None
        }

@pytest.fixture
def sample_crawlers_data():
    """創建測試用的原始爬蟲數據 (字典列表)"""
    now = datetime.now(timezone.utc)
    return [
        {
            'id': 1, 'crawler_name': 'TestCrawler1', 'module_name': 'test_module', 'base_url': 'https://example1.com',
            'crawler_type': 'web', 'config_file_name': 'test1.json', 'is_active': True,
            'created_at': now, 'updated_at': now
        },
        {
            'id': 2, 'crawler_name': 'TestCrawler2', 'module_name': 'test_module', 'base_url': 'https://example2.com',
            'crawler_type': 'web', 'config_file_name': 'test2.json', 'is_active': False,
            'created_at': now, 'updated_at': now
        },
        {
            'id': 3, 'crawler_name': 'TestCrawler3', 'module_name': 'test_module', 'base_url': 'https://example3.com',
            'crawler_type': 'rss', 'config_file_name': 'test3.json', 'is_active': True,
            'created_at': now, 'updated_at': now
        }
    ]

@pytest.fixture
def mock_crawlers_service(monkeypatch, sample_crawlers_data):
    """模擬 CrawlersService，使其回傳值符合實際 Service 的結構"""
    class MockCrawlersService:
        def __init__(self):
            # 儲存 CrawlerMock 對象
            self.crawlers = {c['id']: CrawlerMock(c) for c in sample_crawlers_data}
            self.next_id = max(self.crawlers.keys()) + 1 if self.crawlers else 1

        def _validate_data(self, data, is_update=False):
            """簡易模擬驗證，實際驗證在 Service 層"""
            required = ['crawler_name', 'base_url', 'crawler_type', 'config_file_name']
            missing = [field for field in required if field not in data]
            if not is_update and missing:
                # 模擬 Pydantic 驗證錯誤訊息
                field_errors = {f: "此欄位為必填項" for f in missing}
                raise ValidationError(f"缺少必要欄位: {', '.join(missing)}：{field_errors}") # 假設 ValidationError 接受詳細錯誤
            # 可以在此添加更多模擬驗證邏輯
            return data

        def create_crawler(self, crawler_data):
            try:
                # 模擬 Service 內部的驗證
                validated_data = self._validate_data(crawler_data, is_update=False)

                new_id = self.next_id
                now = datetime.now(timezone.utc)
                # 模擬 Service 添加的欄位
                full_data = {
                    **validated_data,
                    'id': new_id,
                    'is_active': validated_data.get('is_active', True), # 預設值
                    'created_at': now,
                    'updated_at': now
                }
                new_crawler = CrawlerMock(full_data)
                self.crawlers[new_id] = new_crawler
                self.next_id += 1
                # 返回符合 Service 接口的字典，包含 CrawlerReadSchema 的模擬
                return {
                    'success': True,
                    'message': "爬蟲設定創建成功",
                    'crawler': new_crawler # 返回模擬的 Schema 物件
                }
            except ValidationError as e:
                 # 模擬 Service 捕獲驗證錯誤並返回失敗結果
                 return {
                     'success': False,
                     'message': f"爬蟲設定資料驗證失敗: {str(e)}",
                     'crawler': None
                 }
            except Exception as e:
                 logger.error(f"Mock create_crawler error: {e}")
                 return {'success': False, 'message': str(e), 'crawler': None}

        def get_crawler_by_id(self, crawler_id):
            crawler = self.crawlers.get(crawler_id)
            if not crawler:
                return {
                    'success': False,
                    'message': f"爬蟲設定不存在，ID={crawler_id}",
                    'crawler': None
                }
            return {
                'success': True,
                'message': "獲取爬蟲設定成功",
                'crawler': crawler # 返回模擬的 Schema 物件
            }

        def update_crawler(self, crawler_id, crawler_data):
            if crawler_id not in self.crawlers:
                return {
                    'success': False,
                    'message': f"爬蟲設定不存在，ID={crawler_id}",
                    'crawler': None
                }
            try:
                # 模擬 Service 內部的驗證 (更新時允許部分欄位)
                validated_data = self._validate_data(crawler_data, is_update=True)

                crawler = self.crawlers[crawler_id]
                now = datetime.now(timezone.utc)
                # 更新允許的欄位
                for key, value in validated_data.items():
                     if hasattr(crawler, key) and key != 'id': # 不更新 id 和不存在的屬性
                         setattr(crawler, key, value)
                crawler.updated_at = now # Service 會更新 updated_at

                return {
                    'success': True,
                    'message': "爬蟲設定更新成功",
                    'crawler': crawler # 返回更新後的模擬 Schema 物件
                }
            except ValidationError as e:
                return {
                    'success': False,
                    'message': f"爬蟲設定更新資料驗證失敗: {str(e)}",
                    'crawler': None
                }
            except Exception as e:
                 logger.error(f"Mock update_crawler error: {e}")
                 return {'success': False, 'message': str(e), 'crawler': None}

        def delete_crawler(self, crawler_id):
            if crawler_id not in self.crawlers:
                return {
                    'success': False,
                    'message': f"爬蟲設定不存在，ID={crawler_id}"
                }
            del self.crawlers[crawler_id]
            return {
                'success': True,
                'message': "爬蟲設定刪除成功"
            }

        # Renamed from get_all_crawlers
        def find_all_crawlers(self, **kwargs): # 忽略 limit, offset 等參數
            all_crawlers = list(self.crawlers.values())
            return {
                'success': True,
                'message': "獲取爬蟲設定列表成功",
                'crawlers': all_crawlers # 返回模擬 Schema 物件列表
            }

        # Renamed from get_active_crawlers
        def find_active_crawlers(self, **kwargs): # 忽略 limit, offset 等參數
            active = [c for c in self.crawlers.values() if c.is_active]
            message = "獲取活動中的爬蟲設定成功" if active else "找不到任何活動中的爬蟲設定"
            return {
                'success': True, # 即使找不到也算成功
                'message': message,
                'crawlers': active # 返回模擬 Schema 物件列表
            }

        def toggle_crawler_status(self, crawler_id):
            if crawler_id not in self.crawlers:
                return {
                    'success': False,
                    'message': f"爬蟲設定不存在，ID={crawler_id}",
                    'crawler': None
                }
            crawler = self.crawlers[crawler_id]
            crawler.is_active = not crawler.is_active
            crawler.updated_at = datetime.now(timezone.utc)
            return {
                'success': True,
                'message': f"成功切換爬蟲狀態，新狀態={crawler.is_active}",
                'crawler': crawler # 返回更新後的模擬 Schema 物件
            }

        # Renamed from get_crawlers_by_name
        def find_crawlers_by_name(self, name, is_active=None, **kwargs): # 忽略 limit, offset 等參數
            matched = [c for c in self.crawlers.values()
                       if name.lower() in c.crawler_name.lower()]
            if is_active is not None:
                 matched = [c for c in matched if c.is_active == is_active]

            message = "獲取爬蟲設定列表成功" if matched else "找不到任何符合條件的爬蟲設定"
            return {
                'success': True,
                'message': message,
                'crawlers': matched # 返回模擬 Schema 物件列表
            }

        # Renamed from get_crawlers_by_type
        def find_crawlers_by_type(self, crawler_type, **kwargs): # 忽略 limit, offset 等參數
            matched = [c for c in self.crawlers.values() if c.crawler_type == crawler_type]
            message = f"獲取類型為 {crawler_type} 的爬蟲設定列表成功" if matched else f"找不到類型為 {crawler_type} 的爬蟲設定"
            return {
                'success': True,
                'message': message,
                'crawlers': matched # 返回模擬 Schema 物件列表
            }

        def get_crawler_by_exact_name(self, crawler_name, **kwargs): # 忽略 preview 參數
            for c in self.crawlers.values():
                if c.crawler_name == crawler_name:
                    return {
                        'success': True,
                        'message': "獲取爬蟲設定成功",
                        'crawler': c # 返回模擬 Schema 物件
                    }
            return {
                'success': False,
                'message': f"找不到名稱為 {crawler_name} 的爬蟲設定",
                'crawler': None
            }

        def create_or_update_crawler(self, crawler_data):
             crawler_id = crawler_data.get('id')
             if crawler_id and crawler_id in self.crawlers:
                 # 更新邏輯 (調用已有的 update)
                 # 移除 id 以符合 update 的輸入預期
                 data_for_update = crawler_data.copy()
                 del data_for_update['id']
                 result = self.update_crawler(crawler_id, data_for_update)
                 if result['success']:
                     result['message'] = "爬蟲設定更新成功" # 可能需要覆蓋 message
                 return result
             elif crawler_id:
                 # ID 存在但無效
                 return {
                     'success': False,
                     'message': f"爬蟲設定不存在，ID={crawler_id}",
                     'crawler': None
                 }
             else:
                 # 創建邏輯 (調用已有的 create)
                 # 移除 id (如果存在且為 None 或空)
                 data_for_create = crawler_data.copy()
                 if 'id' in data_for_create:
                     del data_for_create['id']
                 return self.create_crawler(data_for_create)


        def batch_toggle_crawler_status(self, crawler_ids, active_status):
            success_count = 0
            fail_count = 0
            failed_ids = []
            for cid in crawler_ids:
                if cid in self.crawlers:
                    self.crawlers[cid].is_active = active_status
                    self.crawlers[cid].updated_at = datetime.now(timezone.utc)
                    success_count += 1
                else:
                    fail_count += 1
                    failed_ids.append(cid)

            result_details = {
                'success_count': success_count,
                'fail_count': fail_count,
                'total': len(crawler_ids),
                'failed_ids': failed_ids # 可以選擇性地返回失敗的 ID
            }

            action = "啟用" if active_status else "停用"
            if success_count > 0:
                message = f"批量{action}爬蟲設定完成，成功: {success_count}，失敗: {fail_count}"
                success = True
            else:
                message = f"批量{action}爬蟲設定失敗，所有操作均未成功"
                success = False # 只有當全部失敗時 success 才為 False

            return {
                'success': success,
                'message': message,
                'result': result_details # 將詳細結果放在 'result' 鍵下
            }

        # Renamed from get_filtered_crawlers
        def find_filtered_crawlers(self, filter_criteria, page=1, per_page=10, sort_by=None, sort_desc=False, **kwargs): # 忽略 preview 參數
             # 模擬過濾
             filtered_crawlers = []
             for crawler in self.crawlers.values():
                 match = True
                 for field, value in filter_criteria.items():
                     # 假設只支持簡單的等值過濾
                     if getattr(crawler, field, None) != value:
                         match = False
                         break
                 if match:
                     filtered_crawlers.append(crawler)

             # 模擬排序 (簡單實現，只支持少數欄位)
             if sort_by:
                 try:
                     filtered_crawlers.sort(key=lambda c: getattr(c, sort_by), reverse=sort_desc)
                 except AttributeError:
                     pass # 忽略不支持的排序欄位

             # 模擬分頁
             total = len(filtered_crawlers)
             start = (page - 1) * per_page
             end = start + per_page
             items_on_page = filtered_crawlers[start:end]
             total_pages = (total + per_page - 1) // per_page

             # *** 新增：將 CrawlerMock 物件轉換為字典 ***
             items_as_dicts = [item.model_dump() for item in items_on_page]

             # 創建 PaginatedCrawlerResponse 實例
             # 使用轉換後的字典列表
             paginated_response = PaginatedCrawlerResponse(
                 items=items_as_dicts, # <--- 傳遞字典列表
                 page=page,
                 per_page=per_page,
                 total=total,
                 total_pages=total_pages,
                 has_next=end < total,
                 has_prev=start > 0
             )

             success = True # Service 層即使找不到也返回 True
             message = "獲取爬蟲設定列表成功" if total > 0 else "找不到符合條件的爬蟲設定"

             # 返回符合 Service 結構的字典，data 包含 PaginatedCrawlerResponse 實例
             return {
                 'success': success,
                 'message': message,
                 'data': paginated_response # 返回 PaginatedCrawlerResponse 實例
             }

        # --- 新增：模擬 validate_crawler_data ---
        # 注意：實際 API 不再調用 service.validate_crawler_data
        # 但 Mock Service 內部可能需要它來模擬 Service 的行為
        def validate_crawler_data(self, data: Dict[str, Any], is_update: bool = False) -> Dict[str, Any]:
             """模擬 Service 層的內部驗證觸發"""
             try:
                 # 調用內部模擬驗證
                 validated_data = self._validate_data(data, is_update=is_update)
                 # Service 的 validate_crawler_data 成功時只返回數據本身（如果有的話）
                 # 或者在失敗時拋出異常，這裡我們讓內部方法拋出異常
                 return validated_data # 或者返回 {'success': True, 'data': validated_data}
             except ValidationError as e:
                 # 模擬 Service 層處理驗證錯誤，返回包含錯誤信息的字典
                 # 但實際 Service 的 validate 方法可能直接拋出異常
                 # 為了讓 create/update 的模擬更準確，這裡讓異常冒泡
                 raise e


    mock_service_instance = MockCrawlersService()
    # 使用 lambda 返回同一個實例
    monkeypatch.setattr('src.web.routes.crawler_api.get_crawlers_service', lambda: mock_service_instance)
    return mock_service_instance

class TestCrawlerApiRoutes:
    """測試爬蟲相關的 API 路由 (已更新以匹配新的 API 回應結構)"""

    def test_get_crawlers(self, client, mock_crawlers_service, sample_crawlers_data):
        """測試取得所有爬蟲設定列表"""
        response = client.get('/api/crawlers')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert '獲取爬蟲設定列表成功' in result['message']
        assert isinstance(result['data'], list)
        assert len(result['data']) == len(sample_crawlers_data)

        # 比較第一個爬蟲的內容 (忽略時間)
        assert compare_crawler_dicts(result['data'][0], sample_crawlers_data[0])
        # 檢查時間是否存在且格式大致正確
        assert 'created_at' in result['data'][0]
        assert 'updated_at' in result['data'][0]
        assert compare_datetimes(result['data'][0]['created_at'], sample_crawlers_data[0]['created_at'])

    def test_get_crawlers_empty(self, client, mock_crawlers_service):
        """測試取得爬蟲設定列表為空的情況"""
        mock_crawlers_service.crawlers = {} # 清空模擬數據
        response = client.get('/api/crawlers')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        # 這裡 message 可能會不同，取決於 Service 實現，但 data 應為空列表
        assert result['message'] # 確保有 message
        assert result['data'] == []

    def test_create_crawler(self, client, mock_crawlers_service):
        """測試新增爬蟲設定"""
        new_crawler_data = {
            'crawler_name': 'NewWebCrawler',
            'module_name': 'test_module',
            'base_url': 'https://newsite.com',
            'crawler_type': 'web',
            'config_file_name': 'new_web.json',
            'is_active': False
        }
        response = client.post(
            '/api/crawlers',
            data=json.dumps(new_crawler_data),
            content_type='application/json'
        )
        assert response.status_code == 201 # 確認是 201 Created
        result = json.loads(response.data)

        assert result['success'] is True
        assert '爬蟲設定創建成功' in result['message']
        assert 'crawler' in result
        created_crawler = result['crawler']

        assert created_crawler['crawler_name'] == new_crawler_data['crawler_name']
        assert created_crawler['base_url'] == new_crawler_data['base_url']
        assert created_crawler['is_active'] == new_crawler_data['is_active']
        assert created_crawler['id'] is not None # 應有 ID
        assert 'created_at' in created_crawler
        assert 'updated_at' in created_crawler

        # 驗證 Mock Service 內部狀態
        assert created_crawler['id'] in mock_crawlers_service.crawlers
        assert mock_crawlers_service.crawlers[created_crawler['id']].crawler_name == new_crawler_data['crawler_name']

    def test_create_crawler_validation_error(self, client, mock_crawlers_service):
        """測試新增爬蟲設定時的驗證錯誤 (由 Service 層處理)"""
        invalid_data = {
            'crawler_name': 'IncompleteCrawler',
            'module_name': 'test_module',
            # 缺少 base_url, crawler_type, config_file_name
        }
        response = client.post(
            '/api/crawlers',
            data=json.dumps(invalid_data),
            content_type='application/json'
        )
        assert response.status_code == 400 # Service 驗證失敗應返回 400
        result = json.loads(response.data)

        assert result['success'] is False
        assert '缺少必要欄位' in result['message'] # 檢查 Service 返回的錯誤訊息
        # 這裡不再檢查 details 或特定欄位，因為 Service 的錯誤訊息格式可能變化
        assert result.get('crawler') is None # 確保沒有返回 crawler 物件

    def test_get_crawler_by_id(self, client, mock_crawlers_service, sample_crawlers_data):
        """測試通過 ID 取得特定爬蟲設定"""
        target_id = 1
        target_crawler_data = sample_crawlers_data[0]

        response = client.get(f'/api/crawlers/{target_id}')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert '獲取爬蟲設定成功' in result['message']
        assert 'crawler' in result
        fetched_crawler = result['crawler']

        assert fetched_crawler['id'] == target_id
        assert compare_crawler_dicts(fetched_crawler, target_crawler_data)
        assert compare_datetimes(fetched_crawler['created_at'], target_crawler_data['created_at'])

    def test_get_crawler_not_found(self, client, mock_crawlers_service):
        """測試取得不存在的爬蟲設定"""
        non_existent_id = 999
        response = client.get(f'/api/crawlers/{non_existent_id}')
        assert response.status_code == 404
        result = json.loads(response.data)

        assert result['success'] is False
        assert '不存在' in result['message'] # 檢查 Service 返回的錯誤訊息
        assert result.get('crawler') is None

    def test_update_crawler(self, client, mock_crawlers_service):
        """測試更新爬蟲設定"""
        target_id = 1
        update_data = {
            'crawler_name': 'UpdatedCrawlerName',
            'base_url': 'https://updated.example.com',
            'is_active': False
        }
        response = client.put(
            f'/api/crawlers/{target_id}',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert '爬蟲設定更新成功' in result['message']
        assert 'crawler' in result
        updated_crawler = result['crawler']

        assert updated_crawler['id'] == target_id
        assert updated_crawler['crawler_name'] == update_data['crawler_name']
        assert updated_crawler['base_url'] == update_data['base_url']
        assert updated_crawler['is_active'] == update_data['is_active']
        # 驗證 updated_at 是否已更新
        original_crawler = mock_crawlers_service.crawlers[target_id] # 獲取更新後的 Mock 物件
        assert updated_crawler['updated_at'] != original_crawler.created_at.isoformat()
        # 比較 updated_at 與當前時間
        assert compare_datetimes(updated_crawler['updated_at'], datetime.now(timezone.utc))

        # 驗證 Mock Service 內部狀態
        assert mock_crawlers_service.crawlers[target_id].crawler_name == update_data['crawler_name']
        assert mock_crawlers_service.crawlers[target_id].is_active == update_data['is_active']

    def test_update_crawler_not_found(self, client, mock_crawlers_service):
        """測試更新不存在的爬蟲設定"""
        non_existent_id = 999
        update_data = {'crawler_name': 'GhostCrawler'}
        response = client.put(
            f'/api/crawlers/{non_existent_id}',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        assert response.status_code == 404
        result = json.loads(response.data)
        assert result['success'] is False
        assert '不存在' in result['message']

    def test_delete_crawler(self, client, mock_crawlers_service):
        """測試刪除爬蟲設定"""
        target_id = 1
        assert target_id in mock_crawlers_service.crawlers # 確認開始時存在

        response = client.delete(f'/api/crawlers/{target_id}')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert '刪除成功' in result['message']

        # 驗證 Mock Service 內部狀態
        assert target_id not in mock_crawlers_service.crawlers

    def test_delete_crawler_not_found(self, client, mock_crawlers_service):
        """測試刪除不存在的爬蟲設定"""
        non_existent_id = 999
        response = client.delete(f'/api/crawlers/{non_existent_id}')
        assert response.status_code == 404
        result = json.loads(response.data)

        assert result['success'] is False
        assert '不存在' in result['message']

    def test_get_available_crawler_types(self, client):
        """測試取得可用的爬蟲類型"""
        # 模擬 CrawlerFactory 的類方法
        mock_types = [
            {'name': 'BnextCrawler', 'description': 'Bnext 網站爬蟲'},
            {'name': 'NewsCrawler', 'description': '新聞網站爬蟲'}
        ]
        with patch('src.crawlers.crawler_factory.CrawlerFactory.list_available_crawler_types', return_value=mock_types) as mock_list_types:
            response = client.get('/api/crawlers/types')
            assert response.status_code == 200
            result = json.loads(response.data)

            assert result['success'] is True
            assert '成功獲取可用的爬蟲類型列表' in result['message']
            assert result['data'] == mock_types
            mock_list_types.assert_called_once()

    def test_get_available_crawler_types_empty(self, client):
        """測試取得可用的爬蟲類型為空"""
        with patch('src.crawlers.crawler_factory.CrawlerFactory.list_available_crawler_types', return_value=[]) as mock_list_types:
             response = client.get('/api/crawlers/types')
             assert response.status_code == 404 # API 應返回 404
             result = json.loads(response.data)
             assert result['success'] is False
             assert '找不到任何可用的爬蟲類型' in result['message']
             mock_list_types.assert_called_once()


    def test_get_active_crawlers(self, client, mock_crawlers_service, sample_crawlers_data):
        """測試取得所有活動中的爬蟲設定"""
        response = client.get('/api/crawlers/active')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert '獲取活動中的爬蟲設定成功' in result['message']
        assert 'data' in result
        active_crawlers_result = result['data']

        expected_active = [c for c in sample_crawlers_data if c['is_active']]
        assert len(active_crawlers_result) == len(expected_active)
        # 檢查第一個活動爬蟲的內容
        assert compare_crawler_dicts(active_crawlers_result[0], expected_active[0])

    def test_get_active_crawlers_empty(self, client, mock_crawlers_service):
         """測試沒有活動爬蟲的情況"""
         # 將所有爬蟲設為非活動
         for crawler in mock_crawlers_service.crawlers.values():
             crawler.is_active = False

         response = client.get('/api/crawlers/active')
         assert response.status_code == 200 # API 仍然返回 200
         result = json.loads(response.data)

         assert result['success'] is True
         assert '找不到任何活動中的爬蟲設定' in result['message'] # Service 應返回此訊息
         assert result['data'] == []

    def test_toggle_crawler_status(self, client, mock_crawlers_service):
        """測試切換爬蟲活躍狀態"""
        target_id = 1
        original_crawler_mock = mock_crawlers_service.crawlers[target_id]
        original_status = original_crawler_mock.is_active

        response = client.post(f'/api/crawlers/{target_id}/toggle')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert f"成功切換爬蟲狀態，新狀態={not original_status}" in result['message']
        assert 'crawler' in result
        toggled_crawler = result['crawler']

        assert toggled_crawler['id'] == target_id
        assert toggled_crawler['is_active'] == (not original_status)
        # 驗證 updated_at 是否更新
        assert toggled_crawler['updated_at'] != original_crawler_mock.created_at.isoformat()
        assert compare_datetimes(toggled_crawler['updated_at'], datetime.now(timezone.utc))

        # 驗證 Mock Service 內部狀態
        assert mock_crawlers_service.crawlers[target_id].is_active == (not original_status)

    def test_toggle_crawler_status_not_found(self, client, mock_crawlers_service):
        """測試切換不存在的爬蟲狀態"""
        non_existent_id = 999
        response = client.post(f'/api/crawlers/{non_existent_id}/toggle')
        assert response.status_code == 404
        result = json.loads(response.data)
        assert result['success'] is False
        assert '不存在' in result['message']

    def test_get_crawlers_by_name(self, client, mock_crawlers_service, sample_crawlers_data):
        """測試根據名稱模糊查詢爬蟲設定"""
        search_name = "TestCrawler"
        response = client.get(f'/api/crawlers/name/{search_name}')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert '獲取爬蟲設定列表成功' in result['message']
        assert 'data' in result
        found_crawlers = result['data']

        expected_found = [c for c in sample_crawlers_data if search_name.lower() in c['crawler_name'].lower()]
        assert len(found_crawlers) == len(expected_found)
        # 可以選擇性地比較第一個找到的內容
        if expected_found:
             assert compare_crawler_dicts(found_crawlers[0], expected_found[0])

    def test_get_crawlers_by_name_not_found(self, client, mock_crawlers_service):
        """測試根據名稱模糊查詢找不到結果"""
        search_name = "NonExistentName"
        response = client.get(f'/api/crawlers/name/{search_name}')
        assert response.status_code == 200 # API 仍然返回 200
        result = json.loads(response.data)

        assert result['success'] is True # Service 認為操作成功，只是沒結果
        assert '找不到任何符合條件的爬蟲設定' in result['message']
        assert result['data'] == []

    def test_get_crawlers_by_type(self, client, mock_crawlers_service, sample_crawlers_data):
        """測試根據爬蟲類型查找爬蟲"""
        search_type = "web"
        response = client.get(f'/api/crawlers/type/{search_type}')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert f"獲取類型為 {search_type} 的爬蟲設定列表成功" in result['message']
        assert 'data' in result
        found_crawlers = result['data']

        expected_found = [c for c in sample_crawlers_data if c['crawler_type'] == search_type]
        assert len(found_crawlers) == len(expected_found)
        assert all(c['crawler_type'] == search_type for c in found_crawlers)

    def test_get_crawlers_by_type_not_found(self, client, mock_crawlers_service):
        """測試根據爬蟲類型找不到結果"""
        search_type = "non_existent_type"
        response = client.get(f'/api/crawlers/type/{search_type}')
        assert response.status_code == 200 # API 仍然返回 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert f"找不到類型為 {search_type} 的爬蟲設定" in result['message']
        assert result['data'] == []

    def test_get_crawler_by_exact_name(self, client, mock_crawlers_service, sample_crawlers_data):
        """測試根據爬蟲名稱精確查詢"""
        target_name = "TestCrawler1"
        target_crawler_data = sample_crawlers_data[0]
        response = client.get(f'/api/crawlers/exact-name/{target_name}')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert '獲取爬蟲設定成功' in result['message']
        assert 'crawler' in result
        fetched_crawler = result['crawler']
        assert compare_crawler_dicts(fetched_crawler, target_crawler_data)

    def test_get_crawler_by_exact_name_not_found(self, client, mock_crawlers_service):
        """測試根據爬蟲名稱精確查詢找不到"""
        target_name = "NonExistentExactName"
        response = client.get(f'/api/crawlers/exact-name/{target_name}')
        assert response.status_code == 404
        result = json.loads(response.data)
        assert result['success'] is False
        assert f"找不到名稱為 {target_name} 的爬蟲設定" in result['message']

    def test_create_or_update_crawler_create(self, client, mock_crawlers_service):
        """測試 create_or_update 創建新爬蟲"""
        new_data = {
            'crawler_name': 'CreateOrUpdateNew',
            'base_url': 'https://cou-new.com',
            'crawler_type': 'rss',
            'config_file_name': 'cou_new.json'
        }
        response = client.post(
            '/api/crawlers/create-or-update',
            data=json.dumps(new_data),
            content_type='application/json'
        )
        assert response.status_code == 201 # 創建應返回 201
        result = json.loads(response.data)
        assert result['success'] is True
        assert '爬蟲設定創建成功' in result['message']
        assert 'crawler' in result
        created_crawler = result['crawler']
        assert created_crawler['crawler_name'] == new_data['crawler_name']
        assert created_crawler['id'] is not None

        # 驗證內部狀態
        assert created_crawler['id'] in mock_crawlers_service.crawlers

    def test_create_or_update_crawler_update(self, client, mock_crawlers_service):
        """測試 create_or_update 更新現有爬蟲"""
        target_id = 2
        update_data = {
            'id': target_id, # 提供 ID
            'crawler_name': 'CreateOrUpdateUpdated',
            'is_active': True # 原本是 False
        }
        response = client.post(
            '/api/crawlers/create-or-update',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        assert response.status_code == 200 # 更新應返回 200
        result = json.loads(response.data)
        assert result['success'] is True
        assert '爬蟲設定更新成功' in result['message']
        assert 'crawler' in result
        updated_crawler = result['crawler']
        assert updated_crawler['id'] == target_id
        assert updated_crawler['crawler_name'] == update_data['crawler_name']
        assert updated_crawler['is_active'] == update_data['is_active']

        # 驗證內部狀態
        assert mock_crawlers_service.crawlers[target_id].crawler_name == update_data['crawler_name']
        assert mock_crawlers_service.crawlers[target_id].is_active == update_data['is_active']

    def test_create_or_update_crawler_update_invalid_id(self, client, mock_crawlers_service):
         """測試 create_or_update 更新不存在的 ID"""
         update_data = {'id': 999, 'crawler_name': 'InvalidUpdate'}
         response = client.post(
             '/api/crawlers/create-or-update',
             data=json.dumps(update_data),
             content_type='application/json'
         )
         assert response.status_code == 404 # 應返回 404
         result = json.loads(response.data)
         assert result['success'] is False
         assert '不存在' in result['message']


    def test_batch_toggle_crawler_status(self, client, mock_crawlers_service):
        """測試批量設置爬蟲的活躍狀態 (全部成功)"""
        ids_to_toggle = [1, 2] # 原本 1:True, 2:False
        target_status = False
        response = client.post(
            '/api/crawlers/batch-toggle',
            data=json.dumps({'crawler_ids': ids_to_toggle, 'active_status': target_status}),
            content_type='application/json'
        )
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert '批量停用爬蟲設定完成' in result['message'] # 根據 target_status 調整
        assert 'result' in result
        batch_result = result['result']
        assert batch_result['success_count'] == len(ids_to_toggle)
        assert batch_result['fail_count'] == 0
        assert batch_result['total'] == len(ids_to_toggle)

        # 驗證內部狀態
        for cid in ids_to_toggle:
            assert mock_crawlers_service.crawlers[cid].is_active == target_status

    def test_batch_toggle_crawler_status_partial_fail(self, client, mock_crawlers_service):
        """測試批量設置爬蟲的活躍狀態 (部分失敗)"""
        ids_to_toggle = [1, 999] # 1 存在, 999 不存在
        target_status = True
        response = client.post(
            '/api/crawlers/batch-toggle',
            data=json.dumps({'crawler_ids': ids_to_toggle, 'active_status': target_status}),
            content_type='application/json'
        )
        assert response.status_code == 200 # 即使部分失敗也應返回 200
        result = json.loads(response.data)

        assert result['success'] is True # Service 認為只要有成功就算成功
        assert '批量啟用爬蟲設定完成' in result['message']
        assert '成功: 1' in result['message']
        assert '失敗: 1' in result['message']
        assert 'result' in result
        batch_result = result['result']
        assert batch_result['success_count'] == 1
        assert batch_result['fail_count'] == 1
        assert batch_result['total'] == 2

        # 驗證內部狀態
        assert mock_crawlers_service.crawlers[1].is_active == target_status

    def test_batch_toggle_crawler_status_all_fail(self, client, mock_crawlers_service):
        """測試批量設置爬蟲的活躍狀態 (全部失敗)"""
        ids_to_toggle = [998, 999] # 都不存在
        target_status = True
        response = client.post(
            '/api/crawlers/batch-toggle',
            data=json.dumps({'crawler_ids': ids_to_toggle, 'active_status': target_status}),
            content_type='application/json'
        )
        # API 返回 400 或 500 取決於 Service 的實現，這裡假設 400
        assert response.status_code == 400
        result = json.loads(response.data)

        assert result['success'] is False # Service 返回 False
        assert '批量啟用爬蟲設定失敗，所有操作均未成功' in result['message']
        assert 'result' in result
        batch_result = result['result']
        assert batch_result['success_count'] == 0
        assert batch_result['fail_count'] == 2
        assert batch_result['total'] == 2


    def test_get_filtered_crawlers(self, client, mock_crawlers_service, sample_crawlers_data):
        """測試根據過濾條件獲取分頁爬蟲列表"""
        filter_data = {
            'filter': {'crawler_type': 'web'},
            'page': 1,
            'per_page': 1 # 每頁 1 個，測試分頁
        }
        response = client.post(
            '/api/crawlers/filter',
            data=json.dumps(filter_data),
            content_type='application/json'
        )
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert '獲取爬蟲設定列表成功' in result['message']
        assert 'data' in result
        paginated_data = result['data']

        assert paginated_data['page'] == filter_data['page']
        assert paginated_data['per_page'] == filter_data['per_page']
        assert isinstance(paginated_data['items'], list)
        assert len(paginated_data['items']) == 1 # 因為 per_page=1

        # 找出預期的 web 類型爬蟲
        expected_items = [c for c in sample_crawlers_data if c['crawler_type'] == 'web']
        assert paginated_data['total'] == len(expected_items)
        assert paginated_data['total_pages'] == len(expected_items)
        assert paginated_data['has_next'] is True
        assert paginated_data['has_prev'] is False

        # 比較返回的第一項
        # 現在 paginated_data['items'][0]['created_at'] 應該是 ISO 字串
        assert compare_crawler_dicts(paginated_data['items'][0], expected_items[0])
        # compare_datetimes 
        assert compare_datetimes(paginated_data['items'][0]['created_at'], expected_items[0]['created_at'])

    def test_get_filtered_crawlers_not_found(self, client, mock_crawlers_service):
        """測試根據過濾條件找不到結果"""
        filter_data = {
            'filter': {'crawler_type': 'non_existent'}
        }
        response = client.post(
            '/api/crawlers/filter',
            data=json.dumps(filter_data),
            content_type='application/json'
        )
        assert response.status_code == 200 # API 仍然返回 200
        result = json.loads(response.data)

        assert result['success'] is True # Service 返回 True
        assert '找不到符合條件的爬蟲設定' in result['message'] # Service 應返回此訊息
        assert 'data' in result
        paginated_data = result['data']
        assert paginated_data['items'] == []
        assert paginated_data['total'] == 0
        assert paginated_data['page'] == 1 # 預設頁碼
        assert paginated_data['per_page'] == 10 # 預設每頁數量
        assert paginated_data['total_pages'] == 0
        assert paginated_data['has_next'] is False
        assert paginated_data['has_prev'] is False 