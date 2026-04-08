import MobileNav from '../components/MobileNav'
import TaskListWithMore from '../components/TaskListWithMore'
import { useState, useEffect } from 'react'
import { useAppStore } from '../store'
import { dashboardApi, statsApi, notificationApi } from '../api'
import SmartAssistant from '../components/SmartAssistant'
import { confirm } from '../components/ConfirmDialog'

interface MonthGoal {
  id: string
  title: string
  progress_rate: number
  status: string
  type?: string
  date?: string
  end_date?: string
}

interface Task {
  task_id: string
  task_name: string
  status: string
  progress: number
  start_date: string | null
  end_date: string | null
  actual_end_date: string | null
  delay_days: number
  daily_reports?: Array<{
    date: string
    reporter: string
    content: string
  }>
}

interface ProjectRisk {
  project_id: number
  project_name: string
  leader: string
  delayed_count: number
  max_delay_days: number
  total_tasks: number
  delayed_tasks: number
  delay_rate: number
  progress?: number  // 项目进度
  tasks?: {
    completed: Task[]       // 按时完成
    delayed_completed: Task[]  // 延期完成
    ongoing: Task[]         // 进行中
    delayed: Task[]         // 已延期未完成
    not_started: Task[]     // 未开始
  }
}

interface TeamWorkHours {
  project_name: string
  members: Array<{
    name: string
    hours: number
    percent: number
  }>
  total_hours: number
}

export default function HomePage() {
  const { user, logout } = useAppStore()
  const [showUserMenu, setShowUserMenu] = useState(false)
  
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
  
  // 今日聚焦数据
  // 本月目标（暂时保留类型）
  const [, setMonthGoals] = useState<MonthGoal[]>([])
  const [dailyReportStatus, setDailyReportStatus] = useState({ submitted: false })
  const [weekOverview, setWeekOverview] = useState({ report_count: 0, total_hours: 0, project_count: 0 })
  const [isLoading, setIsLoading] = useState(true)
  
  // 我负责的项目风险预警
  const [myProjectRisks, setMyProjectRisks] = useState<ProjectRisk[]>([])
  
  // 工时统计
  const [workHoursStats, setWorkHoursStats] = useState<{
    today: number
    week: number
    month: number
    projects: Array<{ name: string; hours: number; percent: number }>
  }>({ today: 0, week: 0, month: 0, projects: [] })
  
  // 团队工时统计（项目负责人视角）
  const [teamWorkHours, setTeamWorkHours] = useState<TeamWorkHours[]>([])
  
  // 通知未读数
  const [notificationUnread, setNotificationUnread] = useState(0)
  
  // 展开的项目ID
  const [expandedProjects, setExpandedProjects] = useState<Set<number>>(new Set())

  // 选中的状态筛选（每个项目独立）
  const [projectStatusFilter, setProjectStatusFilter] = useState<Map<number, 'delayed' | 'ongoing' | 'completed'>>(new Map())

  const toggleProject = (projectId: number) => {
    setExpandedProjects(prev => {
      const next = new Set(prev)
      if (next.has(projectId)) {
        next.delete(projectId)
      } else {
        next.add(projectId)
        // 默认显示延期（如果有延期的话）
        const project = myProjectRisks.find(p => p.project_id === projectId)
        if (project && (project.tasks?.delayed?.length || 0) > 0) {
          setProjectStatusFilter(prev => new Map(prev).set(projectId, 'delayed'))
        } else if (project && (project.tasks?.ongoing?.length || 0) > 0) {
          setProjectStatusFilter(prev => new Map(prev).set(projectId, 'ongoing'))
        } else {
          setProjectStatusFilter(prev => new Map(prev).set(projectId, 'completed'))
        }
      }
      return next
    })
  }

  const setStatusFilter = (projectId: number, status: 'delayed' | 'ongoing' | 'completed') => {
    setProjectStatusFilter(prev => new Map(prev).set(projectId, status))
  }

  useEffect(() => {
    loadData()
  }, [])

  // 缓存工具函数
  const CACHE_KEY = 'home-data-cache'
  const CACHE_DURATION = 5 * 60 * 1000 // 5分钟缓存

  const getCache = () => {
    try {
      const cached = localStorage.getItem(CACHE_KEY)
      if (cached) {
        const { data, timestamp } = JSON.parse(cached)
        if (Date.now() - timestamp < CACHE_DURATION) {
          return data
        }
      }
    } catch {}
    return null
  }

  const setCache = (data: any) => {
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({
        data,
        timestamp: Date.now()
      }))
    } catch {}
  }

  const loadData = async (forceRefresh = false) => {
    // 1. 先检查缓存
    if (!forceRefresh) {
      const cached = getCache()
      if (cached) {
        // 使用缓存数据快速渲染
        setMonthGoals((cached.focusData?.month_goals || []) as unknown as MonthGoal[])
        setDailyReportStatus(cached.focusData?.daily_report_status || { submitted: false })
        setWeekOverview(cached.focusData?.week_overview || { report_count: 0, total_hours: 0, project_count: 0 })
        setWorkHoursStats(cached.hoursData || { today: 0, week: 0, month: 0, projects: [] })
        setNotificationUnread(cached.notifData?.unread_count || 0)
        setMyProjectRisks(cached.risksData || [])
        setTeamWorkHours(cached.teamData || [])
        setIsLoading(false)
        
        // 后台静默刷新（不显示 loading）
        refreshData(true)
        return
      }
    }
    
    setIsLoading(true)
    await refreshData(false)
  }

  const refreshData = async (silent = false) => {
    try {
      // 并行加载
      const [focusData, hoursData, notifData, risksData, teamData] = await Promise.all([
        dashboardApi.getTodayFocus(),
        statsApi.getWorkHoursStats().catch(() => ({ today: 0, week: 0, month: 0, projects: [] })),
        notificationApi.getList(true, 1).catch(() => ({ notifications: [], unread_count: 0 })),
        dashboardApi.getMyProjectRisks().catch(() => []),
        statsApi.getTeamWorkHours().catch(() => [])
      ])
      
      setMonthGoals((focusData.month_goals || []) as unknown as MonthGoal[])
      setDailyReportStatus(focusData.daily_report_status || { submitted: false })
      setWeekOverview(focusData.week_overview || { report_count: 0, total_hours: 0, project_count: 0 })
      setWorkHoursStats(hoursData)
      setNotificationUnread(notifData.unread_count || 0)
      setMyProjectRisks(risksData)
      setTeamWorkHours(teamData)
      
      // 缓存数据
      setCache({ focusData, hoursData, notifData, risksData, teamData })
    } catch (error) {
      console.error('加载数据失败:', error)
    } finally {
      if (!silent) {
        setIsLoading(false)
      }
    }
  }

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
      window.location.href = '/agent/login'
    }
  }

  const getWeekday = () => {
    const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
    return weekdays[new Date().getDay()]
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
              <a href="/agent/" className="nav-link active">个人</a>
              <a href="/agent/daily" className="nav-link">日报</a>
              <a href="/agent/projects" className="nav-link">项目</a>
              <a href="/agent/chat" className="nav-link">问答</a>
              <a href="/agent/dashboard" className="nav-link">看板</a>
            </nav>
          </div>
          <div className="header-right">
            {/* 通知图标 */}
            <a href="/agent/notifications" className="notification-bell">
              🔔
              {notificationUnread > 0 && (
                <span className="notification-badge">{notificationUnread > 99 ? '99+' : notificationUnread}</span>
              )}
            </a>
            
            <div className="user-menu-wrapper">
              <div className="user-info" onClick={() => setShowUserMenu(!showUserMenu)}>
                <div className="user-avatar" style={{
                  background: `linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)`,
                  color: 'white',
                  fontWeight: '600'
                }}>{user?.name?.[0]?.toUpperCase() || 'U'}</div>
                <span className="user-name">{user?.name || '用户'}</span>
                <svg className={`w-4 h-4 text-gray-400 transition-transform ${showUserMenu ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </div>
              {showUserMenu && (
                <div className="user-dropdown">
                  <div className="user-dropdown-header">
                    <div className="user-avatar-lg" style={{
                      background: `linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)`,
                      color: 'white',
                      fontWeight: '600'
                    }}>{user?.name?.[0]?.toUpperCase() || 'U'}</div>
                    <div>
                      <div className="font-medium text-gray-900">{user?.name || '用户'}</div>
                      {user?.department && <div className="text-sm text-gray-600">{user.department}</div>}
                      {user?.position && <div className="text-xs text-gray-500">{user.position}</div>}
                    </div>
                  </div>
                  <div className="user-dropdown-divider" />
                  <a href="/agent/plans" className="user-dropdown-item">📋 我的计划</a>
                  <button onClick={handleLogout} className="user-dropdown-item text-red-600">退出登录</button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* 主内容区 */}
      <main className="content-wrapper">
        {/* 骨架屏加载状态 */}
        {isLoading ? (
          <>
            {/* 欢迎区域骨架 */}
            <div className="skeleton skeleton-welcome mb-6" />
            
            {/* 统计卡片骨架 */}
            <div className="grid-4 mb-6">
              {[1,2,3,4].map(i => (
                <div key={i} className="skeleton skeleton-card" />
              ))}
            </div>
            
            {/* 智能建议骨架 */}
            <div className="skeleton skeleton-box mb-6" style={{ height: '120px' }} />
            
            {/* 项目列表骨架 */}
            <div className="card mb-6">
              <div className="card-header">
                <div className="skeleton skeleton-text" style={{ width: '120px' }} />
              </div>
              <div className="card-body">
                {[1,2,3].map(i => (
                  <div key={i} className="skeleton skeleton-item mb-3" />
                ))}
              </div>
            </div>
            
            {/* 工时统计骨架 */}
            <div className="grid-2">
              <div className="skeleton skeleton-card" style={{ height: '200px' }} />
              <div className="skeleton skeleton-card" style={{ height: '200px' }} />
            </div>
          </>
        ) : (
          <>
            {/* 欢迎区域 + 日报状态 */}
            <div className="home-welcome-section">
              <div className="home-welcome-info">
                <h1 className="home-welcome-title">
                  {getWeekday()}好，{user?.name || '工程师'}
                </h1>
                <p className="home-welcome-date">
                  {new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })}
                </p>
              </div>
              {/* 日报填报状态 */}
              {dailyReportStatus.submitted ? (
                <div className="home-daily-done">
                  <span className="text-green-600 text-xl">✓</span>
                  <span className="text-green-700 font-medium">今日日报已提交</span>
                </div>
              ) : (
                <a href="/agent/daily" className="btn btn-primary home-daily-btn">
                  <span>📝</span>
                  填报今日日报
                </a>
              )}
            </div>

            {/* 本周概览 */}
            <div className="grid-4 mb-6">
              <div className="stat-card">
                <div className="stat-icon">📊</div>
                <div className="stat-content">
                  <div className="stat-value">{weekOverview.report_count}</div>
                  <div className="stat-label">本周日报</div>
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-icon">⏱️</div>
                <div className="stat-content">
                  <div className="stat-value">{(workHoursStats.week || 0).toFixed(1)}<span className="stat-unit">h</span></div>
                  <div className="stat-label">本周工时</div>
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-icon">📁</div>
                <div className="stat-content">
                  <div className="stat-value">{weekOverview.project_count}</div>
                  <div className="stat-label">涉及项目</div>
                </div>
              </div>
              <a href="/agent/report" className="stat-card" style={{ textDecoration: 'none', cursor: 'pointer' }}>
                <div className="stat-icon">📋</div>
                <div className="stat-content">
                  <div className="stat-value" style={{ fontSize: '16px', color: '#3b82f6' }}>查看周报</div>
                  <div className="stat-label">智能生成</div>
                </div>
              </a>
            </div>

            {/* 第一行 - 智能建议（全宽） */}
            <div className="mb-6">
              <SmartAssistant />
            </div>

            {/* 第二行 - 我的项目进度（全宽） */}
            <div className="card mb-6">
              <div className="card-header">
                <h2 className="card-title">📁 我的项目进度</h2>
                <span className="text-sm text-gray-500">{myProjectRisks.length} 个项目</span>
              </div>
              <div className="card-body">
                {myProjectRisks.length === 0 ? (
                  <div className="empty-state" style={{padding: '40px'}}>
                    <div className="empty-icon">📁</div>
                    <p className="empty-title">暂无负责项目</p>
                    <p className="empty-desc">您还未负责任何项目</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {(myProjectRisks || []).map((project) => {
                      const completed = project.tasks?.completed?.length || 0
                      const delayedCompleted = project.tasks?.delayed_completed?.length || 0
                      const ongoing = project.tasks?.ongoing?.length || 0
                      const delayed = project.tasks?.delayed?.length || 0
                      const totalDelayed = delayedCompleted + delayed
                      const isExpanded = expandedProjects.has(project.project_id)
                      const currentFilter = projectStatusFilter.get(project.project_id) || 'delayed'
                      const totalTasks = project.total_tasks || 1
                      const progress = project.progress || 0  // 使用后端返回的进度
                      
                      return (
                        <div 
                          key={project.project_id} 
                          className="home-project-card"
                          data-delayed={totalDelayed > 0}
                        >
                          {/* 项目标题卡片 */}
                          <div 
                            className="home-project-header"
                            onClick={() => toggleProject(project.project_id)}
                          >
                            <div className="home-project-title">
                              <span className="home-project-arrow" style={{transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)'}}>▶</span>
                              <a 
                                href={`/agent/projects/${project.project_id}`} 
                                className="home-project-name"
                                onClick={(e) => e.stopPropagation()}
                              >
                                {project.project_name}
                              </a>
                            </div>
                            <div className="home-project-meta">
                              {/* 进度条 */}
                              <div className="home-project-progress">
                                <div className="progress-bar">
                                  <div className="progress-bar-fill" style={{ width: `${progress}%`, background: totalDelayed > 0 ? '#ef4444' : '#22c55e' }} />
                                </div>
                                <span className="home-project-progress-text">{progress}%</span>
                              </div>
                              {totalDelayed > 0 && (
                                <span className="home-project-badge home-project-badge-delay">
                                  ⚠️ {totalDelayed} 延期
                                </span>
                              )}
                              <span className="home-project-count">
                                {completed + delayedCompleted}/{totalTasks} 完成
                              </span>
                            </div>
                          </div>
                          
                          {/* 展开的任务列表 */}
                          {isExpanded && (
                            <div className="home-project-tasks">
                              {/* 状态Tab */}
                              <div className="home-task-tabs">
                                <button
                                  onClick={() => setStatusFilter(project.project_id, 'delayed')}
                                  className={`home-task-tab ${currentFilter === 'delayed' ? 'active-delayed' : ''}`}
                                >
                                  ⚠️ 延期 ({totalDelayed})
                                </button>
                                <button
                                  onClick={() => setStatusFilter(project.project_id, 'ongoing')}
                                  className={`home-task-tab ${currentFilter === 'ongoing' ? 'active-ongoing' : ''}`}
                                >
                                  🔄 进行中 ({ongoing})
                                </button>
                                <button
                                  onClick={() => setStatusFilter(project.project_id, 'completed')}
                                  className={`home-task-tab ${currentFilter === 'completed' ? 'active-completed' : ''}`}
                                >
                                  ✅ 已完成 ({completed})
                                </button>
                              </div>
                              
                              {/* 任务列表 */}
                              <div className="home-task-list">
                                {currentFilter === 'delayed' && (
                                  <>
                                    {delayed > 0 && (
                                      <div className="mb-3">
                                        <div className="home-task-group-title home-task-group-delayed">
                                          🔴 已延期未完成 ({delayed})
                                        </div>
                                        <TaskListWithMore 
                                          tasks={project.tasks?.delayed || []} 
                                          type="delayed" 
                                        />
                                      </div>
                                    )}
                                    {delayedCompleted > 0 && (
                                      <div>
                                        <div className="home-task-group-title home-task-group-warn">
                                          🟠 延期完成 ({delayedCompleted})
                                        </div>
                                        <TaskListWithMore 
                                          tasks={project.tasks?.delayed_completed || []} 
                                          type="delayed_completed" 
                                        />
                                      </div>
                                    )}
                                  </>
                                )}
                                
                                {currentFilter === 'ongoing' && (
                                  <TaskListWithMore 
                                    tasks={project.tasks?.ongoing || []} 
                                    type="ongoing" 
                                  />
                                )}
                                
                                {currentFilter === 'completed' && (
                                  <TaskListWithMore 
                                    tasks={project.tasks?.completed || []} 
                                    type="completed" 
                                  />
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* 第三行 - 个人本月工时（左） + 团队本月工时（右） */}
            <div className="grid-2" style={{gap: '24px', alignItems: 'stretch'}}>
              {/* 个人本月工时分布 */}
              <div className="card">
                <div className="card-header">
                  <h2 className="card-title">📊 个人本月工时</h2>
                  <span className="text-sm text-gray-500">共 {(workHoursStats.month || 0).toFixed(1)}h</span>
                </div>
                <div className="card-body">
                  {(workHoursStats.projects?.length || 0) === 0 ? (
                    <div className="empty-state" style={{padding: '30px'}}>
                      <div className="empty-icon">📊</div>
                      <p className="empty-title">暂无工时数据</p>
                      <p className="empty-desc">本月还未填报工时</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {(workHoursStats.projects || []).slice(0, 5).map((project) => (
                        <div key={project.name}>
                          <div className="flex justify-between text-sm mb-1">
                            <span className="text-gray-600 truncate" style={{maxWidth: '200px'}}>{project.name}</span>
                            <span className="text-gray-900 font-medium">{project.hours}h ({project.percent}%)</span>
                          </div>
                          <div className="progress-bar">
                            <div className="progress-bar-fill" style={{ width: `${project.percent}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              
              {/* 团队本月工时 */}
              <div className="card">
                <div className="card-header">
                  <h2 className="card-title">👥 团队本月工时</h2>
                </div>
                <div className="card-body">
                  {teamWorkHours.length === 0 ? (
                    <div className="empty-state" style={{padding: '30px'}}>
                      <div className="empty-icon">👥</div>
                      <p className="empty-title">暂无团队工时</p>
                      <p className="empty-desc">您不是项目负责人或暂无数据</p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {(teamWorkHours || []).map((project) => (
                        <div key={project.project_name}>
                          <div className="flex justify-between items-center mb-2">
                            <span className="font-medium text-gray-900">{project.project_name}</span>
                            <span className="text-sm text-gray-500">共 {project.total_hours}h</span>
                          </div>
                          <div className="space-y-2">
                            {(project.members || []).slice(0, 5).map((member, idx) => (
                              <div key={idx} className="flex justify-between text-sm">
                                <span className="text-gray-600">{member.name}</span>
                                <span className="text-gray-900">{member.hours}h ({member.percent}%)</span>
                              </div>
                            ))}
                            {((project.members?.length || 0) > 5) && (
                              <div className="text-xs text-gray-400 text-center">
                                还有 {(project.members?.length || 0) - 5} 人...
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </main>

      {/* 移动端底部导航 */}
      <MobileNav active="home" />
    </div>
  )
}
