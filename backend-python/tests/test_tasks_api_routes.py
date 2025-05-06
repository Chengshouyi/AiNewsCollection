"""測試 src.web.routes.tasks_api 中的 API 路由功能"""
import json
import enum
import logging
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
 # 使用統一的 logger

# flake8: noqa: F811
# pylint: disable=redefined-outer-name

logger = logging.getLogger(__name__)  # 使用統一的 logger # 使用統一的 logger

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
        print(f"DEBUG: data['scrape_mode_internal'] = {data.get('scrape_mode_internal')}") # 添加調試輸出
        self.scrape_mode_internal = data.get('scrape_mode_internal', ScrapeMode.FULL_SCRAPE)
        print(f"DEBUG: self.scrape_mode_internal after get = {self.scrape_mode_internal}") # 添加調試輸出
        self.created_at = data.get('created_at', datetime.now(timezone.utc))
        self.updated_at = data.get('updated_at', datetime.now(timezone.utc))

        # 確保枚舉類型正確
        if isinstance(self.task_status, str):
            self.task_status = TaskStatus(self.task_status)
        if isinstance(self.scrape_phase, str):
            self.scrape_phase = ScrapePhase(self.scrape_phase)

        print(f"DEBUG: self.scrape_mode_internal before type check = {self.scrape_mode_internal}") # 添加調試輸出
        if isinstance(self.scrape_mode_internal, str):
            self.scrape_mode_internal = ScrapeMode(self.scrape_mode_internal)
        print(f"DEBUG: self.scrape_mode_internal after type check = {self.scrape_mode_internal}") # 添加調試輸出

    def model_dump(self):
        """模擬 Pydantic 的 model_dump，使其更接近 CrawlerTaskReadSchema"""
        dumped_data = {
            'id': self.id,
            'task_name': self.task_name,
            'crawler_id': self.crawler_id,
            'is_auto': self.is_auto,
            'is_active': self.is_active,
            'is_scheduled': self.is_scheduled,
            'task_args': self.task_args,
            'notes': self.notes,
            'last_run_at': self.last_run_at.isoformat() if isinstance(self.last_run_at, datetime) else self.last_run_at,
            'last_run_success': self.last_run_success,
            'last_run_message': self.last_run_message,
            'cron_expression': self.cron_expression,
            'scrape_phase': self.scrape_phase.value if hasattr(self.scrape_phase, 'value') else self.scrape_phase,
            'task_status': self.task_status.value if hasattr(self.task_status, 'value') else self.task_status,
            'retry_count': self.retry_count,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'updated_at': self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
        }
        # Ensure task_args always exists, even if empty, as per CrawlerTaskReadSchema
        if 'task_args' not in dumped_data or dumped_data['task_args'] is None:
            dumped_data['task_args'] = {}
        return dumped_data

class CrawlerTaskHistoryMock:
    """模擬 CrawlerTaskHistory ORM 對象，對齊 TaskHistorySchema"""
    def __init__(self, data):
        self.id = data.get('id')
        self.task_id = data.get('task_id')
        self.scrape_phase = data.get('scrape_phase', ScrapePhase.UNKNOWN.value)
        self.task_status = data.get('task_status', TaskStatus.UNKNOWN.value)
        self.message = data.get('message')
        self.details = data.get('details')
        self.created_at = data.get('created_at', datetime.now(timezone.utc))

        if isinstance(self.task_status, str):
             self.task_status = TaskStatus(self.task_status)
        elif isinstance(self.task_status, enum.Enum):
             self.task_status = self.task_status.value # Store as string value if coming as enum

        if isinstance(self.scrape_phase, ScrapePhase): # Comes from sample_history_data as value
            self.scrape_phase = self.scrape_phase.value
        elif not isinstance(self.scrape_phase, str):
            self.scrape_phase = str(self.scrape_phase)


    def model_dump(self):
        """模擬 Pydantic 的 model_dump，符合 TaskHistorySchema"""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'scrape_phase': self.scrape_phase,
            'task_status': self.task_status if isinstance(self.task_status, str) else self.task_status.value,
            'message': self.message,
            'details': self.details,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
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
            'scrape_phase': ScrapePhase.INIT, 'scrape_mode_internal': ScrapeMode.FULL_SCRAPE, 'created_at': now, 'updated_at': now
        },
        {
            'id': 2, 'task_name': '週間財經新聞', 'crawler_id': 1, 'is_auto': True, 'is_active': True,
            'task_args': {'max_items': 50, 'scrape_mode': ScrapeMode.FULL_SCRAPE.value},
            'cron_expression': '0 0 * * 1-5', 'is_scheduled': True, 'task_status': TaskStatus.INIT,
            'scrape_phase': ScrapePhase.INIT, 'scrape_mode_internal': ScrapeMode.FULL_SCRAPE, 'created_at': now, 'updated_at': now
        },
        {
            'id': 3, 'task_name': '手動採集任務', 'crawler_id': 1, 'is_auto': False, 'is_active': True,
            'task_args': {'max_pages': 5, 'scrape_mode': ScrapeMode.FULL_SCRAPE.value},
            'is_scheduled': False, 'task_status': TaskStatus.INIT,
            'scrape_phase': ScrapePhase.INIT, 'scrape_mode_internal': ScrapeMode.FULL_SCRAPE, 'created_at': now, 'updated_at': now
        }
    ]

@pytest.fixture
def sample_history_data():
     """創建測試用的歷史記錄數據"""
     now = datetime.now(timezone.utc)
     return [
         {'id': 101, 'task_id': 1, 'created_at': now - timedelta(minutes=5),
          'scrape_phase': ScrapePhase.COMPLETED.value, 'task_status': TaskStatus.COMPLETED.value,
          'message': '執行成功', 'details': {'articles_count': 10, 'status_detail': 'All done'}},
         {'id': 102, 'task_id': 1, 'created_at': now - timedelta(days=1),
          'scrape_phase': ScrapePhase.FAILED.value, 'task_status': TaskStatus.FAILED.value,
          'message': '執行失敗', 'details': {'error_code': 'E500', 'reason': 'Upstream service unavailable'}},
         {'id': 103, 'task_id': 3, 'created_at': now - timedelta(minutes=2),
          'scrape_phase': ScrapePhase.CONTENT_SCRAPING.value, 'task_status': TaskStatus.RUNNING.value,
          'message': '任務執行中', 'details': {'progress': 50, 'current_step': 'Fetching page 3'}},
     ]

@pytest.fixture
def mock_task_service(monkeypatch, sample_tasks_data, sample_history_data):
    """模擬 CrawlerTaskService"""
    class MockTaskService:
        def __init__(self):
            self.tasks = {task['id']: CrawlerTaskMock(task) for task in sample_tasks_data}
            self.task_history = {}
            for history_item_data in sample_history_data:
                task_id = history_item_data['task_id']
                if task_id not in self.task_history:
                    self.task_history[task_id] = []
                self.task_history[task_id].append(CrawlerTaskHistoryMock(history_item_data))
            self.next_id = max(self.tasks.keys() or [0]) + 1
            all_history_ids = [h.id for histories_list in self.task_history.values() for h in histories_list if h.id is not None]
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

            # Ensure scrape_mode is correctly passed for CrawlerTaskMock
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
                'ai_only': validated_data.get('ai_only', False), # Internal to mock
                'task_args': validated_data.get('task_args', {}),
                'notes': validated_data.get('notes'),
                'cron_expression': validated_data.get('cron_expression'),
                'is_scheduled': validated_data.get('is_scheduled', False), # is_scheduled is part of schema
                'task_status': TaskStatus.INIT,
                'scrape_phase': ScrapePhase.INIT,
                'max_retries': validated_data.get('task_args', {}).get('max_retries', TASK_ARGS_DEFAULT.get('max_retries', 3)), # Internal
                'retry_count': 0,
                'scrape_mode_internal': scrape_mode_enum, # For CrawlerTaskMock's internal field
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
            
            # Use the service's validation, which should align with CrawlerTasksUpdateSchema
            # The route calls service.update_task(task_id, data) where data is request.get_json()
            # The service itself should handle validation internally or use a helper.
            # For the mock, we'll directly apply validated fields if the mock validate_task_data is robust.
            validated_result = self.validate_task_data(data, is_update=True)
            if not validated_result['success']:
                 return validated_result

            update_data = validated_result['data']


            for key, value in update_data.items():
                if key == 'scrape_mode_internal': # if you want to update the internal mock field
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
                         task.task_args = value # Or handle error
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
                 return {'success': False, 'message': '任務不存在', 'history': []}

            histories = self.task_history.get(task_id, [])
            # Ensure created_at is datetime for sorting
            histories_with_dt = [h for h in histories if isinstance(h.created_at, datetime)]
            histories_with_dt.sort(key=lambda h: h.created_at, reverse=sort_desc) # Sort by created_at
            
            start = offset if offset is not None else 0
            end = (start + limit) if limit is not None else None
            histories_to_return = histories_with_dt[start:end]
            
            # The API route will call model_dump on these CrawlerTaskHistoryMock instances
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
                 preview_articles = []
                 for a in unscraped:
                     preview_item = {
                         'id': a.get('id'), # ArticlePreviewSchema 有 id
                         'title': a.get('title'),
                         'link': a.get('link'),
                         'source': a.get('source'),
                         'pub_date': a.get('published_at'), # 將 published_at 映射到 pub_date
                         'is_scraped': a.get('is_scraped', False), # 包含 is_scraped
                         # summary 不再預設包含，因為 ArticlePreviewSchema 沒有它
                     }
                     preview_articles.append(preview_item)
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
                 preview_articles = []
                 for a in scraped:
                     preview_item = {
                         'id': a.get('id'), # ArticlePreviewSchema 有 id
                         'title': a.get('title'),
                         'link': a.get('link'),
                         'source': a.get('source'),
                         'pub_date': a.get('published_at'), # 將 published_at 映射到 pub_date
                         'is_scraped': a.get('is_scraped', True), # 包含 is_scraped
                         # summary 不再預設包含，因為 ArticlePreviewSchema 沒有它
                     }
                     preview_articles.append(preview_item)
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
                 if 'scrape_mode' in kwargs: # This would be from task_args effectively
                     task.scrape_mode_internal = ScrapeMode(kwargs['scrape_mode'])
                 
                 op_type = kwargs.get('operation_type')
                 current_scrape_phase = ScrapePhase.COMPLETED # Default
                 if op_type == 'fetch_full_article':
                     current_scrape_phase = ScrapePhase.COMPLETED
                 elif op_type == 'collect_links_only':
                     current_scrape_phase = ScrapePhase.LINK_COLLECTION
                 elif op_type == 'fetch_content_only':
                     current_scrape_phase = ScrapePhase.CONTENT_SCRAPING
                 task.scrape_phase = current_scrape_phase

                 return {'success': True, 'message': f'任務 {task_id} 模擬執行成功', 
                         'task_status': TaskStatus.COMPLETED.value, 
                         'scrape_phase': current_scrape_phase.value} # Executor result includes scrape_phase
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
            # task object here is CrawlerTaskMock. API route will dump it.
            return {
                'success': True,
                'task_status': task.task_status.value,
                'scrape_phase': task.scrape_phase.value,
                'progress': 100 if task.task_status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED] else 50,
                'message': task.last_run_message or f'任務 {task_id} 狀態',
                'task': task # This is CrawlerTaskMock object
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
        # This override is specific to this test to ensure the service returns CrawlerTaskMock objects
        # which the API route then calls model_dump() on.
        original_find_advanced = mock_task_service.find_tasks_advanced
        def mock_find_tasks_advanced_override(**filters):
            # Filter tasks from the mock_task_service.tasks based on expected filters
            # For this test, it's is_scheduled=True, is_active=True, is_auto=True
            tasks_from_fixture = [
                t for t in mock_task_service.tasks.values() 
                if t.is_scheduled and t.is_active and t.is_auto
            ]
            return {
                'success': True,
                'data': { 
                    'items': tasks_from_fixture, 
                    'page': 1, 'per_page': len(tasks_from_fixture), 'total': len(tasks_from_fixture), 'total_pages': 1,
                    'has_next': False, 'has_prev': False
                },
                'message': '模擬搜尋成功'
            }
        mock_task_service.find_tasks_advanced = mock_find_tasks_advanced_override

        response = client.get('/api/tasks/scheduled')
        mock_task_service.find_tasks_advanced = original_find_advanced # Restore

        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert 'message' in data
        assert 'data' in data
        assert isinstance(data['data'], list)
        task_list_from_response = data['data']
        # Based on sample_tasks_data, tasks 1 and 2 are scheduled, active, and auto
        assert len(task_list_from_response) == 2 
        assert all(isinstance(task, dict) for task in task_list_from_response)
        assert all(task['is_scheduled'] is True and task['is_active'] is True and task['is_auto'] is True for task in task_list_from_response)
        assert any(task['task_name'] == '每日新聞爬取' for task in task_list_from_response)
        assert all('scrape_mode' not in task for task in task_list_from_response) # Check extra field not present

    def test_create_scheduled_task(self, client, mock_task_service, mock_scheduler_service):
        """測試創建排程任務"""
        current_task_args = TASK_ARGS_DEFAULT.copy()
        current_task_args.update({
            'max_items': 100,
            'scrape_mode': 'full_scrape'
            # max_retries and retry_delay (and others) will be from TASK_ARGS_DEFAULT
        })
        task_data = {
            'task_name': '新排程任務',
            'crawler_id': 1,
            'is_auto': True,
            'cron_expression': '0 0 * * *',
            'task_args': current_task_args,
            'scrape_phase': ScrapePhase.INIT.value
        }
        response = client.post('/api/tasks/scheduled', json=task_data)
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['success'] is True
        assert '任務創建成功' in data['message']
        assert 'data' in data # Changed from 'task'
        new_task_id = data['data']['id']
        assert new_task_id == 4 # Assuming next_id starts after sample_tasks_data
        assert data['data']['task_name'] == '新排程任務'
        assert data['data']['is_auto'] is True 
        # The API sets is_scheduled based on scheduler interaction, not directly from this create.
        # The create_scheduled_task API route in tasks_api.py doesn't set is_scheduled=True on the task object itself before returning.
        # It calls scheduler.add_or_update_task_to_scheduler(task)
        # The returned task schema (CrawlerTaskReadSchema) has is_scheduled.
        # The mock_task_service.create_task sets 'is_scheduled': False by default. This should be fine.
        # The actual state of being scheduled is managed by the scheduler, task.is_scheduled reflects DB state.
        assert data['data']['is_scheduled'] is False # Default from mock create
        assert data['data']['cron_expression'] == '0 0 * * *'
        assert data['data']['task_args']['scrape_mode'] == 'full_scrape'
        mock_scheduler_service.add_or_update_task_to_scheduler.assert_called_once()
        call_args = mock_scheduler_service.add_or_update_task_to_scheduler.call_args[0][0]
        assert isinstance(call_args, CrawlerTaskMock)
        assert call_args.id == new_task_id

    def test_create_scheduled_task_scheduler_fail(self, client, mock_task_service, mock_scheduler_service):
        """測試創建任務成功但排程失敗"""
        mock_scheduler_service.add_or_update_task_to_scheduler.return_value = {'success': False, 'message': '排程器錯誤'}
        current_task_args = TASK_ARGS_DEFAULT.copy()
        current_task_args.update({
            'scrape_mode': 'full_scrape'
            # max_retries and retry_delay (and others) will be from TASK_ARGS_DEFAULT
        })
        task_data = {
            'task_name': '排程失敗任務', 'crawler_id': 1, 'is_auto': True, 'cron_expression': '0 1 * * *',
            'task_args': current_task_args,
            'scrape_phase': ScrapePhase.INIT.value
        }
        response = client.post('/api/tasks/scheduled', json=task_data)
        assert response.status_code == 201 # Still 201 as task is created
        data = json.loads(response.data)
        assert data['success'] is True # Overall success of task creation might be true
        assert '任務創建成功' in data['message']
        assert '添加到排程器失敗: 排程器錯誤' in data['message']
        assert 'data' in data # Changed from 'task'
        assert data['data']['id'] == 4

    def test_update_scheduled_task(self, client, mock_task_service, mock_scheduler_service):
        """測試更新排程任務"""
        # Ensure task 1 exists and is_auto for this test path in API
        task_to_update = mock_task_service.tasks[1]
        task_to_update.is_auto = True
        task_to_update.is_scheduled = True # Simulate it was scheduled

        # --- Construct the final task_args payload for the PUT request ---
        # 1. Start with TASK_ARGS_DEFAULT to ensure all potentially required fields have a base value.
        final_task_args_payload = TASK_ARGS_DEFAULT.copy()

        # 2. Merge the task's current arguments (if any) onto the defaults.
        #    This preserves existing non-default values.
        if task_to_update.task_args:
            final_task_args_payload.update(task_to_update.task_args)

        # 3. Apply the specific change for this test case.
        final_task_args_payload['max_items'] = 200
        # --- End constructing task_args ---

        update_data = {
            'task_name': '更新後的任務',
            'cron_expression': '0 12 * * *',
            'task_args': final_task_args_payload # Use the fully constructed dictionary
            # is_auto will be True from _setup_validate_task_data in API
        }
        response = client.put('/api/tasks/scheduled/1', json=update_data)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert '任務更新成功' in data['message']
        assert 'data' in data # Changed from 'task'
        assert data['data']['id'] == 1
        assert data['data']['task_name'] == '更新後的任務'
        assert data['data']['cron_expression'] == '0 12 * * *'
        # Check the updated value and potentially another required value that should persist
        assert data['data']['task_args']['max_items'] == 200
        assert 'scrape_mode' in data['data']['task_args'] # Check a required field persists
        assert 'max_retries' in data['data']['task_args']
        assert 'retry_delay' in data['data']['task_args']
        assert 'timeout' in data['data']['task_args']
        assert data['data']['is_auto'] is True # Should be set by API logic for scheduled task update
        mock_scheduler_service.add_or_update_task_to_scheduler.assert_called_once()
        call_args = mock_scheduler_service.add_or_update_task_to_scheduler.call_args[0][0]
        assert isinstance(call_args, CrawlerTaskMock)
        assert call_args.id == 1
        assert call_args.task_name == '更新後的任務'
        assert call_args.is_auto is True

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
        current_task_args = TASK_ARGS_DEFAULT.copy()
        current_task_args.update({
            'max_items': 50,
            'scrape_mode': ScrapeMode.FULL_SCRAPE.value
        })
        task_data = {
            'task_name': '新手動全爬任務',
            'crawler_id': 1,
            'task_args': current_task_args,
            'scrape_phase': ScrapePhase.INIT.value
        }
        response = client.post('/api/tasks/manual/start', json=task_data)
        assert response.status_code == 202
        data = json.loads(response.data)
        assert data['success'] is True
        # The message comes from executor_result.get('message', default_msg)
        # mock_task_executor_service.fetch_full_article returns message like '任務 {task_id} 模擬執行成功'
        assert f'任務 {mock_task_service.next_id -1 } 模擬執行成功' in data['message'] # mock_task_service.next_id-1 is the new task_id (4)
        
        assert 'data' in data
        assert data['data']['task_id'] == (mock_task_service.next_id -1)
        assert data['data']['task_status'] == TaskStatus.COMPLETED.value # From executor via API

        assert (mock_task_service.next_id -1) in mock_task_service.tasks
        created_task = mock_task_service.tasks[(mock_task_service.next_id -1)]
        assert created_task.is_auto is False
        # The scrape_mode of the task object is set by _setup_validate_task_data and create_task
        # For this route, scrape_mode=ScrapeMode.FULL_SCRAPE.value is passed to _setup_validate_task_data
        assert created_task.task_args.get('scrape_mode') == ScrapeMode.FULL_SCRAPE.value
        assert created_task.scrape_mode_internal == ScrapeMode.FULL_SCRAPE # Check internal mock field if necessary

    def test_get_task_status(self, client, mock_task_service, mock_task_executor_service):
        """測試獲取任務狀態"""
        mock_task_service.tasks[3].task_status = TaskStatus.RUNNING
        mock_task_service.tasks[3].scrape_phase = ScrapePhase.LINK_COLLECTION
        mock_task_service.tasks[3].last_run_message = "正在收集中..."

        response = client.get('/api/tasks/manual/3/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['message'] == "正在收集中..." # This is from executor_result.get('message')

        assert 'data' in data
        assert data['data']['task_status'] == TaskStatus.RUNNING.value
        assert data['data']['scrape_phase'] == ScrapePhase.LINK_COLLECTION.value
        assert data['data']['progress'] == 50
        assert 'task' in data['data']
        assert isinstance(data['data']['task'], dict)
        assert data['data']['task']['id'] == 3
        assert data['data']['task']['task_name'] == '手動採集任務'

    def test_get_task_status_not_found(self, client, mock_task_executor_service):
        """測試獲取不存在的任務狀態"""
        response = client.get('/api/tasks/manual/999/status')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['success'] is False
        assert '任務不存在' in data['message']

    def test_fetch_links_manual_task(self, client, mock_task_service, mock_task_executor_service):
        """測試開始手動 links_only 任務"""
        current_task_args = TASK_ARGS_DEFAULT.copy()
        current_task_args.update({
            'max_pages': 2,
            'scrape_mode': ScrapeMode.LINKS_ONLY.value
        })
        task_data = {
            'task_name': '新手動連結任務',
            'crawler_id': 1,
            'task_args': current_task_args,
            'scrape_phase': ScrapePhase.INIT.value
        }
        response = client.post('/api/tasks/manual/collect-links', json=task_data)
        assert response.status_code == 202
        data = json.loads(response.data)
        assert data['success'] is True
        assert f'任務 {mock_task_service.next_id -1 } 模擬執行成功' in data['message']
        
        assert 'data' in data
        assert data['data']['task_id'] == (mock_task_service.next_id -1)
        assert data['data']['task_status'] == TaskStatus.COMPLETED.value
        # scrape_phase and link_count are not in CollectLinksManualTaskSuccessResponseSchema.data

        assert (mock_task_service.next_id -1) in mock_task_service.tasks
        created_task = mock_task_service.tasks[(mock_task_service.next_id -1)]
        assert created_task.is_auto is False
        assert created_task.task_args.get('scrape_mode') == ScrapeMode.LINKS_ONLY.value
        assert created_task.scrape_mode_internal == ScrapeMode.LINKS_ONLY

    def test_get_unscraped_links(self, client, mock_article_service):
        """測試獲取未抓取的連結"""
        response = client.get('/api/tasks/manual/1/links')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data' in data # Changed from 'articles'
        assert isinstance(data['data'], list)
        assert len(data['data']) == 2
        assert all(a['link'].startswith('http://example.com/') for a in data['data'])
        # ArticlePreviewSchema fields
        expected_keys = ['id', 'title', 'link', 'source', 'pub_date', 'is_scraped']
        assert all(k in data['data'][0] for k in expected_keys)


    def test_fetch_content_manual_task_from_db_links(self, client, mock_task_service, mock_article_service, mock_task_executor_service):
        """測試抓取內容 (從資料庫獲取連結)"""
        request_data = {'task_args': {'get_links_by_task_id': True}} # scrape_mode will be set by API logic
        response = client.post('/api/tasks/manual/1/fetch-content', json=request_data)
        assert response.status_code == 202
        data = json.loads(response.data)
        assert data['success'] is True
        assert '任務 1 模擬執行成功' in data['message']
        
        assert 'data' in data
        assert data['data']['task_id'] == 1
        assert data['data']['task_status'] == TaskStatus.COMPLETED.value
        # scrape_phase not in FetchContentManualTaskSuccessResponseSchema.data

        updated_task = mock_task_service.tasks[1]
        assert updated_task.task_args.get('scrape_mode') == ScrapeMode.CONTENT_ONLY.value
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
                # scrape_mode will be set by API logic
            }
        }
        response = client.post('/api/tasks/manual/3/fetch-content', json=request_data)
        assert response.status_code == 202
        data = json.loads(response.data)
        assert data['success'] is True
        assert '任務 3 模擬執行成功' in data['message']
        
        assert 'data' in data
        assert data['data']['task_id'] == 3
        assert data['data']['task_status'] == TaskStatus.COMPLETED.value

        updated_task = mock_task_service.tasks[3]
        assert updated_task.task_args.get('scrape_mode') == ScrapeMode.CONTENT_ONLY.value
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
        assert 'data' in data # Changed from 'articles'
        assert len(data['data']) == 1
        assert data['data'][0]['link'] == 'http://example.com/3'
        # ArticlePreviewSchema fields, as per MockArticleService:
        # 'id', 'title', 'link', 'source', 'pub_date', 'is_scraped'
        expected_keys = ['id', 'title', 'link', 'source', 'pub_date', 'is_scraped']
        assert all(k in data['data'][0] for k in expected_keys)


    def test_test_crawler(self, client, mock_task_executor_service, mock_task_service):
        """測試爬蟲測試端點"""
        test_data = {
            'crawler_name': 'MyTestCrawler',
            'crawler_id': 1, # Optional, but good to include if service uses it
            'task_args': {'max_pages': 1} # Other defaults from TASK_ARGS_DEFAULT will be merged by API
        }
        response = client.post('/api/tasks/manual/test', json=test_data)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert '爬蟲 MyTestCrawler 測試成功' in data['message']
        assert 'data' in data # Changed from 'result'
        assert data['data']['links_found'] == 3
        assert 'validated_params' in data['data']
        validated_params = data['data']['validated_params']
        # API logic for test sets scrape_mode to LINKS_ONLY and is_test to True etc.
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
        assert 'message' in data
        assert 'data' in data
        
        history_data = data['data']
        assert 'history' in history_data
        assert isinstance(history_data['history'], list)
        # sample_history_data has 2 entries for task_id 1. Mock sorts by created_at desc.
        # Item 101 (created_at = now - 5m)
        # Item 102 (created_at = now - 1d)
        # So 101 should be first.
        assert len(history_data['history']) == 2
        assert 'total_count' in history_data
        assert history_data['total_count'] == 2
        
        # Check based on updated CrawlerTaskHistoryMock and sample_history_data
        # Assuming mock service's find_task_history sorts by created_at descending
        # History for task 1: id 101 (recent), id 102 (older)
        
        first_history_item = history_data['history'][0]
        second_history_item = history_data['history'][1]

        assert first_history_item['id'] == 101
        assert first_history_item['task_id'] == 1
        assert first_history_item['scrape_phase'] == ScrapePhase.COMPLETED.value
        assert first_history_item['task_status'] == TaskStatus.COMPLETED.value
        assert first_history_item['message'] == '執行成功'
        assert first_history_item['details'] == {'articles_count': 10, 'status_detail': 'All done'}
        
        assert second_history_item['id'] == 102
        assert second_history_item['scrape_phase'] == ScrapePhase.FAILED.value
        assert second_history_item['task_status'] == TaskStatus.FAILED.value
        assert second_history_item['details'] == {'error_code': 'E500', 'reason': 'Upstream service unavailable'}


    def test_get_task_history_not_found(self, client, mock_task_service):
        """測試獲取不存在任務的歷史記錄"""
        # Temporarily change the mock's behavior for this specific test case
        original_find_history = mock_task_service.find_task_history
        def mock_find_history_not_found_override(task_id, **kwargs):
            if task_id == 999: # The ID being tested
                return {'success': False, 'message': '任務不存在', 'history': []}
            return original_find_history(task_id, **kwargs) # Call original for other IDs
        mock_task_service.find_task_history = mock_find_history_not_found_override

        response = client.get('/api/tasks/999/history')
        mock_task_service.find_task_history = original_find_history # Restore original method

        assert response.status_code == 404 # API returns 404 if service says not success
        data = json.loads(response.data)
        assert data['success'] is False
        assert '任務不存在' in data['message']

    def test_validation_error_on_create(self, client, mock_task_service):
        """測試創建任務時缺少必要字段導致的驗證錯誤"""
        task_data = {
            'task_name': '缺少字段任務',
            'task_args': {}, # Deliberately missing (or add specific task_args test)
            'cron_expression': '0 0 * * *',
            'is_auto': True
        }
        # This test is designed to fail validation.
        # The current assertions check for crawler_id.
        # If crawler_id was present, it would then likely fail for task_args or scrape_phase
        # depending on the validator's logic.
        # For now, this test remains as is, focusing on a general validation failure.
        # If more specific "missing field" tests are needed, they can be added.
        response = client.post('/api/tasks/scheduled', json=task_data)
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert '以下必填欄位缺失或值為空/空白' in data['message']
        assert 'crawler_id' in data['message']
        assert '以下必填欄位缺失或值為空/空白' in data['message'] or '必須為正整數' in data['message']

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
        assert 'cron_expression: Cron 表達式必須包含 5 個字段' in data['message']
        assert 'cron_expression' in data['message']
        assert 'cron_expression: Cron 表達式必須包含 5 個字段' in data['message']

        mock_task_service.validate_task_data = original_validate

    def test_get_request_without_data(self, client):
        """測試 POST/PUT 請求沒有 JSON body"""
        response = client.post('/api/tasks/scheduled', data=None, content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert '以下必填欄位缺失或值為空/空白' in data['message']

        response = client.put('/api/tasks/scheduled/1', data=None, content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert '必須提供至少一個要更新的欄位' in data['message'] 