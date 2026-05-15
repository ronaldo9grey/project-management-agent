import SharedHeader from '../components/SharedHeader'
import MobileNav from '../components/MobileNav'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { projectApi } from '../api'

interface Project {
  id: number
  name: string
  leader: string
  status: string
  progress: number
  project_year?: number
}

export default function ProjectsPage() {
  const navigate = useNavigate()
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

  // 按年度分组
  const currentYear = new Date().getFullYear()
  const currentYearProjects = projects.filter(p => 
    (p.project_year === currentYear || !p.project_year) && 
    p.name.toLowerCase().includes(searchQuery.toLowerCase())
  )
  const historicalProjects = projects.filter(p => 
    p.project_year && p.project_year < currentYear && 
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


  const goToDetail = (projectId: number) => {
    navigate(`/projects/${projectId}`)
  }

  // 渲染项目卡片
  const renderProjectCards = (projectList: Project[]) => (
    projectList.map((project) => (
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
  )

  return (
    <div className="page-container">
      {/* 顶部导航 */}
      <SharedHeader />

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

        {isLoading ? (
          <div className="empty-state">
            <span className="spinner"></span>
            <p className="text-gray-500 mt-2">加载中...</p>
          </div>
        ) : (
          <>
            {/* 本年度项目 */}
            {currentYearProjects.length > 0 && (
              <div style={{ marginBottom: '32px' }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  marginBottom: '16px',
                  padding: '12px 16px',
                  background: 'linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%)',
                  borderRadius: '12px',
                  border: '1px solid #bfdbfe'
                }}>
                  <span style={{ fontSize: '20px' }}>🚀</span>
                  <div>
                    <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#1e40af', margin: 0 }}>
                      {currentYear}年度项目
                    </h2>
                    <p style={{ fontSize: '13px', color: '#64748b', margin: '4px 0 0' }}>
                      {currentYearProjects.length} 个进行中的项目
                    </p>
                  </div>
                </div>
                <div className="projects-grid">
                  {renderProjectCards(currentYearProjects)}
                </div>
              </div>
            )}

            {/* 历史项目 */}
            {historicalProjects.length > 0 && (
              <div>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  marginBottom: '16px',
                  padding: '12px 16px',
                  background: 'linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%)',
                  borderRadius: '12px',
                  border: '1px solid #cbd5e1'
                }}>
                  <span style={{ fontSize: '20px' }}>📚</span>
                  <div>
                    <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#475569', margin: 0 }}>
                      历史项目
                    </h2>
                    <p style={{ fontSize: '13px', color: '#64748b', margin: '4px 0 0' }}>
                      {historicalProjects.length} 个已完成项目
                    </p>
                  </div>
                </div>
                <div className="projects-grid">
                  {renderProjectCards(historicalProjects)}
                </div>
              </div>
            )}

            {/* 无项目 */}
            {currentYearProjects.length === 0 && historicalProjects.length === 0 && (
              <div className="empty-state">
                <div className="empty-icon">📁</div>
                <p className="empty-title">暂无项目</p>
                <p className="empty-desc">您还没有参与任何项目</p>
              </div>
            )}
          </>
        )}
      </main>

      {/* 移动端底部导航 */}
      <MobileNav active="projects" />
    </div>
  )
}