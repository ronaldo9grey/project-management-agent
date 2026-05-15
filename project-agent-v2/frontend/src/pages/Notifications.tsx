import { Link } from 'react-router-dom'
import { redirectToLogin } from '../utils/auth'
import MobileNav from '../components/MobileNav'
import { useState, useEffect } from 'react'
import { useAppStore } from '../store'
import { notificationApi } from '../api'

interface Notification {
  id: number
  type: string
  priority: string
  title: string
  content: string
  is_read: boolean
  create_time: string
  related_task_id: string | null
}

export default function NotificationsPage() {
  const { user, logout } = useAppStore()
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | 'unread'>('all')

  useEffect(() => {
    loadNotifications()
  }, [filter])

  const loadNotifications = async () => {
    setIsLoading(true)
    try {
      const result = await notificationApi.getList(filter === 'unread', 50)
      setNotifications(result.notifications)
      setUnreadCount(result.unread_count)
    } catch (error) {
      console.error('加载通知失败:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleMarkRead = async (id: number) => {
    try {
      await notificationApi.markRead(id)
      setNotifications(prev => prev.map(n => n.id === id ? {...n, is_read: true} : n))
      setUnreadCount(prev => Math.max(0, prev - 1))
    } catch (error) {
      console.error('标记失败:', error)
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await notificationApi.markAllRead()
      setNotifications(prev => prev.map(n => ({...n, is_read: true})))
      setUnreadCount(0)
    } catch (error) {
      console.error('全部已读失败:', error)
    }
  }

  const handleGenerate = async () => {
    try {
      const result = await notificationApi.generate()
      if (result.success && result.count > 0) {
        loadNotifications()
      }
    } catch (error) {
      console.error('生成通知失败:', error)
    }
  }

  const handleLogout = () => {
    logout()
    redirectToLogin()
  }

  const getPriorityStyle = (priority: string) => {
    switch (priority) {
      case '紧急': return { bg: '#fef2f2', color: '#ef4444', border: '#fecaca' }
      case '高': return { bg: '#fff7ed', color: '#f97316', border: '#fed7aa' }
      case '中': return { bg: '#eff6ff', color: '#3b82f6', border: '#bfdbfe' }
      default: return { bg: '#f8fafc', color: '#64748b', border: '#e2e8f0' }
    }
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'task_reminder': return '📋'
      case 'delay_warning': return '⚠️'
      case 'daily_reminder': return '📝'
      default: return '🔔'
    }
  }

  const formatTime = (timeStr: string) => {
    const date = new Date(timeStr)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    
    if (diff < 60000) return '刚刚'
    if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
    if (diff < 172800000) return '昨天'
    return date.toLocaleDateString('zh-CN')
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
              <Link to="/" className="nav-link">个人</Link>
              <Link to="/daily" className="nav-link">日报</Link>
              <Link to="/projects" className="nav-link">项目</Link>
              <Link to="/chat" className="nav-link">问答</Link>
              <Link to="/dashboard" className="nav-link">看板</Link>
            </nav>
          </div>
          <div className="header-right">
            {/* 通知图标 */}
            <Link to="/notifications" className="notification-bell">
              🔔
              {unreadCount > 0 && (
                <span className="notification-badge">{unreadCount > 99 ? '99+' : unreadCount}</span>
              )}
            </Link>
            
            <div className="user-menu-wrapper">
              <div className="user-info" onClick={() => setShowUserMenu(!showUserMenu)}>
                <div className="user-avatar">{user?.name?.[0]?.toUpperCase() || 'U'}</div>
                <span className="user-name">{user?.name || '用户'}</span>
                <svg className={`w-4 h-4 text-gray-400 transition-transform ${showUserMenu ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </div>
              {showUserMenu && (
                <div className="user-dropdown">
                  <div className="user-dropdown-header">
                    <div className="user-avatar-lg">{user?.name?.[0]?.toUpperCase() || 'U'}</div>
                    <div>
                      <div className="font-medium text-gray-900">{user?.name || '用户'}</div>
                      {user?.department && <div className="text-sm text-gray-600">{user.department}</div>}
                      {user?.position && <div className="text-xs text-gray-500">{user.position}</div>}
                    </div>
                  </div>
                  <div className="user-dropdown-divider" />
                  <button className="user-dropdown-item" onClick={handleLogout}>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                    </svg>
                    退出登录
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* 主内容 */}
      <main className="content-wrapper">
        {/* 标题和操作 */}
        <div className="flex items-center justify-between mb-6 flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">🔔 系统通知</h1>
            <p className="text-gray-500 mt-1">智能提醒，数据追人</p>
          </div>
          <div className="flex gap-2">
            <button onClick={handleGenerate} className="btn btn-secondary btn-sm">
              🔄 生成通知
            </button>
            {unreadCount > 0 && (
              <button onClick={handleMarkAllRead} className="btn btn-secondary btn-sm">
                ✓ 全部已读
              </button>
            )}
          </div>
        </div>

        {/* 筛选 */}
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setFilter('all')}
            className={`tag cursor-pointer ${filter === 'all' ? 'tag-primary' : 'tag-default'}`}
          >
            全部
          </button>
          <button
            onClick={() => setFilter('unread')}
            className={`tag cursor-pointer ${filter === 'unread' ? 'tag-primary' : 'tag-default'}`}
          >
            未读 ({unreadCount})
          </button>
        </div>

        {/* 通知列表 */}
        {isLoading ? (
          <div className="empty-state" style={{padding: '80px'}}>
            <span className="spinner" style={{width: '40px', height: '40px'}}></span>
            <p className="text-gray-500 mt-4">加载中...</p>
          </div>
        ) : notifications.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📭</div>
            <p className="empty-title">暂无通知</p>
            <p className="empty-desc">点击"生成通知"获取最新提醒</p>
          </div>
        ) : (
          <div className="space-y-3">
            {notifications.map((n) => {
              const priorityStyle = getPriorityStyle(n.priority)
              return (
                <div
                  key={n.id}
                  className={`notification-card ${!n.is_read ? 'unread' : ''}`}
                  style={{
                    background: n.is_read ? 'rgba(255,255,255,0.6)' : 'rgba(255,255,255,0.95)',
                    borderLeft: `4px solid ${priorityStyle.color}`
                  }}
                >
                  <div className="flex items-start gap-3">
                    <span className="text-2xl">{getTypeIcon(n.type)}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-gray-900">{n.title}</span>
                        <span
                          className="tag"
                          style={{
                            background: priorityStyle.bg,
                            color: priorityStyle.color,
                            border: `1px solid ${priorityStyle.border}`
                          }}
                        >
                          {n.priority}
                        </span>
                      </div>
                      <p className="text-gray-600 text-sm whitespace-pre-wrap">{n.content}</p>
                      <div className="flex items-center justify-between mt-2">
                        <span className="text-xs text-gray-400">{formatTime(n.create_time)}</span>
                        {!n.is_read && (
                          <button
                            onClick={() => handleMarkRead(n.id)}
                            className="text-xs text-blue-500 hover:text-blue-700"
                          >
                            标记已读
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </main>

      {/* 移动端底部导航 */}
      <MobileNav active="home" />
    </div>
  )
}
