import { useState, useEffect } from 'react'
import { useAppStore } from '../store'
import MobileNav from '../components/MobileNav'

// 视图类型
type ViewType = 'execution' | 'health' | 'trace'

// Tips 弹窗组件
function TipsModal({ 
  title, 
  content, 
  onClose 
}: { 
  title: string
  content: string
  onClose: () => void 
}) {
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
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16
        }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, margin: 0 }}>{title}</h3>
          <button 
            onClick={onClose}
            style={{
              background: '#f1f5f9',
              border: 'none',
              width: 28,
              height: 28,
              borderRadius: '50%',
              fontSize: 16,
              cursor: 'pointer'
            }}
          >✕</button>
        </div>
        <div style={{
          background: '#f8fafc',
          borderRadius: 8,
          padding: 14,
          fontSize: 13,
          lineHeight: 1.7,
          color: '#475569',
          whiteSpace: 'pre-wrap'
        }}>
          {content}
        </div>
      </div>
    </div>
  )
}

// 执行视图数据
interface Task {
  task_id: string
  task_name: string
  progress: number
  status: string
  start_date: string | null
  end_date: string | null
  assignee: string
  project_name: string
  project_id: number
  delay_days?: number
}

interface ExecutionData {
  today_tasks: Task[]
  week_tasks: Task[]
  month_tasks: Task[]
  overdue_tasks: Task[]
  completed: { task_id: string; task_name: string; completed_date: string; project_name: string }[]
  stats: { 
    today_count: number
    week_count: number
    month_count: number
    overdue_count: number
    completed_week: number
    total_pending: number
  }
  formulas: {
    today: string
    week: string
    month: string
    overdue: string
  }
}

// 健康视图数据
interface RiskProject {
  project_id: number
  project_name: string
  leader: string
  progress: number
  delayed_tasks: number
  overdue_tasks: number
  total_delay_days: number
  risk_score: number
}

interface HealthData {
  radar: {
    progress: number
    material: number
    labor: number
    outsource: number
    indirect: number
    overall: number
  }
  top_risks: RiskProject[]
  trends: {
    new_overdue_week: number
    silent_projects: number
    total_overdue: number
    total_delayed: number
  }
  formulas: {
    progress_risk: string
    cost_risk: string
    overall_risk: string
    project_score: string
  }
}

// 溯源视图数据
interface TraceProject {
  project_id: number
  project_name: string
  progress: number
  total_reports: number
  linked_reports: number
  link_rate: number
}

interface TraceData {
  link_rate: number
  linked_count: number
  total_count: number
  target_link_rate: number
  current_stage: string
  projects_trace: TraceProject[]
  untraceable_projects: TraceProject[]
  unsupported_progress: { project_id: number; project_name: string; progress: number; leader: string }[]
  formulas: {
    link_rate: string
    untraceable: string
    unsupported: string
    target_stages: string
  }
}

export default function TrackingPage() {
  const { token } = useAppStore()
  const [activeView, setActiveView] = useState<ViewType>('execution')
  const [executionData, setExecutionData] = useState<ExecutionData | null>(null)
  const [healthData, setHealthData] = useState<HealthData | null>(null)
  const [traceData, setTraceData] = useState<TraceData | null>(null)
  const [loading, setLoading] = useState(false)
  const [tipsModal, setTipsModal] = useState<{title: string; content: string} | null>(null)

  useEffect(() => {
    loadData()
  }, [activeView])

  const loadData = async () => {
    setLoading(true)
    try {
      const headers = { Authorization: `Bearer ${token}` }
      
      if (activeView === 'execution') {
        const res = await fetch('/api/agent/tracking/execution', { headers })
        const json = await res.json()
        setExecutionData(json.data)
      } else if (activeView === 'health') {
        const res = await fetch('/api/agent/tracking/health', { headers })
        const json = await res.json()
        setHealthData(json.data)
      } else {
        const res = await fetch('/api/agent/tracking/trace', { headers })
        const json = await res.json()
        setTraceData(json.data)
      }
    } catch (err) {
      console.error('加载失败:', err)
    } finally {
      setLoading(false)
    }
  }

  // 格式化日期
  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-'
    const d = new Date(dateStr)
    return `${d.getMonth() + 1}/${d.getDate()}`
  }

  // 计算剩余天数
  const getRemainDays = (endDate: string | null) => {
    if (!endDate) return null
    const end = new Date(endDate)
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const diff = Math.ceil((end.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))
    return diff
  }

  // 获取状态样式
  const getStatusStyle = (status: string, endDate: string | null, delayDays?: number) => {
    if (delayDays && delayDays > 0) {
      return { bg: '#fef2f2', color: '#dc2626', label: `延期${delayDays}天` }
    }
    if (status === '延期') {
      return { bg: '#fef2f2', color: '#dc2626', label: '延期' }
    }
    if (status === '已完成') {
      return { bg: '#f0fdf4', color: '#16a34a', label: '完成' }
    }
    const remain = getRemainDays(endDate)
    if (remain !== null && remain <= 3 && remain >= 0) {
      return { bg: '#fffbeb', color: '#d97706', label: '即将到期' }
    }
    return { bg: '#eff6ff', color: '#2563eb', label: '进行中' }
  }

  // 风险等级颜色
  const getRiskColor = (score: number) => {
    if (score >= 70) return '#dc2626'
    if (score >= 40) return '#f59e0b'
    return '#22c55e'
  }

  // Tips 图标按钮
  const TipsIcon = ({ title, content }: { title: string; content: string }) => (
    <button
      onClick={(e) => {
        e.stopPropagation()
        setTipsModal({ title, content })
      }}
      style={{
        background: 'transparent',
        border: 'none',
        fontSize: 14,
        cursor: 'pointer',
        opacity: 0.6,
        marginLeft: 4,
        padding: 0
      }}
    >
      ℹ️
    </button>
  )

  return (
    <div className="page-container" style={{ paddingBottom: 80 }}>
      {/* Tips 弹窗 */}
      {tipsModal && (
        <TipsModal 
          title={tipsModal.title} 
          content={tipsModal.content}
          onClose={() => setTipsModal(null)} 
        />
      )}

      {/* 顶部标题 */}
      <header style={{ 
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        boxShadow: '0 2px 8px rgba(102, 126, 234, 0.3)',
        padding: '14px 16px',
        position: 'sticky',
        top: 0,
        zIndex: 100
      }}>
        <h1 style={{ color: 'white', fontSize: 18, fontWeight: 600, margin: 0 }}>📍 项目追踪</h1>
      </header>

      {/* 视图切换标签 */}
      <div style={{
        display: 'flex',
        background: 'white',
        borderBottom: '1px solid #e5e7eb',
        position: 'sticky',
        top: 50,
        zIndex: 10
      }}>
        {[
          { key: 'execution', label: '执行', icon: '⚡' },
          { key: 'health', label: '健康', icon: '❤️' },
          { key: 'trace', label: '溯源', icon: '🔗' }
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveView(tab.key as ViewType)}
            style={{
              flex: 1,
              padding: '12px 16px',
              border: 'none',
              background: activeView === tab.key ? '#f8fafc' : 'transparent',
              borderBottom: activeView === tab.key ? '2px solid #667eea' : '2px solid transparent',
              color: activeView === tab.key ? '#667eea' : '#64748b',
              fontWeight: activeView === tab.key ? 600 : 400,
              fontSize: 14,
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
          >
            <span style={{ marginRight: 4 }}>{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* 内容区域 */}
      <div style={{ padding: '16px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#94a3b8' }}>
            加载中...
          </div>
        ) : (
          <>
            {/* 执行视图 */}
            {activeView === 'execution' && executionData && (
              <div>
                {/* 统计卡片 */}
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(4, 1fr)',
                  gap: 8,
                  marginBottom: 16
                }}>
                  {[
                    { label: '今日', count: executionData.stats.today_count, color: '#dc2626' },
                    { label: '本周', count: executionData.stats.week_count, color: '#f59e0b' },
                    { label: '本月', count: executionData.stats.month_count, color: '#3b82f6' },
                    { label: '完成', count: executionData.stats.completed_week, color: '#22c55e' }
                  ].map(stat => (
                    <div key={stat.label} style={{
                      background: 'white',
                      borderRadius: 12,
                      padding: '12px 8px',
                      textAlign: 'center',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
                    }}>
                      <div style={{ fontSize: 24, fontWeight: 700, color: stat.color }}>
                        {stat.count}
                      </div>
                      <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>
                        {stat.label}
                      </div>
                    </div>
                  ))}
                </div>

                {/* 已过期任务 */}
                {executionData.overdue_tasks && executionData.overdue_tasks.length > 0 && (
                  <TaskSection
                    title="⚠️ 已过期"
                    tasks={executionData.overdue_tasks}
                    getStatusStyle={getStatusStyle}
                    formatDate={formatDate}
                    getRemainDays={getRemainDays}
                    tipContent={executionData.formulas?.overdue || '截止日期 < 今天（已过期）'}
                  />
                )}

                {/* 今日任务 */}
                {executionData.today_tasks.length > 0 && (
                  <TaskSection
                    title="📌 今日截止"
                    tasks={executionData.today_tasks}
                    getStatusStyle={getStatusStyle}
                    formatDate={formatDate}
                    getRemainDays={getRemainDays}
                  />
                )}

                {/* 本周任务 */}
                {executionData.week_tasks.length > 0 && (
                  <TaskSection
                    title="📅 本周截止"
                    tasks={executionData.week_tasks}
                    getStatusStyle={getStatusStyle}
                    formatDate={formatDate}
                    getRemainDays={getRemainDays}
                  />
                )}

                {/* 本月任务 */}
                {executionData.month_tasks.length > 0 && (
                  <TaskSection
                    title="📆 本月截止"
                    tasks={executionData.month_tasks}
                    getStatusStyle={getStatusStyle}
                    formatDate={formatDate}
                    getRemainDays={getRemainDays}
                  />
                )}

                {/* 近期完成 */}
                {executionData.completed.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <div style={{
                      fontSize: 14,
                      fontWeight: 600,
                      color: '#22c55e',
                      marginBottom: 12,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6
                    }}>
                      ✅ 近期完成
                    </div>
                    {executionData.completed.map(task => (
                      <div key={task.task_id} style={{
                        background: '#f0fdf4',
                        borderRadius: 8,
                        padding: '10px 12px',
                        marginBottom: 6,
                        borderLeft: '3px solid #22c55e'
                      }}>
                        <div style={{ fontSize: 14, fontWeight: 500, color: '#166534' }}>
                          {task.task_name}
                        </div>
                        <div style={{ fontSize: 12, color: '#16a34a', marginTop: 2 }}>
                          {task.project_name} · {formatDate(task.completed_date)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* 空状态 */}
                {executionData.today_tasks.length === 0 && 
                 executionData.week_tasks.length === 0 && 
                 executionData.month_tasks.length === 0 &&
                 (!executionData.overdue_tasks || executionData.overdue_tasks.length === 0) && (
                  <div style={{
                    textAlign: 'center',
                    padding: 40,
                    color: '#94a3b8',
                    background: 'white',
                    borderRadius: 12
                  }}>
                    <div style={{ fontSize: 48, marginBottom: 12 }}>🎉</div>
                    <div>暂无待办任务</div>
                  </div>
                )}
              </div>
            )}

            {/* 健康视图 */}
            {activeView === 'health' && healthData && (
              <div>
                {/* 风险雷达 */}
                <div style={{
                  background: 'white',
                  borderRadius: 16,
                  padding: 20,
                  marginBottom: 16,
                  boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
                }}>
                  <div style={{
                    fontSize: 16,
                    fontWeight: 600,
                    marginBottom: 16,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8
                  }}>
                    🎯 风险雷达
                    <TipsIcon 
                      title="综合风险计算" 
                      content={healthData.formulas?.overall_risk || '进度风险 × 0.5 + 成本风险 × 0.5'} 
                    />
                    <span style={{
                      marginLeft: 'auto',
                      fontSize: 14,
                      background: healthData.radar.overall >= 50 ? '#fef2f2' : '#f0fdf4',
                      color: getRiskColor(healthData.radar.overall),
                      padding: '4px 12px',
                      borderRadius: 20,
                      fontWeight: 600
                    }}>
                      {healthData.radar.overall >= 50 ? '高风险' : '低风险'} {healthData.radar.overall}
                    </span>
                  </div>
                  
                  {/* 五维度进度条 */}
                  {[
                    { label: '进度风险', value: healthData.radar.progress, icon: '📊', tipKey: 'progress_risk' },
                    { label: '材料成本', value: healthData.radar.material, icon: '📦', tipKey: 'cost_risk' },
                    { label: '人工成本', value: healthData.radar.labor, icon: '👷', tipKey: 'cost_risk' },
                    { label: '外包成本', value: healthData.radar.outsource, icon: '🏢', tipKey: 'cost_risk' },
                    { label: '间接成本', value: healthData.radar.indirect, icon: '📋', tipKey: 'cost_risk' }
                  ].map(item => (
                    <div key={item.label} style={{ marginBottom: 12 }}>
                      <div style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        fontSize: 13,
                        marginBottom: 4
                      }}>
                        <span style={{ display: 'flex', alignItems: 'center' }}>
                          {item.icon} {item.label}
                        </span>
                        <span style={{ color: getRiskColor(item.value), fontWeight: 600 }}>
                          {item.value}%
                        </span>
                      </div>
                      <div style={{
                        height: 6,
                        background: '#e2e8f0',
                        borderRadius: 3,
                        overflow: 'hidden'
                      }}>
                        <div style={{
                          width: `${Math.min(item.value, 100)}%`,
                          height: '100%',
                          background: getRiskColor(item.value),
                          borderRadius: 3,
                          transition: 'width 0.3s'
                        }} />
                      </div>
                    </div>
                  ))}
                </div>

                {/* 趋势预警 */}
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(2, 1fr)',
                  gap: 8,
                  marginBottom: 16
                }}>
                  {[
                    { label: '新增过期', value: healthData.trends.new_overdue_week, color: '#dc2626', unit: '个' },
                    { label: '沉默项目', value: healthData.trends.silent_projects, color: '#f59e0b', unit: '个' }
                  ].map(item => (
                    <div key={item.label} style={{
                      background: 'white',
                      borderRadius: 12,
                      padding: '14px 10px',
                      textAlign: 'center',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
                    }}>
                      <div style={{ fontSize: 22, fontWeight: 700, color: item.color }}>
                        {item.value}{item.unit}
                      </div>
                      <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>
                        {item.label}
                      </div>
                    </div>
                  ))}
                </div>

                {/* 高风险项目 */}
                <div style={{
                  fontSize: 14,
                  fontWeight: 600,
                  marginBottom: 12,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6
                }}>
                  🔥 高风险项目 TOP5
                  <TipsIcon 
                    title="项目风险分计算" 
                    content={healthData.formulas?.project_score || '延期天数×2 + 过期任务数×15 + 延期任务数×10\n最高100分'} 
                  />
                </div>
                {healthData.top_risks.length > 0 ? healthData.top_risks.map((project, idx) => (
                  <div key={project.project_id} style={{
                    background: 'white',
                    borderRadius: 12,
                    padding: 14,
                    marginBottom: 8,
                    boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                    borderLeft: `4px solid ${getRiskColor(project.risk_score)}`
                  }}>
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: 8
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{
                          width: 24,
                          height: 24,
                          borderRadius: '50%',
                          background: getRiskColor(project.risk_score),
                          color: 'white',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: 12,
                          fontWeight: 600
                        }}>{idx + 1}</span>
                        <span style={{ fontWeight: 500, fontSize: 14 }}>{project.project_name}</span>
                      </div>
                      <span style={{
                        background: '#fef2f2',
                        color: '#dc2626',
                        padding: '2px 8px',
                        borderRadius: 12,
                        fontSize: 12,
                        fontWeight: 600
                      }}>
                        风险 {project.risk_score}
                      </span>
                    </div>
                    <div style={{
                      display: 'flex',
                      gap: 12,
                      fontSize: 12,
                      color: '#64748b',
                      flexWrap: 'wrap'
                    }}>
                      <span>👤 {project.leader || '未分配'}</span>
                      <span style={{ color: '#dc2626' }}>⏰ 过期 {project.overdue_tasks}</span>
                      <span style={{ color: '#f59e0b' }}>⚠️ 延期 {project.delayed_tasks}</span>
                      {project.total_delay_days > 0 && (
                        <span style={{ color: '#94a3b8' }}>📅 累计{project.total_delay_days}天</span>
                      )}
                    </div>
                  </div>
                )) : (
                  <div style={{
                    textAlign: 'center',
                    padding: 30,
                    color: '#94a3b8',
                    background: 'white',
                    borderRadius: 12
                  }}>
                    暂无高风险项目 🎉
                  </div>
                )}
              </div>
            )}

            {/* 溯源视图 */}
            {activeView === 'trace' && traceData && (
              <div>
                {/* 关联率大卡片 */}
                <div style={{
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  borderRadius: 16,
                  padding: 24,
                  marginBottom: 16,
                  color: 'white'
                }}>
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: 12
                  }}>
                    <span style={{ fontSize: 14, opacity: 0.9 }}>
                      日报-任务关联率
                    </span>
                    <span style={{ fontSize: 12, opacity: 0.7 }}>
                      {traceData.current_stage || '初级'}目标: {traceData.target_link_rate}%
                    </span>
                  </div>
                  <div style={{ fontSize: 42, fontWeight: 700, marginBottom: 8 }}>
                    {traceData.link_rate}%
                  </div>
                  <div style={{
                    height: 8,
                    background: 'rgba(255,255,255,0.2)',
                    borderRadius: 4,
                    overflow: 'hidden'
                  }}>
                    <div style={{
                      width: `${Math.min(traceData.link_rate, 100)}%`,
                      height: '100%',
                      background: 'white',
                      borderRadius: 4
                    }} />
                  </div>
                  <div style={{
                    marginTop: 12,
                    fontSize: 12,
                    opacity: 0.8
                  }}>
                    已关联 {traceData.linked_count} / {traceData.total_count} 条工作项
                  </div>
                </div>

                {/* 目标阶段 */}
                <div style={{
                  background: '#f0f9ff',
                  borderRadius: 12,
                  padding: 12,
                  marginBottom: 16,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8
                }}>
                  <span style={{ fontSize: 20 }}>🎯</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#0369a1' }}>
                      当前阶段：{traceData.current_stage || '初级'}
                    </div>
                    <div style={{ fontSize: 12, color: '#0c4a6e' }}>
                      初级50% → 中级70% → 高级80%
                    </div>
                  </div>
                </div>

                {/* 不可追溯项目 */}
                {traceData.untraceable_projects && traceData.untraceable_projects.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <div style={{
                      fontSize: 14,
                      fontWeight: 600,
                      marginBottom: 12,
                      color: '#dc2626',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6
                    }}>
                      ⚠️ 关联率偏低
                      <TipsIcon 
                        title="不可追溯定义" 
                        content={traceData.formulas?.untraceable || '关联率 < 50% 且有日报记录'} 
                      />
                    </div>
                    {traceData.untraceable_projects.map(project => (
                      <div key={project.project_id} style={{
                        background: '#fef2f2',
                        borderRadius: 10,
                        padding: 12,
                        marginBottom: 6
                      }}>
                        <div style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center'
                        }}>
                          <span style={{ fontWeight: 500, fontSize: 14, color: '#991b1b' }}>
                            {project.project_name}
                          </span>
                          <span style={{
                            background: '#fecaca',
                            color: '#dc2626',
                            padding: '2px 10px',
                            borderRadius: 12,
                            fontSize: 12,
                            fontWeight: 600
                          }}>
                            {project.link_rate}%
                          </span>
                        </div>
                        <div style={{
                          fontSize: 12,
                          color: '#7f1d1d',
                          marginTop: 4
                        }}>
                          已关联 {project.linked_reports}/{project.total_reports} 条
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* 进度无支撑 */}
                {traceData.unsupported_progress && traceData.unsupported_progress.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <div style={{
                      fontSize: 14,
                      fontWeight: 600,
                      marginBottom: 12,
                      color: '#f59e0b',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6
                    }}>
                      ❓ 进度无日报支撑
                      <TipsIcon 
                        title="无支撑定义" 
                        content={traceData.formulas?.unsupported || '项目进度 > 0 但近30天无日报'} 
                      />
                    </div>
                    {traceData.unsupported_progress.map(project => (
                      <div key={project.project_id} style={{
                        background: '#fffbeb',
                        borderRadius: 10,
                        padding: 12,
                        marginBottom: 6
                      }}>
                        <div style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center'
                        }}>
                          <span style={{ fontWeight: 500, fontSize: 14, color: '#92400e' }}>
                            {project.project_name}
                          </span>
                          <span style={{
                            background: '#fde68a',
                            color: '#92400e',
                            padding: '2px 10px',
                            borderRadius: 12,
                            fontSize: 12,
                            fontWeight: 600
                          }}>
                            进度 {project.progress}%
                          </span>
                        </div>
                        <div style={{
                          fontSize: 12,
                          color: '#78350f',
                          marginTop: 4
                        }}>
                          负责人: {project.leader || '未分配'} · 近30天无日报
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* 项目关联排行 */}
                {traceData.projects_trace && traceData.projects_trace.length > 0 && (
                  <>
                    <div style={{
                      fontSize: 14,
                      fontWeight: 600,
                      marginBottom: 12,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6
                    }}>
                      📊 项目关联排行
                    </div>
                    {traceData.projects_trace.slice(0, 5).map((project, idx) => (
                      <div key={project.project_id} style={{
                        background: 'white',
                        borderRadius: 10,
                        padding: 12,
                        marginBottom: 6,
                        boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
                      }}>
                        <div style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center'
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{
                              width: 20,
                              height: 20,
                              borderRadius: '50%',
                              background: project.link_rate >= 80 ? '#22c55e' : project.link_rate >= 50 ? '#f59e0b' : '#94a3b8',
                              color: 'white',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontSize: 11,
                              fontWeight: 600
                            }}>{idx + 1}</span>
                            <span style={{ fontWeight: 500, fontSize: 13 }}>{project.project_name}</span>
                          </div>
                          <span style={{
                            fontSize: 12,
                            fontWeight: 600,
                            color: project.link_rate >= 80 ? '#22c55e' : project.link_rate >= 50 ? '#f59e0b' : '#94a3b8'
                          }}>
                            {project.link_rate}%
                          </span>
                        </div>
                        <div style={{
                          marginTop: 6,
                          height: 4,
                          background: '#e2e8f0',
                          borderRadius: 2,
                          overflow: 'hidden'
                        }}>
                          <div style={{
                            width: `${Math.max(project.link_rate, 1)}%`,
                            height: '100%',
                            background: project.link_rate >= 80 ? '#22c55e' : project.link_rate >= 50 ? '#f59e0b' : '#94a3b8',
                            borderRadius: 2
                          }} />
                        </div>
                      </div>
                    ))}
                  </>
                )}

                {/* 空状态 */}
                {(!traceData.projects_trace || traceData.projects_trace.length === 0) && (
                  <div style={{
                    textAlign: 'center',
                    padding: 40,
                    color: '#94a3b8',
                    background: 'white',
                    borderRadius: 12
                  }}>
                    <div style={{ fontSize: 48, marginBottom: 12 }}>📊</div>
                    <div>暂无溯源数据</div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      <MobileNav active="tracking" />
    </div>
  )
}

// 任务列表组件
function TaskSection({ 
  title, 
  tasks, 
  getStatusStyle, 
  formatDate, 
  getRemainDays,
  tipContent
}: {
  title: string
  tasks: Task[]
  getStatusStyle: (status: string, endDate: string | null, delayDays?: number) => { bg: string; color: string; label: string }
  formatDate: (dateStr: string | null) => string
  getRemainDays: (endDate: string | null) => number | null
  tipContent?: string
}) {
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{
        fontSize: 14,
        fontWeight: 600,
        marginBottom: 10,
        color: '#334155',
        display: 'flex',
        alignItems: 'center'
      }}>
        {title}
        {tipContent && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              alert(tipContent)
            }}
            style={{
              background: 'transparent',
              border: 'none',
              fontSize: 14,
              cursor: 'pointer',
              opacity: 0.6,
              marginLeft: 4,
              padding: 0
            }}
          >ℹ️</button>
        )}
      </div>
      {tasks.map(task => {
        const style = getStatusStyle(task.status, task.end_date, task.delay_days)
        const remain = getRemainDays(task.end_date)
        
        return (
          <div key={task.task_id} style={{
            background: 'white',
            borderRadius: 12,
            padding: 14,
            marginBottom: 8,
            boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
            borderLeft: `3px solid ${style.color}`
          }}>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              marginBottom: 8
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 500, color: '#1e293b', marginBottom: 4 }}>
                  {task.task_name}
                </div>
                <div style={{ fontSize: 12, color: '#64748b' }}>
                  {task.project_name}
                </div>
              </div>
              <div style={{
                background: style.bg,
                color: style.color,
                padding: '3px 10px',
                borderRadius: 12,
                fontSize: 11,
                fontWeight: 600,
                whiteSpace: 'nowrap'
              }}>
                {style.label}
              </div>
            </div>
            
            {/* 进度条 */}
            <div style={{ marginBottom: 8 }}>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: 12,
                marginBottom: 4
              }}>
                <span style={{ color: '#64748b' }}>进度</span>
                <span style={{ fontWeight: 600, color: '#334155' }}>{task.progress}%</span>
              </div>
              <div style={{
                height: 4,
                background: '#e2e8f0',
                borderRadius: 2,
                overflow: 'hidden'
              }}>
                <div style={{
                  width: `${task.progress}%`,
                  height: '100%',
                  background: task.progress >= 80 ? '#22c55e' : task.progress >= 50 ? '#3b82f6' : '#94a3b8',
                  borderRadius: 2
                }} />
              </div>
            </div>
            
            {/* 时间信息 */}
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: 11,
              color: '#94a3b8'
            }}>
              <span>📅 {formatDate(task.start_date)} - {formatDate(task.end_date)}</span>
              {remain !== null && remain >= 0 && (
                <span style={{ color: remain <= 1 ? '#dc2626' : '#64748b' }}>
                  剩余 {remain} 天
                </span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
