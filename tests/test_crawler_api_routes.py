import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from flask import Flask, jsonify
from src.web.routes.crawler_api import crawler_bp
from src.models.crawlers_model import Crawlers
from src.error.errors import ValidationError
from src.error.handle_api_error import handle_api_error
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@pytest.fixture
def app():
    """創建測試用的 Flask 應用程式"""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['JSON_SORT_KEYS'] = False
    
    # 註冊路由藍圖
    app.register_blueprint(crawler_bp)
    
    # 添加通用錯誤處理
    @app.errorhandler(Exception)
    def handle_exception(e):
        if isinstance(e, ValidationError):
            return jsonify({
                "error": str(e),
                "type": "validation_error",
                "details": {"base_url": "此欄位為必填項"}
            }), 400
        return jsonify({"error": str(e)}), 500
    
    return app

@pytest.fixture
def client(app):
    """創建測試客戶端"""
    return app.test_client()

class CrawlerMock:
    """模擬 Crawlers 類型，基於模型的實際結構"""
    def __init__(self, data):
        self.id = data.get('id')
        self.crawler_name = data.get('crawler_name')
        self.base_url = data.get('base_url')
        self.crawler_type = data.get('crawler_type')
        self.config_file_name = data.get('config_file_name')
        self.is_active = data.get('is_active', True)
        self.created_at = data.get('created_at', datetime.now(timezone.utc))
        self.updated_at = data.get('updated_at', datetime.now(timezone.utc))
            
    def to_dict(self):
        """將物件轉換為字典，模擬模型的 to_dict 方法"""
        return {
            'id': self.id,
            'crawler_name': self.crawler_name,
            'base_url': self.base_url,
            'crawler_type': self.crawler_type,
            'config_file_name': self.config_file_name,
            'is_active': self.is_active,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

@pytest.fixture
def sample_crawlers():
    """創建測試用的爬蟲設定數據"""
    now = datetime.now(timezone.utc)
    return [
        {
            'id': 1,
            'crawler_name': 'TestCrawler1',
            'base_url': 'https://example1.com',
            'crawler_type': 'web',
            'config_file_name': 'test1.json',
            'is_active': True,
            'created_at': now,
            'updated_at': now
        },
        {
            'id': 2,
            'crawler_name': 'TestCrawler2',
            'base_url': 'https://example2.com',
            'crawler_type': 'web',
            'config_file_name': 'test2.json',
            'is_active': False,
            'created_at': now,
            'updated_at': now
        },
        {
            'id': 3,
            'crawler_name': 'TestCrawler3',
            'base_url': 'https://example3.com',
            'crawler_type': 'rss',
            'config_file_name': 'test3.json',
            'is_active': True,
            'created_at': now,
            'updated_at': now
        }
    ]

@pytest.fixture
def mock_crawlers_service(monkeypatch, sample_crawlers):
    """模擬 CrawlersService，使用更真實的測試數據"""
    class MockCrawlersService:
        def __init__(self):
            # 將樣本爬蟲轉換為 CrawlerMock 對象
            self.crawlers = {crawler['id']: CrawlerMock(crawler) for crawler in sample_crawlers}
            self.next_id = max(crawler['id'] for crawler in sample_crawlers) + 1

        def validate_crawler_data(self, data, is_update=False):
            required_fields = ['crawler_name', 'base_url', 'crawler_type', 'config_file_name']
            if not is_update:
                for field in required_fields:
                    if field not in data:
                        raise ValidationError(f"缺少必要欄位: {field}")
            return data

        def create_crawler(self, data):
            crawler_id = self.next_id
            # 創建爬蟲物件，包含所有必要的屬性
            crawler_data = {
                'id': crawler_id,
                'crawler_name': data['crawler_name'],
                'base_url': data['base_url'],
                'crawler_type': data['crawler_type'],
                'config_file_name': data['config_file_name'],
                'is_active': data.get('is_active', True),
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc)
            }
            crawler = CrawlerMock(crawler_data)
            self.crawlers[crawler_id] = crawler
            self.next_id += 1
            return {'success': True, 'message': '創建成功', 'crawler': crawler}

        def get_crawler_by_id(self, crawler_id):
            crawler = self.crawlers.get(crawler_id)
            if not crawler:
                return {'success': False, 'message': '找不到爬蟲設定', 'crawler': None}
            return {'success': True, 'message': '取得成功', 'crawler': crawler}

        def update_crawler(self, crawler_id, data):
            if crawler_id not in self.crawlers:
                return {'success': False, 'message': '找不到爬蟲設定', 'crawler': None}
                
            crawler = self.crawlers[crawler_id]
            for key, value in data.items():
                setattr(crawler, key, value)
                
            crawler.updated_at = datetime.now(timezone.utc)
            return {'success': True, 'message': '更新成功', 'crawler': crawler}

        def delete_crawler(self, crawler_id):
            if crawler_id not in self.crawlers:
                return {'success': False, 'message': '找不到爬蟲設定'}
            del self.crawlers[crawler_id]
            return {'success': True, 'message': '刪除成功'}

        def get_all_crawlers(self, filters=None):
            crawlers = list(self.crawlers.values())
            if filters:
                filtered_crawlers = []
                for crawler in crawlers:
                    match = True
                    for k, v in filters.items():
                        if getattr(crawler, k, None) != v:
                            match = False
                            break
                    if match:
                        filtered_crawlers.append(crawler)
                crawlers = filtered_crawlers
            
            return {'success': True, 'message': '取得成功', 'crawlers': crawlers}

        def get_active_crawlers(self):
            active_crawlers = [c for c in self.crawlers.values() if c.is_active]
            return {'success': True, 'message': '取得成功', 'crawlers': active_crawlers}

        def toggle_crawler_status(self, crawler_id):
            if crawler_id not in self.crawlers:
                return {'success': False, 'message': '找不到爬蟲設定', 'crawler': None}
            
            crawler = self.crawlers[crawler_id]
            crawler.is_active = not crawler.is_active
            return {'success': True, 'message': '狀態切換成功', 'crawler': crawler}

        def get_crawlers_by_name(self, name):
            matched_crawlers = [c for c in self.crawlers.values() 
                             if name.lower() in c.crawler_name.lower()]
            if not matched_crawlers:
                return {'success': False, 'message': '找不到符合條件的爬蟲', 'crawlers': []}
            return {'success': True, 'message': '取得成功', 'crawlers': matched_crawlers}

        def get_crawlers_by_type(self, crawler_type):
            matched_crawlers = [c for c in self.crawlers.values() 
                             if c.crawler_type == crawler_type]
            if not matched_crawlers:
                return {'success': False, 'message': f'找不到類型為 {crawler_type} 的爬蟲', 'crawlers': []}
            return {'success': True, 'message': '取得成功', 'crawlers': matched_crawlers}

        def get_crawler_by_exact_name(self, crawler_name):
            for c in self.crawlers.values():
                if c.crawler_name == crawler_name:
                    return {'success': True, 'message': '取得成功', 'crawler': c}
            return {'success': False, 'message': f'找不到名稱為 {crawler_name} 的爬蟲', 'crawler': None}

        def create_or_update_crawler(self, data):
            if 'id' in data and data['id']:
                crawler_id = data['id']
                # 更新現有爬蟲
                if crawler_id not in self.crawlers:
                    return {'success': False, 'message': f'找不到 ID 為 {crawler_id} 的爬蟲', 'crawler': None}
                
                crawler = self.crawlers[crawler_id]
                for key, value in data.items():
                    if key != 'id':  # 不更新 ID
                        setattr(crawler, key, value)
                crawler.updated_at = datetime.now(timezone.utc)
                return {'success': True, 'message': '更新成功', 'crawler': crawler}
            else:
                # 創建新爬蟲
                crawler_data = data.copy()
                crawler_id = self.next_id
                crawler_data['id'] = crawler_id
                crawler_data['created_at'] = datetime.now(timezone.utc)
                crawler_data['updated_at'] = datetime.now(timezone.utc)
                
                crawler = CrawlerMock(crawler_data)
                self.crawlers[crawler_id] = crawler
                self.next_id += 1
                return {'success': True, 'message': '創建成功', 'crawler': crawler}

        def batch_toggle_crawler_status(self, crawler_ids, active_status):
            success_count = 0
            fail_count = 0
            for crawler_id in crawler_ids:
                if crawler_id in self.crawlers:
                    self.crawlers[crawler_id].is_active = active_status
                    success_count += 1
                else:
                    fail_count += 1
            
            result = {
                'success_count': success_count,
                'fail_count': fail_count,
                'total': len(crawler_ids)
            }
            
            if success_count > 0:
                return {'success': True, 'message': f'批量設置成功：{success_count}，失敗：{fail_count}', 'result': result}
            else:
                return {'success': False, 'message': '批量設置失敗，所有操作均未成功', 'result': result}

        def get_filtered_crawlers(self, filter_dict, page=1, per_page=10, sort_by=None, sort_desc=False):
            # 簡單實現過濾邏輯
            filtered_crawlers = []
            for crawler in self.crawlers.values():
                match = True
                for field, value in filter_dict.items():
                    if getattr(crawler, field, None) != value:
                        match = False
                        break
                if match:
                    filtered_crawlers.append(crawler)
            
            # 轉換為字典後再分頁，這是修正的關鍵部分
            crawler_dicts = [crawler.to_dict() for crawler in filtered_crawlers]
            
            # 模擬分頁結果格式
            paginated_result = {
                'items': crawler_dicts[(page-1)*per_page:page*per_page],
                'page': page,
                'per_page': per_page,
                'total': len(filtered_crawlers),
                'total_pages': (len(filtered_crawlers) + per_page - 1) // per_page,
                'has_next': page * per_page < len(filtered_crawlers),
                'has_prev': page > 1
            }
            
            if not filtered_crawlers:
                return {'success': False, 'message': '找不到符合條件的爬蟲', 'data': paginated_result}
            return {'success': True, 'message': '取得成功', 'data': paginated_result}
    
    mock_service = MockCrawlersService()
    monkeypatch.setattr('src.web.routes.crawler_api.get_crawlers_service', lambda: mock_service)
    return mock_service

@pytest.fixture
def mock_handle_api_error(monkeypatch):
    """模擬錯誤處理函數，確保正確的回應格式"""
    def mock_error_handler(error):
        if isinstance(error, ValidationError):
            # 為驗證錯誤添加 details 欄位
            return jsonify({
                "error": str(error),
                "type": "validation_error",
                "details": {"base_url": "此欄位為必填項"}
            }), 400
        # 其他錯誤類型
        return jsonify({"error": str(error)}), 500
    
    monkeypatch.setattr('src.web.routes.crawler_api.handle_api_error', mock_error_handler)
    return mock_error_handler

class TestCrawlerApiRoutes:
    """測試爬蟲相關的 API 路由"""

    def test_get_crawlers(self, client, mock_crawlers_service):
        """測試取得所有爬蟲設定"""
        response = client.get('/api/crawlers')
        
        # 驗證結果
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 3
        assert data[0]['crawler_name'] == 'TestCrawler1'
        assert data[1]['crawler_name'] == 'TestCrawler2'
        assert data[2]['crawler_name'] == 'TestCrawler3'

    def test_get_crawlers_empty(self, client, mock_crawlers_service):
        """測試取得爬蟲設定列表為空的情況"""
        # 清空爬蟲列表
        mock_crawlers_service.crawlers = {}
        
        response = client.get('/api/crawlers')
        
        # 驗證結果
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 0

    def test_create_crawler(self, client, mock_crawlers_service):
        """測試新增爬蟲設定"""
        # 請求資料
        data = {
            'crawler_name': 'NewCrawler',
            'base_url': 'https://example.com',
            'crawler_type': 'web',
            'config_file_name': 'new.json',
            'is_active': True
        }
        
        response = client.post(
            '/api/crawlers',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # 驗證結果
        assert response.status_code == 201
        result = json.loads(response.data)
        assert result['crawler_name'] == 'NewCrawler'
        assert result['base_url'] == 'https://example.com'
        
        # 驗證爬蟲已被加入服務
        assert 4 in mock_crawlers_service.crawlers
        assert mock_crawlers_service.crawlers[4].crawler_name == 'NewCrawler'

    def test_create_crawler_validation_error(self, client, mock_crawlers_service, mock_handle_api_error):
        """測試新增爬蟲設定時的驗證錯誤"""
        # 請求資料缺少必填欄位
        data = {
            'crawler_name': 'NewCrawler',
            # 缺少 base_url, crawler_type, config_file_name
        }
        
        response = client.post(
            '/api/crawlers',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # 驗證結果
        assert response.status_code == 400
        result = json.loads(response.data)
        assert 'error' in result
        assert 'details' in result
        assert 'base_url' in result['details']

    def test_get_crawler_by_id(self, client, mock_crawlers_service):
        """測試通過 ID 取得特定爬蟲設定"""
        response = client.get('/api/crawlers/1')
        
        # 驗證結果
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result['id'] == 1
        assert result['crawler_name'] == 'TestCrawler1'

    def test_get_crawler_not_found(self, client, mock_crawlers_service):
        """測試取得不存在的爬蟲設定"""
        response = client.get('/api/crawlers/999')
        
        # 驗證結果
        assert response.status_code == 404
        result = json.loads(response.data)
        assert 'error' in result
        assert result['error'] == 'Not Found'

    def test_update_crawler(self, client, mock_crawlers_service):
        """測試更新爬蟲設定"""
        # 請求資料
        data = {
            'crawler_name': 'UpdatedCrawler',
            'base_url': 'https://updated.com',
            'is_active': False
        }
        
        response = client.put(
            '/api/crawlers/1',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # 驗證結果
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result['crawler_name'] == 'UpdatedCrawler'
        assert result['base_url'] == 'https://updated.com'
        assert result['is_active'] is False
        
        # 驗證爬蟲已被更新
        assert mock_crawlers_service.crawlers[1].crawler_name == 'UpdatedCrawler'

    def test_delete_crawler(self, client, mock_crawlers_service):
        """測試刪除爬蟲設定"""
        response = client.delete('/api/crawlers/1')
        
        # 驗證結果
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result['message'] == 'Deleted'
        
        # 驗證爬蟲已被刪除
        assert 1 not in mock_crawlers_service.crawlers

    def test_delete_crawler_not_found(self, client, mock_crawlers_service):
        """測試刪除不存在的爬蟲設定"""
        response = client.delete('/api/crawlers/999')
        
        # 驗證結果
        assert response.status_code == 404
        result = json.loads(response.data)
        assert 'error' in result
        assert result['error'] == 'Not Found'

    def test_get_crawler_types(self, client):
        """測試取得可用的爬蟲類型"""
        # 使用 patch 來模擬 CrawlerFactory
        with patch('src.crawlers.crawler_factory.CrawlerFactory') as mock_factory:
            # 設置模擬的爬蟲類型列表
            mock_factory.list_available_crawlers.return_value = [
                {'name': 'BnextCrawler', 'description': 'Bnext 網站爬蟲'},
                {'name': 'NewsCrawler', 'description': '新聞網站爬蟲'}
            ]
            
            # 發送 GET 請求
            response = client.get('/api/crawlers/types')
            
            # 驗證結果
            assert response.status_code == 200
            result = json.loads(response.data)
            assert len(result) == 2
            assert result[0]['name'] == 'BnextCrawler'
            assert result[1]['name'] == 'NewsCrawler'
            
            # 驗證 CrawlerFactory 被正確調用
            mock_factory.list_available_crawlers.assert_called_once()

    def test_get_active_crawlers(self, client, mock_crawlers_service):
        """測試取得所有活動中的爬蟲設定"""
        # 為 MockCrawlersService 添加方法
        def get_active_crawlers():
            active_crawlers = [c for c in mock_crawlers_service.crawlers.values() if c.is_active]
            return {'success': True, 'message': '取得成功', 'crawlers': active_crawlers}
        
        mock_crawlers_service.get_active_crawlers = get_active_crawlers
        
        response = client.get('/api/crawlers/active')
        
        # 驗證結果
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 2  # 根據樣本數據，應該有 2 個活動中的爬蟲
        assert any(c['crawler_name'] == 'TestCrawler1' for c in data)
        assert any(c['crawler_name'] == 'TestCrawler3' for c in data)

    def test_toggle_crawler_status(self, client, mock_crawlers_service):
        """測試切換爬蟲活躍狀態"""
        # 為 MockCrawlersService 添加方法
        def toggle_crawler_status(crawler_id):
            if crawler_id not in mock_crawlers_service.crawlers:
                return {'success': False, 'message': '找不到爬蟲設定', 'crawler': None}
            
            crawler = mock_crawlers_service.crawlers[crawler_id]
            crawler.is_active = not crawler.is_active
            return {'success': True, 'message': '狀態切換成功', 'crawler': crawler}
        
        mock_crawlers_service.toggle_crawler_status = toggle_crawler_status
        
        # 原本狀態為 True 的爬蟲
        original_status = mock_crawlers_service.crawlers[1].is_active
        response = client.post('/api/crawlers/1/toggle')
        
        # 驗證結果
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result['is_active'] != original_status
        assert mock_crawlers_service.crawlers[1].is_active != original_status

    def test_get_crawlers_by_name(self, client, mock_crawlers_service):
        """測試根據名稱模糊查詢爬蟲設定"""
        # 為 MockCrawlersService 添加方法
        def get_crawlers_by_name(name):
            matched_crawlers = [c for c in mock_crawlers_service.crawlers.values() 
                             if name.lower() in c.crawler_name.lower()]
            if not matched_crawlers:
                return {'success': False, 'message': '找不到符合條件的爬蟲', 'crawlers': []}
            return {'success': True, 'message': '取得成功', 'crawlers': matched_crawlers}
        
        mock_crawlers_service.get_crawlers_by_name = get_crawlers_by_name
        
        response = client.get('/api/crawlers/name/Test')
        
        # 驗證結果
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 3  # 所有樣本爬蟲名稱都包含 "Test"

    def test_get_crawlers_by_type(self, client, mock_crawlers_service):
        """測試根據爬蟲類型查找爬蟲"""
        # 為 MockCrawlersService 添加方法
        def get_crawlers_by_type(crawler_type):
            matched_crawlers = [c for c in mock_crawlers_service.crawlers.values() 
                             if c.crawler_type == crawler_type]
            if not matched_crawlers:
                return {'success': False, 'message': f'找不到類型為 {crawler_type} 的爬蟲', 'crawlers': []}
            return {'success': True, 'message': '取得成功', 'crawlers': matched_crawlers}
        
        mock_crawlers_service.get_crawlers_by_type = get_crawlers_by_type
        
        response = client.get('/api/crawlers/type/web')
        
        # 驗證結果
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 2  # 樣本中有 2 個 web 類型爬蟲
        assert all(c['crawler_type'] == 'web' for c in data)

    def test_get_crawler_by_exact_name(self, client, mock_crawlers_service):
        """測試根據爬蟲名稱精確查詢"""
        # 為 MockCrawlersService 添加方法
        def get_crawler_by_exact_name(crawler_name):
            for c in mock_crawlers_service.crawlers.values():
                if c.crawler_name == crawler_name:
                    return {'success': True, 'message': '取得成功', 'crawler': c}
            return {'success': False, 'message': f'找不到名稱為 {crawler_name} 的爬蟲', 'crawler': None}
        
        mock_crawlers_service.get_crawler_by_exact_name = get_crawler_by_exact_name
        
        response = client.get('/api/crawlers/exact-name/TestCrawler1')
        
        # 驗證結果
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['crawler_name'] == 'TestCrawler1'

    def test_create_or_update_crawler(self, client, mock_crawlers_service):
        """測試創建或更新爬蟲設定"""
        # 為 MockCrawlersService 添加方法
        def create_or_update_crawler(data):
            if 'id' in data and data['id']:
                crawler_id = data['id']
                # 更新現有爬蟲
                if crawler_id not in mock_crawlers_service.crawlers:
                    return {'success': False, 'message': f'找不到 ID 為 {crawler_id} 的爬蟲', 'crawler': None}
                
                crawler = mock_crawlers_service.crawlers[crawler_id]
                for key, value in data.items():
                    if key != 'id':  # 不更新 ID
                        setattr(crawler, key, value)
                crawler.updated_at = datetime.now(timezone.utc)
                return {'success': True, 'message': '更新成功', 'crawler': crawler}
            else:
                # 創建新爬蟲
                crawler_data = data.copy()
                crawler_id = mock_crawlers_service.next_id
                crawler_data['id'] = crawler_id
                crawler_data['created_at'] = datetime.now(timezone.utc)
                crawler_data['updated_at'] = datetime.now(timezone.utc)
                
                crawler = CrawlerMock(crawler_data)
                mock_crawlers_service.crawlers[crawler_id] = crawler
                mock_crawlers_service.next_id += 1
                return {'success': True, 'message': '創建成功', 'crawler': crawler}
        
        mock_crawlers_service.create_or_update_crawler = create_or_update_crawler
        
        # 測試創建新爬蟲
        new_data = {
            'crawler_name': 'CreateOrUpdateTest',
            'base_url': 'https://example.com',
            'crawler_type': 'web',
            'config_file_name': 'test.json',
            'is_active': True
        }
        
        response = client.post(
            '/api/crawlers/create-or-update',
            data=json.dumps(new_data),
            content_type='application/json'
        )
        
        # 驗證創建結果
        assert response.status_code == 201
        result = json.loads(response.data)
        assert result['crawler_name'] == 'CreateOrUpdateTest'
        
        # 測試更新爬蟲
        update_data = {
            'id': 1,
            'crawler_name': 'UpdatedViaCreateOrUpdate',
            'is_active': False
        }
        
        response = client.post(
            '/api/crawlers/create-or-update',
            data=json.dumps(update_data),
            content_type='application/json'
        )
        
        # 驗證更新結果
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result['crawler_name'] == 'UpdatedViaCreateOrUpdate'
        assert result['is_active'] is False
        assert mock_crawlers_service.crawlers[1].crawler_name == 'UpdatedViaCreateOrUpdate'

    def test_batch_toggle_crawler_status(self, client, mock_crawlers_service):
        """測試批量設置爬蟲的活躍狀態"""
        # 為 MockCrawlersService 添加方法
        def batch_toggle_crawler_status(crawler_ids, active_status):
            success_count = 0
            fail_count = 0
            for crawler_id in crawler_ids:
                if crawler_id in mock_crawlers_service.crawlers:
                    mock_crawlers_service.crawlers[crawler_id].is_active = active_status
                    success_count += 1
                else:
                    fail_count += 1
            
            result = {
                'success_count': success_count,
                'fail_count': fail_count,
                'total': len(crawler_ids)
            }
            
            if success_count > 0:
                return {'success': True, 'message': f'批量設置成功：{success_count}，失敗：{fail_count}', 'result': result}
            else:
                return {'success': False, 'message': '批量設置失敗，所有操作均未成功', 'result': result}
        
        mock_crawlers_service.batch_toggle_crawler_status = batch_toggle_crawler_status
        
        # 準備請求資料
        data = {
            'crawler_ids': [1, 2],
            'active_status': False
        }
        
        response = client.post(
            '/api/crawlers/batch-toggle',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # 驗證結果
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result['success_count'] == 2
        assert result['fail_count'] == 0
        assert not mock_crawlers_service.crawlers[1].is_active
        assert not mock_crawlers_service.crawlers[2].is_active

    def test_get_filtered_crawlers(self, client, mock_crawlers_service):
        """測試根據過濾條件獲取分頁爬蟲列表"""
        # 為 MockCrawlersService 添加方法
        def get_filtered_crawlers(filter_dict, page=1, per_page=10, sort_by=None, sort_desc=False):
            # 簡單實現過濾邏輯
            filtered_crawlers = []
            for crawler in mock_crawlers_service.crawlers.values():
                match = True
                for field, value in filter_dict.items():
                    if getattr(crawler, field, None) != value:
                        match = False
                        break
                if match:
                    filtered_crawlers.append(crawler)
            
            # 轉換為字典後再分頁，這是修正的關鍵部分
            crawler_dicts = [crawler.to_dict() for crawler in filtered_crawlers]
            
            # 模擬分頁結果格式
            paginated_result = {
                'items': crawler_dicts[(page-1)*per_page:page*per_page],
                'page': page,
                'per_page': per_page,
                'total': len(filtered_crawlers),
                'total_pages': (len(filtered_crawlers) + per_page - 1) // per_page,
                'has_next': page * per_page < len(filtered_crawlers),
                'has_prev': page > 1
            }
            
            if not filtered_crawlers:
                return {'success': False, 'message': '找不到符合條件的爬蟲', 'data': paginated_result}
            return {'success': True, 'message': '取得成功', 'data': paginated_result}
        
        mock_crawlers_service.get_filtered_crawlers = get_filtered_crawlers
        
        # 準備請求資料
        data = {
            'filter': {'crawler_type': 'web'},
            'page': 1,
            'per_page': 5
        }
        
        response = client.post(
            '/api/crawlers/filter',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # 驗證結果
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result['page'] == 1
        assert len(result['items']) == 2  # 樣本中有 2 個 web 類型爬蟲
        assert all(item['crawler_type'] == 'web' for item in result['items']) 