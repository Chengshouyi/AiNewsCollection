// 爬蟲管理頁面的 JavaScript
console.log("爬蟲管理 JS 已加載");

let crawlers = []; // 存儲爬蟲列表的全局變數
let currentCrawlerId = null; // 當前操作的爬蟲ID

// 頁面加載後初始化
$(document).ready(function () {
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
});

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
