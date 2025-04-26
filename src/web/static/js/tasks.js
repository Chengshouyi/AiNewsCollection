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

    // --- 修改：先加載爬蟲列表，成功後再加載任務列表 ---
    loadCrawlers(function () {
        // 爬蟲加載成功後的回調
        console.log("爬蟲列表加載完成，現在開始加載任務列表...");
        loadTasks(); // 在這裡調用 loadTasks
    });
    // --- 修改結束 ---

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
        if (!taskId) return;

        // 不管是什麼類型的任務，都直接執行
        executeTask(taskId, button);
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

    // 綁定爬取模式變更事件
    $('#scrape-mode').change(handleScrapeModeChange);

    // --- 新增：綁定是否限制文章數量 Checkbox 的變更事件 --- 
    $('#is-limit-num-articles').change(toggleNumArticlesInputVisibility);
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
    const taskRow = $(`.task-row[data-task-id="${taskId}"]`);
    if (taskRow.length) {
        // 如果提供了會話ID，將其存儲在行元素上，以便後續使用
        if (sessionId) {
            taskRow.attr('data-session-id', sessionId);
        }

        // 更新進度條
        const progressBar = taskRow.find('.progress .progress-bar');
        if (progressBar.length) {
            // 設置進度百分比
            progressBar.css('width', progress + '%').text(progress + '%');

            // 根據狀態改變進度條顏色
            progressBar.removeClass('bg-success bg-warning bg-danger bg-info bg-secondary');

            // 將狀態轉為大寫以匹配枚舉值
            const upperStatus = status ? status.toUpperCase() : '';

            if (upperStatus === 'COMPLETED') {
                progressBar.addClass('bg-success');
            } else if (upperStatus === 'RUNNING') {
                progressBar.addClass('bg-info');
            } else if (upperStatus === 'FAILED' || upperStatus === 'CANCELLED') {
                progressBar.addClass('bg-danger');
            } else if (upperStatus === 'PENDING') {
                progressBar.addClass('bg-warning');
            } else {
                progressBar.addClass('bg-secondary'); // 其他狀態
            }

            // 添加調試日誌
            // console.log(`更新任務 ${taskId} 進度條: ${progress}%, 狀態: ${status}, 添加的類: bg-${status.toLowerCase() === 'completed' ? 'success' : status.toLowerCase() === 'running' ? 'info' : 'secondary'}`);
        }

        // 更新狀態文本
        const statusBadge = taskRow.find('.task-status-badge');
        if (statusBadge.length) {
            statusBadge.text(status);
            // 根據狀態改變徽章顏色 - **只使用 bg-* 類別**
            statusBadge.removeClass('bg-success bg-warning bg-danger bg-info bg-secondary badge-success badge-warning badge-danger badge-info badge-secondary'); // 移除所有舊的顏色類別

            const upperStatus = status ? status.toUpperCase() : '';

            if (upperStatus === 'COMPLETED') {
                statusBadge.addClass('bg-success');
            } else if (upperStatus === 'RUNNING') {
                statusBadge.addClass('bg-info');
            } else if (upperStatus === 'FAILED' || upperStatus === 'CANCELLED') {
                statusBadge.addClass('bg-danger');
            } else if (upperStatus === 'PENDING') {
                statusBadge.addClass('bg-warning');
            } else {
                statusBadge.addClass('bg-secondary'); // 其他狀態
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

        // 使用大小寫不敏感的比較
        const statusLower = status ? status.toLowerCase() : '';
        if (statusLower === 'running') {
            runButton.prop('disabled', true).text('啟動中...');
            cancelButton.prop('disabled', false);
        } else {
            runButton.prop('disabled', false).text('執行');
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

        // 任務完成後禁用取消按鈕，啟用執行按鈕，並恢復按鈕文字
        taskRow.find('.run-task-btn').prop('disabled', false).text('執行');  // 添加 .text('執行') 重置按鈕文字
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
                $('#no-tasks-alert').addClass('d-none');
                renderTasksTable(tasks);
            } else {
                // 無任務時顯示提示框並渲染空表格
                $('#no-tasks-alert').removeClass('d-none');
                renderTasksTable([]);
            }
        },
        error: function (xhr, status, error) {
            console.error('加載任務列表失敗:', error, xhr.responseText);

            // API調用失敗時，仍顯示暫無任務的友好提示
            $('#no-tasks-alert').removeClass('d-none');

            // 顯示空的任務表格，以便用戶仍可以新增任務
            renderTasksTable([]);
        }
    });
}

// 加載爬蟲列表 (用於任務編輯)
function loadCrawlers(callback) {
    $.ajax({
        url: '/api/crawlers',
        method: 'GET',
        success: function (response) {
            crawlers = response.data || [];
            const select = $('#crawler-id');
            select.find('option:not(:first)').remove(); // 保留第一個選項 (請選擇...)

            if (crawlers.length === 0) {
                console.warn('爬蟲列表為空，請先創建爬蟲');
                select.append(`<option value="" disabled>爬蟲列表為空，請先創建爬蟲</option>`);
            } else {
                crawlers.forEach(crawler => {
                    // 確保使用正確的 crawler id 作為 value
                    select.append(`<option value="${crawler.id}">${escapeHtml(crawler.name || crawler.crawler_name)}</option>`);
                });
            }
            // 如果提供了回調函數，則執行它
            if (typeof callback === 'function') {
                callback();
            }
        },
        error: function (xhr, status, error) {
            console.error('加載爬蟲列表失敗:', error);
            const select = $('#crawler-id'); // 修正：使用正確的選擇器 ID
            select.find('option:not(:first)').remove();
            select.append(`<option value="" disabled>加載爬蟲列表失敗</option>`);
            displayAlert('warning', '加載爬蟲列表失敗: ' + (xhr.responseJSON?.message || error), true);
            // 錯誤情況下也可以執行回調
            if (typeof callback === 'function') {
                callback();
            }
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
        const taskType = task.is_auto ? 'auto' : 'manual';
        const taskName = task.task_name || task.name || `任務 ${task.id}`;
        const cronExpression = task.cron_expression || '';

        console.log(`渲染任務: ID=${task.id}, 名稱=${taskName}, 狀態=${taskStatus}, 類型=${taskType}`);

        // 根據狀態設置徽章樣式 - **只使用 bg-* 類別**
        let statusBadgeClass = 'badge bg-secondary'; // 默認 badge 基礎樣式 + 顏色
        const upperStatus = taskStatus ? taskStatus.toUpperCase() : '';

        if (upperStatus === 'RUNNING') {
            statusBadgeClass = 'badge bg-info';
        } else if (upperStatus === 'COMPLETED') {
            statusBadgeClass = 'badge bg-success';
        } else if (upperStatus === 'FAILED' || upperStatus === 'CANCELLED') {
            statusBadgeClass = 'badge bg-danger';
        } else if (upperStatus === 'PENDING') {
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

    if (taskId) {
        // 編輯模式
        const task = tasks.find(t => t.id === taskId);
        if (!task) {
            console.error('找不到ID為', taskId, '的任務');
            displayAlert('danger', `找不到任務 ID: ${taskId}`);
            return;
        }

        console.log("找到的任務:", JSON.parse(JSON.stringify(task)));

        $('#task-modal-label').text('編輯任務');
        $('#task-form').data('is-edit', true);
        $('#task-form').data('task-id', task.id);
        $('#task-name').val(task.task_name);

        const taskType = task.is_auto ? 'auto' : 'manual';
        $('#task-type').val(taskType);
        if ($('#task-type').val() !== taskType) {
            console.warn(`設置任務類型下拉選單值為 "${taskType}" 失敗。當前值: ${$('#task-type').val()}`);
        }

        $('#ai-only').prop('checked', task.task_args?.ai_only || false);
        $('#task-remark').val(task.notes || '');

        updateScheduleFields(taskType, task.cron_expression);

        console.log("任務參數 (task_args):", JSON.parse(JSON.stringify(task.task_args)));
        if (task.task_args) {
            console.log("準備調用 setAdvancedParams，傳入:", task.task_args);
            setAdvancedParams(task.task_args); // 會調用 toggleNumArticlesInputVisibility
            console.log("setAdvancedParams 調用後，檢查表單值:");
            console.log("Max Pages:", $('#max-pages').val());
            console.log("Num Articles:", $('#num-articles').val());
            console.log("Limit Num Articles Checkbox:", $('#is-limit-num-articles').is(':checked'));
        } else {
            console.warn("任務參數 (task_args) 不存在，使用預設值。");
            setAdvancedParams(null); // 會調用 toggleNumArticlesInputVisibility
        }

        loadCrawlers(function () {
            if (task.crawler_id !== null && task.crawler_id !== undefined) {
                const crawlerSelect = $('#crawler-id');
                crawlerSelect.val(task.crawler_id);
                if (crawlerSelect.val() != task.crawler_id) {
                    console.warn(`設置爬蟲 ID ${task.crawler_id} 失敗...`);
                }
                crawlerSelect.prop('disabled', true);
            } else {
                console.warn("任務數據中缺少有效的 crawler_id");
                $('#crawler-id').prop('disabled', true);
            }
            // 編輯模式下根據初始 scrape-mode 設置 UI
            handleScrapeModeChange();
            toggleContentOnlyLinksInput();
        });

    } else {
        // 新增模式
        $('#task-modal-label').text('新增任務');
        $('#task-form').data('is-edit', false);
        $('#task-form').data('task-id', '');
        setAdvancedParams(null); // 會設置預設值並調用 toggleNumArticlesInputVisibility
        loadCrawlers();
        $('#task-type').val('manual');
        updateScheduleFields('manual');
        // 新增模式下根據初始 scrape-mode 設置 UI
        handleScrapeModeChange();
        toggleContentOnlyLinksInput();
    }

    $('#task-modal').modal('show');
}

// 設置高級參數
function setAdvancedParams(taskArgs) {
    console.log("setAdvancedParams 接收到的參數:", JSON.parse(JSON.stringify(taskArgs)));
    // 如果沒有傳入參數，則使用預設值
    const args = taskArgs || {
        max_pages: 10,
        num_articles: 10,
        is_limit_num_articles: false, // 新增預設值
        max_retries: 3,
        retry_delay: 2.0,
        timeout: 10,
        min_keywords: 3,
        scrape_mode: 'full_scrape',
        save_to_csv: false,
        csv_file_prefix: '',
        save_partial_results_on_cancel: true,
        ai_only: false
    };
    console.log("setAdvancedParams 實際使用的參數 (args):", args);

    // 填充表單 (請確保以下 ID 與 HTML 一致)
    $('#max-pages').val(args.max_pages);
    $('#num-articles').val(args.num_articles); // 填充數量值
    $('#is-limit-num-articles').prop('checked', args.is_limit_num_articles || false); // 設置 Checkbox
    $('#max-retries').val(args.max_retries);
    $('#retry-delay').val(args.retry_delay);
    $('#timeout').val(args.timeout);
    $('#min-keywords').val(args.min_keywords);
    $('#scrape-mode').val(args.scrape_mode);
    $('#save-to-csv').prop('checked', args.save_to_csv || false);
    $('#csv-file-prefix').val(args.csv_file_prefix || '');
    $('#save-partial-results').prop('checked', args.save_partial_results_on_cancel || false);

    // 根據 CSV 勾選框顯示/隱藏前綴欄位
    if ($('#save-to-csv').is(':checked')) {
        $('#csv-prefix-container').removeClass('d-none');
    } else {
        $('#csv-prefix-container').addClass('d-none');
    }

    // 根據 is_limit_num_articles 勾選框顯示/隱藏數量輸入框
    toggleNumArticlesInputVisibility();
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
    $('#crawler-id').prop('disabled', false);
    console.log("爬蟲選擇已啟用 (表單重置)");

    // 重置高級參數為預設值
    setAdvancedParams(null);

    // 確保重置後 scrape-mode 相關的 UI 正確 (因為 setAdvancedParams 會設置 scrape-mode)
    handleScrapeModeChange();
    // 確保 content_only 的容器也隱藏
    toggleContentOnlyLinksInput();
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
    const isLimitNumArticles = $('#is-limit-num-articles').is(':checked'); // 讀取 Checkbox
    const numArticles = parseInt($('#num-articles').val() || 10); // 讀取數量 (即使隱藏)
    const maxRetries = parseInt($('#max-retries').val() || 3);
    const retryDelay = parseFloat($('#retry-delay').val() || 2.0);
    const timeout = parseInt($('#timeout').val() || 10);
    const minKeywords = parseInt($('#min-keywords').val() || 3);
    const aiOnly = $('#ai-only').is(':checked');
    const saveToCsv = $('#save-to-csv').is(':checked');
    const csvFilePrefix = $('#csv-file-prefix').val().trim();
    const scrapeMode = $('#scrape-mode').val();
    const savePartialResults = $('#save-partial-results').is(':checked');

    const taskData = {
        task_name: taskName,
        crawler_id: parseInt(crawlerId),
        is_auto: taskType === 'auto',
        notes: taskRemark
    };

    if (isNaN(taskData.crawler_id)) {
        displayAlert('warning', '請選擇有效的爬蟲', true);
        return;
    }
    if (!taskType) {
        displayAlert('warning', '請選擇任務類型', true);
        return;
    }

    // 添加高級參數
    taskData.task_args = {
        max_pages: maxPages,
        is_limit_num_articles: isLimitNumArticles, // 保存 Checkbox 狀態
        num_articles: numArticles, // 保存數量值
        max_retries: maxRetries,
        retry_delay: retryDelay,
        timeout: timeout,
        min_keywords: minKeywords,
        scrape_mode: scrapeMode,
        ai_only: aiOnly,
        save_to_csv: saveToCsv,
        save_to_database: true,
        csv_file_prefix: csvFilePrefix,
        save_partial_results_on_cancel: savePartialResults,
        save_partial_to_database: savePartialResults,
        is_test: false,
        article_links: [],
        get_links_by_task_id: false,
        max_cancel_wait: 30,
        cancel_interrupt_interval: 5,
        cancel_timeout: 60
    };

    // 根據模式和編輯狀態處理 article_links
    if (scrapeMode === 'content_only') {
        if (!isEdit) {
            // 新增模式 + CONTENT_ONLY: 從 textarea 獲取連結
            const linksText = $('#article-links-input').val().trim();
            if (!linksText) {
                displayAlert('warning', '「僅爬取內容」模式下，請在「文章連結」欄位提供至少一個連結。', true);
                return;
            }
            const parsedLinks = linksText.split('\n')
                .map(link => link.trim())
                .filter(link => link !== '');
            if (parsedLinks.length === 0) {
                displayAlert('warning', '請在「文章連結」欄位提供有效的連結。', true);
                return;
            }
            taskData.task_args.article_links = parsedLinks;
            taskData.task_args.get_links_by_task_id = false; // 新增時明確指定不從DB獲取
        } else {
            // 編輯模式 + CONTENT_ONLY: 標記從 DB 獲取連結
            taskData.task_args.article_links = []; // 清空，以防萬一
            taskData.task_args.get_links_by_task_id = true; // 告訴後端需要從DB加載
        }
    } else {
        // 其他模式，確保 article_links 為空且不從 DB 獲取
        taskData.task_args.article_links = [];
        taskData.task_args.get_links_by_task_id = false;
    }

    // 設置 cron_expression
    if (taskData.is_auto) {
        taskData.cron_expression = $('#cron-expression').val().trim();
    } else {
        taskData.cron_expression = null;
    }

    // 設置 scrape_phase 和 is_active
    taskData.scrape_phase = 'init';
    taskData.is_active = true;

    console.log('準備保存的任務數據:', taskData);

    // 表單驗證
    let errorMessages = [];
    if (!taskData.task_name) errorMessages.push('請填寫任務名稱');
    if (isNaN(taskData.crawler_id)) errorMessages.push('請選擇爬蟲');
    if (taskData.is_auto && !taskData.cron_expression) errorMessages.push('自動執行的任務需要填寫排程表達式');
    // 新增驗證：如果勾選了限制數量，則數量必須大於 0
    if (taskData.task_args.is_limit_num_articles && taskData.task_args.num_articles <= 0) {
        errorMessages.push('文章數量必須大於 0');
    }

    if (errorMessages.length > 0) {
        displayAlert('warning', errorMessages.join('<br>'), true);
        return;
    }

    // 發送 AJAX 請求
    const apiUrl = isEdit ? `/api/tasks/${taskId}` : '/api/tasks';
    console.log(`發送${isEdit ? '更新' : '創建'}請求到: ${apiUrl}，數據:`, JSON.stringify(taskData));

    $.ajax({
        url: apiUrl,
        method: isEdit ? 'PUT' : 'POST',
        contentType: 'application/json',
        data: JSON.stringify(taskData),
        success: function (response) {
            console.log('保存任務成功，API響應:', response);

            // 關閉模態框
            $('#task-modal').modal('hide');

            // 將焦點移到「新增任務」按鈕上
            setTimeout(function () {
                $('#add-task-btn').focus();
            }, 100);

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

            // 將焦點移到適當的元素上
            setTimeout(function () {
                $('#add-task-btn').focus();
            }, 100);

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

// --- 執行任務 ---
function executeTask(taskId, button) {
    console.log(`開始執行任務: ${taskId}`);
    button.prop('disabled', true).text('啟動中...'); // 禁用按鈕並顯示提示

    $.ajax({
        url: `/api/tasks/${taskId}/run`,
        method: 'POST',
        success: function (response) {
            console.log('任務啟動響應:', response);
            if (response.success) {
                // API 快速返回 202 Accepted
                // 後續進度將通過 WebSocket 更新

                // 檢查是否返回了會話ID
                const sessionId = response.session_id;
                // --- 修改：始終使用基礎房間名稱 ---
                const baseRoomName = `task_${taskId}`;
                // --- 修改結束 ---

                // 如果 WebSocket 已連接，加入相應房間
                if (socket && socket.connected) {
                    // --- 修改：使用基礎房間名稱加入 ---
                    console.log(`啟動後加入房間: ${baseRoomName}`);
                    socket.emit('join_room', { 'room': baseRoomName });
                    // --- 修改結束 ---

                    // 保存會話ID到按鈕或行元素上，以便後續使用 (這部分邏輯可以保留，以備將來可能需要)
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
        const modalBody = $('#task-modal .modal-body');
        const modalElement = $('#task-modal');

        if (modalBody.length > 0 && modalElement.length > 0) {
            // --- 新增：移除模態框中已存在的提示 --- 
            modalBody.find('.alert').remove();
            // --- 新增結束 ---
            modalBody.prepend(alertHtml);
            // --- 修改：嘗試捲動整個模態框元素 ---
            modalElement.scrollTop(0);
            // --- 修改結束 ---
        } else {
            console.error("找不到 #task-modal 或其 .modal-body 來顯示提示訊息");
            // 作為備用，嘗試顯示在頁面頂部
            displayAlert(type, message, false);
        }
    } else {
        // 在頁面頂部顯示提示
        const alertContainer = $('#alert-container');
        if (alertContainer.length === 0) {
            // 如果不存在，則創建一個
            $('main.container').prepend('<div id="alert-container"></div>');
        }
        $('#alert-container').html(alertHtml);

        // --- 新增：滾動到提示訊息位置 ---
        window.scrollTo({ top: 0, behavior: 'smooth' });
        // --- 新增結束 ---

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
function updateScheduleFields(taskType, cronExpression = '') { // 修改參數名
    const container = $('#schedule-container');
    container.empty();

    if (taskType === 'auto') { // 使用 taskType 判斷
        container.append(`
            <div class="mb-3"> <!-- 添加 mb-3 增加間距 -->
                <label for="cron-expression" class="form-label">排程 (Cron 表達式)</label>
                <input type="text" class="form-control" id="cron-expression" name="cron_expression"
                       value="${escapeHtml(cronExpression)}" required
                       placeholder="例如: 0 0 * * * (每天凌晨12點)">
                <div class="form-text">
                    Cron 表達式格式: 分鐘 小時 日期 月份 星期 (0-59 0-23 1-31 1-12 0-7)
                </div>
            </div>
        `);
    }
}

// 新增：控制 CONTENT_ONLY 連結輸入框的顯示/隱藏
function toggleContentOnlyLinksInput() {
    const scrapeMode = $('#scrape-mode').val();
    const isEdit = $('#task-form').data('is-edit') === true;
    const container = $('#content-only-links-container');
    const inputArea = $('#article-links-input');
    const editNotice = $('#content-only-edit-notice');
    const linksLabel = $('#content-only-links-label');
    const linksFormText = $('#content-only-links-form-text');

    if (scrapeMode === 'content_only') {
        container.removeClass('d-none'); // 顯示容器
        if (isEdit) {
            // 編輯模式：隱藏輸入相關，顯示提示
            linksLabel.addClass('d-none');
            inputArea.addClass('d-none');
            linksFormText.addClass('d-none');
            editNotice.removeClass('d-none');
            inputArea.val(''); // 清空可能存在的輸入
        } else {
            // 新增模式：顯示輸入相關，隱藏提示
            linksLabel.removeClass('d-none');
            inputArea.removeClass('d-none');
            linksFormText.removeClass('d-none');
            editNotice.addClass('d-none');
        }
    } else {
        // 其他模式：隱藏容器即可
        container.addClass('d-none');
        // 確保提示也隱藏 (以防萬一)
        editNotice.addClass('d-none');
        inputArea.val(''); // 清空可能存在的輸入
    }
}

// 新增：控制文章數量輸入框的可見性
function toggleNumArticlesInputVisibility() {
    const isChecked = $('#is-limit-num-articles').is(':checked');
    const numArticlesContainer = $('#num-articles-container');

    if (isChecked) {
        numArticlesContainer.removeClass('d-none');
    } else {
        numArticlesContainer.addClass('d-none');
    }
}

// 新增：處理 scrape-mode 變更時的 UI 更新
function handleScrapeModeChange() {
    const scrapeMode = $('#scrape-mode').val();
    const maxPagesContainer = $('#max-pages').closest('.col-md-6.mb-3');
    // 包含 Checkbox 和 Input 的整體容器
    const limitCheckboxContainer = $('#limit-num-articles-checkbox-container');
    const numArticlesContainer = $('#num-articles-container');
    const aiOnlyContainer = $('#ai-only').closest('.mb-3');

    if (scrapeMode === 'content_only') {
        maxPagesContainer.addClass('d-none');
        limitCheckboxContainer.addClass('d-none');
        numArticlesContainer.addClass('d-none'); // 同時隱藏輸入框本身
        aiOnlyContainer.addClass('d-none');
    } else {
        maxPagesContainer.removeClass('d-none');
        limitCheckboxContainer.removeClass('d-none');
        // 不直接顯示 numArticlesContainer，而是根據 Checkbox 狀態決定
        // numArticlesContainer.removeClass('d-none');
        aiOnlyContainer.removeClass('d-none');
        // 當 scrapeMode 不是 content_only 時，需要根據 Checkbox 決定 Input 的可見性
        toggleNumArticlesInputVisibility();
    }

    // 同步更新 content_only 相關的 UI
    toggleContentOnlyLinksInput();
}
