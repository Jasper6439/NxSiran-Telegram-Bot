import { useState, FormEvent } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { authApi } from '../api/gameApi'

export default function LoginPage() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

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
          : await authApi.register(username, password)

      const { token } = res.data
      localStorage.setItem('ls_token', token)
      localStorage.setItem('ls_user', JSON.stringify(res.data))

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
        {/* 标题卡片 */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">💕</h1>
          <h2 className="text-3xl font-bold text-white">恋爱至上主义</h2>
          <p className="text-white/60 mt-2">Love Supremacy Universe</p>
        </div>

        {/* 表单 */}
        <div className="glass-dark p-8 rounded-2xl">
          {/* Tab 切换 */}
          <div className="flex mb-6 bg-white/10 rounded-lg p-1">
            {(['login', 'register'] as const).map((m) => (
              <button
                key={m}
                onClick={() => { setMode(m); setError('') }}
                className={`flex-1 py-2 rounded-md text-sm font-medium transition-all ${
                  mode === m ? 'bg-white/20 text-white' : 'text-white/60 hover:text-white'
                }`}
              >
                {m === 'login' ? '登录' : '注册'}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-white/70 mb-1">用户名</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="至少3位字符"
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg
                  text-white placeholder-white/30 focus:outline-none focus:border-purple-400"
                autoComplete="username"
              />
            </div>

            <div>
              <label className="block text-sm text-white/70 mb-1">密码</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === 'register' ? '至少6位字符' : '输入密码'}
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg
                  text-white placeholder-white/30 focus:outline-none focus:border-purple-400"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              />
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-red-400 text-sm text-center py-2 bg-red-500/10 rounded-lg"
              >
                {error}
              </motion.div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-white/20 hover:bg-white/30 text-white
                font-semibold rounded-lg transition-colors disabled:opacity-50"
            >
              {loading ? '处理中...' : mode === 'login' ? '登录' : '创建账号'}
            </button>
          </form>
        </div>
      </motion.div>
    </div>
  )
}
