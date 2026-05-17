// ═══════════════════════════════════════════════════════════════════════════
// 主布局 v1.9.5 - 底部导航 + 页面容器
// ═══════════════════════════════════════════════════════════════════════════
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';

const navItems = [
  { path: '/', label: '首页', icon: '🏠' },
  { path: '/chat', label: '聊天', icon: '💬' },
  { path: '/game', label: '游戏', icon: '🎮' },
  { path: '/settings', label: '设置', icon: '⚙️' },
];

export default function MainLayout() {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* 页面内容 */}
      <main className="flex-1 overflow-hidden">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.2 }}
            className="h-full"
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>

      {/* 底部导航 */}
      <nav className="fixed bottom-0 left-0 right-0 bg-white/90 backdrop-blur-lg border-t border-gray-200/50 safe-area-bottom z-40">
        <div className="max-w-lg mx-auto flex justify-around py-2">
          {navItems.map(item => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex flex-col items-center py-1 px-3 rounded-ios-lg transition-all ${
                  isActive
                    ? 'text-brand-600 bg-brand-50'
                    : 'text-gray-500 hover:text-gray-700'
                }`
              }
            >
              <span className="text-xl">{item.icon}</span>
              <span className="text-xs mt-0.5">{item.label}</span>
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
