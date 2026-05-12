/**
 * NxSiran Mini App - Home Page Module
 * Handles stats display, selfie upload, chatlog import, video import, and auth forms.
 */
(function () {
    'use strict';

    var selectedFiles = [];
    var selectedChatlogFile = null;
    var selectedVideoFile = null;

    /**
     * Initialize the home page.
     */
    function init() {
        setupSelfieUpload();
        setupChatlogImport();
        setupVideoImport();
        setupAuthForms();
        setupQuickActions();
    }

    /**
     * Called when the home page is entered.
     */
    function onPageEnter() {
        loadStats();
        rotateQuote();
    }

    // ===== Quotes =====
    var quotes = [
        '恋爱是两个人的事，但喜欢是一个人的事。',
        '世界上最远的距离，不是生与死，而是我就站在你面前，你却不知道我爱你。',
        '如果你认识从前的我，也许你会原谅现在的我。',
        '人生若只如初见，何事秋风悲画扇。',
        '我行过许多地方的桥，看过许多次数的云，喝过许多种类的酒，却只爱过一个正当最好年龄的人。',
        '于千万人之中遇见你所要遇见的人，于千万年之中，时间的无涯的荒野里，没有早一步，也没有晚一步。',
        '你是一树一树的花开，是燕在梁间呢喃。你是爱，是暖，是希望，你是人间的四月天。',
        '草在结它的种子，风在摇它的叶子。我们站着，不说话，就十分美好。',
        '从前的日色变得慢，车、马、邮件都慢，一生只够爱一个人。',
        '我明白你会来，所以我等。'
    ];

    function showRandomQuote() {
        var container = document.getElementById('quote-display');
        if (!container) return;
        var quote = quotes[Math.floor(Math.random() * quotes.length)];
        container.textContent = '\u300C' + quote + '\u300D';
    }

    function rotateQuote() {
        showRandomQuote();
        setInterval(showRandomQuote, 30000);
    }

    // ===== Stats =====
    function loadStats() {
        if (!window.Auth || !window.Auth.isLoggedIn) return;

        window.API.stats.get().then(function (data) {
            var chatDaysEl = document.getElementById('chat-days-count');
            var chatCountEl = document.getElementById('chat-count');
            var mediaEl = document.getElementById('media-count');
            var userEl = document.getElementById('user-count');
            if (chatDaysEl) chatDaysEl.textContent = data.chat_days || 0;
            if (chatCountEl) chatCountEl.textContent = data.total_messages || 0;
            if (mediaEl) mediaEl.textContent = (data.selfie_count || 0) + (data.user_photo_count || 0);
            if (userEl) userEl.textContent = data.user_photo_count || 0;
        }).catch(function (error) {
            console.error('Load stats error:', error);
        });
    }

    // ===== Chat Days Modal =====
    function showChatDaysModal() {
        var chatDaysEl = document.getElementById('chat-days-count');
        var totalDays = chatDaysEl ? parseInt(chatDaysEl.textContent) || 0 : 0;
        var now = new Date();
        var year = now.getFullYear();
        var month = now.getMonth();
        var daysInMonth = new Date(year, month + 1, 0).getDate();
        var firstDay = new Date(year, month, 1).getDay();

        var modal = document.createElement('div');
        modal.className = 'stats-modal';
        modal.id = 'stats-modal';

        var monthNames = ['一月','二月','三月','四月','五月','六月','七月','八月','九月','十月','十一月','十二月'];

        var html = '<div class="stats-modal-content">' +
            '<div class="stats-modal-header">' +
            '  <h3>' + monthNames[month] + ' ' + year + '</h3>' +
            '  <button class="stats-modal-close" onclick="document.getElementById(\'stats-modal\').remove()">&#10005;</button>' +
            '</div>' +
            '<div class="calendar-grid">';

        ['日','一','二','三','四','五','六'].forEach(function(d) {
            html += '<div class="calendar-day-header">' + d + '</div>';
        });

        for (var i = 0; i < firstDay; i++) {
            html += '<div class="calendar-day empty"></div>';
        }

        var today = now.getDate();
        for (var d = 1; d <= daysInMonth; d++) {
            var isToday = d === today;
            var isActive = d <= today && d > today - 7;
            html += '<div class="calendar-day' + (isToday ? ' today' : '') + (isActive ? ' active' : '') + '">' + d + '</div>';
        }

        html += '</div>' +
            '<div style="text-align:center;margin-top:16px;font-size:13px;color:var(--text-secondary);">累计聊天 ' + totalDays + ' 天</div>' +
            '</div>';
        modal.innerHTML = html;
        document.body.appendChild(modal);
    }

    // ===== Chat Count Modal =====
    function showChatCountModal() {
        var chatCountEl = document.getElementById('chat-count');
        var count = chatCountEl ? parseInt(chatCountEl.textContent) || 0 : 0;
        var modal = document.createElement('div');
        modal.className = 'stats-modal';
        modal.id = 'stats-modal';
        modal.innerHTML =
            '<div class="stats-modal-content">' +
            '  <div class="stats-modal-header">' +
            '    <h3>聊天统计</h3>' +
            '    <button class="stats-modal-close" onclick="document.getElementById(\'stats-modal\').remove()">&#10005;</button>' +
            '  </div>' +
            '  <div class="chat-stats-detail">' +
            '    <div class="detail-item">' +
            '      <span class="detail-label">总消息数</span>' +
            '      <span class="detail-value">' + count + '</span>' +
            '    </div>' +
            '    <p class="detail-note">详细统计功能开发中...</p>' +
            '  </div>' +
            '</div>';
        document.body.appendChild(modal);
    }

    // ===== Selfie Upload =====
    function setupSelfieUpload() {
        var uploadArea = document.getElementById('upload-area');
        var fileInput = document.getElementById('file-input');
        if (!uploadArea || !fileInput) return;

        uploadArea.addEventListener('click', function () {
            fileInput.click();
        });

        uploadArea.addEventListener('dragover', function (e) {
            e.preventDefault();
        });

        uploadArea.addEventListener('drop', function (e) {
            e.preventDefault();
            handleFiles(e.dataTransfer.files);
        });

        fileInput.addEventListener('change', function (e) {
            handleFiles(e.target.files);
        });

        // Wire up upload button
        var uploadBtn = document.getElementById('upload-btn');
        if (uploadBtn) {
            uploadBtn.addEventListener('click', uploadPhotos);
        }
    }

    function handleFiles(files) {
        selectedFiles = Array.from(files).filter(function (f) {
            var type = f.type.toLowerCase();
            var name = f.name.toLowerCase();
            return type.startsWith('image/') ||
                name.endsWith('.jpg') || name.endsWith('.jpeg') ||
                name.endsWith('.png') || name.endsWith('.gif') ||
                name.endsWith('.webp') || name.endsWith('.heic');
        });

        if (selectedFiles.length === 0) {
            window.Toast.show('\u8BF7\u9009\u62E9\u56FE\u7247\u6587\u4EF6', 'error');
            return;
        }

        var previewGrid = document.getElementById('preview-grid');
        var previewSection = document.getElementById('preview-section');
        if (!previewGrid || !previewSection) return;

        previewGrid.innerHTML = '';
        selectedFiles.forEach(function (file, index) {
            var reader = new FileReader();
            reader.onload = function (e) {
                var div = document.createElement('div');
                div.className = 'preview-item';
                div.innerHTML = '<img src="' + e.target.result + '" alt="preview">' +
                    '<button class="remove-btn" data-index="' + index + '">&times;</button>';
                div.querySelector('.remove-btn').addEventListener('click', function (ev) {
                    ev.stopPropagation();
                    removeFile(parseInt(this.getAttribute('data-index')));
                });
                previewGrid.appendChild(div);
            };
            reader.readAsDataURL(file);
        });

        previewSection.classList.add('active');
    }

    function removeFile(index) {
        selectedFiles.splice(index, 1);
        var previewSection = document.getElementById('preview-section');
        var fileInput = document.getElementById('file-input');

        if (selectedFiles.length === 0) {
            if (previewSection) previewSection.classList.remove('active');
        } else {
            if (fileInput) fileInput.value = '';
            handleFiles(selectedFiles);
        }
    }

    function uploadPhotos() {
        if (selectedFiles.length === 0) return;

        var loading = document.getElementById('loading');
        var uploadBtn = document.getElementById('upload-btn');
        if (loading) loading.classList.add('active');
        if (uploadBtn) uploadBtn.disabled = true;

        Promise.all(selectedFiles.map(function (file) {
            return new Promise(function (resolve, reject) {
                var reader = new FileReader();
                reader.onload = function () { resolve(reader.result); };
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
        })).then(function (base64Photos) {
            return window.API.selfies.uploadJSON(base64Photos);
        }).then(function (result) {
            if (result.success) {
                window.Toast.show('\u4E0A\u4F20\u6210\u529F\uFF01', 'success');
                selectedFiles = [];
                var previewSection = document.getElementById('preview-section');
                var fileInput = document.getElementById('file-input');
                if (previewSection) previewSection.classList.remove('active');
                if (fileInput) fileInput.value = '';
                loadStats();
                if (window.GalleryPage) {
                    GalleryPage.loadGallery();
                }
            } else {
                throw new Error(result.error || 'Upload failed');
            }
        }).catch(function (error) {
            console.error('Upload error:', error);
            window.Toast.show('\u4E0A\u4F20\u5931\u8D25\uFF1A' + (error.message || '\u8BF7\u91CD\u8BD5'), 'error');
        }).finally(function () {
            if (loading) loading.classList.remove('active');
            if (uploadBtn) uploadBtn.disabled = false;
        });
    }

    // ===== Chatlog Import =====
    function setupChatlogImport() {
        var chatlogUploadArea = document.getElementById('chatlog-upload-area');
        var chatlogFileInput = document.getElementById('chatlog-file-input');
        var analyzeBtn = document.getElementById('analyze-chatlog-btn');
        if (!chatlogUploadArea || !chatlogFileInput) return;

        chatlogUploadArea.addEventListener('click', function () {
            chatlogFileInput.click();
        });

        chatlogUploadArea.addEventListener('dragover', function (e) {
            e.preventDefault();
        });

        chatlogUploadArea.addEventListener('drop', function (e) {
            e.preventDefault();
            if (e.dataTransfer.files.length > 0) handleChatlogFile(e.dataTransfer.files[0]);
        });

        chatlogFileInput.addEventListener('change', function (e) {
            if (e.target.files.length > 0) handleChatlogFile(e.target.files[0]);
        });

        if (analyzeBtn) {
            analyzeBtn.addEventListener('click', analyzeChatlog);
        }
    }

    function handleChatlogFile(file) {
        selectedChatlogFile = file;
        var filenameEl = document.getElementById('chatlog-filename');
        var previewSection = document.getElementById('chatlog-preview-section');
        if (filenameEl) filenameEl.textContent = file.name;
        if (previewSection) previewSection.classList.add('active');
    }

    function analyzeChatlog() {
        if (!selectedChatlogFile) return;

        var partnerInput = document.getElementById('chat-partner-input');
        var partnerName = (partnerInput ? partnerInput.value.trim() : '') || '\u5BF9\u65B9';

        var loading = document.getElementById('chatlog-loading');
        var analyzeBtn = document.getElementById('analyze-chatlog-btn');
        var loadingText = document.getElementById('chatlog-loading-text');
        if (loading) loading.classList.add('active');
        if (analyzeBtn) analyzeBtn.disabled = true;
        if (loadingText) loadingText.textContent = '\u6B63\u5728\u8BFB\u53D6\u804A\u5929\u8BB0\u5F55...';

        selectedChatlogFile.text().then(function (fileContent) {
            if (loadingText) loadingText.textContent = '\u6B63\u5728\u5206\u6790\u4EBA\u7269\u6027\u683C\u548C\u5173\u7CFB...';
            return window.API.chatlog.analyze(fileContent, partnerName);
        }).then(function (result) {
            if (result.success) {
                window.Toast.show('\u5DF2\u4E86\u89E3' + partnerName + '\uFF01', 'success');
                displayChatlogResult(partnerName, result);

                selectedChatlogFile = null;
                var previewSection = document.getElementById('chatlog-preview-section');
                var chatlogFileInput = document.getElementById('chatlog-file-input');
                if (previewSection) previewSection.classList.remove('active');
                if (chatlogFileInput) chatlogFileInput.value = '';
                if (partnerInput) partnerInput.value = '';
            } else {
                throw new Error(result.error || '\u5206\u6790\u5931\u8D25');
            }
        }).catch(function (error) {
            console.error('Chatlog analysis error:', error);
            window.Toast.show('\u5206\u6790\u5931\u8D25\uFF1A' + (error.message || '\u8BF7\u91CD\u8BD5'), 'error');
        }).finally(function () {
            if (loading) loading.classList.remove('active');
            if (analyzeBtn) analyzeBtn.disabled = false;
        });
    }

    function displayChatlogResult(partnerName, result) {
        var resultDiv = document.getElementById('chatlog-result');
        var contentDiv = document.getElementById('chatlog-result-content');
        if (!resultDiv || !contentDiv) return;

        var analysis = result.analysis || {};
        var esc = window.App ? window.App.escapeHtml : function (s) { return s; };

        var html = '';
        html += '<div class="result-section"><div class="result-section-title">' + esc(partnerName) + '\u7684\u6027\u683C</div>' +
            '<div class="result-section-content">' + esc(analysis.personality || '\u672A\u77E5') + '</div></div>';
        html += '<div class="result-section"><div class="result-section-title">\u4F60\u4EEC\u7684\u5173\u7CFB</div>' +
            '<div class="result-section-content">' + esc(analysis.relationship_pattern || '\u672A\u77E5') + '</div></div>';
        html += '<div class="result-section"><div class="result-section-title">\u5E38\u89C1\u8BDD\u9898</div>' +
            '<div class="result-section-content">' + esc((analysis.common_topics || []).join('\u3001') || '\u672A\u77E5') + '</div></div>';
        html += '<div class="result-section"><div class="result-section-title">\u5173\u5FC3\u65B9\u5F0F</div>' +
            '<div class="result-section-content">' + esc(analysis.care_patterns || '\u672A\u77E5') + '</div></div>';
        html += '<div class="result-badge">\u5206\u6790\u4E86 ' + (result.message_count || 0) + ' \u6761\u6D88\u606F</div>';

        contentDiv.innerHTML = html;
        resultDiv.classList.add('active');
        resultDiv.scrollIntoView({ behavior: 'smooth' });
    }

    // ===== Video Import =====
    function setupVideoImport() {
        var videoUploadArea = document.getElementById('video-upload-area');
        var videoFileInput = document.getElementById('video-file-input');
        var analyzeBtn = document.getElementById('analyze-video-btn');
        if (!videoUploadArea || !videoFileInput) return;

        videoUploadArea.addEventListener('click', function () {
            videoFileInput.click();
        });

        videoFileInput.addEventListener('change', function (e) {
            if (e.target.files.length > 0) {
                selectedVideoFile = e.target.files[0];
                var filenameEl = document.getElementById('video-filename');
                var filesizeEl = document.getElementById('video-filesize');
                var previewSection = document.getElementById('video-preview-section');
                if (filenameEl) filenameEl.textContent = selectedVideoFile.name;
                if (filesizeEl) filesizeEl.textContent = '\u5927\u5C0F: ' + (selectedVideoFile.size / 1024 / 1024).toFixed(1) + ' MB';
                if (previewSection) previewSection.classList.add('active');
            }
        });

        if (analyzeBtn) {
            analyzeBtn.addEventListener('click', analyzeVideo);
        }
    }

    function analyzeVideo() {
        if (!selectedVideoFile) return;

        if (selectedVideoFile.size > 500 * 1024 * 1024) {
            window.Toast.show('\u6587\u4EF6\u592A\u5927\uFF0C\u6700\u5927500MB', 'error');
            return;
        }

        var videoTypeSelect = document.getElementById('video-type-select');
        var videoType = videoTypeSelect ? videoTypeSelect.value : '\u5267\u60C5';

        var loading = document.getElementById('video-loading');
        var analyzeBtn = document.getElementById('analyze-video-btn');
        var loadingText = document.getElementById('video-loading-text');
        if (loading) loading.classList.add('active');
        if (analyzeBtn) analyzeBtn.disabled = true;
        if (loadingText) loadingText.textContent = '\u6B63\u5728\u4E0A\u4F20\u89C6\u9891...';

        var formData = new FormData();
        formData.append('video', selectedVideoFile);
        formData.append('type', videoType);

        window.API.video.analyze(formData).then(function (result) {
            if (result.success) {
                window.Toast.show(videoType + '\u89C6\u9891\u5206\u6790\u5B8C\u6210\uFF01', 'success');
                displayVideoResult(videoType, result);

                selectedVideoFile = null;
                var previewSection = document.getElementById('video-preview-section');
                var videoFileInput = document.getElementById('video-file-input');
                if (previewSection) previewSection.classList.remove('active');
                if (videoFileInput) videoFileInput.value = '';
            } else {
                throw new Error(result.error || '\u5206\u6790\u5931\u8D25');
            }
        }).catch(function (error) {
            console.error('Video analysis error:', error);
            window.Toast.show('\u5206\u6790\u5931\u8D25\uFF1A' + (error.message || '\u8BF7\u91CD\u8BD5'), 'error');
        }).finally(function () {
            if (loading) loading.classList.remove('active');
            if (analyzeBtn) analyzeBtn.disabled = false;
        });
    }

    function displayVideoResult(videoType, result) {
        var resultDiv = document.getElementById('video-result');
        var contentDiv = document.getElementById('video-result-content');
        if (!resultDiv || !contentDiv) return;

        var analysis = result.analysis || {};
        var esc = window.App ? window.App.escapeHtml : function (s) { return s; };

        var html = '';
        html += '<div class="result-section"><div class="result-section-title">\u8BF4\u8BDD\u98CE\u683C</div>' +
            '<div class="result-section-content">' + esc(analysis.speaking_style || '\u672A\u77E5') + '</div></div>';

        var traits = analysis.personality_traits || [];
        if (traits.length) {
            html += '<div class="result-section"><div class="result-section-title">\u6027\u683C\u7279\u70B9</div>' +
                '<div class="result-section-content">' + traits.map(function (t) { return '&bull; ' + esc(t); }).join('<br>') + '</div></div>';
        }

        var catchphrases = analysis.catchphrases || [];
        if (catchphrases.length) {
            html += '<div class="result-section"><div class="result-section-title">\u53E3\u5934\u7985</div>' +
                '<div class="result-section-content">' + esc(catchphrases.join('\u3001')) + '</div></div>';
        }

        if (videoType === '\u5267\u60C5') {
            var dialogues = analysis.key_dialogues || [];
            if (dialogues.length) {
                html += '<div class="result-section"><div class="result-section-title">\u7ECF\u5178\u53F0\u8BCD</div>' +
                    '<div class="result-section-content" style="font-style:italic;">' +
                    dialogues.map(function (d) { return '\u300C' + esc(d) + '\u300D'; }).join('<br>') + '</div></div>';
            }
        }

        html += '<div class="result-section"><div class="result-section-title">\u60C5\u611F\u8868\u8FBE</div>' +
            '<div class="result-section-content">' + esc(analysis.emotional_expression || '\u672A\u77E5') + '</div></div>';
        html += '<div class="result-badge">\u5206\u6790\u7ED3\u679C\u5DF2\u4FDD\u5B58\uFF0C\u8F66\u5982\u4E91\u4F1A\u5B66\u4E60\u8FD9\u4E9B\u8BF4\u8BDD\u98CE\u683C</div>';

        contentDiv.innerHTML = html;
        resultDiv.classList.add('active');
        resultDiv.scrollIntoView({ behavior: 'smooth' });
    }

    // ===== Auth Forms =====
    function setupAuthForms() {
        // Login form submit
        var loginForm = document.getElementById('login-form');
        if (loginForm) {
            // Find the login button (it has onclick="loginUser()" in HTML)
            var loginBtn = loginForm.querySelector('.btn-primary');
            if (loginBtn) {
                loginBtn.removeAttribute('onclick');
                loginBtn.addEventListener('click', handleLogin);
            }
            // Enter key on password field
            var loginPass = document.getElementById('login-password');
            if (loginPass) {
                loginPass.addEventListener('keydown', function (e) {
                    if (e.key === 'Enter') handleLogin();
                });
            }
        }

        // Register form submit
        var registerForm = document.getElementById('register-form');
        if (registerForm) {
            var regBtn = registerForm.querySelector('.btn-primary');
            if (regBtn) {
                regBtn.removeAttribute('onclick');
                regBtn.addEventListener('click', handleRegister);
            }
        }

        // Form switching links
        var showRegLinks = document.querySelectorAll('a[onclick="showRegisterForm()"]');
        showRegLinks.forEach(function (link) {
            link.removeAttribute('onclick');
            link.addEventListener('click', function (e) {
                e.preventDefault();
                if (window.Auth) window.Auth.showRegisterForm();
            });
        });

        var showLoginLinks = document.querySelectorAll('a[onclick="showLoginForm()"]');
        showLoginLinks.forEach(function (link) {
            link.removeAttribute('onclick');
            link.addEventListener('click', function (e) {
                e.preventDefault();
                if (window.Auth) window.Auth.showLoginForm();
            });
        });
    }

    function handleLogin() {
        var usernameEl = document.getElementById('login-username');
        var passwordEl = document.getElementById('login-password');
        var username = usernameEl ? usernameEl.value.trim() : '';
        var password = passwordEl ? passwordEl.value : '';

        if (!username || !password) {
            window.Toast.show('\u8BF7\u8F93\u5165\u7528\u6237\u540D\u548C\u5BC6\u7801', 'error');
            return;
        }

        window.Auth.login(username, password).then(function (result) {
            if (result.success) {
                if (window.App) window.App.updateLoginUI(true);
            } else {
                window.Toast.show(result.error || '\u767B\u5F55\u5931\u8D25', 'error');
            }
        }).catch(function (e) {
            window.Toast.show('\u8FDE\u63A5\u5931\u8D25: ' + e.message, 'error');
        });
    }

    function handleRegister() {
        var usernameEl = document.getElementById('reg-username');
        var passwordEl = document.getElementById('reg-password');
        var chatIdEl = document.getElementById('reg-chatid');
        var username = usernameEl ? usernameEl.value.trim() : '';
        var password = passwordEl ? passwordEl.value : '';
        var chatId = chatIdEl ? chatIdEl.value.trim() : '';

        if (!username || !password || !chatId) {
            window.Toast.show('\u8BF7\u586B\u5199\u6240\u6709\u5FC5\u586B\u9879', 'error');
            return;
        }

        if (password.length < 6) {
            window.Toast.show('\u5BC6\u7801\u957F\u5EA6\u81F3\u5C116\u4F4D', 'error');
            return;
        }

        window.Auth.register(username, password, chatId).then(function (result) {
            if (result.success) {
                if (window.App) window.App.updateLoginUI(true);
            } else {
                window.Toast.show(result.error || '\u6CE8\u518C\u5931\u8D25', 'error');
            }
        }).catch(function (e) {
            window.Toast.show('\u8FDE\u63A5\u5931\u8D25: ' + e.message, 'error');
        });
    }

    // ===== Quick Actions =====
    function setupQuickActions() {
        // Quick action buttons that use switchPage
        var actionBtns = document.querySelectorAll('.action-btn[onclick*="switchPage"]');
        actionBtns.forEach(function (btn) {
            var onclickAttr = btn.getAttribute('onclick');
            var match = onclickAttr.match(/switchPage\('(\w+)'\)/);
            if (match) {
                btn.removeAttribute('onclick');
                btn.addEventListener('click', function () {
                    if (window.App) window.App.navigate(match[1]);
                });
            }
        });

        // Upload quick action
        var uploadQuickBtn = document.querySelector('.action-btn[onclick*="upload-area"]');
        if (uploadQuickBtn) {
            uploadQuickBtn.removeAttribute('onclick');
            uploadQuickBtn.addEventListener('click', function () {
                var fileInput = document.getElementById('file-input');
                if (fileInput) fileInput.click();
            });
        }
    }

    // ===== Export =====
    window.HomePage = {
        init: init,
        onPageEnter: onPageEnter,
        loadStats: loadStats
    };

    // Expose modal functions globally for onclick handlers
    window.showChatDaysModal = showChatDaysModal;
    window.showChatCountModal = showChatCountModal;
})();
