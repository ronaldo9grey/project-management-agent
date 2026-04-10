import { Link } from 'react-router-dom'
import { redirectToLogin, safeRedirect } from '../utils/auth'
import MobileNav from '../components/MobileNav'
import { useState, useEffect } from 'react'
import { useAppStore } from '../store'
import { projectApi } from '../api'

interface Project {
  id: number
  name: string
  leader: string
  status: string
  progress: number
}

export default function ProjectsPage() {
  const { user, logout } = useAppStore()
  const [projects, setProjects] = useState<Project[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [showUserMenu, setShowUserMenu] = useState(false)

  useEffect(() => {
    loadProjects()
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

  const loadProjects = async () => {
    try {
      const data = await projectApi.getMyProjects()
      setProjects(data)
    } catch (error) {
      console.error('加载项目失败:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const filteredProjects = projects.filter(p =>
    p.name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const getStatusTag = (status: string) => {
    switch (status) {
      case '进行中':
        return <span className="tag tag-success">进行中</span>
      case '规划中':
        return <span className="tag tag-warning">规划中</span>
      case '已完成':
        return <span className="tag tag-info">已完成</span>
      default:
        return <span className="tag tag-default">{status}</span>
    }
  }

  const handleLogout = () => {
    logout()
    redirectToLogin()
  }

  const goToDetail = (projectId: number) => {
    safeRedirect(`/agent/projects/${projectId}`)
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
              <Link to="/projects" className="nav-link active">项目</Link>
              <Link to="/chat" className="nav-link">问答</Link>
              <Link to="/dashboard" className="nav-link">看板</Link>
            </nav>
          </div>
          <div className="header-right">
            <div className="user-menu-wrapper">
              <div 
                className="user-info"
                onClick={() => setShowUserMenu(!showUserMenu)}
              >
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
        {/* PC端标题行 */}
        <div className="projects-header-row">
          <div className="projects-header-info">
            <span className="projects-count">共 {projects.length} 个项目</span>
          </div>
          <input
            type="text"
            placeholder="搜索项目..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input projects-search"
          />
        </div>

        {/* 项目列表 */}
        <div className="projects-grid">
            {isLoading ? (
              <div className="empty-state">
                <span className="spinner"></span>
                <p className="text-gray-500 mt-2">加载中...</p>
              </div>
            ) : filteredProjects.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">📁</div>
                <p className="empty-title">暂无项目</p>
                <p className="empty-desc">您还没有参与任何项目</p>
              </div>
            ) : (
              filteredProjects.map((project) => (
                <div
                  key={project.id}
                  className="project-card"
                  onClick={() => goToDetail(project.id)}
                >
                  <div className="project-card-header">
                    <h3 className="project-card-name">{project.name}</h3>
                    {getStatusTag(project.status)}
                  </div>
                  <div className="project-card-meta">
                    <span>👤 {project.leader || '未指定'}</span>
                  </div>
                  <div className="project-card-progress">
                    <div className="progress-bar">
                      <div
                        className="progress-bar-fill"
                        style={{ width: `${project.progress}%` }}
                      />
                    </div>
                    <span className="project-card-progress-text">{project.progress}%</span>
                  </div>
                  <div className="project-card-action">
                    <span>查看详情</span>
                    <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </div>
              ))
            )}
        </div>
      </main>

      {/* 移动端底部导航 */}
      <MobileNav active="projects" />
    </div>
  )
}
