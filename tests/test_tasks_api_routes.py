import pytest
from flask import Flask, jsonify
from src.web.routes.tasks_api import tasks_bp
from src.error.errors import ValidationError
import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from src.models.crawler_tasks_model import TaskPhase, ScrapeMode
import enum

@pytest.fixture
def app():
    """創建測試用的 Flask 應用程式"""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['JSON_SORT_KEYS'] = False
    
    # 註冊路由藍圖
    app.register_blueprint(tasks_bp)
    
    # 添加通用錯誤處理
    @app.errorhandler(Exception)
    def handle_exception(e):
        if isinstance(e, ValidationError):
            return jsonify({
                "error": str(e),
                "type": "validation_error",
                "details": {"crawler_id": "此欄位為必填項"}
            }), 400
        return jsonify({"error": str(e)}), 500
    
    return app

@pytest.fixture
def client(app):
    """創建測試客戶端"""
    return app.test_client()

class CrawlerTaskMock:
    """模擬 CrawlerTasks 類型，基於模型的實際結構"""
    def __init__(self, data):
        self.id = data.get('id')
        self.task_name = data.get('task_name')
        self.crawler_id = data.get('crawler_id')
        self.is_auto = data.get('is_auto', True)
        self.ai_only = data.get('ai_only', False)
        self.task_args = data.get('task_args', {})
        self.notes = data.get('notes')
        self.last_run_at = data.get('last_run_at')
        self.last_run_success = data.get('last_run_success')
        self.last_run_message = data.get('last_run_message')
        self.cron_expression = data.get('cron_expression')
        self.is_scheduled = data.get('is_scheduled', False)
        # 使用枚舉值或字串
        self.current_phase = data.get('current_phase', TaskPhase.INIT)
        self.max_retries = data.get('max_retries', 3)
        self.retry_count = data.get('retry_count', 0)
        self.scrape_mode = data.get('scrape_mode', ScrapeMode.FULL_SCRAPE)
        self.created_at = data.get('created_at', datetime.now(timezone.utc))
        self.updated_at = data.get('updated_at', datetime.now(timezone.utc))
        self.status = data.get('status', 'pending')
            
    def to_dict(self):
        """將物件轉換為字典，模擬模型的 to_dict 方法"""
        # 處理枚舉類型
        current_phase = self.current_phase.value if hasattr(self.current_phase, 'value') else self.current_phase
        scrape_mode = self.scrape_mode.value if hasattr(self.scrape_mode, 'value') else self.scrape_mode

        return {
            'id': self.id,
            'task_name': self.task_name,
            'crawler_id': self.crawler_id,
            'is_auto': self.is_auto,
            'ai_only': self.ai_only,
            'task_args': self.task_args,
            'notes': self.notes,
            'last_run_at': self.last_run_at,
            'last_run_success': self.last_run_success,
            'last_run_message': self.last_run_message,
            'cron_expression': self.cron_expression,
            'is_scheduled': self.is_scheduled,
            'current_phase': current_phase,
            'max_retries': self.max_retries,
            'retry_count': self.retry_count,
            'scrape_mode': scrape_mode,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

@pytest.fixture
def sample_tasks():
    """創建測試用的爬蟲任務數據"""
    now = datetime.now(timezone.utc)
    return [
        {
            'id': 1,
            'task_name': '每日新聞爬取',
            'crawler_id': 1,
            'is_auto': True,
            'ai_only': False,
            'task_args': {'max_items': 100},
            'cron_expression': '0 0 * * *',
            'is_scheduled': True,
            'current_phase': TaskPhase.INIT,
            'max_retries': 3,
            'retry_count': 0,
            'scrape_mode': ScrapeMode.FULL_SCRAPE,
            'created_at': now,
            'updated_at': now,
            'status': 'pending'
        },
        {
            'id': 2,
            'task_name': '週間財經新聞',
            'crawler_id': 1,
            'is_auto': True,
            'ai_only': True,
            'task_args': {'max_items': 50},
            'cron_expression': '0 0 * * 1-5',
            'is_scheduled': True,
            'current_phase': TaskPhase.INIT,
            'max_retries': 3,
            'retry_count': 0,
            'scrape_mode': ScrapeMode.FULL_SCRAPE,
            'created_at': now,
            'updated_at': now,
            'status': 'pending'
        },
        {
            'id': 3,
            'task_name': '手動採集任務',
            'crawler_id': 1,
            'is_auto': False,
            'ai_only': False,
            'task_args': {'max_pages': 5},
            'is_scheduled': False,
            'current_phase': TaskPhase.INIT,
            'max_retries': 3,
            'retry_count': 0,
            'scrape_mode': ScrapeMode.FULL_SCRAPE,
            'created_at': now,
            'updated_at': now,
            'status': 'pending'
        }
    ]

@pytest.fixture
def mock_task_service(monkeypatch, sample_tasks):
    """模擬 CrawlerTaskService，使用更真實的測試數據"""
    class MockTaskService:
        def __init__(self):
            # 將樣本任務轉換為 CrawlerTaskMock 對象
            self.tasks = {task['id']: CrawlerTaskMock(task) for task in sample_tasks}
            self.task_history = {}
            self.next_id = max(task['id'] for task in sample_tasks) + 1

        def _get_repository(self, model_name):
            """模擬獲取 repository 的方法"""
            if model_name == 'CrawlerTask':
                mock_repo = MagicMock()
                # 模擬 exists_by_id 方法，假設所有 crawler_id 都存在
                mock_repo.exists_by_id.return_value = True 
                return mock_repo
            # 可以根據需要擴展以模擬其他 repository
            return MagicMock()

        def validate_task_data(self, data, is_update=False):
            # 保持現有的頂層 scrape_mode 驗證
            if 'scrape_mode' in data:
                scrape_mode = data['scrape_mode']
                if isinstance(scrape_mode, str):
                    try:
                        ScrapeMode(scrape_mode)
                    except ValueError:
                        raise ValidationError(f"無效的抓取模式: {scrape_mode}")
                elif not isinstance(scrape_mode, ScrapeMode):
                    raise ValidationError(f"無效的抓取模式類型: {type(scrape_mode)}")

            return data

        def create_task(self, data):
            
            task_id = self.next_id
            # 創建任務物件，包含所有必要的屬性
            task_data = {
                'id': task_id,
                'task_name': data['task_name'],
                'crawler_id': data['crawler_id'],
                'is_scheduled': data.get('is_scheduled', False),
                'is_auto': data.get('is_auto', True),
                'ai_only': data.get('ai_only', False),
                'cron_expression': data.get('cron_expression'),
                'task_args': data.get('task_args', {}),
                'notes': data.get('notes'),
                'last_run_at': None,
                'last_run_success': None,
                'last_run_message': None,
                'current_phase': TaskPhase.INIT,
                'max_retries': data.get('max_retries', 3), # 從 data 讀取 max_retries
                'retry_count': 0,
                # 從頂層 data 讀取 scrape_mode，若無則使用預設值
                'scrape_mode': data.get('scrape_mode', ScrapeMode.FULL_SCRAPE.value),
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc),
                'status': 'pending'
            }
            task = CrawlerTaskMock(task_data)
            # 確保 scrape_mode 被正確設置為枚舉類型 (如果模型需要)
            if isinstance(task.scrape_mode, str):
                try:
                    task.scrape_mode = ScrapeMode(task.scrape_mode)
                except ValueError:
                    
                    return {'success': False, 'message': f"創建任務時發現無效的抓取模式: {task.scrape_mode}"}

            self.tasks[task_id] = task
            self.next_id += 1
            return {'success': True, 'task_id': task_id, 'message': '任務創建成功'}

        def get_task_by_id(self, task_id):
            task = self.tasks.get(task_id)
            if not task:
                return {'success': False, 'message': '任務不存在'}
            return {'success': True, 'task': task.to_dict()}  # 返回字典而非對象

        def update_task(self, task_id, data):

            if task_id not in self.tasks:
                return {'success': False, 'message': '任務不存在'}

            task = self.tasks[task_id]
            for key, value in data.items():
                # 特別處理 scrape_mode，確保設置的是枚舉類型 (如果模型需要)
                if key == 'scrape_mode':
                    if isinstance(value, str):
                        try:
                            setattr(task, key, ScrapeMode(value))
                        except ValueError:
                            
                            return {'success': False, 'message': f"更新任務時發現無效的抓取模式: {value}"}
                    elif isinstance(value, ScrapeMode):
                        setattr(task, key, value)
                    else:
                        # 可能的錯誤類型
                        return {'success': False, 'message': f"更新任務時無效的抓取模式類型: {type(value)}"}
                elif key != 'task_args': # 不要直接覆蓋 task_args，可能需要合併
                    setattr(task, key, value)

            # 合併 task_args (如果提供了)
            if 'task_args' in data and isinstance(data['task_args'], dict):
                 # 確保 task.task_args 是字典
                if not isinstance(task.task_args, dict):
                    task.task_args = {}
                task.task_args.update(data['task_args'])

            task.updated_at = datetime.now(timezone.utc)
            return {'success': True, 'task': task.to_dict(), 'message': '任務更新成功'}  # 返回字典而非對象

        def delete_task(self, task_id):
            if task_id not in self.tasks:
                return {'success': False, 'message': '任務不存在'}
            del self.tasks[task_id]
            return {'success': True, 'message': '任務刪除成功'}

        def get_all_tasks(self, filters=None):
            tasks = list(self.tasks.values())
            if filters:
                filtered_tasks = []
                for task in tasks:
                    match = True
                    for k, v in filters.items():
                        # 處理枚舉比較
                        attr_value = getattr(task, k, None)
                        if isinstance(attr_value, enum.Enum):
                            # 如果篩選值是字串，嘗試轉換或比較 .value
                            if isinstance(v, str):
                                if attr_value.value != v:
                                    match = False
                                    break
                            elif attr_value != v: # 如果篩選值也是枚舉
                                match = False
                                break
                        elif attr_value != v: # 其他類型直接比較
                            match = False
                            break
                    if match:
                        filtered_tasks.append(task)
                tasks = filtered_tasks

            # 將任務對象轉換為字典
            tasks_dicts = [task.to_dict() for task in tasks]
            return {'success': True, 'tasks': tasks_dicts}  # 返回字典列表而非對象列表

        def get_task_status(self, task_id):
            task = self.tasks.get(task_id)
            if not task:
                return {'success': False, 'message': '任務不存在'}

            # 返回狀態字典，根據服務的實際實現
            status_data = {
                'status': getattr(task, 'status', 'pending'),
                'progress': 50,
                'message': '任務執行中'
            }

            return {'success': True, 'status': status_data}

        def run_task(self, task_id, task_args=None): # task_args 仍然可以傳遞，但不用它來設置 scrape_mode
            task = self.tasks.get(task_id)
            if not task:
                return {'success': False, 'message': '任務不存在'}
            task.status = 'running'
            # 記錄開始時間
            task.last_run_at = datetime.now(timezone.utc)

            
            # 返回成功訊息和任務當前的 scrape_mode (從 task 物件讀取)
            current_scrape_mode = task.scrape_mode.value if hasattr(task.scrape_mode, 'value') else str(task.scrape_mode)
            return {'success': True, 'message': '任務開始執行', 'scrape_mode': current_scrape_mode}

        def fetch_article_content(self, task_id, link_ids):
            task = self.tasks.get(task_id)
            if not task:
                return {'success': False, 'message': '任務不存在'}
            # 模擬狀態變更
            task.status = 'content_scraping'
            task.current_phase = TaskPhase.CONTENT_SCRAPING
            # 設定抓取模式 (這個特定方法強制設定為 CONTENT_ONLY)
            task.scrape_mode = ScrapeMode.CONTENT_ONLY
            return {'success': True, 'message': '開始抓取文章內容', 'articles_count': len(link_ids)}

        def collect_article_links(self, task_id):
            task = self.tasks.get(task_id)
            if not task:
                return {'success': False, 'message': '任務不存在'}
            # 模擬狀態變更
            task.status = 'link_collecting'
            task.current_phase = TaskPhase.LINK_COLLECTION
            # 設定抓取模式 (這個特定方法強制設定為 LINKS_ONLY)
            task.scrape_mode = ScrapeMode.LINKS_ONLY
            return {
                'success': True,
                'message': '文章連結收集完成，共收集 5 個連結',
                'links_found': 5,
                'article_ids': [101, 102, 103, 104, 105],
                'next_step': 'content_scraping'
            }

        def test_crawler_task(self, crawler_data, task_data):
            # 模擬測試結果
            # 注意：這裡的 task_data 是傳入的，可能包含 'scrape_mode'
            # 根據需要決定如何在測試模擬中使用它
            test_scrape_mode = task_data.get('scrape_mode', ScrapeMode.LINKS_ONLY.value) # 測試時默認 LINKS_ONLY

            print(f"模擬測試爬蟲，抓取模式: {test_scrape_mode}")
            # ... 可以根據 test_scrape_mode 調整模擬的 links_found 等

            return {
                'success': True,
                'message': '爬蟲測試成功',
                'test_results': {
                    'links_found': 3,
                    'sample_links': [
                        'http://example.com/test1',
                        'http://example.com/test2',
                        'http://example.com/test3'
                    ]
                }
            }

        def cancel_task(self, task_id):
            task = self.tasks.get(task_id)
            if not task:
                return {'success': False, 'message': '任務不存在'}
            # 模擬任務取消
            task.status = 'cancelled'
            task.last_run_success = False
            task.last_run_message = '任務已手動取消'
            return {'success': True, 'message': '任務已取消'}

        def get_task_history(self, task_id):
            task = self.tasks.get(task_id)
            if not task:
                return {'success': False, 'message': '任務不存在'}

            # 如果沒有歷史記錄，返回空列表
            if task_id not in self.task_history:
                return {'success': True, 'history': []}

            return {'success': True, 'history': self.task_history[task_id]}

    mock_service = MockTaskService()
    # 模擬實際的 get_task_service 行為，注入 mock service
    # 注意：這裡需要確保 tasks_api 模塊中的 get_task_service 被正確 patch
    monkeypatch.setattr('src.web.routes.tasks_api.get_task_service', lambda: mock_service)
    # 同時也要 patch api_validators 中使用的 get_task_service (如果它直接導入的話)
    # 或者確保 tasks_api 中的 service 實例被傳遞給 validator
    # 更好的方式是讓 validator 接受 service 作為參數，就像現在這樣
    
    return mock_service

@pytest.fixture
def sample_articles():
    """創建測試用的文章數據"""
    return {
        1: [  # task_id: 1
            {
                'id': 1,
                'title': '未抓取文章1',
                'link': 'http://example.com/1',
                'scraped': False,
                'preview': True,
                'published_at': datetime.now(timezone.utc)
            },
            {
                'id': 2,
                'title': '未抓取文章2',
                'link': 'http://example.com/2',
                'scraped': False,
                'preview': True,
                'published_at': datetime.now(timezone.utc)
            },
            {
                'id': 3,
                'title': '已抓取文章1',
                'link': 'http://example.com/3',
                'scraped': True,
                'preview': False,
                'content': '這是文章1的內容...',
                'published_at': datetime.now(timezone.utc)
            },
            {
                'id': 4,
                'title': '已抓取文章2',
                'link': 'http://example.com/4',
                'scraped': True,
                'preview': False,
                'content': '這是文章2的內容...',
                'published_at': datetime.now(timezone.utc)
            }
        ],
        3: [  # task_id: 3 (手動任務)
            {
                'id': 5,
                'title': '手動任務文章1',
                'link': 'http://example.com/manual1',
                'scraped': False,
                'preview': True,
                'published_at': datetime.now(timezone.utc)
            },
            {
                'id': 6,
                'title': '手動任務文章2',
                'link': 'http://example.com/manual2',
                'scraped': False,
                'preview': True,
                'published_at': datetime.now(timezone.utc)
            }
        ]
    }

@pytest.fixture
def mock_article_service(monkeypatch, sample_articles):
    """模擬 ArticleService"""
    class MockArticleService:
        def __init__(self):
            self.articles = sample_articles

        def get_articles_by_task(self, filters):
            task_id = filters.get('task_id')

            if task_id not in self.articles:
                return {'success': False, 'message': '找不到相關文章'}

            articles = self.articles[task_id]
            filtered_articles = []

            # 應用過濾條件
            for article in articles:
                # 檢查 scraped 條件
                if 'scraped' in filters and article['scraped'] != filters['scraped']:
                    continue

                # 檢查 preview 條件
                if 'preview' in filters and article.get('preview', False) != filters['preview']:
                    continue
                
                filtered_articles.append(article)

            return {
                'success': True,
                'articles': filtered_articles
            }

    mock_service = MockArticleService()
    monkeypatch.setattr('src.web.routes.tasks_api.get_article_service', lambda: mock_service)
    return mock_service

@pytest.fixture
def mock_scheduler_service(monkeypatch):
    """模擬 SchedulerService 使用 MagicMock"""
    mock_scheduler = MagicMock()
    
    # 設置 cron_scheduler 屬性
    mock_cron = MagicMock()
    mock_cron.remove_job.return_value = True
    mock_cron.add_job.return_value = "job_1"
    mock_scheduler.cron_scheduler = mock_cron
    
    # 設置 _schedule_task 方法
    mock_scheduler._schedule_task.return_value = True

    # 應用模擬
    monkeypatch.setattr('src.web.routes.tasks_api.get_scheduler_service', lambda: mock_scheduler)
    return mock_scheduler

@pytest.fixture
def patch_scheduled_task(monkeypatch):
    """修補 _schedule_task 方法，避免 AttributeError"""
    def mock_schedule_task(self, task):
        """模擬成功排程任務"""
        return True
        
    monkeypatch.setattr('src.services.scheduler_service.SchedulerService._schedule_task', mock_schedule_task)
    
@pytest.fixture
def patch_scheduler_remove_job(monkeypatch):
    """修補 remove_job 方法，避免 JobLookupError"""
    def mock_remove_job(self, job_id, jobstore=None):
        """模擬成功移除任務"""
        return True
        
    monkeypatch.setattr('apscheduler.schedulers.base.BaseScheduler.remove_job', mock_remove_job)

@pytest.fixture
def patch_thread(monkeypatch):
    """修補線程創建，避免實際創建線程"""
    mock_thread = MagicMock()
    mock_thread.daemon = True
    mock_thread.start.return_value = None
    
    def mock_thread_init(*args, **kwargs):
        return mock_thread
        
    monkeypatch.setattr('threading.Thread', mock_thread_init)
    return mock_thread

@pytest.fixture
def mock_handle_api_error(monkeypatch):
    """模擬錯誤處理函數，確保正確的回應格式"""
    def mock_error_handler(error):
        if isinstance(error, ValidationError):
            # 為驗證錯誤添加 details 欄位
            return jsonify({
                "error": str(error),
                "type": "validation_error",
                "details": {"crawler_id": "此欄位為必填項"}
            }), 400
        # 其他錯誤類型
        return jsonify({"error": str(error)}), 500
    
    monkeypatch.setattr('src.web.routes.tasks_api.handle_api_error', mock_error_handler)
    return mock_error_handler

class TestTasksApiRoutes:
    """測試任務相關的 API 路由"""

    def test_get_scheduled_tasks(self, client, mock_task_service):
        """測試獲取排程任務列表"""
        response = client.get('/api/tasks/scheduled')
        assert response.status_code == 200
        data = json.loads(response.data)
        # 應該有兩個排程任務 (task_id: 1, 2)
        assert len(data) == 2
        assert any(task['task_name'] == '每日新聞爬取' for task in data)
        assert any(task['task_name'] == '週間財經新聞' for task in data)

    def test_create_scheduled_task(self, client, mock_task_service, patch_scheduled_task):
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
        assert data['task_id'] == 4  # 基於 sample_tasks 的 next_id

    def test_get_scheduled_task(self, client, mock_task_service):
        """測試獲取單個排程任務"""
        response = client.get('/api/tasks/scheduled/1')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['task_name'] == '每日新聞爬取'
        assert data['cron_expression'] == '0 0 * * *'

    def test_update_scheduled_task(self, client, mock_task_service, patch_scheduled_task):
        """測試更新排程任務"""
        update_data = {
            'task_name': '更新後的任務',
            'cron_expression': '0 12 * * *'
        }

        response = client.put('/api/tasks/scheduled/1', json=update_data)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['task_name'] == '更新後的任務'
        assert data['cron_expression'] == '0 12 * * *'

    def test_delete_scheduled_task(self, client, mock_task_service, patch_scheduler_remove_job):
        """測試刪除排程任務"""
        response = client.delete('/api/tasks/scheduled/1')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['message'] == 'Deleted'

        # 檢查任務是否已刪除
        response = client.get('/api/tasks/scheduled/1')
        assert response.status_code == 404

    def test_start_manual_task(self, client, mock_task_service, patch_thread):
        """測試開始手動任務"""
        task_data = {
            'task_name': '新手動任務',
            'crawler_id': 1,
            'is_scheduled': False,
            'task_args': {
                'max_items': 50,
                'scrape_mode': 'full_scrape'  # 測試顯式設置抓取模式
            }
        }

        response = client.post('/api/tasks/manual/start', json=task_data)
        assert response.status_code == 202
        data = json.loads(response.data)
        assert 'task_id' in data
        assert data['status'] == 'pending'
        assert 'scrape_mode' in data
        assert data['scrape_mode'] == 'full_scrape'

    def test_get_manual_task_status(self, client, mock_task_service):
        """測試獲取手動任務狀態"""
        response = client.get('/api/tasks/manual/3/status')
        assert response.status_code == 200
        data = json.loads(response.data)

        # 檢查返回的狀態對象
        assert 'status' in data
        assert isinstance(data['status'], str)
        assert 'progress' in data
        assert 'message' in data

    def test_get_manual_task_links(self, client, mock_task_service, mock_article_service):
        """測試獲取手動任務的文章連結"""
        response = client.get('/api/tasks/manual/3/links')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 2  # 應該有兩個未抓取的預覽文章
        assert all('title' in article for article in data)
        assert all('link' in article for article in data)
        assert data[0]['title'] == '手動任務文章1'

    def test_fetch_manual_task_content(self, client, mock_task_service, patch_thread):
        """測試抓取手動任務的文章內容"""
        response = client.post('/api/tasks/manual/3/fetch-content', json={'link_ids': [5, 6]})
        assert response.status_code == 202
        data = json.loads(response.data)
        assert data['message'] == 'Content fetching initiated'
        assert 'scrape_mode' in data
        assert data['scrape_mode'] == 'content_only'
        assert 'link_count' in data
        assert data['link_count'] == 2

    def test_get_manual_task_results(self, client, mock_task_service, mock_article_service):
        """測試獲取手動任務的結果"""
        # 先添加一些已抓取的文章以供測試
        mock_article_service.articles[3].append({
            'id': 7,
            'title': '已抓取手動任務文章',
            'link': 'http://example.com/manual_scraped',
            'scraped': True,
            'preview': False,
            'content': '這是手動任務抓取的文章內容...',
            'published_at': datetime.now(timezone.utc)
        })

        response = client.get('/api/tasks/manual/3/results')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 1  # 應該有一個已抓取的文章
        assert data[0]['title'] == '已抓取手動任務文章'
        assert 'content' in data[0]

    def test_test_crawler(self, client, mock_task_service):
        """測試爬蟲測試功能"""
        test_data = {
            'task_data': {
                'task_name': '測試爬蟲',
                'crawler_id': 1,
                'task_args': {'test_mode': True}
            },
            'crawler_data': {
                'crawler_name': 'TestCrawler',
                'base_url': 'https://example.com'
            }
        }

        response = client.post('/api/tasks/manual/test', json=test_data)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'test_results' in data
        assert 'links_found' in data['test_results']
        assert data['test_results']['links_found'] == 3

    def test_cancel_task(self, client, mock_task_service):
        """測試取消任務"""
        # 先將任務設為運行中
        task = mock_task_service.tasks[3]
        task.status = 'running'

        response = client.post('/api/tasks/3/cancel')
        assert response.status_code == 202
        data = json.loads(response.data)
        assert data['message'] == 'Cancellation requested'
        
        # 檢查任務是否已被取消
        assert mock_task_service.tasks[3].status == 'cancelled'

    def test_get_task_history(self, client, mock_task_service):
        """測試獲取任務歷史記錄"""
        # 添加一些歷史記錄供測試
        mock_task_service.task_history[1] = [
            {
                'id': 1,
                'task_id': 1,
                'start_time': datetime.now(timezone.utc).isoformat(),
                'end_time': datetime.now(timezone.utc).isoformat(),
                'success': True,
                'message': '執行成功',
                'articles_count': 10
            },
            {
                'id': 2,
                'task_id': 1,
                'start_time': datetime.now(timezone.utc).isoformat(),
                'end_time': datetime.now(timezone.utc).isoformat(),
                'success': False,
                'message': '執行失敗',
                'articles_count': 0
            }
        ]

        response = client.get('/api/tasks/1/history')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]['success'] is True
        assert data[1]['success'] is False

    def test_task_not_found(self, client, mock_task_service):
        """測試請求不存在的任務"""
        response = client.get('/api/tasks/scheduled/999')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data

    
    def test_collect_manual_task_links(self, client, mock_task_service, patch_thread):
        """測試收集手動任務的文章連結"""
        # 發送 POST 請求並包含空的 JSON body
        response = client.post('/api/tasks/manual/3/collect-links', json={}) 
        assert response.status_code == 202
        data = json.loads(response.data)
        assert data['message'] == 'Link collection initiated'
        assert 'scrape_mode' in data
        assert data['scrape_mode'] == 'links_only'

    def test_invalid_scrape_mode(self, client, mock_task_service):
        """測試無效的抓取模式"""
        # 測試將 scrape_mode 放在頂層
        task_data = {
            'task_name': '無效模式任務',
            'crawler_id': 1,
            'is_scheduled': False,
            'scrape_mode': 'invalid_mode'  # 無效的抓取模式
        }

        response = client.post('/api/tasks/manual/start', json=task_data)
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        # 更新斷言以匹配實際的錯誤消息格式
        assert '無效的抓取模式' in data['error'] or '無效的scrape_mode值' in data['error']

    def test_manual_task_with_default_scrape_mode(self, client, mock_task_service, patch_thread):
        """測試未指定抓取模式時的默認模式"""
        task_data = {
            'task_name': '默認模式任務',
            'crawler_id': 1,
            'is_scheduled': False,
            'task_args': {
                'max_items': 50
                # 不指定scrape_mode
            }
        }

        response = client.post('/api/tasks/manual/start', json=task_data)
        assert response.status_code == 202
        data = json.loads(response.data)
        assert 'scrape_mode' in data
        assert data['scrape_mode'] == 'full_scrape'  # 默認應該是full_scrape 