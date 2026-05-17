// ═══════════════════════════════════════════════════════════════════════════
// 路由配置 v1.9.5 - 游戏模块完全隔离
// 农场 /farm 和校园 /campus 独立路由，互斥渲染
// ═══════════════════════════════════════════════════════════════════════════
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { lazy, Suspense } from 'react';

// 布局
import MainLayout from '../layouts/MainLayout';

// 页面 - 使用懒加载优化性能
const HomePage = lazy(() => import('../features/home/HomePage'));
const ChatPage = lazy(() => import('../features/chat/ChatPage'));
const GameHubPage = lazy(() => import('../features/game/GameHubPage'));
const FarmPage = lazy(() => import('../features/game/FarmPage'));
const CampusPage = lazy(() => import('../features/game/CampusPage'));
const SettingsPage = lazy(() => import('../features/settings/SettingsPage'));

// 加载占位
const PageLoader = () => (
  <div className="min-h-screen flex items-center justify-center">
    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-500" />
  </div>
);

// 带 Suspense 的页面包装
const withSuspense = (Component: React.ComponentType) => (
  <Suspense fallback={<PageLoader />}>
    <Component />
  </Suspense>
);

export const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      { index: true, element: withSuspense(HomePage) },
      { path: 'chat', element: withSuspense(ChatPage) },
      
      // 游戏中心 - 选择入口
      { path: 'game', element: withSuspense(GameHubPage) },
      
      // 农场游戏 - 完全独立路由
      { path: 'farm', element: withSuspense(FarmPage) },
      
      // 校园漫游 - 完全独立路由  
      { path: 'campus', element: withSuspense(CampusPage) },
      
      { path: 'settings', element: withSuspense(SettingsPage) },
      
      // 旧路由重定向
      { path: 'miniapp', element: <Navigate to="/game" replace /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]);

// 路由元数据（供导航使用）
export const ROUTE_META = {
  home: { path: '/', label: '首页', icon: '🏠' },
  chat: { path: '/chat', label: '聊天', icon: '💬' },
  game: { path: '/game', label: '游戏', icon: '🎮' },
  farm: { path: '/farm', label: '农场', icon: '🌾' },
  campus: { path: '/campus', label: '校园', icon: '🏫' },
  settings: { path: '/settings', label: '设置', icon: '⚙️' },
} as const;

export type RouteKey = keyof typeof ROUTE_META;
