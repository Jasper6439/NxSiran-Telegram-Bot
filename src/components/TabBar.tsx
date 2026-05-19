import { useLocation, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  House,
  Gamepad2,
  Sprout,
  Image,
  SlidersHorizontal,
  Monitor,
} from 'lucide-react'

// ─────────────────────────────────────────────────────────────────────────────
// Tab 定义
// ─────────────────────────────────────────────────────────────────────────────

export interface TabItem {
  id: string
  label: string
  icon: typeof House
  path: string
  adminOnly?: boolean
}

const TABS: TabItem[] = [
  { id: 'home',   label: '首页',   icon: House,              path: '/' },
  { id: 'game',   label: '游戏',   icon: Gamepad2,           path: '/game' },
  { id: 'farm',   label: '农场',   icon: Sprout,             path: '/farm' },
  { id: 'media',  label: '多媒体', icon: Image,              path: '/media' },
  { id: 'monitor', label: '监控',  icon: Monitor,            path: '/monitor', adminOnly: true },
  { id: 'settings', label: '设置', icon: SlidersHorizontal,  path: '/settings' },
]

// ─────────────────────────────────────────────────────────────────────────────
// 组件
// ─────────────────────────────────────────────────────────────────────────────

export default function TabBar() {
  const location = useLocation()
  const navigate = useNavigate()
  const currentPath = location.pathname

  // 检查管理员身份
  const userStr = localStorage.getItem('ls_user')
  let isAdmin = false
  if (userStr) {
    try {
      const user = JSON.parse(userStr)
      isAdmin = user.role === 'admin' || user.isAdmin === true
    } catch {}
  }

  const visibleTabs = TABS.filter((t) => !t.adminOnly || isAdmin)

  return (
    <nav className="ios-tabbar">
      {visibleTabs.map((tab) => {
        const active = currentPath === tab.path
        const Icon = tab.icon
        return (
          <button
            key={tab.id}
            className="ios-tab-item"
            onClick={() => navigate(tab.path)}
            style={{ color: active ? 'var(--ios-blue)' : 'var(--ios-gray)' }}
          >
            <div className="ios-tab-icon">
              <AnimatePresence mode="wait">
                {active && (
                  <motion.div
                    key="fill"
                    initial={{ scale: 0.6, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    exit={{ scale: 0.6, opacity: 0 }}
                    transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                    style={{
                      position: 'absolute',
                      width: 20,
                      height: 20,
                      borderRadius: 6,
                      background: active ? 'var(--ios-blue)' : 'transparent',
                      opacity: 0.12,
                    }}
                  />
                )}
              </AnimatePresence>
              <Icon
                size={24}
                strokeWidth={active ? 2.2 : 1.8}
                fill={active ? 'var(--ios-blue)' : 'transparent'}
                fillOpacity={0.15}
              />
            </div>
            <span
              className="ios-tab-label"
              style={{
                fontWeight: active ? 600 : 500,
                color: active ? 'var(--ios-blue)' : 'var(--ios-gray)',
              }}
            >
              {tab.label}
            </span>
          </button>
        )
      })}
    </nav>
  )
}