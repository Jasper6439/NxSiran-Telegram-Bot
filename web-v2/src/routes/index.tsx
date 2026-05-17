// ═══════════════════════════════════════════════════════════════════════════
// 路由配置 - 核心页面路由
// ═══════════════════════════════════════════════════════════════════════════
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { lazy, Suspense } from 'react';

// 布局
import MainLayout from '../layouts/MainLayout';

// 页面 - 使用懒加载优化性能
const HomePage = lazy(() => import('../features/home/HomePage'));
const ChatPage = lazy(() => import('../features/chat/ChatPage'));
const SettingsPage = lazy(() => import('../features/settings/SettingsPage'));

// 游戏容器 (dual-world layout)
const GameContainer = lazy(() => import('../features/game/GameContainer'));

// 游戏场景
const ActionPage = lazy(() => import('../features/game/action/ActionPage'));

// 农场页面 (Phaser + React hybrid)
const FarmPage = lazy(() => import('../features/game/farm/FarmPage'));

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
      { path: 'settings', element: withSuspense(SettingsPage) },
      // Game routes - GameContainer acts as layout with dual-world effects
      {
        path: 'game',
        element: withSuspense(GameContainer),
        children: [
          { index: true, element: <Navigate to="/game/farm" replace /> },
          { path: 'farm', element: withSuspense(FarmPage) },
          { path: 'action', element: withSuspense(ActionPage) },
        ],
      },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]);

// 路由元数据（供导航使用）
export const ROUTE_META = {
  home: { path: '/', label: '首页', icon: '🏠' },
  chat: { path: '/chat', label: '聊天', icon: '💬' },
  game: { path: '/game', label: '游戏', icon: '🎮' },
  settings: { path: '/settings', label: '设置', icon: '⚙️' },
} as const;

export type RouteKey = keyof typeof ROUTE_META;
