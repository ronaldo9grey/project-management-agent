import SharedHeader from '../components/SharedHeader'
import { useState, useEffect } from 'react'
import MobileNav from '../components/MobileNav'
import DashboardTaskList from '../components/DashboardTaskList'
import { apiClient, api } from '../api'
import { showToast } from '../components/Toast'
import { confirm } from '../components/ConfirmDialog'

// 弹窗打开时禁止主页面滚动
const useLockBodyScroll = (lock: boolean) => {
  useEffect(() => {
    if (lock) {
      const originalOverflow = document.body.style.overflow
      document.body.style.overflow = 'hidden'
      return () => {
        document.body.style.overflow = originalOverflow || ''
      }
    }
  }, [lock])
}

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

interface EmployeeHoursData {
  year: number
  month: number
  month_start?: string
  month_end?: string
  working_days: number
  employee_count?: number
  employees: Array<{
    employee_name: string
    projects: Array<{
      project_name: string
      hours: number
      percent: number
    }>
    total_hours: number
    report_count: number
    required_days?: number
    filled_days: number
    missing_days: number
  }>
  total_hours: number
  total_reports: number
}

interface ProjectHoursData {
  year: number
  month: number
  working_days?: number
  employee_count?: number
  official_projects: Array<{
    project_name: string
    members: Record<string, number>
    total_hours: number
  }>
  official_employee_totals: Record<string, number>
  official_grand_total: number
  other_works: Array<{
    project_name: string
    members: Record<string, number>
    total_hours: number
  }>
  other_employee_totals: Record<string, number>
  other_grand_total: number
  all_employees: string[]
  all_employee_totals: Record<string, number>
  grand_total: number
  official_project_count: number
  other_work_count: number
}

// 人员项目投入分析卡片
function PersonAnalysisCard() {
  const currentYear = new Date().getFullYear()
  const [selectedEmployee, setSelectedEmployee] = useState<string>('')
  const [selectedYear, setSelectedYear] = useState<number>(currentYear)
  const [allEmployees, setAllEmployees] = useState<string[]>([])
  const [data, setData] = useState<{
    employee_name: string
    year: number
    total_hours: number
    project_count: number
    projects: Array<{ project_name: string; hours: number; percent: number; report_count: number }>
    monthly_trend: Array<{ month: number; hours: number }>
  } | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    apiClient.get('/api/agent/stats/person-project-analysis', {
      params: { employee_name: 'admin', year: currentYear }
    }).then(res => {
      setAllEmployees(res.data.all_employees || [])
      if (res.data.all_employees && res.data.all_employees.length > 0) {
        setSelectedEmployee(res.data.all_employees[0])
      }
    }).catch(err => console.error('获取员工列表失败:', err))
  }, [])

  useEffect(() => {
    if (!selectedEmployee) return
    setIsLoading(true)
    apiClient.get('/api/agent/stats/person-project-analysis', {
      params: { employee_name: selectedEmployee, year: selectedYear }
    }).then(res => {
      setData(res.data)
      setIsLoading(false)
    }).catch(err => {
      console.error('获取人员分析失败:', err)
      setIsLoading(false)
    })
  }, [selectedEmployee, selectedYear])

  if (isLoading || !data) {
    return (
      <div className="card" style={{ marginBottom: '20px' }}>
        <div className="card-header">
          <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '600' }}>👤 人员项目投入分析</h3>
        </div>
        <div className="card-body"><div className="skeleton skeleton-box" style={{ height: '400px' }} /></div>
      </div>
    )
  }

  const topProjects = data.projects.slice(0, 6)
  const otherHours = data.projects.slice(6).reduce((sum, p) => sum + p.hours, 0)
  if (otherHours > 0) topProjects.push({ project_name: '其他项目', hours: otherHours, percent: 0, report_count: 0 })
  
  const totalPieHours = topProjects.reduce((sum, p) => sum + p.hours, 0)
  topProjects.forEach(p => { p.percent = totalPieHours > 0 ? Math.round(p.hours / totalPieHours * 100) : 0 })
  
  const colors = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#94a3b8']
  const monthCount = data.monthly_trend?.length || 1
  const chartWidth = Math.max(400, monthCount * 60)
  
  return (
    <div className="card" style={{ marginBottom: '20px' }}>
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '600' }}>👤 人员项目投入分析</h3>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <select value={selectedEmployee} onChange={(e) => setSelectedEmployee(e.target.value)} style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid #e5e7eb', background: 'white', fontSize: '14px' }}>
            {allEmployees.map(emp => (<option key={emp} value={emp}>{emp}</option>))}
          </select>
          <select value={selectedYear} onChange={(e) => setSelectedYear(parseInt(e.target.value))} style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid #e5e7eb', background: 'white', fontSize: '14px' }}>
            <option value={currentYear - 1}>{currentYear - 1}年</option>
            <option value={currentYear}>{currentYear}年</option>
          </select>
        </div>
      </div>
      <div className="card-body" style={{ padding: '24px' }}>
        <div style={{ background: 'linear-gradient(135deg, #eff6ff 0%, #f0f9ff 100%)', borderRadius: '12px', padding: '16px 20px', marginBottom: '24px', display: 'flex', gap: '40px', alignItems: 'center' }}>
          <div><span style={{ fontSize: '14px', color: '#64748b' }}>总工时（正式项目）</span><div style={{ fontSize: '32px', fontWeight: '700', color: '#1e40af' }}>{data.total_hours}h</div></div>
          <div style={{ width: '1px', height: '40px', background: '#cbd5e1' }} />
          <div><span style={{ fontSize: '14px', color: '#64748b' }}>参与正式项目</span><div style={{ fontSize: '32px', fontWeight: '700', color: '#059669' }}>{data.project_count}个</div></div>
        </div>

        {data.projects.length > 0 && (
          <div style={{ marginBottom: '24px' }}>
            <h4 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '16px', color: '#1e40af' }}>📋 正式项目工时详情</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {data.projects.sort((a, b) => b.hours - a.hours).map((p, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', padding: '12px 16px', background: i < 3 ? '#eff6ff' : '#f8fafc', borderRadius: '10px', border: i < 3 ? '1px solid #3b82f6' : '1px solid #e2e8f0' }}>
                  <div style={{ width: '28px', height: '28px', borderRadius: '50%', background: i < 3 ? colors[i] : '#94a3b8', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: '700', fontSize: '14px', marginRight: '12px', flexShrink: 0 }}>{i + 1}</div>
                  <div style={{ flex: 1, minWidth: 0 }}><div style={{ fontSize: '14px', fontWeight: '500', color: '#1e293b', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.project_name}</div></div>
                  <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: '12px' }}><span style={{ fontWeight: '700', color: '#1e40af', fontSize: '16px' }}>{p.hours}h</span><span style={{ fontSize: '13px', color: '#64748b', marginLeft: '8px' }}>{p.percent}%</span></div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '32px' }}>
          <div>
            <h4 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '12px', color: '#374151', textAlign: 'center' }}>📊 工时占比</h4>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <svg width="240" height="240" viewBox="0 0 240 240">
                {(() => {
                  const radius = 100, cx = 120, cy = 120
                  let startAngle = 0
                  return topProjects.map((p, i) => {
                    const angle = (p.percent / 100) * 360, endAngle = startAngle + angle
                    const x1 = cx + radius * Math.cos((startAngle - 90) * Math.PI / 180)
                    const y1 = cy + radius * Math.sin((startAngle - 90) * Math.PI / 180)
                    const x2 = cx + radius * Math.cos((endAngle - 90) * Math.PI / 180)
                    const y2 = cy + radius * Math.sin((endAngle - 90) * Math.PI / 180)
                    const largeArc = angle > 180 ? 1 : 0
                    const path = `M ${cx} ${cy} L ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} Z`
                    const midAngle = (startAngle + endAngle) / 2 - 90
                    const labelRadius = radius * 0.65
                    const lx = cx + labelRadius * Math.cos(midAngle * Math.PI / 180)
                    const ly = cy + labelRadius * Math.sin(midAngle * Math.PI / 180)
                    startAngle = endAngle
                    return (
                      <g key={i}>
                        <path d={path} fill={colors[i] || '#94a3b8'} stroke="white" strokeWidth="3" />
                        {p.percent >= 6 && (<text x={lx} y={ly} textAnchor="middle" dominantBaseline="middle" style={{ fontSize: '14px', fontWeight: '700', fill: 'white' }}>{p.percent}%</text>)}
                      </g>
                    )
                  })
                })()}
              </svg>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginTop: '12px', justifyContent: 'center' }}>
                {topProjects.slice(0, 5).map((p, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
                    <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: colors[i] }} />
                    <span style={{ color: '#475569' }}>{(p.project_name || '其他').substring(0, 8)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div>
            <h4 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '12px', color: '#374151', textAlign: 'center' }}>📈 月度工时趋势</h4>
            <div style={{ overflowX: 'auto' }}>
              <svg width={chartWidth} height="200" viewBox={`0 0 ${chartWidth} 200`} style={{ background: '#f8fafc', borderRadius: '12px', minWidth: '100%' }}>
                {(() => {
                  const months = data.monthly_trend
                  if (!months || months.length === 0) return null
                  const maxHours = Math.max(...months.map(m => m.hours), 1)
                  const padding = { left: 45, right: 20, top: 35, bottom: 35 }
                  const chartWidthInner = chartWidth - padding.left - padding.right
                  const chartHeight = 200 - padding.top - padding.bottom
                  const xStep = chartWidthInner / Math.max(months.length - 1, 1)
                  const points = months.map((m, i) => {
                    const x = padding.left + i * xStep
                    const y = padding.top + chartHeight - (m.hours / maxHours) * chartHeight
                    return `${x},${y}`
                  }).join(' ')
                  const areaPoints = `${padding.left},${padding.top + chartHeight} ${points} ${padding.left + (months.length - 1) * xStep},${padding.top + chartHeight}`
                  return (
                    <>
                      {[0, 50, 100].map(pct => {
                        const y = padding.top + chartHeight - (pct / 100) * chartHeight
                        return <line key={pct} x1={padding.left} y1={y} x2={chartWidth - padding.right} y2={y} stroke="#e2e8f0" strokeWidth="1" strokeDasharray="4 4" />
                      })}
                      <polygon points={areaPoints} fill="url(#gradPerson)" opacity="0.3" />
                      <defs><linearGradient id="gradPerson" x1="0%" y1="0%" x2="0%" y2="100%"><stop offset="0%" stopColor="#3b82f6" /><stop offset="100%" stopColor="#3b82f6" stopOpacity="0" /></linearGradient></defs>
                      <polyline points={points} fill="none" stroke="#3b82f6" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                      {months.map((m, i) => {
                        const x = padding.left + i * xStep
                        const y = padding.top + chartHeight - (m.hours / maxHours) * chartHeight
                        return (
                          <g key={i}>
                            <circle cx={x} cy={y} r="6" fill="#3b82f6" stroke="white" strokeWidth="3" />
                            <text x={x} y={y - 14} textAnchor="middle" style={{ fontSize: '13px', fontWeight: '700', fill: '#1e40af' }}>{m.hours}h</text>
                            <text x={x} y={padding.top + chartHeight + 20} textAnchor="middle" style={{ fontSize: '13px', fill: '#64748b', fontWeight: '500' }}>{m.month}月</text>
                          </g>
                        )
                      })}
                    </>
                  )
                })()}
              </svg>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}



function MonthlyHoursCard({
  data,
  projectData,
  isLoading,
  selectedYear,
  selectedMonth,
  onMonthChange,
  onExport,
  onExportHumanCost,
  viewMode,
  onViewModeChange
}: { 
  data: EmployeeHoursData | null
  projectData: ProjectHoursData | null
  isLoading: boolean
  selectedYear: number
  selectedMonth: number
  onMonthChange: (year: number, month: number) => void
  onExport: () => void
  onExportHumanCost: () => void
  viewMode: 'employee' | 'project'
  onViewModeChange: (mode: 'employee' | 'project') => void
}) {
  const months = Array.from({ length: 12 }, (_, i) => i + 1)
  const currentYear = new Date().getFullYear()
  const years = [currentYear - 1, currentYear]
  const [expandedEmployee, setExpandedEmployee] = useState<string | null>(null)
  
  // 工时详情弹窗状态
  const [detailModal, setDetailModal] = useState<{
    show: boolean
    projectName: string
    employeeName: string
    details: any[]
    totalHours: number
    loading: boolean
  }>({
    show: false,
    projectName: '',
    employeeName: '',
    details: [],
    totalHours: 0,
    loading: false
  })
  
  // 弹窗打开时禁止主页面滚动
  useLockBodyScroll(detailModal.show)
  
  // 查询工时详情
  const loadHoursDetail = async (projectName: string, employeeName: string) => {
    setDetailModal(prev => ({ ...prev, show: true, projectName, employeeName, loading: true, details: [] }))
    try {
      const res = await apiClient.get('/api/agent/stats/project-employee-details', {
        params: {
          project_name: projectName,
          employee_name: employeeName,
          year: selectedYear,
          month: selectedMonth
        }
      })
      setDetailModal(prev => ({
        ...prev,
        details: res.data.details,
        totalHours: res.data.total_hours,
        loading: false
      }))
    } catch (error) {
      console.error('加载详情失败:', error)
      setDetailModal(prev => ({ ...prev, loading: false }))
    }
  }

  if (isLoading) {
    return (
      <div className="card" style={{ marginBottom: '20px' }}>
        <div className="card-header">
          <div className="skeleton skeleton-text" style={{ width: '150px' }} />
        </div>
        <div className="card-body">
          <div className="skeleton skeleton-box" style={{ height: '200px' }} />
        </div>
      </div>
    )
  }

  if (!data && !projectData) {
    return (
      <div className="card" style={{ marginBottom: '20px' }}>
        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '600' }}>📊 月度工时统计</h3>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <select 
              value={selectedYear} 
              onChange={(e) => onMonthChange(parseInt(e.target.value), selectedMonth)}
              style={{ 
                padding: '6px 12px', 
                borderRadius: '6px', 
                border: '1px solid #e5e7eb',
                background: 'white',
                fontSize: '14px'
              }}
            >
              {years.map(y => (
                <option key={y} value={y}>{y}年</option>
              ))}
            </select>
            <select 
              value={selectedMonth} 
              onChange={(e) => onMonthChange(selectedYear, parseInt(e.target.value))}
              style={{ 
                padding: '6px 12px', 
                borderRadius: '6px', 
                border: '1px solid #e5e7eb',
                background: 'white',
                fontSize: '14px'
              }}
            >
              {months.map(m => (
                <option key={m} value={m}>{m}月</option>
              ))}
            </select>
          </div>
        </div>
        <div className="card-body" style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
          暂无工时数据
        </div>
      </div>
    )
  }

  return (
    <div className="card" style={{ marginBottom: '20px' }}>
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '600' }}>📊 月度工时统计</h3>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <select 
            value={selectedYear} 
            onChange={(e) => onMonthChange(parseInt(e.target.value), selectedMonth)}
            style={{ 
              padding: '6px 12px', 
              borderRadius: '6px', 
              border: '1px solid #e5e7eb',
              background: 'white',
              fontSize: '14px'
            }}
          >
            {years.map(y => (
              <option key={y} value={y}>{y}年</option>
            ))}
          </select>
          <select 
            value={selectedMonth} 
            onChange={(e) => onMonthChange(selectedYear, parseInt(e.target.value))}
            style={{ 
              padding: '6px 12px', 
              borderRadius: '6px', 
              border: '1px solid #e5e7eb',
              background: 'white',
              fontSize: '14px'
            }}
          >
            {months.map(m => (
              <option key={m} value={m}>{m}月</option>
            ))}
          </select>
          <button 
            onClick={onExport}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              border: '1px solid #e5e7eb',
              background: 'white',
              fontSize: '14px',
              cursor: 'pointer'
            }}
          >
            📥 导出工时
          </button>
          <button 
            onClick={onExportHumanCost}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              border: '1px solid #e5e7eb',
              background: 'white',
              fontSize: '14px',
              cursor: 'pointer'
            }}
          >
            💰 导出人力成本
          </button>
        </div>
      </div>
      
      {/* 视图切换 */}
      <div style={{ 
        padding: '12px 20px', 
        borderBottom: '1px solid #e5e7eb',
        display: 'flex',
        gap: '12px'
      }}>
        <button
          onClick={() => onViewModeChange('employee')}
          style={{
            padding: '6px 16px',
            borderRadius: '20px',
            border: 'none',
            background: viewMode === 'employee' ? '#3b82f6' : 'transparent',
            color: viewMode === 'employee' ? 'white' : '#666',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: 500,
            transition: 'all 0.2s'
          }}
        >
          👤 人员维度
        </button>
        <button
          onClick={() => onViewModeChange('project')}
          style={{
            padding: '6px 16px',
            borderRadius: '20px',
            border: 'none',
            background: viewMode === 'project' ? '#3b82f6' : 'transparent',
            color: viewMode === 'project' ? 'white' : '#666',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: 500,
            transition: 'all 0.2s'
          }}
        >
          📁 项目维度
        </button>
      </div>
      
      <div className="card-body" style={{ padding: 0 }}>
        {/* 人员维度 */}
        {viewMode === 'employee' && data && (
          <>
            {/* 统计信息 */}
            <div style={{
              padding: '16px 20px',
              borderBottom: '1px solid #e5e7eb',
              display: 'flex',
              justifyContent: 'space-around',
              background: '#f9fafb'
            }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 600, color: '#3b82f6' }}>{data.working_days}</div>
                <div style={{ fontSize: '12px', color: '#6b7280' }}>总工作日</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 600, color: '#10b981' }}>{data.total_hours}h</div>
                <div style={{ fontSize: '12px', color: '#6b7280' }}>总工时</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 600, color: '#f59e0b' }}>{data.employee_count}</div>
                <div style={{ fontSize: '12px', color: '#6b7280' }}>参与人数</div>
              </div>
            </div>
          
            <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ background: '#f3f4f6', position: 'sticky', top: 0, zIndex: 1 }}>
                    <th style={{ padding: '10px', textAlign: 'left', borderBottom: '2px solid #e5e7eb', fontWeight: '600' }}>姓名</th>
                    <th style={{ padding: '10px', textAlign: 'right', borderBottom: '2px solid #e5e7eb', fontWeight: '600' }}>总工时</th>
                    <th style={{ padding: '10px', textAlign: 'right', borderBottom: '2px solid #e5e7eb', fontWeight: '600' }}>日报数</th>
                    <th style={{ padding: '10px', textAlign: 'right', borderBottom: '2px solid #e5e7eb', fontWeight: '600' }}>填报天数</th>
                    <th style={{ padding: '10px', textAlign: 'right', borderBottom: '2px solid #e5e7eb', fontWeight: '600' }}>缺失</th>
                  </tr>
                </thead>
                <tbody>
                  {data.employees.map(emp => (
                    <>
                      <tr 
                        key={emp.employee_name} 
                        style={{ cursor: 'pointer', background: expandedEmployee === emp.employee_name ? '#eff6ff' : 'white' }} 
                        onClick={() => setExpandedEmployee(expandedEmployee === emp.employee_name ? null : emp.employee_name)}
                      >
                        <td style={{ padding: '10px', borderBottom: '1px solid #e5e7eb', fontWeight: '500' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{
                              display: 'inline-block',
                              transition: 'transform 0.2s',
                              transform: expandedEmployee === emp.employee_name ? 'rotate(90deg)' : 'none'
                            }}>▶</span>
                            {emp.employee_name}
                          </div>
                        </td>
                        <td style={{ padding: '10px', textAlign: 'right', borderBottom: '1px solid #e5e7eb' }}>{emp.total_hours}h</td>
                        <td style={{ padding: '10px', textAlign: 'right', borderBottom: '1px solid #e5e7eb' }}>{emp.report_count}</td>
                        <td style={{ padding: '10px', textAlign: 'right', borderBottom: '1px solid #e5e7eb' }}>{emp.filled_days}</td>
                        <td style={{ 
                          padding: '10px', 
                          textAlign: 'right', 
                          borderBottom: '1px solid #e5e7eb',
                          color: emp.missing_days > 0 ? '#ef4444' : '#22c55e',
                          fontWeight: 600
                        }}>
                          {emp.missing_days > 0 ? `-${emp.missing_days}` : '✓'}
                        </td>
                      </tr>
                      {/* 展开显示项目分布 */}
                      {expandedEmployee === emp.employee_name && emp.projects && (
                        <tr key={`${emp.employee_name}-detail`}>
                          <td colSpan={5} style={{ padding: '0', background: '#f9fafb' }}>
                            <div style={{ padding: '12px 20px 12px 40px' }}>
                              <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '8px' }}>项目工时分布：</div>
                              {emp.projects.map((proj, idx) => (
                                <div 
                                  key={idx} 
                                  style={{ 
                                    display: 'flex', 
                                    alignItems: 'center', 
                                    justifyContent: 'space-between',
                                    padding: '6px 12px',
                                    marginBottom: '4px',
                                    background: 'white',
                                    borderRadius: '4px',
                                    fontSize: '12px'
                                  }}
                                >
                                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                    {proj.project_name}
                                  </span>
                                  <span style={{ fontWeight: 600, color: '#3b82f6', marginLeft: '12px' }}>
                                    {proj.hours}h ({proj.percent}%)
                                  </span>
                                </div>
                              ))}
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                  <tr style={{ background: '#f9fafb', fontWeight: '600' }}>
                    <td style={{ padding: '12px 10px', borderBottom: '2px solid #e5e7eb' }}>合计</td>
                    <td style={{ padding: '12px 10px', textAlign: 'right', borderBottom: '2px solid #e5e7eb' }}>{data.total_hours}h</td>
                    <td style={{ padding: '12px 10px', textAlign: 'right', borderBottom: '2px solid #e5e7eb' }}>{data.total_reports}</td>
                    <td style={{ padding: '12px 10px', textAlign: 'right', borderBottom: '2px solid #e5e7eb' }}>-</td>
                    <td style={{ padding: '12px 10px', textAlign: 'right', borderBottom: '2px solid #e5e7eb' }}>-</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </>
        )}
        
        {/* 项目维度 */}
        {viewMode === 'project' && projectData && (
          <>
            {/* 统计信息 */}
            <div style={{
              padding: '16px 20px',
              borderBottom: '1px solid #e5e7eb',
              display: 'flex',
              justifyContent: 'space-around',
              background: '#f9fafb'
            }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 600, color: '#3b82f6' }}>{projectData.working_days || 22}</div>
                <div style={{ fontSize: '12px', color: '#6b7280' }}>总工作日</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 600, color: '#10b981' }}>{projectData.grand_total}h</div>
                <div style={{ fontSize: '12px', color: '#6b7280' }}>总工时</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 600, color: '#f59e0b' }}>{projectData.employee_count || projectData.all_employees?.length || 0}</div>
                <div style={{ fontSize: '12px', color: '#6b7280' }}>参与人数</div>
              </div>
            </div>
          
            <div style={{ 
              maxHeight: '500px', 
              overflow: 'auto',
              position: 'relative'
            }}>
            <table style={{ 
              width: 'max-content',
              minWidth: '100%',
              borderCollapse: 'separate',
              borderSpacing: 0,
              fontSize: '13px'
            }}>
              <thead>
                <tr style={{ background: '#f3f4f6' }}>
                  <th style={{ 
                    padding: '10px', 
                    textAlign: 'left', 
                    borderBottom: '2px solid #3b82f6', 
                    fontWeight: '600',
                    position: 'sticky',
                    left: 0,
                    top: 0,
                    background: '#f3f4f6',
                    zIndex: 3,
                    minWidth: '150px'
                  }}>项目</th>
                  {projectData.all_employees.map(emp => (
                    <th key={emp} style={{ 
                      padding: '10px 12px', 
                      textAlign: 'right', 
                      borderBottom: '2px solid #3b82f6', 
                      fontWeight: '500', 
                      fontSize: '12px',
                      minWidth: '60px',
                      whiteSpace: 'nowrap',
                      top: 0,
                      position: 'sticky',
                      background: '#f3f4f6',
                      zIndex: 1
                    }}>{emp}</th>
                  ))}
                  <th style={{ 
                    padding: '10px 12px', 
                    textAlign: 'right', 
                    borderBottom: '2px solid #3b82f6', 
                    fontWeight: '600', 
                    color: '#3b82f6',
                    position: 'sticky',
                    right: 0,
                    top: 0,
                    background: '#f3f4f6',
                    zIndex: 3,
                    minWidth: '70px'
                  }}>合计(h)</th>
                </tr>
              </thead>
              <tbody>
                {/* 第一部分：正式项目 */}
                <tr style={{ background: '#eff6ff' }}>
                  <td style={{ padding: '8px 10px', fontWeight: '600', color: '#3b82f6', position: 'sticky', left: 0, background: '#eff6ff', zIndex: 2 }} colSpan={projectData.all_employees.length + 2}>
                    📁 正式项目（{projectData.official_project_count}个）
                  </td>
                </tr>
                {projectData.official_projects.map((proj, idx) => (
                  <tr key={`official-${idx}`} style={{ background: idx % 2 === 0 ? 'white' : '#fafafa' }}>
                    <td style={{ 
                      padding: '8px 10px', 
                      borderBottom: '1px solid #f3f4f6', 
                      maxWidth: '200px', 
                      overflow: 'hidden', 
                      textOverflow: 'ellipsis', 
                      whiteSpace: 'nowrap',
                      position: 'sticky',
                      left: 0,
                      background: idx % 2 === 0 ? 'white' : '#fafafa',
                      zIndex: 2,
                      fontWeight: '500'
                    }}>
                      {proj.project_name}
                    </td>
                    {projectData.all_employees.map(emp => (
                      <td key={emp} style={{ 
                        padding: '8px 12px', 
                        textAlign: 'right', 
                        borderBottom: '1px solid #f3f4f6', 
                        color: proj.members[emp] ? '#2563eb' : '#e5e7eb', 
                        fontSize: '12px',
                        cursor: proj.members[emp] ? 'pointer' : 'default',
                        textDecoration: proj.members[emp] ? 'underline dotted' : 'none'
                      }}
                      onClick={() => proj.members[emp] && loadHoursDetail(proj.project_name, emp)}
                      >
                        {proj.members[emp] ? `${proj.members[emp]}h` : '-'}
                      </td>
                    ))}
                    <td style={{ 
                      padding: '8px 12px', 
                      textAlign: 'right', 
                      borderBottom: '1px solid #f3f4f6', 
                      fontWeight: '600', 
                      color: '#3b82f6', 
                      fontSize: '12px',
                      position: 'sticky',
                      right: 0,
                      background: idx % 2 === 0 ? 'white' : '#fafafa',
                      zIndex: 2
                    }}>
                      {proj.total_hours}h
                    </td>
                  </tr>
                ))}
                {/* 正式项目合计 */}
                <tr style={{ background: '#dbeafe', fontWeight: '600' }}>
                  <td style={{ padding: '10px', borderBottom: '2px solid #3b82f6', color: '#3b82f6', position: 'sticky', left: 0, background: '#dbeafe', zIndex: 2 }}>【正式项目合计】</td>
                  {projectData.all_employees.map(emp => (
                    <td key={emp} style={{ padding: '10px 12px', textAlign: 'right', borderBottom: '2px solid #3b82f6', color: '#1f2937', fontSize: '12px' }}>
                      {projectData.official_employee_totals[emp] ? `${projectData.official_employee_totals[emp]}h` : '-'}
                    </td>
                  ))}
                  <td style={{ padding: '10px 12px', textAlign: 'right', borderBottom: '2px solid #3b82f6', color: '#3b82f6', fontSize: '14px', position: 'sticky', right: 0, background: '#dbeafe', zIndex: 2 }}>
                    {projectData.official_grand_total}h
                  </td>
                </tr>
                
                {/* 空行 */}
                <tr><td style={{ padding: '8px' }} colSpan={projectData.all_employees.length + 2}></td></tr>
                
                {/* 第二部分：基础工作 */}
                <tr style={{ background: '#fef3c7' }}>
                  <td style={{ padding: '8px 10px', fontWeight: '600', color: '#d97706', position: 'sticky', left: 0, background: '#fef3c7', zIndex: 2 }} colSpan={projectData.all_employees.length + 2}>
                    📋 基础工作（{projectData.other_work_count}个）
                  </td>
                </tr>
                {projectData.other_works.map((proj, idx) => (
                  <tr key={`other-${idx}`} style={{ background: idx % 2 === 0 ? 'white' : '#fafafa' }}>
                    <td style={{ 
                      padding: '8px 10px', 
                      borderBottom: '1px solid #f3f4f6', 
                      maxWidth: '200px', 
                      overflow: 'hidden', 
                      textOverflow: 'ellipsis', 
                      whiteSpace: 'nowrap',
                      position: 'sticky',
                      left: 0,
                      background: idx % 2 === 0 ? 'white' : '#fafafa',
                      zIndex: 2,
                      fontWeight: '500'
                    }}>
                      {proj.project_name}
                    </td>
                    {projectData.all_employees.map(emp => (
                      <td key={emp} style={{ 
                        padding: '8px 12px', 
                        textAlign: 'right', 
                        borderBottom: '1px solid #f3f4f6', 
                        color: proj.members[emp] ? '#2563eb' : '#e5e7eb', 
                        fontSize: '12px',
                        cursor: proj.members[emp] ? 'pointer' : 'default',
                        textDecoration: proj.members[emp] ? 'underline dotted' : 'none'
                      }}
                      onClick={() => proj.members[emp] && loadHoursDetail(proj.project_name, emp)}
                      >
                        {proj.members[emp] ? `${proj.members[emp]}h` : '-'}
                      </td>
                    ))}
                    <td style={{ 
                      padding: '8px 12px', 
                      textAlign: 'right', 
                      borderBottom: '1px solid #f3f4f6', 
                      fontWeight: '600', 
                      color: '#f59e0b', 
                      fontSize: '12px',
                      position: 'sticky',
                      right: 0,
                      background: idx % 2 === 0 ? 'white' : '#fafafa',
                      zIndex: 2
                    }}>
                      {proj.total_hours}h
                    </td>
                  </tr>
                ))}
                {/* 基础工作合计 */}
                <tr style={{ background: '#fef9c3', fontWeight: '600' }}>
                  <td style={{ padding: '10px', borderBottom: '2px solid #f59e0b', color: '#d97706', position: 'sticky', left: 0, background: '#fef9c3', zIndex: 2 }}>【基础工作合计】</td>
                  {projectData.all_employees.map(emp => (
                    <td key={emp} style={{ padding: '10px 12px', textAlign: 'right', borderBottom: '2px solid #f59e0b', color: '#1f2937', fontSize: '12px' }}>
                      {projectData.other_employee_totals[emp] ? `${projectData.other_employee_totals[emp]}h` : '-'}
                    </td>
                  ))}
                  <td style={{ padding: '10px 12px', textAlign: 'right', borderBottom: '2px solid #f59e0b', color: '#d97706', fontSize: '14px', position: 'sticky', right: 0, background: '#fef9c3', zIndex: 2 }}>
                    {projectData.other_grand_total}h
                  </td>
                </tr>
                
                {/* 空行 */}
                <tr><td style={{ padding: '8px' }} colSpan={projectData.all_employees.length + 2}></td></tr>
                
                {/* 总计 */}
                <tr style={{ background: '#e0e7ff', fontWeight: '700' }}>
                  <td style={{ padding: '12px 10px', borderBottom: '3px solid #6366f1', color: '#6366f1', position: 'sticky', left: 0, background: '#e0e7ff', zIndex: 2 }}>【总计】</td>
                  {projectData.all_employees.map(emp => (
                    <td key={emp} style={{ padding: '12px', textAlign: 'right', borderBottom: '3px solid #6366f1', color: '#1f2937', fontSize: '13px' }}>
                      {projectData.all_employee_totals[emp] ? `${projectData.all_employee_totals[emp]}h` : '-'}
                    </td>
                  ))}
                  <td style={{ padding: '12px', textAlign: 'right', borderBottom: '3px solid #6366f1', color: '#6366f1', fontSize: '16px', position: 'sticky', right: 0, background: '#e0e7ff', zIndex: 2 }}>
                    {projectData.grand_total}h
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          </>
        )}
        
        {/* 工时详情弹窗 */}
        {detailModal.show && (
          <div style={{
            position: 'fixed',
            top: 0,
            right: 0,
            bottom: 0,
            left: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            padding: '16px'
          }}
          onClick={() => setDetailModal(prev => ({ ...prev, show: false }))}
          >
            <div style={{
              background: 'white',
              borderRadius: '12px',
              maxWidth: '650px',
              width: '100%',
              maxHeight: '70vh',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)'
            }}
            onClick={e => e.stopPropagation()}
            >
              {/* 弹窗头部 */}
              <div style={{
                padding: '16px 20px',
                borderBottom: '1px solid #e5e7eb',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600 }}>📊 工时详情</h3>
                  <p style={{ margin: '4px 0 0', fontSize: '13px', color: '#6b7280' }}>
                    {detailModal.projectName} - {detailModal.employeeName}
                  </p>
                </div>
                <button
                  onClick={() => setDetailModal(prev => ({ ...prev, show: false }))}
                  style={{
                    border: 'none',
                    background: '#f3f4f6',
                    borderRadius: '6px',
                    padding: '6px 10px',
                    cursor: 'pointer',
                    fontSize: '14px'
                  }}
                >
                  ✕
                </button>
              </div>
              
              {/* 弹窗内容 */}
              <div style={{
                padding: '16px 20px',
                overflowY: 'auto',
                flex: 1
              }}>
                {detailModal.loading ? (
                  <div style={{ textAlign: 'center', padding: '40px' }}>
                    <span className="spinner"></span>
                    <p style={{ color: '#6b7280', marginTop: '12px' }}>加载中...</p>
                  </div>
                ) : detailModal.details.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '40px', color: '#9ca3af' }}>
                    暂无数据
                  </div>
                ) : (
                  <>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                      <thead>
                        <tr style={{ background: '#f9fafb' }}>
                          <th style={{ padding: '8px 12px', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>日期</th>
                          <th style={{ padding: '8px 12px', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>工作内容</th>
                          <th style={{ padding: '8px 12px', textAlign: 'right', borderBottom: '1px solid #e5e7eb', width: '60px' }}>工时</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detailModal.details.map((item: any, idx: number) => (
                          <tr key={idx} style={{ background: idx % 2 === 0 ? 'white' : '#fafafa' }}>
                            <td style={{ padding: '10px 12px', borderBottom: '1px solid #f3f4f6', whiteSpace: 'nowrap' }}>
                              {item.date}
                            </td>
                            <td style={{ padding: '10px 12px', borderBottom: '1px solid #f3f4f6' }}>
                              <div style={{ fontSize: '13px', color: '#1f2937' }}>
                                {item.content || item.project}
                              </div>
                              {item.time_range && (
                                <div style={{ fontSize: '11px', color: '#9ca3af', marginTop: '2px' }}>
                                  {item.time_range}
                                </div>
                              )}
                            </td>
                            <td style={{ padding: '10px 12px', borderBottom: '1px solid #f3f4f6', textAlign: 'right', fontWeight: '500', color: '#3b82f6' }}>
                              {item.hours}h
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    
                    {/* 合计 */}
                    <div style={{
                      marginTop: '16px',
                      padding: '12px 16px',
                      background: '#eff6ff',
                      borderRadius: '8px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center'
                    }}>
                      <span style={{ fontWeight: 600, color: '#1e40af' }}>
                        共 {detailModal.details.length} 条记录
                      </span>
                      <span style={{ fontWeight: 700, color: '#1e40af', fontSize: '16px' }}>
                        合计：{detailModal.totalHours}h
                      </span>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const isMobile = useIsMobile()

  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [projects, setProjects] = useState<Project[]>([])
  const [insight, setInsight] = useState<string>('')
  const [isLoading, setIsLoading] = useState(true)
  const [searchText, setSearchText] = useState('')

  // 月度工时统计状态
  const today = new Date()
  const [selectedYear, setSelectedYear] = useState(today.getFullYear())
  const [selectedMonth, setSelectedMonth] = useState(today.getMonth() + 1)
  const [monthlyHoursData, setMonthlyHoursData] = useState<EmployeeHoursData | null>(null)
  const [monthlyHoursLoading, setMonthlyHoursLoading] = useState(false)
  
  // 项目维度状态
  const [projectHoursData, setProjectHoursData] = useState<ProjectHoursData | null>(null)
  const [projectHoursLoading, setProjectHoursLoading] = useState(false)
  const [viewMode, setViewMode] = useState<'employee' | 'project'>('project')
  
  // 待评估版本状态
  const [pendingVersions, setPendingVersions] = useState<any[]>([])

  useEffect(() => {
    loadDashboardData()
    loadMonthlyHoursData(selectedYear, selectedMonth)
    loadProjectHoursData(selectedYear, selectedMonth)
    loadPendingVersions()
  }, [])

  const loadDashboardData = async () => {
    setIsLoading(true)
    try {
      const [overviewRes, projectsRes, insightRes] = await Promise.all([
        apiClient.get('/api/agent/dashboard/overview').then(r => r.data),
        apiClient.get('/api/agent/dashboard/projects').then(r => r.data),
        apiClient.get('/api/agent/dashboard/insight').then(r => r.data)
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
  
  // 加载月度工时数据（人员维度）
  const loadMonthlyHoursData = async (year: number, month: number) => {
    setMonthlyHoursLoading(true)
    try {
      const data = await api.getMonthlyEmployeeHours(year, month)
      setMonthlyHoursData(data)
    } catch (error) {
      console.error('加载月度工时数据失败:', error)
    } finally {
      setMonthlyHoursLoading(false)
    }
  }
  
  // 加载待评估版本
  const loadPendingVersions = async () => {
    try {
      const res = await apiClient.get('/api/agent/plan-versions/pending-evaluation')
      setPendingVersions(res.data.versions || [])
    } catch (error) {
      console.error('加载待评估版本失败:', error)
    }
  }
  
  // 加载项目维度数据
  const loadProjectHoursData = async (year: number, month: number) => {
    setProjectHoursLoading(true)
    try {
      const res = await apiClient.get('/api/agent/stats/monthly-project-hours', {
        params: { year, month }
      })
      setProjectHoursData(res.data)
    } catch (error: any) {
      console.error('加载项目维度数据失败:', error)
    } finally {
      setProjectHoursLoading(false)
    }
  }

  // 切换月份 - 局部刷新
  const handleMonthChange = (year: number, month: number) => {
    setSelectedYear(year)
    setSelectedMonth(month)
    loadMonthlyHoursData(year, month)
    loadProjectHoursData(year, month)
  }

  // 导出Excel
  const handleExportExcel = async () => {
    // 添加确认对话框
    const confirmed = await confirm({
      title: '导出工时统计',
      message: `确定要导出 ${selectedYear}年${selectedMonth}月 的工时统计数据吗？`,
      confirmText: '确认导出',
      cancelText: '取消',
      type: 'info'
    })
    
    if (!confirmed) return
    
    try {
      showToast('正在生成Excel...', 'info')
      const blob = await api.exportMonthlyEmployeeHours(selectedYear, selectedMonth)
      
      // 创建下载链接
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `正式项目工时统计_${selectedYear}年${selectedMonth}月.xlsx`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      
      showToast('导出成功', 'success')
    } catch (error: any) {
      console.error('导出Excel失败:', error)
      showToast('导出失败，请稍后重试', 'error')
    }
  }

  // 导出人力成本Excel
  const handleExportHumanCost = async () => {
    const confirmed = await confirm({
      title: '导出人力成本',
      message: `确定要导出 ${selectedYear}年${selectedMonth}月 的人力成本数据吗？`,
      confirmText: '确认导出',
      cancelText: '取消',
      type: 'info'
    })
    
    if (!confirmed) return
    
    try {
      showToast('正在生成Excel...', 'info')
      const blob = await api.exportHumanCost(selectedYear, selectedMonth)
      
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${selectedYear}年${selectedMonth}月研究院人员项目成本归集.xlsx`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      
      showToast('导出成功', 'success')
    } catch (error: any) {
      console.error('导出人力成本失败:', error)
      showToast('导出失败，请稍后重试', 'error')
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
      <SharedHeader />
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
      <SharedHeader />
      
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

        {/* 待评估版本提醒 */}
        {pendingVersions.length > 0 && (
          <div style={{ 
            background: 'linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)', 
            borderRadius: '8px', 
            border: '1px solid #f59e0b',
            marginBottom: '20px',
            padding: '16px 20px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
              <span style={{ fontSize: '24px' }}>⚠️</span>
              <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '600', color: '#92400e' }}>
                计划调整效果评估提醒
              </h3>
            </div>
            <div style={{ fontSize: '14px', color: '#78350f' }}>
              {pendingVersions.length} 个计划版本已调整超过7天，请评估调整效果
            </div>
            <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {pendingVersions.slice(0, 3).map((v: any) => (
                <div key={v.id} style={{ 
                  background: 'white', 
                  padding: '12px', 
                  borderRadius: '6px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '12px'
                }}>
                  <div>
                    <div style={{ fontWeight: 500, color: '#374151' }}>
                      {v.project_name} - {v.version_name}
                    </div>
                    <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>
                      {v.change_type} | 上传于 {v.upload_time} ({v.days_ago}天前)
                    </div>
                  </div>
                  <button
                    onClick={() => {
                      window.location.href = `/agent/plans?project_id=${v.project_id}`
                    }}
                    style={{
                      padding: '6px 12px',
                      background: '#f59e0b',
                      color: 'white',
                      borderRadius: '4px',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '13px'
                    }}
                  >
                    去评估
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 月度工时统计 */}
        <MonthlyHoursCard
          data={monthlyHoursData}
          projectData={projectHoursData}
          isLoading={monthlyHoursLoading || projectHoursLoading}
          selectedYear={selectedYear}
          selectedMonth={selectedMonth}
          onMonthChange={handleMonthChange}
          onExport={handleExportExcel}
          onExportHumanCost={handleExportHumanCost}
          viewMode={viewMode}
          onViewModeChange={setViewMode}
        />

        {/* 人员项目投入分析 */}
        <PersonAnalysisCard />

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
            box-shadow: 0 0 12px rgba(239, 68, 68, 0.8);
          }
          50% { 
            opacity: 0.7; 
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
