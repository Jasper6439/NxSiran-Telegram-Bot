import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Settings, Bot, Shield, User, Check, AlertCircle, Loader2 } from 'lucide-react';

/**
 * Telegram 配置相关类型定义
 */
interface TelegramLinkStatus {
  telegram_id: string | null;
  linked: boolean;
}

interface CharacterBindings {
  [characterId: string]: {
    bot_token: string;
    linked_at: string;
  };
}

interface AdminConfig {
  telegram_token: string;
  admin_chat_id: string;
}

interface SettingsFormData {
  // 用户 Telegram 绑定
  chatId: string;
  // 角色 Bot 配置
  selectedCharacter: string;
  botToken: string;
  // 管理员配置
  adminToken: string;
  adminChatId: string;
  adminUsername: string;
  adminPassword: string;
}

interface ToastMessage {
  type: 'success' | 'error';
  message: string;
}

/**
 * Glass UI 组件
 */
const GlassCard = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    className={`glass-dark p-6 ${className}`}
  >
    {children}
  </motion.div>
);

const GlassButton = ({
  children,
  onClick,
  disabled = false,
  variant = 'primary',
  className = ''
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: 'primary' | 'secondary' | 'danger';
  className?: string;
}) => {
  const baseClasses = 'px-4 py-2 rounded-lg font-medium transition-all duration-200 flex items-center gap-2 justify-center';
  const variantClasses = {
    primary: 'bg-blue-600 hover:bg-blue-700 text-white',
    secondary: 'bg-white/10 hover:bg-white/20 text-white',
    danger: 'bg-red-600 hover:bg-red-700 text-white'
  };

  return (
    <motion.button
      whileHover={{ scale: disabled ? 1 : 1.02 }}
      whileTap={{ scale: disabled ? 1 : 0.98 }}
      onClick={onClick}
      disabled={disabled}
      className={`${baseClasses} ${variantClasses[variant]} ${disabled ? 'opacity-50 cursor-not-allowed' : ''} ${className}`}
    >
      {children}
    </motion.button>
  );
};

const GlassInput = ({
  label,
  value,
  onChange,
  type = 'text',
  placeholder = '',
  required = false,
  disabled = false
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
}) => (
  <div className="space-y-2">
    <label className="text-sm text-white/70">
      {label}
      {required && <span className="text-red-400 ml-1">*</span>}
    </label>
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      disabled={disabled}
      className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-white placeholder-white/30 focus:outline-none focus:border-blue-500 transition-colors disabled:opacity-50"
    />
  </div>
);

/**
 * Toast 通知组件
 */
const Toast = ({ message, type, onClose }: ToastMessage & { onClose: () => void }) => {
  useEffect(() => {
    const timer = setTimeout(onClose, 3000);
    return () => clearTimeout(timer);
  }, [onClose]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 50 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 50 }}
      className={`fixed bottom-6 right-6 px-6 py-4 rounded-lg shadow-lg flex items-center gap-3 ${
        type === 'success' ? 'bg-green-600' : 'bg-red-600'
      }`}
    >
      {type === 'success' ? <Check size={20} /> : <AlertCircle size={20} />}
      <span>{message}</span>
    </motion.div>
  );
};

/**
 * 主设置页面组件
 */
export default function SettingsPage() {
  // 状态管理
  const [formData, setFormData] = useState<SettingsFormData>({
    chatId: '',
    selectedCharacter: '',
    botToken: '',
    adminToken: '',
    adminChatId: '',
    adminUsername: '',
    adminPassword: ''
  });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<ToastMessage | null>(null);
  
  // Telegram 绑定状态
  const [telegramStatus, setTelegramStatus] = useState<TelegramLinkStatus>({
    telegram_id: null,
    linked: false
  });
  
  // 角色绑定状态
  const [characterBindings, setCharacterBindings] = useState<CharacterBindings>({});
  const [availableCharacters, setAvailableCharacters] = useState<string[]>([]);
  
  // 用户角色
  const [isAdmin, setIsAdmin] = useState(false);
  const [userRole, setUserRole] = useState<string>('');

  // API 调用函数
  const fetchTelegramStatus = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch('/api/telegram/link', {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setTelegramStatus(data);
        if (data.telegram_id) {
          setFormData(prev => ({ ...prev, chatId: data.telegram_id }));
        }
      }
    } catch (error) {
      console.error('获取 Telegram 状态失败:', error);
    }
  };

  const fetchCharacterBindings = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch('/api/character-bindings', {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setCharacterBindings(data.bindings || {});
      }
    } catch (error) {
      console.error('获取角色绑定失败:', error);
    }
  };

  const fetchCharacters = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch('/api/characters', {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setAvailableCharacters(data.characters || []);
      }
    } catch (error) {
      console.error('获取角色列表失败:', error);
    }
  };

  const fetchAdminConfig = async () => {
    try {
      const res = await fetch('/api/config');
      if (res.ok) {
        const data = await res.json();
        // Token 显示为遮蔽状态
        setFormData(prev => ({
          ...prev,
          adminToken: data.telegram_token ? '********' : '',
          adminChatId: data.admin_chat_id || ''
        }));
      }
    } catch (error) {
      console.error('获取管理员配置失败:', error);
    }
  };

  const fetchUserRole = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch('/api/auth/me', {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUserRole(data.role || '');
        setIsAdmin(data.role === 'admin');
      }
    } catch (error) {
      console.error('获取用户角色失败:', error);
    }
  };

  // 初始化加载
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([
        fetchTelegramStatus(),
        fetchCharacterBindings(),
        fetchCharacters(),
        fetchAdminConfig(),
        fetchUserRole()
      ]);
      setLoading(false);
    };
    loadData();
  }, []);

  // 表单字段更新
  const updateField = (field: keyof SettingsFormData, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  // 绑定 Telegram 账号
  const handleLinkTelegram = async () => {
    if (!formData.chatId.trim()) {
      setToast({ type: 'error', message: '请输入 Chat ID' });
      return;
    }

    setSaving(true);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch('/api/telegram/link', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ telegram_id: formData.chatId })
      });

      if (res.ok) {
        setTelegramStatus({ telegram_id: formData.chatId, linked: true });
        setToast({ type: 'success', message: 'Telegram 账号绑定成功！' });
      } else {
        const error = await res.json();
        setToast({ type: 'error', message: error.message || '绑定失败' });
      }
    } catch (error) {
      setToast({ type: 'error', message: '网络错误，请重试' });
    } finally {
      setSaving(false);
    }
  };

  // 解绑 Telegram 账号
  const handleUnlinkTelegram = async () => {
    setSaving(true);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch('/api/telegram/unlink', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });

      if (res.ok) {
        setTelegramStatus({ telegram_id: null, linked: false });
        setFormData(prev => ({ ...prev, chatId: '' }));
        setToast({ type: 'success', message: 'Telegram 账号已解绑' });
      } else {
        setToast({ type: 'error', message: '解绑失败' });
      }
    } catch (error) {
      setToast({ type: 'error', message: '网络错误，请重试' });
    } finally {
      setSaving(false);
    }
  };

  // 绑定角色 Bot
  const handleBindCharacter = async () => {
    if (!formData.selectedCharacter) {
      setToast({ type: 'error', message: '请选择角色' });
      return;
    }
    if (!formData.botToken.trim()) {
      setToast({ type: 'error', message: '请输入 Bot Token' });
      return;
    }

    setSaving(true);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch('/api/bind-character', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          character_id: formData.selectedCharacter,
          bot_token: formData.botToken
        })
      });

      if (res.ok) {
        await fetchCharacterBindings();
        setFormData(prev => ({ ...prev, botToken: '' }));
        setToast({ type: 'success', message: '角色 Bot 绑定成功！' });
      } else {
        const error = await res.json();
        setToast({ type: 'error', message: error.message || '绑定失败' });
      }
    } catch (error) {
      setToast({ type: 'error', message: '网络错误，请重试' });
    } finally {
      setSaving(false);
    }
  };

  // 保存管理员配置
  const handleSaveAdminConfig = async () => {
    // 表单验证
    if (!formData.adminUsername.trim()) {
      setToast({ type: 'error', message: '请输入管理员用户名' });
      return;
    }
    if (!formData.adminPassword.trim()) {
      setToast({ type: 'error', message: '请输入管理员密码' });
      return;
    }

    setSaving(true);
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          telegram_token: formData.adminToken !== '********' ? formData.adminToken : undefined,
          admin_chat_id: formData.adminChatId,
          admin_username: formData.adminUsername,
          admin_password: formData.adminPassword
        })
      });

      if (res.ok) {
        setToast({ type: 'success', message: '配置保存成功！' });
        // 清除敏感字段
        setFormData(prev => ({
          ...prev,
          adminPassword: '',
          adminToken: '********'
        }));
        await fetchAdminConfig();
      } else {
        const error = await res.json();
        setToast({ type: 'error', message: error.message || '保存失败，请验证管理员权限' });
      }
    } catch (error) {
      setToast({ type: 'error', message: '网络错误，请重试' });
    } finally {
      setSaving(false);
    }
  };

  // 加载状态
  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
        >
          <Loader2 size={48} className="text-blue-500" />
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* 页面标题 */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-3 mb-8"
        >
          <Settings size={32} className="text-blue-400" />
          <h1 className="text-3xl font-bold text-white">设置</h1>
        </motion.div>

        {/* Telegram 账号绑定区块 */}
        <GlassCard>
          <div className="flex items-center gap-3 mb-6">
            <Bot size={24} className="text-blue-400" />
            <h2 className="text-xl font-semibold text-white">Telegram 账号绑定</h2>
          </div>

          <div className="space-y-4">
            {/* 绑定状态 */}
            <div className="flex items-center justify-between p-4 bg-white/5 rounded-lg">
              <div className="flex items-center gap-3">
                {telegramStatus.linked ? (
                  <div className="w-3 h-3 rounded-full bg-green-500" />
                ) : (
                  <div className="w-3 h-3 rounded-full bg-gray-500" />
                )}
                <span className="text-white">
                  {telegramStatus.linked
                    ? `已绑定: ${telegramStatus.telegram_id}`
                    : '未绑定'}
                </span>
              </div>
            </div>

            {/* Chat ID 输入 */}
            <GlassInput
              label="Chat ID"
              value={formData.chatId}
              onChange={(value) => updateField('chatId', value)}
              placeholder="请输入您的 Telegram Chat ID"
              required
            />

            {/* 绑定/解绑按钮 */}
            <div className="flex gap-3">
              {telegramStatus.linked ? (
                <>
                  <GlassButton onClick={handleLinkTelegram} disabled={saving}>
                    <Check size={18} />
                    更新绑定
                  </GlassButton>
                  <GlassButton variant="danger" onClick={handleUnlinkTelegram} disabled={saving}>
                    解除绑定
                  </GlassButton>
                </>
              ) : (
                <GlassButton onClick={handleLinkTelegram} disabled={saving}>
                  绑定账号
                </GlassButton>
              )}
            </div>
          </div>
        </GlassCard>

        {/* 角色 Bot 配置区块 */}
        <GlassCard>
          <div className="flex items-center gap-3 mb-6">
            <User size={24} className="text-purple-400" />
            <h2 className="text-xl font-semibold text-white">角色 Bot 配置</h2>
          </div>

          <div className="space-y-4">
            {/* 已绑定的角色列表 */}
            {Object.keys(characterBindings).length > 0 && (
              <div className="space-y-2">
                <label className="text-sm text-white/70">已绑定的角色</label>
                <div className="space-y-2">
                  {Object.entries(characterBindings).map(([characterId, binding]) => (
                    <div
                      key={characterId}
                      className="flex items-center justify-between p-3 bg-white/5 rounded-lg"
                    >
                      <span className="text-white font-medium">{characterId}</span>
                      <span className="text-white/50 text-sm">
                        绑定于 {new Date(binding.linked_at).toLocaleDateString()}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 角色选择 */}
            <div className="space-y-2">
              <label className="text-sm text-white/70">选择角色</label>
              <select
                value={formData.selectedCharacter}
                onChange={(e) => updateField('selectedCharacter', e.target.value)}
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500"
              >
                <option value="">请选择角色</option>
                {availableCharacters.map((char) => (
                  <option key={char} value={char}>
                    {char}
                  </option>
                ))}
              </select>
            </div>

            {/* Bot Token 输入 */}
            <GlassInput
              label="Bot Token"
              value={formData.botToken}
              onChange={(value) => updateField('botToken', value)}
              type="password"
              placeholder="请输入 Bot Token (如 123456789:ABC...)"
              required
            />

            {/* 绑定按钮 */}
            <GlassButton onClick={handleBindCharacter} disabled={saving}>
              绑定角色 Bot
            </GlassButton>
          </div>
        </GlassCard>

        {/* 管理员配置区块 - 仅管理员可见 */}
        {isAdmin && (
          <GlassCard>
            <div className="flex items-center gap-3 mb-6">
              <Shield size={24} className="text-yellow-400" />
              <h2 className="text-xl font-semibold text-white">管理员配置</h2>
              <span className="px-2 py-1 text-xs bg-yellow-500/20 text-yellow-400 rounded">
                {userRole}
              </span>
            </div>

            <div className="space-y-4">
              {/* 主 Bot Token */}
              <GlassInput
                label="主 Bot Token"
                value={formData.adminToken}
                onChange={(value) => updateField('adminToken', value)}
                type="password"
                placeholder="输入新的 Bot Token 或保留 ********"
              />

              {/* 管理员 Chat ID */}
              <GlassInput
                label="管理员 Chat ID"
                value={formData.adminChatId}
                onChange={(value) => updateField('adminChatId', value)}
                placeholder="用于接收系统通知的 Chat ID"
              />

              <div className="border-t border-white/10 pt-4 mt-4">
                <h3 className="text-lg font-medium text-white mb-4">管理员验证</h3>
                
                {/* 管理员用户名 */}
                <div className="space-y-2 mb-4">
                  <label className="text-sm text-white/70">
                    管理员用户名 <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.adminUsername}
                    onChange={(e) => updateField('adminUsername', e.target.value)}
                    placeholder="请输入管理员用户名"
                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-white placeholder-white/30 focus:outline-none focus:border-blue-500"
                  />
                </div>

                {/* 管理员密码 */}
                <GlassInput
                  label="管理员密码"
                  value={formData.adminPassword}
                  onChange={(value) => updateField('adminPassword', value)}
                  type="password"
                  placeholder="请输入管理员密码"
                  required
                />
              </div>

              {/* 保存按钮 */}
              <GlassButton
                variant="primary"
                onClick={handleSaveAdminConfig}
                disabled={saving}
              >
                {saving ? (
                  <>
                    <Loader2 size={18} className="animate-spin" />
                    保存中...
                  </>
                ) : (
                  '保存配置'
                )}
              </GlassButton>
            </div>
          </GlassCard>
        )}

        {/* 关于区块 */}
        <GlassCard className="text-center">
          <h2 className="text-xl font-semibold text-white mb-2">关于</h2>
          <p className="text-white/60">NxSiran Telegram Bot v1.0.0</p>
          <p className="text-white/40 text-sm mt-1">一个基于 AI 的 Telegram 聊天机器人</p>
        </GlassCard>
      </div>

      {/* Toast 通知 */}
      <AnimatePresence>
        {toast && (
          <Toast
            type={toast.type}
            message={toast.message}
            onClose={() => setToast(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
