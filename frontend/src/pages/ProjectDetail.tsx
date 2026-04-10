import { Link } from 'react-router-dom'
import { redirectToLogin } from '../utils/auth'
import { useState, useEffect } from 'react'
import { useAppStore } from '../store'
import { projectApi } from '../api'
import ProjectTaskList from '../components/ProjectTaskList'
import CostImportModal from '../components/CostImportModal'

interface Project {
  id: number
  name: string
  leader: string
  status: string
  progress: number
  description?: string
  start_date?: string
  end_date?: string
  plan_start_date?: string
  plan_end_date?: string
  budget?: number
  contract_amount?: number
  material_budget?: number
  material_cost?: number
  outsourcing_budget?: number
  outsourcing_cost?: number
  labor_budget?: number
  labor_cost?: number
  indirect_budget?: number
  indirect_cost?: number
  project_category?: string
  project_subject?: string
  implementation_mode?: string
  project_level?: string
  total_hours: number
  total_tasks?: number
  completed_tasks?: number
  progress_formula?: string
  worker_hours: Array<{ name: string; hours: number }>
}

interface Task {
  task_id: string
  task_name: string
  assignee?: string
  start_date?: string
  end_date?: string
  status: string
  progress?: number
  planned_hours?: number
  daily_reports?: Array<{
    report_date: string
    work_content: string
    hours_spent: number
  }>
}

interface KnowledgeDoc {
  id: number
  doc_name: string
  doc_type: string
  project_name: string
  summary: string
  upload_time: string
  uploader_name: string
}

export default function ProjectDetailPage() {
  const { user, logout } = useAppStore()
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [project, setProject] = useState<Project | null>(null)
  const [tasks, setTasks] = useState<Task[]>([])
  const [knowledgeDocs, setKnowledgeDocs] = useState<KnowledgeDoc[]>([])
  const [taskRisks, setTaskRisks] = useState<any>(null)
  const [expandedTasks, setExpandedTasks] = useState<Set<string>>(new Set())  // 展开的任务ID
  const [expandedPhases, setExpandedPhases] = useState<Set<string>>(new Set(['需求阶段', '设计阶段', '开发阶段', '测试阶段']))  // 默认全部展开
  const [isLoading, setIsLoading] = useState(true)
  
  // 聊天相关状态
  const [chatMessages, setChatMessages] = useState<Array<{role: 'user' | 'assistant', content: string}>>([])
  const [chatInput, setChatInput] = useState('')
  const [isChatLoading, setIsChatLoading] = useState(false)
  
  // 知识库相关状态
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [uploadForm, setUploadForm] = useState({
    doc_name: '',
    doc_type: '需求文档',
    file: null as File | null
  })
  
  // 成本导入状态
  const [showCostImport, setShowCostImport] = useState(false)
  
  // 任务阶段分组
  const getTaskPhase = (taskName: string) => {
    if (taskName.includes('需求') || taskName.includes('调研')) return '需求阶段'
    if (taskName.includes('设计') || taskName.includes('数据库')) return '设计阶段'
    if (taskName.includes('开发') || taskName.includes('接口') || taskName.includes('安全')) return '开发阶段'
    if (taskName.includes('测试') || taskName.includes('联调')) return '测试阶段'
    return '其他'
  }
  
  // 按阶段分组任务
  const groupedTasks = tasks.reduce((acc, task) => {
    const phase = getTaskPhase(task.task_name)
    if (!acc[phase]) acc[phase] = []
    acc[phase].push(task)
    return acc
  }, {} as Record<string, Task[]>)

  // 从URL获取项目ID
  const projectId = parseInt(window.location.pathname.split('/').pop() || '0')

  useEffect(() => {
    loadProjectDetail()
  }, [projectId])

  const loadProjectDetail = async () => {
    setIsLoading(true)
    try {
      // 并行加载项目详情、任务、知识库数据
      const [projectDetail, taskList, taskRiskData] = await Promise.all([
        projectApi.getProjectDetail(projectId),
        projectApi.getTasks(projectId),
        projectApi.getTaskRisks(projectId).catch(() => null)
      ])
      
      setProject(projectDetail)
      setTasks(Array.isArray(taskList) ? taskList : [])
      setTaskRisks(taskRiskData)
      
      // 加载知识库数据
      await loadKnowledgeBase()
    } catch (error) {
      console.error('加载项目详情失败:', error)
    } finally {
      setIsLoading(false)
    }
  }
  
  // 加载知识库数据
  const loadKnowledgeBase = async () => {
    try {
      const { token } = useAppStore.getState()
      if (!token) return
      
      // 获取统计信息
      const statsRes = await fetch(`/api/agent/knowledge/stats?project_id=${projectId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      if (statsRes.status === 401) {
        useAppStore.getState().logout()
        redirectToLogin()
        return
      }
      
      // 获取文档列表
      const docsRes = await fetch(`/api/agent/knowledge/list?project_id=${projectId}&limit=10`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      
      if (docsRes.status === 401) {
        useAppStore.getState().logout()
        redirectToLogin()
        return
      }
      
      if (docsRes.ok) {
        const docsData = await docsRes.json()
        setKnowledgeDocs(docsData.data || [])
      }
    } catch (error) {
      console.error('加载知识库失败:', error)
    }
  }
  
  // 智能问答（新版本 - 聊天窗口）
  const handleChatSend = async () => {
    if (!chatInput.trim() || isChatLoading) return
    
    const userMessage = chatInput.trim()
    setChatInput('')
    
    // 添加用户消息到聊天记录
    setChatMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setIsChatLoading(true)
    
    try {
      const { token } = useAppStore.getState()
      
      if (!token) {
        setChatMessages(prev => [...prev, { role: 'assistant', content: '请先登录' }])
        return
      }
      
      const res = await fetch(`/api/agent/projects/${projectId}/chat`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          message: userMessage,
          session_id: `project_${projectId}`
        })
      })
      
      if (res.status === 401) {
        useAppStore.getState().logout()
        redirectToLogin()
        return
      }
      
      const data = await res.json()
      
      if (data.success) {
        setChatMessages(prev => [...prev, { 
          role: 'assistant', 
          content: data.answer || '查询成功' 
        }])
      } else {
        setChatMessages(prev => [...prev, { 
          role: 'assistant', 
          content: data.answer || '查询失败，请稍后重试' 
        }])
      }
    } catch (error) {
      console.error('聊天失败:', error)
      setChatMessages(prev => [...prev, { 
        role: 'assistant', 
        content: '网络错误，请检查网络连接' 
      }])
    } finally {
      setIsChatLoading(false)
    }
  }
  
  // 上传文档
  const handleUpload = async () => {
    if (!uploadForm.doc_name || !uploadForm.file) return
    
    try {
      const { token } = useAppStore.getState()
      const formData = new FormData()
      formData.append('project_id', projectId.toString())
      formData.append('project_name', project?.name || '')
      formData.append('doc_name', uploadForm.doc_name)
      formData.append('doc_type', uploadForm.doc_type)
      formData.append('file', uploadForm.file)
      
      const res = await fetch('/api/agent/knowledge/upload', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      })
      
      if (res.ok) {
        const data = await res.json()
        if (data.success) {
          setShowUploadModal(false)
          setUploadForm({ doc_name: '', doc_type: '需求文档', file: null })
          await loadKnowledgeBase()
          alert('文档上传成功！')
        } else {
          alert(data.message || '上传失败')
        }
      } else {
        alert('上传失败，请稍后重试')
      }
    } catch (error) {
      console.error('上传失败:', error)
      alert('上传失败，请检查网络连接')
    }
  }

  const handleLogout = () => {
    logout()
    redirectToLogin()
  }

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

  if (isLoading) {
    return (
      <div className="page-container">
        <header className="header">
          <div className="header-content">
            <div className="header-left">
              <Link to="/" className="header-logo">
                <span className="text-xl">⚙️</span>
                <span>项目管家</span>
              </Link>
            </div>
          </div>
        </header>
        <main className="content-wrapper">
          {/* 骨架屏 */}
          <div className="skeleton skeleton-text mb-4" style={{ width: '200px', height: '24px' }} />
          <div className="skeleton skeleton-text mb-6" style={{ width: '300px', height: '16px' }} />
          
          <div className="grid-2 mb-6">
            <div className="skeleton skeleton-card" style={{ height: '200px' }} />
            <div className="skeleton skeleton-card" style={{ height: '200px' }} />
          </div>
          
          <div className="card mb-6">
            <div className="card-header">
              <div className="skeleton skeleton-text" style={{ width: '100px' }} />
            </div>
            <div className="card-body">
              {[1,2,3,4].map(i => (
                <div key={i} className="skeleton skeleton-item mb-3" />
              ))}
            </div>
          </div>
        </main>
      </div>
    )
  }

  if (!project) {
    return (
      <div className="page-container">
        <header className="header">
          <div className="header-content">
            <Link to="/projects" className="header-logo">
              <span className="text-xl">⚙️</span>
              <span>项目管家</span>
            </Link>
          </div>
        </header>
        <main className="content-wrapper">
          <div className="empty-state">
            <div className="empty-icon">🔍</div>
            <p className="empty-title">项目不存在</p>
            <Link to="/projects" className="btn btn-primary mt-4">返回项目列表</Link>
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
        {/* 返回按钮 */}
        <Link to="/projects" className="back-link">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          返回项目列表
        </Link>
        
        {/* ========== 第一行：项目基本信息（全宽）========== */}
        <div className="card mt-4">
          <div className="card-header">
            <div className="flex items-center gap-3">
              <h2 className="card-title">{project.name}</h2>
              {getStatusTag(project.status)}
            </div>
          </div>
          <div className="card-body">
            {/* PC端：4列，移动端：单列 */}
            <div className="project-detail-info">
              {/* 基本信息 */}
              <div className="detail-section">
                <div className="detail-section-title">基本信息</div>
                <div className="space-y-3">
                  <div>
                    <div className="detail-label">项目负责人</div>
                    <div className="detail-value">{project.leader || '未指定'}</div>
                  </div>
                  <div>
                    <div className="detail-label">计划周期</div>
                    <div className="detail-value">
                      {project.plan_start_date && project.plan_end_date 
                        ? `${project.plan_start_date} ~ ${project.plan_end_date}`
                        : '未设置'}
                    </div>
                  </div>
                  <div>
                    <div className="detail-label">合同金额</div>
                    <div className="detail-value">{project.contract_amount ? `${(project.contract_amount / 10000).toFixed(2)} 万元` : '未设置'}</div>
                  </div>
                </div>
              </div>
              
              {/* 任务进度 */}
              <div className="detail-section">
                <div className="detail-section-title">任务进度</div>
                <div className="space-y-3">
                  <div>
                    <div className="detail-label">任务完成</div>
                    <div className="detail-value">{project.completed_tasks || 0} / {project.total_tasks || 0} 个</div>
                  </div>
                  <div>
                    <div className="detail-label">累计工时</div>
                    <div className="detail-value" style={{color: 'var(--primary)'}}>{project.total_hours} 小时</div>
                  </div>
                </div>
              </div>
              
              {/* 成本概览 - 2x2 布局 */}
              <div className="detail-section detail-section-wide">
                <div className="detail-section-title" style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                  <span>💰 成本概览（单位：万元）</span>
                  <button
                    onClick={() => setShowCostImport(true)}
                    style={{
                      padding: '6px 12px',
                      background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)',
                      border: 'none',
                      borderRadius: '6px',
                      color: 'white',
                      fontSize: '12px',
                      fontWeight: '500',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                  >
                    📤 导入成本
                  </button>
                </div>
                <div className="cost-grid">
                  <div className="cost-card cost-card-material">
                    <div className="cost-card-header">
                      <div className="cost-card-title">
                        <span>📦</span>
                        <span>材料成本</span>
                      </div>
                      {(project.material_cost || 0) > (project.material_budget || 0) && (project.material_budget || 0) > 0 && (
                        <span className="cost-card-badge">超支</span>
                      )}
                    </div>
                    <div className="cost-card-desc">原材料、设备采购等</div>
                    <div className="cost-card-value">
                      {((project.material_cost || 0) / 10000).toFixed(2)} / {((project.material_budget || 0) / 10000).toFixed(2)} <span>万元</span>
                    </div>
                    {(project.material_budget || 0) > 0 && <div className="cost-card-rate" style={{color: (project.material_cost || 0) > (project.material_budget || 0) ? '#dc2626' : '#16a34a'}}>预算使用率：{((project.material_cost || 0) / (project.material_budget || 1) * 100).toFixed(1)}%</div>}
                  </div>
                  <div className="cost-card cost-card-labor">
                    <div className="cost-card-header">
                      <div className="cost-card-title">
                        <span>👥</span>
                        <span>人力成本</span>
                      </div>
                      {(project.labor_cost || 0) > (project.labor_budget || 0) && (project.labor_budget || 0) > 0 && (
                        <span className="cost-card-badge">超支</span>
                      )}
                    </div>
                    <div className="cost-card-desc">人员工资、福利等</div>
                    <div className="cost-card-value">
                      {((project.labor_cost || 0) / 10000).toFixed(2)} / {((project.labor_budget || 0) / 10000).toFixed(2)} <span>万元</span>
                    </div>
                    {(project.labor_budget || 0) > 0 && <div className="cost-card-rate" style={{color: (project.labor_cost || 0) > (project.labor_budget || 0) ? '#dc2626' : '#16a34a'}}>预算使用率：{((project.labor_cost || 0) / (project.labor_budget || 1) * 100).toFixed(1)}%</div>}
                  </div>
                  <div className="cost-card cost-card-outsource">
                    <div className="cost-card-header">
                      <div className="cost-card-title">
                        <span>🔧</span>
                        <span>外包成本</span>
                      </div>
                      {(project.outsourcing_cost || 0) > (project.outsourcing_budget || 0) && (project.outsourcing_budget || 0) > 0 && (
                        <span className="cost-card-badge">超支</span>
                      )}
                    </div>
                    <div className="cost-card-desc">外包服务、第三方费用</div>
                    <div className="cost-card-value">
                      {((project.outsourcing_cost || 0) / 10000).toFixed(2)} / {((project.outsourcing_budget || 0) / 10000).toFixed(2)} <span>万元</span>
                    </div>
                    {(project.outsourcing_budget || 0) > 0 && <div className="cost-card-rate" style={{color: (project.outsourcing_cost || 0) > (project.outsourcing_budget || 0) ? '#dc2626' : '#16a34a'}}>预算使用率：{((project.outsourcing_cost || 0) / (project.outsourcing_budget || 1) * 100).toFixed(1)}%</div>}
                  </div>
                  <div className="cost-card cost-card-indirect">
                    <div className="cost-card-header">
                      <div className="cost-card-title">
                        <span>📊</span>
                        <span>间接成本</span>
                      </div>
                      {(project.indirect_cost || 0) > (project.indirect_budget || 0) && (project.indirect_budget || 0) > 0 && (
                        <span className="cost-card-badge">超支</span>
                      )}
                    </div>
                    <div className="cost-card-desc">管理费、办公费等</div>
                    <div className="cost-card-value">
                      {((project.indirect_cost || 0) / 10000).toFixed(2)} / {((project.indirect_budget || 0) / 10000).toFixed(2)} <span>万元</span>
                    </div>
                    {(project.indirect_budget || 0) > 0 && <div className="cost-card-rate" style={{color: (project.indirect_cost || 0) > (project.indirect_budget || 0) ? '#dc2626' : '#16a34a'}}>预算使用率：{((project.indirect_cost || 0) / (project.indirect_budget || 1) * 100).toFixed(1)}%</div>}
                  </div>
                </div>
              </div>
            </div>
            
            {/* 进度条 */}
            <div className="mt-6" style={{paddingTop: '16px', borderTop: '1px solid #e5e7eb'}}>
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm text-gray-500">📊 整体进度</span>
                <span className="text-lg font-bold" style={{color: 'var(--primary)'}}>{project.progress}%</span>
              </div>
              <div className="progress-bar-lg">
                <div className="progress-bar-fill" style={{ width: `${project.progress}%` }} />
              </div>
            </div>
          </div>
        </div>

        {/* ========== 第二行：风险预警 + 人员工时（左右布局）========== */}
        <div className="grid-2 mt-4">
          {/* 左：风险预警 */}
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">⚠️ 风险预警</h2>
              {taskRisks && taskRisks.risks && taskRisks.risks.length > 0 && (
                <span className="tag" style={{background: '#fee2e2', color: '#dc2626', fontSize: '12px', fontWeight: '600'}}>{taskRisks.risks.length} 项风险</span>
              )}
            </div>
            <div className="card-body" style={{maxHeight: '280px', overflowY: 'auto'}}>
              {taskRisks && taskRisks.risks && taskRisks.risks.length > 0 ? (
                <div className="space-y-3">
                  {taskRisks.risks.slice(0, 5).map((risk: any, idx: number) => {
                    const getRiskColor = (level: string) => {
                      switch (level) {
                        case 'high': return {bg: 'rgba(239, 68, 68, 0.12)', border: '#ef4444'}
                        case 'medium': return {bg: 'rgba(245, 158, 11, 0.12)', border: '#f59e0b'}
                        default: return {bg: 'rgba(34, 197, 94, 0.12)', border: '#22c55e'}
                      }
                    }
                    const getRiskLabel = (type: string) => {
                      const labels: Record<string, string> = {'delayed': '已延期', 'delayed_completion': '延期完成', 'expiring_soon': '即将到期', 'started_early': '提前启动', 'not_reported': '未报告', 'starting_soon': '即将启动'}
                      return labels[type] || '风险'
                    }
                    const colors = getRiskColor(risk.risk_level)
                    return (
                      <div key={idx} style={{padding: '12px 14px', background: colors.bg, borderLeft: `4px solid ${colors.border}`, borderRadius: '8px'}}>
                        <div style={{display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px'}}>
                          <span style={{fontWeight: '700', color: '#1e293b', fontSize: '14px'}}>{risk.task_name}</span>
                          <span style={{fontSize: '11px', padding: '3px 10px', background: colors.border, color: 'white', borderRadius: '12px', fontWeight: '600'}}>{getRiskLabel(risk.risk_type)}</span>
                        </div>
                        <div style={{color: '#475569', lineHeight: '1.5', fontSize: '13px'}}>{risk.message}</div>
                      </div>
                    )
                  })}
                  {taskRisks.risks.length > 5 && <div style={{textAlign: 'center', color: '#94a3b8', fontSize: '13px', paddingTop: '8px'}}>还有 {taskRisks.risks.length - 5} 项风险...</div>}
                </div>
              ) : (
                <div style={{textAlign: 'center', padding: '50px 20px', color: '#94a3b8'}}>
                  <div style={{fontSize: '40px', marginBottom: '12px'}}>✅</div>
                  <div style={{fontSize: '15px', fontWeight: '500'}}>暂无风险预警</div>
                </div>
              )}
            </div>
          </div>

          {/* 右：人员工时 */}
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">👥 人员工时</h2>
              <span style={{fontSize: '13px', color: '#64748b', fontWeight: '500'}}>共 {project.total_hours} 小时</span>
            </div>
            <div className="card-body" style={{maxHeight: '280px', overflowY: 'auto'}}>
              {project.worker_hours && project.worker_hours.length > 0 ? (
                <div style={{display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px'}}>
                  {project.worker_hours.map((worker, idx) => (
                    <div key={idx} style={{display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 12px', background: '#f8fafc', borderRadius: '10px', border: '1px solid #e5e7eb'}}>
                      <div style={{width: '36px', height: '36px', borderRadius: '50%', background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: '700', fontSize: '14px', flexShrink: 0}}>{worker.name?.[0] || '?'}</div>
                      <div style={{flex: 1, minWidth: 0}}>
                        <div style={{fontWeight: '600', color: '#1e293b', fontSize: '13px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>{worker.name}</div>
                      </div>
                      <div style={{textAlign: 'right', flexShrink: 0}}>
                        <span style={{color: 'var(--primary)', fontWeight: '700', fontSize: '18px'}}>{worker.hours}</span>
                        <span style={{fontSize: '11px', color: '#94a3b8', marginLeft: '2px'}}>h</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{textAlign: 'center', padding: '50px 20px', color: '#94a3b8'}}>
                  <div style={{fontSize: '40px', marginBottom: '12px'}}>📊</div>
                  <div style={{fontSize: '15px', fontWeight: '500'}}>暂无工时数据</div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ========== 第三行：智能问答 + 知识库（左右布局）========== */}
        <div className="grid-2 mt-4">
          {/* 左：智能问答 */}
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">🤖 项目智能问答</h2>
            </div>
            <div className="card-body" style={{display: 'flex', flexDirection: 'column', height: '400px'}}>
              <div style={{flex: 1, overflowY: 'auto', marginBottom: '16px', padding: '8px'}}>
                {chatMessages.length === 0 ? (
                  <div style={{textAlign: 'center', padding: '60px 20px', color: '#94a3b8'}}>
                    <div style={{fontSize: '48px', marginBottom: '16px'}}>💬</div>
                    <div style={{fontSize: '14px', fontWeight: '500', marginBottom: '8px'}}>开始对话</div>
                    <div style={{fontSize: '12px'}}>询问关于项目的任何问题</div>
                  </div>
                ) : (
                  chatMessages.map((msg, idx) => (
                    <div key={idx} style={{marginBottom: '12px', display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start'}}>
                      <div style={{
                        maxWidth: '85%', padding: '10px 14px', borderRadius: '12px',
                        background: msg.role === 'user' ? 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)' : '#f8fafc',
                        color: msg.role === 'user' ? 'white' : '#1e293b',
                        border: msg.role === 'assistant' ? '1px solid #e2e8f0' : 'none'
                      }}>
                        <div style={{fontSize: '11px', fontWeight: '600', marginBottom: '4px', opacity: msg.role === 'user' ? 0.9 : 0.7}}>
                          {msg.role === 'user' ? '👤 我' : '🤖 AI'}
                        </div>
                        <div style={{fontSize: '14px', lineHeight: '1.6', whiteSpace: 'pre-wrap'}}>{msg.content}</div>
                      </div>
                    </div>
                  ))
                )}
                {/* AI 思考中动画 */}
                {isChatLoading && (
                  <div style={{marginBottom: '12px', display: 'flex', justifyContent: 'flex-start'}}>
                    <div style={{
                      maxWidth: '85%', padding: '12px 16px', borderRadius: '12px',
                      background: '#f8fafc', border: '1px solid #e2e8f0'
                    }}>
                      <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
                        <div style={{display: 'flex', gap: '4px'}}>
                          <span style={{width: '8px', height: '8px', borderRadius: '50%', background: '#3b82f6', animation: 'bounce 1.4s infinite ease-in-out both'}}></span>
                          <span style={{width: '8px', height: '8px', borderRadius: '50%', background: '#3b82f6', animation: 'bounce 1.4s infinite ease-in-out both', animationDelay: '0.16s'}}></span>
                          <span style={{width: '8px', height: '8px', borderRadius: '50%', background: '#3b82f6', animation: 'bounce 1.4s infinite ease-in-out both', animationDelay: '0.32s'}}></span>
                        </div>
                        <span style={{fontSize: '13px', color: '#64748b'}}>AI 正在思考...</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
              <div style={{display: 'flex', gap: '8px', marginTop: 'auto'}}>
                <input type="text" value={chatInput} onChange={(e) => setChatInput(e.target.value)} placeholder="输入问题..."
                  style={{flex: 1, padding: '12px 16px', border: '1px solid #e5e7eb', borderRadius: '24px', fontSize: '14px', outline: 'none'}}
                  onKeyPress={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleChatSend() } }}
                  disabled={isChatLoading}
                />
                <button onClick={handleChatSend} disabled={isChatLoading || !chatInput.trim()} className="btn btn-primary" style={{padding: '12px 24px', borderRadius: '24px'}}>
                  {isChatLoading ? '...' : '发送'}
                </button>
              </div>
            </div>
          </div>

          {/* 右：项目知识库（按文档类型显示） */}
          <div className="card">
            <div className="card-header" style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
              <h2 className="card-title">📚 项目知识库</h2>
              <button className="btn btn-outline btn-sm" onClick={() => setShowUploadModal(true)} style={{fontSize: '11px', padding: '4px 10px'}}>📤 上传</button>
            </div>
            <div className="card-body" style={{maxHeight: '400px', overflowY: 'auto'}}>
              {(() => {
                const docTypes = ['需求文档', '设计文档', '会议纪要', '技术方案']
                const typeIcon: Record<string, string> = {'需求文档': '📋', '设计文档': '📐', '会议纪要': '📝', '技术方案': '🔧'}
                const docsByType: Record<string, KnowledgeDoc[]> = {}
                docTypes.forEach(type => { docsByType[type] = (knowledgeDocs || []).filter(d => d.doc_type === type) })
                const hasAnyDocs = Object.values(docsByType).some(docs => docs.length > 0)
                
                if (!hasAnyDocs) {
                  return <div style={{textAlign: 'center', padding: '60px 20px', color: '#94a3b8'}}>
                    <div style={{fontSize: '48px', marginBottom: '16px'}}>📁</div>
                    <div style={{fontSize: '13px'}}>暂无文档</div>
                  </div>
                }
                
                return <div className="space-y-4">
                  {docTypes.map(type => {
                    const docs = docsByType[type]
                    if (docs.length === 0) return null
                    return <div key={type}>
                      <div style={{display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px', paddingBottom: '6px', borderBottom: '1px solid #e5e7eb'}}>
                        <span>{typeIcon[type]}</span>
                        <span style={{fontSize: '12px', fontWeight: '600', color: '#475569'}}>{type}</span>
                        <span style={{fontSize: '10px', padding: '2px 6px', background: '#e5e7eb', borderRadius: '10px', color: '#64748b'}}>{docs.length}</span>
                      </div>
                      <div className="space-y-2">
                        {docs.slice(0, 3).map(doc => (
                          <div key={doc.id} style={{padding: '8px 10px', background: '#f8fafc', borderRadius: '6px', fontSize: '12px'}}>
                            <div style={{fontWeight: '500', color: '#1e293b'}}>{doc.doc_name}</div>
                            <div style={{color: '#94a3b8', fontSize: '11px', marginTop: '2px'}}>{doc.upload_time}</div>
                          </div>
                        ))}
                        {docs.length > 3 && <div style={{textAlign: 'center', color: '#94a3b8', fontSize: '11px'}}>还有 {docs.length - 3} 个...</div>}
                      </div>
                    </div>
                  })}
                </div>
              })()}
            </div>
          </div>
        </div>

        {/* 上传文档模态框 */}
        {showUploadModal && (
          <div className="modal-overlay" onClick={() => setShowUploadModal(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{maxWidth: '520px'}}>
              <div className="modal-header">
                <h3 className="modal-title">📤 上传项目文档</h3>
                <button className="modal-close" onClick={() => setShowUploadModal(false)}>×</button>
              </div>
              <div className="modal-body" style={{padding: '24px'}}>
                <div style={{padding: '12px 16px', background: 'linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%)', borderRadius: '8px', marginBottom: '20px', fontSize: '13px'}}>
                  <div style={{display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px'}}>
                    <span style={{fontSize: '16px'}}>📁</span>
                    <span style={{fontWeight: '600', color: '#0369a1'}}>目标项目</span>
                  </div>
                  <div style={{color: '#0c4a6e', marginLeft: '24px'}}>{project?.name || '未选择项目'}</div>
                </div>
                <div className="form-group">
                  <label className="form-label">📄 文档名称 <span style={{color: '#ef4444'}}>*</span></label>
                  <input type="text" className="form-input" value={uploadForm.doc_name} onChange={(e) => setUploadForm({...uploadForm, doc_name: e.target.value})} placeholder="例如：需求调研报告" style={{fontSize: '14px', padding: '10px 14px'}} />
                </div>
                <div className="form-group">
                  <label className="form-label">📂 文档类型</label>
                  <select className="form-input" value={uploadForm.doc_type} onChange={(e) => setUploadForm({...uploadForm, doc_type: e.target.value})} style={{fontSize: '14px', padding: '10px 14px'}}>
                    <option value="需求文档">📋 需求文档</option>
                    <option value="设计文档">📐 设计文档</option>
                    <option value="会议纪要">📝 会议纪要</option>
                    <option value="技术方案">🔧 技术方案</option>
                  </select>
                </div>
                <div className="form-group" style={{marginBottom: 0}}>
                  <label className="form-label">📎 选择文件 <span style={{color: '#ef4444'}}>*</span></label>
                  <div style={{position: 'relative', padding: '20px', border: '2px dashed #cbd5e1', borderRadius: '8px', background: '#f8fafc', textAlign: 'center', cursor: 'pointer'}}>
                    <input type="file" accept=".pdf,.docx,.doc,.txt,.md" onChange={(e) => setUploadForm({...uploadForm, file: e.target.files?.[0] || null})} style={{position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', opacity: 0, cursor: 'pointer'}} />
                    {uploadForm.file ? (
                      <div>
                        <div style={{fontSize: '24px', marginBottom: '8px'}}>✅</div>
                        <div style={{color: '#059669', fontWeight: '500'}}>{uploadForm.file.name}</div>
                      </div>
                    ) : (
                      <div>
                        <div style={{fontSize: '24px', marginBottom: '8px'}}>📤</div>
                        <div style={{color: '#475569', fontWeight: '500'}}>点击或拖拽文件到此处</div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
              <div className="modal-footer" style={{padding: '16px 24px', gap: '12px'}}>
                <button className="btn btn-outline" onClick={() => setShowUploadModal(false)} style={{flex: 1, padding: '10px 20px'}}>取消</button>
                <button className="btn btn-primary" onClick={handleUpload} disabled={!uploadForm.doc_name || !uploadForm.file} style={{flex: 2, padding: '10px 20px'}}>📤 上传文档</button>
              </div>
            </div>
          </div>
        )}

        {/* 项目计划表 */}
        <div className="card mt-6">
          <div className="card-header">
            <h2 className="card-title">📋 项目计划</h2>
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-500">{(tasks || []).length} 个任务</span>
              <Link to={`/plans?project_id=${project?.id}`} className="btn btn-secondary btn-sm">
                上传计划
              </Link>
            </div>
          </div>
          <div className="card-body">
            {(tasks?.length || 0) === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">📅</div>
                <p className="empty-title">暂无计划任务</p>
                <p className="empty-desc">请上传项目计划Excel</p>
              </div>
            ) : (
              <div className="task-tree">
                {Object.entries(groupedTasks || {}).map(([phase, phaseTasks]) => {
                  const isPhaseExpanded = expandedPhases.has(phase)
                  const phaseProgress = phaseTasks.reduce((sum, t) => sum + (t.progress || 0), 0) / (phaseTasks.length || 1)
                  
                  return (
                    <div key={phase} className="task-phase">
                      <div 
                        className="task-phase-header"
                        onClick={() => {
                          const newExpanded = new Set(expandedPhases)
                          if (isPhaseExpanded) {
                            newExpanded.delete(phase)
                          } else {
                            newExpanded.add(phase)
                          }
                          setExpandedPhases(newExpanded)
                        }}
                      >
                        <span style={{
                          marginRight: '8px',
                          transform: isPhaseExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                          transition: 'transform 0.2s',
                          display: 'inline-block'
                        }}>▶</span>
                        <span style={{fontWeight: '600', color: '#1e293b'}}>{phase}</span>
                        <span className="text-sm text-gray-500" style={{marginLeft: '12px'}}>
                          {(phaseTasks?.length || 0)} 个任务
                        </span>
                        <div className="flex items-center gap-2" style={{marginLeft: 'auto'}}>
                          <div className="progress-bar-sm" style={{width: '100px'}}>
                            <div className="progress-bar-fill" style={{ width: `${phaseProgress}%` }} />
                          </div>
                          <span className="text-sm font-medium">{phaseProgress.toFixed(0)}%</span>
                        </div>
                      </div>
                      
                      {isPhaseExpanded && (
                        <ProjectTaskList 
                          tasks={phaseTasks || []}
                          initialLimit={5}
                          expandedTasks={expandedTasks}
                          onToggleTask={(taskId) => {
                            const newExpanded = new Set(expandedTasks)
                            if (newExpanded.has(taskId)) {
                              newExpanded.delete(taskId)
                            } else {
                              newExpanded.add(taskId)
                            }
                            setExpandedTasks(newExpanded)
                          }}
                        />
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </main>

      {/* 成本导入弹窗 */}
      {showCostImport && (
        <CostImportModal
          projectId={projectId?.toString()}
          projectName={project?.name}
          onClose={() => setShowCostImport(false)}
          onSuccess={() => {
            loadProjectDetail() // 刷新项目数据
          }}
        />
      )}

      {/* 移动端底部导航 */}
      <nav className="mobile-nav">
        <Link to="/" className="mobile-nav-item">
          <span className="mobile-nav-icon">🏠</span>
          <span>首页</span>
        </Link>
        <Link to="/daily" className="mobile-nav-item">
          <span className="mobile-nav-icon">📝</span>
          <span>日报</span>
        </Link>
        <Link to="/projects" className="mobile-nav-item active">
          <span className="mobile-nav-icon">📊</span>
          <span>项目</span>
        </Link>
        <Link to="/plans" className="mobile-nav-item">
          <span className="mobile-nav-icon">📁</span>
          <span>计划</span>
        </Link>
      </nav>
    </div>
  )
}
