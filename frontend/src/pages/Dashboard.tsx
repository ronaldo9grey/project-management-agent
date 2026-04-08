import { useState, useEffect } from 'react'
import { useAppStore } from '../store'
import MobileNav from '../components/MobileNav'
import DashboardTaskList from '../components/DashboardTaskList'

// 判断是否手机端
const useIsMobile = () => {
  const [isMobile, setIsMobile] = useState(false)
  
  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768)
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])
  
  return isMobile
}

interface DashboardStats {
  ongoing_projects: number
  completed_projects: number
  total_projects: number
  total_budget: number
  total_actual: number
  high_alerts: number
  medium_alerts: number
  low_alerts: number
  total_alerts: number
}

interface Task {
  task_id: string
  task_name: string
  start_date: string | null
  end_date: string | null
  actual_end_date: string | null
  progress: number
  status: string
}

interface ProjectAlert {
  type: string
  severity: string
  title: string
  content: string
}

interface Project {
  id: number
  name: string
  leader: string
  status: string
  progress: number
  planned_progress: number
  actual_progress: number
  start_date: string | null
  end_date: string | null
  contract_amount: number
  budget_total_cost: number
  actual_total_cost: number
  tasks: Task[]
  alerts: ProjectAlert[]
}

export default function DashboardPage() {
  const { token, user, logout } = useAppStore()
  const [showUserMenu, setShowUserMenu] = useState(false)
  const isMobile = useIsMobile()

  const handleLogout = () => {
    logout()
    window.location.href = '/agent/login'
  }
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [projects, setProjects] = useState<Project[]>([])
  const [insight, setInsight] = useState<string>('')
  const [isLoading, setIsLoading] = useState(true)
  const [searchText, setSearchText] = useState('')

  useEffect(() => {
    loadDashboardData()
  }, [])

  const loadDashboardData = async () => {
    setIsLoading(true)
    try {
      const headers = { Authorization: `Bearer ${token}` }

      const [overviewRes, projectsRes, insightRes] = await Promise.all([
        fetch('/api/agent/dashboard/overview', { headers }).then(r => r.json()),
        fetch('/api/agent/dashboard/projects', { headers }).then(r => r.json()),
        fetch('/api/agent/dashboard/insight', { headers }).then(r => r.json())
      ])

      setStats(overviewRes.stats)
      setProjects(projectsRes)
      setInsight(insightRes.content)
    } catch (error) {
      console.error('加载看板数据失败:', error)
    } finally {
      setIsLoading(false)
    }
  }

  function formatMoney(value: number | undefined): string {
    const v = value || 0
    if (v >= 10000) {
      return `${(v / 10000).toFixed(1)}万`
    }
    return v.toFixed(0)
  }

  function parseInsight(text: string) {
    const lines = text.split('\n').filter(l => l.trim())
    return lines.length > 1 ? lines : [text]
  }

  function getTaskStatus(progress: number, endDate: string | null): string {
    if (progress >= 100) return 'completed'
    if (endDate && new Date(endDate) < new Date() && progress < 100) return 'delayed'
    if (progress > 0) return 'ongoing'
    return 'pending'
  }

  // 过滤项目
  const filteredProjects = searchText.trim() 
    ? projects.filter(p => p.name.toLowerCase().includes(searchText.toLowerCase()))
    : projects

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return '-'
    const date = new Date(dateStr)
    return `${date.getMonth() + 1}/${date.getDate()}`
  }

  if (isLoading) {
    return (
      <div className="page-container">
        <header className="header">
          <div className="header-content">
            <div className="header-left">
              <a href="/agent/" className="header-logo">
                <span className="text-xl">⚙️</span>
                <span>项目管家</span>
              </a>
            </div>
          </div>
        </header>
        <main className="content-wrapper">
          {/* 骨架屏 */}
          <div className="skeleton skeleton-text mb-6" style={{ width: '150px', height: '28px' }} />
          
          <div className="grid-4 mb-6">
            {[1,2,3,4].map(i => (
              <div key={i} className="skeleton skeleton-card" />
            ))}
          </div>
          
          <div className="grid-2 mb-6">
            <div className="card">
              <div className="card-header">
                <div className="skeleton skeleton-text" style={{ width: '120px' }} />
              </div>
              <div className="card-body">
                {[1,2,3,4,5].map(i => (
                  <div key={i} className="skeleton skeleton-item mb-2" style={{ height: '40px' }} />
                ))}
              </div>
            </div>
            <div className="card">
              <div className="card-header">
                <div className="skeleton skeleton-text" style={{ width: '100px' }} />
              </div>
              <div className="card-body">
                <div className="skeleton skeleton-box" style={{ height: '200px' }} />
              </div>
            </div>
          </div>
        </main>
      </div>
    )
  }

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
              <a href="/agent/" className="nav-link">个人</a>
              <a href="/agent/daily" className="nav-link">日报</a>
              <a href="/agent/projects" className="nav-link">项目</a>
              <a href="/agent/chat" className="nav-link">问答</a>
              <a href="/agent/dashboard" className="nav-link active">看板</a>
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
        <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        
        {/* 统计卡片 */}
        <div className="dashboard-stats-grid">
          <div className="dashboard-stat-card">
            <div className="dashboard-stat-value">{stats?.ongoing_projects || 0}</div>
            <div className="dashboard-stat-label">📊 进行中</div>
          </div>
          <div className="dashboard-stat-card">
            <div className="dashboard-stat-value" style={{ color: '#22c55e' }}>{stats?.completed_projects || 0}</div>
            <div className="dashboard-stat-label">✅ 已完成</div>
          </div>
          <div className="dashboard-stat-card">
            <div className="dashboard-stat-value">¥{formatMoney(stats?.total_budget || 0)}</div>
            <div className="dashboard-stat-label">📋 总合同额</div>
          </div>
          <div className="dashboard-stat-card">
            <div className="dashboard-stat-value" style={{ color: '#f59e0b' }}>¥{formatMoney(stats?.total_actual || 0)}</div>
            <div className="dashboard-stat-label">💰 总成本</div>
          </div>
        </div>

        {/* AI 洞察 */}
        {insight && (
          <div style={{ background: 'white', borderRadius: '8px', border: '1px solid #e5e7eb', marginBottom: '20px' }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid #e5e7eb' }}>
              <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '600' }}>🤖 AI 每日洞察</h3>
            </div>
            <div style={{ padding: '20px' }}>
              {parseInsight(insight).map((line, i) => (
                <p key={i} style={{ margin: i === 0 ? 0 : '12px 0 0 0', lineHeight: '1.8', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                  {line}
                </p>
              ))}
            </div>
          </div>
        )}

        {/* 项目时间线 */}
        <div className="dashboard-timeline">
          <div className="dashboard-timeline-header">
            <h3 className="dashboard-timeline-title">📅 项目时间线</h3>
            <input
              type="text"
              placeholder="搜索项目..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              className="dashboard-search-input"
            />
            <div style={{ flex: 1 }}></div>
            <div className="dashboard-legend">
              <span>✅ 已完成</span>
              <span>🔴 已延期</span>
              <span>🟢 进行中</span>
              <span>⏳ 待开始</span>
            </div>
          </div>
          <div style={{ padding: '20px' }}>
            {filteredProjects.length === 0 && searchText && (
              <div style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
                未找到匹配"{searchText}"的项目
              </div>
            )}
            {filteredProjects.map(project => (
              <div key={project.id} style={{ marginBottom: '24px' }}>
                {/* 项目标题 */}
                <div style={{ 
                  padding: '12px 16px', 
                  background: project.alerts.length > 0 ? '#fef2f2' : '#f9fafb',
                  borderRadius: '8px',
                  border: `1px solid ${project.alerts.length > 0 ? '#fecaca' : '#e5e7eb'}`
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: '500', fontSize: '15px' }}>
                      {project.name}
                      {project.alerts.length > 0 && (
                        <span style={{ marginLeft: '8px', fontSize: '12px', color: '#ef4444' }}>
                          🔴 {project.alerts.length}个预警
                        </span>
                      )}
                    </span>
                    <span style={{ fontWeight: '600', fontSize: '15px', color: project.progress >= 100 ? '#22c55e' : '#3b82f6' }}>
                      {project.progress.toFixed(1)}%
                    </span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginTop: '10px', fontSize: '12px', color: '#666' }}>
                    <div>负责人：{project.leader || '-'}</div>
                    <div>开始时间：{project.start_date || '-'}</div>
                    <div>结束时间：{project.end_date || '-'}</div>
                    <div>合同金额：¥{formatMoney(project.contract_amount)}</div>
                  </div>
                  
                  {/* 预警信息 */}
                  {project.alerts.length > 0 && (
                    <div style={{ marginTop: '10px', padding: '8px', background: 'white', borderRadius: '4px', fontSize: '12px' }}>
                      {project.alerts.map((alert, i) => (
                        <div key={i} style={{ color: alert.severity === 'high' ? '#ef4444' : '#f59e0b' }}>
                          ⚠️ {alert.content}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                
                {/* 计划进度 vs 实际进度 */}
                <div style={{ marginTop: '12px', padding: '0 10px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', marginBottom: '6px' }}>
                    <span style={{ fontSize: '12px', color: '#666', width: '80px' }}>计划进度：</span>
                    <div style={{ flex: 1, height: '8px', background: '#e5e7eb', borderRadius: '4px', overflow: 'hidden' }}>
                      <div style={{ 
                        width: `${project.planned_progress}%`, 
                        height: '100%', 
                        background: '#3b82f6',
                        transition: 'width 0.3s'
                      }}></div>
                    </div>
                    <span style={{ fontSize: '12px', color: '#3b82f6', marginLeft: '8px', width: '40px' }}>{project.planned_progress.toFixed(0)}%</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <span style={{ fontSize: '12px', color: '#666', width: '80px' }}>实际进度：</span>
                    <div style={{ flex: 1, height: '8px', background: '#e5e7eb', borderRadius: '4px', overflow: 'hidden' }}>
                      <div style={{ 
                        width: `${project.actual_progress}%`, 
                        height: '100%', 
                        background: project.actual_progress >= 100 ? '#22c55e' : '#f59e0b',
                        transition: 'width 0.3s'
                      }}></div>
                    </div>
                    <span style={{ fontSize: '12px', color: project.actual_progress >= 100 ? '#22c55e' : '#f59e0b', marginLeft: '8px', width: '40px' }}>{project.actual_progress.toFixed(0)}%</span>
                  </div>
                </div>
                
                {/* 时间线 */}
                {project.tasks.length > 0 && (
                  <div style={{ marginTop: '16px', padding: '0 10px' }}>
                    {isMobile ? (
                      /* 手机端：简化显示本周任务 */
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <DashboardTaskList 
                          tasks={project.tasks}
                          getTaskStatus={getTaskStatus}
                          formatDate={formatDate}
                        />
                      </div>
                    ) : (
                      /* PC端：完整时间线 */
                      <div style={{ position: 'relative', height: '60px' }}>
                        <div style={{ position: 'absolute', top: '20px', left: '0', right: '0', height: '2px', backgroundColor: '#e5e7eb' }}></div>
                      
                      {project.tasks.map((task, index) => {
                        const leftPercent = (index / Math.max(project.tasks.length - 1, 1)) * 85 + 5
                        const status = getTaskStatus(task.progress, task.end_date)
                        
                        return (
                          <div key={task.task_id} style={{ position: 'absolute', left: `${leftPercent}%`, top: '0', textAlign: 'center', transform: 'translateX(-50%)' }}>
                            <div style={{ fontSize: '11px', color: '#666', marginBottom: '4px' }}>{formatDate(task.end_date)}</div>
                            <div style={{
                              width: '16px',
                              height: '16px',
                              borderRadius: '50%',
                              backgroundColor: status === 'completed' ? '#22c55e' : status === 'delayed' ? '#ef4444' : status === 'ongoing' ? '#3b82f6' : '#9ca3af',
                              margin: '0 auto 4px',
                              border: '2px solid white',
                              boxShadow: status === 'delayed' ? '0 0 12px rgba(239, 68, 68, 0.8)' : '0 1px 3px rgba(0,0,0,0.1)',
                              animation: status === 'delayed' ? 'pulse-delayed 1s infinite' : status === 'ongoing' ? 'pulse-ongoing 2s infinite' : status === 'completed' ? 'pulse-completed 2s infinite' : 'pulse-pending 3s infinite',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              color: 'white',
                              fontSize: '10px'
                            }}>
                              {status === 'completed' && '✓'}
                              {status === 'delayed' && '!'}
                              {status === 'ongoing' && '●'}
                              {status === 'pending' && '○'}
                            </div>
                            <div style={{ fontSize: '11px', maxWidth: '60px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', cursor: 'pointer' }} title={task.task_name}>{task.task_name}</div>
                          </div>
                        )
                      })}
                    </div>
                    )}
                    
                    {/* 图例 - 仅PC端显示 */}
                    {!isMobile && (
                    <div style={{ display: 'flex', justifyContent: 'center', gap: '16px', marginTop: '8px', fontSize: '11px', color: '#666' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#22c55e', animation: 'pulse-completed 2s infinite' }}></span>
                        已完成
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#ef4444', animation: 'pulse-delayed 1s infinite', boxShadow: '0 0 6px rgba(239,68,68,0.6)' }}></span>
                        已延期
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#3b82f6', animation: 'pulse-ongoing 2s infinite' }}></span>
                        进行中
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#9ca3af', animation: 'pulse-pending 3s infinite' }}></span>
                        待开始
                      </span>
                    </div>
                    )}
                  </div>
                )}
                
                {project.tasks.length === 0 && (
                  <div style={{ marginTop: '12px', padding: '10px', textAlign: 'center', color: '#999', fontSize: '12px' }}>
                    暂无任务节点数据
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
        </div>
      </main>
      
      <MobileNav active="dashboard" />
      
      <style>{`
        @keyframes pulse-delayed {
          0%, 100% { 
            opacity: 1; 
            transform: scale(1);
            box-shadow: 0 0 12px rgba(239, 68, 68, 0.8);
          }
          50% { 
            opacity: 0.6; 
            transform: scale(1.1);
            box-shadow: 0 0 20px rgba(239, 68, 68, 1);
          }
        }
        @keyframes pulse-ongoing {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }
        @keyframes pulse-completed {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.8; }
        }
        @keyframes pulse-pending {
          0%, 100% { opacity: 0.8; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  )
}
