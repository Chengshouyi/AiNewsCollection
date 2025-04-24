from typing import Dict, Any, List, Callable
from abc import ABC, abstractmethod

class ProgressListener(ABC):
    """進度監聽介面，用於接收爬蟲進度更新"""
    
    @abstractmethod
    def on_progress_update(self, task_id: int, progress_data: Dict[str, Any]) -> None:
        """
        當進度更新時被調用
        
        Args:
            task_id: 任務ID
            progress_data: 進度數據，包含progress、message、scrape_phase等
        """
        pass

class ProgressReporter:
    """進度報告器，管理監聽者並發送進度更新"""
    
    def __init__(self):
        self.listeners: Dict[int, List[ProgressListener]] = {}  # 按任務ID分組的監聽者
        
    def add_listener(self, task_id: int, listener: ProgressListener) -> None:
        """
        添加監聽者
        
        Args:
            task_id: 任務ID
            listener: 監聽者實例
        """
        if task_id not in self.listeners:
            self.listeners[task_id] = []
        if listener not in self.listeners[task_id]:
            self.listeners[task_id].append(listener)
            
    def remove_listener(self, task_id: int, listener: ProgressListener) -> None:
        """
        移除監聽者
        
        Args:
            task_id: 任務ID
            listener: 要移除的監聽者實例
        """
        if task_id in self.listeners and listener in self.listeners[task_id]:
            self.listeners[task_id].remove(listener)
            
    def clear_listeners(self, task_id: int) -> None:
        """
        清除指定任務的所有監聽者
        
        Args:
            task_id: 任務ID
        """
        if task_id in self.listeners:
            self.listeners[task_id] = []
            
    def notify_progress(self, task_id: int, progress_data: Dict[str, Any]) -> None:
        """
        通知所有監聽者進度更新
        
        Args:
            task_id: 任務ID
            progress_data: 進度數據
        """
        if task_id in self.listeners:
            for listener in self.listeners[task_id]:
                try:
                    listener.on_progress_update(task_id, progress_data)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"通知監聽者時發生錯誤: {str(e)}", exc_info=True)
