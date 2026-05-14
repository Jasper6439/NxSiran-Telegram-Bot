/* ================================================================
   Global State
   ================================================================ */
let authToken = localStorage.getItem('auth_token');
let isLoginMode = true;
let currentPage = 'home';
let chatHistory = [];
let lastMessageCount = 0;
let syncInterval = null;

/* ================================================================
   Page Title Map
   ================================================================ */
const PAGE_TITLES = {
    home: '首页',
    chat: '聊天',
    farm: '游戏',
    game: '游戏',
    gallery: '多媒体',
    media: '多媒体',
    quota: '监控',
    settings: '设置'
};

/* ================================================================
   Telegram WebApp Integration
   ================================================================ */
const tg = window.Telegram?.WebApp;
let tgUser = null;

// 初始化 Telegram WebApp
function initTelegramWebApp() {
    if (!tg) {
        console.log('Not running in Telegram WebApp');
        return false;
    }
    
    // 初始化
    tg.ready();
    tg.expand();
    
    // 设置颜色主题
    try {
        tg.setHeaderColor('#7B2D8E');
        tg.setBackgroundColor('#EDE7F6');
    } catch (e) {
        console.log('Telegram theme setup failed:', e);
    }
    
    // 获取用户信息
    tgUser = tg.initDataUnsafe?.user;
    if (tgUser) {
        console.log('Telegram user:', tgUser.username || tgUser.id);
        // 自动填充用户名
        localStorage.setItem('telegram_user', JSON.stringify(tgUser));
    }
    
    return true;
}

/* ================================================================
   Initialization
   ================================================================ */
document.addEventListener('DOMContentLoaded', async () => {
    // 初始化 Telegram WebApp
    const isTelegram = initTelegramWebApp();
    
    // 如果在 Telegram 中且有用户信息，尝试自动登录
    if (isTelegram && tgUser) {
        // 使用 Telegram 用户 ID 作为用户标识
        const telegramId = tgUser.id.toString();
        // 尝试自动登录或注册
        await tryTelegramAuth(telegramId);
        return;
    }
    
    // 普通登录流程
    if (authToken) {
        const isValid = await validateToken();
        if (isValid) {
            showApp();
        } else {
            localStorage.removeItem('auth_token');
            authToken = null;
            showLogin();
        }
    } else {
        showLogin();
    }
});

/* ================================================================
   Telegram Auth
   ================================================================ */
async function tryTelegramAuth(telegramId) {
    try {
        // 尝试用 Telegram ID 登录
        const response = await fetch('/api/auth/telegram', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                telegram_id: telegramId,
                username: tgUser.username || tgUser.first_name,
                first_name: tgUser.first_name,
                last_name: tgUser.last_name
            })
        });
        
        const data = await response.json();
        
        if (data.success && data.token) {
            authToken = data.token;
            localStorage.setItem('auth_token', authToken);
            showApp();
        } else {
            // 自动注册
            await registerWithTelegram(telegramId);
        }
    } catch (e) {
        console.error('Telegram auth failed:', e);
        showLogin();
    }
}

async function registerWithTelegram(telegramId) {
    try {
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username: tgUser.username || `tg_${telegramId}`,
                password: telegramId, // 使用 Telegram ID 作为初始密码
                telegram_id: telegramId,
                telegram_username: tgUser.username,
                auto_login: true
            })
        });
        
        const data = await response.json();
        
        if (data.success && data.token) {
            authToken = data.token;
            localStorage.setItem('auth_token', authToken);
            showApp();
        } else {
            showLogin();
        }
    } catch (e) {
        console.error('Telegram register failed:', e);
        showLogin();
    }
}

/* ================================================================
   Auth Functions
   ================================================================ */
function showLogin() {
    document.getElementById('login-screen').classList.remove('hidden');
    document.getElementById('app-shell').classList.remove('active');

    // 恢复记住的账号
    const rememberedUsername = localStorage.getItem('remembered_username');
    if (rememberedUsername) {
        document.getElementById('auth-username').value = rememberedUsername;
        document.getElementById('remember-me').checked = true;
    }
}

async function showApp() {
    try {
        document.getElementById('login-screen').classList.add('hidden');
        document.getElementById('app-shell').classList.add('active');

        // 获取用户信息，检查是否为管理员
        try {
            const response = await fetch('/api/user/profile', {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });
            const data = await response.json();
            if (data.success && data.is_admin) {
                // 显示监控页面
                document.querySelectorAll('.nav-item.admin-only').forEach(el => {
                    el.style.display = '';
                });
            }
        } catch (e) {
            console.error('检查管理员状态失败:', e);
        }

        // 使用 try-catch 包装每个初始化函数，防止一个失败影响其他
        try { loadUserProfile(); } catch (e) { console.error('loadUserProfile failed:', e); }
        try { loadHomeStats(); } catch (e) { console.error('loadHomeStats failed:', e); }
        try { showHomeQuote(); } catch (e) { console.error('showHomeQuote failed:', e); }
        // 恢复上次所在页面
        var savedPage = sessionStorage.getItem('current_page');
        if (savedPage && savedPage !== 'home') {
            navigateTo(savedPage);
        }
    } catch (e) {
        console.error('showApp failed:', e);
        // 如果显示主应用失败，回到登录页
        showLogin();
    }
}

function switchLoginTab(el, mode) {
    isLoginMode = (mode === 'login');
    document.querySelectorAll('.login-tab').forEach(t => t.classList.remove('active'));
    el.classList.add('active');
    document.getElementById('auth-submit-btn').textContent = isLoginMode ? '登录' : '注册';
    document.getElementById('email-group').style.display = isLoginMode ? 'none' : 'block';
    document.getElementById('telegram-group').style.display = isLoginMode ? 'none' : 'block';
    document.getElementById('auth-email').required = !isLoginMode;
    document.getElementById('auth-telegram').required = !isLoginMode;
    document.getElementById('auth-error').textContent = '';
}

function togglePasswordVisibility() {
    const pwd = document.getElementById('auth-password');
    const btn = document.getElementById('pwd-toggle-btn');
    if (pwd.type === 'password') {
        pwd.type = 'text';
        btn.innerHTML = '&#128564;';
    } else {
        pwd.type = 'password';
        btn.innerHTML = '&#128065;';
    }
}

async function validateToken() {
    try {
        const response = await fetch('/api/user/profile', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        return response.ok;
    } catch (e) {
        return false;
    }
}

async function handleAuth(event) {
    event.preventDefault();
    const errorEl = document.getElementById('auth-error');
    errorEl.textContent = '';

    const username = document.getElementById('auth-username').value.trim();
    const password = document.getElementById('auth-password').value;
    const email = document.getElementById('auth-email').value.trim();
    const autoLogin = document.getElementById('auto-login').checked;
    const btn = document.getElementById('auth-submit-btn');

    if (!username || !password) {
        errorEl.textContent = '请输入用户名和密码';
        return;
    }
    if (!isLoginMode && !email) {
        errorEl.textContent = '请输入邮箱';
        return;
    }
    if (!isLoginMode) {
        const telegramId = document.getElementById('auth-telegram').value.trim();
        if (!telegramId) {
            errorEl.textContent = '请输入 Telegram Chat ID';
            return;
        }
        if (!/^\d+$/.test(telegramId)) {
            errorEl.textContent = 'Telegram Chat ID 必须是纯数字';
            return;
        }
    }

    btn.disabled = true;
    btn.textContent = isLoginMode ? '登录中...' : '注册中...';

    try {
        const endpoint = isLoginMode ? '/api/login' : '/api/register';
        const body = isLoginMode
            ? { username, password, auto_login: autoLogin }
            : { email, username, password, telegram_chat_id: document.getElementById('auth-telegram').value.trim() };
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await response.json();

        if (response.ok && data.token) {
            authToken = data.token;
            localStorage.setItem('auth_token', authToken);

            // 自动登录：保存 auto_token
            if (data.auto_token) {
                localStorage.setItem('auto_login_token', data.auto_token);
            }

            // 记住账号
            const rememberMe = document.getElementById('remember-me').checked;
            if (rememberMe) {
                localStorage.setItem('remembered_username', username);
            } else {
                localStorage.removeItem('remembered_username');
            }

            document.getElementById('auth-username').value = '';
            document.getElementById('auth-password').value = '';
            document.getElementById('auth-email').value = '';
            showApp();
        } else {
            let errorMsg = data.error || (isLoginMode ? '登录失败' : '注册失败');
            if (!isLoginMode && errorMsg.includes('已注册')) {
                errorMsg += '，请直接登录';
            }
            errorEl.textContent = errorMsg;
        }
    } catch (e) {
        errorEl.textContent = '网络错误，请稍后重试';
    } finally {
        btn.disabled = false;
        btn.textContent = isLoginMode ? '登录' : '注册';
    }
}

function logout() {
    stopMessageSync();
    authToken = null;
    localStorage.removeItem('auth_token');
    chatHistory = [];
    lastMessageCount = 0;
    document.getElementById('chat-messages').innerHTML = `
        <div class="message bot">
            <div class="message-bubble">...又是你。（低头，不看你）...好吧，既然你来了。直接说话就行。</div>
            <div class="message-time">刚刚</div>
        </div>
    `;
    showLogin();
}

/* ================================================================
   Forgot Password
   ================================================================ */
function showForgotPassword() {
    document.getElementById('forgot-password-modal').style.display = 'block';
    document.getElementById('login-form').style.display = 'none';
}

function hideForgotPassword() {
    document.getElementById('forgot-password-modal').style.display = 'none';
    document.getElementById('login-form').style.display = 'block';
    document.getElementById('reset-code-group').style.display = 'none';
    document.getElementById('new-password-group').style.display = 'none';
    document.getElementById('reset-btn').style.display = 'none';
    document.getElementById('forgot-email').value = '';
    document.getElementById('reset-code').value = '';
    document.getElementById('new-password').value = '';
}

let resetUserId = null;

async function sendResetCode() {
    const email = document.getElementById('forgot-email').value.trim();
    if (!email) {
        alert('请输入邮箱或用户名');
        return;
    }

    try {
        const response = await fetch('/api/forgot-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email_or_username: email })
        });
        const data = await response.json();

        if (data.success) {
            alert('验证码已发送（测试模式：' + data.code + '）');
            document.getElementById('reset-code-group').style.display = 'block';
            document.getElementById('new-password-group').style.display = 'block';
            document.getElementById('reset-btn').style.display = 'block';
        } else {
            alert(data.error || '发送失败');
        }
    } catch (e) {
        alert('网络错误');
    }
}

async function resetPassword() {
    const email = document.getElementById('forgot-email').value.trim();
    const code = document.getElementById('reset-code').value.trim();
    const newPassword = document.getElementById('new-password').value;

    if (!code || !newPassword) {
        alert('请输入验证码和新密码');
        return;
    }

    if (newPassword.length < 6) {
        alert('密码长度至少6位');
        return;
    }

    try {
        // 先验证验证码
        const verifyResponse = await fetch('/api/verify-reset-code', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email_or_username: email, code: code })
        });
        const verifyData = await verifyResponse.json();

        if (!verifyData.success) {
            alert(verifyData.error || '验证码错误');
            return;
        }

        // 重置密码
        const resetResponse = await fetch('/api/reset-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: verifyData.user_id, new_password: newPassword })
        });
        const resetData = await resetResponse.json();

        if (resetData.success) {
            alert('密码重置成功，请用新密码登录');
            hideForgotPassword();
        } else {
            alert(resetData.error || '重置失败');
        }
    } catch (e) {
        alert('网络错误');
    }
}

/* ================================================================
   User Profile
   ================================================================ */
async function loadUserProfile() {
    try {
        const response = await fetch('/api/user/profile', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        if (response.ok) {
            const data = await response.json();
            const name = data.username || '用户';
            document.getElementById('top-navbar-user').textContent = name;
            document.getElementById('home-username').textContent = name;
            document.getElementById('settings-username').textContent = name;
            document.getElementById('settings-userid').textContent = 'ID: ' + (data.chat_id || '--');
            // 填充自定义称呼
            if (data.preferred_name) {
                document.getElementById('cfg-preferred-name').value = data.preferred_name;
            }
        }
    } catch (e) {
        console.log('Failed to load user profile');
    }
}

async function savePreferredName() {
    const input = document.getElementById('cfg-preferred-name');
    const name = input.value.trim();
    if (!name) {
        Toast.show('请输入称呼', 'warning');
        return;
    }
    try {
        const resp = await fetch('/api/user/preferred-name', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
            body: JSON.stringify({ preferred_name: name })
        });
        const data = await resp.json();
        if (data.success) {
            Toast.show(data.message, 'success');
        } else {
            Toast.show(data.error || '保存失败', 'error');
        }
    } catch (e) {
        Toast.show('保存失败', 'error');
    }
}

/* ================================================================
   Home Stats
   ================================================================ */
async function loadHomeStats() {
    try {
        // 加载角色列表到选择器
        const charSelect = document.getElementById('stats-character-select');
        if (charSelect && charSelect.options.length <= 1) {
            try {
                const charResp = await fetch('/api/characters', { headers: { 'Authorization': `Bearer ${authToken}` } });
                const charData = await charResp.json();
                if (charData.success && charData.characters) {
                    charData.characters.forEach(c => {
                        const opt = document.createElement('option');
                        opt.value = c.id;
                        opt.textContent = c.name;
                        charSelect.appendChild(opt);
                    });
                }
            } catch (e) { console.log('Failed to load characters'); }
        }

        const response = await fetch('/api/stats', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        if (response.ok) {
            const data = await response.json();
            document.getElementById('stat-messages').textContent = data.total_messages || 0;
            document.getElementById('stat-days').textContent = data.total_days || 0;
            var mediaTotal = (data.selfie_count || 0) + (data.user_photo_count || 0);
            document.getElementById('stat-selfies').textContent = mediaTotal;
            document.getElementById('stat-intimacy').textContent = data.intimacy_score || 0;

            // 首次加载后自动弹出总消息数详情
            if (!window._hasAutoShownMsgDetail) {
                window._hasAutoShownMsgDetail = true;
                setTimeout(function() { showStatDetail('messages'); }, 600);
            }
        }
    } catch (e) {
        console.log('Failed to load home stats');
    }
}

/* ================================================================
   Home Quote - 从角色API获取名言
   ================================================================ */
var homeQuotes = [];
var cachedCharacterQuotes = null;

function loadQuotesFromCharacter() {
    if (cachedCharacterQuotes && cachedCharacterQuotes.length > 0) {
        homeQuotes = cachedCharacterQuotes;
        showHomeQuote();
        return;
    }
    
    fetch('/api/characters')
        .then(r => r.json())
        .then(data => {
            var chars = data.characters || [];
            var currentId = data.current;
            var char = chars.find(function(c) { return c.id === currentId; }) || chars[0];
            
            if (char && char.quotes && char.quotes.length > 0) {
                cachedCharacterQuotes = char.quotes;
                homeQuotes = char.quotes;
            } else if (char && char.catchphrases && char.catchphrases.length > 0) {
                cachedCharacterQuotes = char.catchphrases;
                homeQuotes = char.catchphrases;
            } else {
                // 回退到默认名言
                cachedCharacterQuotes = getDefaultQuotes();
                homeQuotes = cachedCharacterQuotes;
            }
            showHomeQuote();
        })
        .catch(function() {
            homeQuotes = getDefaultQuotes();
            showHomeQuote();
        });
}

function getDefaultQuotes() {
    return [
        '恋爱是两个人的事，但喜欢是一个人的事。',
        '世界上最远的距离，不是生与死，而是我就站在你面前，你却不知道我爱你。',
        '如果你认识从前的我，也许你会原谅现在的我。',
        '人生若只如初见，何事秋风悲画扇。',
        '我行过许多地方的桥，看过许多次数的云，喝过许多种类的酒，却只爱过一个正当最好年龄的人。',
        '于千万人之中遇见你所要遇见的人，于千万年之中，时间的无涯的荒野里，没有早一步，也没有晚一步。',
        '草在结它的种子，风在摇它的叶子。我们站着，不说话，就十分美好。',
        '从前的日色变得慢，车、马、邮件都慢，一生只够爱一个人。',
        '我明白你会来，所以我等。',
        '你是一树一树的花开，是燕在梁间呢喃。你是爱，是暖，是希望，你是人间的四月天。'
    ];
}

function showHomeQuote() {
    var mainEl = document.getElementById('home-quote-main');
    if (!mainEl) return;
    if (homeQuotes.length === 0) {
        loadQuotesFromCharacter();
        return;
    }
    var q = homeQuotes[Math.floor(Math.random() * homeQuotes.length)];
    mainEl.textContent = '\u300C' + q + '\u300D';
}

/* ================================================================
   Navigation
   ================================================================ */
function navigateTo(pageName) {
    // Redirects
    if (pageName === 'gallery') pageName = 'media';
    if (pageName === 'game') pageName = 'farm';

    currentPage = pageName;
    sessionStorage.setItem('current_page', pageName);

    // Update sidebar active state
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.page === pageName);
    });

    // Hide all pages, show target
    document.querySelectorAll('.content-area .page').forEach(p => {
        p.classList.remove('active');
    });
    const targetPage = document.getElementById('page-' + pageName);
    if (targetPage) {
        targetPage.classList.add('active');
    }

    // Update top navbar title
    document.getElementById('top-navbar-title').textContent = PAGE_TITLES[pageName] || pageName;

    // Close sidebar on mobile
    closeSidebar();

    // Page-specific hooks
    if (pageName === 'chat') {
        loadChatHistory();
        startMessageSync();
    } else {
        stopMessageSync();
    }

    if (pageName === 'quota') {
        if (window.QuotaPage && window.QuotaPage.onPageEnter) window.QuotaPage.onPageEnter();
    }

    if (pageName === 'gallery' || pageName === 'media') {
        if (window.GalleryPage && window.GalleryPage.onPageEnter) window.GalleryPage.onPageEnter();
        loadMediaCharacterSelector(); // 加载角色选择器
        loadGalleryItems();
    }

    if (pageName === 'farm') {
        if (window.FarmPage && window.FarmPage.onPageEnter) window.FarmPage.onPageEnter();
    }

    if (pageName === 'skills') {
        if (window.SkillsPage && window.SkillsPage.onPageEnter) window.SkillsPage.onPageEnter();
    }

    if (pageName === 'game') {
        // Initialize game canvas
        if (typeof initGame === 'function') {
            setTimeout(() => initGame('game-canvas'), 100);
        }
    }

    if (pageName === 'settings') {
        if (window.SettingsPage && window.SettingsPage.onPageEnter) window.SettingsPage.onPageEnter();
        // Load admin status (only Ulysses can see admin config)
        fetch('/api/user/profile', { headers: { 'Authorization': `Bearer ${authToken}` } })
            .then(r => r.json())
            .then(data => {
                if (data.is_admin) {
                    document.getElementById('admin-config-group').style.display = 'block';
                    // 加载管理员配置到表单
                    fetch('/api/config', { headers: { 'Authorization': `Bearer ${authToken}` } })
                        .then(r => r.json())
                        .then(cfg => {
                            if (cfg.telegram_token) document.getElementById('cfg-token').value = cfg.telegram_token;
                            if (cfg.chat_id) document.getElementById('cfg-chatid').value = cfg.chat_id;
                            if (cfg.ai_api_base) document.getElementById('cfg-aibase').value = cfg.ai_api_base;
                            if (cfg.public_url) document.getElementById('cfg-publicurl').value = cfg.public_url;
                            if (cfg.smtp_email) document.getElementById('cfg-smtp-email').value = cfg.smtp_email;
                            // smtp_password 不回显
                        }).catch(() => {});
                }

                // Avatar upload - 使用标志避免重复绑定事件
                var avatarEl = document.getElementById('settings-avatar');
                var avatarInput = document.getElementById('avatar-upload-input');
                if (avatarEl && avatarInput && !avatarEl.dataset.initialized) {
                    avatarEl.dataset.initialized = 'true';
                    avatarEl.addEventListener('click', function() { avatarInput.click(); });
                    avatarInput.addEventListener('change', function(e) {
                        var file = e.target.files[0];
                        if (!file) return;
                        var reader = new FileReader();
                        reader.onload = function(ev) {
                            localStorage.setItem('user_avatar', ev.target.result);
                            avatarEl.style.backgroundImage = 'url(' + ev.target.result + ')';
                            avatarEl.style.backgroundSize = 'cover';
                            avatarEl.style.backgroundPosition = 'center';
                            avatarEl.innerHTML = '';
                        };
                        reader.readAsDataURL(file);
                    });
                }
                // 每次进入页面都恢复头像显示
                var saved = localStorage.getItem('user_avatar');
                if (saved && avatarEl) {
                    avatarEl.style.backgroundImage = 'url(' + saved + ')';
                    avatarEl.style.backgroundSize = 'cover';
                    avatarEl.style.backgroundPosition = 'center';
                    avatarEl.innerHTML = '';
                }

                // Load character bindings - 保留 Token 输入框，只更新状态
                var bindingsList = document.getElementById('character-bindings-list');
                if (bindingsList) {
                    var bindings = data.character_bindings || {};
                    var keys = Object.keys(bindings);

                    // 更新 Token 输入框所在 item 的状态
                    var tokenStatus = document.getElementById('chayewoon-bind-status');
                    if (tokenStatus) {
                        var boundKeys = keys.filter(function(k) { return k !== '__len__'; });
                        if (boundKeys.length > 0) {
                            tokenStatus.textContent = '已绑定 Bot Token ✓';
                            tokenStatus.style.color = 'var(--success)';
                        } else {
                            tokenStatus.textContent = '未绑定';
                            tokenStatus.style.color = 'var(--text-tertiary)';
                        }
                    }
                }

                // 显示已绑定的 Telegram Chat ID
                var chatIdInput = document.getElementById('telegram-chat-id-input');
                var bindStatus = document.getElementById('telegram-bind-status');
                if (chatIdInput && data.telegram_chat_id) {
                    chatIdInput.value = data.telegram_chat_id;
                    if (bindStatus) bindStatus.textContent = '已绑定 Telegram Chat ID: ' + data.telegram_chat_id;
                    if (bindStatus) bindStatus.style.color = 'var(--success)';
                }
            }).catch(function() {
                var bindingsList = document.getElementById('character-bindings-list');
                if (bindingsList) {
                    bindingsList.innerHTML = '<div class="settings-item"><span class="settings-icon">&#128100;</span><span class="settings-label">加载失败</span></div>';
                }
            });
    }
}

// 绑定 Telegram Chat ID
async function bindTelegramChatId() {
    var chatIdInput = document.getElementById('telegram-chat-id-input');
    var bindStatus = document.getElementById('telegram-bind-status');
    if (!chatIdInput) return;
    
    var chatId = chatIdInput.value.trim();
    if (!chatId) {
        if (bindStatus) { bindStatus.textContent = '请输入 Telegram Chat ID'; bindStatus.style.color = 'var(--danger)'; }
        return;
    }
    
    // 验证是否为数字
    if (!/^\d+$/.test(chatId)) {
        if (bindStatus) { bindStatus.textContent = 'Chat ID 必须是纯数字'; bindStatus.style.color = 'var(--danger)'; }
        return;
    }
    
    try {
        var resp = await fetch('/api/user/bind-telegram', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + authToken },
            body: JSON.stringify({ telegram_chat_id: chatId })
        });
        var data = await resp.json();
        if (data.success) {
            if (bindStatus) { bindStatus.textContent = '绑定成功！Chat ID: ' + chatId; bindStatus.style.color = 'var(--success)'; }
            Toast.show('Telegram Chat ID 绑定成功', 'success');
        } else {
            if (bindStatus) { bindStatus.textContent = data.error || '绑定失败'; bindStatus.style.color = 'var(--danger)'; }
        }
    } catch (e) {
        if (bindStatus) { bindStatus.textContent = '网络错误'; bindStatus.style.color = 'var(--danger)'; }
    }
}

// 绑定角色 Bot Token
async function bindCharacterBotToken(characterId) {
    var tokenInput = document.getElementById(characterId + '-bot-token-input');
    var bindStatus = document.getElementById(characterId + '-bind-status');
    if (!tokenInput) return;

    var botToken = tokenInput.value.trim();
    if (!botToken) {
        if (bindStatus) { bindStatus.textContent = '请输入 Bot Token'; bindStatus.style.color = 'var(--danger)'; }
        return;
    }

    if (botToken.indexOf(':') === -1) {
        if (bindStatus) { bindStatus.textContent = 'Token 格式不正确'; bindStatus.style.color = 'var(--danger)'; }
        return;
    }

    try {
        var resp = await fetch('/api/bind-character', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + authToken },
            body: JSON.stringify({ character_id: characterId, bot_token: botToken })
        });
        var data = await resp.json();
        if (data.success) {
            if (bindStatus) { bindStatus.textContent = '绑定成功！'; bindStatus.style.color = 'var(--success)'; }
            Toast.show(data.message || 'Bot Token 绑定成功', 'success');
        } else {
            if (bindStatus) { bindStatus.textContent = data.error || '绑定失败'; bindStatus.style.color = 'var(--danger)'; }
        }
    } catch (e) {
        if (bindStatus) { bindStatus.textContent = '网络错误'; bindStatus.style.color = 'var(--danger)'; }
    }
}

/* ================================================================
   Global Function Proxies (for onclick handlers)
   ================================================================ */
function refreshFarm() {
    if (window.FarmPage && window.FarmPage.refreshFarm) window.FarmPage.refreshFarm();
}

function sendGameChat() {
    if (window.FarmPage && window.FarmPage.sendGameChat) window.FarmPage.sendGameChat();
    else if (window.FarmPage) console.log('FarmPage.sendGameChat not available');
}

function claimDaily() {
    if (window.FarmPage && window.FarmPage.claimDaily) window.FarmPage.claimDaily();
}

function loadQuota() {
    if (window.QuotaPage && window.QuotaPage.loadQuota) window.QuotaPage.loadQuota();
}

function saveConfig() {
    if (window.SettingsPage && window.SettingsPage.saveConfig) window.SettingsPage.saveConfig();
}

function linkTelegram() {
    if (window.SettingsPage && window.SettingsPage.linkTelegram) window.SettingsPage.linkTelegram();
}

/* ================================================================
   Sidebar (Mobile)
   ================================================================ */
function openSidebar() {
    document.getElementById('sidebar').classList.add('open');
    const overlay = document.getElementById('sidebar-overlay');
    overlay.classList.add('active');
    // Force reflow for transition
    overlay.offsetHeight;
    overlay.classList.add('visible');
}

function closeSidebar() {
    document.getElementById('sidebar').classList.remove('open');
    const overlay = document.getElementById('sidebar-overlay');
    overlay.classList.remove('visible');
    setTimeout(() => {
        overlay.classList.remove('active');
    }, 250);
}

/* ================================================================
   Chat Functions
   ================================================================ */
function getAuthHeaders() {
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
    };
}

async function sendMessage() {
    const input = document.getElementById('chat-message-input');
    const message = input.value.trim();
    if (!message) return;

    addMessage(message, 'user');
    input.value = '';
    closeEmojiPicker();

    document.getElementById('chat-typing').style.display = 'block';
    document.getElementById('chat-status-text').textContent = '正在输入...';

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ message })
        });

        if (response.status === 401) { logout(); return; }

        const data = await response.json();
        document.getElementById('chat-typing').style.display = 'none';
        document.getElementById('chat-status-text').textContent = '在线';

        const replyText = data.response || data.reply;
        if (replyText) addMessage(replyText, 'bot');
        // 自动发自拍
        if (data.selfie) {
            var img = document.createElement('img');
            img.src = 'data:image/jpeg;base64,' + data.selfie;
            img.style.cssText = 'max-width:200px;border-radius:var(--radius-md);margin-top:8px;';
            var msgEl = document.querySelector('#chat-messages .chat-message:last-child .chat-bubble');
            if (msgEl) msgEl.appendChild(img);
        }
        lastMessageCount += 2;
    } catch (e) {
        document.getElementById('chat-typing').style.display = 'none';
        document.getElementById('chat-status-text').textContent = '在线';
        addMessage('...（沉默了一会儿）连接出了点问题。', 'bot');
    }
}

// ================================================================
// Emoji Picker
// ================================================================
var EMOJI_CATEGORIES = [
    { name: '笑脸', emojis: ['😀','😃','😄','😁','😆','😅','🤣','😂','🙂','😊','😇','🥰','😍','🤩','😘','😗','😚','😋','😛','😜','🤪','😝','🤑','🤗','🤭','🤫','🤔','🤐','🤨','😐','😑','😶','😏','😒','🙄','😬','🤥','😌','😔','😪','🤤','😴','😷','🤒','🤕'] },
    { name: '爱心', emojis: ['❤️','🧡','💛','💚','💙','💜','🖤','🤍','🤎','💔','❣','💕','💞','💓','💗','💖','💘','💝','💟','♥'] },
    { name: '手势', emojis: ['👍','👎','👊','✊','🤛','🤜','🤝','👏','🙌','🤲','🙏','💪','🤳','✌','🤞','🤟','🤘','🤙','👈','👉','👆','👇','☝'] },
    { name: '物品', emojis: ['💎','💰','🎁','🎀','🎈','🎉','🎊','🏆','🥇','🥈','🥉','⭐','🌟','✨','💫','🔥','💥','💢','💦','💨','🕐','💭','💬','📱','📷','🎵','🎶'] },
    { name: '食物', emojis: ['🍎','🍊','🍋','🍌','🍉','🍇','🍓','🫐','🍒','🍑','🥭','🍍','🥝','🍅','🥕','🌽','🍕','🍔','🍟','🌭','🍿','🍩','🍪','🎂','🍰','🧁','🍫','🍬','🍭'] },
    { name: '动物', emojis: ['🐶','🐱','🐭','🐹','🐰','🦊','🐻','🐼','🐨','🐯','🦁','🐮','🐷','🐸','🐵','🐔','🐧','🐦','🐤','🦆','🦅','🦉','🦇','🐺','🐗','🐴','🦄','🐝','🐛','🦋','🐌'] }
];

var currentEmojiCategory = 0;

function initEmojiPicker() {
    var tabsContainer = document.getElementById('emoji-tabs');
    if (!tabsContainer) return;
    
    tabsContainer.innerHTML = EMOJI_CATEGORIES.map(function(cat, i) {
        return '<div class="emoji-tab' + (i === 0 ? ' active' : '') + '" data-cat="' + i + '" onclick="switchEmojiCategory(' + i + ')">' + cat.name + '</div>';
    }).join('');
    
    renderEmojiGrid(0);
}

function toggleEmojiPicker() {
    var picker = document.getElementById('emoji-picker');
    if (!picker) return;
    
    if (picker.style.display === 'none') {
        picker.style.display = 'flex';
        if (document.getElementById('emoji-tabs').innerHTML === '') {
            initEmojiPicker();
        }
    } else {
        picker.style.display = 'none';
    }
}

function closeEmojiPicker() {
    var picker = document.getElementById('emoji-picker');
    if (picker) picker.style.display = 'none';
}

// 点击表情面板外部自动关闭
document.addEventListener('click', function(e) {
    var picker = document.getElementById('emoji-picker');
    var btn = document.getElementById('chat-emoji-btn');
    if (picker && picker.style.display !== 'none') {
        if (!picker.contains(e.target) && (!btn || !btn.contains(e.target))) {
            picker.style.display = 'none';
        }
    }
});

function switchEmojiCategory(index) {
    currentEmojiCategory = index;
    
    document.querySelectorAll('.emoji-tab').forEach(function(tab, i) {
        tab.classList.toggle('active', i === index);
    });
    
    renderEmojiGrid(index);
}

function renderEmojiGrid(categoryIndex) {
    var grid = document.getElementById('emoji-grid');
    if (!grid) return;
    
    var category = EMOJI_CATEGORIES[categoryIndex];
    if (!category) return;
    
    grid.innerHTML = category.emojis.map(function(emoji) {
        return '<span class="emoji-item" onclick="insertEmoji(\'' + emoji + '\')">' + emoji + '</span>';
    }).join('');
}

function insertEmoji(emoji) {
    var input = document.getElementById('chat-message-input');
    if (!input) return;
    
    var currentValue = input.value;
    var cursorPos = input.selectionStart || currentValue.length;
    input.value = currentValue.substring(0, cursorPos) + emoji + currentValue.substring(cursorPos);
    
    var newPos = cursorPos + emoji.length;
    input.setSelectionRange(newPos, newPos);
    input.focus();
}

async function syncMessages() {
    try {
        const response = await fetch(`/api/messages/sync?since=${lastMessageCount}`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        if (response.status === 401) { logout(); return; }
        const data = await response.json();
        if (data.messages && data.messages.length > 0) {
            data.messages.forEach(msg => {
                addMessage(msg.content, msg.role === 'user' ? 'user' : 'bot');
            });
            lastMessageCount = data.total_count || lastMessageCount + data.messages.length;
        }
    } catch (e) {
        console.log('Message sync failed:', e);
    }
}

async function loadChatHistory() {
    try {
        const response = await fetch('/api/messages/history?limit=50', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        if (response.status === 401) { logout(); return; }
        const data = await response.json();
        if (data.messages && data.messages.length > 0) {
            const container = document.getElementById('chat-messages');
            container.innerHTML = '';
            data.messages.forEach(msg => {
                addMessage(msg.content, msg.role === 'user' ? 'user' : 'bot');
            });
            lastMessageCount = data.messages.length;
        }
    } catch (e) {
        console.log('Failed to load chat history');
    }
}

function startMessageSync() {
    if (syncInterval) clearInterval(syncInterval);
    syncInterval = setInterval(syncMessages, 3000);
}

function stopMessageSync() {
    if (syncInterval) {
        clearInterval(syncInterval);
        syncInterval = null;
    }
}

function addMessage(text, sender) {
    const container = document.getElementById('chat-messages');
    const now = new Date();
    const timeStr = now.getHours().toString().padStart(2, '0') + ':' +
                   now.getMinutes().toString().padStart(2, '0');
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${sender}`;
    msgDiv.innerHTML = `
        <div class="message-bubble">${escapeHtml(text)}</div>
        <div class="message-time">${timeStr}</div>
    `;
    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/* ================================================================
   Gallery Lightbox
   ================================================================ */
function openLightbox(src) {
    const lightbox = document.getElementById('gallery-lightbox');
    document.getElementById('lightbox-image').src = src;
    lightbox.classList.add('lightbox-visible');
    lightbox.style.display = 'flex';
}

function closeLightbox() {
    const lightbox = document.getElementById('gallery-lightbox');
    lightbox.classList.remove('lightbox-visible');
    lightbox.style.display = 'none';
    document.getElementById('lightbox-image').src = '';
    currentLightboxFilename = '';
    currentLightboxCharacterId = '';
}

var currentLightboxFilename = '';
var currentLightboxCharacterId = '';

function openLightbox(src, filename, characterId) {
    currentLightboxFilename = filename || '';
    currentLightboxCharacterId = characterId || '';
    const lightbox = document.getElementById('gallery-lightbox');
    document.getElementById('lightbox-image').src = src;
    lightbox.classList.add('lightbox-visible');
    lightbox.style.display = 'flex';
}

async function deleteLightboxPhoto() {
    if (!currentLightboxFilename) return;
    if (!confirm('确定要删除这张照片吗？')) return;

    try {
        const resp = await fetch('/api/delete-selfie', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
            body: JSON.stringify({ filename: currentLightboxFilename, character_id: currentLightboxCharacterId || null })
        });
        const data = await resp.json();
        if (data.success) {
            closeLightbox();
            loadGalleryItems();
            Toast.show('已删除', 'success');
        } else {
            Toast.show(data.error || '删除失败', 'error');
        }
    } catch (e) {
        Toast.show('删除失败', 'error');
    }
}

async function deletePhoto(filename, characterId) {
    if (!confirm('确定要删除这张照片吗？')) return;
    try {
        const resp = await fetch('/api/delete-selfie', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
            body: JSON.stringify({ filename: filename, character_id: characterId || null })
        });
        const data = await resp.json();
        if (data.success) {
            loadGalleryItems();
            Toast.show('已删除', 'success');
        } else {
            Toast.show(data.error || '删除失败', 'error');
        }
    } catch (e) {
        Toast.show('删除失败', 'error');
    }
}

// 点击背景关闭 lightbox
document.addEventListener('click', function(e) {
    const lightbox = document.getElementById('gallery-lightbox');
    if (e.target === lightbox) closeLightbox();
});

// ESC 关闭 lightbox
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeLightbox();
});

/* ================================================================
   Photo Upload (Home Page)
   ================================================================ */
document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('home-file-input');
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            const files = e.target.files;
            if (!files.length) return;
            const previewSection = document.getElementById('home-preview-section');
            const previewGrid = document.getElementById('home-preview-grid');
            previewGrid.innerHTML = '';
            previewSection.classList.add('active');
            Array.from(files).forEach(file => {
                const reader = new FileReader();
                reader.onload = (ev) => {
                    const item = document.createElement('div');
                    item.className = 'preview-item';
                    item.innerHTML = `<img src="${ev.target.result}" alt="Preview"><button class="remove-btn" onclick="this.parentElement.remove()">&times;</button>`;
                    previewGrid.appendChild(item);
                };
                reader.readAsDataURL(file);
            });
        });
    }
});

async function uploadPhotos() {
    const fileInput = document.getElementById('home-file-input');
    if (!fileInput.files.length) return;
    const loading = document.getElementById('home-upload-loading');
    loading.classList.add('active');
    try {
        // Convert files to base64
        const photos = await Promise.all(
            Array.from(fileInput.files).map(file => {
                return new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onload = (e) => resolve(e.target.result);
                    reader.onerror = reject;
                    reader.readAsDataURL(file);
                });
            })
        );

        const response = await fetch('/api/upload-selfies', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({ photos, character_id: 'chayewoon' })
        });
        if (response.ok) {
            const data = await response.json();
            if (data.success) {
                if (typeof showToast === 'function') Toast.show('上传成功', 'success');
                // 上传成功后刷新相册
                loadGalleryItems();
            } else {
                if (typeof showToast === 'function') Toast.show(data.error || '上传失败', 'error');
            }
            document.getElementById('home-preview-section').classList.remove('active');
            document.getElementById('home-preview-grid').innerHTML = '';
            fileInput.value = '';
            loadHomeStats();
        } else if (response.status === 401) {
            logout();
        } else {
            if (typeof showToast === 'function') Toast.show('上传失败', 'error');
        }
    } catch (e) {
        console.error('Upload error:', e);
        if (typeof showToast === 'function') Toast.show('网络错误', 'error');
    } finally {
        loading.classList.remove('active');
    }
}

/* ================================================================
   Settings Helpers
   ================================================================ */
async function saveConfig() {
    const token = document.getElementById('cfg-token').value.trim();
    const chatid = document.getElementById('cfg-chatid').value.trim();
    const aikey = document.getElementById('cfg-aikey').value.trim();
    const aibase = document.getElementById('cfg-aibase').value.trim();
    const publicurl = document.getElementById('cfg-publicurl').value.trim();
    const newpass = document.getElementById('cfg-newpass').value;
    const smtpEmail = document.getElementById('cfg-smtp-email').value.trim();
    const smtpPassword = document.getElementById('cfg-smtp-password').value.trim();

    try {
        const body = {};
        if (token) body.bot_token = token;
        if (chatid) body.chat_id = chatid;
        if (aikey) body.ai_api_key = aikey;
        if (aibase) body.ai_api_base = aibase;
        if (publicurl) body.public_url = publicurl;
        if (newpass) body.new_password = newpass;
        if (smtpEmail) body.smtp_email = smtpEmail;
        if (smtpPassword) body.smtp_password = smtpPassword;

        if (Object.keys(body).length === 0) {
            Toast.show('没有需要保存的配置', 'warning');
            return;
        }

        const response = await fetch('/api/config', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify(body)
        });
        const result = await response.json();
        if (response.ok && result.success) {
            Toast.show('配置已保存', 'success');
        } else {
            Toast.show(result.error || '保存失败', 'error');
        }
    } catch (e) {
        console.error('saveConfig error:', e);
        Toast.show('网络错误', 'error');
    }
}

/* ================================================================
   Farm Tab Switch
   ================================================================ */
function switchFarmTab(tab) {
    const dataView = document.getElementById('farm-data-view');
    const gameView = document.getElementById('farm-game-view');
    const tabData = document.getElementById('farm-tab-data');
    const tabGame = document.getElementById('farm-tab-game');
    if (tab === 'game') {
        if (dataView) dataView.style.display = 'none';
        if (gameView) gameView.style.display = 'block';
        if (tabGame) { tabGame.style.background = 'var(--purple)'; tabGame.style.color = '#fff'; }
        if (tabData) { tabData.style.background = 'transparent'; tabData.style.color = 'var(--text-secondary)'; }
        // Init game
        if (typeof initGame === 'function') {
            setTimeout(() => initGame('game-canvas'), 100);
        }
    } else {
        if (dataView) dataView.style.display = 'block';
        if (gameView) gameView.style.display = 'none';
        if (tabData) { tabData.style.background = 'var(--purple)'; tabData.style.color = '#fff'; }
        if (tabGame) { tabGame.style.background = 'transparent'; tabGame.style.color = 'var(--text-secondary)'; }
    }
}

/* ================================================================
   Media Tab Switch & Character Selector
   ================================================================ */

// 加载角色列表到选择器
async function loadMediaCharacterSelector() {
    const select = document.getElementById('media-character-select');
    if (!select) return;

    try {
        const response = await fetch('/api/characters', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        const data = await response.json();

        if (data.success && data.characters) {
            // 保留第一个选项（全部角色）
            select.innerHTML = '<option value="">全部角色</option>';
            data.characters.forEach(char => {
                const option = document.createElement('option');
                option.value = char.id;
                option.textContent = char.name || char.id;
                select.appendChild(option);
            });
        }
    } catch (e) {
        console.error('加载角色列表失败:', e);
    }
}

// 角色选择变化处理
function onMediaCharacterChange() {
    const select = document.getElementById('media-character-select');
    const targetSpan = document.getElementById('upload-target-character');
    const uploadView = document.getElementById('media-upload-view');
    const galleryView = document.getElementById('media-gallery-view');
    const tabsDiv = document.getElementById('media-tabs');
    const hintDiv = document.getElementById('all-characters-hint');

    if (select && targetSpan) {
        const charName = select.value ? select.options[select.selectedIndex].text : '全部角色';
        targetSpan.textContent = charName;
    }

    // 全部角色模式：隐藏上传，显示提示，自动切换到相册
    if (!select || !select.value) {
        if (uploadView) uploadView.style.display = 'none';
        if (galleryView) galleryView.style.display = 'block';
        if (tabsDiv) tabsDiv.style.display = 'none';
        if (hintDiv) hintDiv.style.display = 'block';
    } else {
        // 具体角色模式：显示上传和标签页
        if (uploadView) uploadView.style.display = 'block';
        if (galleryView) galleryView.style.display = 'none';
        if (tabsDiv) tabsDiv.style.display = 'flex';
        if (hintDiv) hintDiv.style.display = 'none';
    }

    // 刷新相册以显示选中角色的内容
    loadGalleryItems();
}

function switchMediaTab(tab) {
    const uploadView = document.getElementById('media-upload-view');
    const galleryView = document.getElementById('media-gallery-view');
    const tabUpload = document.getElementById('media-tab-upload');
    const tabGallery = document.getElementById('media-tab-gallery');
    if (tab === 'gallery') {
        if (uploadView) uploadView.style.display = 'none';
        if (galleryView) galleryView.style.display = 'block';
        if (tabGallery) { tabGallery.style.background = 'var(--purple)'; tabGallery.style.color = '#fff'; }
        if (tabUpload) { tabUpload.style.background = 'transparent'; tabUpload.style.color = 'var(--text-secondary)'; }
        loadGalleryItems();
    } else {
        if (uploadView) uploadView.style.display = 'block';
        if (galleryView) galleryView.style.display = 'none';
        if (tabUpload) { tabUpload.style.background = 'var(--purple)'; tabUpload.style.color = '#fff'; }
        if (tabGallery) { tabGallery.style.background = 'transparent'; tabGallery.style.color = 'var(--text-secondary)'; }
    }
}

/* ================================================================
   Upload Functions
   ================================================================ */
function triggerUpload(type) {
    const input = document.createElement('input');
    input.type = 'file';
    if (type === 'photo') {
        input.accept = 'image/*';
        input.multiple = true;
    } else if (type === 'video') {
        input.accept = 'video/*';
    } else if (type === 'chatlog') {
        input.accept = '.txt,.csv,.json';
    }
    input.onchange = (e) => handleUpload(e.target.files, type);
    input.click();
}

async function handleUpload(files, type) {
    if (!files || !files.length) return;
    const progress = document.getElementById('upload-progress');
    const progressBar = document.getElementById('upload-progress-bar');
    const statusText = document.getElementById('upload-status-text');
    if (progress) progress.style.display = 'block';
    if (statusText) statusText.textContent = '上传中...';
    if (progressBar) progressBar.style.width = '30%';
    try {
        if (type === 'photo') {
            if (statusText) statusText.textContent = '处理照片...';
            const photos = await Promise.all(Array.from(files).map(f => new Promise((r, j) => { const rd = new FileReader(); rd.onload = e => r(e.target.result); rd.onerror = j; rd.readAsDataURL(f); })));
            if (progressBar) progressBar.style.width = '60%';
            const resp = await fetch('/api/upload-selfies', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` }, body: JSON.stringify({ photos }) });
            if (progressBar) progressBar.style.width = '100%';
            if (resp.ok) { if (statusText) statusText.textContent = '✅ 照片上传成功'; }
            else { if (statusText) statusText.textContent = '❌ 上传失败'; }
        } else if (type === 'video') {
            if (statusText) statusText.textContent = '上传视频中...';
            const formData = new FormData();
            formData.append('video', files[0]);
            if (progressBar) progressBar.style.width = '50%';
            const resp = await fetch('/api/analyze-video', { method: 'POST', headers: { 'Authorization': `Bearer ${authToken}` }, body: formData });
            if (progressBar) progressBar.style.width = '100%';
            if (resp.ok) { if (statusText) statusText.textContent = '✅ 视频上传成功'; }
            else { if (statusText) statusText.textContent = '❌ 上传失败'; }
        } else if (type === 'chatlog') {
            if (statusText) statusText.textContent = '分析聊天记录...';
            const text = await files[0].text();
            if (progressBar) progressBar.style.width = '50%';
            const resp = await fetch('/api/analyze-chatlog', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` }, body: JSON.stringify({ content: text, partner: '对方' }) });
            if (progressBar) progressBar.style.width = '100%';
            if (resp.ok) { if (statusText) statusText.textContent = '✅ 聊天记录分析成功'; }
            else { if (statusText) statusText.textContent = '❌ 上传失败'; }
        }
        setTimeout(() => { if (progress) progress.style.display = 'none'; }, 2000);
    } catch (e) {
        if (statusText) statusText.textContent = '❌ 上传出错: ' + e.message;
        setTimeout(() => { if (progress) progress.style.display = 'none'; }, 3000);
    }
}

/* ================================================================
   Load Gallery Items
   ================================================================ */
async function loadGalleryItems() {
    const grid = document.getElementById('gallery-grid');
    const loading = document.getElementById('gallery-loading');
    const countEl = document.getElementById('gallery-count');
    if (!grid) return;
    if (loading) loading.classList.add('active');
    grid.innerHTML = '';
    try {
        // 同时获取 _shared 和 chayewoon 的自拍
        const [sharedResp, charResp] = await Promise.all([
            fetch('/api/selfies', { headers: { 'Authorization': `Bearer ${authToken}` } }),
            fetch('/api/selfies?character_id=chayewoon', { headers: { 'Authorization': `Bearer ${authToken}` } })
        ]);
        const sharedData = await sharedResp.json();
        const charData = await charResp.json();

        const sharedItems = sharedData.photos || sharedData.items || [];
        const charItems = charData.photos || charData.items || [];

        // 合并去重（按 filename）
        const seen = new Set();
        const items = [];
        for (const item of [...charItems, ...sharedItems]) {
            const fn = item.filename || item.name || '';
            if (fn && !seen.has(fn)) {
                seen.add(fn);
                items.push(item);
            }
        }

        if (loading) loading.classList.remove('active');
        if (countEl) countEl.textContent = items.length + ' 项';
        if (items.length === 0) {
            grid.innerHTML = '<div class="empty-state"><div class="empty-state-illustration">📷</div><div class="empty-state-title">还没有内容</div><div class="empty-state-description">切换到上传页添加照片、视频或聊天记录</div></div>';
            return;
        }
        grid.innerHTML = items.map(item => {
            const url = item.url || item.thumbnail || item;
            const filename = item.filename || item.name || '';
            const characterId = item.character_id || '';
            // 添加 token 到 URL，用于图片身份验证
            const urlWithToken = url + (url.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(authToken);
            const fnEsc = filename.replace(/'/g, "\\'");
            const chEsc = characterId.replace(/'/g, "\\'");
            return `<div class="photo-item" data-type="photo" style="aspect-ratio:1; background:var(--bg-tertiary); border-radius:var(--radius-md); overflow:hidden; cursor:pointer; position:relative;">
                <img src="${urlWithToken}" alt="${filename}" style="width:100%; height:100%; object-fit:cover;" onerror="this.parentElement.style.display='none'" onclick="openLightbox('${urlWithToken}','${fnEsc}','${chEsc}')">
                <button onclick="event.stopPropagation(); deletePhoto('${fnEsc}','${chEsc}')" style="position:absolute;top:4px;right:4px;width:24px;height:24px;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.5);color:#fff;border-radius:50%;font-size:12px;cursor:pointer;border:none;opacity:0;transition:opacity 0.2s;" onmouseenter="this.style.opacity=1" onmouseleave="this.style.opacity=0" title="删除">&#10005;</button>
            </div>`;
        }).join('');
    } catch (e) {
        if (loading) loading.classList.remove('active');
        grid.innerHTML = '<div class="empty-state"><div class="empty-state-illustration">⚠️</div><div class="empty-state-title">加载失败</div></div>';
    }
}

/* ================================================================
   Chat Days Calendar Modal
   ================================================================ */
function showChatDaysModal() {
    // 先关闭其他统计详情 modal
    document.getElementById('stat-detail-modal').style.display = 'none';

    // 如果已存在，先移除旧的
    var existing = document.getElementById('chat-days-calendar');
    if (existing) {
        existing.remove();
        return; // 再次点击关闭
    }

    var now = new Date();
    var year = now.getFullYear();
    var month = now.getMonth();
    var daysInMonth = new Date(year, month + 1, 0).getDate();
    var firstDay = new Date(year, month, 1).getDay();
    var today = now.getDate();

    var monthNames = ['一月','二月','三月','四月','五月','六月','七月','八月','九月','十月','十一月','十二月'];

    var html = '<div id="chat-days-calendar" style="margin-top:var(--space-4);background:var(--card-bg);border-radius:var(--radius-lg);padding:var(--space-4);box-shadow:var(--shadow-sm);">';
    html += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--space-3);">';
    html += '<div class="section-title" style="margin-bottom:0;"><span class="section-title-text">📅 ' + monthNames[month] + ' ' + year + '</span></div>';
    html += '<button onclick="document.getElementById(\'chat-days-calendar\').remove()" style="background:none;border:none;font-size:1.2rem;cursor:pointer;color:var(--text-secondary);">&times;</button>';
    html += '</div>';
    html += '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:4px;text-align:center;">';

    ['日','一','二','三','四','五','六'].forEach(function(d) {
        html += '<div style="font-size:12px;color:var(--text-tertiary);padding:8px 0;font-weight:500;">' + d + '</div>';
    });

    for (var i = 0; i < firstDay; i++) {
        html += '<div></div>';
    }

    for (var d = 1; d <= daysInMonth; d++) {
        var isToday = d === today;
        var style = 'aspect-ratio:1;display:flex;align-items:center;justify-content:center;border-radius:50%;font-size:14px;';
        if (isToday) {
            style += 'background:var(--purple);color:#fff;font-weight:600;';
        } else {
            style += 'color:var(--text-primary);';
        }
        html += '<div style="' + style + '">' + d + '</div>';
    }

    html += '</div></div>';

    // Insert after stats grid
    var statsGrid = document.getElementById('home-stats');
    if (statsGrid) {
        statsGrid.insertAdjacentHTML('afterend', html);
    }
}

/* ================================================================
   Stat Detail
   ================================================================ */
function showStatDetail(type) {
    // 先关闭日历 modal
    var calendar = document.getElementById('chat-days-calendar');
    if (calendar) calendar.remove();

    const modal = document.getElementById('stat-detail-modal');
    const title = document.getElementById('stat-detail-title');
    const content = document.getElementById('stat-detail-content');
    if (!modal) return;
    modal.style.display = 'block';
    const titles = { messages: '💬 消息详情', selfies: '🎓 学习数据详情', intimacy: '❤️ 亲密度详情' };
    title.textContent = titles[type] || '详情';
    content.textContent = '加载中...';
    fetch('/api/stats', { headers: { 'Authorization': `Bearer ${authToken}` } })
        .then(r => r.json())
        .then(data => {
            if (type === 'messages') {
                content.innerHTML = `<div style="line-height:2">总消息: <b>${data.total_messages || 0}</b><br>今日: <b>${data.today_count || 0}</b><br>聊天天数: <b>${data.total_days || 0}</b><br>平均每日: <b>${data.avg_daily || '--'}</b><br>你的平均长度: <b>${data.user_avg_len || '--'}</b><br>主动发起: <b>${data.user_initiative || '--'}</b></div>`;
            } else if (type === 'selfies') {
                // 学习数据：照片 + 视频 + 聊天记录
                content.innerHTML = `<div style="line-height:2">
                    <div style="margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid var(--border-color);"><b>📷 照片</b></div>
                    自拍照片: <b>${data.selfie_count || 0}</b><br>
                    用户照片: <b>${data.user_photo_count || 0}</b><br><br>
                    <div style="margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid var(--border-color);"><b>🎬 视频</b></div>
                    视频数量: <b>${data.video_count || 0}</b><br><br>
                    <div style="margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid var(--border-color);"><b>💬 聊天记录</b></div>
                    导入记录: <b>${data.chatlog_count || 0}</b>
                </div>`;
            } else if (type === 'intimacy') {
                content.innerHTML = `<div style="line-height:2">亲密度: <b>${data.intimacy_score || 0}</b><br>等级: <b>${data.intimacy_level || '--'}</b><br>关心次数: <b>${data.caring_count || 0}</b><br>吃醋次数: <b>${data.jealous_count || 0}</b><br>温暖次数: <b>${data.warm_count || 0}</b></div>`;
            }
        })
        .catch(() => { content.textContent = '加载失败'; });
}

/* ================================================================
   Media Filter
   ================================================================ */
function filterMedia(type) {
    document.querySelectorAll('.media-filter-btn').forEach(btn => {
        if (btn.dataset.filter === type) {
            btn.style.background = 'var(--purple)';
            btn.style.color = '#fff';
        } else {
            btn.style.background = 'transparent';
            btn.style.color = 'var(--text-secondary)';
        }
    });
    // Filter gallery items by data-type attribute if present
    document.querySelectorAll('#gallery-grid .photo-item, #gallery-grid > div').forEach(item => {
        if (type === 'all') { item.style.display = ''; }
        else { item.style.display = (item.dataset && item.dataset.type === type) ? '' : 'none'; }
    });
}

/* ================================================================
   Farm Helpers (fallback if external JS not loaded)
   ================================================================ */
function refreshFarm() {
    if (typeof window.refreshFarm === 'function') {
        window.refreshFarm();
    }
}

function claimDaily() {
    if (typeof window.claimDaily === 'function') {
        window.claimDaily();
    }
}

function sendGameChat() {
    if (typeof window.sendGameChat === 'function') {
        window.sendGameChat();
    }
}

/* ================================================================
   Keyboard shortcut: Escape to close sidebar/lightbox
   ================================================================ */
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeSidebar();
        closeLightbox();
        const modal = document.getElementById('image-modal');
        if (modal && modal.classList.contains('active')) {
            modal.classList.remove('active');
        }
    }
});
