"""測試爬蟲 API 路由 (/api/crawlers) 的功能。"""
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from unittest.mock import patch, MagicMock
import io

import pytest
from flask import Flask, jsonify
from werkzeug.datastructures import FileStorage # <-- Import FileStorage for type checking

from src.error.errors import ValidationError
from src.models.crawlers_schema import PaginatedCrawlerResponse, CrawlerReadSchema
from src.utils.log_utils import LoggerSetup  # 使用統一的 logger
from src.web.routes.crawler_api import crawler_bp

# flake8: noqa: F811
# pylint: disable=redefined-outer-name

logger = LoggerSetup.setup_logger(__name__)  # 使用統一的 logger

# 輔助函數：比較字典（忽略時間精度和模擬配置內容）
def compare_crawler_dicts(dict1, dict2, ignore_keys=['created_at', 'updated_at', 'config_content']):
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
    def __init__(self, data, config_content=None):
        self.id = data.get('id')
        self.crawler_name = data.get('crawler_name')
        self.module_name = data.get('module_name')
        self.base_url = data.get('base_url')
        self.crawler_type = data.get('crawler_type')
        self.config_file_name = data.get('config_file_name')
        self.is_active = data.get('is_active', True)
        # 確保時間是 timezone-aware UTC
        created_at_val = data.get('created_at', datetime.now(timezone.utc))
        self.created_at = created_at_val.replace(tzinfo=timezone.utc) if created_at_val and created_at_val.tzinfo is None else created_at_val

        updated_at_val = data.get('updated_at', datetime.now(timezone.utc))
        self.updated_at = updated_at_val.replace(tzinfo=timezone.utc) if updated_at_val and updated_at_val.tzinfo is None else updated_at_val
        self.config_content = config_content

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
            'created_at': now, 'updated_at': now,
            'config_content': {"key1": "value1"}
        },
        {
            'id': 2, 'crawler_name': 'TestCrawler2', 'module_name': 'test_module', 'base_url': 'https://example2.com',
            'crawler_type': 'web', 'config_file_name': 'test2.json', 'is_active': False,
            'created_at': now, 'updated_at': now,
            'config_content': {"key2": "value2"}
        },
        {
            'id': 3, 'crawler_name': 'TestCrawler3', 'module_name': 'test_module', 'base_url': 'https://example3.com',
            'crawler_type': 'rss', 'config_file_name': 'test3.json', 'is_active': True,
            'created_at': now, 'updated_at': now,
            'config_content': None
        }
    ]

@pytest.fixture
def mock_crawlers_service(monkeypatch, sample_crawlers_data):
    """模擬 CrawlersService，使其回傳值符合實際 Service 的結構"""
    class MockCrawlersService:
        def __init__(self):
            # 儲存 CrawlerMock 對象，包含配置內容
            self.crawlers = {c['id']: CrawlerMock(c, c.get('config_content')) for c in sample_crawlers_data}
            self.next_id = max(self.crawlers.keys()) + 1 if self.crawlers else 1
            self.call_history = {}

        def _record_call(self, method_name, *args, **kwargs):
            """記錄方法呼叫的參數，特殊處理檔案物件"""
            processed_args = []
            for arg in args:
                if isinstance(arg, (io.IOBase, FileStorage)):
                    filename = getattr(arg, 'filename', None)
                    try:
                        arg.seek(0)
                        content = arg.read()
                        try:
                            # 嘗試解析為 JSON 字典
                            parsed_content = json.loads(content.decode('utf-8'))
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            # 如果失敗，嘗試直接解碼字串 (適用於非 JSON 但可讀的)
                            try:
                                parsed_content = content.decode('utf-8')
                            except UnicodeDecodeError:
                                # 最後儲存原始 bytes
                                parsed_content = content
                        processed_args.append({'filename': filename, 'content': parsed_content, '_type': 'file'})
                    except Exception as e:
                        logger.error(f"處理 mock 檔案參數時出錯: {e}")
                        processed_args.append({'filename': filename, 'error': str(e), '_type': 'file'})
                else:
                    processed_args.append(arg)

            # 處理 kwargs 中的檔案
            processed_kwargs = {}
            for key, value in kwargs.items():
                if isinstance(value, (io.IOBase, FileStorage)):
                    filename = getattr(value, 'filename', None)
                    try:
                        value.seek(0)
                        content = value.read()
                        try:
                            parsed_content = json.loads(content.decode('utf-8'))
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            try:
                                parsed_content = content.decode('utf-8')
                            except UnicodeDecodeError:
                                parsed_content = content
                        processed_kwargs[key] = {'filename': filename, 'content': parsed_content, '_type': 'file'}
                    except Exception as e:
                         logger.error(f"處理 mock 檔案參數時出錯: {e}")
                         processed_kwargs[key] = {'filename': filename, 'error': str(e), '_type': 'file'}
                else:
                     processed_kwargs[key] = value

            if method_name not in self.call_history:
                self.call_history[method_name] = []
            self.call_history[method_name].append({'args': tuple(processed_args), 'kwargs': processed_kwargs})

        def assert_called_once_with(self, method_name, *args, **kwargs):
             """模擬 mock.assert_called_once_with，能比較包含檔案內容的記錄"""
             assert method_name in self.call_history, f"方法 {method_name} 從未被呼叫"
             assert len(self.call_history[method_name]) == 1, f"方法 {method_name} 被呼叫了 {len(self.call_history[method_name])} 次，預期 1 次"

             recorded_call = self.call_history[method_name][0]
             recorded_args = recorded_call['args']
             recorded_kwargs = recorded_call['kwargs']

             # 比較位置參數
             assert len(recorded_args) == len(args), f"位置參數數量不匹配：預期 {len(args)}，實際 {len(recorded_args)}"
             for i, expected_arg in enumerate(args):
                 recorded_arg = recorded_args[i]

                 # --- 修改：簡化比較邏輯 ---
                 if isinstance(recorded_arg, dict) and recorded_arg.get('_type') == 'file':
                     # 如果記錄的是檔案字典，預期也應該是檔案字典
                     assert isinstance(expected_arg, dict), f"位置參數 {i} 類型不匹配：記錄為檔案字典，預期為 {type(expected_arg).__name__}"
                     assert recorded_arg.get('filename') == expected_arg.get('filename'), f"檔案名不匹配 (參數 {i}): 預期 '{expected_arg.get('filename')}', 實際 '{recorded_arg.get('filename')}'"
                     assert recorded_arg.get('content') == expected_arg.get('content'), f"檔案內容不匹配 (參數 {i})"
                     assert '_type' in expected_arg and expected_arg['_type'] == 'file', f"預期的檔案參數 {i} 缺少 '_type' 或值不為 'file'"
                     assert 'error' not in recorded_arg, f"記錄的檔案參數 {i} 包含錯誤: {recorded_arg.get('error')}"
                 else:
                     # 其他類型直接比較
                     assert recorded_arg == expected_arg, f"位置參數 {i} 不匹配：預期 {expected_arg!r}，實際 {recorded_arg!r}"
                 # --- 修改結束 ---

             # 比較關鍵字參數 (假設 kwargs 中不包含檔案)
             assert recorded_kwargs == kwargs, f"關鍵字參數不匹配：預期 {kwargs!r}，實際 {recorded_kwargs!r}"

        def _validate_data(self, data, is_update=False):
            """簡易模擬驗證，實際驗證在 Service 層"""
            # 更新時，欄位可能是可選的，所以移除必填檢查
            # if not is_update:
            #     required = ['crawler_name', 'base_url', 'crawler_type', 'config_file_name'] # 創建時 config_file_name 由 service 生成
            #     missing = [field for field in required if field not in data]
            #     if missing:
            #         field_errors = {f: "此欄位為必填項" for f in missing}
            #         raise ValidationError(f"缺少必要欄位: {', '.join(missing)}：{field_errors}")

            # 可以在此添加更多模擬驗證邏輯，例如檢查類型
            if 'crawler_name' in data and not isinstance(data['crawler_name'], str):
                raise ValidationError("crawler_name 必須是字串")
            if 'is_active' in data and not isinstance(data['is_active'], bool):
                raise ValidationError("is_active 必須是布林值")

            return data

        def create_crawler(self, crawler_data):
            # 這個方法可能不再被直接使用，如果 POST /api/crawlers 總是需要配置檔案
            # 但保留以防萬一
            try:
                validated_data = self._validate_data(crawler_data, is_update=False)
                # 模擬生成 config_file_name
                validated_data['config_file_name'] = f"{validated_data['crawler_name']}.json"

                new_id = self.next_id
                now = datetime.now(timezone.utc)
                full_data = {
                    **validated_data,
                    'id': new_id,
                    'is_active': validated_data.get('is_active', True),
                    'created_at': now,
                    'updated_at': now
                }
                new_crawler = CrawlerMock(full_data) # 創建時 config_content 為 None
                self.crawlers[new_id] = new_crawler
                self.next_id += 1
                return {
                    'success': True,
                    'message': "爬蟲設定創建成功 (無檔案)",
                    'crawler': new_crawler
                }
            except ValidationError as e:
                 return { 'success': False, 'message': f"爬蟲設定資料驗證失敗: {str(e)}", 'crawler': None }
            except Exception as e:
                 logger.error(f"Mock create_crawler error: {e}")
                 return {'success': False, 'message': str(e), 'crawler': None}

        def get_crawler_by_id(self, crawler_id):
            self._record_call('get_crawler_by_id', crawler_id) # 記錄呼叫
            crawler = self.crawlers.get(crawler_id)
            if not crawler:
                return { 'success': False, 'message': f"爬蟲設定不存在，ID={crawler_id}", 'crawler': None }
            return { 'success': True, 'message': "獲取爬蟲設定成功", 'crawler': crawler }

        def delete_crawler(self, crawler_id):
            self._record_call('delete_crawler', crawler_id) # 記錄呼叫
            if crawler_id not in self.crawlers:
                return { 'success': False, 'message': f"爬蟲設定不存在，ID={crawler_id}" }
            del self.crawlers[crawler_id]
            return { 'success': True, 'message': "爬蟲設定刪除成功" }

        def find_all_crawlers(self, **kwargs):
            self._record_call('find_all_crawlers', **kwargs)
            all_crawlers = list(self.crawlers.values())
            return {'success': True, 'message': "獲取爬蟲設定列表成功", 'crawlers': all_crawlers}

        def find_active_crawlers(self, **kwargs):
            self._record_call('find_active_crawlers', **kwargs)
            active = [c for c in self.crawlers.values() if c.is_active]
            message = "獲取活動中的爬蟲設定成功" if active else "找不到任何活動中的爬蟲設定"
            return {'success': True, 'message': message, 'crawlers': active}

        def toggle_crawler_status(self, crawler_id):
            self._record_call('toggle_crawler_status', crawler_id)
            if crawler_id not in self.crawlers:
                return {'success': False, 'message': f"爬蟲設定不存在，ID={crawler_id}", 'crawler': None}
            crawler = self.crawlers[crawler_id]
            crawler.is_active = not crawler.is_active
            crawler.updated_at = datetime.now(timezone.utc)
            return {'success': True, 'message': f"成功切換爬蟲狀態，新狀態={crawler.is_active}", 'crawler': crawler}

        def find_crawlers_by_name(self, name, is_active=None, **kwargs):
            self._record_call('find_crawlers_by_name', name, is_active=is_active, **kwargs)
            matched = [c for c in self.crawlers.values() if name.lower() in c.crawler_name.lower()]
            if is_active is not None:
                 matched = [c for c in matched if c.is_active == is_active]
            message = "獲取爬蟲設定列表成功" if matched else "找不到任何符合條件的爬蟲設定"
            return {'success': True, 'message': message, 'crawlers': matched}

        def find_crawlers_by_type(self, crawler_type, **kwargs):
            self._record_call('find_crawlers_by_type', crawler_type, **kwargs)
            matched = [c for c in self.crawlers.values() if c.crawler_type == crawler_type]
            message = f"獲取類型為 {crawler_type} 的爬蟲設定列表成功" if matched else f"找不到類型為 {crawler_type} 的爬蟲設定"
            return {'success': True, 'message': message, 'crawlers': matched}

        def get_crawler_by_exact_name(self, crawler_name, **kwargs):
            self._record_call('get_crawler_by_exact_name', crawler_name, **kwargs)
            for c in self.crawlers.values():
                if c.crawler_name == crawler_name:
                    return {'success': True, 'message': "獲取爬蟲設定成功", 'crawler': c}
            return {'success': False, 'message': f"找不到名稱為 {crawler_name} 的爬蟲設定", 'crawler': None}

        def create_or_update_crawler(self, crawler_data):
             # 這個方法現在可能與 PUT /<id> 的 multipart 形式衝突
             # 保持原樣，但測試應優先使用新的 multipart 端點
             self._record_call('create_or_update_crawler', crawler_data)
             crawler_id = crawler_data.get('id')
             if crawler_id and crawler_id in self.crawlers:
                 # 更新邏輯 - 但沒有檔案處理
                 data_for_update = crawler_data.copy()
                 del data_for_update['id']
                 try:
                    validated_data = self._validate_data(data_for_update, is_update=True)
                    crawler = self.crawlers[crawler_id]
                    now = datetime.now(timezone.utc)
                    for key, value in validated_data.items():
                         if hasattr(crawler, key) and key != 'id':
                             setattr(crawler, key, value)
                    crawler.updated_at = now
                    return {'success': True, 'message': "爬蟲設定更新成功 (無檔案)", 'crawler': crawler}
                 except ValidationError as e:
                    return {'success': False, 'message': f"爬蟲設定更新資料驗證失敗: {str(e)}", 'crawler': None}
             elif crawler_id:
                 return {'success': False, 'message': f"爬蟲設定不存在，ID={crawler_id}", 'crawler': None}
             else:
                 # 創建邏輯 - 但沒有檔案處理
                 data_for_create = crawler_data.copy()
                 if 'id' in data_for_create:
                     del data_for_create['id']
                 return self.create_crawler(data_for_create) # 調用無檔案的創建

        def batch_toggle_crawler_status(self, crawler_ids, active_status):
            self._record_call('batch_toggle_crawler_status', crawler_ids, active_status)
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
            result_details = {'success_count': success_count, 'fail_count': fail_count, 'total': len(crawler_ids), 'failed_ids': failed_ids}
            action = "啟用" if active_status else "停用"
            if success_count > 0:
                message = f"批量{action}爬蟲設定完成，成功: {success_count}，失敗: {fail_count}"
                success = True
            else:
                message = f"批量{action}爬蟲設定失敗，所有操作均未成功"
                success = False
            return {'success': success, 'message': message, 'result': result_details}

        def find_filtered_crawlers(self, filter_criteria, page=1, per_page=10, sort_by=None, sort_desc=False, **kwargs):
            self._record_call('find_filtered_crawlers', filter_criteria, page=page, per_page=per_page, sort_by=sort_by, sort_desc=sort_desc, **kwargs)
            filtered_crawlers = []
            for crawler in self.crawlers.values():
                 match = True
                 for field, value in filter_criteria.items():
                     if getattr(crawler, field, None) != value:
                         match = False
                         break
                 if match:
                     filtered_crawlers.append(crawler)
            if sort_by:
                 try: filtered_crawlers.sort(key=lambda c: getattr(c, sort_by), reverse=sort_desc)
                 except AttributeError: pass
            total = len(filtered_crawlers)
            start = (page - 1) * per_page
            end = start + per_page
            items_on_page = filtered_crawlers[start:end]
            total_pages = (total + per_page - 1) // per_page
            items_as_dicts = [item.model_dump() for item in items_on_page]
            paginated_response = PaginatedCrawlerResponse(
                 items=items_as_dicts, page=page, per_page=per_page, total=total,
                 total_pages=total_pages, has_next=end < total, has_prev=start > 0
            )
            success = True
            message = "獲取爬蟲設定列表成功" if total > 0 else "找不到符合條件的爬蟲設定"
            return {'success': success, 'message': message, 'data': paginated_response}

        def validate_crawler_data(self, data: Dict[str, Any], is_update: bool = False) -> Dict[str, Any]:
             self._record_call('validate_crawler_data', data, is_update=is_update)
             try:
                 validated_data = self._validate_data(data, is_update=is_update)
                 return validated_data
             except ValidationError as e:
                 raise e

        def create_crawler_with_config(self, crawler_data, config_file):
            """模擬 create_crawler_with_config 方法"""
            self._record_call('create_crawler_with_config', crawler_data, config_file)
            try:
                validated_data = self._validate_data(crawler_data, is_update=False)

                # 模擬基本的檔案讀取和內容儲存
                config_content_dict = None
                try:
                    config_file.seek(0)
                    config_content_bytes = config_file.read()
                    config_content_dict = json.loads(config_content_bytes.decode('utf-8'))
                    # 模擬服務層可能做的檢查
                    if not isinstance(config_content_dict.get('selectors'), dict):
                         raise ValidationError("模擬配置檔案缺少 selectors 或格式錯誤")
                except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as e:
                    # 模擬服務處理檔案或驗證失敗的情況
                    return {'success': False, 'message': f"配置檔案格式錯誤或驗證失敗: {e}"}
                except AttributeError: # 如果傳入的不是 file-like object
                     return {'success': False, 'message': "傳遞的 config_file 無效"}

                # 模擬資料庫創建
                new_id = self.next_id
                now = datetime.now(timezone.utc)
                # 模擬 Service 層生成檔名
                expected_filename = f"{validated_data['crawler_name']}.json"

                full_data = {
                    **validated_data,
                    'id': new_id,
                    'is_active': validated_data.get('is_active', True),
                    'config_file_name': expected_filename, # Service 生成
                    'created_at': now,
                    'updated_at': now
                }
                new_crawler = CrawlerMock(full_data, config_content=config_content_dict) # 儲存配置內容
                self.crawlers[new_id] = new_crawler
                self.next_id += 1

                return {'success': True, 'message': '爬蟲設定及配置檔案創建成功', 'crawler': new_crawler}
            except ValidationError as e:
                 return {'success': False, 'message': f"爬蟲設定資料驗證失敗: {str(e)}", 'crawler': None}
            except Exception as e:
                 logger.error(f"Mock create_crawler_with_config error: {e}", exc_info=True)
                 return {'success': False, 'message': str(e), 'crawler': None}

        def update_crawler_with_config(self, crawler_id, crawler_data, config_file=None):
             """模擬 update_crawler_with_config 方法"""
             # 記錄呼叫，包括可能的檔案
             self._record_call('update_crawler_with_config', crawler_id, crawler_data, config_file)

             if crawler_id not in self.crawlers:
                 return {'success': False, 'message': f"爬蟲設定不存在，ID={crawler_id}", 'crawler': None}

             try:
                 # 模擬 Service 內部的資料驗證
                 validated_data = self._validate_data(crawler_data, is_update=True)

                 crawler = self.crawlers[crawler_id]
                 now = datetime.now(timezone.utc)
                 new_config_content = None # 用於儲存新檔案內容

                 # 處理配置檔案更新
                 if config_file and config_file.filename: # 確保有檔案且檔名有效
                     try:
                         config_file.seek(0)
                         config_content_bytes = config_file.read()
                         new_config_content = json.loads(config_content_bytes.decode('utf-8'))
                         # 模擬 Service 層可能做的檢查
                         if not isinstance(new_config_content.get('selectors'), dict):
                             raise ValidationError("模擬配置檔案缺少 selectors 或格式錯誤")
                         # 模擬 Service 層更新檔名 (如果需要)
                         new_filename = f"{validated_data.get('crawler_name', crawler.crawler_name)}.json"
                         if crawler.config_file_name != new_filename:
                              logger.info(f"Mock: Config filename changed from {crawler.config_file_name} to {new_filename}")
                              crawler.config_file_name = new_filename
                     except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as e:
                         return {'success': False, 'message': f"新配置檔案格式錯誤或驗證失敗: {e}", 'crawler': None}
                     except AttributeError:
                          return {'success': False, 'message': "傳遞的 config_file 無效"}

                 # 更新爬蟲資料
                 for key, value in validated_data.items():
                     if hasattr(crawler, key) and key not in ['id', 'created_at']: # 不更新 id, created_at
                         setattr(crawler, key, value)
                 crawler.updated_at = now

                 # 如果有新配置，更新 Mock 物件的內容
                 if new_config_content is not None:
                     crawler.config_content = new_config_content

                 return {'success': True, 'message': "爬蟲設定及配置檔案更新成功", 'crawler': crawler}
             except ValidationError as e:
                 return {'success': False, 'message': f"爬蟲設定更新資料驗證失敗: {str(e)}", 'crawler': None}
             except Exception as e:
                  logger.error(f"Mock update_crawler_with_config error: {e}", exc_info=True)
                  return {'success': False, 'message': str(e), 'crawler': None}

        def get_crawler_config(self, crawler_id):
             """模擬獲取爬蟲配置檔案內容"""
             self._record_call('get_crawler_config', crawler_id)
             if crawler_id not in self.crawlers:
                  return {'success': False, 'message': f"爬蟲設定不存在，ID={crawler_id}", 'config': None}

             crawler = self.crawlers[crawler_id]
             if crawler.config_content is None:
                  # 模擬檔案實際不存在或讀取失敗
                  return {'success': False, 'message': f"找不到爬蟲 '{crawler.crawler_name}' 的配置檔案或無法讀取", 'config': None}

             # 模擬成功讀取到內容
             return {
                 'success': True,
                 'message': "獲取爬蟲配置成功",
                 'config': crawler.config_content # 返回之前儲存的字典
             }


    mock_service_instance = MockCrawlersService()
    monkeypatch.setattr('src.web.routes.crawler_api.get_crawlers_service', lambda: mock_service_instance)
    return mock_service_instance

class TestCrawlerApiRoutes:
    """測試爬蟲相關的 API 路由"""

    def test_get_crawlers(self, client, mock_crawlers_service, sample_crawlers_data):
        """測試取得所有爬蟲設定列表"""
        response = client.get('/api/crawlers')
        assert response.status_code == 200
        result = json.loads(response.data)

        assert result['success'] is True
        assert '獲取爬蟲設定列表成功' in result['message']
        assert isinstance(result['data'], list)
        assert len(result['data']) == len(sample_crawlers_data)
        assert compare_crawler_dicts(result['data'][0], sample_crawlers_data[0])
        assert compare_datetimes(result['data'][0]['created_at'], sample_crawlers_data[0]['created_at'])

    def test_get_crawlers_empty(self, client, mock_crawlers_service):
        """測試取得爬蟲設定列表為空的情況"""
        mock_crawlers_service.crawlers = {}
        response = client.get('/api/crawlers')
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result['success'] is True
        assert result['message']
        assert result['data'] == []

    def test_create_crawler_with_config(self, client, mock_crawlers_service):
        """測試使用配置檔案新增爬蟲設定 (multipart/form-data)"""
        crawler_data = {
            'crawler_name': 'NewConfigCrawler',
            'module_name': 'config_module',
            'base_url': 'https://configsite.com',
            'crawler_type': 'config_type',
            'is_active': True
        }
        config_file_content = {
            "name": "config_test", "selectors": { "key": "value" }
        }
        # 傳遞 BytesIO 和檔名
        config_file_tuple = (
            io.BytesIO(json.dumps(config_file_content).encode('utf-8')),
            'test_config.json'
        )
        data = {
            'crawler_data': json.dumps(crawler_data),
            'config_file': config_file_tuple
        }

        response = client.post('/api/crawlers', data=data, content_type='multipart/form-data') # 指定 content_type

        assert response.status_code == 201, f"預期 201，收到 {response.status_code}. 回應: {response.data.decode()}"
        response_data = response.get_json()
        assert response_data['success'] is True
        assert response_data['message'] == '爬蟲設定及配置檔案創建成功'
        created_crawler_resp = response_data['crawler']
        assert created_crawler_resp['crawler_name'] == crawler_data['crawler_name']
        expected_service_filename = f"{crawler_data['crawler_name']}.json"
        assert created_crawler_resp['config_file_name'] == expected_service_filename

        # 驗證 mock 服務呼叫
        try:
            expected_file_arg = { # <--- 新增：定義預期的檔案參數字典
                'filename': 'test_config.json',
                'content': config_file_content,
                '_type': 'file' # 需與 _record_call 一致
            }
            mock_crawlers_service.assert_called_once_with(
                'create_crawler_with_config',
                crawler_data, # 第一個參數是字典
                expected_file_arg # <--- 修改：傳遞預期的記錄字典
            )
        except AssertionError as e:
            pytest.fail(f"Mock 呼叫驗證失敗: {e}")

    def test_get_crawler_by_id(self, client, mock_crawlers_service, sample_crawlers_data):
        """測試通過 ID 取得特定爬蟲設定"""
        target_id = 1
        target_crawler_data = sample_crawlers_data[0]
        response = client.get(f'/api/crawlers/{target_id}')
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result['success'] is True
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
        assert '不存在' in result['message']

    def test_update_crawler_with_config_success(self, client, mock_crawlers_service):
        """測試更新爬蟲資料和配置檔案 (multipart/form-data) - 成功"""
        target_id = 1
        original_crawler = mock_crawlers_service.crawlers[target_id]
        update_data = {
            'crawler_name': 'UpdatedViaMultipart',
            'is_active': False
        }
        new_config_content = {"new_key": "new_value", "selectors": {"a": "b"}} # 必須有 selectors
        new_config_file_tuple = (
            io.BytesIO(json.dumps(new_config_content).encode('utf-8')),
            'updated_config.json'
        )
        data = {
            'crawler_data': json.dumps(update_data),
            'config_file': new_config_file_tuple
        }

        response = client.put(f'/api/crawlers/{target_id}', data=data, content_type='multipart/form-data')

        assert response.status_code == 200, f"預期 200，收到 {response.status_code}. 回應: {response.data.decode()}"
        response_data = response.get_json()
        assert response_data['success'] is True
        assert '更新成功' in response_data['message']
        updated_crawler_resp = response_data['crawler']
        assert updated_crawler_resp['id'] == target_id
        assert updated_crawler_resp['crawler_name'] == update_data['crawler_name']
        assert updated_crawler_resp['is_active'] == update_data['is_active']
        assert compare_datetimes(updated_crawler_resp['updated_at'], datetime.now(timezone.utc))
        # 驗證 mock 物件內部狀態
        updated_mock_crawler = mock_crawlers_service.crawlers[target_id]
        assert updated_mock_crawler.crawler_name == update_data['crawler_name']
        assert updated_mock_crawler.is_active == update_data['is_active']
        assert updated_mock_crawler.config_content == new_config_content # 驗證配置內容已更新
        assert updated_mock_crawler.config_file_name == f"{update_data['crawler_name']}.json" # 檔名應更新

        # 驗證服務呼叫
        try:
            expected_file_arg = { # <--- 新增：定義預期的檔案參數字典
                'filename': 'updated_config.json', # 從 new_config_file_tuple[1] 獲取
                'content': new_config_content,
                '_type': 'file' # 需與 _record_call 一致
            }
            mock_crawlers_service.assert_called_once_with(
                'update_crawler_with_config',
                target_id,
                update_data,
                expected_file_arg # <--- 修改：傳遞預期的記錄字典
            )
        except AssertionError as e:
            pytest.fail(f"Mock 呼叫驗證失敗: {e}")

    def test_delete_crawler(self, client, mock_crawlers_service):
        """測試刪除爬蟲設定"""
        target_id = 1
        assert target_id in mock_crawlers_service.crawlers
        response = client.delete(f'/api/crawlers/{target_id}')
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result['success'] is True
        assert target_id not in mock_crawlers_service.crawlers

    def test_delete_crawler_not_found(self, client, mock_crawlers_service):
        """測試刪除不存在的爬蟲設定"""
        non_existent_id = 999
        response = client.delete(f'/api/crawlers/{non_existent_id}')
        assert response.status_code == 404
        result = json.loads(response.data)
        assert result['success'] is False

    def test_get_crawler_config_success(self, client, mock_crawlers_service, sample_crawlers_data):
         """測試成功獲取爬蟲配置內容"""
         target_id = 1
         expected_config = sample_crawlers_data[0]['config_content']
         response = client.get(f'/api/crawlers/{target_id}/config')
         assert response.status_code == 200
         result = response.get_json()
         assert result['success'] is True
         assert "獲取爬蟲配置成功" in result['message']
         assert result['config'] == expected_config
         # 驗證服務呼叫
         mock_crawlers_service.assert_called_once_with('get_crawler_config', target_id)

    def test_get_crawler_config_not_found(self, client, mock_crawlers_service):
        """測試獲取不存在的爬蟲 ID 的配置"""
        non_existent_id = 999
        response = client.get(f'/api/crawlers/{non_existent_id}/config')
        assert response.status_code == 404 # API 應返回 404
        result = response.get_json()
        assert result['success'] is False
        assert "不存在" in result['message']
        assert result.get('config') is None

    def test_get_crawler_config_file_missing_or_unreadable(self, client, mock_crawlers_service):
        """測試獲取配置時，服務模擬檔案不存在或不可讀"""
        target_id = 3 # 這個爬蟲在 mock 中 config_content 為 None
        response = client.get(f'/api/crawlers/{target_id}/config')
        # Service 返回 success=False，API 應轉發，狀態碼可能是 404 或 500
        # 根據 Mock 邏輯，應該是 404 (找不到配置檔案)
        assert response.status_code == 404
        result = response.get_json()
        assert result['success'] is False
        assert "找不到" in result['message'] and "配置檔案" in result['message']
        assert result.get('config') is None

    def test_get_active_crawlers(self, client, mock_crawlers_service, sample_crawlers_data):
        """測試取得所有活動中的爬蟲設定"""
        response = client.get('/api/crawlers/active')
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result['success'] is True
        expected_active = [c for c in sample_crawlers_data if c['is_active']]
        assert len(result['data']) == len(expected_active)

    def test_toggle_crawler_status(self, client, mock_crawlers_service):
        """測試切換爬蟲活躍狀態"""
        target_id = 1
        original_status = mock_crawlers_service.crawlers[target_id].is_active
        response = client.post(f'/api/crawlers/{target_id}/toggle')
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result['success'] is True
        assert result['crawler']['is_active'] == (not original_status)

    def test_get_crawlers_by_name(self, client, mock_crawlers_service, sample_crawlers_data):
        """測試根據名稱模糊查詢爬蟲設定"""
        search_name = "TestCrawler"
        response = client.get(f'/api/crawlers/name/{search_name}')
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result['success'] is True
        expected_found = [c for c in sample_crawlers_data if search_name.lower() in c['crawler_name'].lower()]
        assert len(result['data']) == len(expected_found)

    def test_get_crawlers_by_type(self, client, mock_crawlers_service, sample_crawlers_data):
        """測試根據爬蟲類型查找爬蟲"""
        search_type = "web"
        response = client.get(f'/api/crawlers/type/{search_type}')
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result['success'] is True
        expected_found = [c for c in sample_crawlers_data if c['crawler_type'] == search_type]
        assert len(result['data']) == len(expected_found)

    def test_get_crawler_by_exact_name(self, client, mock_crawlers_service, sample_crawlers_data):
        """測試根據爬蟲名稱精確查詢"""
        target_name = "TestCrawler1"
        response = client.get(f'/api/crawlers/exact-name/{target_name}')
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result['success'] is True
        assert result['crawler']['crawler_name'] == target_name

    def test_create_or_update_crawler_create(self, client, mock_crawlers_service):
        """測試 create_or_update 創建新爬蟲 (application/json)"""
        new_data = {'crawler_name': 'COU_NewJson', 'base_url': '...', 'crawler_type': '...', 'module_name': '...'}
        response = client.post('/api/crawlers/create-or-update', json=new_data)
        assert response.status_code == 201
        result = response.get_json()
        assert result['success'] is True
        assert result['crawler']['crawler_name'] == new_data['crawler_name']

    def test_create_or_update_crawler_update(self, client, mock_crawlers_service):
        """測試 create_or_update 更新現有爬蟲 (application/json)"""
        target_id = 2
        update_data = {'id': target_id, 'crawler_name': 'COU_UpdatedJson', 'is_active': True}
        response = client.post('/api/crawlers/create-or-update', json=update_data)
        assert response.status_code == 200
        result = response.get_json()
        assert result['success'] is True
        assert result['crawler']['id'] == target_id
        assert result['crawler']['is_active'] == True

    def test_batch_toggle_crawler_status(self, client, mock_crawlers_service):
        """測試批量設置爬蟲的活躍狀態"""
        ids_to_toggle = [1, 2]
        target_status = False
        response = client.post('/api/crawlers/batch-toggle', json={'crawler_ids': ids_to_toggle, 'active_status': target_status})
        assert response.status_code == 200
        result = response.get_json()
        assert result['success'] is True
        assert result['result']['success_count'] == 2

    def test_get_filtered_crawlers(self, client, mock_crawlers_service, sample_crawlers_data):
        """測試根據過濾條件獲取分頁爬蟲列表"""
        filter_data = {'filter': {'crawler_type': 'web'}, 'page': 1, 'per_page': 1}
        response = client.post('/api/crawlers/filter', json=filter_data)
        assert response.status_code == 200
        result = response.get_json()
        assert result['success'] is True
        paginated_data = result['data']
        assert len(paginated_data['items']) == 1
        expected_items = [c for c in sample_crawlers_data if c['crawler_type'] == 'web']
        assert paginated_data['total'] == len(expected_items) 