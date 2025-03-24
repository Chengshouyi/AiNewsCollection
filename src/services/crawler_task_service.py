from datetime import datetime
from typing import List, Dict, Any
import threading
import time
import logging

from src.database.database_manager import DatabaseManager
from src.database.crawler_tasks_repository import CrawlerTasksRepository
from src.database.crawlers_repository import CrawlersRepository
from src.crawlers.crawler_factory import CrawlerFactory

class CrawlerTaskService:
    """爬蟲任務服務，負責管理爬蟲任務的執行和狀態追蹤"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.tasks_repo = CrawlerTasksRepository(db_manager.session)
        self.crawlers_repo = CrawlersRepository(db_manager.session)
        self.crawler_factory = CrawlerFactory()
        self.running_tasks = {}
        self.task_threads = {}
        self.logger = logging.getLogger(__name__)
        
    def get_all_tasks(self) -> List[Dict]:
        """獲取所有任務的列表"""
        tasks = self.tasks_repo.get_all()
        return [task.to_dict() for task in tasks]
        
    def get_task_by_id(self, task_id: int) -> Dict:
        """根據ID獲取任務"""
        task = self.tasks_repo.get_by_id(task_id)
        return task.to_dict() if task else None
        
    def create_task(self, task_data: Dict) -> int:
        """創建新任務"""
        # 驗證爬蟲是否存在
        crawler = self.crawlers_repo.get_by_id(task_data.get('crawler_id'))
        if not crawler:
            raise ValueError(f"爬蟲ID不存在: {task_data.get('crawler_id')}")
            
        # 添加任務到數據庫
        new_task = {
            'crawler_id': task_data.get('crawler_id'),
            'name': task_data.get('name'),
            'schedule': task_data.get('schedule', ''),
            'is_auto': task_data.get('is_auto', False),
            'ai_only': task_data.get('ai_only', True),
            'fetch_details': task_data.get('fetch_details', False),
            'num_articles': task_data.get('num_articles', 10),
            'min_keywords': task_data.get('min_keywords', 3),
            'note': task_data.get('note', ''),
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        task_id = self.tasks_repo.create(new_task)
        return task_id
        
    def update_task(self, task_id: int, task_data: Dict) -> bool:
        """更新任務信息"""
        task = self.tasks_repo.get_by_id(task_id)
        if not task:
            return False
            
        # 更新字段
        for key, value in task_data.items():
            if hasattr(task, key):
                setattr(task, key, value)
                
        task.updated_at = datetime.now()
        self.tasks_repo.update(task)
        return True
        
    def delete_task(self, task_id: int) -> bool:
        """刪除任務"""
        return self.tasks_repo.delete(task_id)
        
    def execute_task(self, task_id: int) -> Dict:
        """手動執行任務"""
        task = self.tasks_repo.get_by_id(task_id)
        if not task:
            raise ValueError(f"任務ID不存在: {task_id}")
            
        # 檢查任務是否已在運行
        if task_id in self.running_tasks:
            return {
                'success': False,
                'message': '任務已在運行中',
                'status': self.running_tasks[task_id]
            }
            
        # 獲取爬蟲實例
        crawler = self.crawlers_repo.get_by_id(task.crawler_id)
        crawler_instance = self.crawler_factory.get_crawler(crawler.crawler_type, crawler.config)
        
        # 準備任務參數
        task_args = {
            'max_pages': task.max_pages if hasattr(task, 'max_pages') else 3,
            'ai_only': task.ai_only,
            'fetch_details': task.fetch_details,
            'num_articles': task.num_articles,
            'min_keywords': task.min_keywords
        }
        
        # 在新線程中執行任務
        thread = threading.Thread(
            target=self._execute_task_thread,
            args=(task_id, crawler_instance, task_args)
        )
        thread.start()
        
        self.task_threads[task_id] = thread
        self.running_tasks[task_id] = {
            'status': 'starting',
            'progress': 0,
            'message': '正在啟動任務',
            'start_time': datetime.now().isoformat()
        }
        
        return {
            'success': True,
            'message': '任務已啟動',
            'task_id': task_id
        }
        
    def _execute_task_thread(self, task_id, crawler_instance, task_args):
        """在線程中執行任務"""
        try:
            # 更新任務開始狀態
            self._update_task_status(task_id, 'running', 0, '開始執行任務')
            
            # 執行爬蟲任務
            result_df = crawler_instance.execute_task(task_id, task_args, self.db_manager)
            
            # 更新任務完成狀態
            self._update_task_status(
                task_id, 
                'completed', 
                100, 
                f'任務完成，爬取了 {len(result_df)} 篇文章'
            )
            
            # 更新任務在數據庫中的狀態
            self.tasks_repo.update_last_run(task_id, True)
            
        except Exception as e:
            self.logger.error(f"任務執行失敗: {str(e)}", exc_info=True)
            self._update_task_status(task_id, 'failed', 0, f'任務失敗: {str(e)}')
            self.tasks_repo.update_last_run(task_id, False, str(e))
            
        finally:
            # 清理線程資源
            if task_id in self.task_threads:
                del self.task_threads[task_id]
                
    def _update_task_status(self, task_id, status, progress, message):
        """更新任務狀態"""
        if task_id in self.running_tasks:
            self.running_tasks[task_id].update({
                'status': status,
                'progress': progress,
                'message': message,
                'update_time': datetime.now().isoformat()
            })
            
    def get_task_status(self, task_id: int) -> Dict:
        """獲取任務的當前狀態"""
        if task_id in self.running_tasks:
            return self.running_tasks[task_id]
            
        # 如果不在運行中，檢查數據庫狀態
        task = self.tasks_repo.get_by_id(task_id)
        if task:
            if task.last_run_at:
                status = 'completed' if task.last_run_success else 'failed'
                return {
                    'status': status,
                    'progress': 100 if status == 'completed' else 0,
                    'message': task.last_run_message or f'上次運行於 {task.last_run_at}',
                    'last_run_at': task.last_run_at.isoformat() if task.last_run_at else None
                }
            else:
                return {
                    'status': 'pending',
                    'progress': 0,
                    'message': '未曾執行'
                }
                
        return {
            'status': 'unknown',
            'progress': 0,
            'message': '任務不存在'
        }
        
    def start_scheduler(self):
        """啟動自動任務的排程器"""
        self.scheduler_running = True
        scheduler_thread = threading.Thread(target=self._scheduler_loop)
        scheduler_thread.daemon = True
        scheduler_thread.start()
        self.logger.info("爬蟲任務排程器已啟動")
        
    def stop_scheduler(self):
        """停止排程器"""
        self.scheduler_running = False
        self.logger.info("爬蟲任務排程器正在停止")
        
    def _scheduler_loop(self):
        """排程器主循環"""
        while self.scheduler_running:
            try:
                # 獲取需要執行的自動任務
                pending_tasks = self.tasks_repo.find_auto_tasks()
                
                for task in pending_tasks:
                    # 檢查任務是否已在運行
                    if task.id in self.running_tasks:
                        continue
                        
                    # 檢查是否達到執行條件
                    if self._should_execute_task(task):
                        self.logger.info(f"自動執行任務: {task.name} (ID: {task.id})")
                        self.execute_task(task.id)
                        
                # 每分鐘檢查一次
                time.sleep(60)
                
            except Exception as e:
                self.logger.error(f"排程器運行錯誤: {str(e)}", exc_info=True)
                time.sleep(300)  # 發生錯誤後等待5分鐘再繼續
                
    def _should_execute_task(self, task):
        """檢查任務是否該執行"""
        # 實現排程邏輯
        # 例如: daily, weekly, monthly, 或 cron 表達式
        # 這裡需要根據 task.schedule 和 task.last_run_at 來決定
        
        # 簡單實現，可根據需求擴展
        if not task.schedule:
            return False
            
        now = datetime.now()
        
        # 如果從未運行過，立即執行
        if not task.last_run_at:
            return True
            
        # 計算時間差
        time_diff = (now - task.last_run_at).total_seconds()
        
        # 根據調度類型計算是否應該執行
        if task.schedule == 'hourly':
            return time_diff >= 3600
        elif task.schedule == 'daily':
            return time_diff >= 86400
        elif task.schedule == 'weekly':
            return time_diff >= 604800
        else:
            # 嘗試解析 cron 表達式或其他排程格式
            # 這裡需要額外的邏輯
            return False 