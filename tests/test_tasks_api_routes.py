import pytest
from flask import Flask
from src.web.routes.tasks import tasks_bp
import json

@pytest.fixture
def app():
    """創建測試用的 Flask 應用程式"""
    app = Flask(__name__)
    app.register_blueprint(tasks_bp)
    return app

@pytest.fixture
def client(app):
    """創建測試客戶端"""
    return app.test_client()

@pytest.fixture
def mock_task_service(monkeypatch):
    """模擬 CrawlerTaskService"""
    class MockTaskService:
        def __init__(self):
            self.tasks = {}
            self.task_history = {}
            self.next_id = 1

        def create_task(self, data):
            task_id = self.next_id
            self.tasks[task_id] = {
                'id': task_id,
                'task_name': data['task_name'],
                'crawler_id': data['crawler_id'],
                'is_scheduled': data.get('is_scheduled', False),
                'cron_expression': data.get('cron_expression'),
                'task_args': data.get('task_args', {}),
                'status': 'pending'
            }
            self.next_id += 1
            return {'success': True, 'task_id': task_id, 'message': '任務創建成功'}

        def get_task_by_id(self, task_id):
            task = self.tasks.get(task_id)
            if not task:
                return {'success': False, 'message': '任務不存在'}
            return {'success': True, 'task': task}

        def update_task(self, task_id, data):
            if task_id not in self.tasks:
                return {'success': False, 'message': '任務不存在'}
            self.tasks[task_id].update(data)
            return {'success': True, 'task': self.tasks[task_id], 'message': '任務更新成功'}

        def delete_task(self, task_id):
            if task_id not in self.tasks:
                return {'success': False, 'message': '任務不存在'}
            del self.tasks[task_id]
            return {'success': True, 'message': '任務刪除成功'}

        def get_all_tasks(self, filters=None):
            tasks = list(self.tasks.values())
            if filters:
                tasks = [t for t in tasks if all(t.get(k) == v for k, v in filters.items())]
            return {'success': True, 'tasks': tasks}

        def get_task_status(self, task_id):
            if task_id not in self.tasks:
                return {'success': False, 'message': '任務不存在'}
            return {
                'status': self.tasks[task_id]['status'],
                'progress': 50,
                'message': '任務執行中'
            }

        def run_task(self, task_id, task_args):
            if task_id not in self.tasks:
                return {'success': False, 'message': '任務不存在'}
            self.tasks[task_id]['status'] = 'running'
            return {'success': True, 'message': '任務開始執行'}

        def fetch_article_content(self, task_id, link_ids):
            if task_id not in self.tasks:
                return {'success': False, 'message': '任務不存在'}
            return {'success': True, 'message': '開始抓取文章內容'}

        def test_crawler_task(self, data):
            return {
                'success': True,
                'message': '爬蟲測試成功',
                'test_results': {
                    'links_found': 3,
                    'sample_links': ['http://example.com/1', 'http://example.com/2', 'http://example.com/3']
                }
            }

        def cancel_task(self, task_id):
            if task_id not in self.tasks:
                return {'success': False, 'message': '任務不存在'}
            self.tasks[task_id]['status'] = 'cancelled'
            return {'success': True, 'message': '任務已取消'}

        def get_task_history(self, task_id):
            if task_id not in self.task_history:
                return {'success': True, 'history': []}
            return {'success': True, 'history': self.task_history[task_id]}

    mock_service = MockTaskService()
    monkeypatch.setattr('src.web.routes.tasks.get_task_service', lambda: mock_service)
    return mock_service

@pytest.fixture
def mock_article_service(monkeypatch):
    """模擬 ArticleService"""
    class MockArticleService:
        def get_articles_by_task(self, filters):
            return {
                'success': True,
                'articles': [
                    {
                        'id': 1,
                        'title': '測試文章1',
                        'link': 'http://example.com/1',
                        'scraped': filters.get('scraped', False)
                    },
                    {
                        'id': 2,
                        'title': '測試文章2',
                        'link': 'http://example.com/2',
                        'scraped': filters.get('scraped', False)
                    }
                ]
            }

    mock_service = MockArticleService()
    monkeypatch.setattr('src.web.routes.tasks.get_article_service', lambda: mock_service)
    return mock_service

@pytest.fixture
def mock_scheduler_service(monkeypatch):
    """模擬 SchedulerService"""
    class MockSchedulerService:
        def _schedule_task(self, task):
            return True

        def cron_scheduler(self):
            class MockScheduler:
                def remove_job(self, job_id):
                    return True
            return MockScheduler()

    mock_service = MockSchedulerService()
    monkeypatch.setattr('src.web.routes.tasks.get_scheduler_service', lambda: mock_service)
    return mock_service

class TestTasksApiRoutes:
    """測試任務相關的 API 路由"""

    def test_get_scheduled_tasks(self, client, mock_task_service):
        """測試獲取排程任務列表"""
        # 創建一些測試用的排程任務
        mock_task_service.create_task({
            'task_name': '排程任務1',
            'crawler_id': 1,
            'is_scheduled': True,
            'cron_expression': '0 0 * * *'
        })
        mock_task_service.create_task({
            'task_name': '排程任務2',
            'crawler_id': 1,
            'is_scheduled': True,
            'cron_expression': '0 12 * * *'
        })

        response = client.get('/api/tasks/scheduled')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 2

    def test_create_scheduled_task(self, client, mock_task_service):
        """測試創建排程任務"""
        task_data = {
            'task_name': '新排程任務',
            'crawler_id': 1,
            'is_scheduled': True,
            'cron_expression': '0 0 * * *',
            'task_args': {'max_items': 100}
        }

        response = client.post('/api/tasks/scheduled', json=task_data)
        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'task_id' in data

    def test_get_scheduled_task(self, client, mock_task_service):
        """測試獲取單個排程任務"""
        # 先創建一個任務
        task_data = {
            'task_name': '測試任務',
            'crawler_id': 1,
            'is_scheduled': True,
            'cron_expression': '0 0 * * *'
        }
        create_result = mock_task_service.create_task(task_data)
        task_id = create_result['task_id']

        response = client.get(f'/api/tasks/scheduled/{task_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['task_name'] == '測試任務'

    def test_update_scheduled_task(self, client, mock_task_service):
        """測試更新排程任務"""
        # 先創建一個任務
        task_data = {
            'task_name': '原始任務',
            'crawler_id': 1,
            'is_scheduled': True,
            'cron_expression': '0 0 * * *'
        }
        create_result = mock_task_service.create_task(task_data)
        task_id = create_result['task_id']

        update_data = {
            'task_name': '更新後的任務',
            'cron_expression': '0 12 * * *'
        }

        response = client.put(f'/api/tasks/scheduled/{task_id}', json=update_data)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['task_name'] == '更新後的任務'

    def test_delete_scheduled_task(self, client, mock_task_service):
        """測試刪除排程任務"""
        # 先創建一個任務
        task_data = {
            'task_name': '待刪除任務',
            'crawler_id': 1,
            'is_scheduled': True,
            'cron_expression': '0 0 * * *'
        }
        create_result = mock_task_service.create_task(task_data)
        task_id = create_result['task_id']

        response = client.delete(f'/api/tasks/scheduled/{task_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['message'] == 'Deleted'

    def test_start_manual_task(self, client, mock_task_service):
        """測試開始手動任務"""
        task_data = {
            'task_name': '手動任務',
            'crawler_id': 1,
            'is_scheduled': False,
            'task_args': {'max_items': 50}
        }

        response = client.post('/api/tasks/manual/start', json=task_data)
        assert response.status_code == 202
        data = json.loads(response.data)
        assert 'task_id' in data
        assert data['status'] == 'pending'

    def test_get_manual_task_status(self, client, mock_task_service):
        """測試獲取手動任務狀態"""
        # 先創建一個任務
        task_data = {
            'task_name': '手動任務',
            'crawler_id': 1,
            'is_scheduled': False
        }
        create_result = mock_task_service.create_task(task_data)
        task_id = create_result['task_id']

        response = client.get(f'/api/tasks/manual/{task_id}/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'status' in data
        assert 'progress' in data

    def test_get_manual_task_links(self, client, mock_task_service, mock_article_service):
        """測試獲取手動任務的文章連結"""
        # 先創建一個任務
        task_data = {
            'task_name': '手動任務',
            'crawler_id': 1,
            'is_scheduled': False
        }
        create_result = mock_task_service.create_task(task_data)
        task_id = create_result['task_id']

        response = client.get(f'/api/tasks/manual/{task_id}/links')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 2
        assert all('title' in article for article in data)
        assert all('link' in article for article in data)

    def test_fetch_manual_task_content(self, client, mock_task_service):
        """測試抓取手動任務的文章內容"""
        # 先創建一個任務
        task_data = {
            'task_name': '手動任務',
            'crawler_id': 1,
            'is_scheduled': False
        }
        create_result = mock_task_service.create_task(task_data)
        task_id = create_result['task_id']

        response = client.post(f'/api/tasks/manual/{task_id}/fetch-content', json={'link_ids': [1, 2]})
        assert response.status_code == 202
        data = json.loads(response.data)
        assert data['message'] == 'Content fetching initiated'

    def test_get_manual_task_results(self, client, mock_task_service, mock_article_service):
        """測試獲取手動任務的結果"""
        # 先創建一個任務
        task_data = {
            'task_name': '手動任務',
            'crawler_id': 1,
            'is_scheduled': False
        }
        create_result = mock_task_service.create_task(task_data)
        task_id = create_result['task_id']

        response = client.get(f'/api/tasks/manual/{task_id}/results')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 2
        assert all('title' in article for article in data)
        assert all('link' in article for article in data)

    def test_test_crawler(self, client, mock_task_service):
        """測試爬蟲測試功能"""
        test_data = {
            'task_name': '測試爬蟲',
            'crawler_id': 1,
            'task_args': {'test_mode': True}
        }

        response = client.post('/api/tasks/manual/test', json=test_data)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'test_results' in data
        assert 'links_found' in data['test_results']

    def test_cancel_task(self, client, mock_task_service):
        """測試取消任務"""
        # 先創建一個任務
        task_data = {
            'task_name': '待取消任務',
            'crawler_id': 1,
            'is_scheduled': False
        }
        create_result = mock_task_service.create_task(task_data)
        task_id = create_result['task_id']

        response = client.post(f'/api/tasks/{task_id}/cancel')
        assert response.status_code == 202
        data = json.loads(response.data)
        assert data['message'] == 'Cancellation requested'

    def test_get_task_history(self, client, mock_task_service):
        """測試獲取任務歷史記錄"""
        # 先創建一個任務
        task_data = {
            'task_name': '歷史任務',
            'crawler_id': 1,
            'is_scheduled': False
        }
        create_result = mock_task_service.create_task(task_data)
        task_id = create_result['task_id']

        response = client.get(f'/api/tasks/{task_id}/history')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list) 