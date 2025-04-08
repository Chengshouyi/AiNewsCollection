# SchedulerService 使用說明

## 概述

`SchedulerService` 是一個使用 APScheduler 的 `BackgroundScheduler` 實現的定時任務調度服務。它負責根據資料庫中儲存的 CrawlerTasks 任務的 cron 表達式，定時觸發任務執行。

## 主要功能

- 根據任務的 cron 表達式定時觸發任務執行
- 支持啟動/停止調度器
- 支持重新載入調度任務（當任務設定變更時）
- 提供調度器狀態查詢

## 依賴項

- APScheduler
- CrawlerTasksRepository: 用於查詢爬蟲任務
- TaskExecutor: 用於執行爬蟲任務

## 基本用法

### 初始化 SchedulerService

```python
from src.services import SchedulerService
from src.database.database_manager import DatabaseManager

# 初始化資料庫管理器
db_manager = DatabaseManager()

# 創建 SchedulerService 實例
scheduler_service = SchedulerService(db_manager=db_manager)
```

### 啟動調度器

```python
# 啟動調度器，開始監聽任務
result = scheduler_service.start_scheduler()
if result['success']:
    print(f"調度器啟動成功: {result['message']}")
else:
    print(f"調度器啟動失敗: {result['message']}")
```

### 停止調度器

```python
# 停止調度器
result = scheduler_service.stop_scheduler()
if result['success']:
    print(f"調度器停止成功: {result['message']}")
else:
    print(f"調度器停止失敗: {result['message']}")
```

### 重新載入調度器

當任務資料（例如 cron 表達式）發生變更時，可以重新載入調度器以更新定時任務。

```python
# 重新載入調度器
result = scheduler_service.reload_scheduler()
if result['success']:
    print(f"調度器重載成功: {result['message']}")
else:
    print(f"調度器重載失敗: {result['message']}")
```

### 獲取調度器狀態

```python
# 獲取調度器狀態
status_result = scheduler_service.get_scheduler_status()
if status_result['success']:
    status = status_result['status']
    print(f"調度器狀態: 運行中={status['running']}, 任務數={status['job_count']}")
    print(f"最後啟動時間: {status['last_start_time']}")
    print(f"最後停止時間: {status['last_shutdown_time']}")
```

## 注意事項

1. 確保所有帶 cron 表達式的任務格式正確。
2. 調度器使用 UTC 時區，確保時區設定正確。
3. 調度器停止時會清空所有任務，重新啟動時會重新載入所有任務。
4. 若需在程序退出時自動停止調度器，可使用 Python 的 `atexit` 模組註冊清理函數。

## 與其他服務集成

### 在 Flask 應用中使用

```python
from flask import Flask
from src.services import SchedulerService
import atexit

app = Flask(__name__)

# 初始化調度器
scheduler_service = SchedulerService()

# 在應用啟動時啟動調度器
@app.before_first_request
def init_scheduler():
    scheduler_service.start_scheduler()
    
# 在應用退出時停止調度器
atexit.register(lambda: scheduler_service.stop_scheduler())
```

### 在長期運行的腳本中使用

```python
import time
from src.services import SchedulerService

def main():
    # 初始化調度器
    scheduler_service = SchedulerService()
    
    try:
        # 啟動調度器
        scheduler_service.start_scheduler()
        
        # 保持腳本運行
        while True:
            time.sleep(60)
            
    except KeyboardInterrupt:
        # 接收到中斷信號時停止調度器
        scheduler_service.stop_scheduler()
        print("調度器已停止")
        
if __name__ == "__main__":
    main()
```

## 常見問題排解

1. **調度器未啟動**：檢查 `start_scheduler()` 返回的結果是否成功。
2. **任務未執行**：確認任務的 cron 表達式是否正確，並檢查 `is_auto` 標志是否為 `True`。
3. **執行失敗**：查看日誌以獲取詳細錯誤信息。

## 進階配置

調度器支持多種高級配置，如設置最大線程數、調整 misfire 策略等。可以通過修改 `BackgroundScheduler` 的參數進行配置：

```python
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

# 自訂調度器配置
scheduler = BackgroundScheduler(
    timezone=pytz.UTC,
    job_defaults={
        'coalesce': True,
        'max_instances': 3
    },
    executor='processpool'  # 使用進程池執行器
)

# 將自訂調度器傳入 SchedulerService
scheduler_service = SchedulerService()
scheduler_service.cron_scheduler = scheduler
``` 