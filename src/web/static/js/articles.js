// 文章列表/查看頁面的 JavaScript
console.log("文章管理 JS 已加載");

// 全局變數
let articles = []; // 存儲文章列表
let currentPage = 1; // 當前頁碼
let totalPages = 1; // 總頁數
let pageSize = 20; // 每頁顯示數量
let currentFilter = 'all'; // 當前篩選條件
let searchQuery = ''; // 搜索關鍵詞

// 頁面加載時初始化
$(document).ready(function () {
    // 檢查是否在文章列表頁面
    if ($('#articles-table-body').length) {
        loadArticles();

        // 綁定搜尋按鈕事件
        $('#search-btn').click(function () {
            const searchTerm = $('#search-input').val().trim();
            if (searchTerm) {
                executeSearch(searchTerm);
            } else {
                // 如果搜尋框為空，則重新加載預設的文章列表
                searchQuery = ''; // 清除全局搜索詞（如果之前有）
                currentPage = 1;
                loadArticles();
            }
        });

        // 綁定回車鍵搜尋
        $('#search-input').keypress(function (e) {
            if (e.which === 13) {
                // 觸發搜尋按鈕的點擊事件，邏輯保持一致
                $('#search-btn').click();
            }
        });

        // 綁定篩選下拉選項點擊事件
        $('.dropdown-item').click(function (e) {
            e.preventDefault();
            currentFilter = $(this).data('filter');
            currentPage = 1; // 重置為第一頁
            $('#filter-dropdown').text($(this).text()); // 更新按鈕文字
            loadArticles();
        });

        // --- 新增：使用事件委託綁定分頁按鈕點擊事件 ---
        $('#pagination').on('click', '.page-link', function () {
            const page = $(this).data('page');
            // 確保 page 是數字且有效
            if (page && !isNaN(page) && page !== currentPage && page >= 1 && page <= totalPages) {
                currentPage = parseInt(page); // 確保 currentPage 是數字
                loadArticles();
                // 滾動到頁面頂部
                $('html, body').animate({ scrollTop: 0 }, 'fast');
            }
        });
        // --- 新增結束 ---
    }

    // 綁定文章列表表格中的查看按鈕事件 (使用事件委託)
    $('#articles-table-body').on('click', '.view-article-btn', function () {
        const articleId = $(this).data('id');
        loadArticleDetailsModal(articleId);
    });
});

// 加載文章列表
function loadArticles() {
    // 構建 API URL (包含分頁、篩選)
    let url = `/api/articles?page=${currentPage}&per_page=${pageSize}`;

    if (currentFilter && currentFilter !== 'all') {
        url += `&filter=${currentFilter}`;
    }

    $.ajax({
        url: url,
        method: 'GET',
        success: function (response) {
            if (response.success) {
                articles = response.data.items || [];
                totalPages = response.data.total_pages || 1;
                renderArticlesTable(articles);
                renderPagination(currentPage, totalPages);
            } else {
                displayAlert('danger', '加載文章失敗: ' + response.message);
            }
        },
        error: function (xhr, status, error) {
            console.error('加載文章列表失敗:', error);
            displayAlert('danger', '加載文章列表失敗: ' + (xhr.responseJSON?.message || error));
        }
    });
}

// 渲染文章表格
function renderArticlesTable(articles) {
    const tableBody = $('#articles-table-body');
    tableBody.empty();

    // 爬取狀態中文映射 (根據 ArticleScrapeStatus)
    const scrapeStatusMap = {
        pending: '待處理',
        link_saved: '連結已存',
        partial_saved: '部分儲存',
        content_scraped: '內容已爬',
        failed: '爬取失敗'
    };

    if (articles.length === 0) {
        tableBody.append('<tr><td colspan="8" class="text-center">暫無文章</td></tr>');
        return;
    }

    articles.forEach(article => {
        // 格式化日期
        const publishDate = article.published_at ? new Date(article.published_at).toLocaleString() : '-';
        const lastScrapeAttempt = article.last_scrape_attempt ? new Date(article.last_scrape_attempt).toLocaleString() : '-';

        // AI 相關徽章
        const aiRelatedBadge = article.is_ai_related
            ? '<span class="badge bg-success">是</span>'
            : '<span class="badge bg-secondary">否</span>';

        // 爬取狀態顯示（使用映射）
        const rawStatus = article.scrape_status;
        const displayStatus = scrapeStatusMap[rawStatus] || rawStatus || '-'; // 如果找不到映射或狀態為空，則顯示原始值或 '-'

        const row = `
            <tr>
                <td>${article.id}</td>
                <td>
                    <a href="javascript:void(0)" class="article-title-link view-article-btn" data-id="${article.id}">
                        ${escapeHtml(article.title)}
                    </a>
                </td>
                <td>${escapeHtml(article.source || '-')}</td>
                <td>${publishDate}</td>
                <td class="text-center">${aiRelatedBadge}</td>
                <td>${lastScrapeAttempt}</td>
                <td>${escapeHtml(displayStatus)}</td>
                <td>
                    <div class="btn-group" role="group">
                        <a href="/articles/${article.id}" class="btn btn-sm btn-primary">
                            <i class="bi bi-eye"></i> 查看
                        </a>
                        <button class="btn btn-sm btn-outline-primary view-article-btn" data-id="${article.id}">
                            <i class="bi bi-box"></i> 快速查看
                        </button>
                    </div>
                </td>
            </tr>
        `;

        tableBody.append(row);
    });
}

// 渲染分頁控制
function renderPagination(currentPage, totalPages) {
    const pagination = $('#pagination');
    pagination.empty();

    if (totalPages <= 1) {
        return; // 不需要分頁
    }

    // 上一頁按鈕
    const prevDisabled = currentPage === 1 ? 'disabled' : '';
    pagination.append(`
        <li class="page-item ${prevDisabled}">
            <a class="page-link" href="javascript:void(0)" data-page="${currentPage - 1}" aria-label="Previous">
                <span aria-hidden="true">&laquo;</span>
            </a>
        </li>
    `);

    // 頁碼按鈕
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, startPage + 4);

    for (let i = startPage; i <= endPage; i++) {
        const active = i === currentPage ? 'active' : '';
        pagination.append(`
            <li class="page-item ${active}">
                <a class="page-link" href="javascript:void(0)" data-page="${i}">${i}</a>
            </li>
        `);
    }

    // 下一頁按鈕
    const nextDisabled = currentPage === totalPages ? 'disabled' : '';
    pagination.append(`
        <li class="page-item ${nextDisabled}">
            <a class="page-link" href="javascript:void(0)" data-page="${currentPage + 1}" aria-label="Next">
                <span aria-hidden="true">&raquo;</span>
            </a>
        </li>
    `);
}

// 加載文章詳情 (模態框版本)
function loadArticleDetailsModal(articleId) {
    $.ajax({
        url: `/api/articles/${articleId}`,
        method: 'GET',
        success: function (response) {
            if (response.success) {
                const article = response.data;

                // 設置模態框標題
                $('#article-modal-label').text(article.title);

                // 構建文章內容 HTML
                let contentHtml = `
                    <div class="article-header mb-4">
                        <div class="d-flex justify-content-between mb-3">
                            <div>
                                <span class="badge bg-info me-2">來源: ${escapeHtml(article.source || '-')}</span>
                                <span class="badge bg-secondary me-2">發布日期: ${article.published_at ? new Date(article.published_at).toLocaleString() : '-'}</span>
                                ${article.is_ai_related ? '<span class="badge bg-success">AI相關</span>' : ''}
                            </div>
                        </div>
                    </div>
                    <div class="article-content">
                        ${article.content || '<p class="text-muted">無內容</p>'}
                    </div>
                `;

                $('#article-detail-container').html(contentHtml);

                // 設置原始網頁連結
                if (article.url) {
                    $('#article-source-link').attr('href', article.url).show();
                } else {
                    $('#article-source-link').hide();
                }

                // 顯示模態框
                $('#article-modal').modal('show');
            } else {
                displayAlert('danger', '加載文章詳情失敗: ' + response.message);
            }
        },
        error: function (xhr, status, error) {
            console.error('加載文章詳情失敗:', error);
            displayAlert('danger', '加載文章詳情失敗: ' + (xhr.responseJSON?.message || error));
        }
    });
}

// 加載文章詳情頁面
function loadArticleDetails(articleId) {
    $.ajax({
        url: `/api/articles/${articleId}`,
        method: 'GET',
        success: function (response) {
            if (response.success) {
                const article = response.data;

                // 更新頁面元素
                $('#article-title').text(article.title);
                $('#article-source').text(article.source || '-');
                $('#article-publish-date').text(article.published_at ? new Date(article.published_at).toLocaleString() : '-');

                // 更新AI相關標籤
                if (article.is_ai_related) {
                    $('#ai-related-badge').removeClass('d-none');
                }

                // 更新文章內容
                $('#article-content').html(article.content || '<p class="text-muted">無內容</p>');

                // 更新原始網頁連結
                if (article.url) {
                    $('#article-original-link').attr('href', article.url);
                } else {
                    $('#article-original-link').addClass('disabled');
                }

                // 如果有 AI 分析，顯示相關內容
                if (article.ai_analysis) {
                    $('#ai-analysis-content').html(article.ai_analysis);
                    $('#ai-analysis-container').removeClass('d-none');
                }

                // 註解掉相關文章的加載
                // loadRelatedArticles(articleId);
            } else {
                displayAlert('danger', '加載文章詳情失敗: ' + response.message);
            }
        },
        error: function (xhr, status, error) {
            console.error('加載文章詳情失敗:', error);
            displayAlert('danger', '加載文章詳情失敗: ' + (xhr.responseJSON?.message || error));
        }
    });
}

// 加載相關文章(尚未實作)
// function loadRelatedArticles(articleId) {
//     $.ajax({
//         url: `/api/articles/${articleId}/related`,
//         method: 'GET',
//         success: function (response) {
//             if (response.success && response.data.length > 0) {
//                 const relatedArticles = response.data;
//                 let html = '<ul class="list-group">';

//                 relatedArticles.forEach(article => {
//                     html += `
//                         <li class="list-group-item">
//                             <a href="/articles/${article.id}">${escapeHtml(article.title)}</a>
//                             <small class="d-block text-muted">${article.published_at ? new Date(article.published_at).toLocaleString() : '-'}</small>
//                         </li>
//                     `;
//                 });

//                 html += '</ul>';
//                 $('#related-articles').html(html);
//             }
//         },
//         error: function (xhr, status, error) {
//             console.error('加載相關文章失敗:', error);
//             // 失敗時不顯示錯誤提示，保持原狀
//         }
//     });
// }

// 顯示提示訊息
function displayAlert(type, message) {
    const alertHtml = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;

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

// --- 新增：執行搜尋的函數 ---
function executeSearch(searchTerm) {
    console.log(`執行搜尋: ${searchTerm}`);
    const url = `/api/articles/search?q=${encodeURIComponent(searchTerm)}`;

    // 可以添加加載提示
    // displayLoadingIndicator(); 

    $.ajax({
        url: url,
        method: 'GET',
        success: function (response) {
            // removeLoadingIndicator();
            if (response.success) {
                articles = response.data || []; // API 返回的 data 應該直接是文章列表
                renderArticlesTable(articles);
                // 搜尋結果通常不顯示分頁，或者需要不同的分頁邏輯
                $('#pagination').empty(); // 清除分頁控件
            } else {
                displayAlert('danger', '搜尋文章失敗: ' + response.message);
                renderArticlesTable([]); // 清空表格
                $('#pagination').empty(); // 清除分頁控件
            }
        },
        error: function (xhr, status, error) {
            // removeLoadingIndicator();
            console.error('搜尋文章請求失敗:', error);
            displayAlert('danger', '搜尋文章請求失敗: ' + (xhr.responseJSON?.message || error));
            renderArticlesTable([]); // 清空表格
            $('#pagination').empty(); // 清除分頁控件
        }
    });
}
// --- 新增結束 ---
