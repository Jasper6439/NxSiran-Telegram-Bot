/**
 * NxSiran Mini App - Quota Monitoring Page Module
 * Loads quota data, displays API requests, CPU, memory, network metrics.
 */
(function () {
    'use strict';

    /**
     * Initialize the quota page.
     */
    function init() {
        setupRetryButton();
    }

    /**
     * Called when the quota page is entered.
     */
    function onPageEnter() {
        loadQuota();
    }

    // ===== Load Quota =====
    function loadQuota() {
        var loadingDiv = document.getElementById('quota-loading');
        var errorDiv = document.getElementById('quota-error');
        var contentDiv = document.getElementById('quota-content');

        // Set current month
        var now = new Date();
        var monthNames = ['\u4E00\u6708', '\u4E8C\u6708', '\u4E09\u6708', '\u56DB\u6708', '\u4E94\u6708', '\u516D\u6708',
            '\u4E03\u6708', '\u516B\u6708', '\u4E5D\u6708', '\u5341\u6708', '\u5341\u4E00\u6708', '\u5341\u4E8C\u6708'];
        var monthEl = document.getElementById('quota-month');
        if (monthEl) monthEl.textContent = now.getFullYear() + '\u5E74' + monthNames[now.getMonth()];

        if (loadingDiv) loadingDiv.classList.add('active');
        if (errorDiv) errorDiv.classList.remove('active');
        if (contentDiv) contentDiv.style.display = 'none';

        window.API.quota.get().then(function (data) {
            if (!data.success) throw new Error(data.error || 'API error');

            if (loadingDiv) loadingDiv.classList.remove('active');
            if (contentDiv) contentDiv.style.display = 'block';

            // Parse items array from API
            var items = data.items || [];
            var itemMap = {};
            items.forEach(function (item) { itemMap[item.name] = item; });

            // API Requests
            var apiItem = itemMap['API \u8BF7\u6C42'] || {};
            updateQuotaCard('api', apiItem.used || 0, apiItem.limit || 1, function (v, l) {
                return v.toLocaleString() + ' <span>/ ' + l.toLocaleString() + '</span>';
            });

            // CPU
            var cpuItem = itemMap['CPU \u7528\u91CF'] || {};
            updateQuotaCard('cpu', cpuItem.used || 0, cpuItem.limit || 1, function (v, l) {
                return v.toLocaleString() + ' <span>' + (cpuItem.unit || '') + ' / ' + l.toLocaleString() + (cpuItem.unit || '') + '</span>';
            });

            // Memory
            var memItem = itemMap['\u5185\u5B58\u7528\u91CF'] || {};
            updateQuotaCard('mem', memItem.used || 0, memItem.limit || 1, function (v, l) {
                return v.toLocaleString() + ' <span>' + (memItem.unit || '') + ' / ' + l.toLocaleString() + (memItem.unit || '') + '</span>';
            });

            // Network
            var netItem = itemMap['\u7F51\u7EDC\u6D41\u91CF'] || {};
            updateQuotaCard('net', netItem.used || 0, netItem.limit || 1, function (v, l) {
                return v + ' <span>' + (netItem.unit || '') + ' / ' + l + (netItem.unit || '') + '</span>';
            });

            // AI requests count
            var aiCountEl = document.getElementById('quota-ai-count');
            var imgCountEl = document.getElementById('quota-img-count');
            if (aiCountEl) aiCountEl.innerHTML = (data.ai_requests || 0) + ' <span>\u6B21</span>';
            if (imgCountEl) imgCountEl.innerHTML = (data.image_generations || 0) + ' <span>\u6B21</span>';

            // Overall status
            var statusEl = document.getElementById('quota-overall-status');
            if (statusEl) {
                var statusMap = {
                    ok: '\u2705 \u8FD0\u884C\u6B63\u5E38',
                    warning: '\u26A0\uFE0F \u989D\u5EA6\u504F\u9AD8',
                    critical: '\uD83D\uDD34 \u5373\u5C06\u8017\u5C3D',
                    shutdown: '\uD83D\uDEAB \u5DF2\u505C\u6B62'
                };
                statusEl.textContent = statusMap[data.status] || statusMap['ok'];
                statusEl.className = 'quota-overall-status ' + (data.status || 'ok');
            }
        }).catch(function (error) {
            console.error('Load quota error:', error);
            if (loadingDiv) loadingDiv.classList.remove('active');
            if (errorDiv) {
                var errorText = errorDiv.querySelector('.quota-error-text');
                // Don't show technical error to user
                var userMessage = '\u65E0\u6CD5\u52A0\u8F7D\u989D\u5EA6\u4FE1\u606F\uFF0C\u8BF7\u7A0D\u540E\u91CD\u8BD5';
                if (error.message && error.message.indexOf('\u670D\u52A1\u5668\u54CD\u5E94\u683C\u5F0F\u9519\u8BEF') !== -1) {
                    userMessage = '\u670D\u52A1\u5668\u54CD\u5E94\u5F02\u5E38\uFF0C\u8BF7\u7A0D\u540E\u91CD\u8BD5';
                }
                if (errorText) errorText.textContent = userMessage;
                errorDiv.classList.add('active');
            }
        });
    }

    // ===== Update Quota Card =====
    function updateQuotaCard(id, used, limit, formatFn) {
        var percent = limit > 0 ? Math.min((used / limit) * 100, 100) : 0;
        var status = 'ok';
        if (percent >= 80) status = 'critical';
        else if (percent >= 60) status = 'warning';

        var statusText = { ok: '\u6B63\u5E38', warning: '\u8B66\u544A', critical: '\u5371\u9669' };

        var bar = document.getElementById('quota-' + id + '-bar');
        var valueEl = document.getElementById('quota-' + id + '-value');
        var statusEl = document.getElementById('quota-' + id + '-status');

        if (bar) {
            setTimeout(function () {
                bar.style.width = percent.toFixed(1) + '%';
            }, 100);
            bar.className = 'quota-progress-bar ' + status;
        }

        if (valueEl) valueEl.innerHTML = formatFn(used, limit);

        if (statusEl) {
            statusEl.className = 'quota-status ' + status;
            statusEl.innerHTML = '<div class="quota-status-dot"></div>' + statusText[status];
        }
    }

    // ===== Retry Button =====
    function setupRetryButton() {
        var retryBtn = document.querySelector('#quota-error .btn-retry');
        if (retryBtn) {
            retryBtn.removeAttribute('onclick');
            retryBtn.addEventListener('click', loadQuota);
        }
    }

    // ===== Export =====
    window.QuotaPage = {
        init: init,
        onPageEnter: onPageEnter,
        loadQuota: loadQuota
    };
})();
