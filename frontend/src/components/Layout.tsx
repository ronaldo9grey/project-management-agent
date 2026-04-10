import { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useAppStore } from '../store'
import { notificationApi } from '../api'
import { redirectToLogin } from '../utils/auth'
import { confirm } from './ConfirmDialog'

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const { user, logout } = useAppStore()
  const location = useLocation()
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [notificationUnread, setNotificationUnread] = useState(0)

  // 获取未读通知数
  useEffect(() => {
    const fetchNotifications = async () => {
      try {
        const data = await notificationApi.getList(true, 1)
        setNotificationUnread(data.unread_count || 0)
      } catch {}
    }
    fetchNotifications()
  }, [])

  // 点击外部关闭用户菜单
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      if (showUserMenu && !target.closest('.user-menu-wrapper')) {
        setShowUserMenu(false)
      }
    }
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [showUserMenu])

  const handleLogout = async () => {
    const confirmed = await confirm({
      title: '确认退出登录？',
      message: '退出后需要重新登录才能使用系统功能。',
      confirmText: '退出',
      cancelText: '取消',
      type: 'warning'
    })
    
    if (confirmed) {
      logout()
      redirectToLogin()
    }
  }

  // 导航项配置
  const navItems = [
    { path: '/', label: '个人' },
    { path: '/daily', label: '日报' },
    { path: '/projects', label: '项目' },
    { path: '/chat', label: '问答' },
    { path: '/dashboard', label: '看板' },
  ]

  // 判断当前路径
  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/'
    }
    return location.pathname.startsWith(path)
  }

  return (
    <div className="page-container">
      {/* 顶部导航 */}
      <header className="header">
        <div className="header-content">
          <div className="header-left">
            <Link to="/" className="header-logo">
              <span className="text-xl">⚙️</span>
              <span>项目管家</span>
            </Link>
            <nav className="header-nav">
              {navItems.map(item => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`nav-link ${isActive(item.path) ? 'active' : ''}`}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="header-right">
            {/* 通知图标 */}
            <Link to="/notifications" className="notification-bell">
              🔔
              {notificationUnread > 0 && (
                <span className="notification-badge">
                  {notificationUnread > 99 ? '99+' : notificationUnread}
                </span>
              )}
            </Link>
            
            <div className="user-menu-wrapper">
              <div className="user-info" onClick={() => setShowUserMenu(!showUserMenu)}>
                <div className="user-avatar" style={{
                  background: 'linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)',
                  color: 'white',
                  fontWeight: '600'
                }}>
                  {user?.name?.[0]?.toUpperCase() || 'U'}
                </div>
                <span className="user-name">{user?.name || '用户'}</span>
                <svg 
                  className={`w-4 h-4 text-gray-400 transition-transform ${showUserMenu ? 'rotate-180' : ''}`} 
                  fill="none" 
                  stroke="currentColor" 
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </div>
              {showUserMenu && (
                <div className="user-dropdown">
                  <div className="user-dropdown-header">
                    <div className="user-avatar-lg" style={{
                      background: 'linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)',
                      color: 'white',
                      fontWeight: '600'
                    }}>
                      {user?.name?.[0]?.toUpperCase() || 'U'}
                    </div>
                    <div>
                      <div className="font-medium text-gray-900">{user?.name || '用户'}</div>
                      {user?.department && <div className="text-sm text-gray-600">{user.department}</div>}
                      {user?.position && <div className="text-xs text-gray-500">{user.position}</div>}
                    </div>
                  </div>
                  <div className="user-dropdown-divider" />
                  <Link to="/plans" className="user-dropdown-item" onClick={() => setShowUserMenu(false)}>
                    📋 我的计划
                  </Link>
                  <button onClick={handleLogout} className="user-dropdown-item text-red-600">
                    退出登录
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* 主内容区 */}
      <main className="content-wrapper">
        {children}
      </main>
    </div>
  )
}