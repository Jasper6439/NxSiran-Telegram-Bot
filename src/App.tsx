import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import HomePage from './pages/HomePage'
import GamePage from './pages/GamePage'
import FarmPage from './pages/FarmPage'
import MediaPage from './pages/MediaPage'
import MonitorPage from './pages/MonitorPage'
import SettingsPage from './pages/SettingsPage'
import TabBar from './components/TabBar'

// ─────────────────────────────────────────────────────────────────────────────
// AppLayout — iOS TabBar 外壳
// ─────────────────────────────────────────────────────────────────────────────

function AppLayout() {
  const location = useLocation()
  const hideTabBar = location.pathname === '/login'
  return (
    <>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/game" element={<GamePage />} />
        <Route path="/farm" element={<FarmPage />} />
        <Route path="/media" element={<MediaPage />} />
        <Route path="/monitor" element={<MonitorPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
      {!hideTabBar && <TabBar />}
    </>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// App 入口
// ─────────────────────────────────────────────────────────────────────────────

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/*" element={<AppLayout />} />
      </Routes>
    </BrowserRouter>
  )
}