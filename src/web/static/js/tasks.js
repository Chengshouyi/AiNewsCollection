// 任務管理頁面的 JavaScript
console.log("任務管理 JS 已加載");

// 全局變數
let socket = null;
let tasks = []; // 存儲任務列表
let crawlers = []; // 存儲爬蟲列表
let currentTaskId = null; // 當前操作的任務ID
let fetchedLinks = []; // 已爬取的連結列表

// --- 頁面加載和事件綁定 --- 
$(document).ready(function () {
    // 頁面加載時初始化 WebSocket 連接
    setupWebSocket();

    // 加載任務列表
    loadTasks();

    // 加載爬蟲列表 (用於新增/編輯任務時選擇)
    loadCrawlers();

    // 綁定新增任務按鈕事件
    $('#add-task-btn').click(function () {
        showTaskModal(null); // 傳入null表示新增模式
    });

    // 綁定任務類型變更事件
    $('#task-type').change(function () {
        updateScheduleFields($(this).val());
    });

    // 綁定保存按鈕事件
    $('#save-task-btn').click(function () {
        saveTask();
    });

    // 綁定刪除確認按鈕事件
    $('#confirm-delete-task-btn').click(function () {
        deleteTask(currentTaskId);
    });

    // 高級參數收合效果
    $('#toggle-advanced-params').click(function () {
        $('#advanced-params-container').slideToggle(300);
        $(this).find('i').toggleClass('bi-chevron-down bi-chevron-up');
    });

    // CSV 儲存選項顯示/隱藏前綴欄位
    $('#save-to-csv').change(function () {
        if ($(this).is(':checked')) {
            $('#csv-prefix-container').removeClass('d-none');
        } else {
            $('#csv-prefix-container').addClass('d-none');
        }
    });

    // 使用事件委託綁定表格中的編輯和刪除按鈕事件
    $('#tasks-table-body').on('click', '.edit-task-btn', function () {
        const taskId = $(this).data('id');
        showTaskModal(taskId);
    });

    $('#tasks-table-body').on('click', '.delete-task-btn', function () {
        currentTaskId = $(this).data('id');
        $('#delete-task-modal').modal('show');
    });

    // 綁定手動執行按鈕事件 (使用事件委託)
    $('#tasks-table-body').on('click', '.run-task-btn', function () {
        const button = $(this);
        const taskId = button.data('task-id');
        const taskType = button.data('task-type');
        if (!taskId) return;

        if (taskType === 'manual') {
            // 手動爬取流程，先抓取連結
            startManualLinksFetch(taskId);
        } else {
            // 自動任務直接執行
            runAutoTask(taskId, button);
        }
    });

    // 綁定取消任務按鈕事件
    $('#tasks-table-body').on('click', '.cancel-task-btn', function () {
        const taskId = $(this).data('task-id');
        if (!taskId) return;

        cancelTask(taskId);
    });

    // 手動爬取連結選擇模態框相關事件
    $('#select-all-links').click(function () {
        $('.link-checkbox').prop('checked', true);
        updateSelectedLinksCount();
    });

    $('#deselect-all-links').click(function () {
        $('.link-checkbox').prop('checked', false);
        updateSelectedLinksCount();
    });

    $('#manual-links-table-body').on('change', '.link-checkbox', function () {
        updateSelectedLinksCount();
    });

    $('#start-fetch-articles-btn').click(function () {
        const selectedLinks = getSelectedLinks();
        if (selectedLinks.length === 0) {
            alert('請至少選擇一個連結');
            return;
        }

        startFetchArticles(currentTaskId, selectedLinks);
    });
});

// --- WebSocket 處理 --- 
function setupWebSocket() {
    // 確保只初始化一次 socket
    if (socket && socket.connected) {
        console.log("WebSocket 已經連接");
        return;
    }

    // 連接到 Socket.IO 伺服器和 /tasks 命名空間
    // 使用 location.protocol, document.domain, location.port 動態構建 URL
    const socketUrl = `${location.protocol}//${document.domain}:${location.port}/tasks`;
    console.log(`嘗試連接到 WebSocket: ${socketUrl}`);
    socket = io.connect(socketUrl);

    socket.on('connect', () => {
        console.log('Socket.IO Connected to /tasks');
        // 連接成功後，自動加入當前頁面上可見任務的房間
        joinVisibleTaskRooms();
    });

    socket.on('disconnect', (reason) => {
        console.log(`Socket.IO Disconnected from /tasks: ${reason}`);
        // 可以加入重連邏輯
        // if (reason === 'io server disconnect') {
        //     // the disconnection was initiated by the server, you need to reconnect manually
        //     socket.connect();
        // }
    });

    socket.on('connect_error', (error) => {
        console.error('Socket.IO Connection Error:', error);
        // 可以在 UI 上顯示錯誤訊息
    });

    socket.on('task_progress', function (data) {
        console.log('Progress update:', data);
        // 獲取任務ID和會話ID（如果有）
        const taskId = data.task_id;
        const sessionId = data.session_id;

        // 更新UI，傳入會話ID以便在需要時使用
        updateTaskUI(taskId, data.progress, data.status, data.scrape_phase, data.message, data.articles_count, sessionId);
    });

    socket.on('task_finished', function (data) {
        console.log('Task finished:', data);
        const taskId = data.task_id;
        const sessionId = data.session_id;

        // 標記任務完成，傳入會話ID以便在需要時使用
        markTaskAsFinished(taskId, data.status, sessionId);

        // 可以選擇性地從房間離開
        // 如果有會話ID，應該包含在房間名稱中
        if (sessionId) {
            const roomName = `task_${taskId}_${sessionId}`;
            socket.emit('leave_room', { 'room': roomName });
            console.log(`離開房間: ${roomName}`);
        } else {
            // 向下兼容：如果沒有會話ID，使用舊的命名方式
            const roomName = `task_${taskId}`;
            socket.emit('leave_room', { 'room': roomName });
            console.log(`離開房間: ${roomName}`);
        }
    });

    socket.on('links_fetched', function (data) {
        console.log('Links fetched:', data);
        if (data.success) {
            loadFetchedLinks(data.task_id);
        } else {
            displayAlert('danger', '抓取連結失敗: ' + data.message);
        }
    });
}

function joinVisibleTaskRooms() {
    const taskIds = getAllVisibleTaskIds();
    taskIds.forEach(taskId => {
        if (taskId) { // 確保 taskId 有效
            // 使用舊的命名方式，因為頁面上僅標示了taskId
            // 這裡不能使用session_id，因為頁面加載時不知道任務可能的會話ID
            const roomName = `task_${taskId}`;
            console.log(`加入房間: ${roomName}`);
            socket.emit('join_room', { 'room': roomName });
        }
    });
}

// 新增：加入特定會話的房間
function joinTaskSessionRoom(taskId, sessionId) {
    if (!socket || !socket.connected) {
        console.error('WebSocket未連接，無法加入房間');
        return;
    }

    // 如果提供了會話ID，使用新的命名方式
    if (sessionId) {
        const roomName = `task_${taskId}_${sessionId}`;
        console.log(`加入特定會話房間: ${roomName}`);
        socket.emit('join_room', { 'room': roomName });
    } else {
        // 向下兼容：如果沒有會話ID，使用舊的命名方式
        const roomName = `task_${taskId}`;
        console.log(`加入任務房間: ${roomName}`);
        socket.emit('join_room', { 'room': roomName });
    }
}

// --- 輔助函數 --- 
function getAllVisibleTaskIds() {
    // 實現邏輯：從 DOM 中獲取當前頁面顯示的所有任務 ID
    // 假設任務行有 .task-row class 和 data-task-id 屬性
    let ids = [];
    $('.task-row').each(function () {
        const taskId = $(this).data('task-id');
        if (taskId) {
            ids.push(taskId);
        }
    });
    console.log("獲取到的可見 Task IDs:", ids);
    return ids;
}

function updateTaskUI(taskId, progress, status, scrapePhase, message, articlesCount, sessionId) {
    // 實現邏輯：找到對應 task_id 的 UI 元素並更新
    const taskRow = $(`.task-row[data-task-id="${taskId}"]`);
    if (taskRow.length) {
        // 如果提供了會話ID，將其存儲在行元素上，以便後續使用
        if (sessionId) {
            taskRow.attr('data-session-id', sessionId);
        }

        // 更新進度條
        const progressBar = taskRow.find('.progress .progress-bar'); // 選擇更精確
        if (progressBar.length) {
            progressBar.css('width', progress + '%').text(progress + '%');
            // 根據狀態改變進度條顏色 (可選)
            progressBar.removeClass('bg-success bg-warning bg-danger bg-info');
            if (status === 'COMPLETED') {
                progressBar.addClass('bg-success');
            } else if (status === 'RUNNING') {
                progressBar.addClass('bg-info');
            } else if (status === 'FAILED' || status === 'CANCELLED') {
                progressBar.addClass('bg-danger');
            } else {
                progressBar.addClass('bg-secondary'); // 其他狀態
            }
        }

        // 更新狀態文本
        const statusBadge = taskRow.find('.task-status-badge'); // 使用徽章 class
        if (statusBadge.length) {
            statusBadge.text(status);
            // 根據狀態改變徽章顏色
            statusBadge.removeClass('badge-success badge-warning badge-danger badge-info badge-secondary');
            if (status === 'COMPLETED') {
                statusBadge.addClass('badge-success');
            } else if (status === 'RUNNING') {
                statusBadge.addClass('badge-info');
            } else if (status === 'FAILED' || status === 'CANCELLED') {
                statusBadge.addClass('badge-danger');
            } else if (status === 'PENDING') {
                statusBadge.addClass('badge-warning');
            } else {
                statusBadge.addClass('badge-secondary');
            }
        }

        // 更新階段文本 (如果元素存在)
        const phaseElement = taskRow.find('.task-scrape-phase');
        if (phaseElement.length && scrapePhase) {
            phaseElement.text(`階段: ${scrapePhase}`);
        }

        // 更新消息文本 (如果元素存在)
        const messageElement = taskRow.find('.task-message');
        if (messageElement.length) {
            messageElement.text(message || '-'); // 顯示消息或'-'
        }

        // 更新文章數量 (如果元素存在)
        const articlesCountElement = taskRow.find('.task-articles-count');
        if (articlesCountElement.length && articlesCount !== undefined && articlesCount !== null) {
            articlesCountElement.text(`文章數: ${articlesCount}`);
        }

        // 根據狀態啟用/禁用按鈕
        const runButton = taskRow.find('.run-task-btn');
        const cancelButton = taskRow.find('.cancel-task-btn');
        if (status === 'RUNNING') {
            runButton.prop('disabled', true);
            cancelButton.prop('disabled', false);
        } else {
            runButton.prop('disabled', false);
            cancelButton.prop('disabled', true);
        }

    } else {
        console.warn(`找不到 Task ID 為 ${taskId} 的 UI 元素`);
    }
}

function markTaskAsFinished(taskId, status, sessionId) {
    const taskRow = $(`.task-row[data-task-id="${taskId}"]`);
    if (taskRow.length) {
        // 如果提供了sessionId，存儲在行元素上
        if (sessionId) {
            taskRow.attr('data-session-id', sessionId);
        }

        // 例如：改變樣式，禁用按鈕等
        taskRow.removeClass('task-running').addClass('task-finished'); // 移除運行中樣式
        // 確保最終狀態的 UI 被正確設置 (特別是進度條和按鈕)
        const finalProgress = (status === 'COMPLETED' || status === 'FAILED' || status === 'CANCELLED') ? 100 : 0;
        updateTaskUI(taskId, finalProgress, status, null, null, null, sessionId); // 使用 null 表示不更新這些字段

        // 任務完成後禁用取消按鈕，啟用執行按鈕
        taskRow.find('.run-task-btn').prop('disabled', false);
        taskRow.find('.cancel-task-btn').prop('disabled', true);

        // 可以添加視覺提示，例如閃爍或短暫高亮
        taskRow.addClass('table-success'); // 假設使用 Bootstrap
        setTimeout(() => {
            taskRow.removeClass('table-success');
        }, 2000);
    }
}

// --- 任務管理功能 ---
// 加載任務列表
function loadTasks() {
    console.log('開始載入任務列表...');
    $.ajax({
        url: '/api/tasks',
        method: 'GET',
        success: function (response) {
            console.log('任務列表API響應：', response);

            // 檢查響應結構
            let taskList = [];
            if (response.data) {
                // 正確的響應結構：{ "success": true, "message": "...", "data": [...] }
                taskList = response.data;
                console.log('從response.data獲取任務列表，數量：', taskList.length);
            } else if (Array.isArray(response)) {
                // 兼容其他可能的響應結構
                taskList = response;
                console.log('從response數組獲取任務列表，數量：', taskList.length);
            } else {
                console.error('無法識別的響應結構', response);
            }

            // 保存到全局變量
            tasks = taskList;

            // 先判斷是否有任務
            if (tasks.length > 0) {
                // 有任務時隱藏提示框
                $('#no-tasks-alert').hide();
                renderTasksTable(tasks);
            } else {
                // 無任務時顯示提示框並渲染空表格
                $('#no-tasks-alert').show();
                renderTasksTable([]);
            }
        },
        error: function (xhr, status, error) {
            console.error('加載任務列表失敗:', error, xhr.responseText);

            // API調用失敗時，仍顯示暫無任務的友好提示
            $('#no-tasks-alert').show();

            // 顯示空的任務表格，以便用戶仍可以新增任務
            renderTasksTable([]);
        }
    });
}

// 加載爬蟲列表 (用於任務編輯)
function loadCrawlers() {
    $.ajax({
        url: '/api/crawlers',
        method: 'GET',
        success: function (response) {
            crawlers = response.data || [];
            // 修正：使用正確的選擇器 ID 'crawler-id'
            const select = $('#crawler-id');
            select.find('option:not(:first)').remove(); // 保留第一個選項 (請選擇...)

            if (crawlers.length === 0) {
                console.warn('爬蟲列表為空，請先創建爬蟲');
                // 添加一個禁用的選項提示用戶
                select.append(`<option value="" disabled>爬蟲列表為空，請先創建爬蟲</option>`);
            } else {
                crawlers.forEach(crawler => {
                    select.append(`<option value="${crawler.id}">${escapeHtml(crawler.name || crawler.crawler_name)}</option>`);
                });
            }
        },
        error: function (xhr, status, error) {
            console.error('加載爬蟲列表失敗:', error);
            // 在錯誤情況下顯示警告訊息
            const select = $('#crawler-id'); // 修正：使用正確的選擇器 ID
            select.find('option:not(:first)').remove();
            select.append(`<option value="" disabled>加載爬蟲列表失敗</option>`);
            displayAlert('warning', '加載爬蟲列表失敗: ' + (xhr.responseJSON?.message || error), true);
        }
    });
}

// 渲染任務表格
function renderTasksTable(tasks) {
    console.log('開始渲染任務表格，任務數量:', tasks.length);
    if (tasks.length > 0) {
        console.log('第一個任務樣本:', tasks[0]);
    }

    const tableBody = $('#tasks-table-body');
    tableBody.empty();

    if (tasks.length === 0) {
        tableBody.append('<tr><td colspan="9" class="text-center">暫無任務，請點擊「新增任務」按鈕添加。</td></tr>');
        return;
    }

    tasks.forEach(task => {
        // 兼容不同的字段命名
        const taskStatus = task.status || task.task_status || 'UNKNOWN';
        const taskType = task.type || 'manual';
        const taskName = task.task_name || task.name || `任務 ${task.id}`;
        const cronExpression = task.cron_expression || '';

        console.log(`渲染任務: ID=${task.id}, 名稱=${taskName}, 狀態=${taskStatus}`);

        // 根據狀態設置徽章樣式
        let statusBadgeClass = 'badge bg-secondary'; // 默認
        if (taskStatus === 'RUNNING') {
            statusBadgeClass = 'badge bg-info';
        } else if (taskStatus === 'COMPLETED') {
            statusBadgeClass = 'badge bg-success';
        } else if (taskStatus === 'FAILED' || taskStatus === 'CANCELLED') {
            statusBadgeClass = 'badge bg-danger';
        } else if (taskStatus === 'PENDING') {
            statusBadgeClass = 'badge bg-warning';
        }

        // 獲取爬蟲名稱
        const crawler = crawlers.find(c => c.id === task.crawler_id);
        const crawlerName = crawler ? (crawler.name || crawler.crawler_name) : `(ID: ${task.crawler_id})`;

        // 根據類型和是否正在運行來決定按鈕狀態
        const isRunning = taskStatus === 'RUNNING';
        const runButtonDisabled = isRunning ? 'disabled' : '';
        const cancelButtonDisabled = !isRunning ? 'disabled' : '';

        // 格式化執行時間
        const lastRunTime = task.last_run_at || task.last_run_time || '-';
        const formattedLastRunTime = lastRunTime !== '-' ? new Date(lastRunTime).toLocaleString() : '-';
        const nextRunTime = task.next_run_time ? new Date(task.next_run_time).toLocaleString() : '-';
        const scheduleDisplay = cronExpression || (taskType === 'manual' ? '手動執行' : '-');

        const row = `
            <tr class="task-row" data-task-id="${task.id}" data-crawler-id="${task.crawler_id}">
                <td>${task.id}</td>
                <td>${escapeHtml(taskName)}</td>
                <td>${escapeHtml(crawlerName)}</td>
                <td>${taskType === 'auto' ? '自動' : '手動'}</td>
                <td>${escapeHtml(scheduleDisplay)}</td>
                <td><span class="task-status-badge ${statusBadgeClass}">${taskStatus}</span></td>
                <td>
                    <div class="progress" style="height: 20px;">
                        <div class="progress-bar" role="progressbar" style="width: 0%;" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">0%</div>
                    </div>
                    <div class="d-flex justify-content-between mt-1">
                        <small class="task-scrape-phase">-</small>
                        <small class="task-articles-count">-</small>
                    </div>
                </td>
                <td>${formattedLastRunTime}</td>
                <td>
                    <div class="btn-group" role="group">
                        <button class="btn btn-sm btn-success run-task-btn" data-task-id="${task.id}" data-task-type="${taskType}" ${runButtonDisabled}>
                            <i class="bi bi-play-fill"></i> 執行
                        </button>
                        <button class="btn btn-sm btn-danger cancel-task-btn" data-task-id="${task.id}" ${cancelButtonDisabled}>
                            <i class="bi bi-stop-fill"></i> 取消
                        </button>
                        <button class="btn btn-sm btn-primary edit-task-btn" data-id="${task.id}">
                            <i class="bi bi-pencil"></i> 編輯
                        </button>
                        <button class="btn btn-sm btn-danger delete-task-btn" data-id="${task.id}">
                            <i class="bi bi-trash"></i> 刪除
                        </button>
                    </div>
                </td>
            </tr>
        `;

        tableBody.append(row);
    });

    console.log('任務表格渲染完成');
}

// 顯示任務新增/編輯模態框
function showTaskModal(taskId) {
    resetTaskForm(); // 清空表單

    // 每次開啟模態框時重新加載爬蟲列表，確保列表是最新的
    loadCrawlers();

    if (taskId) {
        // 編輯模式
        const task = tasks.find(t => t.id === taskId);
        if (!task) {
            console.error('找不到ID為', taskId, '的任務');
            return;
        }

        $('#task-modal-label').text('編輯任務');
        $('#task-form').data('is-edit', true);
        $('#task-form').data('task-id', task.id);
        $('#task-name').val(task.task_name);
        $('#crawler-id').val(task.crawler_id);

        // 設置任務類型單選按鈕
        $(`input[name="taskType"][value="${task.type}"]`).prop('checked', true);

        // 從task_args中讀取ai_only
        $('#ai-only').prop('checked', task.task_args?.ai_only || false);
        $('#task-remark').val(task.remark || '');

        // 根據任務類型更新排程字段
        updateScheduleFields(task.type, task.cron_expression);

        // 設置高級參數
        if (task.task_args) {
            setAdvancedParams(task.task_args);
        }
    } else {
        // 新增模式
        $('#task-modal-label').text('新增任務');
        $('#task-form').data('is-edit', false);
        $('#task-form').data('task-id', '');
        // 設置預設參數
        setAdvancedParams(null);
    }

    $('#task-modal').modal('show');
}

// 設置高級參數
function setAdvancedParams(taskArgs) {
    // 如果沒有傳入參數，則使用預設值
    const args = taskArgs || {
        max_pages: 10,
        num_articles: 10,
        max_retries: 3,
        retry_delay: 2.0,
        timeout: 10,
        min_keywords: 3,
        scrape_mode: 'full_scrape',
        save_to_csv: false,
        csv_file_prefix: '',
        save_partial_results_on_cancel: true
    };

    // 填充表單
    $('#max-pages').val(args.max_pages);
    $('#num-articles').val(args.num_articles);
    $('#max-retries').val(args.max_retries);
    $('#retry-delay').val(args.retry_delay);
    $('#timeout').val(args.timeout);
    $('#min-keywords').val(args.min_keywords);
    $('#scrape-mode').val(args.scrape_mode);
    $('#save-to-csv').prop('checked', args.save_to_csv);
    $('#csv-file-prefix').val(args.csv_file_prefix || '');
    $('#save-partial-results').prop('checked', args.save_partial_results_on_cancel);

    // 根據儲存到CSV的設定顯示/隱藏前綴欄位
    if (args.save_to_csv) {
        $('#csv-prefix-container').removeClass('d-none');
    } else {
        $('#csv-prefix-container').addClass('d-none');
    }
}

// 重置表單
function resetTaskForm() {
    $('#task-id').val('');
    $('#task-name').val('');
    $('#crawler-id').val('');
    $('#task-type').val('');
    $('#ai-only').prop('checked', false);
    $('#task-remark').val('');
    $('#schedule-container').empty();
}

// 保存任務
function saveTask() {
    // 獲取表單數據
    const isEdit = $('#task-form').data('is-edit') === true;
    const taskId = $('#task-form').data('task-id');
    const taskName = $('#task-name').val().trim();
    const crawlerId = $('#crawler-id').val();
    const taskType = $('#task-type').val();
    const taskRemark = $('#task-remark').val().trim();

    // 獲取高級參數
    const maxPages = parseInt($('#max-pages').val() || 10);
    const numArticles = parseInt($('#num-articles').val() || 10);
    const maxRetries = parseInt($('#max-retries').val() || 3);
    const retryDelay = parseFloat($('#retry-delay').val() || 2.0);
    const timeout = parseInt($('#timeout').val() || 10);
    const minKeywords = parseInt($('#min-keywords').val() || 3);
    const aiOnly = $('#ai-only').is(':checked');
    const saveToCsv = $('#save-to-csv').is(':checked');
    const csvFilePrefix = $('#csv-file-prefix').val().trim();
    const scrapeMode = $('#scrape-mode').val();
    const savePartialResults = $('#save-partial-results').is(':checked');

    // 確保必填欄位為正確類型
    const taskData = {
        task_name: taskName, // 確保設置 task_name 作為主要鍵
        crawler_id: parseInt(crawlerId),
        is_auto: taskType === 'auto', // 直接設置為布爾值，而不是字符串'auto'/'manual'
        notes: taskRemark
    };

    // 添加高級參數
    taskData.task_args = {
        max_pages: maxPages,
        num_articles: numArticles,
        max_retries: maxRetries,
        retry_delay: retryDelay,
        timeout: timeout,
        min_keywords: minKeywords,
        scrape_mode: scrapeMode,
        ai_only: aiOnly,
        save_to_csv: saveToCsv,
        save_to_database: true, // 預設總是保存到資料庫
        csv_file_prefix: csvFilePrefix,
        save_partial_results_on_cancel: savePartialResults,
        save_partial_to_database: savePartialResults,
        is_test: false, // 非測試模式
        article_links: [], // 初始為空，手動任務執行時會填充
        get_links_by_task_id: false, // 確保此屬性為布爾值false而非缺失
        max_cancel_wait: 30,
        cancel_interrupt_interval: 5,
        cancel_timeout: 60
    };

    // 如果是自動執行任務，添加 cron_expression
    if (taskType === 'auto') {
        taskData.cron_expression = $('#cron-expression').val().trim();
    }

    // 設置 scrape_phase 初始值
    taskData.scrape_phase = 'init';

    // 設置 is_active 為 true
    taskData.is_active = true;

    // 輸出表單數據到控制台以便調試
    console.log('準備保存的任務數據:', taskData);

    // 表單驗證
    let errorMessages = [];

    if (!taskData.task_name) {
        errorMessages.push('請填寫任務名稱');
    }

    if (!taskData.crawler_id || isNaN(taskData.crawler_id)) {
        errorMessages.push('請選擇爬蟲');
    }

    // 如果是自動執行，需要添加排程設定
    if (taskData.is_auto) {
        if (!taskData.cron_expression) {
            errorMessages.push('自動執行的任務需要填寫排程表達式');
        }
    }

    if (errorMessages.length > 0) {
        displayAlert('warning', errorMessages.join('<br>'), true);
        return;
    }

    // 發送 AJAX 請求
    const apiUrl = isEdit ? `/api/tasks/${taskId}` : '/api/tasks';
    console.log(`發送${isEdit ? '更新' : '創建'}請求到: ${apiUrl}`);

    $.ajax({
        url: apiUrl,
        method: isEdit ? 'PUT' : 'POST',
        contentType: 'application/json',
        data: JSON.stringify(taskData),
        success: function (response) {
            console.log('保存任務成功，API響應:', response);
            // 關閉模態框並刷新列表
            $('#task-modal').modal('hide');
            displayAlert('success', isEdit ? '任務更新成功' : '任務新增成功');
            loadTasks(); // 確保在成功後立即調用任務列表刷新
        },
        error: function (xhr, status, error) {
            console.error('保存任務失敗:', {
                status: xhr.status,
                statusText: xhr.statusText,
                responseText: xhr.responseText,
                error: error
            });

            // 嘗試從響應中提取更詳細的錯誤消息
            let errorMessage = '保存失敗';

            try {
                // 首先檢查 responseJSON
                if (xhr.responseJSON) {
                    if (xhr.responseJSON.message) {
                        errorMessage += ': ' + xhr.responseJSON.message;
                    } else if (xhr.responseJSON.error) {
                        errorMessage += ': ' + xhr.responseJSON.error;
                    } else if (xhr.responseJSON.errors && Array.isArray(xhr.responseJSON.errors)) {
                        // 處理可能的錯誤數組
                        errorMessage += ': ' + xhr.responseJSON.errors.join('; ');
                    } else if (typeof xhr.responseJSON === 'object') {
                        // 遍歷對象中的所有錯誤信息
                        const errorDetails = [];
                        for (const key in xhr.responseJSON) {
                            if (key !== 'success') { // 排除success字段
                                errorDetails.push(`${key}: ${xhr.responseJSON[key]}`);
                            }
                        }
                        if (errorDetails.length > 0) {
                            errorMessage += ': ' + errorDetails.join('; ');
                        }
                    }
                }
                // 如果responseJSON沒有有用信息，嘗試解析responseText
                else if (xhr.responseText) {
                    try {
                        const errorObj = JSON.parse(xhr.responseText);
                        if (errorObj.message) {
                            errorMessage += ': ' + errorObj.message;
                        } else if (errorObj.error) {
                            errorMessage += ': ' + errorObj.error;
                        } else if (errorObj.errors && Array.isArray(errorObj.errors)) {
                            errorMessage += ': ' + errorObj.errors.join('; ');
                        } else {
                            errorMessage += ': ' + JSON.stringify(errorObj);
                        }
                    } catch (e) {
                        // 如果解析失敗，直接使用responseText
                        errorMessage += ': ' + xhr.responseText;
                    }
                } else if (xhr.status) {
                    // 添加HTTP狀態碼信息
                    errorMessage += ` (HTTP ${xhr.status}: ${xhr.statusText || error})`;
                } else {
                    errorMessage += ': ' + error;
                }
            } catch (e) {
                console.error('解析錯誤響應時出錯:', e);
                errorMessage += `: ${error || '未知錯誤'}`;
            }

            displayAlert('danger', errorMessage, true);
        }
    });
}

// 刪除任務
function deleteTask(taskId) {
    if (!taskId) return;

    $.ajax({
        url: `/api/tasks/${taskId}`,
        method: 'DELETE',
        success: function (response) {
            $('#delete-task-modal').modal('hide');
            displayAlert('success', '任務已刪除');
            loadTasks();
        },
        error: function (xhr, status, error) {
            $('#delete-task-modal').modal('hide');
            console.error('刪除任務失敗:', error);
            displayAlert('danger', '刪除失敗: ' + (xhr.responseJSON?.message || error));
        }
    });
}

// --- 自動任務執行 ---
function runAutoTask(taskId, button) {
    console.log(`開始執行自動任務: ${taskId}`);
    button.prop('disabled', true).text('啟動中...'); // 禁用按鈕並顯示提示

    $.ajax({
        url: `/api/tasks/${taskId}/run_manual`,
        method: 'POST',
        success: function (response) {
            console.log('自動任務啟動響應:', response);
            if (response.success) {
                // API 快速返回 202 Accepted
                // 後續進度將通過 WebSocket 更新

                // 檢查是否返回了會話ID
                const sessionId = response.session_id;
                const roomName = response.room || `task_${taskId}`;

                // 如果 WebSocket 已連接，加入相應房間
                if (socket && socket.connected) {
                    console.log(`啟動後加入房間: ${roomName}`);
                    socket.emit('join_room', { 'room': roomName });

                    // 保存會話ID到按鈕或行元素上，以便後續使用
                    if (sessionId) {
                        const taskRow = $(`.task-row[data-task-id="${taskId}"]`);
                        if (taskRow.length) {
                            taskRow.attr('data-session-id', sessionId);
                        }
                    }
                }
            } else {
                button.prop('disabled', false).text('執行');
                displayAlert('danger', '任務啟動失敗: ' + response.message);
            }
        },
        error: function (xhr, status, error) {
            console.error('任務啟動失敗:', error);
            button.prop('disabled', false).text('執行');
            displayAlert('danger', '任務啟動失敗: ' + (xhr.responseJSON?.message || error));
        }
    });
}

// 取消任務
function cancelTask(taskId) {
    if (!taskId) return;

    $.ajax({
        url: `/api/tasks/${taskId}/cancel`,
        method: 'POST',
        success: function (response) {
            console.log('取消任務響應:', response);
            if (!response.success) {
                displayAlert('warning', '取消任務失敗: ' + response.message);
            }
            // 成功取消後，WebSocket 將更新任務狀態
        },
        error: function (xhr, status, error) {
            console.error('取消任務失敗:', error);
            displayAlert('danger', '取消任務失敗: ' + (xhr.responseJSON?.message || error));
        }
    });
}

// --- 手動爬取功能 ---
// 開始手動爬取連結
function startManualLinksFetch(taskId) {
    currentTaskId = taskId; // 設置當前操作的任務ID

    // 發送請求開始抓取連結
    $.ajax({
        url: `/api/tasks/manual/collect-links`,
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            crawler_id: parseInt($('.task-row[data-task-id="' + taskId + '"]').data('crawler-id') || 0),
            task_name: "手動抓取連結_" + new Date().toISOString()
        }),
        success: function (response) {
            console.log('抓取連結請求響應:', response);
            if (response.success) {
                // 顯示加載中的提示
                displayAlert('info', '正在抓取連結，請等待...');

                // 確保加入對應的 room (如果 WebSocket 已連接)
                if (socket && socket.connected) {
                    const roomName = `task_${taskId}`;
                    console.log(`抓取連結後加入房間: ${roomName}`);
                    socket.emit('join_room', { 'room': roomName });
                }
            } else {
                displayAlert('danger', '抓取連結失敗: ' + response.message);
            }
        },
        error: function (xhr, status, error) {
            console.error('抓取連結請求失敗:', error);
            displayAlert('danger', '抓取連結請求失敗: ' + (xhr.responseJSON?.message || error));
        }
    });
}

// 加載已抓取的連結
function loadFetchedLinks(taskId) {
    $.ajax({
        url: `/api/tasks/${taskId}/links`,
        method: 'GET',
        success: function (response) {
            if (response.success) {
                fetchedLinks = response.data || [];
                // 顯示連結選擇模態框
                showLinksModal(fetchedLinks);
            } else {
                displayAlert('danger', '加載連結失敗: ' + response.message);
            }
        },
        error: function (xhr, status, error) {
            console.error('加載連結失敗:', error);
            displayAlert('danger', '加載連結失敗: ' + (xhr.responseJSON?.message || error));
        }
    });
}

// 顯示連結選擇模態框
function showLinksModal(links) {
    const tableBody = $('#manual-links-table-body');
    tableBody.empty();

    if (links.length === 0) {
        tableBody.append('<tr><td colspan="4" class="text-center">暫無連結</td></tr>');
    } else {
        links.forEach((link, index) => {
            const row = `
                <tr>
                    <td>
                        <div class="form-check">
                            <input class="form-check-input link-checkbox" type="checkbox" value="${index}" id="link-${index}">
                        </div>
                    </td>
                    <td>${escapeHtml(link.title || '無標題')}</td>
                    <td><a href="${escapeHtml(link.url)}" target="_blank">${escapeHtml(link.url)}</a></td>
                    <td>${link.published_date ? new Date(link.published_date).toLocaleString() : '-'}</td>
                </tr>
            `;
            tableBody.append(row);
        });
    }

    // 重置選擇計數
    updateSelectedLinksCount();

    // 顯示模態框
    $('#manual-links-modal').modal('show');
}

// 更新已選擇的連結數量
function updateSelectedLinksCount() {
    const count = $('.link-checkbox:checked').length;
    $('#selected-links-count').text(count);
}

// 獲取選中的連結
function getSelectedLinks() {
    const selectedIndices = [];
    $('.link-checkbox:checked').each(function () {
        selectedIndices.push(parseInt($(this).val()));
    });

    return selectedIndices.map(index => fetchedLinks[index]);
}

// 開始爬取選中的文章
function startFetchArticles(taskId, selectedLinks) {
    if (!taskId || !selectedLinks.length) return;

    // 關閉連結選擇模態框
    $('#manual-links-modal').modal('hide');

    // 準備要發送的數據
    const data = {
        task_args: {
            article_links: selectedLinks.map(link => link.url)
        }
    };

    console.log('準備發送抓取文章請求:', data);

    // 發送請求開始爬取文章
    $.ajax({
        url: `/api/tasks/manual/${taskId}/fetch-content`,
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function (response) {
            console.log('爬取文章請求響應:', response);
            if (response.success) {
                displayAlert('info', '正在爬取文章，請等待...');

                // 確保 WebSocket 已連接
                if (socket && socket.connected) {
                    const roomName = `task_${taskId}`;
                    console.log(`爬取文章後加入房間: ${roomName}`);
                    socket.emit('join_room', { 'room': roomName });
                }
            } else {
                displayAlert('danger', '爬取文章失敗: ' + response.message);
            }
        },
        error: function (xhr, status, error) {
            console.error('爬取文章請求失敗:', error);
            displayAlert('danger', '爬取文章請求失敗: ' + (xhr.responseJSON?.message || error));
        }
    });
}

// 顯示提示訊息
function displayAlert(type, message, inModal = false) {
    const alertHtml = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;

    if (inModal) {
        // 在模態框中顯示提示
        const modalBody = $('.modal-body').first();
        modalBody.prepend(alertHtml);
    } else {
        // 在頁面頂部顯示提示
        const alertContainer = $('#alert-container');
        if (alertContainer.length === 0) {
            // 如果不存在，則創建一個
            $('main.container').prepend('<div id="alert-container"></div>');
        }
        $('#alert-container').html(alertHtml);

        // 5秒後自動消失
        setTimeout(() => {
            $('.alert').alert('close');
        }, 5000);
    }
}

// HTML 轉義，防止 XSS
function escapeHtml(unsafe) {
    if (unsafe === null || unsafe === undefined) return '';
    return unsafe
        .toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// 根據任務類型更新排程字段
function updateScheduleFields(type, cronExpression = '') {
    const container = $('#schedule-container');
    container.empty();

    if (type === 'auto') {
        container.append(`
            <label for="cron-expression" class="form-label">排程 (Cron 表達式)</label>
            <input type="text" class="form-control" id="cron-expression" name="cron_expression" 
                   value="${escapeHtml(cronExpression)}" required
                   placeholder="例如: 0 0 * * * (每天凌晨12點)">
            <div class="form-text">
                Cron 表達式格式: 分鐘 小時 日期 月份 星期 (0-59 0-23 1-31 1-12 0-7)
            </div>
        `);
    }
}
