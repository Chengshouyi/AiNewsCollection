"""
此示例顯示如何在系統的任何地方獲取任務執行服務的單體實例
不需要傳遞db_manager參數，因為單體已經初始化
"""

import logging
from src.services.task_executor_service import TaskExecutorService

# 設定日誌
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def example_task_usage():
    """示例任務使用，展示如何在系統中任何地方獲取任務執行服務實例"""
    
    # 獲取任務執行服務的單體實例
    # 不需要再傳遞db_manager，因為實例已在主程序中初始化
    task_executor = TaskExecutorService.get_instance()
    
    # 獲取所有正在執行的任務
    running_tasks = task_executor.get_running_tasks()
    logging.info(f"目前執行中的任務: {running_tasks}")
    
    # 可以用於以下操作：
    # 1. 取得任務執行狀態
    # task_status = task_executor.get_task_status(task_id)
    
    # 2. 測試爬蟲功能
    # test_result = task_executor.test_crawler('CNA爬蟲', {'max_pages': 1, 'num_articles': 3})
    
    # 3. 執行任務
    # execute_result = task_executor.execute_task(task_id)
    
    # 4. 取消任務
    # cancel_result = task_executor.cancel_task(task_id)
    
    # 5. 僅收集連結
    # links_result = task_executor.collect_links_only(task_id)
    
    # 6. 僅獲取內容
    # content_result = task_executor.fetch_content_only(task_id)
    
    # 7. 獲取完整文章
    # full_article_result = task_executor.fetch_full_article(task_id)

if __name__ == "__main__":
    # 示例呼叫
    example_task_usage() 