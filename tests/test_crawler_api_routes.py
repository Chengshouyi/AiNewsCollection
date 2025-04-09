import pytest
import json
from unittest.mock import patch, MagicMock
from src.web.app import create_app
from src.models.crawlers_model import Crawlers

@pytest.fixture
def app():
    """設置測試用 Flask 應用"""
    app = create_app()
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    """設置測試用客戶端"""
    return app.test_client()

@pytest.fixture
def mock_crawlers_service():
    """模擬爬蟲服務"""
    with patch('src.web.routes.crawler.get_crawlers_service') as mock:
        service_instance = MagicMock()
        mock.return_value = service_instance
        yield service_instance

def test_get_crawlers(client, mock_crawlers_service):
    """測試取得所有爬蟲設定"""
    # 創建模擬的爬蟲物件
    crawler1 = MagicMock(spec=Crawlers)
    crawler1.to_dict.return_value = {
        'id': 1,
        'crawler_name': 'TestCrawler1',
        'base_url': 'https://example1.com',
        'crawler_type': 'web',
        'config_file_name': 'test1.json',
        'is_active': True
    }
    
    crawler2 = MagicMock(spec=Crawlers)
    crawler2.to_dict.return_value = {
        'id': 2,
        'crawler_name': 'TestCrawler2',
        'base_url': 'https://example2.com',
        'crawler_type': 'web',
        'config_file_name': 'test2.json',
        'is_active': False
    }
    
    # 設置模擬服務回傳值
    mock_crawlers_service.get_all_crawlers.return_value = {
        'success': True,
        'message': '取得成功',
        'crawlers': [crawler1, crawler2]
    }
    
    # 發送 GET 請求
    response = client.get('/api/crawlers')
    
    # 驗證結果
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data) == 2
    assert data[0]['crawler_name'] == 'TestCrawler1'
    assert data[1]['crawler_name'] == 'TestCrawler2'
    
    # 驗證服務被正確調用
    mock_crawlers_service.get_all_crawlers.assert_called_once()

def test_get_crawlers_empty(client, mock_crawlers_service):
    """測試取得爬蟲設定列表為空的情況"""
    # 設置模擬服務回傳空列表
    mock_crawlers_service.get_all_crawlers.return_value = {
        'success': True,
        'message': '取得成功',
        'crawlers': []
    }
    
    # 發送 GET 請求
    response = client.get('/api/crawlers')
    
    # 驗證結果
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data, list)
    assert len(data) == 0
    
    # 驗證服務被正確調用
    mock_crawlers_service.get_all_crawlers.assert_called_once()

def test_create_crawler(client, mock_crawlers_service):
    """測試新增爬蟲設定"""
    # 創建模擬的爬蟲物件
    new_crawler = MagicMock(spec=Crawlers)
    new_crawler.to_dict.return_value = {
        'id': 1,
        'crawler_name': 'NewCrawler',
        'base_url': 'https://example.com',
        'crawler_type': 'web',
        'config_file_name': 'new.json',
        'is_active': True
    }
    
    # 設置模擬服務回傳值
    mock_crawlers_service.create_crawler.return_value = {
        'success': True,
        'message': '創建成功',
        'crawler': new_crawler
    }
    
    # 請求資料
    data = {
        'crawler_name': 'NewCrawler',
        'base_url': 'https://example.com',
        'crawler_type': 'web',
        'config_file_name': 'new.json',
        'is_active': True
    }
    
    # 發送 POST 請求
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
    
    # 驗證服務被正確調用
    mock_crawlers_service.create_crawler.assert_called_once_with(data)

def test_create_crawler_validation_error(client, mock_crawlers_service):
    """測試新增爬蟲設定時的驗證錯誤"""
    # 請求資料缺少必填欄位
    data = {
        'crawler_name': 'NewCrawler',
        # 缺少 base_url, crawler_type, config_file_name
    }
    
    # 發送 POST 請求
    response = client.post(
        '/api/crawlers',
        data=json.dumps(data),
        content_type='application/json'
    )
    
    # 驗證結果
    assert response.status_code == 400
    result = json.loads(response.data)
    assert 'errors' in result
    assert len(result['errors']) > 0
    
    # 驗證服務沒有被調用
    mock_crawlers_service.create_crawler.assert_not_called()

def test_get_crawler_by_id(client, mock_crawlers_service):
    """測試通過 ID 取得特定爬蟲設定"""
    # 創建模擬的爬蟲物件
    crawler = MagicMock(spec=Crawlers)
    crawler.to_dict.return_value = {
        'id': 1,
        'crawler_name': 'TestCrawler',
        'base_url': 'https://example.com',
        'crawler_type': 'web',
        'config_file_name': 'test.json',
        'is_active': True
    }
    
    # 設置模擬服務回傳值
    mock_crawlers_service.get_crawler_by_id.return_value = {
        'success': True,
        'message': '取得成功',
        'crawler': crawler
    }
    
    # 發送 GET 請求
    response = client.get('/api/crawlers/1')
    
    # 驗證結果
    assert response.status_code == 200
    result = json.loads(response.data)
    assert result['id'] == 1
    assert result['crawler_name'] == 'TestCrawler'
    
    # 驗證服務被正確調用
    mock_crawlers_service.get_crawler_by_id.assert_called_once_with(1)

def test_get_crawler_not_found(client, mock_crawlers_service):
    """測試取得不存在的爬蟲設定"""
    # 設置模擬服務回傳找不到的結果
    mock_crawlers_service.get_crawler_by_id.return_value = {
        'success': False,
        'message': '找不到爬蟲設定',
        'crawler': None
    }
    
    # 發送 GET 請求
    response = client.get('/api/crawlers/999')
    
    # 驗證結果
    assert response.status_code == 404
    result = json.loads(response.data)
    assert 'error' in result
    assert result['error'] == 'Not Found'
    
    # 驗證服務被正確調用
    mock_crawlers_service.get_crawler_by_id.assert_called_once_with(999)

def test_update_crawler(client, mock_crawlers_service):
    """測試更新爬蟲設定"""
    # 創建模擬的爬蟲物件
    updated_crawler = MagicMock(spec=Crawlers)
    updated_crawler.to_dict.return_value = {
        'id': 1,
        'crawler_name': 'UpdatedCrawler',
        'base_url': 'https://updated.com',
        'crawler_type': 'web',
        'config_file_name': 'updated.json',
        'is_active': False
    }
    
    # 設置模擬服務回傳值
    mock_crawlers_service.update_crawler.return_value = {
        'success': True,
        'message': '更新成功',
        'crawler': updated_crawler
    }
    
    # 請求資料
    data = {
        'crawler_name': 'UpdatedCrawler',
        'base_url': 'https://updated.com',
        'is_active': False
    }
    
    # 發送 PUT 請求
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
    
    # 驗證服務被正確調用
    mock_crawlers_service.update_crawler.assert_called_once_with(1, data)

def test_delete_crawler(client, mock_crawlers_service):
    """測試刪除爬蟲設定"""
    # 設置模擬服務回傳值
    mock_crawlers_service.delete_crawler.return_value = {
        'success': True,
        'message': '刪除成功'
    }
    
    # 發送 DELETE 請求
    response = client.delete('/api/crawlers/1')
    
    # 驗證結果
    assert response.status_code == 200
    result = json.loads(response.data)
    assert result['message'] == 'Deleted'
    
    # 驗證服務被正確調用
    mock_crawlers_service.delete_crawler.assert_called_once_with(1)

def test_delete_crawler_not_found(client, mock_crawlers_service):
    """測試刪除不存在的爬蟲設定"""
    # 設置模擬服務回傳找不到的結果
    mock_crawlers_service.delete_crawler.return_value = {
        'success': False,
        'message': '找不到爬蟲設定'
    }
    
    # 發送 DELETE 請求
    response = client.delete('/api/crawlers/999')
    
    # 驗證結果
    assert response.status_code == 404
    result = json.loads(response.data)
    assert 'error' in result
    assert result['error'] == 'Not Found'
    
    # 驗證服務被正確調用
    mock_crawlers_service.delete_crawler.assert_called_once_with(999)

def test_get_crawler_types(client):
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