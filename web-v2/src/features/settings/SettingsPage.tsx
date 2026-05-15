// ═══════════════════════════════════════════════════════════════════════════
// 设置页面 - 含登录功能
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
    // 从 localStorage 读取深色模式设置
    const saved = localStorage.getItem('darkMode');
    if (saved !== null) return saved === 'true';
    // 默认跟随系统
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });
  const [notifications, setNotifications] = useState(true);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [loginForm, setLoginForm] = useState({ username: '', password: '' });
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [appVersion, setAppVersion] = useState<string>('v1.6.5'); // 默认版本

  // 检查登录状态 & 获取版本号
  useEffect(() => {
    const token = getAuthToken();
    if (token) {
      setIsLoggedIn(true);
      fetchUserInfo(token);
    }
    // 获取后端版本号
    fetchVersion();
    // 应用保存的深色模式
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
      // 忽略错误，保持默认状态
    }
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
        <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">外观</h3>
        
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
              // 应用/移除 dark 类到 html 元素
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
    </div>
  );
}
