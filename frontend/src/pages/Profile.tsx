import { redirectToLogin } from '../utils/auth'
import MobileNav from '../components/MobileNav'
import { useState, useEffect } from 'react'
import { useAppStore } from '../store'
import { statsApi, dashboardApi } from '../api'

export default function ProfilePage() {
  const { user, logout } = useAppStore()
  const [stats, setStats] = useState({
    monthReports: 0,
    monthHours: 0,
    projectCount: 0
  })
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    loadStats()
  }, [])

  const loadStats = async () => {
    try {
      const [hoursData, focusData] = await Promise.all([
        statsApi.getWorkHoursStats().catch(() => ({ month: 0, projects: [] })),
        dashboardApi.getTodayFocus().catch(() => ({ week_overview: { project_count: 0 } }))
      ])
      
      // 本月日报数（从工时项目数推断活跃度）
      const projectCount = (hoursData.projects?.length || 0)
      
      setStats({
        monthReports: Math.round((hoursData.month || 0) / 8), // 粗略估算日报数
        monthHours: hoursData.month || 0,
        projectCount: focusData.week_overview?.project_count || projectCount
      })
    } catch (error) {
      console.error('加载统计数据失败:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleLogout = () => {
    logout()
    redirectToLogin()
  }

  const menuItems = [
    { icon: '📋', label: '我的日报', desc: '查看历史日报记录', href: '/agent/daily' },
    { icon: '📊', label: '工时统计', desc: '查看工时统计分析', href: '/agent/' },
    { icon: '⚙️', label: '账号设置', desc: '修改密码等设置', href: '#' },
    { icon: '❓', label: '帮助中心', desc: '使用指南和常见问题', href: '#' },
  ]

  return (
    <div className="page-container">
      {/* 顶部导航 */}
      <header className="header">
        <div className="header-content">
          <div className="header-left">
            <a href="/agent/" className="header-logo">
              <span className="text-xl">⚙️</span>
              <span>项目管家</span>
            </a>
            <nav className="header-nav">
              <a href="/agent/" className="nav-link active">个人</a>
              <a href="/agent/daily" className="nav-link">日报</a>
              <a href="/agent/projects" className="nav-link">项目</a>
              <a href="/agent/chat" className="nav-link">问答</a>
              <a href="/agent/dashboard" className="nav-link">看板</a>
            </nav>
          </div>
          <div className="header-right">
            <div className="user-info">
              <div className="user-avatar" style={{
                background: `linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)`,
                color: 'white',
                fontWeight: '600'
              }}>{user?.name?.[0]?.toUpperCase() || 'U'}</div>
              <span className="user-name">{user?.name || '用户'}</span>
            </div>
          </div>
        </div>
      </header>

      {/* 主内容 */}
      <main className="content-wrapper">
        <div className="max-w-2xl mx-auto">
          {/* 用户信息卡片 */}
          <div className="card mb-6">
            <div className="card-body">
              <div className="profile-user-card">
                <div className="profile-avatar-lg">
                  {user?.name?.[0]?.toUpperCase() || 'U'}
                </div>
                <div className="profile-user-info">
                  <h1 className="profile-user-name">{user?.name || '用户'}</h1>
                  <p className="profile-user-id">工号：{user?.employee_id || user?.id || '-'}</p>
                  <div className="profile-user-tags">
                    {user?.role_name && <span className="tag tag-primary">{user.role_name}</span>}
                    {user?.department && <span className="text-sm text-gray-500">{user.department}</span>}
                  </div>
                </div>
              </div>
              
              {/* 详细信息 */}
              {(user?.email || user?.phone || user?.position) && (
                <div className="mt-6 pt-6 border-t border-gray-100">
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    {user.position && (
                      <div>
                        <span className="text-gray-400">职位：</span>
                        <span className="text-gray-600">{user.position}</span>
                      </div>
                    )}
                    {user.email && (
                      <div>
                        <span className="text-gray-400">邮箱：</span>
                        <span className="text-gray-600">{user.email}</span>
                      </div>
                    )}
                    {user.phone && (
                      <div>
                        <span className="text-gray-400">电话：</span>
                        <span className="text-gray-600">{user.phone}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* 统计概览 */}
          <div className="profile-stats mb-6">
            <div className="profile-stat-card">
              <div className="profile-stat-value blue">
                {isLoading ? '-' : stats.monthReports}
              </div>
              <div className="profile-stat-label">本月日报</div>
            </div>
            <div className="profile-stat-card">
              <div className="profile-stat-value green">
                {isLoading ? '-' : stats.monthHours.toFixed(1)}<span className="text-sm">h</span>
              </div>
              <div className="profile-stat-label">本月工时</div>
            </div>
            <div className="profile-stat-card">
              <div className="profile-stat-value purple">
                {isLoading ? '-' : stats.projectCount}
              </div>
              <div className="profile-stat-label">参与项目</div>
            </div>
          </div>

          {/* 功能菜单 */}
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">功能菜单</h2>
            </div>
            <div className="card-body">
              <div>
                {menuItems.map((item) => (
                  <a
                    key={item.label}
                    href={item.href}
                    className="profile-menu-item"
                  >
                    <span className="profile-menu-icon">{item.icon}</span>
                    <div className="profile-menu-content">
                      <p className="profile-menu-label">{item.label}</p>
                      <p className="profile-menu-desc">{item.desc}</p>
                    </div>
                    <span className="profile-menu-arrow">›</span>
                  </a>
                ))}
              </div>

              {/* 退出登录 */}
              <div className="mt-6 pt-6 border-t border-gray-100">
                <button
                  onClick={handleLogout}
                  className="w-full btn btn-danger"
                >
                  退出登录
                </button>
              </div>
            </div>
          </div>

          {/* 版本信息 */}
          <div className="text-center mt-8 text-sm text-gray-400">
            <p>项目管家 v0.1.0</p>
            <p className="mt-1">基于 LangChain + DeepSeek</p>
          </div>
        </div>
      </main>

      {/* 移动端底部导航 */}
      <MobileNav active="home" />
    </div>
  )
}
