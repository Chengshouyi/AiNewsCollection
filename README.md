# 新聞收集與問答系統

[![Python 版本](https://img.shields.io/badge/python-3.9-blue?style=flat-square)](https://www.python.org/downloads/release/python-390/)
[![程式碼風格: black](https://img.shields.io/badge/code%20style-black-000000.svg?style=flat-square)](https://github.com/psf/black)
[![授權條款: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)

一個功能全面的新聞爬蟲與知識管理平台，整合 RAG 技術支援在地化中文問答。

## 目錄

* [背景](#背景)
* [功能](#功能)
* [系統架構](#系統架構)
* [技術堆疊](#技術堆疊)
* [資料夾架構](#資料夾架構)
* [API 端點](#api-端點)
* [安裝與設定](#安裝與設定)
  * [開發環境](#開發環境)
  * [生產環境](#生產環境)
* [使用範例](#使用範例)
  * [爬蟲管理](#爬蟲管理-範例)
  * [任務管理](#任務管理-範例)
  * [文章查詢](#文章查詢-範例)
* [部署指南](#部署指南)
* [貢獻](#貢獻)
* [維護者](#維護者)
* [授權條款](#授權條款)

## 背景

### 願景與目標

* **願景:** 打造一個功能全面的新聞爬蟲與知識管理平台，整合 RAG 技術支援在地化中文問答[**規劃建置中**]。
* **目標用戶:** 個人用戶（技術愛好者/研究者）、小型團隊。
* **適用場景:** 個人新聞訂閱、技術趨勢研究、NLP 數據集構建、領域知識問答。

## 功能

### 核心功能

1. **爬蟲管理**
   * ✅ 從資料庫讀取爬蟲資料，提供列表展示。
   * ✅ 支援新增爬蟲設定。
   * ✅ 支援修改爬蟲設定。
   * ✅ 支援刪除爬蟲設定。
   * ✅ 提供測試爬蟲功能，並透過 WebSocket 顯示進度。
2. **任務管理**
   * ✅ 從資料庫讀取任務列表。
   * ✅ 支援新增任務 。
   * ✅ 支援修改任務。
   * ✅ 支援刪除任務 。
   * ✅ **自動爬取設定:**
     * ✅ 設定任務名稱、選擇爬蟲、設定爬取週期 (Cron 表達式) 。
     * ✅ 設定是否只收集 AI 相關資料。
     * ✅ 設定備註。
   * ✅ **手動爬取:**
     * ✅ 提供按鈕手動觸發任務執行。
     * ✅ 提供任務取消功能。
     * ✅ 透過 WebSocket 顯示爬取進度 (連結階段/內容階段)**[進度回報機制改善中]** 。
     * ✅ 針對特定手動模式，提供抓取連結後，讓使用者勾選目標連結再爬取完整內容的功能 。
     * ✅ 支援多種爬取模式（如僅連結、完整內容）及限制文章數量 。
3. **資料展示**
   * ✅ 提供文章列表和篩選。
   * ✅ 提供搜尋功能 。
   * ✅ 文章列表展示欄位：ID, 標題 (Title), 來源 (Source), 發布時間 (Published At), 是否 AI 相關 (is\_ai\_related), 最後爬取時間 (Last Scrape Attempt), 爬取狀態 (Scrape Status)。
   * ✅ 提供文章詳細頁面跳轉或快速查看模態框。
4. **資料轉換 (規劃中)**
   * ❌ 將爬取資料轉為領域資料庫，支援 RAG 應用 (尚待實作)。
   * ❌ 提供轉換任務查看功能 (尚待實作)。
5. **問答對話 (規劃中)**
   * ❌ 整合 RAG 技術與在地模型，根據領域資料庫回答中文問題 (尚待實作)。
6. **基礎功能**
   * ✅ 使用 Flask 網頁介面。
   * ✅ 透過 API 與後端互動。
   * ✅ 使用 WebSocket 進行即時狀態更新。
   * ✅ 使用 PostgreSQL 資料庫。
   * ✅ 使用 Git 與 Docker Compose 進行管理與部署。

### 未來擴展功能

* 主題過濾：根據關鍵詞或標籤篩選文章。
* 通知系統：新文章到達時通過電子郵件或 RSS 通知。

## 系統架構

以下是本系統的架構圖：

![系統架構圖](sys_arh.jpg)

## 資料夾架構

```
.
├── .devcontainer/       # VS Code 開發容器設定
├── .github/             # GitHub Actions 工作流程 (CI/CD)
├── data/                # 爬蟲配置檔案、持久化資料
│   └── web_site_configs/ # 網站爬蟲設定檔
├── docker/              # 其他 Docker 相關設定 (例如 Nginx)
├── logs/                # 應用程式日誌
├── migrations/          # Alembic 資料庫遷移腳本
├── src/                 # 核心原始碼
│   ├── config/          # 應用程式配置管理
│   ├── crawlers/        # 各種新聞網站的爬蟲實作
│   ├── database/        # 資料庫模型 (SQLAlchemy) 和連線設定
│   ├── error/           # 自訂錯誤處理
│   ├── interface/       # 定義抽象介面 (例如爬蟲介面)
│   ├── models/          # Pydantic 資料模型 (API 請求/回應)
│   ├── services/        # 業務邏輯服務 (例如任務管理、爬蟲執行)
│   ├── utils/           # 通用工具函數
│   └── web/             # Flask Web 應用程式
│       ├── api/         # API 藍圖 (Blueprints)
│       ├── static/      # 靜態檔案 (CSS, JS, Images)
│       ├── templates/   # HTML 模板 (Jinja2)
│       ├── app.py       # Flask 應用程式實例和設定
│       └── views.py     # 頁面渲染路由
├── tests/               # Pytest 測試案例
├── .dockerignore        # Docker 建置時忽略的檔案
├── .env.example         # 環境變數範本檔
├── .gitignore           # Git 忽略的檔案
├── .pylintrc            # Pylint 設定檔
├── alembic.ini          # Alembic 設定檔
├── docker-compose.yml   # Docker Compose 主要設定 (生產)
├── docker-compose.override.yml # Docker Compose 開發環境覆蓋設定
├── Dockerfile           # 生產環境 Dockerfile
├── LICENSE              # 授權條款
├── README.md            # 就是你現在正在看的這個檔案
├── requirements.txt     # Python 核心依賴
├── requirements-dev.txt # Python 開發依賴
└── run.py               # 應用程式進入點 (可能包含啟動腳本或 Celery worker)
```

## API 端點

系統提供 RESTful API 來管理爬蟲、任務和文章。詳細端點請參考以下摘要：

<details>
<summary>點擊展開 API 端點列表</summary>

### crawler\_api.py (Blueprint: crawler\_bp, 前綴: /api/crawlers)

* **GET /api/crawlers/**: 取得所有爬蟲設定列表。
* **POST /api/crawlers/**: 新增一個爬蟲設定及其配置檔案 (使用 multipart/form-data)。
* **GET /api/crawlers/<int:crawler\_id>**: 取得特定爬蟲設定。
* **PUT /api/crawlers/<int:crawler\_id>**: 更新特定爬蟲設定。
* **DELETE /api/crawlers/<int:crawler\_id>**: 刪除特定爬蟲設定。
* **GET /api/crawlers/types**: 取得可用的爬蟲類型列表。
* **GET /api/crawlers/active**: 取得所有活動中的爬蟲設定。
* **POST /api/crawlers/<int:crawler\_id>/toggle**: 切換爬蟲活躍狀態。
* **GET /api/crawlers/name/<string:name>**: 根據名稱模糊查詢爬蟲設定。可選參數 `is_active` (boolean)。
* **GET /api/crawlers/type/<string:crawler\_type>**: 根據爬蟲類型查詢爬蟲設定。可選參數 `is_active` (boolean)。
* **GET /api/crawlers/target/<string:target\_pattern>**: 根據目標站點模糊查詢爬蟲設定。可選參數 `is_active` (boolean)。
* **GET /api/crawlers/statistics**: 獲取爬蟲的統計資訊。
* **GET /api/crawlers/exact-name/<string:crawler\_name>**: 根據精確名稱查詢爬蟲設定。
* **POST /api/crawlers/create-or-update**: 創建或更新爬蟲設定（根據名稱判斷）。
* **POST /api/crawlers/batch-toggle**: 批量切換爬蟲的活躍狀態。
* **POST /api/crawlers/filter**: 根據多個條件（名稱、類型、目標、狀態）過濾爬蟲設定 (支援分頁)。
* **GET /api/crawlers/<int:crawler\_id>/config**: 獲取指定爬蟲的配置檔案內容。

### tasks\_api.py (Blueprint: tasks\_bp, 前綴: /api/tasks)

* **GET /api/tasks/scheduled**: 獲取所有活躍的自動排程任務。
* **POST /api/tasks/scheduled**: 創建一個新的排程任務。
* **PUT /api/tasks/scheduled/<int:task\_id>**: 更新一個現有的排程任務。
* **DELETE /api/tasks/scheduled/<int:task\_id>**: 刪除一個排程任務 (包含從排程器移除)。
* **POST /api/tasks/manual/start**: 創建並立即執行一個抓取完整文章的手動任務 (FULL\_SCRAPE)。
* **GET /api/tasks/manual/<int:task\_id>/status**: 獲取特定手動任務的狀態。
* **POST /api/tasks/manual/collect-links**: 創建並立即執行一個只收集連結的手動任務 (LINK\_COLLECTION)。
* **GET /api/tasks/manual/<int:task\_id>/links**: 獲取特定連結收集任務結果中未爬取的連結。
* **POST /api/tasks/manual/<int:task\_id>/fetch-content**: 為已完成連結收集的任務，創建並執行一個抓取內容的手動任務 (CONTENT\_FETCH)。
* **GET /api/tasks/manual/<int:task\_id>/results**: 獲取特定手動任務的爬取結果。
* **POST /api/tasks/manual/test**: 測試單個 URL 或連結的爬取 (不創建任務)。
* **POST /api/tasks/<int:task\_id>/cancel**: 取消一個正在運行的任務。
* **GET /api/tasks/<int:task\_id>/history**: 獲取特定任務的歷史狀態記錄。
* **POST /api/tasks/<int:task\_id>/run**: 手動觸發執行一個任務。
* **POST /api/tasks/**: 創建一個任務 (通用)。
* **PUT /api/tasks/<int:task\_id>**: 更新一個任務 (通用)。
* **GET /api/tasks/**: 獲取所有任務列表 (支援分頁/篩選/排序)。
* **DELETE /api/tasks/<int:task\_id>**: 刪除一個任務 (通用)。

### article\_api.py (Blueprint: article\_bp, 前綴: /api/articles)

* **GET /api/articles/**: 取得文章列表 (支援分頁/篩選/排序)。
* **GET /api/articles/<int:article\_id>**: 取得單篇文章詳情。
* **GET /api/articles/search**: 專用搜尋端點 (根據關鍵字 'q' 搜尋標題/內容/摘要)。

### views.py (Blueprint: view\_bp, 前綴: /)

* **GET /**: 渲染主頁面 (index.html)。
* **GET /crawlers**: 渲染爬蟲管理頁面 (crawlers.html)。
* **GET /tasks**: 渲染任務管理頁面 (tasks.html)。
* **GET /articles**: 渲染文章列表頁面 (articles.html)。
* **GET /articles/<int:article\_id>**: 渲染單篇文章查看頁面 (article\_view.html)。

</details>

## 安裝與設定

本系統使用 Docker 和 Docker Compose 進行環境管理。

### 開發環境

1. **前置需求:** 安裝 Docker 和 Docker Compose。

2. **克隆倉庫:** `git clone https://github.com/Chengshouyi/AiNewsCollection.git`

3. **進入目錄:** `cd YOUR_REPOSITORY`

4. **配置環境變數 (可選):** 在專案根目錄創建 `.env` 文件可覆蓋 `docker-compose.yml` 中的預設資料庫設定。
   
   ```dotenv
   # .env (開發環境範例)
   # --- Database Settings ---
   POSTGRES_DB=ainews_dev
   POSTGRES_USER=dev_user
   # Use a simple password for local dev, or keep it the same as prod if preferred
   POSTGRES_PASSWORD=dev_password123Y5%jsjfjdjfg
   # --- Flask Settings ---
   # Development specific secret key (less critical than production)
   SECRET_KEY=a_simple_dev_secret_key
   # --- Worker Settings ---
   SCHEDULE_RELOAD_INTERVAL_SEC=1200 # Maybe less frequent reloading in dev
   # --- Log Settings ---
   LOG_LEVEL=DEBUG  # DEBUG
   LOG_OUTPUT_MODE=console  # 只輸出到控制台  file:只輸出到文件 both:同時輸出到控制台和文件 (預設)
   LOG_CLEANUP_LOG_DIR=logs   # 可選：指定不同的日誌目錄 相對於/app
   LOG_CLEANUP_MODULE_NAME=""  # 可選：只清理 'main_app' 模組的日誌，或""清理全部
   LOG_CLEANUP_KEEP_DAYS=""         # 可選：保留最近 n 天的日誌，或""刪除全部
   LOG_CLEANUP_DRY_RUN=false         # 可選：啟用 Dry Run (建議測試時使用) true/false
   
   # --- SQL settings ---
   SQLALCHEMY_ECHO=False   #True
   
   # --- data locate setting ---
   WEB_SITE_CONFIG_DIR=/app/data/web_site_configs  #不可變更
   ```

5. **安裝開發依賴:** 確保 `requirements-dev.txt` 中的依賴已安裝 (若使用 Dev Container，通常會自動處理)。

6. **啟動服務:**
   
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d
   ```

7. **資料庫遷移:** (首次啟動或模型變更後)
   
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.override.yml exec web alembic upgrade head
   ```

8. **啟動 Flask 應用:** `docker-compose.override.yml` 將 web 服務的啟動指令設為 `sleep infinity`，您需要進入容器手動啟動 Flask 開發伺服器 (或透過 VS Code Dev Container 設定)。
   
   ```bash
   # 進入 web 容器
   docker-compose -f docker-compose.yml -f docker-compose.override.yml exec web bash
   
   # 在容器內啟動 Flask (範例)
   flask run --host=0.0.0.0 --port=8000 --debug
   ```

9. **訪問:** 應用程式將在 `http://localhost:8001` (根據 `docker-compose.override.yml` 的端口映射)。資料庫可透過 `localhost:5432` 訪問。

**開發環境特性:**

* 使用 `.devcontainer/Dockerfile` 建置 `web` 服務。
* 安裝 `requirements.txt` 和 `requirements-dev.txt` 中的依賴。
* `FLASK_ENV=development`。
* 本地程式碼目錄掛載到 `/app`，支援熱加載。
* 資料庫端口映射到主機 `5432`。
* Web 服務端口映射到主機 `8001`。

### 生產環境

1. **前置需求:** 在生產伺服器上安裝 Docker 和 Docker Compose。
2. **取得程式碼:** 將專案複製或 clone 到伺服器。
3. **創建 `.env` 文件 (極度重要):** 在專案根目錄創建 `.env` 文件，並填入**安全**的生產環境配置。**切勿**使用預設值或提交此文件到版本控制。
   
   ```dotenv
   # .env (生產環境範例 - 請務必替換為真實且安全的值!)
   
   # --- Database Settings ---
   POSTGRES_DB=ainews_prod
   POSTGRES_USER=dev_prod
   # Use a simple password for local dev, or keep it the same as prod if preferred
   POSTGRES_PASSWORD=prod_password123Y5%jsjfjdjfg
   # --- Flask Settings ---
   # Development specific secret key (less critical than production)
   SECRET_KEY=a_simple_prod_secret_key
   # --- Worker Settings ---
   SCHEDULE_RELOAD_INTERVAL_SEC=1200 # Maybe less frequent reloading in dev
   # --- Log Settings ---
   LOG_LEVEL=INFO  # DEBUG
   LOG_OUTPUT_MODE=both  # 只輸出到控制台  file:只輸出到文件 both:同時輸出到控制台和文件 (預設)
   LOG_CLEANUP_LOG_DIR=logs   # 可選：指定不同的日誌目錄 相對於/app
   LOG_CLEANUP_MODULE_NAME=""  # 可選：只清理 'main_app' 模組的日誌，或""清理全部
   LOG_CLEANUP_KEEP_DAYS=7         # 可選：保留最近 n 天的日誌，或""刪除全部
   LOG_CLEANUP_DRY_RUN=false         # 可選：啟用 Dry Run (建議測試時使用) true/false
   
   # --- SQL settings ---
   SQLALCHEMY_ECHO=False   #True
   
   # --- data locate setting ---
   WEB_SITE_CONFIG_DIR=/app/data/web_site_configs  #不可變更
   ```
4. **建置映像檔 (可選):** `docker-compose build` (如果尚未建置或需要更新)。
5. **啟動服務:**
   
   ```bash
   docker-compose up -d
   ```
6. **資料庫遷移:** (首次啟動或模型變更後)
   
   ```bash
   docker-compose exec web alembic upgrade head
   ```
7. **訪問:** 應用程式將在 `http://YOUR_SERVER_IP:8001`。建議配置反向代理 (如 Nginx) 來處理 HTTPS 和端口轉發。

**生產環境特性:**

* 使用根目錄的 `Dockerfile` 建置 `web` 服務。
* 僅安裝 `requirements.txt` 中的依賴 (注意：目前包含開發工具，建議分離)。
* `FLASK_ENV=production`。
* 依賴 `.env` 文件設定資料庫連接和 `SECRET_KEY`。
* 程式碼包含在 Docker 映像檔中，不掛載本地目錄。
* 使用 Gunicorn (`gunicorn --workers 4 --bind 0.0.0.0:8000 src.web.app:app`) 運行 Web 應用。
* 資料庫端口**不**映射到主機。
* Web 服務端口映射到主機 `8001`。

## 使用範例

您可以透過 Web UI 或直接呼叫 API 來使用系統。以下是一些基於測試案例的 API 使用範例 (使用 `curl`，假設服務運行在 `localhost:8001`)，更多的範例請參閱` /tests` (測試資料庫使用SQLite memory DB)：

### 爬蟲管理 (範例)

* **獲取所有爬蟲:**
  
  ```bash
  curl -X GET http://localhost:8001/api/crawlers/
  ```
* **創建一個新爬蟲 (假設配置檔為 config.json):**
  
  ```bash
  # 注意：實際創建可能需要透過 UI 或更複雜的客戶端來處理 multipart/form-data
  # 以下為示意
  curl -X POST http://localhost:8001/api/crawlers/ \
       -H "Content-Type: multipart/form-data" \
       -F "crawler_name=範例爬蟲" \
       -F "crawler_type=GenericNews" \
       -F "target_site=example.com" \
       -F "config_file=@/path/to/your/config.json"
  ```
* **獲取 ID 為 1 的爬蟲:**
  
  ```bash
  curl -X GET http://localhost:8001/api/crawlers/1
  ```
* **更新 ID 為 1 的爬蟲:**
  
  ```bash
  curl -X PUT http://localhost:8001/api/crawlers/1 \
       -H "Content-Type: application/json" \
       -d '{"description": "更新後的描述"}'
  ```
* **刪除 ID 為 1 的爬蟲:**
  
  ```bash
  curl -X DELETE http://localhost:8001/api/crawlers/1
  ```
* **測試爬蟲 (觸發測試任務):**
  
  ```bash
  curl -X POST http://localhost:8001/api/tasks/test_crawler \
       -H "Content-Type: application/json" \
       -d '{"crawler_id": 1, "test_url": "http://example.com/news/123"}'
  ```

### 任務管理 (範例)

* **創建自動排程任務 (每小時執行一次 ID 為 1 的爬蟲):**
  
  ```bash
  curl -X POST http://localhost:8001/api/tasks/scheduled \
       -H "Content-Type: application/json" \
       -d '{"task_name": "每小時新聞", "crawler_id": 1, "cron_expression": "0 * * * *", "is_ai_related_filter": false}'
  ```
* **啟動手動完整爬取任務 (使用 ID 為 2 的爬蟲):**
  
  ```bash
  curl -X POST http://localhost:8001/api/tasks/manual/start \
       -H "Content-Type: application/json" \
       -d '{"crawler_id": 2, "task_name": "手動爬取科技新聞", "article_limit": 10}'
  ```
* **獲取 ID 為 5 的手動任務狀態:**
  
  ```bash
  curl -X GET http://localhost:8001/api/tasks/manual/5/status
  ```
* **手動觸發 ID 為 3 的 (排程) 任務:**
  
  ```bash
  curl -X POST http://localhost:8001/api/tasks/3/run
  ```
* **取消 ID 為 6 的任務:**
  
  ```bash
  curl -X POST http://localhost:8001/api/tasks/6/cancel
  ```

### 文章查詢 (範例)

* **獲取第一頁文章 (預設每頁 10 篇):**
  
  ```bash
  curl -X GET http://localhost:8001/api/articles/
  ```
* **獲取第二頁文章，每頁 20 篇:**
  
  ```bash
  curl -X GET http://localhost:8001/api/articles/?page=2&per_page=20
  ```
* **搜尋標題或內容包含 "人工智慧" 的文章:**
  
  ```bash
  curl -X GET "http://localhost:8001/api/articles/search?q=人工智慧"
  ```
* **獲取 ID 為 100 的文章詳情:**
  
  ```bash
  curl -X GET http://localhost:8001/api/articles/100
  ```

## 部署指南

建議使用 **Docker Compose** 進行部署。

1. **確保伺服器已安裝 Docker 和 Docker Compose。**
2. **將專案程式碼部署到伺服器。**
3. **在專案根目錄創建 `.env` 文件，填入生產環境的安全配置 (參考 [生產環境設定](#生產環境) 部分)。** 這是最關鍵的步驟。
4. **(可選) 預先建置映像檔:** `docker-compose build`
5. **啟動服務:** `docker-compose up -d`
6. **(首次) 執行資料庫遷移:** `docker-compose exec web alembic upgrade head`
7. **設置反向代理 (如 Nginx):** 強烈建議使用 Nginx 或類似工具處理 HTTPS、端口轉發 (例如 80/443 -> 8001) 和負載均衡 (如果需要)。
8. **配置資料庫備份策略。**
9. **考慮設置集中式日誌管理和監控系統。**

## 貢獻

歡迎各種形式的貢獻！如果您想做出貢獻，請參考以下步驟：

1. Fork 本倉庫。
2. 創建您的特性分支 (`git checkout -b feature/AmazingFeature`)。
3. 提交您的更改 (`git commit -m 'Add some AmazingFeature'`)。
4. 將您的分支推送到遠程倉庫 (`git push origin feature/AmazingFeature`)。
5. 開啟一個 Pull Request。

請確保您的程式碼符合風格要求並包含必要的測試。

## 授權條款

本專案採用 MIT 授權條款。詳情請參閱 [LICENSE](LICENSE) 文件。