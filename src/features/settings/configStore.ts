import { create } from 'zustand'

export interface Config {
  telegram_token: string
  chat_id: string
  ai_api_key: string
}

export interface AdminAuth {
  admin_username: string
  admin_password: string
}

interface ConfigState {
  config: Config | null
  isLoading: boolean
  error: string | null
  fetchConfig: () => Promise<void>
  saveConfig: (config: Partial<Config>, auth: AdminAuth) => Promise<{ success: boolean; message: string }>
}

export const useConfigStore = create<ConfigState>((set) => ({
  config: null,
  isLoading: false,
  error: null,

  fetchConfig: async () => {
    set({ isLoading: true, error: null })
    try {
      const response = await fetch('/api/config')
      if (!response.ok) {
        throw new Error('获取配置失败')
      }
      const data = await response.json()
      set({ config: data.config, isLoading: false })
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : '获取配置时发生错误', 
        isLoading: false 
      })
    }
  },

  saveConfig: async (config: Partial<Config>, auth: AdminAuth) => {
    set({ isLoading: true, error: null })
    try {
      const response = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...config, ...auth }),
      })
      
      const data = await response.json()
      
      if (!response.ok) {
        throw new Error(data.message || '保存配置失败')
      }
      
      set({ 
        config: data.config, 
        isLoading: false,
        error: null 
      })
      
      return { success: true, message: '配置保存成功' }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '保存配置时发生错误'
      set({ error: errorMessage, isLoading: false })
      return { success: false, message: errorMessage }
    }
  },
}))
