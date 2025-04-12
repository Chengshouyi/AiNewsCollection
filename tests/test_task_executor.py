import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from src.services.task_executor import TaskExecutor
from src.models.crawler_tasks_model import CrawlerTasks, ScrapeMode
from src.models.crawler_task_history_model import CrawlerTaskHistory
from src.database.crawler_task_history_repository import CrawlerTaskHistoryRepository


class TestTaskExecutor:
    """TaskExecutor 類別的測試集合"""
    
    @pytest.fixture
    def mock_task_history_repo(self):
        """模擬 CrawlerTaskHistoryRepository"""
        mock_repo = MagicMock(spec=CrawlerTaskHistoryRepository)
        
        # 模擬 create 方法，返回一個模擬的歷史記錄物件
        mock_history = MagicMock(spec=CrawlerTaskHistory)
        mock_history.id = 1
        mock_repo.create.return_value = mock_history
        
        return mock_repo
    
    @pytest.fixture
    def mock_crawler(self):
        """模擬爬蟲物件"""
        mock_crawler = MagicMock()
        mock_crawler.execute_task.return_value = {
            'success': True,
            'message': '測試任務執行成功',
            'articles_count': 5
        }
        return mock_crawler
    
    @pytest.fixture
    def mock_task(self):
        """模擬 CrawlerTasks 物件"""
        mock_task = MagicMock(spec=CrawlerTasks)
        mock_task.id = 1
        mock_task.crawler = MagicMock()
        mock_task.crawler.crawler_name = 'TestCrawler'
        mock_task.task_args = {}
        # 添加 scrape_mode 和 ai_only 屬性
        mock_task.scrape_mode = ScrapeMode.FULL_SCRAPE
        mock_task.ai_only = True
        return mock_task
    
    def test_init(self, mock_task_history_repo):
        """測試初始化函數"""
        executor = TaskExecutor(mock_task_history_repo)
        assert executor.task_history_repo == mock_task_history_repo
        assert executor.executing_tasks == set()
    
    def test_execute_task_already_executing(self, mock_task_history_repo, mock_task):
        """測試執行已經在執行中的任務"""
        executor = TaskExecutor(mock_task_history_repo)
        
        # 將任務加入執行中集合
        executor.executing_tasks.add(mock_task.id)
        
        # 執行任務
        result = executor.execute_task(mock_task)
        
        # 驗證結果
        assert result['success'] is False
        assert result['message'] == '任務已在執行中'
        
        # 驗證沒有調用 task_history_repo.create
        mock_task_history_repo.create.assert_not_called()
    
    def test_execute_task_missing_crawler_name(self, mock_task_history_repo):
        """測試執行沒有爬蟲名稱的任務"""
        executor = TaskExecutor(mock_task_history_repo)
        
        # 創建沒有爬蟲名稱的任務
        mock_task = MagicMock(spec=CrawlerTasks)
        mock_task.id = 2
        mock_task.crawler = None
        
        # 執行任務
        result = executor.execute_task(mock_task)
        
        # 驗證結果
        assert result['success'] is False
        assert '無法獲取任務' in result['message']
        
        # 驗證任務從執行中集合移除
        assert 2 not in executor.executing_tasks
    
    @patch('src.services.task_executor.CrawlerFactory')
    def test_execute_task_crawler_factory_error(self, mock_factory, mock_task_history_repo, mock_task):
        """測試爬蟲工廠拋出異常的情況"""
        executor = TaskExecutor(mock_task_history_repo)
        
        # 模擬 CrawlerFactory.get_crawler 拋出異常
        mock_factory.get_crawler.side_effect = ValueError("測試錯誤")
        
        # 執行任務
        result = executor.execute_task(mock_task)
        
        # 驗證結果
        assert result['success'] is False
        assert '無法獲取爬蟲實例' in result['message']
        
        # 驗證任務從執行中集合移除
        assert mock_task.id not in executor.executing_tasks
    
    @patch('src.services.task_executor.CrawlerFactory')
    def test_execute_task_success(self, mock_factory, mock_task_history_repo, mock_task, mock_crawler):
        """測試成功執行任務的情況"""
        executor = TaskExecutor(mock_task_history_repo)
        
        # 模擬 CrawlerFactory.get_crawler 返回模擬爬蟲物件
        mock_factory.get_crawler.return_value = mock_crawler
        
        # 設置任務屬性
        mock_task.task_args = {'other_param': 'value'}
        
        # 執行任務
        result = executor.execute_task(mock_task)
        
        # 驗證結果
        assert result['success'] is True
        assert result['message'] == '測試任務執行成功'
        assert result['articles_count'] == 5
        
        # 驗證函數調用
        mock_factory.get_crawler.assert_called_once_with(mock_task.crawler.crawler_name)
        
        # 驗證爬蟲執行時收到的參數
        call_args = mock_crawler.execute_task.call_args[0]
        assert call_args[0] == mock_task.id  # 第一個參數是 task_id
        
        # 驗證 task_args 包含原始參數和附加的參數
        passed_args = call_args[1]
        assert 'other_param' in passed_args
        assert passed_args['other_param'] == 'value'
        assert 'scrape_mode' in passed_args
        assert passed_args['scrape_mode'] == 'full_scrape'
        assert 'ai_only' in passed_args
        assert passed_args['ai_only'] is True
        
        # 驗證歷史記錄創建和更新
        mock_task_history_repo.create.assert_called_once()
        mock_task_history_repo.update.assert_called_once()
        
        # 驗證任務從執行中集合移除
        assert mock_task.id not in executor.executing_tasks
    
    @patch('src.services.task_executor.CrawlerFactory')
    def test_execute_task_crawler_exception(self, mock_factory, mock_task_history_repo, mock_task, mock_crawler):
        """測試爬蟲執行拋出異常的情況"""
        executor = TaskExecutor(mock_task_history_repo)
        
        # 模擬 CrawlerFactory.get_crawler 返回模擬爬蟲物件
        mock_factory.get_crawler.return_value = mock_crawler
        
        # 設置任務屬性
        mock_task.task_args = {'other_param': 'value'}
        
        # 模擬爬蟲執行拋出異常
        mock_crawler.execute_task.side_effect = Exception("爬蟲執行錯誤")
        
        # 執行任務
        result = executor.execute_task(mock_task)
        
        # 驗證結果
        assert result['success'] is False
        assert '執行任務' in result['message']
        assert '爬蟲執行錯誤' in result['message']
        
        # 驗證爬蟲執行時使用了正確的參數
        call_args = mock_crawler.execute_task.call_args[0]
        assert call_args[0] == mock_task.id  # 第一個參數是 task_id
        
        # 驗證 task_args 包含原始參數和附加的參數
        passed_args = call_args[1]
        assert 'other_param' in passed_args
        assert passed_args['other_param'] == 'value'
        assert 'scrape_mode' in passed_args
        assert 'ai_only' in passed_args
        
        # 驗證任務從執行中集合移除
        assert mock_task.id not in executor.executing_tasks
    
    def test_update_history_no_repo(self):
        """測試在沒有歷史記錄庫的情況下更新歷史記錄"""
        executor = TaskExecutor()  # 沒有提供 task_history_repo
        
        # 調用 _update_history，應該不會拋出異常
        executor._update_history(1, True, "測試訊息")
        
        # 沒有斷言，因為方法應該什麼都不做
    
    def test_update_history_no_id(self, mock_task_history_repo):
        """測試在沒有歷史記錄 ID 的情況下更新歷史記錄"""
        executor = TaskExecutor(mock_task_history_repo)
        
        # 調用 _update_history，應該不會拋出異常
        executor._update_history(None, True, "測試訊息")
        
        # 驗證沒有調用 task_history_repo.update
        mock_task_history_repo.update.assert_not_called()
    
    def test_update_history_exception(self, mock_task_history_repo):
        """測試更新歷史記錄時遇到異常的情況"""
        executor = TaskExecutor(mock_task_history_repo)
        
        # 模擬 task_history_repo.update 拋出異常
        mock_task_history_repo.update.side_effect = Exception("更新錯誤")
        
        # 調用 _update_history，應該不會拋出異常
        executor._update_history(1, True, "測試訊息")
        
        # 驗證調用了 task_history_repo.update
        mock_task_history_repo.update.assert_called_once()
    
    def test_update_history_with_required_fields(self, mock_task_history_repo):
        """測試使用必要欄位更新歷史記錄"""
        executor = TaskExecutor(mock_task_history_repo)
        
        # 調用 _update_history
        executor._update_history(1, True, "測試訊息")
        
        # 驗證調用了 task_history_repo.update 並傳遞正確參數
        mock_task_history_repo.update.assert_called_once()
        args, _ = mock_task_history_repo.update.call_args
        assert args[0] == 1  # 第一個參數應該是歷史記錄 ID
        assert args[1]['success'] is True
        assert args[1]['message'] == "測試訊息"
    
    def test_update_history_with_all_fields(self, mock_task_history_repo):
        """測試使用所有欄位更新歷史記錄"""
        executor = TaskExecutor(mock_task_history_repo)
        
        # 設定測試時間
        end_time = datetime.now(timezone.utc)
        
        # 調用 _update_history
        executor._update_history(1, True, "測試訊息", end_time, 10)
        
        # 驗證調用了 task_history_repo.update 並傳遞正確參數
        mock_task_history_repo.update.assert_called_once()
        args, _ = mock_task_history_repo.update.call_args
        assert args[0] == 1  # 第一個參數應該是歷史記錄 ID
        assert args[1]['success'] is True
        assert args[1]['message'] == "測試訊息"
        assert args[1]['end_time'] == end_time
        assert args[1]['articles_count'] == 10
    
    def test_is_task_executing(self):
        """測試 is_task_executing 方法"""
        executor = TaskExecutor()
        
        # 初始狀態下任務不在執行中
        assert executor.is_task_executing(1) is False
        
        # 添加任務到執行中集合
        executor.executing_tasks.add(1)
        
        # 驗證任務正在執行中
        assert executor.is_task_executing(1) is True
        
        # 移除任務
        executor.executing_tasks.remove(1)
        
        # 驗證任務不再執行中
        assert executor.is_task_executing(1) is False
    
    @patch('src.services.task_executor.CrawlerFactory')
    def test_execute_task_with_scrape_mode_and_ai_only(self, mock_factory, mock_task_history_repo, mock_task, mock_crawler):
        """測試含有 scrape_mode 和 ai_only 參數的任務執行"""
        executor = TaskExecutor(mock_task_history_repo)
        
        # 模擬 CrawlerFactory.get_crawler 返回模擬爬蟲物件
        mock_factory.get_crawler.return_value = mock_crawler
        
        # 確保 mock_task 有 scrape_mode 和 ai_only 屬性
        mock_task.scrape_mode = ScrapeMode.LINKS_ONLY
        mock_task.ai_only = True
        
        # 執行任務
        result = executor.execute_task(mock_task)
        
        # 驗證結果
        assert result['success'] is True
        
        # 驗證爬蟲執行時參數包含正確的 scrape_mode 和 ai_only
        call_args = mock_crawler.execute_task.call_args[0][1]  # 獲取第二個位置參數 (task_args)
        assert call_args['scrape_mode'] == 'links_only'  # 應該是字串值而非枚舉
        assert call_args['ai_only'] is True
        
        # 驗證任務從執行中集合移除
        assert mock_task.id not in executor.executing_tasks 