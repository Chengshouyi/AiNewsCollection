// 爬蟲管理頁面的 JavaScript
console.log("爬蟲管理 JS 已加載");

let crawlers = []; // 存儲爬蟲列表的全局變數
let currentCrawlerId = null; // 當前操作的爬蟲ID
let socket = null; // WebSocket連接
let currentTestTaskId = null; // 當前測試任務ID
let currentTestSessionId = null;  // 當前測試任務的會話ID

// 頁面加載後初始化
$(document).ready(function () {
    // 初始化WebSocket連接
    setupWebSocket();

    // 加載爬蟲列表
    loadCrawlers();

    // 綁定新增爬蟲按鈕事件
    $('#add-crawler-btn').click(function () {
        showCrawlerModal(null); // 傳入null表示新增模式
    });

    // 綁定爬蟲類型變更事件
    $('#crawler-type').change(function () {
        updateConfigFields($(this).val());
    });

    // 綁定保存按鈕事件
    $('#save-crawler-btn').click(function () {
        saveCrawler();
    });

    // 綁定刪除確認按鈕事件
    $('#confirm-delete-btn').click(function () {
        deleteCrawler(currentCrawlerId);
    });

    // 使用事件委託綁定表格中的編輯和刪除按鈕事件
    $('#crawlers-table-body').on('click', '.edit-crawler-btn', function () {
        const crawlerId = $(this).data('id');
        showCrawlerModal(crawlerId);
    });

    $('#crawlers-table-body').on('click', '.delete-crawler-btn', function () {
        currentCrawlerId = $(this).data('id');
        $('#delete-modal').modal('show');
    });

    // 在模態框關閉時清空檔案選擇器
    $('#crawler-modal').on('hidden.bs.modal', function () {
        $('#config-file').val('');
    });

    // 綁定測試按鈕事件
    $('#crawlers-table-body').on('click', '.test-crawler-btn', function () {
        const crawlerId = $(this).data('id');
        const crawlerName = $(this).data('crawler-name');
        testCrawler(crawlerId, crawlerName);
    });
});

// WebSocket連接設置
function setupWebSocket() {
    // 確保只初始化一次socket
    if (socket && socket.connected) {
        console.log("WebSocket已經連接");
        return;
    }

    // 連接到Socket.IO服務器
    const socketUrl = `${location.protocol}//${document.domain}:${location.port}/tasks`;
    console.log(`嘗試連接到WebSocket: ${socketUrl}`);
    socket = io.connect(socketUrl);

    socket.on('connect', () => {
        console.log('Socket.IO連接到/tasks成功');
        if ($('#test-debug-info').length) {
            $('#test-debug-info').append('<br>WebSocket已連接');
        }

        // 如果當前有測試任務進行中，重新加入房間
        if (currentTestTaskId) {
            // 檢查是否有保存的會話ID
            const sessionId = currentTestSessionId || '';
            const roomName = sessionId ? `task_${currentTestTaskId}_${sessionId}` : `task_${currentTestTaskId}`;
            console.log(`重新加入測試爬蟲房間: ${roomName}`);
            socket.emit('join_room', { 'room': roomName });

            if ($('#test-debug-info').length) {
                $('#test-debug-info').append(`<br>重新加入房間: ${roomName}`);
            }
        }
    });

    socket.on('disconnect', (reason) => {
        console.log(`Socket.IO斷開連接: ${reason}`);
        if ($('#test-debug-info').length) {
            $('#test-debug-info').append(`<br>WebSocket斷開: ${reason}`);
        }
    });

    socket.on('connect_error', (error) => {
        console.error('Socket.IO連接錯誤:', error);
        if ($('#test-debug-info').length) {
            $('#test-debug-info').append(`<br>WebSocket連接錯誤: ${error}`);
        }
    });

    // 監聽任務進度更新
    socket.on('task_progress', function (data) {
        console.log('收到進度更新事件:', data);

        // 更新調試信息（如果存在）
        if ($('#test-debug-info').length) {
            $('#test-debug-info').append(`<br>收到進度更新: task_id=${data.task_id}, progress=${data.progress}`);
            if (data.session_id) {
                $('#test-debug-info').append(`, session_id=${data.session_id}`);
            }
        }

        // 檢查是否匹配當前測試任務
        // 修改匹配條件，放寬匹配條件，因為有些事件可能只包含crawler_id
        const isCurrentTask = (currentTestTaskId && data.task_id == currentTestTaskId) ||
            (data.crawler_id && data.crawler_id == currentTestCrawlerId);

        if (isCurrentTask) {
            // 如果是首次收到帶有會話ID的消息，保存該會話ID
            if (data.session_id && !currentTestSessionId) {
                currentTestSessionId = data.session_id;
                console.log(`保存爬蟲測試會話ID: ${currentTestSessionId}`);

                // 更新調試信息
                if ($('#test-debug-info').length) {
                    $('#test-debug-info').append(`<br>保存會話ID: ${currentTestSessionId}`);
                }
            }

            updateTestProgress(data);
        } else {
            console.log('收到非當前任務的進度更新', data);
        }
    });

    // 監聽任務完成事件
    socket.on('task_finished', function (data) {
        console.log('收到任務完成事件:', data);

        // 更新調試信息（如果存在）
        if ($('#test-debug-info').length) {
            $('#test-debug-info').append(`<br>收到完成事件: task_id=${data.task_id}, status=${data.status}`);
            if (data.session_id) {
                $('#test-debug-info').append(`, session_id=${data.session_id}`);
            }
        }

        // 使用相同的邏輯檢查是否匹配當前測試任務
        if ((currentTestTaskId && data.task_id == currentTestTaskId &&
            (!currentTestSessionId || !data.session_id || data.session_id == currentTestSessionId)) ||
            (data.crawler_id && data.crawler_id == currentTestCrawlerId)) {

            // 檢查是否有result屬性，獲取連結數量
            let linksCount = 0;
            let message = data.message || '測試已完成';

            if (data.result) {
                // 處理嵌套的scrape_phase對象
                if (data.result.scrape_phase && typeof data.result.scrape_phase === 'object') {
                    const nestedPhase = data.result.scrape_phase;
                    message = nestedPhase.message || message;
                }

                // 設置連結數量，嘗試從多種可能的屬性中獲取
                linksCount = data.result.articles_count ||
                    (data.result.links ? data.result.links.length : 0) ||
                    data.links_count || 0;
            } else {
                // 如果沒有result屬性，嘗試從data直接獲取
                linksCount = data.links_count ||
                    (data.links ? data.links.length : 0) ||
                    data.articles_count || 0;
            }

            console.log(`任務完成，找到 ${linksCount} 個連結`);
            $('#test-debug-info').append(`<br>任務完成，找到 ${linksCount} 個連結`);

            // 確保將任務標記為已完成
            finishTestProgress({
                status: data.status || 'COMPLETED',
                message: message,
                links_count: linksCount,
                result: data.result,
                force_update: true,
                session_id: data.session_id
            });

            // 如果事件包含會話ID，則在完成任務後清除當前會話ID
            if (data.session_id && data.session_id === currentTestSessionId) {
                currentTestSessionId = null;
            }
        }
    });

    // 監聽連結抓取完成事件 (通常用於手動任務)
    socket.on('links_fetched', function (data) {
        console.log('收到連結抓取事件:', data);

        // 更新調試信息（如果存在）
        if ($('#test-debug-info').length) {
            $('#test-debug-info').append(`<br>收到連結事件: task_id=${data.task_id}`);

            if (data.links) {
                $('#test-debug-info').append(`, 連結數=${data.links.length}`);
            }
        }

        // 根據task_id或crawler_id匹配當前測試任務
        if ((currentTestTaskId && data.task_id == currentTestTaskId) ||
            (data.crawler_id && data.crawler_id == currentTestCrawlerId)) {

            // 獲取連結數量
            const linksCount = data.links ? data.links.length : (data.links_count || 0);
            console.log(`找到 ${linksCount} 個連結，測試完成`);

            // 更新進度為100%，表示測試完成
            updateTestProgress({
                task_id: data.task_id,
                crawler_id: data.crawler_id,
                progress: 100,
                message: '連結抓取完成',
                links_count: linksCount,
                force_update: true
            });

            // 直接標記為完成
            finishTestProgress({
                status: 'COMPLETED',
                message: '測試已完成',
                links_count: linksCount,
                force_update: true
            });
        }
    });

    // 監聽測試完成事件（可能有專門的事件類型）
    socket.on('test_completed', function (data) {
        console.log('收到測試完成事件:', data);

        // 更新調試信息（如果存在）
        if ($('#test-debug-info').length) {
            $('#test-debug-info').append(`<br>收到測試完成事件: crawler_id=${data.crawler_id}`);
        }

        finishTestProgress({
            status: 'COMPLETED',
            task_id: data.task_id,
            crawler_id: data.crawler_id,
            message: '測試已完成',
            links_count: data.links_count ||
                (data.links ? data.links.length : 0) ||
                (data.result && data.result.links ? data.result.links.length : 0)
        });
    });
}

// 更新測試進度顯示
function updateTestProgress(data) {
    console.log('收到進度更新:', data);

    // 創建或更新進度提示
    let progressContainer = $('#test-progress-container');
    if (progressContainer.length === 0) {
        // 如果進度容器不存在，創建一個
        $('main.container').prepend(`
            <div id="test-progress-container" class="alert alert-info" role="alert">
                <h5>爬蟲測試進度</h5>
                <div class="progress mb-2">
                    <div id="test-progress-bar" class="progress-bar progress-bar-striped progress-bar-animated" 
                         role="progressbar" style="width: 0%;" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">0%</div>
                </div>
                <div id="test-progress-message"></div>
                <div id="test-progress-links" class="mt-2"></div>
                <div id="test-debug-info" class="mt-2 small text-muted"></div>
            </div>
        `);
        progressContainer = $('#test-progress-container');
    }

    // 簡化確認邏輯：接受任何與當前爬蟲或任務相關的更新
    const isCurrentTask =
        (currentTestTaskId && data.task_id && currentTestTaskId == data.task_id) ||
        (data.crawler_id && data.crawler_id == currentTestCrawlerId) ||
        data.force_update === true;

    if (!isCurrentTask) {
        console.log('非當前任務的進度更新，忽略');
        $('#test-debug-info').append('<br>收到不相關的更新，已忽略');
        return;
    }

    // 處理嵌套的scrape_phase對象
    if (data.scrape_phase && typeof data.scrape_phase === 'object') {
        const nestedPhase = data.scrape_phase;
        // 合併嵌套對象的屬性到頂層
        if (nestedPhase.progress !== undefined) data.progress = nestedPhase.progress;
        if (nestedPhase.message) data.message = nestedPhase.message;
        if (nestedPhase.scrape_phase) data.scrape_phase_value = nestedPhase.scrape_phase;
    }

    // 確保有進度數值，最低不低於當前顯示的進度
    const progressBar = $('#test-progress-bar');
    const currentWidth = parseInt(progressBar.css('width')) || 0;
    const currentPercent = parseInt(progressBar.text()) || 0;

    // 使用較大值，確保進度不會倒退
    let progress = data.progress || 0;
    if (currentPercent > progress && !data.force_update) {
        console.log(`保持現有進度 ${currentPercent}%，忽略較低進度 ${progress}%`);
        progress = currentPercent;
    }

    // 更新進度條
    progressBar.css('width', progress + '%');
    progressBar.text(progress + '%');

    // 更新進度調試信息
    $('#test-debug-info').append(`<br>進度更新: ${progress}%, 訊息: ${data.message || 'N/A'}`);

    // 更新消息
    if (data.message) {
        $('#test-progress-message').text(data.message);
    }

    // 如果有文章數量信息，顯示
    // 檢查不同可能的屬性名稱，因為API可能用不同的名稱傳遞連結數量
    const linksCount = data.links_count ||
        (data.result && data.result.links ? data.result.links.length : null) ||
        (data.articles_count) ||
        null;

    if (linksCount !== null) {
        $('#test-progress-links').text(`找到 ${linksCount} 個連結`);
    }

    // 如果進度是100%，直接觸發完成
    if (progress >= 100) {
        finishTestProgress({
            status: 'COMPLETED',
            message: data.message || '測試已完成',
            links_count: linksCount,
            force_update: true
        });
    } else if (progress >= 50 && linksCount !== null) {
        // 如果已找到連結且進度>=50%，可能任務已接近完成
        // 3秒後檢查是否有完成事件，如果沒有則手動觸發完成
        setTimeout(function () {
            const newProgress = parseInt($('#test-progress-bar').text());
            if (newProgress < 100) {
                console.log('有連結但未收到完成事件，手動觸發完成');
                finishTestProgress({
                    status: 'COMPLETED',
                    message: '測試已完成',
                    links_count: linksCount,
                    force_update: true // 強制更新標誌
                });
            }
        }, 3000);
    }
}

// 完成測試進度顯示
function finishTestProgress(data) {
    console.log('收到完成訊息:', data);

    const progressContainer = $('#test-progress-container');
    if (progressContainer.length > 0) {
        // 防止重複完成
        if (progressContainer.data('completed') === true && !data.force_update) {
            console.log('已經完成，忽略重複的完成事件');
            return;
        }

        // 標記為已完成
        progressContainer.data('completed', true);

        // 更新調試信息
        $('#test-debug-info').append(`<br>任務完成: ${data.status || 'COMPLETED'}`);

        // 更新進度條為完成狀態
        const progressBar = $('#test-progress-bar');
        progressBar.removeClass('progress-bar-animated');

        if (data.status === 'COMPLETED' || !data.status) {
            progressBar.removeClass('bg-info').addClass('bg-success');
            progressBar.css('width', '100%').text('100%');
            $('#test-progress-message').text(data.message || '測試完成');

            // 顯示結果摘要
            const linksCount = data.links_count ||
                (data.result && data.result.links ? data.result.links.length : null) ||
                (data.articles_count) ||
                0;

            $('#test-progress-links').html(`
                <div class="alert alert-success">
                    <strong>測試成功!</strong> 找到 ${linksCount} 個連結
                </div>
            `);
        } else if (data.status === 'FAILED') {
            progressBar.removeClass('bg-info').addClass('bg-danger');
            $('#test-progress-message').text('測試失敗: ' + (data.error || '未知錯誤'));
            $('#test-debug-info').append(`<br>失敗原因: ${data.error || '未知'}`);
        }

        // 完成後不自動關閉，讓用戶能看到結果
        // 改為提供一個關閉按鈕
        if (!$('#close-progress-btn').length) {
            progressContainer.append(`
                <button id="close-progress-btn" class="btn btn-sm btn-outline-secondary mt-2">
                    關閉此訊息
                </button>
                <button id="show-debug-btn" class="btn btn-sm btn-outline-info mt-2 ms-2">
                    顯示/隱藏調試資訊
                </button>
            `);

            // 綁定關閉按鈕事件
            $('#close-progress-btn').click(function () {
                progressContainer.fadeOut('slow', function () {
                    $(this).remove();
                });
            });

            // 綁定顯示/隱藏調試資訊按鈕
            $('#show-debug-btn').click(function () {
                $('#test-debug-info').toggle();
            });

            // 默認隱藏調試資訊
            $('#test-debug-info').hide();
        }
    }
}

// 加載爬蟲列表
function loadCrawlers() {
    $.ajax({
        url: '/api/crawlers',
        method: 'GET',
        success: function (response) {
            crawlers = response.data || [];
            renderCrawlersTable(crawlers);
        },
        error: function (xhr, status, error) {
            console.error('加載爬蟲列表失敗:', error);
            // 顯示錯誤訊息
            displayAlert('danger', '加載爬蟲列表失敗: ' + (xhr.responseJSON?.message || error));
        }
    });
}

// 渲染爬蟲表格
function renderCrawlersTable(crawlers) {
    const tableBody = $('#crawlers-table-body');
    tableBody.empty();

    if (crawlers.length === 0) {
        tableBody.append('<tr><td colspan="7" class="text-center">暫無爬蟲，請點擊「新增爬蟲」按鈕添加。</td></tr>');
        return;
    }

    crawlers.forEach(crawler => {
        const statusBadgeClass = crawler.is_active ? 'badge bg-success' : 'badge bg-secondary';
        const statusText = crawler.is_active ? '啟用' : '停用';

        const row = `
            <tr data-id="${crawler.id}">
                <td>${crawler.id}</td>
                <td>${escapeHtml(crawler.crawler_name)}</td>
                <td>${escapeHtml(crawler.module_name)}</td>
                <td>${escapeHtml(crawler.base_url)}</td>
                <td>${escapeHtml(crawler.crawler_type)}</td>
                <td><span class="${statusBadgeClass}">${statusText}</span></td>
                <td>
                    <button class="btn btn-sm btn-outline-primary edit-crawler-btn" data-id="${crawler.id}">
                        <i class="bi bi-pencil"></i> 編輯
                    </button>
                    <button class="btn btn-sm btn-outline-danger delete-crawler-btn" data-id="${crawler.id}">
                        <i class="bi bi-trash"></i> 刪除
                    </button>
                    <button class="btn btn-sm btn-outline-info test-crawler-btn" data-id="${crawler.id}" 
                            data-crawler-name="${escapeHtml(crawler.crawler_name)}">
                        <i class="bi bi-play"></i> 測試
                    </button>
                </td>
            </tr>
        `;

        tableBody.append(row);
    });
}

// 顯示爬蟲新增/編輯模態框
function showCrawlerModal(crawlerId) {
    resetCrawlerForm(); // 清空表單

    if (crawlerId) {
        // 編輯模式
        const crawler = crawlers.find(c => c.id === crawlerId);
        if (!crawler) {
            console.error('找不到ID為', crawlerId, '的爬蟲');
            return;
        }

        $('#crawler-modal-label').text('編輯爬蟲');
        $('#crawler-id').val(crawler.id);
        $('#crawler-name').val(crawler.crawler_name);
        $('#module-name').val(crawler.module_name);
        $('#crawler-website').val(crawler.base_url);
        $('#crawler-type').val(crawler.crawler_type);

        // 獲取並顯示配置檔案內容
        $.ajax({
            url: `/api/crawlers/${crawlerId}/config`,
            method: 'GET',
            success: function (response) {
                console.log('API 回應:', response);
                if (response.success) {
                    $('#current-config-file').text(crawler.config_file_name);
                    $('#config-content').val(JSON.stringify(response.config, null, 2));
                    $('#config-edit-section').show();
                } else {
                    console.error('API 回應錯誤:', response.message);
                    displayAlert('warning', response.message);
                }
            },
            error: function (xhr, status, error) {
                console.error('API 錯誤詳情:', {
                    status: xhr.status,
                    statusText: xhr.statusText,
                    responseText: xhr.responseText,
                    error: error,
                    configFileName: crawler.config_file_name,
                    url: `/api/crawlers/${crawlerId}/config`
                });
                displayAlert('danger', '獲取配置檔案失敗: ' + (xhr.responseJSON?.message || error));
            }
        });
    } else {
        // 新增模式
        $('#crawler-modal-label').text('新增爬蟲');
        $('#config-edit-section').hide();
    }

    $('#crawler-modal').modal('show');
}

// 根據爬蟲類型更新配置字段
function updateConfigFields(type, configValues = {}) {
    const container = $('#config-fields-container');
    container.empty();

    switch (type) {
        case 'rss':
            container.append(`
                <div class="mb-3">
                    <label for="rss-url" class="form-label">RSS URL</label>
                    <input type="url" class="form-control" id="rss-url" name="rss_url" 
                           value="${escapeHtml(configValues.rss_url || '')}" required>
                </div>
            `);
            break;
        case 'xpath':
            container.append(`
                <div class="mb-3">
                    <label for="base-url" class="form-label">基礎 URL</label>
                    <input type="url" class="form-control" id="base-url" name="base_url" 
                           value="${escapeHtml(configValues.base_url || '')}" required>
                </div>
                <div class="mb-3">
                    <label for="list-xpath" class="form-label">列表 XPath</label>
                    <input type="text" class="form-control" id="list-xpath" name="list_xpath" 
                           value="${escapeHtml(configValues.list_xpath || '')}" required>
                </div>
                <div class="mb-3">
                    <label for="title-xpath" class="form-label">標題 XPath</label>
                    <input type="text" class="form-control" id="title-xpath" name="title_xpath" 
                           value="${escapeHtml(configValues.title_xpath || '')}" required>
                </div>
                <div class="mb-3">
                    <label for="content-xpath" class="form-label">內容 XPath</label>
                    <input type="text" class="form-control" id="content-xpath" name="content_xpath" 
                           value="${escapeHtml(configValues.content_xpath || '')}" required>
                </div>
            `);
            break;
        case 'custom':
            container.append(`
                <div class="mb-3">
                    <label for="custom-config" class="form-label">自訂配置 (JSON)</label>
                    <textarea class="form-control" id="custom-config" name="custom_config" rows="5" required>${escapeHtml(JSON.stringify(configValues, null, 2) || '{}')}</textarea>
                    <div class="form-text">請輸入有效的 JSON 格式配置</div>
                </div>
            `);
            break;
    }
}

// 重置表單
function resetCrawlerForm() {
    $('#crawler-id').val('');
    $('#crawler-name').val('');
    $('#module-name').val('');
    $('#crawler-website').val('');
    $('#crawler-type').val('');
    $('#crawler-remark').val('');
    $('#config-fields-container').empty();
}

// 保存爬蟲
function saveCrawler() {
    // 收集表單數據
    const crawlerId = $('#crawler-id').val();
    const isEdit = !!crawlerId;

    const crawlerData = {
        crawler_name: $('#crawler-name').val(),
        module_name: $('#module-name').val(),
        base_url: $('#crawler-website').val(),
        config_file_name: getConfigFileName(),
        crawler_type: $('#crawler-type').val()
    };

    // 表單驗證
    if (!crawlerData.crawler_name || !crawlerData.base_url || !crawlerData.crawler_type) {
        displayAlert('warning', '請填寫必填欄位');
        return;
    }

    // 處理配置檔案
    const configFile = $('#config-file')[0].files[0];
    if (configFile) {
        // 如果有上傳新檔案，使用 FormData 傳送
        const formData = new FormData();
        formData.append('config_file', configFile);
        formData.append('crawler_data', JSON.stringify(crawlerData));

        const url = isEdit ? `/api/crawlers/${crawlerId}/config` : '/api/crawlers';
        const method = isEdit ? 'PUT' : 'POST';

        $.ajax({
            url: url,
            method: method,
            data: formData,
            processData: false,
            contentType: false,
            success: function (response) {
                console.log('保存成功:', response);
                $('#crawler-modal').modal('hide');
                displayAlert('success', response.message || '保存成功');
                loadCrawlers();
                // 清空檔案選擇器
                $('#config-file').val('');
            },
            error: function (xhr, status, error) {
                console.error('保存失敗:', {
                    status: xhr.status,
                    statusText: xhr.statusText,
                    responseText: xhr.responseText,
                    error: error
                });
                displayAlert('danger', '保存失敗: ' + (xhr.responseJSON?.message || error));
            }
        });
    } else if (isEdit && $('#config-content').val()) {
        // 如果是編輯模式且修改了配置內容，使用修改後的內容
        try {
            console.log('當前配置內容:', $('#config-content').val());
            const configContent = $('#config-content').val().trim();
            if (!configContent) {
                console.warn('配置內容為空');
                displayAlert('warning', '配置內容不能為空');
                return;
            }
            const config = JSON.parse(configContent);
            console.log('解析後的配置:', config);

            // 創建一個新的 Blob 對象作為配置檔案
            const configBlob = new Blob([configContent], { type: 'application/json' });
            const configFile = new File([configBlob], crawlerData.config_file_name, { type: 'application/json' });

            // 使用 FormData 傳送
            const formData = new FormData();
            formData.append('config_file', configFile);
            formData.append('crawler_data', JSON.stringify(crawlerData));

            $.ajax({
                url: `/api/crawlers/${crawlerId}/config`,
                method: 'PUT',
                data: formData,
                processData: false,
                contentType: false,
                success: function (response) {
                    console.log('保存成功:', response);
                    $('#crawler-modal').modal('hide');
                    displayAlert('success', response.message || '保存成功');
                    loadCrawlers();
                    // 清空檔案選擇器
                    $('#config-file').val('');
                },
                error: function (xhr, status, error) {
                    console.error('保存失敗:', {
                        status: xhr.status,
                        statusText: xhr.statusText,
                        responseText: xhr.responseText,
                        error: error
                    });
                    displayAlert('danger', '保存失敗: ' + (xhr.responseJSON?.message || error));
                }
            });
        } catch (error) {
            console.error('配置內容解析錯誤:', error);
            console.error('原始配置內容:', $('#config-content').val());
            displayAlert('danger', '配置內容格式錯誤，請確保是有效的 JSON 格式');
        }
    } else {
        // 其他情況直接保存
        saveCrawlerData(crawlerData);
    }
}

// 保存爬蟲數據到後端
function saveCrawlerData(crawlerData) {
    console.log('準備保存的數據:', crawlerData);
    const crawlerId = $('#crawler-id').val();
    const url = crawlerId ? `/api/crawlers/${crawlerId}` : '/api/crawlers';
    const method = crawlerId ? 'PUT' : 'POST';

    $.ajax({
        url: url,
        method: method,
        contentType: 'application/json',
        data: JSON.stringify(crawlerData),
        success: function (response) {
            console.log('保存成功:', response);
            $('#crawler-modal').modal('hide');
            displayAlert('success', response.message || '保存成功');
            loadCrawlers();
        },
        error: function (xhr, status, error) {
            console.error('保存失敗:', {
                status: xhr.status,
                statusText: xhr.statusText,
                responseText: xhr.responseText,
                error: error
            });
            displayAlert('danger', '保存失敗: ' + (xhr.responseJSON?.message || error));
        }
    });
}

// 刪除爬蟲
function deleteCrawler(crawlerId) {
    if (!crawlerId) return;

    $.ajax({
        url: `/api/crawlers/${crawlerId}`,
        method: 'DELETE',
        success: function (response) {
            $('#delete-modal').modal('hide');
            displayAlert('success', '爬蟲已刪除');
            loadCrawlers();
        },
        error: function (xhr, status, error) {
            $('#delete-modal').modal('hide');
            console.error('刪除爬蟲失敗:', error);
            displayAlert('danger', '刪除失敗: ' + (xhr.responseJSON?.message || error));
        }
    });
}

// 獲取配置數據
function getConfigData() {
    const type = $('#crawler-type').val();
    let config = {};

    switch (type) {
        case 'rss':
            config = {
                rss_url: $('#rss-url').val()
            };
            break;
        case 'xpath':
            config = {
                base_url: $('#base-url').val(),
                list_xpath: $('#list-xpath').val(),
                title_xpath: $('#title-xpath').val(),
                content_xpath: $('#content-xpath').val()
            };
            break;
        case 'custom':
            try {
                config = JSON.parse($('#custom-config').val() || '{}');
            } catch (e) {
                displayAlert('danger', '自訂配置 JSON 格式錯誤', true);
                throw new Error('Invalid JSON');
            }
            break;
    }

    return config;
}

// 獲取配置檔案名稱
function getConfigFileName() {
    const crawlerId = $('#crawler-id').val();
    if (crawlerId) {
        // 如果是編輯模式，保持原始檔名
        const crawler = crawlers.find(c => c.id === parseInt(crawlerId));
        if (crawler) {
            return crawler.config_file_name;
        }
    }
    // 如果是新增模式，使用預設檔名
    const name = $('#crawler-name').val().toLowerCase();
    return `${name}_crawler_config.json`;
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

// 測試爬蟲
function testCrawler(crawlerId, crawlerName) {
    if (!crawlerId) return;

    // 重置測試狀態
    currentTestTaskId = null;
    currentTestCrawlerId = crawlerId;
    currentTestSessionId = null;  // 重置會話ID

    // 顯示測試進度容器
    let progressContainer = $('#test-progress-container');
    if (progressContainer.length === 0) {
        // 如果進度容器不存在，創建一個
        $('main.container').prepend(`
            <div id="test-progress-container" class="alert alert-info" role="alert">
                <h5>爬蟲測試進度</h5>
                <div class="progress mb-2">
                    <div id="test-progress-bar" class="progress-bar progress-bar-striped progress-bar-animated" 
                         role="progressbar" style="width: 0%;" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">0%</div>
                </div>
                <div id="test-progress-message"></div>
                <div id="test-progress-links" class="mt-2"></div>
                <div id="test-debug-info" class="mt-2 small text-muted"></div>
            </div>
        `);
        progressContainer = $('#test-progress-container');
    } else {
        // 如果已存在，重置其狀態
        progressContainer.removeClass('alert-success alert-danger').addClass('alert-info');
        progressContainer.data('completed', false);
        $('#close-progress-btn, #show-debug-btn').remove();
    }

    // 重置進度顯示
    $('#test-progress-bar').css('width', '5%').text('5%')
        .removeClass('bg-success bg-danger')
        .addClass('progress-bar-striped progress-bar-animated');
    $('#test-progress-message').text('開始測試爬蟲...');
    $('#test-progress-links').empty();
    $('#test-debug-info').html(`開始測試爬蟲 ID=${crawlerId}, 名稱=${crawlerName}`);

    // 獲取測試參數
    const aiOnly = $('#test-ai-only').is(':checked');

    // 確保Socket.IO連接已建立
    if (!socket || !socket.connected) {
        console.log('WebSocket未連接，正在嘗試重新連接...');
        $('#test-debug-info').append('<br>WebSocket未連接，正在嘗試重新連接...');
        // 先嘗試重新設置連接
        setupWebSocket();

        // 如果5秒後仍未連接，顯示錯誤
        setTimeout(function () {
            if (!socket || !socket.connected) {
                $('#test-progress-message').text('WebSocket連接失敗，無法接收實時更新');
                $('#test-debug-info').append('<br>WebSocket連接失敗，測試可能繼續但無法接收實時更新');
            }
        }, 5000);
    }

    // 發送測試請求
    $.ajax({
        url: '/api/tasks/manual/test',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            crawler_id: crawlerId,
            crawler_name: crawlerName,
            task_args: {
                ai_only: aiOnly
            }
        }),
        success: function (response) {
            console.log('測試請求響應:', response);
            if (response.success) {
                // 保存測試任務ID (如果有)
                if (response.task_id) {
                    currentTestTaskId = response.task_id;

                    // 保存會話ID (如果有)
                    if (response.session_id) {
                        currentTestSessionId = response.session_id;
                        console.log(`獲取到測試會話ID: ${currentTestSessionId}`);

                        // 更新調試信息
                        if ($('#test-debug-info').length) {
                            $('#test-debug-info').append(`<br>獲取到會話ID: ${currentTestSessionId}`);
                        }
                    }

                    // 加入任務房間 (包含會話ID如果有的話)
                    if (socket && socket.connected) {
                        const roomName = currentTestSessionId ?
                            `task_${currentTestTaskId}_${currentTestSessionId}` :
                            `task_${currentTestTaskId}`;
                        console.log(`加入測試房間: ${roomName}`);
                        socket.emit('join_room', { 'room': roomName });

                        // 更新調試信息
                        if ($('#test-debug-info').length) {
                            $('#test-debug-info').append(`<br>加入房間: ${roomName}`);
                        }
                    } else {
                        console.warn('WebSocket未連接，無法加入任務房間');
                        $('#test-debug-info').append('<br>WebSocket未連接，無法加入任務房間');
                    }

                    $('#test-progress-message').text(`測試任務已啟動，ID: ${currentTestTaskId}`);

                    // 更新進度到20%，表示任務已開始
                    updateTestProgress({
                        task_id: currentTestTaskId,
                        crawler_id: crawlerId,
                        progress: 20,
                        message: '測試任務已開始執行',
                        force_update: true
                    });
                } else {
                    $('#test-progress-message').text('測試已啟動，正在等待進度更新');

                    // 即使沒有task_id，也更新到20%
                    updateTestProgress({
                        crawler_id: crawlerId,
                        progress: 20,
                        message: '測試開始執行',
                        force_update: true
                    });
                }

                // 直接從 response.result 中獲取連結數量 (如果有)
                let linksCount = 0;
                if (response.result) {
                    // 檢查多種可能的屬性名稱
                    linksCount = response.result.links_count ||
                        (response.result.links ? response.result.links.length : 0) ||
                        response.result.articles_count || 0;

                    // 如果有連結數量信息，直接更新進度到100%
                    if (linksCount > 0 || response.result.scrape_phase === 'completed') {
                        console.log(`從API回應獲取到連結數量: ${linksCount}`);
                        $('#test-debug-info').append(`<br>從API回應獲取到連結數量: ${linksCount}`);

                        // 更新進度到100%
                        updateTestProgress({
                            crawler_id: crawlerId,
                            progress: 100,
                            message: response.message || '測試已完成',
                            links_count: linksCount,
                            force_update: true
                        });

                        // 不需要再等待進度更新，直接標記為完成
                        return;
                    }
                }

                // 如果是手動測試模式的實現，可能需要輪詢獲取結果
                if ((!response.task_id && response.redirect_url) || !linksCount) {
                    setTimeout(function () {
                        checkTestResult(crawlerId);
                    }, 2000);
                }
            } else {
                $('#test-progress-message').text(`測試請求失敗: ${response.message}`);
                $('#test-progress-bar').css('width', '100%').text('100%');
                progressContainer.removeClass('alert-info').addClass('alert-danger');
            }
        },
        error: function (xhr, status, error) {
            console.error('測試請求失敗:', error);
            $('#test-progress-message').text(`測試請求失敗: ${xhr.responseJSON?.message || error}`);
            $('#test-progress-bar').css('width', '100%').text('100%');
            progressContainer.removeClass('alert-info').addClass('alert-danger');
        }
    });
}

// 檢查測試結果
function checkTestResult(crawlerId) {
    console.log('檢查爬蟲測試結果，爬蟲ID:', crawlerId);
    $('#test-debug-info').append('<br>檢查爬蟲測試結果...');

    // 檢查進度條當前狀態
    const progressBar = $('#test-progress-bar');
    const currentProgress = parseInt(progressBar.text()) || 0;

    // 如果進度已經達到100%，不需要再檢查
    if (currentProgress >= 100) {
        console.log('進度已達100%，無需再檢查');
        $('#test-debug-info').append('<br>進度已達100%，無需再檢查');
        return;
    }

    // 由於測試任務是同步執行的，當我們執行到這裡時，測試其實已經完成
    // 但前端進度條可能沒有更新，這裡我們直接將進度更新到100%
    console.log('測試可能已完成，但進度未更新，直接更新到100%');
    $('#test-debug-info').append('<br>測試可能已完成，但進度未更新，直接設為完成');

    // 直接標記為完成
    finishTestProgress({
        status: 'COMPLETED',
        message: '測試已完成',
        // 嘗試從頁面找到連結數量
        links_count: getLinksCountFromPage(),
        force_update: true
    });
}

// 幫助函數：從頁面中獲取連結數量
function getLinksCountFromPage() {
    // 嘗試從進度訊息中提取連結數量
    const linksText = $('#test-progress-links').text();
    const match = linksText.match(/找到\s*(\d+)\s*個連結/);
    if (match && match[1]) {
        return parseInt(match[1]);
    }

    // 如果沒有找到，嘗試從調試信息中提取
    const debugText = $('#test-debug-info').text();
    const debugMatch = debugText.match(/找到\s*(\d+)\s*(?:篇文章|個連結)/);
    if (debugMatch && debugMatch[1]) {
        return parseInt(debugMatch[1]);
    }

    // 如果都沒有找到，返回0
    return 0;
}
