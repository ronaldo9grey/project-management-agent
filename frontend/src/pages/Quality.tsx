import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAppStore } from '../store'
import MobileNav from '../components/MobileNav'
import { redirectToLogin } from '../utils/auth'
import { showToast } from '../components/Toast'
import { apiClient } from '../api'

interface QualitySummary {
  total_tasks: number
  total_opportunities: number
  total_defects: number
  dpmo: number
  sigma_level: number
  defect_rate: number
}

interface QualityBreakdown {
  delayed_defects: number
  total_delayed: number
  overbudget_defects: number
  total_cost_projects: number
  severe_delayed?: number
}

interface ProjectDefect {
  project_id: number
  project_name: string
  leader: string
  total_tasks: number
  delayed_tasks: number
  severe_delayed: number
  cost_overrun: number
  total_defects: number
}

interface DefectTrend {
  week: string
  new_tasks: number
  new_delayed: number
}

interface QualityData {
  summary: QualitySummary
  breakdown: QualityBreakdown
  project_defects: ProjectDefect[]
  defect_trend: DefectTrend[]
  formulas: {
    dpmo: string
    defect_definition: string
    sigma_table: string
  }
}

// 帕累托分析数据
interface ParetoProject {
  project_name: string
  leader: string
  total_tasks: number
  severe_defects: number
  total_defects: number
  cumulative: number
  cumulative_pct: number
}

interface ParetoTime {
  delay_range: string
  defect_count: number
  percentage: number
}

interface ParetoInsight {
  type: string
  message: string
  recommendation: string
}

interface ParetoData {
  project_pareto: ParetoProject[]
  time_pareto: ParetoTime[]
  pareto_80_index: number
  total_defects: number
  insights: ParetoInsight[]
}

// Tips 弹窗
function TipsModal({ title, content, onClose }: { title: string; content: string; onClose: () => void }) {
  return (
    <div 
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.5)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center'
      }}
      onClick={onClose}
    >
      <div 
        style={{
          background: 'white',
          width: '100%',
          maxWidth: 500,
          borderRadius: '16px 16px 0 0',
          padding: 20,
          maxHeight: '60vh',
          overflow: 'auto'
        }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, margin: 0 }}>{title}</h3>
          <button onClick={onClose} style={{ background: '#f1f5f9', border: 'none', width: 28, height: 28, borderRadius: '50%', fontSize: 16, cursor: 'pointer' }}>✕</button>
        </div>
        <div style={{ background: '#f8fafc', borderRadius: 8, padding: 14, fontSize: 13, lineHeight: 1.7, color: '#475569', whiteSpace: 'pre-wrap' }}>
          {content}
        </div>
      </div>
    </div>
  )
}

export default function QualityPage() {
  const { token, user, logout } = useAppStore()
  const [data, setData] = useState<QualityData | null>(null)
  const [paretoData, setParetoData] = useState<ParetoData | null>(null)
  const [analysisData, setAnalysisData] = useState<any>(null)
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [analysisProject, setAnalysisProject] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [tipsModal, setTipsModal] = useState<{title: string; content: string} | null>(null)
  const [isMobile, setIsMobile] = useState(false)
  const [showUserMenu, setShowUserMenu] = useState(false)

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768)
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
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

  useEffect(() => {
    loadData()
  }, [])
  
  const handleLogout = () => {
    logout()
    redirectToLogin()
  }

  const loadData = async () => {
    setLoading(true)
    try {
      const [overviewRes, paretoRes] = await Promise.all([
        apiClient.get('/api/agent/quality/overview'),
        apiClient.get('/api/agent/quality/pareto')
      ])
      if (overviewRes.data.success) setData(overviewRes.data.data)
      if (paretoRes.data.success) setParetoData(paretoRes.data.data)
    } catch (err: any) {
      console.error('加载失败:', err)
      if (err.message?.includes('Failed to fetch')) {
        showToast('网络连接不稳定，正在重试...', 'warning')
      } else {
        showToast('加载质量数据失败', 'error')
      }
    } finally {
      setLoading(false)
    }
  }

  // AI 根因分析
  const analyzeProject = async (projectId: number, projectName: string) => {
    setAnalysisLoading(true)
    setAnalysisProject(projectName)
    setAnalysisData(null)
    
    // 立即滚动到 AI 分析结果区域
    setTimeout(() => {
      const analysisSection = document.querySelector('[data-analysis-section]')
      if (analysisSection) {
        analysisSection.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }, 50)
    
    try {
      // 使用 fetch + 超时控制，AI 分析可能需要 30+ 秒
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 60000)
      
      const res = await fetch(`/api/agent/quality/analysis/${projectId}`, {
        headers: { Authorization: `Bearer ${token}` },
        signal: controller.signal
      })
      
      clearTimeout(timeoutId)
      
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }
      
      const json = await res.json()
      if (json.success) {
        setAnalysisData(json.data)
      } else {
        console.error('分析失败:', json.error)
        showToast(json.error || '分析失败', 'error')
      }
    } catch (err: any) {
      console.error('分析失败:', err)
      
      // 友好的错误提示
      if (err.name === 'AbortError') {
        showToast('AI 分析超时，请稍后重试', 'error')
      } else if (err.message?.includes('Failed to fetch') || err.message?.includes('CONNECTION_RESET')) {
        showToast('网络连接不稳定，正在重试...', 'warning')
        // 自动重试一次
        setTimeout(() => {
          analyzeProject(projectId, projectName)
        }, 2000)
        return
      } else {
        showToast('分析失败，请稍后重试', 'error')
      }
    } finally {
      setAnalysisLoading(false)
    }
  }

  // 获取西格玛等级颜色
  const getSigmaColor = (level: number) => {
    if (level >= 5) return '#22c55e'
    if (level >= 4) return '#84cc16'
    if (level >= 3) return '#f59e0b'
    return '#ef4444'
  }

  // Tips 图标
  const TipsIcon = ({ title, content }: { title: string; content: string }) => (
    <button
      onClick={(e) => { e.stopPropagation(); setTipsModal({ title, content }) }}
      style={{ background: 'transparent', border: 'none', fontSize: 14, cursor: 'pointer', opacity: 0.6, marginLeft: 4, padding: 0 }}
    >
      ℹ️
    </button>
  )

  if (loading) {
    return (
      <div className="page-container" style={{ paddingTop: 100, textAlign: 'center', color: '#94a3b8' }}>
        加载中...
      </div>
    )
  }

  if (!data) {
    return (
      <div className="page-container" style={{ paddingTop: 100, textAlign: 'center', color: '#94a3b8' }}>
        暂无数据
      </div>
    )
  }

  return (
    <div className="page-container" style={{ paddingBottom: 80 }}>
      {tipsModal && <TipsModal title={tipsModal.title} content={tipsModal.content} onClose={() => setTipsModal(null)} />}

      {/* 顶部导航 - PC端 */}
      <header className="header" style={{ display: isMobile ? 'none' : 'block' }}>
        <div className="header-content">
          <div className="header-left">
            <Link to="/" className="header-logo">
              <span className="text-xl">⚙️</span>
              <span className="header-title">项目管家</span>
            </Link>
            <nav className="header-nav">
              <Link to="/" className="nav-link">个人</Link>
              <Link to="/daily" className="nav-link">日报</Link>
              <Link to="/projects" className="nav-link">项目</Link>
              <Link to="/tracking" className="nav-link">追踪</Link>
              <Link to="/quality" className="nav-link active">质量</Link>
              <Link to="/dashboard" className="nav-link">看板</Link>
            </nav>
          </div>
          <div className="header-right">
            <div className="user-menu-wrapper" style={{ position: 'relative' }}>
              <div 
                className="user-info"
                onClick={() => setShowUserMenu(!showUserMenu)}
                style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}
              >
                <div className="user-avatar">{user?.name?.[0]?.toUpperCase() || 'U'}</div>
                <span className="user-name">{user?.name || '用户'}</span>
                <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </div>
              {showUserMenu && (
                <div className="user-dropdown">
                  <div className="user-dropdown-header">
                    <div className="user-avatar-lg">{user?.name?.[0]?.toUpperCase() || 'U'}</div>
                    <div>
                      <div style={{ fontWeight: 500, color: '#1f2937' }}>{user?.name || '用户'}</div>
                      {user?.department && <div style={{ fontSize: 12, color: '#6b7280' }}>{user.department}</div>}
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

      {/* 顶部标题 - 移动端 */}
      <header style={{ 
        display: isMobile ? 'flex' : 'none',
        background: 'linear-gradient(135deg, #059669 0%, #047857 100%)',
        boxShadow: '0 2px 8px rgba(5, 150, 105, 0.3)',
        padding: '10px 16px',
        position: 'sticky',
        top: 0,
        zIndex: 100,
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <h1 style={{ color: 'white', fontSize: 18, fontWeight: 600, margin: 0 }}>🎯 质量管理</h1>
        
        {/* 用户菜单 - 移动端 */}
        <div className="user-menu-wrapper" style={{ position: 'relative' }}>
          <div 
            onClick={() => setShowUserMenu(!showUserMenu)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              cursor: 'pointer',
              color: 'white'
            }}
          >
            <div style={{
              width: 28,
              height: 28,
              borderRadius: '50%',
              background: 'rgba(255,255,255,0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 600,
              fontSize: 12
            }}>
              {user?.name?.[0]?.toUpperCase() || 'U'}
            </div>
            <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
          
          {showUserMenu && (
            <div style={{
              position: 'absolute',
              top: '100%',
              right: 0,
              marginTop: 8,
              background: 'white',
              borderRadius: 12,
              boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
              minWidth: 160,
              overflow: 'hidden'
            }}>
              <div style={{ padding: '12px 16px', borderBottom: '1px solid #e5e7eb' }}>
                <div style={{ fontWeight: 500, color: '#1f2937' }}>{user?.name || '用户'}</div>
                {user?.department && <div style={{ fontSize: 12, color: '#6b7280' }}>{user.department}</div>}
              </div>
              <Link to="/plans" style={{ display: 'block', padding: '10px 16px', color: '#374151', textDecoration: 'none' }}>📋 我的计划</Link>
              <button 
                onClick={handleLogout}
                style={{
                  display: 'block',
                  width: '100%',
                  padding: '10px 16px',
                  textAlign: 'left',
                  border: 'none',
                  background: 'none',
                  color: '#dc2626',
                  cursor: 'pointer'
                }}
              >
                退出登录
              </button>
            </div>
          )}
        </div>
      </header>

      <div style={{ padding: 16 }}>
        {/* PC端布局 */}
        {!isMobile && (
          <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
            {/* 西格玛水平大卡片 */}
            <div style={{
              background: `linear-gradient(135deg, ${getSigmaColor(data.summary.sigma_level)} 0%, ${getSigmaColor(data.summary.sigma_level)}dd 100%)`,
              borderRadius: 16,
              padding: '24px 32px',
              color: 'white',
              minWidth: 180,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <div style={{ fontSize: 14, opacity: 0.9, marginBottom: 8 }}>西格玛水平</div>
              <div style={{ fontSize: 56, fontWeight: 700 }}>{data.summary.sigma_level.toFixed(1)}σ</div>
              <div style={{ fontSize: 12, opacity: 0.8, marginTop: 4 }}>DPMO: {data.summary.dpmo.toLocaleString()}</div>
            </div>

            {/* 统计网格 */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
              {/* 核心指标 */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: 10,
                background: 'white',
                borderRadius: 12,
                padding: '16px 20px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.08)'
              }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 24, fontWeight: 700, color: '#3b82f6' }}>{data.summary.total_tasks}</div>
                  <div style={{ fontSize: 12, color: '#64748b' }}>总任务数</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 24, fontWeight: 700, color: '#ef4444' }}>{data.summary.total_defects}</div>
                  <div style={{ fontSize: 12, color: '#64748b' }}>缺陷数</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 24, fontWeight: 700, color: '#f59e0b' }}>{data.summary.defect_rate}%</div>
                  <div style={{ fontSize: 12, color: '#64748b' }}>缺陷率</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 24, fontWeight: 700, color: '#64748b' }}>{data.summary.total_opportunities}</div>
                  <div style={{ fontSize: 12, color: '#64748b' }}>机会数</div>
                </div>
              </div>

              {/* 缺陷分布 */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: 10
              }}>
                <div style={{ background: 'white', borderRadius: 12, padding: '12px 8px', textAlign: 'center', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: '#ef4444' }}>{data.breakdown.severe_delayed}</div>
                  <div style={{ fontSize: 11, color: '#64748b' }}>严重延期</div>
                </div>
                <div style={{ background: 'white', borderRadius: 12, padding: '12px 8px', textAlign: 'center', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: '#f59e0b' }}>{data.breakdown.total_delayed}</div>
                  <div style={{ fontSize: 11, color: '#64748b' }}>延期任务</div>
                </div>
                <div style={{ background: 'white', borderRadius: 12, padding: '12px 8px', textAlign: 'center', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: '#ef4444' }}>{data.breakdown.overbudget_defects}</div>
                  <div style={{ fontSize: 11, color: '#64748b' }}>成本超支</div>
                </div>
                <div style={{ background: 'white', borderRadius: 12, padding: '12px 8px', textAlign: 'center', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: '#3b82f6' }}>{data.breakdown.total_cost_projects}</div>
                  <div style={{ fontSize: 11, color: '#64748b' }}>成本监控</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 手机端布局 */}
        {isMobile && (
          <>
            {/* 西格玛水平 */}
            <div style={{
              background: `linear-gradient(135deg, ${getSigmaColor(data.summary.sigma_level)} 0%, ${getSigmaColor(data.summary.sigma_level)}dd 100%)`,
              borderRadius: 16,
              padding: '20px 24px',
              marginBottom: 12,
              color: 'white',
              display: 'flex',
              alignItems: 'center',
              gap: 20
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, opacity: 0.9 }}>西格玛水平</div>
                <div style={{ fontSize: 42, fontWeight: 700 }}>{data.summary.sigma_level.toFixed(1)}σ</div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: 12, opacity: 0.8 }}>DPMO</div>
                <div style={{ fontSize: 20, fontWeight: 600 }}>{data.summary.dpmo.toLocaleString()}</div>
              </div>
            </div>

            {/* 核心指标 */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 12 }}>
              {[
                { label: '总任务', value: data.summary.total_tasks, color: '#3b82f6' },
                { label: '缺陷', value: data.summary.total_defects, color: '#ef4444' },
                { label: '缺陷率', value: `${data.summary.defect_rate}%`, color: '#f59e0b' },
                { label: '机会数', value: data.summary.total_opportunities, color: '#64748b' }
              ].map(item => (
                <div key={item.label} style={{ background: 'white', borderRadius: 12, padding: '12px 8px', textAlign: 'center', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
                  <div style={{ fontSize: 18, fontWeight: 700, color: item.color }}>{item.value}</div>
                  <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>{item.label}</div>
                </div>
              ))}
            </div>

            {/* 缺陷分布 */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8, marginBottom: 16 }}>
              <div style={{ background: '#fef2f2', borderRadius: 12, padding: '14px 12px' }}>
                <div style={{ fontSize: 12, color: '#991b1b', marginBottom: 4 }}>⚠️ 严重延期</div>
                <div style={{ fontSize: 22, fontWeight: 700, color: '#dc2626' }}>{data.breakdown.severe_delayed} <span style={{ fontSize: 12, fontWeight: 400 }}>个任务</span></div>
              </div>
              <div style={{ background: '#fffbeb', borderRadius: 12, padding: '14px 12px' }}>
                <div style={{ fontSize: 12, color: '#92400e', marginBottom: 4 }}>💰 成本超支</div>
                <div style={{ fontSize: 22, fontWeight: 700, color: '#d97706' }}>{data.breakdown.overbudget_defects} <span style={{ fontSize: 12, fontWeight: 400 }}>个项目</span></div>
              </div>
            </div>
          </>
        )}

        {/* 缺陷定义说明 */}
        <div style={{
          background: '#f0fdf4',
          borderRadius: 12,
          padding: '12px 16px',
          marginBottom: 16,
          display: 'flex',
          alignItems: 'center',
          gap: 8
        }}>
          <span style={{ fontSize: 18 }}>📐</span>
          <div style={{ flex: 1, fontSize: 12, color: '#166534' }}>
            <strong>缺陷标准：</strong>任务延期 &gt; 3天 或 成本超支 &gt; 10%
          </div>
          <TipsIcon title="计算公式" content={data.formulas.dpmo + '\n\n' + data.formulas.sigma_table} />
        </div>

        {/* 高缺陷项目 */}
        {data.project_defects.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
              🔴 高缺陷项目
              <span style={{ fontSize: 12, fontWeight: 400, color: '#64748b' }}>（缺陷数 TOP 10）</span>
            </div>
            {data.project_defects.map((project, idx) => (
              <div 
                key={project.project_id}
                style={{
                  background: 'white',
                  borderRadius: 12,
                  padding: '14px 16px',
                  marginBottom: 8,
                  boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
                  borderLeft: `4px solid ${project.severe_delayed > 0 ? '#ef4444' : '#f59e0b'}`,
                }}
              >
                {/* 项目名称行 */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <span style={{
                    width: 24, height: 24, borderRadius: '50%',
                    background: project.total_defects >= 3 ? '#ef4444' : '#f59e0b',
                    color: 'white',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 12, fontWeight: 600,
                    flexShrink: 0
                  }}>{idx + 1}</span>
                  <span style={{ fontWeight: 500, fontSize: 14, flex: 1, minWidth: 0 }}>{project.project_name}</span>
                </div>
                
                {/* 按钮行 - 手机端单独一行 */}
                <div style={{ 
                  display: 'flex', 
                  gap: 8, 
                  marginBottom: 8,
                  flexDirection: isMobile ? 'row' : 'row',
                  flexWrap: 'wrap'
                }}>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      console.log('[AI分析] 点击项目:', project.project_id, project.project_name)
                      analyzeProject(project.project_id, project.project_name)
                    }}
                    onTouchEnd={(e) => {
                      if (isMobile) {
                        e.preventDefault()
                        e.stopPropagation()
                        console.log('[AI分析] 触摸项目:', project.project_id, project.project_name)
                        analyzeProject(project.project_id, project.project_name)
                      }
                    }}
                    style={{
                      background: '#3b82f6',
                      color: 'white',
                      border: 'none',
                      borderRadius: 8,
                      padding: isMobile ? '10px 16px' : '4px 12px',
                      fontSize: isMobile ? 14 : 11,
                      fontWeight: 500,
                      cursor: 'pointer',
                      whiteSpace: 'nowrap',
                      flex: isMobile ? 1 : 'none',
                      minWidth: isMobile ? 100 : 'auto',
                      touchAction: 'manipulation',
                      WebkitTapHighlightColor: 'transparent'
                    }}
                  >
                    🔍 AI分析
                  </button>
                  <a
                    href={`/agent/projects/${project.project_id}?from=quality`}
                    onClick={() => sessionStorage.setItem('project_detail_from', 'quality')}
                    style={{
                      background: '#f1f5f9',
                      color: '#64748b',
                      borderRadius: 8,
                      padding: isMobile ? '10px 16px' : '4px 12px',
                      fontSize: isMobile ? 14 : 11,
                      fontWeight: 500,
                      textDecoration: 'none',
                      whiteSpace: 'nowrap',
                      flex: isMobile ? 1 : 'none',
                      minWidth: isMobile ? 100 : 'auto',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      touchAction: 'manipulation'
                    }}
                  >
                    查看详情
                  </a>
                </div>
                
                {/* 标签行 */}
                <div style={{ display: 'flex', gap: 12, fontSize: 12, color: '#64748b', flexWrap: 'wrap' }}>
                  <span>👤 {project.leader || '未分配'}</span>
                  {project.severe_delayed > 0 && (
                    <span style={{ color: '#dc2626' }}>🚨 严重延期 {project.severe_delayed}</span>
                  )}
                  {project.delayed_tasks > 0 && (
                    <span style={{ color: '#f59e0b' }}>⚠️ 延期 {project.delayed_tasks}</span>
                  )}
                  {project.cost_overrun > 0 && (
                    <span style={{ color: '#dc2626' }}>💰 成本超支</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* AI 分析结果 */}
        {(analysisLoading || analysisData) && (
          <div data-analysis-section style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>
              🤖 AI 根因分析 - {analysisProject}
            </div>
            
            {analysisLoading && (
              <div style={{
                background: 'white',
                borderRadius: 12,
                padding: 20,
                textAlign: 'center',
                color: '#64748b'
              }}>
                <div style={{ fontSize: 20, marginBottom: 8 }}>⏳</div>
                正在进行 AI 分析...
              </div>
            )}
            
            {analysisData && !analysisLoading && (
              <div style={{
                background: 'white',
                borderRadius: 12,
                padding: 16,
                boxShadow: '0 1px 3px rgba(0,0,0,0.08)'
              }}>
                {!analysisData.has_defects ? (
                  <div style={{ textAlign: 'center', color: '#22c55e', padding: 20 }}>
                    <div style={{ fontSize: 32, marginBottom: 8 }}>✅</div>
                    {analysisData.message}
                  </div>
                ) : (
                  <>
                    {/* 统计摘要 */}
                    <div style={{
                      background: '#f8fafc',
                      borderRadius: 8,
                      padding: '12px 16px',
                      marginBottom: 12
                    }}>
                      <div style={{ fontSize: 12, color: '#64748b', marginBottom: 8 }}>延期统计</div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
                        <div>
                          <div style={{ fontSize: 16, fontWeight: 600, color: '#dc2626' }}>{analysisData.statistics.total_delayed}</div>
                          <div style={{ fontSize: 11, color: '#94a3b8' }}>延期任务</div>
                        </div>
                        <div>
                          <div style={{ fontSize: 16, fontWeight: 600, color: '#f59e0b' }}>{analysisData.statistics.avg_delay_days}天</div>
                          <div style={{ fontSize: 11, color: '#94a3b8' }}>平均延期</div>
                        </div>
                        <div>
                          <div style={{ fontSize: 16, fontWeight: 600, color: '#ef4444' }}>{analysisData.statistics.max_delay_days}天</div>
                          <div style={{ fontSize: 11, color: '#94a3b8' }}>最长延期</div>
                        </div>
                        <div>
                          <div style={{ fontSize: 16, fontWeight: 600, color: '#64748b' }}>{analysisData.statistics.assignees.length}</div>
                          <div style={{ fontSize: 11, color: '#94a3b8' }}>涉及人员</div>
                        </div>
                      </div>
                    </div>

                    {/* 原因分析 */}
                    <div style={{ marginBottom: 12 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: '#64748b', marginBottom: 8 }}>延期原因</div>
                      {analysisData.analysis.reasons?.map((reason: any, idx: number) => (
                        <div key={idx} style={{
                          background: reason.impact === '高' ? '#fef2f2' : '#fffbeb',
                          borderRadius: 8,
                          padding: '10px 12px',
                          marginBottom: 6,
                          display: 'flex',
                          justifyContent: 'space-between'
                        }}>
                          <div style={{ display: 'flex', gap: 8 }}>
                            <span style={{
                              background: reason.impact === '高' ? '#dc2626' : '#f59e0b',
                              color: 'white',
                              padding: '2px 8px',
                              borderRadius: 4,
                              fontSize: 10
                            }}>{reason.impact}</span>
                            <span style={{ fontSize: 13, fontWeight: 500 }}>{reason.type}</span>
                          </div>
                          <span style={{ fontSize: 12, color: '#64748b' }}>{reason.detail}</span>
                        </div>
                      ))}
                    </div>

                    {/* 改进建议 */}
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 600, color: '#64748b', marginBottom: 8 }}>改进建议</div>
                      {analysisData.analysis.recommendations?.map((rec: any, idx: number) => (
                        <div key={idx} style={{
                          background: '#f0fdf4',
                          borderRadius: 8,
                          padding: '10px 12px',
                          marginBottom: 6
                        }}>
                          <div style={{ fontSize: 13, color: '#166534' }}>💡 {rec.action}</div>
                          <div style={{ fontSize: 11, color: '#3b82f6', marginTop: 4 }}>
                            责任人：{rec.responsible} · 优先级：{rec.priority}
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        )}

        {/* 缺陷趋势 */}
        {data.defect_trend.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>📈 近期缺陷趋势</div>
            <div style={{
              background: 'white',
              borderRadius: 12,
              padding: 16,
              boxShadow: '0 1px 3px rgba(0,0,0,0.08)'
            }}>
              {/* 简单趋势图 */}
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 100 }}>
                {data.defect_trend.map((item, idx) => {
                  const maxDelayed = Math.max(...data.defect_trend.map(d => d.new_delayed), 1)
                  const height = (item.new_delayed / maxDelayed * 80)
                  return (
                    <div key={idx} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                      <div style={{
                        width: '100%',
                        background: item.new_delayed > 0 ? '#fecaca' : '#e2e8f0',
                        borderRadius: 4,
                        height: Math.max(height, 4),
                        transition: 'height 0.3s'
                      }} />
                      <div style={{ fontSize: 10, color: '#64748b', marginTop: 4 }}>{item.week}</div>
                      <div style={{ fontSize: 10, fontWeight: 600, color: item.new_delayed > 0 ? '#dc2626' : '#94a3b8' }}>
                        {item.new_delayed}
                      </div>
                    </div>
                  )
                })}
              </div>
              <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 8, textAlign: 'center' }}>
                每周新增延期任务数
              </div>
            </div>
          </div>
        )}

        {/* 帕累托分析 */}
        {paretoData && paretoData.project_pareto.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
              📊 帕累托分析（80/20 规律）
              <TipsIcon title="帕累托定律" content="20% 的原因贡献了 80% 的问题\n优先解决 TOP 项目可快速降低整体风险" />
            </div>
            
            {/* 关键洞察 */}
            {paretoData.insights.length > 0 && (
              <div style={{
                background: '#eff6ff',
                borderRadius: 12,
                padding: '12px 16px',
                marginBottom: 12
              }}>
                {paretoData.insights.map((insight, idx) => (
                  <div key={idx} style={{ marginBottom: idx < paretoData.insights.length - 1 ? 12 : 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: '#1e40af' }}>💡 {insight.message}</div>
                    <div style={{ fontSize: 12, color: '#3b82f6', marginTop: 2 }}>→ {insight.recommendation}</div>
                  </div>
                ))}
              </div>
            )}

            {/* 项目缺陷帕累托图 */}
            <div style={{
              background: 'white',
              borderRadius: 12,
              padding: 16,
              boxShadow: '0 1px 3px rgba(0,0,0,0.08)'
            }}>
              <div style={{ fontSize: 12, fontWeight: 500, color: '#64748b', marginBottom: 12 }}>
                项目缺陷分布（按缺陷数降序）
              </div>
              
              {/* 帕累托柱状图 - 手机端横向滚动 */}
              <div style={{ 
                display: 'flex', 
                alignItems: 'flex-end', 
                gap: isMobile ? 4 : 6, 
                height: 120,
                overflowX: isMobile ? 'auto' : 'visible',
                WebkitOverflowScrolling: 'touch'
              }}>
                {paretoData.project_pareto.slice(0, isMobile ? 5 : 8).map((item, idx) => {
                  const maxDefects = Math.max(...paretoData.project_pareto.map(p => p.total_defects), 1)
                  const height = (item.total_defects / maxDefects * 100)
                  const isTop20 = idx <= paretoData.pareto_80_index
                  const is80Percent = paretoData.pareto_80_index >= 0 && idx === paretoData.pareto_80_index
                  return (
                    <div key={idx} style={{ 
                      flex: isMobile ? '0 0 50px' : 1, 
                      display: 'flex', 
                      flexDirection: 'column', 
                      alignItems: 'center',
                      minWidth: isMobile ? 50 : 'auto'
                    }}>
                      {/* 数字和百分比标签 */}
                      <div style={{ 
                        display: 'flex', 
                        flexDirection: 'column', 
                        alignItems: 'center',
                        height: 28,
                        marginBottom: 4
                      }}>
                        {is80Percent && (
                          <div style={{
                            fontSize: 9,
                            color: '#dc2626',
                            fontWeight: 600,
                            whiteSpace: 'nowrap',
                            marginBottom: 2
                          }}>80%</div>
                        )}
                        <div style={{ fontSize: 10, fontWeight: 600, color: isTop20 ? '#dc2626' : '#64748b' }}>
                          {item.total_defects}
                        </div>
                      </div>
                      <div style={{
                        width: '100%',
                        background: isTop20 && paretoData.pareto_80_index >= 0 ? '#fca5a5' : '#cbd5e1',
                        borderRadius: 4,
                        height: Math.max(height, 4),
                        transition: 'height 0.3s'
                      }}>
                      </div>
                      <div style={{
                        fontSize: isMobile ? 8 : 9,
                        color: '#64748b',
                        marginTop: 4,
                        textAlign: 'center',
                        maxWidth: isMobile ? 50 : 60,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap'
                      }}>
                        {item.project_name.length > (isMobile ? 4 : 6) ? item.project_name.slice(0, isMobile ? 4 : 6) + '..' : item.project_name}
                      </div>
                    </div>
                  )
                })}
              </div>
              
              {/* 累计曲线说明 */}
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                marginTop: 12,
                paddingTop: 12,
                borderTop: '1px solid #e5e7eb',
                fontSize: 11
              }}>
                {paretoData.pareto_80_index >= 0 ? (
                  <span style={{ color: '#dc2626' }}>█ 前 {paretoData.pareto_80_index + 1} 个项目贡献 80% 缺陷</span>
                ) : (
                  <span style={{ color: '#64748b' }}>缺陷分布分散，TOP {paretoData.project_pareto.length} 项目累计 {paretoData.project_pareto[paretoData.project_pareto.length - 1]?.cumulative_pct || 0}%</span>
                )}
                <span style={{ color: '#64748b' }}>共 {paretoData.total_defects} 个缺陷</span>
              </div>
            </div>

            {/* 延期时间段分布 */}
            {paretoData.time_pareto.length > 0 && (
              <div style={{
                background: 'white',
                borderRadius: 12,
                padding: 16,
                marginTop: 12,
                boxShadow: '0 1px 3px rgba(0,0,0,0.08)'
              }}>
                <div style={{ fontSize: 12, fontWeight: 500, color: '#64748b', marginBottom: 12 }}>
                  延期时间段分布
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 8 }}>
                  {paretoData.time_pareto.map((item, idx) => (
                    <div key={idx} style={{
                      background: idx === 0 ? '#fef2f2' : '#f8fafc',
                      borderRadius: 8,
                      padding: '10px 8px',
                      textAlign: 'center'
                    }}>
                      <div style={{ fontSize: 16, fontWeight: 700, color: idx === 0 ? '#dc2626' : '#64748b' }}>
                        {item.defect_count}
                      </div>
                      <div style={{ fontSize: 10, color: '#64748b', marginTop: 2 }}>{item.delay_range}</div>
                      <div style={{ fontSize: 9, color: '#94a3b8' }}>{item.percentage}%</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* 无缺陷状态 */}
        {data.project_defects.length === 0 && (
          <div style={{
            textAlign: 'center',
            padding: 40,
            color: '#94a3b8',
            background: 'white',
            borderRadius: 12
          }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>🎉</div>
            <div>当前无缺陷项目</div>
            <div style={{ fontSize: 12, marginTop: 4 }}>质量水平良好，继续保持！</div>
          </div>
        )}
      </div>

      <MobileNav active="quality" />
    </div>
  )
}
