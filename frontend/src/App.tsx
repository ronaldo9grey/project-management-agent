import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useEffect, useRef } from 'react'
import HomePage from './pages/Home'
import DashboardPage from './pages/Dashboard'
import DailyPage from './pages/Daily'
import ProjectsPage from './pages/Projects'
import ProjectDetailPage from './pages/ProjectDetail'
import PlansPage from './pages/Plans'
import ChatPage from './pages/Chat'
import NotificationsPage from './pages/Notifications'
import WeeklyReportPage from './pages/WeeklyReport'
import TrackingPage from './pages/Tracking'
import QualityPage from './pages/Quality'
import ReportPage from './pages/Report'
import LoginPage from './pages/Login'
import { ToastProvider } from './components/Toast'
import { ConfirmProvider } from './components/ConfirmDialog'
import { isAuthenticated } from './utils/auth'
import { useAppStore } from './store'

// 路由变化时取消未完成的请求
function RouteChangeListener() {
  const location = useLocation()
  const lastPath = useRef<string>('')
  
  useEffect(() => {
    // 路由变化时不再取消所有请求
    // 原因：cancelAllRequests 会中断TCP连接，在移动网络下
    // 被中断的连接被Nginx keepalive池复用，导致 ERR_CONNECTION_RESET
    // 改为仅记录路由变化，让请求自然完成或超时
    if (lastPath.current !== location.pathname) {
      if (import.meta.env.DEV) {
        console.log('路由切换:', lastPath.current, '->', location.pathname)
      }
      lastPath.current = location.pathname
    }
  }, [location.pathname])
  
  return null
}

// 心跳保活 - 已禁用
// 原因：刷新页面时心跳请求被取消，可能导致连接重置
// 如果用户长时间停留后连接断开，再考虑重新启用
function useHeartbeat() {
  // 暂时禁用
  // const token = useAppStore(state => state.token)
  // const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  // ... 心跳逻辑已禁用
}

function App() {
  return (
    <BrowserRouter basename="/agent">
      <ToastProvider>
        <ConfirmProvider>
          <RouteChangeListener />
          <Routes>
            {/* 登录页 */}
            <Route path="/login" element={<LoginPage />} />
            
            {/* 需要认证的页面 - 暂时保持页面独立 header */}
            <Route
              path="/*"
              element={
                <ProtectedRoutes />
              }
            />
          </Routes>
        </ConfirmProvider>
      </ToastProvider>
    </BrowserRouter>
  )
}

// 认证保护组件
function ProtectedRoutes() {
  // 启动心跳保活
  useHeartbeat()
  const user = useAppStore(state => state.user)
  const userRoleId = user?.role_id || 13
  
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />
  }
  
  // 看板角色(role_id=17)只能访问看板页面
  if (userRoleId === 17) {
    return (
      <Routes>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    )
  }
  
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/daily" element={<DailyPage />} />
      <Route path="/projects" element={<ProjectsPage />} />
      <Route path="/projects/:id" element={<ProjectDetailPage />} />
      <Route path="/plans" element={<PlansPage />} />
      <Route path="/chat" element={<ChatPage />} />
      <Route path="/notifications" element={<NotificationsPage />} />
      <Route path="/report" element={<WeeklyReportPage />} />
      <Route path="/tracking" element={<TrackingPage />} />
      <Route path="/quality" element={<QualityPage />} />
      <Route path="/system-report" element={<ReportPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
