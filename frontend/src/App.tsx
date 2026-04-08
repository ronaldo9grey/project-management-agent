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

// 获取基础路径
const BASE_PATH = '/agent'

function App() {
  const fullPath = window.location.pathname
  // 去掉基础路径获取实际路由
  const path = fullPath.startsWith(BASE_PATH) 
    ? fullPath.slice(BASE_PATH.length) || '/'
    : fullPath

  // 登录页面直接渲染，不做任何重定向
  if (path === '/login') {
    return <LoginPage />
  }

  // 其他页面检查登录状态
  const storage = localStorage.getItem('project-agent-storage')
  let token = null
  if (storage) {
    try {
      const data = JSON.parse(storage)
      token = data.state?.token
    } catch {}
  }

  // 未登录跳转到登录页
  if (!token) {
    window.location.href = `${BASE_PATH}/login`
    return null
  }

  // 检查是否为项目详情页
  const projectDetailMatch = path.match(/^\/projects\/(\d+)$/)
  
  // 已登录，根据路径渲染
  return (
    <ToastProvider>
      <ConfirmProvider>
        <div className="min-h-screen bg-gray-50">
          {path === '/' && <HomePage />}
          {path === '/dashboard' && <DashboardPage />}
          {path === '/daily' && <DailyPage />}
          {path === '/projects' && <ProjectsPage />}
          {path === '/plans' && <PlansPage />}
          {path === '/chat' && <ChatPage />}
          {path === '/notifications' && <NotificationsPage />}
          {path === '/report' && <WeeklyReportPage />}
          {projectDetailMatch && <ProjectDetailPage />}
        </div>
      </ConfirmProvider>
    </ToastProvider>
  )
}

export default App
