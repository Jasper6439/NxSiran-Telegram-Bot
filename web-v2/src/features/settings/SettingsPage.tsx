// ═══════════════════════════════════════════════════════════════════════════
// 设置页面 - 含登录功能 + Telegram 配置
// ═══════════════════════════════════════════════════════════════════════════
import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { GlassCard, GlassButton, GlassModal } from '../../components/ui/GlassComponents';

// API 地址
const API_BASE = import.meta.env.VITE_API_BASE || '';

interface UserInfo {
  id: number;
  username: string;
  nickname: string;
  avatar?: string;
}

interface TelegramConfig {
  telegram_token: string;
  chat_id: string;
  ai_api_key: string;
  ai_api_base: string;
  admin_username: string;
  public_url: string;
}

function getAuthToken(): string | null {
  return localStorage.getItem('auth_token');
}

function setAuthToken(token: string) {
  localStorage.setItem('auth_token', token);
}

function clearAuthToken() {
  localStorage.removeItem('auth_token');
}

export default function SettingsPage() {
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('darkMode');
    if (saved !== null) return saved === 'true';
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });
  const [notifications, setNotifications] = useState(true);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [loginForm, setLoginForm] = useState({ username: '', password: '' });
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [appVersion, setAppVersion] = useState<string>('v1.6.5');

  // ===== Telegram 配置相关状态 =====
  const [showTelegramModal, setShowTelegramModal] = useState(false);
  const [telegramConfig, setTelegramConfig] = useState<TelegramConfig>({
    telegram_token: '',
    chat_id: '',
    ai_api_key: '',
    ai_api_base: '',
    admin_username: '',
    public_url: '',
  });
  const [adminPassword, setAdminPassword] = useState('');
  const [isSavingConfig, setIsSavingConfig] = useState(false);
  const [configMessage, setConfigMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [isLoadingConfig, setIsLoadingConfig] = useState(false);

  // 检查登录状态 & 获取版本号
  useEffect(() => {
    const token = getAuthToken();
    if (token) {
      setIsLoggedIn(true);
      fetchUserInfo(token);
    }
    fetchVersion();
    const savedDarkMode = localStorage.getItem('darkMode');
    if (savedDarkMode === 'true') {
      document.documentElement.classList.add('dark');
    }
  }, []);

  const fetchVersion = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/version`);
      if (res.ok) {
        const data = await res.json();
        if (data.success && data.version) {
          setAppVersion(`v${data.version}`);
        }
      }
    } catch {
      // 使用默认版本
    }
  };

  const fetchUserInfo = async (token: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/user/info`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setUserInfo(data);
      }
    } catch {
      // 忽略错误
    }
  };

  // ===== Telegram 配置相关函数 =====

  // 加载 Telegram 配置
  const loadTelegramConfig = async () => {
    setIsLoadingConfig(true);
    setConfigMessage(null);
    try {
      const res = await fetch(`${API_BASE}/api/config`);
      const data = await res.json();
      if (data.success && data.config) {
        setTelegramConfig({
          telegram_token: data.config.telegram_token || '',
          chat_id: data.config.chat_id || '',
          ai_api_key: data.config.ai_api_key || '',
          ai_api_base: data.config.ai_api_base || '',
          admin_username: data.config.admin_username || '',
          public_url: data.config.public_url || '',
        });
      }
    } catch (err) {
      setConfigMessage({ type: 'error', text: '加载配置失败，请稍后重试' });
    } finally {
      setIsLoadingConfig(false);
    }
  };

  // 保存 Telegram 配置
  const saveTelegramConfig = async () => {
    if (!telegramConfig.admin_username || !adminPassword) {
      setConfigMessage({ type: 'error', text: '请填写管理员用户名和密码' });
      return;
    }

    if (!telegramConfig.telegram_token) {
      setConfigMessage({ type: 'error', text: '请填写 Telegram Bot Token' });
      return;
    }

    setIsSavingConfig(true);
    setConfigMessage(null);

    try {
      const res = await fetch(`${API_BASE}/api/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          telegram_token: telegramConfig.telegram_token,
          chat_id: telegramConfig.chat_id,
          ai_api_key: telegramConfig.ai_api_key,
          ai_api_base: telegramConfig.ai_api_base,
          admin_username: telegramConfig.admin_username,
          admin_password: adminPassword,
          public_url: telegramConfig.public_url,
        }),
      });

      const data = await res.json();

      if (data.success) {
        setConfigMessage({ type: 'success', text: data.message || '配置保存成功！' });
        setAdminPassword('');
        setTimeout(() => {
          setShowTelegramModal(false);
          setConfigMessage(null);
        }, 1500);
      } else {
        setConfigMessage({ type: 'error', text: data.error || '保存失败，仅管理员可修改配置' });
      }
    } catch (err) {
      setConfigMessage({ type: 'error', text: '网络错误，请稍后重试' });
    } finally {
      setIsSavingConfig(false);
    }
  };

  // 打开 Telegram 配置弹窗
  const handleOpenTelegramConfig = () => {
    setShowTelegramModal(true);
    loadTelegramConfig();
  };

  const handleLogin = async () => {
    if (!loginForm.username || !loginForm.password) {
      setLoginError('请输入用户名和密码');
      return;
    }

    setIsLoggingIn(true);
    setLoginError(null);

    try {
      const res = await fetch(`${API_BASE}/api/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(loginForm),
      });

      const data = await res.json();

      if (res.ok && data.token) {
        setAuthToken(data.token);
        setIsLoggedIn(true);
        setUserInfo(data.user || { id: 0, username: loginForm.username, nickname: loginForm.username });
        setShowLoginModal(false);
        setLoginForm({ username: '', password: '' });
      } else {
        setLoginError(data.error || data.message || '登录失败，请检查用户名和密码');
      }
    } catch {
      setLoginError('网络错误，请稍后重试');
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleLogout = () => {
    clearAuthToken();
    setIsLoggedIn(false);
    setUserInfo(null);
  };

  const handleExportData = () => {
    const data = localStorage.getItem('nxsiran-game-storage');
    if (data) {
      const blob = new Blob([data], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `nxsiran-backup-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    }
  };

  const handleClearCache = () => {
    localStorage.removeItem('nxsiran-game-storage');
    window.location.reload();
  };

  return (
    <div className="px-4 pb-24 pt-4">
      {/* 用户信息 / 登录入口 */}
      <GlassCard className="p-5 mb-6">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-brand-300 to-brand-500 flex items-center justify-center text-3xl">
            {userInfo?.avatar ? (
              <img src={userInfo.avatar} alt="头像" className="w-full h-full rounded-full object-cover" />
            ) : (
              '🌸'
            )}
          </div>
          <div className="flex-1">
            {isLoggedIn ? (
              <>
                <h2 className="text-lg font-semibold text-gray-800">
                  {userInfo?.nickname || userInfo?.username || '小樱'}
                </h2>
                <p className="text-sm text-gray-500">Lv.5 农场主 · 已登录</p>
              </>
            ) : (
              <>
                <h2 className="text-lg font-semibold text-gray-800">游客模式</h2>
                <p className="text-sm text-gray-500">登录后可保存游戏进度</p>
              </>
            )}
          </div>
          {isLoggedIn ? (
            <GlassButton variant="secondary" size="sm" onClick={handleLogout}>退出</GlassButton>
          ) : (
            <GlassButton variant="primary" size="sm" onClick={() => setShowLoginModal(true)}>登录</GlassButton>
          )}
        </div>
      </GlassCard>

      {/* 设置列表 */}
      <div className="space-y-4">
        {/* ===== Telegram 配置区块 ===== */}
        <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">集成</h3>

        <GlassCard className="p-4" hoverable onClick={handleOpenTelegramConfig}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xl">🤖</span>
              <div>
                <p className="font-medium text-gray-800">Telegram 配置</p>
                <p className="text-sm text-gray-500">绑定 Bot Token 和 Chat ID</p>
              </div>
            </div>
            <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </GlassCard>

        <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide pt-4">外观</h3>

        <GlassCard className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xl">🌙</span>
              <div>
                <p className="font-medium text-gray-800">深色模式</p>
                <p className="text-sm text-gray-500">跟随系统设置</p>
              </div>
            </div>
            <button
              onClick={() => {
                const newMode = !darkMode;
                setDarkMode(newMode);
                localStorage.setItem('darkMode', String(newMode));
                if (newMode) {
                  document.documentElement.classList.add('dark');
                } else {
                  document.documentElement.classList.remove('dark');
                }
              }}
              className={`w-12 h-7 rounded-full transition-colors ${darkMode ? 'bg-brand-500' : 'bg-gray-300'}`}
            >
              <motion.div
                animate={{ x: darkMode ? 20 : 0 }}
                className="w-5 h-5 bg-white rounded-full shadow"
              />
            </button>
          </div>
        </GlassCard>

        <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide pt-4">通知</h3>

        <GlassCard className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xl">🔔</span>
              <div>
                <p className="font-medium text-gray-800">推送通知</p>
                <p className="text-sm text-gray-500">作物成熟时提醒</p>
              </div>
            </div>
            <button
              onClick={() => setNotifications(!notifications)}
              className={`w-12 h-7 rounded-full transition-colors ${notifications ? 'bg-brand-500' : 'bg-gray-300'}`}
            >
              <div className={`w-5 h-5 bg-white rounded-full shadow transform transition-transform ${notifications ? 'translate-x-5' : 'translate-x-1'}`} />
            </button>
          </div>
        </GlassCard>

        <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide pt-4">数据</h3>

        <GlassCard className="p-4" hoverable onClick={handleExportData}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xl">💾</span>
              <div>
                <p className="font-medium text-gray-800">导出数据</p>
                <p className="text-sm text-gray-500">备份你的游戏进度</p>
              </div>
            </div>
            <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </GlassCard>

        <GlassCard className="p-4" hoverable onClick={handleClearCache}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xl">🗑️</span>
              <div>
                <p className="font-medium text-gray-800">清除缓存</p>
                <p className="text-sm text-gray-500">释放存储空间</p>
              </div>
            </div>
            <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </GlassCard>

        <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide pt-4">关于</h3>

        <GlassCard className="p-4">
          <div className="text-center text-gray-500 text-sm">
            <p>恋爱至上主义区域 {appVersion}</p>
            <p className="mt-1">Made with 💕</p>
          </div>
        </GlassCard>
      </div>

      {/* 登录弹窗 */}
      <GlassModal isOpen={showLoginModal} onClose={() => setShowLoginModal(false)} title="登录账号" position="center">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">用户名</label>
            <input
              type="text"
              value={loginForm.username}
              onChange={(e) => setLoginForm({ ...loginForm, username: e.target.value })}
              placeholder="请输入用户名"
              className="w-full px-4 py-3 bg-white/50 rounded-ios-lg border border-gray-200/50 focus:outline-none focus:ring-2 focus:ring-brand-400/50"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">密码</label>
            <input
              type="password"
              value={loginForm.password}
              onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
              placeholder="请输入密码"
              onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
              className="w-full px-4 py-3 bg-white/50 rounded-ios-lg border border-gray-200/50 focus:outline-none focus:ring-2 focus:ring-brand-400/50"
            />
          </div>

          {loginError && (
            <p className="text-sm text-red-500 text-center">{loginError}</p>
          )}

          <GlassButton
            variant="primary"
            className="w-full py-3"
            onClick={handleLogin}
            disabled={isLoggingIn}
          >
            {isLoggingIn ? '登录中...' : '登录'}
          </GlassButton>

          <p className="text-xs text-gray-400 text-center">
            登录后可保存游戏进度并与小樱聊天
          </p>
        </div>
      </GlassModal>

      {/* Telegram 配置弹窗 */}
      <GlassModal isOpen={showTelegramModal} onClose={() => setShowTelegramModal(false)} title="🤖 Telegram 配置" position="center">
        <div className="space-y-4">
          {/* Bot Token */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Bot Token <span className="text-red-500">*</span>
            </label>
            <input
              type="password"
              value={telegramConfig.telegram_token}
              onChange={(e) => setTelegramConfig({ ...telegramConfig, telegram_token: e.target.value })}
              placeholder="从 @BotFather 获取的 Token"
              className="w-full px-4 py-3 bg-white/50 rounded-ios-lg border border-gray-200/50 focus:outline-none focus:ring-2 focus:ring-brand-400/50"
            />
            <p className="text-xs text-gray-400 mt-1">格式: 123456789:ABCDefGhIJKlmNoPQRsTUVwxYZ</p>
          </div>

          {/* Chat ID */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Chat ID
            </label>
            <input
              type="text"
              value={telegramConfig.chat_id}
              onChange={(e) => setTelegramConfig({ ...telegramConfig, chat_id: e.target.value })}
              placeholder="你的 Telegram Chat ID（如 123456789）"
              className="w-full px-4 py-3 bg-white/50 rounded-ios-lg border border-gray-200/50 focus:outline-none focus:ring-2 focus:ring-brand-400/50"
            />
            <p className="text-xs text-gray-400 mt-1">发送消息给 @userinfobot 获取你的 Chat ID</p>
          </div>

          {/* Public URL */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Public URL
            </label>
            <input
              type="text"
              value={telegramConfig.public_url}
              onChange={(e) => setTelegramConfig({ ...telegramConfig, public_url: e.target.value })}
              placeholder="https://your-domain.com（用于 Webhook）"
              className="w-full px-4 py-3 bg-white/50 rounded-ios-lg border border-gray-200/50 focus:outline-none focus:ring-2 focus:ring-brand-400/50"
            />
          </div>

          {/* 分隔线 */}
          <div className="border-t border-gray-200 my-4"></div>

          {/* 管理员验证 */}
          <p className="text-sm text-gray-500">修改配置需要管理员权限</p>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              管理员用户名 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={telegramConfig.admin_username}
              onChange={(e) => setTelegramConfig({ ...telegramConfig, admin_username: e.target.value })}
              placeholder="管理员用户名"
              className="w-full px-4 py-3 bg-white/50 rounded-ios-lg border border-gray-200/50 focus:outline-none focus:ring-2 focus:ring-brand-400/50"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              管理员密码 <span className="text-red-500">*</span>
            </label>
            <input
              type="password"
              value={adminPassword}
              onChange={(e) => setAdminPassword(e.target.value)}
              placeholder="管理员密码"
              className="w-full px-4 py-3 bg-white/50 rounded-ios-lg border border-gray-200/50 focus:outline-none focus:ring-2 focus:ring-brand-400/50"
            />
          </div>

          {/* 消息提示 */}
          {configMessage && (
            <p className={`text-sm text-center ${configMessage.type === 'success' ? 'text-green-500' : 'text-red-500'}`}>
              {configMessage.text}
            </p>
          )}

          {/* 保存按钮 */}
          <GlassButton
            variant="primary"
            className="w-full py-3"
            onClick={saveTelegramConfig}
            disabled={isSavingConfig || isLoadingConfig}
          >
            {isSavingConfig ? '保存中...' : isLoadingConfig ? '加载中...' : '💾 保存配置'}
          </GlassButton>

          <p className="text-xs text-gray-400 text-center">
            保存后 Bot Token 和 Chat ID 将立即生效
          </p>
        </div>
      </GlassModal>
    </div>
  );
}
