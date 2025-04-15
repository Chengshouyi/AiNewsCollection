"""
此示例顯示如何在系統的任何地方獲取排程服務的單體實例
不需要傳遞db_manager參數，因為單體已經初始化
"""

import logging
from src.services.scheduler_service import SchedulerService

# 設定日誌
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def example_task_manager():
    """示例任務管理器，展示如何在系統中任何地方獲取排程服務實例"""
    
    # 獲取排程服務的單體實例
    # 不需要再傳遞db_manager，因為實例已在主程序中初始化
    scheduler_service = SchedulerService.get_instance()
    
    # 使用排程服務
    status = scheduler_service.get_scheduler_status()
    
    if status['running']:
        logging.info(f"排程器正在運行中，目前有 {status['job_count']} 個任務")
        
        # 獲取所有排程作業的信息
        jobs_info = scheduler_service.get_persisted_jobs_info()
        logging.info(f"排程作業信息: {jobs_info}")
        
        # 可以在這裡添加重新載入排程器或停止排程器的邏輯
        # scheduler_service.reload_scheduler()
        # scheduler_service.stop_scheduler()
    else:
        logging.info("排程器未運行，啟動排程器")
        result = scheduler_service.start_scheduler()
        logging.info(f"啟動排程器結果: {result}")

if __name__ == "__main__":
    # 示例呼叫
    example_task_manager() 