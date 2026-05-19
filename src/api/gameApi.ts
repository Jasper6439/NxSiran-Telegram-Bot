import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3001'

const api = axios.create({ baseURL: BASE_URL, timeout: 15000 })

// ── 自动附加 JWT ────────────────────────────────────────────────────────────
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('ls_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401 || err.response?.status === 403) {
      localStorage.removeItem('ls_token')
      localStorage.removeItem('ls_user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// ── 认证 ─────────────────────────────────────────────────────────────────────
export const authApi = {
  login: (username: string, password: string) =>
    api.post<{ token: string; userId: number; gameState: object }>('/api/login', { username, password }),

  register: (username: string, password: string, email?: string, verificationCode?: string, telegramChatId?: string) =>
    api.post<{ token: string; userId: number; gameState: object }>('/api/register', { username, password, email, verificationCode, telegramChatId }),

  sendVerificationCode: (email: string) =>
    api.post<{ success: boolean; message: string }>('/api/send-verification-code', { email }),

  me: () => api.get<{ userId: number; username: string }>('/api/auth/me'),
}

// ── 游戏状态 ─────────────────────────────────────────────────────────────────
export const gameApi = {
  getState: () =>
    api.get<{ state: object; inventory: object[]; farmData: object[] }>('/api/game/state'),

  saveState: (data: { awakeningLevel?: number; worldMode?: string; currentScene?: string }) =>
    api.post<{ success: boolean; state: object }>('/api/game/state', data),
}

// ── 背包 ─────────────────────────────────────────────────────────────────────
export const inventoryApi = {
  add: (itemId: string, quantity: number, mode: string) =>
    api.post('/api/inventory/add', { itemId, quantity, mode }),
}

// ── 农场 ─────────────────────────────────────────────────────────────────────
export const farmApi = {
  getState: () => api.get<{ plots: object[] }>('/api/farm/state'),
  action: (data: { action: string; plotId: number; cropType?: string }) =>
    api.post('/api/farm/action', data),
}

// ── 聊天 ─────────────────────────────────────────────────────────────────────
export const chatApi = {
  send: (message: string, systemHint?: string) =>
    api.post<{ text: string; emotion: string; awakeningChange: number }>('/api/chat', {
      message,
      systemHint,
    }),

  getHistory: () =>
    api.get<{ history: { role: string; content: string }[] }>('/api/chat/history'),
}

// ── 健康检查 ─────────────────────────────────────────────────────────────────
export const healthApi = {
  check: () => api.get<{ status: string }>('/api/health'),
}

export default api
