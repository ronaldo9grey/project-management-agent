import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import HomePage from './pages/Home'
import DashboardPage from './pages/Dashboard'
import DailyPage from './pages/Daily'
import ProjectsPage from './pages/Projects'
import ProjectDetailPage from './pages/ProjectDetail'
import PlansPage from './pages/Plans'
import ChatPage from './pages/Chat'
import NotificationsPage from './pages/Notifications'
import WeeklyReportPage from './pages/WeeklyReport'
import LoginPage from './pages/Login'
import { ToastProvider } from './components/Toast'
import { ConfirmProvider } from './components/ConfirmDialog'
import { isAuthenticated } from './utils/auth'

function App() {
  return (
    <BrowserRouter basename="/agent">
      <ToastProvider>
        <ConfirmProvider>
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
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />
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
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
