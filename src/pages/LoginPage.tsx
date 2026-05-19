import { useState, FormEvent, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { authApi } from '../api/gameApi'

const LS_REMEMBER = 'ls_remember_username'

export default function LoginPage() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [email, setEmail] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [telegramChatId, setTelegramChatId] = useState('')
  const [rememberMe, setRememberMe] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [codeSending, setCodeSending] = useState(false)
  const [codeCountdown, setCodeCountdown] = useState(0)

  // 页面加载：如果之前记住过账号，自动填充
  useEffect(() => {
    const saved = localStorage.getItem(LS_REMEMBER)
    if (saved) {
      setUsername(saved)
      setRememberMe(true)
    }
  }, [])

  // 验证码倒计时
  useEffect(() => {
    if (codeCountdown <= 0) return
    const t = setTimeout(() => setCodeCountdown(c => c - 1), 1000)
    return () => clearTimeout(t)
  }, [codeCountdown])

  const handleSendCode = async () => {
    if (!email.trim()) {
      setError('请先填写邮箱地址')
      return
    }
    setCodeSending(true)
    setError('')
    try {
      const res = await authApi.sendVerificationCode(email.trim())
      setCodeCountdown(60)
      setError(res.data.message || '验证码已发送')
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { error?: string } } }
      setError(axiosErr.response?.data?.error || '发送失败')
    } finally {
      setCodeSending(false)
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    if (!username.trim() || !password.trim()) {
      setError('请填写所有字段')
      return
    }

    setLoading(true)
    try {
      const res =
        mode === 'login'
          ? await authApi.login(username, password)
          : await authApi.register(
              username,
              password,
              email.trim() || undefined,
              verificationCode.trim() || undefined,
              telegramChatId.trim() || undefined
            )

      const { token } = res.data
      localStorage.setItem('ls_token', token)
      localStorage.setItem('ls_user', JSON.stringify(res.data))

      if (mode === 'login') {
        if (rememberMe) {
          localStorage.setItem(LS_REMEMBER, username)
        } else {
          localStorage.removeItem(LS_REMEMBER)
        }
      }

      navigate('/game')
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { error?: string } } }
      setError(axiosErr.response?.data?.error || '请求失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4"
      style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}
    >
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-md"
      >
        {/* 标题 */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">💕</h1>
          <h2 className="text-3xl font-bold text-white">恋爱至上主义</h2>
          <p className="text-white/60 mt-2">Love Supremacy Universe</p>
        </div>

        {/* 表单卡片 — 白色背景 + 深色文字 */}
        <div className="bg-white/95 backdrop-blur-md p-8 rounded-2xl shadow-2xl">
          {/* Tab 切换 */}
          <div className="flex mb-6 bg-gray-100 rounded-lg p-1">
            {(['login', 'register'] as const).map((m) => (
              <button
                key={m}
                onClick={() => { setMode(m); setError('') }}
                className={`flex-1 py-2 rounded-md text-sm font-medium transition-all ${
                  mode === m
                    ? 'bg-white text-purple-700 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {m === 'login' ? '登录' : '注册'}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-600 mb-1">用户名</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="至少3位字符"
                className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-lg
                  text-gray-800 placeholder-gray-400 focus:outline-none focus:border-purple-400 focus:ring-1 focus:ring-purple-400"
                autoComplete="username"
              />
            </div>

            <div>
              <label className="block text-sm text-gray-600 mb-1">密码</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === 'register' ? '至少6位字符' : '输入密码'}
                className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-lg
                  text-gray-800 placeholder-gray-400 focus:outline-none focus:border-purple-400 focus:ring-1 focus:ring-purple-400"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              />
            </div>

            {/* 注册模式：邮箱 + 验证码 */}
            {mode === 'register' && (
              <>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">
                    邮箱 <span className="text-red-500">*</span>
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="example@email.com"
                      className="flex-1 px-4 py-3 bg-gray-50 border border-gray-200 rounded-lg
                        text-gray-800 placeholder-gray-400 focus:outline-none focus:border-purple-400 focus:ring-1 focus:ring-purple-400"
                      autoComplete="email"
                    />
                    <button
                      type="button"
                      onClick={handleSendCode}
                      disabled={codeSending || codeCountdown > 0 || !email.trim()}
                      className="px-3 py-2 bg-purple-100 text-purple-700 text-sm font-medium rounded-lg
                        hover:bg-purple-200 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
                    >
                      {codeCountdown > 0 ? `${codeCountdown}s` : codeSending ? '发送中...' : '获取验证码'}
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-sm text-gray-600 mb-1">验证码</label>
                  <input
                    type="text"
                    value={verificationCode}
                    onChange={(e) => setVerificationCode(e.target.value)}
                    placeholder="6位数字"
                    maxLength={6}
                    className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-lg
                      text-gray-800 placeholder-gray-400 focus:outline-none focus:border-purple-400 focus:ring-1 focus:ring-purple-400"
                  />
                </div>

                <div>
                  <label className="block text-sm text-gray-600 mb-1">
                    Telegram Chat ID <span className="text-gray-400 font-normal">(可选)</span>
                  </label>
                  <input
                    type="text"
                    value={telegramChatId}
                    onChange={(e) => setTelegramChatId(e.target.value)}
                    placeholder="绑定后可直接接收通知"
                    className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-lg
                      text-gray-800 placeholder-gray-400 focus:outline-none focus:border-purple-400 focus:ring-1 focus:ring-purple-400"
                  />
                </div>
              </>
            )}

            {/* 记住账号 —— 仅登录模式显示 */}
            {mode === 'login' && (
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="w-4 h-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                />
                <span className="text-sm text-gray-500">记住账号</span>
              </label>
            )}

            {error && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-red-600 text-sm text-center py-2 bg-red-50 rounded-lg border border-red-100"
              >
                {error}
              </motion.div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700
                text-white font-semibold rounded-lg transition-all disabled:opacity-50 shadow-md"
            >
              {loading ? '处理中...' : mode === 'login' ? '登录' : '创建账号'}
            </button>
          </form>
        </div>
      </motion.div>
    </div>
  )
}
