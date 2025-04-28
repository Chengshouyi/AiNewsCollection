"""測試 src.web.routes.tasks_api 中的 API 路由功能"""
import json
import enum
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from unittest.mock import patch, MagicMock

import pytest
from flask import Flask

from src.web.routes.tasks_api import tasks_bp
from src.error.errors import ValidationError, DatabaseOperationError
from src.error.handle_api_error import handle_api_error
from src.models.crawler_tasks_model import ScrapePhase, ScrapeMode, TaskStatus, TASK_ARGS_DEFAULT
from src.models.crawler_tasks_schema import CrawlerTaskReadSchema
from src.models.crawler_task_history_schema import CrawlerTaskHistoryReadSchema
from src.utils.log_utils import LoggerSetup # 使用統一的 logger

# flake8: noqa: F811
# pylint: disable=redefined-outer-name

logger = LoggerSetup.setup_logger(__name__) # 使用統一的 logger

@pytest.fixture
def app():
    """創建測試用的 Flask 應用程式"""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['JSON_AS_ASCII'] = False
    app.config['JSON_SORT_KEYS'] = False

    # 註冊路由藍圖
    app.register_blueprint(tasks_bp)

    # 使用實際的錯誤處理器
    @app.errorhandler(Exception)
    def error_handler(e):
        return handle_api_error(e)

    return app

@pytest.fixture
def client(app):
    """創建測試客戶端"""
    return app.test_client()

class CrawlerTaskMock:
    """模擬 CrawlerTasks ORM 對象"""
    def __init__(self, data):
        self.id = data.get('id')
        self.task_name = data.get('task_name')
        self.crawler_id = data.get('crawler_id')
        self.is_auto = data.get('is_auto', True)
        self.is_active = data.get('is_active', True)
        self.ai_only = data.get('ai_only', False)
        self.task_args = data.get('task_args', {})
        self.notes = data.get('notes')
        self.last_run_at = data.get('last_run_at')
        self.last_run_success = data.get('last_run_success')
        self.last_run_message = data.get('last_run_message')
        self.cron_expression = data.get('cron_expression')
        self.is_scheduled = data.get('is_scheduled', False)
        self.task_status = data.get('task_status', TaskStatus.INIT)
        self.scrape_phase = data.get('scrape_phase', ScrapePhase.INIT)
        self.max_retries = data.get('max_retries', 3)
        self.retry_count = data.get('retry_count', 0)
        self.scrape_mode = data.get('scrape_mode', ScrapeMode.FULL_SCRAPE)
        self.created_at = data.get('created_at', datetime.now(timezone.utc))
        self.updated_at = data.get('updated_at', datetime.now(timezone.utc))

        # 確保枚舉類型正確
        if isinstance(self.task_status, str):
            self.task_status = TaskStatus(self.task_status)
        if isinstance(self.scrape_phase, str):
            self.scrape_phase = ScrapePhase(self.scrape_phase)
        if isinstance(self.scrape_mode, str):
            self.scrape_mode = ScrapeMode(self.scrape_mode)


    def model_dump(self):
        """模擬 Pydantic 的 model_dump"""
        return {
            'id': self.id,
            'task_name': self.task_name,
            'crawler_id': self.crawler_id,
            'is_auto': self.is_auto,
            'is_active': self.is_active,
            'ai_only': self.ai_only,
            'task_args': self.task_args,
            'notes': self.notes,
            'last_run_at': self.last_run_at.isoformat() if isinstance(self.last_run_at, datetime) else self.last_run_at,
            'last_run_success': self.last_run_success,
            'last_run_message': self.last_run_message,
            'cron_expression': self.cron_expression,
            'is_scheduled': self.is_scheduled,
            'task_status': self.task_status.value if hasattr(self.task_status, 'value') else self.task_status,
            'scrape_phase': self.scrape_phase.value if hasattr(self.scrape_phase, 'value') else self.scrape_phase,
            'max_retries': self.max_retries,
            'retry_count': self.retry_count,
            'scrape_mode': self.scrape_mode.value if hasattr(self.scrape_mode, 'value') else self.scrape_mode,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'updated_at': self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
        }

class CrawlerTaskHistoryMock:
    """模擬 CrawlerTaskHistory ORM 對象"""
    def __init__(self, data):
        self.id = data.get('id')
        self.task_id = data.get('task_id')
        self.start_time = data.get('start_time', datetime.now(timezone.utc))
        self.end_time = data.get('end_time')
        self.success = data.get('success', None)
        self.message = data.get('message')
        self.articles_count = data.get('articles_count', 0)
        self.task_status = data.get('task_status', TaskStatus.INIT)

        # 確保枚舉類型正確
        if isinstance(self.task_status, str):
             self.task_status = TaskStatus(self.task_status)

    def model_dump(self):
        """模擬 Pydantic 的 model_dump"""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'start_time': self.start_time.isoformat() if isinstance(self.start_time, datetime) else self.start_time,
            'end_time': self.end_time.isoformat() if isinstance(self.end_time, datetime) else self.end_time,
            'success': self.success,
            'message': self.message,
            'articles_count': self.articles_count,
            'task_status': self.task_status.value if hasattr(self.task_status, 'value') else self.task_status,
        }

@pytest.fixture
def sample_tasks_data():
    """創建測試用的爬蟲任務數據"""
    now = datetime.now(timezone.utc)
    return [
        {
            'id': 1, 'task_name': '每日新聞爬取', 'crawler_id': 1, 'is_auto': True, 'is_active': True,
            'task_args': {'max_items': 100, 'scrape_mode': ScrapeMode.FULL_SCRAPE.value},
            'cron_expression': '0 0 * * *', 'is_scheduled': True, 'task_status': TaskStatus.INIT,
            'scrape_phase': ScrapePhase.INIT, 'scrape_mode': ScrapeMode.FULL_SCRAPE, 'created_at': now, 'updated_at': now
        },
        {
            'id': 2, 'task_name': '週間財經新聞', 'crawler_id': 1, 'is_auto': True, 'is_active': True,
            'task_args': {'max_items': 50, 'scrape_mode': ScrapeMode.FULL_SCRAPE.value},
            'cron_expression': '0 0 * * 1-5', 'is_scheduled': True, 'task_status': TaskStatus.INIT,
            'scrape_phase': ScrapePhase.INIT, 'scrape_mode': ScrapeMode.FULL_SCRAPE, 'created_at': now, 'updated_at': now
        },
        {
            'id': 3, 'task_name': '手動採集任務', 'crawler_id': 1, 'is_auto': False, 'is_active': True,
            'task_args': {'max_pages': 5, 'scrape_mode': ScrapeMode.FULL_SCRAPE.value},
            'is_scheduled': False, 'task_status': TaskStatus.INIT,
            'scrape_phase': ScrapePhase.INIT, 'scrape_mode': ScrapeMode.FULL_SCRAPE, 'created_at': now, 'updated_at': now
        }
    ]

@pytest.fixture
def sample_history_data():
     """創建測試用的歷史記錄數據"""
     now = datetime.now(timezone.utc)
     start = now - timedelta(minutes=5)
     return [
         {'id': 101, 'task_id': 1, 'start_time': start, 'end_time': now, 'success': True, 'message': '執行成功', 'articles_count': 10, 'task_status': TaskStatus.COMPLETED},
         {'id': 102, 'task_id': 1, 'start_time': start - timedelta(days=1), 'end_time': now - timedelta(days=1), 'success': False, 'message': '執行失敗', 'articles_count': 0, 'task_status': TaskStatus.FAILED},
         {'id': 103, 'task_id': 3, 'start_time': start, 'end_time': None, 'success': None, 'message': '任務執行中', 'articles_count': 0, 'task_status': TaskStatus.RUNNING},
     ]

@pytest.fixture
def mock_task_service(monkeypatch, sample_tasks_data, sample_history_data):
    """模擬 CrawlerTaskService"""
    class MockTaskService:
        def __init__(self):
            self.tasks = {task['id']: CrawlerTaskMock(task) for task in sample_tasks_data}
            self.task_history = {}
            for history in sample_history_data:
                task_id = history['task_id']
                if task_id not in self.task_history:
                    self.task_history[task_id] = []
                self.task_history[task_id].append(CrawlerTaskHistoryMock(history))
            self.next_id = max(self.tasks.keys() or [0]) + 1
            all_history_ids = [h.id for histories in self.task_history.values() for h in histories if h.id is not None]
            self.next_history_id = max(all_history_ids or [100]) + 1


        def validate_task_data(self, data: Dict[str, Any], is_update=False) -> Dict[str, Any]:
            # 模擬資料驗證行為

            if data.get('is_auto') is True:
                if data.get('cron_expression') is None:
                    return {
                        'success': False,
                        'message': "資料驗證失敗：cron_expression: 當設定為自動執行時,此欄位不能為空",
                        'data': None
                    }

            task_args = data.get('task_args', {})

            if task_args.get('scrape_mode') == ScrapeMode.CONTENT_ONLY.value:
                if 'get_links_by_task_id' not in task_args:
                    task_args['get_links_by_task_id'] = True

                if not task_args.get('get_links_by_task_id'):
                    if 'article_links' not in task_args:
                        return {
                            'success': False,
                            'message': "資料驗證失敗：內容抓取模式需要提供 article_links",
                            'data': None
                        }

            errors = {}
            if not is_update:
                if 'task_name' not in data or not data['task_name']:
                    errors['task_name'] = '此欄位不能為空'
                crawler_id = data.get('crawler_id')
                if crawler_id is None or not isinstance(crawler_id, int) or crawler_id <= 0:
                    errors['crawler_id'] = '此欄位不能為空且必須為正整數'

            if 'scrape_mode' in data and data['scrape_mode']:
                try:
                    ScrapeMode(data['scrape_mode'])
                except ValueError:
                    errors['scrape_mode'] = f"無效的抓取模式: {data['scrape_mode']}"

            if errors:
                error_details = ", ".join([f"{field}: {msg}" for field, msg in errors.items()])
                return {
                    'success': False,
                    'message': f"資料驗證失敗：{error_details}",
                    'data': None
                }

            data['task_args'] = task_args
            return {
                'success': True,
                'message': '資料驗證成功',
                'data': data
            }

        def create_task(self, data):
            validated_result = self.validate_task_data(data, is_update=False)
            if not validated_result['success']:
                return validated_result

            validated_data = validated_result['data']

            scrape_mode_value = validated_data.get('task_args', {}).get('scrape_mode', ScrapeMode.FULL_SCRAPE.value)
            try:
                scrape_mode_enum = ScrapeMode(scrape_mode_value)
            except ValueError:
                scrape_mode_enum = ScrapeMode.FULL_SCRAPE

            task_id = self.next_id
            task_data_full = {
                'id': task_id,
                'task_name': validated_data['task_name'],
                'crawler_id': validated_data['crawler_id'],
                'is_auto': validated_data.get('is_auto', False),
                'is_active': validated_data.get('is_active', True),
                'ai_only': validated_data.get('ai_only', False),
                'task_args': validated_data.get('task_args', {}),
                'notes': validated_data.get('notes'),
                'cron_expression': validated_data.get('cron_expression'),
                'is_scheduled': False,
                'task_status': TaskStatus.INIT,
                'scrape_phase': ScrapePhase.INIT,
                'max_retries': validated_data.get('task_args', {}).get('max_retries', TASK_ARGS_DEFAULT.get('max_retries', 3)),
                'retry_count': 0,
                'scrape_mode': scrape_mode_enum,
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc)
            }
            task = CrawlerTaskMock(task_data_full)
            self.tasks[task_id] = task
            self.next_id += 1
            return {'success': True, 'task': task, 'message': '任務創建成功'}

        def get_task_by_id(self, task_id, is_active=None):
            task = self.tasks.get(task_id)
            if not task:
                return {'success': False, 'message': '任務不存在', 'task': None}
            if is_active is not None and task.is_active != is_active:
                 return {'success': False, 'message': f'任務 {task_id} 的活躍狀態不匹配', 'task': None}
            return {'success': True, 'task': task}

        def update_task(self, task_id, data):
            if task_id not in self.tasks:
                return {'success': False, 'message': '任務不存在', 'task': None}
            task = self.tasks[task_id]
            validated_data = self.validate_task_data(data, is_update=True)
            if not validated_data['success']:
                 return validated_data

            update_data = validated_data['data']

            for key, value in update_data.items():
                if key == 'scrape_mode':
                    setattr(task, key, ScrapeMode(value) if isinstance(value, str) else value)
                elif key == 'task_status':
                    setattr(task, key, TaskStatus(value) if isinstance(value, str) else value)
                elif key == 'scrape_phase':
                    setattr(task, key, ScrapePhase(value) if isinstance(value, str) else value)
                elif key == 'task_args':
                    current_args = task.task_args if isinstance(task.task_args, dict) else {}
                    if isinstance(value, dict):
                        current_args.update(value)
                        task.task_args = current_args
                    else:
                         logger.warning(f"task_args for task {task_id} is not a dict: {value}")
                         task.task_args = value
                elif hasattr(task, key):
                    setattr(task, key, value)

            task.updated_at = datetime.now(timezone.utc)
            return {'success': True, 'task': task, 'message': '任務更新成功'}

        def delete_task(self, task_id):
            if task_id not in self.tasks:
                return {'success': False, 'message': '任務不存在'}
            del self.tasks[task_id]
            if task_id in self.task_history:
                del self.task_history[task_id]
            return {'success': True, 'message': '任務刪除成功'}

        def find_tasks_advanced(self, page=1, per_page=10, is_preview=False, **filters):
            tasks = list(self.tasks.values())
            filtered_tasks = []
            sort_by = filters.pop('sort_by', None)
            sort_desc = filters.pop('sort_desc', True)

            for task in tasks:
                match = True
                for k, v in filters.items():
                    if not hasattr(task, k):
                        match = False; break
                    attr_value = getattr(task, k)
                    if isinstance(attr_value, enum.Enum):
                        enum_value = attr_value.value
                        if isinstance(v, enum.Enum):
                            if enum_value != v.value: match = False; break
                        elif enum_value != v:
                            match = False; break
                    elif attr_value != v:
                        match = False; break
                if match:
                    filtered_tasks.append(task)

            total_count = len(filtered_tasks)
            start = (page - 1) * per_page
            end = start + per_page
            paginated_tasks = filtered_tasks[start:end]
            total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

            items_to_return = []
            if not is_preview:
                 items_to_return = paginated_tasks
            else:
                 items_to_return = [t.model_dump() for t in paginated_tasks]

            paginated_response = {
                'items': items_to_return,
                'page': page,
                'per_page': per_page,
                'total': total_count,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
            return {'success': True, 'data': paginated_response, 'message': '任務搜尋成功'}

        def find_task_history(self, task_id, limit=None, offset=None, sort_desc=True, is_preview=False):
            task = self.tasks.get(task_id)
            if not task:
                 # return {'success': False, 'message': '任務不存在', 'history': []} # 保持原樣或修改以匹配API
                 return {'success': False, 'message': '任務不存在', 'history': []} # 修正 key 名稱

            histories = self.task_history.get(task_id, [])
            histories_with_dt = [h for h in histories if isinstance(h.start_time, datetime)]
            histories_with_dt.sort(key=lambda h: h.start_time, reverse=sort_desc)
            start = offset if offset is not None else 0
            end = (start + limit) if limit is not None else None
            histories_to_return = histories_with_dt[start:end]

            # 修正 key 名稱
            return {'success': True, 'history': histories_to_return, 'message': '任務歷史獲取成功'}

    mock_service = MockTaskService()
    monkeypatch.setattr('src.web.routes.tasks_api.get_crawler_task_service', lambda: mock_service)
    return mock_service

@pytest.fixture
def sample_articles_data():
    """創建測試用的文章數據"""
    now = datetime.now(timezone.utc).isoformat()
    return {
        1: [
            {'id': 1, 'task_id': 1, 'title': '未抓取文章1', 'link': 'http://example.com/1', 'is_scraped': False, 'source': 'Test', 'published_at': now, 'summary': '摘要1'},
            {'id': 2, 'task_id': 1, 'title': '未抓取文章2', 'link': 'http://example.com/2', 'is_scraped': False, 'source': 'Test', 'published_at': now, 'summary': '摘要2'},
            {'id': 3, 'task_id': 1, 'title': '已抓取文章1', 'link': 'http://example.com/3', 'is_scraped': True, 'source': 'Test', 'published_at': now, 'summary': '摘要3'},
        ],
        2: [
             {'id': 6, 'task_id': 2, 'title': '任務2已抓取', 'link': 'http://ex.com/t2_scraped', 'is_scraped': True, 'source': 'T2Source', 'published_at': now, 'summary': 'T2S'}
        ],
        3: [
            {'id': 4, 'task_id': 3, 'title': '手動未抓取1', 'link': 'http://example.com/manual1', 'is_scraped': False, 'source': 'Manual', 'published_at': now, 'summary': '手動摘要1'},
            {'id': 5, 'task_id': 3, 'title': '手動已抓取1', 'link': 'http://example.com/manual_scraped', 'is_scraped': True, 'source': 'Manual', 'published_at': now, 'summary': '手動摘要S1'},
        ]
    }

@pytest.fixture
def mock_article_service(monkeypatch, sample_articles_data):
    """模擬 ArticleService"""
    class MockArticleService:
        def find_unscraped_articles(self, task_id, is_preview=False, limit=None, **kwargs):
            articles = sample_articles_data.get(task_id, [])
            unscraped = [a for a in articles if not a.get('is_scraped', False)]
            if limit:
                unscraped = unscraped[:limit]
            if not unscraped:
                 msg = '未找到未抓取的文章' if task_id in sample_articles_data else '找不到任務相關文章'
                 return {'success': False, 'message': msg, 'articles': []}
            if is_preview:
                 preview_articles = [{k: v for k, v in a.items() if k in {'title', 'link', 'summary', 'source', 'published_at'}} for a in unscraped]
                 return {'success': True, 'articles': preview_articles}
            return {'success': True, 'articles': unscraped}

        def find_scraped_articles(self, task_id, is_preview=False, limit=None, **kwargs):
            articles = sample_articles_data.get(task_id, [])
            scraped = [a for a in articles if a.get('is_scraped', False)]
            if limit:
                scraped = scraped[:limit]
            if not scraped:
                 msg = '未找到已抓取的文章' if task_id in sample_articles_data else '找不到任務相關文章'
                 return {'success': False, 'message': msg, 'articles': []}
            if is_preview:
                 preview_articles = [{k: v for k, v in a.items() if k in {'title', 'link', 'summary', 'source'}} for a in scraped]
                 return {'success': True, 'articles': preview_articles}
            return {'success': True, 'articles': scraped}

    mock_service = MockArticleService()
    monkeypatch.setattr('src.web.routes.tasks_api.get_article_service', lambda: mock_service)
    return mock_service

@pytest.fixture
def mock_scheduler_service(monkeypatch):
    """模擬 SchedulerService"""
    mock_scheduler = MagicMock()
    mock_scheduler.add_or_update_task_to_scheduler.return_value = {'success': True, 'message': '排程成功', 'added_count': 1, 'updated_count': 0}
    mock_scheduler.remove_task_from_scheduler.return_value = {'success': True, 'message': '移除排程成功'}
    monkeypatch.setattr('src.web.routes.tasks_api.get_scheduler_service', lambda: mock_scheduler)
    return mock_scheduler

@pytest.fixture
def mock_task_executor_service(monkeypatch, mock_task_service):
    """模擬 TaskExecutorService"""
    class MockTaskExecutorService:
        def execute_task(self, task_id, is_async=True, **kwargs):
             task = mock_task_service.tasks.get(task_id)
             if task:
                 task.task_status = TaskStatus.COMPLETED
                 task.scrape_phase = ScrapePhase.COMPLETED
                 task.last_run_at = datetime.now(timezone.utc)
                 task.last_run_success = True
                 task.last_run_message = "模擬執行成功"
                 if 'scrape_mode' in kwargs:
                     task.scrape_mode = ScrapeMode(kwargs['scrape_mode'])
                 op_type = kwargs.get('operation_type')
                 if op_type == 'fetch_full_article':
                     task.scrape_phase = ScrapePhase.COMPLETED
                 elif op_type == 'collect_links_only':
                     task.scrape_phase = ScrapePhase.LINK_COLLECTION
                 elif op_type == 'fetch_content_only':
                     task.scrape_phase = ScrapePhase.CONTENT_SCRAPING

                 return {'success': True, 'message': f'任務 {task_id} 模擬執行成功', 'task_status': TaskStatus.COMPLETED.value, 'scrape_phase': task.scrape_phase.value}
             else:
                 return {'success': False, 'message': f'任務 {task_id} 不存在', 'task_status': TaskStatus.FAILED.value}

        def fetch_full_article(self, task_id, is_async=True, **kwargs):
            kwargs['operation_type'] = 'fetch_full_article'
            result = self.execute_task(task_id, is_async, **kwargs)
            result['articles_count'] = 5
            return result

        def get_task_status(self, task_id):
            task = mock_task_service.tasks.get(task_id)
            if not task:
                return {
                    'success': False, 'message': '任務不存在',
                    'task_status': TaskStatus.UNKNOWN.value, 'scrape_phase': ScrapePhase.UNKNOWN.value,
                    'progress': 0, 'task': None
                }
            return {
                'success': True,
                'task_status': task.task_status.value,
                'scrape_phase': task.scrape_phase.value,
                'progress': 100 if task.task_status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED] else 50,
                'message': task.last_run_message or f'任務 {task_id} 狀態',
                'task': task
            }

        def collect_links_only(self, task_id, is_async=True, **kwargs):
            kwargs['operation_type'] = 'collect_links_only'
            result = self.execute_task(task_id, is_async, **kwargs)
            result['link_count'] = 10
            return result

        def fetch_content_only(self, task_id, is_async=True, **kwargs):
            kwargs['operation_type'] = 'fetch_content_only'
            result = self.execute_task(task_id, is_async, **kwargs)
            result['articles_processed'] = 8
            return result

        def test_crawler(self, crawler_name, test_params):
             return {
                 'success': True,
                 'message': f'爬蟲 {crawler_name} 測試成功',
                 'result': {
                     'links_found': 3,
                     'sample_links': ['http://test.com/1', 'http://test.com/2'],
                     'validated_params': test_params
                 }
             }

        def cancel_task(self, task_id):
             task = mock_task_service.tasks.get(task_id)
             if not task:
                 return {'success': False, 'message': '任務不存在'}
             if task.task_status == TaskStatus.RUNNING:
                 task.task_status = TaskStatus.CANCELLED
                 task.scrape_phase = ScrapePhase.CANCELLED
                 return {'success': True, 'message': f'任務 {task_id} 已取消'}
             else:
                  return {'success': False, 'message': f'任務 {task_id} 未在運行中，無法取消'}

    mock_service = MockTaskExecutorService()
    monkeypatch.setattr('src.web.routes.tasks_api.get_task_executor_service', lambda: mock_service)
    return mock_service


# --- Test Cases ---

class TestTasksApiRoutes:
    """測試任務相關的 API 路由"""

    def test_get_scheduled_tasks(self, client, mock_task_service):
        """測試獲取排程任務列表"""
        def mock_find_tasks_advanced(**filters):
            tasks = [mock_task_service.tasks[1], mock_task_service.tasks[2]]
            return {
                'success': True,
                'data': {
                    'items': tasks,
                    'page': 1, 'per_page': len(tasks), 'total': len(tasks), 'total_pages': 1,
                    'has_next': False, 'has_prev': False
                },
                'message': '模擬搜尋成功'
            }
        mock_task_service.find_tasks_advanced = mock_find_tasks_advanced

        response = client.get('/api/tasks/scheduled')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 2
        assert all(isinstance(task, dict) for task in data)
        assert all(task['is_scheduled'] is True and task['is_active'] is True and task['is_auto'] is True for task in data)
        assert any(task['task_name'] == '每日新聞爬取' for task in data)

    def test_create_scheduled_task(self, client, mock_task_service, mock_scheduler_service):
        """測試創建排程任務"""
        task_data = {
            'task_name': '新排程任務',
            'crawler_id': 1,
            'cron_expression': '0 0 * * *',
            'task_args': {'max_items': 100, 'scrape_mode': 'full_scrape'}
        }
        response = client.post('/api/tasks/scheduled', json=task_data)
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['success'] is True
        assert '任務創建成功' in data['message']
        assert 'task' in data
        new_task_id = data['task']['id']
        assert new_task_id == 4
        assert data['task']['task_name'] == '新排程任務'
        assert data['task']['is_auto'] is True
        assert data['task']['is_scheduled'] is False
        assert data['task']['cron_expression'] == '0 0 * * *'
        assert data['task']['task_args']['scrape_mode'] == 'full_scrape'
        mock_scheduler_service.add_or_update_task_to_scheduler.assert_called_once()
        call_args = mock_scheduler_service.add_or_update_task_to_scheduler.call_args[0][0]
        assert isinstance(call_args, CrawlerTaskMock)
        assert call_args.id == new_task_id

    def test_create_scheduled_task_scheduler_fail(self, client, mock_task_service, mock_scheduler_service):
        """測試創建任務成功但排程失敗"""
        mock_scheduler_service.add_or_update_task_to_scheduler.return_value = {'success': False, 'message': '排程器錯誤'}
        task_data = {
            'task_name': '排程失敗任務', 'crawler_id': 1, 'cron_expression': '0 1 * * *',
            'task_args': {'scrape_mode': 'full_scrape'}
        }
        response = client.post('/api/tasks/scheduled', json=task_data)
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['success'] is True
        assert '任務創建成功' in data['message']
        assert '添加到排程器失敗: 排程器錯誤' in data['message']
        assert data['task']['id'] == 4

    def test_update_scheduled_task(self, client, mock_task_service, mock_scheduler_service):
        """測試更新排程任務"""
        update_data = {
            'task_name': '更新後的任務',
            'cron_expression': '0 12 * * *',
            'task_args': {'max_items': 200}
        }
        response = client.put('/api/tasks/scheduled/1', json=update_data)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert '任務更新成功' in data['message']
        assert data['task']['id'] == 1
        assert data['task']['task_name'] == '更新後的任務'
        assert data['task']['cron_expression'] == '0 12 * * *'
        assert data['task']['task_args']['max_items'] == 200
        mock_scheduler_service.add_or_update_task_to_scheduler.assert_called_once()
        call_args = mock_scheduler_service.add_or_update_task_to_scheduler.call_args[0][0]
        assert isinstance(call_args, CrawlerTaskMock)
        assert call_args.id == 1
        assert call_args.task_name == '更新後的任務'

    def test_update_scheduled_task_not_found(self, client, mock_task_service):
        """測試更新不存在的任務"""
        response = client.put('/api/tasks/scheduled/999', json={'task_name': '不存在'})
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False
        assert '任務不存在' in data['message']

    def test_delete_scheduled_task(self, client, mock_task_service, mock_scheduler_service):
        """測試刪除排程任務"""
        response = client.delete('/api/tasks/scheduled/1')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert '任務刪除成功' in data['message']
        mock_scheduler_service.remove_task_from_scheduler.assert_called_once_with(1)
        assert 1 not in mock_task_service.tasks

    def test_delete_scheduled_task_scheduler_fail(self, client, mock_task_service, mock_scheduler_service):
        """測試刪除任務時排程器移除失敗"""
        mock_scheduler_service.remove_task_from_scheduler.return_value = {'success': False, 'message': '排程器中未找到'}
        response = client.delete('/api/tasks/scheduled/2')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert '任務刪除成功' in data['message']
        assert '(排程器移除訊息: 排程器中未找到)' in data['message']
        assert 2 not in mock_task_service.tasks

    def test_fetch_full_article_manual_task(self, client, mock_task_service, mock_task_executor_service):
        """測試開始手動 full_scrape 任務"""
        task_data = {
            'task_name': '新手動全爬任務',
            'crawler_id': 1,
            'task_args': {'max_items': 50}
        }
        response = client.post('/api/tasks/manual/start', json=task_data)
        assert response.status_code == 202
        data = json.loads(response.data)
        assert data['success'] is True
        assert '任務 4 模擬執行成功' in data['message']
        assert data['task_status'] == TaskStatus.COMPLETED.value
        assert data['scrape_phase'] == ScrapePhase.COMPLETED.value
        assert 4 in mock_task_service.tasks
        created_task = mock_task_service.tasks[4]
        assert created_task.is_auto is False
        assert created_task.scrape_mode == ScrapeMode.FULL_SCRAPE

    def test_get_task_status(self, client, mock_task_service, mock_task_executor_service):
        """測試獲取任務狀態"""
        mock_task_service.tasks[3].task_status = TaskStatus.RUNNING
        mock_task_service.tasks[3].scrape_phase = ScrapePhase.LINK_COLLECTION
        mock_task_service.tasks[3].last_run_message = "正在收集中..."

        response = client.get('/api/tasks/manual/3/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['task_status'] == TaskStatus.RUNNING.value
        assert data['scrape_phase'] == ScrapePhase.LINK_COLLECTION.value
        assert data['progress'] == 50
        assert data['message'] == "正在收集中..."
        assert 'task' in data
        assert isinstance(data['task'], dict)
        assert data['task']['id'] == 3
        assert data['task']['task_name'] == '手動採集任務'

    def test_get_task_status_not_found(self, client, mock_task_executor_service):
        """測試獲取不存在的任務狀態"""
        response = client.get('/api/tasks/manual/999/status')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False
        assert '任務不存在' in data['message']

    def test_fetch_links_manual_task(self, client, mock_task_service, mock_task_executor_service):
        """測試開始手動 links_only 任務"""
        task_data = {
            'task_name': '新手動連結任務',
            'crawler_id': 1,
            'task_args': {'max_pages': 2}
        }
        response = client.post('/api/tasks/manual/collect-links', json=task_data)
        assert response.status_code == 202
        data = json.loads(response.data)
        assert data['success'] is True
        assert '任務 4 模擬執行成功' in data['message']
        assert data['task_status'] == TaskStatus.COMPLETED.value
        assert data['scrape_phase'] == ScrapePhase.LINK_COLLECTION.value
        assert 'link_count' in data
        assert 4 in mock_task_service.tasks
        created_task = mock_task_service.tasks[4]
        assert created_task.is_auto is False
        assert created_task.scrape_mode == ScrapeMode.LINKS_ONLY

    def test_get_unscraped_links(self, client, mock_article_service):
        """測試獲取未抓取的連結"""
        response = client.get('/api/tasks/manual/1/links')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert isinstance(data['articles'], list)
        assert len(data['articles']) == 2
        assert all(a['link'].startswith('http://example.com/') for a in data['articles'])
        assert all(k in data['articles'][0] for k in ['title', 'link', 'summary', 'source', 'published_at'])

    def test_fetch_content_manual_task_from_db_links(self, client, mock_task_service, mock_article_service, mock_task_executor_service):
        """測試抓取內容 (從資料庫獲取連結)"""
        request_data = {'task_args': {'get_links_by_task_id': True}}
        response = client.post('/api/tasks/manual/1/fetch-content', json=request_data)
        assert response.status_code == 202
        data = json.loads(response.data)
        assert data['success'] is True
        assert '任務 1 模擬執行成功' in data['message']
        assert data['task_status'] == TaskStatus.COMPLETED.value
        assert data['scrape_phase'] == ScrapePhase.CONTENT_SCRAPING.value
        updated_task = mock_task_service.tasks[1]
        assert updated_task.scrape_mode == ScrapeMode.CONTENT_ONLY
        assert 'article_links' in updated_task.task_args
        assert len(updated_task.task_args['article_links']) == 2
        assert updated_task.task_args['article_links'][0] == 'http://example.com/1'

    def test_fetch_content_manual_task_from_request_links(self, client, mock_task_service, mock_task_executor_service):
        """測試抓取內容 (從請求提供連結)"""
        request_links = ['http://custom.com/link1', 'http://custom.com/link2']
        request_data = {
            'task_args': {
                'get_links_by_task_id': False,
                'article_links': request_links
            }
        }
        response = client.post('/api/tasks/manual/3/fetch-content', json=request_data)
        assert response.status_code == 202
        data = json.loads(response.data)
        assert data['success'] is True
        assert '任務 3 模擬執行成功' in data['message']
        updated_task = mock_task_service.tasks[3]
        assert updated_task.scrape_mode == ScrapeMode.CONTENT_ONLY
        assert 'article_links' in updated_task.task_args
        assert updated_task.task_args['article_links'] == request_links

    def test_fetch_content_manual_task_no_links(self, client, mock_task_service, mock_article_service, sample_articles_data):
        """測試抓取內容時找不到連結"""
        request_data = {'task_args': {'get_links_by_task_id': True}}
        response = client.post('/api/tasks/manual/2/fetch-content', json=request_data)
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert '未找到未抓取的文章' in data['message'] or '沒有找到未抓取的文章連結' in data['message']

    def test_get_scraped_task_results(self, client, mock_article_service):
        """測試獲取已抓取的結果"""
        response = client.get('/api/tasks/manual/1/results')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['articles']) == 1
        assert data['articles'][0]['link'] == 'http://example.com/3'
        assert all(k in data['articles'][0] for k in ['title', 'link', 'summary', 'source'])

    def test_test_crawler(self, client, mock_task_executor_service, mock_task_service):
        """測試爬蟲測試端點"""
        test_data = {
            'crawler_name': 'MyTestCrawler',
            'crawler_id': 1,
            'task_args': {**TASK_ARGS_DEFAULT, 'max_pages': 1}
        }
        response = client.post('/api/tasks/manual/test', json=test_data)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert '爬蟲 MyTestCrawler 測試成功' in data['message']
        assert 'result' in data
        assert data['result']['links_found'] == 3
        assert 'validated_params' in data['result']
        validated_params = data['result']['validated_params']
        assert validated_params['scrape_mode'] == ScrapeMode.LINKS_ONLY.value
        assert validated_params['is_test'] is True
        assert validated_params['max_pages'] == 1
        assert validated_params['save_to_database'] is False

    def test_cancel_task(self, client, mock_task_executor_service, mock_task_service):
        """測試取消任務"""
        mock_task_service.tasks[3].task_status = TaskStatus.RUNNING
        response = client.post('/api/tasks/3/cancel')
        assert response.status_code == 202
        data = json.loads(response.data)
        assert data['success'] is True
        assert '任務 3 已取消' in data['message']
        assert mock_task_service.tasks[3].task_status == TaskStatus.CANCELLED

    def test_cancel_task_not_running(self, client, mock_task_executor_service, mock_task_service):
        """測試取消非運行中任務"""
        response = client.post('/api/tasks/1/cancel')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False
        assert '未在運行中' in data['message']

    def test_get_task_history(self, client, mock_task_service):
        """測試獲取任務歷史記錄"""
        response = client.get('/api/tasks/1/history')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'history' in data
        assert isinstance(data['history'], list)
        assert len(data['history']) == 2
        assert 'total_count' in data
        assert data['total_count'] == 2
        assert isinstance(data['history'][0], dict)
        assert data['history'][0]['id'] == 101
        assert data['history'][0]['success'] is True
        assert data['history'][1]['id'] == 102
        assert data['history'][1]['success'] is False
        assert data['history'][0]['task_status'] == TaskStatus.COMPLETED.value

    def test_get_task_history_not_found(self, client, mock_task_service):
        """測試獲取不存在任務的歷史記錄"""
        def mock_find_history_not_found(task_id, **kwargs):
            # 修正 key 名稱
            return {'success': False, 'message': '任務不存在', 'history': []}
        mock_task_service.find_task_history = mock_find_history_not_found

        response = client.get('/api/tasks/999/history')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False
        assert '任務不存在' in data['message']

    def test_validation_error_on_create(self, client, mock_task_service):
        """測試創建任務時缺少必要字段導致的驗證錯誤"""
        task_data = {
            'task_name': '缺少字段任務',
            'cron_expression': '0 0 * * *',
            'is_auto': True
        }
        response = client.post('/api/tasks/scheduled', json=task_data)
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert '資料驗證失敗' in data['message']
        assert 'crawler_id' in data['message']
        assert '此欄位不能為空' in data['message'] or '必須為正整數' in data['message']

    def test_validation_error_on_update(self, client, mock_task_service):
        """測試更新任務時數據驗證失敗"""
        original_validate = mock_task_service.validate_task_data
        def failing_validate(data, is_update=False):
            if is_update:
                 if 'cron_expression' in data and data['cron_expression'] == '無效的表達式':
                     return {
                         'success': False,
                         'message': '資料驗證失敗：cron_expression: Cron 格式無效',
                         'data': None
                     }
            return original_validate(data, is_update)
        mock_task_service.validate_task_data = failing_validate

        update_data = {'cron_expression': '無效的表達式'}
        response = client.put('/api/tasks/scheduled/1', json=update_data)
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert '資料驗證失敗' in data['message']
        assert 'cron_expression' in data['message']
        assert 'Cron 格式無效' in data['message']

        mock_task_service.validate_task_data = original_validate

    def test_get_request_without_data(self, client):
        """測試 POST/PUT 請求沒有 JSON body"""
        response = client.post('/api/tasks/scheduled', data=None, content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert '缺少任務資料' in data['message']

        response = client.put('/api/tasks/scheduled/1', data=None, content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert '缺少任務資料' in data['message'] 