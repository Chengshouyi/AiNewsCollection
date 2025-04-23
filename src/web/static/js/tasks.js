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
        updateTaskUI(data.task_id, data.progress, data.status, data.scrape_phase, data.message, data.articles_count);
    });

    socket.on('task_finished', function (data) {
        console.log('Task finished:', data);
        markTaskAsFinished(data.task_id, data.status);
        // 可以選擇性地從房間離開，但通常保持連接以接收後續更新（如果有的話）
        // socket.emit('leave_room', {'room': `task_${data.task_id}`});
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
            const roomName = `task_${taskId}`;
            console.log(`加入房間: ${roomName}`);
            socket.emit('join_room', { 'room': roomName });
        }
    });
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

function updateTaskUI(taskId, progress, status, scrapePhase, message, articlesCount) {
    // 實現邏輯：找到對應 task_id 的 UI 元素並更新
    const taskRow = $(`.task-row[data-task-id="${taskId}"]`);
    if (taskRow.length) {
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

function markTaskAsFinished(taskId, status) {
    const taskRow = $(`.task-row[data-task-id="${taskId}"]`);
    if (taskRow.length) {
        // 例如：改變樣式，禁用按鈕等
        taskRow.removeClass('task-running').addClass('task-finished'); // 移除運行中樣式
        // 確保最終狀態的 UI 被正確設置 (特別是進度條和按鈕)
        const finalProgress = (status === 'COMPLETED' || status === 'FAILED' || status === 'CANCELLED') ? 100 : 0;
        updateTaskUI(taskId, finalProgress, status, null, null, null); // 使用 null 表示不更新這些字段

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
    $.ajax({
        url: '/api/tasks',
        method: 'GET',
        success: function (response) {
            tasks = response.data || [];
            renderTasksTable(tasks);
        },
        error: function (xhr, status, error) {
            console.error('加載任務列表失敗:', error);
            displayAlert('danger', '加載任務列表失敗: ' + (xhr.responseJSON?.message || error));
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
            // 更新爬蟲選擇下拉框
            const select = $('#crawler-id');
            select.find('option:not(:first)').remove(); // 保留第一個選項 (請選擇...)

            crawlers.forEach(crawler => {
                select.append(`<option value="${crawler.id}">${escapeHtml(crawler.name)}</option>`);
            });
        },
        error: function (xhr, status, error) {
            console.error('加載爬蟲列表失敗:', error);
        }
    });
}

// 渲染任務表格
function renderTasksTable(tasks) {
    const tableBody = $('#tasks-table-body');
    tableBody.empty();

    if (tasks.length === 0) {
        tableBody.append('<tr><td colspan="9" class="text-center">暫無任務，請點擊「新增任務」按鈕添加。</td></tr>');
        return;
    }

    tasks.forEach(task => {
        // 根據狀態設置徽章樣式
        let statusBadgeClass = 'badge bg-secondary'; // 默認
        if (task.status === 'RUNNING') {
            statusBadgeClass = 'badge bg-info';
        } else if (task.status === 'COMPLETED') {
            statusBadgeClass = 'badge bg-success';
        } else if (task.status === 'FAILED' || task.status === 'CANCELLED') {
            statusBadgeClass = 'badge bg-danger';
        } else if (task.status === 'PENDING') {
            statusBadgeClass = 'badge bg-warning';
        }

        // 獲取爬蟲名稱
        const crawler = crawlers.find(c => c.id === task.crawler_id);
        const crawlerName = crawler ? crawler.name : `(ID: ${task.crawler_id})`;

        // 根據類型和是否正在運行來決定按鈕狀態
        const isRunning = task.status === 'RUNNING';
        const runButtonDisabled = isRunning ? 'disabled' : '';
        const cancelButtonDisabled = !isRunning ? 'disabled' : '';

        // 格式化執行時間
        const lastRunTime = task.last_run_time ? new Date(task.last_run_time).toLocaleString() : '-';
        const nextRunTime = task.next_run_time ? new Date(task.next_run_time).toLocaleString() : '-';
        const scheduleDisplay = task.cron_expression || (task.type === 'manual' ? '手動執行' : '-');

        const row = `
            <tr class="task-row" data-task-id="${task.id}">
                <td>${task.id}</td>
                <td>${escapeHtml(task.name)}</td>
                <td>${escapeHtml(crawlerName)}</td>
                <td>${task.type === 'auto' ? '自動' : '手動'}</td>
                <td>${escapeHtml(scheduleDisplay)}</td>
                <td><span class="task-status-badge ${statusBadgeClass}">${task.status}</span></td>
                <td>
                    <div class="progress" style="height: 20px;">
                        <div class="progress-bar" role="progressbar" style="width: 0%;" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">0%</div>
                    </div>
                    <div class="d-flex justify-content-between mt-1">
                        <small class="task-scrape-phase">-</small>
                        <small class="task-articles-count">-</small>
                    </div>
                </td>
                <td>${lastRunTime}</td>
                <td>
                    <div class="btn-group" role="group">
                        <button class="btn btn-sm btn-success run-task-btn" data-task-id="${task.id}" data-task-type="${task.type}" ${runButtonDisabled}>
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
}

// 顯示任務新增/編輯模態框
function showTaskModal(taskId) {
    resetTaskForm(); // 清空表單

    if (taskId) {
        // 編輯模式
        const task = tasks.find(t => t.id === taskId);
        if (!task) {
            console.error('找不到ID為', taskId, '的任務');
            return;
        }

        $('#task-modal-label').text('編輯任務');
        $('#task-id').val(task.id);
        $('#task-name').val(task.name);
        $('#crawler-id').val(task.crawler_id);
        $('#task-type').val(task.type);
        $('#is-ai-related').prop('checked', task.is_ai_related);
        $('#task-remark').val(task.remark || '');

        // 根據任務類型更新排程字段
        updateScheduleFields(task.type, task.cron_expression);
    } else {
        // 新增模式
        $('#task-modal-label').text('新增任務');
    }

    $('#task-modal').modal('show');
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

// 重置表單
function resetTaskForm() {
    $('#task-id').val('');
    $('#task-name').val('');
    $('#crawler-id').val('');
    $('#task-type').val('');
    $('#is-ai-related').prop('checked', false);
    $('#task-remark').val('');
    $('#schedule-container').empty();
}

// 保存任務
function saveTask() {
    // 收集表單數據
    const taskId = $('#task-id').val();
    const isEdit = !!taskId;
    const taskType = $('#task-type').val();

    const taskData = {
        name: $('#task-name').val(),
        crawler_id: $('#crawler-id').val(),
        type: taskType,
        is_ai_related: $('#is-ai-related').is(':checked'),
        remark: $('#task-remark').val()
    };

    // 如果是自動執行，需要添加排程設定
    if (taskType === 'auto') {
        taskData.cron_expression = $('#cron-expression').val();
    }

    // 表單驗證
    if (!taskData.name || !taskData.crawler_id || !taskData.type) {
        displayAlert('warning', '請填寫必填欄位', true);
        return;
    }

    if (taskType === 'auto' && !taskData.cron_expression) {
        displayAlert('warning', '自動執行的任務需要填寫排程表達式', true);
        return;
    }

    // 發送 AJAX 請求
    $.ajax({
        url: isEdit ? `/api/tasks/${taskId}` : '/api/tasks',
        method: isEdit ? 'PUT' : 'POST',
        contentType: 'application/json',
        data: JSON.stringify(taskData),
        success: function (response) {
            // 關閉模態框並刷新列表
            $('#task-modal').modal('hide');
            displayAlert('success', isEdit ? '任務更新成功' : '任務新增成功');
            loadTasks();
        },
        error: function (xhr, status, error) {
            console.error('保存任務失敗:', error);
            displayAlert('danger', '保存失敗: ' + (xhr.responseJSON?.message || error), true);
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
                // 確保加入對應的 room (如果 WebSocket 已連接)
                if (socket && socket.connected) {
                    const roomName = `task_${taskId}`;
                    console.log(`啟動後加入房間: ${roomName}`);
                    socket.emit('join_room', { 'room': roomName });
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
        url: `/api/tasks/${taskId}/run_manual_links`,
        method: 'POST',
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
        links: selectedLinks.map(link => link.url)
    };

    // 發送請求開始爬取文章
    $.ajax({
        url: `/api/tasks/${taskId}/run_manual_articles`,
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
